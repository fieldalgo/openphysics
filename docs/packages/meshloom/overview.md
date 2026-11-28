# meshloom — tetrahedral meshing with an exact-arithmetic compiled kernel

**English** | [한국어](../../locales/ko/pages/packages/meshloom/overview.md)

[Documentation home](../../README.md)

**Status: first mesher, not yet accepted.** meshloom is OpenPhysics's general
tetrahedral mesher for multi-material piecewise-linear inputs: constrained Delaunay
tetrahedralization with exact predicates, boundary recovery, quality refinement and
(later) mesh improvement, in a compiled Rust kernel. `meshloom.generate3d` meshes a
piecewise-linear complex to a size `h` (one number, one per named region, or a function
of position) with a radius-edge bound: `quality="practical"` (the default, `PRACTICAL_RATIO` = 1.4) or
`quality="guaranteed"` (`GUARANTEED_RATIO` = 2, the bound V7 grades), then improves
the mesh (sliver removal, smoothing and flips). `meshloom.builder` adds curved
primitives (spheres, cylinder vias), sampled on their surfaces. The quality gates
measured so far pass, V10 on all 15 of its pairs included, but meshloom has no
refinement on curved surfaces yet, and it is slower than the baseline (see Limits).
Closed triangle surfaces (STL-like inputs) are **experimental** (see Limits).

```python
import numpy as np
import meshloom

points = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                   [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=float)
facets = [[[0, 3, 2, 1]], [[4, 5, 6, 7]], [[0, 1, 5, 4]],
          [[2, 3, 7, 6]], [[1, 2, 6, 5]], [[0, 4, 7, 3]]]
mesh = meshloom.generate3d(points, facets, h=0.1)
mesh["nodes"], mesh["tetrahedra"], mesh["boundary_faces"]   # the output contract
```

A graded size is a function from an (n, 3) float64 array of points to n sizes > 0:

```python
centre = np.array([0.5, 0.5, 0.5])
h = lambda x: np.minimum(0.2, 0.02 + 0.3 * np.linalg.norm(x - centre, axis=1))
mesh = meshloom.generate3d(points, facets, h=h)   # V8's graded cube
```

- **Sampled once.** Before refinement, the function is sampled on a background octree
  over the cube that holds the input points. A cell is split while its edge exceeds
  the smallest size sampled at its corners and centre (`meshloom._core.SIZE_CELL` = 1),
  up to 4,000,000 cells (`SIZE_MAX_CELLS`, 72 bytes each). Refinement then reads the
  octree, by trilinear interpolation, and never calls Python.
- **Where it is read.** At each tetrahedron's and subfacet's circumcentre and each
  subsegment's midpoint: a tetrahedron is split when its circumradius exceeds
  `alpha` times the size there. Points outside the cube read its nearest face.
- **What it misses.** A change of the size function narrower than the cells that
  sample it, and so narrower than the sizes there, can be missed.
- **Errors.** A function that returns the wrong shape or a size that is not finite and
  > 0, or that needs more cells than the cap, raises `ValueError`. A constant function
  meshes exactly as the number does; a number or a mapping meshes exactly as before.

Curved inputs come from `meshloom.builder`. Each builder returns the keyword arguments
of `generate3d`: `sphere(h)` (C1), `nested_spheres(h, radii=..., names=...)` (C11; a None
name leaves a hole), `sphere_in_box(h)` (C5) and `via_in_slab(h)` (C4, a z-axis cylinder
through a slab).

```python
from meshloom import builder

mesh = meshloom.generate3d(h=0.1, **builder.via_in_slab(0.1, radius=0.3))
mesh["region_names"]           # ['via', 'slab']
```

- **Sampling.** A sphere is a geodesic subdivision of the icosahedron, a cylinder a
  stack of rings rotated by half a step. Both use surface edges of about h
  (`builder.SURFACE_EDGE` = 1).
- **Points.** Each point is `c + R·q/‖q‖`, computed with +, −, ×, ÷ and √ only, so the
  points are the same on every platform and lie on the surface to rounding (V5: at most
  1e-15, at most 2.5e-16 measured on C1, C4, C5 and C11).
