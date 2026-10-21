# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual electrical API → heat: analytical fields, convergence and power."""
import copy
from dataclasses import replace

import numpy as np
import pytest

from galerkin.electric import solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.mesh import rectangle_mesh, layered_rectangle_mesh


def ends(mesh, left, right):
    return {int(i): left for i in mesh.boundary['left']} | {
        int(i): right for i in mesh.boundary['right']}


def uniform(mesh, voltage=2.):
    return solve_steady_electric(mesh, conductivity=3., dirichlet=ends(mesh, 0., voltage))


def couple(mesh, electric, **kwargs):
    return solve_steady_joule_heat(mesh, electrical_result=electric, conductivity=5., **kwargs)


def errors(mesh, result, exact):
    z, w = np.polynomial.legendre.leggauss(8)
    z, w = (z+1)/2, w/2
    a, b = np.meshgrid(z, z, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qi,tij->tqj', bary, mesh.nodes[mesh.triangles])
    temp, flux = exact(points)
    discrete = np.einsum('qi,ti->tq', bary, result.temperature[mesh.triangles])
    measure = mesh.areas()[:, None]*weights
    return [np.sqrt(np.sum(measure*(discrete-temp)**2)),
            np.sqrt(np.sum(measure*np.sum((result.heat_flux[:, None]-flux)**2, axis=-1)))]


@pytest.mark.parametrize('voltage', [0., 2., -2., 6.])
def test_uniform_bar_actual_api_analytical_temperature_and_power(voltage):
    mesh = rectangle_mesh(.02, .01, 16, 8)
    electric = uniform(mesh, voltage)
    result = couple(mesh, electric, dirichlet=ends(mesh, 300., 300.))
    q = 3*(voltage/.02)**2
    exact = 300+q*mesh.nodes[:, 0]*(.02-mesh.nodes[:, 0])/10
    np.testing.assert_allclose(result.thermal.temperature, exact, atol=1e-10, rtol=0)
    np.testing.assert_allclose(result.thermal.load, electric.joule_load, atol=1e-12, rtol=1e-12)
    assert result.source_power_per_length == pytest.approx(q*.02*.01, abs=1e-13)
    assert result.outward_heat_per_length == pytest.approx(q*.02*.01, abs=1e-11)
    assert result.electrical is not electric
    assert not np.shares_memory(result.electrical.joule_heating, electric.joule_heating)
    assert not result.electrical.joule_heating.flags.writeable
    assert not result.electrical.mesh.nodes.flags.writeable


def test_two_series_materials_and_element_order():
    mesh = layered_rectangle_mesh([.01, .03], .01, [8, 16], 8, ['a', 'b'])
    electric = solve_steady_electric(mesh, conductivity={'a': 2., 'b': 8.},
                                     dirichlet=ends(mesh, 0., 2.))
    result = solve_steady_joule_heat(mesh, electrical_result=electric,
                                    conductivity={'a': 3., 'b': 7.},
                                    dirichlet=ends(mesh, 300., 300.))
    d, sigma, k = np.array([.01, .02]), np.array([2., 8.]), np.array([3., 7.])
    current = -2/np.sum(d/sigma); q = current**2/sigma
    f0 = -np.sum((np.array([0., q[0]*d[0]])*d+q*d*d/2)/k)/np.sum(d/k)
    x = mesh.nodes[:, 0]; right = x > d[0]
    exact = 300-(f0*x+q[0]*x*x/2)/k[0]
    interface = 300-(f0*d[0]+q[0]*d[0]**2/2)/k[0]
    u = x[right]-d[0]
    exact[right] = interface-((f0+q[0]*d[0])*u+q[1]*u*u/2)/k[1]
    assert np.max(abs(result.thermal.temperature-exact)) < .01
    np.testing.assert_allclose(electric.joule_heating, q[mesh.regions], rtol=1e-10)
    assert result.source_power_per_length == pytest.approx(.01*np.sum(q*d), rel=1e-10)


def test_actual_harmonic_voltage_coupled_mesh_convergence():
    L, H, sigma, alpha, k = .02, .01, 3., 5000., 5.
    def exact(p):
        return (300+sigma*alpha**2/(3*k)*(L**4+H**4-p[..., 0]**4-p[..., 1]**4),
                4*sigma*alpha**2/3*p**3)
    all_errors, powers = [], []
    for n in (8, 16, 32):
        mesh = rectangle_mesh(L, H, n, n)
        fixed = np.unique(np.concatenate(list(mesh.boundary.values())))
        voltage = alpha*(mesh.nodes[:, 0]**2-mesh.nodes[:, 1]**2)
        electric = solve_steady_electric(mesh, conductivity=sigma,
                                         dirichlet={int(i): voltage[i] for i in fixed})
        temp, _ = exact(mesh.nodes)
        result = couple(mesh, electric, dirichlet={int(i): temp[i] for i in fixed})
        all_errors.append(errors(mesh, result.thermal, exact))
        powers.append(result.source_power_per_length)
        assert abs(result.outward_heat_per_length/result.source_power_per_length-1) < 1e-10
    orders = np.log2(np.array(all_errors[:-1])/all_errors[1:])
    print('actual coupled L2 errors, orders, powers:', all_errors, orders.tolist(), powers)
    assert orders[-1, 0] > 1.8
    assert orders[-1, 1] > .9
    exact_power = 4*sigma*alpha**2*(L**3*H+L*H**3)/3
    assert abs(powers[-1]/exact_power-1) < .002
    assert abs(powers[-1]-exact_power) < abs(powers[0]-exact_power)


@pytest.mark.parametrize('kind', ['robin', 'mixed', 'zero_with_heat_flow', 'neumann_electric'])
def test_actual_api_mixed_thermal_boundaries_and_zero_budget(kind):
    mesh = rectangle_mesh(.02, .01, 8, 4)
    electric = uniform(mesh, 0. if kind == 'zero_with_heat_flow' else 2.)
    if kind == 'neumann_electric':
        electric = solve_steady_electric(mesh, conductivity=3., dirichlet={},
                                         outward_current={'left': 300., 'right': -300.},
                                         reference_potential={0: 0.})
    if kind == 'zero_with_heat_flow':
        result = couple(mesh, electric, dirichlet=ends(mesh, 300., 310.))
    elif kind == 'mixed':
        result = couple(mesh, electric, dirichlet={}, outward_flux={'right': 20.},
                         convection={'left': (100., 300.)})
    else:
        result = couple(mesh, electric, dirichlet={},
                         convection={tag: (100., 300.) for tag in mesh.boundary_edges})
    assert result.outward_heat_per_length == pytest.approx(result.source_power_per_length,
                                                           rel=1e-10, abs=1e-10)


@pytest.mark.parametrize('kind', ['coordinates', 'order', 'regions'])
def test_mismatched_mesh_rejected_before_heat_solve(kind):
    mesh = rectangle_mesh(.02, .01, 4, 2); electric = uniform(mesh)
    if kind == 'coordinates':
        mesh.nodes *= 2
    elif kind == 'order':
        mesh.triangles = mesh.triangles[::-1].copy()
    else:
        mesh.regions = np.zeros(mesh.num_triangles, dtype=int); mesh.region_names = ['new']
    with pytest.raises(ValueError, match='do not match'):
        couple(mesh, electric, dirichlet=ends(mesh, 300., 300.))


@pytest.mark.parametrize('field,value', [('joule_heating', -1.), ('joule_heating', np.nan),
                                       ('joule_load', 99.), ('joule_power_per_length', 99.),
                                       ('supplied_power_per_length', 99.)])
def test_corrupted_actual_result_rejected(field, value):
    mesh = rectangle_mesh(.02, .01, 4, 2); electric = uniform(mesh)
    old = getattr(electric, field)
    bad = replace(electric, **{field: np.full_like(old, value) if np.ndim(old) else value})
    with pytest.raises(ValueError):
        couple(mesh, bad, dirichlet=ends(mesh, 300., 300.))


def test_snapshots_survive_input_mutation_and_missing_support_rejected():
    mesh = rectangle_mesh(.02, .01, 4, 2); electric = uniform(mesh)
    with pytest.raises(ValueError, match='requires Dirichlet or positive Robin'):
        couple(mesh, electric, dirichlet={})
    result = couple(copy.deepcopy(mesh), electric, dirichlet=ends(mesh, 300., 300.))
    expected = result.electrical.mesh.nodes.copy()
    mesh.nodes[:] += 100
    electric.mesh.nodes = np.zeros_like(electric.mesh.nodes)
    np.testing.assert_array_equal(result.electrical.mesh.nodes, expected)
    with pytest.raises(ValueError, match='SteadyElectricResult'):
        couple(mesh, object(), dirichlet={})
