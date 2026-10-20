# galerkin-refsol — reference solutions for validating galerkin

[Documentation](../../docs/packages/galerkin-refsol/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Closed-form solutions and published high-accuracy benchmarks used as the
answer key for the [galerkin](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/README.md)
FEM engine. It is a separate package in the same monorepo;
the grader never imports the code it grades. It depends only on numpy and scipy.

A numerical solver is software that can be plausibly wrong. This package is
the part that does not depend on the discretization.

The Python package name is `refsol` (`from refsol import fiber`).

## What is in it

| module | contents | self-checks |
|---|---|---|
| `refsol.thermoelasticity` | Prescribed-Kelvin uniform free/constrained, compatible and sine fields; out-of-plane stress and physical elastic energy | Original three-dimensional law, no FEM imports |
| `refsol.thermal` | Kelvin slab and steady sine manufactured fields; heat flux W/m^2 and source W/m^3 | Direct analytic derivatives, no engine imports |
| `refsol.thermal_boundary` | Steady slabs and a sine field with prescribed outward flux and Robin convection | Closed forms, no engine imports |
| `refsol.transient_heat` | Uniform insulated heating, moving affine field, manufactured sine solution; small dense P1 matrices and backward-Euler modal references | Analytic forms and dense eigenproblems, no engine imports |
| `refsol.thermoelastic_traction` | Combined thermal-strain and traction fields, polynomial manufactured solutions and `traction_from_stress` from the original 3D law | NumPy/stdlib only, no engine imports |
| `refsol.elasticity_traction` | Plane stress/strain uniaxial and shear fields, Cartesian sigma*n and polynomial traction resultants | Closed forms and direct differentiation, no FEM imports |
| `refsol.elasticity` | Homogeneous isotropic plane stress/strain: affine fields, closed-form stress and a smooth manufactured solution | Material coefficients, engineering shear and independent force differentiation |
| `refsol.slab` | planar dielectric waveguide TE/TM modes, symmetric or asymmetric; TE field profile | mode count vs cutoff formula, even-mode equation, interface continuity |
| `refsol.fiber` | step-index fiber: scalar LP modes (Gloge), exact vector modes TE/TM/HE/EH, and exact vector group index by implicit differentiation (`vector_group_index`, optional material dispersion) and exact vector mode fields (`vector_mode_field`) | LP count vs Bessel cutoffs, LP11 cutoff at 2.4048, HE11 ≈ LP01 in weak guidance, LP11 group degeneracy, Rudolph–Neumann approximation; group index vs Richardson-extrapolated refined roots, residual partials vs central differences; field continuity singular at the root, interface conditions (E_phi, E_z, n^2 E_r) |
| `refsol.metallic` | rectangular waveguide cutoffs, rectangular cavity resonances, coaxial potential and field | closed forms |
| `refsol.cavity` | every vacuum PEC box mode up to a frequency ceiling, with polarization and geometric degeneracy, SI | independent Cartesian enumeration, no solver or mesh |
| `refsol.material_cavity` | complex resonances and Q of a PEC box uniformly filled or loaded by a lossy dielectric/magnetic slab (TE/TM-to-z transcendental roots), `exp(+j*omega*t)` | vacuum limit equals the Cartesian spectrum, identical layers equal uniform rescaling, small-loss Q equals the energy filling factor |
| `refsol.wall_loss` | first-order conductor-loss Q of rectangular cavity modes per wall, split degenerate polarizations, uniform filling | Pozar TE101, numerical quadrature of a finite-difference curl, per-wall additivity, sqrt(sigma) scaling |
| `refsol.scattering` | plane wave on a circular cylinder: PEC (TM/TE) and dielectric, partial-wave series; scattering width | boundary conditions satisfied to 1e-9, interface continuity, geometric-optics limit |
| `refsol.benchmarks` | Hadley (2002) rib-waveguide n_eff table (±3e-6) and dielectric-corner cases (±1e-8), fully specified geometry | — |

## Usage

Explicitly import `refsol.thermoelasticity` for the prescribed-temperature
mechanical-stage reference fields. Coordinates/displacement use m, T and Tref
absolute K, signed alpha 1/K, E/stress Pa and energy density J/m^3. The original
3D elastic law retains the plane-strain out-of-plane stress and energy; a free
uniform plane-strain field can have zero in-plane stress and nonzero energy.
This module is automatically included in sdists and wheels, with byte checks.
It does not solve heat or certify a sequential heat-to-mechanics workflow.

For steady heat, explicitly import `refsol.thermal`; `slab` returns temperature,
heat flux and heat source for metre coordinates, Kelvin and conductivity W/(m K).
For boundary-loaded elasticity, explicitly import `refsol.elasticity_traction`.
Its traction vectors use global Cartesian Pa; integrated mechanical load is N/m
of out-of-plane thickness. Both modules are automatically included as Python
code in sdists and wheels. The installed distribution checks verify their bytes
and public imports. They do not implement a coupled thermoelastic model.

For static 2D elasticity, explicitly import `refsol.elasticity`. Its coordinates
and displacement use metres, E and stress use Pa, body force uses N/m^3, and
strain is ordered `(epsilon_xx, epsilon_yy, gamma_xy)` with engineering shear.
For example, uniaxial extension with free lateral traction in plane stress:

```python
from refsol.elasticity import affine

field = affine([[0., 0.], [1., 1.]], [[1e-3, 0.], [0., -0.3e-3]],
               young_modulus=70e9, poisson_ratio=0.3, plane="stress")
print(field.displacement)  # metres
print(field.stress)        # [70e6, 0, 0] Pa at each point (up to roundoff)
```

The reference module is included in both the sdist and wheel. It imports no FEM
engine. The separate [engine contract](../../docs/packages/galerkin/elasticity2d.md)
describes boundary constraints, per-thickness loads and locking limitations.

```python
from refsol import fiber, slab, scattering, benchmarks

# exact HE11 effective index of a step-index fiber
n_eff = fiber.fundamental_neff(a=4.0, n1=1.45, n2=1.44, wavelength=1.55)

# all guided TE modes of a 220 nm SOI slab
slab.modes(n_f=3.48, n_s=1.444, n_c=1.444, d=0.22, wavelength=1.55, pol="TE")

# scattered field of a PEC cylinder, radius a, wavenumber k, at points (x, y)
u_s = scattering.scattered(x, y, k=3.14, a=1.0, kind="pec_tm")

# published reference: quasi-TE n_eff of the Hadley rib waveguide, slab 0.3 um
benchmarks.rib_neff(0.3)   # 3.412492
```

`refsol.thermal_boundary` provides independent closed forms for prescribed
outward flux and Robin boundaries. Coordinates are m, temperature K,
conductivity W/(m K), outward flux W/m^2 and convection h W/(m^2 K).

`refsol.transient_heat` provides `uniform_insulated`, `moving_affine`,
`sine_manufactured`, small dense `p1_matrices`, `smallest_dirichlet_mode` and
`backward_euler_amplitude`. Coordinates/time/temperature are m/s/K,
conductivity W/(m K), volumetric heat capacity J/(m³ K), source W/m³ and flux
W/m². The dense matrices and modes target small reference meshes; a
semidiscrete backward-Euler product is distinct from a continuum PDE solution.
These references do not certify physical temperature validity or a maximum
principle. The transient engine is documented in the galerkin
[transient heat contract](../../docs/packages/galerkin/transient_heat.md).

`refsol.thermoelastic_traction` provides `uniform_combined`,
`polynomial_manufactured`, `parent_state` and `traction_from_stress` from the
original 3D constitutive law. Coordinates/displacement are m, temperature K,
stress/total traction Pa, body force N/m^3, force/reaction N/m and physical
energy J/m. It supplies prescribed-temperature mechanical references, not a heat
solve or source authentication.

All reference modules ship in the sdist and wheel. None of them implements a
coupled model, and independent acceptance tests derive their own expected values.

## Run the self-checks

```bash
# From the repository root
python -m pip install pytest -e packages/galerkin-refsol
python -m pytest -q tests/refsol
```

## Use from galerkin

```bash
# From the repository root
python -m pip install -e packages/galerkin-refsol
```

Suggested validation order for a vector mode solver: step-index fiber
(exact, so the convergence rate can be measured) → Hadley dielectric corners
(±1e-8, structured mesh is enough) → Hadley rib waveguide (±3e-6, needs an
unstructured mesh).

Every module carries tests that check the implementation against independent
physics (cutoff conditions, limiting cases, boundary conditions) rather than
against itself, so a passing suite means the references can be trusted as
graders for another solver.

## Conventions

- Time dependence `exp(-i omega t)`; incident plane waves travel toward +x.
- Lengths in any consistent unit (the wavelength sets the scale).
- Effective index `n_eff = beta / k0`.

## References

- D. Gloge, "Weakly guiding fibers," Appl. Opt. 10, 2252 (1971).
- A. W. Snyder and J. D. Love, *Optical Waveguide Theory* (Chapman & Hall, 1983).
- K. Okamoto, *Fundamentals of Optical Waveguides*, 2nd ed. (Academic Press, 2006).
- G. R. Hadley, "High-accuracy finite-difference equations for dielectric waveguide
  analysis II: dielectric corners," J. Lightwave Technol. 20, 1210 (2002).
- Benchmark values are Hadley's published results, cross-checked against the same
  table in the femwell project's benchmark documentation (GPL-3.0). Only the
  numerical values are reproduced; see NOTICE.

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

The benchmark values in `refsol.benchmarks` are numerical results published by
Hadley (2002); see [NOTICE](NOTICE) for their provenance.
