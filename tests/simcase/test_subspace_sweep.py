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
    """The same document with its shape numbers in ``unit`` (tagged lengths keep their units,
    and the reader takes each to the kernel's micrometres from its exact value)."""
    from decimal import Decimal

    def exact(v):              # the same length written exactly in the other unit
        return float(Decimal(repr(v)) * Decimal(repr(ratio)))
    d = copy.deepcopy(data)
    d["geometry"]["length_unit"] = unit
    d["geometry"]["domain"] = {k: exact(v) for k, v in d["geometry"]["domain"].items()}
    for shape in d["geometry"]["shapes"]:
        for key in ("cx", "cy", "r"):
            shape[key] = exact(shape[key])
    return d


def _kernel_field(field):
    """A public vector field back in the kernel's frame (exp(+i omega t), micrometres)."""
    from simcase.fields import VectorField
    return VectorField(field.edges, np.conj(field.transverse) / 1e-6, np.conj(field.longitudinal),
                       np.conj(field.electric), field.normalization)


def test_he11_pair_is_tracked_as_one_rank_two_cluster(result):
    assert isinstance(result, SubspaceSweepResult)
    assert result.cluster_ranks == [2] and result.cluster_ids == [1]
    assert result.group_index() is None and result.singleton_group_index() == {}
    assert result.effective_index.shape == (5, 2)
    mean = result.mean_effective_index[:, 0]
    np.testing.assert_allclose(mean, result.effective_index.mean(axis=1))
    assert np.all(np.diff(mean) < 0)                          # n_eff falls with wavelength here
    assert np.all((1.44 < result.effective_index) & (result.effective_index < 1.45))
    for point in result.mode_tracking["points"]:
        cluster = point["clusters"][0]
        assert cluster["rank"] == 2 and cluster["lower_guard_rank"] == 3
        assert cluster["span"] <= 1e-4 < 1e-3 < cluster["lower_gap"]
    for point in result.mode_tracking["points"][1:]:
        assert point["clusters"][0]["minimum_principal_squared"] >= 0.8


def test_raw_eigenfields_are_kept_and_frames_reconstruct(result):
    metric = ElectricMetric(Mesh(result.node_coordinates, result.triangles, {}))
    for i, raw in enumerate(result.vector_fields):
        np.testing.assert_allclose(np.linalg.norm(raw.electric, axis=2).max(axis=0), 1.0)
        frame = result.frame_fields(i)
        # the frame is electric-L2 orthonormal on the micrometre mesh: on the saved metres the
        # Gram matrix is the identity times (1e-6)^2 for the line integrals' part
        gram = ElectricMetric(Mesh(result.node_coordinates / 1e-6, result.triangles, {})).product(
            _kernel_field(frame), _kernel_field(frame))
        np.testing.assert_allclose(gram, np.eye(2), atol=1e-10)
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
    values = {"unit": "um", "values": examples.VECTOR_FIBER_SUBSPACE_SWEEP["study"]["values"]["values"][::-1]}
    reverse = run(Document.from_dict(_doc(values=values)), False)
    np.testing.assert_allclose(reverse.mean_effective_index[::-1], result.mean_effective_index, atol=1e-12)
    np.testing.assert_allclose(reverse.mean_group_index[::-1], result.mean_group_index, atol=1e-10)


def _dispersive(data):
    """The example fiber with physmat built-in dispersive materials (SiO2 core, CaF2 cladding)."""
    d = copy.deepcopy(data)
    d["materials"] = {}
    d["geometry"]["background"]["material"] = "physmat:CaF2"
    d["geometry"]["shapes"][0]["material"] = "physmat:SiO2"
    d["physics"]["em1"]["effective_index_threshold"] = 1.427       # above CaF2 and below SiO2 over 1.5-1.6 um
    return d


@pytest.mark.parametrize("materials", ["constant", "dispersive"])
@pytest.mark.parametrize("ratio, unit", [(1e3, "nm"), (1e-6, "m")])
def test_scaled_document_gives_the_same_bits(result, ratio, unit, materials):
    """End to end in another length_unit (check P2-5). The shape numbers reach the micrometre
    kernel frame from their exact picometre counts and every tagged length from its exact
    value, so the mesher, physmat and the solver receive the same doubles and every saved
    value is bitwise equal. (Format 0.2 meshed each unit's own doubles: the answers then
    differed by mesh noise, 5e-6, and by about 2e-10 on one mesh.) The dispersive case also
    exercises physmat's wavelength, which the constant-index example cannot."""
    assert ratio != 1.0
    base = examples.VECTOR_FIBER_SUBSPACE_SWEEP
    if materials == "dispersive":
        base = _dispersive(base)
        um = run(Document.from_dict(base), False)
    else:
        um = result
    other = run(Document.from_dict(_scaled(base, ratio, unit)), False)
    assert other.cluster_ranks == um.cluster_ranks
    for name in ("node_coordinates", "triangles", "effective_index", "mean_effective_index", "mean_group_index",
                 "vacuum_wavelength"):
        assert getattr(other, name).tobytes() == getattr(um, name).tobytes(), name
    for a, b in zip(other.vector_fields, um.vector_fields):
        assert a.transverse.tobytes() == b.transverse.tobytes() and a.electric.tobytes() == b.electric.tobytes()


