# Homogeneous Laplace boundary panels

**English** | [한국어](../../locales/ko/pages/packages/galerkin/laplace_boundary.md)

`galerkin.laplace_boundary.solve_grounded_rectangle` solves constant-potential,
closed conductors in a homogeneous two-dimensional rectangle. The bottom is
grounded; the side and top walls have zero normal flux. It is an explicit
boundary API alongside the [volume electrostatics API](electrostatics.md).

## Inputs and example

```python
import numpy as np
from scipy.constants import epsilon_0
from galerkin.laplace_boundary import solve_grounded_rectangle

trace = 1e-3 * np.array([[1.05, .2], [1.15, .2], [1.14, .24], [1.06, .24]])
result = solve_grounded_rectangle(
    [trace], width=2.4e-3, height=1e-3, panels_per_edge=32,
)
capacitance_f_per_m = epsilon_0 * result.capacitance_per_permittivity
print(capacitance_f_per_m)
```

Coordinates, `width` and `height` are in metres. `height` is the complete
rectangle height, including any substrate thickness in an externally composed
model. The kernel itself has no layered materials. A polygon is implicitly
closed, with no repeated closing vertex; either orientation is accepted.

| Input | Contract |
|---|---|
| `polygons` | List or tuple of 1–16 finite real `(n,2)` arrays, each a simple strictly convex polygon with at least three vertices. No collinear edges, touching, overlap, nesting, zero thickness or wall contact. |
| `width`, `height` | Finite positive real scalars, with width/height in `[0.25,4]`. |
| `panels_per_edge` | Integer 1–256, default 32. At most 2048 panels in total. Every edge uses cubic endpoint grading. |
| `interpolation_degree` | One of the integers 10, 12, 14, 16, default 10. Compare degree−2 with the requested degree. No automatic change. |
| `ground_modes` | Integer 64–4096, default 512. Compare this cosine truncation with twice as many modes; return the refined result. |

The cluster bounding box must be at least its largest extent away from each
side and the top wall. An edge or graded panel shorter than `128*eps` in
coordinates normalized by `max(width,height)` is refused. Boolean scalar
controls, nonfinite coordinates and unresolved systems are refused before a
result is returned. The limits bound this implementation's verified domain and
cost; they are not general restrictions of the Laplace equation.

## Outputs, formulation and checks

`RectangleBoundaryResult` holds immutable snapshots:

| Field | Shape and meaning |
|---|---|
| `capacitance_per_permittivity` | `(n,n)`, dimensionless charge/voltage matrix divided by homogeneous absolute permittivity. Multiply by permittivity in F/m to obtain capacitance per length in F/m. |
| `current_gram` | `(n+1,n,n)` in 1/m. Surface integral of `j_i*j_j` for currents normalized to one on conductor `i`. Input conductor order, then grounded bottom. |
| `current_integrals` | `(n+1,n)`, dimensionless. Identity on conductors, minus one on ground. |
| `panel_count`, `condition_bound` | Total number of panels; infinity-norm matrix condition estimate, required below `1e10`. |
| `reciprocity_error`, `residual_error`, `current_error` | Raw relative matrix/capacitance reciprocity, solve residual and absolute current-conservation errors, each at most `1e-10`. |
| `matrix_refinement_error`, `ground_refinement_error` | Relative quadrature/interpolation/image and ground Fourier/quadrature changes, each at most `1e-10`. |

Constant panel **total charges** are the unknowns. The energy matrix averages
the Green function over both source and target panels, preserving reciprocity.
The singular grounded half-space contribution uses an analytic double log
integral. The same-panel average is `log(length)-3/2`; very unequal panel
lengths use a normalized one-dimensional source primitive and refined target
quadrature to avoid cancellation. The smooth side/top image correction uses a
tensor Chebyshev basis on the conductor cluster. The bottom current Gram matrix
comes from a cosine harmonic-measure Parseval sum.

The implementation compares degrees `interpolation_degree-2` and
`interpolation_degree`, with quadrature orders 6/8 and an extended image sum.
The default remains degree 8/10. A geometry rejected at the default may be
re-evaluated with an explicitly higher degree; the `1e-10` criterion is unchanged. The image count follows the rectangle aspect ratio. Ground truncation is
compared at `ground_modes`/`2*ground_modes` and quadrature orders 6/8. It checks
raw reciprocity before averaging roundoff and requires a positive-definite
Cholesky factorization. There is no diagonal jitter, tolerance relaxation or
fallback to another model.

**These checks do not establish panel or outer-domain convergence.** Repeat
with finer `panels_per_edge` and larger rectangles while retaining the same
conductor coordinates relative to ground. A small algebraic residual does not
bound the physical discretization error. Surface factors alone are not a
frequency-dependent line or a measured accuracy claim.

## Validation and reproduction

Run from the repository root:

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q \
  tests/galerkin/test_laplace_panel_integrals.py \
  tests/galerkin/test_laplace_boundary.py \
  tests/galerkin/test_laplace_boundary_interpolation.py \
  tests/galerkin/test_crosscheck_skfem_laplace_boundary.py
