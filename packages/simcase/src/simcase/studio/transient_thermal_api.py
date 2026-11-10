# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact stored-time transient Studio transport using public simcase results."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from types import MappingProxyType

import numpy as np
from simcase import Document, DocumentError, TransientThermalRunResult
from . import thermal_api as common

KIND = "thermal.transient2d"
# Rectangle documents are format 0.3: arrays under registry names, SI values.
PAIR = ("thermal.transient2d-result-v3", "thermal2d-transient-p1-node-cell-v2")
MANIFEST = "studio-thermal-transient-v2"
FRAME = "studio-thermal-transient-frame-v2"
HISTORY = "studio-thermal-transient-history-v2"
MAX_TIMES = 128
RAW_BYTES = 16*1024**2
ENCODED_BYTES = 4*1024**2
PAGE_ROWS = 16
# Independent transport metadata: do not import private producer implementation.
# (unit, location, time axis); a structural array has no unit, a static one no time axis.
SPEC = {
    "node_coordinates": ("m", "nodes", "static"),
    "triangles": (None, "triangle_connectivity", "static"),
    "time": ("s", "requested_times", "time"),
    "temperature": ("K", "nodes", "time"),
    "heat_flux": ("W/m^2", "triangle_centroids", "time"),
    "generated_heat_rate_per_depth": ("W/m", "nodes", "time"),
    "reaction_heat_rate_per_depth": ("W/m", "nodes", "time[1:]"),
    "residual_heat_rate_per_depth": ("W/m", "nodes", "time[1:]"),
    "heat_storage_rate_per_depth": ("W/m", "nodes", "time[1:]"),
    "stored_heat_per_depth": ("J/m", "domain", "time"),
    "thermal_energy_functional_per_depth": ("J K/m", "domain", "time"),
    "prescribed_node_ids": (None, "prescribed_nodes", "static"),
    "prescribed_temperature": ("K", "prescribed_nodes", "time"),
}
UI_FIELDS = {"temperature", "heat_flux", "stored_heat_per_depth", "thermal_energy_functional_per_depth"}
DYNAMIC = set(SPEC)-{"node_coordinates", "triangles", "time", "prescribed_node_ids"}
STATIC = ("node_coordinates", "triangles", "time", "prescribed_node_ids")
FORMAT_03 = ('transient Studio reads format 0.3 rectangle documents ("openphysics": "0.3", values with their '
             'units); format 0.2 rectangle documents are not read')
def _family(record_pair):
    """``(spec, time key, frame id, history id, rate axis)`` of a record: rectangle and region
    records alike carry the registry names (format 0.3)."""
    return SPEC, "time", FRAME, HISTORY, "time[1:]"


def require(condition, message, status=400, code="invalid_result"):
    if not condition:
        raise common.ThermalAPIError(code, message, status)


def preflight(data, limits):
    require(isinstance(data, dict), "doc must be an object", code="invalid_envelope")
    physics = data.get("physics")
    require(isinstance(physics, dict) and len(physics) == 1
            and isinstance(next(iter(physics.values())), dict)
            and next(iter(physics.values())).get("type") == KIND,
            "transient route accepts one thermal.transient2d entry", code="unsupported_physics")
    require(data.get("openphysics") == "0.3", FORMAT_03, code="invalid_document")
    # The transient view shows the V1 pair only: documents that select the boundary
    # layout (key presence, as in the headless contract) are refused before any
    # validation or run, with no job; run them headless instead.
    entry = next(iter(physics.values()))
    require(not ("inward_heat_flux" in entry or "convection" in entry),
            "transient Studio shows prescribed-temperature and insulated sides only; a document with "
            "inward_heat_flux or convection saves the boundary layout and runs headless "
            "(python -m simcase run)", code="unsupported_physics")
    n, m = common.subdivisions(data, limits)
    study = data.get("study")
    time = study.get("time") if isinstance(study, dict) else None
    times = time.get("values") if isinstance(time, dict) else None
    require(isinstance(times, list) and len(times) >= 2,
            "study.time must be a tagged array of at least two requested times", code="invalid_document")
    require(len(times) <= MAX_TIMES, "too many requested times", 413, "history_limit_exceeded")
    try:
        valid = (all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in times)
                 and all(b > a and math.isfinite(b-a) for a, b in zip(times, times[1:])))
    except OverflowError:
        valid = False
    require(valid, "requested times must be finite strictly increasing values", code="invalid_document")
    nt = len(times)
    # Sound D=N upper bound before public boundary validation/deduplication.
    scalar_count = (5*nt-1)*n+(2*nt+3)*m+(nt+1)*n+3*nt
    require(8*scalar_count <= RAW_BYTES, "combined transient history exceeds raw cap",
            413, "history_limit_exceeded")
    return n, m, nt


