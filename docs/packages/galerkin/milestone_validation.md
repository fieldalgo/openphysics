# galerkin milestone validation (2026-09-05)

**English** | [한국어](../../locales/ko/pages/packages/galerkin/milestone_validation.md)

These measurements were recorded on 2026-09-05, while the electrostatic,
Helmholtz, waveguide-mode and 3D cavity solvers (milestones M1 to M3b) were
built. They are historical results, not a fresh test report. The current gates
are the tests in `tests/galerkin/` and the checks in the examples named below; for a
specific commit, see its CI run. This page was moved unchanged from the package
README.

Every milestone is gated on agreement with an analytical solution plus the
theoretical convergence rate. A solver is software that can be plausibly wrong;
the convergence rate is the lie detector.

- **M1 coaxial cable** (V = ln(b/r)/ln(b/a)): L2 convergence rate 1.91 → **2.00**
  (P1 theory: 2), field direction radial to 0.99998, |E| mean error 0.6%
- **M2 guided plane wave** (u = e^{-ikx}, exact first-order ABC): rate 1.90 → **2.00**
- **M2 cylinder scattering** (ka = π): relative L2 error **1.1%** vs partial-wave
  series — residual dominated by the first-order ABC
- **M2.5 ABC vs PML**: ABC plateaus at 1.1% under refinement; PML keeps
  second-order convergence (rate 1.98) down to **0.029%**. Tensor-coefficient
  assembly verified against the isotropic path with an identity tensor (1e-16)
- **M3-prep waveguide cutoffs** (1×0.5 PEC): first six eigenvalues within
  6.9e-4, TE10 rate **2.00**, curl kernel exactly at zero; the same problem
  discretized with nodal vector P1 produces spurious eigenvalues — a numerical
  demonstration of why edge elements exist
- **M3a step-index fiber** (n_co = 1.5, n_cl = 1.0, V = 3.5, PEC wall at 6a):
  all four guided modes within **2.2e-4** of the exact vector dispersion
  relation, HE11 effective-index convergence rate **2.00**. Two independent
  gates on the way there: the mixed formulation reproduces the analytic
  homogeneously-filled PEC guide spectrum β² = k₀²ε_r − k_c² at rate 2.00, and
  the edge-nodal coupling matrix matches a degree-5 quadrature to 1.1e-15

| mode | exact n_eff | FEM | rel err |
|---|---|---|---|
| HE11 | 1.3581708032 | 1.3580873381 | 6.2e-05 |
| TE01 | 1.1853020171 | 1.1850794850 | 1.9e-04 |
| TM01 | 1.1300844597 | 1.1299299650 | 1.4e-04 |
| HE21 | 1.1219119218 | 1.1216662493 | 2.2e-04 |

  The headline physics is the splitting. Scalar (LP) theory makes TE01, TM01 and
  HE21 one degenerate group; run on the same mesh it returns a single doubly
  degenerate LP11 at 1.1848846, and misses HE11 by 1.5%. The vector solver
  resolves all three, spanning 6.3e-2 in n_eff.

  Graded against `refsol.fiber.vector_modes` on its own weakly-guiding fibre
  (a = 4 um, 1.45/1.44, 1.55 um, V = 2.756, where the three LP11 constituents lie
  within 2e-5 of one another): HE11 4.3e-6, TE01 8.8e-6, TM01 5.5e-6, HE21 7.4e-6,
  at orders **1.99 / 1.90 / 2.11 / 1.97**.

- **M3a in the 1D limit** — a planar SOI slab (220 nm, λ = 1.55) against
  `refsol.slab.modes`. Modelled as a narrow strip, where the side walls select
  the polarization: electric walls leave only the TE family, magnetic walls only
  TM. Both converge at order **2.00 / 1.98** to 2.851739 and 2.056288.

  Worth recording which direction limits it: the TE field varies only across the
  slab, yet its error is governed by the mesh *along* the strip — the Whitney
  basis couples the two directions through each triangle's diagonal, so refining
  the obvious direction alone stalls at 3.6e-4.

