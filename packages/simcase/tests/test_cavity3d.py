# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cavity document validation and product output boundaries."""

import copy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from simcase import CavityRunResult, Document, DocumentError, build_mesh, examples, solve_point
from simcase.cli import main


def cavity_document():
    return copy.deepcopy(examples.CAVITY_BOX)


def test_cavity_defaults_do_not_import_2d_settings_or_an_extra_physics():
    data = cavity_document()
    data["physics"] = {"resonator": data["physics"]["em1"]}
    del data["results"]
    doc = Document.from_dict(data)
    assert list(doc["physics"]) == ["resonator"]
    assert "wavelength" not in doc.sole_physics()[1]
    assert "formulation" not in doc.sole_physics()[1]
    assert doc["mesh"] == {"subdivisions": [6, 6, 6]}
    assert doc["results"] == {"save_fields": True, "plots": False}
    assert "Hz" in doc.summary() and "output coordinates m" in doc.summary()


@pytest.mark.parametrize("path,value", [
    ("physics.em1.target_frequency_hz", 0), ("physics.em1.target_frequency_hz", float("nan")),
    ("physics.em1.target_frequency_hz", True), ("physics.em1.target_frequency_hz", float("inf")),
    ("physics.em1.num_modes", 0), ("physics.em1.num_modes", 1.2), ("physics.em1.num_modes", True),
    ("physics.em1.search", "lowest"), ("physics.em1.boundary", "pmc"),
    ("physics.em1.wavelength", 1), ("physics.em1.formulation", "scalar"),
    ("geometry.domain.zmax", 0), ("geometry.domain.zmax", float("inf")),
    ("geometry.domain.zmax", True), ("geometry.domain.xmin", "zero"),
    ("geometry.background.material", "Si"), ("geometry.shapes", [{}]),
    ("materials", {"vacuum": {"n": 2}}),
    ("mesh.subdivisions", [0, 3, 3]), ("mesh.subdivisions", [2.5, 3, 3]),
    ("mesh.subdivisions", [True, 3, 3]), ("mesh.subdivisions", [3, 3]),
    ("mesh.size", 0.2), ("mesh.grading", None),
    ("study", {"type": "sweep", "parameter": "physics.em1.target_frequency_hz", "values": [1e8, 2e8]}),
    ("results.plots", True), ("results.save_fields", "yes"),
    ("units", {}), ("physics.other", {"type": "em.cavity3d"}),
])
def test_cavity_rejects_unsupported_or_invalid_inputs(path, value):
    data = cavity_document()
    node = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
    with pytest.raises(DocumentError):
        Document.from_dict(data)


@pytest.mark.parametrize("path", ["units", "mesh.subdivisions", "physics.em1.target_frequency_hz",
                                  "physics.em1.search", "physics.em1.boundary", "physics.em1.num_modes",
                                  "geometry.domain.zmin"])
def test_cavity_requires_explicit_physical_and_search_inputs(path):
    data = cavity_document()
    node = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]
    with pytest.raises(DocumentError):
        Document.from_dict(data)


def test_cavity_does_not_enter_the_2d_stages():
    doc = Document.from_dict(cavity_document())
    with pytest.raises(DocumentError, match="2D stage"):
        build_mesh(doc)
    with pytest.raises(DocumentError, match="2D stage"):
        solve_point(None, doc.sole_physics()[1])


def _result(save_fields=True):
    # A serialization fixture, not a physical solve; real numerical validation
    # belongs in the engine and independent acceptance tests.
    data = cavity_document()
    data["results"]["save_fields"] = save_fields
    cavity = SimpleNamespace(
        mesh=SimpleNamespace(nodes=np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]),
                             tets=np.array([[0, 1, 2, 3]])),
        space=SimpleNamespace(edges=np.array([[0, 1], [0, 2]]),
                              tet_edges=np.array([[0, 1, 0, 1, 0, 1]]),
                              signs=np.ones((1, 6))),
        pec_edge_ids=np.array([1]), frequencies_hz=np.array([2e8]), eigenvalues_m2=np.array([17.57]),
        relative_residuals=np.array([1e-12]), edge_coefficients=np.array([[1.], [0.]]),
        electric_field=np.array([[[1., 0., 0.]]]), search="near_target", target_frequency_hz=2.5e8,
        requested_modes=1,
    )
    return CavityRunResult(Document.from_dict(data), cavity, {"mesh_and_solve": 0.1}, ["fixture"])


