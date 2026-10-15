# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent acceptance; thresholds and mesh sequences fixed before execution."""
import json
import numpy as np
import pytest
from numpy.testing import assert_allclose

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.elasticity import solve_elasticity
from elasticity2d_independent_oracle import (
    E, NU, AMPLITUDE, polynomial, mixed, stress, errors, quadrature, fe_strain,
)


def solve(mesh, plane, bc, force=(0., 0.)):
    return solve_elasticity(mesh, young_modulus=E, poisson_ratio=NU,
                            plane=plane, dirichlet=bc, body_force=force)


def prescribed(mesh, u):
    nodes = np.unique(np.concatenate(list(mesh.boundary.values())))
    return {(int(i), c): float(u[i, c]) for i in nodes for c in (0, 1)}


def check_balance_and_work(mesh, result, oracle, plane, bc):
    _, points, weights = quadrature(mesh, 7)
    force = oracle(points, plane)[3]
    total = np.sum(weights[..., None]*force, axis=(0, 1))
    moment = np.sum(weights*(points[..., 0]*force[..., 1]-points[..., 1]*force[..., 0]))
    force_scale = np.sum(weights*np.linalg.norm(force, axis=-1))
    assert_allclose(result.load.sum(axis=0), total, rtol=1e-10, atol=1e-10)
    nodal_moment = np.sum(mesh.nodes[:, 0]*result.load[:, 1]-mesh.nodes[:, 1]*result.load[:, 0])
    assert abs(nodal_moment-moment) < 1e-10*force_scale
    all_force = result.load+result.reaction
    assert np.linalg.norm(all_force.sum(axis=0)) < 1e-9*force_scale
    assert abs(np.sum(mesh.nodes[:, 0]*all_force[:, 1]-mesh.nodes[:, 1]*all_force[:, 0])) < 1e-9*force_scale
    fixed = {2*i+c for i, c in bc}
    free = np.array(sorted(set(range(2*mesh.num_nodes))-fixed))
    assert np.max(abs(result.reaction.ravel()[free])) == 0
    strain = fe_strain(mesh, result.displacement)
    assert_allclose(result.strain, strain, rtol=1e-9, atol=1e-12)
    sigma = stress(strain, plane)
    assert_allclose(result.stress, sigma, rtol=1e-9, atol=1e-6)
    area = weights.sum(axis=1)
    twice_energy = np.sum(area*np.sum(sigma*strain, axis=-1))
    work = np.sum(result.load*result.displacement)+sum(result.reaction[i, c]*v for (i, c), v in bc.items())
    assert abs(work-twice_energy) < 1e-9*max(abs(twice_energy), abs(work))
    # A different virtual affine displacement checks both shear factors and
    # weak-form work, including the prescribed-boundary reactions.
    virtual = mesh.nodes@np.array([[.003, -.001], [.002, -.004]]).T
    virtual_strain = np.array([.003, -.004, .001])
    internal = np.sum(area*np.sum(sigma*virtual_strain, axis=-1))
    external = np.sum(all_force*virtual)
    assert abs(internal-external) < 1e-9*force_scale*np.max(abs(virtual))
    return twice_energy/2


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_elasticity2d_independent_polynomial_oracle_derivatives_and_negative_controls(plane):
    p = np.array([[.17, .31], [.73, .58], [.41, .89]])
    h = 1e-5
    u, strain, sigma, force = polynomial(p, plane)
    dx, dy = np.eye(2)*h
    ux = (polynomial(p+dx, plane)[0]-polynomial(p-dx, plane)[0])/(2*h)
    uy = (polynomial(p+dy, plane)[0]-polynomial(p-dy, plane)[0])/(2*h)
    assert_allclose(strain, np.c_[ux[:, 0], uy[:, 1], uy[:, 0]+ux[:, 1]], rtol=1e-8, atol=1e-12)
    sx = (polynomial(p+dx, plane)[2]-polynomial(p-dx, plane)[2])/(2*h)
    sy = (polynomial(p+dy, plane)[2]-polynomial(p-dy, plane)[2])/(2*h)
    divergence = np.c_[sx[:, 0]+sy[:, 2], sx[:, 2]+sy[:, 1]]
    assert_allclose(force, -divergence, rtol=1e-9, atol=1e-5)
    # Explicit negative controls: reversed force and tensor/engineering shear
    # confusion must fail the same comparisons by much more than roundoff.
    with pytest.raises(AssertionError):
        assert_allclose(-force, -divergence, rtol=1e-9, atol=1e-5)
    wrong = strain.copy(); wrong[:, 2] *= .5
    with pytest.raises(AssertionError):
        assert_allclose(stress(wrong, plane), sigma, rtol=1e-9, atol=1e-6)
    other = 'strain' if plane == 'stress' else 'stress'
    with pytest.raises(AssertionError):
        assert_allclose(stress(strain, other), sigma, rtol=1e-9, atol=1e-6)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('case', ['polynomial', 'mixed'])
