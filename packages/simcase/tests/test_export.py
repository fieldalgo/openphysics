# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""VTU and ParaView time-series export of saved fields through meshio (simcase[export])."""

from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from simcase import Document, run
from simcase.export import export_fields, export_time_series

meshio = pytest.importorskip("meshio", reason="install the export extra: pip install 'simcase[export]'")
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _saved(tmp_path, name):
    result = run(Document.load(EXAMPLES / name), False)
    out = result.save(tmp_path / name.removesuffix(".json"))
    return out / "fields.npz"


def test_steady_heat_vtu_round_trip(tmp_path):
    fields = _saved(tmp_path, "thermal_slab.json")
    out = export_fields(fields, tmp_path / "slab.vtu")
    with np.load(fields) as saved:
        mesh = meshio.read(out)
        np.testing.assert_array_equal(mesh.points[:, :2], saved["nodes_m"])
        np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
        np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
        np.testing.assert_array_equal(mesh.point_data["temperature_k"], saved["temperature_k"])
        flux = mesh.cell_data["heat_flux_w_m2"][0]
        np.testing.assert_array_equal(flux[:, :2], saved["heat_flux_w_m2"])
        np.testing.assert_array_equal(flux[:, 2], 0.0)
    # Independent structural check of the VTK XML header.
    piece = ET.parse(out).getroot().find(".//Piece")
    assert int(piece.get("NumberOfPoints")) == len(mesh.points)
    assert int(piece.get("NumberOfCells")) == len(mesh.cells_dict["triangle"])


def test_transient_heat_exports_the_selected_time(tmp_path):
    fields = _saved(tmp_path, "transient_thermal_uniform.json")
    with np.load(fields) as saved:
        times = len(saved["time_s"])
        for index in (0, times - 1):
            mesh = meshio.read(export_fields(fields, tmp_path / f"t{index}.vtu", time_index=index))
            np.testing.assert_array_equal(mesh.point_data["temperature_k"], saved["temperature_k"][index])
            np.testing.assert_array_equal(mesh.cell_data["heat_flux_w_m2"][0][:, :2],
                                          saved["heat_flux_w_m2"][index])
            # Reaction starts at the second stored time.
            assert ("reaction_w_per_m" in mesh.point_data) is (index > 0)
        with pytest.raises(IndexError):
            export_fields(fields, tmp_path / "bad.vtu", time_index=times)


def test_cavity_exports_each_mode_on_tetrahedra(tmp_path):
    fields = _saved(tmp_path, "cavity_box.json")
    mesh = meshio.read(export_fields(fields, tmp_path / "cavity.vtu"))
    with np.load(fields) as saved:
        np.testing.assert_array_equal(mesh.points, saved["nodes"])
        np.testing.assert_array_equal(mesh.cells_dict["tetra"], saved["tetrahedra"])
        for k, field in enumerate(saved["electric_field"]):
            np.testing.assert_array_equal(mesh.cell_data[f"electric_field_mode_{k}"][0], field)


def test_export_refuses_overwrite_and_unknown_layouts(tmp_path):
    fields = _saved(tmp_path, "thermal_slab.json")
    target = export_fields(fields, tmp_path / "once.vtu")
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        export_fields(fields, target)
    assert target.read_bytes() == before
    with pytest.raises(ValueError, match="must end in .vtu"):
        export_fields(fields, tmp_path / "x.xdmf")
    other = tmp_path / "other.npz"
    np.savez(other, field_layout="unknown-v1")
    with pytest.raises(ValueError, match="unsupported field layout"):
        export_fields(other, tmp_path / "other.vtu")


def _collection(pvd):
    """Parse a .pvd with the standard library: (timestep, file) per DataSet."""
    root = ET.parse(pvd).getroot()
    assert root.tag == "VTKFile" and root.get("type") == "Collection"
    return [(float(d.get("timestep")), d.get("file")) for d in root.iter("DataSet")]


