# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent mixed-boundary acceptance; pre-registered mesh and error gates."""
import json
import numpy as np
import pytest
from numpy.testing import assert_allclose
from galerkin.mesh import Mesh, rectangle_mesh, annulus_mesh
from galerkin.elasticity import solve_elasticity
from traction_independent_oracle import (
    E, NU, A, NORMALS, manufactured, surface, stress, integration, strain_fit,
    errors, consistent_load, right_edge_load,
)


def solve(mesh, plane='stress', **kw):
    return solve_elasticity(mesh, young_modulus=E, poisson_ratio=NU, plane=plane, **kw)


def fixed(mesh, u=None):
    u = np.zeros_like(mesh.nodes) if u is None else u
    nodes = np.unique(np.concatenate(list(mesh.boundary.values())))
    return {(int(i), c): float(u[i, c]) for i in nodes for c in (0, 1)}


def mixed_bc(mesh, plane):
    u = manufactured(mesh.nodes, plane)[0]
    bc = {(int(i), 0): float(u[i, 0]) for i in mesh.boundary['left']}
    bc.update({(int(i), 1): float(u[i, 1]) for i in mesh.boundary['bottom']})
    return bc


def mms_traction(plane):
    fields = {}
    for tag, normal in NORMALS.items():
        def field(p, n, normal=normal):
            assert_allclose(n, np.broadcast_to(normal, p.shape), rtol=0, atol=1e-13)
            return surface(p, n, plane)
        fields[tag] = field
    return fields


def check_work(mesh, result, plane, bc):
    e = strain_fit(mesh, result.displacement)
    s = stress(e, plane)
    assert_allclose(result.strain, e, rtol=1e-9, atol=1e-12)
    assert_allclose(result.stress, s, rtol=1e-9, atol=1e-6)
    _, _, w = integration(mesh, 7)
    area = w.sum(axis=1)
    twice_u = np.sum(area*np.sum(e*s, axis=-1))
    applied_work = np.sum(result.displacement*result.load)
    support_work = sum(result.reaction[i, c]*value for (i, c), value in bc.items())
    assert abs(twice_u-applied_work-support_work) <= 1e-9*max(abs(twice_u), abs(applied_work), abs(support_work), 1e-20)
    force = result.load+result.reaction
    scale = max(np.linalg.norm(result.load, axis=1).sum(), 1.)
    assert np.linalg.norm(force.sum(axis=0)) <= 1e-9*scale
    assert abs(np.sum(mesh.nodes[:, 0]*force[:, 1]-mesh.nodes[:, 1]*force[:, 0])) <= 1e-9*scale
    v = mesh.nodes@np.array([[.003, .001], [-.002, -.004]]).T+[.001, -.002]
    virtual_strain = np.array([.003, -.004, -.001])
    internal = np.sum(area*np.sum(s*virtual_strain, axis=-1))
    external = np.sum(force*v)
    assert abs(internal-external) <= 1e-9*scale*np.max(abs(v))
    return twice_u/2, applied_work, support_work


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_traction_independent_oracle_differentiation(plane):
    p = np.array([[.19, .37], [.83, .42], [.61, .78]])
    h = 1e-5
    dx, dy = np.eye(2)*h
    _, e, _, f = manufactured(p, plane)
    ux = (manufactured(p+dx, plane)[0]-manufactured(p-dx, plane)[0])/(2*h)
    uy = (manufactured(p+dy, plane)[0]-manufactured(p-dy, plane)[0])/(2*h)
    assert_allclose(e, np.c_[ux[:, 0], uy[:, 1], uy[:, 0]+ux[:, 1]], rtol=1e-8, atol=1e-12)
    sx = (manufactured(p+dx, plane)[2]-manufactured(p-dx, plane)[2])/(2*h)
    sy = (manufactured(p+dy, plane)[2]-manufactured(p-dy, plane)[2])/(2*h)
    assert_allclose(f, -np.c_[sx[:, 0]+sy[:, 2], sx[:, 2]+sy[:, 1]], rtol=1e-9, atol=1e-6)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_traction_independent_mixed_mms_convergence(plane):
    history = []
    for n in (6, 12, 24):
        mesh = rectangle_mesh(1., 1., n, n)
        bc = mixed_bc(mesh, plane)
        r = solve(mesh, plane, dirichlet=bc, body_force=lambda p: manufactured(p, plane)[3], traction=mms_traction(plane))
        expected_load = consistent_load(mesh, plane)
        assert_allclose(r.load, expected_load, rtol=1e-11, atol=1e-8)
        # Direct continuum body+full-surface resultants cancel. Nodal moment is
        # exact because the consistent shape functions reproduce coordinates.
        assert_allclose(expected_load.sum(axis=0), 0., atol=1e-8)
        assert abs(np.sum(mesh.nodes[:, 0]*expected_load[:, 1]-mesh.nodes[:, 1]*expected_load[:, 0])) < 1e-8
        check_work(mesh, r, plane, bc)
        error = errors(mesh, r, plane, 7)
        assert_allclose(errors(mesh, r, plane, 5), error, rtol=1e-9)
        history.append(error)
    history = np.array(history); orders = np.log2(history[:-1]/history[1:])
    print('\nINDEPENDENT_TRACTION '+json.dumps(dict(plane=plane, n=[6,12,24], errors=history.tolist(), orders=orders.tolist())))
    assert np.all(np.diff(history, axis=0) < 0)
    assert orders[-1, 0] >= 1.8
    assert np.all(orders[-1, 1:] >= .9)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('kind', ['uniaxial', 'shear'])
