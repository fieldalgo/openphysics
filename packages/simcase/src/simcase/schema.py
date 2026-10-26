# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The model document: everything a simulation needs, as plain data.

A document is a JSON object with these sections (lengths use its declared unit):

    units      the unit system the document's numbers are written in: one symbol
               per SI base dimension it needs, e.g. {"length": "um"}. There is no
               default. An absent dimension is SI, except where the physics
               requires it, and there absence is an error -- so a document in
               metres has to say so and cannot get metres by forgetting.
    openphysics     format version
    name       free text
    geometry   rectangular domain, a background material, and an ordered list
               of shapes (rect / circle / polygon). Later shapes cut earlier
               ones, the background fills whatever is left.
    materials  optional custom constants {"myglass": {"n": 1.5, "k": 0}}
               or Sellmeier models {"myglass": {"sellmeier": {"B": [...], "C": [...]}}};
               any other material name is looked up in physmat.
    physics    named physics, {"em1": {...}}. Each entry names its solver and
               its settings. Currently "em.modes2d": wavelength, formulation
               ("scalar" or "vector"), num_modes, boundary
               conditions per side ("pec" | "pmc"), and explicit n_cladding for
               vector modes. The names are how a study
               and (later) a coupling refer to one physics, so they are part of
               the document, not an implementation detail.
    mesh       global size, optional per-shape sizes (on the shape), optional
               radial grading {center, near, far, distance}, min_angle.
    study      {"type": "single"} or {"type": "sweep", "parameter": "physics.em1.wavelength", "values": [...]}
    results    {"save_fields": true, "plots": true}

The same file drives a script, a command line run, and the optional studio: the GUI
is an editor for this document, nothing more.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import units
from .units import Scale, UnitError
from .tracking import tracking_settings

FORMAT = "0.2"
DEFAULT_PHYSICS = "em1"

#: base dimensions each physics needs a declared unit for
PHYSICS_REQUIRES = {"em.modes2d": {"length"}}

DEFAULTS: dict[str, Any] = {
    "openphysics": FORMAT,
    "name": "untitled",
    "geometry": {"domain": None, "background": {"material": "vacuum"}, "shapes": []},
    "materials": {},
    "physics": {DEFAULT_PHYSICS: {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.55,
                                  "num_modes": 1,
                                  "boundary": {"left": "pec", "right": "pec", "top": "pec",
                                               "bottom": "pec"}}},
    "mesh": {"size": 0.2, "min_angle": 28.0, "grading": None},
    "study": {"type": "single"},
    "results": {"save_fields": True, "plots": True},
}

SHAPE_TYPES = {"rect": {"x", "y", "w", "h"}, "circle": {"cx", "cy", "r"}, "polygon": {"points"}}
BOUNDARY_TYPES = {"pec", "pmc"}
PHYSICS_TYPES = {"em.modes2d", "em.cavity3d", "thermal.steady2d", "thermal.transient2d"}
FORMULATIONS = {"scalar", "vector"}


def _steady_boundary_requested(data) -> bool:
    """New mappings opt into strict v2 by presence, including empty objects."""
    physics = data.get("physics") if isinstance(data, dict) else None
    return isinstance(physics, dict) and any(
        isinstance(p, dict) and p.get("type") == "thermal.steady2d"
        and ("outward_flux_w_m2" in p or "convection" in p)
        for p in physics.values())


class DocumentError(ValueError):
    pass