@dataclass(frozen=True)
class TransientInput:
    doc: object
    client_revision: int
    request_seq: int
    kind = KIND

    def tags(self):
        return {"client_revision": self.client_revision, "request_seq": self.request_seq}


async def read_request(request, limits, *, for_run, region=None):
    # Same bounded strict reader, with a route-specific public preflight callback.
    spec = await common.read_request(request, limits, for_run=for_run,
                                     preflight=preflight, runtime_check=lambda: runtime_available(limits),
                                     region=region)
    if not isinstance(spec, common.ThermalInput):
        return spec  # a region document's input (thermal_regions_api.RegionInput)
    return TransientInput(spec.doc, spec.client_revision, spec.request_seq)


def validation_payload(spec, limits):
    return common.encode_json({"ok": True, "kind": KIND, **spec.tags(),
                               **common.document_body(spec.doc), "summary": spec.doc.summary()},
                              limits.metadata_bytes)


def runtime_available(limits):
    return (callable(getattr(TransientThermalRunResult, "summary", None))
            and hasattr(TransientThermalRunResult, "mesh_triangles")
            and RAW_BYTES+ENCODED_BYTES+limits.status_bytes <= limits.terminal_bytes)


def capabilities(limits):
    bounds = common.asdict(limits)
    bounds.update(max_times=MAX_TIMES, raw_bytes=RAW_BYTES,
                  manifest_bytes=ENCODED_BYTES, frame_page_bytes=ENCODED_BYTES,
                  page_rows=PAGE_ROWS, read_encoding_slots=1, ingress_slots=1)
    return {"supported": True, "run_enabled": runtime_available(limits),
            "validate": "/api/thermal/transient/validate", "run": "/api/thermal/transient/run",
            "input": "json", "mesh_preview": False, "mesh_from_result": True,
            "time_navigation": True, "result_formats": [PAIR[0]], "field_layouts": [PAIR[1]],
            "payload_formats": [MANIFEST, FRAME, HISTORY], "fields": sorted(UI_FIELDS),
            "resource_policy": "candidate-unmeasured",
            "limits": bounds}


def reservation(limits):
    amount = RAW_BYTES+ENCODED_BYTES+limits.status_bytes
    require(amount <= limits.terminal_bytes, "transient reservation exceeds shared budget",
            429, "capacity_exceeded")
    return amount


