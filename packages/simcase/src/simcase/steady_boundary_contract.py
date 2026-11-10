# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict steady rectangle boundary inputs, independent of schema dispatch.

The public document reader is connected separately. These helpers read a
Document without mutating its data, scale or notes. They do not solve or save.
Format 0.3 rectangle documents are read by ``simcase.resolve`` against ``heat_slots``
and checked on their SI values here (the section at the end); the format 0.2 reader is gone
(units batch C7), ``natural_conditions`` stays for the transient contract's sampled data.
"""
import math
from collections.abc import Mapping
from itertools import combinations

import numpy as np

from . import views
from .schema import DocumentError

PHYSICS = "thermal.steady2d"
SIDES = ("left", "right", "bottom", "top")
V1 = ("thermal.steady2d-result-v1", "thermal2d-p1-node-cell-v1")
V2 = ("thermal.steady2d-result-v2", "thermal2d-p1-node-cell-boundary-v2")


def _object(value, allowed, path, required=()):
    if not isinstance(value, dict):
        raise DocumentError(f"{path}: expected an object")
    if set(value)-set(allowed):
        raise DocumentError(f"{path}: unsupported keys {sorted(map(str, set(value)-set(allowed)))}")
    if set(required)-set(value):
        raise DocumentError(f"{path}: missing keys {sorted(set(required)-set(value))}")


def _number(value, path, *, positive=False, nonnegative=False, integer=False):
    try:
        ok = (isinstance(value, (int, float)) and not isinstance(value, bool)
              and math.isfinite(value))
    except OverflowError:
        ok = False
    if (not ok or (positive and value <= 0) or (nonnegative and value < 0)
            or (integer and not isinstance(value, int))):
        raise DocumentError(f"{path}: expected a finite valid "
                            + ("positive integer" if integer else "number"))
    return float(value)


def has_natural_conditions(p):
    """Presence, not truth: an empty or null mapping still selects the boundary layout."""
    return "outward_flux_w_m2" in p or "convection" in p


def natural_conditions(p, path, prescribed):
    """Read the ``outward_flux_w_m2`` and ``convection`` side mappings of one physics entry.

    Shared by the steady and transient rectangle contracts, so both accept the
    same key names, value forms and limits and raise the same messages: sides are
    ``left``/``right``/``bottom``/``top``; g is a finite signed W/m²; convection is
    exactly ``{"h_w_m2k": h >= 0, "ambient_temperature_k": K >= 0}``; a side in
    ``prescribed`` (a side-to-Dirichlet mapping) cannot also carry a natural
    condition. Returns ``({side: g}, {side: (h, ambient)})`` as plain floats.
    """
    flux = p.get("outward_flux_w_m2", {})
    _object(flux, SIDES, path+".outward_flux_w_m2")
    flux = {tag: _number(value, path+".outward_flux_w_m2."+tag) for tag, value in flux.items()}
    robin = p.get("convection", {})
    _object(robin, SIDES, path+".convection")
    convection = {}
    for tag, value in robin.items():
        where = path+".convection."+tag
        members = {"h_w_m2k", "ambient_temperature_k"}
        _object(value, members, where, members)
        h = _number(value["h_w_m2k"], where+".h_w_m2k", nonnegative=True)
        ambient = _number(value["ambient_temperature_k"], where+".ambient_temperature_k", nonnegative=True)
        convection[tag] = (h, ambient)
    if set(prescribed) & (set(flux) | set(convection)):
        raise DocumentError(path+": natural condition overlaps a fully Dirichlet side")
    return flux, convection


def validate_steady_boundary(doc):
    """Validate complete normalized document values without modifying the input.

    Nonnegative prescribed/ambient Kelvin is a document policy; the unchanged
    engine permits finite mathematical Kelvin and does not clamp the solution.
    Empty natural mappings select v2 by presence but do not provide an anchor.
    The document is format 0.3, checked on its SI values (``validate_steady_rectangle_03``); a
    format 0.2 document is refused by name.
    """
    _require_03(doc)
    validate_steady_rectangle_03(doc)


def steady_result_versions(doc):
    """Return independent result/layout IDs; absent new keys keep legacy v1."""
    _require_03(doc)
    return steady_result_versions_03(doc)


def _require_03(doc):
    """The rectangle readers read format 0.3 only (the 0.2 reader is gone since units batch C7)."""
    if getattr(doc, "si", None) is None:
        from .thermal import refuse_format_02
        refuse_format_02(doc, "thermal_steady2d")


def steady_boundary_inputs(doc, mesh):
    """Return five copied solve_steady_heat keyword arguments, never a solution.

    Dirichlet selects complete node sides; natural conditions select actual
    boundary_edges tags. Fully fixed natural edges reject; a single fixed
    endpoint retains its consistent load. Mesh geometry is validated by the
    existing engine, with no new solver or assembly. The values come from the document's
    internal SI view (``simcase.views.steady_rectangle``).
    """
    grid, heat = views.steady_rectangle(doc)
    return boundary_kwargs(grid, heat, mesh)


def boundary_kwargs(grid, heat, mesh):
    """``steady_boundary_inputs`` from a rectangle grid (``views.RectangleMesh``) and heat inputs
    (``views.HeatInputs``) a caller has read: the Joule kinds read their heat stage themselves."""
    lower = np.array(grid.origin)
    upper = np.array(grid.upper)
    p, owners, expected_edges = rectangle_exterior_edges(mesh, lower, upper)
    node_tags, edge_tags = getattr(mesh, "boundary", None), getattr(mesh, "boundary_edges", None)
    if not isinstance(node_tags, Mapping) or not isinstance(edge_tags, Mapping):
        raise DocumentError("mesh: boundary node and edge mappings required")
    prescribed = {}
    for tag, value in heat.dirichlet.items():
        ids = np.asarray(node_tags.get(tag, []))
        # Boundary identity comes from verified exterior edges, not a broad
        # coordinate mask that could also include nearby interior nodes.
        expected = np.array(sorted({node for edge in expected_edges[tag] for node in edge}),
                            dtype=int)
        if (ids.ndim != 1 or ids.dtype.kind not in "iu" or len(ids) != len(expected)
                or len(np.unique(ids)) != len(ids) or np.any(ids < 0) or np.any(ids >= len(p))
                or not np.array_equal(np.sort(ids), expected)):
            raise DocumentError(f"mesh.boundary.{tag}: expected the complete unique SI side")
        for node in ids:
            if int(node) in prescribed and prescribed[int(node)] != value:
                raise DocumentError("mesh.boundary: conflicting Dirichlet corner")
            prescribed[int(node)] = value
    validate_natural_edges(mesh, p, owners, expected_edges, prescribed, heat.outward_flux, heat.convection)
    return {"conductivity": heat.conductivity, "dirichlet": dict(sorted(prescribed.items())),
            "heat_source": heat.heat_source, "outward_flux": dict(heat.outward_flux),
            "convection": dict(heat.convection)}


def rectangle_exterior_edges(mesh, lower, upper):
    """Classify the exterior edges of a connected, hole-free rectangle mesh by side.

    Returns ``(nodes, owners, expected_edges)``: SI node coordinates, the owner
    count of every sorted edge and, per side tag, the set of exterior edges on it.
    Raises DocumentError when the coordinate precision cannot separate opposite
    or adjacent sides, the mesh is disconnected, leaves the rectangle or does not
    cover it.
    """
    extent = upper-lower
    tol = 64*np.finfo(float).eps*np.maximum(np.maximum(abs(lower), abs(upper)), extent)
    # Finite endpoints alone do not guarantee distinguishable opposite sides.
    # Keep the existing roundoff budget, but reject before it can span both
    # sides. Never silently enlarge/shrink that budget to accept ambiguous data.
    if np.any(tol >= extent/2):
        raise DocumentError("mesh: insufficient coordinate precision to distinguish "
                            "opposite rectangle sides; use a smaller coordinate origin")
    from galerkin.core.triangles import triangle_geometry
    try:
        p, t, area, _, count, _ = triangle_geometry(mesh)
    except (ValueError, TypeError, IndexError, AttributeError, OverflowError) as exc:
        raise DocumentError(f"mesh: {exc}") from exc
    if count != 1:
        raise DocumentError("mesh: rectangle must be connected")
    if np.any(p < lower-tol) or np.any(p > upper+tol):
        raise DocumentError("mesh.nodes: outside declared SI rectangle")
    axes = {"left": (0, lower[0]), "right": (0, upper[0]),
            "bottom": (1, lower[1]), "top": (1, upper[1])}
    owners = {}
    for tri in t:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((int(tri[a]), int(tri[b]))))
            owners[edge] = owners.get(edge, 0)+1
    exterior = {edge for edge, n in owners.items() if n == 1}
    expected_edges = {tag: {edge for edge in exterior
                            if np.all(abs(p[list(edge), axis]-value) <= tol[axis])}
                      for tag, (axis, value) in axes.items()}
    # Each actual exterior edge must belong to exactly one side, including
    # adjacent sides: a short corner edge can fit both tolerance bands.
    if any(expected_edges[a] & expected_edges[b] for a, b in combinations(SIDES, 2)):
        raise DocumentError("mesh: insufficient coordinate precision; ambiguous "
                            "rectangle side edge classification")
    if (set().union(*expected_edges.values()) != exterior
            or any(not edges for edges in expected_edges.values())
            or not np.isclose(area.sum(), np.prod(upper-lower), rtol=1e-12, atol=0)):
        raise DocumentError("mesh: must cover the complete rectangle without holes")
    return p, owners, expected_edges


def validate_natural_edges(mesh, p, owners, expected_edges, prescribed, flux, convection):
    """Check that each flux/convection tag selects the complete exterior side in mesh.boundary_edges.

    ``prescribed`` maps fixed node indices to their values: an edge whose two
    nodes are both fixed cannot carry a natural condition. Validation only; the
    returned conditions are the caller's.
    """
    edge_tags = getattr(mesh, "boundary_edges", None)
    if not isinstance(edge_tags, Mapping):
        raise DocumentError("mesh: boundary node and edge mappings required")
    # Validate each condition kind independently: one flux plus one Robin is additive.
    for label, conditions in (("outward_flux", flux), ("convection", convection)):
        seen = set()
        for tag in conditions:
            edges = np.asarray(edge_tags.get(tag, []))
            if (edges.ndim != 2 or edges.shape[1] != 2 or not len(edges)
                    or edges.dtype.kind not in "iu" or np.any(edges < 0) or np.any(edges >= len(p))):
                raise DocumentError(f"mesh.boundary_edges.{tag}: expected valid integer (E,2)")
            found = set()
            for a, b in edges:
                edge = tuple(sorted((int(a), int(b))))
                if a == b or owners.get(edge) != 1 or edge in seen:
                    raise DocumentError(f"mesh.boundary_edges.{tag}: invalid or duplicate {label} edge")
                if int(a) in prescribed and int(b) in prescribed:
                    raise DocumentError(f"mesh.boundary_edges.{tag}: natural edge is fully Dirichlet")
                seen.add(edge)
                found.add(edge)
            if found != expected_edges[tag]:
                raise DocumentError(f"mesh.boundary_edges.{tag}: selection must cover the complete SI side")


# -- format 0.3 ------------------------------------------------------------------------------------
#
# A format 0.3 rectangle heat document (``"openphysics": "0.3"``) is read by ``simcase.resolve``
# against the slots below; the checks here run on its resolved SI tree (``doc.si``); region documents
# are checked in ``thermal_regions``. The electric and Joule kinds share ``rectangle_03`` and
# ``natural_conditions_03`` for their rectangles.

V1_03 = ("thermal.steady2d-result-v3", "thermal2d-p1-node-cell-v2")
V2_03 = ("thermal.steady2d-result-v4", "thermal2d-p1-node-cell-boundary-v3")
#: the geometry forms whose format 0.3 heat documents this release reads
FORMS_03 = frozenset({"rect", "regions", "v1"})
_SOURCE_ABSENT = "absent: no volumetric heat source (no value is assumed)"
REACTION_SIGN_03 = ('reaction_heat_rate_per_depth: heat the prescribed-temperature constraint injects into the '
                    'body; outward_reaction_heat_rate_per_depth = -sum(reaction_heat_rate_per_depth)')
OUTWARD_SIGN_03 = ('outward_heat_rate_per_depth = sum(outward_prescribed_heat_rate_per_depth + '
                   'outward_convective_heat_rate_per_depth - reaction_heat_rate_per_depth)')
LOAD_DEFINITION_03 = ('generated_heat_rate_per_depth: the volumetric source only; applied_heat_rate_per_depth = '
                      'generated_heat_rate_per_depth + ambient_convective_heat_rate_per_depth - '
                      'outward_prescribed_heat_rate_per_depth')


def heat_slots(physics_type, *, transient=False):
    """The physics slots of a heat entry on a rectangle or regions (``simcase.slots``), data only."""
    p = "physics.*{" + physics_type + "}"

    def q(key, quantity, forms=("QS", "AV"), kind="quantity", **extra):
        return {"pattern": f"{p}.{key}", "kind": kind, "quantity": quantity, "forms": list(forms), **extra}

    def obj(key, **extra):
        return {"pattern": f"{p}.{key}", "kind": "structural", "forms": ["OBJECT"], **extra}

    # thermal_conductivity, volumetric_heat_capacity and the steady prescribed_temperature are
    # required on rectangles only (regions take the properties from materials.<m> and may anchor
    # by convection); the kind's validator asks for them
    out = [{"pattern": f"{p}.type", "kind": "enum", "values": [physics_type], "required": True},
           q("thermal_conductivity", "thermal_conductivity", kind="material_property"),
           # a constant, or on region documents {region name: value}
           q("heat_source_density", "heat_source_density", ("QS", "AV", "OBJECT"), default=None,
             default_reason=_SOURCE_ABSENT),
           q("heat_source_density.*", "heat_source_density"),
           obj("prescribed_temperature", **({"required": True} if transient else {})),
           q("prescribed_temperature.*", "prescribed_temperature", ("QS", "AV", "TA") if transient else ("QS", "AV")),
           obj("inward_heat_flux"), q("inward_heat_flux.*", "inward_heat_flux"),
           obj("convection"), obj("convection.*"),
           q("convection.*.heat_transfer_coefficient", "heat_transfer_coefficient", required=True),
           q("convection.*.ambient_temperature", "ambient_temperature", required=True)]
    if transient:
        out += [q("volumetric_heat_capacity", "volumetric_heat_capacity", kind="material_property"),
                q("initial_temperature", "initial_temperature", ("QS", "AV", "OBJECT"), required=True),
                {"pattern": f"{p}.initial_temperature.type", "kind": "enum", "values": ["affine"], "required": True},
                q("initial_temperature.reference_temperature", "reference_temperature", required=True),
                q("initial_temperature.temperature_gradient", "temperature_gradient", ("SL", "TA"), required=True)]
    reads = ["thermal_conductivity", "volumetric_heat_capacity"] if transient else ["thermal_conductivity"]
    results = {"save_fields": True, "plots": False}
    out += [{"pattern": "materials.*", "kind": "override", "library": "none", "reads": {physics_type: reads}},
            {"pattern": "name", "kind": "override", "default": "untitled",
             "default_reason": "structural default: the document has no name"},
            {"pattern": "results", "kind": "override", "default": results,
             "default_reason": "structural default of heat documents"},
            {"pattern": "results.save_fields", "kind": "override", "default": True,
             "default_reason": "structural default of heat documents"},
            {"pattern": "results.plots", "kind": "override", "default": False,
             "default_reason": "structural default of heat documents (headless)"}]
    if not transient:
        out.append({"pattern": "study", "kind": "override", "default": {"type": "single"},
                    "default_reason": "structural default: one steady solve"})
    return tuple(out)


def _refuse(message, path=None, code="E-CONTRACT"):
    raise DocumentError(message, path=path, code=code)


def rect_geometry_03(doc):
    """``(base path, flat block, depth)`` of a format 0.3 rectangle: the flat geometry block, or
    the homogeneous version 1 ``2d`` component compiled to the flat form by ``to_v02`` (D-1),
    whose numbers keep their pm counts at the component's paths."""
    if doc.geometry_flat is not None:
        (cname,) = doc.data["geometry"]["components"]
        base = f"geometry.components.{cname}"
        return base, doc.geometry_flat, doc.si["geometry"]["components"][cname].get("depth")
    return "geometry", doc.data["geometry"], doc.si["geometry"].get("depth")


