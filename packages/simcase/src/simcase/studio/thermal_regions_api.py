# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady and transient heat region documents in Studio; an ordinary public simcase consumer.

A region document (a heat document whose ``geometry`` has ``shapes`` or ``background``,
or is a version 1 geometry block) takes this path on the same routes as rectangle documents, which keep their own code
unchanged. Each stage bounds the cost of the next:

1. on the event loop, O(JSON size): the format 0.3 envelope, the physics entry, a stray
   ``mesh.subdivision_count`` and, for transient documents, the requested times (the rectangle
   checks, copied);
2. in a worker thread: ``region_complexity`` on the raw JSON (shapes, circles, polygon
   points, then boundary crossings), ``Document.from_dict``, ``check_mesh_limits`` (loop
   vertices after the shapes' booleans), the summary floor and, for a run, the run copy;
3. in the job: ``run`` with ``max_nodes``, ``max_triangles`` and ``max_input_vertices``, so
   an over-fine mesh is refused after meshing and before the solve.

The policy values are candidates (``resource_policy`` stays ``candidate-unmeasured``).
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict, dataclass
import json
import math
from types import MappingProxyType

import anyio
import numpy as np
from fastapi.concurrency import run_in_threadpool
from simcase import (Document, DocumentError, MeshLimitError, ThermalRunResult,
                     TransientThermalRunResult, check_mesh_limits, has_region_geometry, region_complexity,
                     void_area)

from . import thermal_api as common
from . import transient_thermal_api as transient

# Region documents are format 0.3: arrays under registry names, SI values (units batch C5b).
STEADY_PAIR = ("thermal.steady2d-regions-result-v2", "thermal2d-p1-node-cell-regions-v2")
TRANSIENT_PAIR = ("thermal.transient2d-regions-result-v2", "thermal2d-transient-p1-node-cell-regions-v2")
STEADY_PAYLOAD = "studio-thermal-steady-regions-v2"
TRANSIENT_MANIFEST = "studio-thermal-transient-regions-v2"   # frames and histories: the rectangle's v2 IDs
REGION_KEYS = ("material", "triangles", "area")
MESH_KEYS = {"nodes", "triangles"}
SUBDIVISIONS = ("region documents (geometry.shapes or geometry.background) set mesh.element_size; "
                "mesh.subdivision_count belongs to rectangle documents")
FORMAT_03 = ('thermal Studio reads format 0.3 region documents ("openphysics": "0.3", values with their units, '
             'element_size quantities); format 0.2 region documents are not read')


@dataclass(frozen=True)
class RegionLimits:
    """Studio's limits for region documents, checked before a job is allocated."""
    max_shapes: int = 64
    max_circles: int = 16
    max_polygon_points: int = 512
    max_boundary_crossings: int = 1024
    max_input_vertices: int = 2048

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) is not int or value <= 0:
                raise ValueError("Studio region limits must be positive integers")


def applies(raw, kind):
    """A raw document of physics ``kind`` that declares region geometry.

    simcase's own choice of the region path (``simcase.has_region_geometry``):
    a physics entry of that type and a ``geometry`` object with ``shapes`` or ``background``,
    or a version 1 block whose component has features or a background material (a
    homogeneous rectangle written as version 1 is compiled to the flat rectangle form at load
    and takes the rectangle path)."""
    return has_region_geometry(raw, kind)


