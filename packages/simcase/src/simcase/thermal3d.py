# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``thermal.steady3d``: steady heat on a ``3d`` geometry component (format 0.3).

A thin document kind on the 3D geometry routes of the geometry document contract
(``docs/packages/simcase/geometry_document.md``, stage 5):

- a ``3d`` component holding only one ``layers`` feature of slab layers takes the
  ``meshine.extrude`` route (``geometry_document.layer_stack``): its footprint is the domain
  rectangle, meshed by meshine at ``mesh.element_size``, with the footprint's side tags
  ``left``, ``right``, ``bottom``, ``top`` and the stack's ``z0`` and ``z1``;
- every other ``3d`` component takes ``simcase.build_mesh3d`` (meshloom; experimental), with the
  tags ``x0``-``z1`` and ``void``, ``boundary_tags`` and the selections of the component.

The physics entry takes the keys of ``thermal.steady2d`` on regions that apply here:
``prescribed_temperature`` ({boundary name: temperature}; a tag, a named boundary selection,
a provenance name or a feature id on the meshloom route) and ``heat_source_density`` (one value
or {region: value}); every other exterior face is insulated. Each region's
``thermal_conductivity`` comes from ``materials.<m>``. The solve is
``galerkin.solve_steady_heat_3d``; the result is saved as ``summary.json``, ``fields.npz``,
``model.json`` and ``log.txt``, as the 2D kind saves its results.
"""

from __future__ import annotations

import copy
import math
import time
from fractions import Fraction

import numpy as np

from .diagnostics import DocumentError
from .registry import PhysicsKind, register

PHYSICS = "thermal.steady3d"
RESULT_FORMAT_03 = "thermal.steady3d-result-v1"
FIELD_LAYOUT_03 = "thermal3d-p1-node-tet-regions-v1"
ALLOWED_KEYS = frozenset({"type", "prescribed_temperature", "heat_source_density"})
EXTRUDE_TAGS = ("left", "right", "bottom", "top", "z0", "z1")
REACTION_SIGN = ("reaction_heat_rate: heat the prescribed-temperature constraint injects into the body; "
                 "outward_reaction_heat_rate = -sum(reaction_heat_rate)")
#: array name -> (registry quantity or None for a structural array, location, components)
FIELDS = {
    "node_coordinates": ("node_coordinates", "nodes", ["x", "y", "z"]),
    "tetrahedra": (None, "tetrahedron_connectivity", None),
    "tetrahedron_regions": (None, "tetrahedra", None),
    "temperature": ("temperature", "nodes", None),
    "heat_flux": ("heat_flux", "tetrahedron_centroids", ["x", "y", "z"]),
    "generated_heat_rate": ("generated_heat_rate", "nodes", None),
    "reaction_heat_rate": ("reaction_heat_rate", "nodes", None),
    "residual_heat_rate": ("residual_heat_rate", "nodes", None),
    "prescribed_node_ids": (None, "prescribed_nodes", None),
    "prescribed_temperature": ("prescribed_temperature", "prescribed_nodes", None),
}


def _refuse(message, path=None, code="E-CONTRACT"):
    raise DocumentError(message, path=path, code=code)


# ----------------------------------------------------------------------------- reading

def _slots():
    from .steady_boundary_contract import heat_slots
    keep = []
    for e in heat_slots(PHYSICS):
        if ".inward_heat_flux" in e["pattern"] or ".convection" in e["pattern"]:
            continue
        keep.append(e)
    return tuple(keep)


def _refuse_03(tree):
    """A thermal.steady3d document has a version 1 block with one ``3d`` component."""
    g = tree.get("geometry") if isinstance(tree, dict) else None
    comps = g.get("components") if isinstance(g, dict) else None
    if not isinstance(comps, dict) or len(comps) != 1:
        return ("geometry", "thermal.steady3d takes a version 1 geometry block with exactly one component, of "
                "dimension 3d")
    (cname, comp), = comps.items()
    if not isinstance(comp, dict) or comp.get("dimension") != "3d":
        return (f"geometry.components.{cname}.dimension",
                "thermal.steady3d takes a 3d component; 2d and axisymmetric regions take thermal.steady2d")
    return None


def is_extrude_route(comp) -> bool:
    """A component holding only one ``layers`` feature keeps the ``meshine.extrude`` route."""
    return len(comp.features) == 1 and comp.features[0].type == "layers"


def _entry(doc):
    doc.sole_physics()
    name, p = next(iter(doc.si["physics"].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse("physics: name must be an identifier", f"physics.{name}")
    path = f"physics.{name}"
    if "thermal_conductivity" in p:
        _refuse(f"{path}.thermal_conductivity: thermal.steady3d takes thermal_conductivity from materials.<m>",
                f"{path}.thermal_conductivity")
    extra = sorted(set(p) - ALLOWED_KEYS)
    if extra:
        _refuse(f"{path}.{extra[0]}: thermal.steady3d does not take {extra[0]} yet; it takes prescribed_temperature "
                "and heat_source_density, and every other exterior face is insulated", f"{path}.{extra[0]}",
                "E-KEY-UNKNOWN")
    return name, p, path


class _Plan:
    """What validation found: the route, the region -> material table, the boundary names and, on the
    meshloom route, the 3D complex."""

    def __init__(self, route, regions, tags, complex_=None, stack=None, handoff=None):
        self.route = route
        self.regions = regions              # region name -> material name (non-void regions)
        self.tags = tags                    # default and boundary_tags tags present on the exterior
        self.complex = complex_
        self.stack = stack
        self.handoff = handoff              # builder route: geometry_builders3d.Handoff


def _plan(doc) -> _Plan:
    from .geometry_document import GeometryError, layer_stack
    comp = doc.component
    if is_extrude_route(comp):
        f = comp.features[0]
        where = f"geometry.components.{comp.name}"
        if any("footprint" in lay for lay in f.data["layers"]):
            _refuse(f"{where}.features[0]: layers {f.name!r} has footprint layers; thermal.steady3d takes a lone "
                    "layers feature of slab layers on the extrude route (footprint layers are not taken yet)",
                    f"{where}.features[0]")
        if comp.selections or comp.boundary_tags:
            key = "selections" if comp.selections else "boundary_tags"
            _refuse(f"{where}.{key}: a lone layers feature takes the meshine.extrude route, whose faces carry its "
                    "tags only (z0, z1, left, right, bottom, top); selections and boundary_tags need the meshloom "
                    "route", f"{where}.{key}")
        try:
            stack = layer_stack(doc.geometry_model, comp.name)
        except GeometryError as exc:
            _refuse(str(exc), where)
        regions = dict(stack.materials)
        return _Plan("extrude", regions, set(EXTRUDE_TAGS), stack=stack)
    from . import geometry_builders3d as builders
    if builders.has_curved(comp):
        from .geometry_engine3d import _prepare
        try:
            _cx, _comp, ho, _info = _prepare(doc.data, comp.name)
        except GeometryError as exc:
            raise DocumentError(str(exc), path=exc.path, code=exc.code) from None
        tags = {next((p.split(".", 1)[1] for p in parts if p.startswith("domain.")), "void")
                for parts in ho.exterior.values()}
        return _Plan("builder", builder_regions(comp), tags, handoff=ho)
    from .geometry_engine3d import _evaluate
    try:
        cx = _evaluate(comp, through_meshloom=False)
    except GeometryError as exc:
        raise DocumentError(str(exc), path=exc.path, code=exc.code) from None
    regions = {}
    for c in cx.cells:
        if not c.void:
            regions.setdefault(c.region, c.material)
    tags = {f.tag for f in cx.faces if f.exterior}
    return _Plan("meshloom", regions, tags, complex_=cx)


def builder_regions(comp) -> dict:
    """Region -> material of a builder-shaped component (the background's when it has a material, and
    each cylinder's or sphere's that has one), in the builders' region names."""
    out = {}
    bg = comp.background.get("material")
    if bg is not None:
        out["background"] = bg
    for f in comp.features:
        if f.material is not None:
            out[f.region] = f.material
    return out


