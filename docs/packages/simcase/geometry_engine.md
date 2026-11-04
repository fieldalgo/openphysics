# The exact 2D geometry engine (stage 2)

**English** | [한국어](../../locales/ko/pages/packages/simcase/geometry_engine.md)

[Documentation home](../../README.md)

`simcase.geometry_engine` is stage 2 of the
[geometry document contract](geometry_document.md). It takes one `2d` or
`axisymmetric` component that the [stage 1 reader](geometry_reader.md) has
parsed and builds the contract's **region complex**: cells with a region name, a
material and the feature that owns them; curves of kind `line`, `arc` or
`circle` with exact parameters, the provenance names of every feature part whose
source curve contains them, and the cell on each side; and the resolved
selections and boundary tags. It replaces the shapely booleans of the 0.2 route
for everything the complex describes, and shapely is now a test reference only.

The engine imports only the standard library. Nothing in it is approximate: the
defining values are integer picometres, intersections of lines are rational,
intersections with circles are quadratic numbers `a + b*sqrt(D)`, and every
decision (the order of points along a curve, the order of curves around a
vertex, the orientation of a boundary, whether a ray crosses a boundary) is
taken with integer arithmetic. So a touch stays a touch whatever unit the
document declares, and the same component written in nanometres and in metres
gives the same complex.

## Use

```python
from simcase.geometry_document import parse
from simcase.geometry_engine import evaluate

model = parse(document)                   # a document with a version 1 geometry block
rc = evaluate(model, "xs")                # the component name may be left out when there is one

rc.region_names()                         # surviving regions in feature order, then "background"
rc.cells                                  # Cell: index, region, material, feature, loops, area (pm^2)
rc.curves                                 # Curve: kind, vertices a and b, params, provenance, left, right, tag
rc.selections                             # name -> ("region" | "boundary", frozenset of cell or curve indices)
rc.area_of_region("core")                 # pm^2
rc.euler()                                # (V, E, F, C): V - E + F == 1 + C always holds

domain, namer, materials = rc.to_domain(size)   # the meshine hand-off, size in micrometres
```

- A `Cell` is one face. A region that later features cut into pieces, or that
  `region` merges from several features, has several cells with the same
  `region`; `loops` lists its outer loop and its holes as `(curve index,
  forward)` pairs. A void cell (`material: null`) has `void == True`.
- A `Curve` is a maximal piece of one supporting line or circle between two
  vertices. An `arc` runs counter-clockwise from vertex `a` to `b` around
  `params["center"]` with `params["r2"]` the radius squared; a `circle` is a
  whole circle that nothing else touches, split at two vertices. `left` and
  `right` are cell indices, `None` for the exterior of the domain.
- `tag` is the mesh tag of a curve that borders the exterior or a void cell:
  `left`, `right`, `bottom`, `top` (`axis` for an axisymmetric component whose
  `xmin` is zero) on the domain sides, `outer` elsewhere, or what
  `boundary_tags` assigned, first matching entry first.
- `vertices` are `(x, y)` pairs of `simcase.geometry_engine.Q2` numbers in
  picometres. `float()` gives a double; `.approx(bits)` a rational within
  `2**-bits`.
- `area` is the exact chord polygon plus the circular segments in floating
  point, so it is accurate to the double rounding of the segment terms.

### What it decides

- **Later wins.** The owner of a face is the latest feature among those that
  contain it, found by walking from the unbounded face across the edges and
  toggling the features each edge bounds. No sample point is ever taken.
- **`later_wins`** removes an edge between two faces of one region, unless a
  `segment` feature that no later area feature covers lies on it.
  **`imprint`** keeps every edge inside the domain, so a covered boundary
  survives as a curve between two cells of one region.
- **`segment`** features are zero-area curves imprinted into the region that
  contains them. A later area feature removes the part it covers. A segment
  that crosses a region splits it into two cells.
- **Provenance** is geometric: a curve carries the part name of every feature,
  and the domain side, whose source curve contains it, whether or not that
  feature owns a neighbouring cell.