def raw_preflight(raw, kind, limits):
    """Event-loop checks of a raw region document; the transient time count, else None."""
    if kind == common.KIND:
        if not isinstance(raw, dict):   # defensive: applies() is false for a non-object
            raise common.ThermalAPIError("invalid_envelope", "doc must be an object", path="doc")
        physics = raw.get("physics")
        if (not isinstance(physics, dict) or len(physics) != 1
                or not isinstance(next(iter(physics.values())), dict)
                or next(iter(physics.values())).get("type") != common.KIND):
            raise common.ThermalAPIError("unsupported_physics", "thermal Studio accepts one thermal.steady2d entry",
                                         path="physics")
        if not common.v2_available():   # region results always carry the boundary arrays
            raise common.ThermalAPIError("unsupported_result_format",
                                         "matching public steady boundary runtime is required")
    else:
        transient.require(isinstance(raw, dict), "doc must be an object", code="invalid_envelope")
        physics = raw.get("physics")
        transient.require(isinstance(physics, dict) and len(physics) == 1
                          and isinstance(next(iter(physics.values())), dict)
                          and next(iter(physics.values())).get("type") == transient.KIND,
                          "transient route accepts one thermal.transient2d entry", code="unsupported_physics")
    if raw.get("openphysics") != "0.3":
        raise common.ThermalAPIError("invalid_document", FORMAT_03, path="openphysics")
    mesh = raw.get("mesh")
    if isinstance(mesh, dict) and "subdivision_count" in mesh:
        raise common.ThermalAPIError("invalid_document", SUBDIVISIONS, path="mesh.subdivision_count")
    if kind == common.KIND:
        return None
    # The rectangle time checks (transient_thermal_api.preflight), same codes and messages.
    study = raw.get("study")
    time = study.get("time") if isinstance(study, dict) else None
    times = time.get("values") if isinstance(time, dict) else None
    transient.require(isinstance(times, list) and len(times) >= 2,
                      "study.time must be a tagged array of at least two requested times", code="invalid_document")
    transient.require(len(times) <= transient.MAX_TIMES, "too many requested times", 413, "history_limit_exceeded")
    try:
        valid = (all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in times)
                 and all(b > a and math.isfinite(b-a) for a, b in zip(times, times[1:])))
    except OverflowError:
        valid = False
    transient.require(valid, "requested times must be finite strictly increasing values", code="invalid_document")
    return len(times)


@dataclass(frozen=True)
class Plan:
    """Node and triangle caps of one region job, and for each whether the raw history of
    ``times`` requested times set it (rather than the ThermalLimits value)."""
    n_cap: int
    m_cap: int
    nodes_from_history: bool = False
    triangles_from_history: bool = False
    times: int | None = None


