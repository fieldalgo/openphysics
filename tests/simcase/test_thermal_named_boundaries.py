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

K = 45.0


def kelvin(values):
    """{name: "<T> K"} of {name: T}."""
    return {name: f"{value!r} K" for name, value in values.items()}


def film(h, ambient):
    return {"heat_transfer_coefficient": f"{h!r} W/(m^2 K)", "ambient_temperature": f"{ambient!r} K"}


def plate(features, physics=None, selections=None, boundary_tags=None, size=0.5, materials=None,
          units="mm", source=0.0, kind="steady"):
    """A region heat document on the 0..40 x 0..20 plate, written as version 1."""
    name = "thermal_regions" if kind == "steady" else "transient_thermal_regions"
    raw = copy.deepcopy(EXAMPLES[name])
    comp = {"dimension": "2d", "length_unit": units, "depth": None,
            "domain": {"xmin": 0.0, "xmax": 40.0, "ymin": 0.0, "ymax": 20.0},
            "background": {"material": "steel"}, "features": features}
    if selections:
        comp["selections"] = selections
    if boundary_tags:
        comp["boundary_tags"] = boundary_tags
    raw["geometry"] = {"version": 1, "components": {"main": comp}}
    raw["materials"] = {"steel": {"thermal_conductivity": f"{K!r} W/(m K)",
                                  "volumetric_heat_capacity": "3.6e6 J/(m^3 K)", "source": "document value"},
                        **(materials or {})}
    (pname, p), = raw["physics"].items()
    p["heat_source_density"] = f"{source!r} W/m^3"
    p["prescribed_temperature"] = {}
    p.pop("inward_heat_flux", None)
    p.pop("convection", None)
    if physics:
        p.update(physics)
    raw["mesh"]["element_size"] = f"{size!r} {units}"
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
    doc = Document.from_dict(_annulus(prescribed_temperature=kelvin({"inner": ta, "rim": tb})))
    result = run(doc, verbose=False)
    assert result.region_names == ["disc"]
    r = np.hypot(result.node_coordinates[:, 0] - 20e-3, result.node_coordinates[:, 1] - 10e-3)
    exact = ta + (tb - ta) * np.log(r / 3e-3) / math.log(3.0)
    mid = np.abs(r - 6e-3) < 0.25e-3
    assert mid.sum() >= 8
    assert np.max(np.abs(result.temperature[mid] - exact[mid])) <= 1e-3 * (ta - tb)
    # the hole wall selection fixes the same nodes as the inner tag
    same = run(Document.from_dict(_annulus(prescribed_temperature=kelvin({"hole_wall": ta, "rim": tb}))), verbose=False)
    np.testing.assert_allclose(same.temperature, result.temperature, rtol=0, atol=1e-9)
    assert set(same.summary()["prescribed_temperature"]) == {"hole_wall", "rim"}


def test_g5_2_flux_and_convection_on_the_hole_wall_balance_the_rim():
    g = 2000.0
    doc = Document.from_dict(_annulus(prescribed_temperature=kelvin({"rim": 300.0}), inward_heat_flux={"hole_wall": f"{-g!r} W/m^2"}))
    result = run(doc, verbose=False)
    summary = result.summary()
    edges = result.mesh.boundary_edges["hole_wall"]
    length = float(np.linalg.norm(result.node_coordinates[edges[:, 0]] - result.node_coordinates[edges[:, 1]], axis=1).sum())
    assert abs(length - 2 * math.pi * 3e-3) <= 2e-3 * 2 * math.pi * 3e-3            # a 48-gon's perimeter
    assert abs(summary["outward_prescribed_heat_rate_per_depth"]["value"] - g * length) <= 1e-9 * g * length
    assert summary["relative_conservation_residual"]["value"] <= 1e-10
    h, amb = 50.0, 250.0
    doc = Document.from_dict(_annulus(prescribed_temperature=kelvin({"rim": 300.0}),
                                      convection={"inner": film(h, amb)}))
    result = run(doc, verbose=False)
    summary = result.summary()
    assert summary["relative_conservation_residual"]["value"] <= 1e-10
    # heat enters at the rim (300 K) and leaves through the film at the hole wall into the 250 K
    # ambient: the series resistance of the annulus and the film gives the rate
    a, b = 3e-3, 9e-3
    r_cond, r_film = math.log(b / a) / (2 * math.pi * K), 1 / (h * 2 * math.pi * a)
    heat = (300.0 - amb) / (r_cond + r_film)                                   # W/m out through the hole
    assert abs(summary["outward_convective_heat_rate_per_depth"]["value"] - heat) <= 2e-3 * heat
    assert abs(summary["outward_reaction_heat_rate_per_depth"]["value"] + heat) <= 2e-3 * heat


