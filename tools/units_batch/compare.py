# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Compare two recordings of ``record.py`` bit for bit, through a closed list of transforms.

    python tools/units_batch/compare.py --old <recording> --new <recording> --identity
    python tools/units_batch/compare.py --old <recording> --new <recording> --plan plan.json

Every document recorded on both sides is compared:

- the solver and mesher calls, entry by entry: arguments, callback samples and digests, results.
  Scalars compare by ``float.hex``; a Python type difference (``int`` against ``float``) is listed,
  not failed (hazard H8);
- every saved ``fields.npz`` array: the same dtype and shape, and ``tobytes()`` equal to the
  transform of the old array;
- every ``summary.json`` and ``metadata_json`` leaf, under ``float.hex``; wall times
  (``timings_s``, ``timing``) and ``software_versions`` are excluded, as are ``log.txt`` and
  ``results.png``;
- the VTU and PVD exports, array by array, and the failure evidence of a failed solve;
- the preconditions: no picometre rounding diagnostic, no binding the recorder missed.

``--identity`` compares every document with the identity map: P2-3 and the self-test of the
harness. ``--plan`` names, per document id, ``"identity"`` or ``"layout"``; a layout document uses
``maps/<old field layout>.json``, whose rules are closed: arrays map by ``=``, ``neg``, ``conj``,
``L1``, ``L2``, ``L1*conj``, ``L2*conj`` (and ``kernel-L1`` for nanometre and metre em fixtures),
summary paths by ``=``, ``neg``, ``conj``, ``L1``, ``L1*conj``, ``rad``, ``qdeg`` or ``removed``
with a check, and only the pre-registered exceptions compare within 4 ulp. Exit status 0 when
every document is equal, 1 otherwise. ``--report`` writes the per-document, per-array SHA-256
table as JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

MAP_FORMAT = "openphysics-units-batch-map-v1"
#: keys excluded wherever they appear in a summary or metadata tree
EXCLUDED_KEYS = frozenset({"timings_s", "timing", "software_versions"})
#: keys every new summary may add (P2-1 "added" list)
ADDED_ALWAYS = ("diagnostics", "defaults_applied", "resolved_inputs", "extent", "field_components",
                "time_convention", "propagation")
EXCLUDED_FILES = frozenset({"log.txt", "results.png"})
ARRAY_TRANSFORMS = ("=", "neg", "conj", "L1", "L2", "L1*conj", "L2*conj", "kernel-L1")
SUMMARY_TRANSFORMS = ("=", "neg", "conj", "L1", "L1*conj", "rad", "qdeg", "removed")
REMOVED_CHECKS = ("unit-metadata", "time-tail", "equals")
#: the only comparisons that are not bitwise (P2-1); each is within 4 ulp
EXCEPTIONS = {"propagation_loss": 100.0, "bend_loss": 1.0, "group_index_length_frame": 1.0}
ULP_LIMIT = 4
ALIASES = {"L1∘conj": "L1*conj", "L2∘conj": "L2*conj"}
MAX_FAILURES = 40


