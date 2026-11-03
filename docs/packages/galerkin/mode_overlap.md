# Mode power, overlap and coupling

**English** | [한국어](../../locales/ko/pages/packages/galerkin/mode_overlap.md)

[galerkin overview](overview.md) · [Eigenspace reliability](eigenspace_reliability.md) · [Derivatives](differentiation.md)

`galerkin.mode_overlap` post-processes the modes of `galerkin.waveguide.solve_modes`
(full-vector, edge `et` and nodal `ez`) and scalar P1 mode functions on a `Mesh`:
guided power, field overlaps, normalisation, coupling efficiency, confinement
factor and effective area. Every integral is an exact mass- or coupling-matrix
product of the finite element coefficients, except `int |E|^4` of the effective
area, which a symmetric triangle rule integrates exactly; nothing is sampled at
centroids except where a function says so. This page is the contract and the validation record; the formulation is
pre-registered and the measured values below are those of
`tests/galerkin/test_mode_overlap.py` on the pinned Linux environment
(2026-11-02).

## Conventions

- Phasor `exp(+i omega t - i beta z)`, as the solver. `et[i]` are the edge line
  integrals of `E_t` (global direction low node id to high), `ez[i]` the nodal
  values with `E_z = 1j * ez[i]`; amplitude and phase are arbitrary
  ([eigenspace reliability](eigenspace_reliability.md)). Scalar modes are nodal
  `phi`.
- `k0` and `n_eff` are the solver's: `beta = k0 n_eff`, `k0` in inverse mesh
  length, `n_eff` real or complex.
- `mu_r` (default 1) and `eps_r` are scalars or one value per triangle, as the
  solver takes them; the functions below use `conj(1/mu_r)` in the Poynting
  integrals and `Re(eps_r)` as the energy weight.
- **Units.** With the mesh in metres and `E` in V/m, `vector_power` is in watts.
  With the mesh in another unit `L` (metres per mesh unit) and `k0` in that
  inverse unit, the result is in watts when `E` is in volts per mesh unit; for
  `E` in V/m multiply by `L^2`. Since mode amplitudes are arbitrary, "power" means
  watts per (field unit)^2 until the mode is normalised. Field overlaps carry
  (field unit)^2 (mesh unit)^2; efficiencies and confinement factors are
  dimensionless. Scalar "power" is `int |phi|^2 dA`, not a physical power.

## Formulation

**Magnetic field from the electric field.** Faraday's law in the phasor above,
with `grad = grad_t - i beta zhat`, gives the transverse magnetic field of a
mode from `E` alone (the solver never forms `H`):

    H_t = (beta / (omega mu)) zhat x E_t + (1 / (i omega mu)) zhat x grad_t E_z.

**Power and cross power.** For transverse `a`, `b`, `(a x (zhat x b)) . zhat = a . b`,
so the complex Poynting integral of mode `a`'s electric field against mode `b`'s
magnetic field is

    P_ab = 1/2 int (E_a x H_b^*) . zhat dA
         = (1 / (2 omega mu0)) int conj(1/mu_r) [ conj(beta_b) E_ta . E_tb^* + i E_ta . grad_t E_zb^* ] dA,

and `P = P_aa`. `Re P` is the time-averaged power in `+z`; for a lossless mode `P`
is real. With `E_t = sum_e et_e W_e` (Whitney edge functions) and
`E_z = i sum_n ez_n phi_n` (P1 hat functions), the two integrals are the edge
mass `M_e(c) = int c W_e . W_f` (`assemble_edge_mass`, exact) and the edge-nodal
coupling `G(c) = int c W_e . grad phi_n` (`assemble_edge_grad`, exact):

    P_ab = (1 / (2 omega mu0)) [ conj(beta_b) et_b^H M_e(c) et_a + ez_b^H G(c)^T et_a ],    c = conj(1/mu_r),

with `omega mu0 = k0 c mu0` (`scipy.constants`). The sign and orientation of the
`G` term were checked against a brute-force centroid integral of
`i int c E_t . conj(grad_t E_z)` (exact for the piecewise-linear integrand):
`conj(ez) @ (G.T @ et)` reproduces it to roundoff; `et^H G ez` is its conjugate
and has the same real part.