@pytest.mark.parametrize("save_fields", [True, False])
def test_cavity_serialization_has_explicit_si_units_and_no_2d_arrays(tmp_path, save_fields):
    result = _result(save_fields)
    out = result.save(tmp_path / "output")
    summary = json.loads((out / "summary.json").read_text())
    assert summary["frequency_unit"] == "Hz" and summary["mesh_length_unit"] == "m"
    assert summary["edge_coefficient_unit"] == "m^-1/2"
    assert summary["electric_field_unit"] == "m^-3/2"
    assert summary["frequencies_hz"] == result.frequencies_hz.tolist()
    assert summary["relative_residuals"] == [1e-12]
    assert "neff" not in summary and "triangles" not in summary["mesh"]
    assert Document.load(out / "model.json").data == result.doc.data
    assert not (out / "results.png").exists()
    assert (out / "fields.npz").exists() == save_fields
    if save_fields:
        with np.load(out / "fields.npz", allow_pickle=False) as arrays:
            assert "triangles" not in arrays and "neff" not in arrays
            assert arrays["tetrahedra"].shape == (1, 4)
            assert arrays["tet_edges"].shape == arrays["edge_signs"].shape == (1, 6)
            assert str(arrays["edge_orientation"]) == "low_node_index_to_high_node_index"
            assert str(arrays["electric_field_location"]) == "tetrahedron_centroid"
            assert "not_assessed" in str(arrays["cluster_completeness"])
            assert arrays["electric_field"].shape == (1, 1, 3)
            assert arrays["edge_coefficients"].shape == (2, 1)
            np.testing.assert_array_equal(arrays["pec_edge_ids"], [1])
            np.testing.assert_array_equal(arrays["edge_coefficients"], result.cavity.edge_coefficients)
            assert str(arrays["mesh_length_unit"]) == "m"


def test_cavity_cli_validation_and_solver_failure(tmp_path, monkeypatch, capsys):
    path = tmp_path / "box.json"
    Document.from_dict(cavity_document()).save(path)
    assert main(["validate", str(path)]) == 0
    assert "Hz" in capsys.readouterr().out
    def fail(*args, **kwargs):
        raise RuntimeError("insufficient positive cavity modes")
    monkeypatch.setattr("simcase.cli.run", fail)
    assert main(["run", str(path), "-o", str(tmp_path / "failed")]) == 1
    assert "insufficient positive cavity modes" in capsys.readouterr().err
    assert not (tmp_path / "failed").exists()


def test_cavity_cli_output_lists_only_files_written(tmp_path, monkeypatch, capsys):
    result = _result(False)
    path = tmp_path / "box.json"
    result.doc.save(path)
    monkeypatch.setattr("simcase.cli.run", lambda *args, **kwargs: result)
    assert main(["run", str(path), "-o", str(tmp_path / "success")]) == 0
    text = capsys.readouterr().out
    assert "summary.json" in text and "fields.npz" not in text and "results.png" not in text


def test_studio_rejects_cavity_before_starting_a_2d_job():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    with TestClient(app) as client:
        assert "cavity_box" not in client.get("/api/examples").json()["examples"]
        for endpoint in ("/api/run", "/api/mesh"):
            response = client.post(endpoint, json={"doc": cavity_document()})
            assert response.status_code == 400
            assert "Studio supports 2D only" in response.json()["detail"]
        assert client.get("/api/examples/cavity_box").status_code == 400
