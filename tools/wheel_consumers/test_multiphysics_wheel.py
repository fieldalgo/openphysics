# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Installed consumers for static elasticity and complex vector fields.

Copied outside the checkout by check_distributions.py. These public-API smoke
checks complement the independent source convergence gates; no imports skip.
"""

import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import galerkin.elasticity as elasticity
import galerkin.waveguide as waveguide
import refsol.elasticity as reference
from galerkin import EdgeSpace, disk_mesh, eval_edge_field
from galerkin.mesh import rectangle_mesh
from simcase import Document, examples
from simcase.fields import VectorField
from simcase.physics_em_modes2d import solve
from simcase.runner import RunResult


def test_new_public_submodules_come_from_installed_environment():
    for module in (elasticity, reference, waveguide):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_installed_elasticity_uniaxial_closed_form(plane):
    # Independent uniaxial stress solution: free lateral boundaries, imposed
    # axial extension; the plane-strain lateral coefficient differs from stress.
    mesh = rectangle_mesh(2., 1., 4, 2)
    e, nu, extension = 70e9, .3, 2e-4
    lateral = -nu * extension if plane == "stress" else -nu / (1 - nu) * extension
    expected_u = mesh.nodes * [extension, lateral]
    expected_strain = np.array([extension, lateral, 0.])
    axial_stress = e * extension if plane == "stress" else e / (1 - nu**2) * extension
    expected_stress = np.array([axial_stress, 0., 0.])
    bc = {(int(i), 0): 0. for i in mesh.boundary["left"]}
    bc.update({(int(i), 0): 2 * extension for i in mesh.boundary["right"]})
    bc.update({(int(i), 1): 0. for i in mesh.boundary["bottom"]})
    result = elasticity.solve_elasticity(mesh, young_modulus=e, poisson_ratio=nu,
                                        plane=plane, dirichlet=bc)
    exact = reference.affine(mesh.nodes, np.diag([extension, lateral]),
                             young_modulus=e, poisson_ratio=nu, plane=plane)
    for u in (result.displacement, exact.displacement):
        np.testing.assert_allclose(u, expected_u, rtol=1e-10, atol=1e-14)
    for strain in (result.strain, exact.strain):
        np.testing.assert_allclose(strain, np.broadcast_to(expected_strain, strain.shape),
                                   rtol=1e-10, atol=1e-14)
    for stress in (result.stress, exact.stress):
        np.testing.assert_allclose(stress, np.broadcast_to(expected_stress, stress.shape),
                                   rtol=1e-10, atol=1e-6)
    assert result.plane == plane
    np.testing.assert_array_equal(result.load, 0.)
    # Reactions on opposite ends match the analytic stress times unit height.
    for side, sign in (("left", -1), ("right", 1)):
        np.testing.assert_allclose(result.reaction[mesh.boundary[side], 0].sum(),
                                   sign * axial_stress, rtol=1e-10)


@pytest.mark.parametrize("plane", ["stress", "strain"])
@pytest.mark.parametrize("constraints", ["none", "one_pinned_node"])
def test_installed_elasticity_rejects_unremoved_rigid_modes(plane, constraints):
    mesh = rectangle_mesh(1., 1., 2, 2)
    node = int(mesh.boundary["left"][0])
    bc = {} if constraints == "none" else {(node, 0): 0., (node, 1): 0.}
    with pytest.raises(ValueError, match="rigid|singular"):
        elasticity.solve_elasticity(mesh, young_modulus=70e9, poisson_ratio=.3,
                                    plane=plane, dirichlet=bc)


def test_english_elasticity_example_runs_with_installed_packages():
    example = Path(__file__).resolve().parents[1] / "examples" / "elasticity2d.py"
    assert example.is_file(), "the checker must copy the checkout example"
    completed = subprocess.run([sys.executable, "-I", str(example)],
                               capture_output=True, text=True, check=True)
    lines = completed.stdout.splitlines()
    labels = ["Minimum vertical displacement (m):", "Body load per thickness (N/m):",
              "Support reaction per thickness (N/m):", "Force imbalance per thickness (N/m):"]
    assert len(lines) == len(labels)
    assert all(line.startswith(label) for line, label in zip(lines, labels))
    displacement = float(lines[0].split(":", 1)[1])
    assert np.isfinite(displacement) and displacement < 0
    load, reaction, imbalance = [np.fromstring(line.split(":", 1)[1].strip(" []"), sep=" ")
                                 for line in lines[1:]]
    assert all(a.shape == (2,) and np.isfinite(a).all() for a in (load, reaction, imbalance))
    assert load[1] < 0 and reaction[1] > 0
    # Normalize by the nonzero applied-force scale. An absolute tolerance in
    # N/m on the zero horizontal component is not a unit-independent balance gate.
    force_scale = np.linalg.norm(load)
    np.testing.assert_allclose(reaction / force_scale, -load / force_scale,
                               rtol=1e-9, atol=1e-12)
    assert np.linalg.norm(imbalance) / force_scale <= 1e-9


def test_installed_vector_solver_and_complex_serialization(tmp_path):
    mesh = disk_mesh((4, 8, 24), (4, 4, 16), 32)
    eps = mesh.by_region([1.45**2, 1.44**2, 1.44**2])
    neff, _, et, ez = waveguide.solve_modes(mesh, eps, 2 * np.pi / 1.5, 1.45, 2)
    assert len(neff) == 2 and np.isfinite(neff).all()
    assert np.iscomplexobj(et) and np.iscomplexobj(ez)
    point = solve(mesh, eps, 1.5, {"outer": "pec"}, 2, "vector", 1.44)
    original = point["vector_field"]
    assert original.electric.shape[1] == 2
    # A deterministic non-real mode phase supplies a sensitive serialization
    # control even if a platform happens to return a nearly-real solver basis.
    phases = np.exp(1j * np.array([.37, -.61]))
    field = VectorField(original.edges.copy(), original.transverse * phases,
                        original.longitudinal * phases, original.electric * phases[None, :, None])
    for array in (field.transverse, field.longitudinal, field.electric):
        assert np.iscomplexobj(array) and np.max(np.abs(array.imag)) > 1e-12
    doc_data = copy.deepcopy(examples.VECTOR_FIBER)
    doc_data["physics"]["em1"].update(wavelength=1.5, num_modes=2)
    doc_data.setdefault("results", {}).update(plots=False, save_fields=True)
    doc = Document.from_dict(doc_data)
    names = ["core_region", "clad_region", "outer_region"]
    material_names = dict(zip(names, ["core", "clad", "clad"]))
    result = RunResult(doc, mesh.nodes, mesh.triangles, mesh.regions, names,
                       material_names, None, [1.5], point["neff"][None, :], [],
                       vector_fields=[field])
    output = result.save(tmp_path / "complex-vector")
    with np.load(output / "fields.npz", allow_pickle=False) as arrays:
        for key, expected in (("vector_transverse", field.transverse),
                              ("vector_longitudinal", field.longitudinal),
                              ("vector_electric", field.electric)):
            assert arrays[key].dtype.kind == "c" and not arrays[key].dtype.hasobject
            np.testing.assert_array_equal(arrays[key][0], expected)
        space = EdgeSpace(mesh)
        for j in range(2):
            np.testing.assert_allclose(eval_edge_field(space, arrays["vector_transverse"][0, :, j]),
                                       arrays["vector_electric"][0, :, j, :2], atol=1e-13)
        np.testing.assert_allclose(arrays["vector_longitudinal"][0][mesh.triangles].mean(axis=1),
                                   arrays["vector_electric"][0, :, :, 2], atol=1e-13)
    payload = json.loads(json.dumps(field.to_dict()))
    decoded = np.array(payload["real"]) + 1j * np.array(payload["imag"])
    np.testing.assert_array_equal(decoded.transpose(1, 0, 2), field.electric)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["field_representation"] == "vector-edge-nodal-v1"
