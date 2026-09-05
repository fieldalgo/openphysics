"""M3a validation: guided modes of a step-index optical fibre (full vector).

The problem
-----------
A circular core of index n_co = 1.5 and radius a inside a cladding of index
n_cl = 1.0, at a wavelength giving V = 3.5. Total internal reflection, not a
metal wall, holds the light in, so every mode is hybrid: E_z and H_z are both
nonzero and the transverse field is not a scalar.

The reference
-------------
Matching E_z, H_z, E_phi, H_phi at r = a (Bessel J_l inside, modified Bessel K_l
outside) gives the exact vector characteristic equation, for azimuthal order l,
with u = a sqrt(k0^2 n_co^2 - beta^2) and w = a sqrt(beta^2 - k0^2 n_cl^2):

    (F + G)(n_co^2 F + n_cl^2 G) = l^2 (1/u^2 + 1/w^2)(n_co^2/u^2 + n_cl^2/w^2)
    F = J_l'(u) / (u J_l(u)),      G = K_l'(w) / (w K_l(w))

Multiplying through by (u J_l(u))^2 clears every pole (K_l > 0 for all w > 0),
leaving a smooth function of u on (0, V) that bisection can be trusted on. For
l = 0 it factorises into the TE0m and TM0m equations.

What this milestone is actually testing
---------------------------------------
At V = 3.5 this fibre guides four distinct modes: HE11 (doubly degenerate),
TE01, TM01, HE21 (doubly degenerate). Scalar theory lumps TE01, TM01 and HE21
into one degenerate LP11 group; only a full-vector solver splits them. So the
run also solves the same fibre with the scalar Helmholtz operator built from the
M1/M2 assembly routines, and shows the single LP11 eigenvalue where the vector
solver resolves three.

That comparison has a dangerous confound: a mesh that is not rotationally
symmetric splits the *degenerate* pairs too, and that artefact could be mistaken
for physics. disk_mesh keeps an exact C_n symmetry, so the HE11 and HE21 pairs
stay degenerate to machine precision while the physical splitting is O(5%) —
signal and artefact end up fifteen digits apart, which is the point.
"""

import numpy as np
import scipy.sparse.linalg as spla
from scipy.optimize import brentq
from scipy.special import jv, jvp, kv, kvp

import scipy.sparse as sp

from galerkin import (disk_mesh, solve_modes, assemble_stiffness, assemble_mass,
                      assemble_edge_grad, assemble_edge_mass, assemble_curlcurl,
                      eval_edge_field, EdgeSpace, rectangle_mesh)

A_CORE, N_CO, N_CL = 1.0, 1.5, 1.0
V_NUM = 3.5
K0 = V_NUM / (A_CORE * np.sqrt(N_CO ** 2 - N_CL ** 2))
R_DOM = 6.0          # PEC truncation radius; the cladding field is ~1e-7 by here


# --------------------------------------------------- Whitney identity gate ---
def check_whitney_identities(nx=9, ny=5, tol=1e-11):
    """Exact algebraic identities the assembly must satisfy, whatever the mesh.

    The gradient of a nodal hat function lies *exactly* in the Whitney edge space:
    its dof on the edge (lo -> hi) is the circulation phi(hi) - phi(lo), so the
    node-to-edge incidence matrix C is a discrete gradient. Then, with any
    per-element coefficient c,

        G(c) = M_t(c) C          S(c) C = 0          K(c) = C^T M_t(c) C

    hold to round-off. They tie the new edge-nodal coupling matrix to the edge
    mass, the curl-curl and the nodal stiffness at once, and any orientation-sign
    or coefficient-placement error breaks them immediately — which is worth more
    than the eigenvalues, because a sign error there still yields a plausible
    spectrum.
    """
    mesh = rectangle_mesh(1.0, 0.6, nx, ny)
    space = EdgeSpace(mesh)
    rng_c = 0.5 + np.arange(mesh.num_triangles) % 7      # a varied coefficient
    lo, hi = space.edges[:, 0], space.edges[:, 1]
    e = np.arange(space.num_edges)
    C = sp.coo_matrix((np.r_[np.ones(len(e)), -np.ones(len(e))],
                       (np.r_[e, e], np.r_[hi, lo])),
                      shape=(space.num_edges, mesh.num_nodes)).tocsr()

    G, Mt = assemble_edge_grad(space, rng_c), assemble_edge_mass(space, rng_c)
    S, K = assemble_curlcurl(space, rng_c), assemble_stiffness(mesh, rng_c)
    d = [("G - M_t C", abs(G - Mt @ C).max(), abs(G).max()),
         ("S C", abs(S @ C).max(), abs(S).max()),
         ("K - C^T M_t C", abs(K - (C.T @ Mt @ C)).max(), abs(K).max())]
    print("Whitney identities (edge/nodal assembly consistency):")
    for name, v, scale in d:
        print(f"  ||{name}||_max = {v:.2e}   (relative to {scale:.2e}: {v/scale:.1e})")
        assert v < tol * scale, f"identity {name} violated: {v/scale:.3e} relative"
    return d


