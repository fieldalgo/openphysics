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
    assert list(doc.si["physics"]) == ["resonator"]
    assert sorted(doc.sole_physics()[1]) == ["boundary", "mode_count", "search", "target_frequency", "type"]
    assert doc.si["mesh"] == {"subdivision_count": [6, 6, 6]}
    assert doc.si["results"] == {"save_fields": True, "plots": False}
    assert "results" in [entry["path"] for entry in doc.defaults_applied]
    assert "250 MHz" in doc.summary() and "output coordinates m" in doc.summary()


P = "physics.em1."
SWEEP = {"type": "sweep", "parameter": P + "target_frequency", "values": {"unit": "MHz", "values": [100, 200]}}


@pytest.mark.parametrize("path,value,code,where", [
    (P + "target_frequency", "0 Hz", "E-DOMAIN", None), (P + "target_frequency", "nan Hz", "E-UNIT-UNKNOWN", None),
    (P + "target_frequency", True, "E-VALUE-FORM", None), (P + "target_frequency", "inf Hz", "E-UNIT-UNKNOWN", None),
    (P + "target_frequency", 250e6, "E-UNIT-MISSING", None), (P + "target_frequency", "1.55 um", "E-UNIT-DIMENSION", None),
    (P + "mode_count", 0, "E-DOMAIN", None), (P + "mode_count", 1.2, "E-DOMAIN", None),
    (P + "mode_count", 2.0, "E-DOMAIN", None), (P + "mode_count", True, "E-VALUE-FORM", None),
    (P + "search", "lowest", "E-VALUE-FORM", None), (P + "boundary", "pmc", "E-VALUE-FORM", None),
    (P + "vacuum_wavelength", "1 um", "E-KEY-UNKNOWN", None), (P + "formulation", "scalar", "E-KEY-UNKNOWN", None),
    (P + "target_frequency_hz", 250e6, "E-KEY-UNKNOWN", None), (P + "num_modes", 5, "E-KEY-UNKNOWN", None),
    (P + "allow_gain", True, "E-CONTRACT", None),
    ("geometry.domain.zmax", 0, "E-DOMAIN", None), ("geometry.domain.zmax", float("inf"), "E-JSON", None),
    ("geometry.domain.zmax", True, "E-VALUE-FORM", None), ("geometry.domain.xmin", "zero", "E-VALUE-FORM", None),
    ("geometry.depth", None, "E-KEY-UNKNOWN", None), ("geometry.depth", "1 m", "E-KEY-UNKNOWN", None),
    ("geometry.background.material", "Si", "E-MATERIAL-UNKNOWN", None),
    ("geometry.background.material", "physmat:Si", "E-CONTRACT", None),
    ("geometry.shapes", [{}], "E-KEY-MISSING", "geometry.shapes[0].material"),
    ("materials", {"glass": {"refractive_index": 2}}, "E-KEY-MISSING", "materials.glass.relative_permittivity"),
    ("mesh.subdivision_count", [0, 3, 3], "E-DOMAIN", "mesh.subdivision_count[0]"),
    ("mesh.subdivision_count", [2.5, 3, 3], "E-DOMAIN", "mesh.subdivision_count[0]"),
    ("mesh.subdivision_count", [True, 3, 3], "E-VALUE-FORM", "mesh.subdivision_count[0]"),
    ("mesh.subdivision_count", [3, 3], "E-VALUE-FORM", None),
    ("mesh.subdivisions", [6, 6, 6], "E-KEY-UNKNOWN", None),
    ("mesh.element_size", "0.2 m", "E-CONTRACT", None), ("mesh.grading", None, "E-VALUE-FORM", None),
    ("study", SWEEP, "E-CONTRACT", "study.type"),
    ("results.plots", True, "E-CONTRACT", None), ("results.save_fields", "yes", "E-VALUE-FORM", None),
    ("units", {}, "E-KEY-UNKNOWN", None), ("physics.other", {"type": "em.cavity3d"}, "E-KEY-MISSING", "physics.other.boundary"),
    ("openphysics", "0.2", "E-FORMAT", None),
])
def test_cavity_rejects_unsupported_or_invalid_inputs(path, value, code, where):
    data = cavity_document()
    node = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    first = [d for d in caught.value.diagnostics if d.severity == "error"][0]
    assert (first.code, first.path) == (code, where or path)


