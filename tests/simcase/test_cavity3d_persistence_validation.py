# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent document-unit and raw-field restoration tests for cavity3d."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

from simcase import Document, run
import galerkin

# Load the independent checks by file path, without relying on pytest's
# cross-package module import order.
_path = (Path(__file__).resolve().parents[1] /
         "galerkin/test_cavity3d_validation.py")
_spec = importlib.util.spec_from_file_location("_independent_cavity_checks", _path)
_checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checks)


def model(unit="m", save_fields=True):
    metre = {"m": 1., "um": 1e-6, "nm": 1e-9}[unit]
    origin = np.array((.1, -.2, .3))
    sides = np.array((1., .8, .6))
    domain = {}
    for i, axis in enumerate("xyz"):
        domain[axis + "min"] = origin[i] / metre
        domain[axis + "max"] = (origin[i] + sides[i]) / metre
    target = _checks.C0 * np.sqrt(1.3 * _checks.oracle(sides)[0]) / (2 * np.pi)
    return Document.from_dict({
        "openphysics": "0.3", "name": "Independent translated vacuum box",
        "geometry": {"length_unit": unit, "domain": domain,
                     "background": {"material": "physmat:vacuum"}, "shapes": []},
        "materials": {},
        "physics": {"em1": {"type": "em.cavity3d", "boundary": "pec",
                   "search": "near_target", "target_frequency": f"{float(target)!r} Hz",
                   "mode_count": 5}},
        "mesh": {"subdivision_count": [3, 3, 3]}, "study": {"type": "single"},
        "results": {"save_fields": save_fields, "plots": False}})


def metadata(check, summary):
    check.assertEqual(summary["cluster_completeness"], "not_certified")
    check.assertEqual(summary["mode_count_policy"], "exact_count_may_split_cluster")
    check.assertEqual(summary["field_layout"], "cavity3d-edge-v2")
    units = summary["field_units"]
    check.assertEqual(units["node_coordinates"], "m")
    check.assertEqual(units["resonant_frequency"], "Hz")
    check.assertEqual(summary["resonant_frequency"]["unit"], "Hz")
    check.assertEqual(units["mass_normalized_electric_field_line_integral"], "1/m^(1/2)")
    check.assertEqual(units["mass_normalized_electric_field"], "1/m^(3/2)")
    check.assertEqual(summary["normalization"], "electric_mass_orthonormal_si")
    check.assertEqual(summary["search"], "near_target")
    check.assertEqual(summary["mode_count"], 5)
    check.assertEqual(summary["returned_mode_count"], 5)
    check.assertFalse([key for key in summary if key.endswith("_unit")])


