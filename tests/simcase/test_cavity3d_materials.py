# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cavity documents with box materials and finite-conductivity walls (format 0.3).

Public complex values read under exp(-i omega t): loss is a positive imaginary part of a material
and a negative imaginary part of a resonant frequency. ``result.cavity`` is the galerkin result
in the kernel's exp(+j omega t) and keeps the kernel's signs."""

import copy
import json
import re
from pathlib import Path

import numpy as np
import pytest

from simcase import Document, DocumentError, examples, run
from simcase.cli import main

galerkin = pytest.importorskip("galerkin")

P = "physics.em1."
TC = "exp(-i omega t)"


def slab_document():
    return copy.deepcopy(examples.CAVITY_LOSSY_SLAB)


def _set(data, path, value):
    node, keys = data, re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for key in keys[:-1]:
        node = node[int(key[1:-1])] if key.startswith("[") else node[key]
    last = keys[-1]
    if last.startswith("["):
        node[int(last[1:-1])] = value
    else:
        node[last] = value


def _errors(data):
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    return [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"], str(caught.value)


def test_example_validates_and_summarizes_materials_and_walls():
    doc = Document.from_dict(slab_document())
    text = doc.summary()
    assert "all faces electrical_conductivity 58 MS/m (surface impedance)" in text
    assert "box slab: lossy_dielectric" in text
    assert "search: near_target 150 MHz, 3 mode(s)" in text
    example = Path(__file__).resolve().parents[2] / "examples" / "simcase" / "cavity_lossy_slab.json"
    with open(example, encoding="utf-8") as handle:
        assert json.load(handle) == examples.CAVITY_LOSSY_SLAB


S0 = "geometry.shapes[0]"
SLAB = "materials.lossy_dielectric"


@pytest.mark.parametrize("path,value,code,where,match", [
    (f"{S0}.zmax", 0.35, "E-CONTRACT", f"{S0}.zmax", "mesh grid plane"),
    (f"{S0}.zmax", 0.7, "E-DOMAIN", f"{S0}.zmax", "inside the domain"),
    (f"{S0}.zmin", 0.3, "E-DOMAIN", f"{S0}.zmax", "inside the domain"),
    (f"{S0}.material", "glass", "E-MATERIAL-UNKNOWN", f"{S0}.material", "no record in materials"),
    (f"{S0}.material", "physmat:vacuum", "E-CONTRACT", f"{S0}.material", "background only"),
    (f"{S0}.type", "rect", "E-CONTRACT", f"{S0}.type", "only type 'box'"),
    (f"{S0}.radius", 1, "E-KEY-UNKNOWN", f"{S0}.radius", "unknown key"),
    (f"{S0}.element_size", "0.1 m", "E-CONTRACT", f"{S0}.element_size", "mesh.subdivision_count"),
    (f"{SLAB}.relative_permittivity", {"re": 4.0, "im": -0.1}, "E-GAIN", f"{SLAB}.relative_permittivity.im",
     "exp"),
    (f"{SLAB}.relative_permeability", {"re": 1.0, "im": -0.01}, "E-GAIN", f"{SLAB}.relative_permeability.im",
     "exp"),
    (f"{SLAB}.relative_permittivity", {"re": -4.0, "im": 0.0}, "E-DOMAIN", f"{SLAB}.relative_permittivity.re",
     "real part > 0"),
    (f"{SLAB}.relative_permittivity", -4.0, "E-DOMAIN", f"{SLAB}.relative_permittivity", "real part > 0"),
    (f"{SLAB}.relative_permeability", 0.0, "E-DOMAIN", f"{SLAB}.relative_permeability", "real part > 0"),
    (f"{SLAB}.relative_permittivity", [4.0, 0.1], "E-VALUE-FORM", f"{SLAB}.relative_permittivity", "re"),
    (f"{SLAB}.relative_permittivity", [4.0], "E-VALUE-FORM", f"{SLAB}.relative_permittivity", "re"),
    (f"{SLAB}.relative_permittivity", True, "E-VALUE-FORM", f"{SLAB}.relative_permittivity", "number"),
    (f"{SLAB}.n", 2.0, "E-KEY-UNKNOWN", f"{SLAB}.n", "unknown key"),
    (f"{SLAB}.loss_tangent", 0.01, "E-CONTRACT", f"{SLAB}.loss_tangent", "loss_tangent"),
    ("geometry.background.material", "glass", "E-MATERIAL-UNKNOWN", "geometry.background.material",
     "no record in materials"),
    ("geometry.background.material", "vacuum", "E-MATERIAL-UNKNOWN", "geometry.background.material",
     "physmat:"),
    ("geometry.background.material", "physmat:Si", "E-CONTRACT", "geometry.background.material",
     "relative_permittivity"),
    (f"{P}boundary", {"electrical_conductivity": "0 S/m"}, "E-DOMAIN", f"{P}boundary.electrical_conductivity",
     "> 0"),
    (f"{P}boundary", {"electrical_conductivity": True}, "E-VALUE-FORM", f"{P}boundary.electrical_conductivity",
     "quantity"),
    (f"{P}boundary", {"electrical_conductivity": 5.8e7}, "E-UNIT-MISSING",
     f"{P}boundary.electrical_conductivity", "no unit"),
    (f"{P}boundary", {"electrical_conductivity": "58 mS/m"}, "E-UNIT-NOT-ACCEPTED",
     f"{P}boundary.electrical_conductivity", "mS/m"),
    (f"{P}boundary", {"electrical_conductivity": {"top": "1 MS/m"}}, "E-KEY-UNKNOWN",
     f"{P}boundary.electrical_conductivity.top", "unknown wall"),
    (f"{P}boundary", {"electrical_conductivity": {}}, "E-KEY-MISSING", f"{P}boundary.electrical_conductivity",
     "at least one wall"),
    (f"{P}boundary", {}, "E-KEY-MISSING", f"{P}boundary.electrical_conductivity", "every wall"),
    (f"{P}boundary", {"impedance": 1}, "E-KEY-UNKNOWN", f"{P}boundary.impedance", "unknown key"),
    (f"{P}boundary", {"conductivity_s_per_m": 5.8e7}, "E-KEY-UNKNOWN", f"{P}boundary.conductivity_s_per_m",
     "electrical_conductivity"),
    (f"{P}boundary", "pmc", "E-VALUE-FORM", f"{P}boundary", "pec"),
    (f"{P}allow_gain", True, "E-CONTRACT", f"{P}allow_gain", "passive"),
])
def test_invalid_material_and_wall_documents(path, value, code, where, match):
    data = slab_document()
    _set(data, path, value)
    errors, text = _errors(data)
    assert errors[0] == (code, where)
    assert re.search(match, text)


def test_missing_permittivity_and_duplicate_shapes_are_rejected():
    data = slab_document()
    del data["materials"]["lossy_dielectric"]["relative_permittivity"]
    assert _errors(data)[0] == [("E-KEY-MISSING", f"{SLAB}.relative_permittivity")]
    data = slab_document()
    data["geometry"]["shapes"].append(copy.deepcopy(data["geometry"]["shapes"][0]))
    errors, text = _errors(data)
    assert errors == [("E-CONTRACT", "geometry.shapes[1].name")] and "unique" in text


def test_a_local_material_named_vacuum_is_an_ordinary_record():
    """Format 0.3 frees the name (the library vacuum is "physmat:vacuum"): a local record named
    vacuum is solved with its own values, exactly as the same record under another name."""
    def frequencies(name, eps):
        data = _small(copy.deepcopy(examples.CAVITY_BOX), n=3)
        data["physics"]["em1"]["mode_count"] = 4
        data["results"]["save_fields"] = False
        data["materials"] = {name: {"relative_permittivity": eps}}
        data["geometry"]["background"] = {"material": name}
        return run(Document.from_dict(data), verbose=False).resonant_frequency
    np.testing.assert_array_equal(frequencies("vacuum", 2.0), frequencies("glass", 2.0))
    assert not np.array_equal(frequencies("vacuum", 2.0), frequencies("vacuum", 1.0))


def _small(data, n=4):
    data["mesh"]["subdivision_count"] = [n, n, n]
    data["physics"]["em1"]["mode_count"] = 2
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
    np.testing.assert_array_equal(result.resonant_frequency, np.conj(result.cavity.frequencies_hz))
    assert np.all(result.resonant_frequency.imag < 0) and np.all(result.quality_factor > 0)


def test_millimetres_and_translation_give_the_same_si_result():
    base = run(Document.from_dict(_small(slab_document())), verbose=False)
    data = _small(slab_document())
    data["geometry"]["length_unit"] = "mm"
    shift = {"x": -500.0, "y": 200.0, "z": 1000.0}
    for key in list(data["geometry"]["domain"]):
        data["geometry"]["domain"][key] = data["geometry"]["domain"][key] * 1000 + shift[key[0]]
        data["geometry"]["shapes"][0][key] = data["geometry"]["shapes"][0][key] * 1000 + shift[key[0]]
    moved = run(Document.from_dict(data), verbose=False)
    np.testing.assert_allclose(moved.cavity.frequencies_hz, base.cavity.frequencies_hz, rtol=1e-10)
    np.testing.assert_allclose(moved.cavity.mesh.nodes,
                               base.cavity.mesh.nodes + [-0.5, 0.2, 1.0], atol=1e-12)
    np.testing.assert_allclose(moved.node_coordinates, base.node_coordinates + [-0.5, 0.2, 1.0], atol=1e-12)


def test_single_wall_conductivity_maps_to_the_engine_wall():
    data = _small(slab_document())
    data["physics"]["em1"]["boundary"] = {"electrical_conductivity": {"zmax": "1 MS/m"}}
    result = run(Document.from_dict(data), verbose=False)
    walls = result.cavity.wall_conductivity_s_per_m
    assert walls["z1"] == 1e6 and all(walls[w] is None for w in walls if w != "z1")
    summary = result.summary()
    assert summary["electrical_conductivity"]["zmax"] == {"value": 1e6, "unit": "S/m"}
    assert summary["electrical_conductivity"]["zmin"] is None
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
    data["physics"]["em1"]["target_frequency"] = "80 MHz"
    result = run(Document.from_dict(data), verbose=False)
    assert np.all(result.cavity.tet_relative_permittivity == 4 - 0.04j)
    assert np.all(result.arrays()["relative_permittivity"] == 4 + 0.04j)
    vacuum = galerkin.solve_cavity_box((1, 0.8, 0.6), (4, 4, 4), num_modes=2,
                                       target_frequency_hz=160e6)
    np.testing.assert_allclose(result.cavity.eigenvalues_m2, vacuum.eigenvalues_m2 / (4 - 0.04j),
                               rtol=1e-10)
    np.testing.assert_allclose(result.wavenumber_squared, np.conj(vacuum.eigenvalues_m2 / (4 - 0.04j)),
                               rtol=1e-10)


def test_complex_output_files_load_without_pickle(tmp_path):
    result = run(Document.from_dict(_small(slab_document())), verbose=False)
    out = result.save(tmp_path / "out")
    summary = json.loads((out / "summary.json").read_text())
    assert summary["field_layout"] == "cavity3d-edge-complex-v2"
    assert summary["time_convention"] == TC
    assert summary["normalization"] == "vacuum_mass_hermitian_unit_si"
    frequency = summary["resonant_frequency"]
    assert frequency["unit"] == "Hz" and frequency["time_convention"] == TC
    np.testing.assert_allclose(frequency["re"], result.cavity.resonant_frequencies_hz, rtol=1e-15)
    np.testing.assert_allclose(frequency["im"], -result.cavity.frequencies_hz.imag, rtol=1e-15)
    assert summary["quality_factor"]["unit"] == "1"
    np.testing.assert_allclose(summary["quality_factor"]["values"], result.cavity.quality_factors,
                               rtol=1e-15)
    assert not any(key.endswith("_unit") or key.endswith("_hz") for key in summary)
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        assert arrays["mass_normalized_electric_field_line_integral"].dtype == np.complex128
        assert arrays["resonant_frequency"].dtype == np.complex128
        np.testing.assert_array_equal(arrays["resonant_frequency"], np.conj(result.cavity.frequencies_hz))
        assert list(arrays["wall_names"]) == ["xmin", "xmax", "ymin", "ymax", "zmin", "zmax"]
        np.testing.assert_array_equal(arrays["electrical_conductivity"], np.full(6, 5.8e7))
        assert str(arrays["field_layout"]) == "cavity3d-edge-complex-v2"
        assert arrays["relative_permittivity"].shape == (result.cavity.mesh.num_tets,)
        np.testing.assert_array_equal(arrays["relative_permittivity"],
                                      np.conj(result.cavity.tet_relative_permittivity))
        metadata = json.loads(str(arrays["metadata_json"]))
        assert metadata["time_convention"] == TC
        assert metadata["field_units"]["mass_normalized_electric_field"] == "1/m^(3/2)"
        assert not any(key.endswith("_unit") for key in arrays.files)


def test_lossless_quality_factor_is_null_in_json(tmp_path):
    data = _small(slab_document())
    data["materials"]["lossy_dielectric"]["relative_permittivity"] = 4.0
    data["physics"]["em1"]["boundary"] = "pec"
    data["results"]["save_fields"] = False
    result = run(Document.from_dict(data), verbose=False)
    assert result.cavity.lossless
    summary = json.loads(result.save(tmp_path / "out").joinpath("summary.json").read_text())
    assert summary["quality_factor"] == {"unit": "1", "values": [None, None]}
    assert summary["lossless"] is True
    assert not (tmp_path / "out" / "fields.npz").exists()


def test_vacuum_pec_document_keeps_the_original_solver(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("the vacuum PEC document must not use the material solver")
    monkeypatch.setattr(galerkin, "solve_material_cavity_box", fail)
    data = copy.deepcopy(examples.CAVITY_BOX)
    data["mesh"]["subdivision_count"] = [2, 2, 2]
    data["physics"]["em1"]["mode_count"] = 1
    result = run(Document.from_dict(data), verbose=False)
    assert not result.complex_layout
    assert result.summary()["field_layout"] == "cavity3d-edge-v2"
    assert "time_convention" not in result.summary()


def test_cli_run_and_missing_material_api(tmp_path, monkeypatch, capsys):
    path = tmp_path / "slab.json"
    Document.from_dict(_small(slab_document())).save(path)
    assert main(["run", str(path), "-o", str(tmp_path / "ok")]) == 0
    out = capsys.readouterr().out
    assert "quality_factor" in out and "time convention exp(-i omega t)" in out
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
