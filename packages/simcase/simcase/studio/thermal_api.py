# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded steady thermal HTTP protocol; an ordinary public simcase consumer.

Policy defaults are candidates for measurement, not peak-RSS guarantees.
No solver, filesystem output or private simcase API is implemented here.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import json
import math
import threading
import time

import numpy as np
from simcase import Document, DocumentError, ThermalRunResult

KIND = "thermal.steady2d"
V1 = ("thermal.steady2d-result-v1", "thermal2d-p1-node-cell-v1")
V2 = ("thermal.steady2d-result-v2", "thermal2d-p1-node-cell-boundary-v2")
PROPERTIES = {
    "nodes_m": "mesh_nodes_m", "triangles": "mesh_triangles",
    "temperature_k": "temperature_k", "heat_flux_w_m2": "heat_flux_w_m2",
    "load_w_per_m": "load_w_per_m", "reaction_w_per_m": "reaction_w_per_m",
    "residual_w_per_m": "residual_w_per_m",
    "dirichlet_node_ids": "dirichlet_node_ids",
    "dirichlet_temperature_k": "dirichlet_temperature_k",
    "prescribed_outward_load_w_per_m": "prescribed_outward_load_w_per_m",
    "ambient_load_w_per_m": "ambient_load_w_per_m",
    "convective_outward_w_per_m": "convective_outward_w_per_m",
    "system_rhs_w_per_m": "system_rhs_w_per_m",
}
BASE_FIELDS = tuple(PROPERTIES)[:9]
BOUNDARY_FIELDS = tuple(PROPERTIES)[9:]


def limited_text(value, limit):
    """Bound UTF-8 error/log text; never use this on scientific arrays."""
    return str(value).encode("utf-8", errors="replace")[:limit].decode("utf-8", errors="ignore")


class ThermalAPIError(Exception):
    def __init__(self, code, message, status=400, *, path=None, tags=None):
        self.code = code
        self.message = limited_text(message, 1024)
        self.status = status
        self.path = limited_text(path, 256) if path is not None else None
        self.tags = dict(tags or {})
        super().__init__(self.message)

    def body(self):
        error = {"code": self.code, "message": self.message}
        if self.path is not None:
            error["path"] = self.path
        return {"ok": False, "error": error, **self.tags}


@dataclass(frozen=True)
class ThermalLimits:
    request_bytes: int = 1048576
    max_nodes: int = 10201
    max_triangles: int = 20000
    payload_bytes: int = 16777216
    active_jobs: int = 1
    terminal_jobs: int = 2
    terminal_bytes: int = 33554432
    ttl_seconds: float = 300.
    log_bytes: int = 65536
    error_bytes: int = 4096
    metadata_bytes: int = 65536
    status_bytes: int = 131072

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == "ttl_seconds":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                    raise ValueError("thermal TTL must be finite positive seconds")
            elif type(value) is not int or value <= 0:
                raise ValueError("thermal resource caps must be positive integers")
        if self.active_jobs > self.terminal_jobs:
            raise ValueError("thermal active reservations need terminal slots")
        if self.payload_bytes+self.status_bytes > self.terminal_bytes:
            raise ValueError("thermal byte budget cannot reserve one complete record")


def v2_available():
    return all(hasattr(ThermalRunResult, PROPERTIES[key]) for key in BOUNDARY_FIELDS)


def capabilities(limits):
    pairs = (V1, V2) if v2_available() else (V1,)
    return {
        "capability_format": "studio-capabilities-v1",
        KIND: {
            "supported": True, "validate": "/api/thermal/validate",
            "run": "/api/thermal/run", "input": "json",
            "mesh_preview": False, "mesh_from_result": True,
            "result_formats": [p[0] for p in pairs],
            "field_layouts": [p[1] for p in pairs],
            "fields": ["temperature_k", "heat_flux_w_m2"],
            "time_navigation": False, "resource_policy": "candidate-unmeasured",
            "limits": asdict(limits),
        },
        "thermal.transient2d": {"supported": False},
        "em.cavity3d": {"supported": False},
    }


def encode_json(value, limit):
    """Count complete encoded bytes, including metadata and JSON punctuation."""
    out = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for fragment in encoder.iterencode(value):
        chunk = fragment.encode("utf-8")
        if len(out)+len(chunk) > limit:
            raise ThermalAPIError("payload_limit_exceeded", "encoded thermal data exceeds its byte limit", 413)
        out.extend(chunk)
    return bytes(out)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ThermalAPIError("invalid_json", "duplicate JSON key")
        result[key] = value
    return result


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ThermalAPIError("invalid_json", "JSON numbers must be finite")
    return number


