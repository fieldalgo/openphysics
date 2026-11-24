# Homogeneous boundary panels with no grounded wall

[한국어](../../locales/ko/pages/packages/galerkin/open-box.md)

`galerkin.laplace_open_box.solve_open_rectangle` solves constant-potential,
closed conductors in a homogeneous rectangle whose four walls all have zero
normal flux. There is no grounded plane: the conductors listed in `grounds` are
held at zero potential and carry the whole return current, as in an unbacked
coplanar line. The [grounded-bottom](laplace_boundary.md) and
[two-ground](two-ground.md) solvers and their results are unchanged.

```python
import numpy as np
from galerkin.laplace_open_box import solve_open_rectangle

def strip(x0, x1, y0=2.2e-3, y1=2.235e-3):
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])

result = solve_open_rectangle(
    [strip(1.85e-3, 2.15e-3), strip(.65e-3, 1.65e-3), strip(2.35e-3, 3.35e-3)],
    width=4e-3, height=4.235e-3, grounds=[1, 2], panels_per_edge=64,
)
print(result.capacitance_per_permittivity)
```

Coordinates are metres; the medium must be homogeneous and isotropic.

| Input | Contract |
|---|---|
| `polygons` | 1–16 finite, disjoint, strictly convex closed polygons strictly inside the rectangle (the [two-ground](two-ground.md) polygon admission). |
| `width`, `height` | Finite positive; width/height in `[0.25,16]`. |
| `grounds` | Indices of the zero-potential conductors: at least one, distinct, and at least one conductor left as a signal. Required; there is no default. |
| `panels_per_edge` | Integer 1–256, default 32, at most 2048 panels in total, cubic endpoint grading. |
| `interpolation_degree` | 10, 12, 14 or 16 (default 12), compared with degree−2. No automatic change. |

`OpenRectangleResult` holds immutable snapshots:

| Field | Meaning |
|---|---|
| `capacitance_per_permittivity` | `(s,s)` signal charge per signal voltage divided by permittivity, every ground at zero voltage. |
| `current_gram` | `(n,s,s)` in 1/m, one matrix per input conductor: surface integral of `j_i*j_j` for unit integrated current on signal `i`. |
| `current_integrals` | `(n,s)`: identity on the signals; the grounds share minus one. Walls carry no current. |
| `signal_indices`, `ground_indices` | Input positions of the signals and grounds. |

The method is a constant Galerkin boundary discretization. The Green function
of the rectangle with zero normal flux on all walls (the Neumann function) is
assembled in closed form: a strip periodic over twice the height, with images
at `y'` and `−y'` (horizontal walls), plus mirrored copies at `2nW ± x'` (side
walls). The free-space logarithm is integrated exactly on near panel pairs, and
only the smooth remainder is interpolated on tensor boxes. A cluster closer to
any wall than its extent uses boxes no wider than each conductor's distance to
the nearest wall (at most 256; closer conductors are refused before a field
solve), and `smooth_interpolation_boxes` reports their number.

A closed Neumann rectangle holds zero total charge. The kernel is therefore
defined only up to terms `f(r)+f(r')`, which change the common potential but not
the charges. The far-field linear growth of every image is such a term and is
omitted. The system is solved on the zero-sum subspace (a Householder basis and
a Cholesky factorization), with the common potential recovered afterwards. A
test adds such a term and checks that the solution is unchanged.

The matrix refinement, raw reciprocity, residual, charge-sum, energy and
current-conservation checks use 1e-10. The reduced condition bound must be
below 1e10, and the current Gram matrices must be positive semidefinite. These
checks refuse unresolved calculations. They do not establish panel or
outer-box convergence, which callers must check for their own geometry.

Validation in `tests/galerkin/test_laplace_open_box.py`, against references
that do not use this implementation:

- The kernel matches an independent x-cosine series to 1e-12, after removing
  terms that zero total charge cannot observe, at width/height 1, 4, 1/4 and 16.
  A neutral pair has zero normal derivative on every wall, and the flux around
  a source is −2π.
- Two circular wires with a/d = 0.2: the error falls monotonically as the box
  grows, below 1e-3 at a box 4 times the default. Extrapolating both the box
  error (~1/L²) and the polygon error (~1/n²) recovers π/acosh(d/2a) within 1e-6
  (8.3e-8 observed).
- Thin wires next to one wall and in a corner match their image charges within
  2e-4 on wall-scaled boxes.
- An unbacked coplanar line matches a scikit-fem P2 volume solution in the same
  box within 1e-3 on corner-graded meshes; the difference falls with refinement
  (3.0e-4, 1.3e-4, 5.4e-5 on Linux).

The test file also covers panel refinement, symmetric return currents, coupled
reciprocity and the refusals. The research study also compared the three SIPI
unbacked coplanar templates with P2, at 1.1e-4 and 4.3e-5 on two meshes. These
finite comparisons are not general accuracy qualifications. No metal,
frequency, roughness or transmission-line law is included.

This adds one runtime module and no dependency. Tests use the existing
BSD-3-Clause scikit-fem reference tool and meshine. Run
`python -m pytest -q tests/galerkin/test_laplace_open_box.py` from the
repository root. One platform does not establish another.
