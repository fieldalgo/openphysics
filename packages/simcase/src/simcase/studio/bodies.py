# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Request bodies that carry a document, read from their raw bytes, and exact JSON replies.

Every Studio route that takes a document reads the request bytes with ``simcase.reader``
(``read_envelope``): a number keeps its written digits (``Decimal``), and a duplicate key,
``NaN``, ``Infinity``, malformed JSON, a byte that is not UTF-8 or a UTF-16/32 text is refused
with its code (``E-JSON``, ``E-KEY-DUPLICATE``), and so is a string that holds an escaped unpaired
surrogate (``"\\ud800"``: not Unicode text, so no UTF-8 reply could carry it back; the reader refuses
it at its path); a leading UTF-8 byte order mark is accepted.
A reply that returns the document writes it with ``reader.dumps`` (``exact_json``), so an
unchanged authored document comes back byte for byte apart from whitespace and the spelling of
string escapes (``"\\u00b5"`` comes back as ``"µ"``).
"""

from __future__ import annotations

import dataclasses
import re

from fastapi.responses import Response

from simcase import reader

#: a reader message that names its object: ``"x" appears more than once in doc.geometry; ...``
_IN_OBJECT = re.compile(r'^("(?:[^"\\]|\\.)*" appears more than once in )(.*?)(; .*)$', re.S)


def _in_document(d):
    """A reader diagnostic inside the envelope's ``doc`` at its document path (None if outside)."""
    segments = reader.split_path(d.path) if d.path else []
    if not segments or segments[0] != "doc":
        return None
    path = reader.display_path(segments[1:])
    message = d.message
    found = _IN_OBJECT.match(message)
    if found:
        message = found.group(1) + (path or "<document>") + found.group(3)
    return dataclasses.replace(d, path=path, message=message)


def diagnostics(found) -> list[dict]:
    """Coded diagnostics as JSON objects (code, severity, path, message, fix, ...)."""
    return [d.as_dict() for d in found]


def exact_json(payload, status_code: int = 200) -> Response:
    """A JSON reply written with ``reader.dumps``: a document's numbers keep their digits, and a
    tree without ``Decimal`` gives the bytes FastAPI's own JSON reply gives."""
    text = reader.dumps(payload, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return Response(text.encode("utf-8"), status_code=status_code, media_type="application/json",
                    headers={"Cache-Control": "no-store"})


class RequestRefused(Exception):
    """A request whose bytes are not one readable ``{"doc": ...}`` envelope (status 400)."""

    def __init__(self, detail: str, found=()):
        super().__init__(detail)
        self.detail, self.found = detail, list(found)

    def reply(self) -> Response:
        return exact_json({"detail": self.detail, "diagnostics": diagnostics(self.found)}, 400)


def read_envelope(raw: bytes, *, optional=()) -> tuple[dict, list]:
    """``(envelope, document diagnostics)`` of a request body ``{"doc": {...}}`` (and the
    ``optional`` keys). Unreadable text (``E-JSON``: malformed, ``NaN``, ``Infinity``, not UTF-8, a
    string with an escaped unpaired surrogate) and a refusal outside ``doc`` raise ``RequestRefused``;
    a duplicate key or an oversized number inside ``doc`` is returned as a diagnostic of the document,
    at its document path."""
    tree, found = reader.parse(raw)
    if tree is None:
        raise RequestRefused("the request is not readable JSON: " + "; ".join(
            f"{d.path}: {d.message}" if d.path else d.message for d in found), found)
    inside = [_in_document(d) for d in found]
    outside = [d for d, mapped in zip(found, inside) if mapped is None]
    if outside:
        raise RequestRefused("the request envelope: " + "; ".join(d.message for d in outside), outside)
    if not isinstance(tree, dict) or "doc" not in tree or set(tree) - {"doc", *optional}:
        allowed = ", ".join(["doc", *optional])
        raise RequestRefused(f"the request body is a JSON object with the keys {allowed} (doc required)")
    if not isinstance(tree["doc"], dict):
        raise RequestRefused("doc: a document is a JSON object")
    return tree, [d for d in inside if d is not None]
