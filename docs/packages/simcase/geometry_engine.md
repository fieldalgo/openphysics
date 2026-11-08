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

`python -m simcase geometry model.json [-c component]` prints the same complex
of a version 1 document (cells, curves with provenance and tags, selections)
as a diagnostic; it reads the geometry block without the physics validation of
`Document.load`, so void, merged, `path` and multi-component documents are
shown too. It is not a persisted format.

- A `Cell` is one face. A region that later features cut into pieces, or that
  `region` merges from several features, has several cells with the same
  `region`; `loops` lists its outer loop and its holes as `(curve index,
  forward)` pairs. A void cell (`material: null`) has `void == True`. A cell
  that `region` merged from several features lists them all in
  `feature_indices`, names the earliest in `feature`, and takes the smallest
  of their `mesh_size` values; `{"feature": id}` selects every cell the
  feature owns a piece of.
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
  contains them. A later area feature removes the part it covers (the part
  that later features own on both sides, under `imprint` too; a segment on
  the boundary of such a feature stays). A segment that crosses a region
  splits it into two cells.
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
  exact circle; its vertex count is raised above the 0.2 rule when needed so
  that the sagitta of its chords stays below the distance to the nearest other
  curve (a chord may not cut across a feature inside the circle), and a circle
  that would need more than 20000 vertices is refused by name;
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

After `meshine.generate`, the mesh edges can be read back by curve:

```python
mesh = generate(domain, namer)
rc.curve_edges(mesh)                 # {curve index: (E, 2) node pairs on that curve}
rc.provenance_edges(mesh)            # {"core.top": (E, 2), "domain.left": ..., ...}
rc.selection_edges(mesh, "wall")     # the edges of a boundary selection
```

