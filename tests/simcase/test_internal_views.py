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
from simcase import Document, examples, run, views
from simcase.thermal_examples import TRANSIENT_THERMAL_REGIONS

def box_03():
    """A format 0.3 box (em.cavity3d) in millimetres whose two length formulas give different doubles
    along x. (Until units batch C11a this was a format 0.2 box read through the retired 0.2 view.)"""
    data = copy.deepcopy(examples.EXAMPLES["cavity_box"])
    data["geometry"]["length_unit"] = "mm"
    data["geometry"]["domain"] = {"xmin": 123.456, "xmax": 133.456, "ymin": -3.2, "ymax": 2.8, "zmin": 0.0, "zmax": 1.0}
    data["mesh"]["subdivision_count"] = [4, 3, 2]
    return Document.from_dict(data)


def rectangle_03(physics):
    """The same rectangle in format 0.3 (rectangle heat reads 0.3 since units batch C5a)."""
    return Document.from_dict({
        "openphysics": "0.3", "name": "views",
        "geometry": {"length_unit": "mm", "depth": None,
                     "domain": {"xmin": 123.456, "xmax": 133.456, "ymin": -3.2, "ymax": 2.8}},
        "materials": {}, "physics": {"p": physics}, "mesh": {"subdivision_count": [4, 3]},
        "study": {"type": "single"}, "results": {"save_fields": False, "plots": False}})


HEAT = {"type": "thermal.steady2d", "thermal_conductivity": "2 W/(m K)", "prescribed_temperature": {"left": "300 K"}}
ELECTRIC = {"type": "electric.steady2d", "electrical_conductivity": "1e6 S/m",
            "prescribed_electric_potential": {"left": "0 V", "right": "1 V"}}


def test_rectangle_lengths_keep_each_kinds_operation_order():
    from physmat.units import pm_to_m
    doc = box_03()
    difference, corners = (views.rectangle_mesh(doc, formula, axes="xyz") for formula in views.LENGTH_FORMULAS)
    assert difference.origin == corners.origin == (0.123456, -0.0032, 0.0)
    assert difference.upper == corners.upper == (0.133456, 0.0028, 0.001)
    assert difference.lengths == (pm_to_m(10 ** 10), pm_to_m(6 * 10 ** 9), pm_to_m(10 ** 9)) == (0.01, 0.006, 0.001)
    assert corners.lengths == (0.133456 - 0.123456, 0.0028 - -0.0032, 0.001 - 0.0)
    # the formulas disagree here, so which one a kind uses is part of what it hands galerkin
    assert difference.lengths[0] == 0.01 and corners.lengths[0] == 0.009999999999999995
    assert difference.subdivisions == (4, 3, 2) and all(type(n) is int for n in difference.subdivisions)
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
    (HEAT, None, "difference"), (ELECTRIC, None, "corners")])
def test_each_rectangle_runner_meshes_with_its_own_formula(monkeypatch, physics, units_, formula):
    calls, original = [], galerkin.rectangle_mesh

    def spy(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(galerkin, "rectangle_mesh", spy)
    doc = rectangle_03(physics)
    before = copy.deepcopy(doc.data)
    result = run(doc, verbose=False)
    grid = views.rectangle_mesh(doc, formula)
    assert [tuple(float(v).hex() for v in c) for c in calls] == [
        tuple(float(v).hex() for v in (*grid.lengths, *grid.subdivisions))]
    nodes = result.node_coordinates if physics is HEAT else result.fields["node_coordinates"]
    assert nodes.min(axis=0).tolist() == list(grid.origin)
    assert doc.data == before


def test_region_nodes_and_corners_come_back_from_micrometres():
    # H17 a: an origin in millimetres is moved to micrometres and back, as the mesh nodes are
    # (the 0.2 region_corner_m helper is retired in C11a; the 0.3 corner below goes the same way)
    # H11: 50 mm meshed in micrometres comes back as 50000 um times 1e-6, not 0.05
    assert views.handback_m([[50000.0, 0.0]])[0, 0] == 0.049999999999999996
    data = copy.deepcopy(TRANSIENT_THERMAL_REGIONS)
    data["geometry"]["domain"].update(ymin=-3.2, ymax=1.8)
    data["geometry"]["shapes"][0].update(y=-3.2)
    doc = Document.from_dict(data)
    # format 0.3: from the pm counts of the corner by the same micrometre hand-back
    np.testing.assert_array_equal(views.region_origin_03(doc, "geometry"), [0.0, -0.0031999999999999997])
    assert views.region_origin_03(doc, "geometry")[1] != -3.2e-3          # not the correctly rounded corner
    heat = views.transient_region_heat_03(doc)
    assert heat.dirichlet == {"left": (300.,) * 9, "right": (300.,) * 9}
    assert heat.conductivity == {"steel": 45., "insulation": .5}


def test_meshine_receives_the_angle_as_written():
    # H3: a degree number converted to radians and back is not always the number written
    assert math.degrees(math.radians(30.)) != 30.
    data = copy.deepcopy(TRANSIENT_THERMAL_REGIONS)
    data["mesh"]["minimum_angle"] = "30 deg"
    from simcase.thermal_regions import handoff_03
    grid = views.region_mesh(handoff_03(Document.from_dict(data)))      # the mesh hand-off of a 0.3 document
    assert type(grid.minimum_angle_deg) is float and grid.minimum_angle_deg == 30.
    assert grid.canonical.length_unit == "um" and grid.grading is None
    em = copy.deepcopy(examples.SLAB_TE_CHECK)
    em["mesh"]["minimum_angle"] = "30 deg"
    from simcase.modes_document import kernel_document
    angle = views.modes_mesh(kernel_document(Document.from_dict(em))).minimum_angle_deg   # the micrometre hand-off
    assert type(angle) is float and angle == 30.
