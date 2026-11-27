# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent analytical and dense-matrix checks of the 3D transient solver."""
import numpy as np
import pytest
from scipy.linalg import eigh

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.transient_heat3d import solve_transient_heat_3d


def test_insulated_pulse_with_nonuniform_steps_and_region_properties():
    box = box_mesh(2, 1, 1, 2, 1, 1)
    right = box.nodes[box.tets, 0].mean(axis=1) > 1
    mesh = Mesh3D(box.nodes, box.tets, regions=right.astype(int), region_names=["left", "right"])
    times = np.array([0., .25, .75, 1., 1.5, 2.])
    calls = []

    def heater(midpoint):
        calls.append(midpoint)
        return np.where(right, 24., 12.) if .25 < midpoint < 1. else 0.

    result = solve_transient_heat_3d(
        mesh, thermal_conductivity={"left": 1., "right": 7.},
        volumetric_heat_capacity={"left": 3., "right": 6.}, time=times,
        initial_temperature=np.full(mesh.num_nodes, 300.), heat_source_density=heater)
    np.testing.assert_array_equal(calls, [.125, .5, .875, 1.25, 1.75])
    expected = 300 + np.array([0., 0., 2., 3., 3., 3.])
    np.testing.assert_allclose(result.temperature, expected[:, None] * np.ones(mesh.num_nodes),
                               rtol=0, atol=1e-12)
    np.testing.assert_allclose(result.generated_heat_rate.sum(axis=1), [0, 36, 36, 0, 0], atol=1e-13)
    np.testing.assert_allclose(np.diff(result.stored_heat), [0, 18, 9, 0, 0], atol=1e-12)
    np.testing.assert_allclose(result.heat_storage_rate, result.generated_heat_rate, atol=1e-13)
    np.testing.assert_array_equal(result.reaction_heat_rate, 0)
    assert not result.temperature.flags.writeable


def test_consistent_mass_eigenmode_and_backward_euler_first_order():
    nodes = np.vstack((np.zeros(3), np.eye(3)))
    mesh = Mesh3D(nodes, [[0, 1, 2, 3]])
    gradients = np.vstack((-np.ones(3), np.eye(3)))
    mass = (np.ones((4, 4)) + np.eye(4)) / 120
    stiffness = gradients @ gradients.T / 6
    eigenvalues, eigenvectors = eigh(stiffness, mass)
    decay = eigenvalues[1]
    mode = eigenvectors[:, 1]
    stop = 1 / decay
    errors = []
    for intervals in (8, 16, 32):
        result = solve_transient_heat_3d(mesh, thermal_conductivity=1., volumetric_heat_capacity=1.,
                                         time=np.linspace(0, stop, intervals + 1),
                                         initial_temperature=300 + mode)
        discrete = 300 + (1 + 1 / intervals) ** -intervals * mode
        np.testing.assert_allclose(result.temperature[-1], discrete, rtol=0, atol=1e-12)
        errors.append(np.linalg.norm(result.temperature[-1] - (300 + np.exp(-1) * mode)))
    assert np.all(np.array(errors[:-1]) / errors[1:] > 1.9)


def test_mixed_fixed_boundaries_and_heat_balance():
    mesh = box_mesh(1, 1, 1, 3, 2, 2)
    x = mesh.nodes[:, 0]
    # k=2, T=300+3x. Right outward flux -6, split between inward load
    # (-8 outward) and Robin (+2 outward). Left reaction is -6 W.
    result = solve_transient_heat_3d(
        mesh, thermal_conductivity=2., volumetric_heat_capacity=9., time=[0, .2, 1.],
        initial_temperature=300 + 3 * x, prescribed_temperature=dict.fromkeys(mesh.boundary["x0"], 300.),
        inward_heat_flux={"x1": 8.}, convection={"x1": (2., 302.)})
    np.testing.assert_allclose(result.temperature, np.tile(300 + 3 * x, (3, 1)), rtol=0, atol=1e-12)
    for field, total in (("outward_prescribed_heat_rate", -8), ("outward_convective_heat_rate", 2),
                         ("reaction_heat_rate", -6), ("heat_storage_rate", 0)):
        np.testing.assert_allclose(getattr(result, field).sum(axis=1), total, atol=1e-12)


@pytest.mark.parametrize(("override", "message"), [
    ({"time": [0, 0, 1]}, "strictly positive"),
    ({"time": [0, np.nan]}, "finite"),
    ({"volumetric_heat_capacity": 0}, "volumetric_heat_capacity"),
    ({"initial_temperature": 300}, "shape"),
    ({"prescribed_temperature": {0: 301}}, "must match"),
    ({"inward_heat_flux": {"missing": 1}}, "exterior face tag"),
    ({"heat_source_density": lambda _: [1.]}, "per tetrahedron"),
])
def test_rejects_invalid_inputs(override, message):
    mesh = box_mesh(1, 1, 1, 1, 1, 1)
    args = dict(thermal_conductivity=1., volumetric_heat_capacity=1., time=[0, 1],
                initial_temperature=np.full(mesh.num_nodes, 300.))
    with pytest.raises(ValueError, match=message):
        solve_transient_heat_3d(mesh, **(args | override))


def test_robin_cools_and_closes_storage_ledger():
    mesh = box_mesh(1, 1, 1, 2, 2, 2)
    result = solve_transient_heat_3d(
        mesh, thermal_conductivity=2., volumetric_heat_capacity=5., time=[0., .25, .75, 1.],
        initial_temperature=np.full(mesh.num_nodes, 320.), convection={"x1": (3., 300.)})
    assert np.all(np.diff(result.stored_heat) < 0)
    outward = result.outward_convective_heat_rate.sum(axis=1)
    np.testing.assert_allclose(np.diff(result.stored_heat), -np.diff(result.time) * outward, atol=1e-12)
    np.testing.assert_allclose(result.residual_heat_rate, 0, atol=1e-12)