def plan(kind, limits, nt):
    if kind == common.KIND:
        return Plan(limits.max_nodes, limits.max_triangles)
    # Raw history with D <= N and M <= m_cap <= 2 n_cap: 6nt N + (2nt+4) M + 3nt scalars,
    # region ids included, at most (10nt+8) n_cap + 3nt <= RAW_BYTES/8.
    n_hist = (transient.RAW_BYTES//8 - 3*nt)//(10*nt + 8)
    n_cap = min(limits.max_nodes, n_hist)
    m_cap = min(limits.max_triangles, 2*n_cap)
    return Plan(n_cap, m_cap, n_hist < limits.max_nodes, 2*n_cap < limits.max_triangles, nt)


@dataclass(frozen=True)
class RegionInput:
    doc: object
    run_doc: object
    plan: Plan
    kind: str
    loop_vertices: int
    client_revision: int
    request_seq: int

    def tags(self):
        return {"client_revision": self.client_revision, "request_seq": self.request_seq}


def runtime_available(kind, limits):
    if kind == common.KIND:
        return common.runtime_available() and common.v2_available()
    return transient.runtime_available(limits)


def capability(kind, limits, rlimits):
    pair = STEADY_PAIR if kind == common.KIND else TRANSIENT_PAIR
    formats = [STEADY_PAYLOAD] if kind == common.KIND else [TRANSIENT_MANIFEST, transient.FRAME, transient.HISTORY]
    return {"supported": True, "run_enabled": runtime_available(kind, limits),
            "result_formats": [pair[0]], "field_layouts": [pair[1]], "payload_formats": formats,
            "limits": asdict(rlimits)}


def _geometry_limit(message, path="geometry.shapes"):
    return common.ThermalAPIError("geometry_limit_exceeded", message, 413, path=path)


def _shapes_path(raw):
    """Where the shapes of a raw region document are: a version 1 block's features count as shapes."""
    geometry = raw.get("geometry") if isinstance(raw, dict) else None
    return "geometry.components" if isinstance(geometry, dict) and "version" in geometry else "geometry.shapes"


def _check_complexity(raw, rlimits):
    counts = region_complexity(raw, max_shapes=rlimits.max_shapes, max_circles=rlimits.max_circles,
                               max_polygon_points=rlimits.max_polygon_points)
    path = _shapes_path(raw)
    for what, count, name in (("shapes", counts.shapes, "max_shapes"),
                              ("circles", counts.circles, "max_circles"),
                              ("polygon points", counts.polygon_points, "max_polygon_points")):
        limit = getattr(rlimits, name)
        if count > limit:
            raise _geometry_limit(f"{path} has {count} {what}, more than Studio's region limit "
                                  f"{name}={limit}", path)
    if counts.boundary_crossings > rlimits.max_boundary_crossings:
        raise _geometry_limit(f"the shapes' boundaries cross {counts.boundary_crossings} times (segment pairs "
                              f"of different shapes), more than Studio's region limit max_boundary_crossings="
                              f"{rlimits.max_boundary_crossings}", path)


def _summary_floor(doc, limits):
    """Refuse a document whose summary cannot fit: the summary copies these three values."""
    _, physics = next(iter(doc.si["physics"].items()))
    floor = {"name": doc.si["name"], "materials": doc.si["materials"],
             "heat_source_density": physics.get("heat_source_density")}
    try:
        common.encode_json(floor, limits.metadata_bytes)
    except common.ThermalAPIError as exc:
        raise common.ThermalAPIError(
            "payload_limit_exceeded", "the result summary copies the document's name, materials and heat "
            f"sources, which encode to more than metadata_bytes={limits.metadata_bytes}", 413,
            path="materials") from exc


def _accept(raw, kind, limits, rlimits, nt, tags, for_run, exact=None):
    """Worker-thread validation; every failure becomes a tagged ThermalAPIError. ``raw`` holds the
    doubles of the authored numbers (the caps read these); the document reads ``exact``, the tree
    of the request bytes with every number as written."""
    try:
        _check_complexity(raw, rlimits)
        try:
            doc = Document.from_dict(raw if exact is None else exact)
        except (DocumentError, ValueError, TypeError, OverflowError) as exc:
            raise common.ThermalAPIError("invalid_document", str(exc), 400 if for_run else 200) from exc
        if getattr(doc, "is_version_1", False) and doc.component.dimension == "axisymmetric":
            raise common.ThermalAPIError("invalid_document", "Studio shows Cartesian region results only; an "
                                         "axisymmetric component has no Studio payload yet (run it with simcase)",
                                         400 if for_run else 200)
        count = check_mesh_limits(doc, max_input_vertices=rlimits.max_input_vertices)
        _summary_floor(doc, limits)
        run_doc = None
        if for_run:
            run_doc = doc.copy()        # copy() resets the scale; validate() restores it
            run_doc.validate()
        return RegionInput(doc, run_doc, plan(kind, limits, nt), kind, count, **tags)
    except common.ThermalAPIError:
        raise
    except MeshLimitError as exc:
        raise _geometry_limit(str(exc)) from exc
    except Exception as exc:
        raise common.ThermalAPIError("invalid_document", str(exc), 400 if for_run else 200) from exc


class Route:
    """The region path of one thermal route, given to thermal_api.read_request."""

    def __init__(self, kind, limits, rlimits):
        self.kind, self.limits, self.rlimits = kind, limits, rlimits

    def applies(self, raw):
        return applies(raw, self.kind)

    async def read(self, raw, tags, *, for_run, exact=None):
        nt = raw_preflight(raw, self.kind, self.limits)
        if for_run and not runtime_available(self.kind, self.limits):
            raise common.ThermalAPIError("unsupported_public_api", "matching public result IDs are required")
        return await _wait_for_thread(_accept, raw, self.kind, self.limits, self.rlimits, nt, tags, for_run,
                                      exact)


async def _wait_for_thread(func, *args):
    """Run ``func`` in a worker thread and wait for it to return, even if this request is
    cancelled meanwhile; then raise the cancellation.

    The caller's ingress permit bounds region validation to one thread at a time, so it
    must stay held until the thread is done. run_in_threadpool alone does not ensure that:
    a native asyncio cancellation ends its wait at once while the thread keeps running.
    The wait is shielded from anyio cancel scopes, which would otherwise cancel it again
    on every event-loop iteration (a busy loop until the thread returns); a native
    cancellation still interrupts it and is raised once the thread is done, and a scope
    cancellation is raised at the checkpoint after the wait."""
    task = asyncio.ensure_future(run_in_threadpool(func, *args))
    cancelled = None
    while not task.done():
        try:
            with anyio.CancelScope(shield=True):
                await asyncio.wait({task})
        except asyncio.CancelledError as exc:
            cancelled = exc
    if not task.cancelled():
        task.exception()       # retrieved now: a cancelled request never reads the result
    if cancelled is not None:
        raise cancelled
    await asyncio.sleep(0)     # a checkpoint: a cancelled scope ends the request here
    return task.result()


def job_error(exc, plan):
    """The Studio error for a failed region run, or None for an unexpected failure."""
    if isinstance(exc, MeshLimitError):
        if exc.quantity == "input_vertices":     # defensive: validation counted them already
            return _geometry_limit(str(exc))
        # meshine's stop at max_points (count None) is a node refusal.
        if plan.triangles_from_history if exc.quantity == "triangles" else plan.nodes_from_history:
            return common.ThermalAPIError(
                "history_limit_exceeded", f"{exc}; this limit comes from {plan.times} saved times and the "
                f"{transient.RAW_BYTES//1024**2} MiB raw history cap", 413)
        return common.ThermalAPIError("mesh_limit_exceeded", str(exc), 413)
    if isinstance(exc, DocumentError):
        return common.ThermalAPIError("invalid_document", str(exc), 400)
    return None


def _require(condition, message):
    if not condition:
        raise common.ThermalAPIError("invalid_result", message, 500)


def _exact_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _cell_areas(nodes, triangles, kind):
    """Each producer's own triangle-area expression, so that region areas compare exactly."""
    if kind == common.KIND:   # galerkin Mesh.areas, as the steady summary uses it
        p = nodes[triangles]
        return 0.5*np.abs((p[:, 1, 0]-p[:, 0, 0])*(p[:, 2, 1]-p[:, 0, 1])
                          - (p[:, 2, 0]-p[:, 0, 0])*(p[:, 1, 1]-p[:, 0, 1]))
    v = nodes[triangles][:, 1:]-nodes[triangles][:, :1]   # the transient summary's expression
    return .5*(v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0])