def _builder_parts(plan):
    """(exterior part names, interior part names) of the builder route."""
    ho = plan.handoff
    exterior = {p for parts in ho.exterior.values() for p in parts}
    return exterior, set(ho.interior.values())


def _builder_names(plan, comp, key, where):
    """The part names a ``prescribed_temperature`` key names on the builder route: a tag, a part, or a
    feature id (all its parts); an interior part is refused."""
    exterior, interior = _builder_parts(plan)
    if key in plan.tags or key in exterior:
        return {key}
    if key in interior:
        _refuse(f"Fixed temperature needs an outer face; {key} is inside", where)
    if any(f.id == key for f in comp.features):
        mine = {p for p in exterior | interior if p.split(".", 1)[0] == key}
        inside = sorted(mine & interior)
        if inside:
            _refuse(f"Fixed temperature needs an outer face; {key} is inside", where)
        return mine
    _refuse(f"{where}: {key!r} is not a tag, a part or a feature id of this component; expected one of "
            f"{sorted(plan.tags | exterior)}", where, "E-SELECTION-UNKNOWN")


def _boundary_faces(plan, comp, key, where):
    """The complex faces a ``prescribed_temperature`` key names (meshloom route)."""
    from .geometry_document import GeometryError
    from .geometry_engine3d import _resolve_boundary
    cx = plan.complex
    try:
        chosen = _resolve_boundary(cx, comp, key, where, ())
    except GeometryError as exc:
        _refuse(f"{where}: {exc}", where, "E-SELECTION-UNKNOWN")
    if not chosen:
        _refuse(f"{where}: {key!r} selects no face", where, "E-SELECTION-UNKNOWN")
    inside = [i for i in chosen if not cx.faces[i].exterior]
    if inside:
        _refuse(f"Fixed temperature needs an outer face; {key} is inside", where)
    return chosen


