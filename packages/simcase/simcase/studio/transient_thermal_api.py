# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact stored-time transient Studio transport using public simcase results."""
from __future__ import annotations

from dataclasses import dataclass
import copy
import json
import math
import re
from types import MappingProxyType

import numpy as np
from simcase import Document, DocumentError, TransientThermalRunResult
from . import thermal_api as common

KIND = "thermal.transient2d"
PAIR = ("thermal.transient2d-result-v1", "thermal2d-transient-p1-node-cell-v1")
MANIFEST = "studio-thermal-transient-v1"
FRAME = "studio-thermal-transient-frame-v1"
HISTORY = "studio-thermal-transient-history-v1"
MAX_TIMES = 128
RAW_BYTES = 16*1024**2
ENCODED_BYTES = 4*1024**2
PAGE_ROWS = 16
# Independent transport metadata: do not import private producer implementation.
SPEC = {
    "nodes_m": ("m", "nodes", "static"),
    "triangles": ("1", "triangle_connectivity", "static"),
    "time_s": ("s", "requested_times", "time_s"),
    "temperature_k": ("K", "nodes", "time_s"),
    "heat_flux_w_m2": ("W/m^2", "triangle_centroids", "time_s"),
    "source_load_w_per_m": ("W/m", "nodes", "time_s"),
    "reaction_w_per_m": ("W/m", "nodes", "time_s[1:]"),
    "residual_w_per_m": ("W/m", "nodes", "time_s[1:]"),
    "storage_rate_w_per_m": ("W/m", "nodes", "time_s[1:]"),
    "heat_content_j_per_m": ("J/m", "domain", "time_s"),
    "quadratic_functional_jk_per_m": ("J K/m", "domain", "time_s"),
    "dirichlet_node_ids": ("1", "dirichlet_nodes", "static"),
    "dirichlet_temperatures_k": ("K", "dirichlet_nodes", "time_s"),
}
UI_FIELDS = {"temperature_k", "heat_flux_w_m2", "heat_content_j_per_m",
             "quadratic_functional_jk_per_m"}
DYNAMIC = set(SPEC)-{"nodes_m", "triangles", "time_s", "dirichlet_node_ids"}


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
    mesh, study = data.get("mesh"), data.get("study")
    subdivisions = mesh.get("subdivisions") if isinstance(mesh, dict) else None
    require(isinstance(subdivisions, list) and len(subdivisions) == 2
            and all(type(n) is int and n > 0 for n in subdivisions),
            "mesh.subdivisions must be two positive integers", code="invalid_document")
    nx, ny = subdivisions
    n, m = (nx+1)*(ny+1), 2*nx*ny
    require(n <= limits.max_nodes and m <= limits.max_triangles,
            "transient mesh exceeds resource cap", 413, "mesh_limit_exceeded")
    times = study.get("time_s") if isinstance(study, dict) else None
    require(isinstance(times, list) and len(times) >= 2,
            "study.time_s must contain at least two requested times", code="invalid_document")
    require(len(times) <= MAX_TIMES, "too many requested times", 413, "history_limit_exceeded")
    try:
        valid = (all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in times)
                 and all(b > a and math.isfinite(b-a) for a, b in zip(times, times[1:])))
    except OverflowError:
        valid = False
    require(valid, "requested times must be finite strictly increasing seconds", code="invalid_document")
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


async def read_request(request, limits, *, for_run):
    # Same bounded strict reader, with a route-specific public preflight callback.
    spec = await common.read_request(request, limits, for_run=for_run,
                                     preflight=preflight, runtime_check=lambda: True)
    return TransientInput(spec.doc, spec.client_revision, spec.request_seq)


def validation_payload(spec, limits):
    return common.encode_json({"ok": True, "kind": KIND, **spec.tags(),
                               "doc": spec.doc.data, "summary": spec.doc.summary(),
                               "notes": list(spec.doc.notes)}, limits.metadata_bytes)


def capabilities():
    return {"supported": True, "run_enabled": True,
            "validate": "/api/thermal/transient/validate", "run": "/api/thermal/transient/run",
            "input": "json", "mesh_preview": False, "mesh_from_result": True,
            "time_navigation": True, "result_formats": [PAIR[0]], "field_layouts": [PAIR[1]],
            "payload_formats": [MANIFEST, FRAME, HISTORY], "fields": sorted(UI_FIELDS),
            "resource_policy": "candidate-unmeasured",
            "limits": {"max_times": MAX_TIMES, "raw_bytes": RAW_BYTES,
                       "manifest_bytes": ENCODED_BYTES, "frame_page_bytes": ENCODED_BYTES,
                       "page_rows": PAGE_ROWS, "read_encoding_slots": 1, "ingress_slots": 1}}


