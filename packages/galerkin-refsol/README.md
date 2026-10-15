# galerkin-refsol — reference solutions for validating galerkin

Closed-form solutions and published high-accuracy benchmarks used as the
answer key for the [galerkin](https://github.com/fieldalgo/openphysics/blob/2efbc413df5d3d36bcc4c9879b34ed88213b9217/packages/galerkin/README.md)
FEM engine. It is a separate package in the same monorepo;
the grader never imports the code it grades. It depends only on numpy and scipy.

A numerical solver is software that can be plausibly wrong. This package is
the part that does not depend on the discretization.

The Python package name is `refsol` (`from refsol import fiber`).

## What is in it

| module | contents | self-checks |
|---|---|---|
| `refsol.thermal` | Kelvin slab and steady sine manufactured fields; heat flux W/m^2 and source W/m^3 | Direct analytic derivatives, no engine imports |
| `refsol.elasticity_traction` | Plane stress/strain uniaxial and shear fields, Cartesian sigma*n and polynomial traction resultants | Closed forms and direct differentiation, no FEM imports |
| `refsol.elasticity` | Homogeneous isotropic plane stress/strain: affine fields, closed-form stress and a smooth manufactured solution | Material coefficients, engineering shear and independent force differentiation |
| `refsol.slab` | planar dielectric waveguide TE/TM modes, symmetric or asymmetric; TE field profile | mode count vs cutoff formula, even-mode equation, interface continuity |
| `refsol.fiber` | step-index fiber: scalar LP modes (Gloge) and exact vector modes TE/TM/HE/EH | LP count vs Bessel cutoffs, LP11 cutoff at 2.4048, HE11 ≈ LP01 in weak guidance, LP11 group degeneracy, Rudolph–Neumann approximation |
| `refsol.metallic` | rectangular waveguide cutoffs, rectangular cavity resonances, coaxial potential and field | closed forms |
| `refsol.scattering` | plane wave on a circular cylinder: PEC (TM/TE) and dielectric, partial-wave series; scattering width | boundary conditions satisfied to 1e-9, interface continuity, geometric-optics limit |
| `refsol.benchmarks` | Hadley (2002) rib-waveguide n_eff table (±3e-6) and dielectric-corner cases (±1e-8), fully specified geometry | — |

## Usage

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
engine. The separate [engine contract](https://github.com/fieldalgo/openphysics/blob/a292ae15707b3713f0464b4d126be765b4c205ae/packages/galerkin/docs/elasticity2d.md)
describes boundary constraints, per-thickness loads and locking limitations.
It is a repository link requiring network access and repository permission.

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

## Run the self-checks

```bash
# From the repository root
python -m pip install pytest -e packages/galerkin-refsol
python -m pytest -q packages/galerkin-refsol/tests
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
