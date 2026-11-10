# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The common parts of format 0.3 results: value objects, the summary envelope, field maps.

Every kind's result writer uses these, so that every ``summary.json`` names values the same
way (phase-2 spec section 5.1):

- a scalar is ``{"value": <SI double>, "unit": "<canonical unit>"}``; a list or a series is
  ``{"unit": .., "values": [..]}``; a complex value adds ``"time_convention": "exp(-i omega t)"``
  and is ``{"re", "im", "unit", ...}`` (lists ``"re": [..], "im": [..]``); counts, booleans and
  text stay bare; a value that is not finite is ``null``;
- the envelope adds ``diagnostics`` (every coded diagnostic, from reading to the last
  stage), ``defaults_applied``, ``resolved_inputs``, ``extent`` and
  ``timing.wall_time``;
- ``field_units``, ``field_locations``, ``field_shapes``, ``field_time_axes`` and
  ``field_components`` describe every saved array by its registry name;
- ``model.json`` is the authored bytes of a document read from bytes, otherwise the
  decimal-preserving ``reader.dumps``; ``log.txt`` starts with the extent lines, then the
  summary text, then every diagnostic.

Units come from the registry (``physmat.units``), never from a name suffix.
"""

from __future__ import annotations

import math
from pathlib import Path

from physmat import units

from .diagnostics import render_text
from .reader import dumps

__all__ = ["TIME_CONVENTION", "value_object", "tagged_array", "complex_value", "complex_array", "timing",
           "field_maps", "envelope", "metadata_json", "dumps_summary", "write_model_json", "log_header",
           "add_depth_totals"]

TIME_CONVENTION = "exp(-i omega t)"


def _finite(x):
    x = float(x)
    return x if math.isfinite(x) else None


def _unit(quantity_name: str) -> str:
    return units.quantity(quantity_name).unit


def value_object(value, quantity_name: str) -> dict:
    """``{"value": <SI double or null>, "unit": <canonical unit>}``."""
    return {"value": _finite(value), "unit": _unit(quantity_name)}


def tagged_array(values, quantity_name: str) -> dict:
    """``{"unit": .., "values": [..]}`` of SI doubles (a series or a vector)."""
    return {"unit": _unit(quantity_name), "values": [_finite(v) for v in values]}


def complex_value(value, quantity_name: str) -> dict:
    z = complex(value)
    return {"re": _finite(z.real), "im": _finite(z.imag), "unit": _unit(quantity_name),
            "time_convention": TIME_CONVENTION}


def complex_array(values, quantity_name: str) -> dict:
    zs = [complex(v) for v in values]
    return {"unit": _unit(quantity_name), "re": [_finite(z.real) for z in zs], "im": [_finite(z.imag) for z in zs],
            "time_convention": TIME_CONVENTION}


def timing(mesh_seconds: float, solve_seconds: float) -> dict:
    return {"wall_time": {"mesh": value_object(mesh_seconds, "wall_time"),
                          "solve": value_object(solve_seconds, "wall_time")}}


def field_maps(fields: dict) -> dict:
    """The ``field_*`` maps of saved arrays.

    ``fields`` maps each array name to ``{"quantity": <registry name or None for a
    structural array>, "location": .., "shape": [..], "time_axis": <axis name, optional>,
    "components": [<names>, optional]}``."""
    out = {"field_units": {}, "field_locations": {}, "field_shapes": {}, "field_time_axes": {},
           "field_components": {}}
    for name, spec in fields.items():
        if spec.get("quantity") is not None:
            out["field_units"][name] = _unit(spec["quantity"])
        out["field_locations"][name] = spec["location"]
        out["field_shapes"][name] = list(spec["shape"])
        if spec.get("time_axis") is not None:
            out["field_time_axes"][name] = spec["time_axis"]
        if spec.get("components") is not None:
            out["field_components"][name] = list(spec["components"])
    return out


def envelope(doc, *, result_format: str, field_layout: str, timing_: dict | None = None) -> dict:
    """The keys every format 0.3 summary shares; a kind adds its own results to it."""
    out = {"result_format": result_format, "field_layout": field_layout,
           "diagnostics": [d.as_dict() for d in doc.diagnostics],
           "defaults_applied": list(doc.defaults_applied),
           "resolved_inputs": doc.resolved_inputs(),
           "extent": doc.extent_lines()}
    if timing_ is not None:
        out["timing"] = timing_
    return out


def add_depth_totals(summary: dict, depth) -> None:
    """Beside each per-depth integrated value (a ``*_per_depth`` key), the total for the
    component's ``depth`` in metres under the plain name: ``per_depth x depth``, computed once
    (rule 2.7). With ``depth`` None ("per metre of depth") nothing is added. Keys keep their
    order; each total follows its per-depth value."""
    if depth is None:
        return
    items = list(summary.items())
    summary.clear()
    for key, value in items:
        summary[key] = value
        if not key.endswith("_per_depth") or not isinstance(value, dict):
            continue
        plain = key[:-len("_per_depth")]
        if "value" in value:
            summary[plain] = {"value": None if value["value"] is None else _finite(value["value"] * depth),
                              "unit": _unit(plain)}
        elif "values" in value:
            summary[plain] = {"unit": _unit(plain),
                              "values": [None if v is None else _finite(v * depth) for v in value["values"]]}


def dumps_summary(summary: dict) -> str:
    """``summary.json`` text: decimal preserving, finite numbers only."""
    return dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def metadata_json(summary: dict) -> str:
    """The npz ``metadata_json`` scalar: the summary as compact JSON."""
    return dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False)


def write_model_json(doc, path) -> None:
    """``model.json``: the authored bytes when the document came from bytes, else ``reader.dumps``."""
    if doc.source_bytes is not None:
        Path(path).write_bytes(doc.source_bytes)
    else:
        Path(path).write_text(dumps(doc.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def log_header(doc) -> str:
    """The first lines of ``log.txt`` (and of ``simcase run``): extent, summary, diagnostics."""
    parts = list(doc.extent_lines()) + [doc.summary()]
    text = render_text(doc.diagnostics)
    if text:
        parts.append(text)
    return "\n".join(parts) + "\n"
