# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transient heat documents with inward heat flux and convection sides (pre-registered gates).

S1 a document run equals the direct solve_transient_heat call with the same inputs, bit
for bit (temperature history and the two boundary heat rate histories). S2 Dirichlet-only
documents keep the plain identifiers, the thirteen plain arrays in their order, the plain
summary keys and the six solver keywords, and their histories equal the direct call without
boundary keywords. S3 the convective slab document on nx=40 x ny=2 cells
with dt=1 s to 80 s (Fo=0.44, Bi=0.5) matches refsol.transient_heat_robin.ConvectiveSlab
at the final time with a relative L2 error <= 2e-3 on the temperature-rise scale (the
measured value is printed). S4 invalid boundary keys are refused with the steady
contract's codes and paths and no output. S5 the boundary layout exports through meshio with the
two per-step arrays, from the second stored time on, and the earlier layouts and the plain
transient export are unchanged. The transient Studio route refuses the boundary layout
before validation or run, with no job. Thresholds are fixed and never loosened here.
Documents are format 0.3; the engine keywords keep their galerkin names.
"""
import copy
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from galerkin import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat
from refsol.transient_heat_robin import ConvectiveSlab
from simcase import Document, DocumentError, examples, run
from simcase.export import SUPPORTED_LAYOUTS, export_fields, export_time_series
from simcase.transient_thermal_contract import (
    V1_03 as V1, V2_03 as V2, transient_result_versions, transient_solver_inputs)

EXAMPLE = examples.TRANSIENT_THERMAL_BOUNDARY
L, K, C = 0.05, 50., 3.6e6
H, AMBIENT, INITIAL = 500., 300., 400.
V1_ARRAYS = ("node_coordinates", "triangles", "time", "temperature", "heat_flux",
             "generated_heat_rate_per_depth", "reaction_heat_rate_per_depth", "residual_heat_rate_per_depth",
             "heat_storage_rate_per_depth", "stored_heat_per_depth", "thermal_energy_functional_per_depth",
             "prescribed_node_ids", "prescribed_temperature")
STRUCTURAL = ("triangles", "prescribed_node_ids")          # no unit
BOUNDARY_ARRAYS = ("outward_prescribed_heat_rate_per_depth", "outward_convective_heat_rate_per_depth")
# the engine's names of the same arrays
ENGINE = {"temperature": "temperature_k", "heat_flux": "heat_flux_w_m2",
          "heat_storage_rate_per_depth": "storage_rate_w_per_m", "reaction_heat_rate_per_depth": "reaction_w_per_m",
          "outward_prescribed_heat_rate_per_depth": "prescribed_outward_load_w_per_m",
          "outward_convective_heat_rate_per_depth": "convective_outward_w_per_m"}
NPZ_STRINGS = ("result_format", "field_layout", "metadata_json")
V1_SUMMARY_KEYS = (
    "name", "physics_name", "physics_type", "result_format", "field_layout", "diagnostics", "defaults_applied",
    "resolved_inputs", "extent", "timing", "field_units", "field_locations", "field_shapes", "field_time_axes",
    "field_components", "mesh", "study", "thermal_conductivity", "volumetric_heat_capacity", "heat_source_density",
    "prescribed_nodes", "minimum_temperature", "maximum_temperature", "generated_heat_rate_per_depth",
    "heat_storage_rate_per_depth", "outward_heat_rate_per_depth", "heat_rate_imbalance_per_depth",
    "stored_heat_per_depth", "thermal_energy_functional_per_depth", "reaction_sign", "balance_equation",
    "heat_content_definition", "quadratic_functional_definition", "save_fields")
EARLIER_LAYOUTS = ("thermal2d-p1-node-cell-v2", "thermal2d-p1-node-cell-boundary-v3",
                   "thermal2d-transient-p1-node-cell-v2", "cavity3d-edge-v1",
                   "thermal2d-p1-node-cell-regions-v2", "thermal2d-transient-p1-node-cell-regions-v2",
                   "electric-joule2d-p1-v1", "cavity3d-edge-complex-v1")
METRES = {"m": Decimal(1), "mm": Decimal("0.001")}


def slab(nx=20, ny=2, times=(0., 10., 20., 40., 80.)):
    data = copy.deepcopy(EXAMPLE)
    data["mesh"]["subdivision_count"] = [nx, ny]
    data["study"]["time"] = {"unit": "s", "values": [float(t) for t in times]}
    return data


def mixed():
    """Left Dirichlet, top prescribed inflow, right convection, uniform source, mm geometry."""
    data = copy.deepcopy(EXAMPLE)
    data["name"] = "Mixed transient boundary"
    data["geometry"]["length_unit"] = "mm"
    data["geometry"]["domain"] = {"xmin": 10., "xmax": 40., "ymin": -20., "ymax": 0.}
    data["physics"]["heat1"].update(
        thermal_conductivity="2.5 W/(m K)", volumetric_heat_capacity="4 J/(m^3 K)", initial_temperature="320 K",
        prescribed_temperature={"left": "320 K"}, heat_source_density="30 W/m^3",
        inward_heat_flux={"top": "20 W/m^2"},
        convection={"right": {"heat_transfer_coefficient": "5 W/(m^2 K)", "ambient_temperature": "300 K"}})
    data["mesh"]["subdivision_count"] = [6, 4]
    data["study"]["time"] = {"unit": "s", "values": [0., .5, 1.5, 3.]}
    return data


def natural_of(doc):
    """The engine keywords of the document's boundary keys: outward flux = 0.0 - inward (hazard H1)."""
    p = doc.si["physics"]["heat1"]
    natural = {}
    if "inward_heat_flux" in p:
        natural["outward_flux"] = {tag: 0.0 - v for tag, v in p["inward_heat_flux"].items()}
    if "convection" in p:
        natural["convection"] = {tag: (v["heat_transfer_coefficient"], v["ambient_temperature"])
                                 for tag, v in p["convection"].items()}
    return natural