class IndependentCavityPersistenceValidation(unittest.TestCase):
    def test_document_unit_invariance_and_translation(self):
        runs = [run(model(unit), verbose=False) for unit in ("m", "um", "nm")]
        results = [r.cavity for r in runs]
        base = results[0]
        mass = _checks.check_result(base, 5)
        for result, done in zip(results[1:], runs[1:]):
            _checks.check_result(result, 5)
            np.testing.assert_allclose(result.resonant_frequency, base.resonant_frequency,
                                       rtol=1e-9, atol=0)
            np.testing.assert_allclose(result.wavenumber_squared, base.wavenumber_squared,
                                       rtol=1e-9, atol=0)
            np.testing.assert_allclose(done.node_coordinates, runs[0].node_coordinates,
                                       rtol=1e-12, atol=1e-14)
            # The first three modes are simple; the final pair is degenerate.
            overlap = (base.mass_normalized_electric_field_line_integral.conj().T
                       @ (mass @ result.mass_normalized_electric_field_line_integral))
            self.assertGreaterEqual(np.linalg.svd(overlap, compute_uv=False).min(),
                                    1 - 1e-7)
        # galerkin solves the box at the origin; simcase's node coordinates start at the domain origin (D14)
        np.testing.assert_allclose(runs[0].node_coordinates.min(axis=0), (.1, -.2, .3),
                                   rtol=1e-12, atol=1e-14)
        np.testing.assert_allclose(runs[0].node_coordinates.max(axis=0), (1.1, .6, .9),
                                   rtol=1e-12, atol=1e-14)

    def test_saved_contract_metadata(self):
        import tempfile
        result = run(model(), verbose=False)
        with tempfile.TemporaryDirectory() as directory:
            result.save(directory)
            summary = json.loads((Path(directory) / "summary.json").read_text())
            metadata(self, summary)
            with np.load(Path(directory) / "fields.npz", allow_pickle=False) as data:
                for key in ("cluster_completeness", "mode_count_policy", "field_layout", "normalization"):
                    self.assertEqual(data[key].item(), summary[key])
                saved = json.loads(str(data["metadata_json"]))
                self.assertEqual(saved["field_units"], summary["field_units"])
                self.assertEqual(saved["returned_mode_count"], summary["returned_mode_count"])

    def test_exact_raw_restore_and_recomputed_physics(self):
        import tempfile
        result = run(model("nm"), verbose=False)
        cavity = result.cavity
        with tempfile.TemporaryDirectory() as directory:
            result.save(directory)
            saved_model = Document.load(Path(directory) / "model.json")
            self.assertEqual(saved_model["geometry"]["length_unit"], "nm")
            with np.load(Path(directory) / "fields.npz", allow_pickle=False) as data:
                arrays = {key: data[key] for key in data.files}
            original = {
                "node_coordinates": result.node_coordinates, "tetrahedra": cavity.mesh.tets,
                "edges": cavity.space.edges, "tet_edges": cavity.space.tet_edges,
                "edge_signs": cavity.space.signs, "pec_edge_ids": cavity.pec_edges,
                "mass_normalized_electric_field_line_integral": cavity.mass_normalized_electric_field_line_integral,
                "mass_normalized_electric_field": cavity.mass_normalized_electric_field,
                "wavenumber_squared": cavity.wavenumber_squared,
                "resonant_frequency": cavity.resonant_frequency,
                "relative_residual": cavity.relative_residual}
            for key, before in original.items():
                self.assertEqual(arrays[key].dtype, before.dtype)
                self.assertEqual(arrays[key].shape, before.shape)
                np.testing.assert_array_equal(arrays[key], before)
            mesh = galerkin.Mesh3D(arrays["node_coordinates"], arrays["tetrahedra"])
            space = galerkin.EdgeSpace3D(mesh)
            np.testing.assert_array_equal(space.edges, arrays["edges"])
            np.testing.assert_array_equal(space.tet_edges, arrays["tet_edges"])
            np.testing.assert_array_equal(space.signs, arrays["edge_signs"])
            restored = SimpleNamespace(mesh=mesh, space=space,
                mass_normalized_electric_field_line_integral=arrays["mass_normalized_electric_field_line_integral"],
                mass_normalized_electric_field=arrays["mass_normalized_electric_field"],
                wavenumber_squared=arrays["wavenumber_squared"],
                resonant_frequency=arrays["resonant_frequency"],
                relative_residual=arrays["relative_residual"],
                pec_edges=arrays["pec_edge_ids"],
                mode_count=json.loads(str(arrays["metadata_json"]))["mode_count"],
                search=arrays["search"].item())
            _checks.check_result(restored, 5)

    def test_save_fields_false_omits_raw_arrays_keeps_spectral_policy(self):
        import tempfile
        result = run(model(save_fields=False), verbose=False)
        with tempfile.TemporaryDirectory() as directory:
            result.save(directory)
            summary = json.loads((Path(directory) / "summary.json").read_text())
            np.testing.assert_allclose(summary["resonant_frequency"]["values"], result.resonant_frequency,
                                       rtol=1e-12, atol=0)
            path = Path(directory) / "fields.npz"
            if path.exists():
                with np.load(path, allow_pickle=False) as data:
                    for key in ("mass_normalized_electric_field_line_integral",
                                "mass_normalized_electric_field"):
                        self.assertNotIn(key, data.files)
            self.assertFalse(Document.load(Path(directory) / "model.json")["results"]["save_fields"])
            # Check raw-array omission even when a separate metadata gate fails.
            metadata(self, summary)


if __name__ == "__main__":
    unittest.main()
