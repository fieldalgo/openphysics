# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady Joule heating on named material regions in Studio; an ordinary public simcase consumer.

``/api/joule/validate`` and ``/api/joule/run`` take one ``joule.steady2d`` or
``joule.temperature2d`` document whose geometry declares regions (``simcase.has_region_geometry``).
A rectangle electric document is refused by name (run it with simcase). The routes reuse the
region heat path (:mod:`.thermal_regions_api`) stage by stage:

1. on the event loop: the request envelope (``thermal_api.read_request``), the physics entry, the
   format and a stray ``mesh.subdivision_count``;
2. in a worker thread: the region complexity limits, ``Document.from_dict``, the loop-vertex
   limit, the summary floor and the document lists, and for a run the run copy;
3. in the job: ``run`` with the node, triangle and loop-vertex caps, so an over-fine mesh is
   refused after meshing and before the solve.

Jobs share the thermal job store: one active job for heat and Joule together, the same byte
budget, retention and pins. A finished job's payload holds every array of the public result
(SI, under their registry names), the summary, and the display length; it is checked before it is
published (shapes and units against the summary, connectivity, region ids and materials).

A ``joule.temperature2d`` document with ``iteration.method: "newton"`` is refused by name
(``unsupported_iteration_method``): the iteration cap and the error text count Picard steps.

Errors follow Studio's policy: document, geometry and limit refusals keep their text; a Picard
iteration that does not converge is reported with the solver's reason and iteration count; any
other failure replies with the fixed message and logs its traceback.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import re

import numpy as np
from simcase import (Document, DocumentError, ElectricJouleRunResult, JouleConvergenceError, MeshLimitError,
                     check_mesh_limits, has_region_geometry)

from . import thermal_api as common
from . import thermal_regions_api as regions
from .bodies import reply_text, unexpected

STEADY = "joule.steady2d"
TEMPERATURE = "joule.temperature2d"
KINDS = (STEADY, TEMPERATURE)
#: the region result and field layout of each kind (simcase.joule_regions, simcase.joule_temperature_regions)
PAIRS = {STEADY: ("joule.steady2d-regions-result-v2", "electric-joule2d-p1-node-cell-regions-v2"),
         TEMPERATURE: ("joule.temperature2d-regions-result-v2", "electric-joule2d-temperature-p1-node-cell-regions-v2")}
PAYLOAD = "studio-joule-regions-v1"
#: arrays without a unit: connectivity, region ids and node indices
STRUCTURAL = ("triangles", "triangle_regions", "electric_prescribed_node_ids", "thermal_prescribed_node_ids")
#: the arrays the workspace reads; a result without one of them is refused
REQUIRED = ("node_coordinates", "triangles", "triangle_regions", "electric_potential", "current_density",
            "joule_power_density", "temperature", "heat_flux", "electric_prescribed_node_ids",
            "thermal_prescribed_node_ids")
#: Studio's cap on a joule.temperature2d document's ``iteration.iteration_limit``: a job's cost is
#: its mesh's cost times its Picard iterations, and its records (about 1 kB each) go to the result
MAX_ITERATIONS = 500
#: the one galerkin refusal inside a Picard iteration that is written for users: a material
#: model's valid temperature range left by an iterate
_RANGE_LEFT = re.compile(r"material '[^']*': temperature \[[^\]]*\] K outside \[[^\]]*\] K")
FORMAT_03 = ('Joule Studio reads format 0.3 region documents ("openphysics": "0.3", values with their units, '
             'element_size quantities)')
RECTANGLE = ("Studio runs Joule heating on named material regions only (geometry with shapes or background, or a "
             "version 1 block with features or a background material); run rectangle electric documents with simcase")
ENTRY = "the Joule route accepts one joule.steady2d or joule.temperature2d entry"


def _kind(raw):
    """The physics type of a raw document's one entry, or None."""
    physics = raw.get("physics") if isinstance(raw, dict) else None
    if not isinstance(physics, dict) or len(physics) != 1 or not isinstance(next(iter(physics.values())), dict):
        return None
    return next(iter(physics.values())).get("type")