# ---------------------------------------------------------------- analytic ---
def _clad(l, w):
    return kvp(l, w, 1) / (w * kv(l, w))


def _char(u, l, part):
    """Pole-free characteristic function; part = 'TE', 'TM' or 'hybrid'."""
    w = np.sqrt(np.maximum(V_NUM ** 2 - u ** 2, 1e-300))
    G, Jl, dJl = _clad(l, w), jv(l, u), jvp(l, u, 1)
    P = dJl + u * G * Jl                      # (u J_l)(F + G)
    Q = N_CO ** 2 * dJl + N_CL ** 2 * u * G * Jl
    if part == "TE":
        return P
    if part == "TM":
        return Q
    R = (l ** 2 * u ** 2 * (1 / u ** 2 + 1 / w ** 2)
         * (N_CO ** 2 / u ** 2 + N_CL ** 2 / w ** 2) * Jl ** 2)
    return P * Q - R


def _roots(l, part, n_scan=40000):
    u = np.linspace(1e-4, V_NUM * (1 - 1e-12), n_scan)
    f = _char(u, l, part)
    idx = np.where(np.sign(f[:-1]) != np.sign(f[1:]))[0]
    return np.array([brentq(lambda t: _char(t, l, part), u[i], u[i + 1],
                            xtol=1e-14, rtol=8.9e-16) for i in idx])


def exact_modes():
    """{label: n_eff} for every guided mode, plus its degeneracy."""
    out = {}
    for part in ("TE", "TM"):
        for m, u in enumerate(_roots(0, part), start=1):
            out[f"{part}0{m}"] = (float(np.sqrt(N_CO ** 2 - (u / (K0 * A_CORE)) ** 2)), 1)
    # At V = 3.5 the l = 1 and l = 2 equations have exactly one guided root each:
    # HE11 (the fundamental, no cutoff) and HE21. Asserting the count keeps the
    # labelling from silently going wrong if the fibre is ever retuned.
    for l, name in ((1, "HE11"), (2, "HE21")):
        u = _roots(l, "hybrid")
        assert len(u) == 1, f"expected one l={l} root at V={V_NUM}, got {len(u)}"
        out[name] = (float(np.sqrt(N_CO ** 2 - (u[0] / (K0 * A_CORE)) ** 2)), 2)
    return dict(sorted(out.items(), key=lambda kv: -kv[1][0]))


# --------------------------------------------------------------------- FEM ---
def fibre_mesh(n_r, n_theta, r_dom=R_DOM):
    mesh = disk_mesh((A_CORE, 2.5, r_dom), n_r, n_theta)
    return mesh, mesh.by_layer([N_CO ** 2, N_CL ** 2, N_CL ** 2])


def solve_vector(n_r, n_theta, num_modes=10, r_dom=R_DOM):
    mesh, eps = fibre_mesh(n_r, n_theta, r_dom)
    n_eff, space, et, ez = solve_modes(mesh, eps, K0, n_target=N_CO,
                                       num_modes=num_modes)
    keep = (n_eff > N_CL) & (n_eff < N_CO)          # guided window
    return mesh, space, n_eff[keep], et[keep], ez[keep]


def guided(n_eff):
    return np.sort(n_eff[(n_eff > N_CL) & (n_eff < N_CO)])[::-1]


def check_truncation(n_theta=128, tol=1e-7):
    """How much does the PEC wall itself move the answer?

    An open fibre has no wall; putting one at a finite radius perturbs every
    effective index, and that bias does NOT shrink under mesh refinement — so a
    convergence rate measured against the exact infinite-cladding values is only
    honest if the truncation bias sits well below the discretization error.
    Measured directly: keep the mesh size fixed and push the wall further out.
    """
    out = []
    for r in (R_DOM, R_DOM + 2.0):
        nr = (16, 24, int(round(16 * (r - 2.5))))       # same h in the cladding
        ne = solve_vector(nr, n_theta, r_dom=r)[2]
        out.append(guided(ne)[[0, 2, 3, 4]])
    shift = np.abs(out[1] - out[0]).max()
    print(f"PEC wall moved {R_DOM}a -> {R_DOM + 2.0}a: max n_eff shift {shift:.2e}")
    assert shift < tol, f"computational domain too small: truncation bias {shift:.2e}"
    return shift


def solve_scalar(n_r, n_theta, num_modes=6):
    """Same fibre under the scalar approximation, using only the M1/M2 assembly.

        grad^2 psi + (k0^2 n^2 - beta^2) psi = 0   ->   (K - k0^2 M(n^2)) psi = -beta^2 M psi

    Both matrices are symmetric and the plain mass matrix is positive definite,
    so this one goes straight to eigsh.
    """
    mesh, eps = fibre_mesh(n_r, n_theta)
    K = assemble_stiffness(mesh, 1.0)
    M_n = assemble_mass(mesh, eps)
    M = assemble_mass(mesh, 1.0)
    free = np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary["outer"])
    Aop = (K - K0 ** 2 * M_n)[free][:, free].tocsc()
    Bop = M[free][:, free].tocsc()
    vals, _ = spla.eigsh(Aop, k=num_modes, M=Bop, sigma=-(K0 * N_CO) ** 2,
                         which="LM", v0=np.ones(len(free)),
                         ncv=min(len(free), max(4 * num_modes, 40)), maxiter=20000)
    beta2 = -np.sort(vals)
    n_eff = np.sqrt(beta2[beta2 > 0]) / K0
    return np.sort(n_eff)[::-1]