def test_elasticity2d_independent_internal_quadrature_convergence(plane, case):
    oracle = polynomial if case == 'polynomial' else mixed
    history, energies = [], []
    for n in (6, 12, 24):
        mesh = rectangle_mesh(1., 1., n, n)
        u = oracle(mesh.nodes, plane)[0]
        if case == 'polynomial':
            bc = prescribed(mesh, u)
        else:
            bc = {(int(i), 0): float(u[i, 0]) for side in ('left', 'right') for i in mesh.boundary[side]}
            bc.update({(int(i), 1): 0. for i in mesh.boundary['bottom']})
        result = solve(mesh, plane, bc, lambda p: oracle(p, plane)[3])
        err = errors(mesh, result, oracle, plane, 7)
        assert_allclose(errors(mesh, result, oracle, plane, 5), err, rtol=1e-9)
        history.append(err)
        energies.append(check_balance_and_work(mesh, result, oracle, plane, bc))
    history = np.array(history)
    orders = np.log2(history[:-1]/history[1:])
    print('\nINDEPENDENT_ELASTICITY '+json.dumps(dict(plane=plane, case=case, n=[6,12,24], errors=history.tolist(), orders=orders.tolist(), energies=energies)))
    assert np.all(np.diff(history, axis=0) < 0)
    assert orders[-1, 0] >= 1.8
    assert np.all(orders[-1, 1:] >= .9)
    if case == 'mixed':
        modulus = E if plane == 'stress' else E/(1-NU**2)
        exact_energy = 2*AMPLITUDE**2*modulus/3
        assert np.all(np.diff(abs(np.array(energies)-exact_energy)) < 0)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_elasticity2d_independent_closed_form_affine_component_supports(plane):
    mesh = rectangle_mesh(1.3, .7, 5, 4)
    # Vertical extension is the transpose of the original implementation test.
    k = NU if plane == 'stress' else NU/(1-NU)
    modulus = E if plane == 'stress' else E/(1-NU**2)
    a = AMPLITUDE
    bc = {(int(i), 1): a*mesh.nodes[i, 1] for side in ('bottom', 'top') for i in mesh.boundary[side]}
    bc.update({(int(i), 0): 0. for i in mesh.boundary['left']})
    result = solve(mesh, plane, bc)
    assert_allclose(result.displacement, mesh.nodes*[-k*a, a], rtol=1e-9, atol=1e-12)
    assert_allclose(result.stress, np.tile([0., a*modulus, 0.], (mesh.num_triangles, 1)), rtol=1e-9, atol=1e-6)
    assert_allclose(result.reaction[mesh.boundary['top'], 1].sum(), 1.3*a*modulus, rtol=1e-9)
    assert_allclose(.5*np.sum(result.displacement*result.reaction), .5*modulus*a*a*1.3*.7, rtol=1e-9)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_elasticity2d_independent_mixed_oracle_and_minimal_rigid_support(plane):
    p = np.array([[.13, .27], [.81, .64], [.37, 1.]])
    h = 1e-5
    dx, dy = np.eye(2)*h
    ux = (mixed(p+dx, plane)[0]-mixed(p-dx, plane)[0])/(2*h)
    uy = (mixed(p+dy, plane)[0]-mixed(p-dy, plane)[0])/(2*h)
    u, strain, sigma, force = mixed(p, plane)
    assert_allclose(strain, np.c_[ux[:, 0], uy[:, 1], uy[:, 0]+ux[:, 1]], rtol=1e-8, atol=1e-12)
    assert_allclose(stress(strain, plane), sigma, rtol=1e-9, atol=1e-6)
    sx = (mixed(p+dx, plane)[2]-mixed(p-dx, plane)[2])/(2*h)
    sy = (mixed(p+dy, plane)[2]-mixed(p-dy, plane)[2])/(2*h)
    assert_allclose(force, -np.c_[sx[:, 0]+sy[:, 2], sx[:, 2]+sy[:, 1]], rtol=1e-9, atol=1e-5)
    assert_allclose(sigma[:, 1:], 0., atol=1e-6)  # horizontal free traction
    mesh = rectangle_mesh(1., 1., 5, 4)
    rigid = .001*np.c_[-mesh.nodes[:, 1], mesh.nodes[:, 0]]+[.004, -.003]
    bc = {(0, 0): .004, (0, 1): -.003, (5, 1): -.002}
    result = solve(mesh, plane, bc)
    assert_allclose(result.displacement, rigid, rtol=1e-9, atol=1e-12)
    assert_allclose(result.strain, 0., atol=1e-12)
    assert_allclose(result.stress, 0., atol=1e-6)
    with pytest.raises(ValueError, match='rigid modes'):
        solve(mesh, plane, {(0, 0): .004, (0, 1): -.003})


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_elasticity2d_independent_rigid_superposition_mesh_covariance(plane):
    base = rectangle_mesh(1., 1., 5, 4)
    n = base.num_nodes
    u = polynomial(base.nodes, plane)[0]
    bc = prescribed(base, u)
    result = solve(base, plane, bc, lambda p: polynomial(p, plane)[3])
    theta, scale = .37, 2.
    q = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    translation = np.array([2.3, -1.7])
    rng = np.random.default_rng(49)
    permutation = rng.permutation(n); inverse = np.argsort(permutation)
    cells = rng.permutation(base.num_triangles)
    # Proper rotation, coordinate scaling, node/cell ordering, cyclic/reversed
    # connectivity and translation are applied together.
    transformed = Mesh((scale*base.nodes@q.T+translation)[permutation],
                       inverse[base.triangles[cells]][:, ::-1],
                       {k: inverse[v] for k, v in base.boundary.items()})
    expected = (scale*u@q.T)[permutation]
    r = solve(transformed, plane, prescribed(transformed, expected),
              lambda p: polynomial(((p-translation)@q)/scale, plane)[3]@q.T/scale)
    assert_allclose(r.displacement, (scale*result.displacement@q.T)[permutation], rtol=1e-9, atol=1e-12)
    sigma = result.stress[cells]
    tensor = np.stack((np.stack((sigma[:, 0], sigma[:, 2]), axis=-1),
                       np.stack((sigma[:, 2], sigma[:, 1]), axis=-1)), axis=1)
    rotated = q@tensor@q.T
    assert_allclose(r.stress, np.c_[rotated[:, 0, 0], rotated[:, 1, 1], rotated[:, 0, 1]], rtol=1e-9, atol=1e-6)
    assert_allclose(r.load, (scale*result.load@q.T)[permutation], rtol=1e-9, atol=1e-9)
    assert_allclose(r.reaction, (scale*result.reaction@q.T)[permutation], rtol=1e-9, atol=1e-9)
    # Infinitesimal rigid rotation/translation can be superposed on a strained
    # solution without changing stress, strain, load or reaction.
    rigid = .001*np.c_[-base.nodes[:, 1], base.nodes[:, 0]]+[.004, -.003]
    s = solve(base, plane, prescribed(base, u+rigid), lambda p: polynomial(p, plane)[3])
    assert_allclose(s.displacement, result.displacement+rigid, rtol=1e-9, atol=1e-12)
    assert_allclose(s.strain, result.strain, rtol=1e-9, atol=1e-12)
    assert_allclose(s.stress, result.stress, rtol=1e-9, atol=1e-6)
    assert_allclose(s.reaction, result.reaction, rtol=1e-9, atol=1e-9)
