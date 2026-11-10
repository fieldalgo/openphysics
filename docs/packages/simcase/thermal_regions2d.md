# Heat documents with material regions

[한국어](../../locales/ko/pages/packages/simcase/thermal_regions2d.md)

A `thermal.steady2d` or `thermal.transient2d` document whose `geometry` has
`background` or `shapes` describes several materials. It uses the same geometry as electromagnetic
documents: named shapes, each naming a material, drawn in order over a
background (later shapes cut earlier ones). Thermal properties come from the
`materials` table. The mesh follows every region boundary. The headless API and
CLI run these documents, and Studio validates, runs and shows them within its
region limits (see Limits below). Region documents are
[format 0.3](document_format.md): every value carries its unit and keys are registry
quantity names; a format 0.2 region document is refused by name (`E-FORMAT`).

Rectangle documents without `background`/`shapes` keep the
[original contract](thermal_steady2d.md) and its
[boundary extension](thermal_steady_boundary2d.md) unchanged.

## Example

The shipped example `thermal_regions` (`examples/simcase/thermal_regions.json`,
`simcase example thermal_regions`) is a steel plate with an embedded copper
heater in insulation, cooled at the bottom and by convection at the top:

```json
{
  "openphysics": "0.3",
  "name": "Heated steel plate in insulation",
  "geometry": {
    "length_unit": "mm",
    "depth": null,
    "domain": {"xmin": 0, "xmax": 40, "ymin": 0, "ymax": 20},
    "background": {"material": "insulation"},
    "shapes": [
      {"name": "plate", "type": "rect", "x": 5, "y": 5, "w": 30, "h": 6, "material": "steel"},
      {"name": "heater", "type": "circle", "cx": 20, "cy": 8, "r": 2, "material": "copper", "element_size": "0.5 mm"}
    ]
  },
  "materials": {
    "steel": {"thermal_conductivity": "45 W/(m K)", "source": "document value"},
    "copper": {"thermal_conductivity": "400 W/(m K)", "source": "document value"},
    "insulation": {"thermal_conductivity": "0.04 W/(m K)", "source": "document value"}
  },
  "physics": {"heat1": {
    "type": "thermal.steady2d",
    "heat_source_density": {"heater": "5000000 W/m^3"},
    "prescribed_temperature": {"bottom": "300 K"},
    "convection": {"top": {"heat_transfer_coefficient": "10 W/(m^2 K)", "ambient_temperature": "295 K"}}
  }},
  "mesh": {"element_size": "2 mm", "minimum_angle": "28 deg"},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

```bash
simcase validate examples/simcase/thermal_regions.json
simcase run examples/simcase/thermal_regions.json -o heated_plate
```

## Input

- `geometry.length_unit`: the unit of the domain and shape numbers, which are plain
  numbers (as in every format 0.3 geometry); `geometry.depth`: a length such as
  `"40 mm"`, or `null` for results per metre of depth.
- `geometry.domain`: the rectangle; its four sides are the boundary tags
  `left`, `right`, `bottom`, `top`.
- `geometry.background`: `material` and optional `element_size` (a length such as
  `"0.5 mm"`). The background region is named `background`.
- `geometry.shapes`: list of `rect` (`x`, `y`, `w`, `h`), `circle` (`cx`, `cy`,
  `r`) or `polygon` (`points`, at least three `[x, y]`, not self-intersecting),
  each with a unique nonempty `name` (not `background`), a `material` and an
  optional `element_size`. No other keys are accepted. Shapes are clipped to the
  domain. A shape that lies outside the domain or is smaller than 1e-12 of the
  domain area is refused (electromagnetic documents drop it without a message in
  the run log). A shape that later shapes cover completely gets no triangles; the
  run log names it. Zero-area pieces left by clipping (where a shape only touches
  the domain or another shape from outside) are not meshed.
- `materials`: `{material name: {...}}` with `thermal_conductivity` > 0 (such as
  `"45 W/(m K)"`, required for every material used), `volumetric_heat_capacity` > 0
  (required by transient heat) and an optional `source` note. The table is shared with
  region mechanics and region electric conduction, so `youngs_modulus`, `poisson_ratio`,
  `linear_expansion_coefficient` and `electrical_conductivity` are accepted and checked
  when present. A property heat does not read is reported as `I-UNUSED-PROPERTY` (checked,
  not used). Thermal properties are never taken from built-in optical materials; every used
  material must be defined here (`E-MATERIAL-UNKNOWN`, `E-PROPERTY-MISSING`). Unused
  materials are allowed.
- `physics.<name>`: `type`, `heat_source_density` (one quantity such as
  `"5e6 W/m^3"`, or `{region name: quantity}` with regions not listed at zero; an
  unknown region is `E-SELECTION-UNKNOWN`), `prescribed_temperature`,
  `inward_heat_flux` and `convection` (`heat_transfer_coefficient`,
  `ambient_temperature`) with the side rules of the rectangle documents (corner
  conflicts refused, a prescribed side or positive convection anchor required, no
  natural condition on a prescribed side). A side with no condition is insulated and
  reported once as `I-DEFAULT-BOUNDARY` at `physics.<name>.inward_heat_flux.<side>`.
  `thermal_conductivity` here is refused: it comes from `materials`. A [version 1
  geometry block](geometry_document.md) may name more boundaries, see
  [Named boundaries](#named-boundaries).
- `mesh`: `element_size` (a length, required) and `minimum_angle` (default `"28 deg"`,
  at most 33 degrees); `element_count_limit` (default 600000) refuses a mesh whose
  estimated element count is larger (`E-MESH-ESTIMATE`). `subdivision_count` and
  `grading` are refused. A version 1 block may add `mesh.controls`
  (`element_size`, `refinement_distance`, `circle_segment_count` on its selections).
- `study` `{"type": "single"}`; `results.plots` must be false.

The reader records every default in `defaults_applied` and every value it read in
`resolved_inputs` (authored text, SI value and unit).

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

For inputs that convert to the same micrometre numbers, the length units mm,
m, um and nm produce identical SI nodes, connectivity, region and boundary tags,
and steady/transient fields in the same numerical environment. This includes an
affine transient initial temperature: its domain origin uses the same
canonical-to-SI conversion as the mesh. Material, load and temperature values and
study times are resolved from their own units and do not depend on the length
unit. Saved `node_coordinates` are in metres, and `model.json` keeps the document
as written. The one summary value that can move by rounding across length units is
`minimum_triangle_angle`, measured on the triangulation in the document's numbers
(compared to 1e-12 in the regression below).

This is not a promise for inputs that differ after conversion (even by one
ulp), or across library versions/platforms. Canonical meshing can change a
previous non-um document's discretization; analytical accuracy and convergence
criteria still apply. meshine itself does not promise unit-invariant node
positions.

## Results

`result_format` is `thermal.steady2d-regions-result-v2` and `field_layout`
`thermal2d-p1-node-cell-regions-v2` (the format 0.2 pair `-result-v1` and
`-regions-v1` is retired: a saved result with it is refused by name). The saved
fields are those of the rectangle boundary layout under their registry names
(`node_coordinates`, `triangles`, `temperature`, `heat_flux`,
`generated_heat_rate_per_depth`, `reaction_heat_rate_per_depth`,
`residual_heat_rate_per_depth`, `prescribed_node_ids`, `prescribed_temperature`,
`outward_prescribed_heat_rate_per_depth`, `ambient_convective_heat_rate_per_depth`,
`outward_convective_heat_rate_per_depth`, `applied_heat_rate_per_depth`) plus
`triangle_regions` (integer region id per triangle, no unit). Boundary fields are
always present (zero when no natural condition is given). `field_units` gives each
array's unit. The summary adds `region_names` (index order of `triangle_regions`),
`regions` (material, triangle count and meshed `area` per region), the `materials`
table, `minimum_thermal_conductivity`, `maximum_thermal_conductivity`, the mesh counts
and the achieved `minimum_triangle_angle` (rad); every physical value is
`{value, unit}`, and the summary keeps `resolved_inputs`, `defaults_applied`,
`diagnostics`, `extent` and `timing.wall_time`. Signs and units are those of the
boundary contract: reaction is inward thermostat heat, total outward heat
(`outward_heat_rate_per_depth`) is
`sum(outward_prescribed + outward_convective - reaction)`, all nodal rates are W/m
of depth.

## Named boundaries

A document with a [version 1 geometry block](geometry_document.md) may give
`prescribed_temperature`, `inward_heat_flux` and `convection` entries (and
the transient runner its `prescribed_temperature`) to boundaries beyond the
four domain sides:

- the exterior tags the [stage 2 engine](geometry_engine.md) declares: a
  `boundary_tags` name, and `outer` on the border of a void feature
  (`material: null`) or of a sliver gap;
- a boundary selection of the component (`selections`); the mesh names its
  nodes under the selection's name (`mesh.boundary[name]`) and, when every
  curve of the selection lies on the exterior (the domain or a void), tags its
  edges too (`mesh.boundary_edges[name]`), beside the side or `outer` tag the
  same edges carry. `prescribed_temperature` may name any selection, an
  interface between two regions included (a prescribed temperature on an
  internal surface; galerkin fixes interior nodes, 2026-11-08); flux and
  convection need exterior edges, so an interface selection is refused by name
  for them.

A void feature is a hole: it is not meshed and its border is an exterior
boundary that is **insulated unless named** (HQ decision 2026-11-08). A side
that borders a void feature only has no mesh edge and is refused by name when
data is given to it. One mesh edge takes one flux and one convection entry: a
side tag and a selection on the same edges, both given data, are refused.
Every boundary selection's edges, interior ones included, are on the galerkin
mesh as `mesh.selection_edges` (the contract's `provenance_edges` read for
selections); nothing else reads them yet.

Checks G5-1 to G5-5 (`tests/simcase/test_thermal_named_boundaries.py`,
pre-registered in the HQ work record on 2026-11-08, measured the same day on
Linux, Python 3.12, pinned environment): a steel disc with a void hole in a
void plate, Dirichlet on both circles through `boundary_tags` and through a
selection, matches the logarithmic profile within 1e-3 of the temperature
difference at the mid radius; a flux on the hole wall gives exactly `g` times
the wall's polygon length and a convection on it the series-resistance rate
within 2e-3, both with heat balance within 1e-10; an unnamed hole is insulated
with the balance within 1e-10; the refusals (interface selections for flux and
convection, unknown names, a region selection, doubled edges); the transient
runner's Dirichlet on a selection and its refusals; a document without a
version 1 block keeps its four sides. G6-2 and G6-3 (2026-11-08): an interface selection fixed at a
temperature gives the same outward heat on the domain sides as the same
rectangle cut out as a void with that temperature on its wall, within 1e-3, and
the fixed region sits at that temperature within 1e-9; the transient runner's
long-time solution with an interface selection matches the steady one within
1e-6.

## Axisymmetric documents

A `thermal.steady2d` or `thermal.transient2d` region document whose [version 1
geometry block](geometry_document.md) has an `axisymmetric` component is a body
of revolution: the component's (x, y) are (r, z), `domain.xmin` is the inner
radius (`0` for a solid) and the same features, materials and sources apply.
The mesh is built in (r, z) by the [stage 2 engine](geometry_engine.md) and
solved with galerkin's [axisymmetric measure](../galerkin/thermal_axisymmetric.md)
(`coordinate_system="axisymmetric"`, volume measure `2πr dr dz`; the transient
runner through [axisymmetric transient heat](../galerkin/transient_heat.md#axisymmetric-transient-heat)).

- **Sides.** With `xmin == 0` the r = 0 side is the mesh tag `axis`, which is
  the symmetry axis: it carries natural regularity and takes no
  `prescribed_temperature`, `inward_heat_flux` or `convection` entry
  (refused by name, as is `left`, which such a domain does not have). The
  physical sides are `right` (the outer radius), `bottom` and `top`. An annulus
  (`xmin > 0`) keeps `left` as its inner radius.
- **Result.** The run returns an `AxisymmetricRegionThermalRunResult`, whose
  identifiers are `thermal.axisymmetric-regions-result-v2` and
  `thermal-axisymmetric-p1-node-cell-regions-v2`. Its nodal rates are
  **full-revolution powers in W**, under the registry names without
  `_per_depth`: `generated_heat_rate`, `reaction_heat_rate`, `residual_heat_rate`,
  `outward_prescribed_heat_rate`, `ambient_convective_heat_rate`,
  `outward_convective_heat_rate` and `applied_heat_rate`; the summary's totals are
  named the same way (`generated_heat_rate`, `outward_heat_rate`, ...) and it records
  `coordinate_system: "axisymmetric"`. Temperature (K), heat flux (W/m²) and triangle
  regions are as in a Cartesian run; each region's area is its `meridional_area`.
  The Cartesian identifiers and `_per_depth` names are never used for such a result,
  and `geometry.depth` is refused (a body of revolution has no depth).
- **Transient result.** A `thermal.transient2d` document returns an
  `AxisymmetricTransientRegionRunResult` with the identifiers
  `thermal.axisymmetric-transient-regions-result-v2` and
  `thermal-axisymmetric-transient-p1-node-cell-regions-v2`: the histories of
  a [transient region result](#transient-documents) with the nodal rates in W
  under `generated_heat_rate`, `reaction_heat_rate`, `residual_heat_rate` and
  `heat_storage_rate`, the stored heat in J as `stored_heat` and the quadratic
  functional in J K as `thermal_energy_functional`; the summary's totals are named
  the same way (`generated_heat_rate`, `heat_storage_rate`, `outward_heat_rate`,
  `heat_rate_imbalance`, `stored_heat`, `thermal_energy_functional`) and it records
  `coordinate_system: "axisymmetric"`. The prescribed-temperature names are those of
  the steady case (`axis` and a `left` at r = 0
  refused by name); the initial field, sampled histories and source map are
  the Cartesian transient contract.
- **Not taken.** The waveguide runner (a body of revolution is not its
  physics; refused at validation whatever `xmin` is) and Studio (no
  axisymmetric payload, steady or transient) refuse an axisymmetric component
  by name. `export_fields` and `export_time_series` write the saved results as
  VTU and PVD with (r, z) points.

Checks G4-1 to G4-5 (`tests/simcase/test_thermal_axisymmetric_regions.py`,
pre-registered in the HQ work record on 2026-11-07, measured the same day on
Linux, Python 3.12, pinned environment): a uniformly heated solid cylinder
(mesh size 0.1 mm on a 3 mm radius) matches the exact parabola
`Q (R² − r²) / (4k)` at every node within 2e-3 of the axis rise, absorbs
`Q π R² L` within 1e-9 and balances its heat within 1e-10; a heated core in a
conducting shell matches the analytic axis and interface rises within 2e-3; a
source-free annulus conducts logarithmically within 1e-3 of the temperature
difference at the mid radius; the axis and left-side refusals, the other
runners' and Studio's refusals, and the result identifiers and field names.

Checks G7-5 (same file, pre-registered on 2026-11-08 and measured the same
day): the transient cylinder document returns the transient axisymmetric
identifiers with the plain (no `_per_depth`) names only, saves and exports them (VTU at a
time index and the PVD series), its source power is `Q π R² L` within 1e-12,
its heat content at t0 `c T0 π R² L` within 1e-12 and its per-step balance
defect within 1e-10 of the rates; with geometrically growing steps it reaches
the steady axisymmetric document's temperatures within 1e-6 of the rise on
the same mesh (reaction within 1e-6); the axis and left-side refusals and the
Studio refusal of the transient document. The engine-level checks G7-1 to
G7-4 (Bessel-series cooling convergence, balances, exact content, steady
limit, Cartesian default) are on the
[galerkin page](../galerkin/transient_heat.md#axisymmetric-transient-heat).

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
| Studio validation | The example validates with `ok: true` on Studio's thermal route with no mesher or worker call |

Observed when first run (mesh size 2 → 0.25 mm):

| Quantity | Values | Orders |
| --- | --- | --- |
| T L2 (K m) | 4.07e-6, 1.03e-6, 2.59e-7, 6.42e-8 | 1.98, 2.00, 2.01 |
| Flux L2 (W/m) | 0.478, 0.241, 0.121, 0.0603 | 0.99, 1.00, 1.01 |

The engine-level per-region validation, including composite cylinders and
interface heat rates, is in [multimaterial](../galerkin/multimaterial.md).

## Transient documents

A `thermal.transient2d` document with `background`/`shapes` uses the same
geometry, `materials` table and `mesh` (`element_size`, `minimum_angle`) as the
steady region documents, with the transient time contract of
[thermal_transient2d](thermal_transient2d.md): `study: {"type": "transient",
"time": {"unit": "s", "values": [...]}}` with explicit increasing times,
`initial_temperature` (a uniform quantity such as `"300 K"`, or an `affine` object)
and `prescribed_temperature` per side (a quantity, or a tagged array sampled at the
requested times, agreeing with the initial field at t0). Every used material needs
`thermal_conductivity` and `volumetric_heat_capacity`; `heat_source_density` is a
quantity or a `{region name: quantity}` map. Physics-level `thermal_conductivity` or
`volumetric_heat_capacity` is refused. The shipped example is
`transient_thermal_regions` (`examples/simcase/transient_thermal_regions.json`).

Results use `thermal.transient2d-regions-result-v2` and
`thermal2d-transient-p1-node-cell-regions-v2` (the `-v1` pair is retired): the
rectangle transient fields under their registry names (`time`, `temperature`,
`heat_flux`, `generated_heat_rate_per_depth`, `reaction_heat_rate_per_depth`,
`residual_heat_rate_per_depth`, `heat_storage_rate_per_depth`,
`stored_heat_per_depth`, `thermal_energy_functional_per_depth`, ...) plus static
`triangle_regions`. The summary adds `region_names`, `regions`, `materials` and the
mesh counts. `stored_heat_per_depth` is `1^T M T` with each region's capacity. Full
histories are kept in memory (O(steps x (nodes + triangles))); the convergence study
below peaked at about 825 MiB.

Validation (`tests/simcase/test_transient_thermal_regions.py`):

| Check | Gate |
| --- | --- |
| Q_i = r c_i in every region, insulated sides | T = T0 + r t at every node and time to 1e-10 of 300 K; flux below 1e-9 W/m^2 |
| Long-time limit (steps of 500 s to 1e4 s) against the steady region document | Identical mesh; final temperature within 1e-9 of the temperature rise |
| Direct `solve_transient_heat` call on the same mesh | Temperature, flux, reaction and heat content identical |
| Layered wall heated from a uniform 300 K (Q 2e5 / 5e4 W/m^3, ends 300 K) against `refsol.transient_heat_multilayer.LayeredWall.source_driven`, mesh size 4, 2, 1, 0.5 mm, dt = 1/64 s, observed at 20 s | T L2 order >= 1.8 and flux L2 order >= 0.9 on the last two intervals; at 0.5 mm halving dt changes each error by <= 5% |
| One material everywhere against the rectangle transient document | Source heat equal to 1e-12; maximum temperature within 2e-3 K |
| Saved fields, CLI, 11 invalid documents (one a shape outside the domain), Studio validation | Formats, regions, materials; exit codes; `DocumentError`; Studio validates with no worker or mesher call |

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

## Mesh limits for callers

A caller that runs documents it did not write, such as a server, can bound what
a region run meshes before anything is solved. `simcase.run` takes three
optional keyword-only limits:

```python
from simcase import MeshLimitError, check_mesh_limits, run

