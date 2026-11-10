# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""VTU and ParaView time-series export of saved fields through meshio (simcase[export])."""

from pathlib import Path
import json
import xml.etree.ElementTree as ET

import copy

import numpy as np
import pytest

from simcase import Document, examples, run
from simcase.export import read_field_data, export_fields, export_time_series

meshio = pytest.importorskip("meshio", reason="install the export extra: pip install 'simcase[export]'")
EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "simcase"


def _saved(tmp_path, name):
    result = run(Document.load(EXAMPLES / name), False)
    out = result.save(tmp_path / name.removesuffix(".json"))
    return out / "fields.npz"


def test_steady_heat_vtu_round_trip(tmp_path):
    fields = _saved(tmp_path, "thermal_slab.json")
    out = export_fields(fields, tmp_path / "slab.vtu")
    with np.load(fields) as saved:
        mesh = meshio.read(out)
        np.testing.assert_array_equal(mesh.points[:, :2], saved["node_coordinates"])
        np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
        np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
        np.testing.assert_array_equal(mesh.point_data["temperature"], saved["temperature"])
        flux = mesh.cell_data["heat_flux"][0]
        np.testing.assert_array_equal(flux[:, :2], saved["heat_flux"])
        np.testing.assert_array_equal(flux[:, 2], 0.0)
        field_units = json.loads(str(saved["metadata_json"]))["field_units"]
    # Independent structural check of the VTK XML header.
    piece = ET.parse(out).getroot().find(".//Piece")
    assert int(piece.get("NumberOfPoints")) == len(mesh.points)
    assert int(piece.get("NumberOfCells")) == len(mesh.cells_dict["triangle"])
    # P2-18: the FieldData unit block, UInt8 UTF-8 JSON, read by xml.etree and by meshio alike
    names = set(mesh.point_data) | set(mesh.cell_data)
    block = read_field_data(out)
    assert block["units"] == {name: field_units[name] for name in names}
    assert block["conventions"]["sign"]["heat_flux"].startswith("q = -k grad T")
    assert set(block["conventions"]["sign"]) == {"heat_flux", "generated_heat_rate_per_depth",
                                                 "reaction_heat_rate_per_depth"}
    assert {k: json.loads(bytes(v).decode("utf-8")) for k, v in mesh.field_data.items()} == block
    assert all(a.get("type") == "UInt8" for a in ET.parse(out).getroot().iter("DataArray")
               if a.get("Name") in ("units", "conventions"))
    assert b'type="String"' not in out.read_bytes()


def test_a_heat_layout_saved_before_the_units_batch_is_refused_by_name(tmp_path):
    fields = tmp_path / "fields.npz"
    np.savez(fields, field_layout=np.array("thermal2d-p1-node-cell-v1"))
    with pytest.raises(ValueError, match=r"saved before the units and naming batch \(layout thermal2d-p1-node-cell-v1\)"):
        export_fields(fields, tmp_path / "old.vtu")


def test_transient_heat_exports_the_selected_time(tmp_path):
    fields = _saved(tmp_path, "transient_thermal_uniform.json")
    with np.load(fields) as saved:
        times = len(saved["time"])
        for index in (0, times - 1):
            mesh = meshio.read(export_fields(fields, tmp_path / f"t{index}.vtu", time_index=index))
            np.testing.assert_array_equal(mesh.point_data["temperature"], saved["temperature"][index])
            np.testing.assert_array_equal(mesh.cell_data["heat_flux"][0][:, :2],
                                          saved["heat_flux"][index])
            # Reaction starts at the second stored time.
            assert ("reaction_heat_rate_per_depth" in mesh.point_data) is (index > 0)
        with pytest.raises(IndexError):
            export_fields(fields, tmp_path / "bad.vtu", time_index=times)


def _cavity_field_data(vtu, mesh, summary):
    """P2-18: each exported cavity array's FieldData unit is its saved array's; complex parts name
    the time convention."""
    block = read_field_data(vtu)
    exported = list(mesh.cell_data)
    base = {n: n.split("_mode_")[0].removesuffix("_real").removesuffix("_imag") for n in exported}
    assert block["units"] == {n: summary["field_units"][base[n]] for n in exported}
    if any(n.endswith(("_real", "_imag")) for n in exported):
        assert block["conventions"]["time_convention"] == "exp(-i omega t)" == summary["time_convention"]
    else:
        assert "time_convention" not in block["conventions"]
    assert {k: json.loads(bytes(v).decode("utf-8")) for k, v in mesh.field_data.items()} == block


