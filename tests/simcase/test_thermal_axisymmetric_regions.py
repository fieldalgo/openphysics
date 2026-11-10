# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Axisymmetric steady region heat through a version 1 geometry block (stage 2c).

Pre-registered checks G4-1 to G4-5 (HQ work record, 2026-11-07): a version 1 ``axisymmetric``
component is meshed as (r, z) and solved with galerkin's axisymmetric measure; the result
carries its own identifiers with full-revolution rates in W.
"""
import copy
import math

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.examples import EXAMPLES

K_PLA, Q, TB = 1.114, 1e5, 293.15


def conductivity(k):
    return {"thermal_conductivity": f"{k!r} W/(m K)", "source": "document value"}


def cylinder(radius_mm=3.0, length_mm=1.0, size_mm=0.1, features=(), materials=None, source=Q, dirichlet=None,
             xmin=0.0, **physics):
    """A region heat document on the (r, z) rectangle [xmin, radius] x [0, length] in mm; ``source``
    (W/m^3, or {region: W/m^3}) and ``dirichlet`` ({name: K}) are numbers in SI."""
    heat = ({r: f"{q!r} W/m^3" for r, q in source.items()} if isinstance(source, dict) else f"{source!r} W/m^3")
    temperatures = {"right": TB} if dirichlet is None else dirichlet
    doc = {"openphysics": "0.3", "name": "axisymmetric cylinder",
           "geometry": {"version": 1, "components": {"rod": {
               "dimension": "axisymmetric", "length_unit": "mm",
               "domain": {"xmin": xmin, "xmax": radius_mm, "ymin": 0.0, "ymax": length_mm},
               "background": {"material": "pla"}, "features": list(features)}}},
           "materials": {"pla": conductivity(K_PLA), **(materials or {})},
           "physics": {"heat1": {"type": "thermal.steady2d", "heat_source_density": heat,
                                 "prescribed_temperature": {t: f"{v!r} K" for t, v in temperatures.items()},
                                 **physics}},
           "mesh": {"element_size": f"{size_mm!r} mm", "minimum_angle": "28 deg"}, "study": {"type": "single"},
           "results": {"save_fields": True, "plots": False}}
    return doc


def _axis_temperature(result):
    nodes = result.node_coordinates
    on_axis = np.abs(nodes[:, 0]) < 1e-12
    assert on_axis.sum() >= 3
    return float(np.mean(result.temperature[on_axis]))


def test_g4_1_a_uniformly_heated_cylinder_matches_the_exact_parabola_and_its_absorbed_power():
    doc = Document.from_dict(cylinder())
    assert doc.is_version_1 and doc.component.dimension == "axisymmetric"
    result = run(doc, verbose=False)
    R, L = 3e-3, 1e-3
    rise = Q * R ** 2 / (4 * K_PLA)
    assert abs(_axis_temperature(result) - TB - rise) <= 2e-3 * rise
    absorbed = float(result.generated_heat_rate.sum())
    assert abs(absorbed - Q * math.pi * R ** 2 * L) <= 1e-9 * Q * math.pi * R ** 2 * L
    summary = result.summary()
    assert summary["relative_conservation_residual"]["value"] <= 1e-10
    assert summary["coordinate_system"] == "axisymmetric" and "nodal_heat_rate_unit" not in summary
    assert set(summary["mesh"]) >= {"nodes", "triangles"} and summary["generated_heat_rate"]["unit"] == "W"
    # the exact parabola holds at every node, not only on the axis
    r = result.node_coordinates[:, 0]
    exact = TB + Q * (R ** 2 - r ** 2) / (4 * K_PLA)
    assert np.max(np.abs(result.temperature - exact)) <= 2e-3 * rise


def test_g4_2_a_heated_core_in_a_conducting_shell_matches_the_analytic_axis_and_interface_rise():
    a, R, k1, k2 = 1.0, 3.0, 2.0, 0.5                                   # mm, W/(m K)
    core = {"name": "core", "type": "rect", "x": 0.0, "y": 0.0, "w": a, "h": 1.0, "material": "copperish"}
    raw = cylinder(features=[core], materials={"copperish": conductivity(k1)}, source={"core": Q}, size_mm=0.05)
    raw["materials"]["pla"] = conductivity(k2)
    doc = Document.from_dict(raw)
    result = run(doc, verbose=False)
    a_m, R_m = a * 1e-3, R * 1e-3
    interface_rise = Q * a_m ** 2 / (2 * k2) * math.log(R_m / a_m)
    axis_rise = Q * a_m ** 2 / (4 * k1) + interface_rise
    assert abs(_axis_temperature(result) - TB - axis_rise) <= 2e-3 * axis_rise
    nodes = result.node_coordinates
    at_interface = np.abs(nodes[:, 0] - a_m) < 1e-12
    assert at_interface.sum() >= 3
    assert abs(float(np.mean(result.temperature[at_interface])) - TB - interface_rise) <= 2e-3 * axis_rise
    assert result.region_names == ["core", "background"]
    assert abs(float(result.generated_heat_rate.sum()) - Q * math.pi * a_m ** 2 * 1e-3) <= \
        1e-9 * Q * math.pi * a_m ** 2 * 1e-3


def test_g4_3_an_annulus_without_source_conducts_logarithmically_and_keeps_its_left_side():
    r1, r2, t1, t2 = 1.0, 3.0, 300.0, 400.0
    doc = Document.from_dict(cylinder(xmin=r1, source=0.0, size_mm=0.05, dirichlet={"left": t1, "right": t2}))
    result = run(doc, verbose=False)
    r = result.node_coordinates[:, 0]
    exact = t1 + (t2 - t1) * np.log(r / (r1 * 1e-3)) / math.log(r2 / r1)
    mid = np.abs(r - 2e-3) < 0.03e-3
    assert mid.sum() >= 3
    assert np.max(np.abs(result.temperature[mid] - exact[mid])) <= 1e-3 * (t2 - t1)
    assert set(result.summary()["prescribed_temperature"]) == {"left", "right"}


@pytest.mark.parametrize("physics, message", [
    ({"prescribed_temperature": {"axis": "300 K"}}, "'axis' is the symmetry axis"),
    ({"inward_heat_flux": {"axis": "-1 W/m^2"}}, "'axis' is the symmetry axis"),
    ({"convection": {"axis": {"heat_transfer_coefficient": "5 W/(m^2 K)", "ambient_temperature": "300 K"}}},
     "'axis' is the symmetry axis"),
    ({"prescribed_temperature": {"left": "300 K"}}, "has no left side; its r = 0 side is the axis"),
])
def test_g4_4_axis_data_and_a_left_side_at_r_zero_are_refused_by_name(physics, message):
    raw = cylinder()
    raw["physics"]["heat1"].update(physics)
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(raw)


def test_g4_4_the_waveguide_runner_refuses_an_axisymmetric_component_by_name():
    # the transient region runner takes an axisymmetric component since stage 2f (G7-5 below)
    from simcase.geometry_document import from_v02
    for xmin in (0.0, 1.0):                           # at r = 0 (an axis tag) and as an annulus (four plain tags)
        em = copy.deepcopy(EXAMPLES["soi_strip"])
        em["geometry"] = from_v02(em["geometry"])
        comp = em["geometry"]["components"]["main"]
        comp["dimension"] = "axisymmetric"
        del comp["depth"]                             # an axisymmetric component has no depth
        shift = xmin - comp["domain"]["xmin"]
        comp["domain"]["xmin"] += shift
        comp["domain"]["xmax"] += shift
        for f in comp["features"]:
            f["x"] += shift
        with pytest.raises(DocumentError, match="em.modes2d takes 2d components only"):
            Document.from_dict(em)


def test_g4_4_studio_refuses_an_axisymmetric_document_at_validation():
    from fastapi.testclient import TestClient
    from simcase.studio import server
    with TestClient(server.app) as client:
        response = client.post("/api/thermal/validate", json={"doc": cylinder(), "client_revision": 1, "request_seq": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False and "axisymmetric" in body["error"]["message"]


def test_g4_5_the_result_keeps_its_own_identifiers_and_full_revolution_field_names(tmp_path):
    result = run(Document.from_dict(cylinder()), verbose=False)
    assert result.result_format == "thermal.axisymmetric-regions-result-v2"
    assert result.field_layout == "thermal-axisymmetric-p1-node-cell-regions-v2"
    arrays = result._raw_arrays()
    assert "generated_heat_rate" in arrays and "reaction_heat_rate" in arrays
    assert not any(k.endswith("_per_depth") for k in arrays)
    assert set(arrays) >= {"outward_prescribed_heat_rate", "ambient_convective_heat_rate",
                           "outward_convective_heat_rate", "applied_heat_rate", "triangle_regions"}
    with pytest.raises(AttributeError, match="per-depth name"):
        result.generated_heat_rate_per_depth                             # full revolution: the plain name only
    summary = result.summary()
    assert summary["field_units"]["generated_heat_rate"] == "W" and summary["field_units"]["applied_heat_rate"] == "W"
    assert summary["field_components"]["node_coordinates"] == ["r", "z"]
    assert summary["field_locations"]["generated_heat_rate"] == "nodes"
    assert not any(k.endswith("_per_depth") for k in (*summary, *summary["field_shapes"]))
    result.save(tmp_path / "out")
    saved = np.load(tmp_path / "out" / "fields.npz")
    assert "generated_heat_rate" in saved.files
    assert str(saved["result_format"]) == "thermal.axisymmetric-regions-result-v2"
    # a Cartesian region document keeps the per-depth names
    plain = run(Document.from_dict(EXAMPLES["thermal_regions"]), verbose=False)
    assert plain.result_format == "thermal.steady2d-regions-result-v2"
    assert "generated_heat_rate_per_depth" in plain._raw_arrays()
    # the saved result exports to VTU with (r, z) points, the full-revolution rates and the region ids
    meshio = pytest.importorskip("meshio")
    from simcase.export import export_fields
    vtu = export_fields(tmp_path / "out" / "fields.npz", tmp_path / "out" / "view.vtu")
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.points[:, :2], saved["node_coordinates"])
    np.testing.assert_array_equal(mesh.point_data["generated_heat_rate"], saved["generated_heat_rate"])
    assert not any(k.endswith("_per_depth") for k in mesh.point_data) and "triangle_regions" in mesh.cell_data


# -- stage 2f: axisymmetric transient region heat (checks G7-5, HQ work record 2026-11-08) -----------------

C_PLA = 1.8e6


def cylinder_transient(times=(0.0, 1.0, 2.0), size_mm=0.2, source=Q, dirichlet=None, initial=TB, **physics):
    """The cylinder of ``cylinder`` as a transient document: PLA with a heat capacity, uniform initial field."""
    raw = cylinder(size_mm=size_mm, source=source, dirichlet=dirichlet)
    raw["name"] = "axisymmetric cylinder transient"
    raw["materials"]["pla"]["volumetric_heat_capacity"] = f"{C_PLA!r} J/(m^3 K)"
    raw["physics"]["heat1"].update({"type": "thermal.transient2d", "initial_temperature": f"{initial!r} K", **physics})
    raw["study"] = {"type": "transient", "time": {"unit": "s", "values": list(times)}}
    return raw


def test_g7_5_the_transient_result_keeps_its_own_identifiers_and_full_revolution_names(tmp_path):
    result = run(Document.from_dict(cylinder_transient()), verbose=False)
    assert type(result).__name__ == "AxisymmetricTransientRegionRunResult"
    assert result.result_format == "thermal.axisymmetric-transient-regions-result-v2"
    assert result.field_layout == "thermal-axisymmetric-transient-p1-node-cell-regions-v2"
    arrays = result._raw_arrays()
    assert not any(k.endswith("_per_depth") for k in arrays), sorted(arrays)
    assert set(arrays) >= {"generated_heat_rate", "reaction_heat_rate", "residual_heat_rate", "heat_storage_rate",
                           "stored_heat", "thermal_energy_functional", "triangle_regions", "prescribed_temperature"}
    assert np.array_equal(result.heat_storage_rate, arrays["heat_storage_rate"])     # the public read path
    assert np.array_equal(result.stored_heat, arrays["stored_heat"])
    with pytest.raises(AttributeError, match="per-depth name"):
        result.stored_heat_per_depth
    summary = result.summary()
    assert summary["result_format"] == "thermal.axisymmetric-transient-regions-result-v2"
    assert summary["coordinate_system"] == "axisymmetric" and "nodal_heat_rate_unit" not in summary
    units = summary["field_units"]
    assert units["generated_heat_rate"] == "W" and units["stored_heat"] == "J"
    assert units["thermal_energy_functional"] == "J K"
    assert summary["field_time_axes"]["heat_storage_rate"] == "time[1:]" and "heat_storage_rate_per_depth" not in units
    assert set(summary) >= {"generated_heat_rate", "heat_storage_rate", "outward_heat_rate", "heat_rate_imbalance",
                            "stored_heat", "thermal_energy_functional"}
    assert not any(k.endswith("_per_depth") for k in summary)
    # physics of the saved numbers: full-revolution source power and the exact uniform content at t0
    R, L = 3e-3, 1e-3
    assert abs(summary["generated_heat_rate"]["values"][-1]/(Q*math.pi*R*R*L)-1) < 1e-12
    assert abs(summary["stored_heat"]["values"][0]/(C_PLA*TB*math.pi*R*R*L)-1) < 1e-12
    scale = np.max(abs(arrays["heat_storage_rate"]).sum(axis=1)+abs(arrays["generated_heat_rate"][1:]).sum(axis=1)
                   +abs(arrays["reaction_heat_rate"]).sum(axis=1))
    assert np.max(np.abs(summary["heat_rate_imbalance"]["values"])) <= 1e-10*scale
    result.save(tmp_path / "out")
    saved = np.load(tmp_path / "out" / "fields.npz")
    assert str(saved["result_format"]) == "thermal.axisymmetric-transient-regions-result-v2"
    assert "heat_storage_rate" in saved.files and "heat_storage_rate_per_depth" not in saved.files
    # the Cartesian transient region example keeps the per-depth names
    plain = run(Document.from_dict(EXAMPLES["transient_thermal_regions"]), verbose=False)
    assert plain.result_format == "thermal.transient2d-regions-result-v2"
    assert "heat_storage_rate_per_depth" in plain._raw_arrays()
    assert plain.summary()["heat_content_definition"].endswith("0 K")
    # the saved history exports to VTU and PVD with (r, z) points, the full-revolution rates and the region ids
    meshio = pytest.importorskip("meshio")
    from simcase.export import SUPPORTED_LAYOUTS, export_fields, export_time_series
    assert SUPPORTED_LAYOUTS[13] == "thermal-axisymmetric-transient-p1-node-cell-regions-v2"   # later layouts go after it
    vtu = export_fields(tmp_path / "out" / "fields.npz", tmp_path / "out" / "last.vtu", time_index=-1)
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.points[:, :2], saved["node_coordinates"])
    np.testing.assert_array_equal(mesh.point_data["heat_storage_rate"], saved["heat_storage_rate"][-1])
    assert "triangle_regions" in mesh.cell_data and not any(k.endswith("_per_depth") for k in mesh.point_data)
    pvd = export_time_series(tmp_path / "out" / "fields.npz", tmp_path / "series")
    assert pvd.exists() and len(list(pvd.parent.glob("*.vtu"))) == 3


def test_g7_5_the_long_time_limit_equals_the_steady_axisymmetric_document():
    """A heated cylinder held at TB on its outer radius reaches the steady document's solution."""
    steady = run(Document.from_dict(cylinder(size_mm=0.2)), verbose=False)
    times = [0.0] + np.cumsum(2.0**np.arange(-4, 22)).tolist()
    transient = run(Document.from_dict(cylinder_transient(times=times)), verbose=False)
    np.testing.assert_array_equal(transient.node_coordinates, steady.node_coordinates)
    rise = float(np.max(abs(steady.temperature-TB)))
    assert rise > 0.1
    np.testing.assert_allclose(transient.temperature[-1], steady.temperature, rtol=0, atol=1e-6*rise)
    power = Q*math.pi*(3e-3)**2*1e-3
    assert abs(transient.reaction_heat_rate[-1].sum()/steady.reaction_heat_rate.sum()-1) < 1e-6
    assert abs(steady.reaction_heat_rate.sum()/power+1) < 1e-9
    assert abs(transient.heat_storage_rate[-1].sum()) < 1e-8*power


@pytest.mark.parametrize("dirichlet, message", [
    ({"axis": TB}, "'axis' is the symmetry axis"),
    ({"left": TB}, "has no left side; its r = 0 side is the axis"),
])
def test_g7_5_transient_axis_data_and_a_left_side_at_r_zero_are_refused_by_name(dirichlet, message):
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(cylinder_transient(dirichlet=dirichlet))


def test_g7_5_studio_refuses_a_transient_axisymmetric_document_at_validation():
    from fastapi.testclient import TestClient
    from simcase.studio import server
    with TestClient(server.app) as client:
        response = client.post("/api/thermal/transient/validate",
                               json={"doc": cylinder_transient(), "client_revision": 1, "request_seq": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False and "axisymmetric" in body["error"]["message"]
