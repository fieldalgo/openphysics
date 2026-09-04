"""M3-prep: cutoff frequencies of a rectangular waveguide (2D Maxwell eigenproblem).

Problem:  curl curl E = k_c^2 E   in Omega = [0,a] x [0,b],   n x E = 0 (PEC)

Analytical cutoff wavenumbers (TE_mn):
    k_c^2 = (m pi/a)^2 + (n pi/b)^2,   m, n >= 0, (m, n) != (0, 0)

Solved two ways:
  1. Nedelec edge elements — the correct method. The kernel of the curl
     (gradient fields) lands exactly at eigenvalue zero and the nonzero
     spectrum contains only physical modes.
  2. Vector P1 nodal elements — deliberately wrong. The kernel is not
     represented correctly, so spurious eigenvalues pollute the spectrum
     between the physical ones: living proof of why edge elements exist.
"""

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from galerkin import (rectangle_mesh, EdgeSpace, assemble_curlcurl,
                      assemble_edge_mass, assemble_stiffness, assemble_mass)

A_WG, B_WG = 1.0, 0.5


def exact_cutoffs(n_max=4):
    """Sorted list of (k_c^2, label)."""
    out = []
    for m in range(n_max + 1):
        for n in range(n_max + 1):
            if m == 0 and n == 0:
                continue
            out.append(((m * np.pi / A_WG) ** 2 + (n * np.pi / B_WG) ** 2,
                        f"TE{m}{n}"))
    return sorted(out)


def all_boundary_nodes(mesh):
    return np.unique(np.concatenate([mesh.boundary[k] for k in mesh.boundary]))


def solve_nedelec(nx, ny, k=10, sigma=60.0):
    """Nedelec: S e = k_c^2 M e, PEC = eliminate boundary-edge dofs."""
    mesh = rectangle_mesh(A_WG, B_WG, nx, ny)
    space = EdgeSpace(mesh)
    S = assemble_curlcurl(space)
    M = assemble_edge_mass(space)

    fixed = space.boundary_edge_ids(all_boundary_nodes(mesh))
    free = np.setdiff1d(np.arange(space.num_edges), fixed)
    S, M = S[free][:, free], M[free][:, free]

    # Shift-invert around sigma: sees both the kernel (0) and physical modes.
    # Fixed start vector + generous ncv keep ARPACK deterministic and robust.
    n = S.shape[0]
    vals, vecs = spla.eigsh(S, k=k, M=M, sigma=sigma, which="LM",
                            v0=np.ones(n), ncv=min(n, max(4 * k, 40)),
                            maxiter=10000)
    return mesh, space, free, vals, vecs


def solve_nodal(nx, ny, k=10, sigma=60.0):
    """Vector P1 nodal elements (deliberately wrong): same eigenproblem.

    With curl u = dx u_y - dy u_x the weak-form blocks are
        [ Dyy  -Dyx ] [ux]          [M  0] [ux]
        [-Dxy   Dxx ] [uy] = k_c^2  [0  M] [uy]
    PEC (zero tangential component): ux = 0 on top/bottom, uy = 0 on left/right.
    """
    mesh = rectangle_mesh(A_WG, B_WG, nx, ny)
    p = mesh.nodes[mesh.triangles]
    x, y = p[:, :, 0], p[:, :, 1]
    b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], axis=1)
    c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], axis=1)
    area = np.abs(0.5 * (b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]))
    gx, gy = b / (2 * area[:, None]), c / (2 * area[:, None])

    def gradmat(ga, gb):
        Ke = area[:, None, None] * ga[:, :, None] * gb[:, None, :]
        tris = mesh.triangles
        rows = np.repeat(tris, 3, axis=1).ravel()
        cols = np.tile(tris, (1, 3)).ravel()
        return sp.coo_matrix((Ke.ravel(), (rows, cols)),
                             shape=(mesh.num_nodes, mesh.num_nodes)).tocsr()

    Dxx, Dyy = gradmat(gx, gx), gradmat(gy, gy)
    Dxy, Dyx = gradmat(gx, gy), gradmat(gy, gx)
    Mn = assemble_mass(mesh)

    S = sp.bmat([[Dyy, -Dyx], [-Dxy, Dxx]]).tocsr()
    M2 = sp.block_diag([Mn, Mn]).tocsr()

    n = mesh.num_nodes
    fixed_x = np.concatenate([mesh.boundary["top"], mesh.boundary["bottom"]])
    fixed_y = np.concatenate([mesh.boundary["left"], mesh.boundary["right"]])
    fixed = np.unique(np.concatenate([fixed_x, n + fixed_y]))
    free = np.setdiff1d(np.arange(2 * n), fixed)
    S, M2 = S[free][:, free], M2[free][:, free]

    n2 = S.shape[0]
    vals, _ = spla.eigsh(S, k=k, M=M2, sigma=sigma, which="LM",
                         v0=np.ones(n2), ncv=min(n2, max(4 * k, 40)),
                         maxiter=10000)
    return np.sort(vals)