```

- Independent adaptive source/target integration checks self, adjacent,
  rotated, close and length ratios through `1e8` at `1e-10`. Rotation, scale,
  exchange, current conservation, positive energy and input refusal are tested.
- A 256-sided circle of radius `a=.1 m`, centre height `h=.5 m`, approaches
  the grounded infinite half-space as `(W,H)` doubles from `(4,2)` through
  `(64,32) m`. With `b=sqrt(h*h-a*a)`, references are
  `C/eps=2*pi/acosh(h/a)`, signal Gram `h/(2*pi*a*b)` and ground Gram
  `1/(2*pi*b)`. Every error must decrease, and the finest must be below `.005`.
- An unequal-width/thickness pair is checked with 32/64/128 panels per edge
  in three fixed rectangles. Each final panel change must decrease and be at
  most `.001` for capacitance and `.005` for each surface Gram matrix.
- A live scikit-fem P2 comparison independently assembles the volume field and
  boundary mass for a matched 64-sided conductor polygon and three volume
  sizes. Different discretizations are **report-only**; they do not replace
  analytical or panel-convergence gates. Set `OPENPHYSICS_CROSSCHECK_DIR` to
  save the tool version, matched conditions, differences and timings.

Runtime uses existing NumPy/SciPy dependencies only. scikit-fem is test-only.
No new Windows/macOS, browser, JSON document, external-material or full-wave
support is established by these tests.

At a fixed 4 m × 2 m rectangle with three 64-sided circular conductors, the
default degree is deliberately refused: the 8→10 change is about `2.35e-10`.
Explicit degrees 12/14/16 agree to `1e-10`, including every surface Gram matrix.
This is refinement at unchanged geometry, not a relaxed tolerance or a larger box.

## Short-panel integration

Unequal-panel logarithmic integrals retain their original evaluation when its
32/64-point check passes. Failed entries retry the same quadrature in normalized
local coordinates before evaluating the source primitive. This avoids rounding away
the motion along a short target by first adding a large coordinate origin.
The existing 32/64-point agreement criterion remains
`1e-12 * max(1, abs(mean_log_distance))`; unresolved integrals still fail.

Stored independent checks cover one short/long geometric pair in both source
orders, using mpmath 1.3.0 at 60 and 80 decimal digits. Direct two-dimensional
log-distance integration agrees between those precisions within `1e-30`
relative. Tests also check endpoint reversal, translation to the origin,
reflection and exact power-of-two scaling. These checks isolate arithmetic
stability; they do not qualify a new grading, interpolation order or arbitrary
conductor-loss accuracy. Existing public defaults and admission limits remain.

## Explicit corner power-panel integrals

`galerkin.laplace_corner` provides numerical building blocks for a normalized
power density, `phi(s) = p/h * (s/h)**(p-1)` on `0 < s < h`. Length `h` is in
metres and the singular endpoint is `s=0`. Require `0.5 < p <= 1`; the integral
of squared current diverges at `p=0.5`. For a homogeneous exterior Laplace wedge
around a convex metal corner of interior angle `alpha`, the leading exponent
is `p = pi/(2*pi-alpha)`. This relation does not cover dielectric junctions,
anisotropic corner laws or finite conductivity diffusion.

```python
from galerkin.laplace_corner import (
    power_panel_gram, power_panel_self_log, power_panel_shared_vertex_log,
)