def test_g5_3_an_unnamed_void_border_is_insulated():
    doc = Document.from_dict(plate([HOLE], physics={"prescribed_temperature": kelvin({"left": 300.0, "right": 350.0})}))
    result = run(doc, verbose=False)
    summary = result.summary()
    assert "outer" in result.mesh.boundary_edges and result.region_names == ["background"]
    assert summary["relative_conservation_residual"]["value"] <= 1e-10
    assert 300.0 <= result.temperature.min() and result.temperature.max() <= 350.0
    # the outer tag can be named directly
    named = Document.from_dict(plate([HOLE], physics={"prescribed_temperature": kelvin({"left": 300.0, "outer": 320.0})}))
    assert run(named, verbose=False).summary()["prescribed_temperature"] == {
        "left": {"value": 300.0, "unit": "K"}, "outer": {"value": 320.0, "unit": "K"}}


@pytest.mark.parametrize("physics, message", [
    ({"inward_heat_flux": {"seam": "-1.0 W/m^2"}}, "lies on an interface between two regions"),
    ({"convection": {"seam": film(1.0, 300.0)}}, "lies on an interface"),
    ({"prescribed_temperature": kelvin({"nowhere": 300.0})}, "nowhere: no side, boundary tag or selection of that name"),
    ({"prescribed_temperature": kelvin({"core_region": 300.0})}, "core_region: no side, boundary tag or selection of that name"),
])
def test_g5_4_interior_flux_unknown_names_and_region_selections_are_refused(physics, message):
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    raw = plate([core], physics={"prescribed_temperature": kelvin({"left": 300.0}), **physics},
                selections={"seam": {"boundary": {"of": "core"}}, "core_region": {"region": "core"}})
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(raw)


def test_g5_4_an_interior_selection_names_its_nodes_but_carries_no_edge_tag_and_doubled_flux_edges_are_refused():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    raw = plate([core], physics={"prescribed_temperature": kelvin({"left": 300.0})},
                selections={"seam": {"boundary": {"of": "core"}}})
    result = run(Document.from_dict(raw), verbose=False)
    assert len(result.mesh.boundary["seam"]) >= 40 and "seam" not in result.mesh.boundary_edges
    assert len(result.mesh.selection_edges["seam"]) >= 40
    doubled = _annulus(prescribed_temperature=kelvin({"rim": 300.0}), inward_heat_flux={"inner": "-1 W/m^2", "hole_wall": "-1 W/m^2"})
    with pytest.raises(DocumentError, match="'hole_wall' and 'inner' share mesh edges"):
        run(Document.from_dict(doubled), verbose=False)


def test_g5_5_the_transient_runner_fixes_a_selection_and_refuses_an_unknown_name():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    raw = plate([core, HOLE], kind="transient", size=1.0, selections={"wall": {"boundary": {"of": "hole"}}},
                physics={"initial_temperature": "300 K", "prescribed_temperature": kelvin({"left": 300.0, "wall": 300.0})})
    raw["study"]["time"] = {"unit": "s", "values": [0.0, 5.0, 10.0]}
    result = run(Document.from_dict(raw), verbose=False)
    assert result.summary()["prescribed_nodes"] > 20
    seam = copy.deepcopy(raw)
    seam["geometry"]["components"]["main"]["selections"]["seam"] = {"boundary": {"of": "core"}}
    seam["physics"]["heat1"]["prescribed_temperature"] = kelvin({"left": 300.0, "seam": 300.0})
    assert run(Document.from_dict(seam), verbose=False).summary()["prescribed_nodes"] > 60   # interface fixed too
    bad = copy.deepcopy(raw)
    bad["physics"]["heat1"]["prescribed_temperature"] = kelvin({"left": 300.0, "nowhere": 300.0})
    with pytest.raises(DocumentError, match="nowhere"):
        Document.from_dict(bad)
    # a flat region document keeps its four sides only
    plain = copy.deepcopy(EXAMPLES["thermal_regions"])
    plain["physics"]["heat1"]["prescribed_temperature"]["outer"] = "300 K"
    with pytest.raises(DocumentError, match="outer: no side, boundary tag or selection of that name"):
        Document.from_dict(plain)


