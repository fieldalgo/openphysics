# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The slot table: what every path of a format 0.3 document may hold.

Each entry maps a path pattern to one kind of slot: a structural object or list, a quantity
of the physmat registry, a shape number, an enum, an identifier, a material reference, ...
The reader (``simcase.resolve``) walks a document against it: every authored path must match
exactly one slot, and a path in no slot is ``E-KEY-UNKNOWN``.

Pattern syntax: dotted segments; ``*`` matches one map key; ``[]`` one list item;
``["a.b"]`` a literal key; ``{type}`` (or ``{type1|type2}``) after ``physics.*`` keeps the
entry for physics entries of that type; ``<rect>``, ``<regions>`` or ``<v1>`` after
``geometry`` keeps it for that geometry form.

Entry fields: ``pattern``, ``kind`` (``SLOT_KINDS``), ``quantity`` (a registry name),
``forms`` (value forms, see ``FORMS``), ``values`` (an enum), ``required``, ``default``
with ``default_reason`` and ``default_if`` (a sibling key that must be present), ``code``
and ``message`` (a refused key), ``nullable``. ``physics_kind`` marks an entry a physics
kind brings (``PhysicsKind.slots``); it applies to that kind's documents only. A kind entry
of kind ``override`` changes ``default``, ``required`` and the material policy fields
(``reads``, ``library``) of the shared slot with the same pattern, for that kind.

