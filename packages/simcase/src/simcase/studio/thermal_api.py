# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded steady thermal HTTP protocol; an ordinary public simcase consumer.

Policy defaults are candidates for measurement, not peak-RSS guarantees.
No solver, filesystem output or private simcase API is implemented here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import decimal
import json
import math
import threading
import time

import numpy as np
from simcase import Document, DocumentError, ThermalRunResult
from simcase import reader

KIND = "thermal.steady2d"
# Rectangle documents are format 0.3: arrays under registry names, SI values.
V1 = ("thermal.steady2d-result-v3", "thermal2d-p1-node-cell-v2")
V2 = ("thermal.steady2d-result-v4", "thermal2d-p1-node-cell-boundary-v3")
PAYLOAD = "studio-thermal-steady-v2"
PROPERTIES = {key: key for key in (
    "node_coordinates", "triangles", "temperature", "heat_flux", "generated_heat_rate_per_depth",
    "reaction_heat_rate_per_depth", "residual_heat_rate_per_depth", "prescribed_node_ids", "prescribed_temperature",
    "outward_prescribed_heat_rate_per_depth", "ambient_convective_heat_rate_per_depth",
    "outward_convective_heat_rate_per_depth", "applied_heat_rate_per_depth")}
BASE_FIELDS = tuple(PROPERTIES)[:9]
BOUNDARY_FIELDS = tuple(PROPERTIES)[9:]
#: arrays without a unit (connectivity and node indices)
STRUCTURAL = ("triangles", "prescribed_node_ids")
FORMAT_03 = ('thermal Studio reads format 0.3 rectangle documents ("openphysics": "0.3", values with their '
             'units); format 0.2 rectangle documents are not read')


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


def runtime_available():
    return all(hasattr(ThermalRunResult, key) for key in ("result_format", "field_layout"))


def v2_available():
    return all(hasattr(ThermalRunResult, PROPERTIES[key]) for key in BOUNDARY_FIELDS)


def capabilities(limits):
    pairs = ((V1, V2) if v2_available() else (V1,)) if runtime_available() else ()
    return {
        "capability_format": "studio-capabilities-v1",
        KIND: {
            "supported": True, "run_enabled": runtime_available(), "validate": "/api/thermal/validate",
            "run": "/api/thermal/run", "input": "json",
            "mesh_preview": False, "mesh_from_result": True,
            "result_formats": [p[0] for p in pairs],
            "field_layouts": [p[1] for p in pairs],
            "fields": ["temperature", "heat_flux"],
            "time_navigation": False, "resource_policy": "candidate-unmeasured",
            "limits": asdict(limits),
        },
        "thermal.transient2d": {"supported": False},
        "em.cavity3d": {"supported": False},
    }


def encode_json(value, limit, *, exact=False):
    """Count complete encoded bytes, including metadata and JSON punctuation. ``exact`` writes a
    tree that holds a document's ``Decimal`` numbers with ``simcase.reader.dumps`` (their digits as
    written); a reply without a document streams through ``json``."""
    if exact:
        try:
            data = reader.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        except ValueError as exc:
            raise ThermalAPIError("invalid_result", "a JSON number is finite") from exc
        if len(data) > limit:
            raise ThermalAPIError("payload_limit_exceeded", "encoded thermal data exceeds its byte limit", 413)
        return data
    out = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for fragment in encoder.iterencode(value):
        chunk = fragment.encode("utf-8")
        if len(out)+len(chunk) > limit:
            raise ThermalAPIError("payload_limit_exceeded", "encoded thermal data exceeds its byte limit", 413)
        out.extend(chunk)
    return bytes(out)


