# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Flat shape numbers reach the mesher on the 1 pm grid (format 0.3, document format "Shape
numbers").

A shape or domain number off the grid is reported (``I-``/``W-PM-ROUNDING``) and stored as its
pm count. The mesher must receive that stored value, so the document meshes exactly as the same
document written on the grid. The off-grid numbers are made with Fraction arithmetic,
independently of the reader. A one-picometre move on the grid is the negative control: it must
change the hand-off, so the equalities below are not vacuous.
"""
import copy
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from simcase import Document
from simcase.modes_document import kernel_document
from simcase.runner import build_mesh
from simcase.thermal_regions import build_region_mesh_03, handoff_03

ROOT = Path(__file__).resolve().parents[2]
PM_PER_UNIT = {"mm": 10 ** 9, "um": 10 ** 6, "nm": 10 ** 3}


def _load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _moved(data, where, shift_pm):
    """A copy of ``data`` with the shape number at ``where`` (keys and indices below
    ``geometry``) moved by ``shift_pm`` picometres, written as a double in the document unit."""
    out = copy.deepcopy(data)
    node = out["geometry"]
    for key in where[:-1]:
        node = node[key]
    unit = out["geometry"]["length_unit"]
    node[where[-1]] = float(Fraction(repr(node[where[-1]])) + Fraction(shift_pm) / PM_PER_UNIT[unit])
    return out


def _path(where):
    return "geometry" + "".join(f"[{k}]" if isinstance(k, int) else f".{k}" for k in where)


def _same_mesh(a, b):
    for attr in ("nodes", "triangles", "regions"):
        x, y = getattr(a, attr), getattr(b, attr)
        assert x.dtype == y.dtype and x.tobytes() == y.tobytes(), attr
    assert a.region_names == b.region_names


REGION_CASES = [
    ("examples/simcase/thermal_regions.json", ("shapes", 0, "x"), Fraction(3, 10)),
    ("examples/simcase/thermal_regions.json", ("shapes", 1, "r"), Fraction(-4, 10)),
    ("tools/units_batch/fixtures/v03/heat_regions_canonical_steady.json", ("shapes", 2, "points", 0, 1),
     Fraction(3, 10)),
    ("tools/units_batch/fixtures/v03/mechanics_r2_flat_strain.json", ("domain", "xmax"), Fraction(-3, 10)),
]


@pytest.mark.parametrize("relative, where, shift", REGION_CASES)
def test_an_off_grid_region_number_is_meshed_at_its_grid_value(relative, where, shift):
    data = _load(relative)
    on_grid = Document.from_dict(copy.deepcopy(data))
    off_grid = Document.from_dict(_moved(data, where, shift))
    assert [(d.code, d.path) for d in off_grid.diagnostics if d.code.endswith("PM-ROUNDING")] == [
        ("W-PM-ROUNDING", _path(where))]
    assert off_grid.pm(_path(where)) == on_grid.pm(_path(where))
    assert handoff_03(off_grid).data["geometry"] == handoff_03(on_grid).data["geometry"]
    _same_mesh(build_region_mesh_03(off_grid)[0], build_region_mesh_03(on_grid)[0])
    control = Document.from_dict(_moved(data, where, 1))       # one picometre on the grid
    assert handoff_03(control).data["geometry"] != handoff_03(on_grid).data["geometry"]


EM_CASES = [
    ("examples/simcase/vector_slab.json", ("shapes", 0, "h"), Fraction(3, 10)),
    ("tools/units_batch/fixtures/v03/em_length_nm_vector_slab.json", ("shapes", 0, "h"), Fraction(-3, 10)),
    ("examples/simcase/hadley_rib.json", ("domain", "ymax"), Fraction(4, 10)),
]


@pytest.mark.parametrize("relative, where, shift", EM_CASES)
def test_an_off_grid_waveguide_number_reaches_the_kernel_at_its_grid_value(relative, where, shift):
    data = _load(relative)
    on_grid = Document.from_dict(copy.deepcopy(data))
    off_grid = Document.from_dict(_moved(data, where, shift))
    assert [(d.code, d.path) for d in off_grid.diagnostics if d.code.endswith("PM-ROUNDING")] == [
        ("W-PM-ROUNDING", _path(where))]
    assert kernel_document(off_grid).data["geometry"] == kernel_document(on_grid).data["geometry"]
    _same_mesh(build_mesh(off_grid).tri, build_mesh(on_grid).tri)
    control = Document.from_dict(_moved(data, where, 1))
    assert kernel_document(control).data["geometry"] != kernel_document(on_grid).data["geometry"]


def test_a_shape_written_a_fraction_of_a_picometre_outside_the_domain_leaves_no_sliver():
    """The film of vector_slab written 0.3 pm left of the domain edge: before, the mesher took the
    written value and did not finish on the 0.3 pm sliver. Checked on the hand-off only, so a
    regression fails here instead of hanging the mesher."""
    data = _load("examples/simcase/vector_slab.json")
    moved = Document.from_dict(_moved(data, ("shapes", 0, "x"), Fraction(-3, 10)))
    assert [(d.code, d.path) for d in moved.diagnostics] == [("W-PM-ROUNDING", "geometry.shapes[0].x")]
    shape = kernel_document(moved).data["geometry"]["shapes"][0]
    domain = kernel_document(moved).data["geometry"]["domain"]
    assert shape["x"] == domain["xmin"] == -0.05 and shape["x"] + shape["w"] == domain["xmax"]
    assert kernel_document(moved).data["geometry"] == kernel_document(Document.from_dict(data)).data["geometry"]