def test_cavity_exports_each_mode_on_tetrahedra(tmp_path):
    fields = _saved(tmp_path, "cavity_box.json")
    vtu = export_fields(fields, tmp_path / "cavity.vtu")
    mesh = meshio.read(vtu)
    with np.load(fields) as saved:
        assert str(saved["field_layout"]) == "cavity3d-edge-v2"
        np.testing.assert_array_equal(mesh.points, saved["node_coordinates"])
        np.testing.assert_array_equal(mesh.cells_dict["tetra"], saved["tetrahedra"])
        for k, field in enumerate(saved["mass_normalized_electric_field"]):
            np.testing.assert_array_equal(mesh.cell_data[f"mass_normalized_electric_field_mode_{k}"][0], field)
        assert len(mesh.cell_data) == len(saved["mass_normalized_electric_field"])
    _cavity_field_data(vtu, mesh, json.loads((fields.parent / "summary.json").read_text(encoding="utf-8")))


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
        times = saved["time"]
        assert len(times) >= 3
        # repr-written timesteps (s) round-trip exactly; names are relative and ordered.
        assert [t for t, _ in entries] == times.tolist()
        assert [f for _, f in entries] == [f"fields_{k:05d}.vtu" for k in range(len(times))]
        assert sorted(p.name for p in out.iterdir()) == sorted([pvd.name] + [f for _, f in entries])
        for k, (_, name) in enumerate(entries):
            mesh = meshio.read(out / name)
            np.testing.assert_array_equal(mesh.points[:, :2], saved["node_coordinates"])
            np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
            np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
            np.testing.assert_array_equal(mesh.point_data["temperature"], saved["temperature"][k])
            np.testing.assert_array_equal(mesh.point_data["generated_heat_rate_per_depth"],
                                          saved["generated_heat_rate_per_depth"][k])
            for late in ("reaction_heat_rate_per_depth", "residual_heat_rate_per_depth",
                         "heat_storage_rate_per_depth"):
                # These histories start at the second stored time.
                if k == 0:
                    assert late not in mesh.point_data
                else:
                    np.testing.assert_array_equal(mesh.point_data[late], saved[late][k - 1])
            flux = mesh.cell_data["heat_flux"][0]
            np.testing.assert_array_equal(flux[:, :2], saved["heat_flux"][k])
            np.testing.assert_array_equal(flux[:, 2], 0.0)
            # each VTU of the series carries the units of its own arrays
            assert read_field_data(out / name)["units"] == {
                n: json.loads(str(saved["metadata_json"]))["field_units"][n]
                for n in (*mesh.point_data, *mesh.cell_data)}


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


def test_time_series_keeps_a_collection_it_did_not_create(tmp_path, monkeypatch):
    fields = _saved(tmp_path, "transient_thermal_uniform.json")
    out = tmp_path / "race"
    real_write = meshio.vtu.write

    def write_then_race(path, mesh, **kwargs):
        real_write(path, mesh, **kwargs)
        # Another writer creates the collection before this call reaches it.
        (out / "fields.pvd").write_text("other", encoding="utf-8")

    monkeypatch.setattr(meshio.vtu, "write", write_then_race)
    with pytest.raises(FileExistsError):
        export_time_series(fields, out)
    assert [p.name for p in out.iterdir()] == ["fields.pvd"]
    assert (out / "fields.pvd").read_text(encoding="utf-8") == "other"


_NOT_EXPORTED = ("nodes_m", "triangles", "field_layout", "result_format", "mesh_length_unit",
                 "metadata_json", "dirichlet_node_ids", "dirichlet_temperature_k",
                 "node_coordinates", "prescribed_node_ids", "prescribed_temperature",
                 "electric_prescribed_node_ids", "prescribed_electric_potential",
                 "thermal_prescribed_node_ids")


