# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Per-region E and nu against independent layered references (refsol.elasticity_multilayer)."""
import numpy as np
import pytest

from galerkin.elasticity import solve_elasticity
from galerkin.mesh import layered_annulus_mesh, layered_rectangle_mesh, rectangle_mesh
from refsol.elasticity_multilayer import composite_cylinder, laminate_axial, series_bar

NAMES = ['steel', 'epoxy', 'aluminium']
CYL = dict(inner_radius=.02, interfaces=[.03, .045, .05], young_moduli=[200e9, 3e9, 70e9],
           poisson_ratios=[.3, .38, .33])


def _by_name(values, names=NAMES):
    return dict(zip(names, values))


def _swap(fields):
    """Reference laminate is stacked in y; the mesh stacks layers in x."""
    u = fields.displacement[:, ::-1]
    s = fields.stress[:, [1, 0, 2]]
    return u, s


def test_uniform_region_mapping_matches_the_scalar_solution():
    mesh = layered_rectangle_mesh([.3, 1.], .5, [3, 5], 4, ['a', 'b'])
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    kw = dict(plane='strain', dirichlet=bc, traction={'right': [1e6, -2e5]}, body_force=[0., -8e4])
    scalar = solve_elasticity(mesh, young_modulus=70e9, poisson_ratio=.33, **kw)
    mapped = solve_elasticity(mesh, young_modulus={'a': 70e9, 'b': 70e9},
                              poisson_ratio={'a': .33, 'b': .33}, **kw)
    mixed = solve_elasticity(mesh, young_modulus={'a': 70e9, 'b': 70e9}, poisson_ratio=.33, **kw)
    for other in (mapped, mixed):
        for field in ('displacement', 'strain', 'stress', 'reaction'):
            a, b = getattr(other, field), getattr(scalar, field)
            np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-12*np.max(abs(b)))


def test_scalar_input_path_is_unchanged_on_meshes_without_regions():
    mesh = rectangle_mesh(1., .5, 4, 2)
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    r = solve_elasticity(mesh, young_modulus=70e9, poisson_ratio=.3, plane='stress', dirichlet=bc,
                         traction={'right': [1e6, 0.]})
    assert mesh.regions is None and r.stress.shape == (len(mesh.triangles), 3)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_parallel_laminate_under_axial_strain_is_reproduced_exactly(plane):
    mesh = layered_rectangle_mesh([.002, .005, .006], .03, [2, 3, 1], 6, NAMES)
    e, nu, eps = [70e9, 3e9, 200e9], [.33, .4, .29], 1e-3
    kw = dict(y_interfaces=[.002, .005, .006], young_moduli=e, poisson_ratios=nu,
              axial_strain=eps, plane=plane)
    bc = {(int(i), 1): 0. for i in mesh.boundary['bottom']}
    bc.update({(int(i), 1): eps*.03 for i in mesh.boundary['top']})
    bc[(int(mesh.boundary['bottom'][0]), 0)] = 0.
    r = solve_elasticity(mesh, young_modulus=_by_name(e), poisson_ratio=_by_name(nu), plane=plane,
                         dirichlet=bc)
    u, _ = _swap(laminate_axial(mesh.nodes[:, ::-1], **kw))
    _, s = _swap(laminate_axial(mesh.nodes[mesh.triangles].mean(axis=1)[:, ::-1], **kw,
                                layer=mesh.regions))
    assert np.max(abs(r.displacement-u)) < 1e-10*eps*.03
    np.testing.assert_allclose(r.stress, s, rtol=0, atol=1e-9*np.max(abs(s)))
    # Voigt resultant: the top support carries sum(E'_i t_i) eps per unit depth.
    stiff = np.array(e) if plane == 'stress' else np.array(e)/(1-np.array(nu)**2)
    resultant = np.sum(stiff*np.diff([0, .002, .005, .006]))*eps
    np.testing.assert_allclose(r.reaction[mesh.boundary['top'], 1].sum(), resultant, rtol=1e-10)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_series_bar_with_matched_lateral_strain_is_reproduced_exactly(plane):
    e = np.array([200e9, 100e9])
    if plane == 'stress':
        nu = np.array([.3, .15])
    else:
        nu = np.array([.3, (-1+np.sqrt(1+4*.3*1.3/200e9*100e9))/2])
    mesh = layered_rectangle_mesh([.04, .1], .02, [4, 6], 3, ['a', 'b'])
    bc = {(int(i), 0): 0. for i in mesh.boundary['left']}
    bc[(int(mesh.boundary['left'][0]), 1)] = 0.
    r = solve_elasticity(mesh, young_modulus=_by_name(e, 'ab'), poisson_ratio=_by_name(nu, 'ab'),
                         plane=plane, dirichlet=bc, traction={'right': [5e7, 0.]})
    exact = series_bar(mesh.nodes, x_interfaces=[.04, .1], young_moduli=e, poisson_ratios=nu,
                       axial_stress=5e7, plane=plane)
    assert np.max(abs(r.displacement-exact.displacement)) < 1e-9*np.max(abs(exact.displacement))
    np.testing.assert_allclose(r.stress, np.broadcast_to([5e7, 0., 0.], r.stress.shape),
                               rtol=0, atol=1e-8*5e7)
    assert {'a', 'b'} == set(mesh.region_names)


