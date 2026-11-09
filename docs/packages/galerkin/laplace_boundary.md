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

The implementation compares degree/order 8/6 with 10/8 and an extended image
sum. The image count follows the rectangle aspect ratio. Ground truncation is
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
