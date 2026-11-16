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

### Immutable parametric corner geometry

`galerkin.laplace_corner_geometry.prepare_two_ground_corner_panels` prepares
geometry for an explicit corner basis. Inputs are polygons and rectangle
`width`/`height` in metres. It reuses the existing two-ground convex,
disjoint, interior and side-distance admission and orients polygons CCW.
The even `panels_per_edge` is 16–512. The first four cubic subdivisions at
each end of an edge become one normalized power panel; the edge therefore
has `panels_per_edge-6` actual panels. The total is bounded by 8192.

```python
from galerkin.laplace_corner_geometry import prepare_two_ground_corner_panels

g = prepare_two_ground_corner_panels(
    [[[.0038, .0008], [.0042, .0008], [.0042, .0012], [.0038, .0012]]],
    width=.008, height=.002, panels_per_edge=32,
)
print(g.panel_count, g.lengths_m)
```

`CornerPanelGeometry` returns immutable normalized anchors, small local
starts, directly computed displacement vectors, exponents, conductor owners,
CCW face indices and shared endpoint IDs. Multiply normalized coordinates by
`length_unit_m` for metres. Panel density starts at `anchor+local_start` and
follows its displacement; the singular exponent is `pi/(2*pi-interior_angle)`
at either end of each polygon edge, and 1 on the remaining panels. The
opposite half of an edge uses the same small cubic coordinate from its other
vertex, avoiding subtraction of a number close to one. Short displacement
vectors are not formed by subtracting two large absolute endpoints.

The normalized width/height, derived starts/ends and physical lengths are
also available. Endpoint IDs have meaning within this snapshot. Unresolved
edges, corner exponents or panel lengths fail explicitly. Analytic square,
equilateral and right-triangle angles, polygon coverage/area, length sums,
reflection, scaling and immutable input/output checks verify this geometry.
This function does not assemble a matrix or establish field/current-loss
convergence. Existing constant-panel solvers keep their own panel limits
and defaults; the geometry budget does not enlarge those solver contracts.

### Corner-density half-space matrices

`galerkin.laplace_corner_assembly.assemble_corner_half_space` accepts the
same polygons, metre-valued rectangle dimensions and subdivisions as the
corner geometry factory. It returns that immutable geometry and raw coarse
and fine matrices for the Green kernel
`0.5*log1p(4*y_target*y_source/distance_squared)` above the grounded line
`y=0`. Each source and target uses its normalized power or constant density.
The rectangle bounds admit and normalize the geometry; upper-plane and side
corrections are not part of this primitive.

```python
from galerkin.laplace_corner_assembly import assemble_corner_half_space

half = assemble_corner_half_space(
    [[[.0038, .0008], [.0042, .0008], [.0042, .0012], [.0038, .0012]]],
    width=.008, height=.002, panels_per_edge=16,
)
print(half.matrix.shape, half.quadrature_error, half.reciprocity_error)
```

Constant far interactions use four-term compensated float64 relative
coordinates before adding quadrature motion. This preserves small distances
without relying on a platform's extended floating-point type. Fixed 6/8-point
Gauss rules and the power primitives' own refinement rules produce the two
matrices. Both normalized matrix refinement and raw reciprocity must be at
most `1e-10`; nonfinite or unresolved results raise `ValueError`. The arrays
retain raw reciprocity evidence rather than averaging it away.

Independent 60/80-digit direct two-dimensional integrals cover shared-corner,
separated-power and constant entries, plus a short far-panel cancellation
case. Horizontal translation/reflection, physical scaling, positive Green
energy and immutability supply separate checks. These are integration checks,
not panel/outer convergence or a field-accuracy guarantee. This primitive
does not change existing solvers, their limits or defaults, and does not
establish browser or Windows qualification.

### Bounded dense residuals

`galerkin.dense_residual.bounded_dense_residual(A, x, b)` computes a fresh
float64 array for `b - A @ x` using Dekker high/low product components and
`math.fsum`. It retains product and summation bits that a rounded matrix
product can lose; it does not solve or alter the equation. Inputs are not
mutated, and no extended floating-point dtype is required.