- **Locked facets.** The curved triangles are passed as `locked_facets`: the mesher adds
  no point on them or on their edges. Recovery needs none there, because the triangles
  are strictly Delaunay on their surface. Where recovery would need one (a locked
  surface whose triangles are not Delaunay faces), the point is moved into the domain
  instead, and the mesh never has a node off the surface; where that fails, meshing
  raises `RecoveryError`.
- **Planar facets.** The box faces and the via's end disks are refined as usual.

A closed triangle surface (an STL-like input: points and triangles, with a tag per
triangle) goes through `builder.triangle_surface(points, triangles, tags=...,
region_points=...)`. **Experimental:** the 3D plan's import gate (V20, on the Thingi10K
population C14) was not evaluated at milestone M4. The readiness check run before the gate
fell short, so the gated run is recorded as not evaluated, which never counts as passed, and
M4 covers the builder's inputs only. Meshing such inputs can fail or exceed the plan's time
limits on real files. Version 1 supports polyhedral inputs and the builder's primitives;
closed-surface import is gated again at M8, and V20 and the other C14 rows stay reported.
- **What it joins.** Two triangles are joined into one polygon facet when they:
  - share an edge that no other triangle uses;
  - carry the same tag;
  - lie exactly in one plane (exact `orient3d` = 0 on the doubles, with no tolerance).

  A joined patch becomes one facet: its outer loop first, then its holes.
- **What it leaves.** These stay triangles:
  - degenerate triangles;
  - a patch whose boundary passes through a vertex twice;
  - a patch with a vertex inside it that a triangle outside it uses.

  Points that no facet uses any more are dropped.
- **Why.** Given one facet per triangle, every triangle edge becomes a segment that
  refinement keeps and splits, and small angles between triangles of one plane cascade
  (see the limits).
- **Not for checks that keep the input triangles.** The output drops the vertices
  inside a patch, and its boundary faces cross the input triangles' edges. So it does
  not keep every input vertex, nor tile each input triangle with its own boundary faces.
  Do not use it for the C14 runs of the 3D plan (V20, V36, V37).
- **Float32 files.** A float32 STL's slanted faces are rarely exactly planar in doubles
  and stay triangles. Axis-aligned faces join.

Errors are typed `ValueError` subclasses exported by the package (`InvalidPLC` with a
witness, `NotClosed`, `RecoveryError`, `RefineError`, `RoundingError`, `RegionError`,
`MeshError`). `meshloom.kernel_available()` and `meshloom.kernel_version()` report the
compiled kernel. The criteria meshloom is accepted by are fixed in advance in the
[pre-registered 3D validation plan](../meshine/validation3d.md). Until it passes them,
[`meshine.extrude`](../meshine/overview.md#layered-tetrahedral-meshes) (layered
geometry) and Gmsh through [`gmshio`](../gmshio/overview.md) stay the tested routes.

## Kernel building blocks

`meshloom._core` wraps the first kernel stages for tests and benchmarks. Its
names may change before the mesher's public API.

- **Exact predicates.** `predicate_signs(kind, coords, ids=None)` returns exact
  signs of `orient3d(a, b, c, d) = det[b − a, c − a, d − a]`, `insphere` (positive
  when e is inside the sphere through a positively oriented a, b, c, d), its
  symbolically perturbed form `insphere_sos`, and `incircle3d` (positive when
  coplanar d is inside the circle through a, b, c, computed in 3D without
  projecting). A floating-point filter with Shewchuk's error bounds decides most
  cases; the rest are evaluated exactly with floating-point expansions.
  Coordinates must be 0 or between 2⁻¹²⁰ and 2¹²⁰ in magnitude, where the exact
  evaluation cannot underflow or overflow; others are refused with `ValueError`.
- **Delaunay tetrahedralization.** `delaunay(points, order=None)` returns
  positively oriented tetrahedra, for each point the index of the equal point that
  became the vertex (the lowest index), and kernel counters. Cospherical ties are
  broken by a symbolic perturbation ordered by point index, so the result depends on
  the points and their indices, not on the insertion order. Points are inserted by
  Bowyer–Watson in a biased randomized order with Hilbert rounds.