@pytest.mark.parametrize("path,where", [
    ("geometry.length_unit", None), ("mesh.subdivision_count", None), (P + "target_frequency", None),
    (P + "search", None), (P + "boundary", None), (P + "mode_count", None), ("geometry.domain.zmin", None),
    ("geometry.background", "geometry.background.material")])
def test_cavity_requires_explicit_physical_and_search_inputs(path, where):
    data = cavity_document()
    node = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    first = [d for d in caught.value.diagnostics if d.severity == "error"][0]
    assert (first.code, first.path) == ("E-KEY-MISSING", where or path)


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
        requested_modes=1, cluster_completeness="not_certified",
        mode_count_policy="exact_count_may_split_cluster",
    )
    return CavityRunResult(Document.from_dict(data), cavity, {"mesh_and_solve": 0.1}, ["fixture"])


@pytest.mark.parametrize("save_fields", [True, False])
def test_cavity_serialization_has_explicit_si_units_and_no_2d_arrays(tmp_path, save_fields):
    result = _result(save_fields)
    out = result.save(tmp_path / "output")
    summary = json.loads((out / "summary.json").read_text())
    units = summary["field_units"]
    assert units["resonant_frequency"] == "Hz" and units["node_coordinates"] == "m"
    assert units["mass_normalized_electric_field_line_integral"] == "1/m^(1/2)"
    assert units["mass_normalized_electric_field"] == "1/m^(3/2)"
    assert summary["resonant_frequency"] == {"unit": "Hz", "values": result.resonant_frequency.tolist()}
    assert summary["relative_residual"] == {"unit": "1", "values": [1e-12]}
    assert summary["field_layout"] == "cavity3d-edge-v2"
    assert summary["cluster_completeness"] == result.cluster_completeness == "not_certified"
    assert summary["mode_count_policy"] == result.mode_count_policy == "exact_count_may_split_cluster"
    assert summary["returned_mode_count"] == 1 and summary["mode_count"] == 5
    assert "neff" not in summary and "triangles" not in summary["mesh"]
    assert not any(key.endswith("_unit") or key.endswith("_hz") for key in summary)
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
            assert str(arrays["cluster_completeness"]) == "not_certified"
            assert str(arrays["mode_count_policy"]) == "exact_count_may_split_cluster"
            assert str(arrays["field_layout"]) == "cavity3d-edge-v2"
            metadata = json.loads(str(arrays["metadata_json"]))
            assert metadata["returned_mode_count"] == 1 and metadata["field_units"]["node_coordinates"] == "m"
            assert arrays["mass_normalized_electric_field"].shape == (1, 1, 3)
            assert arrays["mass_normalized_electric_field_line_integral"].shape == (2, 1)
            np.testing.assert_array_equal(arrays["pec_edge_ids"], [1])
            np.testing.assert_array_equal(arrays["mass_normalized_electric_field_line_integral"],
                                          result.cavity.edge_coefficients)
            assert not any(key.endswith("_unit") or key in ("returned_modes", "requested_modes")
                           for key in arrays.files)


def test_cavity_reused_output_rejected_without_mixing_results(tmp_path):
    out = _result(True).save(tmp_path / "output")
    (out / "notes.txt").write_text("user notes")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    second = _result(False)
    second.cavity.frequencies_hz *= 2
    with pytest.raises(FileExistsError, match="fresh output directory"):
        second.save(out)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


@pytest.mark.parametrize("name", ["summary.json", "model.json", "log.txt", "fields.npz", "results.png"])
def test_cavity_rejects_reserved_output_symlink_before_writing(tmp_path, name):
    out = tmp_path / "output"
    out.mkdir()
    missing_target = tmp_path / "user-target"
    (out / name).symlink_to(missing_target)
    with pytest.raises(FileExistsError, match="fresh output directory"):
        _result(False).save(out)
    assert list(out.iterdir()) == [out / name]
    assert (out / name).is_symlink() and not missing_target.exists()