def test_traction_independent_affine_compliance(plane, kind):
    mesh = rectangle_mesh(1.1, .6, 5, 4)
    if kind == 'uniaxial':
        p = 127.
        ey = p/E if plane == 'stress' else (1-NU**2)*p/E
        ex = -NU*p/E if plane == 'stress' else -NU*(1+NU)*p/E
        u = mesh.nodes*[ex, ey]
        bc = {(int(i), 1): 0. for i in mesh.boundary['bottom']}
        bc.update({(int(i), 0): 0. for i in mesh.boundary['left']})
        traction, target = {'top': (0., p)}, [0., p, 0.]
    else:
        tau, mu = 91., E/(2*(1+NU))
        u = np.c_[np.zeros(mesh.num_nodes), tau/mu*mesh.nodes[:, 0]]
        bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
        traction, target = {'top': (tau, 0.), 'bottom': (-tau, 0.), 'right': (0., tau)}, [0., 0., tau]
    r = solve(mesh, plane, dirichlet=bc, traction=traction)
    assert_allclose(r.displacement, u, rtol=1e-9, atol=1e-12)
    assert_allclose(r.stress, np.tile(target, (mesh.num_triangles, 1)), rtol=1e-9, atol=1e-6)
    check_work(mesh, r, plane, bc)


@pytest.mark.parametrize('segments', [1, 3, 9])
def test_traction_independent_degree_six_consistent_weights(segments):
    mesh = rectangle_mesh(1., 1., 1, segments)
    field = lambda p, n: np.c_[3+2*p[:, 1]**6, -4+p[:, 1]**5]
    r = solve(mesh, dirichlet=fixed(mesh), traction={'right': field})
    expected = right_edge_load(mesh)
    assert_allclose(r.load, expected, rtol=1e-11, atol=1e-12)
    assert_allclose(r.load.sum(axis=0), [3+2/7, -4+1/6], rtol=1e-11)
    moment = np.sum(mesh.nodes[:, 0]*r.load[:, 1]-mesh.nodes[:, 1]*r.load[:, 0])
    assert_allclose(moment, -4+1/6-1.5-2/8, rtol=1e-11)
    assert_allclose(r.reaction, -r.load, atol=1e-12)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_traction_independent_dirichlet_overlap_and_default(plane):
    mesh = rectangle_mesh(1., 1., 4, 3)
    u = mesh.nodes@np.array([[.001, -.002], [.003, .004]]).T+[.002, -.001]
    bc = fixed(mesh, u)
    baseline = solve(mesh, plane, dirichlet=bc)
    for traction in (None, {}):
        r = solve(mesh, plane, dirichlet=bc, traction=traction)
        for name in ('displacement', 'strain', 'stress', 'load', 'reaction', 'residual'):
            assert np.array_equal(getattr(r, name), getattr(baseline, name))
    r = solve(mesh, plane, dirichlet=bc, traction={'right': lambda p, n: np.c_[3+2*p[:, 1]**6, -4+p[:, 1]**5]})
    assert_allclose(r.displacement, baseline.displacement, rtol=0, atol=0)
    assert_allclose(r.reaction-baseline.reaction, -r.load, rtol=1e-10, atol=1e-8)
    energy, external, support = check_work(mesh, r, plane, bc)
    assert abs(2*energy-external) > 1e-3  # support work cannot be dropped


