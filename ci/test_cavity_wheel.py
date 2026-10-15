# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Installed cavity consumer contract, copied outside the checkout by the wheel gate.

These checks require both the cavity engine and simcase candidates. They exercise
public entry points and serialized output, not the independent convergence gate.
Missing APIs are failures, never optional skips.
"""

import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import galerkin
from galerkin import CavityResult, EdgeSpace3D, Mesh3D, eval_edge_field_3d, solve_cavity_box
import simcase
from simcase import Document


def cli(*args, check=True):
    result = subprocess.run([sys.executable, "-I", "-m", "simcase", *map(str, args)],
                            text=True, capture_output=True)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="module")
def cavity_example():
    return json.loads(cli("example", "cavity_box").stdout)


@pytest.fixture(scope="module")
def saved_cavity(tmp_path_factory, cavity_example):
    work = tmp_path_factory.mktemp("cavity-cli")
    model = work / "cavity.json"
    model.write_text(json.dumps(cavity_example), encoding="utf-8")
    validated = cli("validate", model)
    assert "em.cavity3d" in validated.stdout
    output = work / "cavity_results"
    completed = cli("run", model, "-o", output)
    assert "fields.npz" in completed.stdout and "results.png" not in completed.stdout
    return output


def test_documented_public_api_is_installed():
    for module in (galerkin, simcase):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    # Reproduce the public galerkin documentation example without source imports.
    result = solve_cavity_box(lengths_m=(1.0, 1.0, 1.0), subdivisions=(8, 8, 8),
                              num_modes=6, target_frequency_hz=210e6)
    assert isinstance(result, CavityResult)
    assert result.frequencies_hz.shape == (6,)
    assert np.all(np.isfinite(result.frequencies_hz))
    assert np.all(result.frequencies_hz > 0) and np.all(np.diff(result.frequencies_hz) >= 0)
    np.testing.assert_allclose(result.frequencies_hz,
                               299792458 * np.sqrt(result.eigenvalues_m2) / (2 * np.pi))
    assert max(result.relative_residuals) <= 1e-8
    assert result.cluster_completeness == "not_certified"
    assert result.mode_count_policy == "exact_count_may_split_cluster"


def test_documented_cli_json_npz_contract(saved_cavity, cavity_example):
    output = saved_cavity
    assert {p.name for p in output.iterdir()} == {"model.json", "summary.json", "log.txt", "fields.npz"}
    assert Document.load(output / "model.json").data == Document.from_dict(cavity_example).data
    summary = json.loads((output / "summary.json").read_text())
    metadata = {
        "field_layout": "cavity3d-edge-v1", "mesh_length_unit": "m", "frequency_unit": "Hz",
        "eigenvalue_unit": "m^-2", "edge_coefficient_unit": "m^-1/2", "electric_field_unit": "m^-3/2",
        "normalization": "electric_mass_orthonormal_si", "search": "near_target",
        "cluster_completeness": "not_certified", "mode_count_policy": "exact_count_may_split_cluster",
        "edge_orientation": "low_node_index_to_high_node_index", "electric_field_location": "tetrahedron_centroid",
    }
    with np.load(output / "fields.npz", allow_pickle=False) as arrays:
        for name in arrays.files:
            assert not arrays[name].dtype.hasobject, name
        for name, value in metadata.items():
            assert summary[name] == arrays[name].item() == value
        assert "neff" not in summary and "neff" not in arrays and "triangles" not in arrays
        count = summary["requested_modes"]
        assert count == summary["returned_modes"] == arrays["returned_modes"].item() == 5
        for name in ("frequencies_hz", "eigenvalues_m2", "relative_residuals"):
            assert arrays[name].shape == (count,)
            np.testing.assert_array_equal(arrays[name], summary[name])
        assert arrays["target_frequency_hz"].item() == summary["target_frequency_hz"] == 250e6
        mesh = Mesh3D(arrays["nodes"], arrays["tetrahedra"])
        space = EdgeSpace3D(mesh)
        np.testing.assert_array_equal(space.edges, arrays["edges"])
        np.testing.assert_array_equal(space.tet_edges, arrays["tet_edges"])
        np.testing.assert_array_equal(space.signs, arrays["edge_signs"])
        np.testing.assert_array_equal(space.boundary_edge_ids(), arrays["pec_edge_ids"])
        coefficients = arrays["edge_coefficients"]
        assert coefficients.shape == (space.num_edges, count)
        assert arrays["electric_field"].shape == (count, len(mesh.tets), 3)
        np.testing.assert_array_equal(coefficients[arrays["pec_edge_ids"]], 0)
        for mode in range(count):
            np.testing.assert_allclose(eval_edge_field_3d(space, coefficients[:, mode]),
                                       arrays["electric_field"][mode], atol=1e-10)


def test_cli_can_omit_raw_fields(tmp_path, cavity_example):
    document = copy.deepcopy(cavity_example)
    document["results"]["save_fields"] = False
    model = tmp_path / "spectral-only.json"
    model.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "spectral-only"
    completed = cli("run", model, "-q", "-o", output)
    assert "fields.npz" not in completed.stdout
    assert {p.name for p in output.iterdir()} == {"model.json", "summary.json", "log.txt"}
    summary = json.loads((output / "summary.json").read_text())
    assert len(summary["frequencies_hz"]) == summary["returned_modes"] == 5
    assert summary["normalization"] == "electric_mass_orthonormal_si"
    assert summary["cluster_completeness"] == "not_certified"
    assert summary["mode_count_policy"] == "exact_count_may_split_cluster"


def test_cli_rejects_unsupported_plotting(tmp_path, cavity_example):
    document = copy.deepcopy(cavity_example)
    document["results"]["plots"] = True
    model = tmp_path / "unsupported.json"
    model.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "must-not-exist"
    completed = cli("run", model, "-o", output, check=False)
    assert completed.returncode == 2
    assert "plotting is not supported" in completed.stderr
    assert not output.exists()


def test_installed_studio_explicitly_rejects_3d(cavity_example):
    from fastapi.testclient import TestClient
    from simcase.studio import app

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "cavity_box" not in client.get("/api/examples").json()["examples"]
        response = client.get("/api/examples/cavity_box")
        assert response.status_code == 400
        assert "Studio supports 2D only" in response.json()["detail"]
        for endpoint in ("/api/mesh", "/api/run"):
            response = client.post(endpoint, json={"doc": cavity_example})
            assert response.status_code == 400
            assert "Studio supports 2D only" in response.json()["detail"]
            assert "job" not in response.json()