- **M3a against a published benchmark** — Hadley's dielectric-corner problems
  (`refsol.benchmarks.DIELECTRIC_CORNERS`, quoted to ±1e-8), a unit square with a
  square core in one corner, PEC on two sides and PMC on the other two. At a
  48×48 mesh the four cases land 4.0e-5, 6.3e-5, 9.5e-6 and 7.1e-6 from the
  published values, converging at orders 2.09, 2.01 and 2.44.

  The fourth case does not reach second order: it converges at about **order 1**.
  Its high-index region wraps a re-entrant dielectric corner, and the field
  singularity there is exactly what Hadley's paper exists to treat. That is
  recorded and pinned by its own test rather than averaged into the others.

  That measurement has one dangerous confound: a mesh without rotational
  symmetry splits the *degenerate* HE11 and HE21 pairs too, and the artefact
  would be indistinguishable from physics. `disk_mesh` keeps an exact C_n
  symmetry, and the measured artificial splitting is **1.2e-14** — twelve orders
  of magnitude below the physical splitting it could have been confused with.

  The second confound is the PEC wall itself: an open fibre has none, and the
  bias it introduces does *not* shrink under mesh refinement, so a convergence
  rate measured against exact infinite-cladding values is only honest if that
  bias is far below the discretization error. Measured by holding the mesh size
  fixed and moving the wall from 6a to 8a: **8.6e-9**, four thousand times below
  the 3.5e-5 discretization error at the finest mesh.

  Two further checks are permanent gates in `examples/galerkin/fiber_modes.py`:

  - the assembly satisfies the exact Whitney identities G(c) = M_t(c) C,
    S(c) C = 0 and K(c) = C^T M_t(c) C, where C is the node-to-edge incidence
    (discrete gradient) matrix — relative residuals 1.3e-15, 3.9e-15, 4.2e-16.
    An orientation-sign error still yields a plausible spectrum; it cannot
    survive these.
  - the radial field of TM01 steps by exactly n_co²/n_cl² = **2.2500** across the
    core boundary and the FEM element values land on both exact Bessel branches
    (`fiber_interface.png`). That discontinuity is the physical reason the
    transverse field has to live in H(curl).

- **M3b rectangular PEC cavity** (1.0 × 0.8 × 0.6, Kuhn tetrahedral mesh):
  the first six resonances within **1.8e-3** of exact at h = 0.05, convergence
  rates **1.98 / 2.00 / 1.91** on the non-degenerate modes.

| mode | exact k² | FEM | rel err |
|---|---|---|---|
| TM110 | 25.2908613 | 25.2803032 | 4.2e-04 |
| TE101 | 37.2851722 | 37.2478457 | 1.0e-03 |
| TE011 | 42.8368247 | 42.8040753 | 7.7e-04 |
| TE111/TM111 | 52.7064291 | 52.7548173 | 9.2e-04 |
| TE111/TM111 | 52.7064291 | 52.7998679 | 1.8e-03 |
| TM210 | 54.8996745 | 54.8290346 | 1.3e-03 |

  Three structural gates run before any eigenvalue is believed:

  - **the mesh**: every interior face shared by exactly two tetrahedra, boundary
    face count exact, all volumes positive, Euler V − E + F − T = 1
  - **the Whitney identities in 3D** — G(c) = M_t(c) C, S(c) C = 0,
    K(c) = Cᵀ M_t(c) C — relative residuals 2.1e-16, 1.3e-16, 6.8e-16
  - **discrete de Rham exactness**: the kernel of the discrete curl on the
    PEC-constrained edge space has dimension exactly the number of interior nodes
    (1, 4, 12, 24 on four meshes). That integer identity is the structural reason
    no spurious mode can appear between the physical ones — and it is a much
    sharper statement than "we did not see any"

  One honest difference from M3a. The M3a disk mesh has an exact C_n rotational
  symmetry and held its degenerate pairs together to 1.2e-14. The Kuhn
  subdivision has a preferred diagonal and does **not**: the exactly-degenerate
  TE111/TM111 pair comes out split. That split is a discretization artefact, and
  the run measures it and gates it as one — it vanishes at rate **2.15**. Which
  of those two situations a mesh is in decides whether a measured splitting may
  be read as physics at all.

