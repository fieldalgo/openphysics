# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``electric.steady2d`` on named material regions of a version 1 geometry block (stage ①-a).

Pre-registered checks E1 to E7 (HQ work record ``work/openphysics-geometry.md``,
2026-11-08), against independent closed forms: series and parallel layers, a coaxial pair
of circular electrodes, the discrete Joule identity, the rectangle path unchanged, and
refusals by name. E4 (a fixed potential on an interface selection) is refused instead:
galerkin.electric fixes exterior nodes only.
"""
import copy
import math

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.examples import EXAMPLES


def strip(features, physics, *, materials=None, size=0.25, selections=None, background="A", domain=(0, 2, 0, 1)):
    """A version 1 conduction document in mm on a 2 x 1 mm strip."""
    comp = {"dimension": "2d", "domain": dict(zip(("xmin", "xmax", "ymin", "ymax"), domain)),
            "background": {"material": background}, "features": features}
    if selections:
        comp["selections"] = selections
    return {"openphysics": "0.2", "name": "strip", "units": {"length": "mm"},
            "geometry": {"version": 1, "components": {"xs": comp}},
            "materials": materials or {"A": {"electrical_conductivity_s_m": 2.0},
                                       "B": {"electrical_conductivity_s_m": 0.5}},
            "physics": {"e": {"type": "electric.steady2d", **physics}},
            "mesh": {"size": size}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False}}


RIGHT_HALF = {"name": "b", "type": "rect", "x": 1, "y": 0, "w": 1, "h": 1, "material": "B"}
TOP_HALF = {"name": "b", "type": "rect", "x": 0, "y": 0.5, "w": 2, "h": 0.5, "material": "B"}


def test_e1_series_layers_are_piecewise_linear_and_carry_v_over_r():
    result = run(Document.from_dict(strip([RIGHT_HALF], {"dirichlet_potential_v": {"left": 1.0, "right": 0.0}})),
                 verbose=False)
    summary, fields = result.summary(), result.fields
    assert summary["result_format"] == "electric.steady2d-regions-result-v1"
    assert summary["region_conductivity_s_m"] == {"b": 0.5, "background": 2.0}
    L, h = 1e-3, 1e-3
    current = 1.0 / (L / (2.0 * h) + L / (0.5 * h))                      # A per metre of depth
    middle = 1.0 - current * L / (2.0 * h)
    x = fields["nodes_m"][:, 0]
    exact = np.where(x <= L, 1.0 - (1.0 - middle) * x / L, middle * (2 * L - x) / L)
    assert np.max(np.abs(fields["potential_v"] - exact)) <= 1e-10
    terminal = summary["diagnostics"]["terminal_reaction_current_a_per_m"]
    assert abs(terminal["left"] - current) <= 1e-10 * current
    assert abs(terminal["right"] + current) <= 1e-10 * current
    # E5: the discrete Joule power equals the supplied power V * I
    assert abs(summary["diagnostics"]["joule_power_w_per_m"] - 1.0 * current) <= 1e-10 * current


def test_e2_parallel_layers_add_their_conductances():
    result = run(Document.from_dict(strip([TOP_HALF], {"dirichlet_potential_v": {"left": 2.0, "right": 0.0}})),
                 verbose=False)
    summary, fields = result.summary(), result.fields
    L = 2e-3
    current = 2.0 * (2.0 * 0.5e-3 + 0.5 * 0.5e-3) / L
    exact = 2.0 * (1.0 - fields["nodes_m"][:, 0] / L)
    assert np.max(np.abs(fields["potential_v"] - exact)) <= 1e-10
    terminal = summary["diagnostics"]["terminal_reaction_current_a_per_m"]
    assert abs(terminal["left"] - current) <= 1e-10 * current
    assert abs(summary["diagnostics"]["joule_power_w_per_m"] - 2.0 * current) <= 1e-10 * 2.0 * current
    # the region of each triangle and its conductivity are in the fields
    regions = summary["region_names"]
    sigma = np.array([summary["region_conductivity_s_m"][regions[i]] for i in fields["triangle_regions"]])
    np.testing.assert_array_equal(fields["conductivity_s_m"], sigma)


def coax(size, va=1.0, vb=0.0, sigma=3.0, segments=192):
    """A conducting disc of radius 9 mm with a void hole of radius 3 mm; both circles named."""
    cut = {"name": "cut", "type": "rect", "x": 0.0, "y": 0.0, "w": 40.0, "h": 20.0, "material": None}
    disc = {"name": "disc", "type": "circle", "cx": 20.0, "cy": 10.0, "r": 9.0, "material": "M"}
    hole = {"name": "hole", "type": "circle", "cx": 20.0, "cy": 10.0, "r": 3.0, "material": None}
    raw = strip([cut, disc, hole], {"dirichlet_potential_v": {"inner": va, "rim": vb}},
                materials={"M": {"electrical_conductivity_s_m": sigma}}, size=size, background="M",
                domain=(0, 40, 0, 20))
    comp = raw["geometry"]["components"]["xs"]
    comp["boundary_tags"] = [{"tag": "inner", "select": {"boundary": {"of": "hole"}}},
                             {"tag": "rim", "select": {"boundary": {"between": ["disc", "cut"]}}}]
    raw["mesh"]["controls"] = [{"select": "disc", "circle_segments": segments},
                               {"select": "hole", "circle_segments": segments}]
    return raw


def test_e3_coaxial_electrodes_converge_to_the_logarithmic_current():
    exact = 2 * math.pi * 3.0 * (1.0 - 0.0) / math.log(3.0)               # A per metre of depth
    errors = []
    for size in (0.8, 0.4, 0.2):
        summary = run(Document.from_dict(coax(size)), verbose=False).summary()
        current = summary["diagnostics"]["terminal_reaction_current_a_per_m"]["inner"]
        errors.append(abs(current - exact) / exact)
    assert errors[-1] <= 1e-3, errors
    order = math.log(errors[-2] / errors[-1], 2)
    assert order >= 1.5, (errors, order)


def test_e3_coaxial_potential_follows_the_logarithm():
    result = run(Document.from_dict(coax(0.4)), verbose=False)
    fields = result.fields
    r = np.hypot(fields["nodes_m"][:, 0] - 20e-3, fields["nodes_m"][:, 1] - 10e-3)
    exact = 1.0 - np.log(r / 3e-3) / math.log(3.0)
    mid = np.abs(r - 6e-3) < 0.25e-3
    assert mid.sum() >= 8
    assert np.max(np.abs(fields["potential_v"][mid] - exact[mid])) <= 1e-3


def test_e6_a_rectangle_document_keeps_the_rectangle_path():
    raw = copy.deepcopy(EXAMPLES["electric_rectangle"]) if "electric_rectangle" in EXAMPLES else None
    if raw is None:
        pytest.skip("no electric_rectangle example registered")
    result = run(Document.from_dict(raw), verbose=False)
    assert type(result).__name__ == "ElectricJouleRunResult"
    assert result.summary()["result_format"] == "electric.steady2d-result-v1"


@pytest.mark.parametrize("change, message", [
    (lambda raw: raw["physics"]["e"].update(dirichlet_potential_v={"left": 1.0, "iface": 0.5}),
     "selection 'iface' lies on an interface between two regions"),
    (lambda raw: raw["physics"]["e"].update(outward_current_a_m2={"iface": 1.0}),
     "selection 'iface' lies on an interface between two regions"),
    (lambda raw: raw["materials"]["B"].pop("electrical_conductivity_s_m"),
     "materials.B.electrical_conductivity_s_m: required by steady electric conduction"),
    (lambda raw: raw["physics"]["e"].update(conductivity_s_m=1.0),
     "a region document takes electrical conductivity from materials"),
    (lambda raw: raw["physics"]["e"].update(outward_current_a_m2={"left": 1.0}),
     "a current condition overlaps a fixed potential"),
    (lambda raw: raw["physics"]["e"].update(dirichlet_potential_v={}),
     "at least one boundary potential is required"),
    (lambda raw: raw["physics"]["e"].update(dirichlet_potential_v={"nowhere": 1.0}),
     "nowhere"),
    (lambda raw: raw["physics"]["e"].update(type="joule.steady2d"),
     "joule.steady2d: region geometry"),
])
def test_e7_refusals_name_what_is_wrong(change, message):
    raw = strip([RIGHT_HALF], {"dirichlet_potential_v": {"left": 1.0, "right": 0.0}},
                selections={"iface": {"boundary": {"between": ["b", "background"]}}})
    change(raw)
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(raw)


def test_e7_a_void_background_and_an_axisymmetric_component_are_refused():
    raw = strip([dict(RIGHT_HALF, material="B")], {"dirichlet_potential_v": {"right": 0.0}})
    raw["geometry"]["components"]["xs"]["background"] = {"material": None}
    with pytest.raises(DocumentError, match="region electric takes no void background"):
        Document.from_dict(raw)
    raw = strip([RIGHT_HALF], {"dirichlet_potential_v": {"right": 0.0}})
    raw["geometry"]["components"]["xs"]["dimension"] = "axisymmetric"
    with pytest.raises(DocumentError, match="axisymmetric component is not supported for electric conduction"):
        Document.from_dict(raw)


def test_a_current_on_an_exterior_tag_balances_the_electrode():
    raw = coax(0.8)
    raw["physics"]["e"]["dirichlet_potential_v"] = {"rim": 0.0}
    raw["physics"]["e"]["outward_current_a_m2"] = {"inner": -10.0}             # inward 10 A/m^2 at the hole
    summary = run(Document.from_dict(raw), verbose=False).summary()
    injected = 10.0 * 2 * math.pi * 3e-3                                      # A per metre of depth (polygon ~)
    rim = summary["diagnostics"]["terminal_reaction_current_a_per_m"]["rim"]
    assert abs(rim + injected) <= 1e-3 * injected                             # 192-gon perimeter
    assert abs(summary["diagnostics"]["current_balance_a_per_m"]) <= 1e-12 * injected


def test_a_saved_region_result_records_its_layout(tmp_path):
    result = run(Document.from_dict(strip([RIGHT_HALF], {"dirichlet_potential_v": {"left": 1.0, "right": 0.0}})),
                 verbose=False)
    result.save(tmp_path / "out")
    data = np.load(tmp_path / "out" / "fields.npz")
    assert str(data["field_layout"]) == "electric2d-p1-node-cell-regions-v1"
    assert str(data["result_format"]) == "electric.steady2d-regions-result-v1"
    assert data["triangle_regions"].shape == data["triangles"].shape[:1]


def test_mesh_limits_reach_a_region_electric_document():
    from simcase.mesh_limits import MeshLimitError
    from simcase import registry
    raw = strip([RIGHT_HALF], {"dirichlet_potential_v": {"left": 1.0, "right": 0.0}}, size=0.05)
    assert registry.kind_of(raw).accepts_mesh_limits(raw)
    with pytest.raises(MeshLimitError):
        run(Document.from_dict(raw), verbose=False, max_triangles=100)


def test_a_conductor_part_with_no_fixed_potential_is_refused_by_name():
    ring = {"name": "ring", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.4, "material": None}
    island = {"name": "island", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.2, "material": "B"}
    raw = strip([ring, island], {"dirichlet_potential_v": {"left": 1.0, "right": 0.0}}, size=0.1)
    with pytest.raises(DocumentError, match=r"conductor part with regions \['island'\] touches no fixed potential"):
        run(Document.from_dict(raw), verbose=False)


def test_two_potential_names_on_the_same_edges_are_refused_and_attribution_ignores_key_order():
    hole = {"name": "hole", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.3, "material": None}
    raw = strip([hole], {"dirichlet_potential_v": {"outer": 1.0, "left": 0.0, "hb": 1.0}}, size=0.1,
                selections={"hb": {"boundary": {"of": "hole"}}})
    with pytest.raises(DocumentError, match="'hb' and 'outer' share mesh edges"):
        run(Document.from_dict(raw), verbose=False)
    # one name per boundary; reversing the key order gives the same terminal currents
    forward = strip([hole], {"dirichlet_potential_v": {"outer": 1.0, "left": 0.0, "right": 0.0}}, size=0.1)
    backward = strip([hole], {"dirichlet_potential_v": {"right": 0.0, "left": 0.0, "outer": 1.0}}, size=0.1)
    a = run(Document.from_dict(forward), verbose=False).summary()["diagnostics"]["terminal_reaction_current_a_per_m"]
    b = run(Document.from_dict(backward), verbose=False).summary()["diagnostics"]["terminal_reaction_current_a_per_m"]
    assert a == b
    # positive in: the 1 V hole wall injects current, the grounded sides take it out
    assert a["outer"] > 0 and a["left"] < 0 and a["right"] < 0
    assert abs(a["outer"] + a["left"] + a["right"]) <= 1e-12 * a["outer"]


def test_a_current_on_edges_whose_nodes_are_fixed_is_refused_by_name():
    notch = {"name": "notch", "type": "rect", "x": 1.9, "y": 0.9, "w": 0.1, "h": 0.1, "material": None}
    raw = strip([notch], {"dirichlet_potential_v": {"wall": 0.0, "right": 0.0, "left": 1.0},
                          "outward_current_a_m2": {"ledge": 1.0}}, size=0.25,
                selections={"wall": {"boundary": "notch.left"}, "ledge": {"boundary": "notch.bottom"}})
    with pytest.raises(DocumentError, match="'ledge' has mesh edges whose nodes are fixed by"):
        run(Document.from_dict(raw), verbose=False)


def test_electric_key_refusals_do_not_say_thermal():
    raw = strip([RIGHT_HALF], {"dirichlet_potential_v": {"left": 1.0, "nowhere": 0.0}})
    with pytest.raises(DocumentError) as error:
        Document.from_dict(raw)
    assert "unsupported keys ['nowhere']" in str(error.value) and "thermal" not in str(error.value)


def test_a_region_result_exports_to_vtu_with_region_ids(tmp_path):
    meshio = pytest.importorskip("meshio")
    from simcase.export import SUPPORTED_LAYOUTS, export_fields
    assert SUPPORTED_LAYOUTS[-1] == "electric2d-p1-node-cell-regions-v1"
    result = run(Document.from_dict(strip([RIGHT_HALF], {"dirichlet_potential_v": {"left": 1.0, "right": 0.0}})),
                 verbose=False)
    result.save(tmp_path / "out")
    vtu = export_fields(tmp_path / "out" / "fields.npz", tmp_path / "out" / "fields.vtu")
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.point_data["potential_v"], result.fields["potential_v"])
    np.testing.assert_array_equal(mesh.cell_data["triangle_regions"][0], result.fields["triangle_regions"])