def applies(raw):
    """A raw Joule document that declares region geometry (simcase's own choice of the region path)."""
    return any(has_region_geometry(raw, kind) for kind in KINDS)


def rectangle_preflight(raw, limits):
    """A document that does not take the region path: refused, by name when it is a Joule one."""
    if not isinstance(raw, dict):
        raise common.ThermalAPIError("invalid_envelope", "doc must be an object", path="doc")
    if _kind(raw) not in KINDS:
        raise common.ThermalAPIError("unsupported_physics", ENTRY, path="physics")
    raise common.ThermalAPIError("unsupported_geometry", RECTANGLE, path="geometry")


def raw_preflight(raw):
    """Event-loop checks of a raw region document; its physics type."""
    kind = _kind(raw)
    if kind not in KINDS:
        raise common.ThermalAPIError("unsupported_physics", ENTRY, path="physics")
    if raw.get("openphysics") != "0.3":
        raise common.ThermalAPIError("invalid_document", FORMAT_03, path="openphysics")
    mesh = raw.get("mesh")
    if isinstance(mesh, dict) and "subdivision_count" in mesh:
        raise common.ThermalAPIError("invalid_document", regions.SUBDIVISIONS, path="mesh.subdivision_count")
    return kind


def runtime_available():
    return all(hasattr(ElectricJouleRunResult, key) for key in ("result_format", "field_layout", "fields"))


def capability(kind, limits, rlimits):
    return {"supported": True, "run_enabled": runtime_available(), "validate": "/api/joule/validate",
            "run": "/api/joule/run", "input": "json", "geometry": "regions",
            "result_formats": [PAIRS[kind][0]], "field_layouts": [PAIRS[kind][1]], "payload_formats": [PAYLOAD],
            "resource_policy": "candidate-unmeasured",
            "limits": {**asdict(rlimits), **({"max_iterations": MAX_ITERATIONS} if kind == TEMPERATURE else {})}}


def _accept(raw, kind, limits, rlimits, tags, for_run, exact=None):
    """Worker-thread validation; every failure becomes a tagged ThermalAPIError."""
    try:
        regions._check_complexity(raw, rlimits)
        try:
            doc = Document.from_dict(raw if exact is None else exact)
        except (DocumentError, ValueError, TypeError, OverflowError) as exc:
            raise common.ThermalAPIError("invalid_document", reply_text(exc, "Joule region document"),
                                         400 if for_run else 200) from exc
        if kind == TEMPERATURE:
            name, p = next(iter(doc.si["physics"].items()))
            if p["iteration"].get("method", "picard") != "picard":
                # Studio's cost cap and its not_converged text count Picard steps; a Newton step
                # evaluates up to 31 candidates (galerkin halves a step up to 30 times)
                raise common.ThermalAPIError(
                    "unsupported_iteration_method", f'physics.{name}.iteration.method "{p["iteration"]["method"]}": '
                    "Studio runs the Picard iteration only; run a Newton document with simcase",
                    path=f"physics.{name}.iteration.method")
            limit = p["iteration"]["iteration_limit"]
            if limit > MAX_ITERATIONS:
                raise common.ThermalAPIError(
                    "iteration_limit_exceeded", f"physics.{name}.iteration.iteration_limit is {limit}, more than "
                    f"Studio's limit max_iterations={MAX_ITERATIONS}", 413, path=f"physics.{name}.iteration.iteration_limit")
        count = check_mesh_limits(doc, max_input_vertices=rlimits.max_input_vertices)
        regions._summary_floor(doc, limits)
        common.check_document_lists(doc, limits.payload_bytes, "payload_bytes")
        run_doc = None
        if for_run:
            run_doc = doc.copy()        # copy() resets the scale; validate() restores it
            run_doc.validate()
        plan = regions.Plan(limits.max_nodes, limits.max_triangles)
        return regions.RegionInput(doc, run_doc, plan, kind, count, **tags)
    except common.ThermalAPIError:
        raise
    except MeshLimitError as exc:
        raise regions._geometry_limit(str(exc)) from exc
    except Exception as exc:
        raise common.ThermalAPIError("invalid_document", reply_text(exc, "Joule region validation"),
                                     400 if for_run else 200) from exc