# -- small helpers -----------------------------------------------------------------------------

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Result:
    """The findings for one document."""

    def __init__(self, doc_id: str, mode: str):
        self.id, self.mode = doc_id, mode
        self.failures: list[str] = []
        self.type_differences: list[str] = []
        self.counts = {"calls": 0, "arrays": 0, "summary_leaves": 0, "vtu_arrays": 0, "exceptions": 0}
        self.arrays: list[list] = []

    def fail(self, message: str):
        if len(self.failures) < MAX_FAILURES:
            self.failures.append(message)
        elif len(self.failures) == MAX_FAILURES:
            self.failures.append("... more failures not listed")

    @property
    def equal(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict:
        return {"id": self.id, "mode": self.mode, "status": "equal" if self.equal else "different",
                "counts": self.counts, "failures": self.failures, "type_differences": self.type_differences,
                "arrays": self.arrays}


# -- canonical forms from the recorder ---------------------------------------------------------

def _is_number(form) -> bool:
    return isinstance(form, list) and len(form) == 3 and form[0] == "num"


def diff_forms(a, b, path: str, result: Result) -> str | None:
    """The first difference between two canonical forms; numeric types are listed, not failed."""
    if a == b:
        return None
    if _is_number(a) and _is_number(b):
        if a[2] != b[2]:
            return f"{path}: {a[2]} ({a[1]}) != {b[2]} ({b[1]})"
        result.type_differences.append(f"{path}: {a[1]} -> {b[1]}")
        return None
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            found = diff_forms(x, y, f"{path}[{i}]", result)
            if found:
                return found
        return None
    if isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        for k in a:
            found = diff_forms(a[k], b[k], f"{path}.{k}", result)
            if found:
                return found
        return None
    text = lambda v: json.dumps(v)[:160]                       # noqa: E731
    return f"{path}: {text(a)} != {text(b)}"


# -- JSON trees (summary.json, metadata_json, failure evidence) ---------------------------------

def leaves(tree, path=()):
    """{path tuple: leaf} of a JSON tree, without the excluded keys; list indices are ints."""
    out = {}
    if isinstance(tree, dict):
        if not tree and path:
            out[path] = {}
        for k, v in tree.items():
            if k in EXCLUDED_KEYS:
                continue
            out.update(leaves(v, path + (k,)))
    elif isinstance(tree, list):
        if not tree:
            out[path] = []
        for i, v in enumerate(tree):
            out.update(leaves(v, path + (i,)))
    else:
        out[path] = tree
    return out


def show(path) -> str:
    text = ""
    for p in path:
        if isinstance(p, int):
            text += f"[{p}]"
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p):
            text += f".{p}" if text else p
        else:
            text += f'["{p}"]'
    return text or "<root>"


def _hex(value) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float.hex(float(value))


def same_leaf(a, b, where: str, result: Result) -> bool:
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, (str, dict, list)):
        if a != b or type(a) is not type(b):
            result.fail(f"{where}: {json.dumps(a)[:120]} != {json.dumps(b)[:120]}")
            return False
        return True
    ha, hb = _hex(a), _hex(b)
    if ha is None or hb is None or ha != hb:
        result.fail(f"{where}: {a!r} != {b!r}")
        return False
    if type(a) is not type(b):
        result.type_differences.append(f"{where}: {type(a).__name__} -> {type(b).__name__}")
    return True


def compare_trees_identity(old, new, label: str, result: Result):
    a, b = leaves(old), leaves(new)
    for path in sorted(set(a) | set(b), key=lambda p: [str(x) for x in p]):
        if path not in a:
            result.fail(f"{label} {show(path)}: added")
        elif path not in b:
            result.fail(f"{label} {show(path)}: removed")
        else:
            result.counts["summary_leaves"] += 1
            same_leaf(a[path], b[path], f"{label} {show(path)}", result)


# -- path patterns of the maps ---------------------------------------------------------------

_SEGMENT = re.compile(r'\["([^"]*)"\]|\[\]|\*\*|\*|[^.\[\]]+')


def parse_pattern(text: str) -> list:
    """Dotted segments; ``*`` one key, ``[]`` one list index, ``**`` any rest, ``["a.b"]`` literal."""
    out, pos = [], 0
    while pos < len(text):
        if text[pos] == ".":
            pos += 1
            continue
        m = _SEGMENT.match(text, pos)
        if not m:
            raise ValueError(f"bad pattern {text!r} at {pos}")
        token = m.group(0)
        out.append(("lit", m.group(1)) if m.group(1) is not None else
                   ("idx", None) if token == "[]" else ("rest", None) if token == "**" else
                   ("key", None) if token == "*" else ("lit", token))
        pos = m.end()
    return out


def match(pattern: list, path: tuple):
    """The captured segments when ``path`` matches, else None."""
    captures = []
    for i, (kind, value) in enumerate(pattern):
        if kind == "rest":
            captures.append(path[i:])
            return captures
        if i >= len(path):
            return None
        part = path[i]
        if kind == "lit" and part != value:
            return None
        if kind == "key":
            if isinstance(part, int):
                return None
            captures.append(part)
        if kind == "idx":
            if not isinstance(part, int):
                return None
            captures.append(part)
    return captures if len(path) == len(pattern) else None


def fill(pattern: list, captures: list) -> tuple:
    out, it = [], iter(captures)
    for kind, value in pattern:
        if kind == "lit":
            out.append(value)
        elif kind == "rest":
            out.extend(next(it))
        else:
            out.append(next(it))
    return tuple(out)