# ----------------------------------------------------------------- review findings of 2026-11-08

def test_studio_runs_a_void_document_on_both_region_routes():
    from simcase.thermal_regions import void_area_m2
    hole_doc = Document.from_dict(plate([HOLE], physics={"prescribed_temperature": kelvin({"left": 300.0})}))
    assert abs(void_area_m2(hole_doc) - math.pi * 9e-6) <= 1e-9 * math.pi * 9e-6
    assert void_area_m2(Document.from_dict(EXAMPLES["thermal_regions"])) == 0.0
    from fastapi.testclient import TestClient
    from simcase.studio import server, thermal_api
    from simcase.studio import thermal_regions_api as regions
    hole = plate([HOLE], physics={"prescribed_temperature": kelvin({"left": 300.0, "right": 350.0})}, size=1.0)
    annulus = _annulus(prescribed_temperature=kelvin({"inner": 400.0, "rim": 300.0}))
    moving = plate([HOLE], kind="transient", size=1.0, selections={"wall": {"boundary": {"of": "hole"}}},
                   physics={"initial_temperature": "300 K", "prescribed_temperature": kelvin({"left": 300.0, "wall": 300.0})})
    moving["study"]["time"] = {"unit": "s", "values": [0.0, 5.0, 10.0]}
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
    raw = plate([v1, v2], physics={"prescribed_temperature": kelvin({"left": 300.0, "seam": 350.0})},
                selections={"seam": {"boundary": {"between": ["v1", "v2"]}}})
    with pytest.raises(DocumentError, match="no mesh edge lies on 'seam'"):
        run(Document.from_dict(raw), verbose=False)
    raw["physics"]["heat1"]["prescribed_temperature"] = kelvin({"left": 300.0})
    raw["physics"]["heat1"]["inward_heat_flux"] = {"seam": "-5 W/m^2"}
    with pytest.raises(DocumentError, match="no mesh edge lies on 'seam'"):
        run(Document.from_dict(raw), verbose=False)
    moving = plate([v1, v2], kind="transient", size=1.0, selections={"seam": {"boundary": {"between": ["v1", "v2"]}}},
                   physics={"initial_temperature": "300 K", "prescribed_temperature": kelvin({"left": 300.0, "seam": 300.0})})
    moving["study"]["time"] = {"unit": "s", "values": [0.0, 5.0]}
    with pytest.raises(DocumentError, match="no mesh edge lies on 'seam'"):
        run(Document.from_dict(moving), verbose=False)


def test_a_natural_condition_on_a_dirichlet_boundary_under_another_name_is_refused():
    for physics in ({"inward_heat_flux": {"hole_wall": "-2000.0 W/m^2"}},
                    {"convection": {"hole_wall": film(5.0, 300.0)}}):
        raw = _annulus(prescribed_temperature=kelvin({"inner": 400.0, "rim": 300.0}), **physics)
        with pytest.raises(DocumentError, match="shares mesh edges with the prescribed-temperature boundary 'inner'"):
            run(Document.from_dict(raw), verbose=False)


# ----------------------------------------------------------------- interface Dirichlet (G6-2, G6-3; 2026-11-08)

def test_g6_2_a_fixed_interface_matches_the_same_rectangle_cut_out_as_a_void():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    fixed = plate([core], physics={"prescribed_temperature": kelvin({"left": 300.0, "right": 300.0, "seam": 340.0})},
                  selections={"seam": {"boundary": {"of": "core"}}}, size=0.5)
    hole = plate([dict(core, material=None)], physics={"prescribed_temperature": kelvin({"left": 300.0, "right": 300.0,
                                                                                 "wall": 340.0})},
                 selections={"wall": {"boundary": {"of": "core"}}}, size=0.5)
    a = run(Document.from_dict(fixed), verbose=False)
    b = run(Document.from_dict(hole), verbose=False)
    nodes = a.node_coordinates
    inside = (nodes[:, 0] > 10e-3 - 1e-12) & (nodes[:, 0] < 20e-3 + 1e-12) & (nodes[:, 1] > 5e-3 - 1e-12) \
        & (nodes[:, 1] < 15e-3 + 1e-12)
    assert inside.sum() > 50 and np.max(np.abs(a.temperature[inside] - 340.0)) <= 1e-9 * 340.0
    sa, sb = a.summary(), b.summary()
    # the heat the interface injects leaves through the sides: the same in both, at discretization level
    out_a = -sa["outward_reaction_heat_rate_per_depth"]["value"]
    assert out_a != 0.0 and abs(sa["relative_conservation_residual"]["value"]) <= 1e-10
    sides_a = float(a.reaction_heat_rate_per_depth[np.concatenate([a.mesh.boundary["left"], a.mesh.boundary["right"]])].sum())
    sides_b = float(b.reaction_heat_rate_per_depth[np.concatenate([b.mesh.boundary["left"], b.mesh.boundary["right"]])].sum())
    assert abs(sides_a - sides_b) <= 1e-3 * abs(sides_b)
    assert sa["prescribed_nodes"] == sb["prescribed_nodes"]     # the interface nodes only; the enclosed region follows