def _cylinder_case(n, plane, **load):
    mesh = layered_annulus_mesh(CYL['inner_radius'], CYL['interfaces'], [2*n, 3*n, n], 24*n, NAMES)
    nt = 24*n
    bc = {(0, 1): 0., (nt//2, 1): 0., (nt//4, 0): 0.}     # symmetry points on the inner ring
    traction = {'inner': lambda p, nrm: -load['inner_pressure']*nrm,
                'outer': lambda p, nrm: -load['outer_pressure']*nrm}
    r = solve_elasticity(mesh, young_modulus=_by_name(CYL['young_moduli']),
                         poisson_ratio=_by_name(CYL['poisson_ratios']), plane=plane,
                         dirichlet=bc, traction=traction)
    return mesh, r


def _errors(mesh, result, reference):
    x, w = np.polynomial.legendre.leggauss(8)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qi,tij->tqj', bary, mesh.nodes[mesh.triangles])
    exact = reference(points.reshape(-1, 2), np.repeat(mesh.regions, len(weights)))
    uh = np.einsum('qi,tid->tqd', bary, result.displacement[mesh.triangles])
    du = uh-exact.displacement.reshape(uh.shape)
    ds = result.stress[:, None, :]-exact.stress.reshape(*uh.shape[:2], 3)
    weight = mesh.areas()[:, None]*weights[None, :]
    return np.sqrt(np.sum(weight[..., None]*du**2)), np.sqrt(np.sum(weight[..., None]*ds**2))


def _orders(e):
    e = np.asarray(e)
    return np.log2(e[:-1]/e[1:])


@pytest.mark.slow
@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_composite_cylinder_under_pressure_converges_with_continuous_traction(plane):
    load = dict(inner_pressure=4e7, outer_pressure=5e6)
    u_err, s_err, jump, reaction = [], [], [], []
    for n in (1, 2, 4, 8):
        mesh, r = _cylinder_case(n, plane, **load)
        ref = lambda p, i: composite_cylinder(p, **CYL, plane=plane, **load, layer=i)
        a, b = _errors(mesh, r, ref)
        u_err.append(a)
        s_err.append(b)
        c = mesh.nodes[mesh.triangles].mean(axis=1)
        radial = c/np.hypot(*c.T)[:, None]
        srr = (r.stress[:, 0]*radial[:, 0]**2+r.stress[:, 1]*radial[:, 1]**2
               + 2*r.stress[:, 2]*radial[:, 0]*radial[:, 1])
        worst = 0.
        for i, ri in enumerate(CYL['interfaces'][:-1]):
            nodes = np.flatnonzero(abs(np.hypot(*mesh.nodes.T)-ri) < 1e-9*ri)
            on = np.isin(mesh.triangles, nodes).sum(axis=1) == 2
            exact = composite_cylinder([[ri, 0.]], **CYL, plane=plane, **load).radial_stress[0]
            gap = srr[on & (mesh.regions == i)].mean()-srr[on & (mesh.regions == i+1)].mean()
            worst = max(worst, abs(gap)/abs(exact))
        jump.append(worst)
        reaction.append(np.max(abs(r.reaction))/(4e7*.02*2*np.pi))
    print(plane, 'u L2', u_err, _orders(u_err), 'stress L2', s_err, _orders(s_err),
          'radial-traction jump', jump, _orders(jump), 'symmetry reactions', reaction)
    assert np.all(_orders(u_err)[-2:] >= 1.8)
    assert np.all(_orders(s_err)[-2:] >= .9)
    assert np.all(_orders(jump)[-2:] >= .9)
    # Symmetric loads on a C_n-symmetric mesh: the three point supports carry nothing.
    assert max(reaction) < 1e-8


def _two_region():
    return layered_rectangle_mesh([.5, 1.], 1., [1, 1], 1, ['a', 'b'])


@pytest.mark.parametrize('kwargs', [dict(young_modulus={'a': 1e9}), dict(young_modulus={'a': 1e9, 'b': 0.}),
                                    dict(young_modulus={'a': 1e9, 'b': 1e9, 'c': 1e9}),
                                    dict(poisson_ratio={'a': .3, 'b': .5}), dict(poisson_ratio={'a': .3, 'b': -1.}),
                                    dict(poisson_ratio={'a': .3, 'b': np.nan}), dict(young_modulus={'a': 1e9, 'b': 1j}),
                                    dict(young_modulus=[1e9, 1e9]), dict(plane='auto', young_modulus={'a': 1., 'b': 1.})])
def test_invalid_region_materials(kwargs):
    mesh = _two_region()
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    args = dict(young_modulus=1e9, poisson_ratio=.3, plane='stress', dirichlet=bc, **{})
    args.update(kwargs)
    with pytest.raises(ValueError):
        solve_elasticity(mesh, **args)


def test_region_mapping_on_mesh_without_regions_is_rejected():
    mesh = rectangle_mesh(1., 1., 1, 1)
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    with pytest.raises(ValueError):
        solve_elasticity(mesh, young_modulus={'a': 1e9}, poisson_ratio=.3, plane='stress', dirichlet=bc)
