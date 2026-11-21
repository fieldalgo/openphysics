# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``simcase fix``: apply the value-preserving fixes of a format 0.3 document.

A fix keeps every SI value (``"25K"`` -> ``"25 K"``, ``"12 ppm/degC"`` -> ``"12 ppm/K"``, ``2.0``
-> ``2`` for a count, ``"1 µm"`` -> ``"1 um"``); a suggestion may change the meaning and is
never applied here. Each fix replaces only the JSON string or number token at its path, found
by a scanner that records where every value of the text starts and ends, so every other byte
(spacing, key order, line endings, a byte order mark) stays as it was. The result is read
again, and it is refused unless every SI value the original document resolved is
bit-identical.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal

from .reader import display_path

__all__ = ["FixReport", "apply_fixes", "value_spans"]

_WS = " \t\n\r"
_BOM = "﻿"


class _Scanner:
    """Records ``(start, end)`` of every value in a JSON text by its display path."""

    def __init__(self, text: str):
        self.t, self.i, self.spans = text, 0, {}

    def ws(self) -> None:
        while self.i < len(self.t) and self.t[self.i] in _WS:
            self.i += 1

    def string(self) -> str:
        start = self.i
        self.i += 1
        while self.t[self.i] != '"':
            self.i += 2 if self.t[self.i] == "\\" else 1
        self.i += 1
        return json.loads(self.t[start:self.i])

    def value(self, path) -> None:
        self.ws()
        c = self.t[self.i]
        if c == "{":
            self.i += 1
            self.ws()
            if self.t[self.i] == "}":
                self.i += 1
                return
            while True:
                self.ws()
                key = self.string()
                self.ws()
                self.i += 1                              # ':'
                self.value(path + [key])
                self.ws()
                c = self.t[self.i]
                self.i += 1
                if c == "}":
                    return
        if c == "[":
            self.i += 1
            self.ws()
            if self.t[self.i] == "]":
                self.i += 1
                return
            index = 0
            while True:
                self.value(path + [index])
                index += 1
                self.ws()
                c = self.t[self.i]
                self.i += 1
                if c == "]":
                    return
        start = self.i
        if c == '"':
            self.string()
        else:
            while self.i < len(self.t) and self.t[self.i] not in ",]}" + _WS:
                self.i += 1
        self.spans[display_path(path)] = (start, self.i)


def value_spans(text: str) -> dict[str, tuple[int, int]]:
    """``{path: (start, end)}`` of every value of a valid JSON text (without a byte order mark)."""
    scanner = _Scanner(text)
    scanner.value([])
    return scanner.spans


def _token(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (float, Decimal)):
        return repr(float(value)) if isinstance(value, float) else str(value)
    raise TypeError(f"a fix value is a string or a number, not {type(value).__name__}")


@dataclass
class FixReport:
    """What ``apply_fixes`` did: the new bytes (None when nothing may be written) and why."""
    data: bytes | None
    applied: list = field(default_factory=list)          # {"path", "written", "fix", "code"}
    suggestions: list = field(default_factory=list)      # diagnostics with suggestions only, not applied
    problems: list = field(default_factory=list)         # why the result is refused
    readable: bool = True                                # False: the text is no readable JSON


def _si_leaves(node, path="", out=None) -> dict:
    out = {} if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            _si_leaves(v, f"{path}.{k}" if path else k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _si_leaves(v, f"{path}[{i}]", out)
    elif isinstance(node, float):
        out[path] = float.hex(node)
    elif isinstance(node, complex):
        out[path] = (float.hex(node.real), float.hex(node.imag))
    elif node is not None:
        out[path] = repr(node)
    return out


def apply_fixes(raw: bytes) -> FixReport:
    """Apply every fix of a document text; refuse unless its resolved SI values stay bit-identical."""
    from .resolve import resolve_text
    before = resolve_text(raw)
    if before.tree is None:
        return FixReport(None, problems=[str(d) for d in before.diagnostics], readable=False)
    text = raw.decode("utf-8")
    bom = text.startswith(_BOM)
    body = text[1:] if bom else text
    spans = value_spans(body)
    wanted = [(d.path, d.fix.value, d.code) for d in before.diagnostics if d.fix is not None]
    wanted += [(f["path"], f["fix"], "spelling") for f in before.spelling_fixes]
    edits, report = {}, FixReport(None)
    report.suggestions = [d for d in before.diagnostics if d.fix is None and d.suggestions]
    for path, value, code in wanted:
        span = spans.get(path)
        if span is None or path in edits:
            report.problems.append(f"{path}: no value token for the fix {value!r}")
            continue
        edits[path] = (span, _token(value))
        report.applied.append({"path": path, "written": body[span[0]:span[1]], "fix": value, "code": code})
    out = body
    for (start, end), token in sorted(edits.values(), reverse=True):
        out = out[:start] + token + out[end:]
    data = ((_BOM if bom else "") + out).encode("utf-8")
    after = resolve_text(data)
    old, new = _si_leaves(before.si), _si_leaves(after.si)
    for path, leaf in old.items():
        if new.get(path) != leaf:
            report.problems.append(f"{path}: the resolved value changed ({leaf} -> {new.get(path)})")
    if not report.problems:
        report.data = data
    return report
