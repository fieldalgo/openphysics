# Electric and Joule heating documents

**English** | [한국어](../../locales/ko/pages/packages/simcase/electric_joule.md)

This is the normative JSON/CLI contract. The existing
[electric](../galerkin/electric_steady2d.md), [one-way Joule](../galerkin/joule_heating.md)
and [temperature-dependent Joule](../galerkin/temperature_joule_heating.md)
contracts define the numerical solves and unchanged acceptance tolerances.

## Scope and input

This section is the rectangle form; all three kinds also take
[material regions](#material-regions-electric-steady-conduction).
The documents are [format 0.3](document_format.md): every value carries its unit
(`"2 S/m"`, `"1 V"`, `"300 K"`) and keys are registry quantity names. A format 0.2 electric or
Joule document is refused by name (`E-FORMAT`). One named physics entry,
`study: {"type":"single"}` (its default), and a flat rectangle `geometry` with
`length_unit` (for example `m`, `mm` or `um`), `depth` (`null` for results per metre of depth,
or a length such as `"40 mm"`, which adds totals) and the four `domain` bounds as plain numbers
in that unit. `mesh` is `subdivision_count: [nx, ny]` (positive integers), `materials` is `{}`.
There are no shapes, sweeps, remeshing or implicit extra heat sources. Unknown keys
(`E-KEY-UNKNOWN`), non-finite numbers, booleans as numbers and conflicting corners are
refused. At most 200,000 triangles are accepted before allocation. `results` defaults to
`save_fields: true, plots: false`; plots are unsupported, and Studio runs region documents only
([Studio](#studio-region-documents)).

The physics entry:

| Key | Kinds | Value |
|---|---|---|
| `electrical_conductivity` | `electric.steady2d`, `joule.steady2d` | positive, such as `"2 S/m"` (menu `S/m kS/m MS/m S/cm`; `"2 mS/m"` is millisiemens per metre and refused with suggestions). The model form is refused by name: these kinds have no evaluation temperature |
| `prescribed_electric_potential.<side>` | all three | such as `"1 V"` (menu `uV mV V kV`); `"0 V"` is written. At least one side |
| `inward_current_density.<side>` | all three | optional, such as `"2 A/m^2"`, **positive into the body** (the 0.2 `outward_current_a_m2` negated). Overlap with a fixed-potential side is refused. A terminal total (`inward_current`, `inward_current_per_depth`) is refused by name |
| `thermal_conductivity` | Joule | positive, such as `"1 W/(m K)"` |
| `prescribed_temperature.<side>` | Joule | absolute temperatures above 0 K, such as `"300 K"` or `"26.85 degC"`; the key is required and may be `{}` when convection anchors the temperature |
| `inward_heat_flux.<side>` | Joule | optional, positive into the body (the 0.2 `outward_flux_w_m2` negated); added to convection on the same side |
| `convection.<side>` | Joule | `{"heat_transfer_coefficient": "4 W/(m^2 K)", "ambient_temperature": "300 K"}` |
| `heat_source_density` | Joule | refused by name: the current is the only heat source |
| `electrical_conductivity` (model) | `joule.temperature2d` | required on a rectangle, see below; a constant here is `E-VALUE-FORM` |
| `initial_temperature` | `joule.temperature2d` | required, above 0 K and inside `valid.temperature` |
| `iteration` | `joule.temperature2d` | required, see below |

Sides are `left,right,bottom,top`; adjacent fixed sides must agree at their shared corner
(compared on SI values). Actual fixed/natural-edge overlap is also checked on the generated
mesh. A side with no electric condition is electrically insulating and is reported once as
`I-DEFAULT-BOUNDARY` at `physics.<name>.inward_current_density.<side>`; a Joule side with no
thermal condition is insulated and reported at `physics.<name>.inward_heat_flux.<side>`.
Joule documents need a prescribed temperature or a positive convection coefficient (pure
Neumann is refused). Natural loads on a fully fixed edge are invalid. Joule sources come only
from the electrical result on this exact mesh. Absolute temperatures (prescribed, ambient,
initial, reference and the `valid` bounds) must be above 0 K (`E-DOMAIN`); format 0.2 allowed
0 K.

`joule.temperature2d` gives `electrical_conductivity` as a model:

```json
"electrical_conductivity": {
  "model": "linear_resistivity",
  "reference_conductivity": "2 S/m",
  "reference_temperature": "300 K",
  "resistivity_temperature_coefficient": "0.01 1/K",
  "valid": {"temperature": ["290 K", "400 K"]}
}
```

`sigma(T) = reference_conductivity / (1 + resistivity_temperature_coefficient (T - reference_temperature))`,
the law of format 0.2. `reference_conductivity` is positive, `reference_temperature` lies
inside `valid.temperature` (`E-OUTSIDE-VALID`), and the denominator and conductivity are finite
and positive at both ends of the range, which this linear denominator check covers for the
entire interval. Initial, prescribed and ambient temperatures must lie in the interval
(`E-OUTSIDE-VALID` at the value's path). `reference_resistivity` is refused by name; `alpha` and
`conductivity_temperature_coefficient` are unknown keys of `linear_resistivity`. Every trial
nodal temperature is checked by the existing solver; no extrapolation, clipping, arbitrary
Python callback, expression evaluation or import is allowed. The mesh is built once in metres;
element sigma is evaluated at the arithmetic mean of its three nodal temperatures, after
checking all three against the range. Thermal conductivity is constant.

`iteration` (required, because `temperature_tolerance` has no dimensional default):
`relaxation_factor` (default 0.5, echoed in `defaults_applied`; this kind takes
0 < value <= 1 although the registry allows up to 2), `temperature_tolerance` (required, such
as `"1e-8 K"` or `"1e-5 mK"`; `"1e-8 degC"` is refused with a suggestion only),
`relative_tolerance` (default 1e-10, at most 1) and `iteration_limit` (default 100, a positive
integer). The existing relaxed Picard loop checks the **unrelaxed** temperature and conductivity
changes and the refreshed nonlinear thermal residual (<=1e-8); its stopping test is
`|dT| <= temperature_tolerance + relative_tolerance max(|T_i|, |H(T_i)|)`. Electrical/thermal
linear residual and conservation gates are unchanged. See the linked solver contract for
normalization and stopping rules. Documents always use the Picard loop; the Python API's
`method="newton"` is not part of this format.

Format 0.2 keys are refused with their new names (`E-KEY-UNKNOWN`); for the two outward inputs
the message says to write the negated value, and no automatic fix is offered because the
meaning changes:

| Format 0.2 | Format 0.3 |
|---|---|
| `units.length`, `units.temperature` | `geometry.length_unit`; every value carries its unit |
| `mesh.subdivisions` | `mesh.subdivision_count` |
| `conductivity_s_m` | `electrical_conductivity` |
| `dirichlet_potential_v` | `prescribed_electric_potential` |
| `outward_current_a_m2` | `inward_current_density` = −old |
| `thermal_conductivity_w_mk` | `thermal_conductivity` |
| `dirichlet_temperature_k` | `prescribed_temperature` |
| `outward_flux_w_m2` | `inward_heat_flux` = −old |
| `convection.<side>.{h_w_m2k, ambient_temperature_k}` | `convection.<side>.{heat_transfer_coefficient, ambient_temperature}` |
| `conductivity_model` (`type`, `reference_conductivity_s_m`, `reference_temperature_k`, `alpha_per_k`, `temperature_range_k`) | `electrical_conductivity` (`model`, `reference_conductivity`, `reference_temperature`, `resistivity_temperature_coefficient`, `valid.temperature`) |
| `initial_temperature_k` | `initial_temperature` |
| `iteration.{relaxation, temperature_atol_k, relative_tolerance, max_iterations}` | `iteration.{relaxation_factor, temperature_tolerance, relative_tolerance, iteration_limit}` |

## Material regions (electric steady conduction)

An `electric.steady2d` document whose geometry has regions (a
[version 1 geometry block](geometry_document.md) with features or a background
material, or flat `background` and `shapes`) uses the geometry, mesh and boundary names of
[region heat](thermal_regions2d.md):

- `materials.<name>.electrical_conductivity` (positive, such as `"58 MS/m"`) gives each region
  its conductivity; every material a region uses needs it (`E-PROPERTY-MISSING`). The same
  materials table may also hold heat properties (`thermal_conductivity`,
  `volumetric_heat_capacity`); a property this run does not read is reported as
  `I-UNUSED-PROPERTY`. A material's model form is refused by name (only region
  `joule.temperature2d` reads it). Library materials (`physmat:...`)
  carry no electrical conductivity for this physics yet and are refused by name. The physics
  entry takes no `electrical_conductivity`.
- `prescribed_electric_potential` and `inward_current_density` take the domain sides, the
  exterior tags the geometry declares (`boundary_tags` names, `outer` on the border
  of a void feature) and exterior boundary selections. An interface selection
  between two regions is refused for both, because the electric solver fixes
  exterior nodes only. A name without mesh edges, two names given current on the
  same edges, current on an edge of a fixed boundary under another name, and two
  boundaries fixing a shared node to different potentials are refused by name; an unknown
  name is `E-SELECTION-UNKNOWN`.
- An unnamed exterior boundary, including a void border, is electrically insulating and
  domain sides without a condition are reported as `I-DEFAULT-BOUNDARY`. At least one
  potential is required.
- `mesh` is `{"element_size", "minimum_angle", "element_count_limit", "controls"}` as for
  region heat, and the region mesh limits apply. A void background and an axisymmetric
  component are refused.

The result format is `electric.steady2d-regions-result-v2` with field layout
`electric2d-p1-node-cell-regions-v2`: the rectangle fields plus `triangle_regions`.
The summary adds `region_names`, `regions.<region>.{material, electrical_conductivity}`,
`mesh.minimum_triangle_angle` (rad) and `balance.outward_current_per_depth.<name>`, the current
leaving the conductor through each fixed boundary in A per metre of depth (**positive out of
the body**: the 0.2 `diagnostics.terminal_reaction_current_a_per_m`, positive in, negated; a
node fixed by two boundaries counts for the first in name order). Two potential names on the
same mesh edges and a conductor part with no fixed potential are refused by name. A region
result exports to VTU like the rectangle one, plus the cell data `triangle_regions`. Steady
Joule heating on regions is the [next section](#material-regions-steady-joule-heating), and
temperature-dependent Joule heating on regions the
[section after it](#material-regions-temperature-dependent-joule-heating).

Independent checks (`tests/simcase/test_electric_regions.py`, pre-registered E1 to E7):

| Check | Reference | Result |
|---|---|---|
| Two layers in series | piecewise linear potential, I = V / sum(L_i / (sigma_i h)) | nodal error at most 1e-10 V; current 1e-10 relative |
| Two layers in parallel | I = V sum(sigma_i h_i) / L | 1e-10 relative |
| Coaxial circular electrodes (r = 3 and 9 mm, 192-gons) | I = 2 pi sigma (V_a - V_b) / ln(b/a) | relative error 2.0e-3, 6.6e-4, 1.4e-4 at mesh size 0.8, 0.4, 0.2 mm (order 2.3 on the last step) |
| Joule power | supplied power V I | 1e-10 relative |
| Rectangle documents | results before this change | every rectangle electric and Joule example bit for bit |

## Material regions (steady Joule heating)

A `joule.steady2d` document whose geometry has regions solves the region electric
conduction above and heats [region heat](thermal_regions2d.md) with its Joule heating,
on one mesh:

- every material a region uses needs both `electrical_conductivity` and
  `thermal_conductivity`. The physics entry takes neither, and no `heat_source_density`:
  the current is the only heat source (an additional heat source is not supported).
- `prescribed_electric_potential` and `inward_current_density` take the names region
  electric conduction takes (exterior boundaries only); `prescribed_temperature`,
  `inward_heat_flux` and `convection` take the names region heat takes, so a prescribed
  temperature may also fix an interface selection. At least one potential and a prescribed
  temperature or a positive convection coefficient are required.
- An axisymmetric component and a void background are refused; the region mesh limits apply.

The solver checks that the heat load equals the Joule load node by node and that the
outward heat equals the Joule power. The result format is
`joule.steady2d-regions-result-v2` with field layout
`electric-joule2d-p1-node-cell-regions-v2`: the rectangle Joule fields plus
`triangle_regions`, and in the summary `regions.<region>.{material, electrical_conductivity,
thermal_conductivity}`, `mesh.minimum_triangle_angle` and the terminal currents. It exports to
VTU like the rectangle Joule result, plus `triangle_regions`. Temperature-dependent
conductivity on regions is the
[next section](#material-regions-temperature-dependent-joule-heating).

Independent checks (`tests/simcase/test_joule_regions.py`, pre-registered J1 to J7). The
error is the largest nodal temperature error over the temperature rise:

| Check | Reference | Result |
|---|---|---|
| Two materials in series, Dirichlet ends | piecewise quadratic T(x) with continuous T and k dT/dx | 2.1e-2, 4.6e-3, 1.1e-3 at mesh size 0.25, 0.125, 0.0625 mm (order 2.1) |
| The same strip with a convective end | Robin end condition | 1.2e-2, 2.7e-3, 6.5e-4 (order 2.1) |
| Coaxial electrodes held at one temperature (192-gons) | T(r) - T0 = -C (ln r - ln a)(ln r - ln b) / 2, C = sigma V^2 / (k ln^2(b/a)) | 3.8e-3, 1.8e-3, 4.9e-4 at 0.4, 0.2, 0.1 mm (order 1.9 on the last step) |
| Power | supplied V I, Joule and outward heat | agree to 1.4e-14 relative |
| Rectangle documents | results before this change | `joule_rectangle`, `joule_temperature`, `electric_rectangle` field hashes equal to the commit before (checked when this was written; the test checks the rectangle path is taken) |

The coaxial check was pre-registered at 0.8, 0.4 and 0.2 mm, where it failed: the order of
the last step was 1.03. The largest nodal error sits next to the inner electrode
(r ≈ 3.3 mm), where the Joule source (∝ 1/r²) is steepest, and on these coarse
unstructured meshes (h/a ≥ 0.07) it is not yet asymptotic. Region heat with the exact
analytical source on the same meshes dips the same way (1.58, 1.17, then 1.99 at 0.1 mm),
so the dip is not the Joule coupling, and scaling the circle segments with the mesh keeps
it (1.10, 1.40, 1.67), so it is not the fixed boundary resolution. The area-weighted L2
error converges smoothly on the same meshes (orders 1.60, 1.71, 2.16). The thresholds are
unchanged; the sequence is one step finer.

Since the units and naming batch these checks run on format 0.3 documents converted from the
0.2 ones; the 0.2 documents on the code before the batch and the converted documents give the
same solver inputs and saved bytes (`tools/units_batch`), so every number above is unchanged.

## Material regions (temperature-dependent Joule heating)

A `joule.temperature2d` document whose geometry has regions takes the geometry, mesh and
boundary names of [region steady Joule heating](#material-regions-steady-joule-heating), and
`initial_temperature` and `iteration` exactly as the rectangle form:

- every material a region uses needs `thermal_conductivity` (a constant) and
  `electrical_conductivity`, either a constant (`"2 S/m"`) or the `linear_resistivity` model of
  the rectangle form (the same keys and checks: a positive `reference_conductivity`,
  `reference_temperature` inside `valid.temperature`, a positive finite conductivity at both
  ends of the range). The physics entry takes neither conductivity, a constant or a model
  (refused by name), and no `heat_source_density`. Every other physics refuses a model in a
  material by name when the document is read (`E-CONTRACT`, on every material, used or not,
  before its keys are read): none has an evaluation temperature.
- `initial_temperature`, every prescribed temperature and every ambient temperature must lie
  inside the `valid.temperature` of every model material, that is inside their intersection
  (`E-OUTSIDE-VALID` at the value). Ranges with no common temperature are refused at the first
  material whose range empties the intersection. A constant material imposes no range: galerkin
  receives it as a model of constant value on [0 K, largest double] (galerkin refuses an
  infinite range, and no finite temperature reaches that bound).
- An axisymmetric component and a void background are refused; the region mesh limits apply.
  The iteration is Picard, with the rectangle options and convergence tests; a failed
  iteration raises the solver's `JouleConvergenceError` with its history (the CLI prints the
  same failure evidence as for a rectangle).

The solver evaluates each region's conductivity at the element-mean temperature of the iterate
(the saved `evaluation_temperature`). The result format is
`joule.temperature2d-regions-result-v2` with field layout
`electric-joule2d-temperature-p1-node-cell-regions-v2`: the region Joule fields plus
`evaluation_temperature`. The summary adds `regions.<region>.{material,
electrical_conductivity, thermal_conductivity}` (a constant as a value object; a model as
`{model, reference_conductivity, reference_temperature, resistivity_temperature_coefficient,
valid: {temperature: [lo, hi]}}` of value objects), `mesh.minimum_triangle_angle`, the
terminal currents and `iterations`. It exports to VTU like the region Joule result, plus the
point data `evaluation_temperature`.

Independent checks (`tests/simcase/test_joule_temperature_regions.py`, pre-registered T1 to T7):

| Check | Reference | Result |
|---|---|---|
| Two `linear_resistivity` materials in series (a = +4e-3 and -3e-3 1/K), 0.2 V, ends at 300 and 320 K | per material theta = 1 + a (T - T_ref) obeys theta'' = -(a J^2 rho0 / k) theta (trigonometric or hyperbolic), with continuous T and k dT/dx; J by a bracketed root of V = J sum rho0 integral theta | temperature 8.5e-3, 2.0e-3, 4.6e-4 of the rise at mesh size 0.25, 0.125, 0.0625 mm (order 2.1); terminal current 4.1e-4, 9.4e-5, 2.3e-5 relative |
| Direct galerkin call | `solve_temperature_joule_heat` on the same mesh and inputs | bit for bit |
| Power | supplied, Joule and outward heat | agree to 4e-14 relative |
| Zero coefficients, and constant materials | region `joule.steady2d` on the same document | temperature and potential equal (difference 0) |
| Rectangle documents | results before this change | `joule_rectangle`, `joule_temperature` saved arrays, summary (without timings) and model hashes equal to the commit before (checked when this was written) |
| Shipped example `joule_temperature_regions` | the T1 strip with material B a constant 500 S/m: theta_A as in T1, and k_B T'' = -J^2 rho_B (a parabola) in B, with continuous T and k dT/dx and J by the same root | temperature 1.9e-3 of the rise at the example's 0.125 mm (8.4e-3, 1.9e-3, 4.5e-4 at 0.25, 0.125, 0.0625 mm); terminal current 1.3e-6 relative |

The shipped example is `joule_temperature_regions` (`python -m simcase example
joule_temperature_regions`): a 2 x 1 mm strip in mm, a `linear_resistivity` metal
(2000 S/m at 300 K, 0.004 1/K, valid 250 to 600 K) on the left half in series with a
500 S/m resistor on the right, 0.2 V across the ends held at 300 and 320 K, element size
0.125 mm (288 nodes; 30 Picard iterations).

## Studio (region documents)

Studio validates and runs `joule.steady2d` and `joule.temperature2d` documents with material
regions on `POST /api/joule/validate` and `POST /api/joule/run`, with the request envelope of
the heat routes (`{"doc", "client_revision", "request_seq"}`). A rectangle electric document,
an `electric.steady2d` document and any other physics are refused by name
(`unsupported_geometry`, `unsupported_physics`). The routes take the
[Studio region path](thermal_studio.md#region-documents) step by step: the same region limits
(`max_shapes`, `max_circles`, `max_polygon_points`, `max_boundary_crossings`,
`max_input_vertices`) are checked before the document is read, and the job runs with the node
and triangle caps (`max_nodes`, `max_triangles`), so an over-fine mesh fails after meshing and
before the solve. Heat and Joule jobs share the one active job slot, the byte budget and the
result retention of the heat routes; there is no wall-clock limit on a job. A job's cost is its
mesh's times its Picard iterations, so a `joule.temperature2d` document whose
`iteration.iteration_limit` exceeds Studio's `max_iterations` (500) is refused before a job
(`iteration_limit_exceeded`, 413); the iteration records (about 1 kB each) count against the
result's `payload_bytes`, not the 64 KiB `metadata_bytes`. `/api/capabilities`
has a block for each kind (`run`, `validate`, `geometry: "regions"`, the result and payload
formats and the region limits, with `max_iterations` for `joule.temperature2d`).

A finished job's result (`GET /api/jobs/<job>/result`) is the payload
`studio-joule-regions-v1`: every array of the public result under its registry name (SI;
`triangle_regions` included, `evaluation_temperature` for `joule.temperature2d`), the
producer's summary (balances, terminal currents, regions and, for `joule.temperature2d`, the
Picard iteration records), `length_unit` and `display_length_in_m`. Before publishing, Studio
checks the result/layout pair, each array's shape and unit against the summary, the
connectivity and orientation, the prescribed node IDs, the mesh counts, and each region's
material and thermal conductivity against the document (`invalid_result` otherwise).

Errors: document, geometry and limit refusals keep their text (a temperature outside a
model's `valid.temperature`, a missing potential, a conductor part named by its regions that
touches no potential). A Picard iteration that does not converge is the job error
`not_converged` with the iteration count and the solver's reason (the iteration limit, or a
material model's valid range left by an iterate); another error inside the iteration gets the
fixed message. Any other failure replies with
Studio's fixed message and logs its traceback ([Security](../../security.md#browser-studio)).

Checks (`tests/simcase/test_studio_joule_regions.py`, pre-registered J-S1 to J-S4): the payload
of the two-material strip above equals `simcase.run` on the same document array for array and
bit for bit, and its summary apart from wall times, for both kinds; the refusals above; the
shape and node caps and the shared job slot; and results that disagree with their summary.
A strip at about 8,400 nodes gave a 4.9 MB payload in 8 s on one Linux machine (the payload
limit is 16 MiB). The workspace's [Joule heating application](workspace.md#joule-heating-on-named-regions)
builds and runs these documents.

## Run and save

```sh
python -m simcase example joule_temperature > model.json
python -m simcase validate model.json
python -m simcase run model.json -o fresh-results
```

Python uses `Document.from_dict` / `Document.load`, `run(document)` and
`ElectricJouleRunResult.save(path)`. `fields` returns owned numeric array copies;
`summary()` returns an independent JSON-compatible dictionary. Editing the caller's
input or those copies cannot alter the retained calculation. `doc` is a separate
snapshot; editing it invalidates saving. The EM-only `build_mesh`/`solve_point`
stages reject these physics explicitly.

Success writes `model.json` (the authored document), `log.txt` (the extent line first and
every diagnostic last), `summary.json`, and (unless disabled) `fields.npz`, using the existing
exclusive output ownership/cleanup protocol. Existing paths, including empty directories and
symlinks, are refused. A successful summary is written last; `.incomplete` identifies an
interrupted save. NPZ contains only numeric arrays and Unicode metadata and loads with
`allow_pickle=False`.

Result identifiers: `<physics-type>-result-v2`; layout `electric-joule2d-p1-v2` (the format 0.2
identifiers `-result-v1` and `electric-joule2d-p1-v1` are retired, and `simcase export` refuses
them by name). All values are SI:

| NPZ key | Location | Unit |
|---|---|---|
| `node_coordinates` | nodes | m |
| `triangles` | connectivity | (structural) |
| `electric_potential` | nodes | V |
| `electric_field` (x, y) | triangle centroids | V/m |
| `current_density` (x, y) | triangle centroids | A/m^2 |
| `electrical_conductivity` | triangle centroids | S/m |
| `joule_power_density` | triangle centroids | W/m^3 |
| `joule_power_per_depth` | nodes, the Joule load | W/m |
| `reaction_current_per_depth` | nodes, current the fixed potential injects into the body | A/m |
| `outward_prescribed_current_per_depth` | nodes, the prescribed current load, positive out | A/m |
| `residual_current_per_depth` | nodes | A/m |
| `electric_prescribed_node_ids`, `prescribed_electric_potential` | fixed-potential nodes | (structural), V |
| Joule: `temperature`, `heat_flux`, `generated_heat_rate_per_depth`, `reaction_heat_rate_per_depth`, `residual_heat_rate_per_depth`, `outward_prescribed_heat_rate_per_depth`, `ambient_convective_heat_rate_per_depth`, `outward_convective_heat_rate_per_depth`, `applied_heat_rate_per_depth`, `thermal_prescribed_node_ids`, `prescribed_temperature` | as for [heat](thermal_steady_boundary2d.md) | K, W/m^2, W/m |
| `joule.temperature2d`: `evaluation_temperature` | nodes, the T_i sigma was evaluated at | K |

The returned thermal field is H(T_i); sigma belongs to T_i, with the converged difference
bounded by the documented criteria.

`summary.json` carries the identifiers, the `diagnostics` list, `defaults_applied`,
`resolved_inputs` (authored text, SI value and unit of each input), the `extent` line,
`timing.wall_time`, the `field_units`, `field_locations`, `field_shapes` and `field_components`
maps, `mesh` (`nodes`, `triangles`), `study` and `balance`, every value as
`{"value", "unit"}`:

| `balance` key | Meaning | Unit |
|---|---|---|
| `current_imbalance_per_depth` | sum(reaction − outward prescribed load) | A/m |
| `maximum_residual_current_per_depth` | largest residual on a free node | A/m |
| `inward_electric_power_per_depth` | the supplied power sum(V I) | W/m |
| `joule_power_per_depth` | the integrated Joule heating | W/m |
| `electric_power_imbalance_per_depth` | supplied − Joule | W/m |
| Joule: `outward_heat_rate_per_depth` | sum(−reaction + outward prescribed + outward convective) | W/m |
| Joule: `heat_rate_imbalance_per_depth`, `maximum_residual_heat_rate_per_depth` | outward − source; largest free residual | W/m |
| Joule: `minimum_temperature`, `maximum_temperature` | | K |
| regions: `outward_current_per_depth.<name>` | per fixed boundary, positive out | A/m |

With a `depth` each `*_per_depth` value is followed by its total (`joule_power`,
`outward_current.<name>`, ..., per depth × depth). `joule.temperature2d` adds `iterations`, one
record per Picard step with `iteration_count`, `temperature_change` (K),
`relative_electrical_conductivity_change`, `minimum_temperature`, `maximum_temperature`,
`maximum_residual_current_per_depth`, `maximum_residual_heat_rate_per_depth`,
`relative_residual` and the balance columns of that step; each value carries its unit, so the
0.2 `iteration_units` table is gone, as are `units` and `mesh_length_unit`.

Invalid input: CLI exit 2. Solve, convergence or I/O failure: exit 1. Success:
exit 0. Nonconvergence/range failure propagates `JouleConvergenceError` in Python
with reason, completed history and last nodal temperature. The CLI emits that evidence
as one JSON object on stderr: `status: "failed"`, `reason`, `iterations` (the records above),
`last_iterate: {"temperature": {"unit": "K", "values": [...]}}` with non-finite values as
`null`, and `nonfinite_temperature_count`. It creates **no success output directory**.
Redirect stderr to retain a failed run. It never returns partial success.

## Validation and limits

The adapter is checked against direct Python calls; separate 1D resistor and
heated-slab formulas check length scaling, currents, powers and mesh convergence.
Failure paths include unknown keys, range violations, tiny relaxation without
convergence, output conflicts and interrupted writes. Spelling and length-unit invariance,
depth totals, the refusals and the result names are checked in
`tests/simcase/test_units_electric_joule.py`. Existing solver independent
reference-tool comparisons remain in force; this adapter adds no discretization.

Only the above rectangle and region subsets with a single study are exposed. Newton
iteration on documents, interface potentials, axisymmetric conduction, arbitrary
sigma callbacks, gauge-only currents, terminal totals, transient physics, 3D, Studio
execution of rectangle documents and release publishing are outside this contract. Saved fields can be viewed in
ParaView through `simcase.export` ([Viewing in ParaView](overview.md#viewing-in-paraview));
that export copies the saved arrays, adds the FieldData `units` and `conventions` blocks and
nothing else to this contract. A model can be structurally valid yet fail numerically;
validation does not certify convergence.
