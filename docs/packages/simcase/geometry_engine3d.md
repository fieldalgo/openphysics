# 3D boxes, slab layers, cylinders and spheres through meshloom (stage 5, experimental)

**English** | [한국어](../../locales/ko/pages/packages/simcase/geometry_engine3d.md)

[Documentation home](../../README.md)

**Status: experimental** until meshloom's own acceptance
([meshloom](../meshloom/overview.md)). `simcase.geometry_engine3d` is slice 1 of stage 5
of the [geometry document contract](geometry_document.md): it builds the 3D region
complex of the `box` features and slab layers of a `3d` component, under the contract's
[stage 5 compile conditions](geometry_document.md#stage-5-compile-conditions-amended-2026-11-27),
and meshes it with `meshloom.generate3d`. Slice 3 adds cylinders and spheres in meshloom's
builder shapes ([below](#cylinders-and-spheres-in-builder-shapes-slice-3)).

## Use

```python
import simcase

result = simcase.build_mesh3d(document)        # a format 0.3 document (dict or simcase.Document)
mesh = result.mesh                             # galerkin.Mesh3D, in metres
mesh.tagged_faces                              # {"x0": (F, 3), ..., "void": (F, 3)}
result.provenance_faces["cap.z1"]              # (F, 3) faces of every face that carries the name
result.selections["joint"]                     # ("boundary", (F, 3) faces) or ("region", tetrahedra)
result.selection_nodes["joint"]                # the node indices of a selection
result.complex                                 # the 3D region complex (cells, faces, provenance)
```

`build_mesh3d(document, component=None)` takes a document with a version 1 geometry
block (the component may be left out when there is one) and its `mesh` block:

| Key | Meaning |
|---|---|
| `mesh.element_size` | the size of every region that gives none |
| feature or background `element_size` | the size of that feature's or the background's regions |
| `mesh.controls` `{"select": <region selection>, "element_size": h}` | the size of the selected regions; later entries win |
| `mesh.element_count_limit` | default 600000; checked before meshing against T = 6.3 Σ V_r / h_r³ and passed to meshloom as its point cap |

A region takes the smallest size of its cells. The estimate is reported in
`result.diagnostics` as `I-MESH-ESTIMATE` (info), with the expected meshing time at 0.4–0.6 ms
per tetrahedron; above the limit, the document is refused with the estimate
(`E-MESH-ESTIMATE`). A size on a boundary selection, the distance
grading (`near`, `far`, `refinement_distance`) and `z_divisions` are refused by name for
3D components.

`simcase.estimate_mesh3d(document, component=None)` gives the estimate without meshing:
a `Mesh3DEstimate` with `component`, `tetrahedra` (T rounded to an integer), `limit` (the
`mesh.element_count_limit` in effect), `seconds` (T at 0.6 ms per tetrahedron, the slow end
of the engine's 0.4–0.6 ms) and `diagnostics` (the same `I-MESH-ESTIMATE` that
`build_mesh3d` adds). It runs exactly what `build_mesh3d` runs before meshloom, so every
refusal that blocks meshing blocks the estimate too, in the same words:
`E-MESH-ESTIMATE` above the limit, `E-CONTRACT` (a piece below the mesher tolerance),
`E-3D-COMBINATION` and the others. Studio calls it to refuse an
over-limit document before it starts a meshing process ([3D view](studio_3d.md#mesh)).
A component holding only one slab `layers` feature, which `build_mesh3d` refuses for the
`meshine.extrude` route, gets the same T from its exact complex; the extrude mesh's own count
differs (E1 at 0.8 mm: T 3,076, 7,680 made).

`simcase.geometry_engine3d.evaluate3d(model, component=None)` returns the complex alone,
for a model from `simcase.geometry_document.parse`. It refuses a component holding one
`layers` feature, which is meshed on the extrude route. For display (Studio),
`simcase.display_complex3d(model, component=None)` returns the exact complex of any `3d`
component slice 1 takes, that one included: the complex the meshloom route would build. It
meshes nothing and changes nothing `build_mesh3d` does or refuses. `model` is what
`simcase.parse_geometry` returns; `component` may be left out when the model has exactly one
`3d` component (2d footprints beside it are allowed). An unknown name, a `2d` or axisymmetric
component, and an omitted name with no or several `3d` components are refused by name
(`E-CONTRACT` at `geometry.components.<name>`).

## What it builds

- **Prisms.** Every `box` and every slab layer (a layer with a `material` and no
  `footprint`) is a vertical prism. A slab layer covers the domain's x–y extent between
  its exact z levels; its cells are named by its `region`, otherwise by its material, as
  on the extrude route.
- **Later wins.** The footprints of all prisms go once through the
  [stage 2 engine](geometry_engine.md) with every boundary kept, so each fine 2D cell
  carries the exact set of prisms whose footprint contains it. Cutting the component at
  every distinct z level, a cell's region in a slab is that of the last active prism that
  contains it, or the background. This equals the contract's per-slab rule: the
  later-wins arrangement of the prisms active in that slab, resolved by the stage 2 engine. A cell is a fine
  2D cell times one slab; `material: null` makes it void.
- **Faces.** A horizontal face lies where the regions above and below differ, or where
  one side is outside the domain; a vertical face where the regions on the two sides of a
  fine curve differ. Faces between two void cells, or between a void cell and the outside,
  are not meshed and not listed. Faces with equal sides and provenance are merged, in the
  plane and across slabs; a horizontal face whose boundary meets itself at a vertex is
  split into rectangles, so that every loop meshloom receives is simple.
- **Provenance.** A face carries every part whose surface contains it, whether or not
  that feature owns a neighbouring cell: `<box>.x0` … `<box>.z1`, `domain.x0` …
  `domain.z1`, and for a slab layer `<id>.<layer>.bottom`, `<id>.<layer>.top` and
  `<id>.<layer>.domain.x0` … `<id>.<layer>.domain.y1` on its sides: the contract's
  `<id>.<layer>.domain.<side>` with the 3D domain face names, because the 2D names would
  clash with the layer caps (`<id>.<layer>.bottom` and `.top`). `meshine.extrude` emits no
  provenance, so the two routes cannot name these differently. A vertical face
  carries the parts of the prisms active in its slabs only.
- **Tags.** An exterior face on a domain face is tagged `x0`–`z1`; every other exterior
  face (against a void cell) is tagged `void`. `boundary_tags` renames them, first
  matching entry first.
- **Selections** follow the contract's [selector rules](geometry_document.md#selector-rules-frozen):
  `{"boundary": "z0"}` (a tag), `{"boundary": "domain.z0"}` and `{"boundary": "cap.z1"}`
  (provenance names), `{"boundary": "cap"}` (every face whose provenance names the
  feature), `{"boundary": {"between": [a, b]}}`, `{"boundary": {"of": a}}`,
  `{"region": name}`, `{"region": {"feature": id}}` and `{"region": {"material": m}}`.
  A named selection that selects nothing is refused unless it is `optional`.

## Cylinders and spheres in builder shapes (slice 3)

A `3d` component whose features exactly match one of `meshloom.builder`'s public
configurations, on its pm values, is meshed by that builder at `mesh.element_size`. The
builder's input goes to `meshloom.generate3d` unchanged (with `max_points` =
`mesh.element_count_limit`), so the mesh is the builder's mesh, bit for bit; its tags are
renamed to the document's provenance names afterwards.

| Document | Builder | Provenance |
|---|---|---|
| one `cylinder` with `zmin`, `zmax` the domain's, strictly inside it in x–y; background with a material (the slab) | `via_in_slab` (C4) | `<id>.side`, `<id>.bottom` and `<id>.top` (with `domain.z0` and `domain.z1`), `domain.x0` … `domain.z1` |
| one `sphere` strictly inside the domain; background with a material | `sphere_in_box` (C5) | `<id>.surface`, `domain.x0` … `domain.z1` |
| one `sphere`; background `material: null` (the domain only bounds it) | `sphere` (C1) | `<id>.surface` |
| concentric spheres listed outermost first (later wins gives the shells); background `material: null`; the innermost may be `material: null` (a hole) | `nested_spheres` (C11) | `<id>.surface` of each |

Exterior faces on a domain face take its tag (`x0`–`z1`), the others `void`. Interfaces are
keyed by region pair, as for boxes. The builders sample the curved surfaces (ring and geodesic
sampling live in meshloom), and each sampled surface is reported as `I-SURFACE-SAMPLED` (info)
at its feature: the provenance name, the kind, the exact parameters in pm, h in m, the builder
with `meshloom.__version__` and `kernel_version()`, the sampling read from the builder's points
(points per ring m and the ring z levels with the sagitta bound r(1 − cos(π/m)), or the
geodesic frequency n), and the measured V5 deviation of the mesh nodes on the surface from the
exact parameters. `result.complex` is `None`: the exact complex of a sampled surface is not
built yet, and `evaluate3d` and `display_complex3d` refuse such a component by name
(`E-3D-COMBINATION` at `geometry.components.<name>`).

One size only: a feature or background `element_size`, `mesh.controls` sizes, `selections`
and `boundary_tags` are refused by name with a sampled surface, until a later slice.

The below-tolerance refusal applies here too, before the hand-off and after the touch and cross
stems: the smallest exact clearance, a via's surface to each domain side (C4), a sphere to each
domain face (C5) or the difference of consecutive radii (C11), below `MESHER_RELATIVE_TOLERANCE`
(3e-8) of the diagonal is refused with `E-CONTRACT` at `geometry.components.<name>` and the
parser's sentence, naming the later feature. C1's and C11's domains only bound void space (the
builders mesh no box there), so a sphere's distance to them is not checked.

## The meshloom hand-off

- **Coordinates (rule H1).** Each pm value k becomes `float(Fraction(k, 10**12))` metres,
  rounded once, so the points of an axis-aligned plane share one double and the plane
  stays exact. Two distinct values of one axis that round to one double are refused,
  naming both.
- **Facets.** Each face is one planar facet, outer loop first. Every point of the
  complex that lies on a facet's edge is put into that edge, so two facets meet in whole
  edges or points and never overlap partly along a line. Each facet has its own tag
  (`f<i>`), which the result maps back to its tag and provenance.
- **Regions.** One exact interior point per bounded component, named by its region; an
  enclosed void gets `None` and is not meshed. A void that reaches the domain boundary is
  outside the mesh.
- **Sizes.** `h` is one size, or one per region.
- **Mesh faces.** Exterior faces come from the facet tags. Interior faces come from
  meshloom's `interfaces` and are assigned to their facet by exact equality of the
  axis-aligned plane and, when a plane holds several facets, an exact test of the face's
  centroid against each facet's polygon. `mesh.interfaces` is keyed by the sorted pair of
  region names, wound from the first to the second.
- **Errors.** meshloom's errors (`InvalidPLC`, `RecoveryError`, `RoundingError`,
  `RegionError`, `RefineError`, `MeshError`) are re-reported as
  `simcase.geometry_engine3d.Mesh3DError` with the provenance names and features of the
  facets the error names (`.cause`, `.facets`, `.provenance`).

The mesh carries meshloom's guarantees on the doubles galerkin receives: exact
`orient3d > 0` for every tetrahedron and the output contract of the
[3D validation plan](../meshine/validation3d.md).

## What it refuses

Code `E-3D-COMBINATION` at the feature's `features[i]`, with the contract's message stems:

- `extrude`, and a `cylinder` or `sphere` in no builder shape: `<type> '<name>' is not taken
  yet in a 3d component; boxes and slab layers are, and cylinders and spheres in meshloom's
  builder shapes only (one cylinder through the whole slab, one sphere, concentric spheres)`;
- a cylinder crossing or touching a domain side, a sphere touching or crossing a domain face,
  and two spheres touching or crossing, with the contract's fixed stems (`cylinder '<a>'
  crosses the side domain.<s> between z = <z0> and <z1> <unit>; …`, `cylinder '<a>' touches
  domain.<s> at one line; …`, `sphere '<a>' touches or crosses domain.<s>; …`, `spheres '<a>'
  and '<b>' touch or cross; …`). The other stems (a cap partly on a face, two cylinders
  crossing, a sphere containing a prism) have no builder shape: such documents get the
  staging message;
- footprint `layers` with other features: `layers '<name>' has footprint layers; with other
  features a 3d component takes slab layers only, until a later slice`;
- two values that round to one double: `<a>.<part> and <b>.<part> round to the same
  coordinate <x> m`;
- `circle_segment_count` in `mesh.controls`: `mesh.controls: circle_segments on '<select>'
  is not taken for 3d surfaces yet; use size` (at `mesh.controls[i]`).

Before the hand-off, a piece of the arrangement below the mesher tolerance
(`MESHER_RELATIVE_TOLERANCE` = 3e-8 of the component's bounding-box diagonal, the contract's
[What the grid does not fix](geometry_document.md#internal-grid-1-pm-frozen)) is refused as the
parser refuses a whole feature, with `E-CONTRACT` at `geometry.components.<name>` and the same
sentence: `feature '<name>' is <size> pm across, <ratio> of the component's diagonal, below the
mesher tolerance 3e-08; it would vanish in the mesh. …`. The pieces are the distance from a 2D
vertex to a fine curve that does not end there (a short curve, or a thin neck between two
curves), the height of a slab that a meshed vertical face spans, and the width (2 area /
perimeter) of a meshed horizontal face; the later feature whose part bounds the piece is named.
The check runs after the rounding check.

A component that holds only one `layers` feature keeps the `meshine.extrude` route
(`simcase.geometry_document.layer_stack`, unchanged) and is refused by `build_mesh3d`
(`E-CONTRACT`), and `em.cavity3d` documents keep their own route and results.

## Validation

Pre-registered checks, run by `tests/simcase/test_geometry_engine3d.py` (G1–G6, P1) and
`tests/simcase/test_geometry_cavity3d.py` (P4, P5):

| ID | Case | Metric | Threshold | Measured (Linux, 2026-11-27) |
|---|---|---|---|---|
| G1 | 200 seeded later-wins sets of at most 8 boxes on a 4 × 3 × 2 grid (mm), with touches, nesting, shared planes, boxes beyond the domain and void, at h = 0.25 grid unit; a brute-force oracle (the last box containing a point) | (a) tetrahedra whose exact centroid the oracle puts in another region; (b) relative region volume error | (a) 0; (b) ≤ 1e-12 | all 200: (a) 0; (b) at most 2.8e-16 (199 sets meshed, 496–12,664 tetrahedra; seed 69, one void box over a void background, has nothing to mesh and is refused by name) |
| G2 | G1 sets and E1 | faces under a provenance name off the part's exact surface; complex faces on a part's surface that do not list it; mesh area per name against the exact faces (1e-12); exterior faces not in exactly one tag | 0 | 0 |
| G3 | every mesh of the test file | V1 (exact orient3d ≤ 0 on the output doubles) and V2 of [validation3d](../meshine/validation3d.md) | 0; all hold | 0; all hold |
| G4 | E1 written in m, mm, µm and nm, h = 0.8 mm | SHA-256 of the canonical mesh arrays | identical | identical |
| G5 | E1, h = 0.8 mm, 3 fresh processes | SHA-256 | identical | identical |
| G6 | one document per refusal above | code, path, names in the message | 100% | 100% |
| P1 | E1 through meshloom and through `meshine.extrude`, against `refsol.thermal3d.layered_slab` (exact for P1) | max nodal \|T_h − T\|; relative error of the top heat rate | ≤ 1e-10; ≤ 1e-9 | below |
| P4 | E4 at h = 0.24, 0.12, 0.06 m through `galerkin.solve_cavity`, against `refsol.cavity.rectangular_cavity_modes` | relative k² error of the first cluster (the three modes at k² = 2π²), the maximum over the three | decreases with h; observed order ≥ 1.5; finest < 1e-2 | 1.5e-2, 1.9e-3, 3.8e-4; order 2.63; finest 3.8e-4 |
| P5 | E5 at h = 0.24, 0.12, 0.06 m through `galerkin.solve_material_cavity`, against `refsol.material_cavity.slab_loaded_cavity_modes` | relative k² error of the first four modes, ascending computed matched to ascending reference roots, the maximum over the four | decreases with h; observed order ≥ 1.5; finest < 2e-2 | 1.1e-2, 2.8e-3, 9.0e-4; order 1.77; finest 9.0e-4 |

E1 is three slab layers of thickness 1, 0.5 and 1 mm (z levels 0, 1, 1.5, 2.5 mm) with
k = 1, 0.01 and 1 W/(m K) over a 10 × 10 mm domain; T = 0 on `z0`, T = 1 on `z1`, sides
insulated; solved with `galerkin.solve_steady_heat_3d`.

P1, measured:

| Route | h (mm) | Tetrahedra | max \|T_h − T\| | top heat rate |
|---|---|---|---|---|
| meshloom | 0.8 | 4,891 | 1.6e-15 | 1.7e-15 |
| meshloom | 0.4 | 28,284 | 2.3e-15 | 1.4e-14 |
| `meshine.extrude` | 0.8 | 7,680 | 4.8e-15 | 8.8e-14 |
| `meshine.extrude` | 0.4 | 49,152 | 9.4e-15 | 5.0e-15 |

E4 and E5 are cavities written as geometry documents and meshed by `build_mesh3d`; the tests
call galerkin's public cavity solvers on the `Mesh3D` with every face PEC. E4 is one `3d`
component with the domain [0, 1]³ m, a vacuum background and no features. E5 adds a `box`
over z ∈ [0, 0.5] m with the full x and y extent, which is the region `slab` (ε_r = 4); the rest
is the region `background` (vacuum). The observed order is the least-squares slope of log e
against log h over the three sizes. The pairwise orders, the spurious-mode count (computed modes
more than 10% from every reference root) and the times are reported and not gated. The
reference roots of E5 are k²/π² = 0.6907, 0.6979, 0.6979, 1.0021, then 1.4625 twice.

P4 and P5, measured (one core; mesh and solve seconds):

| Case | h (m) | Nodes | Tetrahedra | Error | Spurious | Mesh (s) | Solve (s) |
|---|---|---|---|---|---|---|---|
| E4 | 0.24 | 243 | 682 | 1.5e-2 | 0 | 0.2 | 0.1 |
| E4 | 0.12 | 1,072 | 3,897 | 1.9e-3 | 0 | 0.8 | 0.4 |
| E4 | 0.06 | 5,867 | 26,122 | 3.8e-4 | 0 | 4.5 | 13 |
| E5 | 0.24 | 270 | 753 | 1.1e-2 | 0 | 0.2 | 0.1 |
| E5 | 0.12 | 1,145 | 4,197 | 2.8e-3 | 0 | 0.8 | 1.0 |
| E5 | 0.06 | 6,189 | 27,775 | 9.0e-4 | 0 | 4.8 | 203 |

The pairwise orders are 2.99 and 2.27 for P4, and 1.94 and 1.61 for P5.

Pull requests run G1 on 25 fixed seeds of the 200 (every eighth) in the source test parts;
`OPENPHYSICS_GEOMETRY3D_FULL=1` runs all 200, as the CI job `geometry3d-full` does on main
pushes and manual dispatch ([what CI runs](../../development.md#what-ci-runs)). P4 and P5 run
in that job only. Pull requests run a smoke test of E4 and E5 at h = 0.24 m, which checks only
that each case meshes and solves.

Slice 3, pre-registered (decision 2026-11-27-openphysics-geometry-stage5-adopted), run by
`tests/simcase/test_geometry_engine3d_curved.py`; C1, C4, C5 and C11 are the
[3D validation plan](../meshine/validation3d.md)'s cases written as documents (in m):

| ID | Case | Metric | Threshold | Measured (Linux, 2026-11-27) |
|---|---|---|---|---|
| G7 | C4 at h 0.2, 0.1; C5 at 0.24, 0.12; C11 at 0.2, 0.1, against `generate3d(**builder.<fn>(...))` | nodes, connectivity, regions; faces per renamed tag | bitwise identical | identical (4,134–26,445 tetrahedra) |
| G8 | C4 (r = 0.3 through [−1,1]² × [0,1]) at h 0.2, 0.1, 0.05 | e_V = \|V_via − πr²L\| / πr²L; least-squares slope against the ring chord s = 2πr/m | slope ≥ 1.8; e_V(finest) ≤ 5e-3 | slope 1.99; e_V 1.9e-2, 8.6e-3, 3.1e-3 (m = 16, 24, 40) |
| G9 | C1 (unit ball) at h 0.2, 0.1, 0.05 | e = \|ΣV − 4π/3\| / (4π/3) (V6); slope against h | slope ≥ 1.8; e(0.05) ≤ 1.5e-3 | slope 1.87; e 1.5e-2, 4.6e-3, 1.1e-3 |
| G10 | G7's meshes | V5's δ on every node of a curved surface, against the document's exact parameters in pm | ≤ 1e-15 | at most 1.9e-16 |
| G2, G3 | G7's meshes | provenance faces on their parts (curved within 1e-12 of the diagonal); one tag per exterior face; V1, V2 | 0; all hold | 0; all hold |
| G6 | one document per stem that builder shapes can meet, and per staged configuration | code, path, names | 100% | 100% |
| S1 | slice 1's 25 pull-request G1 seeds and E1 | complex and mesh SHA-256 against main a5c61f8 | identical | identical |

G8 and G9 run on main pushes and manual dispatch only (`geometry3d-full`).

## Limits

- Experimental: meshloom is not yet accepted, and the mesh's quality is meshloom's.
- Boxes and slab layers only. Footprint layers alone take the extrude route; with other
  features they are refused until a later slice. Cylinders and spheres only in the four
  builder shapes, with one element size; general cylinders and spheres in a later-wins
  arrangement wait for meshloom's composable samplers.
- Builder-shaped components are meshed by `build_mesh3d`, but `evaluate3d` and
  `display_complex3d` refuse them by name (no exact complex of a sampled surface is built
  yet), so a 3D view cannot draw them yet.
- One size per region; no graded sizes or sizes on surfaces yet.
- Pieces thinner than about 1e-7 of the diagonal, though above the tolerance, can make meshloom
  not return: two boxes with a face offset by 862 pm (6e-8 of a 14.4 mm diagonal) at h = 0.8 mm
  did not mesh in 600 s, where the same boxes without the offset mesh in about a second
  (2026-11-27; a meshloom backlog item). Studio meshes in a separate, cancellable process.
- Faces and cells are listed per fine 2D cell and slab; the complex is an in-memory
  diagnostic structure, not a persisted format.
- Python: the complex is built in pure Python with exact integers. A component with many
  boxes builds an arrangement that grows with the number of distinct planes.