def reservation(limits):
    amount = RAW_BYTES+ENCODED_BYTES+limits.status_bytes
    require(amount <= limits.terminal_bytes, "transient reservation exceeds shared budget",
            429, "capacity_exceeded")
    return amount


def capture_result(result, identity, limits, document):
    require(isinstance(result, TransientThermalRunResult), "public transient result required")
    original = json.dumps(document.data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    summary = copy.deepcopy(result.summary())
    common.encode_json(summary, limits.metadata_bytes)
    require(isinstance(summary, dict) and summary.get("physics_type") == KIND
            and (summary.get("result_format"), summary.get("field_layout")) == PAIR,
            "unsupported transient summary/result pair")
    # Producer summary validates its own bound snapshot; compare against this job too.
    require(json.dumps(result.doc.data, sort_keys=True, separators=(",", ":"), allow_nan=False)
            == original, "public result document does not match accepted snapshot")
    require(summary.get("units") == document["units"] and summary.get("mesh_length_unit") == "m",
            "transient document/SI units mismatch")
    n, m, nt = preflight(document.data, limits)
    captured = {}
    total = 0
    fixed_count = None
    # Capture each public property exactly once; never use producer _raw_arrays.
    order = ("nodes_m", "triangles", "time_s", "dirichlet_node_ids")+tuple(
        k for k in SPEC if k not in {"nodes_m", "triangles", "time_s", "dirichlet_node_ids"})
    for key in order:
        value = getattr(result, key)
        require(isinstance(value, np.ndarray) and value.dtype.kind in "iuf",
                "transient "+key+" requires real nonboolean ndarray")
        if key == "dirichlet_node_ids":
            require(value.ndim == 1 and len(value) <= n and value.dtype.kind in "iu",
                    "invalid transient Dirichlet IDs")
            fixed_count = len(value)
        shapes = {"nodes_m": (n, 2), "triangles": (m, 3), "time_s": (nt,),
                  "dirichlet_node_ids": (fixed_count,), "temperature_k": (nt, n),
                  "heat_flux_w_m2": (nt, m, 2), "source_load_w_per_m": (nt, n),
                  "reaction_w_per_m": (nt-1, n), "residual_w_per_m": (nt-1, n),
                  "storage_rate_w_per_m": (nt-1, n), "heat_content_j_per_m": (nt,),
                  "quadratic_functional_jk_per_m": (nt,),
                  "dirichlet_temperatures_k": (nt, fixed_count)}
        require(value.shape == shapes[key], "transient "+key+" shape mismatch")
        require(np.isfinite(value).all(), "nonfinite transient "+key)
        require(value.dtype.itemsize <= 8, "unsupported transient numeric width")
        total += value.nbytes
        require(total <= RAW_BYTES, "transient raw bytes exceed cap", 413, "history_limit_exceeded")
        owned = np.array(value, copy=True, order="C")
        require(np.isfinite(owned).all(), "nonfinite captured transient "+key)
        owned.flags.writeable = False
        captured[key] = owned
    x, tri, fixed = (captured[k] for k in ("nodes_m", "triangles", "dirichlet_node_ids"))
    require(tri.dtype.kind in "iu" and np.all(tri >= 0) and np.all(tri < n),
            "transient triangle indices invalid")
    require(np.all(fixed >= 0) and np.all(fixed < n)
            and np.all(fixed[1:] > fixed[:-1]), "transient Dirichlet IDs invalid")
    a, b, c = x[tri[:, 0]], x[tri[:, 1]], x[tri[:, 2]]
    with np.errstate(over="ignore", invalid="ignore"):
        area = (b[:, 0]-a[:, 0])*(c[:, 1]-a[:, 1])-(b[:, 1]-a[:, 1])*(c[:, 0]-a[:, 0])
    require(np.isfinite(area).all() and np.all(area > 0), "transient mesh must be CCW")
    require(np.array_equal(captured["time_s"], np.asarray(document["study"]["time_s"])),
            "transient requested time axis mismatch")
    for meta in ("field_units", "field_locations", "field_time_axes", "field_shapes"):
        require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(SPEC),
                "transient metadata field set mismatch")
    descriptors = {}
    for key, (unit, location, axis) in SPEC.items():
        require(summary["field_units"][key] == unit and summary["field_locations"][key] == location
                and summary["field_time_axes"][key] == axis
                and summary["field_shapes"][key] == list(captured[key].shape),
                "transient metadata mismatch: "+key)
        descriptors[key] = {"shape": list(captured[key].shape), "unit": unit,
                            "location": location, "axis": axis,
                            "available_views": ["frame", "history"] if key in DYNAMIC else [],
                            "initial_available": axis != "time_s[1:]",
                            "ui_supported": key in UI_FIELDS}
    scale = document.scale.to_si(1., {"length": 1})
    require(type(scale) in (int, float) and math.isfinite(scale) and scale > 0,
            "transient display scale invalid")
    pair = {"result_format": PAIR[0], "field_layout": PAIR[1]}
    base = {**identity, **pair, "display_length_in_m": scale}
    job, rid = identity["job"], identity["result_id"]
    payload = {**base, "payload_format": MANIFEST, "summary": summary, "fields": descriptors,
               "time_s": captured["time_s"].tolist(), "default_frame_index": nt-1,
               "arrays": {k: captured[k].tolist() for k in ("nodes_m", "triangles", "dirichlet_node_ids")},
               "frame_url": "/api/jobs/"+job+"/frame?result_id="+rid
                            +"&field={field}&time_index={time_index}&frame_seq={frame_seq}",
               "history_url": "/api/jobs/"+job+"/history?result_id="+rid
                              +"&field={field}&start={start}&stop={stop}&frame_seq={frame_seq}"}
    encoded = common.encode_json(payload, ENCODED_BYTES)
    return encoded, MappingProxyType(captured), scale