def _value_objects(tree):
    """A resolved SI subtree as the summary writes it: each number a ``{value, unit}`` object
    of the quantity its key names, text as is."""
    from physmat.units import quantity

    def walk(node, name):
        if isinstance(node, dict):
            return {k: walk(v, k if isinstance(v, (dict, int, float)) and not isinstance(v, bool) and k in
                            _QUANTITIES else name) for k, v in node.items()}
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            return {"value": float(node), "unit": quantity(name).unit}
        return copy.deepcopy(node)
    return walk(tree, None)


#: the quantity names under which a region summary echoes material and source values
_QUANTITIES = ("thermal_conductivity", "volumetric_heat_capacity", "electrical_conductivity", "youngs_modulus",
               "poisson_ratio", "linear_expansion_coefficient")


def check_regions(summary, names, ids, nodes, triangles, doc, rlimits, kind):
    """Region names, ids, per-region counts, areas and materials against the document."""
    _require(isinstance(names, (list, tuple)) and 1 <= len(names) <= rlimits.max_shapes+1
             and all(isinstance(n, str) and n for n in names) and len(set(names)) == len(names),
             "region names must be unique nonempty strings")
    names = list(names)
    _require(summary.get("region_names") == names, "summary region names disagree with the result")
    count = len(names)
    _require(ids.ndim == 1 and len(ids) == len(triangles) and ids.dtype.kind in "iu"
             and not np.any(ids < 0) and not np.any(ids >= count), "triangle region ids outside the regions")
    # doc.regions() and doc.background read a flat block's shapes or a version 1 block's features
    assigned = {entry["name"]: entry["material"] for entry in doc.regions()}
    assigned["background"] = doc.background["material"]
    regions = summary.get("regions")
    _require(isinstance(regions, dict) and set(regions) == set(names), "summary regions disagree with the names")
    cells = np.bincount(ids, minlength=count)
    areas = _cell_areas(nodes, triangles, kind)
    total = 0.
    for i, name in enumerate(names):
        entry = regions[name]
        _require(isinstance(entry, dict) and set(entry) == set(REGION_KEYS), name+": region entry keys")
        _require(name in assigned and entry["material"] == assigned[name], name+": region material disagrees")
        _require(type(entry["triangles"]) is int and entry["triangles"] == int(cells[i]),
                 name+": region triangle count disagrees")
        area = entry["area"].get("value") if isinstance(entry["area"], dict) else None
        _require(isinstance(entry["area"], dict) and entry["area"].get("unit") == "m^2"
                 and type(area) is float and math.isfinite(area) and area >= 0
                 and area == float(areas[ids == i].sum()), name+": region area disagrees")
        total += area
    domain = common.geometry_block(doc)[1]["domain"]
    expected = (domain["xmax"]-domain["xmin"])*(domain["ymax"]-domain["ymin"])
    void = 0.0
    if getattr(doc, "is_version_1", False):
        # a void feature is a hole: its cells are not meshed, so the regions tile the domain
        # minus the void area (simcase.thermal_regions.void_area, exact). A round border
        # between material and void is meshed as an inscribed polygon, which moves area from
        # one side to the other: within 1e-2 of the void area either way (a 16-gon leaves
        # 2.5e-2 of a disc; the mesher's circles have at least 16 vertices and the hand-off's
        # count grows with the mesh size).
        void = void_area(doc)
    low = expected - void
    _require(math.isfinite(expected) and low > 0 and abs(total-low) <= 1e-2*void + 1e-9*expected,
             "region areas do not add up to the domain minus its void features")
    physics = next(iter(doc.si["physics"].values()))
    _require(_exact_json(summary.get("materials")) == _exact_json(_value_objects(doc.si["materials"])),
             "summary materials disagree with the document")
    source = physics.get("heat_source_density")
    expected_source = (None if source is None else {r: {"value": float(v), "unit": "W/m^3"} for r, v in source.items()}
                       if isinstance(source, dict) else {"value": float(source), "unit": "W/m^3"})
    _require(_exact_json(summary.get("heat_source_density")) == _exact_json(expected_source),
             "summary heat sources disagree with the document")


