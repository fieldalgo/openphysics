# galerkin — a 2D electromagnetic FEM engine (FieldAlgo project)

A finite-element solver engine written in pure Python (numpy + scipy.sparse),
built milestone by milestone with an analytical-validation-first culture.
Currently covers 2D electromagnetics; designed to grow into a multiphysics core.

- **M1**: Electrostatics — ∇·(ε∇V) = −ρ (P1 elements)
- **M2**: Frequency-domain waves — ∇²u + k²u = 0 (complex arithmetic, absorbing boundaries)
- **M2.5**: Cylindrical PML (complex coordinate stretching → anisotropic tensor coefficients)
- **M3-prep**: Nédélec edge elements — waveguide eigenmodes ∇×∇×E = k_c²E in H(curl)
- **M3a**: Dielectric waveguide cross-section mode solver — mixed transverse
  Nédélec / longitudinal nodal formulation, effective indices and vector mode profiles
- **M3b**: 3D Maxwell — tetrahedral Nédélec edge elements, rectangular cavity eigenmodes

## Layout

```
galerkin/
  mesh.py         # Mesh data structure (boundary nodes + edges) + structured mesh generators
  assembly.py     # Stiffness K (scalar/tensor coefficients), mass M, boundary B, load vector
  solver.py       # Dirichlet reduction + scipy sparse direct solve (real/complex)
  postprocess.py  # E = -grad V, L2 error (complex-aware)
  pml.py          # Cylindrical PML coefficients (Collino-Monk complex stretching)
  edge.py         # Lowest-order Nédélec (Whitney) edge elements: numbering, signs, curl-curl, mass, edge-nodal coupling
  waveguide.py    # M3a: mixed edge/nodal vector mode solver, A x = -beta^2 B x
  mesh3d.py       # M3b: Mesh3D + box_mesh (Kuhn subdivision, six tets per cube)
  assembly3d.py   # M3b: P1 tetrahedron stiffness (scalar/tensor) and mass, closed form
  edge3d.py       # M3b: Whitney edge elements on tetrahedra, all matrices closed form
  gmsh.py         # M3b: read/write Gmsh .msh (ASCII 2.2 and 4.1) — Gmsh never linked
  interop.py      # from_mesher: adapt a mesh built elsewhere (meshine, gmshio, ...)
tests/
  # pytest suite grading M1-M3b against `refsol`, the answer-key package
examples/
  coax_convergence.py        # M1 validation: coaxial cable + convergence study
  waveguide_convergence.py   # M2 validation 1: plane wave in a guide + convergence
  cylinder_scattering.py     # M2 validation 2: cylinder scattering vs Bessel/Hankel series
  cylinder_scattering_pml.py # M2.5: first-order ABC vs PML convergence comparison
  waveguide_modes.py         # M3-prep: waveguide cutoff eigenmodes (Nedelec vs nodal)
  fiber_modes.py             # M3a: step-index fibre modes vs the exact vector dispersion relation
  cavity_modes.py            # M3b: rectangular PEC cavity spectrum, 3D
  mesh_io.py                 # M3b: Gmsh reader gates — fixtures, round trip, physics
  visualize*.py              # Figure generation for each milestone
```

## Tests

The engine is graded against [galerkin-refsol](https://github.com/FieldAlgo/galerkin-refsol),
a separate package holding the closed-form and published reference solutions. It
lives in its own repository on purpose: a solver that ships its own idea of the
right answer can agree with itself forever. `tests/test_independence.py` enforces
that the engine never imports it, and that the engine's only dependencies stay
numpy and scipy.

```bash
pip install -e '.[test]'
pytest                      # everything, about fifteen minutes
pytest -m "not slow"        # the fast gates, about two minutes
```

The examples keep their own analytical solutions so they run without the test
extra; two tests check those independent implementations against refsol so the
pair cannot drift apart.

## Run

```bash
PYTHONPATH=. python3 examples/coax_convergence.py        # M1 validation
PYTHONPATH=. python3 examples/waveguide_convergence.py   # M2 convergence
PYTHONPATH=. python3 examples/cylinder_scattering.py     # M2 scattering
PYTHONPATH=. python3 examples/cylinder_scattering_pml.py # M2.5 ABC vs PML
PYTHONPATH=. python3 examples/waveguide_modes.py         # M3-prep eigenmodes
PYTHONPATH=. python3 examples/fiber_modes.py            # M3a step-index fibre
PYTHONPATH=. python3 examples/cavity_modes.py           # M3b 3D cavity
PYTHONPATH=.:examples python3 examples/mesh_io.py       # M3b Gmsh reader
PYTHONPATH=.:examples python3 examples/visualize.py      # figures
PYTHONPATH=.:examples python3 examples/visualize_fiber.py  # M3a figure
PYTHONPATH=.:examples python3 examples/visualize_cavity.py # M3b figure
```

## Validation results (2026-09-05)

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

  Two further checks are permanent gates in `examples/fiber_modes.py`:

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
  a dependency of the engine: [meshine](https://github.com/FieldAlgo/meshine)
  (pure numpy/scipy, planar) and [gmshio](https://github.com/FieldAlgo/gmshio)
  (runs the Gmsh executable as a separate process).

  On a meshine mesh of Hadley's **rib waveguide** (`refsol.benchmarks.RIB_WAVEGUIDES`,
  quoted to ±3e-6) the quasi-TE index comes out **4.8e-5** from the published
  value. Re-entrant dielectric corners where the rib meets the slab, not the
  reference, set that floor.

  On a gmshio mesh of the unit cube the cluster means land within **5.1e-3** and
  nothing spurious appears between the analytic resonances. The strict
  second-order ladder stays on the structured meshes galerkin builds itself:
  Gmsh's `lc` is a target size, so two meshes in a refinement sequence are not
  nested and a fitted order would measure the mesher as much as the solver.

## Next

- **MFEM** as the production core, under consideration for the point where
  problem sizes outgrow a pure-Python direct solve. The 3D sparse factorization
  here is comfortable to about 25k edge dofs on four cores; beyond that it wants
  iterative solvers with an auxiliary-space preconditioner.
- **Dielectric-loaded and open 3D problems**: the tensor-coefficient path exists
  in 3D (`assemble_stiffness_3d` takes (T,3,3) tensors), so the M2.5 PML carries
  over; what is missing is a 3D validation case with an analytical answer.
- **Beyond electromagnetics**: the assembly core is physics-neutral. Anisotropic
  steady heat conduction with convective (Robin) boundaries already runs on the
  M1 routines unchanged; elasticity needs a vector nodal space, transient
  problems a time integrator, and Stokes a P2 space. M3a's two-field block
  system is the pattern every coupled multiphysics problem reuses.

## License

Not yet licensed for redistribution; a permissive license is planned at first
public release.
