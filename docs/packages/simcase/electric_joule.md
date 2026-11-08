# Electric and Joule heating documents

**English** | [한국어](../../locales/ko/pages/packages/simcase/electric_joule.md)

This is the normative JSON/CLI contract. The existing
[electric](../galerkin/electric_steady2d.md), [one-way Joule](../galerkin/joule_heating.md)
and [temperature-dependent Joule](../galerkin/temperature_joule_heating.md)
contracts define the numerical solves and unchanged acceptance tolerances.

## Scope and input

This section is the rectangle form; `electric.steady2d` also takes
[material regions](#material-regions-electric-steady-conduction).
Format `openphysics: "0.2"`. One named physics entry, `study: {"type":"single"}`,
a homogeneous 2D rectangle `geometry.domain` (`xmin,xmax,ymin,ymax`),
`mesh.subdivisions: [nx,ny]` positive integers, and `materials: {}`.
There are no shapes, sweeps, remeshing, thickness or implicit extra heat sources.
`units.length` is explicit (the existing length vocabulary); Joule documents also
require `units.temperature: "K"`. SI-suffixed values always use the indicated SI
unit, independently of the length unit. Unknown keys, nonfinite numbers, booleans
as numbers and conflicting corners are rejected. At most 200,000 triangles are
accepted before allocation. `results` defaults to `save_fields:true, plots:false`;
plots and Studio execution are unsupported.

Physics types:

- `electric.steady2d`: `conductivity_s_m` (>0), `dirichlet_potential_v` (side→V),
  optional `outward_current_a_m2` (side→J·n). At least one voltage side is required;
  pure Neumann/gauge documents are not supported. Unspecified sides are insulated.
- `joule.steady2d`: the same electrical keys, plus `thermal_conductivity_w_mk` (>0),
  `dirichlet_temperature_k` (side→K), optional `outward_flux_w_m2` (side→q·n) and
  `convection` (side→`{h_w_m2k,ambient_temperature_k}`). Nonnegative temperature
  and h; at least one thermal Dirichlet side or positive h. Flux plus convection
  is additive. Natural loads on a fully fixed edge are invalid. Sources come
  only from the electrical result on this exact mesh.
- `joule.temperature2d`: replace `conductivity_s_m` by `conductivity_model`, and
  require `initial_temperature_k` (scalar). Model keys are
  `type:"linear_resistivity"`, `reference_conductivity_s_m`,
  `reference_temperature_k`, `alpha_per_k`, `temperature_range_k:[lo,hi]`.
  `sigma(T)=sigma_ref/(1+alpha*(T-T_ref))`. Require finite `0<=lo<hi`, T_ref in
  range, sigma_ref>0, and finite positive denominator and conductivity at both
  endpoints. This linear denominator check covers the entire declared interval.
  Initial, prescribed and ambient temperatures must lie in the interval. Every
  trial nodal temperature is checked by the existing solver; no extrapolation,
  clipping, arbitrary Python callback, expression evaluation or import is allowed.

Sides are `left,right,bottom,top`; adjacent fixed sides must agree at their shared
corner. Actual fixed/natural-edge overlap is also checked on the generated mesh.
The mesh is built once in metres; element sigma is evaluated at the arithmetic
mean of its three nodal temperatures, after checking all three against the range.
Thermal conductivity is constant.

Optional `iteration` in temperature documents has `relaxation` (default .5,
0<value<=1), `temperature_atol_k` (1e-8), `relative_tolerance` (1e-10),
`max_iterations` (100). Tolerances must be positive; max_iterations is a positive
integer. The existing relaxed Picard loop checks the **unrelaxed** temperature
and conductivity defects and refreshed nonlinear thermal residual (<=1e-8).
Electrical/thermal linear residual and conservation gates are unchanged. See the
linked solver contract for normalization and stopping rules. Documents always
use the Picard loop; the Python API's `method="newton"` is not part of this format.

## Material regions (electric steady conduction)

An `electric.steady2d` document whose geometry has regions (a
[version 1 geometry block](geometry_document.md) with features or a background
material, or 0.2 `shapes`) uses the geometry, mesh and boundary names of
[region heat](thermal_regions2d.md):

- `materials.<name>.electrical_conductivity_s_m` (> 0) gives each region its
  conductivity; every material a region uses needs it. The same materials table may
  also hold heat properties (`conductivity_w_mk`, `volumetric_heat_capacity_j_m3k`);
  each physics reads the keys it needs. Built-in optical materials are never used.
  The physics entry takes no `conductivity_s_m`.
- `dirichlet_potential_v` and `outward_current_a_m2` take the domain sides, the
  exterior tags the geometry declares (`boundary_tags` names, `outer` on the border
  of a void feature) and exterior boundary selections. An interface selection
  between two regions is refused for both, because the electric solver fixes
  exterior nodes only. A name without mesh edges, two names given current on the
  same edges, current on an edge of a fixed boundary under another name, and two
  boundaries fixing a shared node to different potentials are refused by name.
- An unnamed exterior boundary, including a void border, is insulated. At least one
  potential is required.
- `mesh` is `{"size", "min_angle", "controls"}` as for region heat, and the region mesh
  limits apply. A void background and an axisymmetric component are refused.

The result format is `electric.steady2d-regions-result-v1` with field layout
`electric2d-p1-node-cell-regions-v1`: the rectangle fields plus `triangle_regions`,
and in the summary `region_names`, `region_materials`, `region_conductivity_s_m` and
`diagnostics.terminal_reaction_current_a_per_m`, the current leaving through each fixed
boundary in A per metre of depth (a node fixed by two boundaries counts for the first
one listed). `joule.steady2d` and `joule.temperature2d` keep the rectangle form and
refuse region geometry by name.

Independent checks (`tests/simcase/test_electric_regions.py`, pre-registered E1 to E7):

| Check | Reference | Result |
|---|---|---|
| Two layers in series | piecewise linear potential, I = V / sum(L_i / (sigma_i h)) | nodal error at most 1e-10 V; current 1e-10 relative |
| Two layers in parallel | I = V sum(sigma_i h_i) / L | 1e-10 relative |
| Coaxial circular electrodes (r = 3 and 9 mm, 192-gons) | I = 2 pi sigma (V_a - V_b) / ln(b/a) | relative error 2.0e-3, 6.6e-4, 1.4e-4 at mesh size 0.8, 0.4, 0.2 mm (order 2.3 on the last step) |
| Joule power | supplied power V I | 1e-10 relative |
| Rectangle documents | results before this change | every rectangle electric and Joule example bit for bit |

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

Success writes `model.json`, `log.txt`, `summary.json`, and (unless disabled)
`fields.npz`, using the existing exclusive output ownership/cleanup protocol.
Existing paths, including empty directories and symlinks, are refused. A successful
summary is written last; `.incomplete` identifies an interrupted save. NPZ contains
only numeric arrays and Unicode metadata and loads with `allow_pickle=False`.

Result IDs: `<physics-type>-result-v1`; layout `electric-joule2d-p1-v1`.
All coordinates are metres. Nodal arrays: potential V; electrical reaction,
prescribed outward current load and residual A/m; Joule load W/m. Element arrays:
electric field V/m, current density A/m², sigma S/m, Joule density W/m³.
Joule results also store nodal temperature K, thermal load/reaction/residual,
prescribed outward load, ambient load, convective outward load and system RHS
W/m; element heat flux W/m². Fixed-node IDs and prescribed values accompany each
physics. Temperature-dependent results additionally retain evaluated nodal
T_i in K and the full iteration history in summary JSON. The returned thermal
field is H(T_i); sigma belongs to T_i, with the converged difference bounded by
the documented criteria. Metadata gives each field's shape, location and unit.

Integrated currents are A/m of depth and powers W/m of depth, never A or W.
Electrical reaction is inward supplied current; conservation is
`sum(reaction-prescribed_outward_load)=0`. Electrical power is compared with
integrated Joule heat; thermal outward heat is
`sum(-reaction+prescribed_outward_load+convective_outward)`.
The summary records these balances, free residual norms, timings, software
versions and iteration units (absolute temperature defect K; conductivity and
nonlinear defects dimensionless; linear electric/thermal residual A/m and W/m).

Invalid input: CLI exit 2. Solve, convergence or I/O failure: exit 1. Success:
exit 0. Nonconvergence/range failure propagates `JouleConvergenceError` in Python
with reason, completed history and last nodal temperature. CLI emits that evidence
as one JSON object on stderr (`status:"failed"`), including nonfinite failed
values as null with a count if necessary. It creates **no success output directory**.
Redirect stderr to retain a failed run. It never returns partial success.

## Validation and limits

The adapter is checked against direct Python calls; separate 1D resistor and
heated-slab formulas check length scaling, currents, powers and mesh convergence.
Failure paths include unknown keys, range violations, tiny relaxation without
convergence, output conflicts and interrupted writes. Existing solver independent
reference-tool comparisons remain in force; this adapter adds no discretization.

Only the above rectangle and region subsets with a single study are exposed. Region
maps for Joule documents, interface potentials, axisymmetric conduction, arbitrary
sigma callbacks, gauge-only currents, transient physics, 3D, Studio
and release publishing are outside this contract. Saved fields can be viewed in
ParaView through `simcase.export` ([Viewing in ParaView](overview.md#viewing-in-paraview));
that export copies the saved arrays and adds nothing to this contract. A model can be
structurally valid yet fail numerically; validation does not certify convergence.