class Route:
    """The region path of the Joule routes, given to thermal_api.read_request."""

    def __init__(self, limits, rlimits):
        self.limits, self.rlimits = limits, rlimits

    def applies(self, raw):
        return applies(raw)

    async def read(self, raw, tags, *, for_run, exact=None):
        kind = raw_preflight(raw)
        if for_run and not runtime_available():
            raise common.ThermalAPIError("unsupported_public_api", "matching public result IDs are required")
        return await regions._wait_for_thread(_accept, raw, kind, self.limits, self.rlimits, tags, for_run, exact)


def job_error(exc, plan):
    """The Studio error for a failed Joule region run, or None for an unexpected failure."""
    mapped = regions.job_error(exc, plan)
    if mapped is not None:
        return mapped
    if isinstance(exc, JouleConvergenceError):
        cause = exc.__cause__
        # the solver's own reasons are for users: the iteration count (no cause) and a material
        # range left by an iterate; any other exception the iteration wrapped is unexpected
        reason = str(exc.reason)
        if cause is not None and not (type(cause) is ValueError and _RANGE_LEFT.fullmatch(reason)):
            reason = unexpected(exc, "Joule iteration")
        return common.ThermalAPIError("not_converged", f"the Picard iteration did not converge after "
                                      f"{len(exc.history)} iterations: {reason}", 422)
    return None


def _require(condition, message):
    if not condition:
        raise common.ThermalAPIError("invalid_result", message, 500)


def _exact_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unit(key):
    from physmat.units import quantity
    return quantity(key).unit


def _check_regions(summary, names, ids, doc, rlimits):
    """Region names, ids and materials against the document."""
    _require(isinstance(names, list) and 1 <= len(names) <= rlimits.max_shapes+1
             and all(isinstance(n, str) and n for n in names) and len(set(names)) == len(names),
             "region names must be unique nonempty strings")
    _require(not np.any(ids < 0) and not np.any(ids >= len(names)), "triangle region ids outside the regions")
    assigned = {entry["name"]: entry["material"] for entry in doc.regions()}
    assigned["background"] = doc.background["material"]
    entries = summary.get("regions")
    _require(isinstance(entries, dict) and set(entries) == set(names), "summary regions disagree with the names")
    materials = doc.si["materials"]
    for name in names:
        entry = entries[name]
        _require(isinstance(entry, dict) and name in assigned and entry.get("material") == assigned[name],
                 name+": region material disagrees")
        k = materials[assigned[name]]["thermal_conductivity"]
        _require(_exact_json(entry.get("thermal_conductivity")) == _exact_json(
            {"value": float(k), "unit": _unit("thermal_conductivity")}), name+": region thermal conductivity disagrees")


