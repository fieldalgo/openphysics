# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The exact JSON reader and writer of model documents.

    tree = reader.loads(text)          # bytes or str; numbers as written, refusals coded
    tree = reader.load(path)
    tree = reader.read(obj)            # a Python object, read the way its JSON text would be
    text = reader.dumps(tree)          # decimal preserving
    doc, diagnostics = reader.check(text)   # resolve a document without raising

Reading keeps every number exact: a JSON number with a fraction or an exponent becomes a
``decimal.Decimal`` of its text, an integer an ``int``. ``NaN``, ``Infinity``, a duplicate
key at any depth, an undecodable byte and a UTF-16 or UTF-32 text are refused with
``E-JSON`` or ``E-KEY-DUPLICATE``; a leading UTF-8 byte order mark is accepted and dropped. A
number literal longer than ``MAX_NUMBER_CHARS`` characters is ``E-DOMAIN`` at its path
before any arithmetic, so a huge literal costs nothing. A Python float is read through its
shortest ``repr``, so ``0.1`` means the decimal 0.1 as the JSON text ``0.1`` does.

``dumps`` writes what ``json.dumps`` writes, with the same arguments and defaults, and writes
a ``Decimal`` as its own digits, with the exponent where and as ``json.dumps`` writes a
float's (below 1e-4 and from 1e16: ``2e-05``); a tree without ``Decimal`` gives byte-identical
output, and a float read through its ``repr`` is written back as ``json.dumps`` writes it.