def direct(data, **natural):
    """solve_transient_heat on the runner's SI mesh with the document's values."""
    doc = Document.from_dict(data)
    p = doc.si["physics"]["heat1"]
    mesh = _runner_mesh(doc)
    dirichlet = {int(i): float(v) for tag, v in p["prescribed_temperature"].items()
                 for i in mesh.boundary[tag]}
    return mesh, solve_transient_heat(
        mesh, conductivity=p["thermal_conductivity"], volumetric_heat_capacity=p["volumetric_heat_capacity"],
        time_s=np.array(doc.si["study"]["time"], dtype=float),
        initial_temperature_k=np.full(mesh.num_nodes, float(p["initial_temperature"])),
        dirichlet=dirichlet, heat_source=p.get("heat_source_density", 0.0), **natural)


def _runner_mesh(doc):
    """The SI rectangle from the authored numbers: corners correctly rounded from their exact
    decimal value in metres, lengths upper - origin."""
    g = doc.data["geometry"]
    metres = lambda value: float(Decimal(repr(float(value)))*METRES[g["length_unit"]])
    origin = np.array([metres(g["domain"][a+"min"]) for a in "xy"])
    upper = np.array([metres(g["domain"][a+"max"]) for a in "xy"])
    mesh = rectangle_mesh(*(upper-origin), *doc.si["mesh"]["subdivision_count"])
    mesh.nodes += origin
    return mesh


def values(entry):
    return np.asarray(entry["values"], dtype=float)


