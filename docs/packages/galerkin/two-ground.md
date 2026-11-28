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
the smooth remainder, which is interpolated on tensor boxes, except that a
plane-scaled box with fewer panels than the degree integrates it directly
(see below). Interpolation degree is explicitly 10,12,14 or 16
(default12), compared with degree−2. The solver never silently changes a
requested setting.

The grounded planes' current Gram, ∫σᵢσⱼ dx over each plane, is integrated in
physical space. The plane charge density σ of each unit conductor current uses
the closed-form strip Poisson kernel sin(c)E/(H((1−E)²+4E sin²(c/2))), with
E = exp(−π|Δx|/H) and c = πd/H for a panel point at distance d from the plane,
plus every lateral side-wall image whose factor can exceed 1e-30. Panels and x
use Gauss rules of 12 points, compared with 16 points on the same intervals,
under the same 1e-10 entrywise gate as before. Each x interval is 0.75 times
the distance from its start to the nearest singularity of the density
(xs ± i·d over all panel points), so it is at most three times that distance
anywhere in it: intervals are fine only near conductors. Plane totals are the
closed-form zero cosine mode, (1−y/H) and y/H. `ground_modes` is still
admitted (64–4096) but no longer changes the Gram.

A cosine (Parseval) sum, used before, leaves a small entry between two
conductors that hardly overlap on a plane by cancellation, so rounding set its
relative error: the top-plane ground-to-ground entry of a layered coupled
coplanar stripline, about 3e-6 of its Cauchy–Schwarz bound √(GᵢᵢGⱼⱼ), differed
by 1.1e-10 between the two refinements and failed the check. Exact or
compensated sums of the same float64 coefficients reached only 2–3e-11. In
physical space the integrand of that entry is small where it lives, so the
three SIPI layered coplanar striplines now pass at 6–7e-14. The physical-space
Gram agrees with the cosine sum to 1e-12 of its largest entry in the tests, and
on those three sections with an 80-bit extended-precision cosine sum to 8e-14
entrywise; it changed their Gram by at most 9e-16 of the largest entry. It
costs about 2–4 s per section against 0.2 s for the cosine sum.

Lateral side-wall images are summed up to a fixed image count, but an image
is skipped when it cannot change any entry: over a whole target–source block,
|image| ≤ x/(1−x) with x = 2e+e² and e = exp(−πd/H) for the block's nearest
horizontal offset d, and the image is skipped when twice that bound is below
2⁻⁵⁴ times the smallest entry magnitude, where a floating-point sum ignores it.
Results are therefore bit for bit those of the full sum. In wide, low
rectangles most lateral images lie below 1e-24 and are skipped: the layered
coplanar striplines of the SIPI catalog (W/H ≈ 20, up to 42 interpolation
boxes) took 144–213 s before and about a tenth of that after. For the same
reason the degree−2 comparison, which also adds two images, did not test
image truncation in such rectangles: the added images were already below
rounding.

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

On plane-scaled boxes the smooth kernel is reciprocal (Δx changes sign, the
target and source heights swap), so a block between boxes i and j > i+1 is
computed once and its transpose fills the block (j, i). Diagonal blocks and
both orders of each neighbouring pair (j = i+1, the nearest boxes in conductor
and x order) are still computed independently, so the raw reciprocity check
(1e-10) keeps comparing independently interpolated entries where boxes are
closest; it no longer tests the remaining off-diagonal blocks. Tests check that
the kernel is reciprocal to 1e-14 and that the assembled matrix equals the one
with every block computed to 1e-14. On the three SIPI layered coplanar
stripline sections (37–42 boxes, 64 panels per edge, degree 14) this cut a
solve from 9.6–14.1 s to 6.3–10.1 s; capacitance changed by at most 6e-16 and
the current Gram by at most 2e-14 of its largest entry, less than changing the
interpolation degree from 14 to 16 (1e-15 and 3e-14).

A plane-scaled box with fewer panels than the interpolation degree is not
interpolated: the smooth kernel is integrated directly at `degree` Gauss points
per panel, fewer points (panels × degree) than the degree² tensor grid. Grid
and direct boxes combine in any pair, and the degree−2 comparison (1e-10) still
compares two independent rules, degree−2 and degree points per panel or grid
side, so the requested degree is still the only setting. Between two direct
boxes no interpolation is left for the raw reciprocity check to compare: it
then compares only rounding of the same reciprocal integrals. Tests check that
a direct box agrees with a degree-16 interpolated box to 1e-13. On the three
sections (34 of 42 boxes direct in the coupled one) this cut a solve to
3.9–7.2 s, 2.1–2.5 times faster than before both steps; against the solver
before both steps capacitance changed by at most 1.5e-15 and the current Gram
by at most 3e-14 of its largest entry, the size of the change from degree 14
to 16.

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
