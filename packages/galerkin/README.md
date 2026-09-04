# galerkin — a 2D electromagnetic FEM engine (FieldAlgo project)

A finite-element solver engine written in pure Python (numpy + scipy.sparse),
built milestone by milestone with an analytical-validation-first culture.
Currently covers 2D electromagnetics; designed to grow into a multiphysics core.

- **M1**: Electrostatics — ∇·(ε∇V) = −ρ (P1 elements)
- **M2**: Frequency-domain waves — ∇²u + k²u = 0 (complex arithmetic, absorbing boundaries)
- **M2.5**: Cylindrical PML (complex coordinate stretching → anisotropic tensor coefficients)
- **M3-prep**: Nédélec edge elements — waveguide eigenmodes ∇×∇×E = k_c²E in H(curl)

## Layout

```
galerkin/
  mesh.py         # Mesh data structure (boundary nodes + edges) + structured mesh generators
  assembly.py     # Stiffness K (scalar/tensor coefficients), mass M, boundary B, load vector
  solver.py       # Dirichlet reduction + scipy sparse direct solve (real/complex)
  postprocess.py  # E = -grad V, L2 error (complex-aware)
  pml.py          # Cylindrical PML coefficients (Collino-Monk complex stretching)
  edge.py         # Lowest-order Nédélec (Whitney) edge elements: numbering, signs, curl-curl, mass
examples/
  coax_convergence.py        # M1 validation: coaxial cable + convergence study
  waveguide_convergence.py   # M2 validation 1: plane wave in a guide + convergence
  cylinder_scattering.py     # M2 validation 2: cylinder scattering vs Bessel/Hankel series
  cylinder_scattering_pml.py # M2.5: first-order ABC vs PML convergence comparison
  waveguide_modes.py         # M3-prep: waveguide cutoff eigenmodes (Nedelec vs nodal)
  visualize*.py              # Figure generation for each milestone
```

## Run

```bash
PYTHONPATH=. python3 examples/coax_convergence.py        # M1 validation
PYTHONPATH=. python3 examples/waveguide_convergence.py   # M2 convergence
PYTHONPATH=. python3 examples/cylinder_scattering.py     # M2 scattering
PYTHONPATH=. python3 examples/cylinder_scattering_pml.py # M2.5 ABC vs PML
PYTHONPATH=. python3 examples/waveguide_modes.py         # M3-prep eigenmodes
PYTHONPATH=.:examples python3 examples/visualize.py      # figures
```

## Validation results (2026-09-04)

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

## Next

- **M3a**: dielectric waveguide cross-section mode solver (transverse Nédélec +
  longitudinal nodal mixed formulation) — effective indices and vector mode
  profiles, validated against the step-index fiber
- **M3b**: 3D Maxwell (tetrahedral Nédélec, cavity eigenmodes; MFEM under
  consideration as the production core), unstructured mesh input via Gmsh
  (run as a separate executable — GPL isolation)

## License

Not yet licensed for redistribution; a permissive license is planned at first
public release.
