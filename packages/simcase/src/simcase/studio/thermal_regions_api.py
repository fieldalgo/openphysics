# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady and transient heat region documents in Studio; an ordinary public simcase consumer.

A region document (a heat document whose ``geometry`` has ``shapes`` or ``background``)
takes this path on the same routes as rectangle documents, which keep their own code
unchanged. Each stage bounds the cost of the next:

1. on the event loop, O(JSON size): the physics entry, a stray ``mesh.subdivisions`` and,
   for transient documents, the requested times (the rectangle checks, copied);
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
                     TransientThermalRunResult, check_mesh_limits, region_complexity)

from . import thermal_api as common
from . import transient_thermal_api as transient

STEADY_PAIR = ("thermal.steady2d-regions-result-v1", "thermal2d-p1-node-cell-regions-v1")
TRANSIENT_PAIR = ("thermal.transient2d-regions-result-v1", "thermal2d-transient-p1-node-cell-regions-v1")
STEADY_PAYLOAD = "studio-thermal-steady-regions-v1"
TRANSIENT_MANIFEST = "studio-thermal-transient-regions-v1"   # frames and histories keep their IDs
REGION_KEYS = ("material", "triangles", "area_m2")
MESH_KEYS = {"nodes", "triangles", "size", "min_angle_deg", "size_unit"}
SUBDIVISIONS = ("region documents (geometry.shapes or geometry.background) set mesh.size; "
                "mesh.subdivisions belongs to rectangle documents")


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

    The same rule as simcase's own choice of the region path: a physics entry of that type
    and a ``geometry`` object with ``shapes`` or ``background``. Thermal defaults add only
    ``geometry.domain``, so the raw and the merged document agree."""
    if not isinstance(raw, dict) or not isinstance(raw.get("physics"), dict):
        return False
    typed = any(isinstance(p, dict) and p.get("type") == kind for p in raw["physics"].values())
    geometry = raw.get("geometry")
    return typed and isinstance(geometry, dict) and ("shapes" in geometry or "background" in geometry)


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
    mesh = raw.get("mesh")
    if isinstance(mesh, dict) and "subdivisions" in mesh:
        raise common.ThermalAPIError("invalid_document", SUBDIVISIONS, path="mesh.subdivisions")
    if kind == common.KIND:
        return None
    # The rectangle time checks (transient_thermal_api.preflight), same codes and messages.
    study = raw.get("study")
    times = study.get("time_s") if isinstance(study, dict) else None
    transient.require(isinstance(times, list) and len(times) >= 2,
                      "study.time_s must contain at least two requested times", code="invalid_document")
    transient.require(len(times) <= transient.MAX_TIMES, "too many requested times", 413, "history_limit_exceeded")
    try:
        valid = (all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in times)
                 and all(b > a and math.isfinite(b-a) for a, b in zip(times, times[1:])))
    except OverflowError:
        valid = False
    transient.require(valid, "requested times must be finite strictly increasing seconds", code="invalid_document")
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


def _geometry_limit(message):
    return common.ThermalAPIError("geometry_limit_exceeded", message, 413, path="geometry.shapes")


def _check_complexity(raw, rlimits):
    counts = region_complexity(raw, max_shapes=rlimits.max_shapes, max_circles=rlimits.max_circles,
                               max_polygon_points=rlimits.max_polygon_points)
    for what, count, name in (("shapes", counts.shapes, "max_shapes"),
                              ("circles", counts.circles, "max_circles"),
                              ("polygon points", counts.polygon_points, "max_polygon_points")):
        limit = getattr(rlimits, name)
        if count > limit:
            raise _geometry_limit(f"geometry.shapes has {count} {what}, more than Studio's region limit "
                                  f"{name}={limit}")
    if counts.boundary_crossings > rlimits.max_boundary_crossings:
        raise _geometry_limit(f"the shapes' boundaries cross {counts.boundary_crossings} times (segment pairs "
                              f"of different shapes), more than Studio's region limit max_boundary_crossings="
                              f"{rlimits.max_boundary_crossings}")


def _summary_floor(doc, limits):
    """Refuse a document whose summary cannot fit: the summary copies these four values."""
    _, physics = doc.sole_physics()
    floor = {"name": doc["name"], "units": doc["units"], "materials": doc["materials"],
             "heat_source_w_m3": physics.get("heat_source_w_m3")}
    try:
        common.encode_json(floor, limits.metadata_bytes)
    except common.ThermalAPIError as exc:
        raise common.ThermalAPIError(
            "payload_limit_exceeded", "the result summary copies the document's name, units, materials and heat "
            f"sources, which encode to more than metadata_bytes={limits.metadata_bytes}", 413,
            path="materials") from exc


def _accept(raw, kind, limits, rlimits, nt, tags, for_run):
    """Worker-thread validation; every failure becomes a tagged ThermalAPIError."""
    try:
        _check_complexity(raw, rlimits)
        try:
            doc = Document.from_dict(raw)
        except (DocumentError, ValueError, TypeError, OverflowError) as exc:
            raise common.ThermalAPIError("invalid_document", str(exc), 400 if for_run else 200) from exc
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

    async def read(self, raw, tags, *, for_run):
        nt = raw_preflight(raw, self.kind, self.limits)
        if for_run and not runtime_available(self.kind, self.limits):
            raise common.ThermalAPIError("unsupported_public_api", "matching public result IDs are required")
        return await _wait_for_thread(_accept, raw, self.kind, self.limits, self.rlimits, nt, tags, for_run)


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
    geometry = doc["geometry"]
    assigned = {s["name"]: s["material"] for s in geometry["shapes"]}
    assigned["background"] = geometry["background"]["material"]
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
        area = entry["area_m2"]
        _require(type(area) is float and math.isfinite(area) and area >= 0
                 and area == float(areas[ids == i].sum()), name+": region area disagrees")
        total += area
    domain = geometry["domain"]
    scale = doc.scale.to_si(1., {"length": 1})
    expected = (domain["xmax"]-domain["xmin"])*(domain["ymax"]-domain["ymin"])*scale*scale
    _require(math.isfinite(expected) and expected > 0 and abs(total-expected) <= 1e-9*expected,
             "region areas do not add up to the domain")
    _, physics = doc.sole_physics()
    _require(_exact_json(summary.get("materials")) == _exact_json(doc["materials"]),
             "summary materials disagree with the document")
    _require(_exact_json(summary.get("heat_source_w_m3")) == _exact_json(physics["heat_source_w_m3"]),
             "summary heat sources disagree with the document")


def _mesh_summary(summary, n, m, doc):
    mesh = summary.get("mesh")
    _require(isinstance(mesh, dict) and set(mesh) == MESH_KEYS
             and type(mesh["nodes"]) is int and mesh["nodes"] == n
             and type(mesh["triangles"]) is int and mesh["triangles"] == m
             and _exact_json(mesh["size"]) == _exact_json(doc["mesh"]["size"])
             and _exact_json(mesh["min_angle_deg"]) == _exact_json(doc["mesh"]["min_angle"])
             and mesh["size_unit"] == doc.length_unit, "summary mesh disagrees with the result")


def capture_steady(result, identity, limits, rlimits, spec):
    """Read each public array once and encode the steady region payload (14 arrays)."""
    plan_ = spec.plan
    _require(isinstance(result, ThermalRunResult), "expected public ThermalRunResult")
    summary = copy.deepcopy(result.summary())
    _require(isinstance(summary, dict), "thermal summary must be an object")
    common.encode_json(summary, limits.metadata_bytes)
    pair = (result.result_format, result.field_layout)
    _require(pair == STEADY_PAIR and summary.get("physics_type") == common.KIND,
             "unsupported public thermal region result/layout pair")
    _require(pair == (summary.get("result_format"), summary.get("field_layout")),
             "public and summary result/layout pair disagree")
    doc = result.doc
    _require(_exact_json(doc.data) == _exact_json(spec.run_doc.data),
             "public result document does not match accepted snapshot")
    keys = common.BASE_FIELDS+common.BOUNDARY_FIELDS
    arrays = {}
    for key in keys:
        value = getattr(result, common.PROPERTIES[key])  # one property read
        _require(isinstance(value, np.ndarray), key+": expected a numeric ndarray")
        _require(value.dtype.kind in "iuf", key+": expected real nonboolean dtype")
        if key == "nodes_m":
            _require(value.ndim == 2 and value.shape[1] == 2 and 3 <= len(value) <= plan_.n_cap,
                     "invalid or oversized nodes_m")
            node_count = len(value)
        elif key == "triangles":
            _require(value.dtype.kind in "iu" and value.ndim == 2 and value.shape[1] == 3
                     and 1 <= len(value) <= plan_.m_cap, "invalid or oversized triangles")
            cell_count = len(value)
        elif key == "heat_flux_w_m2":
            _require(value.shape == (cell_count, 2), "invalid heat_flux_w_m2 shape before copy")
        elif key == "dirichlet_node_ids":
            _require(value.dtype.kind in "iu" and value.ndim == 1 and len(value) <= node_count,
                     "invalid Dirichlet IDs before copy")
            fixed_count = len(value)
        elif key == "dirichlet_temperature_k":
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
    nodes, triangles, fixed = arrays["nodes_m"], arrays["triangles"], arrays["dirichlet_node_ids"]
    n, m = len(nodes), len(triangles)
    _require(not np.any(triangles < 0) and not np.any(triangles >= n), "triangle index outside nodes")
    _require(not np.any(fixed < 0) and not np.any(fixed >= n), "Dirichlet index outside nodes")
    _require(not np.any(np.diff(fixed.astype(np.int64)) <= 0), "Dirichlet IDs must be sorted unique")
    shapes = {"nodes_m": (n, 2), "triangles": (m, 3), "heat_flux_w_m2": (m, 2),
              "dirichlet_node_ids": (len(fixed),), "dirichlet_temperature_k": (len(fixed),),
              "triangle_regions": (m,)}
    for key in keys:
        shapes.setdefault(key, (n,))
    _require(not np.any(arrays["dirichlet_temperature_k"] < 0), "negative prescribed Kelvin")
    with np.errstate(over="ignore", invalid="ignore"):
        v = nodes[triangles][:, 1:]-nodes[triangles][:, :1]
        det = v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0]
    _require(np.isfinite(det).all() and np.all(det > 0), "triangles must be finite nondegenerate CCW")
    fields = keys+("triangle_regions",)
    for meta in ("field_units", "field_locations", "field_shapes"):
        _require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(fields),
                 "invalid "+meta+" field set")
    for key in fields:
        unit, location = ("1", "triangles") if key == "triangle_regions" else (common._units(key),
                                                                               common._location(key))
        _require(summary["field_units"][key] == unit, key+": wrong unit")
        _require(summary["field_locations"][key] == location, key+": wrong location")
        shape = summary["field_shapes"][key]
        _require(isinstance(shape, list) and all(type(x) is int for x in shape)
                 and shape == list(shapes[key]), key+": wrong metadata shape")
    _mesh_summary(summary, n, m, doc)
    _require(summary.get("units") == doc["units"] and summary.get("mesh_length_unit") == "m",
             "document/summary unit mismatch")
    length_in_m = doc.scale.to_si(1., {"length": 1})
    _require(not isinstance(length_in_m, bool) and math.isfinite(length_in_m) and length_in_m > 0,
             "invalid display length scale")
    check_regions(summary, names, arrays["triangle_regions"], nodes, triangles, doc, rlimits, common.KIND)
    payload = {
        "payload_format": STEADY_PAYLOAD, **identity,
        "result_format": pair[0], "field_layout": pair[1],
        "display_length_in_m": float(length_in_m),
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
    original = _exact_json(document.data)
    summary = copy.deepcopy(result.summary())
    common.encode_json(summary, limits.metadata_bytes)
    pair = (result.result_format, result.field_layout)
    require(isinstance(summary, dict) and summary.get("physics_type") == transient.KIND
            and pair == TRANSIENT_PAIR
            and (summary.get("result_format"), summary.get("field_layout")) == TRANSIENT_PAIR,
            "unsupported transient region summary/result pair")
    require(_exact_json(result.doc.data) == original, "public result document does not match accepted snapshot")
    require(summary.get("units") == document["units"] and summary.get("mesh_length_unit") == "m",
            "transient document/SI units mismatch")
    nt = len(document["study"]["time_s"])
    spec_fields = dict(transient.SPEC, triangle_regions=("1", "triangles", "static"))
    order = ("nodes_m", "triangles", "time_s", "dirichlet_node_ids")+tuple(
        k for k in transient.SPEC if k not in {"nodes_m", "triangles", "time_s", "dirichlet_node_ids"})
    captured, total = {}, 0
    n = m = fixed_count = None
    for key in order+("triangle_regions",):
        value = result.region_ids if key == "triangle_regions" else getattr(result, key)
        require(isinstance(value, np.ndarray) and value.dtype.kind in "iuf",
                "transient "+key+" requires real nonboolean ndarray")
        if key == "nodes_m":
            require(value.ndim == 2 and value.shape[1] == 2 and 3 <= len(value) <= plan_.n_cap,
                    "invalid or oversized transient nodes_m")
            n = len(value)
        elif key == "triangles":
            require(value.dtype.kind in "iu" and value.ndim == 2 and value.shape[1] == 3
                    and 1 <= len(value) <= plan_.m_cap, "invalid or oversized transient triangles")
            m = len(value)
        elif key == "dirichlet_node_ids":
            require(value.ndim == 1 and len(value) <= n and value.dtype.kind in "iu",
                    "invalid transient Dirichlet IDs")
            fixed_count = len(value)
        elif key == "triangle_regions":
            require(value.dtype.kind in "iu", "invalid transient triangle_regions")
        shapes = {"nodes_m": (n, 2), "triangles": (m, 3), "time_s": (nt,),
                  "dirichlet_node_ids": (fixed_count,), "temperature_k": (nt, n),
                  "heat_flux_w_m2": (nt, m, 2), "source_load_w_per_m": (nt, n),
                  "reaction_w_per_m": (nt-1, n), "residual_w_per_m": (nt-1, n),
                  "storage_rate_w_per_m": (nt-1, n), "heat_content_j_per_m": (nt,),
                  "quadratic_functional_jk_per_m": (nt,),
                  "dirichlet_temperatures_k": (nt, fixed_count), "triangle_regions": (m,)}
        require(value.shape == shapes[key], "transient "+key+" shape mismatch")
        require(np.isfinite(value).all(), "nonfinite transient "+key)
        require(value.dtype.itemsize <= 8, "unsupported transient numeric width")
        total += value.nbytes
        require(total <= transient.RAW_BYTES, "transient raw bytes exceed cap", 413, "history_limit_exceeded")
        owned = np.array(value, copy=True, order="C")
        require(np.isfinite(owned).all(), "nonfinite captured transient "+key)
        owned.flags.writeable = False
        captured[key] = owned
    x, tri, fixed, ids = (captured[k] for k in ("nodes_m", "triangles", "dirichlet_node_ids", "triangle_regions"))
    require(tri.dtype.kind in "iu" and np.all(tri >= 0) and np.all(tri < n), "transient triangle indices invalid")
    require(np.all(fixed >= 0) and np.all(fixed < n) and np.all(fixed[1:] > fixed[:-1]),
            "transient Dirichlet IDs invalid")
    a, b, c = x[tri[:, 0]], x[tri[:, 1]], x[tri[:, 2]]
    with np.errstate(over="ignore", invalid="ignore"):
        area = (b[:, 0]-a[:, 0])*(c[:, 1]-a[:, 1])-(b[:, 1]-a[:, 1])*(c[:, 0]-a[:, 0])
    require(np.isfinite(area).all() and np.all(area > 0), "transient mesh must be CCW")
    require(np.array_equal(captured["time_s"], np.asarray(document["study"]["time_s"])),
            "transient requested time axis mismatch")
    for meta in ("field_units", "field_locations", "field_time_axes", "field_shapes"):
        require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(spec_fields),
                "transient metadata field set mismatch")
    _mesh_summary(summary, n, m, document)
    study_meta = summary.get("study")
    declared_times = study_meta.get("time_s") if isinstance(study_meta, dict) else None
    require(isinstance(study_meta, dict) and study_meta.get("type") == "transient"
            and isinstance(declared_times, list)
            and all(type(v) in (int, float) and math.isfinite(v) for v in declared_times)
            and np.array_equal(np.asarray(declared_times), captured["time_s"]),
            "transient summary study disagrees with captured times")
    rate_times = summary.get("rate_time_s")
    require(isinstance(rate_times, list)
            and all(type(v) in (int, float) and math.isfinite(v) for v in rate_times)
            and np.array_equal(np.asarray(rate_times), captured["time_s"][1:]),
            "transient summary rate times disagree")
    require(type(summary.get("dirichlet_nodes")) is int and summary["dirichlet_nodes"] == fixed_count,
            "transient summary Dirichlet count disagrees")
    descriptors = {}
    for key, (unit, location, axis) in spec_fields.items():
        declared_shape = summary["field_shapes"][key]
        require(isinstance(declared_shape, list) and all(type(v) is int for v in declared_shape)
                and summary["field_units"][key] == unit and summary["field_locations"][key] == location
                and summary["field_time_axes"][key] == axis
                and declared_shape == list(captured[key].shape),
                "transient metadata mismatch: "+key)
        descriptors[key] = {"shape": list(captured[key].shape), "unit": unit,
                            "location": location, "axis": axis,
                            "available_views": ["frame", "history"] if key in transient.DYNAMIC else [],
                            "initial_available": axis != "time_s[1:]",
                            "ui_supported": key in transient.UI_FIELDS}
    check_regions(summary, result.region_names, ids, x, tri, document, rlimits, transient.KIND)
    scale = document.scale.to_si(1., {"length": 1})
    require(type(scale) in (int, float) and math.isfinite(scale) and scale > 0,
            "transient display scale invalid")
    base = {**identity, "result_format": TRANSIENT_PAIR[0], "field_layout": TRANSIENT_PAIR[1],
            "display_length_in_m": scale}
    job, rid = identity["job"], identity["result_id"]
    payload = {**base, "payload_format": TRANSIENT_MANIFEST, "summary": summary, "fields": descriptors,
               "time_s": captured["time_s"].tolist(), "default_frame_index": nt-1,
               "arrays": {k: captured[k].tolist()
                          for k in ("nodes_m", "triangles", "dirichlet_node_ids", "triangle_regions")},
               "frame_url": "/api/jobs/"+job+"/frame?result_id="+rid
                            +"&field={field}&time_index={time_index}&frame_seq={frame_seq}",
               "history_url": "/api/jobs/"+job+"/history?result_id="+rid
                              +"&field={field}&start={start}&stop={stop}&frame_seq={frame_seq}"}
    encoded = common.encode_json(payload, transient.ENCODED_BYTES)
    return encoded, MappingProxyType(captured), scale