def _query_integer(value):
    require(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,15}", value) is not None,
            "query requires nonnegative integer", code="invalid_query")
    number = int(value)
    require(number <= 2**53-1, "query integer exceeds safe range", code="invalid_query")
    return number


def parse_query(query, *, history):
    items = list(query.multi_items())
    expected = {"result_id", "field", "frame_seq"} | ({"start", "stop"} if history else {"time_index"})
    require(len(items) == len(expected) and {k for k, _ in items} == expected,
            "unexpected, missing or duplicate query", code="invalid_query")
    values = dict(items)
    require(len(values["result_id"]) <= 128 and values["result_id"].startswith("result-")
            and re.fullmatch(r"[A-Za-z0-9-]+", values["result_id"]) is not None,
            "invalid result identity", code="invalid_query")
    require(values["field"] in DYNAMIC, "unsupported transient field", code="invalid_query")
    for key in expected-{"result_id", "field"}:
        values[key] = _query_integer(values[key])
    return values


def encode_view(record, query, *, history):
    # Only captured immutable backing, never public producer access or re-solve.
    arrays = record.get("raw")
    require(arrays is not None and record["identity"]["kind"] == KIND,
            "job has no transient history", code="unsupported_result_format")
    key = query["field"]
    unit, location, axis = SPEC[key]
    times = arrays["time_s"]
    nt = len(times)
    base = {**record["identity"], "result_format": PAIR[0], "field_layout": PAIR[1],
            # Display scale is captured in immutable manifest, bounded <=4MiB.
            "display_length_in_m": record["display_length_in_m"],
            "frame_seq": query["frame_seq"], "field": key, "unit": unit, "location": location}
    if history:
        start, stop = query["start"], query["stop"]
        require(start < stop <= nt and stop-start <= PAGE_ROWS,
                "history page range invalid", 422, "invalid_range")
        require(axis != "time_s[1:]" or start >= 1,
                "initial rate is unavailable", 422, "unavailable_initial_rate")
        rows = arrays[key][start-1:stop-1] if axis == "time_s[1:]" else arrays[key][start:stop]
        payload = {**base, "payload_format": HISTORY, "start": start, "stop": stop,
                   "time_indices": list(range(start, stop)), "time_s": times[start:stop].tolist(),
                   "shape": list(rows.shape), "arrays": {key: rows.tolist()}}
        if axis == "time_s[1:]":
            payload.update(interval_start_s=times[start-1:stop-1].tolist(),
                           interval_end_s=times[start:stop].tolist())
    else:
        index = query["time_index"]
        require(index < nt, "time index outside requested times", 422, "invalid_range")
        require(axis != "time_s[1:]" or index >= 1,
                "initial rate is unavailable", 422, "unavailable_initial_rate")
        row = arrays[key][index-1 if axis == "time_s[1:]" else index]
        payload = {**base, "payload_format": FRAME, "time_index": index,
                   "time_s": float(times[index]), "shape": list(np.shape(row)),
                   "arrays": {key: row.tolist()}}
        if axis == "time_s[1:]":
            payload.update(interval_start_s=float(times[index-1]), interval_end_s=float(times[index]))
    return common.encode_json(payload, ENCODED_BYTES)