def l2_error(nodes, triangles, nodal, exact, scale):
    """Relative L2 error of the P1 field against exact(x): edge-midpoint rule, exact for quadratics."""
    q = nodes[triangles]
    area = 0.5*abs((q[:, 1, 0]-q[:, 0, 0])*(q[:, 2, 1]-q[:, 0, 1])-(q[:, 2, 0]-q[:, 0, 0])*(q[:, 1, 1]-q[:, 0, 1]))
    total = 0.
    for a, b in ((0, 1), (1, 2), (2, 0)):
        mid = (q[:, a]+q[:, b])/2
        value = (nodal[triangles[:, a]]+nodal[triangles[:, b]])/2
        total += np.sum(area/3*(value-exact(mid[:, 0]))**2)
    return np.sqrt(total/np.sum(area))/scale


# ---------------------------------------------------------------- S1

@pytest.mark.parametrize("case", ["slab", "mixed"])
def test_s1_document_run_equals_the_direct_engine_call_bit_for_bit(case):
    data = slab() if case == "slab" else mixed()
    doc = Document.from_dict(data)
    mesh, engine = direct(data, **natural_of(doc))
    result = run(Document.from_dict(data), verbose=False)
    assert (result.result_format, result.field_layout) == V2
    assert transient_result_versions(Document.from_dict(data)) == V2
    assert result.node_coordinates.tobytes() == mesh.nodes.tobytes()
    for name in ("temperature", "heat_flux", "heat_storage_rate_per_depth", "reaction_heat_rate_per_depth") \
            + BOUNDARY_ARRAYS:
        ours, theirs = getattr(result, name), getattr(engine, ENGINE[name])
        assert ours.shape == theirs.shape and ours.dtype == theirs.dtype, name
        assert ours.tobytes() == theirs.tobytes(), name
    nt, n = len(data["study"]["time"]["values"]), mesh.num_nodes
    assert (result.outward_prescribed_heat_rate_per_depth.shape
            == result.outward_convective_heat_rate_per_depth.shape == (nt-1, n))
    summary = result.summary()
    assert (summary["result_format"], summary["field_layout"]) == V2
    p = doc.si["physics"]["heat1"]
    assert summary["inward_heat_flux"] == {tag: {"value": v, "unit": "W/m^2"}
                                           for tag, v in p.get("inward_heat_flux", {}).items()}
    assert summary["convection"] == {
        tag: {"heat_transfer_coefficient": {"value": v["heat_transfer_coefficient"], "unit": "W/(m^2 K)"},
              "ambient_temperature": {"value": v["ambient_temperature"], "unit": "K"}}
        for tag, v in p.get("convection", {}).items()}
    for name in BOUNDARY_ARRAYS:
        assert summary["field_units"][name] == "W/m"
        assert summary["field_locations"][name] == "nodes"
        assert summary["field_time_axes"][name] == "time[1:]"
        assert summary["field_shapes"][name] == [nt-1, n]
    # Per-step balance of the returned terms: storage = source + reaction - G - C.
    np.testing.assert_allclose(values(summary["heat_rate_imbalance_per_depth"]), 0, rtol=0,
                               atol=1e-10*max(1., np.abs(values(summary["generated_heat_rate_per_depth"])).max(),
                                              np.abs(values(summary["outward_heat_rate_per_depth"])).max()))
    np.testing.assert_allclose(
        values(summary["outward_heat_rate_per_depth"]),
        values(summary["outward_prescribed_heat_rate_per_depth"])
        + values(summary["outward_convective_heat_rate_per_depth"])
        + values(summary["outward_reaction_heat_rate_per_depth"]), rtol=0, atol=1e-9)
    assert "boundary layout "+V2[1] in "\n".join(result.log)
    assert "q.n = -inward_heat_flux + h (T - ambient_temperature)" in Document.from_dict(data).summary()