**Exact discrete power orthogonality.** For the real pencil `A x = -beta^2 B x`
with `x = [beta et; ez]`, the second block row reads
`G^T et = -(K - k0^2 M) ez / beta`. Substituting it into the `B`-orthogonality
`x_b^T B x_a = 0` of two eigenvectors with distinct eigenvalues leaves
`beta_a [ beta_b et_b^T M_t et_a + ez_b^T G^T et_a ] = 2 omega mu0 beta_a P_ab`.
The discrete cross power of distinct lossless modes is therefore zero exactly,
not only in the limit; the measurement below confirms it at roundoff.

**Field overlap, coupling efficiency, confinement.**

    <E_a, E_b> = int E_a^* . E_b dA = et_a^H M_e(1) et_b + ez_a^H M(1) ez_b        (M(1): P1 mass, exact)
    eta        = |<E_m, E_in>|^2 / (<E_m, E_m> <E_in, E_in>)
    Gamma_R    = int_R Re(eps_r) |E|^2 dA / int Re(eps_r) |E|^2 dA

For several modes (a degenerate pair) `eta` is the share of the input in their
span, `||P E_in||^2 / ||E_in||^2` with the orthogonal projector of the field
overlap, computed from the Gram matrix of the modes. A transverse input
(`ez_in` omitted) is compared with `E_t` of the mode alone, so the longitudinal
component enters `eta` only when the input has one. `Gamma_R` restricts the
coefficient to the triangles `R`. The scalar functions use `M(1)` alone.

**Effective area.**

    A_eff = (int |E|^2 dA)^2 / int |E|^4 dA

with `|E|^2 = |E_t|^2` by default (the usual transverse definition) or
`|E_t|^2 + |E_z|^2` with `include_longitudinal=True`; for a scalar mode `|phi|`
replaces `|E|`. The numerator is the field overlap of the mode with itself (edge
and P1 mass matrices, exact). The denominator has no mass-matrix form, so it is
integrated with Dunavant's 6-point degree-4 symmetric triangle rule
(`galerkin.core.quadrature.triangle_symmetric_rule(4)`), evaluating the
Whitney/P1 interpolant at the rule's points: `E_t` (Whitney) and `E_z`, `phi` (P1)
are linear on each triangle, so `(|E|^2)^2` is a polynomial of degree 4 there
and the rule is exact, not approximate; gate F3 below checks this against the
12-point degree-6 rule and the 36-point Gauss–Duffy product rule. `A_eff` is
scale free and carries (mesh unit)^2; for a y-invariant field on a strip of
height `h` it equals `h` times the effective width `(int |E|^2 dx)^2 / int |E|^4 dx`.

**Interpolating a given field.** `interpolate_vector_field(space, field)` maps a
function `field(x, y) -> (N, 2 or 3)` to `(et, ez)`: `et_e` is the tangential
line integral along edge `e` by two-point Gauss quadrature (the lowest-order
Nédélec interpolant; exact for a cubic variation along the edge) and
`ez = -1j * E_z(nodes)`. A field known only at centroids, `(T, 2)`, cannot be
mapped onto edge dofs: the three Whitney functions of a triangle are linearly
dependent at its centroid (the constant-curl bubble vanishes there), so the
centroid-evaluation map has a kernel on common structured meshes and a
least-squares fit is not unique. No such projection is offered; sample the field
as a function, or compare centroid fields directly with `centroid_field`.

## API

All functions are NumPy only; JAX and PyTorch values raise `TypeError`
(`galerkin.core.checks.refuse_live`). `space` is the `EdgeSpace` returned by
`solve_modes`; shapes are checked and nonfinite values refused.