# -------------------------------------------------------------------- main ---
def main():
    check_whitney_identities()
    check_truncation()
    exact = exact_modes()
    print(f"step-index fibre: n_co={N_CO} n_cl={N_CL} a={A_CORE} "
          f"k0={K0:.6f} V={V_NUM}  (PEC wall at r={R_DOM}a)")
    print("\nexact vector modes:")
    for lbl, (v, deg) in exact.items():
        print(f"  {lbl:>5}  n_eff = {v:.10f}   (degeneracy {deg})")

    ex_sorted = [v for _, (v, deg) in exact.items() for _ in range(deg)]
    ex_sorted = sorted(ex_sorted, reverse=True)

    # --- headline accuracy on the finest mesh ---
    mesh, space, n_eff, et, ez = solve_vector((24, 36, 45), 192)
    print(f"\nFEM (n_theta=192, {mesh.num_triangles} triangles, "
          f"{space.num_edges + mesh.num_nodes} dofs):")
    print(f"{'mode':>6} {'exact':>14} {'FEM':>14} {'rel err':>10}")
    labels = [l for l, (_, d) in exact.items() for _ in range(d)]  # exact is sorted
    assert len(n_eff) == len(ex_sorted), f"found {len(n_eff)} guided modes, expected {len(ex_sorted)}"
    for lbl, ev, fv in zip(labels, ex_sorted, n_eff):
        rel = abs(fv - ev) / ev
        print(f"{lbl:>6} {ev:>14.10f} {fv:>14.10f} {rel:>10.2e}")
        assert rel < 2e-3, f"{lbl} effective index off by {rel:.2e}"

    # --- the confound check: numerical vs physical splitting ---
    he11 = np.sort(n_eff)[::-1][:2]
    he21 = np.sort(n_eff)[:2]
    num_split = max(abs(he11[0] - he11[1]), abs(he21[0] - he21[1]))
    phys_split = exact["TE01"][0] - exact["HE21"][0]
    print(f"\ndegenerate-pair splitting (mesh artefact): {num_split:.3e}")
    print(f"TE01-HE21 splitting (physical)           : {phys_split:.3e}")
    assert num_split < 1e-6 * phys_split, "mesh symmetry broken — artefact pollutes the splitting"

    # --- scalar solver on the same fibre: one LP11 where there should be three ---
    sc = solve_scalar((24, 36, 45), 192)
    sc = sc[(sc > N_CL) & (sc < N_CO)]
    print(f"\nscalar (LP) solver, same mesh: " + "  ".join(f"{v:.7f}" for v in sc[:6]))
    lp11 = sc[1:3]                       # the degenerate pair just below LP01
    assert abs(lp11[0] - lp11[1]) < 1e-9, "scalar LP11 pair is not degenerate"
    print(f"  LP01 = {sc[0]:.7f} (vector HE11 = {exact['HE11'][0]:.7f}, "
          f"scalar error {abs(sc[0]-exact['HE11'][0])/exact['HE11'][0]:.2%})")
    print(f"  LP11 = {lp11.mean():.7f} — a single degenerate value where the vector")
    print(f"         solver resolves TE01 {exact['TE01'][0]:.7f} / "
          f"TM01 {exact['TM01'][0]:.7f} / HE21 {exact['HE21'][0]:.7f}")

    # --- convergence of the fundamental ---
    print(f"\n{'n_theta':>8} {'h':>9} {'HE11 n_eff':>14} {'rel err':>11} {'rate':>6}")
    hs, errs, prev = [], [], None
    for s, nt in ((1, 64), (2, 128), (4, 256)):
        nr = tuple(s * v for v in (8, 12, 15))
        _, _, ne, _, _ = solve_vector(nr, nt, num_modes=10)
        v = np.sort(ne)[::-1][0]
        err = abs(v - exact["HE11"][0]) / exact["HE11"][0]
        rate = np.log(prev / err) / np.log(2) if prev else float("nan")
        h = A_CORE / nr[0]
        print(f"{nt:>8} {h:>9.4f} {v:>14.10f} {err:>11.3e} {rate:>6.2f}")
        hs.append(h); errs.append(err); prev = err
    rate = np.log(errs[-2] / errs[-1]) / np.log(2)
    assert rate > 1.8, f"effective-index convergence below second order ({rate:.2f})"
    print(f"\nPASS: step-index fibre effective indices within 2e-3, "
          f"HE11 convergence rate {rate:.2f} (theory: 2.0)")

    np.savez("fiber_modes.npz",
             labels=np.array(labels), exact=np.array(ex_sorted), fem=n_eff,
             scalar=sc[:6], h=np.array(hs), err=np.array(errs),
             k0=K0, a=A_CORE, n_co=N_CO, n_cl=N_CL, r_dom=R_DOM)


if __name__ == "__main__":
    main()
