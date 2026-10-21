# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Unshipped stored-reference reader. Never imports or executes a reference tool."""

from dataclasses import dataclass
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType

import numpy as np

SCHEMA = "openphysics.reference-values/1"
RECORD_LIMIT = 1024 * 1024
PAYLOAD_LIMIT = 512 * 1024
REQUIRED = {
    "schema", "case", "physics", "comparison", "role", "references", "generator",
    "generated_utc", "environment", "cost", "inputs", "matched", "not_matched",
    "reference_self_check", "failed_or_discarded", "not_run", "values_sha256",
    "content_sha256", "consumers", "provenance_status", "not_recorded", "regeneration",
}
REFERENCE_FIELDS = {
    "tool", "version", "build", "modified", "license", "source", "install", "settings",
    "discretization", "arrays", "execution", "independence",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _fields(value, fields, where):
    _require(isinstance(value, dict), f"{where}: expected object")
    _require(fields <= value.keys(), f"{where}: missing {fields - value.keys()}")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=False).encode("utf-8")


def values_digest(arrays):
    """Shared v1 digest: name/NUL/dtype/NUL/shape/NUL/C-order bytes."""
    digest = hashlib.sha256()
    for name, array in sorted(arrays.items()):
        if name == "metadata":
            continue
        array = np.asarray(array)
        _require(array.dtype.kind in "biufc" and np.all(np.isfinite(array)),
                 f"{name}: finite numeric arrays required")
        for part in (name, array.dtype.str, repr(array.shape)):
            digest.update(part.encode("utf-8") + b"\0")
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def content_digest(inputs, values_sha256):
    return hashlib.sha256(canonical_json(
        {"inputs": inputs, "values_sha256": values_sha256})).hexdigest()


def file_digest(path, *, text=False):
    data = Path(path).read_bytes()
    if text:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _json(path, limit):
    _require(path.stat().st_size <= limit, f"{path.name}: size limit exceeded")
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_require(False, f"non-finite JSON: {x}")))