def test_s1_saved_boundary_layout_adds_exactly_two_arrays_with_metadata(tmp_path):
    data = slab()
    result = run(Document.from_dict(data), verbose=False)
    out = result.save(tmp_path/"slab")
    with np.load(out/"fields.npz", allow_pickle=False) as saved:
        assert tuple(saved.files) == V1_ARRAYS + BOUNDARY_ARRAYS + NPZ_STRINGS
        assert (str(saved["result_format"]), str(saved["field_layout"])) == V2
        for name in BOUNDARY_ARRAYS:
            assert saved[name].tobytes() == getattr(result, name).tobytes()
        metadata = json.loads(str(saved["metadata_json"]))
    summary = json.loads((out/"summary.json").read_text(encoding="utf-8"))
    assert metadata == summary
    assert (summary["result_format"], summary["field_layout"]) == V2
    assert set(V1_SUMMARY_KEYS) < set(summary)
    assert {"inward_heat_flux", "convection", "outward_prescribed_heat_rate_per_depth",
            "outward_convective_heat_rate_per_depth", "outward_reaction_heat_rate_per_depth", "outward_sign",
            "natural_condition"} <= set(summary)
    assert json.loads((out/"model.json").read_text(encoding="utf-8")) == data


# ---------------------------------------------------------------- S2

def dirichlet_only_documents():
    sampled = copy.deepcopy(examples.TRANSIENT_THERMAL_UNIFORM)
    sampled["physics"]["heat1"]["prescribed_temperature"] = {
        "left": {"unit": "K", "values": [300., 300.2, 300.6]}, "right": "300 K"}
    sampled["mesh"]["subdivision_count"] = [3, 2]
    return {"uniform": examples.TRANSIENT_THERMAL_UNIFORM, "sampled": sampled}