def test_g6_3_the_transient_runner_fixes_an_interface_and_reaches_the_steady_solution():
    core = {"name": "core", "type": "rect", "x": 10.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    steady = plate([core], physics={"prescribed_temperature": kelvin({"left": 300.0, "right": 300.0, "seam": 340.0})},
                   selections={"seam": {"boundary": {"of": "core"}}}, size=1.0)
    moving = plate([core], kind="transient", size=1.0, selections={"seam": {"boundary": {"of": "core"}}},
                   physics={"initial_temperature": "300 K",
                            "prescribed_temperature": kelvin({"left": 300.0, "right": 300.0, "seam": 300.0})})
    # the interface starts at 300 K (t0 consistency) and steps to 340 K
    # backward Euler reaches the steady state as the last step grows (its residual scales with
    # the plate's 32 s diffusion time over the step), so the study ends with two very long steps
    moving["physics"]["heat1"]["prescribed_temperature"]["seam"] = {"unit": "K", "values": [300.0] + [340.0] * 5}
    moving["study"]["time"] = {"unit": "s", "values": [0.0, 1.0, 10.0, 100.0, 1e4, 1e6]}
    a = run(Document.from_dict(steady), verbose=False)
    b = run(Document.from_dict(moving), verbose=False)
    final = np.asarray(b.temperature)[-1]
    assert final.shape == a.temperature.shape
    assert np.max(np.abs(final - a.temperature)) <= 1e-6 * 40.0


# ----------------------------------------------------------------- review findings of 2026-11-08 (stage 2e)

def test_a_fixed_selection_touching_a_side_is_refused_by_name_under_that_side_s_flux():
    core = {"name": "core", "type": "rect", "x": 0.0, "y": 5.0, "w": 10.0, "h": 10.0, "material": "steel"}
    for physics in ({"inward_heat_flux": {"left": "-1000.0 W/m^2"}},
                    {"convection": {"left": film(5.0, 300.0)}}):
        raw = plate([core], physics={"prescribed_temperature": kelvin({"seam": 340.0, "right": 300.0}), **physics},
                    selections={"seam": {"boundary": {"of": "core"}}}, size=1.0)
        with pytest.raises(DocumentError, match="shares mesh edges with the prescribed-temperature boundary 'seam'"):
            run(Document.from_dict(raw), verbose=False)
    # the same selection at a value other than the side's names both boundaries
    raw = plate([core], physics={"prescribed_temperature": kelvin({"left": 300.0, "seam": 340.0})},
                selections={"seam": {"boundary": {"of": "core"}}}, size=1.0)
    with pytest.raises(DocumentError, match="'left' and 'seam' share node"):
        run(Document.from_dict(raw), verbose=False)


def test_an_axisymmetric_selection_touching_the_axis_fixes_its_off_axis_nodes_only():
    from test_thermal_axisymmetric_regions import cylinder, TB
    core = {"name": "core", "type": "rect", "x": 0.0, "y": 0.2, "w": 1.0, "h": 0.5, "material": "pla"}
    raw = cylinder(features=[core], source=0.0, size_mm=0.2, dirichlet={"right": TB, "seam": 350.0})
    raw["geometry"]["components"]["rod"]["selections"] = {"seam": {"boundary": {"of": "core"}}}
    result = run(Document.from_dict(raw), verbose=False)
    fixed = result.node_coordinates[result.prescribed_node_ids]
    seam = result.mesh.boundary["seam"]
    assert len(seam) >= 10 and np.all(result.node_coordinates[seam, 0] > 0)          # no axis node in the selection
    assert np.all(result.temperature[seam] == 350.0)
    assert result.summary()["relative_conservation_residual"]["value"] <= 1e-10