def _parse(data: bytes):
    """The request tree from its raw bytes, read with ``simcase.reader`` (numbers as written, a
    leading UTF-8 byte order mark accepted); its refusals are ``invalid_json`` with their path."""
    raw, found = reader.parse(data)
    for d in found:
        if d.code == "E-KEY-DUPLICATE":
            raise ThermalAPIError("invalid_json", "duplicate JSON key", path=d.path or None)
        if d.code == "E-DOMAIN":
            raise ThermalAPIError("invalid_json", "a JSON number literal is too long", path=d.path or None)
        message = "JSON numbers must be finite" if "finite numbers" in d.message else "malformed finite UTF-8 JSON"
        raise ThermalAPIError("invalid_json", message)
    return raw


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
    if doc.get("openphysics") != "0.3":
        raise ThermalAPIError("invalid_document", FORMAT_03, path="openphysics")
    if ("inward_heat_flux" in p or "convection" in p) and not v2_available():
        raise ThermalAPIError("unsupported_result_format", "matching public steady boundary runtime is required")
    subdivisions(doc, limits)


def subdivisions(doc, limits):
    """The mesh bound of a rectangle document, checked before it is read: ``(nodes, triangles)``."""
    mesh = doc.get("mesh")
    counts = mesh.get("subdivision_count") if isinstance(mesh, dict) else None
    if (not isinstance(counts, list) or len(counts) != 2
            or any(type(n) is not int or n <= 0 for n in counts)):
        raise ThermalAPIError("invalid_document", "expected two positive integer subdivision counts",
                              path="mesh.subdivision_count")
    nx, ny = counts
    if (nx > limits.max_nodes or ny > limits.max_nodes
            or (nx+1)*(ny+1) > limits.max_nodes or 2*nx*ny > limits.max_triangles):
        raise ThermalAPIError("mesh_limit_exceeded", "thermal mesh exceeds configured node/triangle limits", 413,
                              path="mesh.subdivision_count")
    return (nx+1)*(ny+1), 2*nx*ny


@dataclass(frozen=True)
class ThermalInput:
    doc: object
    client_revision: int
    request_seq: int

    def tags(self):
        return {"client_revision": self.client_revision, "request_seq": self.request_seq}


async def read_request(request, limits, *, for_run, preflight=None, runtime_check=None, region=None):
    """Read ASGI chunks with an application cap, not Content-Length trust.

    ``region`` (thermal_regions_api.Route) takes a document that declares region
    geometry; every other document follows the rectangle path unchanged."""
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
            raw = _parse(bytes(data))
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
        exact = raw["doc"]
        try:
            # the doubles of the authored numbers (what the request reader gave before it kept their
            # digits): the route checks and caps read these, the document reads the exact tree
            view = json_value(exact)
        except ValueError as exc:
            raise ThermalAPIError("invalid_json", "JSON numbers must be finite") from exc
        if region is not None and region.applies(view):
            return await region.read(view, tags, for_run=for_run, exact=exact)
        (preflight or _preflight)(view, limits)
        if for_run and not (runtime_check or runtime_available)():
            raise ThermalAPIError("unsupported_public_api", "matching public result IDs are required")
        try:
            doc = Document.from_dict(exact)
        except (DocumentError, ValueError, TypeError, OverflowError) as exc:
            raise ThermalAPIError("invalid_document", str(exc), 400 if for_run else 200) from exc
        return ThermalInput(doc, **tags)
    except ThermalAPIError as exc:
        exc.tags = dict(tags)
        if not for_run and exc.code == "invalid_document":
            exc.status = 200
        raise


def json_value(value):
    """A format 0.3 tree (a document or summary, whose numbers may be ``Decimal``) as plain JSON
    values: each decimal becomes the number its text reads as; a non-finite float is refused."""
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, decimal.Decimal):
        number = json.loads(str(value)) if value.is_finite() else math.nan
        if isinstance(number, float) and not math.isfinite(number):
            raise ValueError("a JSON number is finite")         # also a decimal beyond the doubles (1e999)
        return number
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("a JSON number is finite")
    return value


def document_body(doc):
    """The authored document (its numbers as written) and its coded ``diagnostics`` for a
    validation reply, encoded with ``encode_json(..., exact=True)``."""
    return {"doc": doc.data, "diagnostics": [d.as_dict() for d in doc.diagnostics]}


def validation_payload(spec, limits):
    body = {"ok": True, **document_body(spec.doc), "summary": spec.doc.summary(), **spec.tags()}
    return encode_json(body, limits.payload_bytes, exact=True)