gram_per_m = power_panel_gram(1e-3, 2/3)
self_log = power_panel_self_log(1e-3, 2/3)
pair = power_panel_shared_vertex_log(
    [1e-3, 0.], [0., 1e-3], 2/3, 2/3,
)
print(gram_per_m, self_log, pair.mean_log_distance, pair.refinement_error)
```

The exact self moments are `p**2 / ((2*p-1)*h)` and
`log(h/1 metre) - 1/(2*p) - digamma(p+1) - EulerGamma`.
At `p=1`, these reduce to `1/h` and `log(h/1 metre)-1.5`.
`power_panel_quadrature(p, order)` returns immutable nodes and positive weights
for the normalized measure `p*u**(p-1) du` on `[0,1]`. Orders 4–128 use the
Golub–Welsch Jacobi tridiagonal matrix and squared first eigenvector components;
computed weights are not divided by their sum.

`power_panel_shared_vertex_log(a, b, p, q)` accepts finite, nonzero planar
displacement vectors from a common vertex, in metres. The panels must meet only
at that vertex, with length ratio at most 64. Overlapping rays are rejected.
The result is the double weighted mean of `log(distance/1 metre)`. A Duffy split
integrates the radial logarithm exactly and applies Gauss–Jacobi to the angular
terms. The explicit coarse order is 4–64, default 32; its doubled order supplies
the result. Require `abs(fine-coarse) <= 1e-12*max(1,abs(fine))`, otherwise raise
`ValueError`. The returned frozen record retains both values and the coarse
order; `refinement_error` reports this normalized difference. Nonfinite inputs,
unrepresentable Gram values and unresolved quadrature are rejected.

Validation uses exact polynomial moments through degree `2*order-1`, constant
panel reductions, current scaling, and four stored independent 60/80-digit
direct two-dimensional mpmath integrals with swaps, rotations, reflections and
length scaling. The stored reference is
`tests/galerkin/two_ground/evidence/corner-panel-integrals.json`; the runtime
does not import mpmath. Quadrature and reference gates are `1e-12`; the two
reference precisions must agree to `1e-30`.

These functions are explicit primitives, not a complete weighted-panel field
solver. Existing boundary solvers, defaults and constant-panel results remain
unchanged. A future field composition must independently verify its assembled
operator, currents, material assumptions, and panel/outer-domain convergence.
No general corner-field, small-mutual-loss or platform accuracy follows from
the integral checks alone.

### Separated power panels

`power_panel_separated_log(first, second, offset, p, q)` evaluates the double
weighted log distance for a panel from zero to `first` and a panel from
`offset` to `offset + second`. These are finite planar displacement vectors
in metres. Each power density starts at its specified panel origin; reversing
a nonconstant panel moves its singularity and is not an invariant operation.

Require a length ratio at most 64 and minimum segment distance at least half
the longer panel length. Endpoint contact, intersection and overlap are
rejected. Norms and quadrature distances must be representable. An explicit
positive tensor Gauss–Jacobi rule compares coarse order 4–64 (default 32) with
twice that order, retaining the same `1e-12*max(1,abs(fine))` gate and frozen
result fields. Coordinate normalization extracts the logarithm of the length
scale analytically; quadrature weights are not renormalized.

```python
from galerkin.laplace_corner import power_panel_separated_log

pair = power_panel_separated_log(
    [1e-3, 0.], [0., 1e-3], [2e-3, 2e-3], 2/3, .75,
)
print(pair.mean_log_distance, pair.refinement_error)
```

Four additional stored direct 2D mpmath 60/80-digit references cover parallel,
perpendicular, skew and collinear separated panels, with unequal powers and
lengths. Their record is
`tests/galerkin/two_ground/evidence/corner-separated-integrals.json`.
Tests retain the `1e-12` reference/transform and `1e-30` precision-agreement
gates; they also check positive-weight distance bounds, the exact separation
admission boundary, explicit refusal, density orientation and representable
length scales. General near pairs, other endpoint contacts and an assembled
weighted field solver remain outside this API.

### Power panel against a constant panel

`power_panel_constant_log(a, b, offset, p)` evaluates the weighted log mean
between the power panel `0 -> a` and the constant panel `offset -> offset+b`.
Vectors are in metres, `0.5 < p <= 1`, and the length ratio is at most `1e6`.
Disjoint panels and contact at one common endpoint are allowed; overlaps,
interior intersections, nonfinite inputs and unrepresentable coordinates are
rejected. Intersection predicates use exact rational representations of the
input floats, without coordinate snapping. Reversing the constant panel
preserves its density; reversing the power panel generally does not.

The constant-source integral is analytic. Its far-distance series has an
absolute truncation bound below `1.5e-18` for the normalized log mean.
The power target uses the cubic coordinate `u=t^3/(t^3+(1-t)^3)` with Jacobi
parameters `(2, 3*p-1)` and analytic density normalization. Computed weights
are not divided by their sum. Only the fixed 64/128 comparison is supported;
require both the weight-sum error and normalized refinement error to be at
most `1e-12`. Unresolved near pairs raise `ValueError`, without an adaptive
fallback. `PowerPanelLogResult` retains both means and coarse order 64.

```python
from galerkin.laplace_corner import power_panel_constant_log

pair = power_panel_constant_log(
    [1e-3, 0.], [1e-3, 0.], [1e-3, 0.], .625,
)
print(pair.mean_log_distance, pair.refinement_error)
```

Five independent direct 2D references cover origin/end contact, near parallel
panels and length ratios 4000:1 and 1:4000. Four direct 1D references cover
complex source coordinates. Stored 60/80-digit mpmath results agree to
`1e-30`; runtime reference and transformation checks retain `1e-12`.
The records are `tests/galerkin/two_ground/evidence/power-constant-integrals.json`
and `constant-segment-log.json` in the same directory. Tests also check
analytic density moments, closed-form constant integrals, rotation/reflection,
source reversal, length scaling, one-ULP gap/overlap distinction and actual
near-pair refusal. These primitives do not establish weighted field or
current-loss convergence and do not change existing boundary solvers.

Repeated quadrature requests reuse at most 128 normalized power rules and
128 cubic-coordinate rules per process. Inputs are validated before lookup,
and cached nodes and weights have immutable byte storage. Rule arithmetic,
orders, normalization and convergence gates are unchanged; this bounded
reuse avoids repeated eigensolutions during field assembly.
