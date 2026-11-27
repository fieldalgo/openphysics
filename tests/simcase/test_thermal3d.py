# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``thermal.steady3d``: steady heat on a ``3d`` geometry component.

Checks (fixed before measuring):

- P1 through the kind on E1 (three slab layers, the meshine.extrude route) against
  galerkin_refsol's layered slab, exact for P1: max nodal |T_h - T| <= 1e-10 and the top
  heat rate (the reaction heat rate on z1) within a relative 1e-9, at h = 0.8 and 0.4 mm.
- Bit identity with the engines called directly on the same document, SHA-256 of the nodes,
  tetrahedra, temperature and reaction heat rate: E1 against meshine.extrude +
  solve_steady_heat_3d, and E1 with a copper box (the meshloom route) against
  build_mesh3d + solve_steady_heat_3d.
- Refusals by name: a fixed temperature on an interior face, unknown boundary names and
  regions, missing conductivities, keys the kind does not take, a 2d component.
"""

import copy
import hashlib
import json
from fractions import Fraction

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from simcase import Document, DocumentError, run  # noqa: E402

K = {"lower": 1.0, "core": 0.01, "upper": 1.0}
LEVELS_MM = [0, 1, 1.5, 2.5]
VIA = {"name": "via", "type": "box", "xmin": 4, "xmax": 6, "ymin": 4, "ymax": 6, "zmin": 1, "zmax": 1.5,
       "material": "cu"}


def e1(h_mm=0.8, *, via=False, physics=None, component=None):
    features = [{"name": "stack", "type": "layers", "z0": 0, "layers": [
        {"name": "a", "thickness": 1, "material": "lower"},
        {"name": "b", "thickness": 0.5, "material": "core"},
        {"name": "c", "thickness": 1, "material": "upper"}]}]
    if via:
        features.append(dict(VIA))
    comp = {"dimension": "3d", "length_unit": "mm",
            "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5},
            "background": {"material": None}, "features": features}
    comp.update(component or {})
    return {"openphysics": "0.3", "name": "E1",
            "geometry": {"version": 1, "components": {"pkg": comp}},
            "materials": {"lower": {"thermal_conductivity": "1 W/(m K)"},
                          "core": {"thermal_conductivity": "0.01 W/(m K)"},
                          "upper": {"thermal_conductivity": "1 W/(m K)"},
                          "cu": {"thermal_conductivity": "400 W/(m K)"}},
            "physics": {"heat": physics or {"type": "thermal.steady3d",
                                            "prescribed_temperature": {"z0": "300 K", "z1": "301 K"}}},
            "mesh": {"element_size": f"{h_mm} mm"}}


def _sha(mesh, temperature, reaction):
    h = hashlib.sha256()
    for a in (np.asarray(mesh.nodes, dtype=float), np.asarray(mesh.tets, dtype=np.int64),
              np.asarray(temperature, dtype=float), np.asarray(reaction, dtype=float)):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


# ----------------------------------------------------------------------------- P1

@pytest.mark.parametrize("h_mm", [0.8, 0.4])
def test_p1_e1_through_the_kind_is_exact(h_mm):
    from refsol.thermal3d import layered_slab
    result = run(Document.from_dict(e1(h_mm)), verbose=False)
    assert result.route == "extrude"
    exact = layered_slab(result.node_coordinates, position=[z * 1e-3 for z in LEVELS_MM],
                         thermal_conductivity=list(K.values()), prescribed_temperature=(300.0, 301.0))
    error = float(np.max(np.abs(result.temperature - exact.temperature)))
    top = result.mesh.boundary["z1"]
    rate = float(result.reaction_heat_rate[top].sum())
    expected = float(-exact.heat_flux[0, 2]) * 1e-4                 # W through the 10 x 10 mm top
    assert error <= 1e-10, f"h={h_mm}: max |T_h - T| = {error:.3e}"
    assert abs(rate - expected) <= 1e-9 * abs(expected), (rate, expected)
    by_boundary = result.summary()["reaction_heat_rate_by_boundary"]
    assert by_boundary["z1"] == {"value": rate, "unit": "W"}


# ----------------------------------------------------------------------------- bit identity

def _direct_extrude(data):
    """E1 by hand: the domain rectangle meshed by meshine, extruded through the levels, solved."""
    from galerkin import from_mesher
    from galerkin.thermal3d import solve_steady_heat_3d
    from meshine import Domain, box_sides, extrude, generate, rectangle
    from simcase.geometry_document import layer_stack, parse
    h = float(Fraction(8, 10) / 1000)
    d = Domain(size=h)
    d.add_region("plate", rectangle(0.0, 0.0, 0.01, 0.01))
    footprint = generate(d, box_sides(0.0, 0.01, 0.0, 0.01))
    stack = layer_stack(parse(data), "pkg")
    mesh = from_mesher(extrude(footprint, [float(Fraction(z, 10 ** 12)) for z in stack.levels],
                               stack.table_for(footprint.region_names), size=h))
    fixed = {int(n): 300.0 for n in np.unique(mesh.boundary["z0"])}
    fixed.update({int(n): 301.0 for n in np.unique(mesh.boundary["z1"])})
    solution = solve_steady_heat_3d(mesh, thermal_conductivity={r: K[r] for r in mesh.region_names},
                                    prescribed_temperature=dict(sorted(fixed.items())))
    return mesh, solution


def _direct_meshloom(data):
    """The meshloom document by hand: build_mesh3d, then solve_steady_heat_3d."""
    from galerkin.thermal3d import solve_steady_heat_3d
    from simcase import build_mesh3d
    mesh = build_mesh3d(data).mesh
    fixed = {int(n): 300.0 for n in np.unique(mesh.tagged_faces["z0"])}
    fixed.update({int(n): 301.0 for n in np.unique(mesh.tagged_faces["z1"])})
    kappa = {**K, "via": 400.0}                                # region via, material cu
    solution = solve_steady_heat_3d(mesh, thermal_conductivity={r: kappa[r] for r in mesh.region_names},
                                    prescribed_temperature=dict(sorted(fixed.items())))
    return mesh, solution


@pytest.mark.parametrize("via, direct", [(False, _direct_extrude), (True, _direct_meshloom)],
                         ids=["E1-extrude", "E1-via-meshloom"])
def test_the_kind_equals_the_engines_called_directly_bit_for_bit(via, direct):
    data = e1(0.8, via=via)
    result = run(Document.from_dict(copy.deepcopy(data)), verbose=False)
    assert result.route == ("meshloom" if via else "extrude")
    mesh, solution = direct(data)
    assert _sha(result.mesh, result.temperature, result.reaction_heat_rate) == \
        _sha(mesh, solution.temperature, solution.reaction_heat_rate)


# ----------------------------------------------------------------------------- reading and refusals

def _refused(data):
    with pytest.raises(DocumentError) as err:
        Document.from_dict(data)
    return err.value


def test_a_fixed_temperature_on_an_interior_face_is_refused_by_name():
    physics = {"type": "thermal.steady3d", "prescribed_temperature": {"z0": "300 K", "via.z0": "301 K"}}
    err = _refused(e1(via=True, physics=physics))
    assert err.code == "E-CONTRACT"
    assert err.path == "physics.heat.prescribed_temperature.via.z0"
    assert "Fixed temperature needs an outer face; via.z0 is inside" in str(err)


def test_boundary_names_resolve_by_the_selector_rules():
    sel = {"bottom_face": {"boundary": "domain.z0"}}
    physics = {"type": "thermal.steady3d", "prescribed_temperature": {"bottom_face": "300 K", "stack.c.top": "301 K"}}
    result = run(Document.from_dict(e1(via=True, physics=physics, component={"selections": sel})), verbose=False)
    assert result.route == "meshloom"
    assert np.array_equal(np.unique(result.by_key["bottom_face"]), np.unique(result.mesh.tagged_faces["z0"]))
    assert np.array_equal(np.unique(result.by_key["stack.c.top"]), np.unique(result.mesh.tagged_faces["z1"]))


@pytest.mark.parametrize("physics, path, code", [
    ({"type": "thermal.steady3d", "prescribed_temperature": {"lid": "300 K"}},
     "physics.heat.prescribed_temperature.lid", "E-SELECTION-UNKNOWN"),
    ({"type": "thermal.steady3d", "prescribed_temperature": {"z0": "300 K"}, "heat_source_density": {"nope": "1 W/m^3"}},
     "physics.heat.heat_source_density.nope", "E-SELECTION-UNKNOWN"),
    ({"type": "thermal.steady3d", "prescribed_temperature": {"z0": "300 K"}, "inward_heat_flux": {"z1": "1 W/m^2"}},
     "physics.heat.inward_heat_flux", "E-KEY-UNKNOWN"),
    ({"type": "thermal.steady3d"}, "physics.heat.prescribed_temperature", "E-KEY-MISSING"),
])
def test_refusals_name_the_path(physics, path, code):
    for via in (False, True):
        err = _refused(e1(via=via, physics=copy.deepcopy(physics)))
        assert (err.code, err.path) == (code, path), (via, str(err))


def test_a_missing_conductivity_is_refused():
    data = e1()
    del data["materials"]["core"]["thermal_conductivity"]
    data["materials"]["core"]["volumetric_heat_capacity"] = "1 MJ/(m^3 K)"
    err = _refused(data)
    assert err.code == "E-PROPERTY-MISSING" and err.path == "materials.core.thermal_conductivity"


def test_a_2d_component_is_refused_by_name():
    data = e1()
    comp = data["geometry"]["components"]["pkg"]
    comp.update({"dimension": "2d", "depth": None, "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10},
                 "features": []})
    comp["background"] = {"material": "lower"}
    err = _refused(data)
    assert err.path == "geometry.components.pkg.dimension"
    assert "thermal.steady3d takes a 3d component" in str(err)


def test_insulated_boundaries_are_reported():
    doc = Document.from_dict(e1())
    infos = sorted(d.path for d in doc.diagnostics if d.code == "I-DEFAULT-BOUNDARY")
    assert infos == [f"physics.heat.prescribed_temperature.{t}" for t in ("bottom", "left", "right", "top")]


# ----------------------------------------------------------------------------- saved results

def test_the_result_saves_like_the_2d_kind(tmp_path):
    result = run(Document.from_dict(e1(via=True)), verbose=False)
    out = result.save(tmp_path / "out")
    assert sorted(p.name for p in out.iterdir()) == ["fields.npz", "log.txt", "model.json", "summary.json"]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert (summary["result_format"], summary["field_layout"]) == ("thermal.steady3d-result-v1",
                                                                   "thermal3d-p1-node-tet-regions-v1")
    assert summary["physics_type"] == "thermal.steady3d" and summary["mesh_route"] == "meshloom"
    assert [d["code"] for d in summary["diagnostics"]].count("I-MESH-ESTIMATE") == 1
    assert set(summary["region_names"]) == {"lower", "via", "core", "upper"}
    rates = summary["reaction_heat_rate_by_boundary"]
    assert abs(rates["z0"]["value"] + rates["z1"]["value"]) <= 1e-9 * abs(rates["z1"]["value"])
    assert summary["relative_conservation_residual"]["value"] <= 1e-10
    with np.load(out / "fields.npz") as f:
        assert sorted(f.files) == sorted(["node_coordinates", "tetrahedra", "tetrahedron_regions", "temperature",
                                          "heat_flux", "generated_heat_rate", "reaction_heat_rate",
                                          "residual_heat_rate", "prescribed_node_ids", "prescribed_temperature",
                                          "result_format", "field_layout", "metadata_json"])
        assert str(f["field_layout"]) == "thermal3d-p1-node-tet-regions-v1"
        assert f["node_coordinates"].shape == (result.mesh.num_nodes, 3)
        np.testing.assert_array_equal(f["temperature"], result.temperature)
    assert summary["field_units"]["temperature"] == "K" and summary["field_units"]["reaction_heat_rate"] == "W"


def test_export_refuses_the_3d_layout_by_name(tmp_path):
    from simcase.export import export_fields
    out = run(Document.from_dict(e1()), verbose=False).save(tmp_path / "out")
    with pytest.raises(ValueError, match="thermal3d-p1-node-tet-regions-v1"):
        export_fields(out / "fields.npz", tmp_path / "x.vtu")