def validate_thermal3d(doc) -> None:
    from physmat.units import Diagnostic
    if doc.si is None:
        _refuse("thermal.steady3d reads format 0.3 documents only (\"openphysics\": \"0.3\")", "openphysics",
                "E-FORMAT")
    name, p, path = _entry(doc)
    mesh = doc.si.get("mesh") or {}
    if "element_size" not in mesh:
        _refuse('mesh.element_size: required by thermal.steady3d (for example "0.5 mm")', "mesh.element_size",
                "E-KEY-MISSING")
    for key in ("subdivision_count", "minimum_angle", "grading"):
        if key in (doc.data.get("mesh") or {}):
            _refuse(f"mesh.{key}: thermal.steady3d does not take {key}", f"mesh.{key}", "E-KEY-UNKNOWN")
    plan = _plan(doc)
    comp = doc.component
    materials = doc.si["materials"]
    for region, mname in plan.regions.items():
        where = f"materials.{mname}"
        if mname is None or mname not in materials:
            _refuse(f"{where}: region {region!r} names material {mname!r}, which materials does not give",
                    where, "E-MATERIAL-UNKNOWN")
        if "thermal_conductivity" not in materials[mname]:
            _refuse(f"{where}.thermal_conductivity: required by thermal.steady3d", f"{where}.thermal_conductivity",
                    "E-PROPERTY-MISSING")
    prescribed = p.get("prescribed_temperature") or {}
    if not prescribed:
        _refuse(f"{path}.prescribed_temperature: a steady heat document needs a prescribed temperature on at least "
                "one outer face; pure Neumann is unsupported", f"{path}.prescribed_temperature", "E-KEY-MISSING")
    for key in prescribed:
        where = f"{path}.prescribed_temperature.{key}"
        if plan.route == "extrude":
            if key not in EXTRUDE_TAGS:
                _refuse(f"{where}: no tag of that name on the extrude route; expected one of {list(EXTRUDE_TAGS)}",
                        where, "E-SELECTION-UNKNOWN")
        elif plan.route == "builder":
            _builder_names(plan, comp, key, where)
        else:
            _boundary_faces(plan, comp, key, where)
    source = p.get("heat_source_density")
    if isinstance(source, dict):
        for region in source:
            if region not in plan.regions:
                _refuse(f"{path}.heat_source_density.{region}: no meshed region of that name; expected one of "
                        f"{sorted(plan.regions)}", f"{path}.heat_source_density.{region}", "E-SELECTION-UNKNOWN")
    for tag in sorted(plan.tags - set(prescribed)):
        where = f"{path}.prescribed_temperature.{tag}"
        found = Diagnostic("I-DEFAULT-BOUNDARY", where, f"boundary {tag!r} has no condition: it is insulated")
        if not any(d.code == found.code and d.path == found.path for d in doc.diagnostics):
            doc.diagnostics.append(found)
    if doc.si["study"] != {"type": "single"}:
        _refuse('study: thermal.steady3d supports only {"type": "single"}', "study.type")
    if doc.si["results"].get("plots"):
        _refuse("results.plots: thermal.steady3d is headless; plots=true is not supported", "results.plots")


# ----------------------------------------------------------------------------- meshing and solving

def _metres(k) -> float:
    return float(Fraction(k, 10 ** 12))


def extrude_mesh(doc):
    """The ``meshine.extrude`` mesh of a lone slab ``layers`` component, as a ``galerkin.Mesh3D`` in metres:
    the domain rectangle meshed by meshine at the size, extruded through the layer levels with
    sub-layers at most that size thick."""
    return _extrude(doc.geometry_model, doc.component, doc.si["mesh"]["element_size"])


#: the largest footprint triangle meshine's refinement leaves: circumradius <= 0.6 h (``generate``'s
#: size_factor), so its area is at most that of the equilateral triangle of that circumradius
FOOTPRINT_TRIANGLE_AREA = 3 * math.sqrt(3) / 4 * 0.6 ** 2
#: up to this lower bound of footprint triangles the extrude count is made exact by meshing the footprint
EXACT_FOOTPRINT_TRIANGLES = 10_000


