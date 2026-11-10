# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``electric.steady2d`` on named material regions of a version 1 geometry block (stage ①-a).

Pre-registered checks E1 to E7 (HQ work record ``work/openphysics-geometry.md``,
2026-11-08), against independent closed forms: series and parallel layers, a coaxial pair
of circular electrodes, the discrete Joule identity, the rectangle path unchanged, and
refusals by name. E4 (a fixed potential on an interface selection) is refused instead:
galerkin.electric fixes exterior nodes only.

Format 0.3 (units batch C6): the documents are the converted 0.2 ones; the terminal currents
are ``balance.outward_current_per_depth`` (0.2 ``terminal_reaction_current_a_per_m``, positive
into the body, negated exactly), so each threshold keeps its value.
"""
import copy
import math

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.examples import EXAMPLES


def strip(features, physics, *, materials=None, size=0.25, selections=None, background="A", domain=(0, 2, 0, 1)):
    """A version 1 conduction document in mm on a 2 x 1 mm strip."""
    comp = {"dimension": "2d", "length_unit": "mm", "depth": None,
            "domain": dict(zip(("xmin", "xmax", "ymin", "ymax"), domain)),
            "background": {"material": background}, "features": features}
    if selections:
        comp["selections"] = selections
    return {"openphysics": "0.3", "name": "strip",
            "geometry": {"version": 1, "components": {"xs": comp}},
            "materials": materials or {"A": {"electrical_conductivity": "2 S/m"},
                                       "B": {"electrical_conductivity": "0.5 S/m"}},
            "physics": {"e": {"type": "electric.steady2d", **physics}},
            "mesh": {"element_size": f"{size} mm"}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False}}


def potentials(**volts):
    return {"prescribed_electric_potential": {side: f"{v} V" for side, v in volts.items()}}


def outward(summary):
    """The terminal currents, A per metre of depth, positive out of the body."""
    return {tag: entry["value"] for tag, entry in summary["balance"]["outward_current_per_depth"].items()}


def balance(summary, key):
    return summary["balance"][key]["value"]


RIGHT_HALF = {"name": "b", "type": "rect", "x": 1, "y": 0, "w": 1, "h": 1, "material": "B"}
TOP_HALF = {"name": "b", "type": "rect", "x": 0, "y": 0.5, "w": 2, "h": 0.5, "material": "B"}


def test_e1_series_layers_are_piecewise_linear_and_carry_v_over_r():
    result = run(Document.from_dict(strip([RIGHT_HALF], potentials(left=1.0, right=0.0))), verbose=False)
    summary, fields = result.summary(), result.fields
    assert summary["result_format"] == "electric.steady2d-regions-result-v2"
    assert {r: v["electrical_conductivity"] for r, v in summary["regions"].items()} == {
        "b": {"value": 0.5, "unit": "S/m"}, "background": {"value": 2.0, "unit": "S/m"}}
    L, h = 1e-3, 1e-3
    current = 1.0 / (L / (2.0 * h) + L / (0.5 * h))                      # A per metre of depth
    middle = 1.0 - current * L / (2.0 * h)
    x = fields["node_coordinates"][:, 0]
    exact = np.where(x <= L, 1.0 - (1.0 - middle) * x / L, middle * (2 * L - x) / L)
    assert np.max(np.abs(fields["electric_potential"] - exact)) <= 1e-10
    terminal = outward(summary)                                         # positive out of the body
    assert abs(terminal["left"] + current) <= 1e-10 * current
    assert abs(terminal["right"] - current) <= 1e-10 * current
    # E5: the discrete Joule power equals the supplied power V * I
    assert abs(balance(summary, "joule_power_per_depth") - 1.0 * current) <= 1e-10 * current


def test_e2_parallel_layers_add_their_conductances():
    result = run(Document.from_dict(strip([TOP_HALF], potentials(left=2.0, right=0.0))), verbose=False)
    summary, fields = result.summary(), result.fields
    L = 2e-3
    current = 2.0 * (2.0 * 0.5e-3 + 0.5 * 0.5e-3) / L
    exact = 2.0 * (1.0 - fields["node_coordinates"][:, 0] / L)
    assert np.max(np.abs(fields["electric_potential"] - exact)) <= 1e-10
    terminal = outward(summary)
    assert abs(terminal["left"] + current) <= 1e-10 * current
    assert abs(balance(summary, "joule_power_per_depth") - 2.0 * current) <= 1e-10 * 2.0 * current
    # the region of each triangle and its conductivity are in the fields
    regions = summary["region_names"]
    sigma = np.array([summary["regions"][regions[i]]["electrical_conductivity"]["value"]
                      for i in fields["triangle_regions"]])
    np.testing.assert_array_equal(fields["electrical_conductivity"], sigma)


def coax(size, va=1.0, vb=0.0, sigma=3.0, segments=192):
    """A conducting disc of radius 9 mm with a void hole of radius 3 mm; both circles named."""
    cut = {"name": "cut", "type": "rect", "x": 0.0, "y": 0.0, "w": 40.0, "h": 20.0, "material": None}
    disc = {"name": "disc", "type": "circle", "cx": 20.0, "cy": 10.0, "r": 9.0, "material": "M"}
    hole = {"name": "hole", "type": "circle", "cx": 20.0, "cy": 10.0, "r": 3.0, "material": None}
    raw = strip([cut, disc, hole], potentials(inner=va, rim=vb),
                materials={"M": {"electrical_conductivity": f"{sigma} S/m"}}, size=size, background="M",
                domain=(0, 40, 0, 20))
    comp = raw["geometry"]["components"]["xs"]
    comp["boundary_tags"] = [{"tag": "inner", "select": {"boundary": {"of": "hole"}}},
                             {"tag": "rim", "select": {"boundary": {"between": ["disc", "cut"]}}}]
    raw["mesh"]["controls"] = [{"select": "disc", "circle_segment_count": segments},
                               {"select": "hole", "circle_segment_count": segments}]
    return raw


def test_e3_coaxial_electrodes_converge_to_the_logarithmic_current():
    exact = 2 * math.pi * 3.0 * (1.0 - 0.0) / math.log(3.0)               # A per metre of depth
    errors = []
    for size in (0.8, 0.4, 0.2):
        summary = run(Document.from_dict(coax(size)), verbose=False).summary()
        current = 0.0 - outward(summary)["inner"]                         # into the body at the inner wall
        errors.append(abs(current - exact) / exact)
    assert errors[-1] <= 1e-3, errors
    order = math.log(errors[-2] / errors[-1], 2)
    assert order >= 1.5, (errors, order)


def test_e3_coaxial_potential_follows_the_logarithm():
    result = run(Document.from_dict(coax(0.4)), verbose=False)
    fields = result.fields
    r = np.hypot(fields["node_coordinates"][:, 0] - 20e-3, fields["node_coordinates"][:, 1] - 10e-3)
    exact = 1.0 - np.log(r / 3e-3) / math.log(3.0)
    mid = np.abs(r - 6e-3) < 0.25e-3
    assert mid.sum() >= 8
    assert np.max(np.abs(fields["electric_potential"][mid] - exact[mid])) <= 1e-3


def test_e6_a_rectangle_document_keeps_the_rectangle_path():
    raw = copy.deepcopy(EXAMPLES["electric_rectangle"]) if "electric_rectangle" in EXAMPLES else None
    if raw is None:
        pytest.skip("no electric_rectangle example registered")
    result = run(Document.from_dict(raw), verbose=False)
    assert type(result).__name__ == "ElectricJouleRunResult"
    assert result.summary()["result_format"] == "electric.steady2d-result-v2"


@pytest.mark.parametrize("change, message, code, path", [
    (lambda raw: raw["physics"]["e"].update(prescribed_electric_potential={"left": "1 V", "iface": "0.5 V"}),
     "selection 'iface' lies on an interface between two regions", "E-CONTRACT",
     "physics.e.prescribed_electric_potential.iface"),
    (lambda raw: raw["physics"]["e"].update(inward_current_density={"iface": "-1 A/m^2"}),
     "selection 'iface' lies on an interface between two regions", "E-CONTRACT",
     "physics.e.inward_current_density.iface"),
    (lambda raw: raw["materials"]["B"].pop("electrical_conductivity"),
     "materials.B.electrical_conductivity: required by steady electric conduction", "E-PROPERTY-MISSING",
     "materials.B.electrical_conductivity"),
    (lambda raw: raw["physics"]["e"].update(electrical_conductivity="1 S/m"),
     "a region document takes electrical_conductivity from materials", "E-CONTRACT",
     "physics.e.electrical_conductivity"),
    (lambda raw: raw["physics"]["e"].update(inward_current_density={"left": "-1 A/m^2"}),
     "a current condition overlaps a fixed potential", "E-CONTRACT", "physics.e.inward_current_density.left"),
    (lambda raw: raw["physics"]["e"].update(prescribed_electric_potential={}),
     "at least one boundary potential is required", "E-CONTRACT", "physics.e.prescribed_electric_potential"),
    (lambda raw: raw["physics"]["e"].update(prescribed_electric_potential={"nowhere": "1 V"}),
     "nowhere", "E-SELECTION-UNKNOWN", "physics.e.prescribed_electric_potential.nowhere"),
    (lambda raw: raw["physics"]["e"].update(type="joule.temperature2d"),
     "joule.temperature2d: region geometry", "E-CONTRACT", "physics.e.type"),
])
def test_e7_refusals_name_what_is_wrong(change, message, code, path):
    raw = strip([RIGHT_HALF], potentials(left=1.0, right=0.0),
                selections={"iface": {"boundary": {"between": ["b", "background"]}}})
    change(raw)
    with pytest.raises(DocumentError, match=message) as error:
        Document.from_dict(raw)
    assert [(d.code, d.path) for d in error.value.diagnostics if d.severity == "error"] == [(code, path)]


def test_e7_a_void_background_and_an_axisymmetric_component_are_refused():
    raw = strip([dict(RIGHT_HALF, material="B")], potentials(right=0.0))
    raw["geometry"]["components"]["xs"]["background"] = {"material": None}
    with pytest.raises(DocumentError, match="region electric takes no void background"):
        Document.from_dict(raw)
    raw = strip([RIGHT_HALF], potentials(right=0.0))
    raw["geometry"]["components"]["xs"]["dimension"] = "axisymmetric"
    del raw["geometry"]["components"]["xs"]["depth"]          # an axisymmetric component has none
    with pytest.raises(DocumentError, match="axisymmetric component is not supported for electric conduction"):
        Document.from_dict(raw)


def test_a_current_on_an_exterior_tag_balances_the_electrode():
    raw = coax(0.8)
    raw["physics"]["e"]["prescribed_electric_potential"] = {"rim": "0 V"}
    raw["physics"]["e"]["inward_current_density"] = {"inner": "10 A/m^2"}     # inward 10 A/m^2 at the hole
    summary = run(Document.from_dict(raw), verbose=False).summary()
    injected = 10.0 * 2 * math.pi * 3e-3                                      # A per metre of depth (polygon ~)
    rim = outward(summary)["rim"]
    assert abs(rim - injected) <= 1e-3 * injected                             # 192-gon perimeter
    assert abs(balance(summary, "current_imbalance_per_depth")) <= 1e-12 * injected


def test_a_saved_region_result_records_its_layout(tmp_path):
    result = run(Document.from_dict(strip([RIGHT_HALF], potentials(left=1.0, right=0.0))), verbose=False)
    result.save(tmp_path / "out")
    with np.load(tmp_path / "out" / "fields.npz") as data:
        assert str(data["field_layout"]) == "electric2d-p1-node-cell-regions-v2"
        assert str(data["result_format"]) == "electric.steady2d-regions-result-v2"
        assert data["triangle_regions"].shape == data["triangles"].shape[:1]


def test_mesh_limits_reach_a_region_electric_document():
    from simcase.mesh_limits import MeshLimitError
    from simcase import registry
    raw = strip([RIGHT_HALF], potentials(left=1.0, right=0.0), size=0.05)
    assert registry.kind_of(raw).accepts_mesh_limits(raw)
    with pytest.raises(MeshLimitError):
        run(Document.from_dict(raw), verbose=False, max_triangles=100)


def test_a_conductor_part_with_no_fixed_potential_is_refused_by_name():
    ring = {"name": "ring", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.4, "material": None}
    island = {"name": "island", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.2, "material": "B"}
    raw = strip([ring, island], potentials(left=1.0, right=0.0), size=0.1)
    with pytest.raises(DocumentError, match=r"conductor part with regions \['island'\] touches no fixed potential"):
        run(Document.from_dict(raw), verbose=False)


def test_two_potential_names_on_the_same_edges_are_refused_and_attribution_ignores_key_order():
    hole = {"name": "hole", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.3, "material": None}
    raw = strip([hole], potentials(outer=1.0, left=0.0, hb=1.0), size=0.1,
                selections={"hb": {"boundary": {"of": "hole"}}})
    with pytest.raises(DocumentError, match="'hb' and 'outer' share mesh edges"):
        run(Document.from_dict(raw), verbose=False)
    # one name per boundary; reversing the key order gives the same terminal currents
    forward = strip([hole], potentials(outer=1.0, left=0.0, right=0.0), size=0.1)
    backward = strip([hole], potentials(right=0.0, left=0.0, outer=1.0), size=0.1)
    a = outward(run(Document.from_dict(forward), verbose=False).summary())
    b = outward(run(Document.from_dict(backward), verbose=False).summary())
    assert a == b
    # positive out: the 1 V hole wall injects current (negative outward), the grounded sides take it out
    assert a["outer"] < 0 and a["left"] > 0 and a["right"] > 0
    assert abs(a["outer"] + a["left"] + a["right"]) <= 1e-12 * -a["outer"]


def test_a_current_on_edges_whose_nodes_are_fixed_is_refused_by_name():
    notch = {"name": "notch", "type": "rect", "x": 1.9, "y": 0.9, "w": 0.1, "h": 0.1, "material": None}
    raw = strip([notch], {**potentials(wall=0.0, right=0.0, left=1.0),
                          "inward_current_density": {"ledge": "-1 A/m^2"}}, size=0.25,
                selections={"wall": {"boundary": "notch.left"}, "ledge": {"boundary": "notch.bottom"}})
    with pytest.raises(DocumentError, match="'ledge' has mesh edges whose nodes are fixed by"):
        run(Document.from_dict(raw), verbose=False)


def test_electric_key_refusals_do_not_say_thermal():
    raw = strip([RIGHT_HALF], potentials(left=1.0, nowhere=0.0))
    with pytest.raises(DocumentError) as error:
        Document.from_dict(raw)
    assert "nowhere" in str(error.value) and "thermal" not in str(error.value)
    assert [(d.code, d.path) for d in error.value.diagnostics] == [
        ("E-SELECTION-UNKNOWN", "physics.e.prescribed_electric_potential.nowhere")]


def test_a_region_result_exports_to_vtu_with_region_ids(tmp_path):
    meshio = pytest.importorskip("meshio")
    from simcase.export import SUPPORTED_LAYOUTS, export_fields
    assert SUPPORTED_LAYOUTS[14] == "electric2d-p1-node-cell-regions-v2"
    result = run(Document.from_dict(strip([RIGHT_HALF], potentials(left=1.0, right=0.0))), verbose=False)
    result.save(tmp_path / "out")
    vtu = export_fields(tmp_path / "out" / "fields.npz", tmp_path / "out" / "fields.vtu")
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.point_data["electric_potential"], result.fields["electric_potential"])
    np.testing.assert_array_equal(mesh.cell_data["triangle_regions"][0], result.fields["triangle_regions"])
