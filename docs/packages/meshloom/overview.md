# meshloom — tetrahedral meshing with an exact-arithmetic compiled kernel

**English** | [한국어](../../locales/ko/pages/packages/meshloom/overview.md)

[Documentation home](../../README.md)

**Status: first mesher, not yet accepted.** meshloom is OpenPhysics's general
tetrahedral mesher for multi-material piecewise-linear inputs: constrained Delaunay
tetrahedralization with exact predicates, boundary recovery, quality refinement and
(later) mesh improvement, in a compiled Rust kernel. `meshloom.generate3d` meshes a
piecewise-linear complex to a size `h` (one number, or one per named region) with a
radius-edge bound: `quality="practical"` (the default, `PRACTICAL_RATIO` = 1.4) or
`quality="guaranteed"` (`GUARANTEED_RATIO` = 2, the bound V7 grades), then improves
the mesh (sliver removal, smoothing and flips). `meshloom.builder` adds curved
primitives (spheres, cylinder vias), sampled on their surfaces. The quality gates
measured so far pass, V10 on all 15 of its pairs included, but meshloom has no graded
sizes and no refinement on curved surfaces yet, and it is slower than the baseline (see
Limits).

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
  are strictly Delaunay on their surface. If one were missing, meshing raises
  `RecoveryError` and never returns a node off the surface.
- **Planar facets.** The box faces and the via's end disks are refined as usual.

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
  Delaunay tetrahedralization, adding S points only on the segments. Where a missing
  piece ends at a vertex whose segments meet at less than 90 degrees, every segment at
  that vertex is first split at one common distance from it (a protecting sphere);
  every other missing piece is halved until it is an edge. The result is the Delaunay
  tetrahedralization of the input and S points under the index-ordered perturbation,
  with each segment as a chain of edges through its own S points. A piece that would
  need more than `max_depth` halvings raises `RuntimeError` instead of looping.
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
  with three facets), `RecoveryError`, `RoundingError`, `RegionError` (a region point
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
- No graded or callable sizes (one size per region only). Curved surfaces are limited
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
- The PLC check compares candidate pairs from a sweep over bounding boxes and the facet
  triangulation uses linear scans: both are meant for builder-sized inputs and are
  not yet tuned for very large surfaces.
- The kernel refuses fewer than four affinely independent points and
  coordinates outside 0 or [2⁻¹²⁰, 2¹²⁰] in magnitude. It runs on one thread.
- No musllinux, 32-bit or free-threaded CPython wheels.
