# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Elasticity acceptance gates fixed before implementation and results."""
import numpy as np
import pytest
from numpy.testing import assert_allclose
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.elasticity import solve_elasticity, constitutive_matrix
from refsol.elasticity import affine, sine_manufactured

MATERIAL = dict(young_modulus=70000., poisson_ratio=.3)


def boundary_values(mesh, values):
    nodes = np.unique(np.concatenate(list(mesh.boundary.values())))
    return {(int(i), c): values[i, c] for i in nodes for c in (0, 1)}


def solve(mesh, plane="stress", **kwargs):
    return solve_elasticity(mesh, **MATERIAL, plane=plane, **kwargs)


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_elasticity_affine_patch(plane):
    m = rectangle_mesh(1.3, .8, 6, 5)
    # Perturb interior vertices; constant-strain reproduction must not rely on a grid.
    boundary = np.unique(np.concatenate(list(m.boundary.values())))
    interior = np.setdiff1d(np.arange(m.num_nodes), boundary)
    m.nodes[interior] += np.random.default_rng(123).uniform(-.025, .025, (len(interior), 2))
    exact = affine(m.nodes, [[.002, .003], [-.001, -.0005]], [.001, -.002],
                   **MATERIAL, plane=plane)
    result = solve(m, plane, dirichlet=boundary_values(m, exact.displacement))
    assert_allclose(result.displacement, exact.displacement, rtol=1e-10, atol=1e-14)
    assert_allclose(result.strain, np.tile(exact.strain[0], (m.num_triangles, 1)), rtol=1e-10, atol=1e-14)
    assert_allclose(result.stress, np.tile(exact.stress[0], (m.num_triangles, 1)), rtol=1e-10, atol=1e-10)
    assert_allclose(result.reaction.sum(axis=0), 0, atol=1e-9)


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_elasticity_rigid_body_strain_zero(plane):
    m = rectangle_mesh(1., 1., 4, 4)
    exact = affine(m.nodes, [[0, -.002], [.002, 0]], [.003, -.001], **MATERIAL, plane=plane)
    result = solve(m, plane, dirichlet=boundary_values(m, exact.displacement))
    assert_allclose(result.displacement, exact.displacement, rtol=0, atol=1e-12)
    assert_allclose(result.strain, 0, rtol=0, atol=1e-12)


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_elasticity_component_dirichlet_zero_traction_extension(plane):
    m = rectangle_mesh(1., 1., 5, 5)
    a, nu, e = .001, MATERIAL["poisson_ratio"], MATERIAL["young_modulus"]
    bc = {(int(i), 0): 0. for i in m.boundary["left"]}
    bc.update({(int(i), 0): a for i in m.boundary["right"]})
    bc.update({(int(i), 1): 0. for i in m.boundary["bottom"]})
    result = solve(m, plane, dirichlet=bc)
    lateral = -nu*a if plane == "stress" else -nu/(1-nu)*a
    axial = e*a if plane == "stress" else e/(1-nu**2)*a
    assert_allclose(result.displacement, m.nodes*[a, lateral], rtol=1e-10, atol=1e-13)
    assert_allclose(result.stress, np.tile([axial, 0, 0], (m.num_triangles, 1)), atol=1e-9)
    assert_allclose(result.reaction[m.boundary["right"], 0].sum(), axial, rtol=1e-10)


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_elasticity_body_force_reaction_and_moment_balance(plane):
    m = rectangle_mesh(1.2, .7, 8, 6)
    bc = {(int(i), c): 0. for i in m.boundary["left"] for c in (0, 1)}
    force = np.array([3., -5.])
    result = solve(m, plane, dirichlet=bc, body_force=force)
    assert_allclose(result.load.sum(axis=0), force*1.2*.7, rtol=1e-12)
    imbalance = result.load+result.reaction
    assert np.linalg.norm(imbalance.sum(axis=0)) / np.linalg.norm(result.load.sum(axis=0)) < 1e-9
    moment = np.sum(m.nodes[:, 0]*imbalance[:, 1]-m.nodes[:, 1]*imbalance[:, 0])
    assert abs(moment) < 1e-9*np.linalg.norm(result.load.sum(axis=0))
    assert_allclose(result.residual[[i for i in range(m.num_nodes) if i not in m.boundary["left"]]],
                    0, atol=1e-11)


