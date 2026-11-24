# Two-ground homogeneous boundary solver

[한국어](../../locales/ko/pages/packages/galerkin/two-ground.md)

`galerkin.laplace_two_ground.solve_two_ground_rectangle` is an explicit shared
Laplace capability. The existing bottom-ground solver and its defaults remain
unchanged. Consumer material laws and adoption are separate contracts.

```python
from galerkin.laplace_two_ground import solve_two_ground_rectangle

result = solve_two_ground_rectangle(
    [[[0.0038, 0.000975], [0.0042, 0.000975],
      [0.0042, 0.001025], [0.0038, 0.001025]]],
    width=0.008, height=0.002, panels_per_edge=64,
    ground_modes=128, interpolation_degree=12,
)
```

Coordinates are metres. Top and bottom potentials are zero; side normal flux is
zero. The medium must be homogeneous and isotropic. The result contains the
capacitance matrix divided by absolute permittivity (dimensionless), a current
Gram matrix for each surface (1/metre), and signed integrated currents. Surface
order is the input conductors followed by bottom and top ground. Each column has
unit integrated current on its corresponding signal; the sum over all surfaces
is zero. Ground currents are separately available, including for asymmetric
vertical placements. Arrays own immutable bytes; their write flags cannot be
re-enabled.

The API admits 1–16 strictly convex, disjoint, closed, finite-thickness polygons
strictly inside a rectangle with width/height in [0.25,64] (the corner solvers that reuse this
admission keep [0.25,16]). A conductor cluster
closer to a side wall than its extent is interpolated on boxes scaled to each
conductor's distance from the planes and side walls (at most 256, else refused
before a field solve). It uses at most 2048 total panels,
with 1–256 cubic-graded panels per polygon edge. Touching, nested, concave,
zero-thickness and unresolved edges are rejected. The admission bounds do not
establish numerical convergence everywhere within them.

The method is a constant Galerkin boundary discretization of the homogeneous
Laplace Green function: a two-Dirichlet-plane strip plus reflected lateral
images for Neumann sides. Exact singular half-space integrals are combined with
a smooth tensor interpolant. Ground normal flux uses an independent harmonic
expansion and cosine orthogonality. Interpolation degree is explicitly 10,12,14
or 16 (default12), compared with degree−2. Ground modes are explicitly 64–4096
(default128), compared with twice that count and higher quadrature. The solver
never silently changes a requested setting.

The smooth part is first interpolated on one box around every conductor. When
that degree−2 comparison exceeds 1e-10, the same comparison is repeated once,
with the same degree, panels and quadrature, on boxes that split each conductor
into equal x intervals no wider than its distance to the nearest plane or side wall. One wide
box converges slowly for coupled, layered and broadside striplines because the
plane images lie close to it. The result then reports
`smooth_interpolation_boxes` (>1) and the failed `single_box_matrix_error`;
otherwise these are 1 and None, and the calculation is unchanged bit for bit.
A box of zero extent, or a repeated comparison above 1e-10, is refused. With
typical inputs this admitted all ten coupled, layered and broadside stripline
templates of the SIPI catalog that previously failed this check.

Internal matrix, reciprocity, residual, energy, current-conservation and ground
refinement checks retain a 1e-10 gate. The matrix condition bound must be below
1e10, and current Gram matrices must be positive semidefinite within the same
scaled numerical gate. These checks reject unresolved calculations; they do not
replace panel refinement, outer-boundary studies, material-model validation or
measurements. No metal, frequency, roughness or transmission-line law is included.

The retained research evidence covers a centered pair, an offset scalar,
an asymmetric pair and a closer pair, with 64/128/256 panels per edge and
independent P4 volume comparisons. The asymmetric pair needs explicit degree14;
its original degree12 failure is preserved. The centered pair also has finite
8/16/32mm width comparisons at 2mm height. The 16/32mm independent references
use the previously validated coarse P4 mesh; they are not new fine-mesh reference
studies. Saved-reference tests replay recorded values and state that the
independent solver is not rerun by those tests. Original failed coarser studies
remain preserved. These finite comparisons are not absolute-accuracy or general
geometry qualifications. There are no new Windows, browser or executable claims.

This addition extends the Apache-2.0 galerkin baseline
625d9f74ca253538f172a42272c869b66d144eed, retaining its LICENSE and NOTICE. It adds
one runtime module with no new dependency; NumPy, SciPy and array-api-compat
remain the declared runtime dependencies. Tests use pytest and the existing
BSD-3-Clause scikit-fem reference tool. Exact installed versions, wheel hashes,
source identity and license payloads belong to the accompanying validation
record. A repeated 0.0.2 version does not identify this candidate.

Run `python -m pytest -q tests/galerkin/two_ground` from the repository root.
The stored data and reference identifiers are in that directory under `evidence/`.
Source and installed-wheel checks must retain the exact artifact identity;
one platform does not establish another platform.

The separate [straight-edge API](two-ground-edges.md) exposes conductor-edge
current factors while retaining this whole-surface result.

The [private compact geometry](laplace_corner_compact_geometry.md) has independent partition checks and does not change any existing field solver.

[Explicit three-active corner-harmonic fields](laplace_corner_harmonic_field.md) preserve separate controls and finite comparison evidence.