The shared entries are here; each kind brings its physics entries. ``python -m simcase.slots
--write`` writes both into ``slot_table.json`` (generated, frozen, shipped); ``--check`` exits
1 when the file differs. The reader uses the frozen file, plus the slots of a kind registered
at run time that the file does not list.
"""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from importlib import resources

TABLE_FILE = "slot_table.json"
TABLE_FORMAT = "simcase-slot-table/1"

SLOT_KINDS = ("structural", "quantity", "material_property", "shape", "length_unit", "depth", "enum", "id", "ref",
              "selector", "bool", "string", "path", "count_list", "study_values", "parameter", "accept",
              "display_unit", "refused", "format", "override")
#: QS quantity string, TA tagged array, SL short list, CO component object, AV annotated value,
#: BD dimensionless number, BC count, CX {re, im}, NK {n, k}, MODEL an object with "model",
#: OBJECT an object whose keys are slots, NULL JSON null, REF a material reference
FORMS = ("QS", "TA", "SL", "CO", "AV", "BD", "BC", "CX", "NK", "MODEL", "OBJECT", "LIST", "NULL", "REF", "BG", "EX")
GEOMETRY_FORMS = ("rect", "regions", "v1")

LENGTH = ("QS", "AV")
UNITS_MESSAGE = ("units travel with each value; give geometry.length_unit (or geometry.components.<c>.length_unit) "
                 "and write every other number with its unit")


def _obj(pattern, **extra):
    return {"pattern": pattern, "kind": "structural", "forms": ["OBJECT"], **extra}


def _list(pattern, **extra):
    return {"pattern": pattern, "kind": "structural", "forms": ["LIST"], **extra}


def _q(pattern, quantity, forms=LENGTH, kind="quantity", **extra):
    return {"pattern": pattern, "kind": kind, "quantity": quantity, "forms": list(forms), **extra}


def _leaf(pattern, kind, **extra):
    return {"pattern": pattern, "kind": kind, **extra}


def _refused(pattern, code, message):
    return {"pattern": pattern, "kind": "refused", "code": code, "message": message}


def _shape_box(prefix, keys, required=()):
    return [_leaf(f"{prefix}.{k}", "shape", **({"required": True} if k in required else {})) for k in keys]


_DOMAIN = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
_FLAT_SHAPE_NUMBERS = ("x", "y", "w", "h", "cx", "cy", "r", "xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
_V1_SHAPE_NUMBERS = ("x", "y", "w", "h", "cx", "cy", "cz", "r", "w_top", "z0", "xmin", "xmax", "ymin", "ymax", "zmin",
                     "zmax")
_V1_FEATURE_TYPES = ["rect", "circle", "polygon", "trapezoid", "segment", "path", "box", "cylinder", "sphere", "extrude",
                     "layers", "ellipse"]
_RESERVED = "reserved for a later version"
#: registry properties a material record may name that no physics of this release reads
NOT_READ_PROPERTIES = ("shear_modulus", "bulk_modulus", "elasticity_tensor", "mean_linear_expansion_coefficient",
                       "volumetric_expansion_coefficient", "specific_heat_capacity", "loss_tangent",
                       "reference_resistivity")
#: material properties of a record and their value forms
MATERIAL_PROPERTIES = {
    "thermal_conductivity": LENGTH, "volumetric_heat_capacity": LENGTH, "electrical_conductivity": LENGTH,
    "youngs_modulus": LENGTH, "poisson_ratio": ("BD", "AV"), "linear_expansion_coefficient": LENGTH,
    "mass_density": LENGTH, "refractive_index": ("BD", "NK", "MODEL"), "relative_permittivity": ("BD", "CX"),
    "relative_permeability": ("BD", "CX"),
}


def _geometry_flat(form: str) -> list[dict]:
    g = f"geometry<{form}>"
    out = [_leaf(f"{g}.length_unit", "length_unit", required=True), _leaf(f"{g}.depth", "depth"),
           _obj(f"{g}.domain", required=True), _leaf(f"{g}.accept", "accept")]
    out += _shape_box(f"{g}.domain", _DOMAIN, required=("xmin", "xmax", "ymin", "ymax"))
    if form == "regions":
        s = f"{g}.shapes[]"
        out += [_obj(f"{g}.background"), _leaf(f"{g}.background.material", "ref"),
                _q(f"{g}.background.element_size", "element_size"),
                _list(f"{g}.shapes", default=[], default_reason="structural default: no shapes"), _obj(s),
                _leaf(f"{s}.name", "id", rule="name", required=True),
                _leaf(f"{s}.type", "enum", values=["rect", "circle", "polygon", "box"], required=True),
                _leaf(f"{s}.material", "ref", required=True), _q(f"{s}.element_size", "element_size"),
                _list(f"{s}.points"), _list(f"{s}.points[]"), _leaf(f"{s}.points[][]", "shape")]
        out += _shape_box(s, _FLAT_SHAPE_NUMBERS)
    return out


def _feature(f: str, *, profile: bool = False) -> list[dict]:
    out = [_leaf(f"{f}.type", "enum", values=_V1_FEATURE_TYPES if not profile else ["rect", "circle", "polygon",
                                                                                     "trapezoid"]),
           _list(f"{f}.points"), _list(f"{f}.points[]"), _leaf(f"{f}.points[][]", "shape"),
           _list(f"{f}.edges"), _leaf(f"{f}.edges[]", "string")]
    out += _shape_box(f, _V1_SHAPE_NUMBERS)
    if profile:
        return out
    out += [_leaf(f"{f}.id", "string"), _leaf(f"{f}.name", "string"), _leaf(f"{f}.region", "string"),
            _leaf(f"{f}.material", "ref", nullable=True), _leaf(f"{f}.axis", "string"),
            _q(f"{f}.element_size", "element_size"),
            _list(f"{f}.start"), _leaf(f"{f}.start[]", "shape"),
            _list(f"{f}.segments"), _obj(f"{f}.segments[]"), _leaf(f"{f}.segments[].name", "string"),
            _list(f"{f}.segments[].line"), _leaf(f"{f}.segments[].line[]", "shape"),
            _obj(f"{f}.segments[].arc"), _leaf(f"{f}.segments[].arc.ccw", "bool"),
            _list(f"{f}.segments[].arc.center"), _leaf(f"{f}.segments[].arc.center[]", "shape"),
            _list(f"{f}.segments[].arc.to"), _leaf(f"{f}.segments[].arc.to[]", "shape"),
            _obj(f"{f}.profile"), *_feature(f"{f}.profile", profile=True),
            _list(f"{f}.layers"), _obj(f"{f}.layers[]"), _leaf(f"{f}.layers[].name", "string"),
            _leaf(f"{f}.layers[].thickness", "shape"), _leaf(f"{f}.layers[].material", "ref", nullable=True),
            _leaf(f"{f}.layers[].footprint", "string"), _leaf(f"{f}.layers[].region", "string"),
            _obj(f"{f}.layers[].map"), _leaf(f"{f}.layers[].map.*", "ref", nullable=True, forms=["REF", "OBJECT"]),
            _leaf(f"{f}.layers[].map.*.material", "ref", nullable=True),
            _leaf(f"{f}.layers[].map.*.region", "string"),
            _refused(f"{f}.layers[].below", "E-CONTRACT", f"below is {_RESERVED}"),
            _refused(f"{f}.layers[].above", "E-CONTRACT", f"above is {_RESERVED}")]
    out += [_refused(f"{f}.{k}", "E-CONTRACT", f"{k} is {_RESERVED}") for k in ("rotation", "offset", "surface")]
    out.append(_refused(f"{f}.mesh_size", "E-KEY-UNKNOWN",
                        "mesh_size is the 0.2 name; write element_size with its unit, such as \"0.5 um\""))
    return out


def _geometry_v1() -> list[dict]:
    g, c = "geometry<v1>", "geometry<v1>.components.*"
    out = [_leaf(f"{g}.version", "enum", values=[1], required=True),
           _obj(f"{g}.parameters"), _obj(f"{g}.parameters.*"), _leaf(f"{g}.parameters.*.value", "parameter",
                                                                       required=True),
           _leaf(f"{g}.parameters.*.kind", "enum", values=["length", "ratio", "angle", "count"]),
           _leaf(f"{g}.parameters.*.range", "parameter"),
           _obj(f"{g}.components", required=True), _obj(c),
           _leaf(f"{c}.dimension", "enum", values=["2d", "axisymmetric", "3d"], required=True),
           _leaf(f"{c}.length_unit", "length_unit", required=True), _leaf(f"{c}.depth", "depth"),
           _obj(f"{c}.domain", required=True), _obj(f"{c}.background"),
           _leaf(f"{c}.background.material", "ref", nullable=True), _q(f"{c}.background.element_size", "element_size"),
           _refused(f"{c}.background.mesh_size", "E-KEY-UNKNOWN",
                    "mesh_size is the 0.2 name; write element_size with its unit, such as \"0.5 um\""),
           _list(f"{c}.features"), _obj(f"{c}.features[]"), *_feature(f"{c}.features[]"),
           _leaf(f"{c}.finalize", "enum", values=["later_wins", "imprint"]),
           _obj(f"{c}.selections"), _leaf(f"{c}.selections.*", "selector"),
           _list(f"{c}.boundary_tags"), _obj(f"{c}.boundary_tags[]"), _leaf(f"{c}.boundary_tags[].tag", "string"),
           _leaf(f"{c}.boundary_tags[].select", "selector"), _leaf(f"{c}.accept", "accept"),
           _refused(f"{c}.periodic", "E-CONTRACT", f"periodic is {_RESERVED}"),
           _refused(f"{g}.length_unit", "E-KEY-UNKNOWN",
                    "a version 1 block gives length_unit on each component (geometry.components.<c>.length_unit), "
                    "so no document-wide unit applies"),
           _refused(f"{g}.depth", "E-KEY-UNKNOWN",
                    "a version 1 block gives depth on each 2d component (geometry.components.<c>.depth)")]
    out += _shape_box(f"{c}.domain", _DOMAIN)
    return out


def _materials() -> list[dict]:
    m, n = "materials.*", "materials.*.refractive_index"
    out = [_obj("materials", default={}, default_reason="structural default: no local materials", keys="material"),
           _obj(m), _leaf(f"{m}.source", "string"),
           _refused(f"{m}.base", "E-KEY-UNKNOWN", "material overrides (base) are not supported in this release; "
                                                  "write the whole record")]
    out += [_q(f"{m}.{name}", name, forms, kind="material_property") for name, forms in MATERIAL_PROPERTIES.items()]
    out += [_refused(f"{m}.{name}", "E-CONTRACT", f"{name} is a registry property that this release does not read; "
                                                  "give the property the physics reads") for name in NOT_READ_PROPERTIES]
    out += [_leaf(f"{n}.model", "enum", values=["sellmeier"], required=True,
                  refused_values={"rii_formula": "the rii_formula model is not read in this release; write the "
                                                 "Sellmeier model"}),
            _q(f"{n}.constant", "constant", ("BD",), default=1, default_reason="the Sellmeier constant A is 1"),
            _list(f"{n}.terms", required=True), _obj(f"{n}.terms[]"),
            _q(f"{n}.terms[].strength", "strength", ("BD",), required=True),
            _q(f"{n}.terms[].resonance_wavelength_squared", "resonance_wavelength_squared", ("QS",)),
            _q(f"{n}.terms[].resonance_wavelength", "resonance_wavelength", ("QS",)),
            _obj(f"{n}.valid"), _q(f"{n}.valid.vacuum_wavelength", "vacuum_wavelength", ("SL",), range=True),
            _leaf(f"{n}.reference_medium", "enum", values=["vacuum"], required=True,
                  object_message="a reference medium other than vacuum (such as {\"air\": ...}) is not implemented "
                                 "in this release")]
    return out


def _mesh() -> list[dict]:
    c = "mesh.controls[]"
    out = [_q("mesh.element_size", "element_size"),
           _q("mesh.minimum_angle", "minimum_angle", default="28 deg", default_if="element_size",
              default_reason="dimensionless default (an angle); meshine's quality bound", maximum="33 deg"),
           _leaf("mesh.subdivision_count", "count_list", quantity="subdivision_count"),
           _q("mesh.element_count_limit", "element_count_limit", ("BC",), default=600000, default_if="element_size",
              default_reason="count default: the E-MESH-ESTIMATE limit"),
           _obj("mesh.grading"), _q("mesh.grading.position", "position", ("SL", "TA"), required=True),
           _q("mesh.grading.near", "element_size", required=True), _q("mesh.grading.far", "element_size", required=True),
           _q("mesh.grading.refinement_distance", "refinement_distance", required=True),
           _list("mesh.controls"), _obj(c), _leaf(f"{c}.select", "selector", required=True),
           _q(f"{c}.element_size", "element_size"), _q(f"{c}.near", "element_size"), _q(f"{c}.far", "element_size"),
           _q(f"{c}.refinement_distance", "refinement_distance"),
           _q(f"{c}.circle_segment_count", "circle_segment_count", ("BC",)),
           _refused(f"{c}.z_divisions", "E-CONTRACT", "z_divisions is not implemented yet (its registry name is "
                                                      "layer_division_count); circle_segment_count, element_size and "
                                                      "the distance grading (near, far, refinement_distance) are")]
    return out


def shared_slots() -> list[dict]:
    """The slots every format 0.3 document shares, before any kind's physics entries."""
    out = [_leaf("openphysics", "format", required=True), _leaf("name", "string"),
           _refused("units", "E-KEY-UNKNOWN", UNITS_MESSAGE),
           _obj("display_units"), _leaf("display_units.*", "display_unit"),
           _obj("geometry", required=True), _obj("physics", required=True, keys="physics"), _obj("physics.*"),
           _obj("mesh"), _obj("study"), _obj("results"),
           _leaf("study.type", "enum", values=["single", "sweep", "transient"]),
           _leaf("study.parameter", "path"), _leaf("study.values", "study_values"),
           _q("study.time", "time", ("TA",)),
           _leaf("results.save_fields", "bool"), _leaf("results.plots", "bool")]
    out += _geometry_flat("rect") + _geometry_flat("regions") + _geometry_v1() + _materials() + _mesh()
    return out


