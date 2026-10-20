# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""End-to-end pipeline check: geometry -> mesh -> assembly -> eigenproblem -> reference.

    meshine (own mesher)  ->  galerkin P1 assembly  ->  scalar mode eigenproblem
                          ->  n_eff  vs  refsol Hadley (2002) rib-waveguide table

The scalar (weakly guiding) approximation is deliberately simple: with the
transverse field phi and propagation constant beta,

    -div(grad phi) - k0^2 n^2 phi = -beta^2 phi          phi = 0 on the outer box

so in P1 matrices (K stiffness, M mass, M_n2 mass weighted by n^2):

    (k0^2 M_n2 - K) phi = beta^2 M phi,     n_eff = beta / k0.

It cannot reach Hadley's quasi-TE value to 3e-6 (polarisation terms at the
air interface are missing), but a ~1e-3 agreement with a clean second-order
mesh convergence proves that every link of the chain is wired correctly. The
vector solver (M3a) drops into the same script by replacing `scalar_modes`.

Run from the repository root:
      pip install -e "packages/galerkin[figures]" -e packages/galerkin-refsol -e packages/meshine
      python3 examples/galerkin/rib_waveguide_scalar.py
"""

from __future__ import annotations

import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from galerkin import Mesh, assemble_mass, assemble_stiffness, from_mesher
from meshine import TriMesh, generate, shapes
from refsol import benchmarks


# --------------------------------------------------------------------------
# adapter: any mesher output in the shared flat format -> galerkin Mesh + materials
# --------------------------------------------------------------------------

def to_galerkin(m: TriMesh) -> tuple[Mesh, np.ndarray, list[str]]:
    """galerkin.Mesh plus the per-triangle region ids.

    galerkin has since grown the material field this script anticipated, so the
    body is now `from_mesher`; the three-value return is kept because it is what
    reads clearly in a pipeline: mesh, materials, names. Works unchanged for
    gmshio.FemMesh2D, which exposes the same attributes."""
    mesh = from_mesher(m)
    return mesh, mesh.regions, mesh.region_names


def material_array(regions: np.ndarray, names: list[str], values: dict[str, float]) -> np.ndarray:
    """Per-triangle coefficient from a {region name: value} table."""
    lut = np.array([values[n] for n in names], dtype=float)
    return lut[regions]


# --------------------------------------------------------------------------
# scalar mode solver on P1
# --------------------------------------------------------------------------

def scalar_modes(mesh: Mesh, n2: np.ndarray, wavelength: float, dirichlet: np.ndarray,
                 num_modes: int = 2, n_guess: float | None = None):
    k0 = 2 * np.pi / wavelength
    K = assemble_stiffness(mesh, 1.0)
    M = assemble_mass(mesh, 1.0)
    Mn = assemble_mass(mesh, n2)
    A = (k0 ** 2 * Mn - K).tocsc()

    free = np.setdiff1d(np.arange(mesh.num_nodes), dirichlet)
    A_f = A[free][:, free]
    M_f = M[free][:, free].tocsc()
    sigma = (k0 * (n_guess if n_guess is not None else np.sqrt(n2.max()))) ** 2
    vals, vecs = spla.eigsh(A_f, k=num_modes, M=M_f, sigma=sigma, which="LM",
                            v0=np.ones(len(free)), ncv=max(4 * num_modes, 40), maxiter=10000)
    order = np.argsort(-vals)
    vals, vecs = vals[order], vecs[:, order]
    neff = np.sqrt(np.maximum(vals, 0)) / k0
    fields = np.zeros((mesh.num_nodes, num_modes))
    fields[free] = vecs
    return neff, fields


# --------------------------------------------------------------------------

def run(slab_thickness: float, size_core: float, wavelength: float = 1.15):
    d, namer = shapes.rib_waveguide(slab_thickness=slab_thickness, size_core=size_core, size_far=6 * size_core)
    t0 = time.time()
    tm = generate(d, namer, size_fn=shapes.size_graded(size_core, 6 * size_core, 3.0, center=(0, 0.5)))
    t_mesh = time.time() - t0
    mesh, regions, names = to_galerkin(tm)
    n2 = material_array(regions, names, {"core": 3.44 ** 2, "box": 3.40 ** 2, "clad": 1.0 ** 2})
    outer = np.unique(np.concatenate([mesh.boundary[k] for k in ("left", "right", "top", "bottom")]))
    t0 = time.time()
    neff, fields = scalar_modes(mesh, n2, wavelength, outer, num_modes=2, n_guess=3.44)
    t_solve = time.time() - t0
    return tm, mesh, neff, fields, t_mesh, t_solve


if __name__ == "__main__":
    t = 0.3
    ref = benchmarks.rib_neff(t)
    print(f"Hadley 2002 rib waveguide, slab {t} um, lambda 1.15 um: reference quasi-TE n_eff = {ref:.6f}\n")
    print(f"{'h_core':>7} {'triangles':>9} {'n_eff (scalar P1)':>18} {'vs Hadley':>10} {'mesh s':>7} {'solve s':>8}")
    results = []
    for h in (0.20, 0.10, 0.05, 0.025):
        tm, mesh, neff, fields, tmesh, tsolve = run(t, h)
        results.append((h, neff[0]))
        print(f"{h:7.3f} {tm.num_triangles:9d} {neff[0]:18.6f} {neff[0] - ref:+10.2e} {tmesh:7.2f} {tsolve:8.2f}")

    hs = np.array([r[0] for r in results])
    ne = np.array([r[1] for r in results])
    # P1 eigenvalues converge as h^2: the increments shrink by ~4 per halving
    inc = np.diff(ne)
    rates = np.log2(np.abs(inc[:-1] / inc[1:]))
    print("\nn_eff increments per mesh halving:", " ".join(f"{v:+.2e}" for v in inc))
    print("observed convergence rates (expect ~2):", " ".join(f"{r:.2f}" for r in rates))
    # Richardson extrapolation from the two finest meshes (rate 2)
    extrap = ne[-1] + (ne[-1] - ne[-2]) / 3
    print(f"Richardson-extrapolated scalar n_eff: {extrap:.6f}   (Hadley quasi-TE {ref:.6f}, "
          f"difference {extrap - ref:+.2e} = polarisation correction missing in the scalar model)")

    # ---- figure ----------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tm, mesh, neff, fields, _, _ = run(t, 0.05)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    ax = axes[0]
    ax.tripcolor(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.triangles, facecolors=tm.regions.astype(float),
                 cmap="Blues", edgecolors="k", linewidth=0.1, alpha=0.9)
    ax.set_aspect("equal"); ax.set_xlim(-4, 4); ax.set_ylim(-2, 2)
    ax.set_title(f"meshine mesh, {tm.num_triangles} triangles (core h=0.05)")
    ax = axes[1]
    f = fields[:, 0] / np.abs(fields[:, 0]).max()
    ax.tricontourf(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.triangles, np.abs(f), levels=30, cmap="inferno")
    ax.plot([-1.5, -1.5, 1.5, 1.5], [t, 1, 1, t], "w-", lw=0.8)
    ax.axhline(0, color="w", lw=0.5); ax.axhline(t, color="w", lw=0.5)
    ax.set_aspect("equal"); ax.set_xlim(-4, 4); ax.set_ylim(-2, 2)
    ax.set_title(f"fundamental mode |phi|, scalar n_eff = {neff[0]:.5f} (Hadley {ref:.6f})")
    for a in axes:
        a.set_xlabel("x (um)"); a.set_ylabel("y (um)")
    fig.suptitle("End-to-end: meshine -> galerkin P1 -> eigenproblem -> refsol reference")
    fig.tight_layout()
    fig.savefig("rib_waveguide_scalar.png", dpi=130)
    print("wrote rib_waveguide_scalar.png")