try:
    result = run(doc, max_input_vertices=2048, max_nodes=10201, max_triangles=20000)
except MeshLimitError as exc:
    print(exc.quantity, exc.count, exc.limit)     # for example: input_vertices 2054 2048
```

- `max_input_vertices` bounds the loop vertices the geometry passes to meshine
  (below). It is checked while the domain is assembled, before meshine builds it.
- `max_nodes` is passed to meshine as `max_points`, so meshing stops at the
  first insertion past it (meshine's `MeshSizeLimitError`); the exact node count
  is compared again after meshing.
- `max_triangles` is compared with the exact triangle count after meshing.

Every check runs before the solve. Each limit is a positive `int` or `None`, and
`None` is not checked: with no limit the run is exactly the unlimited one, and
meshine keeps its own default cap of 300,000 points unless `max_nodes` is given.
The limits apply to region documents only: steady and transient heat,
[region electric conduction and steady Joule heating](electric_joule.md#material-regions-electric-steady-conduction),
and [region mechanics](mechanics2d.md#material-regions-and-named-boundaries).
Giving one for a rectangle heat, electric, Joule or mechanics document, a
`joule.temperature2d` document or an electromagnetic or cavity document is a
`ValueError`, and so is a `bool`, a float or a value below 1. The two heat kinds,
the electric/Joule kind and the mechanics kind declare which of their documents
take limits in the physics registry (`PhysicsKind.accepts_mesh_limits`), and `run`
hands the limits to their runners through it; no other kind's runner changes. `max_nodes` needs
a meshine that has `MeshSizeLimitError`: with an older meshine installed, a run
that sets it raises `ImportError`, and every other run is unchanged.

Only `max_input_vertices` bounds the work before meshing. `max_nodes` and
`max_triangles` act once meshine has built the domain, which compares every
loop vertex with every earlier one (O(V²)), and an isolated circle makes its
vertices before that, or fails while making them at a `mesh.element_size` near zero.
Without `max_input_vertices`, the steady example with its regions sized 2 mm
and a global `mesh.element_size` of 0.004 mm is refused by `max_nodes` 10,201 only after
tens of seconds (28 s and 45 s in two measurements on Linux), and at 5e-324 it
still ends in an `OverflowError`, as with no limit.
For documents from others, give `max_input_vertices` too.

**Loop vertices.** A loop vertex is one entry of a loop given to meshine's
`Domain.add_region` after the shapes' booleans, in outer rings and holes alike:

- a shape inside the background counts twice, once as its own ring and once as
  the background's hole;
- a later shape can cut an earlier one into many parts, each with its own
  loops: two crossing combs of 255 points each give 32,776;
- a circle that another boundary touches or crosses, or that a later shape
  overlaps, is a 128-gon;
- an isolated circle, meshed as an exact meshine `Circle`, counts
  max(16, int(4πr / `mesh.element_size`)) with the **global** `mesh.element_size`,
  even when it sets its own `element_size`, and counts again as the hole of the
  region around it. The shipped steady example at `mesh.element_size` 0.0246 mm has
  2054 loop vertices, 2042 of them from the heater.

The count is taken before meshine's own T-junction splits, so the loops meshine
processes can be longer. It is the count of what is meshed: the document's
micrometre copy (see Mesh and solve). The shapes' booleans and the circle rule
do not depend on the unit, so the count is usually the same as in the
document's own numbers, and it is the same on the 22 millimetre documents the
tests use.
Where 4πr / `mesh.element_size` lies within rounding of an integer it can differ: the
steady example with regions sized 2 mm at `mesh.element_size` 4π·2/20 mm has 52 loop
vertices in millimetres and 50 in the micrometre copy that is meshed, and 50 is
what is counted. `check_mesh_limits(doc, *, max_input_vertices)` returns the
count of a region document without building the domain or changing the
document, or raises `MeshLimitError`. It counts the micrometre copy a run meshes:
for a format 0.3 document, the copy made from the document's geometry and mesh
hand-off (`thermal_regions.handoff_03`). A `Document` that was never read
(`Document(data)`, `Document.copy()`) is read first, as its run would read it.
An isolated circle whose own count is
over the limit is refused before its vertices are made, with that count's
estimate (in micrometres) in the message, so under `max_input_vertices` a
`mesh.element_size` near zero raises `MeshLimitError`, not a division,
overflow or memory error; an element size below 1e-300 m is refused by the reader
(`E-DOMAIN` at `mesh.element_size`), and a mesh estimated above
`mesh.element_count_limit` elements by `E-MESH-ESTIMATE`.

**`MeshLimitError`** is a `ValueError`, not a `DocumentError`: the document is
valid, and the caller's limit refuses it. `quantity` is `'input_vertices'`,
`'nodes'` or `'triangles'`; `limit` is the limit; `count` is the exact count,
or `None` when meshing stopped at the `max_nodes` cap or one isolated circle
alone is over `max_input_vertices`. The message names the quantity, the count
and the limit.

**Before validation: `region_complexity`.** Validating a region document
resolves the shapes' booleans, and that cost grows with the boundaries that
cross each other, even where later shapes cover the crossings and none of them
reaches the mesh. Two 255-point sawtooth polygons whose edges cross 64,455
times, under four covering rects and after 58 small ones, take 18.5 s and
32 s in `Document.from_dict` alone (two measurements on Linux with Python 3.12
and shapely 2.2.0). `region_complexity(data, *,
max_shapes=None, max_circles=None, max_polygon_points=None)` reads the raw
document (the dict JSON gives, before `Document.from_dict`) and returns
`RegionComplexity(shapes, circles, polygon_points, boundary_crossings)`:

- `shapes` is the length of `geometry.shapes`, `circles` the entries of type
  `circle`, and `polygon_points` the summed lengths of the polygons' `points`;
- these three come from the lengths alone; when one is over the maximum given
  for it, `boundary_crossings` is `None` and no geometry is built;
- otherwise `boundary_crossings` is the number of pairs of boundary segments
  from different shapes that properly cross, whose interiors meet in exactly
  one point: touching at an end point, a T-junction or a collinear overlap does
  not count. A rect is its 4 edges, a circle the 128-gon simcase meshes it
  with, and a polygon its edges. Each pair is decided with GEOS's robust
  orientation predicates on the coordinates as given. That is the test
  shapely's `crosses` makes for two segments, except where an end point lies
  within rounding of the other segment: `crosses` rounds the intersection point
  it computes and can call such a crossing a touch. The pairs are found with
  one shapely STRtree query, and only the pairs whose bounding boxes meet are
  tested. The caps bound that work: within 64 shapes, 16 circles and 512
  polygon points a document has at most 2748 segments, so at most 3,774,378
  pairs to test (see the tests below). The example above takes 0.04 to 0.08 s
  on one machine and 0.07 to 0.14 s on a slower one; within those caps, the
  costliest layouts found take 0.3 to 0.8 s (chord stars, polygons whose edges
  are chords through one centre: up to 158,868 crossings) and 0.5 to 1.6 s
  (diagonal and corner fans, below) on the slower machine.

It never raises on malformed data: a document, `geometry` or `shapes` of the
wrong type counts zero, and an entry that is not a dict, has an unknown type or
has a coordinate that is not a finite number counts as a shape (and its points
as points) but adds no segment; `Document.from_dict` raises on it later, a
`DocumentError`, or shapely's `GEOSException` for a circle whose extent
overflows a float. A shape with a coordinate beyond the range where shapely
decides crossings exactly (nonzero and below 2^-300 or above 2^300 in
magnitude) is not measured: each of its segments counts as crossing every
segment of every other shape, an upper bound, so an extreme scale cannot hide
crossings, and a document with such a shape reports a large count that says
nothing about its real crossings.

It counts the document's own numbers, the ones `Document.from_dict` resolves
first. A run resolves the shapes again, twice, on the micrometre copy it meshes
(see Mesh and solve). A decimal unit factor can re-round exact contacts in that
copy, as the scaling check below shows, so the copy's crossings can differ from
the count by such contacts. The micrometre copy counts the same on 22 valid
millimetre documents in the tests (both examples at three mesh sizes, the region
fixtures, the heaters above and three crossing layouts) and on the covered
crossings above (measured once). Two of the costliest layouts change (158,868
to 158,860 and 121,634 to 121,624), but they are not valid documents:
`Document.from_dict` refuses their self-intersecting polygons before any boolean.
These measurements are of millimetre documents. In another unit the factor to
micrometres is another power of ten, and valid documents can differ too
(measured once, on the test documents rewritten with every length scaled): the
8 x 8 grid of touching rects counts 4 in metres and 0 on its micrometre copy,
and 0 and 16 in kilometres; the heaters centred on the plate edge count 0 and
16 in megametres.

`tests/simcase/test_region_mesh_limits.py` checks the mesh limits with criteria
fixed before the change, measuring every node and triangle count in the test instead
of storing it: limits at the exact node, triangle and loop counts of both
examples give the saved arrays and summary of the unlimited run, and one less
is refused before the solver is called; each limit works alone; documents
without regions and invalid values are refused; and the count equals the sum of
the loops meshine receives on 22 documents. Tests added when the limits moved
onto the micrometre copy and the physics registry, not pre-registered, check
that the count is the one of the domain each run hands to meshine in mm, nm and
m documents and in the document above where the units change it, that a
document that was never validated gets the count of its run, and that only a
kind that accepts limits receives them. `tests/simcase/test_region_complexity.py`
checks `region_complexity` against criteria fixed before it was written: the
counts equal direct counts, and malformed input never raises; the crossings
equal a brute force with shapely's `crosses` on every segment pair, on 12
seeded random documents with exact contacts and on the hidden crossings above;
realistic layouts (both examples, an 8 x 8 grid of touching rects, 64 stacked
strips, 8 heaters across the plate edge) stay at or below 256 crossings, in
fact at most 16 (heaters centred on the edge meet it only at vertices of their
128-gons, which count 0; 0.3 mm higher they cross it 16 times); the hidden
crossings count over 1024 (in under 0.5 s, and the costliest layouts found in
under 1 s: a time criterion that failed, see below); scaling every coordinate
by 1e-6 or 1e6 keeps the counts; and over
a maximum nothing is built. The comparison with `crosses` holds on its corpus
but not in general: a review found documents whose segments cross by less than
a rounding error, where `crosses` reports a touch. A test added after the
criteria therefore compares the count with exact rational arithmetic, on such
documents at scales from 1e-80 to 1e80 and on the corpus above. One criterion
failed when first run: scaling by 1e-6 and 1e6 changed the counts of the
costliest layouts (for the one with 8 polygons, 158,868 became 158,874 and
158,860; each of the four changes at 1e-6). In exact arithmetic, vertices of
their circles' 128-gons lie on sides of their rects; in floating point each
such contact is a touch, a crossing by about a rounding error or a near miss,
and a decimal factor rounds it again, so a touch can become a crossing and a
crossing a miss. The count still equals exact arithmetic at every scale, and
scaling by powers of two, which rounds nothing, keeps every count. Layouts with
contacts that rounding can turn into a proper crossing are therefore left out
of that check; after the failure, copies of the four layouts with their
circles moved off the rects' sides were added to it, and they keep their
counts. The time criterion failed too. On a machine slower than the first, the
chord stars took 0.3 to 0.8 s per call in the test, and in one of 26 runs one
call took 1.015 s, over the bound. Diagonal fans, found afterwards (polygon
edges that zigzag between two opposite corners of a square holding all 16
circles, so that every edge's box holds every circle segment), give about
twice as many segment pairs whose boxes meet (2.53 and 2.56 million against
1.10 to 1.20 million) and took 0.5 to 1.6 s per call on that machine, over 1 s
in 15 of 120 calls in twenty runs of the test. A review then found corner fans
(polygons that return to one corner of that square at every other point, so
that all their edges also meet there): a few more such pairs (up to 2.57
million) and, with 8 polygons, the most pairs that meet (197,824 against at
most 158,906 for the others). In ten later runs of the test they took
0.5 to 1.3 s per call, over 1 s in 7 of 60 calls, and the diagonal fans 0.5 to
1.6 s, 8 of 60. By owner decision (2026-10-27) the time criterion stays
recorded as failed, and the tests print the times but no longer check them.
They check a deterministic work bound that follows from the caps instead. A
document within 64 shapes, 16 circles and 512
polygon points gives at most 2748 boundary segments (16 circles of 128, one
polygon with all 512 points and 47 rects of 4; one test document reaches it),
so the STRtree query returns at most 2748² pairs, at most 3,774,378 pairs are
tested, each costs at most five predicate evaluations (one, and four end-point
tests for a pair that meets), and the other shapely calls make or take at most
10,356 items (two end points and a prepared line per segment; a centre, a disc,
a ring and its 129 coordinates per circle). The two pair numbers are what
testing every pair would give: they hold for any document within the caps, but
a brute force would meet them too. What rules a brute force out is a count made
without shapely, which checks on each document that only the pairs whose
bounding boxes meet are tested. A counting stand-in for shapely, which fails
the test on any shapely call it does not count, measures this work on the
hidden crossings, the chord stars, two diagonal fans, two corner fans and 12
seeded random documents within the caps (6 that fill every cap). The most
measured is 2,572,136 query pairs, 1,249,950 tested pairs and 2,041,246
predicate evaluations, about a third of their bounds or less. The bound limits
work, not time: the time per pair depends on the machine.

## Limits

- Studio validates, runs and shows steady and transient region documents
  within its region limits (shapes, circles, polygon points, boundary
  crossings and loop vertices, then node and cell counts); see
  [steady Studio, Region documents](thermal_studio.md#region-documents).
- Piecewise-constant isotropic properties; perfect contact at interfaces.
- Next to a circle that touches or shallowly crosses another boundary, or a
  sharp polygon corner, triangles in either region can be as sharp as the input
  corner or a little sharper (measured 13.0° beside a 14° polygon corner); an
  input meshine cannot resolve ends with an error (see Mesh and solve).
- Plane geometry of unit depth (`depth: null`) or a stated `geometry.depth`; no
  thermal properties from built-in materials.

### Canonical length regression

`tests/simcase/test_thermal_length_canonical.py` compares a translated domain
with rectangles, an isolated circle, a polygon, background and per-shape element
sizes with the shape numbers in mm, m, um and nm (format 0.3 has no custom length
unit). Steady flux/Robin loads and transient affine initial data exercise both
solve paths. Every numeric saved array, region/material assignment, boundary tag
and summary value must be identical, except `minimum_triangle_angle` (within 1e-12,
see Mesh and solve); the original model must be preserved. Existing layered-wall
analytical convergence tests remain required.

## VTU and PVD export

Install `simcase[export]` (meshio, MIT) to view saved region results in ParaView.
`export_fields(fields_npz, output, *, time_index=-1)` accepts
`thermal2d-p1-node-cell-regions-v2`,
`thermal-axisymmetric-p1-node-cell-regions-v2` (points are (r, z), the
rates are the full-revolution powers in W) and the transient
`thermal2d-transient-p1-node-cell-regions-v2` and
`thermal-axisymmetric-transient-p1-node-cell-regions-v2`.
`export_time_series(fields_npz, output_dir, *, name="fields")` accepts the
transient layouts and writes one VTU per stored time plus a PVD collection with
exact `time` values in seconds. Neither function reruns the solver or changes the
saved result. A result saved before format 0.3 (the `-regions-v1` layouts) is
refused by name (`RETIRED_LAYOUTS`).

```python
from simcase import Document, run
from simcase.export import export_fields, export_time_series