Only the standard library is imported here.
"""

from __future__ import annotations

import json
import math
import numbers
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from physmat.units import Diagnostic

from .diagnostics import DocumentError

__all__ = ["loads", "load", "read", "dumps", "parse", "check", "display_path", "split_path", "json_pointer",
           "MAX_NUMBER_CHARS"]

#: the longest number literal read; a double needs 17 significant digits, and an exact
#: decimal expansion of any double fits in this length
MAX_NUMBER_CHARS = 1000

_BOMS = ((b"\x00\x00\xfe\xff", "UTF-32"), (b"\xff\xfe\x00\x00", "UTF-32"), (b"\xfe\xff", "UTF-16"),
         (b"\xff\xfe", "UTF-16"))
_PLAIN_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


# -- paths ----------------------------------------------------------------------------------------

def display_path(segments) -> str:
    """``materials["n3.40"].refractive_index``: keys that are not plain names (letters, digits,
    ``_`` and ``-``, not starting with a digit or ``-``) are quoted."""
    out = ""
    for s in segments:
        if isinstance(s, int):
            out += f"[{s}]"
        elif _PLAIN_KEY.fullmatch(s):
            out += f".{s}" if out else s
        else:
            out += "[" + json.dumps(s, ensure_ascii=False) + "]"
    return out


_PATH_TOKEN = re.compile(r'\.?([A-Za-z_][A-Za-z0-9_-]*)|\[(\d+)\]|\[("(?:[^"\\]|\\.)*")\]')


def split_path(path: str) -> list:
    """The segments of a display path (``display_path`` inverted)."""
    segments, pos = [], 0
    while pos < len(path):
        m = _PATH_TOKEN.match(path, pos)
        if m is None or m.end() == pos:
            raise ValueError(f"not a document path: {path!r}")
        name, index, quoted = m.groups()
        segments.append(name if name is not None else int(index) if index is not None else json.loads(quoted))
        pos = m.end()
    return segments


def json_pointer(segments) -> str:
    """The RFC 6901 JSON Pointer of a path (``/materials/n3.40/refractive_index``)."""
    return "".join("/" + str(s).replace("~", "~0").replace("/", "~1") for s in segments)


# -- reading --------------------------------------------------------------------------------------

class _Oversized:
    """A number literal too long to read; reported at its path after the parse."""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text


class _Duplicated(dict):
    """An object that had a duplicate key; the first value of each key is kept."""

    duplicates: list


class _Constant(Exception):
    pass


def _number(kind):
    def parse(text: str):
        if len(text) > MAX_NUMBER_CHARS:
            return _Oversized(text)
        return kind(text)
    return parse


def _constant(name: str):
    raise _Constant(name)


def _pairs(pairs):
    out, duplicates = {}, []
    for key, value in pairs:
        if key in out:
            duplicates.append(key)
            continue
        out[key] = value
    if duplicates:
        out = _Duplicated(out)
        out.duplicates = duplicates
    return out


def _decode(raw) -> tuple[str | None, Diagnostic | None]:
    if isinstance(raw, str):
        return (raw[1:] if raw.startswith("﻿") else raw), None
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise TypeError("a document text is str or bytes")
    raw = bytes(raw)
    for bom, name in _BOMS:
        if raw.startswith(bom):
            return None, Diagnostic("E-JSON", "", f"the document is {name} text; save it as UTF-8")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return None, Diagnostic("E-JSON", "", f"byte 0x{raw[exc.start]:02x} at offset {exc.start} is not UTF-8; "
                                              "save the document as UTF-8")


def parse(raw) -> tuple[Any, list[Diagnostic]]:
    """``(tree, diagnostics)`` of a document text (bytes or str); the tree is None on a JSON error."""
    text, problem = _decode(raw)
    if problem is not None:
        return None, [problem]
    try:
        tree = json.loads(text, parse_float=_number(Decimal), parse_int=_number(int), parse_constant=_constant,
                          object_pairs_hook=_pairs)
    except _Constant as exc:
        return None, [Diagnostic("E-JSON", "", f"{exc.args[0]} is not JSON; a document holds finite numbers only")]
    except json.JSONDecodeError as exc:
        return None, [Diagnostic("E-JSON", "", f"not valid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}")]
    except RecursionError:
        return None, [Diagnostic("E-JSON", "", "the JSON nesting is too deep")]
    found: list[Diagnostic] = []
    return _clean(tree, [], found), found


def _clean(node, segments, found):
    """Replace the parse markers by values and report them at their paths."""
    if isinstance(node, dict):
        if isinstance(node, _Duplicated):
            where = display_path(segments) or "<document>"
            for key in node.duplicates:
                found.append(Diagnostic("E-KEY-DUPLICATE", display_path(segments),
                                        f'"{key}" appears more than once in {where}; JSON readers disagree on '
                                        "which one counts, so a document gives each key once"))
        return {k: _clean(v, segments + [k], found) for k, v in node.items()}
    if isinstance(node, list):
        return [_clean(v, segments + [i], found) for i, v in enumerate(node)]
    if isinstance(node, _Oversized):
        found.append(Diagnostic("E-DOMAIN", display_path(segments),
                                f"a number of {len(node.text)} characters is longer than the {MAX_NUMBER_CHARS} "
                                "this reader takes"))
        return None
    return node


def loads(raw):
    """The authored tree of a document text; raises ``DocumentError`` on a refusal."""
    tree, found = parse(raw)
    if found:
        raise DocumentError("the document is not readable JSON", diagnostics=found)
    return tree


def load(path):
    return loads(Path(path).read_bytes())


def read(obj) -> Any:
    """A Python object as the authored tree its JSON text would give; raises ``DocumentError``."""
    found: list[Diagnostic] = []
    tree = _read(obj, [], found, set())
    if found:
        raise DocumentError("the document is not a JSON value", diagnostics=found)
    return tree


def read_with_diagnostics(obj) -> tuple[Any, list[Diagnostic]]:
    found: list[Diagnostic] = []
    tree = _read(obj, [], found, set())
    return (None if found else tree), found


def _read(node, segments, found, active):
    where = display_path(segments)
    if node is None or isinstance(node, (bool, str)):
        return node
    if isinstance(node, numbers.Integral):
        return int(node)
    if isinstance(node, Decimal):
        if not node.is_finite():
            found.append(Diagnostic("E-JSON", where, f"{node} is not JSON; a document holds finite numbers only"))
            return None
        return node
    if isinstance(node, numbers.Real):
        x = float(node)
        if not math.isfinite(x):
            found.append(Diagnostic("E-JSON", where, f"{x!r} is not JSON; a document holds finite numbers only"))
            return None
        return Decimal(float.__repr__(x))
    if isinstance(node, (dict, list, tuple)):
        if id(node) in active:
            found.append(Diagnostic("E-JSON", where, "the object contains itself"))
            return None
        active.add(id(node))
        try:
            if isinstance(node, dict):
                out = {}
                for k, v in node.items():
                    if not isinstance(k, str):
                        found.append(Diagnostic("E-JSON", where, f"key {k!r} is not a string; JSON keys are strings"))
                        continue
                    out[k] = _read(v, segments + [k], found, active)
                return out
            return [_read(v, segments + [i], found, active) for i, v in enumerate(node)]
        finally:
            active.discard(id(node))
    found.append(Diagnostic("E-JSON", where, f"a {type(node).__name__} is not a JSON value"))
    return None


# -- writing --------------------------------------------------------------------------------------

def dumps(obj, *, indent=None, separators=None, sort_keys: bool = False, ensure_ascii: bool = True,
          allow_nan: bool = True) -> str:
    """``json.dumps`` with the same arguments, that also writes a ``Decimal`` as its text."""
    if separators is None:
        separators = (",", ": ") if indent is not None else (", ", ": ")
    item_sep, key_sep = separators
    if isinstance(indent, int):
        indent = " " * indent

    def string(s: str) -> str:
        return json.dumps(s, ensure_ascii=ensure_ascii)

    def number(text: str, value) -> str:
        if not allow_nan:
            raise ValueError("Out of range float values are not JSON compliant: " + repr(value))
        return text

    def floating(x: float) -> str:
        if x != x:
            return number("NaN", x)
        if x == math.inf:
            return number("Infinity", x)
        if x == -math.inf:
            return number("-Infinity", x)
        return float.__repr__(x)

    def decimal(d: Decimal) -> str:
        if d.is_nan():
            return number("NaN", d)
        if d.is_infinite():
            return number("Infinity" if d > 0 else "-Infinity", d)
        # the exponent where and as json.dumps writes a float's (repr: below 1e-4 and from 1e16):
        # 2e-05, 1e-10 and 1.5e+16, not Decimal's 0.00002, 1E-10 and 15000000000000000
        if d and not -4 <= d.adjusted() < 16:
            sign, digits, _ = d.as_tuple()
            text = "".join(map(str, digits))
            mantissa = text[0] + ("." + text[1:] if len(text) > 1 else "")
            return f"{'-' if sign else ''}{mantissa}e{'-' if d.adjusted() < 0 else '+'}{abs(d.adjusted()):02d}"
        return str(d).replace("E", "e")

    def key(k) -> str | None:
        if isinstance(k, str):
            return k
        if isinstance(k, float):
            return floating(k)
        if k is True:
            return "true"
        if k is False:
            return "false"
        if k is None:
            return "null"
        if isinstance(k, int):
            return int.__repr__(k)
        raise TypeError(f"keys must be str, int, float, bool or None, not {type(k).__name__}")

    markers: set[int] = set()
    parts: list[str] = []

    def encode(o, level: int) -> None:
        if isinstance(o, str):
            parts.append(string(o))
        elif o is None:
            parts.append("null")
        elif o is True:
            parts.append("true")
        elif o is False:
            parts.append("false")
        elif isinstance(o, int):
            parts.append(int.__repr__(o))
        elif isinstance(o, float):
            parts.append(floating(o))
        elif isinstance(o, Decimal):
            parts.append(decimal(o))
        elif isinstance(o, (list, tuple)):
            if not o:
                parts.append("[]")
                return
            if id(o) in markers:
                raise ValueError("Circular reference detected")
            markers.add(id(o))
            inner = "" if indent is None else "\n" + indent * (level + 1)
            sep = item_sep if indent is None else item_sep + inner
            parts.append("[" + inner)
            for i, v in enumerate(o):
                if i:
                    parts.append(sep)
                encode(v, level + 1)
            parts.append("" if indent is None else "\n" + indent * level)
            parts.append("]")
            markers.discard(id(o))
        elif isinstance(o, dict):
            if not o:
                parts.append("{}")
                return
            if id(o) in markers:
                raise ValueError("Circular reference detected")
            markers.add(id(o))
            inner = "" if indent is None else "\n" + indent * (level + 1)
            sep = item_sep if indent is None else item_sep + inner
            parts.append("{" + inner)
            items = sorted(o.items()) if sort_keys else o.items()
            first = True
            for k, v in items:
                if not first:
                    parts.append(sep)
                first = False
                parts.append(string(key(k)))
                parts.append(key_sep)
                encode(v, level + 1)
            parts.append("" if indent is None else "\n" + indent * level)
            parts.append("}")
            markers.discard(id(o))
        else:
            raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    encode(obj, 0)
    return "".join(parts)


# -- documents ------------------------------------------------------------------------------------

def check(raw):
    """``(document or None, diagnostics)`` of a document text, a path or a Python object,
    without raising for a refused document (``simcase validate``, ``explain``, ``fix``)."""
    from .resolve import resolve_text, resolve_tree
    if isinstance(raw, Path):
        result = resolve_text(raw.read_bytes())
    elif isinstance(raw, (str, bytes, bytearray, memoryview)):
        result = resolve_text(raw)
    else:
        result = resolve_tree(raw, from_python=True)
    return result.document(), list(result.diagnostics)