- **M3b Gmsh input**. Gmsh is GPL, so it is never linked: it is run as a separate
  executable and `gmsh.py` reads the file it writes. ASCII formats 2.2 and 4.1,
  tetrahedra and triangles, physical groups as boundary tags, non-contiguous node
  tags remapped; binary files and higher-order elements are refused rather than
  mis-read. Gated three ways — fixtures transcribed by hand from the format
  documentation, a round trip that preserves every boundary tag, and the cavity
  spectrum recomputed on the read-back mesh, which drifts by **1.4e-14**.

  Now gated on files Gmsh itself wrote, in both formats, cross-checked against
  `gmshio`'s independent parser for identical connectivity — the limitation this
  entry used to record is closed.

- **Meshes built elsewhere.** `galerkin.from_mesher` adapts any object exposing
  `nodes`, `triangles` or `tetrahedra`, `regions`, `region_names` and boundary
  edges or faces, and `Mesh.by_region({"core": ..., "clad": ...})` turns region
  names into a per-element material array. Verified against two meshers, neither
  a dependency of the engine: [meshine](https://github.com/fieldalgo/openphysics/blob/main/packages/meshine/README.md)
  (pure numpy/scipy, planar) and [gmshio](https://github.com/fieldalgo/openphysics/blob/main/packages/gmshio/README.md)
  (runs the Gmsh executable as a separate process).

  All eight of Hadley's **rib waveguides** (`refsol.benchmarks.RIB_WAVEGUIDES`,
  quoted to ±3e-6, slab thickness 0 to 0.7 µm) come out within **1.2e-4** of the
  published quasi-TE indices on a meshine mesh. Re-entrant dielectric corners
  where the rib meets the slab, not the reference, set that floor.

  A per-case tolerance can be met while the family is wrong, so the trend is
  gated separately: the published indices rise monotonically across the eight by
  2.08e-3 in total, and that spread is reproduced to 9.4e-5.

- **The pipeline end to end.** `examples/galerkin/rib_waveguide_scalar.py` and
  `examples/galerkin/rib_waveguide_vector.py` run the whole chain — meshine builds the
  mesh, galerkin assembles and solves, refsol grades — differing only in the
  solver. The scalar model settles about **+2.5e-4 above** Hadley's quasi-TE
  value, missing the polarisation terms at the air interface; the vector solver
  approaches from **below**, reaching −3.6e-5 at h = 0.035 with the observed
  order climbing 0.90 → 1.77 → 2.34.

  Hadley's stated ±3e-6 is **not reached**, and the reason was measured rather
  than assumed. It is not the computational window (widening 18 → 34 µm moves
  n_eff by 1e-6), not the geometry, and not the reference. Extrapolating the
  second-order tail puts it at h ≈ 0.010 with the far field refined to match —
  a mesh meshine can build but not quickly, since it re-triangulates every point
  each refinement round. The mesher's speed is the limit.

  One trap worth recording: refining only near the rib while holding the
  far-field element size fixed makes the observed order *decay* (1.77, 1.06,
  0.70) and stall near −4e-5, because the mode extends past the graded region.
  A stalling order under refinement is the signature of a floor, not of a
  singularity — a singularity holds a constant fractional order.

  On a gmshio mesh of the unit cube the cluster means land within **5.1e-3** and
  nothing spurious appears between the analytic resonances. The strict
  second-order ladder stays on the structured meshes galerkin builds itself:
  Gmsh's `lc` is a target size, so two meshes in a refinement sequence are not
  nested and a fitted order would measure the mesher as much as the solver.