- **Verifier.** `verify_delaunay(points, tetrahedra)` checks from the arrays alone,
  with exact predicates, that every tetrahedron is positive, every interior face is
  locally Delaunay under the perturbation, the hull is locally convex, the Euler
  characteristic is 1 and every distinct point is a vertex.

- **Planar facets and PLC checks.** `triangulate_facet(points, loops)` triangulates
  one planar facet (outer loop, then holes, combined by the even-odd rule) by
  constrained Delaunay triangulation. It refuses points off the plane and loops that
  intersect. Orientation inside the plane is exact after dropping a coordinate.
  Circle tests use the facet's own metric (`incircle_plane`, exact without projecting
  circles), with ties broken by the same index-ordered perturbation as in 3D.
  `check_plc(points, segments, facets)` checks a whole piecewise linear complex
  exactly: distinct points in the kernel's range, planar facets with simple loops, and
  every two cells (points, edges, facets) meeting in a union of cells. So a point may
  lie inside an edge or a facet (a T-junction), an edge inside a facet, and a facet
  inside a coplanar facet; crossings, piercings, partial collinear overlaps and
  coplanar overlaps that no common cell covers are refused. The first violation is
  named in an `InvalidPLC` (a `ValueError`) with the witness type of the import
  validity rule and a witness that can be checked independently: the vertex, the
  facet or facets, and for crossings an exact rational point in both cells that lies
  in no cell contained in both. It also returns the edges split at the points on them
  and the pieces on the boundary of an odd number of facets (none when the surface is
  closed).
- **Points on segments.** Boundary recovery adds points on input segments: an S point
  is `points[a] + t (points[b] - points[a])` with `0 < t < 1`, stored as (a, b, t) and
  never rounded inside the mesher. Its coordinates are exact dyadic rationals, so
  `mixed_predicate_signs(kind, points, segments, t, query, axis=2)` evaluates
  `orient3d`, `insphere`, `insphere_sos` and the in-plane `orient2d_proj`,
  `incircle_plane`, `incircle_plane_sos` exactly on any mix of input and S points:
  an interval filter (every operation rounded outward by one ulp) decides most signs,
  and exact big integers the rest. Queries use global indices, input points first and
  then S points, which also order the tie-breaking perturbation. `spoint_coords` gives
  the output coordinates, each rounded once to the nearest double.