def _assert_every_field_array_exported(fields, mesh):
    """Each saved array that is not mesh, metadata or a Dirichlet list is in the VTU, unchanged."""
    with np.load(fields) as saved:
        exported = set()
        for name in saved.files:
            if name in _NOT_EXPORTED:
                assert name not in mesh.point_data and name not in mesh.cell_data
                continue
            array = saved[name]
            nodes = saved["node_coordinates"] if "node_coordinates" in saved.files else saved["nodes_m"]
            if array.shape == (len(nodes),):
                np.testing.assert_array_equal(mesh.point_data[name], array)
            elif array.shape == (len(saved["triangles"]),):
                np.testing.assert_array_equal(mesh.cell_data[name][0], array)
            else:
                assert array.shape == (len(saved["triangles"]), 2), name
                vector = mesh.cell_data[name][0]
                np.testing.assert_array_equal(vector[:, :2], array)
                np.testing.assert_array_equal(vector[:, 2], 0.0)
            exported.add(name)
        assert exported == set(mesh.point_data) | set(mesh.cell_data)
        np.testing.assert_array_equal(mesh.points[:, :2], nodes)
        np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
    return exported


def test_steady_boundary_heat_exports_its_boundary_loads(tmp_path):
    fields = _saved(tmp_path, "thermal_boundary.json")
    with np.load(fields) as saved:
        assert str(saved["field_layout"]) == "thermal2d-p1-node-cell-boundary-v3"
    mesh = meshio.read(export_fields(fields, tmp_path / "boundary.vtu"))
    exported = _assert_every_field_array_exported(fields, mesh)
    assert {"temperature", "outward_prescribed_heat_rate_per_depth", "ambient_convective_heat_rate_per_depth",
            "outward_convective_heat_rate_per_depth", "applied_heat_rate_per_depth"} <= set(mesh.point_data)
    assert set(mesh.cell_data) == {"heat_flux"}
    assert exported == set(mesh.point_data) | {"heat_flux"}
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")


@pytest.mark.parametrize("example, heat, evaluated", [
    ("electric_rectangle.json", False, False),
    ("joule_rectangle.json", True, False),
    ("joule_temperature.json", True, True)])
def test_electric_and_joule_results_export_every_field_array(tmp_path, example, heat, evaluated):
    fields = _saved(tmp_path, example)
    with np.load(fields) as saved:
        assert str(saved["field_layout"]) == "electric-joule2d-p1-v2"
        field_units = json.loads(str(saved["metadata_json"]))["field_units"]
    vtu = export_fields(fields, tmp_path / "electric.vtu")
    mesh = meshio.read(vtu)
    exported = _assert_every_field_array_exported(fields, mesh)
    assert {"electric_potential", "joule_power_per_depth", "reaction_current_per_depth",
            "outward_prescribed_current_per_depth", "residual_current_per_depth"} <= set(mesh.point_data)
    assert {"electric_field", "current_density", "electrical_conductivity",
            "joule_power_density"} <= set(mesh.cell_data)
    assert ("temperature" in mesh.point_data) is heat
    assert ("applied_heat_rate_per_depth" in mesh.point_data) is heat
    assert ("heat_flux" in mesh.cell_data) is heat
    assert ("evaluation_temperature" in mesh.point_data) is evaluated
    # P2-18: the FieldData unit block equals field_units for every exported array
    block = read_field_data(vtu)
    assert block["units"] == {name: field_units[name] for name in exported}
    assert block["conventions"]["sign"]["reaction_current_per_depth"]
    assert 'type="String"' not in vtu.read_text(encoding="utf-8", errors="replace")
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")