| Function | Returns |
|---|---|
| `vector_power(space, et, ez, n_eff, k0, mu_r=1.0)` | complex `P` of one mode; `Re P` is the +z power, real for a lossless mode |
| `vector_cross_power(space, et_a, ez_a, et_b, ez_b, n_eff_b, k0, mu_r=1.0)` | `P_ab`; `a` carries `E`, `b` carries `H^*` and its `n_eff_b` |
| `vector_field_overlap(space, et_a, ez_a, et_b, ez_b, include_longitudinal=True)` | `<E_a, E_b>`; with `False`, `E_t` only (`ez` may be None) |
| `overlap_matrix(space, et, ez, kind="field" \| "power", n_eff=None, k0=None, mu_r=1.0)` | `(m, m)` matrix of `<E_a, E_b>` or `P_ab` for modes stacked as `(m, n_e)`, `(m, n_n)` |
| `normalize_vector(space, et, ez, n_eff=None, k0=None, mu_r=1.0, convention="power" \| "mass" \| "peak")` | `(et, ez)` with `Re P = 1`, `int |E|^2 = 1` or max centroid `|E| = 1` (the simcase vector convention); phase unchanged; `"power"` needs `Re P > 0` |
| `coupling_efficiency(space, et_mode, ez_mode, et_in, ez_in=None)` | `eta`; `et_mode` `(n_e,)` or `(m, n_e)` for the span of several modes |
| `confinement_factor(space, et, ez, eps_r, triangles)` | `Gamma_R`; `triangles` a boolean mask `(T,)` or an index array |
| `centroid_field(space, et, ez=None)` | `(T, 3)` complex `E` at centroids (`eval_edge_field` and `1j *` mean nodal `ez`) |
| `interpolate_vector_field(space, field)` | `(et, ez)` of a function, `ez` None for a two-component field |
| `effective_area(space, et, ez, include_longitudinal=False)` | `A_eff` in (mesh unit)^2; `E_t` only by default (`ez` may then be None), `E_t` and `E_z` with `True` |
| `scalar_power(mesh, phi)` | `int |phi|^2 dA` |
| `scalar_overlap(mesh, a, b)` | `int a^* b dA` |
| `normalize_scalar(mesh, phi, convention="power" \| "peak")` | unit `int |phi|^2` (phase unchanged) or peak exactly 1 at the node of largest `|phi|` (the simcase scalar convention, which removes the arbitrary phase) |
| `scalar_coupling_efficiency(mesh, mode, field)` | `eta` with the P1 mass; `mode` `(n_n,)` or `(m, n_n)` |
| `scalar_confinement_factor(mesh, phi, triangles)` | `int_R |phi|^2 / int |phi|^2` |
| `scalar_effective_area(mesh, phi)` | `(int |phi|^2 dA)^2 / int |phi|^4 dA` |

The public names are also exported from `galerkin`. The vector power functions
take `n_eff` explicitly because `beta` enters `H_t`; `solve_modes` returns
`(n_eff, space, et, ez)`, so `vector_power(space, et[i], ez[i], n_eff[i], k0)`.

```python
import numpy as np
from galerkin import rectangle_mesh, solve_modes
from galerkin.mode_overlap import normalize_vector, coupling_efficiency, confinement_factor, interpolate_vector_field

n_eff, space, et, ez = solve_modes(mesh, eps_r, k0, n_target=n_core, num_modes=4)
et0, ez0 = normalize_vector(space, et[0], ez[0], n_eff[0], k0)           # Re P = 1
gamma = confinement_factor(space, et0, ez0, eps_r, mesh.regions == 0)   # energy in region 0
et_in, _ = interpolate_vector_field(space, lambda x, y: np.stack([np.exp(-(x**2 + y**2) / w0**2),
                                                                  np.zeros_like(x)], axis=-1))
eta = coupling_efficiency(space, et[:2], ez[:2], et_in)                 # Gaussian into a degenerate pair
```

## Validation

The references never use the module: `refsol.slab.field_te` and
`refsol.fiber.vector_mode_field` integrated with `scipy.integrate.quad` or dense
polar grids split at the core radius, edge-mass products assembled in the test,
and brute-force centroid sums. The gates were fixed before the measurements and
are kept as written; a gate that was not met is reported, not loosened. The
tests print every value; the file runs in about 12 s.

**A. Scalar TE slab** (d = 0.22 µm, n_f = 3.48, n_s = n_c = 1.444, λ = 1.55 µm;
P1 generalized eigenproblem `(k0^2 M_eps - K) phi = beta^2 M phi` built in the
test as the simcase scalar solver does; PEC far walls at ±1.21 µm; three meshes
with h = 0.044, 0.022, 0.011 µm, one cell high with square cells). A strip of
unit height one cell high was tried first and gave an O(h) field error (2.2e-2,
1.0e-2, 5.1e-3, order 1.0): on the one-diagonal structured mesh the Neumann rows
of the P1 mass are not the restriction of the 1D mass, so the y-invariant vector
is not a discrete eigenvector and the eigenfunction varies across y by O(h_y).
Square cells remove the effect; the exact profile normalised to unit
`int E^2 dx` on the whole line is scaled by `sqrt(height)`.