def _mesh_summary(summary, n, m, doc):
    mesh = summary.get("mesh")
    size = summary.get("resolved_inputs", {}).get("mesh.element_size", {})
    _require(isinstance(mesh, dict) and set(mesh) == MESH_KEYS
             and type(mesh["nodes"]) is int and mesh["nodes"] == n
             and type(mesh["triangles"]) is int and mesh["triangles"] == m
             and size.get("value") == doc.si["mesh"]["element_size"], "summary mesh disagrees with the result")


def _length(summary, doc):
    """The display length unit: the geometry's, as the summary's inputs give it."""
    unit, length_in_m = common.length_unit(doc)
    _require(common.domain_input(summary, doc).get("length_unit") == unit, "document/summary length_unit mismatch")
    _require(not isinstance(length_in_m, bool) and math.isfinite(length_in_m) and length_in_m > 0,
             "invalid display length scale")
    return unit, float(length_in_m)


def capture_steady(result, identity, limits, rlimits, spec):
    """Read each public array once and encode the steady region payload (14 arrays)."""
    plan_ = spec.plan
    _require(isinstance(result, ThermalRunResult), "expected public ThermalRunResult")
    summary = common.json_value(result.summary())
    _require(isinstance(summary, dict), "thermal summary must be an object")
    common.encode_json(summary, limits.metadata_bytes)
    pair = (result.result_format, result.field_layout)
    _require(pair == STEADY_PAIR and summary.get("physics_type") == common.KIND,
             "unsupported public thermal region result/layout pair")
    _require(pair == (summary.get("result_format"), summary.get("field_layout")),
             "public and summary result/layout pair disagree")
    doc = result.doc
    _require(doc.canonical_json() == spec.run_doc.canonical_json(),
             "public result document does not match accepted snapshot")
    keys = common.BASE_FIELDS+common.BOUNDARY_FIELDS
    arrays = {}
    for key in keys:
        value = getattr(result, common.PROPERTIES[key])  # one property read
        _require(isinstance(value, np.ndarray), key+": expected a numeric ndarray")
        _require(value.dtype.kind in "iuf", key+": expected real nonboolean dtype")
        if key == "node_coordinates":
            _require(value.ndim == 2 and value.shape[1] == 2 and 3 <= len(value) <= plan_.n_cap,
                     "invalid or oversized node_coordinates")
            node_count = len(value)
        elif key == "triangles":
            _require(value.dtype.kind in "iu" and value.ndim == 2 and value.shape[1] == 3
                     and 1 <= len(value) <= plan_.m_cap, "invalid or oversized triangles")
            cell_count = len(value)
        elif key == "heat_flux":
            _require(value.shape == (cell_count, 2), "invalid heat_flux shape before copy")
        elif key == "prescribed_node_ids":
            _require(value.dtype.kind in "iu" and value.ndim == 1 and len(value) <= node_count,
                     "invalid prescribed node IDs before copy")
            fixed_count = len(value)
        elif key == "prescribed_temperature":
            _require(value.shape == (fixed_count,), "invalid prescribed temperature shape before copy")
        else:
            _require(value.shape == (node_count,), key+": invalid nodal shape before copy")
        _require(np.isfinite(value).all(), key+": nonfinite array before copy")
        arrays[key] = value.copy(order="C")
        _require(np.isfinite(arrays[key]).all(), key+": nonfinite captured array")
    ids = result.triangle_regions          # a live mesh reference: check before copying
    _require(isinstance(ids, np.ndarray) and ids.dtype.kind in "iu" and ids.shape == (cell_count,),
             "invalid triangle_regions before copy")
    arrays["triangle_regions"] = np.array(ids, dtype=np.int64, copy=True, order="C")
    names = result.region_names
    nodes, triangles, fixed = arrays["node_coordinates"], arrays["triangles"], arrays["prescribed_node_ids"]
    n, m = len(nodes), len(triangles)
    _require(not np.any(triangles < 0) and not np.any(triangles >= n), "triangle index outside nodes")
    _require(not np.any(fixed < 0) and not np.any(fixed >= n), "prescribed node index outside nodes")
    _require(not np.any(np.diff(fixed.astype(np.int64)) <= 0), "prescribed node IDs must be sorted unique")
    shapes = {"node_coordinates": (n, 2), "triangles": (m, 3), "heat_flux": (m, 2),
              "prescribed_node_ids": (len(fixed),), "prescribed_temperature": (len(fixed),),
              "triangle_regions": (m,)}
    for key in keys:
        shapes.setdefault(key, (n,))
    _require(not np.any(arrays["prescribed_temperature"] <= 0), "prescribed temperature must be above 0 K")
    with np.errstate(over="ignore", invalid="ignore"):
        v = nodes[triangles][:, 1:]-nodes[triangles][:, :1]
        det = v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0]
    _require(np.isfinite(det).all() and np.all(det > 0), "triangles must be finite nondegenerate CCW")
    fields = keys+("triangle_regions",)
    structural = common.STRUCTURAL+("triangle_regions",)
    for meta, expected in (("field_units", [k for k in fields if k not in structural]),
                           ("field_locations", fields), ("field_shapes", fields)):
        _require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(expected),
                 "invalid "+meta+" field set")
    for key in fields:
        if key not in structural:
            _require(summary["field_units"][key] == common._unit_03(key), key+": wrong unit")
        location = "triangles" if key == "triangle_regions" else common._location_03(key)
        _require(summary["field_locations"][key] == location, key+": wrong location")
        shape = summary["field_shapes"][key]
        _require(isinstance(shape, list) and all(type(x) is int for x in shape)
                 and shape == list(shapes[key]), key+": wrong metadata shape")
    _mesh_summary(summary, n, m, doc)
    unit, length_in_m = _length(summary, doc)
    check_regions(summary, names, arrays["triangle_regions"], nodes, triangles, doc, rlimits, common.KIND)
    payload = {
        "payload_format": STEADY_PAYLOAD, **identity,
        "result_format": pair[0], "field_layout": pair[1],
        "length_unit": unit, "display_length_in_m": length_in_m,
        "summary": summary, "arrays": {key: arrays[key].tolist() for key in fields},
    }
    return common.encode_json(payload, limits.payload_bytes)