def integration_rule():
    # Independent Duffy convention (x=a*(1-b), y=b), 8x8 Gauss rule.
    z, w = np.polynomial.legendre.leggauss(8)
    z, w = (z+1)/2, w/2
    a, b = np.meshgrid(z, z, indexing="ij")
    bary = np.column_stack([((1-a)*(1-b)).ravel(), (a*(1-b)).ravel(), b.ravel()])
    return bary, (2*w[:, None]*w[None, :]*(1-b)).ravel()


@pytest.mark.slow
@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_elasticity_smooth_manufactured_convergence(plane):
    bary, weights = integration_rule()
    errors = []
    for n in (8, 16, 32):
        m = rectangle_mesh(1., 1., n, n)
        exact = sine_manufactured(m.nodes, **MATERIAL, plane=plane)
        force = lambda p: sine_manufactured(p, **MATERIAL, plane=plane).body_force
        r = solve(m, plane, dirichlet=boundary_values(m, exact.displacement), body_force=force)
        p = np.einsum("qa,tad->tqd", bary, m.nodes[m.triangles])
        fields = sine_manufactured(p.reshape(-1, 2), **MATERIAL, plane=plane)
        du = np.einsum("qa,tad->tqd", bary, r.displacement[m.triangles])-fields.displacement.reshape(p.shape)
        de = r.strain[:, None, :]-fields.strain.reshape(len(m.triangles), -1, 3)
        # Tensor Frobenius strain norm: exx^2+eyy^2+2*exy^2.
        strain_density = de[..., 0]**2+de[..., 1]**2+.5*de[..., 2]**2
        d = constitutive_matrix(**MATERIAL, plane=plane)
        energy_density = np.einsum("tqi,ij,tqj->tq", de, d, de)
        area = m.areas()
        errors.append([np.sqrt(np.einsum("tq,q,t->", np.sum(du*du, axis=2), weights, area)),
                       np.sqrt(np.einsum("tq,q,t->", strain_density, weights, area)),
                       np.sqrt(np.einsum("tq,q,t->", energy_density, weights, area))])
        assert np.linalg.norm((r.load+r.reaction).sum(axis=0)) / np.linalg.norm(r.load.sum(axis=0)) < 1e-9
    errors = np.asarray(errors)
    orders = np.log2(errors[:-1]/errors[1:])
    print(f"\nELASTICITY {plane}: errors(L2,strain,energy)={errors.tolist()}, orders={orders.tolist()}")
    assert np.all(np.diff(errors, axis=0) < 0)
    assert orders[-1, 0] >= 1.8
    assert np.all(orders[-1, 1:] >= .9)


@pytest.mark.parametrize("kwargs", [
    {"young_modulus": 0}, {"young_modulus": -1}, {"young_modulus": np.inf},
    {"young_modulus": 1j}, {"young_modulus": [1]}, {"poisson_ratio": -.9999999999999999-1},
    {"poisson_ratio": -1}, {"poisson_ratio": .5}, {"poisson_ratio": np.nan}, {"plane": "auto"},
])
def test_elasticity_reject_material(kwargs):
    args = {**MATERIAL, "plane": "stress", **kwargs}
    with pytest.raises(ValueError):
        constitutive_matrix(**args)


@pytest.mark.parametrize("bc", [{}, {(0, 0): 0}, {(0, 0): 0, (0, 1): 0},
                                   {(0, 0): 0, (1, 0): 0, (2, 0): 0}])
def test_elasticity_reject_rigid_modes(bc):
    with pytest.raises(ValueError, match="rigid modes"):
        solve(rectangle_mesh(1, 1, 2, 2), dirichlet=bc)


def test_elasticity_disconnected_components_need_separate_constraints():
    a, b = rectangle_mesh(1, 1, 1, 1), rectangle_mesh(1, 1, 1, 1)
    p = np.vstack([a.nodes, b.nodes+[2, 0]])
    m = Mesh(p, np.vstack([a.triangles, b.triangles+4]), {})
    with pytest.raises(ValueError, match="component 1"):
        solve(m, dirichlet={(0, 0): 0, (0, 1): 0, (1, 1): 0})
    r = solve(m, dirichlet={(i, c): 0 for i in range(8) for c in (0, 1)})
    assert_allclose(r.displacement, 0)


