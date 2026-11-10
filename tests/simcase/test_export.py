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
                 "electric_dirichlet_node_ids", "dirichlet_potential_v",
                 "thermal_dirichlet_node_ids")


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
        assert str(saved["field_layout"]) == "electric-joule2d-p1-v1"
    mesh = meshio.read(export_fields(fields, tmp_path / "electric.vtu"))
    _assert_every_field_array_exported(fields, mesh)
    assert {"potential_v", "joule_load_w_per_m", "electric_reaction_a_per_m",
            "prescribed_outward_current_a_per_m", "electric_residual_a_per_m"} <= set(mesh.point_data)
    assert {"electric_field_v_m", "current_density_a_m2", "conductivity_s_m",
            "joule_heating_w_m3"} <= set(mesh.cell_data)
    assert ("temperature_k" in mesh.point_data) is heat
    assert ("thermal_system_rhs_w_per_m" in mesh.point_data) is heat
    assert ("heat_flux_w_m2" in mesh.cell_data) is heat
    assert ("evaluated_temperature_k" in mesh.point_data) is evaluated
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")


def test_electric_export_checks_its_arrays_and_still_refuses_other_layouts(tmp_path):
    nodes = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    triangles = np.array([[0, 1, 2]])
    base = dict(field_layout="electric-joule2d-p1-v1", nodes_m=nodes, triangles=triangles)
    missing = tmp_path / "missing.npz"
    np.savez(missing, **base, electric_field_v_m=np.zeros((1, 2)))
    with pytest.raises(ValueError, match="needs the saved potential_v"):
        export_fields(missing, tmp_path / "missing.vtu")
    wrong = tmp_path / "wrong.npz"
    np.savez(wrong, **base, potential_v=np.zeros(3), current_density_a_m2=np.zeros((2, 2)))
    with pytest.raises(ValueError, match="current_density_a_m2: expected one 2D vector per triangle"):
        export_fields(wrong, tmp_path / "wrong.vtu")
    assert not any(tmp_path.glob("*.vtu"))
    other = tmp_path / "other.npz"
    np.savez(other, field_layout="cavity3d-edge-complex-v2")
    with pytest.raises(ValueError, match="unsupported field layout 'cavity3d-edge-complex-v2'"):
        export_fields(other, tmp_path / "other.vtu")


def test_mechanics_result_exports_nodal_vectors_and_named_components(tmp_path):
    fields = _saved(tmp_path, "elastic_plate.json")
    mesh = meshio.read(export_fields(fields, tmp_path / "plate.vtu"))
    with np.load(fields) as saved:
        assert str(saved["field_layout"]) == "mechanics2d-p1-v1"
        np.testing.assert_array_equal(mesh.points[:, :2], saved["nodes_m"])
        np.testing.assert_array_equal(mesh.points[:, 2], 0.0)
        np.testing.assert_array_equal(mesh.cells_dict["triangle"], saved["triangles"])
        nodal = {"displacement_m", "load_n_per_m", "reaction_n_per_m", "residual_n_per_m"}
        assert set(mesh.point_data) == nodal
        for name in nodal:
            np.testing.assert_array_equal(mesh.point_data[name][:, :2], saved[name])
            np.testing.assert_array_equal(mesh.point_data[name][:, 2], 0.0)
        components = {"strain": ("exx", "eyy", "gxy"), "stress_pa": ("sxx_pa", "syy_pa", "sxy_pa")}
        assert set(mesh.cell_data) == {c for names in components.values() for c in names}
        for name, names in components.items():
            for k, component in enumerate(names):
                np.testing.assert_array_equal(mesh.cell_data[component][0], saved[name][:, k])
        for name in ("dirichlet_node_ids", "dirichlet_components", "dirichlet_displacement_m", "metadata_json"):
            assert name in saved.files and name not in mesh.point_data and name not in mesh.cell_data
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")


def test_thermoelastic_result_exports_heat_and_mechanics_arrays(tmp_path):
    fields = _saved(tmp_path, "thermoelastic_bar.json")
    mesh = meshio.read(export_fields(fields, tmp_path / "bar.vtu"))
    with np.load(fields) as saved:
        assert str(saved["field_layout"]) == "thermoelastic2d-p1-v1"
        np.testing.assert_array_equal(mesh.points[:, :2], saved["nodes_m"])
        scalars = {"temperature_k", "thermal_load_w_per_m", "thermal_reaction_w_per_m", "thermal_residual_w_per_m",
                   "prescribed_outward_heat_w_per_m", "ambient_load_w_per_m", "convective_outward_heat_w_per_m",
                   "thermal_system_rhs_w_per_m"}
        vectors = {"displacement_m", "load_external_n_per_m", "load_thermal_n_per_m", "load_body_n_per_m",
                   "load_traction_n_per_m", "reaction_n_per_m", "residual_n_per_m"}
        assert set(mesh.point_data) == scalars | vectors
        for name in scalars:
            np.testing.assert_array_equal(mesh.point_data[name], saved[name])
        for name in vectors:
            np.testing.assert_array_equal(mesh.point_data[name][:, :2], saved[name])
            np.testing.assert_array_equal(mesh.point_data[name][:, 2], 0.0)
        components = {"total_strain": ("total_exx", "total_eyy", "total_gxy"),
                      "thermal_strain": ("thermal_exx", "thermal_eyy", "thermal_gxy"),
                      "elastic_strain": ("elastic_exx", "elastic_eyy", "elastic_gxy"),
                      "stress_pa": ("sxx_pa", "syy_pa", "sxy_pa")}
        expected_cells = {c for names in components.values() for c in names} | {"heat_flux_w_m2", "sigma_zz_pa", "epsilon_zz"}
        assert set(mesh.cell_data) == expected_cells
        for name, names in components.items():
            for k, component in enumerate(names):
                np.testing.assert_array_equal(mesh.cell_data[component][0], saved[name][:, k])
        np.testing.assert_array_equal(mesh.cell_data["heat_flux_w_m2"][0][:, :2], saved["heat_flux_w_m2"])
        np.testing.assert_array_equal(mesh.cell_data["sigma_zz_pa"][0], saved["sigma_zz_pa"])
        np.testing.assert_array_equal(mesh.cell_data["epsilon_zz"][0], saved["epsilon_zz"])
        for name in ("thermal_dirichlet_node_ids", "dirichlet_temperature_k", "dirichlet_node_ids", "metadata_json"):
            assert name in saved.files and name not in mesh.point_data and name not in mesh.cell_data
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")


