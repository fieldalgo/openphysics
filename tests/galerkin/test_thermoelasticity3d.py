# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed-form isotropic thermoelasticity on P1 tetrahedra."""
import numpy as np
import pytest

from galerkin import Mesh3D, box_mesh
from galerkin.elasticity3d import solve_elasticity_3d
from galerkin.thermoelasticity3d import solve_thermoelasticity_3d

E, NU, ALPHA = 3e9, 0.25, 2e-5
NODES = np.vstack((np.zeros(3), np.eye(3)))
RIGID_SUPPORT = dict.fromkeys(((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2)), 0.0)


def solve(mesh, temperature, **overrides):
    options = dict(stress_free_temperature=300.0, linear_expansion_coefficient=ALPHA,
                   youngs_modulus=E, poisson_ratio=NU, prescribed_displacement=RIGID_SUPPORT)
    options.update(overrides)
    return solve_thermoelasticity_3d(mesh, temperature=temperature, **options)


def tet():
    return Mesh3D(NODES.copy(), np.array([[0, 1, 2, 3]]))


@pytest.mark.parametrize("delta", [25.0, 0.0])
def test_uniform_free_expansion(delta):
    result = solve(tet(), np.full(4, 300.0 + delta))
    np.testing.assert_allclose(result.displacement, NODES * ALPHA * delta, atol=1e-14)
    np.testing.assert_allclose(result.strain, (np.eye(3) * ALPHA * delta)[None], atol=1e-14)
    np.testing.assert_allclose(result.stress, 0.0, atol=1e-6)
    np.testing.assert_allclose(result.reaction_force, 0.0, atol=1e-7)


def test_fixed_tetrahedron_p1_average_and_reaction():
    fixed = dict.fromkeys(np.ndindex(4, 3), 0.0)
    result = solve(tet(), [310, 320, 330, 340], prescribed_displacement=fixed)
    pressure = E * ALPHA * 25 / (1 - 2 * NU)
    gradients = np.vstack((-np.ones(3), np.eye(3)))
    np.testing.assert_array_equal(result.displacement, np.zeros((4, 3)))
    np.testing.assert_array_equal(result.strain, np.zeros((1, 3, 3)))
    np.testing.assert_allclose(result.stress, (-pressure * np.eye(3))[None], atol=1e-8)
    np.testing.assert_allclose(result.reaction_force, -pressure * gradients / 6, atol=1e-8)
    np.testing.assert_allclose(result.reaction_force.sum(axis=0), 0, atol=1e-8)


def test_expansion_by_material_region():
    mesh = box_mesh(2, 1, 1, 2, 1, 1)
    ids = (mesh.nodes[mesh.tets, 0].mean(axis=1) > 1).astype(int)
    mesh = Mesh3D(mesh.nodes, mesh.tets.copy(), regions=ids, region_names=["left", "right"])
    fixed = dict.fromkeys(np.ndindex(mesh.num_nodes, 3), 0.0)
    result = solve(mesh, np.full(mesh.num_nodes, 310.0), prescribed_displacement=fixed,
                   linear_expansion_coefficient={"right": -ALPHA, "left": 2 * ALPHA})
    alpha = np.where(ids == 0, 2 * ALPHA, -ALPHA)
    expected = -E / (1 - 2 * NU) * 10 * alpha[:, None, None] * np.eye(3)
    np.testing.assert_allclose(result.stress, expected, atol=1e-8)


@pytest.mark.parametrize(("temperature", "options", "error", "message"), [
    ([300], {}, ValueError, "shape"),
    ([300, 300, -1, 300], {}, ValueError, "nonnegative"),
    ([300, 300, np.nan, 300], {}, ValueError, "finite"),
    ([300] * 4, {"stress_free_temperature": -1}, ValueError, "nonnegative"),
    ([300] * 4, {"linear_expansion_coefficient": {"missing": 1}}, ValueError, "region"),
    ([300] * 4, {"linear_expansion_coefficient": np.inf}, ValueError, "finite"),
    ([300] * 4, {"traction": {"face": "1 Pa"}}, TypeError, "SI numbers"),
])
def test_rejects_invalid_input_before_structural_solve(temperature, options, error, message):
    with pytest.raises(error, match=message):
        solve(tet(), temperature, **options)


def test_thermal_and_mechanical_loads_superpose():
    grid = box_mesh(2, 1, 1, 2, 1, 1)
    ids = (grid.nodes[grid.tets, 0].mean(axis=1) > 1).astype(int)
    mesh = Mesh3D(grid.nodes, grid.tets.copy(), regions=ids, region_names=["left", "right"],
                  tagged_faces=grid.tagged_faces)
    temperature = 300 + 20 * mesh.nodes[:, 0]
    fixed = {(int(n), axis): 0.0 for n in mesh.boundary["x0"] for axis in range(3)}
    loads = dict(body_force_density=(0.0, -4.0, 0.0), traction={"x1": (1.0, 0.0, 0.0)})
    material = dict(youngs_modulus=E, poisson_ratio=NU, prescribed_displacement=fixed)
    thermal = dict(temperature=temperature, stress_free_temperature=300.,
                   linear_expansion_coefficient={"left": 2 * ALPHA, "right": -ALPHA})
    mechanical = solve_elasticity_3d(mesh, **material, **loads)
    expansion = solve_thermoelasticity_3d(mesh, **material, **thermal)
    combined = solve_thermoelasticity_3d(mesh, **material, **thermal, **loads)
    np.testing.assert_allclose(combined.displacement, mechanical.displacement + expansion.displacement,
                               rtol=1e-10, atol=1e-14)
    np.testing.assert_allclose(combined.stress, mechanical.stress + expansion.stress, rtol=1e-10, atol=1e-7)
    np.testing.assert_allclose(combined.reaction_force, mechanical.reaction_force + expansion.reaction_force,
                               rtol=1e-10, atol=1e-7)