# -- transforms ------------------------------------------------------------------------------

def array_transform(name: str, old, kernel_nodes=None):
    import numpy as np
    if name == "=":
        return old
    if name == "neg":
        return np.subtract(np.asarray(0.0, dtype=old.dtype), old)
    if name == "conj":
        return np.conj(old)
    if name == "L1":
        return old * 1e-6
    if name == "L2":
        return old * 1e-12
    if name == "L1*conj":
        return np.conj(old) * 1e-6
    if name == "L2*conj":
        return np.conj(old) * 1e-12
    if name == "kernel-L1":
        if kernel_nodes is None:
            raise ValueError("kernel-L1 needs the old recording's mesher output")
        return kernel_nodes * 1e-6
    raise ValueError(f"array transform {name!r} is not in the closed list {ARRAY_TRANSFORMS}")


_qdeg_reader = None


def _qdeg(value: float) -> float:
    global _qdeg_reader
    if _qdeg_reader is None:
        source = Path(__file__).resolve().parents[2] / "packages" / "physmat" / "src"
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))
        from physmat.units import q
        _qdeg_reader = q
    return _qdeg_reader(f"{value!r} deg", "minimum_angle")


def scalar_transform(name: str, value):
    """A summary leaf under a summary transform (``conj`` of a real leaf is the leaf)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        if name in ("=", "conj"):
            return value
        raise ValueError(f"transform {name} of a non-numeric leaf {value!r}")
    if name in ("=", "conj"):
        return value
    if name == "neg":
        return 0.0 - value
    if name in ("L1", "L1*conj"):
        return value * 1e-6
    if name == "rad":
        return math.radians(value)
    if name == "qdeg":
        return _qdeg(value)
    raise ValueError(f"summary transform {name!r} is not in the closed list {SUMMARY_TRANSFORMS}")


def _ordered(x: float) -> int:
    bits = struct.unpack("<q", struct.pack("<d", x))[0]
    return bits if bits >= 0 else -(bits & 0x7FFFFFFFFFFFFFFF)


def ulp_distance(a: float, b: float) -> float:
    if math.isnan(a) or math.isnan(b):
        return math.inf
    return abs(_ordered(a) - _ordered(b))


# -- the map of one layout -------------------------------------------------------------------

class LayoutMap:
    def __init__(self, data: dict, source: str):
        if data.get("format") != MAP_FORMAT:
            raise ValueError(f"{source}: format must be {MAP_FORMAT!r}")
        self.source = source
        self.old_layout, self.new_layout = data["old_layout"], data.get("new_layout")
        self.arrays = {}
        for rule in data.get("arrays", []):
            f = ALIASES.get(rule.get("f", "="), rule.get("f", "="))
            if f not in ARRAY_TRANSFORMS:
                raise ValueError(f"{source}: array transform {f!r} is not in the closed list")
            self.arrays[rule["old"]] = (rule["new"], f)
        self.arrays_removed = {r["old"]: r for r in data.get("arrays_removed", [])}
        self.arrays_added = [re.compile(p) for p in data.get("arrays_added", [])]
        self.summary = []
        for rule in data.get("summary", []):
            f = ALIASES.get(rule.get("f", "="), rule.get("f", "="))
            if f not in SUMMARY_TRANSFORMS:
                raise ValueError(f"{source}: summary transform {f!r} is not in the closed list")
            if f == "removed" and rule.get("check", "unit-metadata") not in REMOVED_CHECKS:
                raise ValueError(f"{source}: removed check {rule.get('check')!r} is not in the closed list")
            self.summary.append((parse_pattern(rule["old"]), None if f == "removed" else parse_pattern(rule["new"]),
                                 f, rule))
        self.summary_added = [parse_pattern(p) for p in (*ADDED_ALWAYS, *data.get("summary_added", []))]
        self.identifiers = [parse_pattern(p) for p in data.get("identifiers", [])]
        self.vtu = {r["old"]: (r["new"], ALIASES.get(r.get("f", "="), r.get("f", "="))) for r in data.get("vtu", [])}
        self.vtu_added = [re.compile(p) for p in data.get("vtu_added", [])]
        self.exceptions = {}
        for rule in data.get("exceptions", []):
            if rule["kind"] not in EXCEPTIONS:
                raise ValueError(f"{source}: exception {rule['kind']!r} is not pre-registered")
            self.exceptions[(rule.get("where", "summary"), rule["new"])] = rule

    @classmethod
    def load(cls, maps: Path, layout: str) -> "LayoutMap":
        path = maps / f"{layout}.json"
        if not path.is_file():
            raise FileNotFoundError(f"no map for layout {layout!r} ({path.name}); maps are closed per layout")
        return cls(_load_json(path), path.name)


# -- per-document comparison -----------------------------------------------------------------

def _npz(path: Path) -> dict:
    import numpy as np
    with np.load(path, allow_pickle=False) as data:
        return {k: data[k] for k in data.files}


def _metadata(arrays: dict):
    value = arrays.get("metadata_json")
    return None if value is None else json.loads(str(value))


def compare_calls(old: dict, new: dict, result: Result):
    a, b = old.get("calls", []), new.get("calls", [])
    if len(a) != len(b):
        result.fail(f"calls: {len(a)} recorded on the old side, {len(b)} on the new side")
    for i, (x, y) in enumerate(zip(a, b)):
        result.counts["calls"] += 1
        x, y = dict(x), dict(y)
        found = diff_forms(x, y, f"calls[{i}] {x.get('function')}", result)
        if found:
            result.fail(found)


def compare_arrays_identity(old_arrays: dict, new_arrays: dict, result: Result):
    for key in sorted(set(old_arrays) | set(new_arrays)):
        if key not in old_arrays or key not in new_arrays:
            result.fail(f"fields.npz {key}: {'added' if key not in old_arrays else 'removed'}")
            continue
        a, b = old_arrays[key], new_arrays[key]
        result.counts["arrays"] += 1
        sa, sb = _sha(a.tobytes()), _sha(b.tobytes())
        if key == "metadata_json":
            compare_trees_identity(_metadata(old_arrays), _metadata(new_arrays), "metadata_json", result)
            result.arrays.append([key, sa, sb, "json", "compared as JSON"])
            continue
        ok = a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
        result.arrays.append([key, sa, sb, "=", "equal" if ok else "differs"])
        if not ok:
            result.fail(f"fields.npz {key}: {a.dtype}{a.shape} sha {sa[:12]} != {b.dtype}{b.shape} sha {sb[:12]}")


def _within_ulp(expected, actual, kind, where, result: Result) -> bool:
    import numpy as np
    e, n = np.atleast_1d(np.asarray(expected, dtype=float)), np.atleast_1d(np.asarray(actual, dtype=float))
    if e.shape != n.shape:
        result.fail(f"{where} ({kind}): shape {e.shape} != {n.shape}")
        return False
    worst = max((ulp_distance(float(x), float(y)) for x, y in zip(e.ravel(), n.ravel())), default=0)
    result.counts["exceptions"] += 1
    if worst > ULP_LIMIT:
        result.fail(f"{where} ({kind}): {worst} ulp from the old value, more than {ULP_LIMIT}")
        return False
    return True


def _exception_allowed(rule, old_record) -> bool:
    if rule["kind"] != "group_index_length_frame":
        return True
    units = old_record.get("load", {}).get("length_units", [])
    return bool(units) and all(u in ("nm", "m") for u in units)


def compare_arrays_layout(old_arrays, new_arrays, lmap: LayoutMap, old_record, old_dir: Path, result: Result):
    seen_new = set()
    kernel_nodes = None
    for key in sorted(old_arrays):
        a = old_arrays[key]
        if key in ("metadata_json", "field_layout", "result_format", "field_representation", "study_parameter") \
                and key not in lmap.arrays:
            seen_new.add(key)
            continue
        if key in lmap.arrays_removed:
            _removed_array_check(key, lmap.arrays_removed[key], old_arrays, result)
            continue
        if key not in lmap.arrays:
            result.fail(f"fields.npz {key}: not in map {lmap.source} (neither mapped nor removed)")
            continue
        new_key, f = lmap.arrays[key]
        seen_new.add(new_key)
        if new_key not in new_arrays:
            result.fail(f"fields.npz {key} -> {new_key}: missing on the new side")
            continue
        b = new_arrays[new_key]
        result.counts["arrays"] += 1
        rule = lmap.exceptions.get(("array", new_key))
        if rule is not None:
            if not _exception_allowed(rule, old_record):
                result.fail(f"fields.npz {new_key}: exception {rule['kind']} does not apply to this document")
            else:
                _within_ulp(a * EXCEPTIONS[rule["kind"]], b, rule["kind"], f"fields.npz {new_key}", result)
            continue
        if f == "kernel-L1":
            units = old_record.get("load", {}).get("length_units", [])
            if not units or not all(u in ("nm", "m") for u in units):
                result.fail(f"fields.npz {new_key}: kernel-L1 applies to nanometre and metre em fixtures only")
                continue
            if kernel_nodes is None:
                kernel = _npz(old_dir / "mesher_outputs.npz")
                last = max(int(k.split("_")[1]) for k in kernel if k.startswith("nodes_"))
                kernel_nodes = kernel[f"nodes_{last}"]
        expected = array_transform(f, a, kernel_nodes)
        ok = expected.dtype == b.dtype and expected.shape == b.shape and expected.tobytes() == b.tobytes()
        result.arrays.append([f"{key} -> {new_key}", _sha(a.tobytes()), _sha(b.tobytes()), f,
                              "equal" if ok else "differs"])
        if not ok:
            result.fail(f"fields.npz {key} -> {new_key} ({f}): {expected.dtype}{expected.shape} != "
                        f"{b.dtype}{b.shape} or bytes differ")
    for key in sorted(new_arrays):
        if key in seen_new or key == "metadata_json":
            continue
        if not any(p.fullmatch(key) for p in lmap.arrays_added):
            result.fail(f"fields.npz {key}: added on the new side and not on the map's added list")
    if "metadata_json" in new_arrays and "metadata_json" in old_arrays:
        compare_trees_layout(_metadata(old_arrays), _metadata(new_arrays), lmap, old_record, "metadata_json", result)


def _removed_array_check(key, rule, old_arrays, result: Result):
    check = rule.get("check", "unit-metadata")
    if check == "time-tail":
        ok = old_arrays[key].tobytes() == old_arrays[rule["of"]][1:].tobytes()
    elif check == "equals":
        ok = old_arrays[key].tobytes() == old_arrays[rule["of"]].tobytes()
    else:
        ok = True
    if not ok:
        result.fail(f"fields.npz {key}: removed, but its check {check} failed")


def compare_trees_layout(old, new, lmap: LayoutMap, old_record, label: str, result: Result):
    a, b = leaves(old), leaves(new)
    used_new = set()
    by_path = {}
    for path in a:
        for pattern, new_pattern, f, rule in lmap.summary:
            captures = match(pattern, path)
            if captures is not None:
                by_path[path] = (new_pattern, f, rule, captures)
                break
    for path, value in sorted(a.items(), key=lambda kv: [str(x) for x in kv[0]]):
        where = f"{label} {show(path)}"
        if any(match(p, path) is not None for p in lmap.identifiers):
            continue
        if path not in by_path:
            result.fail(f"{where}: not in map {lmap.source}")
            continue
        new_pattern, f, rule, captures = by_path[path]
        if f == "removed":
            _removed_leaf_check(path, value, rule, captures, a, where, result)
            continue
        new_path = fill(new_pattern, captures)
        used_new.add(new_path)
        if new_path not in b:
            result.fail(f"{where} -> {show(new_path)}: missing on the new side")
            continue
        result.counts["summary_leaves"] += 1
        exception = lmap.exceptions.get(("summary", show(new_path)))
        if exception is not None:
            if not _exception_allowed(exception, old_record):
                result.fail(f"{where}: exception {exception['kind']} does not apply to this document")
            else:
                _within_ulp(value * EXCEPTIONS[exception["kind"]], b[new_path], exception["kind"], where, result)
            continue
        try:
            expected = scalar_transform(f, value)
        except ValueError as exc:
            result.fail(f"{where}: {exc}")
            continue
        same_leaf(expected, b[new_path], f"{where} -> {show(new_path)} ({f})", result)
    for path in sorted(set(b) - used_new, key=lambda p: [str(x) for x in p]):
        if any(match(p, path) is not None for p in lmap.summary_added + lmap.identifiers):
            continue
        result.fail(f"{label} {show(path)}: added on the new side and not on the map's added list")


def _removed_leaf_check(path, value, rule, captures, old_leaves, where, result: Result):
    """``equals``: the leaf equals the old leaf ``of`` (with this rule's captures filled in);
    ``time-tail``: leaf ``i`` equals old leaf ``of[i + 1]`` (``rate_time_s == time_s[1:]``)."""
    check = rule.get("check", "unit-metadata")
    if check == "unit-metadata":
        return
    of = parse_pattern(rule["of"])
    if check == "time-tail":
        if not isinstance(path[-1], int):
            result.fail(f"{where}: time-tail applies to list entries")
            return
        other = old_leaves.get(fill(of, []) + (path[-1] + 1,))
    else:
        other = old_leaves.get(fill(of, captures))
    if _hex(value) is None or _hex(value) != _hex(other):
        result.fail(f"{where}: removed, but its check {check} against {rule['of']} failed ({value!r}, {other!r})")


def _vtu_arrays(form: dict) -> dict:
    out = {"points": form["points"]}
    for kind in ("point_data", "field_data"):
        for name, value in form.get(kind, []):
            out[f"{kind}:{name}"] = value
    for name, values in form.get("cell_data", []):
        out[f"cell_data:{name}"] = values
    out["cells"] = form.get("cells")
    return out


def compare_exports(old: dict, new: dict, old_dir: Path, new_dir: Path, lmap, result: Result):
    a, b = old.get("export", {}), new.get("export", {})
    if set(a) != set(b):
        result.fail(f"exports: {sorted(a)} != {sorted(b)}")
    for name in sorted(set(a) & set(b)):
        x, y = a[name], b[name]
        if x["status"] != y["status"]:
            result.fail(f"export {name}: {x['status']} != {y['status']}")
            continue
        if x["status"] == "refused":
            same = x["exception"][0] == y["exception"][0] and (lmap is not None or x["exception"] == y["exception"])
            if not same:
                result.fail(f"export {name}: refusal {x['exception']} != {y['exception']}")
            continue
        if set(x["files"]) != set(y["files"]):
            result.fail(f"export {name}: files {sorted(x['files'])} != {sorted(y['files'])}")
            continue
        for rel in sorted(x["files"]):
            fx, fy = x["files"][rel], y["files"][rel]
            if "collection" in fx:
                cx = [[float.hex(float(t)), f] for t, f in fx["collection"]]
                cy = [[float.hex(float(t)), f] for t, f in fy["collection"]]
                if cx != cy:
                    result.fail(f"export {rel}: collection {cx[:3]} != {cy[:3]}")
                continue
            if lmap is None:
                ax, ay = _vtu_arrays(fx), _vtu_arrays(fy)
                for key in sorted(set(ax) | set(ay)):
                    result.counts["vtu_arrays"] += 1
                    if key not in ax or key not in ay:
                        result.fail(f"export {rel} {key}: {'added' if key not in ax else 'removed'}")
                        continue
                    found = diff_forms(ax[key], ay[key], f"export {rel} {key}", result)
                    if found:
                        result.fail(found)
            else:
                _compare_vtu_layout(old_dir / "export" / rel, new_dir / "export" / rel, lmap, rel, result)


def _compare_vtu_layout(old_path: Path, new_path: Path, lmap: LayoutMap, rel: str, result: Result):
    import meshio
    a, b = meshio.read(old_path), meshio.read(new_path)
    result.counts["vtu_arrays"] += 1
    if a.points.tobytes() != b.points.tobytes():
        result.fail(f"export {rel} points differ")
    used = set()
    for kind in ("point_data", "cell_data"):
        old_data, new_data = getattr(a, kind), getattr(b, kind)
        for name, value in old_data.items():
            if name not in lmap.vtu:
                result.fail(f"export {rel} {kind}:{name}: not in map {lmap.source}")
                continue
            new_name, f = lmap.vtu[name]
            used.add((kind, new_name))
            if new_name not in new_data:
                result.fail(f"export {rel} {kind}:{name} -> {new_name}: missing")
                continue
            result.counts["vtu_arrays"] += 1
            olds = value if kind == "cell_data" else [value]
            news = new_data[new_name] if kind == "cell_data" else [new_data[new_name]]
            for x, y in zip(olds, news):
                expected = array_transform(f, x)
                if expected.dtype != y.dtype or expected.shape != y.shape or expected.tobytes() != y.tobytes():
                    result.fail(f"export {rel} {kind}:{name} -> {new_name} ({f}) differs")
        for name in new_data:
            if (kind, name) not in used and not any(p.fullmatch(name) for p in lmap.vtu_added):
                result.fail(f"export {rel} {kind}:{name}: added and not on the map's added list")


def compare_document(doc_id: str, old_dir: Path, new_dir: Path, mode: str, maps: Path) -> Result:
    result = Result(doc_id, mode)
    old, new = _load_json(old_dir / "record.json"), _load_json(new_dir / "record.json")
    for side, record in (("old", old), ("new", new)):
        if "recorder_error" in record:
            result.fail(f"{side} side: the recorder failed: {record['recorder_error'].splitlines()[-1]}")
        if record.get("leaked_bindings"):
            result.fail(f"{side} side: bindings the recorder missed: {record['leaked_bindings']}")
        load = record.get("load", {})
        if load.get("status") != "ok":
            result.fail(f"{side} side: the document did not load: {load.get('exception')}")
        roundings = load.get("pm_roundings", []) + record.get("run", {}).get("after", {}).get("pm_roundings", [])
        if roundings:
            result.fail(f"{side} side: picometre rounding on a corpus document: {roundings[:3]}")
    if not result.equal:
        return result
    if mode == "identity":
        for key in ("load",):
            found = diff_forms(old.get(key), new.get(key), key, result)
            if found:
                result.fail(found)
    compare_calls(old, new, result)
    run_a, run_b = old.get("run", {}), new.get("run", {})
    if mode == "identity" and run_a.get("after") != run_b.get("after"):
        result.fail(f"diagnostics after the run differ: {run_a.get('after')} != {run_b.get('after')}")
    if run_a.get("status") != run_b.get("status"):
        result.fail(f"run status {run_a.get('status')} != {run_b.get('status')}")
        return result
    if run_a.get("status") == "error":
        if run_a["exception"][0] != run_b["exception"][0]:
            result.fail(f"run error {run_a['exception']} != {run_b['exception']}")
        if mode == "identity" and run_a["exception"] != run_b["exception"]:
            result.fail(f"run error message {run_a['exception'][1]!r} != {run_b['exception'][1]!r}")
        evidence_a, evidence_b = run_a.get("failure_evidence"), run_b.get("failure_evidence")
        if (evidence_a is None) != (evidence_b is None):
            result.fail("failure evidence recorded on one side only")
        elif evidence_a is not None:
            if mode == "identity":
                compare_trees_identity(evidence_a, evidence_b, "failure_evidence", result)
            else:
                lmap = _map_for(old_dir, maps, result)
                if lmap is not None:
                    compare_trees_layout(evidence_a, evidence_b, lmap, old, "failure_evidence", result)
        return result
    save_a, save_b = old.get("save", {}), new.get("save", {})
    if save_a.get("status") != save_b.get("status") or save_a.get("status") != "ok":
        result.fail(f"save {save_a.get('status')} != {save_b.get('status')}")
        return result
    files_a = {f[0] for f in save_a["files"]} - EXCLUDED_FILES
    files_b = {f[0] for f in save_b["files"]} - EXCLUDED_FILES
    if files_a != files_b:
        result.fail(f"saved files {sorted(files_a)} != {sorted(files_b)}")
    if ("results.png" in {f[0] for f in save_a["files"]}) != ("results.png" in {f[0] for f in save_b["files"]}):
        result.fail("results.png written on one side only")
    summary_a = _load_json(old_dir / "result" / "summary.json")
    summary_b = _load_json(new_dir / "result" / "summary.json")
    arrays_a = _npz(old_dir / "result" / "fields.npz") if (old_dir / "result" / "fields.npz").exists() else {}
    arrays_b = _npz(new_dir / "result" / "fields.npz") if (new_dir / "result" / "fields.npz").exists() else {}
    if mode == "identity":
        compare_trees_identity(summary_a, summary_b, "summary.json", result)
        if "model.json" in files_a & files_b:
            compare_trees_identity(_load_json(old_dir / "result" / "model.json"),
                                   _load_json(new_dir / "result" / "model.json"), "model.json", result)
        compare_arrays_identity(arrays_a, arrays_b, result)
        compare_exports(old, new, old_dir, new_dir, None, result)
    else:
        lmap = _map_for(old_dir, maps, result)
        if lmap is None:
            return result
        compare_trees_layout(summary_a, summary_b, lmap, old, "summary.json", result)
        compare_arrays_layout(arrays_a, arrays_b, lmap, old, old_dir, result)
        compare_exports(old, new, old_dir, new_dir, lmap, result)
    return result


def _map_for(old_dir: Path, maps: Path, result: Result):
    record = _load_json(old_dir / "record.json")
    layout = None
    fields = old_dir / "result" / "fields.npz"
    if fields.exists():
        layout = str(_npz(fields).get("field_layout", ""))
    layout = layout or record.get("load", {}).get("kind")
    try:
        return LayoutMap.load(maps, layout)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        result.fail(str(exc))
        return None


def compare(old: Path, new: Path, plan: dict | None, maps: Path) -> tuple[list[Result], list[str]]:
    manifest_a, manifest_b = _load_json(old / "manifest.json"), _load_json(new / "manifest.json")
    ids_a = [d["id"] for d in manifest_a["documents"]]
    ids_b = [d["id"] for d in manifest_b["documents"]]
    problems = []
    if sorted(ids_a) != sorted(ids_b):
        problems.append(f"documents recorded on one side only: old {sorted(set(ids_a) - set(ids_b))}, "
                        f"new {sorted(set(ids_b) - set(ids_a))}")
    for side, manifest in (("old", manifest_a), ("new", manifest_b)):
        install = manifest.get("install", {})
        if install.get("targets_missing"):
            problems.append(f"{side} side: recorded functions missing: {install['targets_missing']}")
        if not manifest.get("isolated"):
            problems.append(f"{side} side: the recorder did not run with python -I")
    if plan is not None and set(plan) - set(ids_a):
        problems.append(f"plan names documents not recorded: {sorted(set(plan) - set(ids_a))}")
    results = []
    for doc_id in [d for d in ids_a if d in set(ids_b)]:
        mode = "identity" if plan is None else plan.get(doc_id)
        if mode not in ("identity", "layout"):
            problems.append(f"{doc_id}: the plan gives no mode (identity or layout)")
            continue
        results.append(compare_document(doc_id, old / doc_id, new / doc_id, mode, maps))
    return results, problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old", type=Path, required=True, help="recording of the baseline")
    parser.add_argument("--new", type=Path, required=True, help="recording of the change")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--identity", action="store_true", help="compare every document with the identity map")
    group.add_argument("--plan", type=Path, help="JSON {document id: 'identity' | 'layout'}")
    parser.add_argument("--maps", type=Path, default=Path(__file__).resolve().parent / "maps")
    parser.add_argument("--report", type=Path, help="write the findings and the SHA-256 tables as JSON")
    args = parser.parse_args(argv)
    plan = None if args.identity else _load_json(args.plan)
    results, problems = compare(args.old, args.new, plan, args.maps)
    equal = sum(r.equal for r in results)
    for r in results:
        types = f", {len(r.type_differences)} type differences" if r.type_differences else ""
        print(f"{r.id}: {'equal' if r.equal else 'DIFFERENT'} ({r.mode}; {r.counts['calls']} calls, "
              f"{r.counts['arrays']} arrays, {r.counts['summary_leaves']} summary leaves, "
              f"{r.counts['vtu_arrays']} VTU arrays{types})")
        for failure in r.failures:
            print(f"    {failure}")
    for problem in problems:
        print(f"problem: {problem}")
    print(f"{len(results)} documents compared: {equal} equal, {len(results) - equal} different; "
          f"{len(problems)} other problems")
    if args.report:
        manifests = {side: _load_json(path / "manifest.json") for side, path in (("old", args.old), ("new", args.new))}
        report = {"old": {k: manifests["old"].get(k) for k in ("root_commit", "root_dirty", "versions")},
                  "new": {k: manifests["new"].get(k) for k in ("root_commit", "root_dirty", "versions")},
                  "problems": problems, "documents": [r.as_dict() for r in results]}
        args.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0 if results and equal == len(results) and not problems else 1


if __name__ == "__main__":
    sys.exit(main())