def capture(result, identity, limits, rlimits, spec):
    """Read the public result once, check it and encode the payload."""
    plan = spec.plan
    _require(isinstance(result, ElectricJouleRunResult), "expected a public ElectricJouleRunResult")
    summary = common.json_value(result.summary())
    _require(isinstance(summary, dict), "Joule summary must be an object")
    # the iteration records grow with the run (at most MAX_ITERATIONS) and count against the
    # payload, like the document lists; metadata_bytes bounds the rest
    common.check_summary({k: v for k, v in summary.items() if k != "iterations"}
                         if isinstance(summary, dict) else summary, limits)
    pair = PAIRS[spec.kind]
    _require((result.result_format, result.field_layout) == pair and summary.get("physics_type") == spec.kind,
             "unsupported public Joule region result/layout pair")
    _require((summary.get("result_format"), summary.get("field_layout")) == pair,
             "public and summary result/layout pair disagree")
    doc = result.doc
    _require(doc.canonical_json() == spec.run_doc.canonical_json(),
             "public result document does not match accepted snapshot")
    arrays = result.fields                       # owned copies, read once
    _require(isinstance(arrays, dict) and all(k in arrays for k in REQUIRED)
             and ((spec.kind == TEMPERATURE) == ("evaluation_temperature" in arrays)), "Joule result fields missing")
    shapes = summary.get("field_shapes")
    _require(isinstance(shapes, dict) and set(shapes) == set(arrays), "invalid field_shapes field set")
    units = summary.get("field_units")
    _require(isinstance(units, dict) and set(units) == set(arrays)-set(STRUCTURAL), "invalid field_units field set")
    for key, value in arrays.items():
        _require(isinstance(value, np.ndarray) and value.dtype.kind in "iuf", key+": expected a real numeric array")
        _require(np.isfinite(value).all(), key+": nonfinite array")
        _require(isinstance(shapes[key], list) and shapes[key] == list(value.shape), key+": wrong metadata shape")
        if key in STRUCTURAL:
            _require(value.dtype.kind in "iu", key+": expected integers")
        else:
            _require(units[key] == _unit(key), key+": wrong unit")
    nodes, triangles, ids = arrays["node_coordinates"], arrays["triangles"], arrays["triangle_regions"]
    _require(nodes.ndim == 2 and nodes.shape[1] == 2 and 3 <= len(nodes) <= plan.n_cap,
             "invalid or oversized node_coordinates")
    _require(triangles.ndim == 2 and triangles.shape[1] == 3 and 1 <= len(triangles) <= plan.m_cap,
             "invalid or oversized triangles")
    n, m = len(nodes), len(triangles)
    _require(not np.any(triangles < 0) and not np.any(triangles >= n), "triangle index outside nodes")
    _require(ids.shape == (m,), "invalid triangle_regions")
    for key, values in (("electric_prescribed_node_ids", "prescribed_electric_potential"),
                        ("thermal_prescribed_node_ids", "prescribed_temperature")):
        fixed = arrays[key]
        _require(fixed.ndim == 1 and not np.any(fixed < 0) and not np.any(fixed >= n)
                 and not np.any(np.diff(fixed.astype(np.int64)) <= 0), key+": node IDs must be sorted unique")
        _require(arrays[values].shape == fixed.shape, values+": shape disagrees with its node IDs")
    rows = {"nodes": n, "triangle_connectivity": m, "triangles": m, "triangle_centroids": m,
            "electric_prescribed_nodes": len(arrays["electric_prescribed_node_ids"]),
            "thermal_prescribed_nodes": len(arrays["thermal_prescribed_node_ids"])}
    locations = summary.get("field_locations")
    _require(isinstance(locations, dict) and set(locations) == set(arrays), "invalid field_locations field set")
    for key, value in arrays.items():
        _require(locations[key] in rows and len(value) == rows[locations[key]], key+": length disagrees with its location")
    _require(not np.any(arrays["temperature"] <= 0), "temperature must be above 0 K")
    with np.errstate(over="ignore", invalid="ignore"):
        v = nodes[triangles][:, 1:]-nodes[triangles][:, :1]
        det = v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0]
    _require(np.isfinite(det).all() and np.all(det > 0), "triangles must be finite nondegenerate CCW")
    mesh = summary.get("mesh")
    size = summary.get("resolved_inputs", {}).get("mesh.element_size", {})
    _require(isinstance(mesh, dict) and mesh.get("nodes") == n and type(mesh.get("nodes")) is int
             and mesh.get("triangles") == m and type(mesh.get("triangles")) is int
             and size.get("value") == doc.si["mesh"]["element_size"], "summary mesh disagrees with the result")
    _check_regions(summary, summary.get("region_names"), ids, doc, rlimits)
    iterations = summary.get("iterations")
    _require(isinstance(iterations, list) and (spec.kind == TEMPERATURE or not iterations),
             "invalid iteration records")
    unit, length_in_m = regions._length(summary, doc)
    payload = {"payload_format": PAYLOAD, **identity, "result_format": pair[0], "field_layout": pair[1],
               "length_unit": unit, "display_length_in_m": length_in_m, "summary": summary,
               "arrays": {key: value.tolist() for key, value in arrays.items()}}
    return common.encode_json(payload, limits.payload_bytes, name="payload_bytes")

