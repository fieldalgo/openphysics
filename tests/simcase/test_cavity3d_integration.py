# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Real document/CLI integration: requires the approved cavity-enabled engine.

These tests deliberately do not skip if the matching engine API is absent.
The standalone product branch must be combined with its recorded core commit
before this integration gate can pass. Independent acceptance owns the broader
numerical convergence and spectral-completeness validation.
"""

import copy
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from galerkin import (EdgeSpace3D, Mesh3D, assemble_curlcurl_3d,
                      assemble_edge_mass_3d, eval_edge_field_3d)
from refsol.metallic import rect_cavity_resonances
from simcase import CavityRunResult, Document, examples, run


def translated_cube():
    data = copy.deepcopy(examples.CAVITY_BOX)
    data["geometry"]["domain"] = {
        "xmin": 2, "xmax": 3, "ymin": -3, "ymax": -2, "zmin": 4, "zmax": 5,
    }
    return data


@pytest.fixture(scope="module")
def solved_cube():
    return run(Document.from_dict(translated_cube()), verbose=False)


def test_real_cavity_document_selects_expected_reference_modes(solved_cube):
    result = solved_cube
    assert isinstance(result, CavityRunResult)
    assert result.resonant_frequency.shape == (5,)
    exact_k2 = np.array([k2 for k2, _ in rect_cavity_resonances(1, 1, 1, n_max=2)][:5])
    exact_hz = 299792458 / (2 * np.pi) * np.sqrt(exact_k2)
    # This coarse product example is a smoke/reference check, not the independent
    # acceptance convergence gate. Five modes span the first two full clusters.
    np.testing.assert_allclose(result.resonant_frequency, exact_hz, rtol=0.03)
    assert result.cluster_completeness == "not_certified"
    assert result.mode_count_policy == "exact_count_may_split_cluster"


def test_real_cavity_saved_fields_reconstruct_after_document_translation(solved_cube, tmp_path):
    result = solved_cube
    out = result.save(tmp_path / "translated")
    summary = json.loads((out / "summary.json").read_text())
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        metadata = json.loads(str(arrays["metadata_json"]))
        nodes = arrays["node_coordinates"]
        np.testing.assert_allclose(nodes.min(axis=0), [2, -3, 4], atol=1e-14)
        np.testing.assert_allclose(nodes.max(axis=0), [3, -2, 5], atol=1e-14)
        mesh = Mesh3D(nodes, arrays["tetrahedra"])
        space = EdgeSpace3D(mesh)
        np.testing.assert_array_equal(space.edges, arrays["edges"])
        np.testing.assert_array_equal(space.tet_edges, arrays["tet_edges"])
        np.testing.assert_array_equal(space.signs, arrays["edge_signs"])
        np.testing.assert_array_equal(space.boundary_edge_ids(), arrays["pec_edge_ids"])
        q = arrays["mass_normalized_electric_field_line_integral"]
        assert q.shape == (space.num_edges, 5)
        np.testing.assert_array_equal(q[arrays["pec_edge_ids"]], 0)
        mass = assemble_edge_mass_3d(space)
        np.testing.assert_allclose(q.T @ mass @ q, np.eye(5), atol=1e-7)
        stiffness = assemble_curlcurl_3d(space)
        free = np.setdiff1d(np.arange(space.num_edges), arrays["pec_edge_ids"])
        residuals = []
        for i, eigenvalue in enumerate(arrays["wavenumber_squared"]):
            reconstructed = eval_edge_field_3d(space, q[:, i])
            np.testing.assert_allclose(reconstructed, arrays["mass_normalized_electric_field"][i], atol=1e-10)
            lhs = (stiffness @ q[:, i])[free]
            rhs = eigenvalue * (mass @ q[:, i])[free]
            residuals.append(np.linalg.norm(lhs - rhs) / (np.linalg.norm(lhs) + np.linalg.norm(rhs)))
        assert max(residuals) < 1e-8
        np.testing.assert_allclose(residuals, arrays["relative_residual"], atol=1e-11)
        np.testing.assert_allclose(arrays["resonant_frequency"], summary["resonant_frequency"]["values"],
                                   rtol=0, atol=0)
        assert summary["resonant_frequency"]["unit"] == metadata["field_units"]["resonant_frequency"] == "Hz"
        assert str(arrays["field_layout"]) == summary["field_layout"] == "cavity3d-edge-v2"
        assert metadata["returned_mode_count"] == summary["returned_mode_count"] == 5
        assert str(arrays["cluster_completeness"]) == summary["cluster_completeness"] == "not_certified"
        assert str(arrays["mode_count_policy"]) == summary["mode_count_policy"] == "exact_count_may_split_cluster"


@pytest.mark.parametrize("unit,ratio", [("mm", 1000), ("um", 1e6), ("nm", 1e9)])
def test_real_cavity_document_unit_invariance(solved_cube, unit, ratio):
    data = translated_cube()
    data["geometry"]["length_unit"] = unit
    data["geometry"]["domain"] = {k: v * ratio for k, v in data["geometry"]["domain"].items()}
    result = run(Document.from_dict(data), verbose=False)
    # the box is the same picometre grid in every unit: the solve is bitwise the same
    np.testing.assert_array_equal(result.resonant_frequency, solved_cube.resonant_frequency)
    np.testing.assert_array_equal(result.cavity.mesh.nodes, solved_cube.cavity.mesh.nodes)
    np.testing.assert_array_equal(result.cavity.mesh.tets, solved_cube.cavity.mesh.tets)
    assert max(result.cavity.relative_residuals) < 1e-8


@pytest.mark.parametrize("save_fields", [True, False])
def test_real_cavity_cli_writes_declared_outputs(tmp_path, save_fields):
    data = translated_cube()
    data["results"]["save_fields"] = save_fields
    path = tmp_path / "cavity.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "results"
    completed = subprocess.run(
        [sys.executable, "-m", "simcase", "run", str(path), "-q", "-o", str(out)],
        text=True, capture_output=True, env=os.environ.copy(), check=False, cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "results.png" not in completed.stdout
    assert ("fields.npz" in completed.stdout) == save_fields
    assert (out / "fields.npz").exists() == save_fields
    assert not (out / "results.png").exists()
    summary = json.loads((out / "summary.json").read_text())
    assert len(summary["resonant_frequency"]["values"]) == summary["returned_mode_count"] == summary["mode_count"] == 5
    assert summary["field_layout"] == "cavity3d-edge-v2"
    assert summary["resonant_frequency"]["unit"] == "Hz" and summary["field_units"]["node_coordinates"] == "m"
    assert summary["cluster_completeness"] == "not_certified"
    assert summary["mode_count_policy"] == "exact_count_may_split_cluster"
    assert summary["normalization"] == "electric_mass_orthonormal_si"
    assert Document.load(out / "model.json").data == Document.from_dict(data).data
