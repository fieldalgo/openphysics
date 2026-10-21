# Heat documents with material regions

[한국어](../../locales/ko/pages/packages/simcase/thermal_regions2d.md)

A `thermal.steady2d` or `thermal.transient2d` document whose `geometry` has
`background` or `shapes` describes several materials. It uses the same geometry as electromagnetic
documents: named shapes, each naming a material, drawn in order over a
background (later shapes cut earlier ones). Thermal properties come from the
`materials` table. The mesh follows every region boundary. This is a headless
API/CLI path; Studio refuses these documents (see Limits below).

Rectangle documents without `background`/`shapes` keep the
[original contract](thermal_steady2d.md) and its
[boundary extension](thermal_steady_boundary2d.md) unchanged.

## Example

The shipped example `thermal_regions` (`examples/simcase/thermal_regions.json`,
`simcase example thermal_regions`) is a steel plate with an embedded copper
heater in insulation, cooled at the bottom and by convection at the top:

```json
{
  "openphysics": "0.2",
  "name": "Heated steel plate in insulation",
  "units": {"length": "mm", "temperature": "K"},
  "geometry": {
    "domain": {"xmin": 0, "xmax": 40, "ymin": 0, "ymax": 20},
    "background": {"material": "insulation"},
    "shapes": [
      {"name": "plate", "type": "rect", "x": 5, "y": 5, "w": 30, "h": 6, "material": "steel"},
      {"name": "heater", "type": "circle", "cx": 20, "cy": 8, "r": 2, "material": "copper", "mesh_size": 0.5}
    ]
  },
  "materials": {
    "steel": {"conductivity_w_mk": 45, "source": "document value"},
    "copper": {"conductivity_w_mk": 400, "source": "document value"},
    "insulation": {"conductivity_w_mk": 0.04, "source": "document value"}
  },
  "physics": {"heat1": {
    "type": "thermal.steady2d",
    "heat_source_w_m3": {"heater": 5e6},
    "dirichlet_temperature_k": {"bottom": 300},
    "convection": {"top": {"h_w_m2k": 10, "ambient_temperature_k": 295}}
  }},
  "mesh": {"size": 2, "min_angle": 28},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

```bash
simcase validate examples/simcase/thermal_regions.json
simcase run examples/simcase/thermal_regions.json -o heated_plate
```

## Input

- `units`: explicit `length` and `temperature: "K"`, as for rectangle documents.
  Geometry, shape sizes and mesh sizes use the length unit; property names with
  an SI suffix (`_w_mk`, `_w_m3`, `_w_m2`, `_w_m2k`, `_k`) are SI.
- `geometry.domain`: the rectangle; its four sides are the boundary tags
  `left`, `right`, `bottom`, `top`.
- `geometry.background`: `material` and optional `mesh_size`. The background
  region is named `background`.
- `geometry.shapes`: list of `rect` (`x`, `y`, `w`, `h`), `circle` (`cx`, `cy`,
  `r`) or `polygon` (`points`, at least three `[x, y]`, not self-intersecting),
  each with a unique nonempty `name` (not `background`), a `material` and an
  optional `mesh_size`. No other keys are accepted. Shapes are clipped to the
  domain. A shape that lies outside the domain or is smaller than 1e-12 of the
  domain area is refused (electromagnetic documents drop it without a message in
  the run log). A shape that later shapes cover completely gets no triangles; the
  run log names it. Zero-area pieces left by clipping (where a shape only touches
  the domain or another shape from outside) are not meshed.
- `materials`: `{material name: {...}}` with `conductivity_w_mk` > 0 (required
  for every material used), optional `volumetric_heat_capacity_j_m3k` > 0 (not
  used by steady heat) and an optional `source` note. Thermal properties are
  never taken from built-in optical materials; every used material must be
  defined here. Unused materials are allowed.
- `physics.<name>`: `type`, `heat_source_w_m3` (one number, or `{region name:
  number}` with regions not listed at zero), `dirichlet_temperature_k`,
  `outward_flux_w_m2` and `convection` with the side rules of the rectangle
  documents (corner conflicts refused, a Dirichlet side or positive Robin anchor
  required, no natural condition on a Dirichlet side). `conductivity_w_mk` here
  is refused: it comes from `materials`.
- `mesh`: `size` > 0 (length unit, required) and `min_angle` (degrees, default
  28, at most 33). `subdivisions` and `grading` are refused.
- `study` `{"type": "single"}`; `results.plots` must be false.

A source named for a region that does not survive meshing (fully covered by a
later shape) is refused when the document runs.

## Mesh and solve

Geometry and global/per-region mesh sizes are first converted to micrometres
with the same decimal-ratio conversion used by electromagnetic documents.
meshine then performs constrained Delaunay refinement with the requested
minimum angle. Its canonical coordinates are converted directly to SI metres
for the heat solver, without a round trip through the document unit.
Every shape boundary is a chain of element edges, so each triangle lies in
one region. Curved boundaries are inscribed polygons: the meshed area of a
circle is smaller than pi r^2 by O(h^2). The meshed problem is passed to
`galerkin.thermal.solve_steady_heat` with conductivity and source mapped by
region name ([multimaterial](../galerkin/multimaterial.md)).

A circle that no later shape overlaps (including one lying wholly inside it) and
no other boundary touches keeps its nodes on the exact circle. Any other circle
is meshed as a 128-sided polygon like the other shapes, so neighbouring regions
share one boundary.

**Meshing near small angles.** A circle that touches or crosses another
boundary, or a sharp polygon corner, makes an input angle below 60 degrees,
where plain Ruppert refinement does not finish. meshine treats such corners,
refuses an input it still cannot resolve with an error, and drops the
sub-resolution edges that clipping can leave
([meshine overview](../meshine/overview.md#small-input-angles)).
Every placement of the shipped example's heater (r = 2 mm) that used to run
without end now meshes. Measured on Linux, best of five runs:

| Heater placed across | Crossing | Time | Triangles | Smallest angle |
| --- | --- | --- | --- | --- |
| The bottom side | tangent | 0.51 s | 3030 | 1.41° |
| | 18° | 0.22 s | 2093 | 18.28° |
| | 20° | 0.19 s | 2062 | 21.09° |
| | 25° | 0.20 s | 2018 | 23.91° |
| | 35° | 0.25 s | 1979 | 28.11° |
| | 45° | 0.13 s | 1716 | 28.45° |
| The plate's top edge (from above) | tangent | 0.78 s | 3942 | 1.41° |
| | 18° | 0.51 s | 2554 | 18.28° |
| | 30° | 0.26 s | 2602 | 28.39° |
| | 45° | 0.18 s | 2116 | 28.52° |

The heater is meshed as a 128-sided polygon, so its corner with the edge is
1.41° when it is tangent and differs from the nominal crossing angle by up to
1.4° otherwise (18.28° at 18°, 21.09° at 20°). Where that corner is below the
28° bound, the triangle in it keeps the corner's angle. Every triangle below
28° lies within 0.03 mm of the touch or crossing point, and every triangle
reaching farther than 0.1 mm from it is at least 28.0°. Region areas equal the
clipped geometry to 1e-12 mm², except at 45°: there clipping leaves an edge of
6.3e-7 mm (1.4e-8 of the domain diagonal), which meshine drops, and the region
areas change by 3.1e-9 mm². The 30, 41, 50 and 60 degree crossings and a
0.001 mm clearance from the bottom side, which meshed before, give the same
meshes node for node. Crossings of either edge at every odd angle from 1 to 89
degrees mesh in at most 1.1 s.

What remains: termination is measured on these cases, not proved, and only on
Linux. An input meshine still cannot handle ends with an error instead of
running on: the point cap, the round limit, or a boundary point the
triangulation cannot resolve, which the error names (for example a vertex about
1e-9 to 1e-7 of the domain diagonal off an edge it does not belong to; move it
onto the edge or clear of it). Shapes clear of other boundaries still give the
best triangles. Electromagnetic documents use the same mesher and behave the
same way.

For inputs that convert to the same micrometre numbers, mm, m, um, nm and
custom length units now produce identical SI nodes, connectivity, region and
boundary tags, and steady/transient fields in the same numerical environment.
This includes an affine transient initial temperature: its domain origin uses
the same canonical-to-SI conversion as the mesh. SI-suffixed material, load and
temperature values and study times are unchanged. Saved `nodes_m` remain in
metres, and `model.json` retains the original document units.

This is not a promise for inputs that differ after conversion (even by one
ulp), or across library versions/platforms. Canonical meshing can change a
previous non-um document's discretization; analytical accuracy and convergence
criteria still apply. meshine itself does not promise unit-invariant node
positions.

## Results

`result_format` is `thermal.steady2d-regions-result-v1` and `field_layout`
`thermal2d-p1-node-cell-regions-v1`. The saved fields are those of the
boundary v2 layout (`nodes_m`, `triangles`, `temperature_k`, `heat_flux_w_m2`,
`load_w_per_m`, `reaction_w_per_m`, `residual_w_per_m`, `dirichlet_node_ids`,
`dirichlet_temperature_k`, `prescribed_outward_load_w_per_m`,
`ambient_load_w_per_m`, `convective_outward_w_per_m`, `system_rhs_w_per_m`)
plus `triangle_regions` (integer region id per triangle). Boundary fields are
always present (zero when no natural condition is given). The summary adds
`region_names` (index order of `triangle_regions`), `regions` (material,
triangle count and meshed area in m^2 per region), the `materials` table,
`conductivity_range_w_mk`, the mesh size and the achieved minimum angle.
Signs and units are those of the boundary contract: reaction is inward
thermostat heat, total outward heat is
`sum(prescribed_outward_load + convective_outward - reaction)`, all nodal
rates are W/m of depth.

## Validation

`tests/simcase/test_thermal_regions.py`, gates fixed before the
comparison:

| Check | Gate |
| --- | --- |
| Layered wall document (10 mm steel with Q = 2e5 W/m^3, 20 mm insulation, 400/300 K) against `refsol.thermal_multilayer.layered_slab`, mesh size 2, 1, 0.5, 0.25 mm | T L2 order >= 1.8 and flux L2 order >= 0.9 on the last two intervals; heat balance <= 1e-10 |
| Same wall in mm, m, um and nm | SI nodes, triangles, T and flux identical; existing absolute analytical error bounds retained |
| Shipped example against a direct `solve_steady_heat` call on the same mesh | Temperature and reaction identical; source heat = Q x meshed heater area to 1e-12; heater area within 1% of pi r^2; outward = source to 1e-10 |
| Saved fields and summary | Formats, `triangle_regions`, boundary fields, region table, materials, total area, model copy |
| CLI | validate and run exit 0; an existing output exits 1 |
| 19 invalid documents, a covered source region, a shape outside the domain and a shape below the sliver limit | Refused with `DocumentError` |
| A shape covered by a later shape | No triangles; named in the run log |
| Heater moved across the plate's top edge | Meshes (in a subprocess with a 300 s limit) as a polygon; heat balance <= 1e-10 |
| Heater tangent to the bottom side or the plate's top edge, or crossing the side at 18, 35 and 45 degrees and the edge at 18 and 45 degrees (7 placements that did not finish before) | Meshes in a subprocess with a 120 s limit, in under 10 s; tags exactly the four sides; region areas equal `resolve_regions` to 1e-9 mm^2 (1e-8 at 45 degrees); smallest angle >= the smaller of the input corner and 28 degrees, less 1e-6 |
| Exact-circle rule | Only a circle clear of every other boundary, with no later shape inside it, is meshed as an exact circle |
| A concave shape that clips to a polygon plus a line piece | Only the polygon part is meshed; heat balance <= 1e-10; an electromagnetic document keeps its exact circle |
| Rectangle documents | Non-empty `materials` still refused; original result format |
| Studio | Region documents are refused before any mesher or worker call |

Observed when first run (mesh size 2 → 0.25 mm):

| Quantity | Values | Orders |
| --- | --- | --- |
| T L2 (K m) | 4.07e-6, 1.03e-6, 2.59e-7, 6.42e-8 | 1.98, 2.00, 2.01 |
| Flux L2 (W/m) | 0.478, 0.241, 0.121, 0.0603 | 0.99, 1.00, 1.01 |

The engine-level per-region validation, including composite cylinders and
interface heat rates, is in [multimaterial](../galerkin/multimaterial.md).

## Transient documents

A `thermal.transient2d` document with `background`/`shapes` uses the same
geometry, `materials` table and `mesh` (`size`, `min_angle`) as the steady
region documents, with the transient time contract of
[thermal_transient2d](thermal_transient2d.md): `units.time: "s"`,
`study: {"type": "transient", "time_s": [...]}` with explicit increasing
seconds, `initial_temperature_k` (uniform number or `affine` object) and
`dirichlet_temperature_k` per side (constant or `{"values_k": [...]}` sampled at
the requested times, agreeing with the initial field at t0). Every used
material needs `conductivity_w_mk` and `volumetric_heat_capacity_j_m3k`;
`heat_source_w_m3` is a number or a `{region name: number}` map. Physics-level
`conductivity_w_mk` or `volumetric_heat_capacity_j_m3k` is refused. The shipped
example is `transient_thermal_regions` (`examples/simcase/transient_thermal_regions.json`).

Results use `thermal.transient2d-regions-result-v1` and
`thermal2d-transient-p1-node-cell-regions-v1`: the rectangle transient fields
plus static `triangle_regions`. The summary adds `region_names`, `regions`,
`materials` and the mesh size. `heat_content_j_per_m` is `1^T M T` with each
region's capacity. Full histories are kept in memory (O(steps x (nodes +
triangles))); the convergence study below peaked at about 825 MiB.

Validation (`tests/simcase/test_transient_thermal_regions.py`):

| Check | Gate |
| --- | --- |
| Q_i = r c_i in every region, insulated sides | T = T0 + r t at every node and time to 1e-10 of 300 K; flux below 1e-9 W/m^2 |
| Long-time limit (steps of 500 s to 1e4 s) against the steady region document | Identical mesh; final temperature within 1e-9 of the temperature rise |
| Direct `solve_transient_heat` call on the same mesh | Temperature, flux, reaction and heat content identical |
| Layered wall heated from a uniform 300 K (Q 2e5 / 5e4 W/m^3, ends 300 K) against `refsol.transient_heat_multilayer.LayeredWall.source_driven`, mesh size 4, 2, 1, 0.5 mm, dt = 1/64 s, observed at 20 s | T L2 order >= 1.8 and flux L2 order >= 0.9 on the last two intervals; at 0.5 mm halving dt changes each error by <= 5% |
| One material everywhere against the rectangle transient document | Source heat equal to 1e-12; maximum temperature within 2e-3 K |
| Saved fields, CLI, 11 invalid documents (one a shape outside the domain), Studio refusal | Formats, regions, materials; exit codes; `DocumentError`; no worker or mesher call |

Two earlier configurations of the convergence gate failed because backward
Euler's first-order time error was not separated from the space error:

| Configuration | Observed | Result |
| --- | --- | --- |
| dt = 1/4 s to 180 s | 20, 60, 180 s | T orders on the last interval 0.62, 0.52, 0.88; dt/2 changed T errors by 43%, 44%, 37% (flux orders 0.99-1.00 passed) |
| dt = 1/64 s to 20 s | 5, 10, 20 s | Last-interval T orders 1.72, 1.86, 1.92; dt/2 changed T errors by 13%, 7.1%, 4.4% |

The retained gate observes 20 s, the only time that met the separation gate in
the second run; that time was chosen after the run. Observed (mesh size 4 →
0.5 mm): T L2 1.81e-4, 4.75e-5, 1.18e-5, 3.11e-6 K m (orders 1.93, 2.01, 1.92),
flux L2 0.942, 0.477, 0.241, 0.121 W/m (orders 0.98, 0.99, 1.00), dt/2 change
4.4% (T) and 3e-8 (flux). Earlier transient times at these resolutions are
covered only by the exact-reproduction and engine-equality checks above and by
the engine validation in [multimaterial](../galerkin/multimaterial.md).

## Limits

- Studio refuses steady and transient region documents (its heat views read `mesh.subdivisions`);
  use the CLI or Python API.
- Piecewise-constant isotropic properties; perfect contact at interfaces.
- Next to a circle that touches or shallowly crosses another boundary, or a
  sharp polygon corner, triangles in either region can be as sharp as the input
  corner or a little sharper (measured 13.0° beside a 14° polygon corner); an
  input meshine cannot resolve ends with an error (see Mesh and solve).
- Plane geometry of unit depth; no thermal properties from built-in materials.
- The VTU export (`simcase.export`, extra `simcase[export]`) does not accept the
  region layouts yet; it refuses them as an unsupported field layout.

### Canonical length regression

`tests/simcase/test_thermal_length_canonical.py` compares a translated domain
with rectangles, an isolated circle, a polygon, background and per-shape mesh
sizes in mm, m, um, nm and a custom `in_m` unit. Steady flux/Robin loads and
transient affine initial data exercise both solve paths. Every numeric saved
array, region/material assignment and boundary tag must be identical; the
original model and declared units must be preserved. Existing layered-wall
analytical convergence tests remain required.