def test_transient_time_series_matches_every_stored_time(tmp_path):
    fields = _saved(tmp_path, "transient_thermal_uniform.json")
    out = tmp_path / "series"
    pvd = export_time_series(fields, out)
    assert pvd == out / "fields.pvd"
    entries = _collection(pvd)
    with np.load(fields) as saved:
        times = saved["time_s"]
        assert len(times) >= 3
        # repr-written timesteps round-trip exactly; names are relative and ordered.
        assert [t for t, _ in entries] == times.tolist()
        assert [f for _, f in entries] == [f"fields_{k:05d}.vtu" for k in range(len(times))]
        assert sorted(p.name for p in out.iterdir()) == sorted([pvd.name] + [f for _, f in entries])
        for k, (_, name) in enumerate(entries):
            mesh = meshio.read(out / name)
            np.testing.assert_array_equal(mesh.points[:, :2], saved["nodes_m"])
            np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
            np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
            np.testing.assert_array_equal(mesh.point_data["temperature_k"], saved["temperature_k"][k])
            np.testing.assert_array_equal(mesh.point_data["source_load_w_per_m"],
                                          saved["source_load_w_per_m"][k])
            for late in ("reaction_w_per_m", "residual_w_per_m", "storage_rate_w_per_m"):
                # These histories start at the second stored time.
                if k == 0:
                    assert late not in mesh.point_data
                else:
                    np.testing.assert_array_equal(mesh.point_data[late], saved[late][k - 1])
            flux = mesh.cell_data["heat_flux_w_m2"][0]
            np.testing.assert_array_equal(flux[:, :2], saved["heat_flux_w_m2"][k])
            np.testing.assert_array_equal(flux[:, 2], 0.0)


def test_time_series_accepts_an_empty_directory_and_a_custom_name(tmp_path):
    fields = _saved(tmp_path, "transient_thermal_uniform.json")
    out = tmp_path / "empty"
    out.mkdir()
    pvd = export_time_series(fields, out, name="heat")
    assert pvd.name == "heat.pvd"
    assert all("/" not in f and "\\" not in f and f.startswith("heat_") for _, f in _collection(pvd))


def test_time_series_refuses_existing_content_and_bad_inputs(tmp_path):
    transient = _saved(tmp_path, "transient_thermal_uniform.json")
    steady = _saved(tmp_path, "thermal_slab.json")
    full = tmp_path / "full"
    full.mkdir()
    (full / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_time_series(transient, full)
    assert [p.name for p in full.iterdir()] == ["keep.txt"]
    a_file = tmp_path / "file.pvd"
    a_file.write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_time_series(transient, a_file)
    assert a_file.read_text(encoding="utf-8") == "x"
    # A second export into the same directory is refused, leaving the first intact.
    once = tmp_path / "once"
    pvd = export_time_series(transient, once)
    before = {p.name: p.read_bytes() for p in once.iterdir()}
    with pytest.raises(FileExistsError):
        export_time_series(transient, once)
    assert {p.name: p.read_bytes() for p in once.iterdir()} == before
    assert pvd.exists()
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(steady, tmp_path / "steady")
    assert not (tmp_path / "steady").exists()
    for bad in ("", "a/b", "a\\b", "..", "c:x"):
        with pytest.raises(ValueError, match="plain file stem"):
            export_time_series(transient, tmp_path / "named", name=bad)
    assert not (tmp_path / "named").exists()


def test_time_series_removes_partial_output_on_failure(tmp_path, monkeypatch):
    fields = _saved(tmp_path, "transient_thermal_uniform.json")
    calls = []
    real_write = meshio.vtu.write

    def failing_write(path, mesh, **kwargs):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("simulated write failure")
        return real_write(path, mesh, **kwargs)

    monkeypatch.setattr(meshio.vtu, "write", failing_write)
    out = tmp_path / "partial"
    with pytest.raises(OSError, match="simulated"):
        export_time_series(fields, out)
    assert not out.exists()
    kept = tmp_path / "kept"
    kept.mkdir()
    calls.clear()
    with pytest.raises(OSError, match="simulated"):
        export_time_series(fields, kept)
    assert kept.is_dir() and not any(kept.iterdir())
