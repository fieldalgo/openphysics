# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent analytical, conservation, convergence and input-contract gates."""
import numpy as np
import pytest

from galerkin.electric import solve_steady_electric
from galerkin.mesh import Mesh, rectangle_mesh, layered_rectangle_mesh


def voltage(mesh, left=2., right=0.):
    return {int(i): left for i in mesh.boundary['left']} | {
        int(i): right for i in mesh.boundary['right']}


def balance(r):
    np.testing.assert_allclose(r.supplied_power_per_length, r.joule_power_per_length, rtol=1e-10)
    np.testing.assert_allclose(r.joule_load.sum(), r.joule_power_per_length, rtol=1e-13)
    assert abs(np.sum(r.reaction-r.prescribed_outward_load)) <= 1e-10*max(
        np.sum(abs(r.reaction)+abs(r.prescribed_outward_load)), np.finfo(float).tiny)


def test_slab_fields_reactions_units_and_snapshot():
    m = rectangle_mesh(2., .7, 8, 5)
    r = solve_steady_electric(m, conductivity=3., dirichlet=voltage(m))
    np.testing.assert_allclose(r.potential, 2-m.nodes[:, 0], atol=1e-10)
    np.testing.assert_allclose(r.electric_field, np.tile([1., 0.], (m.num_triangles, 1)), atol=1e-10)
    np.testing.assert_allclose(r.current_density, 3*r.electric_field, atol=1e-10)
    np.testing.assert_allclose(r.joule_heating, 3., atol=1e-10)
    np.testing.assert_allclose(r.reaction[m.boundary['left']].sum(), 2.1, rtol=1e-10)
    np.testing.assert_allclose(r.reaction[m.boundary['right']].sum(), -2.1, rtol=1e-10)
    np.testing.assert_allclose(r.joule_power_per_length, 4.2, rtol=1e-10)
    balance(r)
    expected_nodes = m.nodes.copy()
    m.nodes[:] += 20
    m.boundary['left'][:] = 0
    np.testing.assert_array_equal(r.mesh.nodes, expected_nodes)
    for a in (r.potential, r.electric_field, r.current_density, r.conductivity,
              r.joule_heating, r.joule_load, r.reaction, r.residual,
              r.prescribed_outward_load, r.mesh.nodes, r.mesh.triangles,
              r.mesh.boundary['left'], r.mesh.boundary_edges['left']):
        assert not a.flags.writeable


@pytest.mark.parametrize('direction', ['series', 'parallel'])
def test_two_material_interfaces(direction):
    m = layered_rectangle_mesh([.4, 1.], .5, [4, 6], 5, ['a', 'b'])
    sigma = {'a': 2., 'b': 8.}
    x = m.nodes[:, 0]
    if direction == 'series':
        bc = voltage(m, 3., 0.)
        j = 3/(.4/2+.6/8)
        exact = 3-j*(np.minimum(x, .4)/2+np.maximum(x-.4, 0)/8)
        expected_j = np.tile([j, 0.], (m.num_triangles, 1))
        expected_q = j*j/m.by_region(sigma)
        power = 3*j*.5
    else:
        bc = {int(i): 1. for i in m.boundary['bottom']} | {
            int(i): 0. for i in m.boundary['top']}
        exact = 1-2*m.nodes[:, 1]
        expected_j = np.column_stack([np.zeros(m.num_triangles), 2*m.by_region(sigma)])
        expected_q = 4*m.by_region(sigma)
        power = 2*(.4*2+.6*8)
    r = solve_steady_electric(m, conductivity=sigma, dirichlet=bc)
    np.testing.assert_allclose(r.potential, exact, atol=1e-10)
    np.testing.assert_allclose(r.current_density, expected_j, atol=1e-10)
    np.testing.assert_allclose(r.joule_heating, expected_q, rtol=1e-10)
    np.testing.assert_allclose(r.joule_power_per_length, power, rtol=1e-10)
    np.testing.assert_array_equal(r.mesh.regions, m.regions)
    balance(r)


@pytest.mark.parametrize('pure', [False, True])
@pytest.mark.parametrize('offset', [0., 1e8])
def test_current_sign_gauge_and_offset_invariance(pure, offset):
    m = rectangle_mesh(2., 1., 8, 4)
    m.boundary_edges['right'] = m.boundary_edges['right'][:, ::-1]
    bc = {} if pure else {int(i): offset for i in m.boundary['left']}
    flux = {'right': lambda p, n: 6*n[:, 0]}
    if pure:
        flux['left'] = -6.
    r = solve_steady_electric(m, conductivity=3., dirichlet=bc, outward_current=flux,
                             reference_potential={0: offset} if pure else None)
    np.testing.assert_allclose(r.potential-offset, -2*m.nodes[:, 0], atol=2e-8)
    np.testing.assert_allclose(r.electric_field, np.tile([2., 0.], (m.num_triangles, 1)), atol=1e-10)
    np.testing.assert_allclose(r.joule_power_per_length, 24., rtol=1e-10)
    if pure:
        assert np.count_nonzero(r.reaction) == 0
        assert np.max(abs(r.residual)) < 1e-10
    balance(r)


def test_interior_reference_and_zero_current():
    m = rectangle_mesh(1, 1, 4, 4)
    r = solve_steady_electric(m, conductivity=2, dirichlet={}, reference_potential={12: -7})
    np.testing.assert_array_equal(r.potential, -7*np.ones(25))
    assert not np.any(r.joule_heating)
    assert not np.any(r.reaction)
    assert r.joule_power_per_length == r.supplied_power_per_length == 0


