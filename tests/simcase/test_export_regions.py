# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Region VTU/PVD consumers, also run against installed wheels on three OSes."""
import copy
from fractions import Fraction
import json
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from simcase import Document, run
from simcase.export import export_fields, export_time_series

meshio = pytest.importorskip("meshio", reason="install simcase[export]")


def _document(transient, unit="mm", scale="1"):
    def length(value):
        return float(Fraction(str(value)) * Fraction(scale))
    data = {
        "openphysics": "0.2", "name": "region export",
        "units": {"length": unit, "temperature": "K"},
        "geometry": {
            "domain": dict(zip(("xmin", "xmax", "ymin", "ymax"), map(length, (2, 6, -1, 1)))),
            "background": {"material": "same"},
            "shapes": [{"name": "plate", "type": "rect", "material": "same",
                        **dict(zip(("x", "y", "w", "h"), map(length, (2, -1, 2, 2))))}]},
        "materials": {"same": {"conductivity_w_mk": 2.}},
        "physics": {"heat": {"type": "thermal.steady2d",
                              "heat_source_w_m3": {"plate": 1e6},
                              "dirichlet_temperature_k": {"left": 300.},
                              "outward_flux_w_m2": {"bottom": -40.},
                              "convection": {"right": {"h_w_m2k": 25., "ambient_temperature_k": 290.}}}},
        "mesh": {"size": length(1)}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False}}
    if transient:
        data["units"]["time"] = "s"
        data["materials"]["same"]["volumetric_heat_capacity_j_m3k"] = 2e6
        p = data["physics"]["heat"]
        p["type"] = "thermal.transient2d"
        p["initial_temperature_k"] = 300.
        p.pop("outward_flux_w_m2")
        p.pop("convection")
        data["study"] = {"type": "transient", "time_s": [0., .03, .11]}
    return data


def _assert_vtu(path, saved, index=None):
    mesh = meshio.read(path)
    np.testing.assert_array_equal(mesh.points[:, :2], saved["nodes_m"])
    np.testing.assert_array_equal(mesh.points[:, 2], 0.)
    np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
    regions = mesh.cell_data["triangle_regions"][0]
    assert regions.dtype.kind in "iu"
    np.testing.assert_array_equal(regions, saved["triangle_regions"])
    flux = saved["heat_flux_w_m2"] if index is None else saved["heat_flux_w_m2"][index]
    np.testing.assert_array_equal(mesh.cell_data["heat_flux_w_m2"][0][:, :2], flux)
    np.testing.assert_array_equal(mesh.cell_data["heat_flux_w_m2"][0][:, 2], 0.)
    names = {"temperature_k", "reaction_w_per_m", "residual_w_per_m"}
    if index is None:
        names.update(("load_w_per_m", "prescribed_outward_load_w_per_m", "ambient_load_w_per_m",
                      "convective_outward_w_per_m", "system_rhs_w_per_m"))
    else:
        names.update(("source_load_w_per_m", "storage_rate_w_per_m"))
    late = {"reaction_w_per_m", "residual_w_per_m", "storage_rate_w_per_m"}
    expected = names - late if index == 0 else names
    assert mesh.point_data.keys() == expected
    for name in expected:
        value = saved[name]
        if index is not None:
            value = value[index - 1 if name in late else index]
        np.testing.assert_array_equal(mesh.point_data[name], value, err_msg=name)
    return {"points": mesh.points, "triangles": mesh.cells_dict["triangle"],
            **mesh.point_data, **{key: value[0] for key, value in mesh.cell_data.items()}}