- **Segment recovery.** `recover_segments(points, segments, max_depth=60)` turns every
  elementary segment (the `subsegments` of `check_plc`) into a union of edges of the
  Delaunay tetrahedralization, adding S points only on the segments, and only on
  pieces that are missing (Si and Gärtner's rules, as in Diazzi et al. 2023). A
  missing piece is split once per round where its reference point says: the mesh
  neighbour of its ends inside its diametral ball that sees it under the largest
  angle. A piece of a segment with an end where segments meet at less than 90 degrees
  is split on a sphere about that end through the reference point (rules 2 and 3, so
  points about one vertex build its protecting spheres lazily); another piece at the
  distance of the reference point from its nearer end (rule 1); a segment with two
  such ends, or a piece without a reference point, at its middle. The parameter is a
  short dyadic near the target, and a target outside the middle 62/64 of the piece
  falls back to the middle. A vertex with more than 32 segments (a fan's centre) at
  which a piece is missing is protected first, as Shewchuk does: every segment at it
  gets points at radii rc 2^k from it (rc is at most 2/3 of the distance to its nearest
  neighbour and a third of each segment) and one point just short of its far end on a
  dyadic grid of radii common to the hub's segments; later split points on those
  segments are rounded down to that grid too. The points of a thin fan's segments then
  lie on common spheres, so float32 rim points, whose radii differ by a rounding, do
  not make the segments encroach each other without end (a 36,000-segment fan
  converges in 83 rounds). The result is the Delaunay tetrahedralization of the input
  and S points under the index-ordered perturbation, with each segment as a chain of
  edges through its own S points. A piece shorter than 2^-`max_depth` of its segment
  raises `RuntimeError` instead of looping (termination after rounding the parameter
  is not proven, as for Diazzi et al.).
- **Facet recovery.** `recover_plc(points, segments, facets)` runs the PLC check and
  segment recovery, then triangulates every facet again with the S points on its
  segments (its subfacets, with the same exact predicates and tie-breaking) and lists
  the subfacets that are not yet faces. `recover_boundary(points, segments, facets)`
  goes on and makes every subfacet a face: around each connected region of missing
  subfacets of a facet it removes the tetrahedra whose interiors cross the region and
  refills each side of the facet plane. Each side is first filled with the Delaunay
  tetrahedralization of its own vertices, keeping the tetrahedra inside the cavity;
  when that does not conform to the side's boundary, gift-wrapping fills it (every new
  tetrahedron the exact Delaunay choice among the cavity vertices that see its face).
  Both give the same result: the constrained Delaunay tetrahedralization is unique
  under the perturbation. It then verifies
  the result from the arrays: positive tetrahedra, the hull unchanged, every point a
  vertex, every subfacet a face, every segment piece an edge, and every other interior
  face locally Delaunay, which makes the result a constrained Delaunay
  tetrahedralization. A cavity it cannot fill raises `ValueError`; the tetrahedra
  still fill the convex hull (no region labels yet).
- **Mesh without refinement.** `mesh_plc(points, facets, segments=None,
  domain="regions")` goes on from boundary recovery to a mesh in the plan's output
  contract. Tetrahedra joined by a face that is not a facet form a component; a
  component reaching a hull face that is not a facet is outside. With
  `domain="regions"` every other component is a region (a multi-region PLC);
  with `domain="parity"` the components an odd number of facets away from the
  outside form one region (the even-odd domain of closed surfaces; a face shared by
  two touching shells counts twice). In regions mode, `region_points` names the regions:
  `(point, name)` pairs, where the bounded component that holds a point is region `name`
  (components may share a name) and `name=None` marks a hole that is not meshed. Every
  bounded component then needs a point, each point must lie strictly inside one (decided
  exactly, against the unrounded points), and regions are numbered in the order the
  names first appear. Errors are typed, all `ValueError`: `InvalidPLC`
  from the input check with its witness, `NotClosed` in parity mode with witness type 6
  (an elementary segment on the boundary of an odd number of facets, such as an edge
  with three facets; decided from the input check before boundary recovery, so an open
  surface in one plane is `NotClosed` too), `RecoveryError`, `RoundingError`, `RegionError` (a region point
  outside every region or on a facet, two names in one region, or a region without a
  point), and `MeshError` for anything else. Points on
  segments are rounded once to the nearest double, input points are kept bit for bit,
  unused points are dropped, and every tetrahedron is certified with exact
  `orient3d > 0` on the output doubles. Tetrahedra that rounding makes flat or
  inverted are repaired by 2-3 flips and edge removals (rings of three to seven
  tetrahedra, with one consistent fan), by edge removals inside one facet that
  re-triangulate the facet there, and otherwise by refilling a small cavity around the
  tetrahedron as a cone from one of its vertices or from one new point inside the domain
  (`node_source` −1). None removes a segment edge or uncovers a facet. The result is
  certified: every tetrahedron positive, every face in at most two tetrahedra with
  opposite windings, and the faces used once exactly the domain's boundary. It returns `nodes`, `tetrahedra`, `regions`,
  `region_names`, `boundary_faces` and `boundary_nodes` by facet index (wound
  outward), and `interfaces` by region pair (wound from the lower region to the
  higher). Without refinement (below) the mesh has the input points and the points
  boundary recovery needed. The plan's C10 adversarial inputs are meshed this way
  and checked against V1–V4 on every platform's installed wheel (the Schönhardt
  prism and the Chazelle polyhedron, which need Steiner points, a cospherical prism
  with an interior vertex, near-coplanar quadrilaterals, stacked layers, a 4³ box lattice, 5° and 30°
  wedges, a 1:100 slab, and touching, nested and stacked shells). C13 fuzzing runs
  200 seeded assemblies of dyadic boxes and n-gon prisms, some with 1-ulp jitter, in a
  child process with a 60 s progress limit: each must give a valid mesh or a typed
  error.