def disconnected():
    a = rectangle_mesh(1, 1, 2, 2)
    n = a.num_nodes
    return Mesh(np.vstack([a.nodes, a.nodes+[2, 0]]),
                np.vstack([a.triangles, a.triangles+n]),
                {k: v.copy() for k, v in a.boundary.items()} | {
                    k+'2': v+n for k, v in a.boundary.items()},
                {k: v.copy() for k, v in a.boundary_edges.items()} | {
                    k+'2': v+n for k, v in a.boundary_edges.items()})


def test_disconnected_components_need_independent_compatibility_and_gauges():
    m = disconnected()
    with pytest.raises(ValueError, match='incompatible Neumann'):
        solve_steady_electric(m, conductivity=1, dirichlet={},
                             outward_current={'left': -1., 'right2': 1.},
                             reference_potential={0: 0., 9: 0.})
    r = solve_steady_electric(m, conductivity=1, dirichlet={0: 3.},
                             outward_current={'left2': -1., 'right2': 1.},
                             reference_potential={9: 8.})
    np.testing.assert_allclose(r.potential[:9], 3., atol=1e-10)
    np.testing.assert_allclose(r.potential[9:], 8-(m.nodes[9:, 0]-2), atol=1e-10)
    balance(r)


@pytest.mark.parametrize('sigma', [0, -1, np.nan, np.inf, True, 1j, [1, 2], np.eye(2), {'missing': 1}])
def test_invalid_conductivity(sigma):
    m = rectangle_mesh(1, 1, 2, 2)
    with pytest.raises(ValueError):
        solve_steady_electric(m, conductivity=sigma, dirichlet=voltage(m))


@pytest.mark.parametrize('bc,gauge,current,match', [
    ({}, None, None, 'exactly one'),
    ({}, {0: 0, 1: 0}, None, 'exactly one'),
    ({0: 0}, {1: 0}, None, 'unnecessary'),
    ({}, {0: 0}, {'left': 1e-100}, 'incompatible'),
    ({4: 0}, None, None, 'exterior'),
    ({True: 0}, None, None, 'indices'),
    ({0: np.nan}, None, None, 'finite'),
    ({0: [0]}, None, None, 'scalar'),
    ({0: 0}, None, {'bad': 0}, 'unknown'),
    ({0: 0}, None, {'right': lambda p, n: 1.}, 'shape'),
    ({0: 0}, None, {'right': np.inf}, 'finite'),
])
def test_invalid_boundary_or_gauge(bc, gauge, current, match):
    with pytest.raises(ValueError, match=match):
        solve_steady_electric(rectangle_mesh(1, 1, 2, 2), conductivity=1,
                             dirichlet=bc, reference_potential=gauge, outward_current=current)


def test_overlap_duplicate_and_interior_edges_rejected():
    m = rectangle_mesh(1, 1, 2, 2)
    with pytest.raises(ValueError, match='overlaps'):
        solve_steady_electric(m, conductivity=1, dirichlet=voltage(m), outward_current={'left': 0})
    m.boundary_edges['copy'] = m.boundary_edges['right'][:, ::-1]
    with pytest.raises(ValueError, match='duplicate'):
        solve_steady_electric(m, conductivity=1, dirichlet={0: 0},
                             outward_current={'right': 1., 'copy': 1.})
    m.boundary_edges['interior'] = np.array([[0, 4]])
    with pytest.raises(ValueError, match='incident triangle'):
        solve_steady_electric(m, conductivity=1, dirichlet={0: 0}, outward_current={'interior': 0})


def harmonic(p):
    x, y = p[..., 0], p[..., 1]
    v = np.sin(np.pi*x)*np.sinh(np.pi*y)/np.sinh(np.pi)
    e = -np.pi/np.sinh(np.pi)*np.stack([
        np.cos(np.pi*x)*np.sinh(np.pi*y), np.sin(np.pi*x)*np.cosh(np.pi*y)], axis=-1)
    return v, e


def test_harmonic_interior_norm_convergence_and_power():
    errors = []
    x, w = np.polynomial.legendre.leggauss(6)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    for n in (4, 8, 16, 32):
        m = rectangle_mesh(1, 1, n, n)
        ids = np.unique(np.concatenate(list(m.boundary.values())))
        bc = {int(i): harmonic(m.nodes[i])[0] for i in ids}
        r = solve_steady_electric(m, conductivity=2., dirichlet=bc)
        points = np.einsum('qa,tad->tqd', bary, m.nodes[m.triangles])
        exact_v, exact_e = harmonic(points)
        v = np.einsum('qa,ta->tq', bary, r.potential[m.triangles])
        dv = (v-exact_v)**2
        de = np.sum((r.electric_field[:, None]-exact_e)**2, axis=-1)
        errors.append([np.sqrt(m.areas()@(dv@weights)), np.sqrt(m.areas()@(de@weights))])
        balance(r)
    rates = np.log2(np.array(errors[:-1])/np.array(errors[1:]))
    print('harmonic L2 errors V/E:', errors, 'rates:', rates.tolist())
    assert np.all(rates[-2:, 0] > 1.8)
    assert np.all(rates[-2:, 1] > .9)
    # Exact boundary work for the harmonic solution: sigma*pi*coth(pi)/2.
    exact_power = np.pi/np.tanh(np.pi)
    assert abs(r.joule_power_per_length/exact_power-1) < .005


def test_field_scaling_sign_and_voltage_offset():
    m = rectangle_mesh(1, 1, 5, 5)
    a = solve_steady_electric(m, conductivity=3, dirichlet=voltage(m, 1., 0.))
    b = solve_steady_electric(m, conductivity=3, dirichlet=voltage(m, 97., 100.))
    np.testing.assert_allclose(b.electric_field, -3*a.electric_field, atol=1e-11)
    np.testing.assert_allclose(b.joule_heating, 9*a.joule_heating, rtol=1e-10)
    balance(b)
