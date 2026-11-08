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


def cylinder(radius_mm=3.0, length_mm=1.0, size_mm=0.1, features=(), materials=None, source=Q, dirichlet=None,
             xmin=0.0, **physics):
    """A region heat document on the (r, z) rectangle [xmin, radius] x [0, length] in mm."""
    doc = {"openphysics": "0.2", "name": "axisymmetric cylinder", "units": {"length": "mm", "temperature": "K"},
           "geometry": {"version": 1, "components": {"rod": {
               "dimension": "axisymmetric", "domain": {"xmin": xmin, "xmax": radius_mm, "ymin": 0.0, "ymax": length_mm},
               "background": {"material": "pla"}, "features": list(features)}}},
           "materials": {"pla": {"conductivity_w_mk": K_PLA, "source": "document value"}, **(materials or {})},
           "physics": {"heat1": {"type": "thermal.steady2d", "heat_source_w_m3": source,
                                 "dirichlet_temperature_k": {"right": TB} if dirichlet is None else dirichlet,
                                 **physics}},
           "mesh": {"size": size_mm, "min_angle": 28.0}, "study": {"type": "single"},
           "results": {"save_fields": True, "plots": False}}
    return doc


def _axis_temperature(result):
    nodes = result.mesh_nodes_m
    on_axis = np.abs(nodes[:, 0]) < 1e-12
    assert on_axis.sum() >= 3
    return float(np.mean(result.temperature_k[on_axis]))


def test_g4_1_a_uniformly_heated_cylinder_matches_the_exact_parabola_and_its_absorbed_power():
    doc = Document.from_dict(cylinder())
    assert doc.is_version_1 and doc.component.dimension == "axisymmetric"
    result = run(doc, verbose=False)
    R, L = 3e-3, 1e-3
    rise = Q * R ** 2 / (4 * K_PLA)
    assert abs(_axis_temperature(result) - TB - rise) <= 2e-3 * rise
    absorbed = float(result.load_w.sum())
    assert abs(absorbed - Q * math.pi * R ** 2 * L) <= 1e-9 * Q * math.pi * R ** 2 * L
    summary = result.summary()
    assert summary["normalized_heat_balance_defect"] <= 1e-10
    assert summary["coordinate_system"] == "axisymmetric" and summary["nodal_heat_rate_unit"] == "W"
    assert set(summary["mesh"]) >= {"nodes", "triangles"} and "source_heat_w" in summary
    # the exact parabola holds at every node, not only on the axis
    r = result.mesh_nodes_m[:, 0]
    exact = TB + Q * (R ** 2 - r ** 2) / (4 * K_PLA)
    assert np.max(np.abs(result.temperature_k - exact)) <= 2e-3 * rise


def test_g4_2_a_heated_core_in_a_conducting_shell_matches_the_analytic_axis_and_interface_rise():
    a, R, k1, k2 = 1.0, 3.0, 2.0, 0.5                                   # mm, W/(m K)
    core = {"name": "core", "type": "rect", "x": 0.0, "y": 0.0, "w": a, "h": 1.0, "material": "copperish"}
    doc = Document.from_dict(cylinder(features=[core], materials={"copperish": {"conductivity_w_mk": k1,
                                                                                 "source": "document value"}},
                                      source={"core": Q}, size_mm=0.05))
    doc.data["materials"]["pla"]["conductivity_w_mk"] = k2
    doc = Document.from_dict(doc.to_dict())
    result = run(doc, verbose=False)
    a_m, R_m = a * 1e-3, R * 1e-3
    interface_rise = Q * a_m ** 2 / (2 * k2) * math.log(R_m / a_m)
    axis_rise = Q * a_m ** 2 / (4 * k1) + interface_rise
    assert abs(_axis_temperature(result) - TB - axis_rise) <= 2e-3 * axis_rise
    nodes = result.mesh_nodes_m
    at_interface = np.abs(nodes[:, 0] - a_m) < 1e-12
    assert at_interface.sum() >= 3
    assert abs(float(np.mean(result.temperature_k[at_interface])) - TB - interface_rise) <= 2e-3 * axis_rise
    assert result.region_names == ["core", "background"]
    assert abs(float(result.load_w.sum()) - Q * math.pi * a_m ** 2 * 1e-3) <= 1e-9 * Q * math.pi * a_m ** 2 * 1e-3


