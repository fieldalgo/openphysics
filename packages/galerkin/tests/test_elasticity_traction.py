# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent traction acceptance: exact fields, quadrature, work and balance."""
import numpy as np
import pytest
from numpy.testing import assert_allclose
from galerkin.mesh import Mesh, rectangle_mesh, annulus_mesh
from galerkin.elasticity import solve_elasticity
from refsol import elasticity_traction as oracle

MATERIAL = dict(young_modulus=70000., poisson_ratio=.3)


def solve(mesh, plane="stress", **kwargs):
    return solve_elasticity(mesh, **MATERIAL, plane=plane, **kwargs)


def fixed(mesh, tag, values=None):
    return {(int(i), c): 0. if values is None else values[i, c]
            for i in mesh.boundary[tag] for c in (0, 1)}


def all_boundary_fixed(mesh, values=None):
    return {key: val for tag in mesh.boundary for key, val in fixed(mesh, tag, values).items()}


def force_moment_work(mesh, result):
    total = result.load+result.reaction
    scale = max(np.linalg.norm(result.load, axis=1).sum(), np.finfo(float).tiny)
    assert np.linalg.norm(total.sum(axis=0))/scale <= 1e-9
    moment = np.sum(mesh.nodes[:, 0]*total[:, 1]-mesh.nodes[:, 1]*total[:, 0])
    size = np.linalg.norm(np.ptp(mesh.nodes, axis=0))
    assert abs(moment)/(size*scale) <= 1e-9
    energy = .5*np.sum(mesh.areas()*np.sum(result.strain*result.stress, axis=1))
    work = .5*np.sum(result.displacement*total)
    assert abs(work-energy) <= 1e-10*max(abs(energy), 1e-20)
    return energy


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_traction_uniform_uniaxial_closed_form(plane):
    m = rectangle_mesh(1.2, .7, 6, 5)
    exact = oracle.uniaxial(m.nodes, 123., **MATERIAL, plane=plane)
    bc = {(int(i), 0): 0. for i in m.boundary["left"]}
    bc.update({(int(i), 1): 0. for i in m.boundary["bottom"]})
    r = solve(m, plane, dirichlet=bc, traction={"right": (123., 0.)})
    assert_allclose(r.displacement, exact.displacement, rtol=1e-10, atol=1e-14)
    assert_allclose(r.strain, np.tile(exact.strain[0], (m.num_triangles, 1)), rtol=1e-10, atol=1e-14)
    assert_allclose(r.stress, np.tile([123., 0, 0], (m.num_triangles, 1)), rtol=1e-10, atol=1e-10)
    assert_allclose(r.load.sum(axis=0), [123*.7, 0], rtol=1e-12, atol=1e-12)
    expected_energy = .5*123*exact.strain[0, 0]*1.2*.7
    assert_allclose(force_moment_work(m, r), expected_energy, rtol=1e-10)


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_traction_uniform_shear_closed_form(plane):
    m = rectangle_mesh(1.2, .7, 6, 5)
    exact = oracle.shear(m.nodes, 87., **MATERIAL, plane=plane)
    r = solve(m, plane, dirichlet=fixed(m, "bottom"),
              traction={"top": (87., 0.), "right": (0., 87.), "left": (0., -87.)})
    assert_allclose(r.displacement, exact.displacement, rtol=1e-10, atol=1e-14)
    assert_allclose(r.strain, np.tile([0, 0, exact.strain[0, 2]], (m.num_triangles, 1)), atol=1e-13)
    assert_allclose(r.stress, np.tile([0, 0, 87.], (m.num_triangles, 1)), atol=1e-9)
    force_moment_work(m, r)


@pytest.mark.parametrize("degree", [1, 6])
def test_traction_consistent_nodal_weights_and_origin_moment(degree):
    m = rectangle_mesh(1, 1, 1, 1)
    if degree == 1:
        field = lambda p, n: np.column_stack([2+3*p[:, 1], -1+4*p[:, 1]])
        expected = [[1.5, 1/6], [2., 5/6]]
        moment = -1.
    else:
        field = lambda p, n: np.column_stack([p[:, 1]**6, p[:, 1]**5])
        expected = [[1/56, 1/42], [1/8, 1/7]]
        moment = 1/24
    r = solve(m, dirichlet=all_boundary_fixed(m), traction={"right": field})
    assert_allclose(r.load[m.boundary["right"]], expected, rtol=1e-12, atol=1e-14)
    assert_allclose(np.sum(m.nodes[:, 0]*r.load[:, 1]-m.nodes[:, 1]*r.load[:, 0]), moment, atol=1e-13)
    assert_allclose(r.reaction, -r.load, rtol=0, atol=0)