def capture_result(result, identity, limits, document):
    require(isinstance(result, TransientThermalRunResult), "public transient result required")
    require(document.si is not None, "a format 0.3 rectangle document required")
    original = document.canonical_json(separators=(",", ":"))
    summary = common.json_value(result.summary())
    common.encode_json(summary, limits.metadata_bytes)
    require(isinstance(summary, dict) and summary.get("physics_type") == KIND
            and (summary.get("result_format"), summary.get("field_layout")) == PAIR,
            "unsupported transient summary/result pair")
    # Producer summary validates its own bound snapshot; compare against this job too.
    require(result.doc.canonical_json(separators=(",", ":"))
            == original, "public result document does not match accepted snapshot")
    unit, scale = common.length_unit(document)
    require(common.domain_input(summary, document).get("length_unit") == unit,
            "transient document/summary length_unit mismatch")
    n, m, nt = preflight(common.json_value(document.data), limits)
    captured = {}
    total = 0
    fixed_count = None
    # Capture each public property exactly once; never use producer _raw_arrays.
    order = STATIC+tuple(k for k in SPEC if k not in STATIC)
    for key in order:
        value = getattr(result, key)
        require(isinstance(value, np.ndarray) and value.dtype.kind in "iuf",
                "transient "+key+" requires real nonboolean ndarray")
        if key == "prescribed_node_ids":
            require(value.ndim == 1 and len(value) <= n and value.dtype.kind in "iu",
                    "invalid transient prescribed node IDs")
            fixed_count = len(value)
        shapes = {"node_coordinates": (n, 2), "triangles": (m, 3), "time": (nt,),
                  "prescribed_node_ids": (fixed_count,), "temperature": (nt, n),
                  "heat_flux": (nt, m, 2), "generated_heat_rate_per_depth": (nt, n),
                  "reaction_heat_rate_per_depth": (nt-1, n), "residual_heat_rate_per_depth": (nt-1, n),
                  "heat_storage_rate_per_depth": (nt-1, n), "stored_heat_per_depth": (nt,),
                  "thermal_energy_functional_per_depth": (nt,),
                  "prescribed_temperature": (nt, fixed_count)}
        require(value.shape == shapes[key], "transient "+key+" shape mismatch")
        require(np.isfinite(value).all(), "nonfinite transient "+key)
        require(value.dtype.itemsize <= 8, "unsupported transient numeric width")
        total += value.nbytes
        require(total <= RAW_BYTES, "transient raw bytes exceed cap", 413, "history_limit_exceeded")
        owned = np.array(value, copy=True, order="C")
        require(np.isfinite(owned).all(), "nonfinite captured transient "+key)
        owned.flags.writeable = False
        captured[key] = owned
    x, tri, fixed = (captured[k] for k in ("node_coordinates", "triangles", "prescribed_node_ids"))
    require(tri.dtype.kind in "iu" and np.all(tri >= 0) and np.all(tri < n),
            "transient triangle indices invalid")
    require(np.all(fixed >= 0) and np.all(fixed < n)
            and np.all(fixed[1:] > fixed[:-1]), "transient prescribed node IDs invalid")
    a, b, c = x[tri[:, 0]], x[tri[:, 1]], x[tri[:, 2]]
    with np.errstate(over="ignore", invalid="ignore"):
        area = (b[:, 0]-a[:, 0])*(c[:, 1]-a[:, 1])-(b[:, 1]-a[:, 1])*(c[:, 0]-a[:, 0])
    require(np.isfinite(area).all() and np.all(area > 0), "transient mesh must be CCW")
    require(np.array_equal(captured["time"], np.asarray(document.si["study"]["time"])),
            "transient requested time axis mismatch")
    expected = {"field_units": [k for k, v in SPEC.items() if v[0] is not None],
                "field_locations": list(SPEC), "field_shapes": list(SPEC),
                "field_time_axes": [k for k, v in SPEC.items() if v[2] != "static"]}
    for meta, keys in expected.items():
        require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(keys),
                "transient metadata field set mismatch")
    mesh_meta, study_meta = summary.get("mesh"), summary.get("study")
    counts = summary.get("resolved_inputs", {}).get("mesh.subdivision_count", {}).get("value")
    require(isinstance(mesh_meta, dict) and type(mesh_meta.get("nodes")) is int
            and type(mesh_meta.get("triangles")) is int
            and mesh_meta["nodes"] == n and mesh_meta["triangles"] == m
            and isinstance(counts, list) and all(type(v) is int for v in counts)
            and counts == document.si["mesh"]["subdivision_count"],
            "transient summary mesh disagrees with captured geometry")
    declared = study_meta.get("time") if isinstance(study_meta, dict) else None
    declared_times = declared.get("values") if isinstance(declared, dict) else None
    require(isinstance(study_meta, dict) and study_meta.get("type") == "transient"
            and declared.get("unit") == "s" and isinstance(declared_times, list)
            and all(type(v) in (int, float) and math.isfinite(v) for v in declared_times)
            and np.array_equal(np.asarray(declared_times), captured["time"]),
            "transient summary study disagrees with captured times")
    require(type(summary.get("prescribed_nodes")) is int
            and summary["prescribed_nodes"] == fixed_count,
            "transient summary prescribed node count disagrees")
    descriptors = {}
    for key, (field_unit, location, axis) in SPEC.items():
        declared_shape = summary["field_shapes"][key]
        require(isinstance(declared_shape, list) and all(type(v) is int for v in declared_shape)
                and summary["field_units"].get(key) == field_unit and summary["field_locations"][key] == location
                and summary["field_time_axes"].get(key, "static") == axis
                and declared_shape == list(captured[key].shape),
                "transient metadata mismatch: "+key)
        descriptors[key] = {"shape": list(captured[key].shape), "unit": field_unit,
                            "location": location, "axis": axis,
                            "available_views": ["frame", "history"] if key in DYNAMIC else [],
                            "initial_available": axis != "time[1:]",
                            "ui_supported": key in UI_FIELDS}
    require(type(scale) in (int, float) and math.isfinite(scale) and scale > 0,
            "transient display scale invalid")
    pair = {"result_format": PAIR[0], "field_layout": PAIR[1]}
    base = {**identity, **pair, "length_unit": unit, "display_length_in_m": scale}
    job, rid = identity["job"], identity["result_id"]
    payload = {**base, "payload_format": MANIFEST, "summary": summary, "fields": descriptors,
               "time": captured["time"].tolist(), "default_frame_index": nt-1,
               "arrays": {k: captured[k].tolist() for k in ("node_coordinates", "triangles", "prescribed_node_ids")},
               "frame_url": "/api/jobs/"+job+"/frame?result_id="+rid
                            +"&field={field}&time_index={time_index}&frame_seq={frame_seq}",
               "history_url": "/api/jobs/"+job+"/history?result_id="+rid
                              +"&field={field}&start={start}&stop={stop}&frame_seq={frame_seq}"}
    encoded = common.encode_json(payload, ENCODED_BYTES)
    return encoded, MappingProxyType(captured), scale