@pytest.mark.parametrize("bc", [{(-1, 0): 0}, {(100, 0): 0}, {(0, 2): 0}, {(0., 0): 0},
                                   {(True, 0): 0}, {(0, 0): np.nan}, {(0, 0): [0]},
                                   {0: 0}, {(4, 0): 0}])
def test_elasticity_reject_dirichlet(bc):
    with pytest.raises(ValueError):
        solve(rectangle_mesh(1, 1, 2, 2), dirichlet=bc)


@pytest.mark.parametrize("force", [1, [1], [1, 2, 3], [np.nan, 0], [1j, 0],
                                     lambda p: np.zeros(2), lambda p: np.full(p.shape, np.inf)])
def test_elasticity_reject_force(force):
    m = rectangle_mesh(1, 1, 1, 1)
    with pytest.raises(ValueError):
        solve(m, dirichlet=boundary_values(m, np.zeros_like(m.nodes)), body_force=force)


@pytest.mark.parametrize("mutation", ["nan", "shape", "index", "fractional", "degenerate", "duplicate", "unused"])
def test_elasticity_reject_bad_mesh_arrays(mutation):
    m = rectangle_mesh(1, 1, 2, 2)
    if mutation == "nan": m.nodes[0, 0] = np.nan
    if mutation == "shape": m.nodes = np.zeros((m.num_nodes, 3))
    if mutation == "index": m.triangles[0, 0] = -1
    if mutation == "fractional": m.triangles = m.triangles.astype(float)
    if mutation == "degenerate": m.nodes[1] = (m.nodes[0]+m.nodes[4])/2
    if mutation == "duplicate": m.triangles = np.vstack([m.triangles, m.triangles[0]])
    if mutation == "unused": m.nodes = np.vstack([m.nodes, [2, 2]])
    with pytest.raises(ValueError):
        solve(m, dirichlet={})


def test_elasticity_reject_hinge_overlap_and_hanging_node():
    cases = [
        ([[0,0],[1,0],[0,1],[-1,0],[0,-1]], [[0,1,2],[0,3,4]]),
        ([[0,0],[1,0],[0,1],[.1,.1],[.7,.1],[.1,.7]], [[0,1,2],[3,4,5]]),
        ([[0,0],[1,0],[0,1],[.5,0],[0,-1]], [[0,1,2],[0,4,3],[3,4,1]]),
    ]
    for p, t in cases:
        with pytest.raises(ValueError):
            solve(Mesh(np.array(p), np.array(t), {}), dirichlet={})


def test_elasticity_translation_of_coordinates_and_scaling_units():
    m = rectangle_mesh(1, 1, 3, 3)
    bc = {(int(i), c): 0 for i in m.boundary["left"] for c in (0, 1)}
    r = solve(m, dirichlet=bc, body_force=[0, 1])
    m.nodes = 2*m.nodes+[7, -3]
    s = solve(m, dirichlet=bc, body_force=[0, 1])
    assert_allclose(s.displacement, 4*r.displacement, rtol=1e-10, atol=1e-14)
    assert_allclose(s.stress, 2*r.stress, rtol=1e-10, atol=1e-10)
    assert_allclose(s.reaction, 4*r.reaction, rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("nu", [-.4, 0., .3, .49])
def test_elasticity_minimal_supports_preserve_prescribed_rigid_motion(nu):
    m = rectangle_mesh(1, 1, 4, 4)
    exact = affine(m.nodes, [[0, -.002], [.002, 0]], [.003, -.001],
                   young_modulus=70000, poisson_ratio=nu, plane="strain")
    bc = {(0, 0): .003, (0, 1): -.001, (4, 1): .001}
    r = solve_elasticity(m, young_modulus=70000, poisson_ratio=nu, plane="strain", dirichlet=bc)
    assert_allclose(r.displacement, exact.displacement, rtol=0, atol=1e-12)
    assert_allclose(r.strain, 0, atol=1e-12)


def test_elasticity_reject_nonmanifold_edge():
    m = Mesh([[0,0],[1,0],[0,1],[0,-1],[.5,1]], [[0,1,2],[0,3,1],[0,1,4]], {})
    with pytest.raises(ValueError, match="nonmanifold mesh edge"):
        solve(m, dirichlet={})