An edge belongs to a curve when both nodes lie on one piece of its polyline, or
on its circle, within `1e-9` of the mesh diagonal (meshine's merge tolerance)
and are consecutive there; a mesh that does not come from the complex's last
`to_domain` (a hand-off vertex without a node) is refused; nothing is read back from the mesher, so the
internal constraints of `imprint` pieces, which meshine keeps but does not
report as interfaces, are found too. This is the contract's `provenance_edges`
field. For a version 1 document, `build_mesh` and the region heat mesh builder
put it on the galerkin `Mesh` they return (`mesh.provenance_edges`, node pairs,
the same in every unit); a 0.2 document's mesh carries `None`. Nothing in
galerkin reads the field yet.

A document with a version 1 geometry block is meshed through this route.
`Document.from_dict` keeps the parsed model (`doc.geometry_model`, integer
picometres, unit-free) and, for a 2D region component, **keeps the block
itself in `doc.data`**: the validators, summaries and result files read it
through the accessors `doc.domain`, `doc.background` and `doc.regions()` (one
entry per declared region, merged features as one entry with the smallest
`mesh_size`, `material` None for void), the canonical micrometre copy carries
the model without re-reading the block, and `build_domain` evaluates the
complex once (`doc.complex()`) and hands it to meshine as above, with the 0.2
sliver rule (a piece under `1e-12` of the domain area is left out and noted in
`doc.notes`). The mesh-limit routes (`check_mesh_limits`, a run with
`max_input_vertices`) take the same engine route and count the same loop
vertices. So `imprint`, `segment`, void, merged regions and `path` documents
load and run. A homogeneous rectangle component and a box-only 3D component are
still compiled to the 0.2 form their kinds read (`to_v02`), losslessly.

What the runners refuse, by name: the waveguide runner takes exterior edges on
the four domain sides only, so a `boundary_tags` entry that renames a side, a
void region or a sliver gap is refused before the solver; region heat takes a
void feature as a hole whose border is insulated unless named, and names its
`boundary_tags`, `outer` and exterior selections for boundary data ([named
boundaries](thermal_regions2d.md#named-boundaries)); a `segment` that
ends inside a cell is refused at load (meshine takes region loops only); an
axisymmetric component is taken by steady region heat only ([axisymmetric
documents](thermal_regions2d.md#axisymmetric-documents)); the waveguide and
transient runners and Studio refuse it by name (the waveguide runner at validation, whatever `xmin` is); region heat refuses a
feature that the domain cuts away or that is a sliver (a feature later
features cover is allowed, as a covered 0.2 shape is). Arcs reach the mesher
with the 0.2 circle vertex rule, `max(16, 2πr / (mesh.size / 2))` per circle
from the global mesh size, so a coarse `mesh.size` gives coarse arcs unless a
`mesh.controls` entry says otherwise (below). A 0.2 block is meshed by the
shapely route as before. The loops reach meshine in a different vertex order from the
shapely route, so a version 1 copy of a 0.2 document gives a different refined
mesh and results that agree at discretization level, as the contract's internal
grid section says (region heat example: 595 against 597 nodes, maximum and mean
temperature within 6e-4 and 4e-4 of the temperature rise; waveguide examples:
effective indices within 2e-6 to 1.6e-4).

### `mesh.controls`

The contract's optional `mesh.controls` list is read for a version 1 document
with a 2D region component (a 0.2 block has no selections and is refused with
it). Each entry is `{"select": <target>, <one control>}`; later entries win.

- `select` names a declared selection, or is a region selector (a region name,
  a feature id, `{"feature": ..}`, `{"material": ..}`) or, failing that, a
  boundary selector (a tag, a provenance name such as `core.boundary`,
  `{"of": ..}`, `{"between": ..}`). A name that is none of these is refused at
  load.
- `circle_segments: n` (an integer, at least 8) sets the vertex count of every
  circle that the selected curves lie on, or that bounds a selected cell, in
  place of the 0.2 rule. A cut circle's arcs take their share of `n`. A whole
  circle whose chords at `n` would cut across a neighbouring curve is raised to
  the count the clearance needs and the raise is noted in the `notes` of the
  document given to the runner (`build_mesh`, the region heat and transient
  region runs); a result's own document is re-validated on every read, which
  resets its notes, so read the note on the document you ran.
- `size: h` (a positive length in `units.length`, converted with the document)
  sets the mesh size of the selected cells, over the feature's own `mesh_size`.
  A size on a boundary selection is not implemented yet and is refused by name,
  as is the contract's `z_divisions`.
- `near: h0, far: h1, distance: d` (three positive lengths, together) is the
  contract's distance grading: the mesh size is `h0` on the selection and grows
  linearly with the distance from it to `h1` at `d` and beyond. The distance is
  to a boundary selection's curves (polylines and true circles) and to a region
  selection's cells, zero inside them. Several gradings, and the 0.2
  `mesh.grading`, combine by minimum; meshine also takes the minimum with the
  cells' own sizes. Both runners apply it (`runner.build_mesh`, the region heat
  mesh builder, the mesh-limit routes).

`rc.to_domain(size, controls=[...])` takes the same entries with lengths in
picometres (`Document.controls_pm()`, which checks the entries first);
`rc.size_function(controls, unit_pm)` is the gradings' size function in mesher
units after a hand-off (`geometry.size_function(doc)` for a document);
`rc.select(expr)` resolves a target to `("region", cells)` or
`("boundary", curves)`.

The runner's micrometre copy (`runner.micrometre_document`) keeps a version 1
block in the document's own unit while its `units.length` says micrometres (the
engine is unit-free, so nothing re-reads the block); the copy records that unit
in `geometry_block_unit` and refuses `to_dict()` and `save()`. Results record
the original document.

## Design velocity (stage 4)

`simcase.geometry_velocity` implements the [stage 4
amendment](geometry_document.md#parameters-sweeps-and-derivatives-frozen) of the
contract (2026-11-08). For one independent length parameter p, it gives
V = ∂x/∂p of a 2D or axisymmetric component. It imports only the standard
library, and NumPy for meshes. Nothing else changes: `parse`, `evaluate` and
`to_domain` give the same results whether or not a derivative is asked for.

```python
from simcase.geometry_velocity import design_velocity, TopologyChange

dv = design_velocity(document, "w")      # the document dict; component= when there are several
dv.defining["geometry.components.xs.features[0].w"]   # Fraction(1)
dv.vertices[v]                           # (Vx, Vy) as Q2, exact
dv.curves[i]                             # CurveMotion: va, vb (ends); vc, dr for an arc or circle
dv.area_derivative("core")               # d(area)/dp in pm
dv.perimeter_derivative("core")          # dimensionless
dv.complex                               # the RegionComplex at p, equal to evaluate()'s

domain, namer, _ = dv.complex.to_domain(size)
nv = dv.node_velocity(generate(domain, namer))
nv.values, nv.curve, nv.vertex           # (N, 2) V of nodes on curves; their curve and vertex, -1 otherwise
```

**What V is.** x and p are both lengths in the document unit, so V is
dimensionless. V is computed at the rounded geometry, from the unrounded
expressions:
- **Length fields.** The expressions are evaluated once more with p as a dual
  number.
- **Vertices.** V solves the exact linear constraints of every curve and
  defining point through the vertex, in its field: rational, or a + b√D on a
  circle.
- **Split points of a whole circle.** They move radially.
- **Points along a curve.** On a line, a point moves with the end velocities
  interpolated linearly. On an arc, it moves with vc + dr·n, plus the ends'
  tangential parts interpolated in angle. The normal part is fixed by the
  geometry; the tangential part is a convention.

**Node velocity.** `node_velocity(mesh)` reads the curves' mesh edges as
`provenance_edges` does: exterior boundaries, interfaces and internal
constraints. It returns:
- the V of each node on a curve;
- the curve and the vertex each node lies on;
- zero for interior nodes, which galerkin moves. galerkin does not read this yet.

**Refused.** `TopologyChange` is a `GeometryError`. Its `features` hold the ids
of the features involved (`domain` for a domain side), and the message names
them and the location. It is raised when:
- the constraints at a vertex disagree, for example a touch that opens, an
  overlap that starts or three concurrent curves that separate;
- the constraints fix one direction only (a tangent contact);
- the exact evaluations at p ± δ differ in combinatorial signature, with
  δ = 2⁻²⁰ pm / 2^⌈log₂ max |V|⌉ (`dv.delta_pm`).

`exact_complex(document, p, offset)` is that unrounded evaluation. Also refused
by name:
- unknown, ratio and derived parameters;
- `3d` components;
- `path` arcs whose start, centre or end moves (static arcs are taken).

**Checked** (`tests/simcase/test_geometry_design_velocity.py`, pre-registered
D1–D8, 2026-11-08):

| Check | Criterion | Result |
|---|---|---|
| Closed forms | rect dA/dw = h, dP/dw = 2; circle dA/dr = 2πr, dP/dr = 2π, within 1e-12; corner V exact | pass |
| Derived points | line–line V exact; line–circle dx/dr = ±r/√(r² − 1) within 1e-12 | pass |
| Exact finite differences | linear dependence exact; y = 8/a observed order ≥ 1.9, ≤ 1e-9 at the smallest step | order 2.000; 3.6e-12 at 2⁻¹⁶ µm |
| Rounded-document finite differences | area of a cut circle, h = 1 µm to 1 nm, best within 1e-6 | 4.3e-10 at 1 nm (2.2e-12 at 0.1 nm; the 1 pm rounding floor appears at 1 pm) |
| Topology | touching rects, a corner leaving a domain side, tangent circles, a segment through a corner, a moving closed-path start: refused with the features; a touch linked by an expression is not refused | pass |
| Unchanged outputs | `parse` and `evaluate` unchanged; the complex is equal before and after a derivative | pass |
| Node velocity | circle nodes V·n = dr/dp within 1e-12, tangential 0; vertex nodes equal the vertex V | pass |

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