def test_electric_export_checks_its_arrays_and_still_refuses_other_layouts(tmp_path):
    nodes = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    triangles = np.array([[0, 1, 2]])
    base = dict(field_layout="electric-joule2d-p1-v2", node_coordinates=nodes, triangles=triangles)
    missing = tmp_path / "missing.npz"
    np.savez(missing, **base, electric_field=np.zeros((1, 2)))
    with pytest.raises(ValueError, match="needs the saved electric_potential"):
        export_fields(missing, tmp_path / "missing.vtu")
    wrong = tmp_path / "wrong.npz"
    np.savez(wrong, **base, electric_potential=np.zeros(3), current_density=np.zeros((2, 2)))
    with pytest.raises(ValueError, match="current_density: expected one 2D vector per triangle"):
        export_fields(wrong, tmp_path / "wrong.vtu")
    retired = tmp_path / "retired.npz"
    np.savez(retired, field_layout="electric-joule2d-p1-v1", nodes_m=nodes, triangles=triangles,
             potential_v=np.zeros(3))
    with pytest.raises(ValueError, match=r"saved before the units and naming batch \(layout electric-joule2d-p1-v1\)"):
        export_fields(retired, tmp_path / "retired.vtu")
    assert not any(tmp_path.glob("*.vtu"))
    other = tmp_path / "other.npz"
    np.savez(other, field_layout="cavity3d-edge-complex-v3")
    with pytest.raises(ValueError, match="unsupported field layout 'cavity3d-edge-complex-v3'"):
        export_fields(other, tmp_path / "other.vtu")
    # the cavity layouts of format 0.2 are refused by name (units batch C9)
    for layout in ("cavity3d-edge-v1", "cavity3d-edge-complex-v1"):
        retired = tmp_path / f"{layout}.npz"
        np.savez(retired, field_layout=layout, nodes=np.zeros((4, 3)), tetrahedra=np.array([[0, 1, 2, 3]]))
        with pytest.raises(ValueError, match=rf"saved before the units and naming batch \(layout {layout}\)"):
            export_fields(retired, tmp_path / "retired.vtu")
    assert not any(tmp_path.glob("*.vtu"))


def _field_data_matches(vtu, summary, exported):
    """The FieldData units are the saved field_units of each exported array (a split component
    takes its array's unit), and the conventions carry the sign texts."""
    from simcase.export import read_field_data
    block = read_field_data(vtu)
    assert set(block["units"]) == exported
    return block


def test_mechanics_result_exports_nodal_vectors_and_named_components(tmp_path):
    fields = _saved(tmp_path, "elastic_plate.json")
    vtu = export_fields(fields, tmp_path / "plate.vtu")
    mesh = meshio.read(vtu)
    with np.load(fields) as saved:
        assert str(saved["field_layout"]) == "mechanics2d-p1-v2"
        summary = json.loads(str(saved["metadata_json"]))
        np.testing.assert_array_equal(mesh.points[:, :2], saved["node_coordinates"])
        np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
        np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
        nodal = {"displacement", "applied_force_per_depth", "reaction_force_per_depth", "residual_force_per_depth"}
        assert set(mesh.point_data) == nodal
        for name in nodal:
            np.testing.assert_array_equal(mesh.point_data[name][:, :2], saved[name])
            np.testing.assert_array_equal(mesh.point_data[name][:, 2], 0.0)
        components = {"strain": ("strain_xx", "strain_yy", "engineering_shear_strain_xy"),
                      "stress": ("stress_xx", "stress_yy", "stress_xy")}
        assert {name: tuple(names) for name, names in summary["field_components"].items()
                if name in components} == components
        assert set(mesh.cell_data) == {c for names in components.values() for c in names}
        for name, names in components.items():
            for k, component in enumerate(names):
                np.testing.assert_array_equal(mesh.cell_data[component][0], saved[name][:, k])
        for name in ("prescribed_node_ids", "prescribed_components", "prescribed_displacement", "metadata_json"):
            assert name in saved.files and name not in mesh.point_data and name not in mesh.cell_data
    block = _field_data_matches(vtu, summary, set(mesh.point_data) | set(mesh.cell_data))
    for name in nodal:
        assert block["units"][name] == summary["field_units"][name]
    for name, names in components.items():
        assert all(block["units"][c] == summary["field_units"][name] for c in names)
    assert block["conventions"]["sign"]["reaction_force_per_depth"]
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")