def test_traction_dirichlet_overlap_preserves_load_and_support_work():
    m = rectangle_mesh(1, .8, 4, 4)
    values = m.nodes @ np.array([[.002, -.001], [.003, .0005]]).T + [.001, -.002]
    bc = all_boundary_fixed(m, values)
    zero = solve(m, dirichlet=bc)
    r = solve(m, dirichlet=bc, traction={"right": (5., -7.), "left": (-3., 4.)})
    assert_allclose(r.displacement, zero.displacement, rtol=0, atol=0)
    assert_allclose(r.reaction, zero.reaction-r.load, atol=1e-12)
    assert np.linalg.norm(r.load) > 0
    force_moment_work(m, r)
    # Ignoring prescribed-displacement reaction work is an incorrect work law.
    energy = .5*np.sum(m.areas()*np.sum(r.strain*r.stress, axis=1))
    assert abs(.5*np.sum(r.displacement*r.load)-energy) > .1*energy


def test_traction_zero_default_and_constant_callback_agree():
    m = rectangle_mesh(1, 1, 3, 3)
    bc = fixed(m, "left")
    a = solve(m, dirichlet=bc, body_force=(0., -2.))
    for traction in (None, {}):
        b = solve(m, dirichlet=bc, body_force=(0., -2.), traction=traction)
        for name in ("displacement", "strain", "stress", "load", "reaction", "residual"):
            assert np.array_equal(getattr(a, name), getattr(b, name))
    a = solve(m, dirichlet=bc, traction={"right": (3., 5.)})
    b = solve(m, dirichlet=bc, traction={"right": lambda p, n: np.tile([3., 5.], (len(p), 1))})
    assert_allclose(a.load, b.load, rtol=0, atol=0)
    assert_allclose(a.displacement, b.displacement, rtol=0, atol=0)


def test_traction_normal_sign_edge_direction_and_triangle_orientation():
    m = rectangle_mesh(1.2, .7, 4, 3)
    expected_normal = {"left": [-1,0], "right": [1,0], "bottom": [0,-1], "top": [0,1]}
    fields = {}
    for tag, normal in expected_normal.items():
        def field(p, n, normal=normal):
            assert_allclose(n, np.tile(normal, (len(p), 1)), rtol=0, atol=1e-14)
            return oracle.traction_from_stress(np.tile([11., -5., 3.], (len(p), 1)), n)
        fields[tag] = field
    a = solve(m, dirichlet=all_boundary_fixed(m), traction=fields)
    m.triangles = m.triangles[:, ::-1]
    m.boundary_edges = {tag: edges[::-1, ::-1] for tag, edges in m.boundary_edges.items()}
    b = solve(m, dirichlet=all_boundary_fixed(m), traction=dict(reversed(list(fields.items()))))
    assert_allclose(a.load, b.load, rtol=0, atol=1e-13)
    assert_allclose(a.load.sum(axis=0), 0, atol=1e-13)
    assert_allclose(np.sum(m.nodes[:,0]*a.load[:,1]-m.nodes[:,1]*a.load[:,0]), 0, atol=1e-13)


def test_traction_hole_normals_point_into_hole():
    m = annulus_mesh(.4, 1., 3, 16)
    seen = []
    def field(p, n):
        assert_allclose(np.linalg.norm(n, axis=1), 1, atol=1e-14)
        assert np.all(np.sum(p*n, axis=1) < 0)
        seen.append(len(p))
        return np.tile([2., -3.], (len(p), 1))
    r = solve(m, dirichlet=fixed(m, "outer"), traction={"inner": field})
    circumference = 2*16*.4*np.sin(np.pi/16)
    assert seen == [16*4]
    assert_allclose(r.load.sum(axis=0), circumference*np.array([2., -3.]), rtol=1e-12)
    force_moment_work(m, r)


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_traction_rigid_rotation_translation_and_length_units(plane):
    m = rectangle_mesh(1, .8, 5, 4)
    exact = oracle.uniaxial(m.nodes, 123., **MATERIAL, plane=plane)
    a = solve(m, plane, dirichlet=fixed(m, "left", exact.displacement), traction={"right": (123., 0.)})
    angle = .37
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    m.nodes = 2*m.nodes @ rotation.T + [3., -5.]
    target = 2*exact.displacement @ rotation.T
    b = solve(m, plane, dirichlet=fixed(m, "left", target), traction={"right": rotation @ [123., 0.]})
    assert_allclose(b.displacement, 2*a.displacement @ rotation.T, rtol=1e-10, atol=1e-13)
    assert_allclose(b.load, 2*a.load @ rotation.T, rtol=1e-10, atol=1e-12)
    sigma = rotation @ np.diag([123., 0.]) @ rotation.T
    assert_allclose(b.stress, np.tile([sigma[0,0],sigma[1,1],sigma[0,1]], (m.num_triangles,1)), atol=1e-9)
    assert_allclose(force_moment_work(m, b), 4*force_moment_work(rectangle_mesh(1,.8,5,4), a), rtol=1e-10)


def integration_rule():
    z, w = np.polynomial.legendre.leggauss(8)
    z, w = (z+1)/2, w/2
    a, b = np.meshgrid(z, z, indexing="ij")
    return np.column_stack([((1-a)*(1-b)).ravel(), (a*(1-b)).ravel(), b.ravel()]), (2*w[:,None]*w[None,:]*(1-b)).ravel()


