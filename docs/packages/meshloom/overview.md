# meshloom — tetrahedral meshing with an exact-arithmetic compiled kernel

**English** | [한국어](../../locales/ko/pages/packages/meshloom/overview.md)

[Documentation home](../../README.md)

**Status: kernel building blocks, no mesher yet.** meshloom will be OpenPhysics's
general tetrahedral mesher for multi-material piecewise-linear inputs: constrained
Delaunay tetrahedralization with exact predicates, boundary recovery, quality
refinement and mesh improvement, in a compiled Rust kernel. The kernel now has its
first two stages, exact geometric predicates and the Delaunay tetrahedralization
of a point set (below). They are internal building blocks for the mesher, not
public API yet. `generate3d` raises `NotImplementedError`.

```python
import meshloom
meshloom.kernel_available()   # True when the compiled kernel loaded
meshloom.kernel_version()     # the kernel's version, equal to meshloom.__version__
```

Use [`meshine.extrude`](../meshine/overview.md#layered-tetrahedral-meshes) for layered
geometry and Gmsh through [`gmshio`](../gmshio/overview.md) for other shapes until
meshloom generates meshes. The criteria it will be accepted by are fixed in
advance in the [pre-registered 3D validation plan](../meshine/validation3d.md); its
output will have the fields `galerkin.from_mesher` reads, like `meshine.TetMesh`.

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
  refills each side of the facet plane by gift-wrapping (every new tetrahedron the
  exact Delaunay choice among the cavity vertices that see its face). It then verifies
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
  outside form one region (the even-odd domain of closed surfaces; a surface that is
  not closed, such as an edge with three facets, raises `ValueError`). Points on
  segments are rounded once to the nearest double, input points are kept bit for bit,
  unused points are dropped, and every tetrahedron is certified with exact
  `orient3d > 0` on the output doubles. Tetrahedra that rounding makes flat or
  inverted are repaired by 2-3 flips and edge removals (rings of three to seven
  tetrahedra), which never remove a facet face or a segment edge and are applied only
  when every new tetrahedron is positive and every face stays in at most two. It returns `nodes`, `tetrahedra`, `regions`,
  `region_names`, `boundary_faces` and `boundary_nodes` by facet index (wound
  outward), and `interfaces` by region pair (wound from the lower region to the
  higher). There is no refinement: the mesh has the input points and the points
  boundary recovery needed. The plan's C10 adversarial inputs are meshed this way
  and checked against V1–V4 on every platform's installed wheel (twisted prism,
  near-coplanar quadrilaterals, stacked layers, a 4³ box lattice, 5° and 30°
  wedges, a 1:100 slab, and touching, nested and stacked shells).

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

- No refinement or quality improvement yet: `mesh_plc` returns the boundary-conforming
  mesh of the input and recovery points only. A tetrahedron that rounding to doubles
  makes flat or inverted and that no flip repairs raises `ValueError`; flips cannot
  repair an inversion against a facet face itself (in a synthetic test with points
  snapped to a coarse grid, every interior inversion was repaired and inversions at
  the fixed boundary were refused). No meshing test has needed a repair yet. Facet recovery fills cavities by gift-wrapping only: a cavity
  without a constrained Delaunay filling (none so far in the tests) is an error, not
  yet repaired with extra points, and the fill takes time quadratic in the cavity
  size (the faster cavity path comes with the rest of boundary recovery).
- The PLC check compares candidate pairs from a sweep over bounding boxes and the facet
  triangulation uses linear scans: both are meant for builder-sized inputs and are
  not yet tuned for very large surfaces.
- The kernel refuses fewer than four affinely independent points and
  coordinates outside 0 or [2⁻¹²⁰, 2¹²⁰] in magnitude. It runs on one thread.
- No musllinux, 32-bit or free-threaded CPython wheels.
