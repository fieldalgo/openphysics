# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Single rectangular cavity studies (``em.cavity3d``) in format 0.3, and their SI results.

A format 0.3 cavity document writes ``target_frequency`` with its unit (``"250 MHz"``),
``mode_count``, ``boundary`` (``"pec"``, or ``{"electrical_conductivity": "58 MS/m"}`` for every
wall, or ``{"electrical_conductivity": {"zmax": "1 MS/m"}}`` per wall, the others PEC),
``mesh.subdivision_count`` (``[nx, ny, nz]``) and local materials whose
``relative_permittivity`` and ``relative_permeability`` read under exp(-i omega t): a number,
or ``{"re": .., "im": ..}``, with Re > 0 and Im >= 0 (loss). The background is ``"physmat:vacuum"`` or a
local material; the shapes are boxes on the subdivision planes (phase-2 spec section 4.9).

The galerkin cavity solvers keep their own convention, exp(+j omega t). ``_to_kernel`` hands
them every material value conjugated once, as ``0.0 - Im`` so that a real value keeps its
+0.0, and ``_to_public`` conjugates every complex result once (section 5.3.5): these two are
the cavity's only conversions between the conventions (check P2-15). Lengths reach the solver
in metres from the exact picometre values of the geometry numbers.

A vacuum PEC box gives the real layout ``cavity3d-edge-v2``; box materials, a non-vacuum
background or conducting walls run the complex material cavity solver and give
``cavity3d-edge-complex-v2``. The cavity refuses the 2D stage API (``build_mesh``,
``solve_point``).

The format 0.2 helpers further down (``_cavity_materials``, ``_cavity_boundary``,
``_cavity_shapes``, ``uses_material_solver``) serve only the format 0.2 view builder
``views.cavity_inputs`` until the 0.2 reader is retired; no format 0.2 cavity document is read.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from . import results_common, views
from .registry import PhysicsKind, register
from .schema import Document, DocumentError

if TYPE_CHECKING:
    from galerkin import CavityResult

TYPE = "em.cavity3d"
FIELD_LAYOUT = "cavity3d-edge-v2"
FIELD_LAYOUT_COMPLEX = "cavity3d-edge-complex-v2"
_FORMAT_02 = ('format 0.2 em.cavity3d documents are not read: units now travel with each value ("250 MHz", '
              '"58 MS/m"), keys are registry names (target_frequency, mode_count, boundary.electrical_conductivity, '
              'mesh.subdivision_count), the vacuum background is "physmat:vacuum" and complex values read under '
              'exp(-i omega t) (a 0.2 [re, im] is {"re": re, "im": -im}). Write "openphysics": "0.3" '
              '(docs/packages/simcase/cavity3d.md)')


# -- format 0.2 helpers of the view builder (views.cavity_inputs; retired with the 0.2 reader) ----

