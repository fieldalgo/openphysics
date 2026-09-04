"""M1 validation: electrostatics of a coaxial cable cross-section.

Inner conductor (radius a) at V = 1, outer conductor (radius b) at V = 0,
no charge in between (Laplace). Analytical solution:

    V(r) = ln(b/r) / ln(b/a)

The mesh is refined step by step to confirm that the L2 error decays as h^2.
P1 elements converge at second order in theory — anything less indicates an
implementation bug.
"""

import numpy as np

from galerkin import (annulus_mesh, assemble_stiffness, assemble_load,
                      solve_dirichlet, l2_error)

A, B = 1.0, 3.0  # inner, outer radius


def exact(x, y):
    r = np.sqrt(x ** 2 + y ** 2)
    return np.log(B / r) / np.log(B / A)


def solve_on(n_r, n_theta):
    mesh = annulus_mesh(A, B, n_r, n_theta)
    K = assemble_stiffness(mesh, eps=1.0)
    f = assemble_load(mesh, rho=0.0)
    V = solve_dirichlet(K, f, {
        tuple(mesh.boundary["inner"]): 1.0,
        tuple(mesh.boundary["outer"]): 0.0,
    })
    return mesh, V


def main():
    print(f"{'n_r':>5} {'nodes':>8} {'h':>10} {'L2 error':>12} {'rate':>6}")
    errors, hs = [], []
    prev = None
    for n_r in [4, 8, 16, 32, 64]:
        n_theta = 6 * n_r  # keep radial/azimuthal element sizes comparable
        mesh, V = solve_on(n_r, n_theta)
        h = (B - A) / n_r
        err = l2_error(mesh, V, exact)
        rate = np.log(prev / err) / np.log(2) if prev else float("nan")
        print(f"{n_r:>5} {mesh.num_nodes:>8} {h:>10.4f} {err:>12.4e} {rate:>6.2f}")
        errors.append(err)
        hs.append(h)
        prev = err

    final_rate = np.log(errors[-2] / errors[-1]) / np.log(2)
    assert final_rate > 1.8, (
        f"convergence rate {final_rate:.2f} — below second order, check implementation")
    print(f"\nPASS: final convergence rate {final_rate:.2f} (theory: 2.0)")
    np.savez("coax_convergence.npz", h=np.array(hs), err=np.array(errors))


if __name__ == "__main__":
    main()