def geometry_block(doc):
    """``(base path, SI block)`` of a format 0.3 document's geometry: the flat block, or the one
    component of a version 1 block (a homogeneous rectangle or a region component)."""
    g = doc.si["geometry"]
    if "version" not in g:
        return "geometry", g
    (name, block), = g["components"].items()
    return f"geometry.components.{name}", block


def length_unit(doc):
    """``(length_unit, metres per unit)`` of a format 0.3 document's geometry."""
    from physmat.units import length_to_pm, pm_to_m
    unit = geometry_block(doc)[1]["length_unit"]
    return unit, pm_to_m(length_to_pm(1, unit).picometres)


def domain_input(summary, doc):
    """The ``resolved_inputs`` entry of the domain's xmin, which names the geometry's length_unit."""
    return summary.get("resolved_inputs", {}).get(geometry_block(doc)[0] + ".domain.xmin", {})


def _unit_03(key):
    from physmat.units import quantity
    return quantity(key).unit


def _location_03(key):
    if key == "triangles":
        return "triangle_connectivity"
    if key.startswith("prescribed_"):
        return "prescribed_nodes"
    if key == "heat_flux":
        return "triangle_centroids"
    return "nodes"


def _require(condition, message):
    if not condition:
        raise ThermalAPIError("invalid_result", message, 500)