def _walk(value, path=""):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            _require(key not in {"gate", "tolerance"}, f"forbidden key: {key}")
            yield from _walk(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _strings(record):
    items = list(_walk(record))
    for path, value in list(items):
        if isinstance(value, dict):
            items.extend((path, key) for key in value)
    for path, value in items:
        if isinstance(value, (float, int)):
            _require(np.isfinite(value), f"{path}: non-finite number")
        if not isinstance(value, str):
            continue
        _require(not re.search(r"(?:^|[\s='\"])(?:/|~[/\\]|[A-Za-z]:[/\\]|\\\\)", value),
                 f"{path}: absolute or home path")
        _require(not re.search(r"(?:decisions|work|notes)[/\\]|claude\.ai/code/session_|"
                               r"(?:openphysics|wavebit)-lab", value),
                 f"{path}: private provenance string")


def _relative(base, name):
    _require(isinstance(name, str) and bool(name), "expected relative file name")
    _require(not Path(name).is_absolute() and ".." not in Path(name).parts and "\\" not in name,
             "file must be a portable relative path")
    path = (base / name).resolve()
    _require(path.is_relative_to(base.resolve()), "file escapes its directory")
    return path


def _array(spec):
    _fields(spec, {"name", "unit", "dtype", "shape"}, "array")
    _require(isinstance(spec["name"], str) and spec["name"] != "metadata", "invalid array name")
    _require(isinstance(spec["unit"], str), "array unit must be a string")
    dtype = np.dtype(spec["dtype"])
    _require(dtype.kind in "biufc", "only numeric dtypes are supported")
    shape = spec["shape"]
    _require(isinstance(shape, list) and all(type(n) is int and n >= 0 for n in shape),
             "invalid array shape")
    # Check before allocating; tiny metadata cannot request an enormous array.
    import math
    _require(math.prod(shape) * dtype.itemsize <= PAYLOAD_LIMIT, "array size limit exceeded")
    if dtype.kind == "c":
        _fields(spec, {"real", "imag"}, "complex array")
        real, imag = np.asarray(spec["real"]), np.asarray(spec["imag"])
        _require(real.shape == imag.shape, "complex component shapes differ")
        data = real + 1j * imag
    else:
        _fields(spec, {"data"}, "array")
        data = spec["data"]
    array = np.asarray(data, dtype=dtype)
    _require(array.size == math.prod(shape), "array data and shape differ")
    array = array.reshape(shape)
    _require(np.all(np.isfinite(array)), "non-finite array")
    return array


def _arrays(record, directory):
    _require(("values" in record) != ("payload" in record), "use values or payload, exclusively")
    if "values" in record:
        specs = record["values"]
        _require(isinstance(specs, list) and specs, "values must be a nonempty list")
        arrays = {}
        for spec in specs:
            array = _array(spec)
            _require(spec["name"] not in arrays, "duplicate array name")
            arrays[spec["name"]] = array
        return arrays
    payload = record["payload"]
    _fields(payload, {"file", "format", "file_sha256", "arrays"}, "payload")
    path = _relative(directory, payload["file"])
    _require(path.stat().st_size <= PAYLOAD_LIMIT, "payload size limit exceeded")
    _require(payload["format"] in {"npz", "json"}, "unknown payload format")
    _require(file_digest(path, text=payload["format"] == "json") == payload["file_sha256"],
             "payload file hash mismatch")
    if payload["format"] == "json":
        return _arrays({"values": _json(path, PAYLOAD_LIMIT)}, directory)
    # Bound expanded size too: do not let a compressed archive become a zip bomb.
    import zipfile
    with zipfile.ZipFile(path) as archive:
        _require(sum(i.file_size for i in archive.infolist()) <= PAYLOAD_LIMIT,
                 "expanded payload size limit exceeded")
    with np.load(path, allow_pickle=False) as archive:
        _require(len(archive.files) == len(set(archive.files)), "duplicate payload array")
        return {name: archive[name] for name in archive.files}


@dataclass(frozen=True)
class StoredReference:
    """Validated metadata and read-only arrays; inputs are available for case construction."""

    path: Path
    record: dict
    arrays: object

    @property
    def inputs(self):
        return self.record["inputs"]


def load_reference(path):
    """Validate a v1 record and its payload without repository tools or solver installs."""
    path = Path(path)
    record = _json(path, RECORD_LIMIT)
    _fields(record, REQUIRED, "record")
    _require(record["schema"] == SCHEMA, "unknown reference schema")
    _strings(record)
    _require(record["comparison"] in {"same-discretization", "different-discretization",
                                       "structure-oracle"}, "invalid comparison")
    _require(record["provenance_status"] in {"complete", "reconstructed"}, "invalid provenance status")
    for key in ("case", "physics", "role", "generated_utc"):
        _require(isinstance(record[key], str) and bool(record[key]), f"{key} must be nonempty")
    _fields(record["generator"], {"path", "sha256", "command", "product_commit", "clean"}, "generator")
    _fields(record["environment"], {"python", "numpy", "os", "cpu", "dtype", "backend/device"}, "environment")
    _fields(record["cost"], {"compile_s", "compute_s", "wall_time_s", "peak_rss_mb", "threads", "not_measured"}, "cost")
    for key in ("matched", "not_matched", "reference_self_check", "failed_or_discarded", "not_run", "consumers", "regeneration"):
        _require(isinstance(record[key], list), f"{key} must be a list")
    _require(record["consumers"] and all(isinstance(p, str) and p for p in record["consumers"]),
             "at least one consumer path is required")
    _require(isinstance(record["inputs"], dict), "inputs must be an object")
    for key in ("values_sha256", "content_sha256"):
        _require(isinstance(record[key], str) and re.fullmatch(r"[0-9a-f]{64}", record[key]),
                 f"invalid {key}")
    refs = record["references"]
    _require(isinstance(refs, list) and refs, "references must be nonempty")
    for ref in refs:
        _fields(ref, REFERENCE_FIELDS, "reference")
        for key in ("tool", "version", "license", "source"):
            _require(isinstance(ref[key], str) and bool(ref[key]), f"reference.{key} required")
        _require(not re.search(r"[<>=*~]", ref["version"]), "exact reference version required")
        _fields(ref["modified"], {"value", "description"}, "modified")
        _require(type(ref["modified"]["value"]) is bool, "modified.value must be boolean")
        if "AGPL" in ref["license"] or "Affero" in ref["license"]:
            _require(ref["modified"]["value"] is False, "AGPL reference must be unmodified")
        _fields(ref["install"], {"kind", "command", "lock"}, "install")
        _fields(ref["independence"], {"product_loaded", "inputs_from_product"}, "independence")
        _require(ref["execution"] in {"separate-process", "in-process", "unknown"}, "invalid execution")
        _require(isinstance(ref["arrays"], list) and ref["arrays"] and
                 all(isinstance(x, str) for x in ref["arrays"]), "array globs required")
    nulls = {key for key, value in _walk(record) if value is None}
    missing = record["not_recorded"]
    _require(isinstance(missing, dict) and set(missing) == nulls and
             all(isinstance(v, str) and v.strip() for v in missing.values()),
             "not_recorded must explain every null field and its consulted source")
    previous = None
    for entry in record["regeneration"]:
        _fields(entry, {"date", "mode", "reason", "previous_content_sha256", "tool_version", "review", "approval", "content_sha256"}, "regeneration")
        _require(entry["mode"] in {"restamp", "rebaseline"} and bool(entry["reason"].strip()),
                 "regeneration requires a mode and reason")
        for key in ("previous_content_sha256", "content_sha256"):
            _require(isinstance(entry[key], str) and re.fullmatch(r"[0-9a-f]{64}", entry[key]),
                     "invalid regeneration hash")
        for key in ("date", "tool_version", "review", "approval"):
            _require(isinstance(entry[key], str) and entry[key].strip(), "incomplete regeneration provenance")
        if previous is not None:
            _require(entry["previous_content_sha256"] == previous, "broken regeneration chain")
        if entry["mode"] == "restamp":
            _require(entry["previous_content_sha256"] == entry["content_sha256"], "restamp changed values/inputs")
        previous = entry["content_sha256"]
    if previous is not None:
        _require(previous == record["content_sha256"], "regeneration chain does not end at current content")
    arrays = _arrays(record, path.parent)
    _require(arrays and sum(a.nbytes for a in arrays.values()) <= PAYLOAD_LIMIT, "array size limit exceeded")
    for name in arrays:
        _require(name != "metadata", "metadata is not a value array")
        _require(sum(any(fnmatchcase(name, glob) for glob in ref["arrays"]) for ref in refs) == 1,
                 f"{name}: must be covered by exactly one reference")
    if "payload" in record:
        _require(set(record["payload"]["arrays"]) == set(arrays), "payload arrays differ")
    _require(values_digest(arrays) == record["values_sha256"], "values hash mismatch")
    _require(content_digest(record["inputs"], record["values_sha256"]) == record["content_sha256"],
             "content hash mismatch")
    for array in arrays.values():
        array.flags.writeable = False
    return StoredReference(path, record, MappingProxyType(arrays))