```python
from galerkin.dense_residual import bounded_dense_residual

r = bounded_dense_residual(
    [[1.0, 1.0, 1.0]], [[2.0**53], [1.0], [-2.0**53]], [[0.0]],
)
assert r[0, 0] == -1.0
```

Inputs are real finite values converted to float64 and must be compatible
2D arrays. Matrix rows and columns are 1–8192; right-hand columns are 1–16.
Nonzero matrix and solution magnitudes are bounded by `2**-400` and `2**400`,
inclusive, and right-side magnitudes by `2**900`. These ranges keep splitting
and all nonzero product-expansion intermediates normal and finite; values
outside the contract raise `ValueError`. Row blocks bound temporary storage.
Exact binary rational product/sum references, cancellation cases, column
permutations and inclusive boundary checks verify the arithmetic. An actual
6072-row matrix comparison is recorded separately from small unit cases.
A residual is neither a condition estimate nor a forward-error or field-
convergence certificate. Existing solvers and their checks remain unchanged;
this primitive alone does not qualify a corrected field or another platform.

## Normalized power/constant half-space integral

`galerkin.laplace_half_space.power_constant_half_space(first, second, offset,
exponent, height=...)` averages the bottom-ground Green kernel
`log(image_distance / distance)` over one normalized power target density
`p*u**(p-1)` and one constant source density. It omits the `1/(2*pi)` factor.
The target is `(0,height) + u*first`; the source is
`(0,height) + offset + v*second`, for `u,v` in `[0,1]`. Vectors and height
are in metres. `HalfSpacePanelIntegral` retains immutable `green_mean`,
`coarse_green_mean`, `quadrature_order` and `refinement_error`.

```python
from galerkin.laplace_half_space import power_constant_half_space

mean = power_constant_half_space(
    [0.001, 0.0], [0.001, 0.0], [0.001, 0.0], 0.625, height=0.002,
)
assert mean.refinement_error <= 1e-12
```

The exponent must lie in `(0.5,1]`, the length ratio must not exceed `1e6`,
and all endpoints must be above ground. Segments may be disjoint or touch
at endpoints; exact binary-input topology refuses overlap and interior
intersections without snapping. The largest length, offset/image norm or
start height defines a scale: each panel length and endpoint height must
be at least `128*binary64_epsilon` times that scale. Non-real, nonfinite
or unrepresentable inputs are refused.

The constant source is integrated analytically. Fixed target orders 64/128
must agree within `1e-12*max(1,abs(fine))`; each rule's mass must be within
`1e-12` of one. The exact zeroth moment is separated as
`f(0) + sum(w*(f(u)-f(0)))`, without rescaling any weights. Far image/source
logarithms share a stable log-ratio and bounded series difference. A zero
or negative mean from cancellation is refused because the exact Green
kernel is strictly positive here. There is no fallback, clipping or
relative-accuracy guarantee for a small mean.

Six stored direct two-dimensional mpmath 1.3.0 (BSD-3-Clause) references,
each agreeing at 60/80 decimal digits, cover endpoint contact, near and
oblique panels and length ratios of 4000 in both directions. Reflection,
source reversal, physical scaling, constant-density reciprocity, ground
translation, unchanged weights and input refusal are checked separately.
These are primitive integration checks, not a complete field solution,
mesh/outer convergence, another platform or a physical measurement.

## Hierarchical linear modes on a power panel

`power_panel_linear_gram(length, exponent)` and
`power_panel_linear_self_log(length, exponent)` in `galerkin.laplace_corner`
return immutable 2-by-2 matrices for two modes on one panel. With `h=length`,
`u=s/h` and `p=exponent`, define

- `phi0 = p/h * u**(p-1)`, of integrated mass one;
- `phi1 = sqrt(p*(p+2)) * ((p+1)/h*u**p - phi0)`, of integrated mass zero.

Rows and columns follow `[phi0, phi1]`. Require finite positive `h` in metres
and `p` in `(0.5,1]`; both modes then have finite squared current. The Gram
entries have units `1/metre`; the self integral uses
`log(abs(s-t) / 1 metre)` and is dimensionless. Only self entry 00 depends on
`log(h)`, since the other mode has zero mass. Shared digamma and length terms
are canceled analytically before evaluation. Unrepresentable Gram entries
are refused. Close to `p=0.5`, the current Gram becomes poorly conditioned;
finite entries alone do not certify the accuracy of a cancelling quadratic
form or a field solution.

