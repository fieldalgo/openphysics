# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The multiphysics document (contract D2): several physics on one geometry, and couplings.

    {"openphysics": ENVELOPE, "geometry": {...}, "materials": {...}, "mesh": {...},
     "physics": {"heat1": {"type": "thermal.steady2d", ...}, "modes1": {"type": "em.modes2d", ...}},
     "couplings": {"heat_to_optics": {"from": "heat1.temperature", "to": "modes1.temperature",
                                      "transfer": "same_mesh"}}}

A document whose physics entries belong to more than one kind, or that has ``couplings``,
declares the multiphysics envelope ``ENVELOPE`` instead of ``"0.3"``. A reader that does not
know it refuses it by its format check (``E-FORMAT``), so a coupling is never dropped.

Reading (``resolve_envelope``): each ``physics.<name>`` entry is resolved by the kind that
claims its type, as a single-physics format 0.3 *view* of the document: the shared
``geometry``, ``mesh``, ``results`` and ``study`` blocks, that one entry, and the material
records cut down to the properties that kind reads. Every kind validates its own entry as it
validates a single-physics document. This module then checks what only the whole document
holds: the couplings (ports, quantities, units, ``combine``, the transfer), the solve order
and its cycles (``study.loops``), and the thermo-optic model of every optical material whose
``temperature`` input is coupled.

Running (``run``): the physics are solved in the order the coupling graph gives (strongly
connected groups, then topological order; ties keep the order of the ``physics`` block).
A coupling's values are carried by ``galerkin.coupling.transfer`` (``same_mesh``: the
identity, with exact ``MeshSignature`` equality). The result is ``multiphysics-run-v1``.

