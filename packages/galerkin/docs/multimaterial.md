# Piecewise-constant materials on named regions

**English** | [한국어](locales/ko/pages/multimaterial.md)

Steady and transient heat conduction, static elasticity, the
prescribed-temperature mechanical stage and the steady and transient
heat-to-mechanics workflows can assign a different material to each named region of a 2D mesh. This page holds the shared input rule, each
contract and its independent validation. Further physics will be added here as it is
validated; until then their pages state that only one homogeneous material is
accepted.

## Input rule

Each material property argument accepts exactly one of:

| Form | Meaning |
| --- | --- |
| finite real scalar | One homogeneous material (the original contract, unchanged) |
| `{region name: scalar}` | One value per region; keys must equal `mesh.region_names` exactly |

```python
from galerkin.mesh import layered_rectangle_mesh
from galerkin.thermal import solve_steady_heat

mesh = layered_rectangle_mesh([0.02, 0.05], 0.02, [4, 6], 4, ["steel", "foam"])
dirichlet = {int(i): 400.0 for i in mesh.boundary["left"]}
dirichlet.update({int(i): 300.0 for i in mesh.boundary["right"]})
result = solve_steady_heat(
    mesh,
    conductivity={"steel": 45.0, "foam": 0.04},   # W/(m K)
    heat_source={"steel": 2e5, "foam": 0.0},      # W/m^3
    dirichlet=dirichlet,
)
```

- Region names come from `Mesh.region_names`: `disk_mesh`,
  `layered_rectangle_mesh`, `layered_annulus_mesh`, or gmsh physical groups
  read through gmshio. `mesh.regions` holds one region id per triangle.
- A missing name, an unknown name, a non-string key, or a value that fails the
  property's own check (for example k <= 0) raises `ValueError` naming the
  region. A mapping on a mesh without region data is rejected.