def capture_transient(result, identity, limits, rlimits, spec):
    """Read each public array once; encode the transient region manifest and keep the raw
    histories (region ids included) for frames and history pages."""
    plan_ = spec.plan
    document = spec.run_doc
    require = transient.require
    require(isinstance(result, TransientThermalRunResult), "public transient result required")
    original = document.canonical_json()
    summary = common.json_value(result.summary())
    common.encode_json(summary, limits.metadata_bytes)
    pair = (result.result_format, result.field_layout)
    require(isinstance(summary, dict) and summary.get("physics_type") == transient.KIND
            and pair == TRANSIENT_PAIR
            and (summary.get("result_format"), summary.get("field_layout")) == TRANSIENT_PAIR,
            "unsupported transient region summary/result pair")
    require(result.doc.canonical_json() == original, "public result document does not match accepted snapshot")
    nt = len(document.si["study"]["time"])
    spec_fields = dict(transient.SPEC, triangle_regions=(None, "triangles", "static"))
    order = transient.STATIC+tuple(k for k in transient.SPEC if k not in transient.STATIC)
    captured, total = {}, 0
    n = m = fixed_count = None
    for key in order+("triangle_regions",):
        value = result.region_ids if key == "triangle_regions" else getattr(result, key)
        require(isinstance(value, np.ndarray) and value.dtype.kind in "iuf",
                "transient "+key+" requires real nonboolean ndarray")
        if key == "node_coordinates":
            require(value.ndim == 2 and value.shape[1] == 2 and 3 <= len(value) <= plan_.n_cap,
                    "invalid or oversized transient node_coordinates")
            n = len(value)
        elif key == "triangles":
            require(value.dtype.kind in "iu" and value.ndim == 2 and value.shape[1] == 3
                    and 1 <= len(value) <= plan_.m_cap, "invalid or oversized transient triangles")
            m = len(value)
        elif key == "prescribed_node_ids":
            require(value.ndim == 1 and len(value) <= n and value.dtype.kind in "iu",
                    "invalid transient prescribed node IDs")
            fixed_count = len(value)
        elif key == "triangle_regions":
            require(value.dtype.kind in "iu", "invalid transient triangle_regions")
        shapes = {"node_coordinates": (n, 2), "triangles": (m, 3), "time": (nt,),
                  "prescribed_node_ids": (fixed_count,), "temperature": (nt, n),
                  "heat_flux": (nt, m, 2), "generated_heat_rate_per_depth": (nt, n),
                  "reaction_heat_rate_per_depth": (nt-1, n), "residual_heat_rate_per_depth": (nt-1, n),
                  "heat_storage_rate_per_depth": (nt-1, n), "stored_heat_per_depth": (nt,),
                  "thermal_energy_functional_per_depth": (nt,),
                  "prescribed_temperature": (nt, fixed_count), "triangle_regions": (m,)}
        require(value.shape == shapes[key], "transient "+key+" shape mismatch")
        require(np.isfinite(value).all(), "nonfinite transient "+key)
        require(value.dtype.itemsize <= 8, "unsupported transient numeric width")
        total += value.nbytes
        require(total <= transient.RAW_BYTES, "transient raw bytes exceed cap", 413, "history_limit_exceeded")
        owned = np.array(value, copy=True, order="C")
        require(np.isfinite(owned).all(), "nonfinite captured transient "+key)
        owned.flags.writeable = False
        captured[key] = owned
    x, tri, fixed, ids = (captured[k] for k in ("node_coordinates", "triangles", "prescribed_node_ids",
                                                "triangle_regions"))
    require(tri.dtype.kind in "iu" and np.all(tri >= 0) and np.all(tri < n), "transient triangle indices invalid")
    require(np.all(fixed >= 0) and np.all(fixed < n) and np.all(fixed[1:] > fixed[:-1]),
            "transient prescribed node IDs invalid")
    a, b, c = x[tri[:, 0]], x[tri[:, 1]], x[tri[:, 2]]
    with np.errstate(over="ignore", invalid="ignore"):
        area = (b[:, 0]-a[:, 0])*(c[:, 1]-a[:, 1])-(b[:, 1]-a[:, 1])*(c[:, 0]-a[:, 0])
    require(np.isfinite(area).all() and np.all(area > 0), "transient mesh must be CCW")
    require(np.array_equal(captured["time"], np.asarray(document.si["study"]["time"])),
            "transient requested time axis mismatch")
    expected = {"field_units": [k for k, v in spec_fields.items() if v[0] is not None],
                "field_locations": list(spec_fields), "field_shapes": list(spec_fields),
                "field_time_axes": [k for k, v in spec_fields.items() if v[2] != "static"]}
    for meta, keys in expected.items():
        require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(keys),
                "transient metadata field set mismatch")
    _mesh_summary(summary, n, m, document)
    study_meta = summary.get("study")
    declared = study_meta.get("time") if isinstance(study_meta, dict) else None
    declared_times = declared.get("values") if isinstance(declared, dict) else None
    require(isinstance(study_meta, dict) and study_meta.get("type") == "transient"
            and declared.get("unit") == "s" and isinstance(declared_times, list)
            and all(type(v) in (int, float) and math.isfinite(v) for v in declared_times)
            and np.array_equal(np.asarray(declared_times), captured["time"]),
            "transient summary study disagrees with captured times")
    require(type(summary.get("prescribed_nodes")) is int and summary["prescribed_nodes"] == fixed_count,
            "transient summary prescribed node count disagrees")
    descriptors = {}
    for key, (unit, location, axis) in spec_fields.items():
        declared_shape = summary["field_shapes"][key]
        require(isinstance(declared_shape, list) and all(type(v) is int for v in declared_shape)
                and summary["field_units"].get(key) == unit and summary["field_locations"][key] == location
                and summary["field_time_axes"].get(key, "static") == axis
                and declared_shape == list(captured[key].shape),
                "transient metadata mismatch: "+key)
        descriptors[key] = {"shape": list(captured[key].shape), "unit": unit,
                            "location": location, "axis": axis,
                            "available_views": ["frame", "history"] if key in transient.DYNAMIC else [],
                            "initial_available": axis != "time[1:]",
                            "ui_supported": key in transient.UI_FIELDS}
    check_regions(summary, result.region_names, ids, x, tri, document, rlimits, transient.KIND)
    try:
        unit, scale = _length(summary, document)
    except common.ThermalAPIError:
        require(False, "transient document/summary length_unit mismatch")
    base = {**identity, "result_format": TRANSIENT_PAIR[0], "field_layout": TRANSIENT_PAIR[1],
            "length_unit": unit, "display_length_in_m": scale}
    job, rid = identity["job"], identity["result_id"]
    payload = {**base, "payload_format": TRANSIENT_MANIFEST, "summary": summary, "fields": descriptors,
               "time": captured["time"].tolist(), "default_frame_index": nt-1,
               "arrays": {k: captured[k].tolist()
                          for k in ("node_coordinates", "triangles", "prescribed_node_ids", "triangle_regions")},
               "frame_url": "/api/jobs/"+job+"/frame?result_id="+rid
                            +"&field={field}&time_index={time_index}&frame_seq={frame_seq}",
               "history_url": "/api/jobs/"+job+"/history?result_id="+rid
                              +"&field={field}&start={start}&stop={stop}&frame_seq={frame_seq}"}
    encoded = common.encode_json(payload, transient.ENCODED_BYTES)
    return encoded, MappingProxyType(captured), scale