For `p=1`, the modes are the normalized constant and first shifted Legendre
mode: the Gram is `I/h`, and the self matrix is
`[[log(h)-1.5, 0], [0, -0.75]]`. The old scalar functions supply entry 00
unchanged. The other entries do not alter the existing constant/power basis
or any solver. Inter-panel interactions and a complete linear Galerkin
field model require separate implementation and validation.

Independent direct 1D squared-density and 2D Duffy log integrals at 60/80
digits (mpmath 1.3.0, BSD-3-Clause) cover five exponents including `0.5001`
and the uniform limit. Tests retain exact uniform zero cross terms, compare
nonzero reference entries without a denominator floor, check physical
scaling, positive Gram energy, mode moments and exact uniform subdivision.

## Explicit all-active corner field between two grounds

`galerkin.laplace_two_ground.solve_two_ground_corner_rectangle_edges` is a
separate homogeneous static solver for **one or two all-active convex
conductors**. It returns the existing immutable `TwoGroundRectangleEdgesResult`
contract: dimensionless capacitance/permittivity, straight-edge current Gram
in `1/metre`, signed unit-current integrals, and separate bottom/top grounds.
It does not replace an existing solver or add a fixed-ground conductor selector.

```python
from galerkin.laplace_two_ground import solve_two_ground_corner_rectangle_edges

result = solve_two_ground_corner_rectangle_edges(
    [[[0.00385, 0.0008], [0.00445, 0.0008],
      [0.00445, 0.00087], [0.00385, 0.00087]]],
    width=0.008, height=0.002, panels_per_edge=128, ground_modes=256,
)
```

The rectangle has Dirichlet bottom/top grounds and Neumann side walls.
The original convex/disjoint/interior admission and cluster-clearance rules
apply. Even subdivisions `16..512` merge four cubic intervals at each end
into a corner-power panel, leaving `n-6` panels per edge and at most 4096
panels. Corner powers are `pi/(2*pi-interior_angle)`; other panels are constant.
The analytic density Gram retains the integrable corner singularity.

Local relative coordinates, stable near-source integration, exact constant
moments and bounded vectorized pairs form the bottom-ground matrix. The
smooth upper/side correction uses degrees 20/24; `interpolation_degree` must
be 24. Two fixed compensated residual corrections precede current
normalization and direct per-edge/whole Gram products. No quadrature weight
rescaling or diagonal floor is used. `ground_modes` is the **actual fine count**,
even `64..4096`, compared with half that count, with power quadrature 16/32;
this differs from the original solver's coarse-count convention. Numerical
refinement, reciprocity, energy, conservation, partition and PSD checks use
`1e-10`, with condition bound below `1e10`; unresolved cases raise `ValueError`.
These checks do not establish panel or outer convergence for a new geometry.

Two independent scikit-fem 12.0.2 (BSD-3-Clause, unshipped) P3 volume-energy
references per case use exact triangle-bubble condensation, two interior
velocity extensions and quadrature 8/10. A parallel-plate analytical anchor
checks capacitance and shape-current Gram at `1e-10`. Stored references and
provenance are in `tests/galerkin/two_ground/evidence/corner-field-*.json`;
replay tests do not rerun the independent solver. All comparisons retain each
nonzero entry, including small signed cross terms.

| Selected case, 8 by 2 mm domain | Independent reference DOFs | Last panel whole change | Whole reflection change | Fine reference whole difference |
|---|---:|---:|---:|---:|
| One offset rectangle | 265878 / 422727 | 0.009256% | 6.98e-16 | 0.006748% |
| Unequal tapered pair | 746444 / 914228 | 0.098622% | 2.12e-11 | 0.265163% |

The declared gates are: reference mesh and final panel `256→512` change
`1%`, each outer width `8→16→32 mm` change `1%`, capacitance reference
`0.05%`, edge reference `2%`, whole reference `1%`, and reflection `1e-10`.
Outer cases use 256/512/1024 fine Fourier modes respectively. The pair's
prior 441197→746444-DOF reference failed the 1% whole-mesh gate at 1.127808%;
that failure remains distinct from the later qualified mesh pair.