- Bare per-triangle arrays are **not** accepted by the physics APIs. A
  length-M sequence is ambiguous with vector or tensor input, and the original
  contract rejects such sequences. Low-level assembly routines
  (`assemble_stiffness`, the electromagnetic mode solvers' `eps_r`) keep their
  per-triangle array input.
- Units are those of the scalar argument. A mapping never converts units.
- A scalar input follows the original code path, so homogeneous results are
  unchanged bit for bit. A mapping with the same value in every region gives
  the same arrays as the scalar (heat: identical; elasticity: to 1e-12
  relative, because the per-triangle constitutive contraction sums in a
  different order).

Material properties are constant within each triangle. Interfaces must lie on
element edges (meshes that follow region boundaries, as all generators above
do); a region that cuts through triangles is not representable.

## Steady heat conduction

`galerkin.thermal.solve_steady_heat` accepts per-region `conductivity` k > 0
in W/(m K) and per-region constant `heat_source` Q in W/m^3. Scalars and the
existing coordinate callback for Q are unchanged. The weak form is the same
with k and Q constant on each triangle:

```text
K_ij = sum_e k_e integral_e grad(N_i).grad(N_j) dA,   f_i = sum_e Q_e integral_e N_i dA
heat_flux_e = -k_e grad(T_h) on triangle e
```

Temperature is continuous (P1). The exact normal heat flux is continuous across
an interface while the gradient jumps by the conductivity ratio; the
element-constant P1 flux satisfies this only in the limit, with an O(h)
jump. Perfect thermal contact is assumed: no contact resistance and no
interface heat source. Boundary conditions, reactions and balance checks are
those of [thermal_steady2d](thermal_steady2d.md) and
[thermal_flux_robin](thermal_flux_robin.md).

## Independent references

`refsol.thermal_multilayer` evaluates two closed forms and imports only NumPy:

- `layered_slab`: series wall 0 < x_1 < ... < x_n = L with k_i and uniform
  Q_i per layer, T(0)=T_L, T(L)=T_R. The flux is q(x) = q_0 + integral of Q,
  T' = -q/k, and q_0 follows from T(L); without sources this is the series
  thermal resistance q_0 = (T_L-T_R)/sum(L_i/k_i).
- `composite_cylinder`: concentric shells r_0 < ... < r_n with k_i and Q_i,
  T(r_0)=T_i, T(r_n)=T_o. r q_r = C + integral of Q r dr and
  T = A_i - (C + offset_i) ln(r)/k_i - Q_i r^2/(4 k_i) in each shell.

The reference tests check, by finite differences only, Fourier's law and
energy balance in every layer, temperature and flux continuity at every
interface, boundary values, the series/log resistance formulas without source,
radial direction of the flux, and the single-layer textbook formulas. An
optional `layer=` index evaluates a layer's closed form as its analytic
continuation, so points of a polygonal mesh triangle just beyond a curved
interface are compared with their own triangle's material.

## Acceptance (fixed before the comparison)

`packages/galerkin/tests/test_thermal_multimaterial.py`:

| Case | Mesh | Gate |
| --- | --- | --- |
| Uniform mapping vs scalar | 2-region rectangle | Every result array identical |
| Three-layer wall, no source (k 15/0.8/45) | layered rectangle | Nodal T error <= 1e-10 of 420 K; flux equal in all layers; side reactions = exact q·height to 1e-10 |
| Three-layer wall with sources Q 2e5/-3e4/6e5 | layered rectangle, n=1,2,4,8 | T L2 order >= 1.8 and flux L2 order >= 0.9 on the last two intervals; variational interface heat rate from each side within 1e-9 of the exact rate |
| Three-shell cylinder, k 50/0.25/16, Q 1e6/0/-2e5 | layered annulus, n=1,2,4,8 | T L2 order >= 1.8, flux L2 order >= 0.9, interface heat rate order >= 1.8, mean normal-flux jump order >= 0.9 (last two intervals) |
| Invalid regions | — | Missing/unknown/nonpositive/nonfinite/complex/boolean/sequence values, integer keys, bare arrays, no region data and out-of-range region ids raise `ValueError` |

Errors use an independent 8x8 Duffy quadrature in every triangle. The
variational interface heat rate is the residual of one side's own stiffness
and load summed over the interface nodes.

Observed when the gates were first run (Linux, Python 3.12):

| Quantity | n=1 → 2 → 4 → 8 | Orders |
| --- | --- | --- |
| Wall T L2 (K m) | 8.77e-3, 2.24e-3, 5.63e-4, 1.41e-4 | 1.97, 1.99, 2.00 |
| Wall flux L2 (W/m) | 26.1, 13.4, 6.76, 3.39 | 0.96, 0.99, 1.00 |
| Wall interface rate (relative) | 2.5e-13, 2.6e-13, 2.0e-13, 1.5e-13 | roundoff |
| Cylinder T L2 (K m) | 5.40e-2, 1.35e-2, 3.39e-3, 8.47e-4 | 2.00, 2.00, 2.00 |
| Cylinder flux L2 (W/m) | 19.0, 9.41, 4.70, 2.35 | 1.01, 1.00, 1.00 |
| Cylinder interface rate (relative) | 8.5e-3, 2.1e-3, 5.3e-4, 1.3e-4 | 2.00, 2.00, 2.00 |
| Cylinder normal-flux jump (relative) | 0.186, 0.092, 0.046, 0.023 | 1.01, 1.00, 1.00 |

The wall data are independent of y, so P1 nodal values and the variational
interface rate are exact there; the cylinder's interface rate converges at
second order through the inscribed polygon. Run them with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s \
  packages/galerkin/tests/test_thermal_multimaterial.py \
  packages/galerkin-refsol/tests/test_thermal_multilayer_reference.py
```

## Static elasticity

`galerkin.elasticity.solve_elasticity` accepts `young_modulus` (Pa) and
`poisson_ratio` each as a scalar or a region mapping; one may be a scalar and
the other a mapping. Each region must satisfy E > 0 and -1 < nu < 0.5, and
`plane` ('stress' or 'strain') applies to every region. The element matrix is
`K_e = A_e B_e^T D_e B_e` with the region's own `D_e`, and the reported stress
is `D_e` times the element strain. Body force, traction, Dirichlet data,
reactions and residual checks are unchanged
([elasticity2d](elasticity2d.md), [elasticity_traction](elasticity_traction.md)).
Perfect bonding is assumed: displacement is continuous, and the traction
`sigma.n` across an interface is continuous only in the limit (O(h) jump of the
element-constant P1 stress). Interface stress singularities at free edges of
dissimilar materials are physical and are not resolved by this element.

`refsol.elasticity_multilayer` (NumPy only) gives three exact states:

- `laminate_axial`: layers stacked across the load, uniform axial strain,
  free faces. Displacement is continuous and piecewise linear, sigma_xx = E' eps
  per layer (E' = E in plane stress, E/(1-nu^2) in plane strain).
- `series_bar`: layers in series under uniform sigma_xx. This is exact only
  when every layer has the same lateral strain (plane stress nu/E equal; plane
  strain nu(1+nu)/E equal); other data are rejected because the true solution
  then has interface singularities.
- `composite_cylinder`: concentric shells under inner and outer pressure,
  u_r = A_i r + B_i/r per shell, with displacement and radial stress
  continuous; the 2n coefficients come from a small dense linear system.

Their tests check the isotropic law by central differences of the displacement,
Cartesian equilibrium by central differences of the stress, continuity of
displacement and radial traction at interfaces, traction-free and pressure
boundaries, the Voigt resultant, and the single-shell textbook Lamé formulas.

| Case | Mesh | Gate |
| --- | --- | --- |
| Uniform mapping (both, or E only) vs scalar | 2-region rectangle | Displacement, strain, stress, reaction within 1e-12 relative |
| Laminate, E 70/3/200 GPa, nu .33/.4/.29, both planes | layered rectangle | Nodal displacement <= 1e-10 of eps·H; stress <= 1e-9; top reaction = Voigt resultant to 1e-10 |
| Series bar with matched lateral strain, both planes | layered rectangle | Displacement <= 1e-9 relative; stress = (s,0,0) to 1e-8 |
| Composite cylinder E 200/3/70 GPa, nu .3/.38/.33, p_i 40 MPa, p_o 5 MPa, both planes | layered annulus, n=1,2,4,8 | Displacement L2 order >= 1.8, stress L2 order >= 0.9, mean radial-traction jump order >= 0.9 (last two intervals); symmetry-point reactions <= 1e-8 of the inner load |
| Invalid regions | — | Missing/unknown names, E <= 0, nu outside (-1, 0.5), nonfinite/complex values, bare arrays, invalid plane, mapping without region data raise `ValueError` |

Observed when first run (n=1 → 8):

| Quantity | Plane stress | Plane strain |
| --- | --- | --- |
| Displacement L2 (m^2) | 4.17e-8 → 7.06e-10, orders 1.91, 1.98, 1.99 | 5.33e-8 → 9.35e-10, orders 1.87, 1.97, 1.99 |
| Stress L2 (Pa m) | 5.54e5 → 7.28e4, orders 0.95, 0.99, 1.00 | 6.62e5 → 8.90e4, orders 0.92, 0.98, 0.99 |
| Radial-traction jump (relative) | 1.47 → 0.187, orders 0.97, 1.00, 1.00 | 1.67 → 0.215, orders 0.95, 1.00, 1.00 |
| Symmetry reactions (relative) | <= 1.9e-14 | <= 7.2e-15 |

The soft epoxy shell (E 3 GPa) between steel and aluminium makes the
element-constant traction jump large on coarse meshes; it halves with each
refinement.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s \
  packages/galerkin/tests/test_elasticity_multimaterial.py \
  packages/galerkin-refsol/tests/test_elasticity_multilayer_reference.py
```

## Thermoelasticity and heat-to-mechanics coupling

`galerkin.thermoelasticity.solve_thermoelasticity` accepts
`thermal_expansion_per_k` (1/K), `young_modulus` and `poisson_ratio` each as a
scalar or region mapping. With any mapping, triangle e uses its own
`D_e` and thermal stress coefficient (E/(1-nu) in plane stress, E/(1-2nu) in
plane strain), and the thermal strain at the element nodes is
`alpha_e (T - T_ref)`. Thermal load, centroid fields, `sigma_zz`/`epsilon_zz` and
the reduced physical energy use the same per-triangle values. The result echoes
each material as a float or a `{region name: float}` copy. The all-scalar call
keeps the original code path.

`galerkin.thermal_mechanical.solve_steady_thermoelasticity` accepts mappings for
`conductivity`, `young_modulus`, `poisson_ratio`, `thermal_expansion_per_k` and
a constant `heat_source`; they are validated at the `input` stage and passed to
the heat and mechanical stages. The manifest records materials as sorted
dictionaries and a per-region source as `{'kind': 'per_region', 'value': ...}`;
scalar manifests are unchanged. `galerkin.transient_thermal_mechanical` accepts
the same mechanical mappings (per-region transient heat is a separate step).

**Reference.** `refsol.elasticity_multilayer.composite_cylinder` with
`thermal_expansions` and `temperature_change` rows (a_i, b_i), dT = a_i +
b_i ln(r/r_0): in each shell u_r = kappa_i I(r)/r + A_i r + B_i/r with
I = integral of s dT ds and kappa_i = beta_i/(lambda_i+2 mu_i)
(beta = (3 lambda + 2 mu) alpha in plane strain, E alpha/(1-nu) in plane stress).
Its tests reproduce the Timoshenko-Goodier thick-cylinder thermal stresses
(evaluated by independent Gauss quadrature of the temperature integrals),
stress-free uniform heating of one material, and equilibrium/continuity by
finite differences. Steady conduction without a source gives exactly
dT = a_i + b_i ln(r/r_0) in each shell, so the coupled problem has an exact
solution built from the two references.

The bimetal strip (Timoshenko 1925) is a beam-theory approximation that
ignores free-end stress concentrations; it is not used as an acceptance
reference.

| Case | Mesh | Gate |
| --- | --- | --- |
| Uniform alpha mapping (with scalar or mapped E, nu) vs scalar | 2-region rectangle, nonuniform T, traction | All fields within 1e-12 relative, energy too |
| Expansion mismatch: alpha 12/70/23 x1e-6 1/K, E 200/3/70 GPa, nu .3/.38/.33, uniform +120 K, free surfaces, both planes | layered annulus, n=1,2,4,8 | Displacement L2 order >= 1.8, stress L2 order >= 0.9, plane-strain sigma_zz order >= 0.9 (last two intervals); symmetry reactions <= 1e-9 |
| Coupled steady heat -> mechanics: k 45/0.25/200 W/(m K), 420 K inside, 300 K outside, same mechanics, both planes | layered annulus, n=1,2,4,8 | Temperature L2 order >= 1.8; displacement >= 1.8; stress >= 0.9; plane-strain sigma_zz >= 0.9 |
| Transient steps with mappings | 2-region rectangle | Each step equals a direct per-region mechanical solve exactly |
| Invalid regions | — | Missing/unknown names, nonfinite alpha, E <= 0, nu = 0.5, invalid plane raise `ValueError`; the workflow raises `WorkflowStageError` at stage `input` |

Observed when first run (n=1 → 8):

| Quantity | Plane stress orders | Plane strain orders |
| --- | --- | --- |
| Mismatch displacement L2 | 1.94, 1.98, 2.00 | 1.89, 1.97, 1.99 |
| Mismatch stress L2 | 0.98, 0.99, 1.00 | 0.96, 0.99, 1.00 |
| Mismatch sigma_zz L2 | — (zero) | 0.92, 0.98, 0.99 |
| Coupled temperature L2 | 2.00, 2.00, 2.00 | 2.00, 2.00, 2.00 |
| Coupled displacement L2 | 1.93, 1.98, 2.00 | 1.89, 1.97, 1.99 |
| Coupled stress L2 | 0.98, 0.99, 1.00 | 0.95, 0.99, 1.00 |
| Coupled sigma_zz L2 | — (zero) | 0.93, 0.98, 1.00 |

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s \
  packages/galerkin/tests/test_thermoelastic_multimaterial.py
```

## Transient heat conduction

`galerkin.transient_heat.solve_transient_heat` accepts `conductivity` (W/(m K)),
`volumetric_heat_capacity` (J/(m^3 K)) and a constant `heat_source` (W/m^3) as
scalars or region mappings; callbacks for Q are unchanged. The consistent mass
`M_e = c_e A_e/12 [[2,1,1],[1,2,1],[1,1,2]]` and the stiffness use each
triangle's values; backward Euler, offsets, refinement and every residual and
balance check are unchanged ([transient_heat](transient_heat.md)). The result
records `conductivity_w_mk` and `volumetric_heat_capacity_j_m3k` as a float or
a `{region name: float}` copy.

**Reference.** `refsol.transient_heat_multilayer.LayeredWall`: a layered wall
with fixed end temperatures, T = T_s(x) + sum A_m X_m(x) exp(-lambda_m t).
X_m solve -(k X')' = lambda c X with continuous X and k X'; the m-th
eigenvalue is found by bisection on the number of interior zeros of the
transfer-matrix solution, counted exactly from its Prüfer phase layer by layer
(Sturm oscillation), so no root is skipped however close two roots are.
Choosing the initial field as T_s + sum A_m X_m makes the finite series exact.
Its tests check the single-layer sine eigenvalues, the two-layer characteristic
equation, that mode m has exactly m interior zeros, agreement with an
independent fine 1D finite-element eigensolve (relative 1e-4; the test wall and
a foam/copper/foam sandwich, k 0.03/400/0.03, whose roots cluster), c-weighted
orthogonality, interface continuity, the PDE and Fourier's law by finite
differences, boundary values and the steady limit.

The first version bracketed roots on a fixed sqrt(lambda) grid; review found it
could skip two roots closer than the grid step (high-contrast sandwich walls).
The test wall was not affected, and its recorded results below are unchanged.

| Case | Mesh / time | Gate |
| --- | --- | --- |
| Uniform mappings (k, c, Q) vs scalars | 2-region rectangle | Every history array identical |
| BE step with independent dense per-region M and K | 2-layer rectangle, unequal steps | Free residual <= 1e-9, reactions and heat content match |
| Steel/insulation wall 10 + 20 mm, k 45/0.5, c 3.6e6/1.2e6, ends 400/300 K, three modes A = 60/-25/10 K | layered rectangle [n, 2n] x n, n=1,2,4,8; dt = 1/32 s to 120 s; observed at 10, 40, 120 s | At every observed time, T L2 order >= 1.8 and flux L2 order >= 0.9 on the last two intervals; at n=8 halving dt changes every error by <= 5% |
| Wall B: 15 + 15 mm, k 2/1, c 4e6/1e6, same ends and modes | layered rectangle [n, n] x n, n=1,2,4,8; same times and gates | Same gates as the steel/insulation wall |
| Wrong region property: each of k and c of each wall B layer doubled | wall B, n=4 and n=8 | See below |
| Invalid regions | — | Missing/unknown names, k or c <= 0, nonfinite Q, bare arrays, mapping without region data raise `ValueError`; a non-real region value gets the labelled region message |

The first run of the wall gate used [2n, 4n] divisions and dt = 1/8 s. Spatial
orders passed (T 1.84-2.61, flux 0.98-1.05) but the dt/2 companion changed the
finest temperature errors by 12%, 22% and 35%: time error was not separated
from space error, so that configuration failed. The retained configuration
(coarser mesh, dt four times smaller, chosen because the BE error scales with
dt) observed:

| Time | T L2 orders (n=1→8) | Flux L2 orders | dt/2 change (T, flux) |
| --- | --- | --- | --- |
| 10 s | 2.10, 1.84, 1.97 | 1.19, 0.99, 1.00 | 0.69%, 0.015% |
| 40 s | 2.15, 1.88, 1.99 | 1.08, 1.03, 1.01 | 1.06%, 0.020% |
| 120 s | 2.12, 1.95, 2.02 | 1.46, 1.05, 1.01 | 1.36%, 0.017% |

The steel layer of this wall has a conductance (k/d = 4500 W/(m^2 K)) 180 times
that of the insulation, so it stays close to the Dirichlet temperature. Review
found the gate insensitive to the steel properties; measured at n=4, doubling
steel k or c changes the temperature errors by at most 2.4%, while doubling
insulation k or c raises them 2.1x to 28x. Wall B (conductances 133 and
67 W/(m^2 K), heat capacities per area 6e4 and 1.5e4 J/(m^2 K)) closes that gap.
Its gates were fixed before the first run and passed:

| Time | T L2 orders (n=1→8) | Flux L2 orders | dt/2 change (T, flux) |
| --- | --- | --- | --- |
| 10 s | 2.16, 1.82, 1.96 | 1.16, 0.95, 0.99 | 0.29%, 0.004% |
| 40 s | 2.36, 1.85, 1.97 | 1.16, 0.99, 1.01 | 0.48%, 0.011% |
| 120 s | 2.31, 1.96, 2.00 | 1.20, 1.01, 1.00 | 0.56%, 0.004% |

Wrong-property check on wall B. Criterion 1, fixed before the first run: at n=4
the T error rises at least 5x at some observed time. It failed for the light
layer's c (2.75x): that layer holds a fifth of the wall's heat capacity, so
doubling it moves T by less than 5x the n=4 discretisation error. Criterion 2,
fixed after that failure and before its run: the wrong property breaks the
convergence gate on the last interval (T order below 1.8 at some observed time)
and raises the n=8 T error at least 5x. The test asserts criterion 2 for all four
cases and criterion 1 for the three that passed it.

| Doubled property | n=4 error ratio (max) | n=8 error ratio (max) | Lowest last-interval T order |
| --- | --- | --- | --- |
| k, dense layer | 6.15 | 23.0 | 0.10 |
| k, light layer | 22.7 | 88.0 | 0.04 |
| c, dense layer | 16.5 | 69.2 | -0.77 |
| c, light layer | 2.75 (criterion 1 failed) | 12.2 | -0.15 |

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s \
  packages/galerkin/tests/test_transient_heat_multimaterial.py \
  packages/galerkin-refsol/tests/test_transient_heat_multilayer_reference.py
```

## Reference-tool comparison

The analytical gates above decide acceptance. Separately, the same problems
were solved with scikit-fem 12.0.2 (BSD-3-Clause); agreement between the tools
is code-to-code evidence, not convergence evidence.

- In CI, `tests/test_crosscheck_skfem_multimaterial.py` solves a three-region
  wall on the same mesh with the same per-triangle values in both tools: steady
  heat, elasticity and thermoelasticity in both planes, and backward-Euler
  transient heat. Temperatures, displacements, fluxes and stresses agree to
  1.6e-12 or better, gated at 1e-9 ([reference comparisons](https://github.com/fieldalgo/openphysics/blob/main/docs/reference-comparisons.md)).
- A separate study (2026-10-19) repeated the steady, elasticity,
  thermoelasticity and steel/insulation-wall transient gate problems at all four
  refinement levels, on code from before wall B and the zero-count eigenvalue
  search were added; wall B and its wrong-property check have no reference-tool
  comparison yet. Same-mesh P1 fields agreed to 1.4e-12 (temperature,
  displacement) and 6.2e-11 (flux, stress). scikit-fem P2 against the same refsol
  references confirmed them: on the straight-sided annulus meshes P2 is limited
  to order about 2 by the polygonal geometry, and isoparametric P2 on the curved
  geometry reaches about 3. On a source-driven layered wall with dt = 1/4 s,
  scikit-fem P2 also lost its spatial order on the finest meshes and Richardson
  extrapolation in time restored it, so backward-Euler time error, not the
  spatial discretisation, dominated that configuration.

## Limits

- Piecewise constant per region only: no conductivity varying inside a region,
  no anisotropic tensors, no temperature-dependent properties.
- No contact resistance or interface sources.
- No mixed formulation: nearly incompressible regions lock in plane strain,
  as in the homogeneous solver.
- No temperature-dependent properties; reference temperature is one value.
- simcase steady and transient heat documents accept named material regions
  ([thermal_regions2d](https://github.com/fieldalgo/openphysics/blob/main/packages/simcase/docs/thermal_regions2d.md)); elasticity and thermoelasticity have no simcase
  document.
