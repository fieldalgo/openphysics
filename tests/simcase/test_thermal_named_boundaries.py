# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Named boundaries in region heat through a version 1 geometry block (stage 2d).

Pre-registered checks G5-1 to G5-5 (HQ work record, 2026-11-08): Dirichlet, flux and convection
data on the exterior tags a complex declares (``boundary_tags`` names, ``outer`` on a void
border) and on boundary selections; an unnamed void border is insulated (HQ decision
2026-11-08).
"""
import copy
import math

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.examples import EXAMPLES
from simcase.geometry_document import from_v02

K = 45.0


def plate(features, physics=None, selections=None, boundary_tags=None, size=0.5, materials=None,
          units="mm", source=0.0, kind="steady"):
    """A region heat document on the 0..40 x 0..20 plate, written as version 1."""
    name = "thermal_regions" if kind == "steady" else "transient_thermal_regions"
    raw = copy.deepcopy(EXAMPLES[name])
    raw["geometry"] = from_v02(raw["geometry"])
    comp = raw["geometry"]["components"]["main"]
    comp["features"] = features
    comp["domain"] = {"xmin": 0.0, "xmax": 40.0, "ymin": 0.0, "ymax": 20.0}
    if selections:
        comp["selections"] = selections
    if boundary_tags:
        comp["boundary_tags"] = boundary_tags
    raw["units"]["length"] = units
    raw["materials"] = {"steel": {"conductivity_w_mk": K, "volumetric_heat_capacity_j_m3k": 3.6e6,
                                  "source": "document value"}, **(materials or {})}
    comp["background"] = {"material": "steel"}
    (pname, p), = raw["physics"].items()
    p["heat_source_w_m3"] = source
    p["dirichlet_temperature_k"] = {}
    p.pop("outward_flux_w_m2", None)
    p.pop("convection", None)
    if physics:
        p.update(physics)
    raw["mesh"]["size"] = size
    return raw


DISC = {"name": "disc", "type": "circle", "cx": 20.0, "cy": 10.0, "r": 9.0, "material": "steel"}
HOLE = {"name": "hole", "type": "circle", "cx": 20.0, "cy": 10.0, "r": 3.0, "material": None}


def _annulus(**physics):
    """A steel disc of radius 9 with a void hole of radius 3 in a void plate: two named circles."""
    cut = {"name": "cut", "type": "rect", "x": 0.0, "y": 0.0, "w": 40.0, "h": 20.0, "material": None}
    return plate([cut, DISC, HOLE], physics=physics, size=0.4,
                 boundary_tags=[{"tag": "inner", "select": {"boundary": {"of": "hole"}}},
                                {"tag": "rim", "select": {"boundary": {"between": ["disc", "cut"]}}}],
                 selections={"hole_wall": {"boundary": {"of": "hole"}}})


def test_g5_1_dirichlet_on_both_circles_of_an_annulus_conducts_logarithmically():
    ta, tb = 400.0, 300.0
    doc = Document.from_dict(_annulus(dirichlet_temperature_k={"inner": ta, "rim": tb}))
    result = run(doc, verbose=False)
    assert result.region_names == ["disc"]
    r = np.hypot(result.mesh_nodes_m[:, 0] - 20e-3, result.mesh_nodes_m[:, 1] - 10e-3)
    exact = ta + (tb - ta) * np.log(r / 3e-3) / math.log(3.0)
    mid = np.abs(r - 6e-3) < 0.25e-3
    assert mid.sum() >= 8
    assert np.max(np.abs(result.temperature_k[mid] - exact[mid])) <= 1e-3 * (ta - tb)
    # the hole wall selection fixes the same nodes as the inner tag
    same = run(Document.from_dict(_annulus(dirichlet_temperature_k={"hole_wall": ta, "rim": tb})), verbose=False)
    np.testing.assert_allclose(same.temperature_k, result.temperature_k, rtol=0, atol=1e-9)
    assert set(same.summary()["dirichlet_temperature_k"]) == {"hole_wall", "rim"}


def test_g5_2_flux_and_convection_on_the_hole_wall_balance_the_rim():
    g = 2000.0
    doc = Document.from_dict(_annulus(dirichlet_temperature_k={"rim": 300.0}, outward_flux_w_m2={"hole_wall": g}))
    result = run(doc, verbose=False)
    summary = result.summary()
    edges = result.mesh.boundary_edges["hole_wall"]
    length = float(np.linalg.norm(result.mesh_nodes_m[edges[:, 0]] - result.mesh_nodes_m[edges[:, 1]], axis=1).sum())
    assert abs(length - 2 * math.pi * 3e-3) <= 2e-3 * 2 * math.pi * 3e-3            # a 48-gon's perimeter
    assert abs(summary["prescribed_outward_heat_w_per_m"] - g * length) <= 1e-9 * g * length
    assert summary["normalized_heat_balance_defect"] <= 1e-10
    h, amb = 50.0, 250.0
    doc = Document.from_dict(_annulus(dirichlet_temperature_k={"rim": 300.0},
                                      convection={"inner": {"h_w_m2k": h, "ambient_temperature_k": amb}}))
    result = run(doc, verbose=False)
    summary = result.summary()
    assert summary["normalized_heat_balance_defect"] <= 1e-10
    # heat enters at the rim (300 K) and leaves through the film at the hole wall into the 250 K
    # ambient: the series resistance of the annulus and the film gives the rate
    a, b = 3e-3, 9e-3
    r_cond, r_film = math.log(b / a) / (2 * math.pi * K), 1 / (h * 2 * math.pi * a)
    heat = (300.0 - amb) / (r_cond + r_film)                                   # W/m out through the hole
    assert abs(summary["convective_outward_heat_w_per_m"] - heat) <= 2e-3 * heat
    assert abs(summary["thermostat_outward_heat_w_per_m"] + heat) <= 2e-3 * heat


def test_g5_3_an_unnamed_void_border_is_insulated():
    doc = Document.from_dict(plate([HOLE], physics={"dirichlet_temperature_k": {"left": 300.0, "right": 350.0}}))
    result = run(doc, verbose=False)
    summary = result.summary()
    assert "outer" in result.mesh.boundary_edges and result.region_names == ["background"]
    assert summary["normalized_heat_balance_defect"] <= 1e-10
    assert 300.0 <= result.temperature_k.min() and result.temperature_k.max() <= 350.0
    # the outer tag can be named directly
    named = Document.from_dict(plate([HOLE], physics={"dirichlet_temperature_k": {"left": 300.0, "outer": 320.0}}))
    assert run(named, verbose=False).summary()["dirichlet_temperature_k"] == {"left": 300.0, "outer": 320.0}


@pytest.mark.parametrize("physics, message", [
    ({"outward_flux_w_m2": {"seam": 1.0}}, "lies on an interface between two regions"),
    ({"convection": {"seam": {"h_w_m2k": 1.0, "ambient_temperature_k": 300.0}}}, "lies on an interface"),
    ({"dirichlet_temperature_k": {"nowhere": 300.0}}, "unsupported thermal keys \\['nowhere'\\]"),
    ({"dirichlet_temperature_k": {"core_region": 300.0}}, "unsupported thermal keys \\['core_region'\\]"),
])
def test_g5_4_interior_flux_unknown_names_and_region_selections_are_refused(physics, message):
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    raw = plate([core], physics={"dirichlet_temperature_k": {"left": 300.0}, **physics},
                selections={"seam": {"boundary": {"of": "core"}}, "core_region": {"region": "core"}})
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(raw)


def test_g5_4_an_interior_selection_names_its_nodes_but_carries_no_edge_tag_and_doubled_flux_edges_are_refused():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    raw = plate([core], physics={"dirichlet_temperature_k": {"left": 300.0}},
                selections={"seam": {"boundary": {"of": "core"}}})
    result = run(Document.from_dict(raw), verbose=False)
    assert len(result.mesh.boundary["seam"]) >= 40 and "seam" not in result.mesh.boundary_edges
    assert len(result.mesh.selection_edges["seam"]) >= 40
    doubled = _annulus(dirichlet_temperature_k={"rim": 300.0}, outward_flux_w_m2={"inner": 1.0, "hole_wall": 1.0})
    with pytest.raises(DocumentError, match="'hole_wall' and 'inner' share mesh edges"):
        run(Document.from_dict(doubled), verbose=False)


def test_g5_5_the_transient_runner_fixes_a_selection_and_refuses_an_unknown_name():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    raw = plate([core, HOLE], kind="transient", size=1.0, selections={"wall": {"boundary": {"of": "hole"}}},
                physics={"initial_temperature_k": 300.0, "dirichlet_temperature_k": {"left": 300.0, "wall": 300.0}})
    raw["study"]["time_s"] = [0.0, 5.0, 10.0]
    result = run(Document.from_dict(raw), verbose=False)
    assert result.summary()["dirichlet_nodes"] > 20
    seam = copy.deepcopy(raw)
    seam["geometry"]["components"]["main"]["selections"]["seam"] = {"boundary": {"of": "core"}}
    seam["physics"]["heat1"]["dirichlet_temperature_k"] = {"left": 300.0, "seam": 300.0}
    assert run(Document.from_dict(seam), verbose=False).summary()["dirichlet_nodes"] > 60   # interface fixed too
    bad = copy.deepcopy(raw)
    bad["physics"]["heat1"]["dirichlet_temperature_k"] = {"left": 300.0, "nowhere": 300.0}
    with pytest.raises(DocumentError, match="nowhere"):
        Document.from_dict(bad)
    # a 0.2 document keeps its four sides only
    plain = copy.deepcopy(EXAMPLES["thermal_regions"])
    plain["physics"]["heat1"]["dirichlet_temperature_k"]["outer"] = 300.0
    with pytest.raises(DocumentError, match="unsupported thermal keys \\['outer'\\]"):
        Document.from_dict(plain)


# ----------------------------------------------------------------- review findings of 2026-11-08

def test_studio_runs_a_void_document_on_both_region_routes():
    from simcase.thermal_regions import void_area_m2
    hole_doc = Document.from_dict(plate([HOLE], physics={"dirichlet_temperature_k": {"left": 300.0}}))
    assert abs(void_area_m2(hole_doc) - math.pi * 9e-6) <= 1e-9 * math.pi * 9e-6
    assert void_area_m2(Document.from_dict(EXAMPLES["thermal_regions"])) == 0.0
    from fastapi.testclient import TestClient
    from simcase.studio import server, thermal_api
    from simcase.studio import thermal_regions_api as regions
    hole = plate([HOLE], physics={"dirichlet_temperature_k": {"left": 300.0, "right": 350.0}}, size=1.0)
    annulus = _annulus(dirichlet_temperature_k={"inner": 400.0, "rim": 300.0})
    moving = plate([HOLE], kind="transient", size=1.0, selections={"wall": {"boundary": {"of": "hole"}}},
                   physics={"initial_temperature_k": 300.0, "dirichlet_temperature_k": {"left": 300.0, "wall": 300.0}})
    moving["study"]["time_s"] = [0.0, 5.0, 10.0]
    server._thermal_jobs = thermal_api.ThermalJobs()
    server._region_limits = regions.RegionLimits()
    server._start_thermal_thread = lambda target, args: target(*args)
    with TestClient(server.app) as client:
        for doc, route in ((hole, "/api/thermal/"), (annulus, "/api/thermal/"), (moving, "/api/thermal/transient/")):
            response = client.post(route + "run", json={"doc": doc, "client_revision": 1, "request_seq": 1})
            assert response.status_code == 200, response.text
            status = client.get("/api/jobs/" + response.json()["job"]).json()
            assert status["status"] == "done", status


def test_an_exterior_selection_without_mesh_edges_is_refused_by_name():
    v1 = {"name": "v1", "type": "rect", "x": 10.0, "y": 5.0, "w": 5.0, "h": 10.0, "material": None}
    v2 = {"name": "v2", "type": "rect", "x": 15.0, "y": 5.0, "w": 5.0, "h": 10.0, "material": None}
    raw = plate([v1, v2], physics={"dirichlet_temperature_k": {"left": 300.0, "seam": 350.0}},
                selections={"seam": {"boundary": {"between": ["v1", "v2"]}}})
    with pytest.raises(DocumentError, match="no mesh edge lies on 'seam'"):
        run(Document.from_dict(raw), verbose=False)
    raw["physics"]["heat1"]["dirichlet_temperature_k"] = {"left": 300.0}
    raw["physics"]["heat1"]["outward_flux_w_m2"] = {"seam": 5.0}
    with pytest.raises(DocumentError, match="no mesh edge lies on 'seam'"):
        run(Document.from_dict(raw), verbose=False)
    moving = plate([v1, v2], kind="transient", size=1.0, selections={"seam": {"boundary": {"between": ["v1", "v2"]}}},
                   physics={"initial_temperature_k": 300.0, "dirichlet_temperature_k": {"left": 300.0, "seam": 300.0}})
    moving["study"]["time_s"] = [0.0, 5.0]
    with pytest.raises(DocumentError, match="no mesh edge lies on 'seam'"):
        run(Document.from_dict(moving), verbose=False)


def test_a_natural_condition_on_a_dirichlet_boundary_under_another_name_is_refused():
    for physics in ({"outward_flux_w_m2": {"hole_wall": 2000.0}},
                    {"convection": {"hole_wall": {"h_w_m2k": 5.0, "ambient_temperature_k": 300.0}}}):
        raw = _annulus(dirichlet_temperature_k={"inner": 400.0, "rim": 300.0}, **physics)
        with pytest.raises(DocumentError, match="shares mesh edges with the Dirichlet boundary 'inner'"):
            run(Document.from_dict(raw), verbose=False)


# ----------------------------------------------------------------- interface Dirichlet (G6-2, G6-3; 2026-11-08)

def test_g6_2_a_fixed_interface_matches_the_same_rectangle_cut_out_as_a_void():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    fixed = plate([core], physics={"dirichlet_temperature_k": {"left": 300.0, "right": 300.0, "seam": 340.0}},
                  selections={"seam": {"boundary": {"of": "core"}}}, size=0.5)
    hole = plate([dict(core, material=None)], physics={"dirichlet_temperature_k": {"left": 300.0, "right": 300.0,
                                                                                 "wall": 340.0}},
                 selections={"wall": {"boundary": {"of": "core"}}}, size=0.5)
    a = run(Document.from_dict(fixed), verbose=False)
    b = run(Document.from_dict(hole), verbose=False)
    nodes = a.mesh_nodes_m
    inside = (nodes[:, 0] > 10e-3 - 1e-12) & (nodes[:, 0] < 20e-3 + 1e-12) & (nodes[:, 1] > 5e-3 - 1e-12) \
        & (nodes[:, 1] < 15e-3 + 1e-12)
    assert inside.sum() > 50 and np.max(np.abs(a.temperature_k[inside] - 340.0)) <= 1e-9 * 340.0
    sa, sb = a.summary(), b.summary()
    # the heat the interface injects leaves through the sides: the same in both, at discretization level
    out_a = -sa["thermostat_outward_heat_w_per_m"]
    assert out_a != 0.0 and abs(sa["normalized_heat_balance_defect"]) <= 1e-10
    sides_a = float(a.reaction_w_per_m[np.concatenate([a.mesh.boundary["left"], a.mesh.boundary["right"]])].sum())
    sides_b = float(b.reaction_w_per_m[np.concatenate([b.mesh.boundary["left"], b.mesh.boundary["right"]])].sum())
    assert abs(sides_a - sides_b) <= 1e-3 * abs(sides_b)
    assert sa["dirichlet_nodes"] == sb["dirichlet_nodes"]     # the interface nodes only; the enclosed region follows


def test_g6_3_the_transient_runner_fixes_an_interface_and_reaches_the_steady_solution():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    steady = plate([core], physics={"dirichlet_temperature_k": {"left": 300.0, "right": 300.0, "seam": 340.0}},
                   selections={"seam": {"boundary": {"of": "core"}}}, size=1.0)
    moving = plate([core], kind="transient", size=1.0, selections={"seam": {"boundary": {"of": "core"}}},
                   physics={"initial_temperature_k": 300.0,
                            "dirichlet_temperature_k": {"left": 300.0, "right": 300.0, "seam": 300.0}})
    # the interface starts at 300 K (t0 consistency) and steps to 340 K
    # backward Euler reaches the steady state as the last step grows (its residual scales with
    # the plate's 32 s diffusion time over the step), so the study ends with two very long steps
    moving["physics"]["heat1"]["dirichlet_temperature_k"]["seam"] = {"values_k": [300.0] + [340.0] * 5}
    moving["study"]["time_s"] = [0.0, 1.0, 10.0, 100.0, 1e4, 1e6]
    a = run(Document.from_dict(steady), verbose=False)
    b = run(Document.from_dict(moving), verbose=False)
    final = np.asarray(b.temperature_k)[-1]
    assert final.shape == a.temperature_k.shape
    assert np.max(np.abs(final - a.temperature_k)) <= 1e-6 * 40.0