The coupling hook of a kind (``PhysicsKind.coupling``) is internal to simcase in this release:
it is not part of the provider protocol, so the kinds of other providers do not take part in
couplings yet.
"""

from __future__ import annotations

import copy
import json
import re
import time
from decimal import Decimal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from physmat import units
from physmat.units import Diagnostic, Suggestion

from .diagnostics import DiagnosticList, DocumentError
from .reader import display_path

__all__ = ["ENVELOPE", "RESULT_FORMAT", "envelope_refusal", "resolve_envelope", "solve_order", "run",
           "MultiphysicsRunResult", "CouplingHook", "LoopNotConverged"]

#: the multiphysics envelope: the value of ``openphysics`` in a multiphysics document. The one
#: place it is spelled; every reader compares with this constant
ENVELOPE = "0.3/multiphysics.1"
#: the result identifier of a multiphysics run (single-physics results keep their own)
RESULT_FORMAT = "multiphysics-run-v1"
#: the transfers this release reads
TRANSFERS = ("same_mesh",)
#: the top-level keys of a multiphysics document
TOP_KEYS = ("openphysics", "name", "display_units", "geometry", "materials", "physics", "mesh", "study",
            "results", "couplings")
#: the thermo-optic model of a local material record
THERMO_OPTIC_KEYS = ("thermo_optic_coefficient", "reference_temperature")
#: the library materials that carry a thermo-optic model: dn/dT is physmat's
#: ``thermo_optic_dn_dT`` property, the reference temperature 300 K
LIBRARY_THERMO_OPTIC = ("Si", "SiO2")
LIBRARY_REFERENCE_TEMPERATURE = 300.0
#: the accepted iteration step a cycle without one is offered
LOOP_DEFAULTS = {"method": "fixed_point", "norm": "max_abs", "value": "1e-6", "max_iterations": 30,
                 "relaxation": 0.5}
LOOP_KEYS = ("physics", "method", "tolerance", "max_iterations", "relaxation")
#: the keys of a multiphysics ``study``
STUDY_KEYS = ("type", "parameter", "values", "tracking", "loops")
#: the quantity a tolerance of a port is read as: a change of a temperature is a temperature
#: difference (K or mK; a degC value would be read as an absolute temperature)
_DIFFERENCE = {"temperature": "temperature_difference"}
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
#: the registry dimensions of a power quantity: W, W/m, W/m^2 and W/m^3 (M L^k T^-3)
_POWER = [{"M": 1, "L": k, "T": -3} for k in (2, 1, 0, -1)]


# ---------------------------------------------------------------------------------------------
# the coupling hook

@dataclass(frozen=True)
class CouplingHook:
    """How a kind takes part in a multiphysics run (internal to simcase in this release).

    ``prepare(doc, name) -> state`` builds what the solve of ``physics.<name>`` needs (its mesh)
    from the multiphysics document ``doc`` and its entry's single-physics view
    ``doc.views[name]``; ``state.mesh`` is the ``galerkin.mesh.Mesh`` its input fields live on
    (None for a kind without input ports) and ``state.triangle_regions`` the region name of each
    triangle. ``solve(state, inputs, verbose) -> (result, outputs)`` solves with ``inputs``
    (input port name -> ``galerkin.coupling.Field`` on ``state.mesh``) and returns the kind's
    usual result object and its output fields (output port name -> Field). ``check(view, name,
    coupled, materials)`` returns the diagnostics of the entry ``name`` under the coupled input
    ports ``coupled`` (``materials`` is the document's resolved SI ``materials`` block, with the
    thermo-optic values).
    ``ignored_mesh_keys`` are the ``mesh`` keys the kind does not read (it meshes as if they
    were absent). ``ports`` describe the kind's ports when no provider manifest does (a kind
    registered outside a provider)."""
    prepare: Any
    solve: Any
    check: Any = None
    ignored_mesh_keys: frozenset = frozenset()
    ports: tuple = ()
    #: the output ports ``solve`` produces; None for every output port of the kind
    outputs: frozenset | None = None
    #: concrete types of a multi-type kind that support this hook
    types: frozenset | None = None


def ports_of(kind) -> dict[str, dict]:
    """``{port name: port}`` of a kind: its provider manifest's ports, else its hook's."""
    from . import providers, registry
    owner = registry._OWNERS.get(kind.name)
    if owner is not None:
        for info in providers.providers():
            if info.name == owner and info.manifest:
                return {p["name"]: p for p in info.manifest["kinds"][kind.name]["ports"]}
    hook = getattr(kind, "coupling", None)
    return {p["name"]: dict(p) for p in (hook.ports if hook is not None else ())}


# ---------------------------------------------------------------------------------------------
# the envelope

def _kinds_of(tree) -> list:
    from .registry import kind_of_type
    physics = tree.get("physics") if isinstance(tree, dict) else None
    out = []
    for entry in (physics.values() if isinstance(physics, dict) else ()):
        kind = kind_of_type(entry["type"]) if isinstance(entry, dict) and isinstance(entry.get("type"), str) else None
        if kind is not None and kind not in out:
            out.append(kind)
    return out


def envelope_refusal(tree: dict) -> Diagnostic | None:
    """``E-FORMAT`` at ``openphysics`` for a format 0.3 document that needs the multiphysics
    envelope: it has ``couplings``, or physics entries of more than one kind. None otherwise."""
    kinds = _kinds_of(tree)
    if isinstance(tree.get("couplings"), dict) and tree["couplings"]:
        why = "has couplings"
    elif len(kinds) > 1:
        why = "has physics of more than one kind (" + ", ".join(k.name for k in kinds) + ")"
    else:
        return None
    return Diagnostic("E-FORMAT", "openphysics",
                      f'the document {why}, which a single-physics "0.3" document cannot hold; declare the '
                      f'multiphysics envelope: write "openphysics": "{ENVELOPE}" (docs/packages/simcase/'
                      'multiphysics_document.md)')


# ---------------------------------------------------------------------------------------------
# reading

class _Checks:
    """The diagnostics of the whole document, appended in order."""

    def __init__(self, diagnostics: DiagnosticList):
        self.diagnostics = diagnostics

    def add(self, code: str, path, message: str, **extra) -> None:
        where = display_path(path) if isinstance(path, list) else path
        if code == "E-CONTRACT" and where and not message.startswith(where):
            message = f"{where}: {message}"
        self.diagnostics.append(Diagnostic(code, where, message, **extra))


def resolve_envelope(tree: dict, result) -> Any:
    """Resolve a multiphysics document into ``result`` (``resolve.Resolution``)."""
    from . import resolve
    from .registry import kind_of_type
    checks = _Checks(result.diagnostics)
    result.kind = KIND
    unknown = [k for k in tree if k not in TOP_KEYS]
    for k in unknown:
        checks.add("E-KEY-UNKNOWN", [k], f'unknown key "{k}" in the document. Keys here: {", ".join(TOP_KEYS)}.')
    for required in ("geometry", "physics"):
        if required not in tree:
            checks.add("E-KEY-MISSING", [required], f"the document needs {required}")
    if result.diagnostics.errors:
        return result
    physics = tree["physics"]
    if not isinstance(physics, dict) or not physics:
        checks.add("E-VALUE-FORM", ["physics"], "physics is an object with one entry per physics")
        return result
    bad = resolve._unknown_type(tree)
    if bad is not None:
        result.diagnostics.append(bad)
        return result
    for name, entry in physics.items():
        path = ["physics", name]
        if not isinstance(entry, dict) or "type" not in entry:
            checks.add("E-KEY-MISSING", path + ["type"], f"{display_path(path)} needs type")
            continue
        if not isinstance(name, str) or not _NAME.match(name):
            checks.add("E-CONTRACT", path, "a physics name is an identifier (letters, digits and _): a coupling "
                                           "and a study refer to the physics by this name")
        kind = kind_of_type(entry["type"])
        hook = getattr(kind, "coupling", None)
        if hook is None or (hook.types is not None and entry["type"] not in hook.types):
            checks.add("E-CONTRACT", path + ["type"], f'"{entry["type"]}" is not coupled in this release; run it '
                                                      'as its own "0.3" document')
    if result.diagnostics.errors:
        return result
    kinds = _kinds_of(tree)
    if not tree.get("couplings") and len(kinds) == 1:
        checks.add("E-FORMAT", "openphysics", f'the document has no couplings and its physics are all of kind '
                                              f'{kinds[0].name}; write "openphysics": "0.3", the single-physics form')
        return result
    from . import slots
    if slots.geometry_form(tree["geometry"]) != "v1":
        checks.add("E-CONTRACT", ["geometry"], "a multiphysics document takes a version 1 geometry block "
                                               "(\"version\": 1, components with their length_unit): the physics "
                                               "share its regions (docs/packages/simcase/geometry_document.md)")
        return result
    _check_blocks(tree, checks)
    if result.diagnostics.errors:
        return result
    incoming = _coupled_inputs(tree)
    views = {}
    for name, entry in physics.items():
        view = _view_tree(tree, name, kind_of_type(entry["type"]))
        views[name] = resolve.resolve_tree(view, from_python=False,
                                           coupled_inputs=incoming.get(name, frozenset()))
        _merge_diagnostics(result.diagnostics, views[name].diagnostics)
    result.views = views
    if result.diagnostics.errors:
        return result
    _merge(result, tree, views)
    _check_materials(tree, result, checks)
    graph = _check_couplings(tree, views, checks)
    if graph is not None:
        _check_order(tree, graph, checks)
        _check_hooks(tree, views, checks, result.si["materials"])
    if not result.diagnostics.errors:
        from .schema import Document
        doc = Document._from_resolution(result)
        doc.views = {name: r.document() for name, r in views.items()}
        result._document = doc
    return result


def _merge_diagnostics(into: DiagnosticList, found) -> None:
    seen = {(d.code, d.path, d.message) for d in into}
    for d in found:
        if (d.code, d.path, d.message) not in seen:
            into.append(d)
            seen.add((d.code, d.path, d.message))


def _check_blocks(tree, checks: _Checks) -> None:
    """The blocks the views do not see: ``results`` (save_fields and plots only), ``study``
    (``single``, or a sweep of a value of one physics entry) and the shape of ``couplings``."""
    results = tree.get("results")
    if results is not None:
        if not isinstance(results, dict):
            checks.add("E-VALUE-FORM", ["results"], "expected an object")
        else:
            for k, v in results.items():
                if k not in ("save_fields", "plots"):
                    checks.add("E-KEY-UNKNOWN", ["results", k], f'unknown key "{k}" in results. A multiphysics '
                                                                'document takes save_fields and plots here; '
                                                                "each physics writes its own result files")
                elif not isinstance(v, bool):
                    checks.add("E-VALUE-FORM", ["results", k], "expected true or false")
    study = tree.get("study")
    if study is not None:
        if not isinstance(study, dict):
            checks.add("E-VALUE-FORM", ["study"], "expected an object")
        else:
            for k in study:
                if k not in STUDY_KEYS:
                    checks.add("E-KEY-UNKNOWN", ["study", k], f'unknown key "{k}" in study. Keys here: '
                                                              + ", ".join(STUDY_KEYS) + ".")
            kind = study.get("type", "single")
            if kind == "single":
                for k in ("parameter", "values", "tracking"):
                    if k in study:
                        checks.add("E-CONTRACT", ["study", k], f'study.{k} belongs to a sweep; a "single" study '
                                                               "solves once")
            if kind == "sweep":
                for k in ("parameter", "values"):
                    if k not in study:
                        checks.add("E-KEY-MISSING", ["study", k], f"a sweep needs study.{k}")
                if "parameter" in study and not isinstance(study["parameter"], str):
                    checks.add("E-VALUE-FORM", ["study", "parameter"], "expected the dotted path of the swept value")
            if not isinstance(kind, str) or kind not in ("single", "sweep"):
                checks.add("E-CONTRACT", ["study", "type"], f"{json.dumps(kind, default=str)} is not a study of a multiphysics "
                                                            'document, which reads "single" and "sweep"')
            parameter = study.get("parameter")
            if kind == "sweep" and isinstance(parameter, str):
                parts = parameter.split(".")
                if len(parts) < 3 or parts[0] != "physics" or parts[1] not in tree["physics"]:
                    checks.add("E-CONTRACT", ["study", "parameter"], f"{parameter!r} names no value of a physics "
                                                                     "entry; a multiphysics sweep varies one value "
                                                                     "under physics.<name>.")
            if "loops" in study and not isinstance(study["loops"], list):
                checks.add("E-VALUE-FORM", ["study", "loops"], "expected a list of accepted loops")
    couplings = tree.get("couplings", {})
    if not isinstance(couplings, dict):
        checks.add("E-VALUE-FORM", ["couplings"], "expected an object with one entry per coupling")
        return
    for cname, c in couplings.items():
        path = ["couplings", cname]
        if not isinstance(cname, str) or not _NAME.match(cname):
            checks.add("E-CONTRACT", path, "a coupling name is an identifier (letters, digits and _)")
        if not isinstance(c, dict):
            checks.add("E-VALUE-FORM", path, "expected an object with from, to and transfer")
            continue
        for k in c:
            if k not in ("from", "to", "transfer"):
                checks.add("E-KEY-UNKNOWN", path + [k], f'unknown key "{k}" in {display_path(path)}. Keys here: '
                                                        "from, to, transfer.")
        for k in ("from", "to", "transfer"):
            if k not in c:
                checks.add("E-KEY-MISSING", path + [k], f"{display_path(path)} needs {k}")
            elif not isinstance(c[k], str):
                checks.add("E-VALUE-FORM", path + [k], "expected a string")


def _view_tree(tree: dict, name: str, kind) -> dict:
    """The single-physics format 0.3 tree the kind of ``physics.<name>`` reads."""
    from .slots import MATERIAL_PROPERTIES, table_for
    view = {"openphysics": "0.3"}
    for k in ("name", "display_units", "geometry", "mesh"):
        if k in tree:
            view[k] = copy.deepcopy(tree[k])
    from .registry import kind_of_type
    reads = set((table_for(kind).policy().get("reads") or {}).get(tree["physics"][name]["type"], []))
    others = set()
    for entry in tree["physics"].values():
        physics_type = entry["type"]
        other = kind_of_type(physics_type)
        others.update((table_for(other).policy().get("reads") or {}).get(physics_type, []))
    if isinstance(tree.get("materials"), dict):
        materials = {}
        for mname, record in tree["materials"].items():
            if not isinstance(record, dict):
                materials[mname] = copy.deepcopy(record)
                continue
            # a property another physics of the document reads is that physics' to check; a
            # property no physics reads stays, so that its value is checked and reported unused
            materials[mname] = {k: copy.deepcopy(v) for k, v in record.items()
                                if k not in THERMO_OPTIC_KEYS
                                and not (k in MATERIAL_PROPERTIES and k not in reads and k in others)}
        view["materials"] = materials
    view["physics"] = {name: copy.deepcopy(tree["physics"][name])}
    study = tree.get("study") if isinstance(tree.get("study"), dict) else {}
    parameter = study.get("parameter")
    if study.get("type") == "sweep" and isinstance(parameter, str) and parameter.split(".")[1:2] == [name]:
        view["study"] = {k: copy.deepcopy(v) for k, v in study.items() if k != "loops"}
    else:
        view["study"] = {"type": "single"}
    results = tree.get("results") if isinstance(tree.get("results"), dict) else {}
    view["results"] = {"save_fields": results.get("save_fields", True), "plots": results.get("plots", False)}
    return view


def _merge(result, tree, views) -> None:
    """The document-level resolution: the views' resolved values under one tree."""
    first = next(iter(views.values()))
    result.table = first.table
    result.geometry_model, result.geometry_flat = first.geometry_model, first.geometry_flat
    result.extent = list(first.extent)
    si = {"openphysics": ENVELOPE}
    for k in ("name", "display_units", "geometry", "mesh"):
        if first.si is not None and k in first.si:
            si[k] = copy.deepcopy(first.si[k])
    materials = {}
    for r in views.values():
        for mname, record in ((r.si or {}).get("materials") or {}).items():
            materials.setdefault(mname, {}).update(copy.deepcopy(record))
    si["materials"] = materials
    si["physics"] = {name: copy.deepcopy(r.si["physics"][name]) for name, r in views.items()}
    study = tree.get("study") if isinstance(tree.get("study"), dict) else {}
    si["study"] = {"type": study.get("type", "single")}
    for name, r in views.items():
        if r.si["study"].get("type") == "sweep":
            si["study"] = copy.deepcopy(r.si["study"])
    if "loops" in study:
        si["study"]["loops"] = copy.deepcopy(study["loops"])
    results = tree.get("results") if isinstance(tree.get("results"), dict) else {}
    si["results"] = {"save_fields": results.get("save_fields", True), "plots": results.get("plots", False)}
    for key, value in (("save_fields", True), ("plots", False)):
        if key not in results:
            result.defaults_applied.append({"path": f"results.{key}", "value": value,
                                            "reason": "structural default of multiphysics documents"})
    if "study" not in tree:
        result.defaults_applied.append({"path": "study", "value": {"type": "single"},
                                        "reason": "structural default: one solve"})
    si["couplings"] = copy.deepcopy(tree.get("couplings", {}))
    result.si = si
    seen = {d["path"] for d in result.defaults_applied}
    for r in views.values():
        for d in r.defaults_applied:
            if d["path"] not in seen and not d["path"].startswith(("results", "study", "name")):
                result.defaults_applied.append(d)
                seen.add(d["path"])
        for attr in ("exact", "pm", "authored", "conversions", "inputs", "refs", "accepts", "estimates"):
            getattr(result, attr).update(getattr(r, attr))
        for fix in r.spelling_fixes:
            if fix not in result.spelling_fixes:
                result.spelling_fixes.append(fix)


