# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M2 validation 2: plane-wave scattering off a cylinder (2D).

An incident plane wave u_inc = exp(ikx) hits a sound-soft cylinder of radius a
(u_total = 0 on the surface; mathematically identical to TM scattering off a
perfect conductor).

Scattered-field formulation with unknown u_s:
    r = a:  Dirichlet  u_s = -u_inc   (so that u_total = u_inc + u_s = 0)
    r = R:  curvature-corrected first-order absorbing condition
            du_s/dr = (ik - 1/(2R)) u_s
            -> enters the system as -(ik - 1/(2R)) B_outer

Analytical solution (partial-wave series):
    u_s = -sum_m eps_m i^m [J_m(ka)/H(1)_m(ka)] H(1)_m(kr) cos(m theta)
    eps_0 = 1, eps_m = 2 (m >= 1)

Because the absorbing boundary is approximate, we check agreement within a few
percent rather than full second-order convergence (the PML in M2.5 removes
this limitation).
"""

import numpy as np
from scipy.special import jv, hankel1

from galerkin import (annulus_mesh, assemble_stiffness, assemble_mass,
                      assemble_boundary_mass, solve_dirichlet)

A_CYL = 1.0        # scatterer radius
R_OUT = 4.0        # absorbing-boundary radius
K_WAVE = np.pi     # wavelength = 2, equal to the scatterer diameter


def u_inc(x, y):
    return np.exp(1j * K_WAVE * x)


def u_scat_exact(x, y, n_terms=40):
    r = np.sqrt(x ** 2 + y ** 2)
    th = np.arctan2(y, x)
    ka, kr = K_WAVE * A_CYL, K_WAVE * r
    u = np.zeros_like(r, dtype=complex)
    for m in range(n_terms):
        eps = 1.0 if m == 0 else 2.0
        u -= (eps * (1j ** m) * jv(m, ka) / hankel1(m, ka)
              * hankel1(m, kr) * np.cos(m * th))
    return u


def solve(n_r=96, n_theta=512):
    mesh = annulus_mesh(A_CYL, R_OUT, n_r, n_theta)
    K = assemble_stiffness(mesh)
    M = assemble_mass(mesh)
    B = assemble_boundary_mass(mesh, mesh.boundary_edges["outer"])
    gamma = 1j * K_WAVE - 1.0 / (2.0 * R_OUT)
    A = (K - K_WAVE ** 2 * M - gamma * B).tocsr()
    f = np.zeros(mesh.num_nodes, dtype=complex)

    inner = mesh.boundary["inner"]
    g = -u_inc(mesh.nodes[inner, 0], mesh.nodes[inner, 1])
    u_s = solve_dirichlet(A, f, {tuple(inner): g})
    return mesh, u_s


def main():
    mesh, u_s = solve()
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]

    # Compare with the series well inside the absorbing boundary (r < 0.6 R)
    r = np.sqrt(x ** 2 + y ** 2)
    sel = r < 0.6 * R_OUT
    ex = u_scat_exact(x[sel], y[sel])
    rel = np.linalg.norm(u_s[sel] - ex) / np.linalg.norm(ex)
    print(f"scattered-field relative L2 error (r < {0.6*R_OUT:.1f}): {rel:.3%}")
    assert rel < 0.05, "more than 5% off the series solution — check implementation"
    print("PASS")

    u_total = u_s + u_inc(x, y)
    np.savez("scattering_solution.npz",
             nodes=mesh.nodes, triangles=mesh.triangles,
             u_s=u_s, u_total=u_total)
    return mesh, u_s, u_total


if __name__ == "__main__":
    main()