def _extrude_size(comp, element_size) -> float:
    f = comp.features[0]
    return _metres(f.mesh_size) if f.mesh_size is not None else float(element_size)


def _footprint(comp, h):
    from meshine import Domain, box_sides, generate, rectangle
    d = comp.domain
    x0, x1, y0, y1 = (_metres(d[k]) for k in ("xmin", "xmax", "ymin", "ymax"))
    plate = Domain(size=h)
    plate.add_region("plate", rectangle(x0, y0, x1, y1))
    return generate(plate, box_sides(x0, x1, y0, y1))


def _sub_layers(model, comp, h) -> tuple[list, dict, int]:
    """``(levels in m, the extrude table, solid sub-layers)``: meshine.extrude's ``size`` rule, the
    fewest sub-layers at most h thick, counted over the layers with a material."""
    from .geometry_document import layer_stack
    stack = layer_stack(model, comp.name)
    levels = [_metres(z) for z in stack.levels]
    table = stack.table_for(["plate"])
    counts = np.maximum(1, np.ceil(np.diff(np.asarray(levels, dtype=float)) / float(h) * (1 - 1e-12))).astype(np.int64)
    solid = int(sum(int(n) for n, m in zip(counts, table["plate"]) if m is not None))
    return levels, stack, solid


def extrude_count(model, comp, element_size) -> dict:
    """The tetrahedra of the extrude route without extruding: 3 per prism, footprint triangles T2 times
    solid sub-layers. Exact (the footprint meshed) when the lower bound A / (0.468 h^2) of T2 is at most
    ``EXACT_FOOTPRINT_TRIANGLES``; otherwise that lower bound. ``{"tetrahedra", "exact",
    "footprint_triangles", "sub_layers"}``."""
    h = _extrude_size(comp, element_size)
    d = comp.domain
    area = (_metres(d["xmax"]) - _metres(d["xmin"])) * (_metres(d["ymax"]) - _metres(d["ymin"]))
    lower = max(1, math.ceil(area / (FOOTPRINT_TRIANGLE_AREA * h * h) * (1 - 1e-12)))
    _, _, solid = _sub_layers(model, comp, h)
    if lower <= EXACT_FOOTPRINT_TRIANGLES:
        t2 = len(_footprint(comp, h).triangles)
        return {"tetrahedra": 3 * t2 * solid, "exact": True, "footprint_triangles": t2, "sub_layers": solid}
    return {"tetrahedra": 3 * lower * solid, "exact": False, "footprint_triangles": lower, "sub_layers": solid}


def extrude_limit_error(comp, count: int, limit: int, *, exact: bool):
    from .geometry_document import GeometryError
    what = f"{count} tetrahedra" if exact else f"at least {count} tetrahedra"
    return GeometryError(f"component {comp.name!r}: {what} on the extrude route (3 x footprint triangles x "
                         f"sub-layers); the limit is {limit} (mesh.element_count_limit)",
                         path="mesh.element_count_limit", code="E-MESH-ESTIMATE")


def _extrude(model, comp, element_size, *, limit: int | None = None):
    """The extrude mesh; with ``limit``, its exact count is checked after the footprint mesh and before
    the extrusion (``E-MESH-ESTIMATE``), so nothing over the limit is built."""
    from galerkin import from_mesher
    from meshine import extrude
    h = _extrude_size(comp, element_size)
    footprint = _footprint(comp, h)
    levels, stack, solid = _sub_layers(model, comp, h)
    if limit is not None and 3 * len(footprint.triangles) * solid > limit:
        raise extrude_limit_error(comp, 3 * len(footprint.triangles) * solid, limit, exact=True)
    mesh = extrude(footprint, levels, stack.table_for(footprint.region_names), size=h)
    return from_mesher(mesh)


def build_thermal3d_mesh(document, component: str | None = None):
    """The mesh ``thermal.steady3d`` solves a document's ``3d`` component on, by the kind's own route
    choice: for a component holding only one slab ``layers`` feature the ``meshine.extrude`` mesh
    (a ``galerkin.Mesh3D`` in metres), otherwise ``build_mesh3d``'s ``Mesh3DResult`` (meshloom, or
    meshloom's builder shapes). ``document`` is a format 0.3 document (a dict or a
    ``simcase.Document``) with a version 1 geometry block and a ``mesh`` block; it needs no physics
    block. ``solve_thermal3d`` solves on the result; ``mesh3d_to_arrays`` writes it as arrays."""
    from .geometry_document import _pick, parse
    from .geometry_engine3d import _mesh_options, build_mesh3d
    data = getattr(document, "data", document)
    model = parse(data)
    comp = _pick(model, component)
    if comp.dimension != "3d" or not is_extrude_route(comp):
        return build_mesh3d(data, component)
    return _extrude(model, comp, _element_size(data, comp),
                    limit=_mesh_options(data, comp)["element_count_limit"])