def _reject_tagged_values(node, path: str = "") -> None:
    """``[value, "unit"]`` is reserved for a future tagged quantity, so refuse it now."""
    if isinstance(node, dict):
        for k, v in node.items():
            _reject_tagged_values(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        if len(node) == 2 and isinstance(node[1], str) and isinstance(node[0], (int, float)):
            raise DocumentError(
                f"{path}: tagged quantities ([value, unit]) are reserved and not accepted in "
                f"openphysics {FORMAT}; write a bare number in the units the document declares")
        for i, v in enumerate(node):
            _reject_tagged_values(v, f"{path}.{i}")


def _merge(defaults: dict, given: dict) -> dict:
    out = copy.deepcopy(defaults)
    for k, v in given.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _material_number(value, path: str) -> None:
    try:
        finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise DocumentError(f"{path}: expected a finite number")


def _validate_material(spec, path: str) -> None:
    if not isinstance(spec, dict):
        raise DocumentError(f"{path}: custom material must be an object with n or sellmeier")
    if "source" in spec and not isinstance(spec["source"], str):
        raise DocumentError(f"{path}.source: expected a string")
    if "sellmeier" not in spec:
        if "n" not in spec:
            raise DocumentError(f"{path}: custom material needs n or sellmeier")
        for key in ("n", "k"):
            value = spec.get(key, 0.0)
            _material_number(value, f"{path}.{key}")
            if value < 0:
                raise DocumentError(f"{path}.{key}: must be non-negative")
        return
    if "n" in spec or "k" in spec:
        raise DocumentError(f"{path}: choose either n/k or sellmeier; mixing them would ignore n/k")
    path += ".sellmeier"
    model = spec["sellmeier"]
    if not isinstance(model, dict):
        raise DocumentError(f"{path}: expected an object with B and C arrays")
    if "range_um" in model:
        raise DocumentError(f"{path}.range_um: not supported; use range in the document's length unit")
    unknown = set(model) - {"B", "C", "A", "range"}
    if unknown:
        raise DocumentError(f"{path}: unknown keys {sorted(unknown)}")
    for key in ("B", "C"):
        values = model.get(key)
        if not isinstance(values, (list, tuple)) or not values:
            raise DocumentError(f"{path}.{key}: expected a non-empty array")
        for i, value in enumerate(values):
            _material_number(value, f"{path}.{key}[{i}]")
    if len(model["B"]) != len(model["C"]):
        raise DocumentError(f"{path}: B and C must have the same length")
    _material_number(model.get("A", 1.0), f"{path}.A")
    if "range" in model:
        bounds = model["range"]
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise DocumentError(f"{path}.range: expected [minimum, maximum] in the document's length unit")
        for i, value in enumerate(bounds):
            _material_number(value, f"{path}.range[{i}]")
        if not 0 <= bounds[0] < bounds[1]:
            raise DocumentError(f"{path}.range: require 0 <= minimum < maximum")


@dataclass
class Document:
    data: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULTS))
    #: resolved by validate(); the document's numbers mean nothing without it
    scale: Scale = field(default=units.SI, init=False, repr=False)
    #: magnitude warnings from validate(); a scale error is not an invalid document
    notes: list[str] = field(default_factory=list, init=False, repr=False)

    # -- construction --------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        if not isinstance(d, dict):
            raise DocumentError('document: expected an object')
        from .thermal import is_thermal, defaults as thermal_defaults
        from .transient_thermal_contract import is_transient_thermal, defaults as transient_defaults
        defaults = DEFAULTS
        if is_transient_thermal(d):
            defaults = transient_defaults()
        elif is_thermal(d):
            defaults = thermal_defaults()
        elif isinstance(d.get("physics"), dict) and any(
                isinstance(p, dict) and p.get("type") == "em.cavity3d"
                for p in d["physics"].values()):
            defaults = copy.deepcopy(DEFAULTS)
            defaults.update(physics={}, mesh={}, results={"save_fields": True, "plots": False})
        doc = cls(_merge(defaults, d))
        doc.validate()
        return doc

    @classmethod
    def load(cls, path: str | Path) -> "Document":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def copy(self) -> "Document":
        return Document(copy.deepcopy(self.data))

    # -- access --------------------------------------------------------------

    def __getitem__(self, key: str):
        return self.data[key]

    def get_path(self, dotted: str):
        node = self.data
        for part in dotted.split("."):
            node = node[part]
        return node

    def set_path(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value

    @property
    def shapes(self) -> list[dict]:
        return self.data["geometry"]["shapes"]

    @property
    def domain(self) -> dict:
        return self.data["geometry"]["domain"]

    @property
    def length_unit(self) -> str:
        """Display the declared unit without rescaling any document values."""
        declaration = self.data["units"]["length"]
        return declaration if isinstance(declaration, str) else f"{declaration['in_m']} m"

    def sole_physics(self) -> tuple[str, dict]:
        """The (name, settings) of the one physics, for the paths that assume one."""
        items = list(self.data["physics"].items())
        if len(items) != 1:
            raise DocumentError(
                f"this document declares {len(items)} physics ({', '.join(n for n, _ in items)}); "
                "solving more than one, and coupling them, is not implemented yet")
        return items[0]

    # -- validation ----------------------------------------------------------

    def validate(self) -> None:
        d = self.data
        from .transient_thermal_contract import is_transient_thermal, validate_transient_thermal
        if is_transient_thermal(d):
            from .transient_regions import (is_transient_region_thermal,
                                            validate_transient_region_thermal)
            if is_transient_region_thermal(d):
                _reject_tagged_values(d)
                validate_transient_region_thermal(self)
                return
            validate_transient_thermal(self)
            return
        from .thermal_regions import is_region_thermal, validate_region_thermal
        if is_region_thermal(d):
            if str(d.get("openphysics")) != FORMAT:
                raise DocumentError(f"unsupported openphysics format {d.get('openphysics')!r}; this reader handles {FORMAT}")
            try:
                self.scale = units.resolve(d.get("units"))
            except UnitError as exc:
                raise DocumentError(str(exc)) from None
            _reject_tagged_values(d)
            validate_region_thermal(self)
            return
        if _steady_boundary_requested(d):
            from .steady_boundary_contract import validate_steady_boundary
            validate_steady_boundary(self)
            # Schema normalization is separate from the non-mutating validator.
            self.scale = units.resolve(d["units"])
            self.sole_physics()[1].setdefault("heat_source_w_m3", 0.0)
            self.notes = []
            return
        if str(d.get("openphysics")) != FORMAT:
            raise DocumentError(f"unsupported openphysics format {d.get('openphysics')!r}; this reader handles {FORMAT}")
        try:
            self.scale = units.resolve(d.get("units"))
        except UnitError as exc:
            raise DocumentError(str(exc)) from None
        _reject_tagged_values(d)
        from .thermal import is_thermal, validate_thermal
        if is_thermal(d):
            validate_thermal(self)
            return
        if isinstance(d.get("physics"), dict) and any(
                isinstance(p, dict) and p.get("type") == "em.cavity3d"
                for p in d["physics"].values()):
            from .cavity import validate_cavity
            validate_cavity(self)
            return
        g = d["geometry"]
        dom = g.get("domain")
        if not dom or any(k not in dom for k in ("xmin", "xmax", "ymin", "ymax")):
            raise DocumentError("geometry.domain needs xmin, xmax, ymin, ymax")
        if not (dom["xmin"] < dom["xmax"] and dom["ymin"] < dom["ymax"]):
            raise DocumentError("geometry.domain is empty")
        names = set()
        for i, s in enumerate(g["shapes"]):
            t = s.get("type")
            if t not in SHAPE_TYPES:
                raise DocumentError(f"shape {i}: unknown type {t!r} (rect, circle, polygon)")
            missing = SHAPE_TYPES[t] - set(s)
            if missing:
                raise DocumentError(f"shape {i} ({t}): missing {sorted(missing)}")
            if "name" not in s or "material" not in s:
                raise DocumentError(f"shape {i}: needs 'name' and 'material'")
            if s["name"] in names or s["name"] == "background":
                raise DocumentError(f"shape name {s['name']!r} is duplicated or reserved")
            names.add(s["name"])
            if t == "rect" and (s["w"] <= 0 or s["h"] <= 0):
                raise DocumentError(f"shape {s['name']}: w and h must be positive")
            if t == "circle" and s["r"] <= 0:
                raise DocumentError(f"shape {s['name']}: r must be positive")
            if t == "polygon" and len(s["points"]) < 3:
                raise DocumentError(f"shape {s['name']}: polygon needs >= 3 points")
        if "material" not in g["background"]:
            raise DocumentError("geometry.background needs a material")
        if not isinstance(d["materials"], dict):
            raise DocumentError("materials must be an object mapping names to material definitions")
        for name, spec in d["materials"].items():
            _validate_material(spec, f"materials.{name}")
        if not isinstance(d["physics"], dict) or not d["physics"]:
            raise DocumentError("physics must be a non-empty map of name -> settings, e.g. {'em1': {...}}")
        for pname, p in d["physics"].items():
            if not (isinstance(pname, str) and pname.isidentifier()):
                raise DocumentError(f"physics name {pname!r} must be an identifier: a study or a coupling "
                                    "refers to a physics by this name")
            where = f"physics.{pname}"
            if not isinstance(p, dict):
                raise DocumentError(f"{where} must be a settings map; physics is keyed by name since 0.2, "
                                    "so a setting now lives at physics.<name>.<setting>")
            if p.get("type") not in PHYSICS_TYPES:
                raise DocumentError(f"{where}.type {p.get('type')!r} not supported ({sorted(PHYSICS_TYPES)})")
            if p["formulation"] not in FORMULATIONS:
                raise DocumentError(f"{where}.formulation must be one of {sorted(FORMULATIONS)}")
            if "n_target" in p:
                _material_number(p["n_target"], f"{where}.n_target")
                if p["n_target"] <= 0:
                    raise DocumentError(f"{where}.n_target must be positive")
            for side in ("left", "right", "top", "bottom"):
                if p["boundary"].get(side) not in BOUNDARY_TYPES:
                    raise DocumentError(f"{where}.boundary.{side} must be one of {sorted(BOUNDARY_TYPES)}")
            if not (isinstance(p["wavelength"], (int, float)) and p["wavelength"] > 0):
                raise DocumentError(f"{where}.wavelength must be a positive number (use study.sweep for several)")
            if p["formulation"] == "vector":
                for key in ("wavelength", "n_cladding", "num_modes"):
                    value = p.get(key)
                    _material_number(value, f"{where}.{key}")
                    if value <= 0:
                        raise DocumentError(f"{where}.{key} must be positive")
                if p["num_modes"] != int(p["num_modes"]):
                    raise DocumentError(f"{where}.num_modes must be an integer")
            elif int(p["num_modes"]) < 1:
                raise DocumentError(f"{where}.num_modes must be >= 1")
        required = set()
        for p in d["physics"].values():
            required |= PHYSICS_REQUIRES.get(p["type"], set())
        missing = sorted(required - self.scale.declared)
        if missing:
            raise DocumentError(
                f"units is missing {missing}, which the physics in this document needs. "
                f"An absent dimension means SI, and that is not assumed where it matters: say "
                f"what the numbers are in, e.g. \"units\": {{\"length\": \"um\"}}.")
        self.notes = []
        for pname, p in d["physics"].items():
            note = units.implausible("wavelength", self.scale.to_si(p["wavelength"], {"length": 1}))
            if note:
                self.notes.append(f"physics.{pname}.wavelength: {note}")

        m = d["mesh"]
        if m["size"] <= 0:
            raise DocumentError("mesh.size must be positive")
        if m.get("grading"):
            gr = m["grading"]
            for k in ("center", "near", "far", "distance"):
                if k not in gr:
                    raise DocumentError(f"mesh.grading needs {k}")
        st = d["study"]
        if st["type"] not in ("single", "sweep"):
            raise DocumentError("study.type must be 'single' or 'sweep'")
        if st["type"] == "sweep":
            if (not isinstance(st.get("parameter"), str) or
                    not isinstance(st.get("values"), list) or not st["values"]):
                raise DocumentError("study.sweep needs 'parameter' (dotted path) and non-empty 'values'")
            try:
                self.get_path(st["parameter"])
            except (KeyError, TypeError):
                raise DocumentError(f"study.parameter {st['parameter']!r} does not exist in the document") from None
            if not st["parameter"].startswith("physics."):
                raise DocumentError(
                    f"study.parameter {st['parameter']!r} is not under 'physics.'. The mesh is built once for "
                    "the whole study, so sweeping geometry, mesh or materials would solve every point on the "
                    "first point's mesh. Only physics parameters may be swept.")
            vector_names = [name for name, p in d["physics"].items() if p["formulation"] == "vector"]
            if vector_names:
                if len(d["physics"]) != 1 or st["parameter"] != f"physics.{vector_names[0]}.wavelength":
                    raise DocumentError("vector sweeps support only the wavelength of one fixed physics entry")
                if len(st["values"]) < 3:
                    raise DocumentError("vector wavelength sweeps need at least 3 values for group index")
                for i, value in enumerate(st["values"]):
                    _material_number(value, f"study.values[{i}]")
                    if value <= 0:
                        raise DocumentError("vector sweep wavelengths must be positive")
                pairs = list(zip(st["values"], st["values"][1:]))
                if not (all(a < b for a, b in pairs) or all(a > b for a, b in pairs)):
                    raise DocumentError("vector sweep wavelengths must be strictly monotone (no duplicates)")
                try:
                    tracking_settings(int(d["physics"][vector_names[0]]["num_modes"]), st.get("tracking"))
                except (ValueError, OverflowError) as exc:
                    raise DocumentError(str(exc)) from None
                return
            if "tracking" in st:
                raise DocumentError("study.tracking is only supported for vector wavelength sweeps")
            for value in st["values"]:
                candidate = self.copy()
                candidate.set_path(st["parameter"], value)
                if any(isinstance(p, dict) and p.get("formulation") == "vector"
                       for p in candidate["physics"].values()):
                    raise DocumentError("a scalar sweep cannot switch to vector; use a vector wavelength sweep")

    def summary(self) -> str:
        from .transient_thermal_contract import is_transient_thermal, transient_thermal_summary
        if is_transient_thermal(self.data):
            return transient_thermal_summary(self)
        from .thermal_regions import is_region_thermal, region_summary
        if is_region_thermal(self.data):
            return region_summary(self)
        if _steady_boundary_requested(self.data):
            from .steady_boundary_contract import steady_result_versions
            self.validate()
            name, p = self.sole_physics()
            result_format, field_layout = steady_result_versions(self)
            return (
                f'{self["name"]} (openphysics 0.2)\n'
                f'  physics {name}: thermal.steady2d, single steady heat\n'
                f'  domain {self.domain} {self.length_unit}; mesh {self["mesh"]["subdivisions"]}\n'
                f'  k={p["conductivity_w_mk"]} W/(m K), Q={p["heat_source_w_m3"]} W/m^3\n'
                f'  Dirichlet {p["dirichlet_temperature_k"]} K; '
                f'outward flux {p.get("outward_flux_w_m2", {})} W/m^2; '
                f'convection {p.get("convection", {})}\n'
                '  q.n = g_out + h*(T-T_ambient); unselected natural sides insulated\n'
                f'  result: {result_format}; layout: {field_layout}\n'
                '  output: coordinates m, temperature K, flux W/m^2, nodal heat W/m of depth')
        from .thermal import is_thermal, thermal_summary
        if is_thermal(self.data):
            return thermal_summary(self)
        if any(p.get("type") == "em.cavity3d" for p in self.data["physics"].values()):
            from .cavity import cavity_summary
            return cavity_summary(self)
        g, p, m, st = self.data["geometry"], self.data["physics"], self.data["mesh"], self.data["study"]
        length = self.length_unit
        lines = [f"{self.data['name']}  (openphysics {FORMAT})",
                 f"  domain x [{g['domain']['xmin']}, {g['domain']['xmax']}]  y [{g['domain']['ymin']}, {g['domain']['ymax']}] {length}",
                 f"  background: {g['background']['material']}"]
        for s in g["shapes"]:
            lines.append(f"  shape {s['name']}: {s['type']} of {s['material']}" +
                         (f", mesh {s['mesh_size']} {length}" if "mesh_size" in s else ""))
        for pname, ph in p.items():
            lines.append(f"  physics {pname}: {ph['type']} {ph['formulation']}, lambda {ph['wavelength']} {length}, "
                         f"{ph['num_modes']} mode(s), boundary {ph['boundary']}")
        lines.append(f"  mesh: size {m['size']} {length}" + (f", grading {m['grading']} ({length})" if m.get("grading") else ""))
        lines.append(f"  study: {st['type']}" + (f" over {st['parameter']} x{len(st['values'])}" if st["type"] == "sweep" else ""))
        return "\n".join(lines)
