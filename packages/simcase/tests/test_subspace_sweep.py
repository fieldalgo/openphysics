# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Document-level behaviour of the opt-in electric-l2-subspace-v1 sweep.

These are contract and consistency checks on the product fiber example. They
do not establish physical accuracy of the cluster mean group index; that needs
the independent vector-fiber field and dispersion-derivative references.
"""

import copy
import json

import numpy as np
import pytest

from simcase import Document, ModeTrackingError, SubspaceSweepResult, examples, run
from simcase.cli import main
from simcase.subspace_tracking import ElectricMetric
from galerkin import Mesh


@pytest.fixture(scope="module")
def result():
    return run(Document.from_dict(examples.VECTOR_FIBER_SUBSPACE_SWEEP), False)


def _doc(**study):
    d = copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP)
    d["study"].update(study)
    return d


def _scaled(data, ratio, unit):
    d = copy.deepcopy(data)
    d["units"] = {"length": unit}
    d["geometry"]["domain"] = {k: v * ratio for k, v in d["geometry"]["domain"].items()}
    for shape in d["geometry"]["shapes"]:
        for key in ("cx", "cy", "r", "mesh_size"):
            shape[key] *= ratio
    d["mesh"]["size"] *= ratio
    grading = d["mesh"]["grading"]
    grading["center"] = [v * ratio for v in grading["center"]]
    for key in ("near", "far", "distance"):
        grading[key] *= ratio
    d["physics"]["em1"]["wavelength"] *= ratio
    d["study"]["values"] = [v * ratio for v in d["study"]["values"]]
    return d


def test_he11_pair_is_tracked_as_one_rank_two_cluster(result):
    assert isinstance(result, SubspaceSweepResult)
    assert result.cluster_ranks == [2] and result.cluster_ids == [1]
    assert result.group_index() is None and result.singleton_group_index() == {}
    assert result.neff.shape == (5, 2)
    mean = result.cluster_mean_index()[:, 0]
    np.testing.assert_allclose(mean, result.neff.mean(axis=1))
    assert np.all(np.diff(mean) < 0)                          # n_eff falls with wavelength here
    assert np.all((1.44 < result.neff) & (result.neff < 1.45))
    for point in result.mode_tracking["points"]:
        cluster = point["clusters"][0]
        assert cluster["rank"] == 2 and cluster["lower_guard_rank"] == 3
        assert cluster["span"] <= 1e-4 < 1e-3 < cluster["lower_gap"]
    for point in result.mode_tracking["points"][1:]:
        assert point["clusters"][0]["min_principal_squared"] >= 0.8


def test_raw_eigenfields_are_kept_and_frames_reconstruct(result):
    metric = ElectricMetric(Mesh(result.mesh_nodes, result.mesh_triangles, {}))
    for i, raw in enumerate(result.vector_fields):
        np.testing.assert_allclose(np.linalg.norm(raw.electric, axis=2).max(axis=0), 1.0)
        frame = result.frame_fields(i)
        np.testing.assert_allclose(metric.product(frame, frame), np.eye(2), atol=1e-10)
        if i:
            cross = metric.product(result.frame_fields(i - 1), frame)
            np.testing.assert_allclose(cross, cross.conj().T, atol=1e-10)      # aligned: Hermitian PSD
            assert np.linalg.eigvalsh(cross).min() > 0
        density = result.subspace_density(i, 1)
        assert density.max() == pytest.approx(1.0) and density.min() >= 0


def test_density_is_invariant_under_a_unitary_change_of_frame(result):
    o = result.cluster_offsets
    frame = result.frame_fields(2).electric[:, o[0]:o[1], :]
    unitary = np.array([[np.cos(0.4), -np.exp(0.3j) * np.sin(0.4)], [np.exp(-0.3j) * np.sin(0.4), np.cos(0.4)]])
    rotated = np.einsum("tmc,mk->tkc", frame, unitary)
    np.testing.assert_allclose((abs(rotated) ** 2).sum(axis=(1, 2)), (abs(frame) ** 2).sum(axis=(1, 2)),
                               rtol=1e-12, atol=1e-14)


def test_reversed_wavelengths_give_the_same_cluster_statistics(result):
    values = examples.VECTOR_FIBER_SUBSPACE_SWEEP["study"]["values"][::-1]
    reverse = run(Document.from_dict(_doc(values=values)), False)
    np.testing.assert_allclose(reverse.cluster_mean_index()[::-1], result.cluster_mean_index(), atol=1e-12)
    np.testing.assert_allclose(reverse.cluster_mean_group_index()[::-1], result.cluster_mean_group_index(),
                               atol=1e-10)


def test_nanometre_document_is_consistent(result):
    """Same physics in nm; the mesher's roundoff gives a slightly different mesh."""
    nm = run(Document.from_dict(_scaled(examples.VECTOR_FIBER_SUBSPACE_SWEEP, 1e3, "nm")), False)
    assert len(nm.mesh_triangles) == len(result.mesh_triangles)
    np.testing.assert_allclose(nm.cluster_mean_index(), result.cluster_mean_index(), atol=5e-6)
    np.testing.assert_allclose(nm.cluster_mean_group_index(), result.cluster_mean_group_index(), atol=5e-6)