def _element_size(data, comp):
    """``mesh.element_size`` in m, as the document reader converts it (None when the feature gives one)."""
    from .geometry_document import GeometryError
    size = None
    if comp.features[0].mesh_size is None:
        mesh = data.get("mesh") if isinstance(data.get("mesh"), dict) else {}
        if "element_size" not in mesh:
            raise GeometryError("mesh.element_size: the meshine.extrude route needs an element size",
                                path="mesh.element_size", code="E-CONTRACT")
        from physmat import units
        c = units.convert(mesh["element_size"], "element_size", path="mesh.element_size")
        if not c.ok:
            raise GeometryError(f"mesh.element_size: {c.diagnostics[0].message if c.diagnostics else 'not a size'}",
                                path="mesh.element_size", code="E-VALUE-FORM")
        size = c.value
    return size


def build(doc):
    """``(galerkin.Mesh3D, route, Mesh3DResult or None)`` of a validated document."""
    if is_extrude_route(doc.component):
        return extrude_mesh(doc), "extrude", None
    from . import geometry_builders3d as builders
    from .geometry_engine3d import build_mesh3d
    built = build_mesh3d(doc.data)
    return built.mesh, ("builder" if builders.has_curved(doc.component) else "meshloom"), built


def prescribed_nodes(doc, mesh, built):
    """``{node: temperature}`` of the ``prescribed_temperature`` keys in document order, and
    ``{key: node ids}`` (a node fixed by two keys must get one temperature)."""
    name, p = next(iter(doc.si["physics"].items()))
    out, by_key = {}, {}
    for key, value in (p.get("prescribed_temperature") or {}).items():
        if built is None:
            nodes = np.asarray(mesh.boundary.get(key, []), dtype=int)
        else:
            nodes = _selection_nodes(doc, built, key)
        nodes = np.unique(nodes)
        if not len(nodes):
            _refuse(f"physics.{name}.prescribed_temperature.{key}: selects no mesh node",
                    f"physics.{name}.prescribed_temperature.{key}", "E-SELECTION-UNKNOWN")
        for node in nodes.tolist():
            if node in out and out[node] != value:
                _refuse(f"physics.{name}.prescribed_temperature: conflicting temperatures at node {node} "
                        f"({out[node]!r} K and {value!r} K from {key!r})",
                        f"physics.{name}.prescribed_temperature.{key}")
            out[node] = value
        by_key[key] = nodes
    return dict(sorted(out.items())), by_key


def _selection_nodes(doc, built, key):
    if built.complex is None:                  # builder route: tags and part names (validated)
        mesh = built.mesh
        if key in mesh.tagged_faces:
            return np.asarray(mesh.tagged_faces[key]).ravel()
        if key in built.provenance_faces:
            return np.asarray(built.provenance_faces[key]).ravel()
        faces = [v for p, v in built.provenance_faces.items() if p.split(".", 1)[0] == key]
        return np.concatenate(faces).ravel() if faces else np.zeros(0, dtype=int)
    from .geometry_engine3d import _resolve_boundary
    cx = built.complex
    chosen = _resolve_boundary(cx, doc.component, key, f"prescribed_temperature.{key}", ())
    faces = [built.facet_faces[fi] for fi, fidx in enumerate(built.face_of_facet) if fidx in chosen]
    return np.concatenate(faces).ravel() if faces else np.zeros(0, dtype=int)


def solver_inputs(doc, mesh, built):
    """The keyword arguments of ``galerkin.solve_steady_heat_3d`` for this document."""
    name, p = next(iter(doc.si["physics"].items()))
    materials = doc.si["materials"]
    plan_regions = _region_materials(doc, mesh)
    kappa = {r: float(materials[m]["thermal_conductivity"]) for r, m in plan_regions.items()}
    source = p.get("heat_source_density")
    if isinstance(source, dict):
        source = {r: float(source.get(r, 0.0)) for r in mesh.region_names}
    elif source is not None:
        source = float(source)
    fixed, by_key = prescribed_nodes(doc, mesh, built)
    return {"thermal_conductivity": kappa, "prescribed_temperature": fixed, "heat_source_density": source}, by_key