def test_mechanics_export_checks_its_arrays(tmp_path):
    nodes = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    base = dict(field_layout="mechanics2d-p1-v1", nodes_m=nodes, triangles=np.array([[0, 1, 2]]))
    missing = tmp_path / "missing.npz"
    np.savez(missing, **base, stress_pa=np.zeros((1, 3)))
    with pytest.raises(ValueError, match="needs the saved displacement_m"):
        export_fields(missing, tmp_path / "missing.vtu")
    wrong = tmp_path / "wrong.npz"
    np.savez(wrong, **base, displacement_m=np.zeros((3, 2)), strain=np.zeros((1, 2)))
    with pytest.raises(ValueError, match="strain: expected three components per triangle"):
        export_fields(wrong, tmp_path / "wrong.vtu")
    flat = tmp_path / "flat.npz"
    np.savez(flat, **base, displacement_m=np.zeros(3))
    with pytest.raises(ValueError, match="displacement_m: expected one 2D vector per node"):
        export_fields(flat, tmp_path / "flat.vtu")
    assert not any(tmp_path.glob("*.vtu"))


def _saved_lossy_cavity(tmp_path, n=4):
    data = copy.deepcopy(examples.CAVITY_LOSSY_SLAB)
    data["mesh"]["subdivisions"] = [n, n, n]
    data["physics"]["em1"]["num_modes"] = 2
    data["results"] = {"save_fields": True, "plots": False}
    out = run(Document.from_dict(data), False).save(tmp_path / "lossy")
    with np.load(out / "fields.npz", allow_pickle=False) as archive:
        saved = {key: archive[key] for key in archive.files}
    return out / "fields.npz", saved


def test_complex_cavity_exports_real_and_imaginary_parts(tmp_path):
    fields, saved = _saved_lossy_cavity(tmp_path)
    assert str(saved["field_layout"]) == "cavity3d-edge-complex-v1"
    assert saved["electric_field"].dtype.kind == "c"
    mesh = meshio.read(export_fields(fields, tmp_path / "lossy.vtu"))
    np.testing.assert_array_equal(mesh.points, saved["nodes"])
    np.testing.assert_array_equal(mesh.cells_dict["tetra"], saved["tetrahedra"])
    modes = len(saved["electric_field"])
    assert modes == int(saved["returned_modes"]) == 2
    expected = set()
    for k in range(modes):
        for part in ("real", "imag"):
            expected.add(f"electric_field_mode_{k}_{part}")
            values = mesh.cell_data[f"electric_field_mode_{k}_{part}"][0]
            assert values.dtype.kind == "f" and values.shape == (len(saved["tetrahedra"]), 3)
            np.testing.assert_array_equal(values, getattr(saved["electric_field"][k], part))
    for name in ("tet_relative_permittivity", "tet_relative_permeability"):
        for part in ("real", "imag"):
            expected.add(f"{name}_{part}")
            np.testing.assert_array_equal(mesh.cell_data[f"{name}_{part}"][0], getattr(saved[name], part))
    assert set(mesh.cell_data) == expected
    assert not mesh.point_data
    # The slab is lossy: the imaginary parts are not all zero.
    assert any(np.any(mesh.cell_data[f"electric_field_mode_{k}_imag"][0]) for k in range(modes))
    assert str(saved["electric_field_unit"]) == "m^-3/2"
    assert str(saved["time_convention"]) == "exp(+j*omega*t)"
    with pytest.raises(ValueError, match="time series export needs layout"):
        export_time_series(fields, tmp_path / "series")
    assert not (tmp_path / "series").exists()


def test_complex_cavity_export_checks_its_array_shapes(tmp_path):
    fields, saved = _saved_lossy_cavity(tmp_path)
    for name, value in (("electric_field", saved["electric_field"][:, :-1]),
                        ("tet_relative_permittivity", saved["tet_relative_permittivity"][:-1])):
        corrupt = tmp_path / f"{name}.npz"
        np.savez(corrupt, **dict(saved, **{name: value}))
        with pytest.raises(ValueError, match=f"{name}: expected"):
            export_fields(corrupt, tmp_path / f"{name}.vtu")
        assert not (tmp_path / f"{name}.vtu").exists()