@pytest.mark.slow
@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_traction_nonuniform_polynomial_manufactured_convergence(plane):
    bary, weights = integration_rule()
    errors = []
    force_exact, moment_exact = oracle.polynomial_resultants(**MATERIAL, plane=plane)
    for n in (8,16,32):
        m = rectangle_mesh(1, 1, n, n)
        field = lambda p: oracle.polynomial_manufactured(p, **MATERIAL, plane=plane)
        tr = lambda p, normal: oracle.polynomial_traction(p, normal, **MATERIAL, plane=plane)
        r = solve(m, plane, dirichlet=fixed(m, "left"), body_force=lambda p: field(p).body_force,
                  traction={tag: tr for tag in ("right", "top", "bottom")})
        assert_allclose(r.load.sum(axis=0), force_exact, rtol=1e-12, atol=1e-12)
        assert_allclose(np.sum(m.nodes[:,0]*r.load[:,1]-m.nodes[:,1]*r.load[:,0]), moment_exact, rtol=1e-12)
        energy = force_moment_work(m, r)
        p = np.einsum("qa,tad->tqd", bary, m.nodes[m.triangles])
        exact = field(p.reshape(-1,2))
        de = r.strain[:,None,:]-exact.strain.reshape(m.num_triangles,-1,3)
        ds = r.stress[:,None,:]-exact.stress.reshape(m.num_triangles,-1,3)
        du = np.einsum("qa,tad->tqd", bary, r.displacement[m.triangles])-exact.displacement.reshape(p.shape)
        strain_density = de[...,0]**2+de[...,1]**2+.5*de[...,2]**2
        energy_squared = np.einsum("tqi,tqi,q,t->", de, ds, weights, m.areas())
        errors.append([np.sqrt(np.einsum("tqd,tqd,q,t->", du, du, weights, m.areas())),
                       np.sqrt(np.einsum("tq,q,t->", strain_density, weights, m.areas())),
                       np.sqrt(energy_squared)])
        exact_density = np.sum(exact.strain*exact.stress, axis=1).reshape(m.num_triangles,-1)
        exact_energy = .5*np.einsum("tq,q,t->", exact_density, weights, m.areas())
        # Galerkin orthogonality with homogeneous essential data:
        # 2*(U_exact-U_h) = ||u_exact-u_h||_energy^2.
        assert abs(2*(exact_energy-energy)-energy_squared) <= 1e-8*exact_energy
    errors = np.asarray(errors)
    orders = np.log2(errors[:-1]/errors[1:])
    print(f"\nTRACTION {plane}: errors(L2,strain,energy)={errors.tolist()}, orders={orders.tolist()}")
    assert np.all(np.diff(errors,axis=0)<0)
    assert orders[-1,0] >= 1.8
    assert np.all(orders[-1,1:] >= .9)


@pytest.mark.parametrize("traction", [[], (1,2), {"absent": (1,2)}, {"right": 3},
    {"right": [1]}, {"right": [1,2,3]}, {"right": [np.nan,0]}, {"right": [0,1j]},
    {"right": lambda p,n: np.zeros(2)}, {"right": lambda p,n: np.full(p.shape,np.inf)}])
def test_traction_reject_invalid_inputs(traction):
    m = rectangle_mesh(1,1,2,2)
    with pytest.raises(ValueError):
        solve(m, dirichlet=fixed(m,"left"), traction=traction)


@pytest.mark.parametrize("edges", [[], np.empty((0,2),dtype=int), [1,2], [[0,1,2]],
    np.array([[2.,5.]]), [[-1,2]], [[2,100]], [[2,2]], [[0,4]], [[0,8]], [[2,5],[5,2]]])
def test_traction_reject_invalid_selected_edges(edges):
    m = rectangle_mesh(1,1,2,2)
    m.boundary_edges["selected"] = np.asarray(edges)
    with pytest.raises(ValueError):
        solve(m, dirichlet=fixed(m,"left"), traction={"selected": (1,2)})


def test_traction_duplicate_selected_tags_and_node_only_tag_rejected():
    m = rectangle_mesh(1,1,2,2)
    m.boundary_edges["alias"] = m.boundary_edges["right"].copy()
    with pytest.raises(ValueError, match="duplicate traction edge"):
        solve(m, dirichlet=fixed(m,"left"), traction={"right": (1,0), "alias": (0,1)})
    m.boundary["node_only"] = m.boundary["right"]
    with pytest.raises(ValueError, match="no boundary_edges"):
        solve(m, dirichlet=fixed(m,"left"), traction={"node_only": (1,0)})


def test_traction_balanced_pure_load_does_not_remove_rigid_modes():
    m = rectangle_mesh(1,1,2,2)
    with pytest.raises(ValueError, match="rigid modes"):
        solve(m, dirichlet={}, traction={"left": (-1,0), "right": (1,0)})
