# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M2 validation 1: plane wave travelling through a guide.

Helmholtz:  laplace(u) + k^2 u = 0,  exact solution u = exp(-i k x)

Weak form (whole equation multiplied by -1):
    int grad u . grad w - k^2 int u w - int_Gamma (du/dn) w = 0
Boundary conditions:
    x = 0 (inlet):  Dirichlet u = 1
    x = L (outlet): first-order absorbing condition du/dn + i k u = 0,
                    which enters as +i k int u w (exact for u = e^{-ikx})
    y = 0, H:       natural Neumann (du/dn = 0, consistent with the solution)

Discrete system: (K - k^2 M + i k B_right) u = 0  plus the Dirichlet data.
The theoretical P1 convergence rate is again second order.
"""

import numpy as np

from galerkin import (rectangle_mesh, assemble_stiffness, assemble_mass,
                      assemble_boundary_mass, solve_dirichlet, l2_error)

L, H = 1.0, 0.5
K_WAVE = 4.0 * np.pi  # wavelength lambda = 0.5 -> two wavelengths per domain


def exact(x, y):
    return np.exp(-1j * K_WAVE * x)


def solve_on(nx):
    ny = max(2, nx // 4)
    mesh = rectangle_mesh(L, H, nx, ny)
    K = assemble_stiffness(mesh)
    M = assemble_mass(mesh)
    B = assemble_boundary_mass(mesh, mesh.boundary_edges["right"])
    A = (K - K_WAVE ** 2 * M + 1j * K_WAVE * B).tocsr()
    f = np.zeros(mesh.num_nodes, dtype=complex)
    u = solve_dirichlet(A, f, {tuple(mesh.boundary["left"]): 1.0 + 0j})
    return mesh, u


def main():
    print(f"{'nx':>5} {'nodes/wavelength':>17} {'L2 error':>12} {'rate':>6}")
    errors, hs = [], []
    prev = None
    for nx in [16, 32, 64, 128, 256]:
        mesh, u = solve_on(nx)
        err = l2_error(mesh, u, exact)
        nodes_per_lam = nx / (L * K_WAVE / (2 * np.pi))
        rate = np.log(prev / err) / np.log(2) if prev else float("nan")
        print(f"{nx:>5} {nodes_per_lam:>17.1f} {err:>12.4e} {rate:>6.2f}")
        errors.append(err); hs.append(L / nx)
        prev = err

    final_rate = np.log(errors[-2] / errors[-1]) / np.log(2)
    assert final_rate > 1.8, f"rate {final_rate:.2f} — check implementation"
    print(f"\nPASS: final convergence rate {final_rate:.2f} (theory: 2.0)")
    np.savez("waveguide_convergence.npz", h=np.array(hs), err=np.array(errors))
    return solve_on(128)


if __name__ == "__main__":
    main()