# Run from the repository root, with new output paths.
steady = run(Document.load("examples/simcase/thermal_regions.json"), verbose=False)
steady_dir = steady.save("out/region-steady")
export_fields(steady_dir / "fields.npz", "out/region-steady/view.vtu")
transient = run(Document.load("examples/simcase/transient_thermal_regions.json"), verbose=False)
transient_dir = transient.save("out/region-transient")
export_fields(transient_dir / "fields.npz", "out/region-transient/initial.vtu", time_index=0)
export_time_series(transient_dir / "fields.npz", "out/region-transient/paraview")
```

Open `view.vtu` or `paraview/fields.pvd` in ParaView. Color by the **cell**
array `triangle_regions` to distinguish regions (even when they use the same
material), or by `temperature` to inspect the nodal temperature. IDs are the
unchanged zero-based indices into `summary.json["region_names"]`;
`summary.json["regions"][name]["material"]` identifies each material. The same
summary is in the NPZ metadata. Each VTU's FieldData holds `units` (every exported
array's unit, as `field_units`) and `conventions` (the sign sentence of each signed
array). Names, properties and boundary tags are not copied into VTU; keep the
original NPZ/summary for their meaning.

| VTU association | Arrays and units |
|---|---|
| Points | `node_coordinates`, embedded at z = 0, in metres regardless of the geometry's length unit |
| Point data | `temperature` (K); stored nodal heat rates, reactions, residuals and storage rates (W/m of depth; W for an axisymmetric result) |
| Cell data | `heat_flux` (W/m², zero z component); `triangle_regions` (integer, no unit) |

Steady region exports include `generated_heat_rate_per_depth`,
`reaction_heat_rate_per_depth`, `residual_heat_rate_per_depth`,
`outward_prescribed_heat_rate_per_depth`, `ambient_convective_heat_rate_per_depth`,
`outward_convective_heat_rate_per_depth` and `applied_heat_rate_per_depth`. Their
flux/convection signs and outer-side boundary conditions remain those described
above. Transient exports include `generated_heat_rate_per_depth`; reaction, residual
and `heat_storage_rate_per_depth` arrays exist only from the second stored time. No
initial rate is invented. Domain histories such as stored heat, boundary-node
subsets and names remain in NPZ/summary. No point/cell interpolation or region
renumbering occurs.

An existing VTU is refused; a series directory must be new or empty. Series
failures remove files created by that call. Missing, non-integer, negative or
incorrectly shaped `triangle_regions` arrays are rejected before output is
created. This is an exporter for valid `save()` results, not a full validator
for arbitrary NPZ archives. It does not support restart, XDMF or transient
flux/Robin input. The separate rectangular steady `boundary-v3` layout is
exported by the same function with its own arrays ([overview](overview.md#viewing-in-paraview)).

`tests/simcase/test_export_regions.py` checks all exported arrays against NPZ,
all stored timesteps, initial-rate absence, region IDs distinct from material
IDs, the FieldData block, output protection and failure cleanup. Equivalent
mm/m/um/nm problems must give exactly equal SI export arrays in the same numerical
environment, subject to the canonical-length condition above. These consumers
also run against installed wheels on Linux, macOS and Windows.