# -- patterns -------------------------------------------------------------------------------------

_TOKEN = re.compile(r'(?P<lit>\["(?:[^"\\]|\\.)*"\])|(?P<item>\[\])|(?P<star>\*)|(?P<name>[A-Za-z_][A-Za-z0-9_]*)'
                    r'|(?P<type>\{[^}]*\})|(?P<form><[a-z0-9]+>)|(?P<dot>\.)')


class Segment:
    """One pattern segment: a literal key, any key (``*``) or a list item (``[]``), with a guard."""

    __slots__ = ("kind", "name", "types", "form")

    def __init__(self, kind: str, name: str | None = None):
        self.kind, self.name, self.types, self.form = kind, name, None, None

    def matches(self, segment) -> bool:
        if self.kind == "item":
            return isinstance(segment, int)
        if not isinstance(segment, str):
            return False
        return self.kind == "any" or segment == self.name


@lru_cache(maxsize=None)
def compile_pattern(pattern: str) -> tuple[Segment, ...]:
    out: list[Segment] = []
    pos, expect_key = 0, True
    while pos < len(pattern):
        m = _TOKEN.match(pattern, pos)
        if m is None:
            raise ValueError(f"slot pattern {pattern!r}: cannot read {pattern[pos:]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "dot":
            if expect_key:
                raise ValueError(f"slot pattern {pattern!r}: empty segment")
            expect_key = True
        elif kind in ("name", "star", "lit"):
            if not expect_key:
                raise ValueError(f"slot pattern {pattern!r}: missing '.'")
            name = m.group(kind) if kind == "name" else json.loads(m.group(kind)[1:-1]) if kind == "lit" else None
            out.append(Segment("any" if kind == "star" else "key", name))
            expect_key = False
        elif kind == "item":
            if not out:
                raise ValueError(f"slot pattern {pattern!r}: '[]' needs a list before it")
            out.append(Segment("item"))
            expect_key = False
        elif kind == "type":
            if not out or out[-1].kind != "any" or len(out) != 2 or out[0].name != "physics":
                raise ValueError(f"slot pattern {pattern!r}: a type guard follows physics.*")
            out[-1].types = frozenset(t.strip() for t in m.group(kind)[1:-1].split("|"))
        elif kind == "form":
            form = m.group(kind)[1:-1]
            if len(out) != 1 or out[0].name != "geometry" or form not in GEOMETRY_FORMS:
                raise ValueError(f"slot pattern {pattern!r}: a form guard <{'|'.join(GEOMETRY_FORMS)}> follows "
                                 "geometry")
            out[-1].form = form
    if expect_key:
        raise ValueError(f"slot pattern {pattern!r}: ends with '.'")
    return tuple(out)


def geometry_form(geometry) -> str | None:
    """``v1`` for a block with ``version``, ``regions`` with a background or shapes, else ``rect``."""
    if not isinstance(geometry, dict):
        return None
    if "version" in geometry:
        return "v1"
    if "background" in geometry or "shapes" in geometry:
        return "regions"
    return "rect"


def _guards_hold(segments: tuple[Segment, ...], path, tree) -> bool:
    for i, s in enumerate(segments):
        if s.form is not None and geometry_form(tree.get("geometry") if isinstance(tree, dict) else None) != s.form:
            return False
        if s.types is not None:
            physics = tree.get("physics") if isinstance(tree, dict) else None
            entry = physics.get(path[i]) if isinstance(physics, dict) else None
            if not isinstance(entry, dict) or entry.get("type") not in s.types:
                return False
    return True


class SlotTable:
    """The slots of one document kind: matching, siblings, requirements and defaults."""

    def __init__(self, entries, kind_name: str | None):
        self.kind_name = kind_name
        overrides = {e["pattern"]: e for e in entries if e["kind"] == "override"
                     and e.get("physics_kind") == kind_name}
        self.entries = []
        for e in entries:
            if e["kind"] == "override" or (e.get("physics_kind") not in (None, kind_name)):
                continue
            if e["pattern"] in overrides:
                e = {**e, **{k: v for k, v in overrides[e["pattern"]].items()
                             if k not in ("pattern", "kind", "physics_kind")}}
            self.entries.append((compile_pattern(e["pattern"]), e))
        self._by_length: dict[int, list] = {}
        for compiled, e in self.entries:
            self._by_length.setdefault(len(compiled), []).append((compiled, e))

    def match(self, path, tree) -> list[dict]:
        """Every slot whose pattern matches ``path`` (a list of keys and indices) in ``tree``."""
        found = []
        for compiled, e in self._by_length.get(len(path), ()):
            if all(s.matches(p) for s, p in zip(compiled, path)) and _guards_hold(compiled, path, tree):
                found.append(e)
        return found

    def children(self, path, tree) -> list[dict]:
        """The slots one segment below ``path`` that name a literal key."""
        found = []
        for compiled, e in self._by_length.get(len(path) + 1, ()):
            last = compiled[-1]
            if last.kind == "key" and all(s.matches(p) for s, p in zip(compiled, path)) \
                    and _guards_hold(compiled[:-1], path, tree):
                found.append(e)
        return found

    def policy(self) -> dict:
        """The material policy of this kind: the ``materials.*`` slot with its overrides
        (``library``: ``any``, ``vacuum`` or ``none``; ``reads``: physics type -> properties)."""
        return next((e for _c, e in self.entries if e["pattern"] == "materials.*"), {})

    def sibling_names(self, path, tree) -> list[str]:
        return sorted({compile_pattern(e["pattern"])[-1].name for e in self.children(path, tree)
                       if e["kind"] != "refused"})


# -- the generated table --------------------------------------------------------------------------

def _validate(entries) -> None:
    from physmat import units
    seen = set()
    for e in entries:
        compile_pattern(e["pattern"])
        if e["kind"] not in SLOT_KINDS:
            raise ValueError(f"slot {e['pattern']!r}: unknown kind {e['kind']!r}")
        key = (e["pattern"], e.get("physics_kind"), e["kind"] == "override")
        if key in seen:
            raise ValueError(f"slot {e['pattern']!r} is listed twice")
        seen.add(key)
        for form in e.get("forms", ()):
            if form not in FORMS:
                raise ValueError(f"slot {e['pattern']!r}: unknown form {form!r}")
        if e["kind"] in ("quantity", "material_property") or (e["kind"] == "count_list" and "quantity" in e):
            q = units.quantity(e["quantity"])
            if not {"document", "material"} & set(q.places):
                raise ValueError(f"slot {e['pattern']!r}: {e['quantity']} is not placed in documents or materials")


def generate() -> str:
    """The text of ``slot_table.json``: the shared slots and every built-in kind's (deterministic)."""
    from .registry import kinds
    entries = [dict(e) for e in shared_slots()]
    names = {}
    for kind in kinds():
        if kind.slots is None:
            continue
        names[kind.name] = sorted(kind.types)
        entries += [{**e, "physics_kind": kind.name} for e in kind.slots]
    _validate(entries)
    entries.sort(key=lambda e: (e["pattern"], e.get("physics_kind") or "", e["kind"]))
    lines = [json.dumps(e, sort_keys=True, ensure_ascii=False) for e in entries]
    head = json.dumps({"format": TABLE_FORMAT, "kinds": names}, sort_keys=True, ensure_ascii=False)[:-1]
    return (head + ', "note": "generated by python -m simcase.slots --write; do not edit", "slots": [\n'
            + ",\n".join(lines) + "\n]}\n")


@lru_cache(maxsize=1)
def _frozen() -> dict:
    return json.loads(resources.files("simcase").joinpath(TABLE_FILE).read_text(encoding="utf-8"))


def table_for(kind) -> SlotTable:
    """The slot table of documents of ``kind``: the frozen file, plus the kind's own slots when
    the file does not list the kind (a kind registered at run time)."""
    frozen = _frozen()
    entries = list(frozen["slots"])
    if kind is not None and kind.slots is not None and kind.name not in frozen["kinds"]:
        added = [{**e, "physics_kind": kind.name} for e in kind.slots]
        _validate(added)
        entries += added
    return SlotTable(entries, None if kind is None else kind.name)


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m simcase.slots", description="the generated slot table")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="exit 1 when slot_table.json differs from the generator")
    group.add_argument("--write", action="store_true", help="regenerate slot_table.json")
    args = ap.parse_args(argv)
    text = generate()
    target = resources.files("simcase").joinpath(TABLE_FILE)
    if args.write:
        with resources.as_file(target) as path:
            path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {TABLE_FILE}")
        return 0
    current = target.read_text(encoding="utf-8") if target.is_file() else None
    if current != text:
        print(f"{TABLE_FILE} is stale: run python -m simcase.slots --write", file=sys.stderr)
        return 1
    print(f"{TABLE_FILE} is current")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