def test_thermoelastic_result_exports_heat_and_mechanics_arrays(tmp_path):
    fields = _saved(tmp_path, "thermoelastic_bar.json")
    vtu = export_fields(fields, tmp_path / "bar.vtu")
    mesh = meshio.read(vtu)
    with np.load(fields) as saved:
        assert str(saved["field_layout"]) == "thermoelastic2d-p1-v2"
        summary = json.loads(str(saved["metadata_json"]))
        np.testing.assert_array_equal(mesh.points[:, :2], saved["node_coordinates"])
        scalars = {"temperature", "generated_heat_rate_per_depth", "reaction_heat_rate_per_depth",
                   "residual_heat_rate_per_depth", "outward_prescribed_heat_rate_per_depth",
                   "ambient_convective_heat_rate_per_depth", "outward_convective_heat_rate_per_depth",
                   "applied_heat_rate_per_depth"}
        vectors = {"displacement", "applied_force_per_depth", "thermal_equivalent_force_per_depth",
                   "applied_body_force_per_depth", "applied_traction_force_per_depth", "reaction_force_per_depth",
                   "residual_force_per_depth"}
        assert set(mesh.point_data) == scalars | vectors
        for name in scalars:
            np.testing.assert_array_equal(mesh.point_data[name], saved[name])
        for name in vectors:
            np.testing.assert_array_equal(mesh.point_data[name][:, :2], saved[name])
            np.testing.assert_array_equal(mesh.point_data[name][:, 2], 0.0)
        components = {"strain": ("strain_xx", "strain_yy", "engineering_shear_strain_xy"),
                      "thermal_strain": ("thermal_strain_xx", "thermal_strain_yy",
                                         "engineering_shear_thermal_strain_xy"),
                      "elastic_strain": ("elastic_strain_xx", "elastic_strain_yy",
                                         "engineering_shear_elastic_strain_xy"),
                      "stress": ("stress_xx", "stress_yy", "stress_xy")}
        assert {name: tuple(names) for name, names in summary["field_components"].items()
                if name in components} == components
        expected_cells = {c for names in components.values() for c in names} | {"heat_flux", "stress_zz", "strain_zz"}
        assert set(mesh.cell_data) == expected_cells
        for name, names in components.items():
            for k, component in enumerate(names):
                np.testing.assert_array_equal(mesh.cell_data[component][0], saved[name][:, k])
        np.testing.assert_array_equal(mesh.cell_data["heat_flux"][0][:, :2], saved["heat_flux"])
        np.testing.assert_array_equal(mesh.cell_data["stress_zz"][0], saved["stress_zz"])
        np.testing.assert_array_equal(mesh.cell_data["strain_zz"][0], saved["strain_zz"])
        for name in ("thermal_prescribed_node_ids", "prescribed_temperature", "prescribed_node_ids", "metadata_json"):
            assert name in saved.files and name not in mesh.point_data and name not in mesh.cell_data
    block = _field_data_matches(vtu, summary, set(mesh.point_data) | set(mesh.cell_data))
    for name in (*scalars, *vectors, "heat_flux", "stress_zz", "strain_zz"):
        assert block["units"][name] == summary["field_units"][name], name
    for name, names in components.items():
        assert all(block["units"][c] == summary["field_units"][name] for c in names)
    assert block["conventions"]["sign"]["heat_flux"]
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")


def test_mechanics_export_checks_its_arrays(tmp_path):
    nodes = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    base = dict(field_layout="mechanics2d-p1-v2", node_coordinates=nodes, triangles=np.array([[0, 1, 2]]))
    missing = tmp_path / "missing.npz"
    np.savez(missing, **base, stress=np.zeros((1, 3)))
    with pytest.raises(ValueError, match="needs the saved displacement array"):
        export_fields(missing, tmp_path / "missing.vtu")
    wrong = tmp_path / "wrong.npz"
    np.savez(wrong, **base, displacement=np.zeros((3, 2)), strain=np.zeros((1, 2)))
    with pytest.raises(ValueError, match="strain: expected three components per triangle"):
        export_fields(wrong, tmp_path / "wrong.vtu")
    flat = tmp_path / "flat.npz"
    np.savez(flat, **base, displacement=np.zeros(3))
    with pytest.raises(ValueError, match="displacement: expected one 2D vector per node"):
        export_fields(flat, tmp_path / "flat.vtu")
    # a result saved before the units batch is refused by its layout, and a region result is not exported
    for layout in ("mechanics2d-p1-v1", "thermoelastic2d-p1-v1"):
        retired = tmp_path / f"{layout}.npz"
        np.savez(retired, field_layout=layout, nodes_m=nodes, triangles=np.array([[0, 1, 2]]))
        with pytest.raises(ValueError, match=rf"saved before the units and naming batch \(layout {layout}\)"):
            export_fields(retired, tmp_path / "retired.vtu")
    for layout in ("mechanics2d-p1-regions-v2", "thermoelastic2d-p1-regions-v2"):
        region = tmp_path / f"{layout}.npz"
        np.savez(region, field_layout=layout, node_coordinates=nodes, triangles=np.array([[0, 1, 2]]))
        with pytest.raises(ValueError, match=f"unsupported field layout '{layout}'"):
            export_fields(region, tmp_path / "region.vtu")
    assert not any(tmp_path.glob("*.vtu"))