def _constant(value):
    raise ThermalAPIError("invalid_json", "JSON numbers must be finite")


def _counter(value, name):
    if type(value) is not int or not 0 <= value <= 2**53-1:
        raise ThermalAPIError("invalid_envelope", "expected a nonnegative safe integer", path=name)
    return value


def _preflight(doc, limits):
    if not isinstance(doc, dict):
        raise ThermalAPIError("invalid_envelope", "doc must be an object", path="doc")
    physics = doc.get("physics")
    if (not isinstance(physics, dict) or len(physics) != 1
            or not isinstance(next(iter(physics.values())), dict)
            or next(iter(physics.values())).get("type") != KIND):
        raise ThermalAPIError("unsupported_physics", "thermal Studio accepts one thermal.steady2d entry", path="physics")
    p = next(iter(physics.values()))
    if ("outward_flux_w_m2" in p or "convection" in p) and not v2_available():
        raise ThermalAPIError("unsupported_result_format", "matching public steady boundary runtime is required")
    mesh = doc.get("mesh")
    counts = mesh.get("subdivisions") if isinstance(mesh, dict) else None
    if (not isinstance(counts, list) or len(counts) != 2
            or any(type(n) is not int or n <= 0 for n in counts)):
        raise ThermalAPIError("invalid_document", "expected two positive integer subdivisions", path="mesh.subdivisions")
    nx, ny = counts
    if (nx > limits.max_nodes or ny > limits.max_nodes
            or (nx+1)*(ny+1) > limits.max_nodes or 2*nx*ny > limits.max_triangles):
        raise ThermalAPIError("mesh_limit_exceeded", "thermal mesh exceeds configured node/triangle limits", 413, path="mesh.subdivisions")


@dataclass(frozen=True)
class ThermalInput:
    doc: object
    client_revision: int
    request_seq: int

    def tags(self):
        return {"client_revision": self.client_revision, "request_seq": self.request_seq}


async def read_request(request, limits, *, for_run):
    """Read ASGI chunks with an application cap, not Content-Length trust."""
    tags = {}
    try:
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ThermalAPIError("unsupported_media_type", "thermal requests require application/json", 415)
        data = bytearray()
        try:
            async for chunk in request.stream():
                if len(data)+len(chunk) > limits.request_bytes:
                    raise ThermalAPIError("request_limit_exceeded", "thermal request exceeds configured byte limit", 413)
                data.extend(chunk)
        except ThermalAPIError:
            raise
        except Exception as exc:
            raise ThermalAPIError("request_read_failed", "could not read thermal request body") from exc
        try:
            raw = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                             parse_float=_float, parse_constant=_constant)
            pending = [raw]
            while pending:
                value = pending.pop()
                if isinstance(value, str):
                    value.encode("utf-8")  # escaped unpaired surrogates also refuse
                elif isinstance(value, list):
                    pending.extend(value)
                elif isinstance(value, dict):
                    pending.extend(value.keys())
                    pending.extend(value.values())
        except ThermalAPIError:
            raise
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise ThermalAPIError("invalid_json", "malformed finite UTF-8 JSON") from exc
        if not isinstance(raw, dict) or set(raw) != {"doc", "client_revision", "request_seq"}:
            raise ThermalAPIError("invalid_envelope", "expected exactly doc, client_revision and request_seq")
        tags = {"client_revision": _counter(raw["client_revision"], "client_revision"),
                "request_seq": _counter(raw["request_seq"], "request_seq")}
        _preflight(raw["doc"], limits)
        try:
            doc = Document.from_dict(raw["doc"])
        except (DocumentError, ValueError, TypeError, OverflowError) as exc:
            raise ThermalAPIError("invalid_document", str(exc), 400 if for_run else 200) from exc
        return ThermalInput(doc, **tags)
    except ThermalAPIError as exc:
        exc.tags = dict(tags)
        raise


def validation_payload(spec, limits):
    body = {"ok": True, "doc": spec.doc.data, "summary": spec.doc.summary(),
            "notes": list(spec.doc.notes), **spec.tags()}
    return encode_json(body, limits.payload_bytes)


def _units(key):
    if key == "nodes_m":
        return "m"
    if key in ("triangles", "dirichlet_node_ids"):
        return "1"
    if key in ("temperature_k", "dirichlet_temperature_k"):
        return "K"
    if key == "heat_flux_w_m2":
        return "W/m^2"
    return "W/m"


def _location(key):
    if key == "triangles":
        return "triangle_connectivity"
    if key.startswith("dirichlet_"):
        return "dirichlet_nodes"
    if key == "heat_flux_w_m2":
        return "triangle_centroids"
    return "nodes"


def _require(condition, message):
    if not condition:
        raise ThermalAPIError("invalid_result", message, 500)