- **Refinement.** `mesh_plc(..., h=None, ratio=None, alpha=1.0, max_points=0)` refines
  the recovered mesh before rounding when `h` or `ratio` is given (constrained Delaunay
  refinement): an encroached subsegment splits at its midpoint, an encroached subfacet
  at its circumcentre, and a tetrahedron whose circumradius exceeds `alpha·h` or whose
  radius-edge ratio (circumradius over shortest edge) exceeds `ratio` at its
  circumcentre, unless that point encroaches a subsegment or subfacet, which splits
  instead. Points are exact (on a segment, on a facet, or in the volume) and rounded
  once with the rest. Each insertion removes the tetrahedra whose circumspheres hold the
  point and that it sees: a cavity never holds both sides of a subfacet it does not
  replace, and it holds both sides of every subfacet it does. Near input angles below
  60° the rules of Shewchuk (1998, 2002) and Ruppert (1995) stop the cascades: concentric
  shells on segments meeting at such an angle, no split of a subfacet for a vertex of a
  facet meeting it there, and no ratio split of a tetrahedron that is skinny because of
  the angle. Those tetrahedra and the subsegments and subfacets left encroached are
  counted in `stats` (`exempt_subsegments`, `exempt_subfacets`). A cap on inserted
  points (`max_points`, or by default 20·V/h³ + 200·A/h² + 100·n₀, plus 200·A/ℓ² with a
  ratio where ℓ is the shortest input edge, between 1,000 and 5,000,000) ends refinement
  with `RefineError` instead of a hang. All 14 C10 inputs refine to the end at h = ½, ¼
  and ⅛ of their size with ratio 2 and pass V1–V4. V7 (guaranteed mode, ratio 2, max
  ratio ≤ 2(1 + 10⁻⁹), decided exactly) passes on C2 at h = 0.12, 0.06 and 0.03 (max
  1.970, 1.993, 1.914), on C3 at h = 0.8, 0.4 and 0.2 (1.888, 1.892, 1.763) and on C9 at
  C2's sizes (1.990, 1.998, 1.997).
- **Boundary size and robustness (M6).** Refinement first drops the tetrahedra outside
  the domain (the rest of the convex hull, and holes): every face between them and the
  domain is a subfacet, so the boundary becomes a hull boundary, as a convex domain's
  is. Kept, that filling had to be retriangulated around every boundary point, and on
  re-entrant inputs (C6) it became non-Delaunay and left no valid cavity. A subsegment
  longer than `alpha·h`, a subfacet with circumradius above 0.68 `alpha·h` or with
  radius-edge ratio above 1.5 is split even when nothing encroaches it, so the boundary
  is discretized to the size first. After each insertion, Lawson 2-3/3-2 flips restore
  the Delaunay property where a cavity was cut short. A tetrahedron whose circumcentre
  cannot be inserted is retried at most 3 times; one far above the size whose
  circumcentre lies beyond a subfacet is split at that point's projection on the facet.
- **Mesh improvement (M6).** Once refinement ends: tetrahedra with a dihedral angle
  below 15° are split at their circumcentres (only those with circumradius at least 0.7
  `alpha·h`, unless no vertex of the sliver can move; at most 10% more points);
  remaining slivers' volume vertices are moved in fixed directions; volume vertices are
  smoothed towards their neighbours' centroid, facet points within their facet's plane
  (exact facet coordinates) and segment points along their segment; 2-3 and 3-2 flips
  and edge removal (rings of 4 to 7 tetrahedra, the best triangulation of the ring by
  dynamic programming) change the connectivity. A change is kept when it raises the
  worst (dihedral angle, q) of the tetrahedra it touches, or keeps that worst shape at
  least 15° and q 0.5 and lowers their total badness (sum of 1/q − 1); it never moves a
  constraint off its segment or facet, never flips across a subfacet, and keeps V7's
  bound. These passes run twice. `stats` counts each (`sliver_points`, `slivers_left`,
  `sliver_moves`, `smooth_moves`, `quality_flips`, `quality_edge_removals`,
  `lawson_flips`).

