# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Temperature-dependent Joule heating graded against refsol.joule_slab.

A 1 m x 0.25 m rectangle with fixed potentials and temperatures on the left and
right edges and insulated long edges reproduces the one-dimensional slab. The
conductivity model is the linear ``sigma0 (1 + alpha (T - T0))`` the reference
solves exactly, bounded by a range that contains the reference's temperature
extrema. Errors are the RMS over the three-point triangle rule of the
interpolated P1 fields, as in test_temperature_joule_heating.py.

Measured with n = 8, 16, 32 cells along the slab (Picard, relaxation 1):
    alpha = 0.5 /K,   drop 2 V, T 300/300 K: T L2 5.65e-3 1.40e-3 3.50e-4 K (orders 2.01, 2.00)
    alpha = 0.5 /K,   drop 2 V, T 300/304 K: T L2 6.71e-3 1.66e-3 4.13e-4 K (orders 2.02, 2.00)
    alpha = -0.004 /K, drop 5 V, T 300/300 K: T L2 3.32e-2 8.31e-3 2.08e-3 K (orders 2.00, 2.00)
    alpha = -0.004 /K, drop 5 V, T 320/300 K: T L2 3.18e-2 7.96e-3 1.99e-3 K (orders 2.00, 2.00)
with the relative error of the dissipated power 1.1e-4, 1.9e-4, 8.2e-6 and
8.8e-6 at n = 32. The bounds below leave a factor 2.4 or more on the finest
temperature error, 2.5 on the power, and ask for order 1.8.
"""

import numpy as np
import pytest

from galerkin.mesh import rectangle_mesh
from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat
from conftest import rate

BARY = np.array([[2 / 3, 1 / 6, 1 / 6], [1 / 6, 2 / 3, 1 / 6], [1 / 6, 1 / 6, 2 / 3]])
WIDTH = 0.25
SIGMA0, T0, K = 1.0, 300.0, 1.0
CASES = [
    pytest.param(0.5, 2.0, (300.0, 300.0), 1e-3, id="rising-symmetric"),
    pytest.param(0.5, 2.0, (300.0, 304.0), 1e-3, id="rising-asymmetric"),
    pytest.param(-0.004, 5.0, (300.0, 300.0), 5e-3, id="metal-symmetric"),
    pytest.param(-0.004, 5.0, (320.0, 300.0), 5e-3, id="metal-asymmetric"),
]


def solve(n, alpha, drop, temperatures, reference):
    low, high = reference.temperature_range
    model = ConductivityModel(lambda t: SIGMA0 * (1 + alpha * (t - T0)), (low - 50.0, high + 50.0))
    mesh = rectangle_mesh(1.0, WIDTH, n, max(2, n // 4))
    left, right = mesh.boundary["left"], mesh.boundary["right"]
    result = solve_temperature_joule_heat(
        mesh, electrical_conductivity=model, thermal_conductivity=K,
        electric_dirichlet={**{int(i): drop for i in left}, **{int(i): 0.0 for i in right}},
        thermal_dirichlet={**{int(i): temperatures[0] for i in left}, **{int(i): temperatures[1] for i in right}},
        initial_temperature=T0, relaxation=1.0, max_iterations=300, method="picard")
    return mesh, result


def rms(mesh, nodal, exact):
    xq = mesh.nodes[mesh.triangles, 0] @ BARY.T
    return float(np.sqrt(np.mean((nodal[mesh.triangles] @ BARY.T - exact(xq)) ** 2)))


@pytest.mark.parametrize("alpha,drop,temperatures,bound", CASES)
def test_temperature_and_power_converge_to_the_slab_reference(refsol, alpha, drop, temperatures, bound):
    reference = refsol.joule_slab.voltage_driven(1.0, (drop, 0.0), temperatures, SIGMA0, alpha, T0, K)
    assert reference.current_density > 0
    errors, potential_errors, power_errors, current_errors = [], [], [], []
    for n in (8, 16, 32):
        mesh, result = solve(n, alpha, drop, temperatures, reference)
        errors.append(rms(mesh, result.coupled.thermal.temperature, reference.temperature))
        potential_errors.append(rms(mesh, result.coupled.electrical.potential, reference.potential))
        power_errors.append(abs(result.coupled.source_power_per_length / (reference.joule_power * WIDTH) - 1))
        current_errors.append(np.max(abs(result.coupled.electrical.current_density[:, 0] - reference.current_density)))
        assert abs(result.history[-1].current_balance) < 1e-10
        assert result.history[-1].nonlinear_heat_residual <= 1e-8
    assert errors[0] > errors[1] > errors[2]
    assert rate(errors)[-1] > 1.8, f"orders {rate(errors)} for errors {errors}"
    assert errors[-1] < bound
    assert potential_errors[0] > potential_errors[1] > potential_errors[2]
    assert rate(potential_errors)[-1] > 1.8
    assert power_errors[-1] < 5e-4 and power_errors[0] > power_errors[2]
    assert current_errors[0] > current_errors[1] > current_errors[2]


def test_constant_conductivity_limit_matches_the_closed_form(refsol):
    reference = refsol.joule_slab.voltage_driven(1.0, (2.0, 0.0), (300.0, 304.0), SIGMA0, 0.0, T0, K)
    closed = refsol.joule_slab.constant_conductivity(1.0, (2.0, 0.0), (300.0, 304.0), SIGMA0, K)
    x = np.linspace(0, 1, 11)
    assert np.array_equal(reference.temperature(x), closed.temperature(x))
    errors = []
    for n in (8, 16, 32):
        mesh, result = solve(n, 0.0, 2.0, (300.0, 304.0), reference)
        errors.append(rms(mesh, result.coupled.thermal.temperature, reference.temperature))
        # the potential of a constant conductivity is affine and exact on P1
        assert rms(mesh, result.coupled.electrical.potential, reference.potential) < 1e-12
        assert abs(result.coupled.source_power_per_length / (reference.joule_power * WIDTH) - 1) < 1e-12
    assert rate(errors)[-1] > 1.9 and errors[-1] < 1e-3