def _check_materials(tree, result, checks: _Checks) -> None:
    """The thermo-optic keys of the local records: their values, both or none, and a note when
    no coupled temperature input reads them."""
    for mname, record in (tree.get("materials") or {}).items():
        if not isinstance(record, dict):
            continue
        given = [k for k in THERMO_OPTIC_KEYS if k in record]
        quantities = {"thermo_optic_coefficient": "thermo_optic_coefficient",
                      "reference_temperature": "reference_temperature"}
        for k in given:
            path = ["materials", mname, k]
            try:
                c = units.convert(record[k], quantities[k], path=display_path(path))
            except TypeError:
                checks.add("E-VALUE-FORM", path, f"{k} is a value with its unit, such as "
                                                 + ('"1.8e-4 1/K"' if k == "thermo_optic_coefficient" else '"300 K"'))
                continue
            for d in c.diagnostics:
                result.diagnostics.append(d)
            if c.ok:
                result.si["materials"].setdefault(mname, {})[k] = c.value
                result.exact[display_path(path)] = c.exact
                result.authored[display_path(path)] = record[k]
                result.inputs[display_path(path)] = {"authored": record[k], "value": c.value, "unit": c.unit}
        if len(given) == 1:
            missing = next(k for k in THERMO_OPTIC_KEYS if k not in record)
            checks.add("E-KEY-MISSING", ["materials", mname, missing],
                       f"materials.{mname} gives {given[0]} without {missing}; the thermo-optic model "
                       f"n = n0 + (dn/dT)(T - T_ref) needs both")


