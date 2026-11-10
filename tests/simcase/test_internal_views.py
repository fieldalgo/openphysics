# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The internal SI views between documents and solvers (``simcase.views``; not public API).

The units-batch harness (``tools/units_batch``, check P2-3) compares every solver and mesher
input bit for bit, but it runs only on request. These checks keep, in the default suite, the
doubles of the hand-off hazards the views exist for: each kind's rectangle length formula
(H17 b), the micrometre hand-back of region nodes and corners (H11, H17 a) and the angle number
meshine receives (H3).
"""

import copy
import dataclasses
import math

import numpy as np
import pytest

import galerkin
from simcase import Document, examples, run, units, views
from simcase.thermal_examples import TRANSIENT_THERMAL_REGIONS

MM = units.resolve({"length": "mm"})


def rectangle(physics, length_units=None):
    """A rectangle whose two length formulas give different doubles along x."""
    return Document.from_dict({
        "openphysics": "0.2", "name": "views", "units": length_units or {"length": "mm", "temperature": "K"},
        "geometry": {"domain": {"xmin": 123.456, "xmax": 133.456, "ymin": -3.2, "ymax": 2.8}},
        "materials": {}, "physics": {"p": physics}, "mesh": {"subdivisions": [4, 3]},
        "study": {"type": "single"}, "results": {"save_fields": False, "plots": False}})


def rectangle_03(physics):
    """The same rectangle in format 0.3 (rectangle heat reads 0.3 since units batch C5a)."""
    return Document.from_dict({
        "openphysics": "0.3", "name": "views",
        "geometry": {"length_unit": "mm", "depth": None,
                     "domain": {"xmin": 123.456, "xmax": 133.456, "ymin": -3.2, "ymax": 2.8}},
        "materials": {}, "physics": {"p": physics}, "mesh": {"subdivision_count": [4, 3]},
        "study": {"type": "single"}, "results": {"save_fields": False, "plots": False}})


HEAT = {"type": "thermal.steady2d", "thermal_conductivity": "2 W/(m K)", "prescribed_temperature": {"left": "300 K"}}
ELECTRIC = {"type": "electric.steady2d", "conductivity_s_m": 1e6, "dirichlet_potential_v": {"left": 0., "right": 1.}}


def si(value):
    return MM.to_si(value, {"length": 1})


def test_rectangle_lengths_keep_each_kinds_operation_order():
    doc = rectangle(ELECTRIC, {"length": "mm"})
    difference, corners = (views.rectangle_mesh(doc, formula) for formula in views.LENGTH_FORMULAS)
    assert difference.origin == corners.origin == (si(123.456), si(-3.2))
    assert difference.upper == corners.upper == (si(133.456), si(2.8))
    assert difference.lengths == (si(133.456 - 123.456), si(2.8 - -3.2))
    assert corners.lengths == (si(133.456) - si(123.456), si(2.8) - si(-3.2))
    # the formulas disagree here, so which one a kind uses is part of what it hands galerkin
    assert difference.lengths[0] == 0.009999999999999986 and corners.lengths[0] == 0.009999999999999981
    assert difference.subdivisions == (4, 3) and all(type(n) is int for n in difference.subdivisions)
    with pytest.raises(dataclasses.FrozenInstanceError):
        difference.lengths = corners.lengths
    with pytest.raises(ValueError, match="formula"):
        views.rectangle_mesh(doc, "rounded")


def test_a_format_0_3_rectangle_keeps_the_operation_order_on_picometres():
    # corners pm_to_m(k), correctly rounded; lengths by the same two formulas on the pm counts
    from physmat.units import pm_to_m
    doc = rectangle_03(HEAT)
    difference, corners = (views.rectangle_mesh(doc, formula) for formula in views.LENGTH_FORMULAS)
    assert difference.origin == corners.origin == (0.123456, -0.0032) == (pm_to_m(123456000000), pm_to_m(-3200000000))
    assert difference.upper == corners.upper == (0.133456, 0.0028)
    assert difference.lengths == (0.01, 0.006) == (pm_to_m(10 ** 10), pm_to_m(6 * 10 ** 9))
    assert corners.lengths == (0.133456 - 0.123456, 0.0028 - -0.0032)
    assert difference.subdivisions == (4, 3) and all(type(n) is int for n in difference.subdivisions)


@pytest.mark.parametrize("physics, units_, formula", [
    (HEAT, None, "difference"), (ELECTRIC, {"length": "mm"}, "corners")])
def test_each_rectangle_runner_meshes_with_its_own_formula(monkeypatch, physics, units_, formula):
    calls, original = [], galerkin.rectangle_mesh

    def spy(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(galerkin, "rectangle_mesh", spy)
    doc = rectangle_03(physics) if physics is HEAT else rectangle(physics, units_)
    before = copy.deepcopy(doc.data)
    result = run(doc, verbose=False)
    grid = views.rectangle_mesh(doc, formula)
    assert [tuple(float(v).hex() for v in c) for c in calls] == [
        tuple(float(v).hex() for v in (*grid.lengths, *grid.subdivisions))]
    nodes = result.node_coordinates if physics is HEAT else result.fields["nodes_m"]
    assert nodes.min(axis=0).tolist() == list(grid.origin)
    assert doc.data == before


def test_region_nodes_and_corners_come_back_from_micrometres():
    # H17 a: an origin in millimetres is moved to micrometres and back, as the mesh nodes are
    assert views.region_corner_m(-3.2, MM) == -0.0031999999999999997 != si(-3.2)
    np.testing.assert_array_equal(views.region_corner_m([123.456, -3.2], MM),
                                  [views.region_corner_m(123.456, MM), -0.0031999999999999997])
    # H11: 50 mm meshed in micrometres comes back as 50000 um times 1e-6, not 0.05
    assert views.handback_m([[50000.0, 0.0]])[0, 0] == 0.049999999999999996
    data = copy.deepcopy(TRANSIENT_THERMAL_REGIONS)
    data["geometry"]["domain"].update(ymin=-3.2, ymax=1.8)
    data["geometry"]["shapes"][0].update(y=-3.2)
    doc = Document.from_dict(data)
    np.testing.assert_array_equal(views.region_origin_m(doc), [0.0, -0.0031999999999999997])
    heat = views.transient_region_heat(doc)
    assert heat.dirichlet == {"left": (300.,) * 9, "right": (300.,) * 9}
    assert heat.conductivity == {"steel": 45., "insulation": .5}


def test_meshine_receives_the_angle_as_written():
    # H3: a degree number converted to radians and back is not always the number written
    assert math.degrees(math.radians(30.)) != 30.
    data = copy.deepcopy(TRANSIENT_THERMAL_REGIONS)
    data["mesh"]["min_angle"] = 30
    grid = views.region_mesh(Document.from_dict(data))
    assert type(grid.minimum_angle_deg) is float and grid.minimum_angle_deg == 30.
    assert grid.canonical.length_unit == "um" and grid.grading is None
    em = copy.deepcopy(examples.SLAB_TE_CHECK)
    em["mesh"]["min_angle"] = 30.
    assert views.modes_mesh(Document.from_dict(em)).minimum_angle_deg == 30.