@pytest.mark.parametrize('hole', [False, True])
@pytest.mark.parametrize('pressure_sign', [-1., 1.])
def test_traction_independent_pressure_normals_order_rotation(hole, pressure_sign):
    mesh = annulus_mesh(.35, 1., 2, 15) if hole else rectangle_mesh(1., .7, 4, 3)
    pressure = 73.*pressure_sign  # -P*n compresses when pressure_sign=-1
    center = np.zeros(2)
    def fields_for(m, rotation=np.eye(2), offset=center):
        fields = {}
        for tag in m.boundary_edges:
            def field(p, normal, tag=tag):
                if hole:
                    # For a regular polygon, the facet normal is parallel to
                    # its midpoint, not the radial vector at each Gauss point.
                    assert_allclose(np.linalg.norm(normal, axis=1), 1., atol=1e-13)
                    dot = np.sum((p-offset)*normal, axis=1)
                    assert np.all(dot < 0) if tag == 'inner' else np.all(dot > 0)
                else:
                    assert_allclose(normal, np.broadcast_to(np.asarray(NORMALS[tag])@rotation.T, p.shape), atol=1e-13)
                return pressure*normal
            fields[tag] = field
        return fields
    expected = np.zeros_like(mesh.nodes)
    for tag, edges in mesh.boundary_edges.items():
        for i, j in edges:
            mid = (mesh.nodes[i]+mesh.nodes[j])/2
            if hole:
                normal = mid/np.linalg.norm(mid)*(1 if tag == 'outer' else -1)
            else:
                normal = np.asarray(NORMALS[tag])
            expected[[i, j]] += .5*pressure*np.linalg.norm(mesh.nodes[j]-mesh.nodes[i])*normal
    base = solve(mesh, dirichlet=fixed(mesh), traction=fields_for(mesh))
    assert_allclose(base.load, expected, rtol=1e-10, atol=1e-8)
    assert_allclose(base.reaction, -expected, rtol=1e-10, atol=1e-8)
    theta = .41; q = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    shift, scale = np.array([1.7, -2.1]), 2.
    rng = np.random.default_rng(31); permutation = rng.permutation(mesh.num_nodes); inverse = np.argsort(permutation)
    cells = rng.permutation(mesh.num_triangles)
    changed = Mesh((scale*mesh.nodes@q.T+shift)[permutation], inverse[mesh.triangles[cells]][:, ::-1],
                   {tag: inverse[v] for tag, v in mesh.boundary.items()},
                   {tag: inverse[e][::-1, ::-1] for tag, e in reversed(list(mesh.boundary_edges.items()))})
    r = solve(changed, dirichlet=fixed(changed), traction=fields_for(changed, q, shift))
    assert_allclose(r.load, (scale*base.load@q.T)[permutation], rtol=1e-10, atol=1e-8)
    assert_allclose(r.reaction, -r.load, atol=1e-8)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_traction_independent_displacement_stress_covariance(plane):
    mesh = rectangle_mesh(1., 1., 6, 6)
    u = manufactured(mesh.nodes, plane)[0]
    bc = {(int(i), c): float(u[i, c]) for i in mesh.boundary['left'] for c in (0, 1)}
    base = solve(mesh, plane, dirichlet=bc, body_force=lambda p: manufactured(p, plane)[3], traction=mms_traction(plane))
    angle, scale = .41, 2.
    q = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    shift = np.array([1.7, -2.1])
    rng = np.random.default_rng(77); permutation = rng.permutation(mesh.num_nodes); inverse = np.argsort(permutation)
    cells = rng.permutation(mesh.num_triangles)
    rotated = Mesh((scale*mesh.nodes@q.T+shift)[permutation], inverse[mesh.triangles[cells]][:, ::-1],
                   {tag: inverse[v] for tag, v in mesh.boundary.items()},
                   {tag: inverse[e][::-1, ::-1] for tag, e in reversed(list(mesh.boundary_edges.items()))})
    target = (scale*u@q.T)[permutation]
    rb = {(int(i), c): float(target[i, c]) for i in rotated.boundary['left'] for c in (0, 1)}
    def traction(p, normal):
        return surface((p-shift)@q/scale, normal@q, plane)@q.T
    r = solve(rotated, plane, dirichlet=rb,
              body_force=lambda p: manufactured((p-shift)@q/scale, plane)[3]@q.T/scale,
              traction={tag: traction for tag in rotated.boundary_edges})
    assert_allclose(r.displacement, (scale*base.displacement@q.T)[permutation], rtol=1e-10, atol=1e-12)
    assert_allclose(r.load, (scale*base.load@q.T)[permutation], rtol=1e-10, atol=1e-8)
    assert_allclose(r.reaction, (scale*base.reaction@q.T)[permutation], rtol=1e-10, atol=1e-8)
    s = base.stress[cells]
    tensor = np.stack((np.stack((s[:, 0], s[:, 2]), axis=-1), np.stack((s[:, 2], s[:, 1]), axis=-1)), axis=1)
    expected = q@tensor@q.T
    assert_allclose(r.stress, np.c_[expected[:, 0, 0], expected[:, 1, 1], expected[:, 0, 1]], rtol=1e-10, atol=1e-6)
    u0 = check_work(mesh, base, plane, bc)[0]
    u1 = check_work(rotated, r, plane, rb)[0]
    assert_allclose(u1, scale**2*u0, rtol=1e-10)


