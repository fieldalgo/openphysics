# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import copy

import numpy as np
import pytest
from numpy.testing import assert_allclose

from galerkin.mesh import rectangle_mesh
from galerkin.electric import ElementConductivity, solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.temperature_joule_heating import (
    METHODS, ConductivityModel, JouleConvergenceError, solve_temperature_joule_heat)


def problem(n=8, alpha=.5, **options):
    mesh = rectangle_mesh(1., .25, n, max(2, n//4))
    left, right = mesh.boundary['left'], mesh.boundary['right']
    thermal = {int(i): 300. for i in np.r_[left, right]}
    model = ConductivityModel(lambda t: 1/(1+alpha*(t-300)), (300., 400.))
    args = dict(electrical_conductivity=model, thermal_conductivity=1.,
                electric_dirichlet={int(i): 0. for i in left},
                thermal_dirichlet=thermal, initial_temperature=300.,
                outward_current={'right': 1.}, relaxation=1., max_iterations=200, method='picard')
    args.update(options)
    return mesh, args


@pytest.mark.parametrize('method', METHODS)
def test_constant_limit_and_balances(method):
    mesh, args = problem(alpha=0., method=method)
    actual = solve_temperature_joule_heat(mesh, **args)
    e = solve_steady_electric(mesh, conductivity=1., dirichlet=args['electric_dirichlet'],
                             outward_current=args['outward_current'])
    expected = solve_steady_joule_heat(mesh, electrical_result=e, conductivity=1.,
                                     dirichlet=args['thermal_dirichlet'])
    assert_allclose(actual.coupled.thermal.temperature, expected.thermal.temperature, rtol=1e-10)
    assert_allclose(actual.coupled.electrical.potential, expected.electrical.potential, rtol=1e-10)
    assert len(actual.history) == 2
    for row in actual.history:
        assert abs(row.current_balance) < 1e-10
        assert abs(row.electric_power_defect) < 1e-10
        assert abs(row.heat_power_defect) < 1e-10
    assert not actual.evaluated_temperature.flags.writeable


@pytest.mark.parametrize('method', METHODS)
def test_analytic_mesh_convergence(method):
    errors = []
    current_errors = []
    for n in (8, 16, 32):
        mesh, args = problem(n, method=method)
        result = solve_temperature_joule_heat(mesh, **args)
        x = mesh.nodes[:, 0]
        exact = 300+(np.cos(np.sqrt(.5)*(x-.5))/np.cos(np.sqrt(.5)/2)-1)/.5
        # Three-point triangle quadrature measures the interpolated P1 field,
        # not only superconvergent nodal samples.
        bary = np.array([[2/3, 1/6, 1/6], [1/6, 2/3, 1/6], [1/6, 1/6, 2/3]])
        xq = mesh.nodes[mesh.triangles, 0] @ bary.T
        tq = result.coupled.thermal.temperature[mesh.triangles] @ bary.T
        exact_q = 300+(np.cos(np.sqrt(.5)*(xq-.5))/np.cos(np.sqrt(.5)/2)-1)/.5
        errors.append(np.sqrt(np.mean((tq-exact_q)**2)))
        v_exact = -(np.sin(np.sqrt(.5)*(x-.5))+np.sin(np.sqrt(.5)/2))/(np.sqrt(.5)*np.cos(np.sqrt(.5)/2))
        assert np.max(abs(result.coupled.electrical.potential-v_exact)) < .003
        exact_power = .25*2*np.tan(np.sqrt(.5)/2)/np.sqrt(.5)
        assert abs(result.coupled.source_power_per_length/exact_power-1) < .003
        current_errors.append(np.max(abs(result.coupled.electrical.current_density[:, 0]-1)))
        assert abs(result.history[-1].current_balance) < 1e-10
        assert abs(result.history[-1].heat_power_defect) < 1e-10
    assert np.log2(errors[-2]/errors[-1]) > 1.8
    assert errors[-1] < 2e-4
    assert np.sqrt(np.mean((result.coupled.thermal.temperature-exact)**2)) < 2e-5
    assert current_errors[-1] < current_errors[0]


def test_strong_feedback_and_relaxation():
    results = []
    for relaxation in (1., .5):
        mesh, args = problem(alpha=7., relaxation=relaxation, max_iterations=300)
        result = solve_temperature_joule_heat(mesh, **args)
        results.append(result.coupled.thermal.temperature)
        assert result.history[-1].conductivity_defect <= 1e-10
        assert result.history[-1].nonlinear_heat_residual <= 1e-8
    assert_allclose(*results, rtol=0., atol=2e-8)


def test_nonconvergence_and_small_relaxation_preserve_evidence():
    mesh, args = problem(alpha=7., max_iterations=2, relaxation=1e-12)
    with pytest.raises(JouleConvergenceError, match='maximum iterations') as exc:
        solve_temperature_joule_heat(mesh, **args)
    assert len(exc.value.history) == 2
    assert exc.value.history[-1].temperature_defect > .1
    assert not exc.value.last_temperature.flags.writeable


@pytest.mark.parametrize('model', [
    ConductivityModel(lambda t: np.ones_like(t), (300., 300.01)),
    ConductivityModel(lambda t: -np.ones_like(t), (0., 400.)),
    ConductivityModel(lambda t: np.full_like(t, np.nan), (0., 400.)),
    ConductivityModel(lambda t: 1., (0., 400.)),
    ConductivityModel(lambda t: np.ones_like(t, dtype=complex), (0., 400.)),
])
@pytest.mark.parametrize('method', METHODS)
def test_material_failures(model, method):
    mesh, args = problem(electrical_conductivity=model, method=method)
    with pytest.raises(JouleConvergenceError) as exc:
        solve_temperature_joule_heat(mesh, **args)
    assert exc.value.__cause__ is not None
    assert exc.value.last_temperature.shape == (mesh.num_nodes,)


@pytest.mark.parametrize('conductivity', [-1., np.nan])
@pytest.mark.parametrize('method', METHODS)
def test_invalid_thermal_conductivity_is_wrapped_with_its_cause(conductivity, method):
    # The contract checks k in the first evaluation, not up front: the caller
    # gets JouleConvergenceError (not ValueError) with the ValueError chained,
    # no history, and the state being evaluated, since no heat solution exists.
    mesh, args = problem(thermal_conductivity=conductivity, method=method)
    with pytest.raises(JouleConvergenceError, match='conductivity must') as exc:
        solve_temperature_joule_heat(mesh, **args)
    assert type(exc.value.__cause__) is ValueError
    assert exc.value.history == ()
    expected = np.full(mesh.num_nodes, 300.)
    assert np.array_equal(exc.value.last_temperature, expected)


@pytest.mark.parametrize('option,value', [('relaxation', 0), ('relaxation', 1.1),
    ('relative_tolerance', 0), ('temperature_atol', np.nan),
    ('max_iterations', True), ('max_iterations', 1.5), ('initial_temperature', [300, 301])])
def test_invalid_options(option, value):
    mesh, args = problem(**{option: value})
    with pytest.raises(ValueError):
        solve_temperature_joule_heat(mesh, **args)


def test_element_conductivity_binding():
    mesh, args = problem()
    field = ElementConductivity(mesh, np.ones(mesh.num_triangles))
    changed = copy.deepcopy(mesh)
    changed.nodes[0, 0] += .001
    with pytest.raises(ValueError, match='do not match'):
        field.on_mesh(changed)
    for bad in (np.zeros(mesh.num_triangles), np.full(mesh.num_triangles, np.inf)):
        with pytest.raises(ValueError):
            ElementConductivity(mesh, bad)
    with pytest.raises(ValueError):
        solve_steady_electric(mesh, conductivity=field.values, dirichlet=args['electric_dirichlet'])


def test_element_conductivity_is_labelled_as_conductivity():
    # The values sit in an element Field in S/m, and errors name a conductivity,
    # not the heat source whose machinery the class once reused.
    mesh, _ = problem()
    field = ElementConductivity(mesh, np.ones(mesh.num_triangles))
    assert field._field.unit == 'S/m'
    assert field._field.location == 'element'
    changed = copy.deepcopy(mesh)
    changed.nodes[0, 0] += .001
    with pytest.raises(ValueError, match='^element conductivity .*do not match$'):
        field.on_mesh(changed)
    with pytest.raises(ValueError, match=r'^element conductivity must be finite real shape \(M,\)$'):
        ElementConductivity(mesh, np.ones(mesh.num_triangles + 1))


@pytest.mark.parametrize('method', METHODS)
def test_regions_interface_ranges_and_element_mean(method):
    mesh, args = problem(method=method)
    mesh.regions = (mesh.nodes[mesh.triangles].mean(axis=1)[:, 0] > .5).astype(int)
    mesh.region_names = ('a', 'b')
    seen = []
    def evaluate(t):
        seen.append(t.copy())
        return 1/(1+.5*(t-300))
    model = ConductivityModel(evaluate, (300., 400.))
    args['electrical_conductivity'] = {'a': model, 'b': model}
    result = solve_temperature_joule_heat(mesh, **args)
    expected = 1/(1+.5*(result.evaluated_temperature[mesh.triangles].mean(axis=1)-300))
    assert_allclose(result.coupled.electrical.conductivity, expected, rtol=1e-13)
    args['electrical_conductivity']['b'] = ConductivityModel(evaluate, (300., 300.001))
    with pytest.raises(JouleConvergenceError, match="material 'b'"):
        solve_temperature_joule_heat(mesh, **args)
    args['electrical_conductivity'] = {'a': model}
    with pytest.raises(ValueError, match='exactly'):
        solve_temperature_joule_heat(mesh, **args)


@pytest.mark.parametrize('method', METHODS)
def test_zero_voltage(method):
    mesh, args = problem(outward_current=None, method=method)
    result = solve_temperature_joule_heat(mesh, **args)
    assert len(result.history) == 1
    assert result.coupled.source_power_per_length == 0


@pytest.mark.parametrize('bounds', [(300, 300), (-1, 400), (0, np.inf), (0,), (0, 1j)])
def test_invalid_ranges(bounds):
    with pytest.raises(ValueError):
        ConductivityModel(lambda t: t, bounds)


@pytest.mark.parametrize('method', METHODS)
def test_initial_range_and_callback_exception(method):
    mesh, args = problem(initial_temperature=299., method=method)
    with pytest.raises(JouleConvergenceError, match='outside') as exc:
        solve_temperature_joule_heat(mesh, **args)
    assert exc.value.history == ()
    def broken(t):
        raise RuntimeError('material unavailable')
    args.update(initial_temperature=300., electrical_conductivity=ConductivityModel(broken, (0., 500.)))
    with pytest.raises(JouleConvergenceError, match='material unavailable') as exc:
        solve_temperature_joule_heat(mesh, **args)
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.parametrize('method', METHODS)
def test_zero_power_with_nonuniform_thermal_boundary(method):
    mesh, args = problem(outward_current=None, method=method)
    for i in mesh.boundary['right']:
        args['thermal_dirichlet'][int(i)] = 301.
    result = solve_temperature_joule_heat(mesh, **args)
    assert_allclose(result.coupled.thermal.temperature, 300+mesh.nodes[:, 0], atol=1e-10)
    assert result.history[-1].nonlinear_heat_residual <= 1e-8