```python
import numpy as np
from meshloom._core import delaunay, verify_delaunay

points = np.random.default_rng(0).random((10_000, 3))
tetrahedra, vertex_of, stats = delaunay(points)
verify_delaunay(points, tetrahedra)   # raises ValueError on any violation
```

These stages are graded by V16 and V17 of the
[3D plan](../meshine/validation3d.md). `cargo test` compares every predicate with
big-integer determinants on 10⁴ random and 10⁴ adversarial cases each, and
`tests/meshloom` cross-checks them with Python `Fraction` and runs the verifier and
three insertion orders on the C12 point sets. `benchmarks/benchmark_delaunay.py`
measures throughput on 10⁶ uniform points, with the V15 counters per vertex, and
`benchmarks/benchmark_recovery.py` the segment recovery counters (Steiner points per
segment) on the chip package and a geodesic sphere.

## Platforms and build

meshloom is the one OpenPhysics package with compiled code. It depends on numpy
only. Wheels use the stable ABI (`cp312-abi3`, one wheel per platform for
CPython 3.12 and later) and are built for manylinux 2.17 x86_64 and aarch64,
macOS 11 x86_64 and arm64, and Windows x64. Elsewhere `pip` builds the sdist,
which needs a Rust toolchain and maturin; without a kernel, `kernel_available()`
is `False` and `generate3d` raises `KernelUnavailable`.

From a checkout (repository root):

```bash
rustup toolchain install 1.97.0 --profile minimal --component rust-src
python -m pip install maturin -e packages/meshloom
python -m pytest -q tests/meshloom
(cd packages/meshloom && cargo test --locked)
```

The kernel's unit tests run with `cargo test`; `tests/meshloom` checks the built
extension: it is an abi3 module of the package's version, its error-free product
agrees with exact rational arithmetic, and its predicates and Delaunay
tetrahedralization pass the checks above.

## Licenses

meshloom is Apache-2.0. The extension statically links PyO3, its small
dependencies and the Rust standard library, all under permissive licenses and
with no third-party C or C++ code; their license texts ship in
`THIRD_PARTY_NOTICES`, generated and checked by `tools/build_meshloom_notices.py`.
See [third-party software](../../third-party.md).

## Limits