This is bounded numerical evidence, not general accuracy or measurement
qualification. A three-active-conductor reference failed whole-mesh convergence;
a two-signal plus fixed-ground case failed whole reflection. Neither is in
this solver's supported scope. Heterogeneous interface corners, finite-metal
diffusion, material laws, other platforms and browser memory limits require
separate work. The implementation helpers are internal package modules.

## Hierarchical linear far interactions

`galerkin.laplace_corner.power_panel_linear_far_log` returns immutable fine/coarse
2×2 log-distance blocks for the same `phi0` and `phi1` as the linear self/Gram
primitives. The first panel starts at zero and the second at the explicit offset;
vector lengths are metres. Exponents must lie in (0.5,1], length ratio at most64,
and the origin offset must be at least four times the sum of panel lengths.
This is a bounded far-interaction primitive; near/touching blocks and a full
linear current solver remain outside its scope.

Analytic mode masses are [1,0]. Centered `log1p` differences avoid carrying
`log(scale)` into zero-mass rows or columns; physical quadrature weights are
not rescaled. Orders n/2n (n=4..64) must agree entrywise within
1e-12*max(1,abs(fine)), a dimensionless quadrature criterion. Only entry00
changes by log(scale) under common geometric scaling. Exchange transposes the
block. Neither identity establishes current-field convergence.

Eight independent 100-term complex Taylor references use analytic moments
mu0(r)=p/(p+r), mu1(r)=sqrt(p(p+2))*r/((p+r)*(p+r+1)), mpmath1.3.0 at60/80 digits,
and tail bound16*rho^101/(101*(1-rho)) for rho<=1/4. The reference tool is unshipped.
References include unequal exponents/lengths, endpoint powers and orientations;
structural tests retain admission, immutability, exchange, reflection and scaling.
Existing constant-power, half-space and field paths remain unchanged.

## Hierarchical linear shared-vertex interactions

`power_panel_linear_shared_vertex_log` uses the same two modes and immutable
fine/coarse block result as the far primitive. Both vectors start at the shared
origin, are measured in metres and must define nonoverlapping rays. The length
ratio is at most64 and each exponent lies in(0.5,1]. This complements the self
and far blocks; disjoint near-panel interactions and a full linear field solver
remain separate work.

For r,s in{0,1}, the Duffy split yields the weighted moment after scaling the
vectors by their maximum length:

`J_rs - M*log(scale) = (p*E_q[v^s*log|a-v*b|] + q*E_p[u^r*log|u*a-b|] - M)/T`,
where `T=p+q+r+s` and `M=p*q/((p+r)*(q+s))`.

The radial logarithm is integrated analytically. The normalized Gauss-Jacobi
rules integrate the remaining angular functions without computed-mass
normalization. Apply the two mode polynomials to the four moments and add
log(scale) only to00, using analytic masses[1,0]. Each n/2n pair (n=4..64) must
meet the same dimensionless1e-12*max(1,abs(fine)) entrywise quadrature criterion.
A geometrically admissible input can be unresolved at a requested order;
there is no automatic retry or fallback. The retained length-ratio64 example
fails at32/64 and passes when the caller explicitly selects64/128.

The equal opposite collinear p=q=1 case has independent closed form
`[[log(h)+2log(2)-3/2, 2sqrt(3)*(1-log(2))/3], [same, 5/4-2log(2)]]`.
Six stored60/80-digit adaptive angular references also check unequal powers,
lengths and angles. They share the mathematical Duffy split but use adaptive
integration rather than this finite Gauss-Jacobi implementation; they are not
an independent full-field solver. Exchange, reflection, geometric scaling,
constant-mode compatibility and immutable results are checked separately.
No current-solver defaults, physical geometry or existing acceptance gates change.

### Reproducible linear-block reference provenance

The [far record](../../../tests/galerkin/reference_values/mpmath/linear_far_log.json)
and [shared-vertex record](../../../tests/galerkin/reference_values/mpmath/linear_vertex_log.json)
use the stored-reference v1 contract. Their explicit consumer builds inputs from
those records and verifies that every binary64 value equals the original raw
fixture before applying its unchanged dimensionless primitive criterion.
The original fixtures, tests and requested-order refusals remain unchanged.

