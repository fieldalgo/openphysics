# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""VTU and PVD export of saved em.modes2d results (em-modes2d-p1-node-centroid-v2)."""

import copy
from decimal import Decimal
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from simcase import Document, examples, run
from simcase.export import export_fields, export_sweep, export_time_series, read_field_data

meshio = pytest.importorskip("meshio", reason="install the export extra: pip install 'simcase[export]'")
EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "simcase"
LAYOUT = "em-modes2d-p1-node-centroid-v2"
SUBSPACE_LAYOUT = "em-modes2d-subspace-raw-v2"
TAGGED = re.compile(r"(-?[0-9][0-9.eE+-]*) um")


def _exact(value, factor_text):
    return float(Decimal(repr(float(value))) * Decimal(factor_text))


def _written_in(data, symbol, factor_text):
    """The same document typed in ``symbol``: shape numbers and tagged lengths rescaled as decimals."""
    d = copy.deepcopy(data)
    g = d["geometry"]
    g["length_unit"] = symbol
    g["domain"] = {k: _exact(v, factor_text) for k, v in g["domain"].items()}
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h", "cx", "cy", "r"):
            if k in s:
                s[k] = _exact(s[k], factor_text)

    def retag(node):
        if isinstance(node, dict):
            if node.get("unit") == "um" and isinstance(node.get("values"), list):   # a study value list
                return {"unit": symbol, "values": [_exact(v, factor_text) for v in node["values"]]}
            return {k: retag(v) for k, v in node.items()}
        if isinstance(node, list):
            return [retag(v) for v in node]
        found = TAGGED.fullmatch(node) if isinstance(node, str) else None
        return f"{Decimal(found.group(1)) * Decimal(factor_text)} {symbol}" if found else node
    return retag(d)


