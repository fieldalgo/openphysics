# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent thermoelastic history checks using analytical temperatures."""
import numpy as np
import pytest

from galerkin import Mesh3D
from galerkin.transient_thermoelasticity3d import solve_thermoelasticity_history_3d

NODES = np.vstack((np.zeros(3), np.eye(3)))
E, NU, ALPHA = 3e9, 0.25, 2e-5
FIXED = dict.fromkeys(np.ndindex(4, 3), 0.0)
SUPPORTS = dict.fromkeys(((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2)), 0.0)


def tet():
    return Mesh3D(NODES.copy(), np.array([[0, 1, 2, 3]]))


def solve(time, temperature, mesh=None, **updates):
    options = dict(stress_free_temperature=300.0, linear_expansion_coefficient=ALPHA,
                   youngs_modulus=E, poisson_ratio=NU, prescribed_displacement=FIXED)
    options.update(updates)
    return solve_thermoelasticity_history_3d(
        tet() if mesh is None else mesh, time=time, temperature=temperature, **options,
    )


def test_heater_on_off_clamped_and_independent_retention():
    # Analytical lumped-temperature history with heating until t=2 and exponential cooldown.
    time = np.array([0., 1., 2., 3., 8., 40.])
    peak = -40 * np.expm1(-2)
    rise = np.where(time <= 2, -40 * np.expm1(-time), peak * np.exp(2 - time))
    temperature = np.repeat((300 + rise)[:, None], 4, axis=1)
    indices = np.array([0, 2, 3, 5])
    result = solve(time, temperature, sample_indices=indices)
    stored = time[indices].copy()
    time[:] = -1
    temperature[:] = 0
    indices[:] = 0
    np.testing.assert_array_equal(result.time, stored)
    assert result.units["time"] == "s"
    assert result.sample_indices == (0, 2, 3, 5)
    gradients = np.vstack((-np.ones(3), np.eye(3)))
    for step, index in zip(result.steps, result.sample_indices, strict=True):
        pressure = E * ALPHA * rise[index] / (1 - 2 * NU)
        np.testing.assert_allclose(step.stress, (-pressure * np.eye(3))[None], atol=1e-7)
        np.testing.assert_allclose(step.reaction_force, -pressure * gradients / 6, atol=1e-7)
    assert np.max(np.abs(result.steps[-1].stress)) < 1e-7
    assert not np.shares_memory(result.steps[1].stress, result.steps[2].stress)


def test_free_expansion_keeps_every_time_including_initial():
    time = [0., 0.1, 2.7, 4.]
    rise = np.array([0., 20., 7., 0.])
    result = solve(time, np.repeat((300 + rise)[:, None], 4, axis=1),
                   prescribed_displacement=SUPPORTS)
    np.testing.assert_array_equal(result.time, time)
    for step, delta in zip(result.steps, rise, strict=True):
        np.testing.assert_allclose(step.displacement, ALPHA * delta * NODES, atol=1e-14)
        np.testing.assert_allclose(step.stress, 0, atol=1e-6)


def test_nonuniform_temperature_with_heterogeneous_materials():
    mesh = Mesh3D(np.vstack((NODES, [0, 0, -1])), np.array([[0, 1, 2, 3], [0, 2, 1, 4]]),
                  regions=np.array([0, 1]), region_names=["top", "bottom"])
    temp = [[300]*5, [300, 310, 320, 350, 290], [300]*5]
    result = solve([0, 2, 4], temp, mesh,
                   prescribed_displacement=dict.fromkeys(np.ndindex(5, 3), 0.0),
                   youngs_modulus={"top": E, "bottom": 2*E},
                   poisson_ratio={"top": NU, "bottom": 0.2},
                   linear_expansion_coefficient={"top": ALPHA, "bottom": -ALPHA})
    pressure = np.array([E * ALPHA * 20 / (1-2*NU), -2*E * ALPHA * 5 / (1-0.4)])
    np.testing.assert_allclose(result.steps[1].stress, -pressure[:, None, None]*np.eye(3), atol=1e-7)
    np.testing.assert_allclose(result.steps[2].stress, 0, atol=1e-7)


@pytest.mark.parametrize("indices", [[], [0, 0], [1, 0], [3], [-1], [True], [0.0], [[0]]])
def test_invalid_selection(indices):
    with pytest.raises(ValueError, match="sample_indices"):
        solve([0, 1, 2], np.full((3, 4), 300.), sample_indices=indices)


@pytest.mark.parametrize(("time", "temperature", "message"), [
    ([], [], "time"), ([0, 0], [[300]*4]*2, "increasing"), ([1, 0], [[300]*4]*2, "increasing"),
    ([0, np.inf], [[300]*4]*2, "time"), ([0], [300]*4, "shape"),
    ([0, 1], [[300]*4, [300, 300, 300, np.nan]], "temperature"),
    ([0, 1], [[300]*4, [300, 300, 300, -1]], "nonnegative"),
])
def test_validates_even_unselected_rows(time, temperature, message):
    with pytest.raises(ValueError, match=message):
        solve(time, temperature, sample_indices=[0])
