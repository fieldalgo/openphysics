# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical and convergence checks for tetrahedral elasticity."""
import numpy as np
import pytest

from galerkin.elasticity3d import _solve_elasticity_3d, solve_elasticity_3d
from galerkin.mesh3d import Mesh3D, box_mesh


def fixed(nodes, axes=(0, 1, 2)):
    return {(i, axis): 0. for i in nodes for axis in axes}


def test_uniaxial_traction():
    mesh = box_mesh(2, 1, 1, 4, 2, 2)
    x, y, z = mesh.nodes.T
    prescribed = fixed(np.flatnonzero(x == 0), (0,))
    prescribed.update(fixed(np.flatnonzero(y == 0), (1,)))
    prescribed.update(fixed(np.flatnonzero(z == 0), (2,)))
    result = solve_elasticity_3d(mesh, youngs_modulus={"domain": 200.}, poisson_ratio={"domain": .25},
                                 prescribed_displacement=prescribed, traction={"x1": (2., 0., 0.)})
    expected = np.diag([.01, -.0025, -.0025])
    np.testing.assert_allclose(result.displacement, mesh.nodes @ expected, atol=1e-14)
    np.testing.assert_allclose(result.strain, np.broadcast_to(expected, result.strain.shape), atol=1e-14)
    stress = np.diag([2., 0., 0.])
    np.testing.assert_allclose(result.stress, np.broadcast_to(stress, result.stress.shape), atol=1e-13)
    np.testing.assert_allclose(result.reaction_force.sum(axis=0), [-2, 0, 0], atol=1e-13)


def test_simple_shear_and_force_moment_balance():
    mesh = box_mesh(1, 2, 3, 2, 2, 2)
    prescribed = fixed(mesh.boundary_nodes())
    for node in mesh.boundary_nodes():
        prescribed[node, 0] = .01 * mesh.nodes[node, 1]
    result = solve_elasticity_3d(mesh, youngs_modulus=200., poisson_ratio=.25,
                                 prescribed_displacement=prescribed)
    np.testing.assert_allclose(result.displacement[:, 0], .01 * mesh.nodes[:, 1], atol=1e-14)
    np.testing.assert_allclose(result.strain[:, 0, 1], .005, atol=1e-14)
    np.testing.assert_allclose(result.stress[:, 0, 1], .8, atol=1e-13)
    np.testing.assert_array_equal(result.stress, result.stress.swapaxes(1, 2))
    np.testing.assert_allclose(result.reaction_force.sum(axis=0), 0, atol=1e-13)
    np.testing.assert_allclose(np.cross(mesh.nodes, result.reaction_force).sum(axis=0), 0, atol=1e-13)


def test_thermal_expansion_and_blocked_reaction():
    mesh = box_mesh(1, 1, 1, 2, 2, 2)
    kw = dict(youngs_modulus=100., poisson_ratio=.25, thermal_strain=np.full(mesh.num_tets, .001))
    anchors = {}
    for axis in range(3):
        anchors.update(fixed(np.flatnonzero(mesh.nodes[:, axis] == 0), (axis,)))
    free = _solve_elasticity_3d(mesh, prescribed_displacement=anchors, **kw)
    np.testing.assert_allclose(free.displacement, .001 * mesh.nodes, atol=1e-15)
    np.testing.assert_allclose(free.stress, 0., atol=1e-13)
    blocked = _solve_elasticity_3d(mesh, prescribed_displacement=fixed(range(mesh.num_nodes)), **kw)
    expected = -.2 * np.eye(3)
    np.testing.assert_allclose(blocked.stress, np.broadcast_to(expected, blocked.stress.shape))
    np.testing.assert_allclose(blocked.reaction_force[mesh.boundary["x1"], 0].sum(), -.2)
    np.testing.assert_array_equal(blocked.strain, 0.)


def test_disconnected_component_must_constrain_all_modes():
    box = box_mesh(1, 1, 1, 1, 1, 1)
    mesh = Mesh3D(np.r_[box.nodes, box.nodes + [2, 0, 0]], np.r_[box.tets, box.tets + box.num_nodes])
    kw = dict(youngs_modulus=100., poisson_ratio=.25)
    held = fixed(box.boundary["x0"])
    held.update(fixed([box.num_nodes]))
    with pytest.raises(ValueError, match="component 1.*rigid-body"):
        solve_elasticity_3d(mesh, prescribed_displacement=held, **kw)
    held.update(fixed(box.boundary["x0"] + box.num_nodes))
    result = solve_elasticity_3d(mesh, prescribed_displacement=held, **kw)
    np.testing.assert_array_equal(result.displacement, 0.)


def test_manufactured_solution_converges():
    errors = []
    for count in (2, 4, 8):
        mesh = box_mesh(1, 1, 1, count, count, count)
        x = mesh.nodes[:, 0]
        held = fixed(mesh.boundary_nodes())
        for node in mesh.boundary_nodes():
            held[node, 0] = x[node] * (1 - x[node])
        result = solve_elasticity_3d(mesh, youngs_modulus=5., poisson_ratio=.25,
                                     prescribed_displacement=held, body_force_density=(12., 0., 0.))
        center_x = x[mesh.tets].mean(axis=1)
        errors.append(np.linalg.norm(result.stress[:, 0, 0] - 6 * (1 - 2 * center_x))
                      / np.sqrt(mesh.num_tets))
        force = result.applied_force + result.reaction_force
        np.testing.assert_allclose(force.sum(axis=0), 0., atol=1e-12)
        np.testing.assert_allclose(np.cross(mesh.nodes, force).sum(axis=0), 0., atol=1e-12)
    assert np.all(np.array(errors[1:]) < .55 * np.array(errors[:-1])), errors


def test_two_materials_in_series():
    box = box_mesh(2, 1, 1, 4, 2, 2)
    region = (box.nodes[box.tets, 0].mean(axis=1) >= 1).astype(int)
    mesh = Mesh3D(box.nodes, box.tets, regions=region, region_names=["left", "right"],
                  tagged_faces=box.tagged_faces)
    result = solve_elasticity_3d(
        mesh, youngs_modulus={"left": 100., "right": 200.}, poisson_ratio={"left": 0., "right": 0.},
        prescribed_displacement=fixed(mesh.boundary["x0"]), traction={"x1": (2., 0., 0.)})
    x = mesh.nodes[:, 0]
    exact = .02 * np.minimum(x, 1) + .01 * np.maximum(x - 1, 0)
    np.testing.assert_allclose(result.displacement[:, 0], exact, atol=1e-14)
    np.testing.assert_allclose(result.strain[:, 0, 0], np.where(region, .01, .02), atol=1e-14)
    np.testing.assert_allclose(result.stress[:, 0, 0], 2., atol=1e-13)
