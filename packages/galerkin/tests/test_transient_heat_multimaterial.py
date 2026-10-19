# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Per-region conductivity and heat capacity in backward-Euler transient heat.

Reference: refsol.transient_heat_multilayer.LayeredWall, an eigenfunction
series for a layered wall with fixed end temperatures (NumPy only).
"""
import numpy as np
import pytest

from galerkin.mesh import layered_rectangle_mesh, rectangle_mesh
from galerkin.transient_heat import solve_transient_heat
from refsol.transient_heat_multilayer import LayeredWall

NAMES = ['steel', 'insulation']
WALL = dict(interfaces=[.01, .03], conductivities=[45., .5], capacities=[3.6e6, 1.2e6])
STATE = dict(left_temperature=400., right_temperature=300., amplitudes=[60., -25., 10.])
OBSERVE = (10., 40., 120.)


def _by_name(values):
    return dict(zip(NAMES, values))


def _solve(n, dt, wall):
    mesh = layered_rectangle_mesh(WALL['interfaces'], .005, [n, 2*n], n, NAMES)
    times = np.arange(0., OBSERVE[-1]+dt/2, dt)
    initial = wall.fields(mesh.nodes, 0., **STATE).temperature
    left, right = mesh.boundary['left'], mesh.boundary['right']
    initial[left], initial[right] = 400., 300.
    bc = {int(i): 400. for i in left}
    bc.update({int(i): 300. for i in right})
    r = solve_transient_heat(mesh, conductivity=_by_name(WALL['conductivities']),
                             volumetric_heat_capacity=_by_name(WALL['capacities']),
                             time_s=times, initial_temperature_k=initial, dirichlet=bc)
    return mesh, r


def _errors(mesh, result, wall):
    x, w = np.polynomial.legendre.leggauss(8)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qi,tij->tqj', bary, mesh.nodes[mesh.triangles])
    layer = np.repeat(mesh.regions, len(weights))
    weight = mesh.areas()[:, None]*weights[None, :]
    out = []
    for t in OBSERVE:
        index = int(np.argmin(abs(result.time_s-t)))
        assert abs(result.time_s[index]-t) < 1e-9
        exact = wall.fields(points.reshape(-1, 2), t, **STATE, layer=layer)
        th = np.einsum('qi,ti->tq', bary, result.temperature_k[index][mesh.triangles])
        dt_ = th-exact.temperature.reshape(th.shape)
        dq = result.heat_flux_w_m2[index][:, None, :]-exact.heat_flux.reshape(*th.shape, 2)
        out.append((np.sqrt(np.sum(weight*dt_**2)), np.sqrt(np.sum(weight[..., None]*dq**2))))
    return np.array(out)   # (times, [T, q])


def test_uniform_region_mapping_matches_the_scalar_history():
    mesh = layered_rectangle_mesh([.3, 1.], .5, [3, 5], 4, ['a', 'b'])
    bc = {int(i): 300. for i in mesh.boundary['left']}
    initial = np.full(len(mesh.nodes), 300.)
    kw = dict(time_s=[0., .5, 1.5], initial_temperature_k=initial, dirichlet=bc)
    scalar = solve_transient_heat(mesh, conductivity=2.5, volumetric_heat_capacity=4., heat_source=7., **kw)
    mapped = solve_transient_heat(mesh, conductivity={'a': 2.5, 'b': 2.5},
                                  volumetric_heat_capacity={'a': 4., 'b': 4.},
                                  heat_source={'a': 7., 'b': 7.}, **kw)
    for name in ('temperature_k', 'heat_flux_w_m2', 'reaction_w_per_m', 'storage_rate_w_per_m',
                 'heat_content_j_per_m'):
        np.testing.assert_array_equal(getattr(mapped, name), getattr(scalar, name))
    assert mapped.conductivity_w_mk == {'a': 2.5, 'b': 2.5} and scalar.conductivity_w_mk == 2.5


def test_backward_euler_step_uses_each_region_s_mass_and_stiffness():
    """Independent dense P1 element matrices with per-triangle k and c."""
    mesh = layered_rectangle_mesh([.01, .03], .005, [2, 3], 2, NAMES)
    k, c = mesh.by_region(_by_name([45., .5])), mesh.by_region(_by_name([3.6e6, 1.2e6]))
    n = len(mesh.nodes)
    K, M = np.zeros((n, n)), np.zeros((n, n))
    for tri, kk, cc in zip(mesh.triangles, k, c):
        xy = mesh.nodes[tri]
        e1, e2 = xy[1]-xy[0], xy[2]-xy[0]
        area = .5*abs(e1[0]*e2[1]-e1[1]*e2[0])
        grad = np.linalg.solve(np.column_stack([np.ones(3), xy]), np.eye(3))[1:]   # (2,3)
        K[np.ix_(tri, tri)] += kk*area*grad.T@grad
        M[np.ix_(tri, tri)] += cc*area/12*(np.ones((3, 3))+np.eye(3))
    initial = 300.+80*np.sin(np.pi*mesh.nodes[:, 0]/.03)
    bc = {int(i): 300. for i in np.r_[mesh.boundary['left'], mesh.boundary['right']]}
    r = solve_transient_heat(mesh, conductivity=_by_name([45., .5]),
                             volumetric_heat_capacity=_by_name([3.6e6, 1.2e6]),
                             time_s=[0., 2., 5.], initial_temperature_k=initial, dirichlet=bc)
    free = np.setdiff1d(np.arange(n), sorted(bc))
    for i, dt in ((1, 2.), (2, 3.)):
        residual = M@(r.temperature_k[i]-r.temperature_k[i-1])/dt+K@r.temperature_k[i]
        scale = np.max(abs(M@(r.temperature_k[i]-r.temperature_k[i-1])/dt))
        assert np.max(abs(residual[free])) < 1e-9*scale
        np.testing.assert_allclose(r.reaction_w_per_m[i-1][sorted(bc)], residual[sorted(bc)],
                                   rtol=1e-8, atol=1e-9*scale)
    np.testing.assert_allclose(r.heat_content_j_per_m, [np.sum(M@T) for T in r.temperature_k], rtol=1e-12)


@pytest.mark.slow
def test_two_layer_wall_converges_in_space_with_separated_time_error():
    # A first run with [2n, 4n] divisions and dt = 1/8 s failed the dt/2
    # separation gate (12-35% change); see docs/multimaterial.md.
    wall = LayeredWall(**WALL)
    dt = 1/32
    errors = []
    for n in (1, 2, 4, 8):
        mesh, r = _solve(n, dt, wall)
        errors.append(_errors(mesh, r, wall))
    errors = np.array(errors)                    # (mesh, time, [T, q])
    orders = np.log2(errors[:-1]/errors[1:])
    fine_mesh, fine = _solve(8, dt/2, wall)
    companion = _errors(fine_mesh, fine, wall)
    change = abs(companion-errors[-1])/errors[-1]
    print('two-layer transient errors', errors.tolist(), 'orders', orders.tolist(),
          'dt/2 change', change.tolist())
    assert np.all(orders[-2:, :, 0] >= 1.8)
    assert np.all(orders[-2:, :, 1] >= .9)
    assert np.all(change <= .05)


def _two():
    return layered_rectangle_mesh([.5, 1.], 1., [1, 1], 1, ['a', 'b'])


@pytest.mark.parametrize('bad', [dict(conductivity={'a': 1.}), dict(conductivity={'a': 1., 'b': 0.}),
                                 dict(volumetric_heat_capacity={'a': 1., 'b': -1.}),
                                 dict(volumetric_heat_capacity={'a': 1., 'x': 1.}),
                                 dict(heat_source={'a': 1., 'b': np.nan}),
                                 dict(conductivity=[1., 2.])])
def test_invalid_region_transient_inputs(bad):
    mesh = _two()
    kw = dict(conductivity=1., volumetric_heat_capacity=1., time_s=[0., 1.],
              initial_temperature_k=np.full(len(mesh.nodes), 300.),
              dirichlet={int(i): 300. for i in mesh.boundary['left']})
    kw.update(bad)
    with pytest.raises(ValueError):
        solve_transient_heat(mesh, **kw)


def test_region_mapping_on_a_mesh_without_regions_is_rejected():
    mesh = rectangle_mesh(1., 1., 1, 1)
    with pytest.raises(ValueError):
        solve_transient_heat(mesh, conductivity={'a': 1.}, volumetric_heat_capacity=1., time_s=[0., 1.],
                             initial_temperature_k=np.full(4, 300.), dirichlet={0: 300.})