def rectangle_03(doc, label, required=("thermal_conductivity",), *, noun="heat",
                 homogeneous="thermal_conductivity is homogeneous"):
    """The checks every format 0.3 rectangle heat document shares; returns ``(name, entry)``
    of its one physics entry (SI values). ``label`` names the physics in messages, ``noun``
    the document kind and ``homogeneous`` its physics-entry properties (the electric and Joule
    kinds share these checks)."""
    si = doc.si
    doc.sole_physics()                       # one physics entry; several are not coupled yet
    name, p = next(iter(si["physics"].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse("physics: name must be an identifier")
    for key in required:
        if key not in p:
            _refuse(f"physics.{name} needs {key}", f"physics.{name}.{key}", "E-KEY-MISSING")
    if isinstance(p.get("heat_source_density"), dict):
        _refuse(f"physics.{name}.heat_source_density: a rectangle takes one value; {{region: value}} belongs to "
                "region documents", f"physics.{name}.heat_source_density")
    base, flat, _ = rect_geometry_03(doc)
    dom = flat["domain"]
    extra = sorted(set(dom) - {"xmin", "xmax", "ymin", "ymax"})
    if extra:
        _refuse(f"{base}.domain: unsupported keys {extra}; a rectangle {noun} document is 2D")
    for axis in "xy":
        lo, hi = doc.pm(f"{base}.domain.{axis}min"), doc.pm(f"{base}.domain.{axis}max")
        if not lo < hi:
            _refuse(f"{base}.domain.{axis} extent: expected a positive extent (xmin < xmax, ymin < ymax)",
                    f"{base}.domain.{axis}max")
    if si.get("materials"):
        _refuse(f"materials: {label} on a rectangle requires an empty object; "
                f"{homogeneous} and given on the physics entry")
    mesh = si.get("mesh")
    if mesh is None or "subdivision_count" not in mesh:
        _refuse(f"mesh.subdivision_count: a rectangle {noun} document needs [nx, ny]", "mesh.subdivision_count",
                "E-KEY-MISSING")
    extra = sorted(set(doc.data["mesh"]) - {"subdivision_count"})
    if extra:
        _refuse(f"mesh: a rectangle {noun} document takes subdivision_count only, got {extra}; element sizes "
                "belong to region documents")
    if len(mesh["subdivision_count"]) != 2:
        _refuse("mesh.subdivision_count: expected [nx, ny]")
    results = si["results"]
    if results.get("plots"):
        _refuse(f"results.plots: {label} is headless; plots=true is not supported")
    return name, p


def _temperatures_03(p, path, sides=SIDES):
    temperatures = p["prescribed_temperature"]
    extra = sorted(set(temperatures) - set(sides))
    if extra:
        _refuse(f"{path}.prescribed_temperature: unsupported keys {extra}; a rectangle takes {list(sides)}")
    return temperatures


def natural_conditions_03(p, path, prescribed):
    """``({side: outward g}, {side: (h, ambient)})`` of an SI heat entry; ``inward_heat_flux`` is
    negated as ``0.0 - x`` (hazard H1), so galerkin keeps receiving its outward flux."""
    flux = p.get("inward_heat_flux", {})
    extra = sorted(set(flux) - set(SIDES))
    if extra:
        _refuse(f"{path}.inward_heat_flux: unsupported keys {extra}; a rectangle takes {list(SIDES)}")
    robin = p.get("convection", {})
    extra = sorted(set(robin) - set(SIDES))
    if extra:
        _refuse(f"{path}.convection: unsupported keys {extra}; a rectangle takes {list(SIDES)}")
    outward = {tag: 0.0 - float(value) for tag, value in flux.items()}
    convection = {tag: (float(c["heat_transfer_coefficient"]), float(c["ambient_temperature"]))
                  for tag, c in robin.items()}
    if set(prescribed) & (set(outward) | set(convection)):
        _refuse(path + ": natural condition overlaps a fully prescribed-temperature side")
    return outward, convection


def has_natural_conditions_03(p):
    """Presence selects the boundary layout, as in format 0.2 (an empty object included)."""
    return "inward_heat_flux" in p or "convection" in p


def validate_steady_rectangle_03(doc):
    """thermal.steady2d on a rectangle, format 0.3: the checks of today's contract on SI values."""
    name, p = rectangle_03(doc, "steady heat", ("thermal_conductivity", "prescribed_temperature"))
    path = "physics." + name
    if doc.si["study"] != {"type": "single"}:
        _refuse('thermal.steady2d supports only study {"type": "single"}')
    prescribed = {tag: float(v) for tag, v in _temperatures_03(p, path).items()}
    for a in ("left", "right"):
        for b in ("bottom", "top"):
            if a in prescribed and b in prescribed and prescribed[a] != prescribed[b]:
                _refuse(f"{path}.prescribed_temperature: conflicting corner temperatures on {a}/{b}")
    flux, convection = natural_conditions_03(p, path, prescribed)
    from .thermal_regions import default_boundaries_03
    default_boundaries_03(doc, name, p, SIDES)
    if not has_natural_conditions_03(p):
        if not prescribed:
            _refuse(f"{path}.prescribed_temperature: at least one exterior side is required")
    elif not prescribed and not any(h > 0 for h, _ in convection.values()):
        _refuse(path + ": requires a prescribed-temperature or positive-convection anchor; pure Neumann "
                "is unsupported")


def heat_inputs_03(doc):
    """The heat inputs (``views.HeatInputs``) of a validated format 0.3 steady rectangle."""
    name, p = next(iter(doc.si["physics"].items()))
    prescribed = {tag: float(v) for tag, v in p["prescribed_temperature"].items()}
    flux, convection = natural_conditions_03(p, "physics." + name, prescribed)
    source = p.get("heat_source_density")
    return views.HeatInputs(conductivity=float(p["thermal_conductivity"]),
                            heat_source=0.0 if source is None else float(source),     # hazard H9
                            dirichlet=prescribed, outward_flux=flux, convection=convection,
                            boundary_layout=has_natural_conditions_03(p))


def steady_result_versions_03(doc):
    """The (result_format, field_layout) pair a format 0.3 steady rectangle saves."""
    return V2_03 if has_natural_conditions_03(next(iter(doc.si["physics"].values()))) else V1_03