- Not yet accepted. Measured with the defaults (2026-11-21), every row run so far
  passes:
  - V10 on all 15 pairs (C2–C6 at the plan's three sizes): smallest dihedral angle
    15.4–23.1°, mean q 0.767–0.857, T within its window.
  - V9 on C1: smallest angle 25.2 / 21.1 / 19.0°, smallest q ≥ 0.43, mean q above the
    floor.
  - V8 on C1, C2 and C3 with the die at h/2 (every region).
  - V8 graded on C2 (2026-11-26): 97.1% of the edges have r_e / 1.281 in [0.5, 1.5]
    (the gate is 90%).
  - V26 on C1–C9 at h = 0.1 (2026-11-26): the same SHA-256 per case over 3 fresh
    processes and 2 runs in one process, on Python 3.12.13 and 3.15.0b4 with the same
    wheel. Pull requests run it without C3, whose mesh has about 1.27 million
    tetrahedra (513 s and 2.1 GiB on one core); main pushes run it in full on both
    Pythons ([meshloom V26 jobs](../../development.md#what-ci-runs)).
  - V27 on C1 at three sizes and C3 at two: scaled by 2⁻²⁰ and 2¹⁰, the mesh is the
    same and its nodes are the scaled nodes, bit for bit.
  - V28 on C2, C3 and C5 at two sizes each, from micrometres to 1e6 m: V1–V5 hold,
    and the volume fractions and tetrahedron counts are within the gates.
  - V14's graded 1M-tetrahedron cube (benchmark): V8's graded size times 0.130 gives
    1,005,634 tetrahedra at 0.77 GiB peak RSS, **within** ≤ 1 GiB, in a median of 131 s
    (5 fresh processes, one thread), which **fails** ≤ 60 s (2026-11-27; 255 s and
    2.12 GiB on 2026-11-26, before the shape memo was removed).
  - V6: sphere volume slope 1.87, e(0.05) = 1.15e-3.
  - V5 on C1, C4, C5 and C11 (at most 2.5e-16).
  - V21 at the plan's CI sizes on C2 (L2 slope 2.08, H1 1.05) and on C1 (L2 2.06).
  - V23, and the V32 refinement ladder of the unstructured cavity (first-cluster errors
    0.0130, 0.0027, 0.0005).
  - V7 on C2, C3 and C9.
  - V24 on C11 at the sizes of the amendment of 2026-11-21, {0.1, 0.05, 0.025}:
    capacitance errors 1.05e-2, 2.07e-3 and 4.95e-4, slope 2.20. V5 holds on its three
    spheres. At h = 0.025 the mesh has 1,078,489 tetrahedra and took 17 minutes and
    0.8 GiB to make; conjugate gradients to a relative residual of 1e-12 took 18 s.
  - V25 (report): the PEC sphere cavity on C1 has k² errors of 9.27e-3, 2.64e-3 and
    6.73e-4 for TM11 (order 1.89) and 3.32e-3, 1.03e-3 and 2.82e-4 for TE11 (order 1.78)
    at h = 0.2, 0.1 and 0.05: monotone, order ≥ 1.5 and finest < 2e-2, as the plan
    expects.

  `ALPHA` (1.0) and the boundary's subfacet size (0.68 `alpha·h`) were chosen on V8's C2
  and C3 rows, so V8 does not check them independently. The curved surface edge
  (`SURFACE_EDGE` = 1) was set before V8 on C1 was measured.
- **A mesh depends on how the input is numbered.** The same arrays give the same mesh,
  bit for bit (V26). The same points and facets numbered differently can give a
  different mesh, equally valid: cospherical ties in the Delaunay tetrahedralization
  are broken by point index, and boundary recovery works through segments and split
  points in an order that follows the numbering. Counts taken on the mesh, such as V3
  bound failures on needle facets, can then differ. On synthetic surfaces of 5,000
  triangles (2026-11-28), the generator's numbering, the C14 loader's numbering (in
  order of first reference) and a random one gave 16,280, 16,308 and 20,325
  tetrahedra for a needle surface, and 12,067, 12,463 and 17,018 for a coplanar one.
  Compare results on the same arrays: C14 measures the loader's canonical arrays, so a
  quick check against a C14 number has to use them too.
- A graded size is one function for the whole domain; it cannot be combined with a
  mapping from region name to size. Curved surfaces are limited
  to the builder's primitives, sampled once, uniformly, at h, with no refinement on
  them: a small curved feature needs a small h everywhere.
  Meshing is slow: the unit cube at h = 0.03 (190,000 tetrahedra) takes about 2 minutes
  on one core. Without `h` or `ratio`, `mesh_plc` returns the boundary-conforming mesh of the
  input and recovery points (and the few points repair adds) only. A
  tetrahedron that rounding to doubles makes flat or inverted and that repair cannot fix
  raises `RoundingError`. Near-coplanar facets meeting at a segment are the hard case: in
  a seeded test of rotated prisms with points within 1e-13 of a facet, 42 of 60 inputs
  mesh and 18 raise `RoundingError` (before this repair: 18 and 42); every mesh returned
  passes V1–V4. Until 2026-11-11 the repair never ran inside `mesh_plc` (it was given a
  label per tetrahedron, which forbade every flip) and its edge removal could orient a
  fan inconsistently; both are fixed. A cavity without a constrained Delaunay filling
  (none so far in the tests) is an error, not yet repaired with extra points. The
  gift-wrapping fallback takes time quadratic in the cavity size; the Delaunay path
  filled every cavity side in the tests (a cavity of 25,979 tetrahedra in 0.26 s).
- **Closed triangle surfaces (STL-like inputs) are experimental**: the import gate (V20
  on C14) was not evaluated at M4, which covers builder inputs only, and is taken again at M8. A closed triangle surface given as one
  facet per triangle meshes, small angles between its triangles included. Its quality is not guaranteed, and it
  can be slow. Every triangle edge is then a segment.
  - Inside an input angle too small for any triangle to meet the quality bound
    (19.5° for subfacets, 20.9° for tetrahedra at the default bound 1.4), refinement
    leaves skinny elements instead of splitting them.
  - Where a segment leaves a facet at less than 60° to its plane, the facet and the
    segment do not split each other.
  - Polygon facets and locked facets are not affected by these rules.
  - Measured 2026-11-24 (median of 3 runs, Linux) on 55 inputs, each mesh checked
    exactly:
    - meshloom's own boundaries of C1–C7 at the plan's three sizes;
    - the unit cube from its triangles;
    - 30 synthetic small-angle surfaces: fans and needle triangles down to 0.01°,
      a vertex 1e-8 of the diagonal from a non-incident edge, folds 0.001° from flat,
      and wedges down to 3°.
  - All 55 mesh validly:
    - every input vertex is kept, bit for bit;
    - each boundary face lies in one input triangle;
    - the triangles are tiled to the rounding bound;
    - the volume matches to 1e-12.
  - All but one take at most twice as long as the same case from its builder or polygon
    input (for the cube: twice its six-polygon time, plus 1 s). The synthetic surfaces
    take under 9 s.
  - C3 at h = 0.8 takes 24 s, against 5.9 s:
    - its surface edges are shorter than h;
    - points placed next to them split them again and again;
    - the result is 32,011 tetrahedra, against 4,848.
  - Quality is reported, not guaranteed. 5 of the 15 rows with a V10 gate reach it: C4
    at all three sizes, and C5 and C6 at h = 0.24. The others have smallest dihedral
    angles of 12.5–17.2°, or a mean q below the gate.
  - No tetrahedron is well shaped next to a small input angle. Wedges of 10° and 3°,
    thinner than h, keep tetrahedra of 0.7–7.0° more than h from their edge.
  - Through `builder.triangle_surface` (measured 2026-11-24 before the rules above, median
    of 3 runs), 18 of 21
    mesh and pass the same volume and area checks. On C2–C6 they take 0.82–1.11 times as
    long as from the builder or polygon input. 13 of the 15 rows with a V10 gate reach it.
    The two that miss are C2 at h = 0.06 (smallest dihedral angle 13.5°) and C5 at
    h = 0.12 (mean q 0.811, against 0.8185). C1, a sphere, has no coplanar triangles and is
    unchanged. C7's slanted face is not exactly planar in doubles, so its triangles stay,
    and all three sizes ran past 10 minutes. With the rules, C7 meshes at all three sizes
    and passes the volume and area checks: 7.7 s, 33 s and 182 s at h = 0.06, 0.03 and
    0.015 (one run each, 2026-11-24). The other rows were not measured again. The cube
    from its triangles takes 0.07–3.6 s, and as six polygons 0.06–3.6 s.
  - Locking those triangles (`locked_facets`) keeps them exactly. Recovery puts points on
    them, and each such point is then moved into the domain: the fans of facet triangles
    around it are triangulated again without it, and the space around it is refilled
    from a new point inside (exact `orient3d` > 0 for every new tetrahedron), or the
    point is collapsed onto a neighbour on its segment. The method follows the papers
    that relocate boundary Steiner points into the interior (Si and Gärtner 2011).
    C1–C6 mesh at all sizes with every boundary and interface face an input triangle.
    On C7, the 15° wedge, it fails at all three sizes with `RecoveryError`: 18–38 points
    near the wedge's edges cannot move. There, the space a new point would have to lie
    in is thinner than double resolution.
- The PLC check takes candidate pairs from a uniform grid (cells about the median edge
  extent; each segment and triangle listed in the cells its pieces meet) and checks
  pairs that share a vertex in that vertex's star (a planar fan by the angular order
  of its rays), so its time grows about linearly with the facet count on the
  synthetic surfaces of `tests/meshloom/cdt_inputs.py`; an invalid input is reported
  with the first failing pair of the full bounding-box sweep, as before. Facet
  triangulations walk their triangle adjacency. Neither is tuned further yet.
- The kernel refuses fewer than four affinely independent points and
  coordinates outside 0 or [2⁻¹²⁰, 2¹²⁰] in magnitude. It runs on one thread.
- No musllinux, 32-bit or free-threaded CPython wheels.
