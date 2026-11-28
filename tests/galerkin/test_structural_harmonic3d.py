# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical verification of the complex forced response of a supported solid."""
import numpy as np
import pytest

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.structural_harmonic3d import solve_structural_harmonic_3d


def fixed(nodes, axes=(0, 1, 2)):
    return {(node, axis): 0.0 for node in nodes for axis in axes}


@pytest.fixture
def oscillator():
    # The sole free coordinate is the x displacement of the node at (1, 0, 0).
    mesh = Mesh3D(np.vstack([np.zeros(3), np.eye(3)]), [[0, 1, 2, 3]],
                  tagged_faces={"base": [[0, 2, 1]], "other": [[0, 1, 3], [0, 3, 2], [1, 2, 3]]})
    supports = fixed(range(4))
    del supports[1, 0]
    return mesh, dict(youngs_modulus=8.0, poisson_ratio=0.0, mass_density=3.0,
                      prescribed_displacement=supports)


@pytest.mark.parametrize("alpha, beta", [(0.2, 0.0), (0.0, 0.015), (0.2, 0.015)])
def test_single_coordinate_complex_response_and_support_forces(oscillator, alpha, beta):
    mesh, material = oscillator
    volume = 1 / 6
    # N1 = x, K11 = E V, consistent M11 = rho V/10 and Mj1 = rho V/20.
    stiffness = material["youngs_modulus"] * volume
    mass = material["mass_density"] * volume / 10
    natural_frequency = np.sqrt(stiffness / mass) / (2 * np.pi)
    frequency = natural_frequency * np.array([1.4, 0.6, 1.0, 0.0, 0.999, 0.6])
    omega = 2 * np.pi * frequency
    body = np.array([3.0 + 2.0j, 0.0, -0.5j])
    traction = np.array([1.0 - 0.3j, 2.0j, 0.0])
    result = solve_structural_harmonic_3d(
        mesh, **material, frequency=frequency, body_force_density=body, traction={"base": traction},
        mass_proportional_damping_coefficient=alpha, stiffness_proportional_damping_coefficient=beta,
    )
    # Equal nodal shares of the uniform loads on the volume and the 1/2 m² base.
    applied = np.tile(volume * body / 4, (4, 1))
    applied[[0, 1, 2]] += 0.5 * traction / 3
    dynamic_stiffness = stiffness - mass * omega**2 - 1j * omega * (alpha * mass + beta * stiffness)
    coordinate = applied[1, 0] / dynamic_stiffness
    expected_u = np.zeros((len(frequency), 4, 3), complex)
    expected_u[:, 1, 0] = coordinate
    expected_stress = np.zeros((len(frequency), 1, 3, 3), complex)
    expected_stress[:, 0, 0, 0] = material["youngs_modulus"] * coordinate

    reaction = -np.tile(applied, (len(frequency), 1, 1))
    reaction[:, 0, 0] -= stiffness * (1 - 1j * omega * beta) * coordinate
    reaction[:, [0, 2, 3], 0] -= (0.5 * mass * (omega**2 + 1j * omega * alpha) * coordinate)[:, None]
    reaction[:, 1, 0] = 0
    np.testing.assert_array_equal(result.frequency, frequency)
    np.testing.assert_allclose(result.displacement, expected_u, rtol=1e-12)
    np.testing.assert_allclose(result.stress, expected_stress, rtol=1e-12)
    np.testing.assert_allclose(result.reaction_force, reaction, rtol=1e-12, atol=1e-15)
    # At undamped natural frequency the response lags the applied load by 90° for exp(-i omega t).
    np.testing.assert_allclose(np.angle(result.displacement[2, 1, 0] / applied[1, 0]), np.pi / 2)
    assert result.relative_residual.shape == frequency.shape
    assert np.all(result.relative_residual < 1e-12)