def _object(value, allowed, path):
    if not isinstance(value, dict):
        raise DocumentError(f"{path}: expected an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise DocumentError(f"{path}: unsupported cavity keys {sorted(unknown)}")


def _number(value, path, *, positive=False, integer=False):
    try:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or (positive and value <= 0) or (integer and int(value) != value):
        kind = "positive integer" if integer else "finite positive number" if positive else "finite number"
        raise DocumentError(f"{path}: expected a {kind}")


WALL_NAMES = {"xmin": "x0", "xmax": "x1", "ymin": "y0", "ymax": "y1", "zmin": "z0", "zmax": "z1"}
_GRID_TOLERANCE = 1e-9


def _complex_constant(value, path):
    """A JSON real number or [real, imag] pair; passive under exp(+j*omega*t)."""
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise DocumentError(f"{path}: expected a number or [real, imag]")
        _number(value[0], f"{path}[0]", positive=True)
        _number(value[1], f"{path}[1]")
        if value[1] > 0:
            raise DocumentError(f"{path}[1]: imaginary part must be <= 0 (passive, exp(+j*omega*t))")
        return complex(value[0], value[1])
    _number(value, path, positive=True)
    return complex(value)


def _cavity_materials(d):
    materials = d["materials"]
    if not isinstance(materials, dict):
        raise DocumentError("materials: expected an object")
    resolved = {}
    for name, spec in materials.items():
        path = f"materials.{name}"
        if not isinstance(name, str) or not name or name == "vacuum":
            raise DocumentError(f"{path}: material names must be non-empty and not 'vacuum'")
        _object(spec, {"relative_permittivity", "relative_permeability"}, path)
        if "relative_permittivity" not in spec:
            raise DocumentError(f"{path}: relative_permittivity is required")
        resolved[name] = (_complex_constant(spec["relative_permittivity"], f"{path}.relative_permittivity"),
                          _complex_constant(spec.get("relative_permeability", 1.0),
                                            f"{path}.relative_permeability"))
    return resolved


def _cavity_boundary(boundary, path):
    """'pec', or {"conductivity_s_per_m": S/m or {wall: S/m}} with walls xmin..zmax."""
    if boundary == "pec":
        return None
    _object(boundary, {"conductivity_s_per_m"}, path)
    value = boundary.get("conductivity_s_per_m")
    if isinstance(value, dict):
        if not value:
            raise DocumentError(f"{path}.conductivity_s_per_m: name at least one wall")
        unknown = set(value) - set(WALL_NAMES)
        if unknown:
            raise DocumentError(f"{path}.conductivity_s_per_m: unknown walls {sorted(unknown)}; "
                                f"use {list(WALL_NAMES)}")
        for wall, sigma in value.items():
            _number(sigma, f"{path}.conductivity_s_per_m.{wall}", positive=True)
        return {WALL_NAMES[wall]: float(sigma) for wall, sigma in value.items()}
    _number(value, f"{path}.conductivity_s_per_m", positive=True)
    return float(value)


def _cavity_shapes(doc, materials):
    """Validated box shapes as (bounds relative to the domain origin in metres, name)."""
    g = doc.data["geometry"]
    shapes = g.get("shapes")
    if not isinstance(shapes, list):
        raise DocumentError("geometry.shapes: expected a list")
    dom = g["domain"]
    cells = doc.data["mesh"]["subdivisions"]
    names, boxes = set(), []
    for i, shape in enumerate(shapes):
        path = f"geometry.shapes[{i}]"
        keys = {axis + side for axis in "xyz" for side in ("min", "max")}
        _object(shape, keys | {"type", "name", "material"}, path)
        if shape.get("type") != "box":
            raise DocumentError(f"{path}: em.cavity3d supports only type 'box'")
        missing = (keys | {"name", "material"}) - set(shape)
        if missing:
            raise DocumentError(f"{path}: missing {sorted(missing)}")
        name = shape["name"]
        if not isinstance(name, str) or not name or name in names:
            raise DocumentError(f"{path}.name: expected a unique non-empty string")
        names.add(name)
        if shape["material"] not in materials:
            raise DocumentError(f"{path}.material: {shape['material']!r} is not defined in materials")
        bounds = []
        for a, axis in enumerate("xyz"):
            low, high = shape[axis + "min"], shape[axis + "max"]
            _number(low, f"{path}.{axis}min")
            _number(high, f"{path}.{axis}max")
            if not dom[axis + "min"] <= low < high <= dom[axis + "max"]:
                raise DocumentError(f"{path}: needs {axis}min < {axis}max inside the domain")
            extent = dom[axis + "max"] - dom[axis + "min"]
            for label, value in ((axis + "min", low), (axis + "max", high)):
                position = (value - dom[axis + "min"]) / extent * cells[a]
                if abs(position - round(position)) > _GRID_TOLERANCE * max(1, cells[a]):
                    raise DocumentError(
                        f"{path}.{label}: must lie on a mesh grid plane (multiples of "
                        f"{extent / cells[a]:g} {doc.length_unit} from {axis}min); adjust mesh.subdivisions")
            bounds.append((doc.scale.to_si(low - dom[axis + "min"], {"length": 1}),
                           doc.scale.to_si(high - dom[axis + "min"], {"length": 1})))
        boxes.append((tuple(bounds), shape["material"]))
    return boxes


def uses_material_solver(doc: Document) -> bool:
    """True when a format 0.2 study needs the complex material/impedance cavity solver."""
    d = doc.data
    p = doc.sole_physics()[1]
    return bool(d["materials"] or d["geometry"]["shapes"] or p.get("boundary") != "pec"
                or d["geometry"]["background"] != {"material": "vacuum"})

# -- format 0.3: slots ------------------------------------------------------------------------------

_MESH_ONLY = "a cavity is meshed by mesh.subdivision_count only; {key} is not read by em.cavity3d"
_BOX_KEYS = tuple(axis + side for axis in "xyz" for side in ("min", "max"))
_GAIN = ("the cavity solvers are passive: a gain material is not supported and allow_gain is not a key; give "
         "Im relative_permittivity >= 0 (loss) under exp(-i omega t)")


def cavity_slots():
    """The physics slots of em.cavity3d (``simcase.slots``), data only."""
    p = "physics.*{" + TYPE + "}"

    def q(key, quantity, forms=("QS", "AV"), kind="quantity", **extra):
        return {"pattern": f"{p}.{key}", "kind": kind, "quantity": quantity, "forms": list(forms), **extra}

    out = [{"pattern": f"{p}.type", "kind": "enum", "values": [TYPE], "required": True},
           {"pattern": f"{p}.search", "kind": "enum", "values": ["near_target"], "required": True},
           q("target_frequency", "target_frequency", required=True),
           q("mode_count", "mode_count", ("BC",), required=True),
           # "pec", or an object whose electrical_conductivity is one value or {wall: value}
           {"pattern": f"{p}.boundary", "kind": "enum", "values": ["pec"], "forms": ["OBJECT"], "required": True},
           q("boundary.electrical_conductivity", "electrical_conductivity", ("QS", "AV", "OBJECT"),
             kind="material_property"),
           q("boundary.electrical_conductivity.*", "electrical_conductivity", kind="material_property"),
           {"pattern": f"{p}.allow_gain", "kind": "refused", "code": "E-CONTRACT", "message": _GAIN}]
    results = {"save_fields": True, "plots": False}
    out += [{"pattern": "materials.*", "kind": "override", "library": "vacuum",
             "reads": {TYPE: ["relative_permittivity", "relative_permeability"]}},
            {"pattern": "materials.*.relative_permittivity", "kind": "override", "required": True},
            {"pattern": "materials.*.relative_permeability", "kind": "override", "default": 1,
             "default_reason": "dimensionless default: a nonmagnetic material (relative_permeability 1)"},
            {"pattern": "name", "kind": "override", "default": "untitled",
             "default_reason": "structural default: the document has no name"},
            {"pattern": "results", "kind": "override", "default": results,
             "default_reason": "structural default of cavity documents"},
            {"pattern": "results.save_fields", "kind": "override", "default": True,
             "default_reason": "structural default of cavity documents"},
            {"pattern": "results.plots", "kind": "override", "default": False,
             "default_reason": "structural default of cavity documents (headless)"},
            {"pattern": "study", "kind": "override", "default": {"type": "single"},
             "default_reason": "structural default: one eigenvalue search"}]
    return tuple(out)


# -- format 0.3: validation -------------------------------------------------------------------------

def _refuse(message, path=None, code="E-CONTRACT"):
    """A coded refusal. An E-CONTRACT message names its own path; any other code does not repeat it."""
    if code != "E-CONTRACT" and path and message.startswith(path + ": "):
        message = message[len(path) + 2:]
    raise DocumentError(message, path=path, code=code)


def entry(doc):
    """``(name, SI entry, path)`` of the one physics entry."""
    doc.sole_physics()
    name, p = next(iter(doc.si["physics"].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse("physics: name must be an identifier", f"physics.{name}")
    return name, p, f"physics.{name}"


def geometry_block(doc):
    """``(base path, flat block, shape path)`` of the cavity geometry: the flat block, or the
    box-only version 1 ``3d`` component compiled to the flat form (whose numbers keep their pm
    counts at the component's paths, its boxes at ``features[i]``)."""
    if doc.geometry_flat is not None:
        (cname,) = doc.data["geometry"]["components"]
        base = f"geometry.components.{cname}"
        return base, doc.geometry_flat, f"{base}.features"
    return "geometry", doc.data["geometry"], "geometry.shapes"


def _background_material(doc, base, flat):
    background = flat.get("background") if isinstance(flat.get("background"), dict) else {}
    material = background.get("material")
    if material is None:
        _refuse("a cavity names its background: \"physmat:vacuum\" or a local material",
                f"{base}.background.material", "E-KEY-MISSING")
    return material


def _domain_pm(doc, base):
    """{axis: (pm min, pm max)} of the box domain."""
    out = {}
    for axis in "xyz":
        try:
            low, high = doc.pm(f"{base}.domain.{axis}min"), doc.pm(f"{base}.domain.{axis}max")
        except KeyError:
            _refuse(f"{base}.domain.{axis}min: em.cavity3d needs a 3D domain (xmin, xmax, ymin, ymax, zmin, zmax)",
                    f"{base}.domain.{axis}min", "E-KEY-MISSING")
        if not low < high:
            _refuse(f"{base}.domain: needs {axis}min < {axis}max", f"{base}.domain.{axis}max", "E-DOMAIN")
        out[axis] = (low, high)
    return out


def _unit_text(doc, base):
    block = doc.si["geometry"] if base == "geometry" else doc.si["geometry"]["components"][base.rsplit(".", 1)[1]]
    return block.get("length_unit", "m")


def _boxes(doc, materials):
    """``[(bounds in metres from the domain origin per axis, material name)]`` of the box shapes,
    checked on their picometre counts: inside the domain, on a subdivision plane within today's
    1e-9 relative tolerance (spec section 2.2 rule 10, G4 Q20)."""
    from physmat.units import pm_to_m
    base, flat, shape_path = geometry_block(doc)
    dom = _domain_pm(doc, base)
    cells = [int(n) for n in doc.si["mesh"]["subdivision_count"]]
    unit = _unit_text(doc, base)
    names, out = set(), []
    for i, shape in enumerate(flat.get("shapes") or []):
        path = f"{shape_path}[{i}]"
        if shape.get("type") != "box":
            _refuse(f"{path}.type: em.cavity3d supports only type 'box'", f"{path}.type")
        other = sorted(set(shape) - {"name", "type", "material", *_BOX_KEYS})
        if other:
            _refuse(f"{path}.{other[0]}: a cavity box takes name, material and xmin..zmax only"
                    + (" (the mesh is mesh.subdivision_count)" if other[0] == "element_size" else ""),
                    f"{path}.{other[0]}")
        missing = [key for key in _BOX_KEYS if key not in shape]
        if missing:
            _refuse(f"{path}.{missing[0]}: a cavity box needs xmin, xmax, ymin, ymax, zmin and zmax",
                    f"{path}.{missing[0]}", "E-KEY-MISSING")
        if shape["name"] in names:
            _refuse(f"{path}.name: box names are unique ({shape['name']!r} repeats)", f"{path}.name")
        names.add(shape["name"])
        if shape["material"] not in materials:
            _refuse(f"{path}.material: a cavity box takes a local material of materials (physmat:vacuum is the "
                    "background only)", f"{path}.material")
        bounds = []
        for a, axis in enumerate("xyz"):
            low, high = doc.pm(f"{path}.{axis}min"), doc.pm(f"{path}.{axis}max")
            d_low, d_high = dom[axis]
            if not d_low <= low < high <= d_high:
                _refuse(f"{path}: needs {axis}min < {axis}max inside the domain", f"{path}.{axis}max", "E-DOMAIN")
            extent = d_high - d_low
            for label, value in ((axis + "min", low), (axis + "max", high)):
                position = Fraction(value - d_low) * cells[a] / extent
                if abs(position - round(position)) > _GRID_TOLERANCE * max(1, cells[a]):
                    step = float(Fraction(extent, cells[a]) / _pm_per(unit))
                    _refuse(f"{path}.{label}: must lie on a mesh grid plane (multiples of {step:g} {unit} from "
                            f"{axis}min); adjust mesh.subdivision_count", f"{path}.{label}")
            bounds.append((pm_to_m(low - d_low), pm_to_m(high - d_low)))
        out.append((tuple(bounds), shape["material"]))
    return out


def _pm_per(unit) -> Fraction:
    from physmat import units
    return Fraction(units.length_to_pm(1, unit).picometres)


def _conductivity(p, path):
    """None (PEC walls), one value, or {galerkin wall name: value} in S/m, checked."""
    boundary = p["boundary"]
    if boundary == "pec":
        return None
    where = f"{path}.boundary.electrical_conductivity"
    if "electrical_conductivity" not in boundary:
        _refuse(f"{where}: give one value for every wall (such as \"58 MS/m\") or {{wall: value}}", where,
                "E-KEY-MISSING")
    value = boundary["electrical_conductivity"]
    if isinstance(value, dict):
        if not value:
            _refuse(f"{where}: name at least one wall ({', '.join(WALL_NAMES)})", where, "E-KEY-MISSING")
        for wall, sigma in value.items():
            if wall not in WALL_NAMES:
                _refuse(f"{where}.{wall}: unknown wall; the walls are {', '.join(WALL_NAMES)}", f"{where}.{wall}",
                        "E-KEY-UNKNOWN")
            if not sigma > 0:
                _refuse(f"{where}.{wall}: a conducting wall needs electrical_conductivity > 0 (omit the wall for "
                        "PEC)", f"{where}.{wall}", "E-DOMAIN")
        return {WALL_NAMES[wall]: float(sigma) for wall, sigma in value.items()}
    if not value > 0:
        _refuse(f"{where}: conducting walls need electrical_conductivity > 0 (write boundary \"pec\" for PEC)",
                where, "E-DOMAIN")
    return float(value)


def uses_material_solver_03(doc) -> bool:
    """True when the study needs the complex material/impedance cavity solver: local materials,
    boxes, conducting walls or a background other than physmat:vacuum."""
    _, flat, _ = geometry_block(doc)
    p = entry(doc)[1]
    return bool(doc.si["materials"] or flat.get("shapes") or p["boundary"] != "pec"
                or _background_material(doc, *geometry_block(doc)[:2]) != "physmat:vacuum")


def validate_cavity(doc) -> None:
    """Format 0.3 cavity documents; a format 0.2 document is refused by name."""
    if doc.si is None:
        raise DocumentError(_FORMAT_02, path="openphysics", code="E-FORMAT")
    name, p, path = entry(doc)
    if p["mode_count"] < 1:
        _refuse(f"{path}.mode_count: a search returns at least one mode", f"{path}.mode_count", "E-DOMAIN")
    _conductivity(p, path)
    base, flat, _ = geometry_block(doc)
    _domain_pm(doc, base)
    background = _background_material(doc, base, flat)
    if isinstance(flat.get("background"), dict) and "element_size" in flat["background"]:
        where = f"{base}.background.element_size"
        _refuse(f"{where}: " + _MESH_ONLY.format(key="element_size"), where)
    materials = doc.si["materials"]
    if background != "physmat:vacuum" and background not in materials:
        _refuse(f"{base}.background.material: use \"physmat:vacuum\" or a name of materials",
                f"{base}.background.material", "E-MATERIAL-UNKNOWN")
    for mname, record in materials.items():
        for key in ("relative_permittivity", "relative_permeability"):
            value = complex(record.get(key, 1))
            if not value.real > 0:
                authored = ((doc.data.get("materials") or {}).get(mname) or {}).get(key)
                where = f"materials.{mname}.{key}" + (".re" if isinstance(authored, dict) else "")
                _refuse(f"{where}: the cavity solvers take a real part > 0 (got {value.real:g})", where, "E-DOMAIN")
    mesh = doc.si.get("mesh") or {}
    for key in ("element_size", "minimum_angle", "element_count_limit", "grading", "controls"):
        if key in (doc.data.get("mesh") or {}):
            _refuse(f"mesh.{key}: " + _MESH_ONLY.format(key=key), f"mesh.{key}")
    if "subdivision_count" not in mesh:
        _refuse("mesh.subdivision_count: a cavity needs [nx, ny, nz]", "mesh.subdivision_count", "E-KEY-MISSING")
    if len(mesh["subdivision_count"]) != 3:
        _refuse("mesh.subdivision_count: a cavity takes three counts [nx, ny, nz]", "mesh.subdivision_count",
                "E-VALUE-FORM")
    _boxes(doc, materials)
    if doc.si["study"] != {"type": "single"}:
        _refuse("study: em.cavity3d supports only {\"type\": \"single\"} (no sweeps)", "study.type")
    if doc.si["results"].get("plots"):
        _refuse("results.plots: em.cavity3d plotting is not supported; set results.plots to false", "results.plots")


# -- format 0.3: summary text -----------------------------------------------------------------------

def _shown(doc, where):
    """The authored text of a value for the summary (an annotated value's value)."""
    value = doc.authored(where)
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    return value if isinstance(value, str) else repr(value)


def cavity_summary(doc) -> str:
    doc.validate()
    name, p, path = entry(doc)
    base, flat, _ = geometry_block(doc)
    unit = _unit_text(doc, base)
    dom = flat["domain"]
    bounds = "  ".join(f"{axis} [{dom[axis + 'min']}, {dom[axis + 'max']}]" for axis in "xyz")
    sigma = _conductivity(p, path)
    where = f"{path}.boundary.electrical_conductivity"
    if sigma is None:
        walls = "all faces PEC"
    elif isinstance(sigma, float):
        walls = f"all faces electrical_conductivity {_shown(doc, where)} (surface impedance)"
    else:
        walls = ("surface impedance on " + ", ".join(f"{w} electrical_conductivity {_shown(doc, f'{where}.{w}')}"
                                                    for w in p["boundary"]["electrical_conductivity"])
                 + "; other faces PEC")
    fill = _background_material(doc, base, flat)
    shapes = "".join(f"\n  box {s['name']}: {s['material']}" for s in flat.get("shapes") or [])
    return (f"{doc.si['name']}  (openphysics 0.3)\n"
            f"  domain {bounds} {unit}\n"
            f"  physics {name}: em.cavity3d, background {fill}, {walls}{shapes}\n"
            f"  search: near_target {_shown(doc, f'{path}.target_frequency')}, {p['mode_count']} mode(s)\n"
            f"  mesh: subdivision_count {[int(n) for n in doc.si['mesh']['subdivision_count']]}\n"
            "  study: single; output coordinates m, frequencies Hz")


# -- format 0.3: the kernel hand-off and back ------------------------------------------------------

def _to_kernel(doc) -> dict:
    """{name: (relative permittivity, relative permeability)} of the local materials as the galerkin
    cavity solvers take them, under exp(+j omega t): each SI value under exp(-i omega t)
    conjugated once, as ``0.0 - Im`` (a real value keeps +0.0, so the solver receives the doubles
    of the format 0.2 input; hazard H16)."""
    out = {}
    for name, record in doc.si["materials"].items():
        eps, mu = complex(record["relative_permittivity"]), complex(record.get("relative_permeability", 1))
        out[name] = (complex(eps.real, 0.0 - eps.imag), complex(mu.real, 0.0 - mu.imag))
    return out


def kernel_inputs(doc) -> views.CavityInputs:
    """The SI solver inputs of a validated format 0.3 cavity document: the box from the exact
    picometre corners (``views.rectangle_mesh``), the counts as Python ints, the target frequency
    in Hz, the wall conductivities in S/m and the materials under the kernel's convention."""
    name, p, path = entry(doc)
    material_solver = uses_material_solver_03(doc)
    materials = _to_kernel(doc) if material_solver else {}
    base, flat, _ = geometry_block(doc)
    background = _background_material(doc, base, flat)
    return views.CavityInputs(box=views.rectangle_mesh(doc, "difference", axes="xyz"),
                              num_modes=int(p["mode_count"]), target_frequency=float(p["target_frequency"]),
                              wall_conductivity=_conductivity(p, path), materials=materials,
                              background=background,
                              boxes=_boxes(doc, materials) if material_solver else [],
                              material_solver=material_solver)


def _to_public(cavity) -> dict:
    """The saved arrays of a galerkin cavity result under the format 0.3 names, SI under
    exp(-i omega t): every complex kernel value conjugated once (section 5.3.5). The real layout
    holds real values only and is saved as computed."""
    complex_layout = hasattr(cavity, "quality_factors")
    conj = np.conj if complex_layout else (lambda a: a)
    out = {"node_coordinates": cavity.mesh.nodes, "tetrahedra": cavity.mesh.tets, "edges": cavity.space.edges,
           "tet_edges": cavity.space.tet_edges, "edge_signs": cavity.space.signs,
           "pec_edge_ids": cavity.pec_edge_ids,
           "resonant_frequency": conj(cavity.frequencies_hz), "wavenumber_squared": conj(cavity.eigenvalues_m2)}
    if complex_layout:
        out["quality_factor"] = cavity.quality_factors
    out.update(mass_normalized_electric_field_line_integral=conj(cavity.edge_coefficients),
               mass_normalized_electric_field=conj(cavity.electric_field),
               relative_residual=cavity.relative_residuals)
    if complex_layout:
        sigma = cavity.wall_conductivity_s_per_m
        out.update(relative_permittivity=np.conj(cavity.tet_relative_permittivity),
                   relative_permeability=np.conj(cavity.tet_relative_permeability),
                   wall_names=np.array(list(WALL_NAMES)),
                   electrical_conductivity=np.array([np.nan if sigma[w] is None else sigma[w]
                                                     for w in WALL_NAMES.values()]),
                   iteration_count=cavity.fixed_point_iterations)
    return out


def run_cavity(doc: Document, *, verbose: bool = True) -> "CavityRunResult":
    import galerkin

    doc.validate()
    inputs = views.cavity_inputs(doc)
    box = inputs.box
    start = time.perf_counter()
    if inputs.material_solver:
        solve = getattr(galerkin, "solve_material_cavity_box", None)
        region_type = getattr(galerkin, "CavityMaterialRegion", None)
        if solve is None or region_type is None:
            raise RuntimeError("em.cavity3d with materials or conducting walls requires a galerkin "
                               "build providing solve_material_cavity_box")
        regions = []
        if inputs.background != "physmat:vacuum":
            eps, mu = inputs.materials[inputs.background]
            regions.append(region_type(tuple((0.0, length) for length in box.lengths), eps, mu))
        for bounds, name in inputs.boxes:
            eps, mu = inputs.materials[name]
            regions.append(region_type(bounds, eps, mu))
        cavity = solve(list(box.lengths), list(box.subdivisions), regions=regions, num_modes=inputs.num_modes,
                       target_frequency_hz=inputs.target_frequency,
                       wall_conductivity_s_per_m=inputs.wall_conductivity)
    else:
        solve = getattr(galerkin, "solve_cavity_box", None)
        if solve is None:
            raise RuntimeError("em.cavity3d requires a matching cavity-enabled galerkin build "
                               "providing solve_cavity_box")
        cavity = solve(list(box.lengths), list(box.subdivisions), num_modes=inputs.num_modes,
                       target_frequency_hz=inputs.target_frequency)
    cavity.mesh.nodes += np.array(box.origin)
    timings = {"mesh_and_solve": time.perf_counter() - start}
    result = CavityRunResult(doc, cavity, timings, [])
    result.log = [results_common.log_header(doc).rstrip("\n"), *result.result_lines()]
    if verbose:
        print("\n".join(result.log))
    return result


# -- format 0.3: results ----------------------------------------------------------------------------

#: array name -> (registry quantity or None for a structural array, location, components)
FIELDS = {
    "node_coordinates": ("node_coordinates", "nodes", ["x", "y", "z"]),
    "tetrahedra": (None, "tetrahedron_connectivity", None),
    "edges": (None, "edge_connectivity", None),
    "tet_edges": (None, "tetrahedron_edges", None),
    "edge_signs": (None, "tetrahedron_edges", None),
    "pec_edge_ids": (None, "edges", None),
    "resonant_frequency": ("resonant_frequency", "modes", None),
    "wavenumber_squared": ("wavenumber_squared", "modes", None),
    "quality_factor": ("quality_factor", "modes", None),
    "mass_normalized_electric_field_line_integral": ("mass_normalized_electric_field_line_integral", "edges_modes",
                                                     None),
    "mass_normalized_electric_field": ("mass_normalized_electric_field", "modes_tetrahedron_centroids",
                                       ["x", "y", "z"]),
    "relative_residual": ("relative_residual", "modes", None),
    "relative_permittivity": ("relative_permittivity", "tetrahedra", None),
    "relative_permeability": ("relative_permeability", "tetrahedra", None),
    "wall_names": (None, "walls", None),
    "electrical_conductivity": ("electrical_conductivity", "walls", None),
    "iteration_count": ("iteration_count", "modes", None),
}
_TEXT = {"edge_orientation": "low_node_index_to_high_node_index", "electric_field_location": "tetrahedron_centroid"}
_AMPLITUDE = "arbitrary normalized; not V/m"


def _material_echo(doc, name, record):
    """A local material in SI value objects: a number as written stays a real value object, a
    {re, im} pair (or a value with an imaginary part) a complex value object."""
    out = {}
    for key in ("relative_permittivity", "relative_permeability"):
        z = complex(record.get(key, 1))
        authored = doc.authored(f"materials.{name}.{key}")
        if isinstance(authored, dict) and "value" in authored:
            authored = authored["value"]
        out[key] = (results_common.value_object(z.real, key) if not isinstance(authored, dict)
                    else results_common.complex_value(z, key))
    return out


@dataclass
class CavityRunResult:
    """A cavity result in SI under exp(-i omega t) (spec section 5.3.5).

    ``cavity`` is galerkin's result, in the solver's convention exp(+j omega t), with its mesh
    translated to the domain origin; the public names (``resonant_frequency``,
    ``mass_normalized_electric_field``, ...) are its values conjugated once
    (``_to_public``). See ``docs/packages/simcase/cavity3d.md`` for the units of the raw
    coefficients and the limits of the search.
    """
    doc: Document
    cavity: CavityResult
    timings: dict[str, float]
    log: list[str]

    @property
    def complex_layout(self) -> bool:
        """True for the material/impedance solver's complex result."""
        return hasattr(self.cavity, "quality_factors")

    @property
    def field_layout(self) -> str:
        return FIELD_LAYOUT_COMPLEX if self.complex_layout else FIELD_LAYOUT

    def arrays(self) -> dict:
        """The ``fields.npz`` arrays and text scalars (without ``metadata_json``)."""
        c = self.cavity
        return {**_to_public(c), "field_layout": self.field_layout, "normalization": self._normalization(),
                "search": c.search, **_TEXT, "cluster_completeness": c.cluster_completeness,
                "mode_count_policy": c.mode_count_policy}

    @property
    def node_coordinates(self):
        return self.cavity.mesh.nodes

    @property
    def resonant_frequency(self):
        """Hz, one per mode; complex in the complex layout, Im < 0 a decaying mode."""
        return _to_public(self.cavity)["resonant_frequency"]

    @property
    def quality_factor(self):
        """Re f / (-2 Im f) per mode (inf when lossless); None in the real layout."""
        return self.cavity.quality_factors if self.complex_layout else None

    @property
    def wavenumber_squared(self):
        return _to_public(self.cavity)["wavenumber_squared"]

    @property
    def mass_normalized_electric_field(self):
        return _to_public(self.cavity)["mass_normalized_electric_field"]

    @property
    def mass_normalized_electric_field_line_integral(self):
        return _to_public(self.cavity)["mass_normalized_electric_field_line_integral"]

    @property
    def relative_residual(self):
        return self.cavity.relative_residuals

    @property
    def cluster_completeness(self):
        return self.cavity.cluster_completeness

    @property
    def mode_count_policy(self):
        return self.cavity.mode_count_policy

    def _normalization(self) -> str:
        return "vacuum_mass_hermitian_unit_si" if self.complex_layout else "electric_mass_orthonormal_si"

    def result_lines(self) -> list[str]:
        """The log lines of the solved modes, public values."""
        f = self.resonant_frequency
        if not self.complex_layout:
            return ["resonant_frequency (Hz): " + ", ".join(f"{v:.12g}" for v in f),
                    "near-target candidate search; no complete lowest-spectrum guarantee; multiplicities are retained"]
        q = ", ".join("inf" if math.isinf(v) else f"{v:.8g}" for v in self.quality_factor)
        return ["resonant_frequency (Hz): " + ", ".join(f"{v.real:.12g}{v.imag:+.6g}i" for v in f),
                "quality_factor: " + q,
                "time convention exp(-i omega t); Q = Re f / (-2 Im f)",
                "near-target candidate search; no complete lowest-spectrum guarantee; multiplicities are retained"]

    def _field_maps(self, arrays: dict) -> dict:
        fields = {name: {"quantity": FIELDS[name][0], "location": FIELDS[name][1], "shape": list(np.shape(a)),
                         "components": FIELDS[name][2]} for name, a in arrays.items() if name in FIELDS}
        maps = results_common.field_maps(fields)
        del maps["field_time_axes"]
        return maps

    def summary(self) -> dict:
        doc, c = self.doc, self.cavity
        name, p, path = entry(doc)
        base, flat, _ = geometry_block(doc)
        arrays = self.arrays()
        out = {"name": doc.si["name"], "physics_type": TYPE, "field_layout": self.field_layout}
        if self.complex_layout:
            out["time_convention"] = results_common.TIME_CONVENTION
        out.update({"diagnostics": [d.as_dict() for d in doc.diagnostics],
                    "defaults_applied": list(doc.defaults_applied), "resolved_inputs": doc.resolved_inputs(),
                    "extent": doc.extent_lines(),
                    "timing": {"wall_time": {"mesh_and_solve": results_common.value_object(
                        self.timings.get("mesh_and_solve", 0.0), "wall_time")}},
                    **self._field_maps(arrays),
                    "normalization": self._normalization(), "amplitude": _AMPLITUDE, **_TEXT,
                    "cluster_completeness": c.cluster_completeness, "mode_count_policy": c.mode_count_policy,
                    "mesh": {"nodes": len(c.mesh.nodes), "tetrahedra": len(c.mesh.tets), "edges": len(c.space.edges)},
                    "study": {"type": "single"}})
        boundary = p["boundary"]
        if boundary == "pec":
            out["boundary"] = "pec"
        else:
            sigma = boundary["electrical_conductivity"]
            out["boundary"] = {"electrical_conductivity": (
                {wall: results_common.value_object(v, "electrical_conductivity") for wall, v in sigma.items()}
                if isinstance(sigma, dict) else results_common.value_object(sigma, "electrical_conductivity"))}
        if self.complex_layout:
            out["electrical_conductivity"] = {
                wall: None if c.wall_conductivity_s_per_m[engine] is None
                else results_common.value_object(c.wall_conductivity_s_per_m[engine], "electrical_conductivity")
                for wall, engine in WALL_NAMES.items()}
        out["background"] = {"material": _background_material(doc, base, flat)}
        if self.complex_layout:
            out["materials"] = {m: _material_echo(doc, m, record) for m, record in doc.si["materials"].items()}
            out["lossless"] = bool(c.lossless)
        out.update({"search": c.search,
                    "target_frequency": results_common.value_object(p["target_frequency"], "target_frequency"),
                    "mode_count": int(p["mode_count"]), "returned_mode_count": len(c.frequencies_hz)})
        f = arrays["resonant_frequency"]
        k2 = arrays["wavenumber_squared"]
        if self.complex_layout:
            out["resonant_frequency"] = results_common.complex_array(f, "resonant_frequency")
            # JSON has no infinity: a lossless mode reports null
            out["quality_factor"] = results_common.tagged_array(arrays["quality_factor"], "quality_factor")
            out["wavenumber_squared"] = results_common.complex_array(k2, "wavenumber_squared")
        else:
            out["resonant_frequency"] = results_common.tagged_array(f, "resonant_frequency")
            out["wavenumber_squared"] = results_common.tagged_array(k2, "wavenumber_squared")
        out["relative_residual"] = results_common.tagged_array(arrays["relative_residual"], "relative_residual")
        if self.complex_layout:
            out["iteration_count"] = [int(v) for v in arrays["iteration_count"]]
        results_common.dumps_summary(out)                # finite JSON only
        return out

    def save(self, outdir: str | Path) -> Path:
        """Write a result without overwriting or mixing earlier result files."""
        outdir = Path(outdir)
        reserved = ("summary.json", "model.json", "log.txt", "fields.npz", "results.png")
        existing = [name for name in reserved
                    if (outdir / name).exists() or (outdir / name).is_symlink()]
        if existing:
            raise FileExistsError(
                f"cavity output already contains result paths: {', '.join(existing)}; "
                "choose a fresh output directory")
        outdir.mkdir(parents=True, exist_ok=True)
        summary = self.summary()
        (outdir / "summary.json").write_text(results_common.dumps_summary(summary), encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        results_common.write_model_json(self.doc, outdir / "model.json")
        if self.doc.si["results"]["save_fields"]:
            np.savez_compressed(outdir / "fields.npz",
                                **self.arrays(), metadata_json=results_common.metadata_json(summary))
        return outdir


def _defaults() -> dict:
    """The format 0.2 merge base; a format 0.3 document takes its defaults from the slots."""
    import copy
    from .schema import DEFAULTS
    defaults = copy.deepcopy(DEFAULTS)
    defaults.update(physics={}, mesh={}, results={"save_fields": True, "plots": False})
    return defaults


register(PhysicsKind(
    name="em.cavity3d", types=frozenset({TYPE}), precedence=40,
    validate=validate_cavity, run=run_cavity, summary=cavity_summary,
    result_types=(CavityRunResult,), defaults=_defaults,
    stage_refusal="{stage} is a 2D stage; use run(document) for em.cavity3d", slots=cavity_slots()))