def _query_integer(value, *, signed=False):
    require(isinstance(value, str) and re.fullmatch(r"-?(0|[1-9][0-9]{0,15})" if signed else r"0|[1-9][0-9]{0,15}", value) is not None,
            "query requires nonnegative integer", code="invalid_query")
    number = int(value)
    require(abs(number) <= 2**53-1, "query integer exceeds safe range", code="invalid_query")
    return number


def parse_query(query, *, history):
    items = list(query.multi_items())
    expected = {"result_id", "field", "frame_seq"} | ({"start", "stop"} if history else {"time_index"})
    require(len(items) == len(expected) and {k for k, _ in items} == expected,
            "unexpected, missing or duplicate query", code="invalid_query")
    values = dict(items)
    require(0 < len(values["result_id"]) <= 128
            and re.fullmatch(r"[A-Za-z0-9._~-]+", values["result_id"]) is not None,
            "invalid result identity", code="invalid_query")
    require(values["field"] in DYNAMIC, "unsupported transient field", code="invalid_query")
    for key in expected-{"result_id", "field"}:
        values[key] = _query_integer(values[key], signed=key != "frame_seq")
    return values


def encode_view(record, query, *, history):
    # Only captured immutable backing, never public producer access or re-solve.
    arrays = record.get("raw")
    require(arrays is not None and record["identity"]["kind"] == KIND,
            "job has no transient history", code="unsupported_result_format")
    pair = record.get("pair", PAIR)  # region records store their own pair
    spec, time_key, frame_id, history_id, rate_axis = _family(pair)
    key = query["field"]
    require(key in spec and key in arrays, "unsupported transient field for this result", code="invalid_query")
    unit, location, axis = spec[key]
    times = arrays[time_key]
    nt = len(times)
    base = {**record["identity"], "result_format": pair[0], "field_layout": pair[1],
            # Display scale is captured in immutable manifest, bounded <=4MiB.
            "display_length_in_m": record["display_length_in_m"],
            "frame_seq": query["frame_seq"], "field": key, "unit": unit, "location": location}
    start_key, end_key = "interval_start", "interval_end"
    if history:
        start, stop = query["start"], query["stop"]
        require(0 <= start < stop <= nt and stop-start <= PAGE_ROWS,
                "history page range invalid", 422, "invalid_range")
        require(axis != rate_axis or start >= 1,
                "initial rate is unavailable", 422, "unavailable_initial_rate")
        rows = arrays[key][start-1:stop-1] if axis == rate_axis else arrays[key][start:stop]
        payload = {**base, "payload_format": history_id, "start": start, "stop": stop,
                   "time_indices": list(range(start, stop)), time_key: times[start:stop].tolist(),
                   "shape": list(rows.shape), "arrays": {key: rows.tolist()}}
        if axis == rate_axis:
            payload.update({start_key: times[start-1:stop-1].tolist(), end_key: times[start:stop].tolist()})
    else:
        index = query["time_index"]
        require(0 <= index < nt, "time index outside requested times", 422, "invalid_range")
        require(axis != rate_axis or index >= 1,
                "initial rate is unavailable", 422, "unavailable_initial_rate")
        row = arrays[key][index-1 if axis == rate_axis else index]
        payload = {**base, "payload_format": frame_id, "time_index": index,
                   time_key: float(times[index]), "shape": list(np.shape(row)),
                   "arrays": {key: row.tolist()}}
        if axis == rate_axis:
            payload.update({start_key: float(times[index-1]), end_key: float(times[index])})
    return common.encode_json(payload, ENCODED_BYTES)
