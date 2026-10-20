# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Per-region conductivity and source against independent layered-wall references.

The references (refsol.thermal_multilayer) are closed forms that import no
engine code. Meshes put every material interface on element edges, so the only
geometric error is the inscribed polygon of the annulus.
"""
import numpy as np
import pytest

from galerkin.assembly import assemble_load, assemble_stiffness
from galerkin.mesh import Mesh, layered_annulus_mesh, layered_rectangle_mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat
from refsol.thermal_multilayer import composite_cylinder, layered_slab

NAMES = ['copper', 'insulation', 'steel']
SLAB = dict(interfaces=[.02, .05, .06], conductivities=[15., .8, 45.],
            left_temperature=420., right_temperature=300., sources=[2e5, -3e4, 6e5])
CYL = dict(inner_radius=.01, interfaces=[.015, .03, .034], conductivities=[50., .25, 16.],
           inner_temperature=500., outer_temperature=310., sources=[1e6, 0., -2e5])


def _by_name(values):
    return dict(zip(NAMES, values))


def _slab(n, sources=True):
    mesh = layered_rectangle_mesh(SLAB['interfaces'], .02, [2*n, 3*n, n], 2*n, NAMES)
    bc = {int(i): SLAB['left_temperature'] for i in mesh.boundary['left']}
    bc.update({int(i): SLAB['right_temperature'] for i in mesh.boundary['right']})
    source = _by_name(SLAB['sources']) if sources else 0.
    result = solve_steady_heat(mesh, conductivity=_by_name(SLAB['conductivities']),
                               dirichlet=bc, heat_source=source)
    return mesh, result


def _cylinder(n):
    mesh = layered_annulus_mesh(CYL['inner_radius'], CYL['interfaces'], [2*n, 4*n, 2*n], 24*n, NAMES)
    bc = {int(i): CYL['inner_temperature'] for i in mesh.boundary['inner']}
    bc.update({int(i): CYL['outer_temperature'] for i in mesh.boundary['outer']})
    result = solve_steady_heat(mesh, conductivity=_by_name(CYL['conductivities']),
                               dirichlet=bc, heat_source=_by_name(CYL['sources']))
    return mesh, result


def _errors(mesh, result, reference):
    # Independent 8x8 Duffy quadrature in every triangle; each point lies in
    # the interior of its triangle and therefore of one material layer.
    x, w = np.polynomial.legendre.leggauss(8)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qi,tij->tqj', bary, mesh.nodes[mesh.triangles])
    layer = np.repeat(mesh.regions, len(weights))
    exact = reference(points.reshape(-1, 2), layer)
    th = np.einsum('qi,ti->tq', bary, result.temperature[mesh.triangles])
    dt = th-exact.temperature.reshape(th.shape)
    dq = result.heat_flux[:, None, :]-exact.heat_flux.reshape(*th.shape, 2)
    area = mesh.areas()[:, None]
    weight = area*weights[None, :]
    return np.sqrt(np.sum(weight*dt**2)), np.sqrt(np.sum(weight[..., None]*dq**2))


def _orders(errors):
    e = np.asarray(errors)
    return np.log2(e[:-1]/e[1:])


def _interface_rate(mesh, result, case, region_ids, interface_nodes):
    """Heat leaving the union of region_ids through interface nodes (W/m).

    Variational flux: the residual of the subdomain's own stiffness and load,
    summed over its interface nodes, is the heat injected into the subdomain
    there (the reaction sign convention), so the outgoing rate is its negative.
    """
    keep = np.isin(mesh.regions, region_ids)
    part = Mesh(mesh.nodes, mesh.triangles[keep], {})
    k = mesh.by_region(_by_name(case['conductivities']))[keep]
    q = mesh.by_region(_by_name(case['sources']))[keep]
    residual = assemble_stiffness(part, k)@result.temperature-assemble_load(part, q)
    return -float(np.sum(residual[interface_nodes]))


def test_uniform_region_mapping_reproduces_the_scalar_solution_bit_for_bit():
    mesh = layered_rectangle_mesh([.3, 1.], .5, [3, 5], 4, ['a', 'b'])
    bc = {int(i): 350. for i in mesh.boundary['left']}
    bc.update({int(i): 300. for i in mesh.boundary['right']})
    scalar = solve_steady_heat(mesh, conductivity=12., dirichlet=bc, heat_source=4e3)
    mapped = solve_steady_heat(mesh, conductivity={'a': 12., 'b': 12.}, dirichlet=bc,
                               heat_source={'a': 4e3, 'b': 4e3})
    for field in ('temperature', 'heat_flux', 'load', 'reaction', 'residual'):
        np.testing.assert_array_equal(getattr(mapped, field), getattr(scalar, field))


def test_scalar_input_on_a_mesh_without_regions_is_unchanged():
    mesh = rectangle_mesh(2., .7, 8, 5)
    assert mesh.regions is None
    bc = {int(i): 350. for i in mesh.boundary['left']}
    bc.update({int(i): 300. for i in mesh.boundary['right']})
    r = solve_steady_heat(mesh, conductivity=12., dirichlet=bc)
    np.testing.assert_allclose(r.heat_flux, np.broadcast_to([300., 0.], r.heat_flux.shape),
                               rtol=0, atol=300e-10)


def test_series_wall_without_source_is_reproduced_exactly():
    mesh, r = _slab(2, sources=False)
    exact = layered_slab(mesh.nodes, **{**SLAB, 'sources': None})
    assert np.max(abs(r.temperature-exact.temperature))/420. < 1e-10
    k = mesh.by_region(_by_name(SLAB['conductivities']))
    centroid = layered_slab(mesh.nodes[mesh.triangles].mean(axis=1), **{**SLAB, 'sources': None})
    np.testing.assert_allclose(r.heat_flux, centroid.heat_flux, rtol=0,
                               atol=1e-9*np.max(abs(centroid.heat_flux)))
    # The flux is one value across all three materials, the gradient is not.
    assert np.ptp(k) > 40 and np.ptp(r.heat_flux[:, 0]) < 1e-9*abs(r.heat_flux[0, 0])
    rate = centroid.heat_flux[0, 0]*.02
    np.testing.assert_allclose(sum(r.reaction[mesh.boundary['left']]), rate, rtol=1e-10)
    np.testing.assert_allclose(sum(r.reaction[mesh.boundary['right']]), -rate, rtol=1e-10)


@pytest.mark.slow
def test_series_wall_with_layer_sources_converges_and_conserves_interface_heat():
    t_err, q_err, rate_err = [], [], []
    for n in (1, 2, 4, 8):
        mesh, r = _slab(n)
        a, b = _errors(mesh, r, lambda p, i: layered_slab(p, **SLAB, layer=i))
        t_err.append(a)
        q_err.append(b)
        worst = 0.
        for i, x in enumerate(SLAB['interfaces'][:-1]):
            nodes = np.flatnonzero(abs(mesh.nodes[:, 0]-x) < 1e-12)
            exact = layered_slab([[x, 0.]], **SLAB).heat_flux[0, 0]*.02
            left = _interface_rate(mesh, r, SLAB, list(range(i+1)), nodes)
            right = -_interface_rate(mesh, r, SLAB, list(range(i+1, 3)), nodes)
            worst = max(worst, abs(left-exact)/abs(exact), abs(right-exact)/abs(exact))
        rate_err.append(worst)
    print('slab T L2', t_err, _orders(t_err), 'q L2', q_err, _orders(q_err), 'interface', rate_err)
    assert np.all(_orders(t_err)[-2:] >= 1.8)
    assert np.all(_orders(q_err)[-2:] >= .9)
    # y-independent data: P1 nodal values and the variational interface rate are exact.
    assert max(rate_err) < 1e-9


@pytest.mark.slow
def test_composite_cylinder_converges_and_flux_is_continuous_across_interfaces():
    t_err, q_err, rate_err, jump = [], [], [], []
    for n in (1, 2, 4, 8):
        mesh, r = _cylinder(n)
        a, b = _errors(mesh, r, lambda p, i: composite_cylinder(p, **CYL, layer=i))
        t_err.append(a)
        q_err.append(b)
        radius = np.hypot(*mesh.nodes.T)
        worst_rate, worst_jump = 0., 0.
        for i, ri in enumerate(CYL['interfaces'][:-1]):
            nodes = np.flatnonzero(abs(radius-ri) < 1e-9*ri)
            exact_qr = composite_cylinder([[ri, 0.]], **CYL).heat_flux[0, 0]
            exact = 2*np.pi*ri*exact_qr
            left = _interface_rate(mesh, r, CYL, list(range(i+1)), nodes)
            worst_rate = max(worst_rate, abs(left-exact)/abs(exact))
            # Normal flux of the two triangles sharing each interface edge.
            on = np.isin(mesh.triangles, nodes).sum(axis=1) == 2
            inside, outside = on & (mesh.regions == i), on & (mesh.regions == i+1)
            normal = lambda cells: np.einsum('td,td->t', r.heat_flux[cells],
                                             mesh.nodes[mesh.triangles[cells]].mean(axis=1)
                                             / np.hypot(*mesh.nodes[mesh.triangles[cells]].mean(axis=1).T)[:, None])
            worst_jump = max(worst_jump, abs(normal(inside).mean()-normal(outside).mean())/abs(exact_qr))
        rate_err.append(worst_rate)
        jump.append(worst_jump)
    print('cylinder T L2', t_err, _orders(t_err), 'q L2', q_err, _orders(q_err),
          'interface rate', rate_err, _orders(rate_err), 'normal-flux jump', jump, _orders(jump))
    assert np.all(_orders(t_err)[-2:] >= 1.8)
    assert np.all(_orders(q_err)[-2:] >= .9)
    assert np.all(_orders(rate_err)[-2:] >= 1.8)
    assert np.all(_orders(jump)[-2:] >= .9)


def test_region_heat_source_matches_an_equivalent_callable_load():
    mesh = layered_rectangle_mesh([.3, 1.], .5, [3, 5], 4, ['a', 'b'])
    bc = {int(i): 300. for i in np.unique(np.concatenate(list(mesh.boundary.values())))}
    mapped = solve_steady_heat(mesh, conductivity={'a': 2., 'b': 7.}, dirichlet=bc,
                               heat_source={'a': 5e3, 'b': -1e3})
    np.testing.assert_allclose(sum(mapped.load), 5e3*.3*.5-1e3*.7*.5, rtol=1e-13)
    assert abs(sum(mapped.load+mapped.reaction)) < 1e-10*sum(abs(mapped.load))


def _region_mesh():
    return layered_rectangle_mesh([.3, 1.], .5, [1, 1], 1, ['a', 'b'])


@pytest.mark.parametrize('k', [{'a': 1.}, {'a': 1., 'b': 2., 'c': 3.}, {'a': 1., 'b': 0.},
                               {'a': 1., 'b': -2.}, {'a': 1., 'b': np.nan}, {'a': 1., 'b': 1j},
                               {'a': 1., 'b': True}, {'a': 1., 'b': [2.]}, {0: 1., 1: 2.}])
def test_invalid_region_conductivity(k):
    mesh = _region_mesh()
    with pytest.raises(ValueError):
        solve_steady_heat(mesh, conductivity=k, dirichlet={0: 300.})


@pytest.mark.parametrize('q', [{'a': 1.}, {'a': 1., 'b': np.inf}, {'a': 1., 'b': 1j}, {'a': 1., 'x': 1.}])
def test_invalid_region_source(q):
    with pytest.raises(ValueError):
        solve_steady_heat(_region_mesh(), conductivity=1., dirichlet={0: 300.}, heat_source=q)


def test_region_mapping_needs_region_data_and_bare_arrays_stay_rejected():
    plain = rectangle_mesh(1., 1., 1, 1)
    with pytest.raises(ValueError):
        solve_steady_heat(plain, conductivity={'a': 1.}, dirichlet={0: 300.})
    with pytest.raises(ValueError):
        solve_steady_heat(_region_mesh(), conductivity=[1., 2.], dirichlet={0: 300.})
    broken = _region_mesh()
    broken.regions = np.array([0, 0, 1, 5])
    with pytest.raises(ValueError):
        solve_steady_heat(broken, conductivity={'a': 1., 'b': 2.}, dirichlet={0: 300.})


def test_layered_meshes_put_interfaces_on_mesh_lines_and_name_regions():
    m = layered_rectangle_mesh([.1, .3, .35], .2, [2, 3, 1], 2, ['a', 'b', 'c'])
    assert m.region_names == ['a', 'b', 'c']
    x = m.nodes[m.triangles][..., 0]
    for i, (lo, hi) in enumerate([(0., .1), (.1, .3), (.3, .35)]):
        cells = m.regions == i
        assert np.all(x[cells] >= lo) and np.all(x[cells] <= hi)
        np.testing.assert_allclose(m.areas()[cells].sum(), (hi-lo)*.2, rtol=1e-13)
    assert {.1, .3, .35} <= set(m.nodes[:, 0])
    a = layered_annulus_mesh(1., [1.5, 2.], [2, 3], 12)
    r = np.hypot(*a.nodes[a.triangles].transpose(2, 0, 1))
    assert np.all(r[a.regions == 0] <= 1.5+1e-12) and np.all(r[a.regions == 1] >= 1.5-1e-12)
    np.testing.assert_allclose(np.hypot(*a.nodes[a.boundary['outer']].T), 2., rtol=1e-15)
    assert a.region_names == ['layer0', 'layer1']
    for bad in (dict(x_interfaces=[.2, .1]), dict(x_interfaces=[]), dict(nx=[1, 0]),
                dict(region_names=['only'])):
        args = dict(x_interfaces=[.1, .2], height=1., nx=[1, 1], ny=1, **{})
        args.update(bad)
        with pytest.raises(ValueError):
            layered_rectangle_mesh(**args)
    with pytest.raises(ValueError):
        layered_annulus_mesh(0., [1.], 1, 8)