def capture_result(result, identity, limits):
    """Read each selected public array once; encode only captured owned copies."""
    _require(isinstance(result, ThermalRunResult), "expected public ThermalRunResult")
    summary = copy.deepcopy(result.summary())
    _require(isinstance(summary, dict), "thermal summary must be an object")
    encode_json(summary, limits.metadata_bytes)
    pair = (summary.get("result_format"), summary.get("field_layout"))
    _require(pair in (V1, V2) and summary.get("physics_type") == KIND, "unsupported thermal result/layout pair")
    keys = BASE_FIELDS+BOUNDARY_FIELDS if pair == V2 else BASE_FIELDS
    arrays = {}
    for key in keys:
        value = getattr(result, PROPERTIES[key])  # one property read
        _require(isinstance(value, np.ndarray), key+": expected a numeric ndarray")
        _require(value.dtype.kind in "iuf", key+": expected real nonboolean dtype")
        arrays[key] = value.copy(order="C")
        _require(np.isfinite(arrays[key]).all(), key+": nonfinite array")
    nodes, triangles, fixed = arrays["nodes_m"], arrays["triangles"], arrays["dirichlet_node_ids"]
    _require(nodes.ndim == 2 and nodes.shape[1] == 2 and len(nodes) >= 3, "invalid nodes_m shape")
    _require(triangles.ndim == 2 and triangles.shape[1] == 3 and len(triangles) > 0
             and triangles.dtype.kind in "iu", "invalid triangle connectivity")
    n, m = len(nodes), len(triangles)
    _require(n <= limits.max_nodes and m <= limits.max_triangles, "result exceeds configured mesh limits")
    _require(not np.any(triangles < 0) and not np.any(triangles >= n), "triangle index outside nodes")
    _require(fixed.ndim == 1 and fixed.dtype.kind in "iu"
             and (pair == V2 or len(fixed) > 0), "invalid Dirichlet IDs")
    _require(not np.any(fixed < 0) and not np.any(fixed >= n), "Dirichlet index outside nodes")
    _require(not np.any(np.diff(fixed.astype(np.int64)) <= 0), "Dirichlet IDs must be sorted unique")
    shapes = {"nodes_m": (n, 2), "triangles": (m, 3), "temperature_k": (n,),
              "heat_flux_w_m2": (m, 2), "dirichlet_node_ids": (len(fixed),),
              "dirichlet_temperature_k": (len(fixed),)}
    for key in keys:
        if key not in shapes:
            shapes[key] = (n,)
        _require(arrays[key].shape == shapes[key], key+": invalid shape")
    _require(not np.any(arrays["dirichlet_temperature_k"] < 0), "negative prescribed Kelvin")
    with np.errstate(over="ignore", invalid="ignore"):
        v = nodes[triangles][:, 1:]-nodes[triangles][:, :1]
        det = v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0]
    _require(np.isfinite(det).all() and np.all(det > 0), "triangles must be finite nondegenerate CCW")
    for meta in ("field_units", "field_locations", "field_shapes"):
        _require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(keys),
                 "invalid "+meta+" field set")
    for key in keys:
        _require(summary["field_units"][key] == _units(key), key+": wrong unit")
        _require(summary["field_locations"][key] == _location(key), key+": wrong location")
        shape = summary["field_shapes"][key]
        _require(isinstance(shape, list) and all(type(x) is int for x in shape)
                 and shape == list(shapes[key]), key+": wrong metadata shape")
    doc = result.doc
    declared = copy.deepcopy(doc["units"])
    _require(summary.get("units") == declared and summary.get("mesh_length_unit") == "m",
             "document/summary unit mismatch")
    length_in_m = doc.scale.to_si(1., {"length": 1})
    _require(not isinstance(length_in_m, bool) and math.isfinite(length_in_m) and length_in_m > 0,
             "invalid display length scale")
    payload = {
        "payload_format": "studio-thermal-steady-v1", **identity,
        "result_format": pair[0], "field_layout": pair[1],
        "display_length_in_m": float(length_in_m),
        "summary": summary, "arrays": {key: arrays[key].tolist() for key in keys},
    }
    return encode_json(payload, limits.payload_bytes)


def bounded_log(values, limit):
    lines, size = [], 2
    if not isinstance(values, (list, tuple)):
        values = ["thermal log unavailable"]
    for value in values[:64]:
        text = limited_text(value, min(limit, 4096))
        encoded = json.dumps(text, ensure_ascii=False).encode("utf-8")
        if size+len(encoded)+1 > limit:
            break
        lines.append(text)
        size += len(encoded)+1
    return lines


