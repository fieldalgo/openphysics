# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin.core.forms and core.kernels, and the public assembly functions built on them.

On NumPy the public functions (galerkin.assembly, assembly3d, edge, edge3d)
give, bit for bit, the CSR matrix of their kernel assembled through forms: this
checks their DOF tables, shapes and dtypes. Whether the kernels integrate the
right thing is checked against exact integrals in
test_crosscheck_symfem_elements.py and test_crosscheck_symfem_coefficients.py.
The public functions refuse JAX and PyTorch values instead of converting them.
On JAX and PyTorch the kernels agree with NumPy to 1e-12 relative and carry
derivatives with respect to their coefficients; those cases skip when the
library is absent (the CI job that installs both checks that they import).
"""
import numpy as np
import pytest

from galerkin import (EdgeSpace, EdgeSpace3D, annulus_mesh, assemble_boundary_mass, assemble_curlcurl,
                      assemble_curlcurl_3d, assemble_edge_grad, assemble_edge_grad_3d, assemble_edge_mass,
                      assemble_edge_mass_3d, assemble_load, assemble_mass, assemble_mass_3d,
                      assemble_stiffness, assemble_stiffness_3d, box_mesh, rectangle_mesh)
from galerkin.core import forms, kernels
from galerkin.core.backend import namespace
from galerkin.core.triangles import triangle_geometry, vector_strain
from galerkin.elasticity import constitutive_matrix, stiffness_and_stress

RNG = np.random.default_rng(11)


def _meshes2d():
    return {"rectangle": rectangle_mesh(2.0, 1.0, 7, 5), "annulus": annulus_mesh(0.4, 1.3, 5, 17)}


MESH2D = _meshes2d()
MESH3D = box_mesh(1.0, 0.7, 0.5, 3, 3, 2)


def _same_csr(ours, theirs):
    ours = ours.to_scipy() if hasattr(ours, "to_scipy") else ours
    assert ours.shape == theirs.shape
    assert np.array_equal(ours.indptr, theirs.indptr) and np.array_equal(ours.indices, theirs.indices)
    assert ours.data.dtype == theirs.data.dtype
    assert np.array_equal(ours.data, theirs.data), np.max(np.abs(ours.data - theirs.data))


def _n2(mesh):
    return (mesh.num_nodes, mesh.num_nodes)


@pytest.mark.parametrize("name", MESH2D)
@pytest.mark.parametrize("coeff", ["scalar", "cells", "tensor", "complex tensor"])
def test_p1_stiffness_is_assemble_stiffness(name, coeff):
    mesh = MESH2D[name]
    T = mesh.num_triangles
    value = {"scalar": 2.5, "cells": RNG.uniform(1, 3, T),
             "tensor": RNG.uniform(1, 2, (T, 2, 2)),
             "complex tensor": RNG.uniform(1, 2, (T, 2, 2)) + 1j * RNG.uniform(-1, 0, (T, 2, 2))}[coeff]
    ours = forms.matrix(mesh.triangles, mesh.triangles, kernels.p1_stiffness(mesh, value), _n2(mesh))
    _same_csr(ours, assemble_stiffness(mesh, value))


@pytest.mark.parametrize("name", MESH2D)
@pytest.mark.parametrize("coeff", ["scalar", "cells", "complex cells"])
def test_p1_mass_is_assemble_mass(name, coeff):
    mesh = MESH2D[name]
    T = mesh.num_triangles
    value = {"scalar": 1.7, "cells": RNG.uniform(1, 3, T),
             "complex cells": RNG.uniform(1, 3, T) - 0.2j * RNG.uniform(0, 1, T)}[coeff]
    ours = forms.matrix(mesh.triangles, mesh.triangles, kernels.p1_mass(mesh, value), _n2(mesh))
    _same_csr(ours, assemble_mass(mesh, value))


def test_p1_boundary_mass_is_assemble_boundary_mass():
    mesh = MESH2D["rectangle"]
    edges = np.concatenate([np.asarray(e) for e in mesh.boundary_edges.values()])
    for value in (0.3, RNG.uniform(1, 2, len(edges)) + 0.5j):
        ours = forms.matrix(edges, edges, kernels.p1_boundary_mass(mesh, edges, value), _n2(mesh))
        _same_csr(ours, assemble_boundary_mass(mesh, edges, value))


@pytest.mark.parametrize("name", MESH2D)
def test_p1_load_is_assemble_load(name):
    mesh = MESH2D[name]
    cases = (0.0, 3.5, RNG.uniform(-1, 1, mesh.num_triangles), lambda x, y: np.sin(x) + y * y)
    for rho in cases:
        ours = forms.vector(mesh.triangles, kernels.p1_load(mesh, rho), mesh.num_nodes, order="columns")
        assert np.array_equal(ours, assemble_load(mesh, rho))


@pytest.mark.parametrize("name", MESH2D)
def test_p1_joule_is_the_centroid_joule_load(name):
    """Current sigma E, heating sigma E . E and its p1_load centroid load, bit for bit."""
    mesh = MESH2D[name]
    sigma = RNG.uniform(.5, 2., mesh.num_triangles)
    field = RNG.normal(size=(mesh.num_triangles, 2))
    current, heat, load = kernels.p1_joule(mesh, sigma, field)
    assert np.array_equal(current, sigma[:, None] * field)
    assert np.array_equal(heat, np.einsum("ij,ij->i", sigma[:, None] * field, field))
    assert np.array_equal(load, kernels.p1_load(mesh, heat))


@pytest.mark.parametrize("name", MESH2D)
def test_complex_step_through_p1_kernels_matches_central_differences(name):
    """p1_joule and p1_stiffness are analytic in their coefficient and field: a complex step gives
    the derivative a central difference measures (the Newton step of temperature_joule_heating)."""
    mesh = MESH2D[name]
    sigma = RNG.uniform(.5, 2., mesh.num_triangles)
    field = RNG.normal(size=(mesh.num_triangles, 2))
    local = RNG.normal(size=(mesh.num_triangles, 3))
    dsigma, dfield, dlocal = (RNG.normal(size=a.shape) for a in (sigma, field, local))

    def outputs(s, f, v):
        _, heat, load = kernels.p1_joule(mesh, s, f)
        return np.concatenate([heat, load.ravel(), np.einsum("tij,tj->ti", kernels.p1_stiffness(mesh, s), v).ravel()])

    h = 1e-30
    complex_step = outputs(sigma + 1j * h * dsigma, field + 1j * h * dfield, local + 1j * h * dlocal).imag / h
    d = 1e-6
    central = (outputs(sigma + d * dsigma, field + d * dfield, local + d * dlocal)
               - outputs(sigma - d * dsigma, field - d * dfield, local - d * dlocal)) / (2 * d)
    np.testing.assert_allclose(complex_step, central, rtol=0, atol=1e-8 * np.max(np.abs(central)))


@pytest.mark.parametrize("coeff", ["scalar", "cells", "tensor"])
def test_tet_kernels_are_assembly3d(coeff):
    mesh, T = MESH3D, MESH3D.num_tets
    value = {"scalar": 1.3, "cells": RNG.uniform(1, 2, T), "tensor": RNG.uniform(1, 2, (T, 3, 3))}[coeff]
    shape = _n2(mesh)
    _same_csr(forms.matrix(mesh.tets, mesh.tets, kernels.tet_stiffness(mesh, value), shape),
              assemble_stiffness_3d(mesh, value))
    if coeff != "tensor":
        _same_csr(forms.matrix(mesh.tets, mesh.tets, kernels.tet_mass(mesh, value), shape),
                  assemble_mass_3d(mesh, value))


@pytest.mark.parametrize("name", MESH2D)
@pytest.mark.parametrize("coeff", ["scalar", "cells", "tensor", "complex tensor"])
def test_nedelec_kernels_are_edge(name, coeff):
    mesh = MESH2D[name]
    space, T = EdgeSpace(mesh), mesh.num_triangles
    value = {"scalar": 0.8, "cells": RNG.uniform(1, 3, T), "tensor": RNG.uniform(1, 2, (T, 2, 2)),
             "complex tensor": RNG.uniform(1, 2, (T, 2, 2)) - 0.3j}[coeff]
    E = (space.num_edges, space.num_edges)
    _same_csr(forms.matrix(space.tri_edges, space.tri_edges, kernels.nedelec_mass(space, value), E),
              assemble_edge_mass(space, value))
    _same_csr(forms.matrix(space.tri_edges, mesh.triangles, kernels.nedelec_grad(space, value),
                           (space.num_edges, mesh.num_nodes)),
              assemble_edge_grad(space, value))
    if "tensor" not in coeff:
        _same_csr(forms.matrix(space.tri_edges, space.tri_edges, kernels.nedelec_curlcurl(space, value), E),
                  assemble_curlcurl(space, value))


@pytest.mark.parametrize("coeff", ["scalar", "cells"])
def test_nedelec3d_kernels_are_edge3d(coeff):
    mesh = MESH3D
    space = EdgeSpace3D(mesh)
    value = 1.4 if coeff == "scalar" else RNG.uniform(1, 2, mesh.num_tets)
    E = (space.num_edges, space.num_edges)
    _same_csr(forms.matrix(space.tet_edges, space.tet_edges, kernels.nedelec3d_curlcurl(space, value), E),
              assemble_curlcurl_3d(space, value))
    _same_csr(forms.matrix(space.tet_edges, space.tet_edges, kernels.nedelec3d_mass(space, value), E),
              assemble_edge_mass_3d(space, value))
    _same_csr(forms.matrix(space.tet_edges, mesh.tets, kernels.nedelec3d_grad(space, value),
                           (space.num_edges, mesh.num_nodes)),
              assemble_edge_grad_3d(space, value))


@pytest.mark.parametrize("value", [1.0 + 1j, "cells"])
def test_real_coefficient_functions_refuse_complex_ones(value):
    """A complex array used to lose its imaginary part with only a ComplexWarning; now every form raises."""
    space = EdgeSpace3D(MESH3D)
    mesh = MESH2D["rectangle"]
    if value == "cells":
        value = np.full(MESH3D.num_tets, 1.0 + 1j)
    for build in (assemble_curlcurl_3d, assemble_edge_mass_3d, assemble_edge_grad_3d,
                  kernels.nedelec3d_curlcurl):
        with pytest.raises(TypeError, match="real coefficient"):
            build(space, value)
    rho = 1.0 + 1j if np.ndim(value) == 0 else np.full(mesh.num_triangles, 1.0 + 1j)
    with pytest.raises(TypeError, match="real coefficient"):
        assemble_load(mesh, rho)


@pytest.mark.parametrize("library", ["jax", "torch"])
def test_public_assembly_refuses_live_values(library):
    """The NumPy functions would cut the derivative of a JAX or PyTorch value; they refuse it."""
    mesh, space, space3d = MESH2D["rectangle"], EdgeSpace(MESH2D["rectangle"]), EdgeSpace3D(MESH3D)
    c2, c3 = _live(library, np.ones(mesh.num_triangles)), _live(library, np.ones(MESH3D.num_tets))
    calls = [lambda: assemble_stiffness(mesh, c2), lambda: assemble_mass(mesh, c2),
             lambda: assemble_load(mesh, c2), lambda: assemble_curlcurl(space, c2),
             lambda: assemble_edge_mass(space, c2), lambda: assemble_edge_grad(space, c2),
             lambda: assemble_boundary_mass(mesh, np.array([[0, 1], [1, 2], [2, 3]]), c2[:3]),
             lambda: assemble_load(mesh, lambda x, y: c2),
             lambda: assemble_stiffness_3d(MESH3D, c3), lambda: assemble_mass_3d(MESH3D, c3),
             lambda: assemble_curlcurl_3d(space3d, c3), lambda: assemble_edge_mass_3d(space3d, c3),
             lambda: assemble_edge_grad_3d(space3d, c3)]
    for call in calls:
        with pytest.raises(TypeError, match="cut the derivative"):
            call()


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_vector_p1_stiffness_is_elasticity(plane):
    mesh = MESH2D["annulus"]
    p, t, area, *_ = triangle_geometry(mesh, counterclockwise=False)
    bmat, dofs = vector_strain(p, t)
    d = constitutive_matrix(2.0e9, 0.3, plane=plane)
    expected, _ = stiffness_and_stress(bmat, d, area)
    assert np.array_equal(kernels.vector_p1_stiffness(bmat, d, area), expected)
    per_cell = np.broadcast_to(d, (len(t), 3, 3)) * RNG.uniform(0.5, 2, len(t))[:, None, None]
    expected, _ = stiffness_and_stress(bmat, per_cell, area)
    assert np.array_equal(kernels.vector_p1_stiffness(bmat, per_cell, area), expected)
    K = forms.matrix(dofs, dofs, expected, (2 * len(p),) * 2)
    assert K.to_scipy().shape == (2 * len(p),) * 2


def test_generic_quadrature_matches_closed_forms():
    mesh = MESH2D["annulus"]
    T = mesh.num_triangles
    # Edge-midpoint rule, exact for degree 2: P1 mass.
    lam = 0.5 * (np.ones((3, 3)) - np.eye(3))                    # (Q, 3)
    weights = np.full(3, 1 / 3)
    values = np.broadcast_to(lam, (T, 3, 3))                      # (T, Q, i)
    c = RNG.uniform(1, 2, T)
    mass = forms.integrate_bilinear(values, values, weights, mesh.areas(), c)
    np.testing.assert_allclose(mass, kernels.p1_mass(mesh, c), rtol=1e-14, atol=0)
    # Constant gradients: P1 stiffness from the quadrature path.
    g, area = kernels.triangle_gradients(mesh)
    grads = np.broadcast_to(g[:, None], (T, 3, 3, 2))             # (T, Q, i, 2)
    stiff = forms.integrate_bilinear(grads, grads, weights, area, c)
    np.testing.assert_allclose(stiff, kernels.p1_stiffness(mesh, c), rtol=1e-13, atol=1e-13 * np.abs(stiff).max())
    # Linear form: constant source with the same rule equals the centroid load.
    load = forms.integrate_linear(values, weights, mesh.areas(), np.full(T, 2.0))
    np.testing.assert_allclose(load, kernels.p1_load(mesh, 2.0), rtol=1e-14)


def test_forms_validate_shapes():
    mesh = MESH2D["rectangle"]
    with pytest.raises(ValueError, match="expected"):
        forms.matrix(mesh.triangles, mesh.triangles, np.ones((mesh.num_triangles, 3, 2)), _n2(mesh))
    with pytest.raises(ValueError, match="2-D integer"):
        forms.matrix(mesh.triangles.ravel(), mesh.triangles, np.ones((1, 3, 3)), _n2(mesh))
    with pytest.raises(ValueError, match="order"):
        forms.vector(mesh.triangles, np.ones((mesh.num_triangles, 3)), mesh.num_nodes, order="rows")


# -- other array libraries -----------------------------------------------------

def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _live(name, array):
    if name == "jax":
        return _jax().numpy.asarray(array)
    return _torch().as_tensor(np.asarray(array))


def _numpy(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


CASES = {
    "p1_stiffness": (lambda c: kernels.p1_stiffness(MESH2D["annulus"], c), MESH2D["annulus"].num_triangles),
    "p1_mass": (lambda c: kernels.p1_mass(MESH2D["annulus"], c), MESH2D["annulus"].num_triangles),
    "p1_load": (lambda c: kernels.p1_load(MESH2D["annulus"], c), MESH2D["annulus"].num_triangles),
    "tet_stiffness": (lambda c: kernels.tet_stiffness(MESH3D, c), MESH3D.num_tets),
    "nedelec_mass": (lambda c: kernels.nedelec_mass(EdgeSpace(MESH2D["annulus"]), c), MESH2D["annulus"].num_triangles),
    "nedelec_curlcurl": (lambda c: kernels.nedelec_curlcurl(EdgeSpace(MESH2D["annulus"]), c), MESH2D["annulus"].num_triangles),
    "nedelec3d_mass": (lambda c: kernels.nedelec3d_mass(EdgeSpace3D(MESH3D), c), MESH3D.num_tets),
}


@pytest.mark.parametrize("library", ["jax", "torch"])
@pytest.mark.parametrize("case", CASES)
def test_kernels_agree_across_libraries(library, case):
    kernel, cells = CASES[case]
    c = RNG.uniform(1, 2, cells)
    expected = kernel(c)
    live = kernel(_live(library, c))
    assert namespace(live) is not namespace(expected)
    np.testing.assert_allclose(_numpy(live), expected, rtol=1e-12, atol=1e-12 * np.abs(expected).max())


@pytest.mark.parametrize("library", ["jax", "torch"])
def test_assembled_matrix_and_vector_agree_across_libraries(library):
    mesh = MESH2D["annulus"]
    c = RNG.uniform(1, 2, mesh.num_triangles)
    K = forms.matrix(mesh.triangles, mesh.triangles, kernels.p1_stiffness(mesh, c), _n2(mesh)).to_dense()
    K_live = forms.matrix(mesh.triangles, mesh.triangles, kernels.p1_stiffness(mesh, _live(library, c)),
                          _n2(mesh)).to_dense()
    np.testing.assert_allclose(_numpy(K_live), K, rtol=1e-12, atol=1e-12 * np.abs(K).max())
    f = forms.vector(mesh.triangles, kernels.p1_load(mesh, c), mesh.num_nodes, order="columns")
    f_live = forms.vector(mesh.triangles, kernels.p1_load(mesh, _live(library, c)), mesh.num_nodes, order="columns")
    np.testing.assert_allclose(_numpy(f_live), f, rtol=1e-12, atol=1e-14)


def _energy_gradient_reference(mesh, u):
    """d(u^T K(c) u)/dc_t = u_t^T K1_t u_t: the unit-coefficient element energy."""
    K1 = kernels.p1_stiffness(mesh, np.ones(mesh.num_triangles))
    ut = u[mesh.triangles]
    return np.einsum("ti,tij,tj->t", ut, K1, ut)


def test_stiffness_derivative_on_jax():
    jax = _jax()
    mesh = MESH2D["annulus"]
    u = np.sin(mesh.nodes[:, 0]) * np.cos(2 * mesh.nodes[:, 1])

    def energy(c):
        K = forms.matrix(mesh.triangles, mesh.triangles, kernels.p1_stiffness(mesh, c), _n2(mesh)).to_dense()
        return u @ K @ u
    c = jax.numpy.asarray(RNG.uniform(1, 2, mesh.num_triangles))
    expected = _energy_gradient_reference(mesh, u)
    np.testing.assert_allclose(jax.grad(energy)(c), expected, rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(jax.jit(jax.grad(energy))(c), expected, rtol=1e-12, atol=1e-14)


def test_stiffness_derivative_on_torch():
    torch = _torch()
    mesh = MESH2D["annulus"]
    u_np = np.sin(mesh.nodes[:, 0]) * np.cos(2 * mesh.nodes[:, 1])
    u = torch.as_tensor(u_np)
    c = torch.as_tensor(RNG.uniform(1, 2, mesh.num_triangles)).requires_grad_(True)
    K = forms.matrix(mesh.triangles, mesh.triangles, kernels.p1_stiffness(mesh, c), _n2(mesh)).to_dense()
    (u @ K @ u).backward()
    np.testing.assert_allclose(c.grad.numpy(), _energy_gradient_reference(mesh, u_np), rtol=1e-12, atol=1e-14)