| Gate | Measured (h = 0.044, 0.022, 0.011 µm) | Order | Result |
|---|---|---|---|
| A1 relative L2 error of the unit-power TE0 field vs the exact profile, order ≥ 1.8, finest ≤ 1e-3 | 6.17e-3, 1.48e-3, 3.64e-4 | 2.06, 2.03 | pass |
| A2 `1 - eta(TE0 numerical, exact at nodes)`, order ≥ 1.8 | 7.63e-6, 3.02e-7, 1.34e-8 | 4.66, 4.49 | pass |
| A3 `eta(TE0, next mode)` ≤ 1e-10 (discrete mass orthogonality) | 0, 1.2e-34, 2.2e-34 | — | pass |
| A4 film confinement vs `quad` of `E^2` over |x| ≤ d/2, order ≥ 1.8, finest ≤ 1e-3 | 6.86e-3, 1.76e-3, 4.46e-4 | 1.96, 1.98 | pass |
| A5 Gaussian input `exp(-x^2/w0^2)`, w0 = d: `eta` vs the `quad` overlap, finest ≤ 1e-3 | 1.19e-3, 3.14e-4, 8.00e-5 | 1.91, 1.98 | pass |

The effective index converges alongside (relative error 3.1e-3, 7.9e-4, 2.0e-4).

**B. Vector slab** (`solve_modes` on the two-cells-wide strip of
`tests/galerkin/test_slab_modes.py`, scales 1, 2, 4; TE with PEC side walls, TM
with magnetic side walls).

| Gate | Measured (scale 1, 2, 4) | Order | Result |
|---|---|---|---|
| B1 TM: `vector_power` (Faraday route) vs the Ampère route `(omega eps0 / 2 beta) int eps_r |E_t|^2` with the eps-weighted edge mass, relative difference, order ≥ 1.8, finest ≤ 2e-3 | 1.47e-6, 1.12e-7, 7.37e-9 | 3.72, 3.92 | pass |
| B1 TE: the `grad E_z` term is zero, so the routes agree ≤ 1e-12 | share of the `G` term in the power 3.61e-9, 1.55e-10, 8.83e-12 | 4.54, 4.13 | **not met** (8.8e-12 > 1e-12 at the finest mesh) |
| B2 distinct modes `|P_ab| / sqrt(P_a P_b)`, order ≥ 1.8, finest ≤ 1e-4 | TE 9.8e-17, 5.4e-17, 7.4e-17; TM 1.4e-16, 3.5e-16, 1.8e-15 | not measurable (roundoff) | bound passes; see below |

On B1 TE: the discrete TE mode has a small nonzero `ez`, because the Whitney
interpolant of an x-invariant `E_x` is not exactly x-invariant and the second
block row then gives `ez = -(K - k0^2 M)^{-1} G^T et != 0`. The term is a
discretisation quantity converging at order 4 to 4.5, far above eigensolver
noise, and the pre-registered 1e-12 bound is not reached on the finest mesh
used. The test asserts, post hoc and labelled as such, only that the term
converges (order ≥ 1.8). The Ampère expression itself does not apply to TE
(`H_z != 0`): its measured difference from the Faraday route, 0.2552, 0.2557,
0.2558, is printed and not gated. On B2: the cross power vanishes exactly by the
identity of the formulation section, so the bound is met at every mesh and no
convergence order exists to measure. Both lossless powers have zero imaginary
part to 1e-12 relative.

**C. Step-index fibre HE11** (a = 4 µm, n1 = 1.45, n2 = 1.44, λ = 1.55 µm, the
scale-2 mesh of `tests/galerkin/test_fiber_modes.py`, R = 6a; the numerical HE11
pair is degenerate to 1e-9).

| Gate | Measured | Result |
|---|---|---|
| C1 `eta` of the exact HE11 field into the span of the numerical pair ≥ 1 − 5e-3 | centroid comparison (exact at centroids vs `centroid_field`, area weighted, Gram projection) 0.998843 (1 − eta = 1.16e-3); interpolated field (`interpolate_vector_field` then `coupling_efficiency` with the pair) 0.999987 (1 − eta = 1.29e-5); best single member of the pair 0.9116 | pass |
| C2 core confinement vs the dense integral of `eps_r |E|^2` (Gamma = 0.874409, grid-converged to 1e-8) | 0.873395, difference 1.01e-3 (≤ 5e-3) | pass |