def test_undamped_pole_and_resolvable_neighbors(oscillator):
    mesh, material = oscillator
    natural_frequency = np.sqrt(10 * material["youngs_modulus"] / material["mass_density"]) / (2 * np.pi)
    body = (3.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        solve_structural_harmonic_3d(mesh, **material, frequency=[natural_frequency], body_force_density=body)
    with pytest.raises(ValueError):
        solve_structural_harmonic_3d(mesh, **material, frequency=[natural_frequency])
    ratio = np.array([1 - 1e-5, 1 + 1e-5])
    nearby = solve_structural_harmonic_3d(mesh, **material, frequency=natural_frequency * ratio,
                                          body_force_density=body)
    static_displacement = body[0] / (4 * material["youngs_modulus"])
    np.testing.assert_allclose(nearby.displacement[:, 1, 0], static_displacement / (1 - ratio**2), rtol=5e-10)


def test_undriven_antisymmetric_resonance_of_supported_solids():
    # Replicate the two-coordinate fixture to exercise the sparse singularity check.
    tetrahedron = np.vstack([np.zeros(3), np.eye(3)])
    copies = 18
    mesh = Mesh3D(np.vstack([tetrahedron + [2*i, 0, 0] for i in range(copies)]),
                  np.arange(4*copies).reshape(-1, 4))
    supports = fixed(range(mesh.num_nodes))
    free_nodes = mesh.tets[:, 1:3].ravel()
    for node in free_nodes:
        del supports[node, 2]
    young, density = 8.0, 1.0
    parameters = dict(youngs_modulus=young, poisson_ratio=0.0, mass_density=density,
                      prescribed_displacement=supports, body_force_density=(0.0, 0.0, 1.0))
    # Shapes x and y moving along z give equal diagonal shear stiffness k and no
    # stiffness coupling. The two mass eigenvalues are m/2 (odd) and 3m/2 (even).
    # A uniform body load drives only the even mode, so even zero residual at the
    # odd-mode frequency cannot establish a unique solution.
    volume = 1 / 6
    stiffness, mass = young * volume / 2, density * volume / 10
    odd_frequency = np.sqrt(stiffness / (0.5 * mass)) / (2 * np.pi)
    with pytest.raises(ValueError, match="singular"):
        solve_structural_harmonic_3d(mesh, **parameters, frequency=[odd_frequency])
    frequency = odd_frequency * 1.0001
    nearby = solve_structural_harmonic_3d(mesh, **parameters, frequency=[frequency])
    even_displacement = (volume / 4) / (stiffness - 1.5 * mass * (2 * np.pi * frequency)**2)
    np.testing.assert_allclose(nearby.displacement[0, free_nodes, 2], even_displacement, rtol=1e-10)


def test_omitted_loads_and_fully_prescribed_body(oscillator):
    mesh, parameters = oscillator
    unloaded = solve_structural_harmonic_3d(mesh, **parameters, frequency=[0.0, 0.2])
    for field in (unloaded.displacement, unloaded.stress, unloaded.reaction_force, unloaded.relative_residual):
        np.testing.assert_array_equal(field, 0.0)

    parameters["prescribed_displacement"] = fixed(range(4))
    body = np.array([0.5j, 2.0, 3.0 - 1.0j])
    held = solve_structural_harmonic_3d(mesh, **parameters, frequency=[0.0, 1.0], body_force_density=body)
    np.testing.assert_array_equal(held.displacement, 0.0)
    np.testing.assert_array_equal(held.stress, 0.0)
    np.testing.assert_array_equal(held.relative_residual, 0.0)
    np.testing.assert_allclose(held.reaction_force, np.tile(-body / 24, (2, 4, 1)))


@pytest.mark.parametrize("override", [
    {"frequency": 2.0}, {"frequency": []}, {"frequency": [[1.0]]}, {"frequency": [-0.1]},
    {"frequency": [np.nan]}, {"frequency": [1 + 0.1j]}, {"frequency": [False]},
    {"mass_proportional_damping_coefficient": -0.1}, {"stiffness_proportional_damping_coefficient": np.inf},
    {"mass_density": 0.0}, {"prescribed_displacement": {}},
    {"body_force_density": (1.0, 2.0)}, {"body_force_density": (1.0, 0.0, np.inf * 1j)},
    {"traction": {"missing_face": (1.0, 0.0, 0.0)}},
])
def test_invalid_inputs(oscillator, override):
    mesh, parameters = oscillator
    with pytest.raises(ValueError):
        solve_structural_harmonic_3d(mesh, **(parameters | {"frequency": [1.0]} | override))


def test_missing_frequency(oscillator):
    mesh, parameters = oscillator
    with pytest.raises(TypeError, match="frequency"):
        solve_structural_harmonic_3d(mesh, **parameters)


def test_nonzero_prescribed_displacement(oscillator):
    mesh, parameters = oscillator
    parameters["prescribed_displacement"][0, 0] = 1.0
    with pytest.raises(ValueError):
        solve_structural_harmonic_3d(mesh, **parameters, frequency=[0.1])


def test_damped_axial_wave_converges_to_continuum_solution():
    length, width = 1.0, 0.25
    young, density, omega = 9.0, 1.0, 3.6
    alpha, beta = 0.14, 0.015
    traction = 1.0 + 0.4j
    # With nu=0 the supported rod admits pure axial motion. Its total end traction
    # is (1-i omega beta) E u'(L), while the reported elastic stress is E u'(x).
    modulus = young * (1 - 1j * omega * beta)
    wave_number = np.sqrt(density * (omega**2 + 1j * omega * alpha) / modulus)
    amplitude = traction / (modulus * wave_number * np.cos(wave_number * length))
    errors = []
    for n in (1, 2, 4):
        mesh = box_mesh(length, width, width, 4*n, n, n)
        supports = fixed(range(mesh.num_nodes), axes=(1, 2))
        supports.update(fixed(mesh.boundary["x0"], axes=(0,)))
        result = solve_structural_harmonic_3d(
            mesh, youngs_modulus=young, poisson_ratio=0.0, mass_density=density, prescribed_displacement=supports,
            frequency=[omega / (2 * np.pi)], traction={"x1": (traction, 0.0, 0.0)},
            mass_proportional_damping_coefficient=alpha, stiffness_proportional_damping_coefficient=beta,
        )
        x = mesh.nodes[:, 0]
        exact_u = amplitude * np.sin(wave_number * x)
        centroid = x[mesh.tets].mean(axis=1)
        exact_stress = young * amplitude * wave_number * np.cos(wave_number * centroid)
        errors.append([np.linalg.norm(result.displacement[0, :, 0] - exact_u) / np.linalg.norm(exact_u),
                       np.linalg.norm(result.stress[0, :, 0, 0] - exact_stress) / np.linalg.norm(exact_stress)])
    errors = np.array(errors)
    assert np.all(errors[1:] < [0.45, 0.66] * errors[:-1]), errors
    assert np.all(errors[-1] < [0.007, 0.025]), errors
