# meshine — a small quality triangle mesher for multi-material planar domains

**English** | [한국어](../../locales/ko/pages/packages/meshine/overview.md)

[English / 한국어 documentation and translation status](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Constrained Delaunay refinement (Ruppert's algorithm) written in Python on top
of scipy's Delaunay. Describe a cross-section as named material regions —
polygons and circles that tile the domain, holes allowed — and get back a
conforming triangle mesh with a guaranteed minimum angle, per-region size
control, one region id per triangle, and boundary edges grouped by name.

Depends on numpy and scipy only. No external mesher, no GPL code.

```python
from meshine import Domain, Circle, generate, box_sides, rectangle

d = Domain(size=0.3)
d.add_region("core", rectangle(-1, 0, 1, 0.5), size=0.05)
d.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)])
d.add_region("clad", rectangle(-3, 0.5, 3, 2))
mesh = generate(d, box_sides(-3, 3, -2, 2), min_angle=28)

mesh.nodes            # (N, 2)
mesh.triangles        # (T, 3) counter-clockwise
mesh.regions          # (T,) index into mesh.region_names == ["core", "clad"]
mesh.boundary_edges   # {"left": (E, 2), "right": ..., "top": ..., "bottom": ...}
mesh.interfaces       # {("clad", "core"): (E, 2)}  edges between materials
mesh.min_angle(), mesh.quality(), mesh.region_area("core")
```

Shared edges and T-junctions between regions are resolved automatically.
Circles are exact: nodes the refinement inserts on a circular boundary are
projected onto the true circle, so a fiber core really is round.

The mesher is never told what a length is, and there is no absolute length
constant anywhere in the package. Point merging and boundary classification are
a dimensionless fraction of the domain's own bounding-box diagonal, and the
degeneracy test compares a triangle's area to its own edge lengths, so the same
cross-section meshes to the same geometry whether it is written in micrometres
or in kilometres. Triangle counts legally differ a little between scales,
because refinement rounds differently; region areas, the angle bound and the
boundary names do not.

```python
from meshine import shapes
d, namer = shapes.rib_waveguide(slab_thickness=0.3, size_core=0.1, size_far=0.5)   # Hadley 2002
mesh = generate(d, namer, size_fn=shapes.size_graded(0.1, 0.5, dist_max=3.0, center=(0, 0.5)))
mesh = generate(shapes.circular_fiber(core_radius=4.0, domain_radius=20.0, size_core=0.4))

d = Domain(size=0.3)                                  # PEC cylinder in a circular air domain
d.add_region("air", Circle((0, 0), 4.0), holes=[Circle((0, 0), 1.0)])
mesh = generate(d, lambda mid: "pec" if abs(complex(*mid)) < 2 else "abc")
```

## How it works

Each round: triangulate all points (Qhull); split any input segment that is
missing from the triangulation or whose diametral circle contains another
vertex; then, for triangles inside the domain that are too thin (angle below
`min_angle`) or too big (circumradius above `size_factor * h`), insert their
circumcenters — unless a circumcenter would encroach a segment, in which case
that segment is split instead. Repeat until nothing is bad. This is Ruppert's
rule set; it terminates with the requested angle bound for reasonable input
(right-angled geometries up to about 30°). Input segments that meet at less
than 60° fall outside its termination argument; see
[small input angles](#small-input-angles). A final Laplacian pass moves
interior nodes only where no incident triangle gets worse.

Points are inserted in batches with a separation filter and the point set is
re-triangulated each round, so the refinement code stays about 430 lines. A
10k-triangle rib cross-section takes about a second.

The separation filter considers larger circumradii first. The default
`generate(..., candidate_order="legacy")` preserves the existing NumPy quicksort
selection. Opt into `candidate_order="stable"` to retain the input candidate
order when radii are equal; SIPI uses this mode for its cross-sections. An
unstable tie order can select different points on native and WebAssembly NumPy
builds. Stable ordering removes that source of variation, but does not guarantee
identical meshes across all Qhull versions, floating-point platforms or
geometrically equivalent input orderings. Choosing stable ordering can change
meshes with tied candidates. Other values are rejected with `ValueError`.

## Small input angles

Ruppert's termination argument needs every angle between two input segments to
be at least 60°. Below that, two kinds of corner never finish on their own:

- An *acute* corner opens into a region at less than `min_angle`. The triangle
  that fills it always has the input angle, so it is always bad, and splitting
  it only moves the problem closer to the apex.
- In a *halving-incompatible* corner, the vertex on each side encroaches the
  first piece of the other side: their length ratio is not within 1/cos(angle)
  of a power of two, and midpoint splits never change that, so the two sides
  split each other forever. A corner that opens into a hole or out of the
  domain does this too.

A vertex with such a corner is *treated*, and only treated vertices take the
two rules below. The compatibility test uses the first pieces that rule 1 leaves:
where the far end of a side is treated, the lattice vertex it puts on that side
shortens the piece, and a corner that was compatible on the input lengths can
become incompatible. The test therefore repeats until it treats no further
vertex. Where the sides are straight, plain refinement does not finish an
input with a treated vertex (argued above), so an input that meshed before gives
the same mesh, node for node. That was checked on the ten shipped simcase examples
meshine meshes, on the 104 meshes and 5 error messages of the earlier meshine,
simcase and galerkin tests, and on 83 other inputs that meshed before, 54 of
them crossing angles. A corner with a side on a meshine `Circle` is the
exception; see [Limits](#limits).

1. **One halving lattice per treated vertex.** `unit` is the length of the
   shortest side of a sharp corner (below 60°) at the vertex. Before the first
   round, each such side gets one vertex at the largest `unit · 2^k` below half
   its length. A later split of a piece that touches the vertex lands on the
   `unit · 2^k` nearest its midpoint, a shell concentric with the vertex, and is
   projected onto the circle where the side is curved. The pieces next to the
   vertex stay equal, so neither encroaches the other.
2. **Acute corners keep their angle.** A triangle's angle at the apex is not
   tested when the triangle lies inside the corner; its other angles and its
   size still are. A triangle that is bad only by its angle is left as it is
   when its circumcenter encroaches a piece at the apex and splitting that piece
   would put two vertices closer together than the triangle's own shortest edge
   (Shewchuk's terminator). Refinement then ends through the normal "nothing
   bad" exit.

The triangle in a corner below `min_angle` keeps the input angle, the other
triangles below `min_angle` stay next to the apex, and the bound holds
everywhere else. How far they reach is measured, not proved. In units of the
longest subsegment at the apex, the farthest was 1.43, for two wedges at one
apex with region sizes 0.01 and 0.5; a triangle with corners of 2° and 17°
reached 1.33, and every other input of the tests below at most 1.26. Wedges of
0.1° to 20°, a 64-gon and default (n = 32) meshine `Circle`s that touch a side
or each other, and simcase's 128-gon heater crossing a side at every odd angle
from 1° to 89° each mesh in at most about 2 s; coarser `Circle`s can fail (see
[Limits](#limits)).

## Safeguards

These apply to every input:

- `max_points` is a hard cap. `generate` raises before an insertion would pass
  it, in every round; the segment-splitting rounds used to go unchecked. The
  input domain as built is checked too, before the corner analysis, the lattice
  splits and the first triangulation, so an input with more points is refused
  before any refinement work; building the domain, which is O(V²) in its
  vertices (see Limits), still comes first. The error is `MeshSizeLimitError`,
  a `RuntimeError` subclass exported by `meshine`; its message starts with
  `more than <max_points> points`.
- A boundary point the triangulation cannot resolve is refused at once. Qhull
  leaves a point out when two boundaries come closer than double precision
  separates at the domain's extent: a vertex a hair off another edge, a sliver
  edge, or the two sides of a sharp corner with a curved side that kept
  splitting each other toward the apex (see [Limits](#limits)). A segment
  through that point can never be recovered, so
  `generate` raises a `RuntimeError` that names the point and the distance,
  instead of splitting the segment forever.
- An input edge shorter than `SNAP_EPS` (3e-8 of the domain diagonal, below
  the shortest edge the earlier meshine meshed, 4.5e-8) is dropped where that
  is safe. When one end vertex has exactly two segments with the same owners
  and the same curve, the vertex is removed and the two segments become one,
  which moves the boundary by less than the edge's length. The end where the
  boundary bends less is tried first, so a corner next to a collinear vertex
  stays, and a vertex whose removal would change a boundary name (a corner of
  `box_sides`) is kept. Polygon clipping leaves such edges where a cut passes
  within a rounding error of a vertex. `Domain(snap_eps=0)` turns the drop off.
- The encroachment, corner and terminator queries are local. Each segment asks
  a tree of the candidate circumcenters for those within its own half-length.
  Before, every candidate asked for every segment midpoint within the
  half-length of the longest segment, and next to one long segment that is
  nearly every pair. The probes that tell whether a sharp corner opens into a
  region go through one point-in-polygon pass per region, not one per corner.
  Shewchuk's terminator asks a tree of the skinny triangles' circumcenters,
  once per first piece at an acute corner with that piece's own half-length,
  instead of comparing every triangle with every piece in one array. The strict
  tests and the meshes are unchanged. Measured on Linux as time and peak memory
  of the process (about 70 MB of it the interpreter and imports), times as the
  range of six runs, each run ending with the `max_points` error before and
  after:
  - a strip 0.005 wide with mesh size 0.01 in a 40 x 20 box of size 1000,
    `max_points=10003`: 2.6 to 5.3 s and 1.04 GB before, 0.4 to 0.7 s and 91 MB
    now. Its largest query returned 8,298,339 pairs and returns 8,192;
  - a 511-point sawtooth with 10° tips, `min_angle=33`, `max_points=10201`: 4.8
    to 6.0 s and 440 MB before, 1.4 to 2.0 s and 94 MB now. Its 507 corner
    probes took about 2 s and take under 0.04 s;
  - the same sawtooth crossed by 60 rectangles 0.03 wide: 9.5 to 11 s and 1.47
    GB before, 1.2 to 1.4 s and 92 MB now. The terminator compared 7167
    triangles with 1204 pieces in one array;
  - a film 1e-7 thick across a 30 x 10 box, `max_points=10201`: 0.9 to 1.0 s
    and 332 MB before, 0.4 to 0.5 s and 89 MB now.

  `tests/meshine/test_refine_cost.py` builds these inputs, bounds the query
  sizes, and checks the queries against a brute force and the corners and
  meshes against the old implementations.

## Tetrahedral mesh contract

meshine does not generate tetrahedra yet. `TetMesh`, `check` and `write_msh`
fix the output that OpenPhysics's own 3D meshers will return, so that solvers and
tests can be written against it now:

```python
from meshine import TetMesh, check, write_msh

mesh = TetMesh(nodes, tetrahedra, regions, region_names, boundary_faces, interfaces=interfaces)
check(mesh)                    # raises MeshCheckError listing every violation
write_msh(mesh, "part.msh")    # Gmsh MSH 4.1 ASCII, read back by gmshio.read_msh
mesh.quality(), mesh.dihedral_angles(), mesh.radius_edge(), mesh.region_volume("die")
```

`check` decides the sign of every tetrahedron's volume exactly: a floating-point
filter settles the clear cases and `Fraction` arithmetic the rest. It then checks
that every face is used once or twice, that the tagged faces are exactly the
outward-wound exterior faces with one tag each, that `boundary_nodes` match the
faces, that no node is orphaned or duplicated, that every region is non-empty and
that `interfaces` hold exactly the faces between two regions, wound from the first
name to the second. The fields are those `galerkin.from_mesher` reads. The criteria
the meshers must meet are fixed in the
[pre-registered 3D validation plan](validation3d.md).

## Self-checks

```bash
# From the repository root
python -m pip install pytest -e packages/meshine
python -m pytest -q tests/meshine
```

Checked properties: polygonal region areas reproduced to 1e-9; every triangle
positively oriented; the tagged boundary equals the set of edges used by
exactly one triangle (watertight, no gaps or overlaps); interface edges are
shared by exactly two triangles of the two named materials; the requested
minimum angle holds; edge lengths follow per-region sizes and a size function;
fiber interface nodes lie on the true circle to 1e-12 with second-order area
convergence; holes are left empty; and edge-midpoint quadrature of a smooth
function converges at second order on a deliberately irregular mesh.

Scale is checked separately: the same device written at five length scales
spanning twelve decades gives the same region-area fractions, the same angle
bound and the same boundary names, and each comparison fails as vacuous if its
scale ratio turns out to be 1.0. An empty mesh is refused by `generate` with a
message naming the count that was zero and which of the two causes it was,
rather than returned for a reduction several frames later to trip over.

Small input angles and the safeguards are checked in
`tests/meshine/test_small_angles.py`, against references independent of the
mesher. Wedges of 0.1° to 20° keep their exact area, with exactly one triangle
below 28°, at the apex, and none sharper than the wedge. The other inputs are
two wedges that share an apex, a 35.5° corner whose sides split each other, a
sharp corner that opens into a hole, lines that leave a side at 20° and 35°, and
a polygon and meshine circles that touch a side or each other; there, every
triangle below 28° lies within 1.5 times the longest constrained edge at the
touch point. The trigger must leave every simcase example and every input that
meshed before alone. The point cap, the unresolved-point error and the
short-edge drop have their own checks; `tests/meshine/test_size_limit.py` adds
the error type, the refusal of an input over the cap before any refinement
work, and a cap at the node count of an uncapped mesh, which gives the same
mesh while one point less raises. An input that used to hang runs in a
child process with a timeout. The pass criteria were fixed before the
implementation, and one of them failed: the trigger was expected to treat
simcase's 45° crossings, but those hung on a clipped edge of 1.4e-8 of the
diagonal, not on their angle, and the short-edge drop is what meshes them. The
failure is recorded here; the test now checks the measured behaviour (no
treated vertex at their 46.41° corners). Checks added later, with measured rather than
pre-registered values, cover a 31° corner that the lattice of its treated 20°
neighbour makes incompatible, the triangles beside a straight 14° corner, two
wedges of very different sizes at one apex, and the error that two touching
8-gon `Circle`s end with.

`examples/meshine/compare_with_gmsh.py` draws the same rib waveguide meshed here and
by Gmsh (through the `gmshio` package) side by side. Gmsh's Frontal-Delaunay
still produces higher mean quality (0.98 vs 0.93 radius ratio) and smoother
grading; meshine's guarantee is the angle bound.

## Limits

- 2D only. Tetrahedral meshing is a different problem; use Gmsh via `gmshio` for 3D. The criteria for OpenPhysics's own 3D meshers are fixed in advance in the [pre-registered 3D validation plan](validation3d.md).
- Termination near small input angles is measured, not proved. An input the rules miss stops with the point cap, `max_rounds` or the unresolved-point error instead of running on.
- Next to a small angle, quality is bounded only by measurement. The triangle in an acute corner keeps the input angle. Rule 2 also leaves skinny triangles outside the corner, in the neighbouring region, when their circumcenter encroaches a first piece, so triangles beside a straight corner can end a little below the input angle: 13.70° and 13.02° beside the 14° corner of a triangle whose other base corner is 20° or 23°, in a box at size 0.05. Where simcase's 128-gon heater touches a side, triangles that do not touch the apex reached at least 5.6°. At a curved cusp, where a meshine `Circle` touches a side or another circle (a true angle of 0°), triangles go below the corner of the 32-gon itself (5.6° at a side, 11.25° at another 32-gon): down to 0.70° at the apex, and 4.1° in triangles that do not touch it.
- A sharp corner with a side on a meshine `Circle` can be treated although the earlier meshine meshed it: each split of a curved side is projected onto the circle and turns the first piece by up to 180°/n toward the tangent, so a corner that is acute or incompatible on its input chord can widen and finish on its own. Such an input now gets a different mesh; in every one measured, all angles stayed at least `min_angle` (28.05° and up at 28). A triangle inside a 16-gon `Circle`, touching it at a vertex with 33° corners and a side ratio of 1.5, gave 660 nodes before and 661 now; of 121 such triangles (n = 8 to 32, corners of 16° to 42°) that meshed before, the 85 with a treated vertex all changed. simcase never passes a touching `Circle`, so its documents are not affected.
- The halving-compatibility test is exact for straight sides only. A corner between `min_angle` and 60° with a side on a meshine `Circle` that the test calls compatible is not treated, and its sides can keep splitting each other toward the apex; it then ends with the unresolved-point error instead of a mesh. Measured: two `Circle`s with n = 8, 10 or 12 that touch each other and n = 32 touching n = 8 (chord corners of 28.1° to 45° at `min_angle` 28), an n = 8 `Circle` touching a side at `min_angle` 20, and a polygon edge that leaves an n = 32 `Circle` vertex at a 39.3° chord corner, each within about 4 s. Touching `Circle`s of n = 16, 32 and 64 mesh.
- An edge between `SNAP_EPS` and the triangulation's resolution gets the unresolved-point error instead of a mesh (measured from 3.5e-8 to 1.5e-7 of the diagonal, on edges the earlier meshine never finished either). The resolution depends on the layout: the shortest edges the earlier meshine finished were 4.5e-8 of the diagonal next to a 90° corner and 1.4e-7 at a 45° corner. The drop handles only a vertex with two segments of the same owners and curve, and only where removing it keeps every boundary name; a short edge with no such end gets the error too. Where both ends are corners and no name changes, one corner is cut, by less than the edge's length. A vertex about 1e-9 to 1e-7 of the diagonal off an edge it does not belong to also gets the error; snap it onto the edge.
- The unresolved-point check raises whenever Qhull drops a boundary point. That never happened in a mesh that finished before, but Qhull's choice is not guaranteed to be stable.
- The cap now holds in every round, so a run whose segment rounds passed `max_points` just before a final round with nothing bad, which the old check accepted, is refused. An input domain that already has more than `max_points` points is refused before refinement, including one that needs no insertion, which used to come back over the cap.
- Node-for-node identity and the dropped-point behaviour were measured on Linux with numpy 2.5.4 and scipy 1.18.1. Other Qhull builds may differ; macOS and Windows are unverified.
- Building a domain compares every input vertex with every earlier one, O(V²) in the number of vertices.
- Curved boundaries: circles are built in; other curves can be added as polylines (or by adding a `project` method to a loop object).

## License

Apache License 2.0 - see [LICENSE](../../../packages/meshine/LICENSE) and [NOTICE](../../../packages/meshine/NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)