The adjacent hash-pinned mpmath 1.3.0 requirements are for reference reproduction
only, not a runtime dependency. Its unmodified BSD-3-Clause wheel runs in a
separate environment without loading product modules. The compare-only script
recomputes all entries at 60 and 80 decimal digits, prints per-array differences
and removes temporary output; it cannot overwrite a fixture. From the repository
root in that reference environment, run:

```bash
python tests/galerkin/reference_values/mpmath/compare_linear_logs.py far
python tests/galerkin/reference_values/mpmath/compare_linear_logs.py vertex
```

The new records describe the measured reproduction, not the original generation
time. Uncaptured CPU model, compilation time and resident memory remain null
with reasons. A stored consumer reports no current reference execution time.
These are mathematical primitive comparisons: the vertex reference shares the
Duffy identity, and neither record establishes field convergence, physical
accuracy or support on another platform.

### Separated hierarchical linear-power blocks

`power_panel_linear_separated_log(first, second, offset, p, q,
quadrature_order=32)` covers two disjoint segments with minimum separation at
least half the longer length, powers in(0.5,1] and length ratio at most64.
The first segment runs from zero to `first`; the second from `offset` to
`offset+second`, in metres. Normalized directions must remain representable.
This is an explicit additional API, with the same immutable fine/coarse 2x2
result and physical modes as the self, vertex and far blocks. It does not
replace their admission rules or choose methods automatically.

Each zero-mass mode uses an anchored logarithmic difference. For base vector b
and increment d, evaluate the log-distance difference through
`log1p((2*b.dot(d)+d.dot(d))/(|b|*(|b+d|+|b|)))`.
The mixed block subtracts the corresponding single-variable anchor before
integration. Physical quadrature weights are unchanged; analytic masses[1,0]
place log(scale) only in00. Explicit n/2n rules, n=4..64, retain the dimensionless
entrywise1e-12*max(1,abs(fine)) comparison; an unresolved requested order raises
without retries. Segments closer than the stated limit and touching at other
endpoints still need separate contracts.

For parallel equal unit-power segments separated by h times their length,
independent difference-coordinate convolution gives
`I00=log(length)+J0-J1`, `I01=I10=0`, `I11=J0-3*J1+2*J3`, where
`Jk=integral_0^1 t^k*log(t^2+h^2) dt`. Closed antiderivatives for k=0,1,3
check h=.5/1/2 and lengths2^-15/1/2^15.
The [stored direct-integral record](../../../tests/galerkin/reference_values/mpmath/linear_separated_log.json)
checks five unequal-power, length and angle cases. Its mpmath1.3.0 implementation
uses direct tensor Gauss-Jacobi integration at48/64 points and60/80 digits:
it shares the Gaussian family but does not use product centering or import
product code. Order agreement below1e-25 and precision agreement below1e-45
are reference self-checks, not field-convergence evidence. The adjacent
compare-only generator and hash-pinned requirements reproduce all five arrays.

Exchange, signed-axis transformations, physical scaling, constant-mode
compatibility, overlap with the far API, immutable outputs and explicit refusal
are checked separately. These primitive blocks do not yet supply a full linear
boundary field solver, current partition or validated fixed-ground adapter.

### Linear power/constant endpoint interactions

`power_panel_linear_constant_log(a, b, offset, exponent)` provides a 2x2 block
between a power target and a unit-power source. The target runs from zero to a,
the source from offset to offset+b, in planar metres. Each has two physical
modes; source modes are1 andsqrt(3)*(2v-1) in normalized coordinates. Target
powers lie in(0.5,1], length ratio is at most1e6. Exact binary-input topology
admits disjoint panels and common endpoints, refusing overlap and interior
crossings. Normalized directions and source coordinates must remain representable.
Self interactions use the separate exact self API.

The source's first polynomial moment is
`F(z)=Re[z+1/2-z*(z+1)*(log(z+1)-log(z))]`, with F(0)=1/2 and F(-1)=-1/2.
For |z|>2,48 terms of
`sum_k>=1 (-1)^(k+1)/((k+1)*(k+2)*z^k)` avoid cancellation; the omitted
absolute tail is below1.5e-18. Multiply bysqrt(3) for the physical source mode.
The existing exact constant-source logarithmic integral supplies mode0.