def capture_result(result, identity, limits):
    """Read each selected public array once; encode only captured owned copies."""
    _require(isinstance(result, ThermalRunResult), "expected public ThermalRunResult")
    _require(result.doc.si is not None, "expected a format 0.3 rectangle result")
    summary = json_value(result.summary())
    _require(isinstance(summary, dict), "thermal summary must be an object")
    encode_json(summary, limits.metadata_bytes)
    public_format = result.result_format
    public_layout = result.field_layout
    pair = (public_format, public_layout)
    _require(pair in (V1, V2) and summary.get("physics_type") == KIND,
             "unsupported public thermal result/layout pair")
    _require(pair == (summary.get("result_format"), summary.get("field_layout")),
             "public and summary result/layout pair disagree")
    keys = BASE_FIELDS+BOUNDARY_FIELDS if pair == V2 else BASE_FIELDS
    arrays = {}
    for key in keys:
        value = getattr(result, PROPERTIES[key])  # one property read
        _require(isinstance(value, np.ndarray), key+": expected a numeric ndarray")
        _require(value.dtype.kind in "iuf", key+": expected real nonboolean dtype")
        # Refuse malformed oversized producers before allocating another owned copy.
        if key == "node_coordinates":
            _require(value.ndim == 2 and value.shape[1] == 2
                     and 3 <= len(value) <= limits.max_nodes, "invalid or oversized node_coordinates")
            node_count = len(value)
        elif key == "triangles":
            _require(value.dtype.kind in "iu" and value.ndim == 2 and value.shape[1] == 3
                     and 1 <= len(value) <= limits.max_triangles, "invalid or oversized triangles")
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
    nodes, triangles, fixed = arrays["node_coordinates"], arrays["triangles"], arrays["prescribed_node_ids"]
    _require(nodes.ndim == 2 and nodes.shape[1] == 2 and len(nodes) >= 3, "invalid node_coordinates shape")
    _require(triangles.ndim == 2 and triangles.shape[1] == 3 and len(triangles) > 0
             and triangles.dtype.kind in "iu", "invalid triangle connectivity")
    n, m = len(nodes), len(triangles)
    _require(n <= limits.max_nodes and m <= limits.max_triangles, "result exceeds configured mesh limits")
    _require(not np.any(triangles < 0) and not np.any(triangles >= n), "triangle index outside nodes")
    _require(fixed.ndim == 1 and fixed.dtype.kind in "iu"
             and (pair == V2 or len(fixed) > 0), "invalid prescribed node IDs")
    _require(not np.any(fixed < 0) and not np.any(fixed >= n), "prescribed node index outside nodes")
    _require(not np.any(np.diff(fixed.astype(np.int64)) <= 0), "prescribed node IDs must be sorted unique")
    shapes = {"node_coordinates": (n, 2), "triangles": (m, 3), "temperature": (n,),
              "heat_flux": (m, 2), "prescribed_node_ids": (len(fixed),),
              "prescribed_temperature": (len(fixed),)}
    for key in keys:
        if key not in shapes:
            shapes[key] = (n,)
        _require(arrays[key].shape == shapes[key], key+": invalid shape")
    _require(not np.any(arrays["prescribed_temperature"] <= 0), "prescribed temperature must be above 0 K")
    with np.errstate(over="ignore", invalid="ignore"):
        v = nodes[triangles][:, 1:]-nodes[triangles][:, :1]
        det = v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0]
    _require(np.isfinite(det).all() and np.all(det > 0), "triangles must be finite nondegenerate CCW")
    unit_keys = [key for key in keys if key not in STRUCTURAL]
    for meta, expected in (("field_units", unit_keys), ("field_locations", keys), ("field_shapes", keys)):
        _require(isinstance(summary.get(meta), dict) and set(summary[meta]) == set(expected),
                 "invalid "+meta+" field set")
    for key in keys:
        if key not in STRUCTURAL:
            _require(summary["field_units"][key] == _unit_03(key), key+": wrong unit")
        _require(summary["field_locations"][key] == _location_03(key), key+": wrong location")
        shape = summary["field_shapes"][key]
        _require(isinstance(shape, list) and all(type(x) is int for x in shape)
                 and shape == list(shapes[key]), key+": wrong metadata shape")
    unit, length_in_m = length_unit(result.doc)
    _require(domain_input(summary, result.doc).get("length_unit") == unit,
             "document/summary length_unit mismatch")
    _require(not isinstance(length_in_m, bool) and math.isfinite(length_in_m) and length_in_m > 0,
             "invalid display length scale")
    payload = {
        "payload_format": PAYLOAD, **identity,
        "result_format": pair[0], "field_layout": pair[1],
        "length_unit": unit, "display_length_in_m": float(length_in_m),
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
    """Bounded thermal cache; evict oldest released terminal, never active/optical."""

    def __init__(self, limits=None, *, clock=None):
        self.limits = limits or ThermalLimits()
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._records = {}
        self._active = 0
        self._reserved_bytes = 0
        self._pending = 0
        self._retired = {}
        self._snapshots = {}
        self._read_workspace = 0
        self.ingress = AdmissionGate("ingress_capacity_exceeded")
        self.read_encoder = AdmissionGate("read_capacity_exceeded")

    def _expire(self):
        now = self._clock()
        for job, rec in list(self._records.items()):
            if (rec["lease"].released and rec["terminal_at"] is not None
                    and now-rec["terminal_at"] >= self.limits.ttl_seconds):
                self._discard(job)

    @staticmethod
    def _record_bytes(rec):
        return len(rec["status_bytes"])+len(rec["result"] or b"")+rec.get("raw_bytes", 0)

    def _discard(self, job):
        rec = self._records.pop(job)
        if rec.get("pins", 0):
            self._retired[id(rec)] = rec

    @staticmethod
    def _allocations(rec):
        """Payload identities, not references; full-record pins retain all."""
        values = {}
        for key in ("status_bytes", "result"):
            value = rec.get(key)
            if value is not None:
                values[id(value)] = len(value)
        for value in (rec.get("raw") or {}).values():
            values[id(value)] = value.nbytes
        return values

    def _retained_bytes(self):
        covered, retained = {}, {}
        for rec in self._records.values():
            (retained if rec["lease"].released else covered).update(self._allocations(rec))
        for rec in self._retired.values():
            retained.update(self._allocations(rec))
        for allocation, snapshot in self._snapshots.items():
            if allocation not in covered:
                retained[allocation] = len(snapshot["payload"])
        return sum(size for allocation, size in retained.items() if allocation not in covered)+self._read_workspace

    def begin_read(self, budget):
        permit = self.read_encoder.acquire()
        try:
            with self._lock:
                self._make_room(budget, 0)
                self._read_workspace += budget
            return ReadAllocation(self, permit, budget)
        except BaseException:
            permit.release()
            raise

    def pin(self, job, *, result=False, result_id=None):
        """Pin one immutable terminal record until transport/reader finally."""
        with self._lock:
            self._expire()
            rec = self._records.get(job)
            if rec is None:
                raise ThermalAPIError("unknown_job", "unknown or expired thermal job", 404)
            if result_id is not None and result_id != rec["identity"]["result_id"]:
                raise ThermalAPIError("stale_result", "result identity does not match", 409,
                                      tags=dict(rec["identity"]))
            if result and (rec["status"] != "done" or rec["result"] is None):
                raise ThermalAPIError("result_not_ready", "thermal result is not available", 409,
                                      tags=dict(rec["identity"]))
            # Running status is a small snapshot, not a reference to mutable rec.
            if not rec["lease"].released:
                if not result:
                    payload = rec["status_bytes"]
                    allocation = id(payload)
                    snapshot = self._snapshots.setdefault(allocation, {"payload": payload, "refs": 0})
                    snapshot["refs"] += 1
                    return RecordPin(self, None, payload, allocation)
            rec["pins"] = rec.get("pins", 0)+1
            return RecordPin(self, rec, rec["result"] if result else rec["status_bytes"])

    def _unpin_snapshot(self, allocation):
        with self._lock:
            snapshot = self._snapshots[allocation]
            snapshot["refs"] -= 1
            if snapshot["refs"] == 0:
                del self._snapshots[allocation]

    def _unpin(self, rec):
        with self._lock:
            rec["pins"] -= 1
            if rec["pins"] == 0:
                self._retired.pop(id(rec), None)

    def _make_room(self, byte_count, slots, *, released_reservation=0):
        # Caller holds the lock. TTL is a maximum, not a retention guarantee.
        while (len(self._records)+self._pending+slots > self.limits.terminal_jobs
               or self._retained_bytes()+self._reserved_bytes-released_reservation+byte_count
               > self.limits.terminal_bytes):
            candidates = [(key, rec) for key, rec in self._records.items()
                          if rec["lease"].released and rec["status"] in ("done", "error")]
            if not candidates:
                raise ThermalAPIError("capacity_exceeded", "thermal job capacity unavailable", 429)
            # dict insertion order breaks equal monotonic-clock ties deterministically.
            oldest, _ = min(candidates, key=lambda item: item[1]["terminal_at"])
            self._discard(oldest)

    def reserve(self, reservation=None):
        with self._lock:
            self._expire()
            budget = (self.limits.payload_bytes+self.limits.status_bytes
                      if reservation is None else reservation)
            if type(budget) is not int or budget <= 0 or budget > self.limits.terminal_bytes:
                raise ThermalAPIError("capacity_exceeded", "invalid thermal reservation", 429)
            if self._active >= self.limits.active_jobs:
                raise ThermalAPIError("capacity_exceeded", "thermal job capacity unavailable", 429)
            self._make_room(budget, 1)
            lease = ThermalLease(budget)
            self._active += 1
            self._pending += 1
            self._reserved_bytes += budget
            return lease

    def _status(self, identity, status, log, error, has_result):
        encode_json(log, self.limits.log_bytes)
        if error is not None:
            encode_json(error, self.limits.error_bytes)
        return encode_json({**identity, "status": status, "log": log,
                            "error": error, "has_result": has_result}, self.limits.status_bytes)

    def attach(self, lease, job, result_id, spec):
        identity = {"kind": getattr(spec, "kind", KIND), "job": job, "result_id": result_id, **spec.tags()}
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

    def _publish(self, lease, status, result, log, error, *, raw=None):
        with self._lock:
            rec = self._records.get(lease.job)
            if lease.released or rec is None or rec["status"] != "running":
                return False
            encoded = self._status(rec["identity"], status, log, error, result is not None)
            raw_bytes = sum(a.nbytes for a in raw.values()) if raw is not None else 0
            if len(encoded)+len(result or b"")+raw_bytes > lease.reservation:
                raise ThermalAPIError("capacity_exceeded", "result exceeds reserved bytes", 429)
            old_status = rec["status_bytes"]
            orphan = len(old_status) if id(old_status) in self._snapshots else 0
            self._make_room(len(encoded)+len(result or b"")+raw_bytes+orphan, 0,
                            released_reservation=lease.reservation)
            rec.update(status=status, status_bytes=encoded, result=result,
                       raw=raw, raw_bytes=raw_bytes, terminal_at=self._clock())
            return True

    def complete(self, lease, payload, log):
        if type(payload) is not bytes or len(payload) > self.limits.payload_bytes:
            raise ThermalAPIError("payload_limit_exceeded", "invalid or oversized encoded result", 413)
        return self._publish(lease, "done", payload,
                             bounded_log(log, self.limits.log_bytes), None)

    def complete_transient(self, lease, payload, arrays, log, display_scale, pair=None):
        if type(payload) is not bytes:
            raise ValueError("encoded transient manifest required")
        with self._lock:
            published = self._publish(lease, "done", payload, bounded_log(log, self.limits.log_bytes),
                                      None, raw=arrays)
            if published:
                self._records[lease.job]["display_length_in_m"] = display_scale
                if pair is not None:   # region records; rectangle records keep their shape
                    self._records[lease.job]["pair"] = tuple(pair)
            return published

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
                    orphan = len(rec["status_bytes"]) if id(rec["status_bytes"]) in self._snapshots else 0
                    self._make_room(max(0, len(encoded)-len(rec["status_bytes"])+orphan), 0)
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


class AdmissionGate:
    """Nonblocking single permit, with token identity and idempotent release."""

    def __init__(self, code):
        self._lock = threading.Lock()
        self._token = None
        self.code = code

    def acquire(self):
        with self._lock:
            if self._token is not None:
                raise ThermalAPIError(self.code, "thermal request capacity unavailable", 429)
            token = Permit(self)
            self._token = token
            return token

    def _release(self, token):
        with self._lock:
            if self._token is token:
                self._token = None


class Permit:
    def __init__(self, gate):
        self.gate = gate
        self.released = False

    def release(self):
        if not self.released:
            self.released = True
            self.gate._release(self)


class RecordPin:
    def __init__(self, jobs, record, payload, allocation=None):
        self.jobs, self.record, self.payload = jobs, record, payload
        self.allocation = allocation
        self.released = False
        self._release_lock = threading.Lock()

    def release(self):
        with self._release_lock:
            if self.released:
                return
            self.released = True
            self.payload = None
            record, self.record = self.record, None
            jobs, self.jobs = self.jobs, None
            if jobs is not None:
                if record is None:
                    jobs._unpin_snapshot(self.allocation)
                else:
                    jobs._unpin(record)
            record = None


class ReadAllocation:
    """Reserved encoder workspace transfers to immutable output until send ends."""

    def __init__(self, jobs, permit, budget):
        self.jobs, self.permit, self.budget = jobs, permit, budget
        self.allocation = None
        self.payload = None
        self.released = False
        self._lock = threading.Lock()

    def publish(self, payload):
        if type(payload) is not bytes or len(payload) > self.budget:
            raise ThermalAPIError("payload_limit_exceeded", "encoded view exceeds reservation", 413)
        with self._lock, self.jobs._lock:
            if self.released or self.allocation is not None:
                raise RuntimeError("read allocation already completed")
            self.jobs._read_workspace -= self.budget
            self.allocation = id(payload)
            self.payload = payload
            entry = self.jobs._snapshots.setdefault(self.allocation, {"payload": payload, "refs": 0})
            entry["refs"] += 1

    def release(self):
        with self._lock:
            if self.released:
                return
            self.released = True
            self.payload = None
            jobs, self.jobs = self.jobs, None
            permit, self.permit = self.permit, None
            with jobs._lock:
                if self.allocation is None:
                    jobs._read_workspace -= self.budget
                else:
                    jobs._unpin_snapshot(self.allocation)
            permit.release()