def _port(spec, checks: _Checks, path, physics, views, direction):
    """``(physics name, port name, port)`` of a ``<physics>.<port>`` string, or None (reported)."""
    from .registry import kind_of_type
    if "." not in spec:
        checks.add("E-VALUE-FORM", path, f'{json.dumps(spec, default=str)} is not "<physics name>.<{direction} port>"')
        return None
    pname, port = spec.split(".", 1)
    if pname not in physics:
        checks.add("E-CONTRACT", path, f"{json.dumps(spec, default=str)} names the physics {pname!r}, which this document does "
                                       "not have; physics here: " + ", ".join(physics))
        return None
    kind = kind_of_type(physics[pname]["type"])
    ports = ports_of(kind)
    if port not in ports:
        shown = [n for n, p in ports.items() if p["direction"] == direction]
        checks.add("E-CONTRACT", path, f"{pname} ({physics[pname]['type']}) has no port {port!r}; its {direction} "
                                       "ports: " + (", ".join(shown) if shown else "none"))
        return None
    if ports[port]["direction"] != direction:
        checks.add("E-CONTRACT", path, f"{spec} is an {ports[port]['direction']} port; "
                                       f"{'from' if direction == 'output' else 'to'} names an {direction} port")
        return None
    produced = kind.coupling.outputs
    if direction == "output" and produced is not None and port not in produced:
        checks.add("E-CONTRACT", path, f"{spec} is an output {kind.name} saves but does not couple in this release; "
                                       "its coupled outputs: " + (", ".join(sorted(produced)) or "none"))
        return None
    return pname, port, ports[port]


@dataclass
class _Edge:
    name: str
    source: str
    output: str
    target: str
    input: str
    quantity: str
    unit: str


def _check_couplings(tree, views, checks: _Checks):
    """Every coupling's ports, quantities, units, ``combine`` and transfer; the edges, or None."""
    from .registry import kind_of_type
    physics = tree["physics"]
    edges, into = [], {}
    for cname, c in (tree.get("couplings") or {}).items():
        path = ["couplings", cname]
        source = _port(c["from"], checks, path + ["from"], physics, views, "output")
        target = _port(c["to"], checks, path + ["to"], physics, views, "input")
        if source is None or target is None:
            continue
        if source[0] == target[0]:
            checks.add("E-CONTRACT", path, f"couples {source[0]} to itself; a coupling carries a field from one "
                                           "physics to another")
            continue
        out, inp = source[2], target[2]
        if out["quantity"] != inp["quantity"]:
            checks.add("E-COUPLING-PAIR", display_path(path),
                       f"{c['from']} carries {out['quantity']} and {c['to']} takes {inp['quantity']}; the two "
                       "ports of a coupling carry the same quantity")
            continue
        if out["unit"] != inp["unit"]:
            checks.add("E-COUPLING-PAIR", display_path(path),
                       f"{c['from']} is in {out['unit']!r} and {c['to']} in {inp['unit']!r}; a coupling does not "
                       "convert units, so the two ports give the same unit string")
            continue
        if not (out["location"] == inp["location"] or (out["location"], inp["location"]) == ("node", "element")):
            checks.add("E-COUPLING-PAIR", display_path(path),
                       f"{c['from']} is a {out['location']} field and {c['to']} takes a {inp['location']} field; "
                       "a coupling carries a node field to a node or an element input, or an element field to an "
                       "element input")
            continue
        if c["transfer"] not in TRANSFERS:
            checks.add("E-CONTRACT", path + ["transfer"], f"{json.dumps(c['transfer'], default=str)} is not a transfer this "
                                                          'release reads; write "same_mesh" (the identity on one '
                                                          "mesh)")
            continue
        sk, tk = kind_of_type(physics[source[0]]["type"]), kind_of_type(physics[target[0]]["type"])
        mesh = tree.get("mesh") if isinstance(tree.get("mesh"), dict) else {}
        for key in sorted(mesh):
            ignoring = [n for n, k in ((source[0], sk), (target[0], tk)) if key in k.coupling.ignored_mesh_keys]
            if len(ignoring) == 1:
                reader = target[0] if ignoring[0] == source[0] else source[0]
                checks.add("E-CONTRACT", path + ["transfer"],
                           f"same_mesh needs one mesh, but {ignoring[0]} does not read mesh.{key}, which {reader} "
                           f"reads, so {source[0]} and {target[0]} would build different meshes; remove mesh.{key} "
                           "(grade the mesh with mesh.controls, which every physics reads)")
        previous = into.get((target[0], target[1]), [])
        if inp.get("combine", "single") == "single" and previous:
            checks.add("E-CONTRACT", path + ["to"], f"{c['to']} takes one coupling (combine \"single\"); "
                                                    f"{previous[0]} already couples into it")
            continue
        into.setdefault((target[0], target[1]), []).append(cname)
        edges.append(_Edge(cname, source[0], source[1], target[0], target[1], out["quantity"], out["unit"]))
    if checks.diagnostics.errors:
        return None
    return edges