def test_g4_3_an_annulus_without_source_conducts_logarithmically_and_keeps_its_left_side():
    r1, r2, t1, t2 = 1.0, 3.0, 300.0, 400.0
    doc = Document.from_dict(cylinder(xmin=r1, source=0.0, size_mm=0.05, dirichlet={"left": t1, "right": t2}))
    result = run(doc, verbose=False)
    r = result.mesh_nodes_m[:, 0]
    exact = t1 + (t2 - t1) * np.log(r / (r1 * 1e-3)) / math.log(r2 / r1)
    mid = np.abs(r - 2e-3) < 0.03e-3
    assert mid.sum() >= 3
    assert np.max(np.abs(result.temperature_k[mid] - exact[mid])) <= 1e-3 * (t2 - t1)
    assert set(result.summary()["dirichlet_temperature_k"]) == {"left", "right"}


@pytest.mark.parametrize("physics, message", [
    ({"dirichlet_temperature_k": {"axis": 300.0}}, "'axis' is the symmetry axis"),
    ({"outward_flux_w_m2": {"axis": 1.0}}, "'axis' is the symmetry axis"),
    ({"convection": {"axis": {"h_w_m2k": 5.0, "ambient_temperature_k": 300.0}}}, "'axis' is the symmetry axis"),
    ({"dirichlet_temperature_k": {"left": 300.0}}, "has no left side; its r = 0 side is the axis"),
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
    assert result.result_format == "thermal.axisymmetric-regions-result-v1"
    assert result.field_layout == "thermal-axisymmetric-p1-node-cell-regions-v1"
    arrays = result._raw_arrays()
    assert "load_w" in arrays and "reaction_w" in arrays and not any(k.endswith("_w_per_m") for k in arrays)
    assert set(arrays) >= {"prescribed_outward_load_w", "ambient_load_w", "convective_outward_w", "system_rhs_w",
                           "triangle_regions"}
    assert np.array_equal(result.load_w, result.load_w_per_m)          # the inherited read path serves the same array
    summary = result.summary()
    assert summary["field_units"]["load_w"] == "W" and summary["field_units"]["system_rhs_w"] == "W"
    assert summary["field_locations"]["load_w"] == "nodes" and "load_w_per_m" not in summary["field_shapes"]
    result.save(tmp_path / "out")
    saved = np.load(tmp_path / "out" / "fields.npz")
    assert "load_w" in saved.files and str(saved["result_format"]) == "thermal.axisymmetric-regions-result-v1"
    # a Cartesian region document keeps its identifiers and names
    plain = run(Document.from_dict(EXAMPLES["thermal_regions"]), verbose=False)
    assert plain.result_format == "thermal.steady2d-regions-result-v1" and "load_w_per_m" in plain._raw_arrays()
    # the saved result exports to VTU with (r, z) points, the _w rates and the region ids
    meshio = pytest.importorskip("meshio")
    from simcase.export import export_fields
    vtu = export_fields(tmp_path / "out" / "fields.npz", tmp_path / "out" / "view.vtu")
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.points[:, :2], saved["nodes_m"])
    np.testing.assert_array_equal(mesh.point_data["load_w"], saved["load_w"])
    assert "load_w_per_m" not in mesh.point_data and "triangle_regions" in mesh.cell_data


# -- stage 2f: axisymmetric transient region heat (checks G7-5, HQ work record 2026-11-08) -----------------

C_PLA = 1.8e6


def cylinder_transient(times=(0.0, 1.0, 2.0), size_mm=0.2, source=Q, dirichlet=None, initial=TB, **physics):
    """The cylinder of ``cylinder`` as a transient document: PLA with a heat capacity, uniform initial field."""
    raw = cylinder(size_mm=size_mm, source=source, dirichlet=dirichlet)
    raw["name"] = "axisymmetric cylinder transient"
    raw["units"]["time"] = "s"
    raw["materials"]["pla"]["volumetric_heat_capacity_j_m3k"] = C_PLA
    raw["physics"]["heat1"].update({"type": "thermal.transient2d", "initial_temperature_k": initial, **physics})
    raw["study"] = {"type": "transient", "time_s": list(times)}
    return raw


def test_g7_5_the_transient_result_keeps_its_own_identifiers_and_full_revolution_names(tmp_path):
    result = run(Document.from_dict(cylinder_transient()), verbose=False)
    assert type(result).__name__ == "AxisymmetricTransientRegionRunResult"
    assert result.result_format == "thermal.axisymmetric-transient-regions-result-v1"
    assert result.field_layout == "thermal-axisymmetric-transient-p1-node-cell-regions-v1"
    arrays = result._raw_arrays()
    assert not any(k.endswith("_per_m") for k in arrays), sorted(arrays)
    assert set(arrays) >= {"source_load_w", "reaction_w", "residual_w", "storage_rate_w", "heat_content_j",
                           "quadratic_functional_jk", "triangle_regions", "dirichlet_temperatures_k"}
    assert np.array_equal(result.storage_rate_w, result.storage_rate_w_per_m)   # the inherited read path
    assert np.array_equal(result.heat_content_j, result.heat_content_j_per_m)
    summary = result.summary()
    assert summary["result_format"] == "thermal.axisymmetric-transient-regions-result-v1"
    assert summary["coordinate_system"] == "axisymmetric" and summary["nodal_heat_rate_unit"] == "W"
    units = summary["field_units"]
    assert units["source_load_w"] == "W" and units["heat_content_j"] == "J" and units["quadratic_functional_jk"] == "J K"
    assert summary["field_time_axes"]["storage_rate_w"] == "time_s[1:]" and "storage_rate_w_per_m" not in units
    assert set(summary) >= {"source_heat_w", "storage_heat_w", "outward_heat_w", "heat_balance_defect_w",
                            "heat_content_j", "quadratic_functional_jk"}
    assert not any(k.endswith("_per_m") for k in summary)
    # physics of the saved numbers: full-revolution source power and the exact uniform content at t0
    R, L = 3e-3, 1e-3
    assert abs(summary["source_heat_w"][-1]/(Q*math.pi*R*R*L)-1) < 1e-12
    assert abs(summary["heat_content_j"][0]/(C_PLA*TB*math.pi*R*R*L)-1) < 1e-12
    scale = np.max(abs(arrays["storage_rate_w"]).sum(axis=1)+abs(arrays["source_load_w"][1:]).sum(axis=1)
                   +abs(arrays["reaction_w"]).sum(axis=1))
    assert np.max(np.abs(summary["heat_balance_defect_w"])) <= 1e-10*scale
    result.save(tmp_path / "out")
    saved = np.load(tmp_path / "out" / "fields.npz")
    assert str(saved["result_format"]) == "thermal.axisymmetric-transient-regions-result-v1"
    assert "storage_rate_w" in saved.files and "storage_rate_w_per_m" not in saved.files
    # the Cartesian transient region example keeps its identifiers and names
    plain = run(Document.from_dict(EXAMPLES["transient_thermal_regions"]), verbose=False)
    assert plain.result_format == "thermal.transient2d-regions-result-v1"
    assert "storage_rate_w_per_m" in plain._raw_arrays() and plain.summary()["heat_content_definition"].endswith("0 K")
    # the saved history exports to VTU and PVD with (r, z) points, the _w rates and the region ids
    meshio = pytest.importorskip("meshio")
    from simcase.export import SUPPORTED_LAYOUTS, export_fields, export_time_series
    assert SUPPORTED_LAYOUTS[-1] == "thermal-axisymmetric-transient-p1-node-cell-regions-v1"
    vtu = export_fields(tmp_path / "out" / "fields.npz", tmp_path / "out" / "last.vtu", time_index=-1)
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.points[:, :2], saved["nodes_m"])
    np.testing.assert_array_equal(mesh.point_data["storage_rate_w"], saved["storage_rate_w"][-1])
    assert "triangle_regions" in mesh.cell_data and not any(k.endswith("_per_m") for k in mesh.point_data)
    pvd = export_time_series(tmp_path / "out" / "fields.npz", tmp_path / "series")
    assert pvd.exists() and len(list(pvd.parent.glob("*.vtu"))) == 3


def test_g7_5_the_long_time_limit_equals_the_steady_axisymmetric_document():
    """A heated cylinder held at TB on its outer radius reaches the steady document's solution."""
    steady = run(Document.from_dict(cylinder(size_mm=0.2)), verbose=False)
    times = [0.0] + np.cumsum(2.0**np.arange(-4, 22)).tolist()
    transient = run(Document.from_dict(cylinder_transient(times=times)), verbose=False)
    np.testing.assert_array_equal(transient.mesh_nodes_m, steady.mesh_nodes_m)
    rise = float(np.max(abs(steady.temperature_k-TB)))
    assert rise > 0.1
    np.testing.assert_allclose(transient.temperature_k[-1], steady.temperature_k, rtol=0, atol=1e-6*rise)
    power = Q*math.pi*(3e-3)**2*1e-3
    assert abs(transient.reaction_w[-1].sum()/steady.reaction_w.sum()-1) < 1e-6
    assert abs(steady.reaction_w.sum()/power+1) < 1e-9
    assert abs(transient.storage_rate_w[-1].sum()) < 1e-8*power


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
