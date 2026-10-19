# Material-loaded rectangular PEC cavity solver

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
It returns complex resonant frequencies and quality factors. The walls remain
perfect electric conductors; finite-conductivity walls, open boundaries,
anisotropic or dispersive materials and arbitrary geometry are not included.
`solve_cavity_box` and its contract are unchanged.

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
target_frequency_hz)` returns a `MaterialCavityResult`. `lengths_m`, `subdivisions`,
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
| `lossless` | every material constant is real | bool |
| `time_convention` | `"exp(+j*omega*t)"` | metadata |

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
  packages/galerkin-refsol/tests/test_material_cavity_reference.py
```

The references are in `refsol.material_cavity` and use no mesh or FEM code.

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

## Limitations

- PEC walls only. Finite wall conductivity (surface impedance) is planned separately;
  it makes the eigenproblem nonlinear in frequency.
- Constant, isotropic, frequency-independent `eps_r`, `mu_r`. Dispersive materials
  would also make the problem nonlinear.
- Regions are boxes aligned with grid planes. No staircase or curved interfaces.
- Search, cluster and count policies are those of the vacuum solver.
