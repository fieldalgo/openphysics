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
examples/
  coax_convergence.py        # M1 validation: coaxial cable + convergence study
  waveguide_convergence.py   # M2 validation 1: plane wave in a guide + convergence
  cylinder_scattering.py     # M2 validation 2: cylinder scattering vs Bessel/Hankel series
  cylinder_scattering_pml.py # M2.5: first-order ABC vs PML convergence comparison
  waveguide_modes.py         # M3-prep: waveguide cutoff eigenmodes (Nedelec vs nodal)
  fiber_modes.py             # M3a: step-index fibre modes vs the exact vector dispersion relation
  visualize*.py              # Figure generation for each milestone
```

## Run

```bash
PYTHONPATH=. python3 examples/coax_convergence.py        # M1 validation
PYTHONPATH=. python3 examples/waveguide_convergence.py   # M2 convergence
PYTHONPATH=. python3 examples/cylinder_scattering.py     # M2 scattering
PYTHONPATH=. python3 examples/cylinder_scattering_pml.py # M2.5 ABC vs PML
PYTHONPATH=. python3 examples/waveguide_modes.py         # M3-prep eigenmodes
PYTHONPATH=. python3 examples/fiber_modes.py            # M3a step-index fibre
PYTHONPATH=.:examples python3 examples/visualize.py      # figures
PYTHONPATH=.:examples python3 examples/visualize_fiber.py  # M3a figure
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
  2.5e-3, TE10 rate **2.00**, curl kernel exactly at zero; the same problem
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

  That measurement has one dangerous confound: a mesh without rotational
  symmetry splits the *degenerate* HE11 and HE21 pairs too, and the artefact
  would be indistinguishable from physics. `disk_mesh` keeps an exact C_n
  symmetry, and the measured artificial splitting is **1.2e-14** — twelve orders
  of magnitude below the physical splitting it could have been confused with.

## Next

- **M3b**: 3D Maxwell (tetrahedral Nédélec, cavity eigenmodes; MFEM under
  consideration as the production core), unstructured mesh input via Gmsh
  (run as a separate executable — GPL isolation)
- **Beyond electromagnetics**: the assembly core is physics-neutral. Anisotropic
  steady heat conduction with convective (Robin) boundaries already runs on the
  M1 routines unchanged; elasticity needs a vector nodal space, transient
  problems a time integrator, and Stokes a P2 space. M3a's two-field block
  system is the pattern every coupled multiphysics problem reuses.

## License

Not yet licensed for redistribution; a permissive license is planned at first
public release.