def test_cavity_save_preserves_unrelated_files(tmp_path):
    (tmp_path / "notes.txt").write_text("user notes")
    _result(False).save(tmp_path)
    assert (tmp_path / "notes.txt").read_text() == "user notes"
    assert not (tmp_path / "fields.npz").exists()


def test_cavity_cli_reused_default_output_reports_error(tmp_path, monkeypatch, capsys):
    path = tmp_path / "box.json"
    result = _result(True)
    result.doc.save(path)
    monkeypatch.setattr("simcase.cli.run", lambda *args, **kwargs: result)
    assert main(["run", str(path)]) == 0
    capsys.readouterr()
    out = tmp_path / "box_results"
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    result = _result(False)
    result.doc.save(path)
    assert main(["run", str(path)]) == 1
    captured = capsys.readouterr()
    assert "fresh output directory" in captured.err
    assert "results written" not in captured.out
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


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


def test_cavity_guards_preserve_2d_mesh_preview():
    data = copy.deepcopy(examples.SLAB_TE_CHECK)
    model = build_mesh(Document.from_dict(copy.deepcopy(data)))
    assert model.tri.num_triangles > 0
    # format 0.3 takes one physics entry per document (every 0.3 kind): a second entry is refused at
    # read, before any mesh, where format 0.2 meshed the document and refused only the solve
    data["physics"]["second"] = copy.deepcopy(data["physics"]["em1"])
    with pytest.raises(DocumentError, match="2 physics .em1, second.; solving more than one"):
        Document.from_dict(data)


@pytest.mark.parametrize("unit,ratio", [("m", 1), ("mm", 1000), ("um", 1e6), ("nm", 1e9)])
def test_cavity_adapter_converts_lengths_and_translation_to_si(unit, ratio, monkeypatch):
    import galerkin
    from simcase import run
    data = cavity_document()
    data["geometry"]["length_unit"] = unit
    data["geometry"]["domain"] = {
        "xmin": ratio * 2, "xmax": ratio * 3,
        "ymin": ratio * -3, "ymax": ratio * -1,
        "zmin": ratio * 4, "zmax": ratio * 7,
    }
    captured = {}
    expected = _result().cavity
    original_nodes = expected.mesh.nodes.copy()
    def solve(lengths_m, subdivisions, **kwargs):
        captured.update(lengths_m=lengths_m, subdivisions=subdivisions, **kwargs)
        return expected
    monkeypatch.setattr(galerkin, "solve_cavity_box", solve, raising=False)
    result = run(Document.from_dict(data), verbose=False)
    # the lengths are differences of exact picometre corners: [1, 2, 3] m in every unit
    assert captured["lengths_m"] == [1.0, 2.0, 3.0]
    assert captured["subdivisions"] == [6, 6, 6]
    assert captured["target_frequency_hz"] == 250000000.0
    assert captured["num_modes"] == 5 and type(captured["num_modes"]) is int
    np.testing.assert_array_equal(result.cavity.mesh.nodes, original_nodes + [2, -3, 4])
    summary = result.summary()
    assert summary["resolved_inputs"]["geometry.domain.xmin"]["length_unit"] == unit
    assert summary["resolved_inputs"]["geometry.domain.xmin"]["value"] == 2.0
    assert summary["field_units"]["node_coordinates"] == "m"


def test_cavity_cli_reports_missing_engine_api_without_a_traceback(tmp_path, monkeypatch, capsys):
    import galerkin
    monkeypatch.delattr(galerkin, "solve_cavity_box", raising=False)
    path = tmp_path / "box.json"
    Document.from_dict(cavity_document()).save(path)
    assert main(["run", str(path), "-o", str(tmp_path / "output")]) == 1
    error = capsys.readouterr().err
    assert "matching cavity-enabled galerkin build" in error
    assert "Traceback" not in error
    assert not (tmp_path / "output").exists()