@pytest.mark.parametrize('bad', ['duplicate_tag', 'duplicate_edge', 'interior', 'shape', 'float_index', 'negative', 'self', 'missing_tag', 'callback_shape', 'callback_transpose', 'nan', 'complex', 'normal_nan', 'rigid'])
def test_traction_independent_rejection_contract(bad):
    mesh = rectangle_mesh(1., 1., 2, 2)
    bc = fixed(mesh); traction = {'right': (1., 2.)}
    if bad == 'duplicate_tag':
        mesh.boundary_edges['alias'] = mesh.boundary_edges['right'][::-1, ::-1]; traction['alias'] = (3., 4.)
    elif bad == 'duplicate_edge': mesh.boundary_edges['right'] = np.vstack([mesh.boundary_edges['right'], mesh.boundary_edges['right'][0, ::-1]])
    elif bad == 'interior': mesh.boundary_edges['right'] = np.array([[0, 4]])
    elif bad == 'shape': mesh.boundary_edges['right'] = np.zeros((2, 3), int)
    elif bad == 'float_index': mesh.boundary_edges['right'] = mesh.boundary_edges['right'].astype(float)
    elif bad == 'negative': mesh.boundary_edges['right'] = np.array([[-1, 2]])
    elif bad == 'self': mesh.boundary_edges['right'] = np.array([[2, 2]])
    elif bad == 'missing_tag': traction = {'node_only': (1., 2.)}; mesh.boundary['node_only'] = mesh.boundary['right']
    elif bad == 'callback_shape': traction['right'] = lambda p, n: np.array([1., 2.])
    elif bad == 'callback_transpose': traction['right'] = lambda p, n: np.ones((2, len(p)))
    elif bad == 'nan': traction['right'] = (np.nan, 2.)
    elif bad == 'complex': traction['right'] = lambda p, n: np.ones(p.shape, complex)
    elif bad == 'normal_nan': traction['right'] = lambda p, n: n*np.nan
    elif bad == 'rigid': bc = {}
    with pytest.raises(ValueError):
        solve(mesh, dirichlet=bc, traction=traction)