def main():
    exact = exact_cutoffs()
    print("analytical (first 6):",
          "  ".join(f"{lbl}={v:.3f}" for v, lbl in exact[:6]))

    # --- Nedelec: validation ---
    mesh, space, free, vals, _ = solve_nedelec(60, 30, k=14, sigma=60.0)
    ned = np.sort(vals[vals > 1.0])   # drop the kernel (~0)
    print("\nNedelec (60x30):")
    print(f"{'mode':>6} {'exact':>10} {'FEM':>10} {'rel err':>10}")
    for i, (ev, lbl) in enumerate(exact[:6]):
        rel = abs(ned[i] - ev) / ev
        print(f"{lbl:>6} {ev:>10.4f} {ned[i]:>10.4f} {rel:>10.2e}")
        assert rel < 5e-3, f"{lbl} error too large"

    n_zero = np.sum(np.abs(vals) < 1.0)
    print(f"  (kernel eigenvalues caught near sigma: {n_zero} — all should be ~0)")

    # --- Nodal elements: spurious-mode demonstration ---
    nod = solve_nodal(60, 30, k=14, sigma=60.0)
    nod = nod[nod > 1.0]
    print("\nVector P1 nodal elements (60x30), same eigenvalue window:")
    print("  ", "  ".join(f"{v:.2f}" for v in nod[:10]))
    print("   ^ values absent from the analytical list crowd in between the"
          " physical modes (spurious)")

    # --- TE10 eigenvalue convergence ---
    print(f"\n{'nx':>5} {'h':>9} {'TE10 rel err':>13} {'rate':>6}")
    errs, hs = [], []
    prev = None
    te10 = exact[0][0]
    for nx in [10, 20, 40, 80]:
        _, _, _, v, _ = solve_nedelec(nx, nx // 2, k=6, sigma=12.0)
        lam = np.sort(v[v > 1.0])[0]
        err = abs(lam - te10) / te10
        rate = np.log(prev / err) / np.log(2) if prev else float("nan")
        print(f"{nx:>5} {A_WG/nx:>9.4f} {err:>13.3e} {rate:>6.2f}")
        errs.append(err); hs.append(A_WG / nx)
        prev = err
    rate = np.log(errs[-2] / errs[-1]) / np.log(2)
    assert rate > 1.8, "eigenvalue convergence below second order"
    print(f"\nPASS: TE10 eigenvalue convergence rate {rate:.2f} (theory: 2.0)")

    np.savez("waveguide_modes.npz",
             exact=np.array([v for v, _ in exact[:8]]),
             labels=np.array([l for _, l in exact[:8]]),
             nedelec=ned[:8], nodal=nod[:12],
             h=np.array(hs), err=np.array(errs))


if __name__ == "__main__":
    main()