@pytest.mark.parametrize("transient", [False, True])
def test_region_exports_preserve_saved_fields_and_unit_equivalence(tmp_path, transient):
    reference = None
    for n, (unit, scale) in enumerate((("mm", "1"), ("m", ".001"), ("um", "1000"),
                                        ("nm", "1000000"), ({"in_m": 2e-5}, "50"))):
        data = _document(transient, unit, scale)
        original = copy.deepcopy(data)
        out = run(Document.from_dict(data), verbose=False).save(tmp_path / str(n))
        fields = out / "fields.npz"
        before = fields.read_bytes()
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        assert {row["material"] for row in summary["regions"].values()} == {"same"}
        with np.load(fields, allow_pickle=False) as saved:
            assert len(np.unique(saved["triangle_regions"])) == 2  # region IDs, not material IDs
            snapshots = []
            if transient:
                pvd = export_time_series(fields, out / "series", name="heat & regions")
                entries = list(ET.parse(pvd).getroot().iter("DataSet"))
                assert [float(e.attrib["timestep"]) for e in entries] == saved["time_s"].tolist()
                for index, entry in enumerate(entries):
                    assert entry.attrib["file"] == f"heat & regions_{index:05d}.vtu"
                    snapshots.append(_assert_vtu(pvd.parent / entry.attrib["file"], saved, index))
                for index in (0, 1, -1):
                    actual = _assert_vtu(export_fields(fields, out / f"at{index}.vtu", time_index=index),
                                         saved, index % len(entries))
                    for key in actual:
                        np.testing.assert_array_equal(actual[key], snapshots[index][key])
                _assert_vtu(export_fields(fields, out / "default.vtu"), saved, len(entries) - 1)
                with pytest.raises(IndexError):
                    export_fields(fields, out / "bad.vtu", time_index=len(entries))
                assert not (out / "bad.vtu").exists()
            else:
                snapshots.append(_assert_vtu(export_fields(fields, out / "steady.vtu"), saved))
                with pytest.raises(ValueError, match="time series export needs layout"):
                    export_time_series(fields, out / "invalid-series")
                assert not (out / "invalid-series").exists()
            if reference is None:
                reference = snapshots
            else:
                for expected, actual in zip(reference, snapshots, strict=True):
                    assert expected.keys() == actual.keys()
                    for key in expected:
                        np.testing.assert_array_equal(expected[key], actual[key], err_msg=key)
        assert data == original and fields.read_bytes() == before


@pytest.mark.parametrize("bad", ["missing", "float", "negative", "short", "matrix", "bool"])
@pytest.mark.parametrize("series", [False, True])
def test_bad_region_ids_fail_before_creating_output(tmp_path, bad, series):
    out = run(Document.from_dict(_document(True)), verbose=False).save(tmp_path / "saved")
    with np.load(out / "fields.npz", allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    ids = data["triangle_regions"]
    if bad == "missing":
        del data["triangle_regions"]
    else:
        data["triangle_regions"] = {"float": ids.astype(float), "negative": -np.ones_like(ids),
                                    "short": ids[:-1], "matrix": ids[:, None],
                                    "bool": ids.astype(bool)}[bad]
    corrupt = tmp_path / "bad.npz"
    np.savez(corrupt, **data)
    target = tmp_path / ("series" if series else "field.vtu")
    with pytest.raises(ValueError, match="triangle_regions"):
        (export_time_series if series else export_fields)(corrupt, target)
    assert not target.exists()


def test_region_exports_preserve_targets_and_clean_partial_series(tmp_path, monkeypatch):
    out = run(Document.from_dict(_document(True)), verbose=False).save(tmp_path / "saved")
    fields = out / "fields.npz"
    target = export_fields(fields, tmp_path / "view.vtu")
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        export_fields(fields, target)
    assert target.read_bytes() == before
    folder = tmp_path / "existing"
    pvd = export_time_series(fields, folder)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    with pytest.raises(FileExistsError):
        export_time_series(fields, folder)
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    assert pvd.exists()
    real_write = meshio.vtu.write
    calls = []
    def fail_second(path, mesh, **kwargs):
        calls.append(path)
        real_write(path, mesh, **kwargs)
        if len(calls) == 2:
            raise OSError("partial write")
    monkeypatch.setattr(meshio.vtu, "write", fail_second)
    for existing in (False, True):
        partial = tmp_path / f"partial-{existing}"
        if existing:
            partial.mkdir()
        calls.clear()
        with pytest.raises(OSError, match="partial write"):
            export_time_series(fields, partial)
        assert partial.exists() == existing
        if existing:
            assert not any(partial.iterdir())