@dataclass(eq=False)
class ThermalLease:
    reservation: int
    job: str | None = None
    released: bool = False


class ThermalJobs:
    """Separate bounded thermal store; never evicts optical/unexpired jobs."""

    def __init__(self, limits=None, *, clock=None):
        self.limits = limits or ThermalLimits()
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._records = {}
        self._active = 0
        self._reserved_bytes = 0
        self._pending = 0

    def _expire(self):
        now = self._clock()
        for job, rec in list(self._records.items()):
            if (rec["lease"].released and rec["terminal_at"] is not None
                    and now-rec["terminal_at"] >= self.limits.ttl_seconds):
                del self._records[job]

    def _retained_bytes(self):
        return sum(len(rec["status_bytes"])+len(rec["result"] or b"")
                   for rec in self._records.values() if rec["lease"].released)

    def reserve(self):
        with self._lock:
            self._expire()
            budget = self.limits.payload_bytes+self.limits.status_bytes
            if (self._active >= self.limits.active_jobs
                    or len(self._records)+self._pending >= self.limits.terminal_jobs
                    or self._retained_bytes()+self._reserved_bytes+budget > self.limits.terminal_bytes):
                raise ThermalAPIError("capacity_exceeded", "thermal job capacity unavailable", 429)
            lease = ThermalLease(budget)
            self._active += 1
            self._pending += 1
            self._reserved_bytes += budget
            return lease

    def _status(self, identity, status, log, error, has_result):
        return encode_json({**identity, "status": status, "log": log,
                            "error": error, "has_result": has_result}, self.limits.status_bytes)

    def attach(self, lease, job, result_id, spec):
        identity = {"kind": KIND, "job": job, "result_id": result_id, **spec.tags()}
        status = self._status(identity, "running", [], None, False)
        with self._lock:
            if lease.released or lease.job is not None or job in self._records:
                raise RuntimeError("invalid thermal job attachment")
            self._records[job] = {"lease": lease, "identity": identity,
                                  "status": "running", "status_bytes": status,
                                  "result": None, "terminal_at": None}
            lease.job = job
            self._pending -= 1
        return dict(identity)

    def identity(self, lease):
        with self._lock:
            return dict(self._records[lease.job]["identity"])

    def _publish(self, lease, status, result, log, error):
        with self._lock:
            rec = self._records.get(lease.job)
            if lease.released or rec is None or rec["status"] != "running":
                return False
            encoded = self._status(rec["identity"], status, log, error, result is not None)
            rec.update(status=status, status_bytes=encoded, result=result,
                       terminal_at=self._clock())
            return True

    def complete(self, lease, payload, log):
        if type(payload) is not bytes or len(payload) > self.limits.payload_bytes:
            raise ThermalAPIError("payload_limit_exceeded", "invalid or oversized encoded result", 413)
        return self._publish(lease, "done", payload,
                             bounded_log(log, self.limits.log_bytes), None)

    def fail(self, lease, exc, code="solver_failed"):
        if isinstance(exc, ThermalAPIError):
            code, message = exc.code, exc.message
        else:
            message = type(exc).__name__+": "+limited_text(exc, self.limits.error_bytes//8)
        error = {"code": limited_text(code, 64),
                 "message": limited_text(message, self.limits.error_bytes//8)}
        # Escaping overhead is counted; the conservative text bound is not raw-only.
        encode_json(error, self.limits.error_bytes)
        return self._publish(lease, "error", None, [], error)

    def release(self, lease):
        with self._lock:
            if lease.released:
                return
            lease.released = True
            self._active -= 1
            self._reserved_bytes -= lease.reservation
            if lease.job is None:
                self._pending -= 1
                return
            rec = self._records.get(lease.job)
            if rec is not None and rec["status"] == "running":
                try:
                    error = {"code": "publication_failed", "message": "thermal job did not publish a terminal state"}
                    encoded = self._status(rec["identity"], "error", [], error, False)
                    rec.update(status="error", status_bytes=encoded, result=None, terminal_at=self._clock())
                except Exception:
                    # Remove only this unpublished thermal record; never a shared job.
                    self._records.pop(lease.job, None)

    def status(self, job):
        with self._lock:
            self._expire()
            rec = self._records.get(job)
            if rec is None:
                raise ThermalAPIError("unknown_job", "unknown or expired thermal job", 404)
            return rec["status_bytes"]

    def result(self, job):
        with self._lock:
            self._expire()
            rec = self._records.get(job)
            if rec is None:
                raise ThermalAPIError("unknown_job", "unknown or expired thermal job", 404)
            if rec["status"] != "done" or rec["result"] is None:
                raise ThermalAPIError("result_not_ready", "thermal job is "+rec["status"], 409)
            return rec["result"]
