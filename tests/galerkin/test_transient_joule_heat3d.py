# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent interval and power checks for the voltage-driven heater."""
import numpy as np
import pytest

from galerkin import box_mesh
from galerkin.temperature_joule_heating import ConductivityModel
from galerkin.transient_joule_heat3d import solve_transient_joule_heat_3d


def run(*, model, voltage=None, **changes):
    mesh = box_mesh(1., .5, .25, 2, 1, 1)
    options = dict(time=[0., 1., 3., 5.], initial_temperature=np.full(mesh.num_nodes, 300.),
                   electrical_conductivity=model, thermal_conductivity=2., volumetric_heat_capacity=1.,
                   prescribed_electric_potential={"x0": 0., "x1": 2.} if voltage is None else voltage,
                   temperature_tolerance=1e-10)
    options.update(changes)
    return mesh, solve_transient_joule_heat_3d(mesh, **options)


def test_backward_euler_feedback_and_switched_power():
    beta = .02
    model = ConductivityModel(lambda t: 2 / (1 + beta * (t - 300)), (290., 400.))
    calls = []

    def voltage(t):
        calls.append(t)
        return {"x0": 0., "x1": 2. if t < 3 else 0.}

    mesh, result = run(model=model, voltage=voltage, relaxation_factor=.8)
    assert calls == [.5, 2., 4.]
    np.testing.assert_array_equal(result.heat.time, [0., 1., 3., 5.])
    rise = [0.]
    for dt in (1., 2.):
        previous = rise[-1]
        rise.append((beta*previous - 1 + np.sqrt((1 + beta*previous)**2 + 4*beta*dt*8)) / (2*beta))
    rise.append(rise[-1])
    np.testing.assert_allclose(result.heat.temperature, np.repeat((300 + np.array(rise))[:, None],
                                                                mesh.num_nodes, axis=1), rtol=0, atol=2e-10)
    assert len(result.electric) == len(result.iteration_count) == 3
    assert result.units["iteration_count"] == "1"
    assert np.all(result.iteration_count[:2] > 1)
    assert result.iteration_count[2] == 1
    assert result.electric[1].joule_power < result.electric[0].joule_power
    assert result.electric[2].joule_power == 0
    for i, electric in enumerate(result.electric):
        heat = result.heat
        np.testing.assert_allclose(electric.electrical_conductivity,
                                   model.evaluate(heat.temperature[i+1, mesh.tets].mean(axis=1)),
                                   rtol=1e-11, atol=0)
        expected_load = np.bincount(mesh.tets.ravel(), minlength=mesh.num_nodes,
                                    weights=np.repeat(electric.joule_power_density * mesh.volumes() / 4, 4))
        np.testing.assert_allclose(heat.generated_heat_rate[i], expected_load, rtol=1e-13, atol=0)
        assert electric.inward_electric_power == pytest.approx(electric.joule_power, abs=1e-12)
        assert heat.heat_storage_rate[i].sum() == pytest.approx(electric.joule_power, abs=1e-12)


def test_constant_material_with_convection_balances_energy():
    _, result = run(model={"domain": 2.}, convection={"z1": (2., 300.)})
    assert result.heat.outward_convective_heat_rate[0].sum() > 0
    heat = result.heat
    generated = heat.generated_heat_rate.sum(axis=1)
    exported = heat.outward_convective_heat_rate.sum(axis=1)
    np.testing.assert_allclose(np.diff(heat.stored_heat), np.diff(heat.time) * (generated - exported),
                               rtol=0, atol=2e-12)


def test_nonconvergence_has_interval_context():
    model = ConductivityModel(lambda t: 2 / (1 + .02 * (t - 300)), (290., 400.))
    with pytest.raises(ValueError, match="did not converge on interval 0.*after 1 iterations"):
        run(model=model, iteration_limit=1)


def test_model_range_and_invalid_voltage_are_interval_errors():
    model = ConductivityModel(lambda t: np.full_like(t, 2.), (290., 301.))
    with pytest.raises(ValueError, match="interval 0.*(outside|range)"):
        run(model=model)
    invalid = ConductivityModel(lambda t: np.full_like(t, np.nan), (290., 400.))
    with pytest.raises(ValueError, match="interval 0.*finite"):
        run(model=invalid)
    with pytest.raises(ValueError, match="interval 0.*mapping"):
        run(model=2., voltage=lambda _: 2.)


@pytest.mark.parametrize("options", [
    {"temperature_tolerance": 0}, {"relative_tolerance": np.nan},
    {"iteration_limit": False}, {"relaxation_factor": 1.1},
])
def test_invalid_iteration_controls(options):
    with pytest.raises(ValueError):
        run(model=2., **options)