def solve_order(names: list[str], edges) -> list[list[str]]:
    """The strongly connected groups of the coupling graph in topological order; ties keep the
    order of ``names`` (the ``physics`` block), and so do the members of a group."""
    index = {n: i for i, n in enumerate(names)}
    succ = {n: [] for n in names}
    for e in edges:
        if e.target not in succ[e.source]:
            succ[e.source].append(e.target)
    # Tarjan, iterative
    counter, stack, on, low, num, groups = [0], [], set(), {}, {}, []

    def visit(root):
        work = [(root, iter(succ[root]))]
        num[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            w = next(it, None)
            if w is None:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == num[v]:
                    group = []
                    while True:
                        x = stack.pop()
                        on.discard(x)
                        group.append(x)
                        if x == v:
                            break
                    groups.append(sorted(group, key=index.get))
            elif w not in num:
                num[w] = low[w] = counter[0]
                counter[0] += 1
                stack.append(w)
                on.add(w)
                work.append((w, iter(succ[w])))
            elif w in on:
                low[v] = min(low[v], num[w])

    for n in names:
        if n not in num:
            visit(n)
    group_of = {n: i for i, g in enumerate(groups) for n in g}
    preds = {i: set() for i in range(len(groups))}
    for e in edges:
        a, b = group_of[e.source], group_of[e.target]
        if a != b:
            preds[b].add(a)
    order, done = [], set()
    while len(order) < len(groups):
        ready = [i for i in range(len(groups)) if i not in done and preds[i] <= done]
        pick = min(ready, key=lambda i: min(index[n] for n in groups[i]))
        order.append(groups[pick])
        done.add(pick)
    return order


def _loop_proposal(group, edges, tree) -> dict:
    """The accepted-loop entry a cycle without one is offered: its first member's first output
    inside the cycle carries the tolerance, in that port's unit."""
    from .registry import kind_of_type
    inside = [e for e in edges if e.source in group and e.target in group]
    first = min(inside, key=lambda e: (group.index(e.source), e.name))
    unit = ports_of(kind_of_type(tree["physics"][first.source]["type"]))[first.output]["unit"]
    return {"physics": list(group), "method": LOOP_DEFAULTS["method"],
            "tolerance": {"port": f"{first.source}.{first.output}", "norm": LOOP_DEFAULTS["norm"],
                          "value": f"{LOOP_DEFAULTS['value']} {unit}" if unit != "1" else LOOP_DEFAULTS["value"]},
            "max_iterations": LOOP_DEFAULTS["max_iterations"], "relaxation": LOOP_DEFAULTS["relaxation"]}


def _check_order(tree, edges, checks: _Checks) -> None:
    """The cycles of the coupling graph against ``study.loops``, and every loop entry."""
    from .registry import kind_of_type
    names = list(tree["physics"])
    groups = [g for g in solve_order(names, edges) if len(g) > 1]
    study = tree.get("study") if isinstance(tree.get("study"), dict) else {}
    loops = study.get("loops") if isinstance(study.get("loops"), list) else []
    claimed = {}
    for i, loop in enumerate(loops):
        path = ["study", "loops", i]
        if not isinstance(loop, dict):
            checks.add("E-VALUE-FORM", path, "expected an object: physics, method, tolerance, max_iterations, "
                                             "relaxation")
            continue
        for k in loop:
            if k not in LOOP_KEYS:
                checks.add("E-KEY-UNKNOWN", path + [k], f'unknown key "{k}" in {display_path(path)}. Keys here: '
                                                        + ", ".join(LOOP_KEYS) + ".")
        missing = [k for k in LOOP_KEYS if k not in loop]
        for k in missing:
            checks.add("E-KEY-MISSING", path + [k], f"{display_path(path)} needs {k}")
        if missing:
            continue
        members = loop["physics"]
        if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
            checks.add("E-VALUE-FORM", path + ["physics"], "expected a list of physics names")
            continue
        group = next((g for g in groups if sorted(g) == sorted(members)), None)
        if group is None:
            shown = "; ".join(", ".join(g) for g in groups) or "none"
            checks.add("E-CONTRACT", path + ["physics"], f"{', '.join(members)} is not a cycle of the couplings, so "
                                                         f"it takes no loop; the cycles of this document: {shown}")
            continue
        key = tuple(group)
        if key in claimed:
            checks.add("E-CONTRACT", path, f"the cycle {', '.join(group)} already has its loop at "
                                           f"study.loops[{claimed[key]}]")
            continue
        claimed[key] = i
        if loop["method"] != "fixed_point":
            checks.add("E-CONTRACT", path + ["method"], f"{json.dumps(loop['method'], default=str)} is not a loop method this "
                                                        'release reads; write "fixed_point"')
        n = loop["max_iterations"]
        if isinstance(n, bool) or not isinstance(n, int) or n < 2:
            checks.add("E-VALUE-FORM", path + ["max_iterations"], "expected a whole number of at least 2 (the first "
                                                                  "residual is measured at the second iteration)")
        w = loop["relaxation"]
        if isinstance(w, bool) or not isinstance(w, (int, float, Decimal)) or not 0 < float(w) <= 1:
            checks.add("E-DOMAIN", display_path(path + ["relaxation"]),
                       "the relaxation w of x <- (1 - w) x + w G(x) is a number in (0, 1]")
        tol = loop["tolerance"]
        tpath = path + ["tolerance"]
        if not isinstance(tol, dict):
            checks.add("E-VALUE-FORM", tpath, "expected an object: port, norm, value")
            continue
        for k in ("port", "norm", "value"):
            if k not in tol:
                checks.add("E-KEY-MISSING", tpath + [k], f"{display_path(tpath)} needs {k}")
        if any(k not in tol for k in ("port", "norm", "value")):
            continue
        if tol["norm"] != "max_abs":
            checks.add("E-CONTRACT", tpath + ["norm"], f'{json.dumps(tol["norm"], default=str)} is not a norm this release '
                                                       'reads; write "max_abs"')
        spec = tol["port"]
        pname, _, port = spec.partition(".") if isinstance(spec, str) else ("", "", "")
        if pname not in group:
            checks.add("E-CONTRACT", tpath + ["port"], f"{json.dumps(spec, default=str)} is not an output of a physics of this "
                                                       f"loop ({', '.join(group)})")
            continue
        ports = ports_of(kind_of_type(tree["physics"][pname]["type"]))
        if port not in ports or ports[port]["direction"] != "output":
            checks.add("E-CONTRACT", tpath + ["port"], f"{pname} has no output port {port!r}")
            continue
        carried = sorted(f"{e.source}.{e.output}" for e in edges if e.source in group and e.target in group)
        if spec not in carried:
            checks.add("E-CONTRACT", tpath + ["port"], f"{spec} is not carried by a coupling inside the loop; the "
                                                       "residual is measured on a coupled field: "
                                                       + ", ".join(dict.fromkeys(carried)))
            continue
        try:
            c = units.convert(tol["value"], _DIFFERENCE.get(ports[port]["quantity"], ports[port]["quantity"]),
                              path=display_path(tpath + ["value"]))
        except TypeError:
            checks.add("E-VALUE-FORM", tpath + ["value"], "expected a value with the port's unit")
            continue
        for d in c.diagnostics:
            checks.diagnostics.append(d)
        if c.ok and not c.value > 0:
            checks.add("E-DOMAIN", display_path(tpath + ["value"]), "the tolerance is a positive value")
    for group in groups:
        if tuple(group) not in claimed:
            proposal = _loop_proposal(group, edges, tree)
            through = sorted(e.name for e in edges if e.source in group and e.target in group)
            checks.add("E-COUPLING-CYCLE", "study.loops",
                       f"{' and '.join(group) if len(group) == 2 else ', '.join(group)} form a cycle (couplings "
                       f"{', '.join(through)}) with no accepted loop; a cycle runs only with an iteration step. "
                       f"Add to study.loops: {json.dumps(proposal)}",
                       suggestions=(Suggestion(proposal, None, None, "1"),))


def _coupled_inputs(tree):
    coupled = {}
    for c in (tree.get("couplings") or {}).values():
        pname, _, port = c["to"].partition(".")
        coupled.setdefault(pname, set()).add(port)
    return {name: frozenset(ports) for name, ports in coupled.items()}


def _check_hooks(tree, views, checks: _Checks, materials: dict) -> None:
    """Each kind's own checks of its entry under its coupled inputs."""
    from .registry import kind_of_type
    coupled = _coupled_inputs(tree)
    for name, r in views.items():
        hook = kind_of_type(tree["physics"][name]["type"]).coupling
        if hook.check is not None:
            for d in hook.check(r.document(), name, coupled.get(name, set()), materials):
                checks.diagnostics.append(d)
    read = set()
    for name, ports in coupled.items():
        if "temperature" in ports and tree["physics"].get(name, {}).get("type") == "em.modes2d":
            view = views[name].document()
            if view is not None:
                read |= set(region_material_refs(view))
    for mname, record in (tree.get("materials") or {}).items():
        if isinstance(record, dict) and any(k in record for k in THERMO_OPTIC_KEYS) and mname not in read:
            for k in THERMO_OPTIC_KEYS:
                if k in record:
                    checks.add("I-UNUSED-PROPERTY", ["materials", mname, k],
                               f"no coupled temperature input reads {k}; it is checked and not used")


def region_material_refs(view) -> list[str]:
    """The material references of a view's version 1 component: its background's, then its
    regions', each once, in order (void regions have none)."""
    out = []
    for ref in [view.background.get("material")] + [r.get("material") for r in view.regions()]:
        if ref is not None and ref not in out:
            out.append(ref)
    return out


def thermo_optic(materials: dict, ref: str) -> tuple[float, float] | None:
    """``(dn/dT in 1/K, T_ref in K)`` of a material reference, or None when it has no model;
    ``materials`` is a multiphysics document's resolved ``materials`` block (``doc.si``)."""
    if ref.startswith("physmat:"):
        name = ref[len("physmat:"):]
        if name not in LIBRARY_THERMO_OPTIC:
            return None
        import physmat
        return float(physmat.material(name).properties["thermo_optic_dn_dT"].value), LIBRARY_REFERENCE_TEMPERATURE
    record = materials.get(ref) or {}
    if all(k in record for k in THERMO_OPTIC_KEYS):
        return float(record["thermo_optic_coefficient"]), float(record["reference_temperature"])
    return None


# ---------------------------------------------------------------------------------------------
# the kind of multiphysics documents

def _validate(doc) -> None:
    if getattr(doc, "views", None) is None:
        raise DocumentError("a multiphysics document is validated when it is read; read it with Document.load, "
                            "Document.loads or Document.from_dict")


def _summary(doc) -> str:
    lines = [f"multiphysics document ({ENVELOPE}): {doc.si.get('name', 'untitled')}"]
    for name, view in doc.views.items():
        lines.append(f"physics {name}:")
        lines += ["  " + line for line in view.summary().splitlines()]
    edges = _edges(doc)
    for e in edges:
        lines.append(f"coupling {e.name}: {e.source}.{e.output} -> {e.target}.{e.input} ({e.quantity}, {e.unit}, "
                     f"{doc.si['couplings'][e.name]['transfer']})")
    lines.append("solve order: " + " -> ".join("[" + ", ".join(g) + "]" if len(g) > 1 else g[0]
                                              for g in solve_order(list(doc.si["physics"]), edges)))
    return "\n".join(lines)


def _edges(doc) -> list[_Edge]:
    from .registry import kind_of_type
    out = []
    for cname, c in doc.si["couplings"].items():
        source, output = c["from"].split(".", 1)
        target, inp = c["to"].split(".", 1)
        port = ports_of(kind_of_type(doc.si["physics"][source]["type"]))[output]
        out.append(_Edge(cname, source, output, target, inp, port["quantity"], port["unit"]))
    return out


# ---------------------------------------------------------------------------------------------
# running

class LoopNotConverged(DocumentError):
    """``E-LOOP-DIVERGED``: a loop reached ``max_iterations`` without meeting its tolerance;
    ``history`` holds its residuals in the port's unit. No result is returned."""

    def __init__(self, message: str, history: list[float], unit: str):
        super().__init__(message, path="study.loops", code="E-LOOP-DIVERGED")
        self.history = list(history)
        self.unit = unit


def _is_power(quantity: str) -> bool:
    return dict(units.quantity(quantity).dimension) in _POWER


def _integral(field_, mesh) -> float:
    """The integral of a node (lumped P1) or element field over its mesh."""
    nodes, tris = np.asarray(mesh.nodes), np.asarray(mesh.triangles)
    p = nodes[tris]
    area = 0.5 * np.abs((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
                        - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
    values = np.asarray(field_.values)
    if field_.location == "element":
        return float(np.sum(values * area))
    return float(np.sum(values[tris].sum(axis=1) * area / 3.0))


def _transfer(edge: _Edge, sent, state):
    """The field of ``edge`` on the receiver's mesh (``same_mesh``), and its record."""
    from galerkin.coupling import transfer
    message = (f"couplings.{edge.name}: same_mesh needs one mesh, but {edge.source} and {edge.target} built "
               "different meshes (nodes or triangles differ)")
    try:
        received = transfer(sent, state.mesh, regions=False, message=message)
    except ValueError as exc:
        raise DocumentError(str(exc), path=f"couplings.{edge.name}") from exc
    sent_regions = _triangle_regions(sent.signature)
    if sent_regions is not None and state.triangle_regions is not None \
            and not np.array_equal(sent_regions, np.asarray(state.triangle_regions)):
        raise DocumentError(f"couplings.{edge.name}: same_mesh needs one mesh, but {edge.source} and {edge.target} "
                            "assign different regions to the same triangles", path=f"couplings.{edge.name}")
    difference = float(np.max(np.abs(np.asarray(received.values) - np.asarray(sent.values)))) \
        if len(sent.values) else 0.0
    if difference != 0.0:
        raise DocumentError(f"couplings.{edge.name}: the same_mesh transfer changed the values by {difference!r} "
                            f"{edge.unit}; the identity did not hold", path=f"couplings.{edge.name}")
    record = {"from": f"{edge.source}.{edge.output}", "to": f"{edge.target}.{edge.input}",
              "quantity": edge.quantity, "unit": edge.unit, "transfer": "same_mesh", "location": sent.location,
              "mesh_signature": "match", "max_abs_difference": {"value": difference, "unit": edge.unit},
              "conservation_residual": None}
    if _is_power(edge.quantity):
        total_sent = _integral(sent, state.mesh)
        total_received = _integral(received, state.mesh)
        record["conservation_residual"] = (abs(total_sent - total_received) / abs(total_sent)
                                           if total_sent != 0 else 0.0)
    return received, record


def _triangle_regions(signature):
    if signature.regions is None or signature.region_names is None:
        return None
    return np.asarray(signature.region_names, dtype=object)[np.asarray(signature.regions)]


def _combine(port: dict, fields: list, mesh):
    from galerkin.coupling import Field
    if len(fields) == 1:
        return fields[0]
    total = np.sum([np.asarray(f.values) for f in fields], axis=0)
    return Field(mesh, total, location=fields[0].location, unit=fields[0].unit, name=port["name"])


def run(doc, verbose: bool = True, *, on_event=None) -> "MultiphysicsRunResult":
    """Solve a validated multiphysics document in its solve order.

    ``on_event``, when given, is called with one JSON-data dict per step, in order, so that a
    caller can show progress: ``{"event": "physics_started", "physics": name}``,
    ``{"event": "physics_finished", "physics": name, "seconds": t}``, and for an accepted loop
    ``{"event": "loop_started", "physics": [...]}``, one ``{"event": "loop_iteration",
    "physics": [...], "iteration": k, "residual": r, "unit": u}`` per iteration that measures a
    residual, and ``{"event": "loop_finished", "physics": [...], "iterations": n}``. A failing
    loop raises after its last ``loop_iteration``."""
    from .registry import kind_of_type
    _validate(doc)
    log: list[str] = []
    emit = on_event if on_event is not None else (lambda event: None)

    def say(msg):
        log.append(msg)
        if verbose:
            print(msg)

    if doc.si["study"]["type"] == "sweep":
        raise DocumentError("study.type: a multiphysics sweep is validated but not run in this release; run each "
                            "point as its own document (study.type \"single\")", path="study.type")
    edges = _edges(doc)
    names = list(doc.si["physics"])
    order = solve_order(names, edges)
    loops = {tuple(sorted(l["physics"])): l for l in doc.si["study"].get("loops", [])}
    say(f"multiphysics run: {doc.si.get('name', 'untitled')}")
    say("solve order: " + " -> ".join("[" + ", ".join(g) + "]" if len(g) > 1 else g[0] for g in order))
    outputs, results, records, histories, timings = {}, {}, {}, [], {}
    for group in order:
        if len(group) > 1:
            loop = loops[tuple(sorted(group))]
            emit({"event": "loop_started", "physics": list(group)})
            history = _run_loop(doc, group, loop, edges, outputs, results, records, timings, say, verbose, emit)
            histories.append(history)
            emit({"event": "loop_finished", "physics": list(group), "iterations": history["iterations"]})
            continue
        name = group[0]
        kind = kind_of_type(doc.si["physics"][name]["type"])
        emit({"event": "physics_started", "physics": name})
        t0 = time.perf_counter()
        state = kind.coupling.prepare(doc, name)
        inputs = _inputs(name, kind, state, edges, outputs, records)
        say(f"physics {name} ({kind.name})" + (": inputs " + ", ".join(sorted(inputs)) if inputs else ""))
        result, produced = kind.coupling.solve(state, inputs, verbose)
        timings[name] = time.perf_counter() - t0
        emit({"event": "physics_finished", "physics": name, "seconds": timings[name]})
        results[name] = result
        for port, f in produced.items():
            outputs[(name, port)] = f
        log += [f"  {line}" for line in getattr(result, "log", [])]
    return MultiphysicsRunResult(doc, order, results, records, histories, timings, log)


def _inputs(name, kind, state, edges, outputs, records, relaxed=None) -> dict:
    """The input fields of ``physics.<name>``: every coupling into it, carried onto its mesh and
    combined per port. ``relaxed`` replaces the field of a coupling inside a loop (by name)."""
    ports = ports_of(kind)
    incoming = {}
    for e in edges:
        if e.target != name:
            continue
        if relaxed is not None and e.name in relaxed:
            if relaxed[e.name] is None:              # the first iteration: no value inside the loop yet
                continue
            received = relaxed[e.name]
        elif (e.source, e.output) in outputs:
            received, records[e.name] = _transfer(e, outputs[(e.source, e.output)], state)
        else:
            continue
        incoming.setdefault(e.input, []).append(received)
    return {port: _combine(ports[port], fields, state.mesh) for port, fields in incoming.items()}


def _run_loop(doc, group, loop, edges, outputs, results, records, timings, say, verbose, emit) -> dict:
    """An accepted loop: the under-relaxed fixed point x <- (1 - w) x + w G(x) on the fields of the
    couplings inside ``group``. Each iteration solves the members in their order; a coupling's
    field enters the next iteration relaxed. The residual is the largest change (``max_abs``) of
    the tolerance port between two iterations, in that port's unit; the loop has converged when it
    is at most the tolerance. At ``max_iterations`` it fails with its residual history
    (``LoopNotConverged``) and gives no result."""
    from galerkin.coupling import Field
    from .registry import kind_of_type
    inside = [e for e in edges if e.source in group and e.target in group]
    w = float(loop["relaxation"])
    spec = loop["tolerance"]
    port_name = spec["port"]
    pname, _, port = port_name.partition(".")
    port_info = ports_of(kind_of_type(doc.si["physics"][pname]["type"]))[port]
    tolerance = units.convert(spec["value"], _DIFFERENCE.get(port_info["quantity"], port_info["quantity"])).value
    kinds = {n: kind_of_type(doc.si["physics"][n]["type"]) for n in group}
    t0 = time.perf_counter()
    states = {n: kinds[n].coupling.prepare(doc, n) for n in group}
    relaxed = {e.name: None for e in inside}
    history = []
    say(f"loop {', '.join(group)}: fixed_point, relaxation {w:g}, tolerance {spec['value']} on {port_name}")
    for iteration in range(1, int(loop["max_iterations"]) + 1):
        residual = None
        for n in group:
            inputs = _inputs(n, kinds[n], states[n], edges, outputs, records, relaxed)
            results[n], produced = kinds[n].coupling.solve(states[n], inputs, False)
            for p, f in produced.items():
                outputs[(n, p)] = f
            for e in inside:
                if e.source == n:
                    received, records[e.name] = _transfer(e, outputs[(n, e.output)], states[e.target])
                    old = relaxed[e.name]
                    if old is not None and f"{e.source}.{e.output}" == port_name:
                        # the fixed-point residual |G(x) - x| of this coupling's field, whatever w is
                        change = np.abs(np.asarray(received.values) - np.asarray(old.values))
                        residual = max(residual or 0.0, float(np.max(change)) if change.size else 0.0)
                    relaxed[e.name] = received if old is None else Field(
                        states[e.target].mesh, (1 - w) * np.asarray(old.values) + w * np.asarray(received.values),
                        location=received.location, unit=received.unit, name=e.name)
        if residual is not None:
            history.append(residual)
            emit({"event": "loop_iteration", "physics": list(group), "iteration": iteration, "residual": residual,
                  "unit": port_info["unit"]})
            say(f"  iteration {iteration}: max_abs |G(x) - x| of {port_name} {residual!r} {port_info['unit']}")
            if residual <= tolerance:
                for n in group:
                    timings[n] = (time.perf_counter() - t0) / len(group)
                return {"physics": list(group), "method": "fixed_point", "tolerance": copy.deepcopy(spec),
                        "relaxation": w, "iterations": iteration, "converged": True,
                        "residuals": [{"value": r, "unit": port_info["unit"]} for r in history]}
    shown = ", ".join(f"{r:.3e}" for r in history) or "none (one iteration gives no change to measure)"
    raise LoopNotConverged(f"study.loops: the loop of {', '.join(group)} did not converge in "
                           f"{loop['max_iterations']} iterations: max_abs |G(x) - x| of {port_name} per iteration "
                           f"({port_info['unit']}): {shown}; no result is returned. Raise max_iterations, lower "
                           "relaxation or check the couplings", history, port_info["unit"])


@dataclass
class MultiphysicsRunResult:
    """``multiphysics-run-v1``: each physics result under its name, the solve order used, each
    coupling's record and each loop's iteration history."""
    doc: Any
    solve_order: list
    results: dict
    couplings: dict
    loops: list
    timings: dict = field(default_factory=dict)
    log: list = field(default_factory=list)

    def summary(self) -> dict:
        from . import results_common
        doc = self.doc
        out = {"result": RESULT_FORMAT, "format": ENVELOPE, "name": doc.si.get("name", "untitled"),
               "diagnostics": [d.as_dict() for d in doc.diagnostics],
               "defaults_applied": list(doc.defaults_applied),
               "solve_order": [list(g) for g in self.solve_order],
               "physics": {}, "couplings": copy.deepcopy(self.couplings), "loops": copy.deepcopy(self.loops),
               "timing": {"physics": {n: {"value": t, "unit": "s"} for n, t in self.timings.items()}}}
        for name, r in self.results.items():
            summary = r.summary()
            identifier = summary.get("result_format") or summary.get("field_layout")
            out["physics"][name] = {"type": doc.si["physics"][name]["type"], "result": identifier, "folder": name}
        results_common.dumps_summary(out)
        return out

    def save(self, outdir) -> Path:
        from . import results_common
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        for name, r in self.results.items():
            r.save(outdir / name)
            # the view a physics was solved as is not a document the user wrote (and without its
            # coupled inputs it would not give this result): the run's model.json is the document's
            view_model = outdir / name / "model.json"
            if view_model.exists():
                view_model.unlink()
        results_common.write_model_json(self.doc, outdir / "model.json")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        (outdir / "summary.json").write_text(results_common.dumps_summary(self.summary()), encoding="utf-8")
        return outdir


def _make_kind():
    from .registry import PhysicsKind
    return PhysicsKind(name="multiphysics", types=frozenset(), precedence=0, validate=_validate, run=run,
                       summary=_summary, result_types=(MultiphysicsRunResult,), fresh_output=True,
                       stage_refusal="{stage} is a single-physics stage; run(document) solves a multiphysics "
                                     "document")


#: the kind ``registry.kind_of`` gives a multiphysics document; it is no provider's kind and
#: claims no type: each physics entry is its own kind's
KIND = _make_kind()