@pytest.mark.parametrize("case", sorted(dirichlet_only_documents()))
def test_s2_dirichlet_only_documents_keep_plain_identifiers_arrays_keys_and_values(case, tmp_path):
    from simcase.steady_boundary_contract import REACTION_SIGN_03
    from simcase.transient_thermal import BALANCE_EQUATION_03
    data = dirichlet_only_documents()[case]
    doc = Document.from_dict(data)
    assert transient_result_versions(doc) == V1 == ("thermal.transient2d-result-v3",
                                                    "thermal2d-transient-p1-node-cell-v2")
    mesh, _ = direct(data) if case == "uniform" else (None, None)
    inputs = transient_solver_inputs(doc, mesh if mesh is not None else _runner_mesh(doc))
    assert set(inputs) == {"conductivity", "volumetric_heat_capacity", "time_s",
                           "initial_temperature_k", "dirichlet", "heat_source"}
    result = run(doc, verbose=False)
    assert (result.result_format, result.field_layout) == V1 and not result.boundary_enabled
    with pytest.raises(AttributeError):
        result.outward_prescribed_heat_rate_per_depth
    with pytest.raises(AttributeError):
        result.outward_convective_heat_rate_per_depth
    if case == "uniform":
        _, engine = direct(data)
        assert result.temperature.tobytes() == engine.temperature_k.tobytes()
        assert result.heat_storage_rate_per_depth.tobytes() == engine.storage_rate_w_per_m.tobytes()
        assert engine.prescribed_outward_load_w_per_m is None
    out = result.save(tmp_path/case)
    with np.load(out/"fields.npz", allow_pickle=False) as saved:
        assert tuple(saved.files) == V1_ARRAYS + NPZ_STRINGS
        assert (str(saved["result_format"]), str(saved["field_layout"])) == V1
    summary = json.loads((out/"summary.json").read_text(encoding="utf-8"))
    assert tuple(summary) == V1_SUMMARY_KEYS
    assert summary["reaction_sign"] == REACTION_SIGN_03
    assert summary["balance_equation"] == BALANCE_EQUATION_03
    assert tuple(summary["field_shapes"]) == V1_ARRAYS
    assert tuple(summary["field_units"]) == tuple(a for a in V1_ARRAYS if a not in STRUCTURAL)
    assert "boundary layout" not in (out/"log.txt").read_text(encoding="utf-8")
    assert "q.n" not in (out/"log.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------- S3

def test_s3_convective_slab_document_matches_the_independent_series():
    times = np.linspace(0., 80., 81)              # dt = 1 s, Fo = alpha*t/L^2 = 0.44, Bi = 0.5
    result = run(Document.from_dict(slab(40, 2, times)), verbose=False)
    series = ConvectiveSlab(L, K, C, H, AMBIENT, INITIAL)
    assert series.biot == pytest.approx(0.5)
    exact = lambda x: series.temperature(x, float(times[-1])).temperature_k
    error = l2_error(result.node_coordinates, result.triangles, result.temperature[-1], exact, INITIAL-AMBIENT)
    example = run(Document.from_dict(EXAMPLE), verbose=False)
    example_error = l2_error(example.node_coordinates, example.triangles, example.temperature[-1], exact,
                             INITIAL-AMBIENT)
    print(f"\nconvective slab document nx=40 ny=2 dt=1 s t=80 s: relative L2 error {error:.3e} "
          f"(temperature-rise scale {INITIAL-AMBIENT:g} K); shipped example [20,2], 4 steps: {example_error:.3e}")
    assert error <= 2e-3
    # Consistency, not a gate: the convective outward history is h*(T_surface-T_ambient)
    # integrated over the 0.01 m side; the first backward-Euler step is the least accurate.
    outward = result.summary()["outward_convective_heat_rate_per_depth"]["values"]
    expected = [H*(series.temperature(L, float(t)).temperature_k-AMBIENT)*0.01 for t in times[1:]]
    np.testing.assert_allclose(outward, expected, rtol=1e-2, atol=0)
    assert all(a > b > 0 for a, b in zip(outward, outward[1:]))


# ---------------------------------------------------------------- S4

CONVECTION = "physics.heat1.convection"
FLUX = "physics.heat1.inward_heat_flux"
# fault -> (path, value, code, refused path); the codes are the steady contract's
INVALID = {
    "negative_h": (CONVECTION+".right.heat_transfer_coefficient", "-1 W/(m^2 K)", "E-DOMAIN",
                   CONVECTION+".right.heat_transfer_coefficient"),
    "unknown_side": (CONVECTION, {"front": {"heat_transfer_coefficient": "1 W/(m^2 K)", "ambient_temperature": "300 K"}},
                     "E-CONTRACT", CONVECTION),
    "unknown_flux_side": (FLUX, {"center": "2 W/m^2"}, "E-CONTRACT", FLUX),
    "sampled_flux": (FLUX, {"right": {"unit": "W/m^2", "values": [1., 2., 3., 4., 5.]}}, "E-VALUE-FORM",
                     FLUX+".right"),
    "sampled_ambient": (CONVECTION+".right.ambient_temperature", {"unit": "K", "values": [300.]*5},
                        "E-VALUE-FORM", CONVECTION+".right.ambient_temperature"),
    "negative_ambient": (CONVECTION+".right.ambient_temperature", "-5 K", "E-DOMAIN",
                         CONVECTION+".right.ambient_temperature"),
    "missing_ambient": (CONVECTION+".right", {"heat_transfer_coefficient": "1 W/(m^2 K)"}, "E-KEY-MISSING",
                        CONVECTION+".right.ambient_temperature"),
    "extra_member": (CONVECTION+".right", {"heat_transfer_coefficient": "1 W/(m^2 K)", "ambient_temperature": "300 K",
                                           "time": "1 s"}, "E-KEY-UNKNOWN", CONVECTION+".right.time"),
    "boolean_h": (CONVECTION+".right.heat_transfer_coefficient", True, "E-VALUE-FORM",
                  CONVECTION+".right.heat_transfer_coefficient"),
    "null_mapping": (FLUX, None, "E-VALUE-FORM", FLUX),
    "infinite_flux": (FLUX, {"left": float("inf")}, "E-JSON", FLUX+".left"),
    "outward_key": ("physics.heat1.outward_flux_w_m2", {"left": 2.}, "E-KEY-UNKNOWN",
                    "physics.heat1.outward_flux_w_m2"),
}


def set_path(data, dotted, value):
    node = data
    for key in dotted.split(".")[:-1]:
        node = node[key]
    node[dotted.split(".")[-1]] = value


def refusals(caught):
    return [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"]


@pytest.mark.parametrize("fault", sorted(INVALID))
def test_s4_invalid_boundary_keys_are_refused_with_the_steady_codes(fault):
    path, value, code, where = INVALID[fault]
    data = slab()
    set_path(data, path, value)
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert refusals(caught) == [(code, where)]
    with pytest.raises(DocumentError) as caught:
        run(Document(copy.deepcopy(data)), verbose=False)
    assert refusals(caught) == [(code, where)]


def test_s4_dirichlet_and_natural_condition_on_one_side_is_refused():
    message = "physics.heat1: natural condition overlaps a fully prescribed-temperature side"
    data = slab()
    data["physics"]["heat1"]["prescribed_temperature"] = {"right": "400 K"}
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(data)
    data = slab()
    data["physics"]["heat1"]["prescribed_temperature"] = {"right": "400 K"}
    data["physics"]["heat1"].pop("convection")
    data["physics"]["heat1"]["inward_heat_flux"] = {"right": "-2 W/m^2"}
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(data)
    # An adjacent Dirichlet side is allowed: the shared corner node keeps its value and
    # the natural edge keeps its consistent load, as in the steady contract.
    data = slab()
    data["physics"]["heat1"]["prescribed_temperature"] = {"top": "400 K"}
    result = run(Document.from_dict(data), verbose=False)
    assert result.boundary_enabled and result.prescribed_node_ids.size == 21


def test_s4_zero_h_everywhere_is_still_the_boundary_layout_without_an_anchor():
    data = slab()
    data["physics"]["heat1"]["convection"]["right"]["heat_transfer_coefficient"] = "0 W/(m^2 K)"
    result = run(Document.from_dict(data), verbose=False)
    assert (result.result_format, result.field_layout) == V2
    assert not result.outward_convective_heat_rate_per_depth.any()
    np.testing.assert_array_equal(result.temperature, INITIAL)
    data["physics"]["heat1"]["convection"] = {}
    data["physics"]["heat1"]["inward_heat_flux"] = {}
    assert transient_result_versions(Document.from_dict(data)) == V2


def test_s4_cli_refuses_an_invalid_boundary_document_and_writes_nothing(tmp_path):
    data = slab()
    data["physics"]["heat1"]["convection"]["right"]["heat_transfer_coefficient"] = "-1 W/(m^2 K)"
    model = tmp_path/"bad.json"
    model.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path/"never"
    for command in (["validate", str(model)], ["run", str(model), "-q", "-o", str(out)]):
        child = subprocess.run([sys.executable, "-X", "utf8", "-m", "simcase", *command],
                               cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
        assert child.returncode == 2, (child.stdout, child.stderr)
        assert "heat_transfer_coefficient" in child.stderr+child.stdout
    assert not out.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.json"]


def test_s4_mesh_without_edge_tags_or_incomplete_side_is_refused():
    doc = Document.from_dict(slab(4, 2))
    mesh = _runner_mesh(doc)
    complete = transient_solver_inputs(doc, mesh)
    assert set(complete) == {"conductivity", "volumetric_heat_capacity", "time_s", "initial_temperature_k",
                             "dirichlet", "heat_source", "outward_flux", "convection"}
    assert complete["outward_flux"] == {} and complete["convection"] == {"right": (H, AMBIENT)}
    partial = _runner_mesh(doc)
    partial.boundary_edges = {tag: np.asarray(e) for tag, e in mesh.boundary_edges.items()}
    partial.boundary_edges["right"] = partial.boundary_edges["right"][:-1]
    with pytest.raises(DocumentError, match="mesh.boundary_edges.right: selection must cover the complete SI side"):
        transient_solver_inputs(doc, partial)
    bare = _runner_mesh(doc)
    del bare.boundary_edges
    with pytest.raises(DocumentError, match="boundary node and edge mappings required"):
        transient_solver_inputs(doc, bare)


# ---------------------------------------------------------------- S5

def test_s5_boundary_layout_exports_its_two_arrays_per_step_and_earlier_layouts_are_unchanged(tmp_path):
    meshio = pytest.importorskip("meshio", reason="install the export extra: pip install 'simcase[export]'")
    assert SUPPORTED_LAYOUTS[:8] == EARLIER_LAYOUTS and SUPPORTED_LAYOUTS[8] == V2[1]
    fields = run(Document.from_dict(slab()), verbose=False).save(tmp_path/"slab")/"fields.npz"
    with np.load(fields, allow_pickle=False) as saved:
        assert str(saved["field_layout"]) == V2[1]
        times = saved["time"]
        last = meshio.read(export_fields(fields, tmp_path/"last.vtu"))
        for name in BOUNDARY_ARRAYS:
            np.testing.assert_array_equal(last.point_data[name], saved[name][-1])
        first = meshio.read(export_fields(fields, tmp_path/"first.vtu", time_index=0))
        assert not set(BOUNDARY_ARRAYS) & set(first.point_data)
        np.testing.assert_array_equal(first.point_data["temperature"], saved["temperature"][0])
        pvd = export_time_series(fields, tmp_path/"series")
        names = sorted(p.name for p in pvd.parent.iterdir() if p.suffix == ".vtu")
        assert len(names) == len(times)
        for k, name in enumerate(names):
            mesh = meshio.read(pvd.parent/name)
            np.testing.assert_array_equal(mesh.point_data["temperature"], saved["temperature"][k])
            for array in BOUNDARY_ARRAYS:
                if k == 0:
                    assert array not in mesh.point_data
                else:
                    np.testing.assert_array_equal(mesh.point_data[array], saved[array][k-1])
    # The plain transient export still carries no boundary arrays.
    v1 = run(Document.from_dict(examples.TRANSIENT_THERMAL_UNIFORM), verbose=False).save(tmp_path/"v1")/"fields.npz"
    mesh = meshio.read(export_fields(v1, tmp_path/"v1.vtu"))
    assert not set(BOUNDARY_ARRAYS) & set(mesh.point_data)
    assert "temperature" in mesh.point_data


# ---------------------------------------------------------------- Studio

@pytest.mark.parametrize("route,status", [("validate", 400), ("run", 400)])
def test_transient_studio_refuses_the_boundary_layout_before_validation_with_no_job(route, status, monkeypatch):
    pytest.importorskip("fastapi", reason="install the Studio extra: pip install 'simcase[studio]'")
    from fastapi.testclient import TestClient
    from simcase.studio import server, thermal_api, transient_thermal_api
    monkeypatch.setattr(server, "_thermal_jobs", thermal_api.ThermalJobs())
    monkeypatch.setattr(server, "_start_thermal_thread", lambda target, args: target(*args))
    for data in (slab(2, 2, (0., 1.)), mixed()):
        body = {"doc": data, "client_revision": 7, "request_seq": 11}
        with TestClient(server.app) as client:
            response = client.post("/api/thermal/transient/"+route, json=body)
            assert response.status_code == status, response.text
            payload = response.json()
            assert payload["ok"] is False
            assert payload["error"]["code"] == "unsupported_physics"
            assert "inward_heat_flux or convection" in payload["error"]["message"]
            assert not server._thermal_jobs._records
            capabilities = client.get("/api/capabilities").json()
    transient = capabilities["thermal.transient2d"]
    assert transient["result_formats"] == [V1[0]] and transient["field_layouts"] == [V1[1]]
    # The preflight itself refuses by key presence, even with an empty mapping.
    empty = slab(2, 2, (0., 1.))
    empty["physics"]["heat1"]["convection"] = {}
    with pytest.raises(thermal_api.ThermalAPIError, match="inward_heat_flux or convection"):
        transient_thermal_api.preflight(empty, thermal_api.ThermalLimits())