**D. Gaussian to HE11** (x-polarised `exp(-r^2/w0^2)`, w0 = a, interpolated onto
edge dofs; `eta` into the pair vs a dense polar integral over both exact
polarisations): 0.997946 vs 0.997924, difference 2.15e-5 (≤ 5e-3), pass. At
scales 1 and 3 the difference was 8.2e-5 and 1.3e-5.

**F. Effective area.**

| Gate | Measured | Order | Result |
|---|---|---|---|
| F1 x-polarised Gaussian `exp(-r^2/w0^2)` interpolated with `interpolate_vector_field` onto a disk mesh of radius 4 w0 (`disk_mesh`, 16, 32, 64 radial by 24, 48, 96 azimuthal divisions): `effective_area` vs `pi w0^2`, relative error, order ≥ 1.8, finest ≤ 1e-3 | 1.33e-2, 3.31e-3, 8.26e-4 | 2.00, 2.00 | pass |
| F2 scalar slab TE0 of A: `scalar_effective_area / height` vs the effective width `(int E^2 dx)^2 / int E^4 dx` of `field_te` by `quad` (0.299304 µm), relative error, order ≥ 1.8, finest ≤ 1e-3 | 1.20e-2, 3.07e-3, 7.72e-4 | 1.97, 1.99 | pass |
| F3 `int |E|^4` by the degree-4 rule vs the degree-6 rule, relative, ≤ 1e-12 on one mesh (scale-1 TM slab mode, `E_t` alone and with `E_z`; the P1 TE0 field of A at h = 0.044 µm) | 4.3e-15, 6.9e-15, 2.7e-15; vs the 36-point product rule 6.7e-16, 4.7e-15, 4.0e-15 | — | pass (exact) |
| F4 refusal of JAX and PyTorch values (`TypeError`), shape errors, nonfinite and zero fields (`ValueError`); scale invariance; `A_eff` of a constant scalar field equals the domain area | as stated | — | pass |

The F1 error of the interpolated Gaussian converges at second order although the
Whitney interpolant itself is first order in `L2`: the leading interpolation
error of a smooth field has zero mean on each triangle, so both integrals of
`A_eff` see it at `O(h^2)`. F3 also checks the two rules integrate every
monomial up to their degree on the unit triangle to 1e-13.

Unit tests cover the three vector and two scalar normalisation conventions
(round trip, phase preserved), the projection onto a span (one for a member, a
linear combination of the pair, refusal of dependent modes), mask and index
forms of the confinement regions, exact reproduction of a Whitney and a hat
function by the interpolant, shape errors and the refusal of JAX and PyTorch
values (skipped where the libraries are absent; the backend CI job runs them).

## Limitations

- NumPy only: no derivatives through these integrals; live values raise
  `TypeError`. The kernels they use (`assemble_edge_mass`, `assemble_edge_grad`,
  `assemble_mass`) are likewise NumPy.
- The power is the lossless-waveguide definition, `Re` of the complex Poynting
  integral of the given field. For lossy or leaky modes it is still the `+z`
  power of that field, but modes are then not power-orthogonal, `P` has a
  reactive imaginary part and `conj(1/mu_r)` matters; nothing here certifies a
  PML candidate ([modal coordinates](modal_coordinates.md)).
- Modes with coordinate factors (PML, bends) are covariant computational
  components; the integrals here do not undo the stretch.
- No group-velocity or energy-velocity power, no overlap with an imported
  measured field, no centroid-to-edge projection. The effective area is the
  `|E|^2`/`|E|^4` definition above; no nonlinear-coefficient weighting
  (`n_2`, `chi^(3)` per region) is offered.
- simcase saves `vector_power`/`scalar_power`, `confinement_factor`,
  `overlap_matrix` and an optional Gaussian `coupling_efficiency` with every
  closed-window `em.modes2d` result
  ([mode post-processing](../simcase/overview.md#mode-post-processing)); not
  exposed in Studio. The simcase normalisations (`"peak"`) are reproduced here
  for comparison only.