def _region_materials(doc, mesh):
    comp = doc.component
    if is_extrude_route(comp):
        from .geometry_document import layer_stack
        mats = layer_stack(doc.geometry_model, comp.name).materials
        return {r: mats[r] for r in mesh.region_names}
    from . import geometry_builders3d as builders
    if builders.has_curved(comp):
        table = builder_regions(comp)
        return {r: table[r] for r in mesh.region_names}
    from .geometry_engine3d import _evaluate
    cx = _evaluate(comp, through_meshloom=False)
    table = {}
    for c in cx.cells:
        if not c.void:
            table.setdefault(c.region, c.material)
    return {r: table[r] for r in mesh.region_names}


def run_thermal3d(doc, verbose=True):
    doc.validate()
    doc = doc.copy()
    doc.validate()
    t0 = time.perf_counter()
    from .geometry_document import GeometryError
    try:
        mesh, route, built = build(doc)
    except GeometryError as exc:
        raise DocumentError(str(exc), path=exc.path, code=exc.code) from exc
    return _solve(doc, mesh, route, built, time.perf_counter() - t0, verbose)


def solve_thermal3d(doc, mesh, verbose=True):
    """Solve a ``thermal.steady3d`` document on an existing mesh: ``build_thermal3d_mesh``'s result
    for the document (a ``Mesh3DResult``, or the ``galerkin.Mesh3D`` of the ``meshine.extrude``
    route), or that mesh read back by ``mesh3d_from_arrays``. The result is ``simcase.run``'s,
    bit for bit, with no mesh time. A mesh of the other route, or of another component, is refused."""
    doc.validate()
    if doc.sole_physics()[1].get("type") != PHYSICS:
        raise DocumentError(f"solve_thermal3d takes a {PHYSICS} document", path="physics", code="E-CONTRACT")
    doc = doc.copy()
    doc.validate()
    mesh, route, built = _accept(doc, mesh)
    return _solve(doc, mesh, route, built, 0.0, verbose)


def _accept(doc, mesh):
    """``(galerkin mesh, route, Mesh3DResult or None)`` of a given mesh, checked against the route
    ``build`` would take for the document."""
    from galerkin.mesh3d import Mesh3D
    from . import geometry_builders3d as builders
    from .geometry_engine3d import Mesh3DResult
    comp = doc.component
    where = f"geometry.components.{comp.name}"
    if is_extrude_route(comp):
        if not isinstance(mesh, Mesh3D):
            _refuse(f"{where}: a component holding only one layers feature is solved on its meshine.extrude mesh "
                    "(build_thermal3d_mesh), not on a build_mesh3d result", where)
        return mesh, "extrude", None
    curved = builders.has_curved(comp)
    route = "builder" if curved else "meshloom"
    if not isinstance(mesh, Mesh3DResult) or (mesh.complex is None) != curved:
        _refuse(f"{where}: this component takes the {route} route; solve it on its build_mesh3d result "
                "(build_thermal3d_mesh), not on a meshine.extrude mesh or another route's", where)
    if mesh.complex is not None and mesh.complex.component != comp.name:
        _refuse(f"{where}: the mesh is of component {mesh.complex.component!r}", where)
    return mesh.mesh, route, mesh


def _solve(doc, mesh, route, built, t_mesh, verbose):
    from galerkin.thermal3d import solve_steady_heat_3d
    name, _p = doc.sole_physics()
    if built is not None:
        doc.diagnostics.extend(built.diagnostics)          # I-MESH-ESTIMATE (and I-SURFACE-SAMPLED)
    t0 = time.perf_counter()
    kwargs, by_key = solver_inputs(doc, mesh, built)
    t_mesh += time.perf_counter() - t0
    t0 = time.perf_counter()
    try:
        solution = solve_steady_heat_3d(mesh, **kwargs)
    except ValueError as exc:
        raise ValueError(f"physics.{name} ({PHYSICS}): {exc}") from exc
    t_solve = time.perf_counter() - t0
    result = Thermal3DRunResult(doc, mesh, solution, route, kwargs, by_key,
                                {"mesh": t_mesh, "solve": t_solve}, built)
    printed = [doc.summary(),
               f"temperature: {solution.temperature.min():.12g} K to {solution.temperature.max():.12g} K",
               f"generated_heat_rate {float(solution.generated_heat_rate.sum()):.12g} W; "
               f"outward_reaction_heat_rate {-float(solution.reaction_heat_rate.sum()):.12g} W"]
    from .thermal import log_lines_03
    result.log = log_lines_03(doc, printed)
    if verbose:
        print("\n".join(printed))
    result.summary()                    # validate complete output even without saving raw fields
    return result


# ----------------------------------------------------------------------------- the result

