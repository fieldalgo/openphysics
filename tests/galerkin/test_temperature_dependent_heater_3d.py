# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent insulated DC feedback limit and lossy switched-heater regression."""

import numpy as np
import pytest

from temperature_dependent_heater_3d import (
    AMBIENT, BETA, END, EXPANSION, OFF, ON, VOLTAGE, WIDTH, YOUNG, axial_history,
    interval_power, solve_heater, uniform_temperature_rise,
)


def test_uniform_reference_energy_and_initial_slope():
    # P0 = 0.5 W, CV = 0.5 J/K, so the accumulated cold-power dose is t K.
    time = np.linspace(0, 2, 65)
    rise = uniform_temperature_rise(time)
    np.testing.assert_allclose(rise + 0.125 * rise**2, time, rtol=2e-15)
    assert uniform_temperature_rise(1e-6) / 1e-6 == pytest.approx(1.0, rel=1e-6)
    assert np.all(np.diff(rise) > 0)
    assert rise[-1] == pytest.approx(4 * (np.sqrt(2) - 1))


def _check_energy(mesh, coupled):
    heat = coupled.heat
    power = interval_power(coupled)
    np.testing.assert_allclose([mesh.volumes() @ step.joule_power_density for step in coupled.electric],
                               power, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(heat.generated_heat_rate.sum(axis=1), power, rtol=1e-9, atol=1e-12)
    loss = (heat.outward_convective_heat_rate + heat.outward_prescribed_heat_rate
            - heat.reaction_heat_rate).sum(axis=1)
    dt = np.diff(heat.time)
    np.testing.assert_allclose(np.diff(heat.stored_heat), dt * (power - loss), rtol=0, atol=1e-9)
    return dt @ power, dt @ loss


def test_insulated_feedback_against_closed_form():
    errors = []
    for intervals in (8, 16, 32):
        time = np.linspace(0, 2, intervals + 1)
        mesh, result, solid = solve_heater(time, insulated=True, nx=4)
        heat = result.heat
        np.testing.assert_array_equal(heat.time, time)
        np.testing.assert_array_equal(solid.time, time)
        rise = heat.temperature.mean(axis=1) - AMBIENT
        np.testing.assert_allclose(heat.temperature - AMBIENT, np.broadcast_to(rise[:, None], heat.temperature.shape),
                                   rtol=0, atol=1e-9)
        assert rise[0] == 0 and np.all(np.diff(rise) > 0)
        exact = uniform_temperature_rise(time)
        errors.append(np.max(abs(rise - exact)))

        # Resistances from the returned end temperatures audit implicit rather than lagged coupling.
        current = np.array([s.inward_current["x0"] for s in result.electric])
        np.testing.assert_allclose(current, 0.25 / (1 + BETA * rise[1:]), rtol=1e-9)
        assert np.all(np.diff(current) < 0)
        np.testing.assert_allclose(interval_power(result), VOLTAGE * current, rtol=1e-9)
        assert np.all(np.asarray(result.iteration_count) > 0)
        energy, loss = _check_energy(mesh, result)
        assert loss == 0
        assert energy == pytest.approx(0.5 * rise[-1], rel=1e-9)

        stress, reaction = axial_history(mesh, solid)
        np.testing.assert_allclose(stress, -YOUNG * EXPANSION * rise, rtol=1e-9, atol=1e-6)
        np.testing.assert_allclose(reaction, WIDTH**2 * stress[:, None] * [-1, 1], rtol=1e-9, atol=1e-8)
    print("Maximum insulated temperature error (K):", errors)
    assert errors[-1] < 0.02
    assert np.all(np.asarray(errors[:-1]) / errors[1:] > 1.8)
    np.testing.assert_allclose(current, 0.25 / (1 + BETA * exact[1:]), rtol=0.005)
    np.testing.assert_allclose(stress, -YOUNG * EXPANSION * exact, rtol=0, atol=0.02 * YOUNG * EXPANSION)


def test_lossy_pulse_feedback_uses_less_energy_and_relaxes():
    time = np.arange(END * 16 + 1) / 16
    on, off = (int(np.flatnonzero(time == t)[0]) for t in (ON, OFF))
    measurements = []
    for feedback in (True, False):
        mesh, result, solid = solve_heater(time, feedback=feedback)
        heat = result.heat
        power = interval_power(result)
        stress, reaction = axial_history(mesh, solid)
        energy, loss = _check_energy(mesh, result)
        assert 0 < loss < energy
        assert np.any(heat.outward_convective_heat_rate[on:] > 0)
        np.testing.assert_allclose(power[:on], 0, rtol=0, atol=1e-12)
        np.testing.assert_allclose(power[off:], 0, rtol=0, atol=1e-12)
        np.testing.assert_allclose(heat.temperature[:on + 1], AMBIENT, rtol=0, atol=1e-9)
        np.testing.assert_allclose(stress[:on + 1], 0, rtol=0, atol=1e-3)
        if feedback:
            cell_rise = heat.temperature[1:, mesh.tets].mean(axis=2) - AMBIENT
            sigma = np.array([step.electrical_conductivity for step in result.electric])
            np.testing.assert_allclose(sigma, 10.0 / (1 + BETA * cell_rise), rtol=1e-9)
            assert np.all(np.diff(power[on:off]) < 0)
        else:
            np.testing.assert_allclose(power[on:off], 0.5, rtol=1e-10)
        peak_rise = heat.temperature.max(axis=1) - AMBIENT
        assert 0 < peak_rise[-1] < peak_rise[off + 1] < peak_rise[off]
        assert np.all(np.diff(stress[off:]) > 0)
        assert stress[off] < stress[-1] < 0
        assert reaction[off, 0] > reaction[-1, 0] > 0
        np.testing.assert_allclose(reaction.sum(axis=1), 0, rtol=0, atol=1e-6)
        measurements.append((energy, peak_rise[off], -stress[off]))
    dependent, constant = np.asarray(measurements)
    assert constant[0] == pytest.approx(1.0, rel=1e-10)
    print("Feedback and constant (J, K, magnitude of mean stress in Pa):", measurements)
    assert np.all(dependent < 0.95 * constant)
