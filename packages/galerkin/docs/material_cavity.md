# Material-loaded rectangular cavity solver

**English** | [한국어](locales/ko/pages/material_cavity.md)

```python
from galerkin import CavityMaterialRegion, solve_material_cavity_box

slab = CavityMaterialRegion(
    bounds_m=((0.0, 1.0), (0.0, 0.8), (0.0, 0.3)),
    relative_permittivity=4.0 - 0.04j,      # eps' (1 - j tan_delta), tan_delta = 0.01
)
result = solve_material_cavity_box(
    lengths_m=(1.0, 0.8, 0.6),
    subdivisions=(8, 8, 8),
    regions=[slab],
    num_modes=4,
    target_frequency_hz=150e6,
)
print(result.resonant_frequencies_hz, result.quality_factors)
```

This API extends the [vacuum PEC box solver](cavity_solver.md) with piecewise-constant,
possibly lossy, relative permittivity and permeability in axis-aligned box regions.
It returns complex resonant frequencies and quality factors. Walls are perfect
electric conductors unless a finite wall conductivity is given; then they use the
Leontovich surface-impedance condition (see [Finite-conductivity walls](#finite-conductivity-walls)).
Open boundaries, anisotropic or dispersive materials and arbitrary geometry are
not included. `solve_cavity_box` and its contract are unchanged.

## Conventions

Fields vary in time as **`exp(+j*omega*t)`**. A passive material has

    eps_r = eps' - j*eps'',  eps'' >= 0,    mu_r = mu' - j*mu'',  mu'' >= 0,

so a dielectric with loss tangent `tan_delta` is `eps' * (1 - 1j*tan_delta)`.
Inputs with negative real part or positive imaginary part (gain) are rejected.
A decaying resonance has `Im(omega) > 0`. The quality factor is

    Q = Re(omega) / (2 * Im(omega)) = Re(f) / (2 * Im(f)),

the ratio of the phase rate to the energy decay rate. It is infinite when every
material is lossless. For a cavity uniformly filled with `eps' (1 - j tan_delta)`
and real `mu_r`, `Q = (1 + sqrt(1 + tan_delta**2)) / (2 tan_delta)`, about `1/tan_delta`.

The weak form of `curl(mu_r^-1 curl E) = k0^2 eps_r E` with PEC walls gives the
complex-symmetric (non-Hermitian) generalized problem

    S(1/mu_r) q = k0^2 M(eps_r) q,

with `k0^2` complex. `frequencies_hz = c0 * sqrt(k0^2) / (2*pi)` uses the principal
square root, so `Re f > 0`.

## Arguments

`solve_material_cavity_box(lengths_m, subdivisions, *, regions=(), num_modes=6,
target_frequency_hz, wall_conductivity_s_per_m=None)` returns a `MaterialCavityResult`. `lengths_m`, `subdivisions`,
`num_modes` and `target_frequency_hz` have the vacuum solver's meaning and validation,
and the mesh is the same alternating Kuhn mesh.

`regions` is a sequence of `CavityMaterialRegion(bounds_m, relative_permittivity=1,
relative_permeability=1)`. `bounds_m` is `((x0, x1), (y0, y1), (z0, z1))` in metres
from the box origin. Space outside all regions is vacuum; where regions overlap
the later one wins. Each tetrahedron takes the material containing its centroid.

Every bound must be a mesh grid plane, a multiple of `length/subdivisions` on its
axis (relative tolerance `1e-9` of one cell), so material interfaces coincide with
mesh faces. Otherwise `ValueError` names the bound and the grid spacing; change
the subdivisions rather than relying on a staircase approximation.

## Result

Let K be the requested mode count, E the edge count and T the tetrahedron count.

| Attribute | Shape / meaning | Units |
| --- | --- | --- |
| `frequencies_hz` | `(K,)` complex, `Im > 0` when lossy | Hz |
| `resonant_frequencies_hz` | `(K,)` `Re(frequencies_hz)`, ascending | Hz |
| `quality_factors` | `(K,)` `Re f / (2 Im f)`; `inf` when lossless | dimensionless |
| `eigenvalues_m2` | `(K,)` complex `k0^2` | m^-2 |
| `edge_coefficients` | `(E,K)` complex, exact zeros on PEC edges | m^-1/2 |
| `electric_field` | `(K,T,3)` complex, tetrahedron centroids | m^-3/2 |
| `relative_residuals` | `(K,)` free-edge equations | dimensionless |
| `pec_edge_ids`, `mesh`, `space` | as in the vacuum solver | |
| `tet_relative_permittivity`, `tet_relative_permeability` | `(T,)` complex per tetrahedron | dimensionless |
| `lossless` | every material constant is real and every wall is PEC | bool |
| `time_convention` | `"exp(+j*omega*t)"` | metadata |
| `wall_conductivity_s_per_m` | dict over `WALLS`; `None` means PEC | S/m |
| `fixed_point_iterations` | `(K,)`; zero without finite-conductivity walls | count |

`search`, `cluster_completeness` and `mode_count_policy` carry the vacuum solver's
values and meaning. When `lossless` is true, the solve is still complex; returned
eigenvalues are checked to have `|Im k0^2| <= 1e-9 |k0^2|` and their imaginary
parts are then set to zero.

Each mode is normalized with the Hermitian **vacuum** edge mass `M0` on the returned
SI mesh, `q^H M0 q = 1`, and its largest-magnitude coefficient is made real and
positive. This is an arbitrary mathematical normalization: not volts, V/m, energy
or power. Distinct resonances are biorthogonal in the unconjugated bilinear form
`q_i^T M(eps_r) q_j = 0`, not orthogonal in `M0`.

## Numerical method and failure policy

S and M are assembled per distinct material as real indicator-weighted assemblies
multiplied by the complex constants `1/mu_r` and `eps_r`. For the gradient kernel
(`(nx-1)(ny-1)(nz-1)` interior nodal gradients), let C map interior nodal potentials
to free-edge circulations and `P = I - C (C^T M C)^-1 C^T M`, with plain transposes.

- Up to 256 free edges: dense `scipy.linalg.eig(S, M)`, with an exact kernel-count check.
- Otherwise: ARPACK on the **standard** problem `T = P (S - sigma M)^-1 M P`, `which="LM"`,
  with `sigma = (2*pi*f_target*L/c0)^2`, then `k0^2 = sigma + 1/nu`. ARPACK's generalized
  mode is not used, because it requires a Hermitian positive M. T annihilates gradients
  (`nu = 0`, dropped) and keeps physical values. The candidate count, `ncv`, tolerance
  `1e-10`, iteration limit and seed follow the vacuum solver.
  Sparse LU factorizations use the `MMD_AT_PLUS_A` ordering, which suits the symmetric
  sparsity pattern.

Physical candidates are those with `|k0^2|` above `1e-8` times the analytic vacuum
fundamental divided by `max|eps_r mu_r|`. The requested number nearest the target in
`|k0^2 - sigma|` are returned in ascending real frequency. Every returned set must pass:

- relative residual `||S q - k0^2 M q|| / (||S q|| + |k0^2| ||M q||) <= 1e-8`;
- `M0`-norm of the gradient component (projection with M) `<= 1e-9`;
- smallest eigenvalue of the `M0` Gram matrix `>= 1e-6` (no duplicate vectors);
- for resonances separated by more than `1e-6` relative,
  `|q_i^T M q_j| <= 1e-7 * sqrt((|q_i|^T |M| |q_i|)(|q_j|^T |M| |q_j|))`;
- no physical candidate with `Im k0^2 < -1e-9 |k0^2|` (gain) or `Re k0^2 <= 0`.

Failures raise `RuntimeError` with no partial result; invalid arguments raise `ValueError`.

## Validation

From the repository root:

```bash
python -m pytest -c pyproject.toml -q packages/galerkin/tests/test_material_cavity.py \
  packages/galerkin/tests/test_cavity_wall_loss.py \
  packages/galerkin-refsol/tests/test_material_cavity_reference.py \
  packages/galerkin-refsol/tests/test_wall_loss_reference.py
```

The references are in `refsol.material_cavity` and `refsol.wall_loss` and use no mesh or FEM code.

**Uniform filling.** A homogeneous cavity has the vacuum fields and
`k0^2 = k_vac^2 / (eps_r mu_r)` exactly, and the discrete problem rescales the same way.
Tests compare the material solver with the vacuum solver times this factor at relative
`1e-11` (n = 2 and 4; lossy dielectric-magnetic, lossless dielectric and lossy magnetic
cases), and every returned Q with the closed form at `1e-9`. For `tan_delta = 1e-3`,
`Q = 1/tan_delta` within `1e-6`.

**Slab loading.** A slab filling the cross-section `0 <= z <= d` of an `a x b x c`
box separates into TE-to-z (`Ez = 0`) and TM-to-z (`Hz = 0`) modes with
`kx = m pi/a`, `ky = n pi/b` and `kz_i^2 = eps_i mu_i k0^2 - kx^2 - ky^2`. Matching
tangential fields at `z = d` gives, with `S_i = sin(kz_i L_i)/kz_i`, `C_i = cos(kz_i L_i)`,
`L_1 = d`, `L_2 = c - d`:

    TE-to-z:  C_1 S_2 / mu_1 + S_1 C_2 / mu_2 = 0
    TM-to-z:  kz_1^2 S_1 C_2 / eps_1 + kz_2^2 S_2 C_1 / eps_2 = 0

Both are entire functions of `k0^2`, so they have no spurious roots at `kz_i = 0`.
Lossless roots are bracketed on a real scan and bisected, then continued to the
complex materials in 16 homotopy steps with a complex secant iteration. Reference
self-checks: with `eps = 1` the 15 vacuum modes below 500 MHz in `(1, 0.8, 0.6) m`
are reproduced at `1e-13`; identical lossy materials in both layers reproduce the
uniform rescaling at `1e-12`; and for `tan_delta = 1e-4` the computed `1/Q` equals
`tan_delta` times the electric filling factor `-(eps'/k0^2) dk0^2/deps'` from
independent lossless roots, within `2e-3` relative.

The fixed convergence study uses box `(1, 0.8, 0.6) m`, slab `0 <= z <= 0.3 m`,
`n = 4, 8, 16` in every direction, target 50 MHz (below the fundamental) and the
six lowest modes in ascending real order.

Case `eps = 4 - 0.04j`, `mu = 1` (TM11, TE10, TE01, TE11, TM21, TE20 to z):

| Quantity | TM11 | TE10 | TE01 | TE11 | TM21 | TE20 |
| --- | --- | --- | --- | --- | --- | --- |
| Reference f (MHz) | 155.763+0.605j | 175.160+0.780j | 186.637+0.839j | 205.021+0.935j | 207.719+0.947j | 228.145+1.057j |
| Reference Q | 128.676 | 112.238 | 111.187 | 109.625 | 109.635 | 107.904 |
| `|dk0^2|/|k0^2|`, n=16 | 6.9e-4 | 8.9e-4 | 3.5e-3 | 2.9e-4 | 2.9e-3 | 2.4e-4 |
| Order 8→16 | 1.949 | 2.035 | 1.999 | 1.539 | 1.934 | -0.576 |
| Q relative error, n=16 | 4.2e-4 | 3.3e-4 | 2.3e-4 | 2.9e-4 | 1.19e-3 | 5.9e-4 |

Case `eps = 2.5 - 0.1j`, `mu = 1.2 - 0.02j` (TM11, TE10, TE01, TM21, TE11, TM12 to z):

| Quantity | TM11 | TE10 | TE01 | TM21 | TE11 | TM12 |
| --- | --- | --- | --- | --- | --- | --- |
| Reference f (MHz) | 170.767+3.662j | 202.255+4.386j | 215.658+4.763j | 234.327+5.944j | 237.134+5.388j | 261.535+6.849j |
| Reference Q | 23.313 | 23.055 | 22.637 | 19.711 | 22.004 | 19.094 |
| `|dk0^2|/|k0^2|`, n=16 | 5.8e-4 | 9.9e-4 | 3.6e-3 | 2.4e-3 | 1.5e-4 | 1.2e-3 |
| Order 8→16 | 1.943 | 2.033 | 1.998 | 1.918 | 0.867 | 1.758 |
| Q relative error, n=16 | 4.6e-5 | 3.9e-4 | 6.3e-5 | 1.10e-3 | 1.5e-4 | 1.41e-3 |

Gates (both cases): the complex eigenvalue errors of the three lowest modes decrease
at each step and their final orders exceed **1.8**; all six have `|dk0^2|/|k0^2| < 4e-3`
and Q relative error `< 1.5e-3` at n = 16, and every Q error decreases from n = 8 to 16.
The TE11 mode's real-part error changes sign between n = 4 and 8 in both cases
(TE20's as well in the first case), so its observed rate on this fixed sequence
reflects cancellation and is not gated; its absolute error is among the smallest.
Matching is by ascending real part; at n = 16 every error is far below the gaps
between neighbouring reference modes.

Other tests: the near-target selection equals the complete dense complex spectrum
(including the exact `(n-1)^3` kernel) for n = 2, 4 and 6 with a lossy
dielectric-magnetic slab; residuals are recomputed from an independent per-material
assembly; empty `regions` reproduce `solve_cavity_box` at `1e-10`; a slab normal to x in
a permuted box agrees with the z-stacked reference (eigenvalues within 1.5% and Q within
0.3% at n = 8); region override and centroid assignment; and rejection of off-grid
bounds, gain, non-positive real parts, malformed bounds and wrong types.

## Finite-conductivity walls

`wall_conductivity_s_per_m` is `None` (all six walls PEC), one positive conductivity
for every wall, or a dict over `galerkin.material_cavity.WALLS`
(`"x0", "x1", "y0", "y1", "z0", "z1"`, the walls at the low and high end of each
axis). Missing or `None` entries are PEC. Values are finite positive S/m; zero,
negative, infinite, boolean and unknown wall names raise `ValueError`.

A finite wall uses the Leontovich condition `E_t = Zs H x n` (n outward from the
cavity), with the good-conductor impedance

    Zs = sqrt(j omega mu0 / sigma) = (1 + j) Rs,   Rs = sqrt(omega mu0 / (2 sigma)).

Integrating `curl(mu_r^-1 curl E)` by parts leaves `-j omega mu0 int (n x H) . v dS`,
and `n x H = -E_t / Zs`, so the weak form gains the wall term

    j k0 (eta0 / Zs) int_wall E_t . v_t dS = sqrt(j k0 eta0 sigma) B_wall,

with `eta0 = mu0 c0`, `mu0 = 1.25663706212e-6 H/m` and `B_wall` the exact tangential
Whitney edge mass of that wall's triangles. Edges in a PEC wall stay constrained;
edges in a finite wall become unknowns. The interior-node gradients remain the
exact kernel, so the projector and its kernel count are unchanged. The wall
coefficient varies as `k0^(1/2)`, so

    T(k0^2) q = [S + sum_w sqrt(j k0 eta0 sigma_w) B_w - k0^2 M] q = 0

is a nonlinear eigenproblem. It is solved as follows:

1. Solve the linear problem with the wall coefficient evaluated at the target and
   select modes as usual.
2. For each selected mode, use residual inverse iteration (Neumaier 1985) with one
   LU of `T` at that mode's starting value. Each step solves the scalar equation
   `x^T T(k0^2) x = 0` by Newton and corrects `x <- x - P T0^-1 P^T T(k0^2) x`.
   Stop when the relative nonlinear residual is `<= 1e-10` and the eigenvalue
   change is `<= 1e-12`, with at most 50 steps.
3. Modes degenerate within `1e-8` relative (for example the cube's 011/101/110
   triplet) share one wall coefficient, evaluated at their mean, and are refined
   by repeated shifted eigensolves under the same stop rule.

Nonconvergence raises `RuntimeError`. The reported residual is the larger of the
linear residual and the nonlinear residual with `Zs` at each mode's own final
`k0`; it must satisfy the same `<= 1e-8` gate. M-biorthogonality is not checked
with finite walls, because each mode solves its own operator. All other gates
apply. The impedance condition is valid only while the skin depth is small
compared with the wall curvature and cell size, so that `|Zs| << eta0`. No
surface roughness, wall coatings or frequency-dependent conductivity are modelled.

### Wall-loss reference and validation

`refsol.wall_loss` computes the standard first-order (perturbational) conductor Q,

    Q_c = omega W / P_c,   W = (mu/2) int |H|^2 dV,   P_c = (Rs/2) sum_w int_w |H_t|^2 dS,

from the PEC standing waves `Ex = Ax cos(kx x) sin(ky y) sin(kz z)` (and cyclic
permutations). All integrals are closed-form products of `sin^2` and `cos^2`. When
all three indices are positive, the two polarizations are degenerate. Wall loss
is then a quadratic form on the amplitude plane, and its eigenvectors give two Q
values. The Leontovich reactance lowers the real frequency by as much as the loss
raises the imaginary part: `omega = omega0 (1 + (j - 1)/(2 Q_c))`. The neglected
terms are of relative order `1/Q_c`.

Reference self-checks: TE101 equals Pozar's closed form (*Microwave Engineering*,
4th ed., eq. 6.46) at `1e-12`. Every mode of `(1, 0.8, 0.6) m` up to 400 MHz,
including the split 111 doublet, matches Gauss quadrature of a finite-difference
curl at `1e-6`. Per-wall losses add up to the total. `Q` scales as `sqrt(sigma)`.
Uniform filling gives `Q -> Q mu_r (eps_r mu_r)^(-1/4)`. Cube degeneracies are
preserved.

The FEM tests use box `(1, 0.45, 0.8) m` (no accidental degeneracy among the four
lowest modes) and copper, `sigma = 5.8e7 S/m`:

| Mode | f (MHz) | Reference Q_c | Q error n=4 | n=8 | n=16 | Order 8→16 |
| --- | --- | --- | --- | --- | --- | --- |
| 101 | 239.951 | 51776.8 | -4.74% | -1.25% | -0.314% | 1.988 |
| 201 | 353.530 | 65216.0 | -13.9% | -2.77% | -0.714% | 1.958 |
| 110 | 365.276 | 54744.4 | +6.12% | +0.715% | +0.184% | 1.958 |
| 011 | 382.185 | 59436.8 | +8.28% | +2.37% | +0.616% | 1.945 |

The fixed slow gate requires Q errors that decrease at every step, final orders
**> 1.8**, n=16 Q errors `< 8e-3` and complex-frequency errors `< 4e-3`
(observed at most `3.5e-3`). Every mode needed four nonlinear iterations.

Other wall tests:

- TE101 at n=8 is within 1.5% of Pozar.
- An independent SI rebuild of `T(k0)` with `j k0 eta0 / Zs` gives nonlinear residuals `< 1e-7`.
- The wall mass integrates every uniform field's tangential part exactly (`1e-12`).
- Single-wall Q at n=8 agrees with the reference within 6.7%.
- First-order additivity: the six single-wall `1/Q` sum to the all-wall `1/Q` within `3.1e-4`.
- `sigma = 1e18` reproduces the PEC solver within `7.7e-11`.
- A lossy dielectric fill plus copper walls gives `1/Q = 1/Q_walls + 1/Q_d` within `5e-6`. The filled-cavity wall Q matches the reference within 2.8% at n=8.
- The cube triplet stays exactly degenerate (spread `9e-16`), has three independent modes and has Q within 3.8% of the reference at n=4.
- A dense n=2 case uses mixed walls.
- Invalid conductivities are rejected.

## Reference-tool comparisons

Same-discretization comparison with scikit-fem 12.0.2 (`BSD-3-Clause`, test extra
`galerkin[crosscheck]`): `tests/test_crosscheck_skfem_lossy_cavity.py` rebuilds the lossy slab and
the impedance-wall operators on galerkin's mesh and gates the eigenvalue differences at `1e-9`
(observed `4.1e-15` and `6.8e-13`). See the [reference comparisons](https://github.com/fieldalgo/openphysics/blob/main/docs/reference-comparisons.md).

### Higher-order comparison (NGSolve)

This comparison is separate from the analytic pass/fail gates above. It neither
replaces them nor serves as convergence evidence.

**Tool and setup.**

- NGSolve 6.2.2608 with netgen-mesher 6.2.2608 (both `LGPL-2.1-only`). Installed from
  PyPI wheels into a separate Python 3.12 environment and run as a separate process.
  It is not an OpenPhysics dependency, and no NGSolve code was copied.
- The reproduction script and raw JSON are kept in the private lab repository.

**Matched:**

- geometry: box `(1, 0.8, 0.6) m` with slab `z <= 0.3 m`, and box `(1, 0.45, 0.8) m`;
- materials: `eps = 4 - 0.04j`; and `eps = 2.5 - 0.1j` with `mu = 1.2 - 0.02j`;
- PEC walls, or copper Leontovich walls (`sigma = 5.8e7 S/m`, same weak-form term and `mu0`);
- time convention, Q definition, and the lowest modes by real part;
- per-mode fixed point in `k0`.

**Not matched:**

- mesh: unstructured Netgen tetrahedra versus the structured alternating Kuhn mesh;
- element order: NGSolve order 4 (`maxh = 0.15 m`, 27.5k–47.3k complex unknowns),
  with an order-3 run (`maxh = 0.2 m`) as the tool's own self-check, versus lowest-order
  galerkin at n = 16;
- eigensolver: NGSolve Arnoldi with a shift at the target.

With 14 Arnoldi vectors, one order-4 run returned an unconverged sixth value
(908.5 MHz, negative Q) for the `eps = 4 - 0.04j` case. Rerun with 26 vectors, all six
modes converged. Only the converged rerun is used; the failed value is kept in the raw record.

Largest relative differences over the six (slab) or four (copper) modes:

| Case | NGSolve p4 vs analytic: f / Q | NGSolve p3 vs p4: f / Q | galerkin n=16 vs NGSolve p4: f / Q | galerkin n=16 vs analytic: Q |
| --- | --- | --- | --- | --- |
| Slab `eps 2.5-0.1j`, `mu 1.2-0.02j` | 7.8e-6 / 1.2e-4 | 1.4e-4 / 3.6e-4 | 1.8e-3 / 1.5e-3 | 1.4e-3 |
| Slab `eps 4-0.04j` | 1.6e-7 / 1.3e-7 | 3.3e-4 / 1.3e-3 | 1.8e-3 / 1.2e-3 | 1.2e-3 |
| Copper walls | 6.2e-7 / 1.3e-5 | 1.9e-3 / 1.4e-2 | 3.5e-3 / 7.1e-3 | 7.1e-3 |

The high-order NGSolve results agree with the independent analytic references to
`1.6e-7`–`7.8e-6` in frequency. For copper walls, the Q difference of `1.3e-5` is within
the first-order perturbation reference's `O(1/Q)` term. Q there is `Re f / (2 Im f)`,
which differs from `omega0 W / P` by one half. galerkin's differences from NGSolve match
its differences from the analytic references: they are its own mesh error, already gated above.

| Run | Time / memory (one core) |
| --- | --- |
| NGSolve order 4 | 29 s, 25 s (42 s with 26 vectors), 63 s per case; peak RSS 1.8 GB |
| galerkin n=16 | 9.6 s, 9.2 s, 34 s |

These timings come from different discretizations and are not a performance comparison.

**Support decision:** unchanged. The feature is supported on the basis of the analytic
gates. The comparison found no disagreement beyond galerkin's documented mesh error
and the reference's first-order term.

## Limitations

- Finite-conductivity walls are local Leontovich impedances on whole box walls, with
  first-order references; no roughness, coatings, or partial-wall patches.
- Constant, isotropic, frequency-independent `eps_r`, `mu_r`. Dispersive materials
  would also make the problem nonlinear.
- Regions are boxes aligned with grid planes. No staircase or curved interfaces.
- Search, cluster and count policies are those of the vacuum solver.