Fixed cubic-coordinate64/128 rules integrate the target. Analytic masses[1,0]
place log(source_length) only in00; subtract the source moment at the target
origin before integrating each zero-mass target mode. Computed quadrature
weights are never renormalized. Target mass errors and each normalized
fine/coarse difference retain their1e-12 primitive criteria. Short sources
opposite target interiors can remain unresolved: the registered target[0,1],
source starting at(.5,.001) with lengths1/64,1e-3 or1e-4 is refused. No retry
or implication of universal near-interaction accuracy is provided.

The [stored adaptive record](../../../tests/galerkin/reference_values/mpmath/linear_power_constant_log.json)
checks11 source first moments by direct80-digit quadrature and7 full blocks
at60/80 digits. The source identity is shared mathematics; the full reference
uses separate adaptive target integration after flattening the power measure.
Its initial unsplit source quadrature at z=-.3+.01j failed the1e-50 identity
criterion; splitting around the closest projected point resolved it without
changing that criterion. The compare-only generator preserves this history and
requires the adjacent hash-pinned mpmath1.3.0 environment.

Source reversal changes the sign of only the source's linear mode. Target
reversal has the analogous rule only for unit target power; reversing a general
power panel would move its singularity and is not an equivalent input.
Independent endpoint identities, shared-vertex/far overlaps, constant-mode
compatibility, signed-coordinate transformations, scaling, reciprocity for
unit powers, immutable outputs and unresolved-input refusal are tested.
No full linear field assembly, fixed-ground accuracy or platform support follows
from these primitive checks.

### Self and squared-density reference provenance

The [stored self/Gram record](../../../tests/galerkin/reference_values/mpmath/linear_self_gram.json)
reproduces the original five power/length cases with direct density-removed
Gram and Duffy self-log integrals at60/80 digits. All ten binary64 arrays equal
the original raw fixture, including its tiny nonzero uniform cross moments.
The consumer retains strict1e-12 nonzero-entry relative comparisons and the
original exact uniform-mode zeros with the1e-30 reference cross-moment check.
It introduces no denominator floor or numeric clipping. The adjacent compare-
only generator uses the same hash-pinned mpmath1.3.0 reference environment.
The new receipt measures only this reproduction; uncaptured CPU/RSS/compile
metadata remain null. No runtime, raw fixture, old test or criterion changes.

### Partitioned mixed linear-power blocks

`galerkin.laplace_corner_partitioned.power_panel_linear_constant_log_partitioned`
is an explicit alternative for a power target and unit-power source, each with
constant-mass and zero-mass linear modes. It keeps the existing `(0.5, 1]`
exponent range, length ratio at most1e6, and exact binary-input intersection
admission. It does not retry the unpartitioned method or change that method.

Source endpoint projections select integration cuts in the target parameter.
Dyadic distance cuts and upper/lower<=2 grading away from the singular origin
limit density variation. At most128 subintervals use fixed64/128 double-ended
cubic rules; the first interval integrates the exact power measure, and other
intervals retain the physical power density. No geometry, physical weights or
returned moments are normalized, snapped or clipped. Analytic masses[1,0] and
entrywise coarse/fine differences retain1e-12 checks; an over-budget or
unresolved interaction fails explicitly. Result fields include immutable
`mean_log_distance`, `coarse_mean_log_distance`, `quadrature_order`,
`subintervals`, and `mass_error`.

The [stored adaptive reference](../../../tests/galerkin/reference_values/mpmath/linear_partitioned_log.json)
contains two admitted assembly interactions and nine localized short-source
cases. Separate mpmath1.3.0/BSD-3-Clause generation uses a flattened target
coordinate with adaptive integration at60/80 digits, not the product dyadic
partition. Exact source identities share mathematics, and the first two inputs
come from product geometry. The adjacent compare-only generator preserves the
record; unknown generation costs remain explicit. Existing unpartitioned
refusals, raw fixtures, tolerances and solvers remain unchanged. This primitive
does not establish full-field convergence or other-platform accuracy.
