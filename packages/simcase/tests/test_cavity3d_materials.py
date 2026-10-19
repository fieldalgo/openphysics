# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cavity documents with box materials and finite-conductivity walls."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from simcase import Document, DocumentError, examples, run
from simcase.cli import main

galerkin = pytest.importorskip("galerkin")


def slab_document():
    return copy.deepcopy(examples.CAVITY_LOSSY_SLAB)


def _set(data, path, value):
    node = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if part.isdigit() else node[part]
    last = parts[-1]
    if last.isdigit():
        node[int(last)] = value
    else:
        node[last] = value


def test_example_validates_and_summarizes_materials_and_walls():
    doc = Document.from_dict(slab_document())
    text = doc.summary()
    assert "sigma=5.8e+07 S/m (surface impedance)" in text
    assert "box slab: lossy_dielectric" in text
    example = Path(__file__).resolve().parents[1] / "examples" / "cavity_lossy_slab.json"
    with open(example, encoding="utf-8") as handle:
        assert json.load(handle) == examples.CAVITY_LOSSY_SLAB


@pytest.mark.parametrize("path,value,match", [
    ("geometry.shapes.0.zmax", 0.35, "grid plane"),
    ("geometry.shapes.0.zmax", 0.7, "inside the domain"),
    ("geometry.shapes.0.zmin", 0.3, "inside the domain"),
    ("geometry.shapes.0.material", "glass", "not defined"),
    ("geometry.shapes.0.type", "rect", "only type 'box'"),
    ("geometry.shapes.0.radius", 1, "unsupported cavity keys"),
    ("materials.lossy_dielectric.relative_permittivity", [4.0, 0.1], "passive"),
    ("materials.lossy_dielectric.relative_permittivity", [-4.0, 0.0], "positive"),
    ("materials.lossy_dielectric.relative_permittivity", [4.0], r"\[real, imag\]"),
    ("materials.lossy_dielectric.relative_permittivity", True, "positive"),
    ("materials.lossy_dielectric.n", 2.0, "unsupported cavity keys"),
    ("materials.vacuum", {"relative_permittivity": 2.0}, "not 'vacuum'"),
    ("geometry.background.material", "glass", "vacuum' or a name"),
    ("physics.em1.boundary", {"conductivity_s_per_m": 0}, "positive"),
    ("physics.em1.boundary", {"conductivity_s_per_m": True}, "positive"),
    ("physics.em1.boundary", {"conductivity_s_per_m": {"top": 1e6}}, "unknown walls"),
    ("physics.em1.boundary", {"conductivity_s_per_m": {}}, "at least one wall"),
    ("physics.em1.boundary", {"impedance": 1}, "unsupported cavity keys"),
    ("physics.em1.boundary", "pmc", "expected an object"),
])
def test_invalid_material_and_wall_documents(path, value, match):
    data = slab_document()
    _set(data, path, value)
    with pytest.raises(DocumentError, match=match):
        Document.from_dict(data)


def test_missing_permittivity_and_duplicate_shapes_are_rejected():
    data = slab_document()
    del data["materials"]["lossy_dielectric"]["relative_permittivity"]
    with pytest.raises(DocumentError, match="relative_permittivity is required"):
        Document.from_dict(data)
    data = slab_document()
    data["geometry"]["shapes"].append(copy.deepcopy(data["geometry"]["shapes"][0]))
    with pytest.raises(DocumentError, match="unique"):
        Document.from_dict(data)


def _small(data, n=4):
    data["mesh"]["subdivisions"] = [n, n, n]
    data["physics"]["em1"]["num_modes"] = 2
    data["results"]["save_fields"] = True
    return data


def test_document_run_equals_direct_engine_call():
    result = run(Document.from_dict(_small(slab_document())), verbose=False)
    direct = galerkin.solve_material_cavity_box(
        (1, 0.8, 0.6), (4, 4, 4),
        regions=[galerkin.CavityMaterialRegion(((0, 1), (0, 0.8), (0, 0.3)), 4 - 0.04j)],
        num_modes=2, target_frequency_hz=150e6, wall_conductivity_s_per_m=5.8e7)
    np.testing.assert_allclose(result.cavity.frequencies_hz, direct.frequencies_hz, rtol=1e-12)
    np.testing.assert_allclose(result.cavity.edge_coefficients, direct.edge_coefficients,
                               rtol=1e-9, atol=1e-12)


def test_millimetres_and_translation_give_the_same_si_result():
    base = run(Document.from_dict(_small(slab_document())), verbose=False)
    data = _small(slab_document())
    data["units"] = {"length": "mm"}
    shift = {"x": -500.0, "y": 200.0, "z": 1000.0}
    for key in list(data["geometry"]["domain"]):
        data["geometry"]["domain"][key] = data["geometry"]["domain"][key] * 1000 + shift[key[0]]
        data["geometry"]["shapes"][0][key] = data["geometry"]["shapes"][0][key] * 1000 + shift[key[0]]
    moved = run(Document.from_dict(data), verbose=False)
    np.testing.assert_allclose(moved.cavity.frequencies_hz, base.cavity.frequencies_hz, rtol=1e-10)
    np.testing.assert_allclose(moved.cavity.mesh.nodes,
                               base.cavity.mesh.nodes + [-0.5, 0.2, 1.0], atol=1e-12)


