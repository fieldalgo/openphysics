"""The same end-to-end pipeline with the full-vector M3a solver.

    meshine (own mesher)  ->  galerkin M3a mixed edge/nodal solver
                          ->  n_eff  vs  refsol Hadley (2002) rib-waveguide table

Exactly one link differs from rib_waveguide_scalar.py: `scalar_modes` becomes
`vector_modes`. The mesher, the adapter, the material table and the reference are
untouched, which is the point — swapping the physics module should not disturb
anything else in the chain.

What changes in the answer
--------------------------
The scalar model drops the polarisation terms at the air interface and lands
about +2.5e-4 above Hadley's quasi-TE value. The vector solver keeps them and
lands BELOW it, converging from the other side; the gap between the two models is
the polarisation correction the scalar approximation is missing.

How close it actually gets, and why not closer
----------------------------------------------
Measured here, slab 0.3 um, meshine with the same grading as the scalar script:

    h_core   triangles   n_eff        vs Hadley   observed order
    0.200        2469    3.411968     -5.2e-04
    0.100        7756    3.412212     -2.8e-04         0.90
    0.050       27050    3.412410     -8.2e-05         1.77
    0.035       50278    3.412456     -3.6e-05         2.34

The observed order climbs through 2, so the remaining gap is mesh resolution,
not a modelling error. Three things were ruled out by
measurement rather than assumed:

  - the computational window: widening it from 18 to 34 um, deepening the
    substrate from 10 to 16 um, or the cladding from 3 to 6 um, each moves n_eff
    by about 1e-6
  - the geometry: meshine's rib_waveguide reproduces the benchmark exactly,
    total core thickness 1 um with the slab included, slab spanning the full
    width, substrate 3.40, air cover
  - refining only near the rib: holding the far-field element size fixed while
    refining the core makes the order DECAY (1.77, 1.06, 0.70) and stall near
    -4e-5, because the mode extends past the graded region. The far field has to
    be refined along with the core, which is what the size_far = 6 h rule does.

Extrapolating the h = 0.035 error at second order, Hadley's stated +-3e-6 needs
h ~ 0.010 with the far field refined to match. meshine can build that mesh but
not quickly — it re-triangulates every point each refinement round, and already
takes tens of minutes at h = 0.025 — so the target is out of reach here. The
limit is the mesher's speed, not the engine and not the reference.

Run:  pip install -e '.[test]'          # brings in meshine and refsol
      PYTHONPATH=. python3 examples/rib_waveguide_vector.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from galerkin import Mesh, eval_edge_field, solve_modes
from meshine import generate, shapes
from refsol import benchmarks
from rib_waveguide_scalar import material_array, to_galerkin   # unchanged adapters

N_CORE, N_BOX, N_CLAD = 3.44, 3.40, 1.0


# --------------------------------------------------------------------------
# the one link that differs: full vector instead of scalar
# --------------------------------------------------------------------------

def vector_modes(mesh: Mesh, n2: np.ndarray, wavelength: float,
                 dirichlet: np.ndarray, num_modes: int = 4,
                 n_guess: float | None = None):
    """Same signature as scalar_modes; transverse E in H(curl), longitudinal in H1.

    dirichlet is the PEC wall: n x E = 0 constrains both the edge dofs lying in
    it and the longitudinal nodal dofs on it, which solve_modes handles.
    """
    k0 = 2 * np.pi / wavelength
    target = n_guess if n_guess is not None else float(np.sqrt(n2.max()))
    n_eff, space, et, ez = solve_modes(mesh, n2, k0, n_target=target,
                                       num_modes=num_modes, pec_nodes=dirichlet)
    guided = (n_eff > np.sqrt(N_BOX ** 2)) & (n_eff < target)
    order = np.argsort(-n_eff[guided])
    return n_eff[guided][order], (space, et[guided][order], ez[guided][order])


# --------------------------------------------------------------------------

def run(slab_thickness: float, size_core: float, wavelength: float = 1.15):
    d, namer = shapes.rib_waveguide(slab_thickness=slab_thickness,
                                    size_core=size_core, size_far=6 * size_core)
    t0 = time.time()
    tm = generate(d, namer, size_fn=shapes.size_graded(size_core, 6 * size_core,
                                                       3.0, center=(0, 0.5)))
    t_mesh = time.time() - t0
    mesh, regions, names = to_galerkin(tm)
    n2 = material_array(regions, names, {"core": N_CORE ** 2, "box": N_BOX ** 2,
                                         "clad": N_CLAD ** 2})
    outer = np.unique(np.concatenate(
        [mesh.boundary[k] for k in ("left", "right", "top", "bottom")]))
    t0 = time.time()
    neff, fields = vector_modes(mesh, n2, wavelength, outer, num_modes=4,
                                n_guess=N_CORE)
    t_solve = time.time() - t0
    return tm, mesh, neff, fields, t_mesh, t_solve


def main(levels=(0.20, 0.10, 0.05, 0.035)):
    t = 0.3
    ref = benchmarks.rib_neff(t)
    print(f"Hadley 2002 rib waveguide, slab {t} um, lambda 1.15 um: "
          f"reference quasi-TE n_eff = {ref:.6f} (+-3e-6)\n")
    print(f"{'h_core':>7} {'triangles':>9} {'n_eff (vector)':>16} {'vs Hadley':>10} "
          f"{'mesh s':>7} {'solve s':>8}")
    results = []
    for h in levels:
        tm, mesh, neff, fields, t_mesh, t_solve = run(t, h)
        assert len(neff), f"h={h}: no guided mode found"
        results.append((h, neff[0]))
        print(f"{h:7.3f} {tm.num_triangles:9d} {neff[0]:16.6f} "
              f"{neff[0] - ref:+10.2e} {t_mesh:7.2f} {t_solve:8.2f}")

    ne = np.array([v for _, v in results])
    err = np.abs(ne - ref)
    if len(ne) >= 3:
        hs = np.array([h for h, _ in results])
        orders = np.log(err[:-1] / err[1:]) / np.log(hs[:-1] / hs[1:])
        print("\nobserved order against the reference:",
              " ".join(f"{o:.2f}" for o in orders))
        print("  (climbing through 2 — the remaining gap is mesh resolution;"
              " see the module docstring for what was ruled out)")
    print(f"\nfinest vector n_eff {ne[-1]:.6f} is {ne[-1]-ref:+.2e} from Hadley,"
          f" approaching from BELOW")
    print("the scalar model in rib_waveguide_scalar.py approaches from ABOVE"
          " (+2.5e-4);\nthe span between them is the polarisation correction")
    return results


if __name__ == "__main__":
    results = main()

    # ---- figure ----------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = 0.3
    ref = benchmarks.rib_neff(t)
    tm, mesh, neff, (space, et, ez), _, _ = run(t, 0.05)
    E = eval_edge_field(space, et[0])
    E = E / np.abs(E).max()
    centroid = mesh.nodes[mesh.triangles].mean(axis=1)
    mag = np.linalg.norm(E, axis=1)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    ax = axes[0]
    ax.tripcolor(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.triangles,
                 facecolors=mesh.regions.astype(float), cmap="Blues",
                 edgecolors="k", linewidth=0.1, alpha=0.9)
    ax.set_aspect("equal"); ax.set_xlim(-4, 4); ax.set_ylim(-2, 2)
    ax.set_title(f"meshine mesh, {tm.num_triangles} triangles (core h=0.05)")

    ax = axes[1]
    ax.tripcolor(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.triangles,
                 facecolors=mag, cmap="inferno")
    step = max(1, len(centroid) // 400)
    ax.quiver(centroid[::step, 0], centroid[::step, 1],
              E[::step, 0], E[::step, 1], color="white", width=0.004, scale=12)
    ax.plot([-1.5, -1.5, 1.5, 1.5], [t, 1, 1, t], "w-", lw=0.8)
    ax.axhline(0, color="w", lw=0.5); ax.axhline(t, color="w", lw=0.5)
    ax.set_aspect("equal"); ax.set_xlim(-4, 4); ax.set_ylim(-2, 2)
    ax.set_title(f"fundamental |E_t| and direction, vector n_eff = {neff[0]:.6f} "
                 f"(Hadley {ref:.6f})")
    for a in axes:
        a.set_xlabel("x (um)"); a.set_ylabel("y (um)")
    fig.suptitle("End-to-end: meshine -> galerkin M3a vector solver -> refsol reference")
    fig.tight_layout()
    fig.savefig("rib_waveguide_vector.png", dpi=130)
    print("wrote rib_waveguide_vector.png")
