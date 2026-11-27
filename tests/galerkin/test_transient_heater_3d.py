# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Spatial and temporal acceptance for the three-stage pulsed heater."""

import numpy as np
import pytest

from transient_heater_3d import (
    AMBIENT, END, EXPANSION, LENGTH, OFF, ON, THERMAL_CONDUCTIVITY,
    VOLUMETRIC_HEAT_CAPACITY, WIDTH, YOUNG, axial_history, slab_reference,
    solve_heater_heat, solve_heater_history,
)

# Normalize by the peak exact signal across the entire history, including switch times.
_TEMPERATURE_LIMIT = 0.06
_STRESS_LIMIT = 0.06
_REACTION_LIMIT = 0.06


def test_reference_pulse_continuity_diffusion_and_spatial_mean():
    times = [0.0, ON, ON + 1e-9, OFF - 1e-9, OFF, OFF + 1e-9, END]
    x = np.linspace(0, LENGTH, 41)
    rise, mean = slab_reference(times, x)
    np.testing.assert_array_equal(rise[:2], 0)
    np.testing.assert_array_equal(rise[:, [0, -1]], 0)
    np.testing.assert_allclose(rise[3], rise[4], rtol=0, atol=2e-9)
    np.testing.assert_allclose(rise[4], rise[5], rtol=0, atol=2e-9)
    assert 0 < mean[2] < mean[-1] < mean[4]
    # Independent volume integration of the temperature series.
    points, weights = np.polynomial.legendre.leggauss(64)
    sampled, _ = slab_reference([2.0, OFF, END], LENGTH * (1 + points) / 2)
    _, average = slab_reference([2.0, OFF, END], [LENGTH / 2])
    np.testing.assert_allclose(sampled @ weights / 2, average, rtol=1e-7)

    # Check the dimensional heat equation at an interior point on each side of cutoff.
    dt, dx = 1e-4, 1e-5
    x0 = LENGTH / 3
    for t, source in ((2.0, 1000.0), (4.0, 0.0)):
        theta, _ = slab_reference(t + np.array([-dt, 0, dt]), x0 + np.array([-dx, 0, dx]))
        derivative = (theta[2, 1] - theta[0, 1]) / (2 * dt)
        curvature = (theta[1, 0] - 2 * theta[1, 1] + theta[1, 2]) / dx**2
        balance = VOLUMETRIC_HEAT_CAPACITY * derivative - THERMAL_CONDUCTIVITY * curvature
        # Twice differentiating a truncated sine series exposes the source tail.
        assert balance == pytest.approx(source, abs=1.0 if source else 1e-3)


def test_reference_pulse_series_tail_and_late_decay():
    x = np.linspace(0, LENGTH, 21)
    times = [ON + 1 / 64, 2.0, OFF, OFF + 1 / 64, END]
    rise, mean = slab_reference(times, x)
    fine_rise, fine_mean = slab_reference(times, x, modes=801)
    np.testing.assert_allclose(rise, fine_rise, rtol=0, atol=1e-7)
    np.testing.assert_allclose(mean, fine_mean, rtol=0, atol=1e-9)
    # Long after turn-off the first Dirichlet eigenmode is the surviving mode.
    _, far_mean = slab_reference([END, END + 1], x)
    decay = THERMAL_CONDUCTIVITY / VOLUMETRIC_HEAT_CAPACITY * (np.pi / LENGTH)**2
    assert far_mean[1] / far_mean[0] == pytest.approx(np.exp(-decay), rel=1e-7)


def _temperature_error(mesh, time, temperature):
    exact, _ = slab_reference(time, mesh.nodes[:, 0])
    return np.max(abs(temperature - AMBIENT - exact)) / np.max(exact)


