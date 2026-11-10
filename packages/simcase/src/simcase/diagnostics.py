# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Coded diagnostics of a document, from reading to the last result.

A diagnostic is ``physmat.units.Diagnostic``: ``{code, severity, path, message, fix,
suggestions, acknowledged}``, with a code from the registry's closed list. A document keeps
its diagnostics in one ``DiagnosticList``, which only grows: no stage clears what another
stage found.

``DocumentError`` and ``GeometryError`` carry diagnostics too. Built from one message, as
every kind refusal is, ``str()`` is exactly that message and the error is one ``E-CONTRACT``
diagnostic. Built from the reader's diagnostics, ``str()`` has one line per error.

Only the standard library and ``physmat.units`` are imported here.
"""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Iterable

from physmat.units import DIAGNOSTIC_CODES, Diagnostic

__all__ = ["CodedError", "DocumentError", "DiagnosticList", "contract", "acknowledge", "from_exception",
           "exit_code", "render_text", "render_json", "error_lines"]

#: an info diagnostic that ``--strict`` refuses like a warning (answer 3.8)
STRICT_INFOS = frozenset({"I-DATUM-ASSUMED"})


def error_lines(diagnostics: Iterable[Diagnostic]) -> list[str]:
    """One line per error: an ``E-CONTRACT`` message as it is (it names its own path), any
    other code as ``<path>: <message> (<code>)``, because registry messages do not name it."""
    lines = []
    for d in diagnostics:
        if d.severity != "error":
            continue
        message = " ".join(d.message.split("\n"))
        if d.code == "E-CONTRACT":
            lines.append(message)
        else:
            lines.append(f"{d.path}: {message} ({d.code})" if d.path else f"{message} ({d.code})")
    return lines


class CodedError(ValueError):
    """A refusal with a code and a JSON path, and the diagnostics behind it.

    ``CodedError(message)`` keeps the single-message form every raise site uses: ``str()``
    is the message and ``diagnostics`` holds one diagnostic of ``code`` at ``path``. With
    ``diagnostics``, ``str()`` is one line per error diagnostic (``error_lines``)."""

    def __init__(self, message: str = "", *, path: str | None = None, code: str = "E-CONTRACT",
                 diagnostics: Iterable[Diagnostic] = ()):
        found = tuple(diagnostics)
        text = message
        if found:
            lines = error_lines(found)
            if lines:
                text = "\n".join(lines)
                first = next(d for d in found if d.severity == "error")
                path, code = (first.path or None), first.code
        else:
            if code not in DIAGNOSTIC_CODES:
                raise ValueError(f"unknown diagnostic code {code!r}")
            found = (Diagnostic(code, path or "", message),)
        super().__init__(text)
        self.message = message
        self.path = path
        self.code = code
        self.diagnostics = found


class DocumentError(CodedError):
    """A document that this reader or its physics kind does not accept."""


def contract(message: str, path: str = "") -> Diagnostic:
    """A kind refusal as an ``E-CONTRACT`` diagnostic."""
    return Diagnostic("E-CONTRACT", path, message)


def acknowledge(diagnostic: Diagnostic, reason: str) -> Diagnostic:
    """The same diagnostic, marked acknowledged with ``reason``; errors cannot be."""
    if diagnostic.severity == "error":
        raise ValueError("an error cannot be acknowledged")
    return dataclasses.replace(diagnostic, acknowledged=reason)


#: a refusal message that starts with the path it refuses (``physics.heat1.convection.top: ...``)
_LEADING_PATH = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*|\[\d+\]|\["[^"]*"\])*):\s')


def from_exception(exc: BaseException) -> tuple[Diagnostic, ...]:
    """The diagnostics of a refusal. A single-message refusal is one diagnostic of its code; its
    path is the one it was given, or the path its message starts with."""
    found = tuple(getattr(exc, "diagnostics", ()) or ())
    if not found:
        found = (contract(str(exc), getattr(exc, "path", None) or ""),)
    out = []
    for d in found:
        if not d.path:
            m = _LEADING_PATH.match(d.message)
            if m is not None:
                d = dataclasses.replace(d, path=m.group(1))
        out.append(d)
    return tuple(out)


class DiagnosticList:
    """An append-only list of diagnostics. There is no way to remove or replace an entry."""

    __slots__ = ("_items",)

    def __init__(self, items: Iterable[Diagnostic] = ()):
        self._items: list[Diagnostic] = []
        self.extend(items)

    def append(self, diagnostic: Diagnostic) -> None:
        if not isinstance(diagnostic, Diagnostic):
            raise TypeError("a diagnostic is a physmat.units.Diagnostic")
        if diagnostic.code not in DIAGNOSTIC_CODES:
            raise ValueError(f"unknown diagnostic code {diagnostic.code!r}")
        self._items.append(diagnostic)

    def extend(self, diagnostics: Iterable[Diagnostic]) -> None:
        for d in diagnostics:
            self.append(d)

    def __iter__(self):
        return iter(tuple(self._items))

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index):
        return tuple(self._items)[index]

    def __repr__(self) -> str:
        return f"DiagnosticList({len(self._items)} entries)"

    def copy(self) -> "DiagnosticList":
        return DiagnosticList(self._items)

    def of_severity(self, severity: str) -> list[Diagnostic]:
        return [d for d in self._items if d.severity == severity]

    @property
    def errors(self) -> list[Diagnostic]:
        return self.of_severity("error")

    @property
    def warnings(self) -> list[Diagnostic]:
        return self.of_severity("warning")

    @property
    def infos(self) -> list[Diagnostic]:
        return self.of_severity("info")

    def as_dicts(self) -> list[dict]:
        return [d.as_dict() for d in self._items]


def exit_code(diagnostics: Iterable[Diagnostic], strict: bool = False) -> int:
    """2 with any error; 3 under ``strict`` with an unacknowledged warning or a strict info; else 0."""
    found = list(diagnostics)
    if any(d.severity == "error" for d in found):
        return 2
    if strict and any((d.severity == "warning" and d.acknowledged is None) or d.code in STRICT_INFOS
                      for d in found):
        return 3
    return 0


def render_text(diagnostics: Iterable[Diagnostic]) -> str:
    """Every diagnostic as physmat prints it, with its acknowledgement."""
    blocks = []
    for d in diagnostics:
        text = str(d)
        if d.acknowledged is not None:
            text += f"\n  Acknowledged: {d.acknowledged}"
        blocks.append(text)
    return "\n".join(blocks)


def render_json(diagnostics: Iterable[Diagnostic]) -> str:
    return json.dumps([d.as_dict() for d in diagnostics], indent=2, ensure_ascii=False)
