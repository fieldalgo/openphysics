# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M2 and M2.5: frequency-domain waves.

A guided plane wave with an exact absorbing condition, scattering off a cylinder
against the partial-wave series, and the PML that replaces the first-order
absorbing boundary.
"""

import numpy as np
import pytest

from galerkin import (rectangle_mesh, annulus_mesh, assemble_stiffness,
                      assemble_mass, assemble_boundary_mass, solve_dirichlet,
                      l2_error, radial_pml_coeffs)
from conftest import assert_second_order, rate

L, H, K_WAVE = 1.0, 0.5, 4.0 * np.pi
A_CYL, R_OUT, K_SCAT = 1.0, 4.0, np.pi


def test_guided_plane_wave_converges_at_second_order():
    """The absorbing condition is EXACT for u = exp(-ikx), so nothing but the
    discretization error is left and the rate must be a clean 2."""
    exact = lambda x, y: np.exp(-1j * K_WAVE * x)
    errors = []
    for nx in (16, 32, 64):
        mesh = rectangle_mesh(L, H, nx, max(2, nx // 4))
        A = (assemble_stiffness(mesh) - K_WAVE ** 2 * assemble_mass(mesh)
             + 1j * K_WAVE * assemble_boundary_mass(
                 mesh, mesh.boundary_edges["right"])).tocsr()
        u = solve_dirichlet(A, np.zeros(mesh.num_nodes, dtype=complex),
                            {tuple(mesh.boundary["left"]): 1.0 + 0j})
        errors.append(l2_error(mesh, u, exact))
    assert_second_order(errors, name="guided plane wave")


def test_cylinder_scattering_matches_the_partial_wave_series(refsol):
    mesh = annulus_mesh(A_CYL, R_OUT, 64, 342)
    B = assemble_boundary_mass(mesh, mesh.boundary_edges["outer"])
    gamma = 1j * K_SCAT - 1.0 / (2.0 * R_OUT)
    A = (assemble_stiffness(mesh) - K_SCAT ** 2 * assemble_mass(mesh)
         - gamma * B).tocsr()
    inner = mesh.boundary["inner"]
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
    g = -refsol.scattering.incident(x[inner], y[inner], K_SCAT)
    u_s = solve_dirichlet(A, np.zeros(mesh.num_nodes, dtype=complex),
                          {tuple(inner): g})

    r = np.hypot(x, y)
    sel = r < 0.6 * R_OUT
    ex = refsol.scattering.scattered(x[sel], y[sel], K_SCAT, A_CYL, kind="pec_tm")
    rel = np.linalg.norm(u_s[sel] - ex) / np.linalg.norm(ex)
    # The first-order absorbing boundary, not the mesh, sets this floor; M2.5
    # replaces it with a PML and the error drops by two orders of magnitude.
    assert rel < 0.05, f"{rel:.3%} off the series solution"


# ------------------------------- M2.5: the cylindrical PML -------------------

R0, D_PML = 3.0, 1.0
R_END = R0 + D_PML


def _error(mesh, u_s, refsol, r_max=2.4):
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
    sel = np.hypot(x, y) < r_max
    ex = refsol.scattering.scattered(x[sel], y[sel], K_SCAT, A_CYL, kind="pec_tm")
    return np.linalg.norm(u_s[sel] - ex) / np.linalg.norm(ex)


def _solve(n_r, n_theta, pml, refsol):
    r_out = R_END if pml else 4.0
    mesh = annulus_mesh(A_CYL, r_out, n_r, n_theta)
    if pml:
        Lam, beta = radial_pml_coeffs(mesh, K_SCAT, R0, D_PML)
        A = (assemble_stiffness(mesh, Lam)
             - K_SCAT ** 2 * assemble_mass(mesh, beta)).tocsr()
        outer = {tuple(mesh.boundary["outer"]): 0.0 + 0j}
    else:
        gamma = 1j * K_SCAT - 1.0 / (2.0 * r_out)
        A = (assemble_stiffness(mesh) - K_SCAT ** 2 * assemble_mass(mesh)
             - gamma * assemble_boundary_mass(
                 mesh, mesh.boundary_edges["outer"])).tocsr()
        outer = {}
    inner = mesh.boundary["inner"]
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
    g = -refsol.scattering.incident(x[inner], y[inner], K_SCAT)
    u = solve_dirichlet(A, np.zeros(mesh.num_nodes, dtype=complex),
                        {tuple(inner): g, **outer})
    return mesh, u


@pytest.mark.slow
def test_pml_keeps_second_order_where_the_abc_plateaus(refsol):
    """The claim is about SLOPES, not about a ratio at one mesh size.

    A first-order absorbing boundary commits an error that refinement cannot
    remove, so its convergence stalls; a PML's reflection is ~1e-6, so only mesh
    error is left and second order continues. Asserting "the PML beats the ABC by
    N times" instead would only be testing where the ladder happens to stop — the
    gap keeps widening, reaching 38x by n_r = 192 in examples/galerkin/.

    Measured here: ABC 4.62e-2, 1.72e-2, 1.19e-2 (orders 1.42 then 0.54);
                   PML 3.84e-2, 9.86e-3, 2.57e-3 (order 1.94).
    """
    err_abc, err_pml = [], []
    for n_r in (16, 32, 64):
        n_theta = int(5.33 * n_r + 0.5) // 2 * 2
        err_abc.append(_error(*_solve(n_r, n_theta, False, refsol), refsol))
        err_pml.append(_error(*_solve(n_r, n_theta, True, refsol), refsol))

    assert_second_order(err_pml, name="PML scattered field")
    abc_order = rate(err_abc)[-1]
    assert abc_order < 1.0, (
        f"the first-order ABC is supposed to stall, but it converged at order "
        f"{abc_order:.2f} — either the mesh is too coarse to see the plateau or "
        f"the boundary condition changed")
    assert err_pml[-1] < err_abc[-1] / 3, (
        f"PML {err_pml[-1]:.3e} vs ABC {err_abc[-1]:.3e}")


def test_identity_tensor_reproduces_the_isotropic_path():
    """The tensor-coefficient assembly is the PML's only new code path, so it is
    checked against the scalar one it must generalise."""
    mesh = annulus_mesh(1.0, 3.0, 12, 64)
    eye = np.zeros((mesh.num_triangles, 2, 2))
    eye[:, 0, 0] = eye[:, 1, 1] = 1.0
    diff = abs(assemble_stiffness(mesh, eye) - assemble_stiffness(mesh, 1.0)).max()
    assert diff < 1e-14, f"tensor path differs from the scalar one by {diff:.2e}"
