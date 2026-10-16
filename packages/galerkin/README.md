# galerkin — an electromagnetic FEM engine (FieldAlgo project)

[English](README.md) | [한국어](README.ko.md)

[English / 한국어 documentation and translation status](https://github.com/fieldalgo/openphysics/blob/develop/docs/README.md)

A finite-element solver engine written in pure Python (numpy + scipy.sparse),
built milestone by milestone with an analytical-validation-first culture.
Currently covers 2D electromagnetics, static 2D elasticity and 3D cavity eigenmodes; designed to grow
into a multiphysics core.

- **M1**: Electrostatics — ∇·(ε∇V) = −ρ (P1 elements)
- **M2**: Frequency-domain waves — ∇²u + k²u = 0 (complex arithmetic, absorbing boundaries)
- **M2.5**: Cylindrical PML (complex coordinate stretching → anisotropic tensor coefficients)
- **M3-prep**: Nédélec edge elements — waveguide eigenmodes ∇×∇×E = k_c²E in H(curl)
- **M3a**: Dielectric waveguide cross-section mode solver — mixed transverse
  Nédélec / longitudinal nodal formulation, effective indices and vector mode profiles
- **M3b**: 3D Maxwell — tetrahedral Nédélec edge elements, rectangular cavity eigenmodes

The public `solve_cavity_box` API provides SI frequencies and raw edge fields for
a vacuum PEC box. See its [API and numerical contract](docs/cavity_solver.md),
including near-target search limitations and the alternating-mesh repair of the
rectangular cluster-mean convergence gate.

The standalone `galerkin.elasticity` submodule solves homogeneous isotropic,
small-strain static P1 elasticity with explicit plane stress or plane strain.
See the [elasticity API, units and limitations](docs/elasticity2d.md) and the
[English example](examples/elasticity2d.py). These files are included in the
sdist. The example can run from the repository root or an unpacked galerkin
sdist after installing the packages; it is not a simcase/Studio model.
The separate [independent elasticity validation](docs/elasticity2d_independent_validation.md)
documents polynomial manufactured fields, mixed boundaries and work/energy
checks; its contract is also included byte-for-byte in the sdist.

Vector modes retain complex transverse and longitudinal coefficients, including
degenerate eigenspace directions. Read the [eigenspace reliability contract](docs/eigenspace_reliability.md)
before converting fields to real values; this does not add subspace tracking.

The standalone `galerkin.thermal` API solves homogeneous isotropic steady 2D
conduction in Kelvin, with volumetric sources and natural insulation. Read the
[heat contract and boundary signs](docs/thermal_steady2d.md) and run the
[English heat example](examples/thermal_steady2d.py) after installing the packages.
The [independent heat validation](docs/thermal_independent_validation.md) and
[historical acceptance manifest](docs/thermal_independent_validation_manifest.json)
are preserved as originally recorded and included byte-for-byte in the sdist.
Static elasticity additionally accepts global Cartesian boundary tractions:
see the [traction guide](docs/elasticity_traction.md),
[English traction example](examples/elasticity_traction.py) and
[independent acceptance](docs/elasticity_traction_independent_validation.md).
These documents and examples are included in the sdist. Neither API adds
transient analysis, thermoelastic coupling, simcase or Studio integration.

The separate `galerkin.thermoelasticity` submodule is a static mechanical stage
for an explicitly prescribed same-mesh nodal-P1 Kelvin field. See its
[SI contract, immutable snapshot and physical 3D energy](docs/prescribed_temperature_thermoelasticity.md)
and [English executable example](examples/prescribed_temperature_thermoelasticity.py),
both included byte-for-byte in the sdist. Alpha is signed 1/K; displacement is
m, stress Pa, load/reaction N/m and physical elastic energy J/m of thickness.
It does not solve heat, automatically connect a heat result, validate a full
sequential coupling workflow, or add simcase/Studio integration.
The separate [independent mechanical-stage acceptance](docs/prescribed_temperature_thermoelasticity_independent_validation.md)
and its original oracle/tests are also included unchanged in the sdist.

## Layout

For a headless JSON/API/CLI wrapper around the standalone steady heat solver,
see the [simcase thermal document contract](https://github.com/fieldalgo/openphysics/blob/4ec9da9fcba661958a12f37bc445a543cb4ffc1c/packages/simcase/docs/thermal_steady2d.md).
The wrapper handles explicit length units, Kelvin inputs and numeric SI result
files; this does not add a thermal Studio interface or automatic heat-to-mechanics
workflow to this engine.

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
  cavity.py       # Public vacuum PEC box solver, SI output and projected gradient kernel
  gmsh.py         # M3b: read/write Gmsh .msh (ASCII 2.2 and 4.1) — Gmsh never linked
  interop.py      # from_mesher: adapt a mesh built elsewhere (meshine, gmshio, ...)
tests/
  test_electrostatics.py   # M1   coax potential and field
  test_helmholtz.py        # M2   guided wave, cylinder scattering, and the PML
  test_edge_elements.py    # M3-prep waveguide cutoffs, and the nodal counter-example
  test_slab_modes.py       # M3a  the 1D limit, where the polarizations separate
  test_fiber_modes.py      # M3a  step-index fibre vector modes
  test_hadley.py           # M3a  dielectric corners and the rib waveguide family
  test_cavity_modes.py     # M3b  3D cavity, structured and unstructured
  test_mesh_io.py          # M3b  the Gmsh reader
  test_interop.py          #      meshes built by meshine and gmshio
  test_pipeline.py         #      the two end-to-end example pipelines
  test_independence.py     #      the engine never imports its own answer key
examples/
  coax_convergence.py        # M1 validation: coaxial cable + convergence study
  waveguide_convergence.py   # M2 validation 1: plane wave in a guide + convergence
  cylinder_scattering.py     # M2 validation 2: cylinder scattering vs Bessel/Hankel series
  cylinder_scattering_pml.py # M2.5: first-order ABC vs PML convergence comparison
  waveguide_modes.py         # M3-prep: waveguide cutoff eigenmodes (Nedelec vs nodal)
  fiber_modes.py             # M3a: step-index fibre modes vs the exact vector dispersion relation
  cavity_modes.py            # M3b: rectangular PEC cavity spectrum, 3D
  rib_waveguide_scalar.py    # end-to-end: meshine -> galerkin P1 -> refsol Hadley
  rib_waveguide_vector.py    # the same chain with the M3a vector solver
  mesh_io.py                 # M3b: Gmsh reader gates — fixtures, round trip, physics
  visualize*.py              # Figure generation for each milestone
```

## Tests

The engine is graded against [galerkin-refsol](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin-refsol/README.md),
a separate package holding the closed-form and published reference solutions. It
shares this repository but stays an independent implementation: the reference
package does not import the solver it grades. `tests/test_independence.py` enforces
that the engine never imports it, and that the engine's only dependencies stay
numpy and scipy.

```bash
# From the repository root
python -m pip install -e packages/galerkin   # engine only: numpy and scipy
# Install the full local test stack using ../../README.md, then:
python -m pytest -q packages/galerkin/tests
python -m pytest -q packages/galerkin/tests -m "not slow"
```

Run all commands from the repository root. An editable install puts `galerkin`
on the path, so the tests and examples run without `PYTHONPATH=.`.

The examples keep their own analytical solutions so they run without the test
extra; two tests check those independent implementations against refsol so the
pair cannot drift apart.

## Run

```bash
python packages/galerkin/examples/coax_convergence.py        # M1 validation
python packages/galerkin/examples/waveguide_convergence.py   # M2 convergence
python packages/galerkin/examples/cylinder_scattering.py     # M2 scattering
python packages/galerkin/examples/cylinder_scattering_pml.py # M2.5 ABC vs PML
python packages/galerkin/examples/waveguide_modes.py         # M3-prep eigenmodes
python packages/galerkin/examples/fiber_modes.py            # M3a step-index fibre
python packages/galerkin/examples/cavity_modes.py           # M3b 3D cavity
python packages/galerkin/examples/mesh_io.py       # M3b Gmsh reader
python packages/galerkin/examples/visualize.py      # figures
python packages/galerkin/examples/visualize_fiber.py  # M3a figure
python packages/galerkin/examples/visualize_cavity.py # M3b figure
```

## Validation results (2026-09-05)

These are historical measurements from the date above, not a fresh test report.

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

  All eight of Hadley's **rib waveguides** (`refsol.benchmarks.RIB_WAVEGUIDES`,
  quoted to ±3e-6, slab thickness 0 to 0.7 µm) come out within **1.2e-4** of the
  published quasi-TE indices on a meshine mesh. Re-entrant dielectric corners
  where the rib meets the slab, not the reference, set that floor.

  A per-case tolerance can be met while the family is wrong, so the trend is
  gated separately: the published indices rise monotonically across the eight by
  2.08e-3 in total, and that spread is reproduced to 9.4e-5.

- **The pipeline end to end.** `examples/rib_waveguide_scalar.py` and
  `examples/rib_waveguide_vector.py` run the whole chain — meshine builds the
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

## Next

- **MFEM** as the production core, under consideration for the point where
  problem sizes outgrow a pure-Python direct solve. The 3D sparse factorization
  here is comfortable to about 25k edge dofs on four cores; beyond that it wants
  iterative solvers with an auxiliary-space preconditioner.
- **Dielectric-loaded and open 3D problems**: the tensor-coefficient path exists
  in 3D (`assemble_stiffness_3d` takes (T,3,3) tensors), so the M2.5 PML carries
  over; what is missing is a 3D validation case with an analytical answer.
- **Beyond electromagnetics**: the low-level assembly can represent anisotropic
  coefficients. The public steady-heat API currently accepts homogeneous
  isotropic conductivity, including prescribed outward flux and Robin boundaries.
  Static elasticity provides its own vector nodal space. The transient heat
  submodule below uses backward Euler; other transient physics needs its own
  time integration, and Stokes needs a P2 space. The M3a two-field block system
  illustrates an assembly pattern; it does not certify automatic coupling.

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

Gmsh is a separate program under GPL-2.0-or-later. It is neither distributed
with this engine nor linked into it: `galerkin.gmsh` is an independent parser
for the published MSH ASCII formats, and Gmsh itself, when used at all, is run
as a separate executable. The GPL therefore does not extend to `galerkin` or to
code that uses it.

This project is not affiliated with, endorsed by, or supported by the Gmsh
project.

## Steady heat boundary contract

The standalone isotropic `galerkin.thermal` API adds prescribed outward flux and
Robin convection; see [boundary contract](docs/thermal_flux_robin.md),
[English example](examples/thermal_flux_robin.py), and
[independent acceptance](docs/thermal_flux_robin_independent_validation.md).
The contract and independent report distinguish implementation from measured acceptance.
The headless simcase JSON contract still rejects flux/Robin boundaries; the
standalone extension does not enable them in Studio or add automatic coupling.

## Explicit one-way thermal–mechanical workflow

`galerkin.thermal_mechanical.solve_steady_thermoelasticity` explicitly solves
steady Dirichlet/insulated heat, freezes the exact nodal-P1 Kelvin field, and
runs prescribed-temperature mechanics on the same isolated reference mesh.
See the [EN/KO implementation contract](docs/thermal_mechanical_workflow.md),
[English example](examples/thermal_mechanical_workflow.py) and
[independent acceptance report](docs/thermal_mechanical_independent_validation.md).
Inputs require explicit m/K declarations; no unit conversion is inferred.
This Python-only, steady one-way operation adds no JSON/CLI/Studio or persistence
contract, Robin/flux/traction workflow, transient feedback or thermodynamic
coupling. Immutable transfer does not certify callbacks or mutable results after
return. The contract separates heat W/m, mechanical N/m and physical energy J/m.

## Transient heat Python submodule

Import `galerkin.transient_heat.solve_transient_heat` explicitly. It uses fixed conforming P1 triangles, consistent mass and backward Euler, constant isotropic conductivity/volumetric heat capacity, fixed Dirichlet nodes with time-dependent temperatures, and insulation elsewhere. Coordinates, time and temperature are m, s and K. Finite negative Kelvin is allowed by the linear mathematical API; no clamping, physical-temperature certification or discrete maximum principle is promised. The separate heat-to-mechanics transfer still rejects negative K.

[Usage](docs/transient_heat.md) ([한국어](docs/locales/ko/pages/transient_heat.md)) · [Producer validation contract](docs/transient_heat_validation.md) ([한국어](docs/locales/ko/pages/transient_heat_validation.md)) · [Independent validation report](docs/transient_heat_independent_validation.md) ([한국어](docs/locales/ko/pages/transient_heat_independent_validation.md))

Implementation and acceptance files are submitted, but numerical, build and installed checks are unexecuted. Fixed verification gates are not measured pass results; this is not release or integration acceptance. No Robin/flux, JSON/CLI/Studio, persistence or automatic thermal–mechanical connection is added.

## Prescribed-temperature total mechanical traction

The [total-traction contract](docs/thermoelastic_traction.md), [English example](examples/thermoelastic_traction.py) and [independent report](docs/thermoelastic_traction_independent_validation.md) describe optional global Cartesian Pa loads on the frozen-temperature mechanical stage. The prescribed mapping is total physical `sigma*n`; do not add/subtract thermal traction. Body, line, thermal loads and constrained reactions remain separately accounted for. Legacy18 positional result construction remains valid; new load fields default to None. There is no dedicated scalar-pressure/local-frame/follower API, but `lambda points_m, normals: -p * normals` is a valid global Pa callback on the fixed reference boundary. This does not extend the heat workflow, JSON/CLI/Studio or persistence.