def _saved_lossy_cavity(tmp_path, n=4):
    data = copy.deepcopy(examples.CAVITY_LOSSY_SLAB)
    data["mesh"]["subdivision_count"] = [n, n, n]
    data["physics"]["em1"]["mode_count"] = 2
    data["results"] = {"save_fields": True, "plots": False}
    out = run(Document.from_dict(data), False).save(tmp_path / "lossy")
    with np.load(out / "fields.npz", allow_pickle=False) as archive:
        saved = {key: archive[key] for key in archive.files}
    return out / "fields.npz", saved


def test_complex_cavity_exports_real_and_imaginary_parts(tmp_path):
    fields, saved = _saved_lossy_cavity(tmp_path)
    assert str(saved["field_layout"]) == "cavity3d-edge-complex-v2"
    field = "mass_normalized_electric_field"
    assert saved[field].dtype.kind == "c"
    vtu = export_fields(fields, tmp_path / "lossy.vtu")
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.points, saved["node_coordinates"])
    np.testing.assert_array_equal(mesh.cells_dict["tetra"], saved["tetrahedra"])
    metadata = json.loads(str(saved["metadata_json"]))
    modes = len(saved[field])
    assert modes == metadata["returned_mode_count"] == 2
    expected = set()
    for k in range(modes):
        for part in ("real", "imag"):
            expected.add(f"{field}_mode_{k}_{part}")
            values = mesh.cell_data[f"{field}_mode_{k}_{part}"][0]
            assert values.dtype.kind == "f" and values.shape == (len(saved["tetrahedra"]), 3)
            np.testing.assert_array_equal(values, getattr(saved[field][k], part))
    for name in ("relative_permittivity", "relative_permeability"):
        for part in ("real", "imag"):
            expected.add(f"{name}_{part}")
            np.testing.assert_array_equal(mesh.cell_data[f"{name}_{part}"][0], getattr(saved[name], part))
    assert set(mesh.cell_data) == expected
    assert not mesh.point_data
    # The slab is lossy: the imaginary parts are not all zero, and loss is Im >= 0 under exp(-i omega t).
    assert any(np.any(mesh.cell_data[f"{field}_mode_{k}_imag"][0]) for k in range(modes))
    assert mesh.cell_data["relative_permittivity_imag"][0].max() == 0.04
    assert mesh.cell_data["relative_permittivity_imag"][0].min() == 0.0
    assert metadata["field_units"][field] == "1/m^(3/2)"
    assert metadata["time_convention"] == "exp(-i omega t)"
    _cavity_field_data(vtu, mesh, json.loads((fields.parent / "summary.json").read_text(encoding="utf-8")))
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")
    assert not (tmp_path / "series").exists()


def test_complex_cavity_export_checks_its_array_shapes(tmp_path):
    fields, saved = _saved_lossy_cavity(tmp_path)
    for name, value in (("mass_normalized_electric_field", saved["mass_normalized_electric_field"][:, :-1]),
                        ("relative_permittivity", saved["relative_permittivity"][:-1])):
        corrupt = tmp_path / f"{name}.npz"
        np.savez(corrupt, **dict(saved, **{name: value}))
        with pytest.raises(ValueError, match=f"{name}: expected"):
            export_fields(corrupt, tmp_path / f"{name}.vtu")
        assert not (tmp_path / f"{name}.vtu").exists()