- **Selections and `boundary_tags`** resolve as the contract's
  [selector rules](geometry_document.md#selector-rules-frozen) say. A named
  selection that selects nothing is refused unless it is `optional`.

### What it refuses

Every refusal names the feature.

- A `3d` component. The engine is 2D; stage 5 covers 3D.
- A `path` whose boundary crosses or touches itself, repeats a point, or whose
  boundary overlaps itself along a piece.
- An arc segment of a `path` whose `to` does not lie exactly on the arc's
  circle (`|to - center|^2 != r^2` in picometres). The contract allows the end
  point to be a derived point; this engine takes only arcs that start and end on
  the grid, so that every supporting line has rational coefficients and every
  circle an integer radius squared. Put a line segment between two arcs, or
  choose `to` on the circle.
- At the hand-off, a `segment` curve that lies inside one cell: meshine takes
  region loops only.

## The meshine hand-off

`to_domain(size, unit_pm=10**6)` builds a `meshine.Domain`:

- each coordinate is rounded **once**, from picometres to the mesher's unit
  (micrometres by default);
- an arc becomes a polyline whose vertices the two cells on its sides share,
  with the vertex count a whole circle would get from `max(16, int(2πr /
  (size / 2)))`, the 0.2 rule;
- a `circle` curve becomes one `meshine.Circle` object that the inside cell and
  the surrounding cell's hole share, so mesh nodes on it are projected onto the
  exact circle;
- cells of one region are added under that name as separate loops, and
  meshine merges them and keeps the shared segment as a constraint (that is
  how `imprint` pieces travel);
- void cells are not added, so their borders become exterior boundary tagged
  `outer` unless `boundary_tags` says otherwise;
- after the rounding, the polylines are checked: two vertices rounding to one
  point, a zero-length piece or two pieces crossing is refused by name rather
  than meshed.

The namer it returns maps a boundary segment's midpoint to the tag of the
nearest exterior polyline piece.

The runners still take the 0.2 form that `to_v02` compiles, so a version 1
document that reaches a solver is meshed through the 0.2 builder today; the
engine is the route for the features the 0.2 builder refuses (`imprint`, void,
merged regions, `path`, `segment`) once the runners read the complex. That
wiring is separate work.

## Validation

The pre-registered checks G2-1 to G2-7 (HQ work record, 2026-11-04) are in
`tests/simcase/test_geometry_engine.py`, with shapely as the test reference.
Measured on 2026-11-04 (Linux, Python 3.12, pinned environment):

| Check | Criterion | Result |
|---|---|---|
| G2-1 shapely, general position | 2000 seeded cases of rects and convex polygons with no touching, shared vertex or vertex on an edge: per-region area within 1e-12 relative, same face and hole counts | all agree. 300 touching cases agree in area and face count; 27 differ only in representation (shapely's hole touching the shell is the engine's pinched loop) |
| G2-2 circles and arcs | two-circle lens, circle cut by a rect, concentric annulus and a path with arcs against closed forms, 1e-12 relative | pass |
| G2-3 Euler | on every complex the tests build: V − E + F = 1 + C, cells tile the domain within 1e-12 | pass |
| G2-4 invariance | translation by whole picometres, 90° rotation and mirror keep the cells, curves, provenance and areas | pass |
| G2-5 degenerate inputs | externally and internally tangent circles, concentric rings, collinear overlapping edges, a vertex on an edge, three curves through one point, the 8 × 8 grid of touching rects in nm, µm and m (64 cells, 144 curves), against hand-derived counts and areas | pass |
| G2-6 current documents | all 51 built-in and example documents: region names, materials and face counts equal the shapely route's; areas equal except where a circle is involved | pass; circle regions differ by the 128-gon approximation (4.0e-4 of a circle's area, 1.3e-5 of a fibre cladding), one zero-area sliver part of the 0.2 route (`pml_leaky_slab`, the `0.47 + 2.0` corner) is absent |
| G2-7 time | Studio maximum (8 shapes × 12 vertices) under 0.2 s; a PCB-like plane with 200 features under 10 s, pure Python | 0.07–0.08 s and 2.2–2.3 s |

The gate values of G2-7 are proposals confirmed after this measurement; the
other criteria are fixed.
