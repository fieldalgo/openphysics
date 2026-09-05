"""M2: frequency-domain waves — a guided plane wave and cylinder scattering."""

import numpy as np
import pytest

from galerkin import (rectangle_mesh, annulus_mesh, assemble_stiffness,
                      assemble_mass, assemble_boundary_mass, solve_dirichlet,
                      l2_error)
from conftest import assert_second_order

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
