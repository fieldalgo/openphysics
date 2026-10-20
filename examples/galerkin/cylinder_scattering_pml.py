# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M2.5: cylinder scattering revisited with a PML, compared against the ABC.

Geometry: scatterer r=a -> physical region a..R0 -> PML R0..R_end (thickness d)
-> outer Dirichlet 0. The scattered wave decays exponentially inside the PML,
so the outermost boundary condition no longer matters.

Expected outcome:
  - ABC: error plateaus at the boundary-approximation level (~1%) no matter
    how fine the mesh gets
  - PML: reflection ~1e-6, so only mesh error remains and second-order
    convergence continues
"""

import numpy as np

from galerkin import (annulus_mesh, assemble_stiffness, assemble_mass,
                      solve_dirichlet, radial_pml_coeffs)
from cylinder_scattering import (u_inc, u_scat_exact, solve as solve_abc,
                                 A_CYL, K_WAVE)

R0 = 3.0      # PML start (end of the physical region)
D_PML = 1.0   # PML thickness
R_END = R0 + D_PML


def solve_pml(n_r, n_theta):
    mesh = annulus_mesh(A_CYL, R_END, n_r, n_theta)
    Lam, beta = radial_pml_coeffs(mesh, K_WAVE, R0, D_PML)
    K = assemble_stiffness(mesh, Lam)
    M = assemble_mass(mesh, beta)
    A = (K - K_WAVE ** 2 * M).tocsr()
    f = np.zeros(mesh.num_nodes, dtype=complex)

    inner = mesh.boundary["inner"]
    g = -u_inc(mesh.nodes[inner, 0], mesh.nodes[inner, 1])
    u_s = solve_dirichlet(A, f, {
        tuple(inner): g,
        tuple(mesh.boundary["outer"]): 0.0 + 0j,  # PML end — wave already dead
    })
    return mesh, u_s


def rel_error(mesh, u_s, r_max=2.4):
    x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
    r = np.sqrt(x ** 2 + y ** 2)
    sel = r < r_max
    ex = u_scat_exact(x[sel], y[sel])
    return np.linalg.norm(u_s[sel] - ex) / np.linalg.norm(ex)


def main():
    print(f"{'n_r':>5} {'h':>9} {'ABC error':>11} {'PML error':>11}")
    hs, err_abc, err_pml = [], [], []
    for n_r in [24, 48, 96, 192]:
        n_theta = int(5.33 * n_r + 0.5) // 2 * 2
        h = (R_END - A_CYL) / n_r

        m1, u1 = solve_abc(n_r, n_theta)          # ABC: r <= 4 all physical
        e1 = rel_error(m1, u1)
        m2, u2 = solve_pml(n_r, n_theta)
        e2 = rel_error(m2, u2)

        print(f"{n_r:>5} {h:>9.4f} {e1:>10.3%} {e2:>10.3%}")
        hs.append(h); err_abc.append(e1); err_pml.append(e2)

    rate = np.log(err_pml[-2] / err_pml[-1]) / np.log(2)
    print(f"\nPML final convergence rate: {rate:.2f} (theory: 2.0)")
    assert err_pml[-1] < err_abc[-1] / 10, "PML did not beat the ABC by enough"
    assert rate > 1.8, "PML convergence stalled — reflection or implementation bug"
    print("PASS: ABC plateaus at its boundary error; PML keeps second order")

    np.savez("pml_comparison.npz", h=np.array(hs),
             err_abc=np.array(err_abc), err_pml=np.array(err_pml))


if __name__ == "__main__":
    main()