@pytest.mark.parametrize("num_modes, message", [
    (1, r"cut the observed cluster at candidate ranks 1-2; include all 2 vectors or fewer \(0\)"),
    (3, "cut the observed cluster at candidate ranks 3-6"),
    (6, "no observed lower guard candidate"),
])
def test_incomplete_clusters_and_unresolved_guards_fail(num_modes, message):
    d = _doc()
    d["physics"]["em1"]["num_modes"] = num_modes
    with pytest.raises(ModeTrackingError, match=f"wavelength 1.5 um.*{message}"):
        run(Document.from_dict(d), False)


def test_default_method_still_rejects_the_same_fiber_pair():
    d = _doc()
    del d["study"]["tracking"]
    with pytest.raises(ModeTrackingError, match="near-degenerate"):
        run(Document.from_dict(d), False)


def test_save_writes_a_fresh_versioned_layout(result, tmp_path):
    output = result.save(tmp_path / "out")
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["field_representation"] == "vector-subspace-edge-nodal-v1"
    assert summary["clusters"] == [{"id": 1, "rank": 2, "columns": [0, 2]}]
    assert "neff" not in summary and "group_index" not in summary
    assert summary["mode_tracking"] == result.mode_tracking
    np.testing.assert_allclose(summary["cluster_mean_group_index"], result.cluster_mean_group_index())
    with np.load(output / "fields.npz", allow_pickle=False) as arrays:
        assert str(arrays["field_representation"]) == "vector-subspace-edge-nodal-v1"
        assert arrays["cluster_offsets"].tolist() == [0, 2]
        np.testing.assert_array_equal(arrays["raw_neff"], result.neff)
        assert arrays["frame_transform"].shape == (5, 2, 2)
        frame = arrays["raw_transverse"][3] @ arrays["frame_transform"][3]
        np.testing.assert_allclose(frame, result.frame_fields(3).transverse)
        assert json.loads(str(arrays["mode_tracking_json"])) == result.mode_tracking
    with pytest.raises(FileExistsError, match="choose a fresh output directory"):
        result.save(output)


def test_save_fields_false_omits_arrays(tmp_path):
    d = _doc()
    d["results"] = {"save_fields": False, "plots": False}
    output = run(Document.from_dict(d), False).save(tmp_path / "out")
    assert sorted(p.name for p in output.iterdir()) == ["log.txt", "model.json", "summary.json"]


def test_cli_writes_results_and_refuses_existing_or_failed_output(tmp_path, capsys):
    model = tmp_path / "fiber.json"
    Document.from_dict(examples.VECTOR_FIBER_SUBSPACE_SWEEP).save(model)
    output = tmp_path / "out"
    assert main(["run", str(model), "-q", "-o", str(output)]) == 0
    assert (output / "fields.npz").exists()
    assert main(["run", str(model), "-q", "-o", str(output)]) == 1
    assert "subspace sweep output already exists" in capsys.readouterr().err
    bad = _doc()
    bad["physics"]["em1"]["num_modes"] = 1
    Document.from_dict(bad).save(model)
    assert main(["run", str(model), "-q", "-o", str(tmp_path / "bad")]) == 1
    error = capsys.readouterr().err
    assert "include all 2 vectors" in error and "Traceback" not in error
    assert not (tmp_path / "bad").exists()


def test_studio_returns_a_versioned_cluster_payload(result):
    pytest.importorskip("fastapi")
    import time
    from fastapi.testclient import TestClient
    from simcase.studio.server import app

    client = TestClient(app)
    assert "vector_fiber_subspace_sweep" in client.get("/api/examples").json()["examples"]
    doc = client.get("/api/examples/vector_fiber_subspace_sweep").json()
    assert client.post("/api/validate", json={"doc": doc}).json()["ok"] is True
    job = client.post("/api/run", json={"doc": doc}).json()["job"]
    for _ in range(600):
        status = client.get(f"/api/jobs/{job}").json()["status"]
        if status in ("done", "error"):
            break
        time.sleep(0.1)
    assert status == "done"
    payload = client.get(f"/api/jobs/{job}/result").json()
    assert payload["neff"] is None and payload["group_index"] is None and "vector_fields" not in payload
    sub = payload["subspace"]
    assert sub["field_representation"] == payload["summary"]["field_representation"] == "vector-subspace-edge-nodal-v1"
    assert sub["clusters"] == [{"id": 1, "rank": 2, "columns": [0, 2]}]
    np.testing.assert_allclose(sub["cluster_mean_group_index"], result.cluster_mean_group_index())
    density = np.array(sub["density"])
    assert density.shape == (5, 1, len(result.mesh_triangles))
    np.testing.assert_allclose(density[2, 0], result.subspace_density(2, 1))
    assert np.allclose(density.max(axis=2), 1.0)