def test_heater_full_field_and_support_history():
    mesh, electric, heat, solid = solve_heater_history()
    assert electric.inward_electric_power == pytest.approx(0.5, rel=1e-10)
    np.testing.assert_allclose(electric.joule_power_density, 1000.0, rtol=1e-10)
    assert mesh.volumes() @ electric.joule_power_density == pytest.approx(0.5, rel=1e-10)
    np.testing.assert_array_equal(solid.time, heat.time)
    assert heat.temperature.shape == (len(heat.time), mesh.num_nodes)
    assert heat.units["time"] == "s" and heat.units["temperature"] == "K"
    assert len(solid.steps) == len(heat.time)
    assert solid.steps[0].units["stress"] == "Pa"
    assert solid.steps[0].units["reaction_force"] == "N"

    on, off = (int(np.flatnonzero(heat.time == t)[0]) for t in (ON, OFF))
    np.testing.assert_allclose(heat.temperature[:on + 1], AMBIENT, rtol=0, atol=1e-9)
    expected_power = np.zeros(len(heat.time) - 1)
    expected_power[on:off] = 0.5  # W, from independent Ohm's law
    generated = heat.generated_heat_rate.sum(axis=1)
    cooling = -heat.reaction_heat_rate.sum(axis=1)
    dt = np.diff(heat.time)
    np.testing.assert_allclose(generated, expected_power, rtol=1e-10, atol=1e-12)
    assert dt @ generated == pytest.approx(1.0, rel=1e-10)  # J
    np.testing.assert_allclose(np.diff(heat.stored_heat), dt * (generated - cooling), atol=1e-10)
    end_nodes = np.r_[mesh.boundary["x0"], mesh.boundary["x1"]]
    np.testing.assert_allclose(heat.temperature[:, end_nodes], AMBIENT, rtol=0, atol=1e-9)
    volume_weights = mesh.volumes() / mesh.volumes().sum()
    mean_rise = (heat.temperature[:, mesh.tets].mean(axis=2) - AMBIENT) @ volume_weights
    assert 0 < mean_rise[on + 1] < mean_rise[off - 1] < mean_rise[off]
    assert np.all(np.diff(mean_rise[off:]) < 0)

    stress, reaction = axial_history(mesh, solid)
    np.testing.assert_allclose(stress[:on + 1], 0, rtol=0, atol=1e-3)
    np.testing.assert_allclose(reaction[:on + 1], 0, rtol=0, atol=1e-5)
    assert stress[off] < stress[off + 1] < 0
    assert np.all(np.diff(stress[off:]) > 0)
    assert 0 < -stress[-1] < 0.25 * -stress[off]
    assert np.all(reaction[on + 1:, 0] > 0) and np.all(reaction[on + 1:, 1] < 0)
    np.testing.assert_allclose(reaction.sum(axis=1), 0, rtol=0, atol=1e-6)

    _, exact_mean = slab_reference(heat.time, [LENGTH / 2])
    exact_stress = -YOUNG * EXPANSION * exact_mean
    exact_reaction = WIDTH**2 * exact_stress[:, None] * np.array([-1, 1])
    stress_error = np.max(abs(stress - exact_stress)) / np.max(abs(exact_stress))
    reaction_error = np.max(abs(reaction - exact_reaction)) / np.max(abs(exact_reaction))
    temperature_error = _temperature_error(mesh, heat.time, heat.temperature)
    print("Normalized full-history errors (temperature, stress, reaction):",
          temperature_error, stress_error, reaction_error)
    assert temperature_error < _TEMPERATURE_LIMIT
    assert stress_error < _STRESS_LIMIT
    assert reaction_error < _REACTION_LIMIT


def test_heater_separate_space_and_time_refinement():
    spatial_errors, temporal_errors = [], []
    # For spatial refinement use the same fine time grid. Evaluate at common times
    # in all runs so that changing the sample set cannot manufacture convergence.
    for nx in (4, 8, 16):
        mesh, _, heat = solve_heater_heat(nx, 64)
        spatial_errors.append(_temperature_error(mesh, heat.time[::16], heat.temperature[::16]))
    for steps_per_second in (4, 8, 16):
        mesh, _, heat = solve_heater_heat(24, steps_per_second)
        step = steps_per_second // 4
        temporal_errors.append(_temperature_error(mesh, heat.time[::step], heat.temperature[::step]))
    print("Normalized field errors (space, time):", spatial_errors, temporal_errors)
    assert spatial_errors[2] < spatial_errors[1] < spatial_errors[0]
    assert temporal_errors[2] < temporal_errors[1] < temporal_errors[0]
