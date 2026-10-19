# Steady heat documents with material regions

[한국어](locales/ko/pages/thermal_regions2d.md)

A `thermal.steady2d` document whose `geometry` has `background` or `shapes`
describes several materials. It uses the same geometry as electromagnetic
documents: named shapes, each naming a material, drawn in order over a
background (later shapes cut earlier ones). Thermal properties come from the
`materials` table. The mesh follows every region boundary. This is a headless
API/CLI path; Studio refuses these documents (see Limits below).

Rectangle documents without `background`/`shapes` keep the
[original contract](thermal_steady2d.md) and its
[boundary extension](thermal_steady_boundary2d.md) unchanged.

## Example

The shipped example `thermal_regions` (`examples/thermal_regions.json`,
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
    "steel": {"conductivity_w_mk": 45},
    "copper": {"conductivity_w_mk": 400},
    "insulation": {"conductivity_w_mk": 0.04}
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
simcase validate packages/simcase/examples/thermal_regions.json
simcase run packages/simcase/examples/thermal_regions.json -o heated_plate
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
  domain; a region left smaller than 1e-12 of the domain area is dropped, as in
  electromagnetic documents.
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

The geometry is meshed by meshine in document units (constrained Delaunay
refinement with the requested minimum angle), then scaled exactly to metres.
Every shape boundary is a chain of element edges, so each triangle lies in
one region. Curved boundaries are inscribed polygons: the meshed area of a
circle is smaller than pi r^2 by O(h^2). The meshed problem is passed to
`galerkin.thermal.solve_steady_heat` with conductivity and source mapped by
region name ([multimaterial](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/multimaterial.md)).

meshine does not produce the same node positions for one geometry written in
different length units. Results in mm, m and um therefore agree to
discretization error, not node for node; the adapter's own conversion is an
exact multiplication.

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

`packages/simcase/tests/test_thermal_regions.py`, gates fixed before the
comparison:

| Check | Gate |
| --- | --- |
| Layered wall document (10 mm steel with Q = 2e5 W/m^3, 20 mm insulation, 400/300 K) against `refsol.thermal_multilayer.layered_slab`, mesh size 2, 1, 0.5, 0.25 mm | T L2 order >= 1.8 and flux L2 order >= 0.9 on the last two intervals; heat balance <= 1e-10 |
| Same wall in mm, m and um | Adapter nodes = meshine nodes x unit factor exactly; T and flux errors against the exact wall agree within 5% |
| Shipped example against a direct `solve_steady_heat` call on the same mesh | Temperature and reaction identical; source heat = Q x meshed heater area to 1e-12; heater area within 1% of pi r^2; outward = source to 1e-10 |
| Saved fields and summary | Formats, `triangle_regions`, boundary fields, region table, materials, total area, model copy |
| CLI | validate and run exit 0; an existing output exits 1 |
| 19 invalid documents and a covered source region | Refused with `DocumentError` |
| Rectangle documents | Non-empty `materials` still refused; original result format |
| Studio | Region documents are refused before any mesher or worker call |

Observed when first run (mesh size 2 → 0.25 mm):

| Quantity | Values | Orders |
| --- | --- | --- |
| T L2 (K m) | 4.07e-6, 1.03e-6, 2.59e-7, 6.42e-8 | 1.98, 2.00, 2.01 |
| Flux L2 (W/m) | 0.478, 0.241, 0.121, 0.0603 | 0.99, 1.00, 1.01 |

The engine-level per-region validation, including composite cylinders and
interface heat rates, is in [multimaterial](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/multimaterial.md).

## Limits

- Steady heat only; transient region documents are not yet accepted.
- Studio refuses region documents (its heat views read `mesh.subdivisions`);
  use the CLI or Python API.
- Piecewise-constant isotropic properties; perfect contact at interfaces.
- Plane geometry of unit depth; no thermal properties from built-in materials.
