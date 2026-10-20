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
        "openphysics": "0.2", "name": "Independent translated vacuum box",
        "units": {"length": unit},
        "geometry": {"domain": domain, "background": {"material": "vacuum"},
                     "shapes": []},
        "materials": {},
        "physics": {"em1": {"type": "em.cavity3d", "boundary": "pec",
                   "search": "near_target", "target_frequency_hz": target,
                   "num_modes": 5}},
        "mesh": {"subdivisions": [3, 3, 3]}, "study": {"type": "single"},
        "results": {"save_fields": save_fields, "plots": False}})


def metadata(check, summary):
    check.assertEqual(summary["cluster_completeness"], "not_certified")
    check.assertEqual(summary["mode_count_policy"], "exact_count_may_split_cluster")
    check.assertEqual(summary["field_layout"], "cavity3d-edge-v1")
    check.assertEqual(summary["mesh_length_unit"], "m")
    check.assertEqual(summary["frequency_unit"], "Hz")
    check.assertEqual(summary["edge_coefficient_unit"], "m^-1/2")
    check.assertEqual(summary["electric_field_unit"], "m^-3/2")
    check.assertEqual(summary["normalization"], "electric_mass_orthonormal_si")
    check.assertEqual(summary["search"], "near_target")
    check.assertEqual(summary["requested_modes"], 5)
    check.assertEqual(summary["returned_modes"], 5)


class IndependentCavityPersistenceValidation(unittest.TestCase):
    def test_document_unit_invariance_and_translation(self):
        results = [run(model(unit), verbose=False).cavity for unit in ("m", "um", "nm")]
        base = results[0]
        mass = _checks.check_result(base, 5)
        for result in results[1:]:
            _checks.check_result(result, 5)
            np.testing.assert_allclose(result.frequencies_hz, base.frequencies_hz,
                                       rtol=1e-9, atol=0)
            np.testing.assert_allclose(result.eigenvalues_m2, base.eigenvalues_m2,
                                       rtol=1e-9, atol=0)
            np.testing.assert_allclose(result.mesh.nodes, base.mesh.nodes,
                                       rtol=1e-12, atol=1e-14)
            # The first three modes are simple; the final pair is degenerate.
            overlap = base.edge_coefficients.conj().T @ (mass @ result.edge_coefficients)
            self.assertGreaterEqual(np.linalg.svd(overlap, compute_uv=False).min(),
                                    1 - 1e-7)
        np.testing.assert_allclose(base.mesh.nodes.min(axis=0), (.1, -.2, .3),
                                   rtol=1e-12, atol=1e-14)
        np.testing.assert_allclose(base.mesh.nodes.max(axis=0), (1.1, .6, .9),
                                   rtol=1e-12, atol=1e-14)

    def test_saved_contract_metadata(self):
        import tempfile
        result = run(model(), verbose=False)
        with tempfile.TemporaryDirectory() as directory:
            result.save(directory)
            summary = json.loads((Path(directory) / "summary.json").read_text())
            metadata(self, summary)
            with np.load(Path(directory) / "fields.npz", allow_pickle=False) as data:
                for key in ("cluster_completeness", "mode_count_policy", "field_layout",
                            "mesh_length_unit", "frequency_unit", "normalization"):
                    self.assertEqual(data[key].item(), summary[key])

    def test_exact_raw_restore_and_recomputed_physics(self):
        import tempfile
        result = run(model("nm"), verbose=False)
        cavity = result.cavity
        with tempfile.TemporaryDirectory() as directory:
            result.save(directory)
            saved_model = Document.load(Path(directory) / "model.json")
            self.assertEqual(saved_model["units"]["length"], "nm")
            with np.load(Path(directory) / "fields.npz", allow_pickle=False) as data:
                arrays = {key: data[key] for key in data.files}
            original = {
                "nodes": cavity.mesh.nodes, "tetrahedra": cavity.mesh.tets,
                "edges": cavity.space.edges, "tet_edges": cavity.space.tet_edges,
                "edge_signs": cavity.space.signs, "pec_edge_ids": cavity.pec_edge_ids,
                "edge_coefficients": cavity.edge_coefficients,
                "electric_field": cavity.electric_field,
                "eigenvalues_m2": cavity.eigenvalues_m2,
                "frequencies_hz": cavity.frequencies_hz,
                "relative_residuals": cavity.relative_residuals}
            for key, before in original.items():
                self.assertEqual(arrays[key].dtype, before.dtype)
                self.assertEqual(arrays[key].shape, before.shape)
                np.testing.assert_array_equal(arrays[key], before)
            mesh = galerkin.Mesh3D(arrays["nodes"], arrays["tetrahedra"])
            space = galerkin.EdgeSpace3D(mesh)
            np.testing.assert_array_equal(space.edges, arrays["edges"])
            np.testing.assert_array_equal(space.tet_edges, arrays["tet_edges"])
            np.testing.assert_array_equal(space.signs, arrays["edge_signs"])
            restored = SimpleNamespace(mesh=mesh, space=space,
                edge_coefficients=arrays["edge_coefficients"],
                electric_field=arrays["electric_field"],
                eigenvalues_m2=arrays["eigenvalues_m2"],
                frequencies_hz=arrays["frequencies_hz"],
                relative_residuals=arrays["relative_residuals"],
                pec_edge_ids=arrays["pec_edge_ids"],
                requested_modes=int(arrays["requested_modes"]), search=arrays["search"].item())
            _checks.check_result(restored, 5)

    def test_save_fields_false_omits_raw_arrays_keeps_spectral_policy(self):
        import tempfile
        result = run(model(save_fields=False), verbose=False)
        with tempfile.TemporaryDirectory() as directory:
            result.save(directory)
            summary = json.loads((Path(directory) / "summary.json").read_text())
            np.testing.assert_allclose(summary["frequencies_hz"], result.frequencies_hz,
                                       rtol=1e-12, atol=0)
            path = Path(directory) / "fields.npz"
            if path.exists():
                with np.load(path, allow_pickle=False) as data:
                    for key in ("edge_coefficients", "electric_field"):
                        self.assertNotIn(key, data.files)
            self.assertFalse(Document.load(Path(directory) / "model.json")["results"]["save_fields"])
            # Check raw-array omission even when a separate metadata gate fails.
            metadata(self, summary)


if __name__ == "__main__":
    unittest.main()
