# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Verification of supported, undamped 3D structural modes."""
import numpy as np
import pytest

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.structural_modes3d import solve_structural_modes_3d


def clamp(nodes):
    return {(node, axis): 0.0 for node in nodes for axis in range(3)}


def test_cantilever_bending_converges_in_both_planes():
    length, width, thickness = .12, .018, .012
    young, density = 70e9, 2700.
    # Euler-Bernoulli slender-beam limit, weak and strong bending axes.
    beta = 1.875104068711961
    analytic = beta**2 / (2 * np.pi * length**2) * np.sqrt(young / (12 * density)) * np.array([thickness, width])
    errors = []
    for n in (3, 6, 9):
        mesh = box_mesh(length, width, thickness, 8*n, n, n)
        result = solve_structural_modes_3d(mesh, youngs_modulus=young, poisson_ratio=0.,
                                           mass_density=density, prescribed_displacement=clamp(mesh.boundary["x0"]),
                                           mode_count=2)
        errors.append(np.abs(result.frequency / analytic - 1))
        shape = result.mass_normalized_displacement
        assert shape.shape == (2, mesh.num_nodes, 3)
        assert np.all(shape[:, mesh.boundary["x0"], :] == 0)
        tip = np.abs(shape[:, mesh.boundary["x1"], :].mean(axis=1))
        assert tip[0, 2] > 3 * tip[0, 1] and tip[1, 1] > 3 * tip[1, 2]
        assert np.max(result.relative_residual) < 1e-7
    assert np.all(np.diff(errors, axis=0) < 0), errors
    assert np.all(errors[-1] < np.array([.025, .01])), errors


@pytest.mark.parametrize("copies", [2, 12])
def test_repeated_modes_of_separately_supported_solids(copies):
    block = box_mesh(1., .5, .3, 2, 1, 1)
    n = block.num_nodes
    assembly = Mesh3D(np.vstack([block.nodes + [0., float(i), 0.] for i in range(copies)]),
                      np.vstack([block.tets + n*i for i in range(copies)]))
    held = block.boundary["x0"]
    kw = dict(youngs_modulus=10., poisson_ratio=.2, mass_density=3.)
    single = solve_structural_modes_3d(block, prescribed_displacement=clamp(held), mode_count=2, **kw)
    with pytest.raises(ValueError, match="rigid-body"):
        solve_structural_modes_3d(assembly, prescribed_displacement=clamp(held), **kw)
    supports = clamp(np.concatenate([held + n*i for i in range(copies)]))
    modes = solve_structural_modes_3d(assembly, prescribed_displacement=supports, mode_count=copies+1, **kw)
    expected = np.r_[np.repeat(single.frequency[0], copies), single.frequency[1]]
    np.testing.assert_allclose(modes.frequency, expected, rtol=1e-10)


def test_one_free_dof_consistent_mass_and_material_scaling():
    mesh = Mesh3D(np.eye(4, 3), [[0, 1, 2, 3]])
    fixed = clamp(range(4))
    del fixed[0, 0]
    for young, density in ((8., 3.), (32., 3.), (8., 12.)):
        result = solve_structural_modes_3d(mesh, youngs_modulus=young, poisson_ratio=0.,
                                           mass_density=density, prescribed_displacement=fixed)
        # N0=x; K00=E V, M00=rho V/10, V=1/6.
        np.testing.assert_allclose(result.frequency, [np.sqrt(10*young/density)/(2*np.pi)])
        np.testing.assert_allclose(abs(result.mass_normalized_displacement[0, 0, 0]), np.sqrt(60/density))
        assert np.count_nonzero(result.mass_normalized_displacement) == 1
        assert result.units == {"frequency": "Hz", "mass_normalized_displacement": "1/kg^(1/2)",
                                "relative_residual": "1"}


@pytest.mark.parametrize("override, message", [
    ({"prescribed_displacement": {}}, "rigid-body"),
    ({"mode_count": 13}, "free displacement"),
    ({"mode_count": True}, "positive integer"),
    ({"mass_density": 0.}, "mass_density"),
    ({"mass_density": {"missing": 2.}}, "regions"),
    ({"poisson_ratio": .5}, "poisson_ratio"),
])
def test_invalid_inputs(override, message):
    mesh = box_mesh(1., 1., 1., 1, 1, 1)
    kw = dict(youngs_modulus=1., poisson_ratio=.2, mass_density=1.,
              prescribed_displacement=clamp(mesh.boundary["x0"]))
    with pytest.raises(ValueError, match=message):
        solve_structural_modes_3d(mesh, **(kw | override))


def test_nonzero_or_fully_prescribed_supports():
    mesh = box_mesh(1., 1., 1., 1, 1, 1)
    fixed = clamp(range(mesh.num_nodes))
    kw = dict(youngs_modulus=1., poisson_ratio=.2, mass_density=1., prescribed_displacement=fixed)
    with pytest.raises(ValueError, match="free displacement"):
        solve_structural_modes_3d(mesh, **kw)
    fixed[0, 0] = 1.
    with pytest.raises(ValueError, match="zero prescribed displacement"):
        solve_structural_modes_3d(mesh, **kw)