class Thermal3DRunResult:
    """The result of a ``thermal.steady3d`` run: the mesh (``galerkin.Mesh3D``, metres), the solution
    (``galerkin`` ``SteadyHeat3DResult``) and the route it was meshed on."""

    result_format = RESULT_FORMAT_03
    field_layout = FIELD_LAYOUT_03

    def __init__(self, doc, mesh, solution, route, inputs, by_key, timings, built=None):
        self.doc = doc
        self.mesh = mesh
        self.solution = solution
        self.route = route
        self.inputs = inputs
        self.by_key = by_key
        self.timings = timings
        self.built = built
        self.log = []

    @property
    def temperature(self):
        return self.solution.temperature

    @property
    def heat_flux(self):
        return self.solution.heat_flux

    @property
    def reaction_heat_rate(self):
        return self.solution.reaction_heat_rate

    @property
    def node_coordinates(self):
        return self.mesh.nodes

    @property
    def tetrahedra(self):
        return self.mesh.tets

    def arrays(self) -> dict:
        fixed = self.inputs["prescribed_temperature"]
        return {"node_coordinates": np.asarray(self.mesh.nodes, dtype=float),
                "tetrahedra": np.asarray(self.mesh.tets, dtype=np.int64),
                "tetrahedron_regions": np.asarray(self.mesh.regions, dtype=np.int64),
                "temperature": np.asarray(self.solution.temperature, dtype=float),
                "heat_flux": np.asarray(self.solution.heat_flux, dtype=float),
                "generated_heat_rate": np.asarray(self.solution.generated_heat_rate, dtype=float),
                "reaction_heat_rate": np.asarray(self.solution.reaction_heat_rate, dtype=float),
                "residual_heat_rate": np.asarray(self.solution.residual_heat_rate, dtype=float),
                "prescribed_node_ids": np.array(sorted(fixed), dtype=np.int64),
                "prescribed_temperature": np.array([fixed[k] for k in sorted(fixed)], dtype=float)}

    def heat_rates_by_boundary(self) -> dict:
        """W: the reaction heat rate of each ``prescribed_temperature`` key (a node fixed by two keys counts
        under the first), and the boundary heat rate of each exterior tag."""
        reaction = np.asarray(self.solution.reaction_heat_rate)
        out, seen = {}, set()
        for key, nodes in self.by_key.items():
            mine = [n for n in nodes.tolist() if n not in seen]
            seen.update(mine)
            out[key] = float(reaction[mine].sum())
        return out

    def summary(self) -> dict:
        from . import results_common
        vo = results_common.value_object
        doc = self.doc
        name, p = next(iter(doc.si["physics"].items()))
        arrays = self.arrays()
        fields = {k: {"quantity": FIELDS[k][0], "location": FIELDS[k][1], "shape": list(a.shape),
                      "components": FIELDS[k][2]} for k, a in arrays.items()}
        maps = results_common.field_maps(fields)
        del maps["field_time_axes"]
        materials = doc.si["materials"]
        table = _region_materials(doc, self.mesh)
        p_ = self.mesh.nodes[self.mesh.tets]
        vol = np.abs(np.einsum("ti,ti->t", p_[:, 1] - p_[:, 0],
                               np.cross(p_[:, 2] - p_[:, 0], p_[:, 3] - p_[:, 0]))) / 6
        load = np.asarray(self.solution.generated_heat_rate)
        reaction = np.asarray(self.solution.reaction_heat_rate)
        source_heat, outward = float(load.sum()), -float(reaction.sum())
        scale = max(float(np.abs(load).sum() + np.abs(reaction).sum()), np.finfo(float).tiny)
        k = np.asarray(self.solution.thermal_conductivity)
        result = {"name": doc.si["name"], "physics_name": name, "physics_type": PHYSICS,
                  **results_common.envelope(doc, result_format=self.result_format, field_layout=self.field_layout,
                                            timing_=results_common.timing(self.timings["mesh"],
                                                                          self.timings["solve"])),
                  **maps,
                  "mesh_route": self.route,
                  "region_names": list(self.mesh.region_names),
                  "regions": {r: {"material": table[r], "tetrahedra": int(np.sum(self.mesh.regions == i)),
                                  "volume": vo(float(vol[self.mesh.regions == i].sum()), "volume")}
                              for i, r in enumerate(self.mesh.region_names)},
                  "materials": {m: {key: vo(v, key) if isinstance(v, (int, float)) and not isinstance(v, bool)
                                    else copy.deepcopy(v) for key, v in spec.items()}
                                for m, spec in materials.items()},
                  "reaction_sign": REACTION_SIGN,
                  "mesh": {"nodes": int(self.mesh.num_nodes), "tetrahedra": int(self.mesh.num_tets),
                           "boundary_tags": sorted(self.mesh.tagged_faces)},
                  "study": {"type": "single"}}
        source = p.get("heat_source_density")
        if isinstance(source, dict):
            result["heat_source_density"] = {r: vo(v, "heat_source_density") for r, v in source.items()}
        elif source is not None:
            result["heat_source_density"] = vo(source, "heat_source_density")
        result["prescribed_temperature"] = {t: vo(v, "prescribed_temperature")
                                            for t, v in (p.get("prescribed_temperature") or {}).items()}
        result["prescribed_nodes"] = len(arrays["prescribed_node_ids"])
        result["reaction_heat_rate_by_boundary"] = {key: vo(v, "reaction_heat_rate")
                                                    for key, v in self.heat_rates_by_boundary().items()}
        result["minimum_thermal_conductivity"] = vo(k.min(), "minimum_thermal_conductivity")
        result["maximum_thermal_conductivity"] = vo(k.max(), "maximum_thermal_conductivity")
        result["minimum_temperature"] = vo(self.solution.temperature.min(), "minimum_temperature")
        result["maximum_temperature"] = vo(self.solution.temperature.max(), "maximum_temperature")
        result["generated_heat_rate"] = vo(source_heat, "generated_heat_rate")
        result["outward_reaction_heat_rate"] = vo(outward, "outward_reaction_heat_rate")
        result["heat_rate_imbalance"] = vo(outward - source_heat, "heat_rate_imbalance")
        result["relative_conservation_residual"] = vo(abs(outward - source_heat) / scale,
                                                      "relative_conservation_residual")
        results_common.dumps_summary(result)            # finite JSON only
        return result

    def save(self, outdir):
        """``summary.json``, ``fields.npz`` (with ``result_format``, ``field_layout`` and ``metadata_json``),
        ``model.json`` and ``log.txt``, written as the 2D heat kind writes them."""
        from . import results_common
        from .thermal import _OwnedOutput, model_bytes_03
        owned = _OwnedOutput(outdir)
        try:
            owned.write(".incomplete", lambda f: f.write(b"incomplete thermal result\n"))
            summary = self.summary()
            encoded = results_common.dumps_summary(summary).encode("utf-8")
            model = model_bytes_03(self.doc)
            owned.write("model.json", lambda f: f.write(model))
            owned.write("log.txt", lambda f: f.write(("\n".join(self.log) + "\n").encode("utf-8")))
            if self.doc.si["results"]["save_fields"]:
                arrays = dict(self.arrays(), result_format=self.result_format, field_layout=self.field_layout,
                              metadata_json=results_common.metadata_json(summary))
                for key, value in arrays.items():
                    a = np.asarray(value)
                    if a.dtype.kind in "iuf" and not np.isfinite(a).all():
                        raise ValueError(f"thermal raw array {key} must be finite")
                owned.write("fields.npz", lambda f: np.savez_compressed(f, **arrays))
            owned.write("summary.json", lambda f: f.write(encoded))
            owned.finish()
        except Exception:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def summary_thermal3d(doc) -> str:
    doc.validate()
    from .thermal import _authored
    name, p = next(iter(doc.si["physics"].items()))
    comp = doc.component
    route = "meshine.extrude" if is_extrude_route(comp) else "meshloom (experimental)"
    where = f"physics.{name}"
    out = [f'{doc.si["name"]} (openphysics 0.3)', f"  physics {name}: steady heat on a 3d component",
           f"  component {comp.name}: {len(comp.features)} feature(s), mesh route {route}; element_size "
           f"{_authored(doc, 'mesh.element_size')}"]
    temperatures = {t: _authored(doc, f"{where}.prescribed_temperature.{t}")
                    for t in (p.get("prescribed_temperature") or {})}
    out.append(f"  prescribed_temperature {temperatures}; other exterior faces insulated")
    source = p.get("heat_source_density")
    out.append("  no heat_source_density" if source is None else "  heat_source_density given")
    out.append(f"  result: {RESULT_FORMAT_03}; layout: {FIELD_LAYOUT_03}")
    return "\n".join(out)


#: the kind this module registers; the built-in provider openphysics-fem reads it here
KIND = register(PhysicsKind(
    name=PHYSICS, types=frozenset({PHYSICS}), precedence=35,
    validate=validate_thermal3d, run=run_thermal3d, summary=summary_thermal3d,
    result_types=(Thermal3DRunResult,), fresh_output=True,
    stage_refusal="{stage} is an EM 2D stage; use run(document) for thermal.steady3d",
    slots=_slots(), forms_03=frozenset({"v1"}), refuse_03=_refuse_03, geometry_3d=True))
