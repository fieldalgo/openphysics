# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""VTU and PVD export of saved em.modes2d results (em-modes2d-p1-node-centroid-v1)."""

import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from simcase import Document, examples, run
from simcase.export import export_fields, export_sweep, export_time_series

meshio = pytest.importorskip("meshio", reason="install the export extra: pip install 'simcase[export]'")
EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "simcase"
LAYOUT = "em-modes2d-p1-node-centroid-v1"
SUBSPACE_LAYOUT = "em-modes2d-subspace-raw-v1"


def _scalar_slab(symbol="um", ratio=1.0):
    """A coarse lossless scalar slab, written in the length unit ``symbol``."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["geometry"]["shapes"][0]["mesh_size"] = 0.03
    d["mesh"] = {"size": 0.12, "grading": {"center": [0.0, 0.11], "near": 0.03, "far": 0.12, "distance": 1.0}}
    d["results"] = {"plots": False}
    d["units"] = {"length": symbol}
    g = d["geometry"]
    g["domain"] = {k: v * ratio for k, v in g["domain"].items()}
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h", "mesh_size"):
            s[k] *= ratio
    d["mesh"]["size"] *= ratio
    gr = d["mesh"]["grading"]
    gr["center"] = [c * ratio for c in gr["center"]]
    for k in ("near", "far", "distance"):
        gr[k] *= ratio
    d["physics"]["em1"]["wavelength"] *= ratio
    return d


def _saved(tmp_path, data, name="result"):
    out = run(Document.from_dict(data), False).save(tmp_path / name)
    with np.load(out / "fields.npz", allow_pickle=False) as archive:
        saved = {key: archive[key] for key in archive.files}
    return out, saved


def _collection(pvd):
    root = ET.parse(pvd).getroot()
    assert root.tag == "VTKFile" and root.get("type") == "Collection"
    return [(float(d.get("timestep")), d.get("file")) for d in root.iter("DataSet")]


def _assert_mesh(mesh, saved):
    """X1: points are the saved nodes times the saved unit size, exactly; z = 0."""
    expected = saved["nodes"] * saved["length_unit_to_m"]
    np.testing.assert_allclose(mesh.points[:, :2], expected, rtol=1e-15, atol=0)
    np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
    np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
    regions = mesh.cell_data["triangle_regions"][0]
    assert regions.dtype.kind in "iu"
    np.testing.assert_array_equal(regions, saved["regions"])


@pytest.mark.parametrize("symbol, ratio, size", [("nm", 1e3, 1e-9), ("um", 1.0, 1e-6), ("m", 1e-6, 1.0)])
def test_scalar_single_point_round_trips_in_metres(tmp_path, symbol, ratio, size):
    out, saved = _saved(tmp_path, _scalar_slab(symbol, ratio))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["field_layout"] == str(saved["field_layout"]) == LAYOUT
    assert summary["mesh_length_unit"] == str(saved["mesh_length_unit"]) == symbol
    assert summary["length_unit_to_m"] == float(saved["length_unit_to_m"]) == size
    assert str(saved["study_parameter"]) == ""
    assert saved["fields"].dtype.kind == "f" and saved["fields"].shape[0] == 1
    mesh = meshio.read(export_fields(out / "fields.npz", tmp_path / f"{symbol}.vtu"))
    _assert_mesh(mesh, saved)
    # The exported points are the mesh in metres: the slab spans the same metres in every unit.
    np.testing.assert_allclose(mesh.points[:, 1].max(), 1.2e-6, rtol=1e-12)
    assert set(mesh.point_data) == {"mode_0"}
    np.testing.assert_array_equal(mesh.point_data["mode_0"], saved["fields"][0][:, 0])
    assert set(mesh.cell_data) == {"triangle_regions"}
    assert "neff" not in mesh.point_data and "neff" not in mesh.cell_data


def test_lossy_scalar_modes_are_written_as_real_and_imaginary_parts(tmp_path):
    d = _scalar_slab()
    d["materials"] = {"Si": {"n": 3.48, "k": 0.01}}
    d["physics"]["em1"]["num_modes"] = 2
    out, saved = _saved(tmp_path, d)
    assert saved["fields"].dtype.kind == "c" and saved["fields"].shape[2] == 2
    mesh = meshio.read(export_fields(out / "fields.npz", tmp_path / "lossy.vtu"))
    _assert_mesh(mesh, saved)
    assert set(mesh.point_data) == {"mode_0_real", "mode_0_imag", "mode_1_real", "mode_1_imag"}
    for k in range(2):
        np.testing.assert_array_equal(mesh.point_data[f"mode_{k}_real"], saved["fields"][0][:, k].real)
        np.testing.assert_array_equal(mesh.point_data[f"mode_{k}_imag"], saved["fields"][0][:, k].imag)
    assert np.any(mesh.point_data["mode_0_imag"])


def test_vector_single_point_writes_centroid_cell_data_and_nodal_longitudinal_pairs(tmp_path):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["results"] = {"plots": False}
    out, saved = _saved(tmp_path, d)
    assert str(saved["field_representation"]) == "vector-edge-nodal-v1"
    assert "fields" not in saved
    mesh = meshio.read(export_fields(out / "fields.npz", tmp_path / "vector.vtu"))
    _assert_mesh(mesh, saved)
    electric, longitudinal = saved["vector_electric"][0], saved["vector_longitudinal"][0]
    modes = electric.shape[1]
    assert modes == 1
    assert set(mesh.cell_data) == {"triangle_regions"} | {
        f"electric_field_mode_{k}_{part}" for k in range(modes) for part in ("real", "imag")}
    assert set(mesh.point_data) == {
        f"longitudinal_electric_mode_{k}_{part}" for k in range(modes) for part in ("real", "imag")}
    for k in range(modes):
        for part in ("real", "imag"):
            cell = mesh.cell_data[f"electric_field_mode_{k}_{part}"][0]
            assert cell.shape == (len(saved["triangles"]), 3) and cell.dtype.kind == "f"
            np.testing.assert_array_equal(cell, getattr(electric[:, k, :], part))
            np.testing.assert_array_equal(mesh.point_data[f"longitudinal_electric_mode_{k}_{part}"],
                                          getattr(longitudinal[:, k], part))
    # The saved normalization is kept: the largest centroid |E| is one.
    magnitude = np.hypot(np.linalg.norm(mesh.cell_data["electric_field_mode_0_real"][0], axis=1),
                         np.linalg.norm(mesh.cell_data["electric_field_mode_0_imag"][0], axis=1))
    np.testing.assert_allclose(magnitude.max(), 1.0)
    # Edge coefficients and n_eff stay in the NPZ only.
    for name in ("edges", "vector_transverse", "neff"):
        assert name in saved and name not in mesh.point_data and name not in mesh.cell_data


def test_pml_result_exports_the_whole_computational_domain(tmp_path):
    doc = Document.load(EXAMPLES / "pml_leaky_slab.json")
    doc.data["results"] = {"plots": False}
    out = run(doc, False).save(tmp_path / "pml")
    with np.load(out / "fields.npz", allow_pickle=False) as archive:
        saved = {key: archive[key] for key in archive.files}
    assert str(saved["field_layout"]) == LAYOUT
    assert str(saved["field_representation"]).startswith("pml-")
    mesh = meshio.read(export_fields(out / "fields.npz", tmp_path / "pml.vtu"))
    _assert_mesh(mesh, saved)
    # The mesh, and so the exported arrays, extend beyond the physical window into the PML.
    bounds = np.asarray(json.loads(str(saved["open_boundary_json"]))[0]["physical_bounds"])
    nodes_m = mesh.points[:, :2] / float(saved["length_unit_to_m"])
    assert nodes_m[:, 1].min() < bounds[0][1] - 1e-9 and nodes_m[:, 1].max() > bounds[1][1] + 1e-9
    assert all(name.startswith(("electric_field_mode_", "triangle_regions")) for name in mesh.cell_data)
    assert "open_boundary_json" not in mesh.point_data and "open_boundary_json" not in mesh.cell_data


def test_vector_wavelength_sweep_collection_uses_the_wavelengths(tmp_path):
    d = copy.deepcopy(examples.VECTOR_SLAB_SWEEP)
    d["results"] = {"plots": False}
    out, saved = _saved(tmp_path, d)
    assert str(saved["study_parameter"]) == "physics.em1.wavelength"
    points = len(saved["values"])
    assert points == 5
    with pytest.raises(ValueError, match="5 study points.*export_sweep"):
        export_fields(out / "fields.npz", tmp_path / "single.vtu")
    assert not (tmp_path / "single.vtu").exists()
    target = tmp_path / "sweep"
    pvd = export_sweep(out / "fields.npz", target)
    assert pvd == target / "fields.pvd"
    entries = _collection(pvd)
    # X3: one VTU per point; timesteps are the wavelengths (document unit), round-tripped by repr.
    assert len(entries) == points
    assert [t for t, _ in entries] == saved["values"].tolist()
    assert [f for _, f in entries] == [f"fields_{k:05d}.vtu" for k in range(points)]
    assert sorted(p.name for p in target.iterdir()) == sorted([pvd.name] + [f for _, f in entries])
    for k, (_, name) in enumerate(entries):
        mesh = meshio.read(target / name)
        _assert_mesh(mesh, saved)
        np.testing.assert_array_equal(mesh.cell_data["electric_field_mode_0_real"][0],
                                      saved["vector_electric"][k][:, 0, :].real)
        np.testing.assert_array_equal(mesh.cell_data["electric_field_mode_0_imag"][0],
                                      saved["vector_electric"][k][:, 0, :].imag)
        np.testing.assert_array_equal(mesh.point_data["longitudinal_electric_mode_0_imag"],
                                      saved["vector_longitudinal"][k][:, 0].imag)


@pytest.mark.parametrize("parameter, values, expected", [
    ("physics.em1.wavelength", [1.55, 1.5, 1.6], [0.0, 1.0, 2.0]),      # not monotone: indices
    ("physics.em1.n_cladding", [1.3, 1.4, 1.5], [0.0, 1.0, 2.0]),       # not a wavelength: indices
    ("physics.em1.wavelength", [1.6, 1.55, 1.5], [1.6, 1.55, 1.5]),     # monotone wavelength: values
])
def test_scalar_sweep_collection_timesteps(tmp_path, parameter, values, expected):
    d = _scalar_slab()
    d["physics"]["em1"]["n_cladding"] = 1.44
    d["study"] = {"type": "sweep", "parameter": parameter, "values": values}
    out, saved = _saved(tmp_path, d)
    assert str(saved["study_parameter"]) == parameter
    assert saved["fields"].shape[0] == 3
    pvd = export_sweep(out / "fields.npz", tmp_path / "sweep", name="modes")
    entries = _collection(pvd)
    assert [t for t, _ in entries] == expected
    assert [f for _, f in entries] == [f"modes_{k:05d}.vtu" for k in range(3)]
    for k, (_, name) in enumerate(entries):
        mesh = meshio.read(tmp_path / "sweep" / name)
        _assert_mesh(mesh, saved)
        assert set(mesh.point_data) == {"mode_0"}
        np.testing.assert_array_equal(mesh.point_data["mode_0"], saved["fields"][k][:, 0])


def test_single_point_result_is_also_a_one_frame_collection(tmp_path):
    out, saved = _saved(tmp_path, _scalar_slab())
    entries = _collection(export_sweep(out / "fields.npz", tmp_path / "one"))
    assert entries == [(0.0, "fields_00000.vtu")]
    mesh = meshio.read(tmp_path / "one" / "fields_00000.vtu")
    np.testing.assert_array_equal(mesh.point_data["mode_0"], saved["fields"][0][:, 0])


def test_legacy_result_without_a_layout_is_refused_with_no_output(tmp_path):
    out, saved = _saved(tmp_path, _scalar_slab())
    legacy = tmp_path / "legacy.npz"
    np.savez(legacy, **{k: v for k, v in saved.items() if k != "field_layout"})
    with np.load(legacy, allow_pickle=False) as archive:
        assert "field_layout" not in archive.files and "neff" in archive.files
    message = r"no 'field_layout' array.*regenerated.*model\.json"
    with pytest.raises(ValueError, match=message):
        export_fields(legacy, tmp_path / "legacy.vtu")
    assert not (tmp_path / "legacy.vtu").exists()
    with pytest.raises(ValueError, match=message):
        export_sweep(legacy, tmp_path / "legacy")
    assert not (tmp_path / "legacy").exists()
    with pytest.raises(ValueError, match=message):
        export_time_series(legacy, tmp_path / "legacy")
    assert not (tmp_path / "legacy").exists()


def test_subspace_layout_is_refused_by_both_exporters(tmp_path):
    d = copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP)
    d["results"] = {"plots": False}
    out, saved = _saved(tmp_path, d, "subspace")
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["field_layout"] == str(saved["field_layout"]) == SUBSPACE_LAYOUT
    assert summary["field_representation"] == "vector-subspace-edge-nodal-v1"
    assert summary["mesh_length_unit"] == str(saved["mesh_length_unit"]) == "um"
    assert summary["length_unit_to_m"] == float(saved["length_unit_to_m"]) == 1e-6
    assert str(saved["study_parameter"]) == "physics.em1.wavelength"
    message = r"em-modes2d-subspace-raw-v1.*raw eigenpair columns.*deferred"
    with pytest.raises(ValueError, match=message):
        export_fields(out / "fields.npz", tmp_path / "subspace.vtu")
    assert not (tmp_path / "subspace.vtu").exists()
    with pytest.raises(ValueError, match=message):
        export_sweep(out / "fields.npz", tmp_path / "subspace-sweep")
    assert not (tmp_path / "subspace-sweep").exists()
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(out / "fields.npz", tmp_path / "subspace-series")
    assert not (tmp_path / "subspace-series").exists()


def test_existing_output_is_never_touched(tmp_path):
    d = copy.deepcopy(examples.VECTOR_SLAB_SWEEP)
    d["results"] = {"plots": False}
    out, _ = _saved(tmp_path, d)
    fields = out / "fields.npz"
    target = tmp_path / "sweep"
    pvd = export_sweep(fields, target)
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    with pytest.raises(FileExistsError):
        export_sweep(fields, target)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before
    assert pvd.exists()
    full = tmp_path / "full"
    full.mkdir()
    (full / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_sweep(fields, full)
    assert [p.name for p in full.iterdir()] == ["keep.txt"]
    for bad in ("", "a/b", "a\\b", "..", "c:x"):
        with pytest.raises(ValueError, match="plain file stem"):
            export_sweep(fields, tmp_path / "named", name=bad)
    assert not (tmp_path / "named").exists()
    single = copy.deepcopy(examples.VECTOR_SLAB)
    single["results"] = {"plots": False}
    out, _ = _saved(tmp_path, single, "single")
    vtu = export_fields(out / "fields.npz", tmp_path / "once.vtu")
    bytes_before = vtu.read_bytes()
    with pytest.raises(FileExistsError):
        export_fields(out / "fields.npz", vtu)
    assert vtu.read_bytes() == bytes_before
    thermal = run(Document.load(EXAMPLES / "thermal_slab.json"), False).save(tmp_path / "thermal")
    with pytest.raises(ValueError, match="sweep export needs layout"):
        export_sweep(thermal / "fields.npz", tmp_path / "thermal-sweep")
    assert not (tmp_path / "thermal-sweep").exists()


def test_corrupt_arrays_are_refused_before_anything_is_written(tmp_path):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["results"] = {"plots": False}
    out, saved = _saved(tmp_path, d)
    cases = {
        "vector_electric": (saved["vector_electric"][:, :-1], "vector_electric: expected shape"),
        "vector_longitudinal": (saved["vector_longitudinal"][:, :-1], "vector_longitudinal: expected shape"),
        "regions": (saved["regions"].astype(float), "regions must contain"),
        "length_unit_to_m": (np.array(-1e-6), "length_unit_to_m must be one positive finite number"),
        "values": (np.array([1.55, 1.6]), "values: expected one study value per point"),
    }
    for name, (value, message) in cases.items():
        corrupt = tmp_path / f"{name}.npz"
        np.savez(corrupt, **dict(saved, **{name: value}))
        with pytest.raises(ValueError, match=message):
            export_fields(corrupt, tmp_path / f"{name}.vtu")
        assert not (tmp_path / f"{name}.vtu").exists()
        with pytest.raises(ValueError, match=message):
            export_sweep(corrupt, tmp_path / name)
        assert not (tmp_path / name).exists()
    scalar_out, scalar = _saved(tmp_path, _scalar_slab(), "scalar")
    corrupt = tmp_path / "fields.npz"
    np.savez(corrupt, **dict(scalar, fields=scalar["fields"][:, :-1]))
    with pytest.raises(ValueError, match="fields: expected shape"):
        export_fields(corrupt, tmp_path / "fields.vtu")
    neither = tmp_path / "neither.npz"
    np.savez(neither, **{k: v for k, v in scalar.items() if k != "fields"})
    with pytest.raises(ValueError, match="needs the saved fields .scalar. or vector_electric"):
        export_fields(neither, tmp_path / "neither.vtu")
    assert not any(tmp_path.glob("*.vtu"))


def test_sweep_export_removes_partial_output_on_failure(tmp_path, monkeypatch):
    d = copy.deepcopy(examples.VECTOR_SLAB_SWEEP)
    d["results"] = {"plots": False}
    out, _ = _saved(tmp_path, d)
    calls = []
    real_write = meshio.vtu.write

    def failing_write(path, mesh, **kwargs):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("simulated write failure")
        return real_write(path, mesh, **kwargs)

    monkeypatch.setattr(meshio.vtu, "write", failing_write)
    target = tmp_path / "partial"
    with pytest.raises(OSError, match="simulated"):
        export_sweep(out / "fields.npz", target)
    assert not target.exists()
    kept = tmp_path / "kept"
    kept.mkdir()
    calls.clear()
    with pytest.raises(OSError, match="simulated"):
        export_sweep(out / "fields.npz", kept)
    assert kept.is_dir() and not any(kept.iterdir())