def _scalar_slab(symbol="um", factor_text="1"):
    """A coarse lossless scalar slab, written in the length unit ``symbol``."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["geometry"]["shapes"][0]["element_size"] = "0.03 um"
    d["mesh"] = {"element_size": "0.12 um", "grading": {"position": ["0 um", "0.11 um"], "near": "0.03 um",
                                                        "far": "0.12 um", "refinement_distance": "1 um"}}
    d["results"] = {"plots": False}
    return _written_in(d, symbol, factor_text)


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
    """X1: points are the saved node coordinates in metres, exactly; z = 0."""
    np.testing.assert_array_equal(mesh.points[:, :2], saved["node_coordinates"])
    np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
    np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
    regions = mesh.cell_data["regions"][0]
    assert regions.dtype.kind in "iu"
    np.testing.assert_array_equal(regions, saved["regions"])


def _assert_field_data(vtu, mesh, summary):
    """The FieldData block: each exported array's unit is its saved array's, and complex parts
    name the time convention."""
    block = read_field_data(vtu)
    exported = [n for n in (*mesh.point_data, *mesh.cell_data) if n != "regions"]
    base = {n: re.fullmatch(r"(.+)_mode_\d+(_real|_imag)?", n).group(1) for n in exported}
    assert block["units"] == {n: summary["field_units"][base[n]] for n in exported}
    if any(n.endswith(("_real", "_imag")) for n in exported):
        assert block["conventions"]["time_convention"] == "exp(-i omega t)" == summary["time_convention"]
    else:
        assert "time_convention" not in block["conventions"]
    assert {k: json.loads(bytes(v).decode("utf-8")) for k, v in mesh.field_data.items()} == block


@pytest.mark.parametrize("symbol, factor_text", [("nm", "1000"), ("um", "1"), ("m", "1e-6")])
def test_scalar_single_point_round_trips_in_metres(tmp_path, symbol, factor_text):
    out, saved = _saved(tmp_path, _scalar_slab(symbol, factor_text))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["field_layout"] == str(saved["field_layout"]) == LAYOUT
    assert "mesh_length_unit" not in summary and "length_unit_to_m" not in saved and "nodes" not in saved
    assert summary["field_units"]["node_coordinates"] == "m"
    assert str(saved["study_parameter"]) == ""
    field = saved["unnormalized_mode_field"]
    assert field.dtype.kind == "f" and field.shape[0] == 1
    vtu = export_fields(out / "fields.npz", tmp_path / f"{symbol}.vtu")
    mesh = meshio.read(vtu)
    _assert_mesh(mesh, saved)
    # The exported points are the mesh in metres: the slab spans the same metres in every unit.
    np.testing.assert_allclose(mesh.points[:, 1].max(), 1.2e-6, rtol=1e-12)
    assert set(mesh.point_data) == {"unnormalized_mode_field_mode_0"}
    np.testing.assert_array_equal(mesh.point_data["unnormalized_mode_field_mode_0"], field[0][:, 0])
    assert set(mesh.cell_data) == {"regions"}
    assert "effective_index" not in mesh.point_data and "effective_index" not in mesh.cell_data
    _assert_field_data(vtu, mesh, summary)


def test_lossy_scalar_modes_are_written_as_real_and_imaginary_parts(tmp_path):
    d = _scalar_slab()
    d["materials"] = {"lossy": {"refractive_index": {"n": 3.48, "k": 0.01}}}
    d["geometry"]["shapes"][0]["material"] = "lossy"
    d["physics"]["em1"]["mode_count"] = 2
    out, saved = _saved(tmp_path, d)
    field = saved["unnormalized_mode_field"]
    assert field.dtype.kind == "c" and field.shape[2] == 2
    vtu = export_fields(out / "fields.npz", tmp_path / "lossy.vtu")
    mesh = meshio.read(vtu)
    _assert_mesh(mesh, saved)
    assert set(mesh.point_data) == {f"unnormalized_mode_field_mode_{k}_{part}" for k in range(2)
                                    for part in ("real", "imag")}
    for k in range(2):
        np.testing.assert_array_equal(mesh.point_data[f"unnormalized_mode_field_mode_{k}_real"], field[0][:, k].real)
        np.testing.assert_array_equal(mesh.point_data[f"unnormalized_mode_field_mode_{k}_imag"], field[0][:, k].imag)
    assert np.any(mesh.point_data["unnormalized_mode_field_mode_0_imag"])
    _assert_field_data(vtu, mesh, json.loads((out / "summary.json").read_text(encoding="utf-8")))


def test_vector_single_point_writes_centroid_cell_data_and_nodal_longitudinal_pairs(tmp_path):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["results"] = {"plots": False}
    out, saved = _saved(tmp_path, d)
    assert str(saved["field_representation"]) == "vector-edge-nodal-v2"
    assert "unnormalized_mode_field" not in saved
    vtu = export_fields(out / "fields.npz", tmp_path / "vector.vtu")
    mesh = meshio.read(vtu)
    _assert_mesh(mesh, saved)
    electric, longitudinal = saved["unnormalized_electric_field"][0], saved["unnormalized_electric_field_z"][0]
    modes = electric.shape[1]
    assert modes == 1
    assert set(mesh.cell_data) == {"regions"} | {
        f"unnormalized_electric_field_mode_{k}_{part}" for k in range(modes) for part in ("real", "imag")}
    assert set(mesh.point_data) == {
        f"unnormalized_electric_field_z_mode_{k}_{part}" for k in range(modes) for part in ("real", "imag")}
    for k in range(modes):
        for part in ("real", "imag"):
            cell = mesh.cell_data[f"unnormalized_electric_field_mode_{k}_{part}"][0]
            assert cell.shape == (len(saved["triangles"]), 3) and cell.dtype.kind == "f"
            np.testing.assert_array_equal(cell, getattr(electric[:, k, :], part))
            np.testing.assert_array_equal(mesh.point_data[f"unnormalized_electric_field_z_mode_{k}_{part}"],
                                          getattr(longitudinal[:, k], part))
    # The saved normalization is kept: the largest centroid |E| is one.
    magnitude = np.hypot(np.linalg.norm(mesh.cell_data["unnormalized_electric_field_mode_0_real"][0], axis=1),
                         np.linalg.norm(mesh.cell_data["unnormalized_electric_field_mode_0_imag"][0], axis=1))
    np.testing.assert_allclose(magnitude.max(), 1.0)
    # Edge line integrals and n_eff stay in the NPZ only.
    for name in ("edges", "unnormalized_electric_field_line_integral", "effective_index"):
        assert name in saved and name not in mesh.point_data and name not in mesh.cell_data
    _assert_field_data(vtu, mesh, json.loads((out / "summary.json").read_text(encoding="utf-8")))


def test_pml_result_exports_the_whole_computational_domain(tmp_path):
    doc = Document.load(EXAMPLES / "pml_leaky_slab.json")
    out = run(doc, False).save(tmp_path / "pml")
    with np.load(out / "fields.npz", allow_pickle=False) as archive:
        saved = {key: archive[key] for key in archive.files}
    assert str(saved["field_layout"]) == LAYOUT
    assert str(saved["field_representation"]).startswith("pml-")
    mesh = meshio.read(export_fields(out / "fields.npz", tmp_path / "pml.vtu"))
    _assert_mesh(mesh, saved)
    # The mesh, and so the exported arrays, extend beyond the physical window into the PML.
    bounds = json.loads(str(saved["open_boundary_json"]))[0]["physical_bounds"]
    assert bounds["unit"] == "m"
    bounds = np.asarray(bounds["values"])
    nodes = mesh.points[:, :2]
    assert nodes[:, 1].min() < bounds[0][1] - 1e-15 and nodes[:, 1].max() > bounds[1][1] + 1e-15
    assert all(name.startswith(("unnormalized_electric_field_mode_", "regions")) for name in mesh.cell_data)
    assert "open_boundary_json" not in mesh.point_data and "open_boundary_json" not in mesh.cell_data


def test_vector_wavelength_sweep_collection_uses_the_wavelengths(tmp_path):
    d = copy.deepcopy(examples.VECTOR_SLAB_SWEEP)
    d["results"] = {"plots": False}
    out, saved = _saved(tmp_path, d)
    assert str(saved["study_parameter"]) == "physics.em1.vacuum_wavelength"
    points = len(saved["vacuum_wavelength"])
    assert points == 5
    with pytest.raises(ValueError, match="5 study points.*export_sweep"):
        export_fields(out / "fields.npz", tmp_path / "single.vtu")
    assert not (tmp_path / "single.vtu").exists()
    target = tmp_path / "sweep"
    pvd = export_sweep(out / "fields.npz", target)
    assert pvd == target / "fields.pvd"
    entries = _collection(pvd)
    # X3: one VTU per point; timesteps are the vacuum wavelengths in metres, round-tripped by repr.
    assert len(entries) == points
    assert [t for t, _ in entries] == saved["vacuum_wavelength"].tolist()
    assert [t for t, _ in entries] == [w * 1e-6 for w in (1.45, 1.5, 1.55, 1.6, 1.65)]   # kernel um x 1e-6
    assert [f for _, f in entries] == [f"fields_{k:05d}.vtu" for k in range(points)]
    assert sorted(p.name for p in target.iterdir()) == sorted([pvd.name] + [f for _, f in entries])
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    for k, (_, name) in enumerate(entries):
        mesh = meshio.read(target / name)
        _assert_mesh(mesh, saved)
        np.testing.assert_array_equal(mesh.cell_data["unnormalized_electric_field_mode_0_real"][0],
                                      saved["unnormalized_electric_field"][k][:, 0, :].real)
        np.testing.assert_array_equal(mesh.cell_data["unnormalized_electric_field_mode_0_imag"][0],
                                      saved["unnormalized_electric_field"][k][:, 0, :].imag)
        np.testing.assert_array_equal(mesh.point_data["unnormalized_electric_field_z_mode_0_imag"],
                                      saved["unnormalized_electric_field_z"][k][:, 0].imag)
        _assert_field_data(target / name, mesh, summary)


@pytest.mark.parametrize("parameter, values, expected", [
    ("physics.em1.vacuum_wavelength", {"unit": "um", "values": [1.55, 1.5, 1.6]}, [0.0, 1.0, 2.0]),  # indices
    ("physics.em1.boundary.left", ["pmc", "pec", "pmc"], [0.0, 1.0, 2.0]),           # not a wavelength: indices
    ("physics.em1.vacuum_wavelength", {"unit": "um", "values": [1.6, 1.55, 1.5]}, [1.6e-6, 1.55e-6, 1.5e-6]),
])
def test_scalar_sweep_collection_timesteps(tmp_path, parameter, values, expected):
    d = _scalar_slab()
    d["study"] = {"type": "sweep", "parameter": parameter, "values": values}
    out, saved = _saved(tmp_path, d)
    assert str(saved["study_parameter"]) == parameter
    assert saved["unnormalized_mode_field"].shape[0] == 3
    pvd = export_sweep(out / "fields.npz", tmp_path / "sweep", name="modes")
    entries = _collection(pvd)
    assert [t for t, _ in entries] == expected
    assert [f for _, f in entries] == [f"modes_{k:05d}.vtu" for k in range(3)]
    for k, (_, name) in enumerate(entries):
        mesh = meshio.read(tmp_path / "sweep" / name)
        _assert_mesh(mesh, saved)
        assert set(mesh.point_data) == {"unnormalized_mode_field_mode_0"}
        np.testing.assert_array_equal(mesh.point_data["unnormalized_mode_field_mode_0"],
                                      saved["unnormalized_mode_field"][k][:, 0])


def test_single_point_result_is_also_a_one_frame_collection(tmp_path):
    out, saved = _saved(tmp_path, _scalar_slab())
    entries = _collection(export_sweep(out / "fields.npz", tmp_path / "one"))
    assert entries == [(0.0, "fields_00000.vtu")]
    mesh = meshio.read(tmp_path / "one" / "fields_00000.vtu")
    np.testing.assert_array_equal(mesh.point_data["unnormalized_mode_field_mode_0"],
                                  saved["unnormalized_mode_field"][0][:, 0])


def test_legacy_result_without_a_layout_is_refused_with_no_output(tmp_path):
    out, saved = _saved(tmp_path, _scalar_slab())
    legacy = tmp_path / "legacy.npz"
    np.savez(legacy, **{k: v for k, v in saved.items() if k != "field_layout"})
    with np.load(legacy, allow_pickle=False) as archive:
        assert "field_layout" not in archive.files and "effective_index" in archive.files
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


@pytest.mark.parametrize("layout", ["em-modes2d-p1-node-centroid-v1", "em-modes2d-subspace-raw-v1"])
def test_a_retired_mode_layout_is_refused_by_name(tmp_path, layout):
    fields = tmp_path / "fields.npz"
    np.savez(fields, field_layout=np.array(layout), nodes=np.zeros((3, 2)), triangles=np.array([[0, 1, 2]]))
    for export in (lambda: export_fields(fields, tmp_path / "fields.vtu"),
                   lambda: export_sweep(fields, tmp_path / "sweep")):
        with pytest.raises(ValueError, match=re.escape(f"(layout {layout})")):
            export()
    assert not (tmp_path / "fields.vtu").exists() and not (tmp_path / "sweep").exists()


def test_subspace_layout_is_refused_by_both_exporters(tmp_path):
    d = copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP)
    d["results"] = {"plots": False}
    out, saved = _saved(tmp_path, d, "subspace")
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["field_layout"] == str(saved["field_layout"]) == SUBSPACE_LAYOUT
    assert summary["field_representation"] == "vector-subspace-edge-nodal-v2"
    assert summary["field_units"]["node_coordinates"] == "m" and "length_unit_to_m" not in saved
    assert str(saved["study_parameter"]) == "physics.em1.vacuum_wavelength"
    message = r"em-modes2d-subspace-raw-v2.*raw eigenpair columns.*deferred"
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
        "unnormalized_electric_field": (saved["unnormalized_electric_field"][:, :-1],
                                        "unnormalized_electric_field: expected shape"),
        "unnormalized_electric_field_z": (saved["unnormalized_electric_field_z"][:, :-1],
                                          "unnormalized_electric_field_z: expected shape"),
        "regions": (saved["regions"].astype(float), "regions must contain"),
        "vacuum_wavelength": (np.array([1.55e-6, 1.6e-6]), "vacuum_wavelength: expected one value per study point"),
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
    np.savez(corrupt, **dict(scalar, unnormalized_mode_field=scalar["unnormalized_mode_field"][:, :-1]))
    with pytest.raises(ValueError, match="unnormalized_mode_field: expected shape"):
        export_fields(corrupt, tmp_path / "fields.vtu")
    neither = tmp_path / "neither.npz"
    np.savez(neither, **{k: v for k, v in scalar.items() if k != "unnormalized_mode_field"})
    with pytest.raises(ValueError, match="needs the saved unnormalized_mode_field .scalar. or "
                                         "unnormalized_electric_field"):
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
