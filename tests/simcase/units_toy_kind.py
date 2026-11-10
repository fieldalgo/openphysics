# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A test-only physics kind that reads format 0.3, for the shared reader's tests.

No built-in kind claims format 0.3 until its own commit of the units batch, so the reader,
the slot table and the command line are tested on ``toy.bar``: a kind with a few physics
slots of every value form, a contract refusal, an info diagnostic of its own and a runner
that writes the common result files. ``registered()`` adds it to the registry for one test
and removes it afterwards; nothing outside the tests sees it.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from physmat.units import Diagnostic

from simcase import registry
from simcase.diagnostics import DocumentError
from simcase import results_common

NAME = "toy"
TYPE = "toy.bar"
P = "physics.*{toy.bar}"


def _q(key, quantity, forms, **extra):
    return {"pattern": f"{P}.{key}", "kind": "quantity", "quantity": quantity, "forms": list(forms), **extra}


SLOTS = (
    {"pattern": f"{P}.type", "kind": "enum", "values": [TYPE], "required": True},
    {"pattern": f"{P}.youngs_modulus", "kind": "material_property", "quantity": "youngs_modulus",
     "forms": ["QS", "AV"]},
    {"pattern": f"{P}.poisson_ratio", "kind": "material_property", "quantity": "poisson_ratio", "forms": ["BD", "AV"]},
    {"pattern": f"{P}.relative_permittivity", "kind": "material_property", "quantity": "relative_permittivity",
     "forms": ["BD", "CX"]},
    {"pattern": f"{P}.prescribed_temperature", "kind": "structural", "forms": ["OBJECT"]},
    _q("prescribed_temperature.*", "prescribed_temperature", ("QS", "AV", "TA")),
    _q("ambient_temperature", "ambient_temperature", ("QS", "AV")),
    {"pattern": f"{P}.inward_heat_flux", "kind": "structural", "forms": ["OBJECT"]},
    _q("inward_heat_flux.*", "inward_heat_flux", ("QS", "AV")),
    _q("vacuum_wavelength", "vacuum_wavelength", ("QS", "AV")),
    _q("gauge_pressure", "gauge_pressure", ("QS", "AV")),
    _q("mode_count", "mode_count", ("BC",), default=1, default_reason="count default"),
    {"pattern": f"{P}.prescribed_displacement", "kind": "structural", "forms": ["OBJECT"]},
    _q("prescribed_displacement.*", "prescribed_displacement", ("CO",), components=["x", "y"]),
    {"pattern": f"{P}.traction", "kind": "structural", "forms": ["OBJECT"]},
    _q("traction.*", "traction", ("SL", "TA")),
    {"pattern": f"{P}.boundary", "kind": "structural", "forms": ["OBJECT"]},
    {"pattern": f"{P}.boundary.*", "kind": "enum", "values": ["fixed", "free"]},
    {"pattern": f"{P}.absolute_pressure", "kind": "refused", "code": "E-ABSOLUTE-AS-LOAD",
     "message": "a load is a gauge pressure; absolute_pressure = gauge + ambient is not a load"},
    {"pattern": f"{P}.allow_gain", "kind": "refused", "code": "E-CONTRACT",
     "message": "allow_gain is refused: this solver is passive only"},
    {"pattern": "name", "kind": "override", "default": "untitled", "default_reason": "structural default"},
    {"pattern": "results", "kind": "override", "default": {"save_fields": True, "plots": False},
     "default_reason": "structural default of toy.bar"},
    {"pattern": "materials.*", "kind": "override", "library": "any",
     "reads": {TYPE: ["youngs_modulus", "poisson_ratio", "refractive_index"]}},
)

#: the contract refusal the kind raises, as every kind raises today (one message)
STIFF = "physics.{name}.youngs_modulus: a toy bar is softer than 1 TPa"


def validate(doc) -> None:
    name, entry = next(iter(doc.si["physics"].items()))
    if entry.get("youngs_modulus") is not None and entry["youngs_modulus"] > 1e12:
        raise DocumentError(STIFF.format(name=name))
    sides = entry.get("boundary") or {}
    for side in ("left", "right"):
        if side not in sides:
            path = f"physics.{name}.boundary.{side}"
            doc.diagnostics.append(Diagnostic("I-DEFAULT-BOUNDARY", path, f"{path} is omitted: it is free"))


def summary(doc) -> str:
    return f"{doc.si.get('name', 'untitled')}  (openphysics 0.3, toy.bar)"


class ToyResult:
    result_format = "toy.bar-result-v1"
    field_layout = "toy-bar-v1"

    def __init__(self, doc):
        self.doc = doc

    def summary(self) -> dict:
        return results_common.envelope(self.doc, result_format=self.result_format, field_layout=self.field_layout,
                                       timing_=results_common.timing(0.0, 0.0))

    def save(self, out) -> Path:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / "summary.json").write_text(results_common.dumps_summary(self.summary()), encoding="utf-8")
        results_common.write_model_json(self.doc, out / "model.json")
        (out / "log.txt").write_text(results_common.log_header(self.doc), encoding="utf-8")
        return out


def run(doc, verbose=True, **_):
    return ToyResult(doc)


def kind() -> registry.PhysicsKind:
    return registry.PhysicsKind(name=NAME, types=frozenset({TYPE}), precedence=99, validate=validate, run=run,
                                summary=summary, result_types=(ToyResult,), slots=SLOTS)


@contextlib.contextmanager
def registered():
    """The toy kind in the registry for the duration of a ``with`` block."""
    registry.kinds()
    registry.register(kind())
    try:
        yield
    finally:
        registry._KINDS.pop(NAME, None)


def document(**changes) -> dict:
    """A valid toy document on a flat regions block, as authored JSON values."""
    doc = {
        "openphysics": "0.3", "name": "toy bar",
        "geometry": {"length_unit": "mm", "depth": None,
                     "domain": {"xmin": 0, "xmax": 40, "ymin": 0, "ymax": 20},
                     "background": {"material": "steel"},
                     "shapes": [{"name": "core", "type": "rect", "x": 5, "y": 5, "w": 30, "h": 6,
                                 "material": "steel", "element_size": "1 mm"}]},
        "materials": {"steel": {"youngs_modulus": "200 GPa", "poisson_ratio": 0.3, "source": "test value"}},
        "physics": {"bar": {"type": TYPE, "youngs_modulus": "200 GPa", "poisson_ratio": 0.3,
                            "prescribed_temperature": {"left": "300 K"},
                            "boundary": {"left": "fixed", "right": "free"}}},
        "mesh": {"element_size": "2 mm"},
        "study": {"type": "single"},
    }
    for path, value in changes.items():
        node = doc
        parts = path.split("__")
        for part in parts[:-1]:
            node = node[part]
        if value is _DELETE:
            del node[parts[-1]]
        else:
            node[parts[-1]] = value
    return doc


_DELETE = object()
DELETE = _DELETE


def text(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False)
