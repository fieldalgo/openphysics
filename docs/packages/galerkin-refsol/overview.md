# galerkin-refsol — reference solutions for validating galerkin

**English** | [한국어](../../locales/ko/pages/packages/galerkin-refsol/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Closed-form solutions and published high-accuracy benchmarks used as the
answer key for the [galerkin](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/README.md)
FEM engine. It is a separate package in the same monorepo;
the grader never imports the code it grades. It depends only on numpy and scipy;
`refsol.bent_slab` alone needs the optional `mpmath` when called.

A numerical solver is software that can be plausibly wrong. This package is
the part that does not depend on the discretization.

The Python package name is `refsol` (`from refsol import fiber`).

## What is in it

| module | contents | self-checks |
|---|---|---|
| `refsol.thermoelasticity` | Prescribed-Kelvin uniform free/constrained, compatible and sine fields; out-of-plane stress and physical elastic energy | Original three-dimensional law, no FEM imports |
| `refsol.thermal` | Kelvin slab and steady sine manufactured fields; heat flux W/m^2 and source W/m^3 | Direct analytic derivatives, no engine imports |
| `refsol.thermal_boundary` | Steady slabs and a sine field with a prescribed inward heat flux and Robin convection | Closed forms, no engine imports |
| `refsol.transient_heat` | Uniform insulated heating, moving affine field, manufactured sine solution; small dense P1 matrices and backward-Euler modal references | Analytic forms and dense eigenproblems, no engine imports |
| `refsol.thermal_multilayer` | Steady conduction through layered walls with piecewise-constant conductivity and a uniform source per layer: series slab and concentric composite cylinder, temperature and normal flux continuous at the interfaces | Boundary values and series resistance without source, interface continuity, Fourier's law and energy balance by finite differences, textbook single layer; no engine imports |
| `refsol.transient_heat_multilayer` | Transient conduction through a layered wall by an eigenfunction series (`LayeredWall`): eigenvalues by bisection on the exact Pruefer zero count, so none is skipped; fixed end temperatures, given initial amplitudes or source-driven starts | Single-layer sine series, two-layer characteristic equation, independent fine finite-element eigenvalues, c-weighted orthogonality and interface conditions, PDE/boundary/initial residuals, steady long-time limit; no engine imports |
| `refsol.elasticity_multilayer` | Perfectly bonded layered isotropic solids in plane stress or strain: axial laminate with free faces, series bar under uniform axial stress (matched lateral strain only) and a concentric composite cylinder under pressure with a per-layer logarithmic temperature change | Traction-free faces and the elastic law, Lamé single shell, Timoshenko thermal stresses, stress-free uniform heating, equilibrium with interface and boundary conditions; no engine imports |
| `refsol.thermoelastic_traction` | Combined thermal-strain and traction fields, polynomial manufactured solutions and `traction_from_stress` from the original 3D law | NumPy/stdlib only, no engine imports |
| `refsol.elasticity_traction` | Plane stress/strain uniaxial and shear fields, Cartesian sigma*n and polynomial traction resultants | Closed forms and direct differentiation, no FEM imports |
| `refsol.elasticity` | Homogeneous isotropic plane stress/strain: affine fields, closed-form stress and a smooth manufactured solution | Material coefficients, engineering shear and independent force differentiation |
| `refsol.slab` | planar dielectric waveguide TE/TM modes, symmetric or asymmetric; TE field profile | mode count vs cutoff formula, even-mode equation, interface continuity |
| `refsol.lossy_slab` | multilayer slab with complex permittivity, public values in `exp(-i omega t)` (the transfer matrix computes in `exp(+i omega t - i beta z)` and converts once): transfer-matrix characteristic function, bound absorbing modes continued from the lossless `slab` roots, substrate-leaky modes on the outgoing sheet, field profiles | lossless limit equals `slab`, normalized residual ≤ 1e-12, first-order perturbation theory (TE confinement factor, TM vector formula) to O(n''^2), interface and layer equations by finite differences, exp(-2 k0 gamma gap) tunnelling rate, path-independent continuation |
| `refsol.fiber` | step-index fiber: scalar LP modes (Gloge), exact vector modes TE/TM/HE/EH, and exact vector group index by implicit differentiation (`vector_group_index`, indices frozen at the wavelength) and exact vector mode fields (`vector_mode_field`, public values in `exp(-i omega t)`: computed in galerkin's kernel frame and converted once); keyword-only SI registry names (`radius` the core radius, `refractive_index` the pair (core, cladding), `vacuum_wavelength`, `points` (Q,2)), lossless | LP count vs Bessel cutoffs, LP11 cutoff at 2.4048, HE11 ≈ LP01 in weak guidance, LP11 group degeneracy, Rudolph–Neumann approximation; group index vs Richardson-extrapolated refined roots (with material dispersion through the tests' internal form), residual partials vs central differences; field continuity singular at the root, interface conditions (E_phi, E_z, n^2 E_r), `div E = 0` with `+i beta E_z` |
| `refsol.metallic` | rectangular waveguide cutoffs (`rect_waveguide_cutoffs(*, box_size, n_max=5, include_tm=False)`, the cross-section (a, b) in m, since L3 commit 11e), rectangular cavity resonances, coaxial potential and field (`coax_potential(points, *, position, prescribed_electric_potential)`, SI registry names since L3 commit 10) | closed forms |
| `refsol.electrostatics` | coaxial-line capacitance `2 pi eps0 eps_r / ln(b/a)` and two-layer parallel-plate series capacitance per metre of depth (`capacitance_per_depth`), real or complex `relative_permittivity` (`exp(-i omega t)`, loss `Im >= 0`); keyword-only SI registry names (`position` for the radii, `thickness` and `relative_permittivity` per layer, `length`); re-exports the coaxial potential | closed forms; the plate case is exact in P1 |
| `refsol.cavity` | every vacuum PEC box mode up to a frequency ceiling, with polarization and geometric degeneracy, SI | independent Cartesian enumeration, no solver or mesh |
| `refsol.material_cavity` | complex resonances and Q of a PEC box uniformly filled or loaded by a lossy dielectric/magnetic slab (TE/TM-to-z transcendental roots), `exp(+j*omega*t)` | vacuum limit equals the Cartesian spectrum, identical layers equal uniform rescaling, small-loss Q equals the energy filling factor |
| `refsol.wall_loss` | first-order conductor-loss Q of rectangular cavity modes per wall, split degenerate polarizations, uniform filling | Pozar TE101, numerical quadrature of a finite-difference curl, per-wall additivity, sqrt(sigma) scaling |
| `refsol.scattering` | plane wave on a circular cylinder: PEC (TM/TE) and dielectric, partial-wave series; scattering width (m); `exp(-i omega t)` as written (nothing converted); keyword-only SI registry names after `points` (`vacuum_angular_wavenumber`, `radius` the cylinder radius, `refractive_index`, `kind`, `terms`) | boundary conditions satisfied to 1e-9, interface continuity, geometric-optics limit; outgoing `exp(+i k r)` and absorption `>= 0` for `Im n >= 0` |
| `refsol.bimetal` | Timoshenko (1925) bimetal thermostat: curvature from force/moment balance, the published closed forms (Timoshenko, Villarceau, uniaxial Stoney limit) and the exact plane-stress strip field with its end traction | Three closed forms agree on random data, Stoney limit, section force/moment zero, interface continuity, finite-difference strains |
| `refsol.thermal_convection` | NAFEMS T4 rectangle (hot edge, insulated edge, two convecting edges): separation-of-variables series and the published target 18.3 °C with its provenance, read in SI (K) through `nafems_t4()` and `nafems_t4_target()` | Eigenvalue equation, Laplace and Fourier by finite differences, Robin/insulated/hot-edge conditions, geometric convergence, linearity |
| `refsol.joule_slab` | steady 1D Joule heating with `sigma = sigma0 (1 + alpha (T - T0))` between fixed potentials and temperatures: closed form in erf/erfi (`voltage_driven`), the constant-conductivity limit, current-driven states on both sides of the metal-like fold (`current_driven`, `fold_current`), temperature range for bounded conductivity models | integrated conservation laws (`J = -sigma V'`, `k (T'(0) - T'(x)) = J (V_a - V(x))`), quadrature of the module's own derivatives, finite differences, O(alpha) approach to the constant-sigma closed form, symmetry and reflection, power balance, one-parameter symmetric equation |
| `refsol.bent_slab` | constant-radius bent slab poles by complex-order Bessel/Hankel matching (inner `J`, film `J`/`Y`, outgoing `H^(2)`), `n_eff` referred to the inner radius, public values in `exp(-i omega t)` (matched in `exp(+i omega t)`, converted once); needs the optional `mpmath` at call time | residual ≤ 1e-12, straight-slab limit at first order in 1/R (Richardson), super-exponentially vanishing loss at large radius, loss growing as the radius shrinks, TE better confined than TM, ImportError without mpmath |
| `refsol.thermal3d` | Steady 3D heat: sine-product manufactured field on a box (temperature, flux, source) and series conduction through a layered slab along z | Flux and source against finite differences, slab against the series-resistance formula, NumPy only |
| `refsol.benchmarks` | Hadley (2002) rib-waveguide n_eff table (±3e-6) and dielectric-corner cases (±1e-8), fully specified geometry; stored as published in a private module, read in SI through `rib_waveguides()`, `rib_neff(*, thickness)` and `dielectric_corners()` | — |

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

field = affine([[0., 0.], [1., 1.]],
               displacement_gradient=[[1e-3, 0.], [0., -0.3e-3]], displacement=(0., 0.),
               youngs_modulus=70e9, poisson_ratio=0.3, plane="stress")
print(field.displacement)  # metres
print(field.stress)        # [70e6, 0, 0] Pa at each point (up to roundoff)
```

The reference module is included in both the sdist and wheel. It imports no FEM
engine. The separate [engine contract](../galerkin/elasticity2d.md)
describes boundary constraints, per-thickness loads and locking limitations.

```python
from refsol import fiber, slab, lossy_slab, scattering, benchmarks

# exact HE11 effective index of a step-index fiber: core radius 4 um, indices (core, cladding), lengths in m
n_eff = fiber.fundamental_neff(radius=4e-6, refractive_index=(1.45, 1.44), vacuum_wavelength=1.55e-6)

# all guided TE modes of a 220 nm SOI slab: layers (substrate, film, cover), lengths in m
slab.modes(refractive_index=(1.444, 3.48, 1.444), thickness=0.22e-6, vacuum_wavelength=1.55e-6, pol="TE")

# complex TE0 of the same slab with an absorbing film n = 3.48 + 0.01i (exp(-i omega t): Im n_eff > 0)
lossy_slab.three_layer_modes(refractive_index=(1.444, 3.48 + 0.01j, 1.444), thickness=0.22e-6,
                             vacuum_wavelength=1.55e-6, pol="TE")[0]

# substrate-leaky TE0: 0.22 um film over a 0.25 um low-index gap on silicon, outgoing sheet;
# layers (cover, film, gap material, substrate), thickness the pair (film, gap)
lossy_slab.substrate_leaky_mode(refractive_index=(1.444, 3.48, 1.444, 3.48), thickness=(0.22e-6, 0.25e-6),
                                vacuum_wavelength=1.55e-6)

# scattered field of a PEC cylinder of radius 1 um at k0 = 3.14 rad/um, at points (Q, 2) in m
u_s = scattering.scattered(points, vacuum_angular_wavenumber=3.14e6, radius=1e-6, kind="pec_tm")

# published reference: quasi-TE n_eff of the Hadley rib waveguide, slab thickness 0.3 um
benchmarks.rib_neff(thickness=0.3e-6)   # 3.412492
```

`refsol.lossy_slab` solves the planar multilayer stack with complex permittivity.
Its public values follow `exp(-i omega t)` (galerkin step, L3 commit 11c): a
passive material has `Im eps >= 0` (index `n' + i n''`) and an attenuated mode
`Im n_eff > 0`. The transfer matrix computes in the `exp(+i omega t - i beta z)`
convention of the galerkin mode kernels, unchanged; each function converts its
complex inputs once with `refsol._conventions.to_kernel` and returns the
conjugate of the result (`to_public`), so the sheet rules below are stated in that
internal convention and read with the opposite sign of `Im` on the public side.
The functions take keyword-only SI registry names: `relative_permittivity` (one
per layer), `thickness` (one per interior layer, m), `vacuum_wavelength` (m),
`effective_index`, `target_effective_index`, `refractive_index` (the layers of
`three_layer_modes` and `substrate_leaky_mode`), `mode_count`, `mode_index`,
`subdivision_count`, `relative_tolerance` and `iteration_limit`; the lengths only
enter through `k0 d`, so any consistent scale gives the same index. `characteristic` is the analytic transfer-matrix function whose
zeros are the modes; `solve` refines a guess (scipy root on real and imaginary
parts, then complex Newton) and rejects a result whose normalized residual
exceeds `1e-12`; `continued_root` follows a root along a path of structures.
`three_layer_modes` starts every mode of an absorbing slab from the lossless
`slab` root on the decaying sheet (`Im Q <= 0`, exterior fields decay);
`substrate_leaky_mode` starts from the bound mode of the isolated slab and
shrinks the gap to a high-index substrate on the outgoing sheet (`Re Q >= 0`;
the leaky mode has `Im Q_sub > 0`, a transversally growing improper substrate
field, the pole a complex-coordinate PML solver converges to). `field` returns
`E_y` (TE) or `H_y` (TM). The self-checks compare the lossless limit with `slab`,
the small-loss limit with first-order perturbation theory (relative error of
`Im n_eff` 2.6e-8 at `n'' = 1e-3` falling 100-fold at `1e-4`), the fields with
the interface and layer equations and the leakage rate with the tunnelling law
`exp(-2 k0 gamma gap)`. `tests/galerkin/test_lossy_slab_modes.py` grades
galerkin's scalar and vector solvers against these roots in a closed strip
(absorbing film) and with the complex-coordinate PML (leaky slab): the complex
error falls at second order (orders 1.97-2.00 on the finest pair) to
3.9e-4 to 6.8e-4 at a 0.01 um step, where `Im n_eff` agrees to 3e-4 (TE) and
4e-3 (TM) relative.

`refsol.thermal_boundary` provides independent closed forms for a prescribed
inward heat flux and Robin boundaries. Coordinates are m, temperature K,
conductivity W/(m K), inward heat flux W/m^2 (positive enters the body) and
convection h W/(m^2 K).

Since the galerkin step (L2 commit 6) the heat references (`refsol.thermal`,
`thermal3d`, `thermal_boundary`, `thermal_convection`, `thermal_multilayer`,
`transient_heat`, `transient_heat_multilayer`, `transient_heat_robin`) take
keyword-only SI arguments under registry names (after a leading `points`), with
no dimensional defaults: `thermal_conductivity`, `prescribed_temperature` (a pair
for the two ends), `heat_source_density`, `inward_heat_flux`, `position` (the
layer boundaries, first face included), `time`, `initial_temperature` and
`temperature_difference`; their fields carry the same names. A text value
raises `TypeError`. The NAFEMS T4 data, published in °C, are kept as published
in a private module and converted to kelvin when read.

Since L2 commit 8 the mechanics references (`refsol.elasticity`,
`elasticity_traction`, `elasticity_multilayer`, `thermoelasticity`,
`thermoelastic_traction`, `bimetal`) do the same after their leading `points`
(and `normals` for a traction): `youngs_modulus`, `poisson_ratio`, `plane`,
`linear_expansion_coefficient`, `stress_free_temperature`, `temperature`,
`temperature_change`, `temperature_gradient`, `displacement`,
`displacement_gradient`, `strain`, `stress`, `stress_xx`, `stress_xy`,
`strain_xx`, `gauge_pressure` (the inner/outer pair), `position` (the layer
boundaries, first face or inner radius included), `thickness` (one per layer),
`length`. Former defaults are written out by the caller, and the fields carry
the registry names (`stress_zz`, `strain_zz`, `strain_energy_density`,
`body_force_density`, `displacement_gradient`, `strain_yy`, ...).

`refsol.transient_heat` provides `uniform_insulated`, `moving_affine`,
`sine_manufactured`, small dense `p1_matrices`, `smallest_dirichlet_mode` and
`backward_euler_amplitude`. Coordinates/time/temperature are m/s/K,
conductivity W/(m K), volumetric heat capacity J/(m³ K), source W/m³ and flux
W/m². The dense matrices and modes target small reference meshes; a
semidiscrete backward-Euler product is distinct from a continuum PDE solution.
These references do not certify physical temperature validity or a maximum
principle. The transient engine is documented in the galerkin
[transient heat contract](../galerkin/transient_heat.md).

`refsol.thermoelastic_traction` provides `uniform_combined`,
`polynomial_manufactured`, `parent_state` and `traction_from_stress` from the
original 3D constitutive law. Coordinates/displacement are m, temperature K,
stress/total traction Pa, body force N/m^3, force/reaction N/m and physical
energy J/m. It supplies prescribed-temperature mechanical references, not a heat
solve or source authentication.

`refsol.bent_slab` (optional, `python -m pip install mpmath`) solves the
constant-radius bent slab: a film `R <= r <= R + d` between cladding regions,
matched with Bessel and Hankel functions of complex order `nu = k0 R n_eff`
(`J` inside, `J`/`Y` in the film, outgoing `H^(2)` outside under
`exp(+i omega t)`), so `n_eff` is referred to the inner radius `R` as in the
galerkin bend solver. `mode` starts a secant iteration from the straight
`slab` root and accepts a pole only when its normalized `residual` is at most
`1e-12`; `mpmath` is imported when a function is called and a missing package
raises `ImportError` naming it, so `import refsol` and the rest of the package
work without it. It takes `refractive_index` (the regions `(cladding, film,
cladding)` by increasing radius), `thickness`, `bend_radius`, `vacuum_wavelength`,
`effective_index`, `target_effective_index`, `mode_index` and `relative_tolerance`,
and its public values follow `exp(-i omega t)` (L3 commit 11c): the matching above
runs in `exp(+i omega t)` and the result is conjugated once. The self-checks skip without `mpmath` and verify the residual,
`Im n_eff > 0`, the straight-slab limit at first order in `1/R` (the
Richardson-extrapolated R = 40/80 um values recover the straight root to
5.8e-6 against a 3.9e-3 shift), the super-exponential vanishing of the loss at
large radius and its growth as the radius shrinks. The poles coincide with the
independent oracle of `tests/galerkin/test_pml_modes.py`, which grades the
galerkin bend solver against the same equation.

`refsol.joule_slab` solves the coupled steady equations `(sigma(T) V')' = 0`,
`k T'' + sigma(T) V'^2 = 0` on a slab `0 <= x <= L` with fixed face potentials and
temperatures and the linear isotropic model `sigma = sigma0 (1 + alpha (T - T0))`,
the form a galerkin `ConductivityModel` callback evaluates. Units are SI (m, K,
V, S/m, W/(m K), A/m^2). The functions take keyword-only registry names: `length`,
the face pairs `prescribed_electric_potential` and `prescribed_temperature`,
`reference_conductivity` (sigma0), `conductivity_temperature_coefficient` (alpha),
`reference_temperature` (T0), `thermal_conductivity`, and for `current_driven`
`current_density` and `prescribed_electric_potential` (V(0), required); a `str`
raises `TypeError`. `alpha > 0` is a conductivity rising with temperature,
`alpha < 0` metal-like, `alpha = 0` the parabolic constant-conductivity closed
form. With `u = sigma/sigma0` the heat equation is `u'' = -c/u`,
`c = alpha J^2/(k sigma0)`, whose first integral gives `u` and `x` in closed
form through `erf` (`alpha > 0`) or `erfi` (`alpha < 0`) of the scaled slope; the
voltage drop fixes both face slopes independently of `J`, so `voltage_driven`
is explicit, evaluated with `erfcx`/`dawsn` so that nearly linear solutions do
not overflow. `current_driven` finds the drop carrying a prescribed `J`; for
`alpha < 0` the current-voltage curve folds at `fold_current` and both branches
are available. Each `JouleSlab` carries its inputs under the same names, evaluates
`temperature`, `temperature_gradient`, `heat_flux`, `electric_potential`,
`electric_field`, `electrical_conductivity` and `joule_power_density` at the x
coordinates `points`, and holds `current_density`, the private `_joule_power` (per
face area, `J (V_a - V_b) = k (T'(0) - T'(L))`; no registry name, rule R(2)) and
`temperature_range`, the interval a bounded model must cover. `tests/galerkin/test_joule_slab_reference.py` grades
`solve_temperature_joule_heat` on a 1 m x 0.25 m rectangle (Picard, relaxation
1): the RMS temperature error over the three-point triangle rule falls at second
order (orders 2.00-2.02) to 3.5e-4 and 4.1e-4 K (`alpha = 0.5` /K, 2 V,
symmetric and 300/304 K faces) and 2.1e-3 and 2.0e-3 K (`alpha = -0.004` /K,
5 V) at 32 cells, with the dissipated power within 1.9e-4 relative; the
`alpha = 0` run matches the constant-conductivity closed form.

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
- Lengths in metres under SI registry names (galerkin step); the waveguide and scattering references depend only on k0 times a length, so a problem written in another consistent scale gives the same indices and fields.
- Effective index `n_eff = beta / k0`.
- `refsol.lossy_slab` and `refsol.bent_slab` follow `exp(-i omega t)` like galerkin's public mode functions (galerkin step, L3 commit 11c): passive `Im eps >= 0`, attenuated or radiating `Im n_eff > 0`. Their formulas are written in `exp(+i omega t)` and convert once in `refsol._conventions`; a galerkin test that compares them with a mode kernel (exp(+i omega t)) conjugates once at the comparison.
- `refsol.fiber.vector_mode_field` follows `exp(-i omega t)` (galerkin step, L3 commit 11d): a forward mode varies as `exp(i (beta z - omega t))`, so `dEx/dx + dEy/dy + i beta E_z = 0`. The field is computed in galerkin's kernel frame `exp(+i omega t - i beta z)` and converted once in `refsol._conventions`; a test that compares it with a mode kernel conjugates once at the comparison. The fiber's other values are real.
- `refsol.material_cavity` uses `exp(+i omega t)` like the galerkin cavity kernels: passive `Im eps <= 0`, decaying resonance `Im omega > 0`. Conjugate to convert.
- `refsol.electrostatics` follows `exp(-i omega t)` like galerkin's public electrostatics (galerkin step, L3 commit 10): passive `Im eps_r >= 0` gives `Im C >= 0`. Its closed forms are the same formula in either convention, so nothing is converted.

## References

- D. Gloge, "Weakly guiding fibers," Appl. Opt. 10, 2252 (1971).
- A. W. Snyder and J. D. Love, *Optical Waveguide Theory* (Chapman & Hall, 1983).
- K. Okamoto, *Fundamentals of Optical Waveguides*, 2nd ed. (Academic Press, 2006).
- G. R. Hadley, "High-accuracy finite-difference equations for dielectric waveguide
  analysis II: dielectric corners," J. Lightwave Technol. 20, 1210 (2002).
- D. Marcuse, *Theory of Dielectric Optical Waveguides* (Academic Press, 1974).
- J. Hu and C. R. Menyuk, "Understanding leaky modes: slab waveguide revisited,"
  Adv. Opt. Photon. 1, 58 (2009).
- W. C. Chew, *Waves and Fields in Inhomogeneous Media* (IEEE Press, 1995).
- D. Marcuse, "Curvature loss formula for optical fibers," J. Opt. Soc. Am. 66, 216 (1976).
- K. R. Hiremath, M. Hammer, R. Stoffer, L. Prkna and J. Čtyroký, "Analytic approach to
  dielectric optical bent slab waveguides," Opt. Quantum Electron. 37, 37 (2005).
- H. S. Carslaw and J. C. Jaeger, *Conduction of Heat in Solids*, 2nd ed. (Oxford, 1959).
- A. C. Fowler, I. Frigaard and S. D. Howison, "Temperature surges in current-limiting
  circuit devices," SIAM J. Appl. Math. 52, 998 (1992).
- Benchmark values are Hadley's published results, cross-checked against the same
  table in the femwell project's benchmark documentation (GPL-3.0). Only the
  numerical values are reproduced; see NOTICE.

## License

Apache License 2.0 - see [LICENSE](../../../packages/galerkin-refsol/LICENSE) and [NOTICE](../../../packages/galerkin-refsol/NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

The benchmark values that `refsol.benchmarks` reads are numerical results published by
Hadley (2002), and the NAFEMS T4 target in `refsol.thermal_convection` is a published
benchmark number; see [NOTICE](../../../packages/galerkin-refsol/NOTICE) for their provenance.
