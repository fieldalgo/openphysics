# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed-form powered-bar reference for the one-way three-physics example."""

import numpy as np
import pytest

from electrothermomechanical_3d import solve_bar_displacement, solve_electrothermal_bar

# Reference inputs in SI, independently of the example's assembly and results.
_LENGTH, _AREA = 0.2, 0.05**2
_VOLTAGE, _SIGMA = 2.0, 10.0
_K, _H, _AMBIENT = 2.0, 20.0, 300.0
_YOUNG, _ALPHA = 70e9, 1.2e-5
_RESOLUTIONS = (4, 8, 16)
_Q = _SIGMA * (_VOLTAGE / _LENGTH)**2
_CURVATURE = _Q / (2.0 * _K)
_SLOPE = (_Q * _LENGTH + _H * _CURVATURE * _LENGTH**2) / (_K + _H * _LENGTH)
_MEAN_RISE = _SLOPE * _LENGTH / 2 - _CURVATURE * _LENGTH**2 / 3
_PEAK_RISE = _SLOPE**2 / (4 * _CURVATURE)
_AXIAL_STRESS = -_YOUNG * _ALPHA * _MEAN_RISE


def _rise(x):
    return _SLOPE * x - _CURVATURE * x**2


def _axial_displacement(x):
    # Integrate u' = alpha * (T - Tref - average rise) with u(0) = 0.
    return _ALPHA * (_SLOPE * x**2 / 2 - _CURVATURE * x**3 / 3 - _MEAN_RISE * x)


@pytest.fixture(scope="module")
def bars():
    return [solve_electrothermal_bar(nx) for nx in _RESOLUTIONS]


def test_dc_to_heat_balance_and_convergence(bars):
    current = _SIGMA * _AREA * _VOLTAGE / _LENGTH
    power = current * _VOLTAGE
    temperature_errors = []
    for mesh, electric, heat in bars:
        np.testing.assert_allclose(electric.electric_potential, _VOLTAGE * (1 - mesh.nodes[:, 0] / _LENGTH),
                                   rtol=0, atol=1e-11)
        np.testing.assert_allclose([electric.inward_current["x0"], electric.inward_current["x1"]],
                                   [current, -current], rtol=1e-9)
        np.testing.assert_allclose(electric.joule_power_density, _Q, rtol=1e-9)
        np.testing.assert_array_equal(heat.heat_source_density, electric.joule_power_density)
        face_ids = mesh.tagged_faces["x1"]
        faces = mesh.nodes[face_ids]
        area = np.linalg.norm(np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0]), axis=1) / 2
        convection = _H * (area @ (heat.temperature[face_ids].mean(axis=1) - _AMBIENT))
        left_out = -heat.reaction_heat_rate.sum()
        np.testing.assert_allclose(
            [electric.inward_electric_power, mesh.volumes() @ electric.joule_power_density,
             heat.generated_heat_rate.sum(), left_out + convection], power, rtol=1e-9,
        )
        np.testing.assert_allclose(heat.outward_convective_heat_rate.sum(), convection, rtol=1e-9)
        assert convection > 0 and left_out > 0
        assert electric.units["joule_power_density"] == "W/m^3"
        assert heat.units["temperature"] == "K"
        assert heat.units["outward_convective_heat_rate"] == "W"
        error = np.max(abs(heat.temperature - _AMBIENT - _rise(mesh.nodes[:, 0]))) / _PEAK_RISE
        temperature_errors.append(error)
    print("Normalized temperature errors:", temperature_errors)
    assert temperature_errors[2] < temperature_errors[1] < temperature_errors[0]
    assert temperature_errors[-1] < 0.02
    # The finest mesh also recovers the physical partition of outgoing heat.
    np.testing.assert_allclose([convection, left_out],
                               [_H * _AREA * _rise(_LENGTH), _K * _AREA * _SLOPE], rtol=0.02)


def test_heat_to_thermoelasticity_fields_and_end_reactions(bars):
    displacement_errors, stress_errors, strain_errors = [], [], []
    end_force = -_AXIAL_STRESS * _AREA
    # The nonzero stationary point lies where u' vanishes in the interior.
    extrema = np.roots([_CURVATURE, -_SLOPE, _MEAN_RISE])
    peak_displacement = np.max(abs(_axial_displacement(extrema)))
    for mesh, _, heat in bars:
        solid = solve_bar_displacement(mesh, heat)
        left, right = (mesh.boundary[tag] for tag in ("x0", "x1"))
        assert solid.displacement.shape == solid.reaction_force.shape == (mesh.num_nodes, 3)
        assert solid.strain.shape == solid.stress.shape == (mesh.num_tets, 3, 3)
        for name, unit in {"displacement": "m", "strain": "1", "stress": "Pa", "reaction_force": "N"}.items():
            assert solid.units[name] == unit
        np.testing.assert_allclose(solid.displacement[:, 1:], 0, atol=1e-14)
        np.testing.assert_allclose(solid.displacement[np.r_[left, right], 0], 0, atol=1e-14)
        np.testing.assert_allclose(solid.strain, solid.strain.swapaxes(1, 2), atol=1e-14)
        np.testing.assert_allclose(solid.stress, solid.stress.swapaxes(1, 2), atol=1e-7)
        displacement = solid.displacement[:, 0]
        axial_stress = solid.stress[:, 0, 0]
        assert np.min(displacement) < 0
        assert np.all(axial_stress < 0)
        reactions = solid.reaction_force
        forces = np.array([reactions[left, 0].sum(), reactions[right, 0].sum()])
        assert forces[0] > 0 > forces[1]
        np.testing.assert_allclose(reactions.sum(axis=0), 0, atol=1e-8 * end_force)
        x = mesh.nodes[:, 0]
        # Exact means of x and x^2 over each tetrahedron by barycentric moments.
        cell_x = x[mesh.tets]
        mean_x2 = (cell_x.sum(axis=1)**2 + (cell_x**2).sum(axis=1)) / 20
        cell_rise = _SLOPE * cell_x.mean(axis=1) - _CURVATURE * mean_x2
        strain_reference = np.zeros_like(solid.strain)
        strain_reference[:, 0, 0] = _ALPHA * (cell_rise - _MEAN_RISE)
        strain_errors.append(np.max(abs(solid.strain - strain_reference)) / (_ALPHA * _PEAK_RISE))
        stress_reference = _YOUNG * (strain_reference - _ALPHA * cell_rise[:, None, None] * np.eye(3))
        displacement_errors.append(np.max(abs(displacement - _axial_displacement(x))) / peak_displacement)
        stress_errors.append(np.max(abs(solid.stress - stress_reference)) / abs(_AXIAL_STRESS))
    print("Normalized displacement, strain and stress errors:", displacement_errors, strain_errors, stress_errors)
    assert displacement_errors[2] < displacement_errors[1] < displacement_errors[0]
    assert strain_errors[2] < strain_errors[1] < strain_errors[0]
    assert strain_errors[-1] < 0.15
    assert stress_errors[2] < stress_errors[1] < stress_errors[0]
    assert displacement_errors[-1] < 0.05
    assert stress_errors[-1] < 0.15
    np.testing.assert_allclose(forces, [end_force, -end_force], rtol=0.03)