def test_single_wall_conductivity_maps_to_the_engine_wall():
    data = _small(slab_document())
    data["physics"]["em1"]["boundary"] = {"conductivity_s_per_m": {"zmax": 1e6}}
    result = run(Document.from_dict(data), verbose=False)
    walls = result.cavity.wall_conductivity_s_per_m
    assert walls["z1"] == 1e6 and all(walls[w] is None for w in walls if w != "z1")
    summary = result.summary()
    assert summary["wall_conductivity_s_per_m"]["zmax"] == 1e6
    assert summary["wall_conductivity_s_per_m"]["zmin"] is None
    z1 = np.all(np.isclose(result.cavity.mesh.nodes[result.cavity.space.edges][:, :, 2], 0.6), axis=1)
    pec = np.zeros(len(z1), dtype=bool)
    pec[result.cavity.pec_edge_ids] = True
    x = result.cavity.mesh.nodes[result.cavity.space.edges]
    on_other_walls = np.zeros(len(z1), dtype=bool)
    for axis, top in enumerate((1.0, 0.8, 0.6)):
        for position in (0.0, top):
            if (axis, position) != (2, 0.6):
                on_other_walls |= np.all(np.isclose(x[:, :, axis], position), axis=1)
    np.testing.assert_array_equal(pec, on_other_walls)
    assert np.any(z1 & ~pec)


def test_background_material_fills_the_box():
    data = _small(slab_document())
    data["geometry"]["shapes"] = []
    data["geometry"]["background"] = {"material": "lossy_dielectric"}
    data["physics"]["em1"]["boundary"] = "pec"
    data["physics"]["em1"]["target_frequency_hz"] = 80e6
    result = run(Document.from_dict(data), verbose=False)
    assert np.all(result.cavity.tet_relative_permittivity == 4 - 0.04j)
    vacuum = galerkin.solve_cavity_box((1, 0.8, 0.6), (4, 4, 4), num_modes=2,
                                       target_frequency_hz=160e6)
    np.testing.assert_allclose(result.cavity.eigenvalues_m2, vacuum.eigenvalues_m2 / (4 - 0.04j),
                               rtol=1e-10)


def test_complex_output_files_load_without_pickle(tmp_path):
    result = run(Document.from_dict(_small(slab_document())), verbose=False)
    out = result.save(tmp_path / "out")
    summary = json.loads((out / "summary.json").read_text())
    assert summary["field_layout"] == "cavity3d-edge-complex-v1"
    assert summary["time_convention"] == "exp(+j*omega*t)"
    assert summary["normalization"] == "vacuum_mass_hermitian_unit_si"
    np.testing.assert_allclose(summary["resonant_frequencies_hz"],
                               result.cavity.resonant_frequencies_hz, rtol=1e-15)
    np.testing.assert_allclose(summary["quality_factors"], result.cavity.quality_factors,
                               rtol=1e-15)
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        assert arrays["edge_coefficients"].dtype == np.complex128
        assert arrays["frequencies_hz"].dtype == np.complex128
        np.testing.assert_array_equal(arrays["frequencies_hz"], result.cavity.frequencies_hz)
        assert list(arrays["wall_names"]) == ["xmin", "xmax", "ymin", "ymax", "zmin", "zmax"]
        np.testing.assert_array_equal(arrays["wall_conductivity_s_per_m"], np.full(6, 5.8e7))
        assert str(arrays["field_layout"]) == "cavity3d-edge-complex-v1"
        assert arrays["tet_relative_permittivity"].shape == (result.cavity.mesh.num_tets,)


def test_lossless_quality_factor_is_null_in_json(tmp_path):
    data = _small(slab_document())
    data["materials"]["lossy_dielectric"]["relative_permittivity"] = 4.0
    data["physics"]["em1"]["boundary"] = "pec"
    data["results"]["save_fields"] = False
    result = run(Document.from_dict(data), verbose=False)
    assert result.cavity.lossless
    summary = json.loads(result.save(tmp_path / "out").joinpath("summary.json").read_text())
    assert summary["quality_factors"] == [None, None]
    assert summary["lossless"] is True
    assert not (tmp_path / "out" / "fields.npz").exists()


def test_vacuum_pec_document_keeps_the_original_solver(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("the vacuum PEC document must not use the material solver")
    monkeypatch.setattr(galerkin, "solve_material_cavity_box", fail)
    data = copy.deepcopy(examples.CAVITY_BOX)
    data["mesh"]["subdivisions"] = [2, 2, 2]
    data["physics"]["em1"]["num_modes"] = 1
    result = run(Document.from_dict(data), verbose=False)
    assert not result.complex_layout
    assert result.summary()["field_layout"] == "cavity3d-edge-v1"


def test_cli_run_and_missing_material_api(tmp_path, monkeypatch, capsys):
    path = tmp_path / "slab.json"
    Document.from_dict(_small(slab_document())).save(path)
    assert main(["run", str(path), "-o", str(tmp_path / "ok")]) == 0
    assert "quality_factors" in capsys.readouterr().out
    monkeypatch.delattr(galerkin, "solve_material_cavity_box")
    assert main(["run", str(path), "-o", str(tmp_path / "missing")]) == 1
    error = capsys.readouterr().err
    assert "solve_material_cavity_box" in error and "Traceback" not in error
    assert not (tmp_path / "missing").exists()


def test_studio_does_not_list_or_run_the_material_cavity():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    with TestClient(app) as client:
        assert "cavity_lossy_slab" not in client.get("/api/examples").json()["examples"]
        response = client.post("/api/run", json={"doc": slab_document()})
        assert response.status_code == 400