@pytest.mark.parametrize("mode_count, message", [
    (1, r"cut the observed cluster at candidate ranks 1-2; include all 2 vectors or fewer \(0\)"),
    (3, "cut the observed cluster at candidate ranks 3-6"),
    (6, "no observed lower guard candidate"),
])
def test_incomplete_clusters_and_unresolved_guards_fail(mode_count, message):
    d = _doc()
    d["physics"]["em1"]["mode_count"] = mode_count
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
    assert summary["field_representation"] == "vector-subspace-edge-nodal-v2"
    assert summary["field_layout"] == "em-modes2d-subspace-raw-v2"  # not the per-mode layout
    assert "mesh_length_unit" not in summary and "length_unit_to_m" not in summary
    assert summary["field_units"]["unnormalized_electric_field_line_integral"] == "m"
    assert summary["frame_normalization"].startswith("electric-L2 orthonormal on the micrometre solver mesh")
    assert summary["clusters"] == [{"id": 1, "rank": 2, "columns": [0, 2]}]
    assert "neff" not in summary and "group_index" not in summary
    assert summary["mode_tracking"] == result.mode_tracking
    assert summary["mean_group_index"]["values"] == result.mean_group_index.tolist()
    with np.load(output / "fields.npz", allow_pickle=False) as arrays:
        assert str(arrays["field_representation"]) == "vector-subspace-edge-nodal-v2"
        assert str(arrays["field_layout"]) == "em-modes2d-subspace-raw-v2"
        assert str(arrays["study_parameter"]) == "physics.em1.vacuum_wavelength"
        assert arrays["cluster_offsets"].tolist() == [0, 2]
        np.testing.assert_array_equal(arrays["effective_index"], result.effective_index)
        assert arrays["frame_transform"].shape == (5, 2, 2)
        frame = arrays["unnormalized_electric_field_line_integral"][3] @ arrays["frame_transform"][3]
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
    bad["physics"]["em1"]["mode_count"] = 1
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
    assert payload["effective_index"] is None and payload["group_index"] is None and "vector_fields" not in payload
    sub = payload["subspace"]
    assert sub["field_representation"] == payload["summary"]["field_representation"] == "vector-subspace-edge-nodal-v2"
    assert sub["clusters"] == [{"id": 1, "rank": 2, "columns": [0, 2]}]
    np.testing.assert_allclose(sub["mean_group_index"], result.mean_group_index)
    density = np.array(sub["density"])
    assert density.shape == (5, 1, len(result.triangles))
    np.testing.assert_allclose(density[2, 0], result.subspace_density(2, 1))
    assert np.allclose(density.max(axis=2), 1.0)


def test_raw_eigenpairs_satisfy_the_original_pencil_and_rotated_mixtures_do_not(result):
    """Raw columns stay eigenpairs; mixing unequal eigenvalues is not an eigenmode."""
    from simcase.physics_em_modes2d import vector_pencil_residuals
    from simcase.runner import build_mesh, solve_point
    from simcase.subspace_tracking import columns

    # vector_pencil_residuals is a kernel-frame internal (micrometres, exp(+i omega t)): the
    # public results go back to that frame first
    doc = Document.from_dict(examples.VECTOR_FIBER_SUBSPACE_SWEEP)
    model = build_mesh(doc)
    physics = doc.si["physics"]["em1"]
    for i, wl in enumerate(result.vacuum_wavelength):
        eps = np.conj(model.relative_permittivity(wl))
        raw = vector_pencil_residuals(model.solver_mesh, eps, wl / 1e-6, physics["boundary"],
                                      np.conj(result.effective_index[i]), _kernel_field(result.vector_fields[i]))
        assert raw.max() < 1e-10
    solved = solve_point(model, dict(physics, mode_count=6))
    wl = physics["vacuum_wavelength"]
    eps = np.conj(model.relative_permittivity(wl))
    neff, field = np.conj(solved["effective_index"]), _kernel_field(solved["vector_field"])
    base = vector_pencil_residuals(model.solver_mesh, eps, wl / 1e-6, physics["boundary"], neff, field)
    mix = np.eye(len(neff), dtype=complex)
    mix[1:3, 1:3] = [[np.cos(0.7), -np.sin(0.7)], [np.sin(0.7), np.cos(0.7)]]       # HE11 member with TE01
    mixed = vector_pencil_residuals(model.solver_mesh, eps, wl / 1e-6, physics["boundary"], neff,
                                    columns(field, mix))
    assert base.max() < 1e-10
    assert mixed[1:3].min() > 1e6 * base.max()


def test_failed_save_leaves_no_partial_output(result, tmp_path, monkeypatch):
    def broken_plot(path):
        raise RuntimeError("plot failed")
    monkeypatch.setattr(result, "plot", broken_plot)
    with pytest.raises(RuntimeError, match="plot failed"):
        result.save(tmp_path / "out")
    assert list(tmp_path.iterdir()) == []


def test_cli_fresh_output_rule_applies_only_to_subspace_sweeps(tmp_path, capsys):
    d = copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP)
    d["study"] = {"type": "single", "tracking": d["study"]["tracking"]}
    d["results"] = {"save_fields": False, "plots": False}
    model = tmp_path / "single.json"
    Document.from_dict(d).save(model)
    output = tmp_path / "out"
    output.mkdir()
    assert main(["run", str(model), "-q", "-o", str(output)]) == 0
