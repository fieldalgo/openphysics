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
with a check, and only the pre-registered exceptions compare within 4 ulp. The em maps add
closed rules (README "The em.modes2d commit"): alternatives (exactly one new name present), the
``array`` summary rule, ``json`` arrays, call rules for the D-24 names and the D-22 argument,
the VTU transform ``imag-conj`` and the ``collection`` transform. Exit status 0 when
every document is equal, 1 otherwise. ``--report`` writes the per-document, per-array SHA-256
table as JSON.

    python tools/units_batch/compare.py --old <recording> --new <recording> --phase3 [--rules phase3_rules.json]

``--phase3`` is the galerkin step's mode (README "Phase 3"): both sides read the same documents,
every saved array, summary leaf, VTU array and message must be identical, and the recorded calls
are compared by parameter name (the ``bound`` form of each call) under the rule entries of
``phase3_rules.json``, whose kinds are the closed table RULE_KINDS. Each side's recorded targets
are its own declaration; a target recorded on one side only must be mapped by a kind 1 or kind
7 entry, an entry of an unknown kind is refused, and an entry that applies nowhere is a problem.
"""

from __future__ import annotations

import argparse
import copy
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
#: the VTU-only transform of an exported imaginary part: the sign flip of a conjugation (spec §5.4,
#: "imaginary parts are -old"), which keeps a signed zero as np.conj does
VTU_TRANSFORMS = ARRAY_TRANSFORMS + ("imag-conj",)
#: the D-24 renames of local em material names (convert_v02.D24_RENAMES)
D24_RENAMES = {"SiO2": "oxide", "Si": "silicon"}
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
        self.counts = {"calls": 0, "arrays": 0, "summary_leaves": 0, "vtu_arrays": 0, "exceptions": 0,
                       "absent_defaults": 0}
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

_SEGMENT = re.compile(r'\["([^"]*)"\]|\[(\d+)\]|\[\]|\*\*|\*|[^.\[\]]+')


def parse_pattern(text: str) -> list:
    """Dotted segments; ``*`` one key, ``[]`` one list index, ``[2]`` that index, ``**`` any rest,
    ``["a.b"]`` literal."""
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
                   ("lit", int(m.group(2))) if m.group(2) is not None else
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
        self.json_arrays = {}
        for rule in data.get("arrays", []):
            f = ALIASES.get(rule.get("f", "="), rule.get("f", "="))
            if f == "json":
                # a JSON text array whose content is a summary subtree: compared through the
                # summary rules under the given prefixes (spec §5.3.4, "content keys renamed")
                self.json_arrays[rule["old"]] = (rule["new"], rule["prefix"], rule.get("new_prefix", rule["prefix"]))
                continue
            if f not in ARRAY_TRANSFORMS:
                raise ValueError(f"{source}: array transform {f!r} is not in the closed list")
            new = rule["new"]
            # alternatives: exactly one of the names is saved (a scalar or a vector result)
            self.arrays[rule["old"]] = (tuple(new) if isinstance(new, list) else (new,), f)
        self.arrays_removed = {r["old"]: r for r in data.get("arrays_removed", [])}
        self.arrays_added = [re.compile(p) for p in data.get("arrays_added", [])]
        self.summary = []
        for rule in data.get("summary", []):
            f = ALIASES.get(rule.get("f", "="), rule.get("f", "="))
            if f not in SUMMARY_TRANSFORMS and f != "array":
                raise ValueError(f"{source}: summary transform {f!r} is not in the closed list")
            if f == "removed" and rule.get("check", "unit-metadata") not in REMOVED_CHECKS:
                raise ValueError(f"{source}: removed check {rule.get('check')!r} is not in the closed list")
            if "absent_default" in rule and (f != "=" or not isinstance(rule["absent_default"], str)):
                raise ValueError(f"{source}: absent_default names an input key and applies to '=' rules only")
            if f == "array" and (rule.get("part") not in ("real", "imag") or "old_array" not in rule
                                 or "new_array" not in rule):
                raise ValueError(f"{source}: an array rule names old_array, new_array and part (real or imag)")
            # a list of new paths are alternatives: exactly one is present (the real or the complex
            # form of one value)
            news = None if f == "removed" else [parse_pattern(n) for n in
                                                (rule["new"] if isinstance(rule["new"], list) else [rule["new"]])]
            self.summary.append((parse_pattern(rule["old"]), news, f, rule))
        # an always-added key covers its whole subtree (resolved_inputs, diagnostics, ...)
        self.summary_added = [parse_pattern(p) for p in (*(f"{k}.**" for k in ADDED_ALWAYS),
                                                         *data.get("summary_added", []))]
        self.identifiers = [parse_pattern(p) for p in data.get("identifiers", [])]
        self.vtu = {r["old"]: (r["new"], ALIASES.get(r.get("f", "="), r.get("f", "="))) for r in data.get("vtu", [])}
        for name, (_new, f) in self.vtu.items():
            if f not in VTU_TRANSFORMS:
                raise ValueError(f"{source}: VTU transform {f!r} is not in the closed list")
        self.collection = data.get("collection", "=")
        if self.collection not in ("=", "L1"):
            raise ValueError(f"{source}: collection transform {self.collection!r} is not '=' or 'L1'")
        self.calls = data.get("calls", {})
        if set(self.calls) - {"d24_material_names", "arguments"}:
            raise ValueError(f"{source}: unknown call rules {sorted(set(self.calls) - {'d24_material_names', 'arguments'})}")
        self.vtu_added = [re.compile(p) for p in data.get("vtu_added", [])]
        self.exceptions = []
        for rule in data.get("exceptions", []):
            if rule["kind"] not in EXCEPTIONS:
                raise ValueError(f"{source}: exception {rule['kind']!r} is not pre-registered")
            where = rule.get("where", "summary")
            # an array exception names the array; a summary exception is a path pattern
            self.exceptions.append((where, rule["new"] if where == "array" else parse_pattern(rule["new"]), rule))

    def exception(self, where: str, new, old_record):
        """The pre-registered exception for a new array name or summary path that applies to this
        document (``group_index_length_frame`` to the nanometre and metre fixtures only), or None;
        everything else compares bitwise."""
        for kind, target, rule in self.exceptions:
            if kind != where:
                continue
            hit = target == new if where == "array" else match(target, new) is not None
            if hit and _exception_allowed(rule, old_record):
                return rule
        return None

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


def _d24_material_names(form, local: set):
    """A recorded call form with each D-24 renamed local material (``SiO2`` -> ``oxide``, ``Si``
    -> ``silicon``) under its new name: the physmat ``Material`` name and its model's label. Only
    names the old document defines locally are renamed (P2-1 conversion rule; D-24)."""
    if isinstance(form, list):
        if len(form) == 3 and form[0] == "physmat.Material" and form[1] in local:
            renamed = D24_RENAMES[form[1]]
            return ["physmat.Material", renamed, _d24_label(form[2], form[1], renamed)]
        return [_d24_material_names(v, local) for v in form]
    if isinstance(form, dict):
        return {k: _d24_material_names(v, local) for k, v in form.items()}
    return form


def _d24_label(form, old, new):
    if isinstance(form, list):
        if len(form) == 2 and form[0] == "label" and form[1] == old:
            return ["label", new]
        return [_d24_label(v, old, new) for v in form]
    return form


def _apply_call_rules(calls: list, rules: dict, local_materials) -> list:
    """The old side's calls under the map's call rules (closed): ``d24_material_names`` renames
    the D-24 local materials inside physmat Material forms; ``arguments`` replaces a positional
    argument of a function by its new value when another argument has a given value (D-22: the
    kernel's n_cladding on a scalar solve, which format 0.3 refuses and the kernel never reads)."""
    if not rules:
        return calls
    out = copy.deepcopy(calls)
    if rules.get("d24_material_names"):
        local = set(local_materials) & set(D24_RENAMES)
        if local:
            out = [_d24_material_names(c, local) for c in out]
            for call in out:
                # physmat is recorded at the optical model's evaluation (README "Phase 3"), whose
                # object is the model a local material builds, labelled with the material's name
                if call.get("function", "").startswith("physmat.") and "self" in call:
                    for old in sorted(local):
                        call["self"] = _d24_label(call["self"], old, D24_RENAMES[old])
    for rule in rules.get("arguments", []):
        for call in out:
            args = call.get("args")
            if call.get("function") != rule["function"] or not (isinstance(args, list) and args[0] == "list"):
                continue
            items = args[1]
            when = rule["when"]
            if len(items) > max(rule["index"], when["index"]) and items[when["index"]] == when["equals"]:
                items[rule["index"]] = rule["new"]
    return out


def compare_calls(old: dict, new: dict, result: Result, rules: dict | None = None, local_materials=()):
    """The identity and layout modes: every call as written (positions and keywords); the
    phase-3 fields (the call bound to parameter names) are not compared here."""
    a, b = _apply_call_rules(old.get("calls", []), rules or {}, local_materials), new.get("calls", [])
    if len(a) != len(b):
        result.fail(f"calls: {len(a)} recorded on the old side, {len(b)} on the new side")
    for i, (x, y) in enumerate(zip(a, b)):
        result.counts["calls"] += 1
        x = {k: v for k, v in x.items() if k not in PHASE3_ONLY_FIELDS}
        y = {k: v for k, v in y.items() if k not in PHASE3_ONLY_FIELDS}
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
        if key in lmap.json_arrays:
            new_key, prefix, new_prefix = lmap.json_arrays[key]
            seen_new.add(new_key)
            if new_key not in new_arrays:
                result.fail(f"fields.npz {key} -> {new_key}: missing on the new side")
                continue
            result.counts["arrays"] += 1
            result.arrays.append([f"{key} -> {new_key}", _sha(a.tobytes()), _sha(new_arrays[new_key].tobytes()), "json",
                                  "compared as JSON"])
            compare_trees_layout({prefix: json.loads(str(a))}, {new_prefix: json.loads(str(new_arrays[new_key]))},
                                 lmap, old_record, f"fields.npz {key}", result)
            continue
        if key not in lmap.arrays:
            result.fail(f"fields.npz {key}: not in map {lmap.source} (neither mapped nor removed)")
            continue
        names, f = lmap.arrays[key]
        present = [n for n in names if n in new_arrays]
        if len(present) > 1:
            result.fail(f"fields.npz {key}: more than one alternative is saved: {present}")
            continue
        new_key = present[0] if present else names[0]
        seen_new.add(new_key)
        if new_key not in new_arrays:
            result.fail(f"fields.npz {key} -> {' | '.join(names)}: missing on the new side")
            continue
        b = new_arrays[new_key]
        result.counts["arrays"] += 1
        rule = lmap.exception("array", new_key, old_record)
        if rule is not None:
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
        compare_trees_layout(_metadata(old_arrays), _metadata(new_arrays), lmap, old_record, "metadata_json", result,
                             (old_arrays, new_arrays))


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


def compare_trees_layout(old, new, lmap: LayoutMap, old_record, label: str, result: Result, arrays=None):
    """Old tree against new tree through the map's summary rules. ``arrays`` is the pair (old
    npz, new npz) that ``array`` rules read: such a leaf is the part of a saved array (a
    summary value object of a complex array), so the old leaf must equal the old array's entry
    and the new leaf the new array's entry, while the arrays themselves are compared bitwise
    by their array rule."""
    a, b = leaves(old), leaves(new)
    used_new = set()
    by_path = {}
    for path in a:
        for pattern, new_patterns, f, rule in lmap.summary:
            captures = match(pattern, path)
            if captures is not None:
                by_path[path] = (new_patterns, f, rule, captures)
                break
    for path, value in sorted(a.items(), key=lambda kv: [str(x) for x in kv[0]]):
        where = f"{label} {show(path)}"
        if any(match(p, path) is not None for p in lmap.identifiers):
            continue
        if path not in by_path:
            result.fail(f"{where}: not in map {lmap.source}")
            continue
        new_patterns, f, rule, captures = by_path[path]
        if f == "removed":
            _removed_leaf_check(path, value, rule, captures, a, where, result)
            continue
        candidates = [fill(p, captures) for p in new_patterns]
        present = [c for c in candidates if c in b]
        if len(candidates) > 1 and len(present) > 1:
            result.fail(f"{where}: more than one alternative is present on the new side: {[show(c) for c in present]}")
            continue
        new_path = present[0] if present else candidates[0]
        used_new.add(new_path)
        if new_path not in b:
            if "absent_default" in rule and _absent_default(value, rule["absent_default"], new):
                result.counts["absent_defaults"] += 1
                continue
            result.fail(f"{where} -> {' | '.join(show(c) for c in candidates)}: missing on the new side")
            continue
        result.counts["summary_leaves"] += 1
        exception = lmap.exception("summary", new_path, old_record)
        if exception is not None:
            _within_ulp(value * EXCEPTIONS[exception["kind"]], b[new_path], exception["kind"], where, result)
            continue
        if f == "array":
            _array_leaf(value, b[new_path], rule, captures, arrays, f"{where} -> {show(new_path)}", result)
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


def _array_leaf(old_value, new_value, rule, captures, arrays, where: str, result: Result):
    """An ``array`` rule: the old leaf is ``part`` of ``old_array`` at the captured indices, the
    new leaf the same part of ``new_array`` (or of the one alternative saved)."""
    if arrays is None:
        result.fail(f"{where}: an array rule needs the saved arrays")
        return
    old_arrays, new_arrays = arrays
    names = rule["new_array"] if isinstance(rule["new_array"], list) else [rule["new_array"]]
    saved = [n for n in names if n in new_arrays]
    if rule["old_array"] not in old_arrays or len(saved) != 1:
        result.fail(f"{where}: arrays {rule['old_array']} and {names} are not saved as the rule needs")
        return
    index = tuple(c for c in captures if isinstance(c, int))
    part = rule["part"]
    old_entry = float(getattr(old_arrays[rule["old_array"]][index], part))
    new_entry = float(getattr(new_arrays[saved[0]][index], part))

    def same(entry, leaf):          # a value that is not finite is written as null
        return not math.isfinite(entry) if leaf is None else _hex(entry) == _hex(leaf)
    if not same(old_entry, old_value):
        result.fail(f"{where}: the old leaf {old_value!r} is not {rule['old_array']}{list(index)}.{part}")
    if not same(new_entry, new_value):
        result.fail(f"{where}: the new leaf {new_value!r} is not {saved[0]}{list(index)}.{part}")


def _absent_default(value, key: str, new_tree) -> bool:
    """An input the 0.2 reader filled with zero and echoed, and the 0.3 reader leaves absent: it
    records the default in ``defaults_applied`` and writes nothing (hazard H9). The old leaf must
    be +0.0 and the new tree must list a default whose path ends in ``.<key>`` (rule
    ``absent_default``); a given input is compared under its rule as usual."""
    if _hex(value) != float.hex(0.0) or not isinstance(new_tree, dict):
        return False
    applied = new_tree.get("defaults_applied")
    return isinstance(applied, list) and any(
        isinstance(entry, dict) and str(entry.get("path", "")).endswith("." + key) for entry in applied)


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


def layout_renames(maps: Path) -> dict:
    """old field layout -> new field layout of every layout map: the identifiers a kind's commit
    replaces. Identifier strings are not compared (P2-1), so an export refusal that lists the
    supported layouts is compared after this renaming."""
    out = {}
    for path in sorted(Path(maps).glob("*.json")):
        data = _load_json(path)
        if data.get("format") == "openphysics-units-batch-map-v1" and data.get("new_layout"):
            out[data["old_layout"]] = data["new_layout"]
    return out


def _renamed(message: str, renames: dict) -> str:
    # the longest identifiers first, so that one is never replaced inside another
    for old in sorted(renames, key=len, reverse=True):
        message = re.sub(r"(?<![\w-])" + re.escape(old) + r"(?![\w-])", "\0" + renames[old] + "\0", message)
    return message.replace("\0", "")


def compare_exports(old: dict, new: dict, old_dir: Path, new_dir: Path, lmap, result: Result, renames=None):
    a, b = old.get("export", {}), new.get("export", {})
    if set(a) != set(b):
        result.fail(f"exports: {sorted(a)} != {sorted(b)}")
    for name in sorted(set(a) & set(b)):
        x, y = a[name], b[name]
        if x["status"] != y["status"]:
            result.fail(f"export {name}: {x['status']} != {y['status']}")
            continue
        if x["status"] == "refused":
            renamed = [x["exception"][0], _renamed(x["exception"][1], renames or {})] + list(x["exception"][2:])
            same = x["exception"][0] == y["exception"][0] and (lmap is not None or renamed == list(y["exception"]))
            if not same:
                result.fail(f"export {name}: refusal {x['exception']} != {y['exception']}")
            continue
        if set(x["files"]) != set(y["files"]):
            result.fail(f"export {name}: files {sorted(x['files'])} != {sorted(y['files'])}")
            continue
        for rel in sorted(x["files"]):
            fx, fy = x["files"][rel], y["files"][rel]
            if "collection" in fx:
                step = (lambda t: float(t)) if not _collection_transformed(lmap, old_dir) else \
                    (lambda t: scalar_transform(lmap.collection, float(t)))
                cx = [[float.hex(step(t)), f] for t, f in fx["collection"]]
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


def _collection_transformed(lmap, old_dir: Path) -> bool:
    """The map's collection transform applies to the timesteps of an old wavelength sweep only
    (its saved ``study_parameter`` ends in ``.wavelength``); point indices compare as written."""
    if lmap is None or lmap.collection == "=":
        return False
    fields = old_dir / "result" / "fields.npz"
    return fields.exists() and str(_npz(fields).get("study_parameter", "")).endswith(".wavelength")


def _compare_vtu_layout(old_path: Path, new_path: Path, lmap: LayoutMap, rel: str, result: Result):
    import meshio
    import numpy as np
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
                expected = np.negative(x) if f == "imag-conj" else array_transform(f, x)
                if expected.dtype != y.dtype or expected.shape != y.shape or expected.tobytes() != y.tobytes():
                    result.fail(f"export {rel} {kind}:{name} -> {new_name} ({f}) differs")
        for name in new_data:
            if (kind, name) not in used and not any(p.fullmatch(name) for p in lmap.vtu_added):
                result.fail(f"export {rel} {kind}:{name}: added and not on the map's added list")


# -- phase 3: the same documents on both sides; calls by parameter name under closed rule kinds ---

RULES_FORMAT = "openphysics-units-batch-phase3-rules-v1"
#: The closed table of rule kinds (phase-3 specification §6): kind -> (what it does, required
#: fields, optional fields). Names of recorded functions are the recorder's (``module.name``,
#: ``module.Class.method``); ``function`` and ``class`` name the new side's (after kinds 1, 4
#: and 7). Renames act on the old side's record, value transforms on the new side's values:
#: the old value must equal the transform of the new one (``0.0 - x`` turns the head's inward
#: value into the baseline's outward one, ``to_kernel`` its exp(-i omega t) value into the
#: kernel's exp(+i omega t) one).
RULE_KINDS = {
    1: ("function rename", ("old", "new"), ()),
    2: ("keyword rename", ("function", "old", "new"), ()),
    3: ("value transform on a keyword", ("function", "keyword", "transform"), ()),
    4: ("class rename", ("old", "new"), ()),
    5: ("dataclass field rename, removal or replacement", ("class", "old", "new"), ("transform",)),
    6: ("transform inside the fields of an object", ("class", "fields", "transform"), ()),
    7: ("compare at the kernel frame", ("old", "wrapper", "kernel"), ()),
    8: ("removed keyword default", ("function", "keyword"), ("value", "form")),
    9: ("positional/keyword move", ("function", "keyword"), ()),
}
#: the value transforms of kinds 3, 5 and 6: ``0.0 - x``, and ``complex(x.real, 0.0 - x.imag)``
#: (elementwise for arrays, through the recorder's transform table)
VALUE_TRANSFORMS = ("neg", "to_kernel")
#: what phase 3 compares of a call: its arguments bound to parameter names, never their positions
PHASE3_CALL_FIELDS = ("depth", "function", "self", "bound", "bound_callbacks", "samples", "result", "raised")
PHASE3_ONLY_FIELDS = frozenset({"bound", "bound_callbacks"})
#: canonical forms whose second item is a class's qualified name (where kind 4 renames it)
QUALNAME_TAGS = frozenset({"object", "type", "opaque", "deep", "cycle", "raises", "linear-operator",
                           "conductivity-model"})


def _dumps(obj) -> str:
    """record.dumps: the key of a canonical form in a recording's transform table."""
    return json.dumps(obj, sort_keys=False, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _value_form(value):
    """The canonical form of a JSON scalar (kind 8 ``value``)."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int) and abs(value) <= 2 ** 53:
        return ["num", "int", float.hex(float(value))]
    if isinstance(value, float):
        return ["num", "float", float.hex(value)]
    raise ValueError(f"value {value!r} is not a JSON scalar; give its canonical form as 'form'")


def map_forms(form, fn):
    """``form`` rebuilt with ``fn`` applied to every canonical form in it, innermost first,
    following record.canon's grammar (a leaf such as an array form is passed to ``fn`` whole)."""
    if not isinstance(form, list) or not form or not isinstance(form[0], str):
        return form
    tag = form[0]
    if tag in ("object", "dict") and len(form) == 3 and isinstance(form[2], list):
        form = [tag, form[1], [[map_forms(k, fn) if tag == "dict" else k, map_forms(v, fn)] for k, v in form[2]]]
    elif tag == "object-array" and len(form) == 3:
        form = [tag, form[1], [map_forms(v, fn) for v in form[2]]]
    elif tag == "physmat.Material" and len(form) == 3:
        form = [tag, form[1], map_forms(form[2], fn)]
    elif tag == "callable" and len(form) == 3 and isinstance(form[2], list):
        form = [tag, form[1], [[*s[:-1], map_forms(s[-1], fn)] for s in form[2]]]
    elif tag == "linear-operator" and len(form) == 5:
        form = [*form[:4], map_forms(form[4], fn)]
    elif tag == "conductivity-model" and len(form) == 5:
        form = [*form[:3], map_forms(form[3], fn), map_forms(form[4], fn)]
    elif tag == "sparse" and len(form) == 5:
        form = [*form[:4], [[k, map_forms(v, fn)] for k, v in form[4]]]
    elif len(form) == 2 and isinstance(form[1], list):                 # a list, tuple or set
        form = [tag, [map_forms(v, fn) for v in form[1]]]
    return fn(form)


def _scalar(form):
    """The Python or NumPy scalar a number form was recorded from (its type, its double)."""
    import numpy as np
    if form[0] == "num":
        if form[2].startswith("int:"):
            raise ValueError("an integer beyond 2**53 has no value transform")
        value = float.fromhex(form[2])
        make = {"int": int, "float": float}.get(form[1]) or getattr(np, form[1], None)
    else:
        value = complex(float.fromhex(form[2]), float.fromhex(form[3]))
        make = {"complex": complex}.get(form[1]) or getattr(np, form[1], None)
    if make is None:
        raise ValueError(f"no scalar type {form[1]!r}")
    return make(value)


def _scalar_form(x) -> list:
    import numpy as np
    if isinstance(x, (complex, np.complexfloating)):
        return ["complex", type(x).__name__, float.hex(float(x.real)), float.hex(float(x.imag))]
    return ["num", type(x).__name__, float.hex(float(x))]


def transform_form(form, how: str, table: dict):
    """A canonical value under ``neg`` (``0.0 - x``) or ``to_kernel`` (``complex(x.real, 0.0 -
    x.imag)``): scalars are recomputed from their recorded type and double, arrays are looked up in
    the recording's transform table, containers and callback samples are transformed item by item
    (a refusal stays a refusal) and None stays None. Anything else raises ValueError."""
    if how not in VALUE_TRANSFORMS:
        raise ValueError(f"transform {how!r} is not in {VALUE_TRANSFORMS}")
    if form is None:
        return None
    if not isinstance(form, list) or not form:
        raise ValueError(f"{how} of {json.dumps(form)[:60]}")
    tag = form[0]
    if tag in ("num", "complex"):
        x = _scalar(form)
        return _scalar_form(0.0 - x if how == "neg" else complex(x.real, 0.0 - x.imag))
    if tag == "array" and len(form) == 4:
        entry = table.get(_dumps(form))
        if entry is None:
            raise ValueError(f"no {how} of the array {form[3][:12]} in the recording's transform table")
        return entry[how]
    if tag == "dict" and len(form) == 3:
        return [tag, form[1], [[k, transform_form(v, how, table)] for k, v in form[2]]]
    if tag == "callable" and len(form) == 3:
        return [tag, form[1], [[*s[:-1], s[-1] if isinstance(s[-1], list) and s[-1][:1] == ["raises"]
                                else transform_form(s[-1], how, table)] for s in form[2]]]
    if tag in ("list", "tuple", "object-array") and isinstance(form[-1], list):
        return [*form[:-1], [transform_form(v, how, table) for v in form[-1]]]
    raise ValueError(f"{how} of a {tag!r} form (an object's fields take kind 6)")


class Phase3Rules:
    """The entries of ``phase3_rules.json``, checked against RULE_KINDS, and how often each one
    applied (an entry that applies nowhere is reported by ``unused``)."""

    def __init__(self, data: dict, source: str):
        if not isinstance(data, dict) or data.get("format") != RULES_FORMAT:
            raise ValueError(f"{source}: format must be {RULES_FORMAT!r}")
        extra = set(data) - {"format", "description", "entries"}
        if extra or not isinstance(data.get("entries", []), list):
            raise ValueError(f"{source}: keys are format, description and entries (a list); not {sorted(extra)}")
        self.source = source
        self.entries = [self._checked(i, e) for i, e in enumerate(data.get("entries", []))]
        self.used = [0] * len(self.entries)
        # the targets each kind 1 and kind 7 entry maps, on each side; one entry per name
        self.maps_old, self.maps_new = {}, {}
        for i, e in enumerate(self.entries):
            if e["kind"] not in (1, 7):
                continue
            news = [e["new"]] if e["kind"] == 1 else [e["wrapper"], e["kernel"]]
            for side, names in ((self.maps_old, [e["old"]]), (self.maps_new, news)):
                for name in names:
                    if name in side:
                        raise ValueError(f"{source} entries[{i}]: {name} is mapped by entries[{side[name]}] too")
                    side[name] = i

    @classmethod
    def load(cls, path: Path) -> "Phase3Rules":
        return cls(_load_json(path), path.name)

    def _checked(self, i: int, entry) -> dict:
        where = f"{self.source} entries[{i}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: an entry is an object")
        kind = entry.get("kind")
        if isinstance(kind, bool) or kind not in RULE_KINDS:
            raise ValueError(f"{where}: kind {kind!r} is not in the closed table of rule kinds 1-9")
        _what, required, optional = RULE_KINDS[kind]
        missing = [f for f in required if f not in entry]
        unknown = sorted(set(entry) - {"kind", "note", *required, *optional})
        if missing or unknown:
            raise ValueError(f"{where} (kind {kind}): missing fields {missing}, unknown fields {unknown}")
        e = dict(entry)
        if not isinstance(e.get("note", ""), str):
            raise ValueError(f"{where}: note is a string")
        for f in required:
            if f in ("fields", "transform"):
                continue
            if not (isinstance(e[f], str) and e[f]) and not (kind == 5 and f in ("old", "new") and e[f] is None):
                raise ValueError(f"{where}: {f} must be a non-empty string")
        if kind in (1, 2, 4) and e["old"] == e["new"]:
            raise ValueError(f"{where}: old and new are the same")
        if kind == 5:
            e.setdefault("transform", "=")
            if e["old"] is None and e["new"] is None:
                raise ValueError(f"{where}: a field rule names the old field, the new one or both")
            if e["transform"] not in ("=",) + VALUE_TRANSFORMS:
                raise ValueError(f"{where}: transform {e['transform']!r} is not '=' or one of {VALUE_TRANSFORMS}")
            if e["transform"] != "=" and (e["old"] is None or e["new"] is None):
                raise ValueError(f"{where}: a transformed field names both its old and its new name")
        if kind in (3, 6) and e["transform"] not in VALUE_TRANSFORMS:
            raise ValueError(f"{where}: transform {e['transform']!r} is not one of {VALUE_TRANSFORMS}")
        if kind == 6 and not (isinstance(e["fields"], list) and e["fields"]
                              and all(isinstance(f, str) and f for f in e["fields"])):
            raise ValueError(f"{where}: fields is a non-empty list of field names")
        if kind == 7 and e["wrapper"] == e["kernel"]:
            raise ValueError(f"{where}: the wrapper and the kernel are different targets")
        if kind == 8:
            if ("value" in e) == ("form" in e):
                raise ValueError(f"{where}: give exactly one of value (a JSON scalar) and form")
            e["form"] = e["form"] if "form" in e else _value_form(e["value"])
        return e

    def of(self, *kinds):
        return [(i, e) for i, e in enumerate(self.entries) if e["kind"] in kinds]

    def check_targets(self, old_targets, new_targets) -> list[str]:
        """Each side's recorded targets are its own declaration: a target on one side only must be
        mapped by a kind 1 or kind 7 entry, and every name such an entry maps must be declared on
        its side."""
        old, new = set(old_targets), set(new_targets)
        problems = []
        for side, names, maps in (("old", old, self.maps_old), ("new", new, self.maps_new)):
            for name, i in sorted(maps.items()):
                if name not in names:
                    problems.append(f"rule entries[{i}] (kind {self.entries[i]['kind']}) maps {name}, which the "
                                    f"{side} side does not record")
        for side, only, maps in (("old", old - new, self.maps_old), ("new", new - old, self.maps_new)):
            for name in sorted(only):
                if name in maps:
                    self.used[maps[name]] += 1
                else:
                    problems.append(f"target {name} is recorded on the {side} side only and no kind 1 or kind 7 "
                                    "entry maps it")
        for i, e in self.of(2, 3, 8, 9):
            if e["function"] not in new:
                problems.append(f"rule entries[{i}] (kind {e['kind']}) names {e['function']}, which the new side "
                                "does not record")
        return problems

    def unused(self) -> list[str]:
        return [f"rule entries[{i}] (kind {e['kind']}, {RULE_KINDS[e['kind']][0]}) applies to nothing recorded"
                for i, e in enumerate(self.entries) if not self.used[i]]

    # -- applying the entries to one document's calls --------------------------------------------

    def apply(self, old_calls: list, new_calls: list, table: dict, result: Result) -> tuple[list, list]:
        """The two call lists made comparable: kind 7 drops the listed wrapper frames on the new
        side and maps the old frame to the kernel beneath; kinds 1 and 4 rename functions and
        classes on the old side; kind 5 renames, drops or transforms fields; kind 6 transforms
        fields of new objects; kind 2 renames old keywords; per aligned pair of calls, kind 8 drops
        a new argument that equals the removed default the old call relied on, kind 3 transforms a
        new argument and kind 9 counts the arguments bound on both sides."""
        old = [{k: copy.deepcopy(c[k]) for k in PHASE3_CALL_FIELDS if k in c} for c in old_calls]
        new = [{k: copy.deepcopy(c[k]) for k in PHASE3_CALL_FIELDS if k in c} for c in new_calls]
        wrappers = {e["wrapper"]: i for i, e in self.of(7)}
        if wrappers:
            new = self._drop_frames(new, wrappers)
        renames = {e["old"]: (i, e["kernel"]) for i, e in self.of(7)}
        renames.update({e["old"]: (i, e["new"]) for i, e in self.of(1)})
        for call in old:
            hit = renames.get(call.get("function"))
            if hit is not None:
                call["function"] = hit[1]
                self.used[hit[0]] += 1
        classes = {e["old"]: (i, e["new"]) for i, e in self.of(4)}
        fields_old = [(i, e) for i, e in self.of(5) if e["old"] is not None]
        fields_new = [(i, e) for i, e in self.of(5) if e["old"] is None or e["transform"] != "="] + self.of(6)
        for side, edit in ((old, lambda f: self._old_form(f, classes, fields_old)),
                           (new, lambda f: self._new_form(f, fields_new, table, result))):
            if not (classes or fields_old) and side is old or not fields_new and side is new:
                continue
            for call in side:
                for key in ("self", "result"):
                    if key in call:
                        call[key] = map_forms(call[key], edit)
                if isinstance(call.get("bound"), dict):
                    call["bound"] = {k: map_forms(v, edit) for k, v in call["bound"].items()}
                if side is old and isinstance(call.get("raised"), list) and call["raised"][0] in classes:
                    i, name = classes[call["raised"][0]]
                    call["raised"] = [name, *call["raised"][1:]]
                    self.used[i] += 1
        keywords = self.of(2)
        for call in old:
            for i, e in keywords:
                if call.get("function") == e["function"] and isinstance(call.get("bound"), dict) \
                        and e["old"] in call["bound"] and e["new"] not in call["bound"]:
                    call["bound"] = {e["new"] if k == e["old"] else k: v for k, v in call["bound"].items()}
                    if call.get("bound_callbacks"):
                        call["bound_callbacks"] = sorted([e["new"] if p == e["old"] else p, *rest]
                                                         for p, *rest in call["bound_callbacks"])
                    self.used[i] += 1
        pair_rules = self.of(3, 8, 9)
        if pair_rules:
            for x, y in zip(old, new):
                if x.get("function") == y.get("function") and isinstance(x.get("bound"), dict) \
                        and isinstance(y.get("bound"), dict):
                    self._pair(x, y, pair_rules, table, result)
        return old, new

    @staticmethod
    def _drop_frames(calls: list, wrappers: dict) -> list:
        out, open_depths = [], []          # depths of the dropped frames still open
        for call in calls:
            while open_depths and call["depth"] <= open_depths[-1]:
                open_depths.pop()
            if call.get("function") in wrappers:
                open_depths.append(call["depth"])
                continue
            out.append({**call, "depth": call["depth"] - len(open_depths)})
        return out

    def _old_form(self, form, classes, fields):
        if form[0] in QUALNAME_TAGS and len(form) >= 2 and form[1] in classes:
            i, name = classes[form[1]]
            form = [form[0], name, *form[2:]]
            self.used[i] += 1
        if form[0] == "object" and len(form) == 3 and fields:
            items = form[2]
            for i, e in fields:
                if form[1] != e["class"] or not any(k == e["old"] for k, _ in items):
                    continue
                items = [[e["new"], v] if k == e["old"] else [k, v] for k, v in items if k != e["old"] or e["new"]]
                self.used[i] += 1
            form = [form[0], form[1], items]
        return form

    def _new_form(self, form, rules, table, result: Result):
        if form[0] != "object" or len(form) != 3:
            return form
        items = form[2]
        for i, e in rules:
            if form[1] != e["class"]:
                continue
            if e["kind"] == 5 and e["old"] is None:                   # a field the new class added
                if any(k == e["new"] for k, _ in items):
                    items = [[k, v] for k, v in items if k != e["new"]]
                    self.used[i] += 1
                continue
            names = {e["new"]} if e["kind"] == 5 else set(e["fields"])
            out = []
            for k, v in items:
                if k in names:
                    try:
                        v = transform_form(v, e["transform"], table)
                        self.used[i] += 1
                    except ValueError as exc:
                        result.fail(f"rule entries[{i}] (kind {e['kind']}) on {form[1]}.{k}: {exc}")
                out.append([k, v])
            items = out
        return [form[0], form[1], items]

    def _pair(self, x: dict, y: dict, rules, table, result: Result):
        for i, e in rules:
            if x["function"] != e["function"]:
                continue
            key = e["keyword"]
            if e["kind"] == 8:
                callbacks = [c for c in y.get("bound_callbacks") or [] if c[0] == key]
                if key not in x["bound"] and key in y["bound"] and not callbacks \
                        and _untyped(y["bound"][key]) == _untyped(e["form"]):
                    del y["bound"][key]
                    self.used[i] += 1
            elif e["kind"] == 3:
                if key in y["bound"]:
                    try:
                        y["bound"][key] = transform_form(y["bound"][key], e["transform"], table)
                        self.used[i] += 1
                    except ValueError as exc:
                        result.fail(f"rule entries[{i}] (kind 3) on {e['function']} {key}: {exc}")
            elif key in x["bound"] and key in y["bound"]:                # kind 9: nothing to change
                self.used[i] += 1


def _untyped(form):
    """A form with the Python type of its numbers left out (int and float compare by value, H8)."""
    if isinstance(form, list):
        if len(form) == 3 and form[0] == "num":
            return ["num", form[2]]
        if len(form) == 4 and form[0] == "complex":
            return ["complex", form[2], form[3]]
        return [_untyped(v) for v in form]
    return form


def compare_calls_phase3(old: dict, new: dict, rules: Phase3Rules, result: Result):
    """Every recorded call, bound to its parameter names, under the rule entries."""
    a, b = rules.apply(old.get("calls", []), new.get("calls", []), new.get("transforms", {}), result)
    if len(a) != len(b):
        result.fail(f"calls: {len(a)} recorded on the old side, {len(b)} on the new side (after the rule entries)")
    for i, (x, y) in enumerate(zip(a, b)):
        result.counts["calls"] += 1
        for side, call in (("old", x), ("new", y)):
            if not isinstance(call.get("bound"), dict):
                result.fail(f"calls[{i}] {call.get('function')}: the {side} call does not bind: {call.get('bound')}")
        if set(x) != set(y):
            result.fail(f"calls[{i}] {x.get('function')}: fields {sorted(x)} != {sorted(y)}")
            continue
        for key in PHASE3_CALL_FIELDS:
            if key not in x:
                continue
            if key == "bound" and isinstance(x[key], dict) and isinstance(y[key], dict) and x[key].keys() != y[key].keys():
                result.fail(f"calls[{i}] {x.get('function')}.bound: parameters only on the old side "
                            f"{sorted(set(x[key]) - set(y[key]))}, only on the new side {sorted(set(y[key]) - set(x[key]))}")
                continue
            found = diff_forms(x[key], y[key], f"calls[{i}] {x.get('function')}.{key}", result)
            if found:
                result.fail(found)


def compare_document(doc_id: str, old_dir: Path, new_dir: Path, mode: str, maps: Path,
                     rules: Phase3Rules | None = None) -> Result:
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
    identical = mode in ("identity", "phase3")
    if mode == "phase3" and old.get("document") != new.get("document"):
        result.fail(f"the two sides read different documents: {old.get('document')} != {new.get('document')}")
    if identical:
        for key in ("load",):
            found = diff_forms(old.get(key), new.get(key), key, result)
            if found:
                result.fail(found)
    call_rules, local, lmap = None, (), None
    if mode == "layout":
        lmap = _map_for(old_dir, maps, result)
        if lmap is None:
            return result
        call_rules = lmap.calls
        model = old_dir / "result" / "model.json"
        if model.is_file():
            local = tuple((_load_json(model).get("materials") or {}))
    if mode == "phase3":
        compare_calls_phase3(old, new, rules, result)
    else:
        compare_calls(old, new, result, call_rules, local)
    run_a, run_b = old.get("run", {}), new.get("run", {})
    if identical and run_a.get("after") != run_b.get("after"):
        result.fail(f"diagnostics after the run differ: {run_a.get('after')} != {run_b.get('after')}")
    if run_a.get("status") != run_b.get("status"):
        result.fail(f"run status {run_a.get('status')} != {run_b.get('status')}")
        return result
    if run_a.get("status") == "error":
        if run_a["exception"][0] != run_b["exception"][0]:
            result.fail(f"run error {run_a['exception']} != {run_b['exception']}")
        if identical and run_a["exception"] != run_b["exception"]:
            result.fail(f"run error message {run_a['exception'][1]!r} != {run_b['exception'][1]!r}")
        evidence_a, evidence_b = run_a.get("failure_evidence"), run_b.get("failure_evidence")
        if (evidence_a is None) != (evidence_b is None):
            result.fail("failure evidence recorded on one side only")
        elif evidence_a is not None:
            if identical:
                compare_trees_identity(evidence_a, evidence_b, "failure_evidence", result)
            else:
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
    if identical:
        compare_trees_identity(summary_a, summary_b, "summary.json", result)
        if "model.json" in files_a & files_b:
            compare_trees_identity(_load_json(old_dir / "result" / "model.json"),
                                   _load_json(new_dir / "result" / "model.json"), "model.json", result)
        compare_arrays_identity(arrays_a, arrays_b, result)
        # phase 3 renames no identifier: both sides write today's layouts
        compare_exports(old, new, old_dir, new_dir, None, result,
                        layout_renames(maps) if mode == "identity" else None)
    else:
        compare_trees_layout(summary_a, summary_b, lmap, old, "summary.json", result, (arrays_a, arrays_b))
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


def compare(old: Path, new: Path, plan: dict | None, maps: Path,
            rules: Phase3Rules | None = None) -> tuple[list[Result], list[str]]:
    """Every document of two recordings: ``plan`` None compares them as identical documents;
    ``rules`` (phase 3, ``plan`` None) compares the calls by parameter name under its entries."""
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
        if install.get("targets_shadowed"):
            problems.append(f"{side} side: recorded methods a subclass overrides: {install['targets_shadowed']}")
        if not manifest.get("isolated"):
            problems.append(f"{side} side: the recorder did not run with python -I")
    if plan is not None and set(plan) - set(ids_a):
        problems.append(f"plan names documents not recorded: {sorted(set(plan) - set(ids_a))}")
    if rules is not None:
        problems += rules.check_targets(manifest_a.get("install", {}).get("targets", []),
                                        manifest_b.get("install", {}).get("targets", []))
    results = []
    for doc_id in [d for d in ids_a if d in set(ids_b)]:
        mode = "phase3" if rules is not None else "identity" if plan is None else plan.get(doc_id)
        if mode not in ("identity", "layout", "phase3"):
            problems.append(f"{doc_id}: the plan gives no mode (identity or layout)")
            continue
        results.append(compare_document(doc_id, old / doc_id, new / doc_id, mode, maps, rules))
    if rules is not None:
        problems += rules.unused()
    return results, problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old", type=Path, required=True, help="recording of the baseline")
    parser.add_argument("--new", type=Path, required=True, help="recording of the change")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--identity", action="store_true", help="compare every document with the identity map")
    group.add_argument("--plan", type=Path, help="JSON {document id: 'identity' | 'layout'}")
    group.add_argument("--phase3", action="store_true",
                       help="the galerkin step: the same documents, calls by parameter name under --rules")
    parser.add_argument("--rules", type=Path, default=Path(__file__).resolve().parent / "phase3_rules.json",
                        help="the phase-3 rule entries (default: phase3_rules.json beside this script)")
    parser.add_argument("--maps", type=Path, default=Path(__file__).resolve().parent / "maps")
    parser.add_argument("--report", type=Path, help="write the findings and the SHA-256 tables as JSON")
    args = parser.parse_args(argv)
    plan = None if args.identity or args.phase3 else _load_json(args.plan)
    rules = Phase3Rules.load(args.rules) if args.phase3 else None
    results, problems = compare(args.old, args.new, plan, args.maps, rules)
    equal = sum(r.equal for r in results)
    for r in results:
        types = f", {len(r.type_differences)} type differences" if r.type_differences else ""
        if r.counts["absent_defaults"]:
            types += f", {r.counts['absent_defaults']} absent defaults"
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
        if rules is not None:
            report["rules"] = {"source": rules.source, "entries": rules.entries, "applied": rules.used}
        args.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0 if results and equal == len(results) and not problems else 1


if __name__ == "__main__":
    sys.exit(main())
