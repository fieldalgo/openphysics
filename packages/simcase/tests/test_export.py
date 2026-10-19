# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""VTU export of saved fields through meshio (simcase[export])."""

from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from simcase import Document, run
from simcase.export import export_fields

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
