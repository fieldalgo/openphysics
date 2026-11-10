# Linear elasticity and thermoelastic documents

**English** | [한국어](../../locales/ko/pages/packages/simcase/mechanics2d.md)

This is the normative JSON/CLI contract of `mechanics.elasticity2d` (isothermal) and
`mechanics.thermoelastic2d` (steady heat, then thermal stress on the same mesh). The
existing [2D elasticity](../galerkin/elasticity2d.md), [Cartesian traction](../galerkin/elasticity_traction.md),
[steady heat](../galerkin/thermal_steady2d.md) and
[thermoelastic traction](../galerkin/thermoelastic_traction.md) contracts define the
numerical solves and their unchanged acceptance tolerances; this adapter adds no
discretization.

## Scope and input

The documents are [format 0.3](document_format.md): every value carries its unit
(`"200 GPa"`, `"0 mm"`, `"1 MPa"`) and keys are registry quantity names. A format 0.2
mechanics document is refused by name (`E-FORMAT`). One named physics entry,
`study: {"type":"single"}` (its default), and a flat rectangle `geometry` with `length_unit`
(for example `m`, `mm` or `um`), `depth` (`null` for results per metre of depth, or a length
such as `"10 mm"`, which adds totals; for plane stress it is the plate thickness) and the four
`domain` bounds as plain numbers in that unit. `mesh` is `subdivision_count: [nx, ny]`
(positive integers) and `materials` is `{}`. There are no sweeps or remeshing. A document whose
geometry declares material regions takes the [region contract](#material-regions-and-named-boundaries)
instead; this section and the next describe the rectangle documents. Unknown keys
(`E-KEY-UNKNOWN`), non-finite numbers, booleans as numbers and conflicting corners are
refused. At most 200,000 triangles are accepted before allocation. `results` defaults to
`save_fields: true, plots: false`; plots and Studio execution are unsupported.

The physics entry of `mechanics.elasticity2d`:

| Key | Value |
|---|---|
| `plane` | `"stress"` or `"strain"` (required) |
| `youngs_modulus` | positive, such as `"200 GPa"` (menu `Pa kPa MPa GPa psi ksi`; `"200 mPa"` is millipascal and refused). `young_modulus` and `E` are unknown keys with "did you mean youngs_modulus" |
| `poisson_ratio` | a bare number, −1 < ν < 0.5 (both exclusive); a string is refused. Below 0 and above 0.49 warn (`W-MAGNITUDE`). Plane-strain P1 elements lock as ν approaches 0.5; passing the range check is not an accuracy guarantee there |
| `prescribed_displacement` | required: `{side: {"x": "0 mm", "y": "0 mm"}}`, sides `left,right,bottom,top`, at least one of `x`, `y` per listed side (menu `pm nm um mm m in mil`; `"0 mm"` is written). Each listed component is prescribed on every node of that side; the other stays free. Adjacent sides prescribing the same component must agree at their shared corner (compared on SI values). `z`, `r` and `"fixed"` are refused |
| `traction` | optional: `{side: ["1 MPa", "0 MPa"]}` or `{side: {"unit": "MPa", "values": [1, 0]}}`, a global Cartesian vector of exactly two entries, constant along the side (not normal/tangential). A component object is refused: a missing component would read as free. A traction component on a side whose same displacement component is prescribed must be zero; it would only be a reaction |
| `body_force_density` | optional: `["0 N/m^3", "-77000 N/m^3"]` (menu `N/m^3 kN/m^3 N/mm^3`); absent means no body force, recorded in `defaults_applied` |

A side with no displacement and no traction is traction free and is reported once as
`I-DEFAULT-BOUNDARY` at `physics.<name>.traction.<side>`. Refused by name: `gauge_pressure`
on a rectangle (give a traction, or use a region document), `absolute_pressure`
(`E-ABSOLUTE-AS-LOAD`: an absolute pressure is not a load), `force` and `force_per_depth` (no
point loads), `gravitational_acceleration` (gravity needs a mass density this release does not
read; give the weight as `body_force_density`), and every key of the thermal stage on
`mechanics.elasticity2d`.

**Rigid-body rule.** The constraints must hold all three planar rigid motions
u = (a − θy, b + θx). The document is refused unless some side prescribes `x`,
some side prescribes `y`, and the rotation θ is blocked, which happens exactly when
`x` is prescribed on `left` or `right`, or `y` on `bottom` or `top`, or `x` on both
`bottom` and `top`, or `y` on both `left` and `right`. Prescribing only `x` on one
horizontal side and `y` on one vertical side leaves a hinge about their corner and
is refused. The rule is decided from the document alone, before meshing; the
solver's rank test on the generated mesh agrees with it (checked for every
combination in the test set).

### Steady heat then thermal stress

`mechanics.thermoelastic2d` takes the same mechanical keys plus:

| Key | Value |
|---|---|
| `stress_free_temperature` | required, an absolute temperature above 0 K such as `"293.15 K"` or `"20 degC"`: the temperature at which the body is free of thermal strain. `reference_temperature` is an unknown key with "did you mean stress_free_temperature" |
| `linear_expansion_coefficient` | finite, signed, such as `"23 ppm/K"` (menu `1/K ppm/K um/(m K)`; `"23 ppm/degC"` is refused with a K fix). `mean_linear_expansion_coefficient` and `volumetric_expansion_coefficient` are refused by name |
| `thermal_conductivity` | positive, such as `"237 W/(m K)"` |
| `prescribed_temperature.<side>` | absolute temperatures above 0 K; required, and may be `{}` when a positive convection coefficient anchors the temperature |
| `inward_heat_flux.<side>` | optional, **positive into the body** (the 0.2 `outward_flux_w_m2` negated); `outward_heat_flux` is an unknown key ("inputs are inward_") |
| `convection.<side>` | `{"heat_transfer_coefficient": "25 W/(m^2 K)", "ambient_temperature": "300 K"}` |
| `heat_source_density` | optional, such as `"20000 W/m^3"`; absent means no source (`defaults_applied`) |

These are the side-constant heat data of the [steady heat](thermal_steady2d.md) and
[boundary](thermal_steady_boundary2d.md) contracts: at least one fixed side or a positive
convection coefficient, no natural condition on a fixed side, corners agreeing. A side with no
thermal condition is insulated and is reported as `I-DEFAULT-BOUNDARY` at
`physics.<name>.inward_heat_flux.<side>`. Absolute temperatures (stress-free, prescribed,
ambient) must be above 0 K (`E-DOMAIN`); format 0.2 allowed 0 K. The runner solves
`galerkin.thermal.solve_steady_heat` on the mesh, freezes the nodal temperature with
`galerkin.thermoelasticity.freeze_temperature` and calls `solve_thermoelasticity` with the
mechanical arguments. `traction` is the TOTAL physical σ·n, as in the Python contract, never
adjusted by a thermal traction. The coupling is one-way: no mechanical feedback to heat, no
temperature-dependent material, no cross-mesh transfer.

Format 0.2 keys are refused with their new names (`E-KEY-UNKNOWN`); for the outward heat flux
the message says to write the negated value, and no automatic fix is offered because the
meaning changes:

| Format 0.2 | Format 0.3 |
|---|---|
| `units.length`, `units.temperature` | `geometry.length_unit`; every value carries its unit |
| `mesh.subdivisions` | `mesh.subdivision_count` |
| `young_modulus_pa` | `youngs_modulus` |
| `displacement_m` | `prescribed_displacement` |
| `traction_pa` | `traction` |
| `body_force_n_m3` | `body_force_density` |
| `pressure_pa` (regions) | `gauge_pressure`, the same sign |
| `reference_temperature_k` | `stress_free_temperature` |
| `thermal_expansion_per_k` | `linear_expansion_coefficient` |
| `thermal_conductivity_w_mk`, materials `conductivity_w_mk` | `thermal_conductivity` |
| `dirichlet_temperature_k` | `prescribed_temperature` |
| `outward_flux_w_m2` | `inward_heat_flux` = −old |
| `convection.<side>.{h_w_m2k, ambient_temperature_k}` | `convection.<side>.{heat_transfer_coefficient, ambient_temperature}` |
| `heat_source_w_m3` | `heat_source_density` |
| `mesh.size`, `mesh.min_angle` (regions) | `mesh.element_size` (a length with its unit), `mesh.minimum_angle` (`"28 deg"` by default) |

## Run and save

```sh
python -m simcase example elastic_plate > model.json
python -m simcase validate model.json
python -m simcase run model.json -o fresh-results
```

Python uses `Document.from_dict` / `Document.load`, `run(document)` and
`MechanicsRunResult.save(path)`. `fields` returns owned numeric array copies;
`summary()` returns an independent JSON-compatible dictionary. Editing the caller's
input or those copies cannot alter the retained calculation. `doc` is a separate
snapshot; editing it invalidates saving. The EM-only `build_mesh`/`solve_point`
stages reject this physics explicitly.

The runner builds `galerkin.rectangle_mesh` once in metres (nodes offset to the
domain origin), prescribes the side nodes as `{(node, component): m}` sorted by
`(node, component)`, and calls `galerkin.elasticity.solve_elasticity` with the
document's plane, E, ν, body force (`(0, 0)` when absent) and tractions in document order.
A document run and a direct call with these arguments give byte-identical arrays.

Success writes `model.json` (the authored document), `log.txt` (the extent line first and
every diagnostic last), `summary.json`, and (unless disabled) `fields.npz`, using the existing
exclusive output ownership/cleanup protocol. Existing paths, including empty directories and
symlinks, are refused. A successful summary is written last; `.incomplete` identifies an
interrupted save. NPZ contains only numeric arrays and Unicode metadata and loads with
`allow_pickle=False`.

Result identifiers: `mechanics.elasticity2d-result-v2` with layout `mechanics2d-p1-v2`, and
`mechanics.thermoelastic2d-result-v2` with layout `thermoelastic2d-p1-v2` (the format 0.2
identifiers `-result-v1`, `mechanics2d-p1-v1` and `thermoelastic2d-p1-v1` are retired, and
`simcase export` refuses them by name). All values are SI:

| NPZ key | Shape | Unit | Meaning |
|---|---|---|---|
| `node_coordinates` | (N,2) | m | node coordinates |
| `triangles` | (T,3) | (structural) | connectivity |
| `displacement` (x, y) | (N,2) | m | nodal (u_x, u_y) |
| `strain` | (T,3) | 1 | element strain, components `strain_xx, strain_yy, engineering_shear_strain_xy` (γ_xy = 2 ε_xy); thermoelastic: the total strain |
| `stress` | (T,3) | Pa | element stress `stress_xx, stress_yy, stress_xy` |
| `applied_force_per_depth` | (N,2) | N/m | the consistent body plus traction load |
| `reaction_force_per_depth` | (N,2) | N/m | K·u − load at prescribed DOFs (zero elsewhere): the force the constraint exerts on the body |
| `residual_force_per_depth` | (N,2) | N/m | K·u − load at all DOFs |
| `prescribed_node_ids`, `prescribed_components`, `prescribed_displacement` | (K,) | (structural), (structural), m | the prescribed DOFs (component 0 = x, 1 = y) and values |

A thermoelastic result adds:

| NPZ key | Shape | Unit | Meaning |
|---|---|---|---|
| `temperature`, `heat_flux`, `generated_heat_rate_per_depth`, `reaction_heat_rate_per_depth`, `residual_heat_rate_per_depth`, `outward_prescribed_heat_rate_per_depth`, `ambient_convective_heat_rate_per_depth`, `outward_convective_heat_rate_per_depth`, `applied_heat_rate_per_depth`, `thermal_prescribed_node_ids`, `prescribed_temperature` | | K, W/m², W/m | the steady heat solution the mechanics used, as for [heat](thermal_steady_boundary2d.md) (the rates are zero when the document has no flux or convection) |
| `thermal_strain`, `elastic_strain` | (T,3) | 1 | components `thermal_strain_xx, …, engineering_shear_thermal_strain_xy` and the same for `elastic_`; `strain` = thermal + elastic |
| `stress_zz`, `strain_zz` | (T,) | Pa, 1 | the out-of-plane stress (plane strain) or strain (plane stress) |
| `thermal_equivalent_force_per_depth`, `applied_body_force_per_depth`, `applied_traction_force_per_depth` | (N,2) | N/m | the thermal-equivalent load and the two parts of `applied_force_per_depth` |

Strain and stress are constant per P1 element (`field_locations` says `triangle_centroids`);
`field_components` names the components of each array. `summary.json` carries the identifiers,
the `diagnostics` list, `defaults_applied`, `resolved_inputs` (authored text, SI value and unit
of each input), the `extent` line, `timing.wall_time`, the `field_units`, `field_locations`,
`field_shapes` and `field_components` maps, `plane`, `youngs_modulus`, `poisson_ratio` (bare),
`body_force_density` when given, `mesh` (`nodes`, `triangles`), `study` and `balance`, every
value as `{"value", "unit"}` (an [x, y] force as `{"unit", "values"}`); the thermoelastic
summary adds `linear_expansion_coefficient`, `thermal_conductivity`, `stress_free_temperature`
and the `temperature_snapshot` hashes (`mesh_hash`, `temperature_hash`, `snapshot_hash`) of the
frozen temperature.

| `balance` key | Meaning | Unit |
|---|---|---|
| `applied_force_per_depth` | the summed applied (external) load per component | N/m |
| thermoelastic: `thermal_equivalent_force_per_depth` | the summed thermal-equivalent load | N/m |
| `reaction_force_per_depth` | the summed support reaction | N/m |
| `force_imbalance_per_depth` | applied (plus thermal) load plus reaction, per component | N/m |
| `maximum_residual_force_per_depth` | the largest free-DOF residual | N/m |
| `strain_energy_per_depth` | elasticity: ½ uᵀKu; thermoelastic: the physical elastic energy ½ ∫ σ:ε_el | J/m |
| thermoelastic: `stiffness_energy_functional_per_depth` | the solver's ½ uᵀKu (it includes the thermal load term, so it is not the stored energy) | J/m |
| `maximum_displacement` | the largest nodal displacement magnitude | m |
| `maximum_stress` | the largest absolute in-plane Cartesian stress component over elements | Pa |
| thermoelastic: `generated_heat_rate_per_depth`, `outward_heat_rate_per_depth`, `heat_rate_imbalance_per_depth`, `maximum_residual_heat_rate_per_depth`, `minimum_temperature`, `maximum_temperature` | the heat stage, as for Joule heating | W/m, K |

With a `depth` each `*_per_depth` value is followed by its total (`applied_force`,
`strain_energy`, …, per depth × depth); without one, results are per metre of depth and no
total appears. The format 0.2 `strain_energy_j_per_m` of a thermoelastic result is
`stiffness_energy_functional_per_depth`, and its `physical_elastic_energy_j_per_m` is
`strain_energy_per_depth`; the format 0.2 `units`, `mesh_length_unit`, `diagnostic_units` and
component lists are gone.

Invalid input: CLI exit 2 and no output directory. Solve or I/O failure (a singular
system the rule did not foresee, nonfinite values, an occupied output): exit 1.
Success: exit 0. Saved fields can be viewed in ParaView through `simcase.export`
([Viewing in ParaView](overview.md#viewing-in-paraview)): point data `displacement` and the
nodal force arrays as vectors with z = 0 (the thermoelastic layout adds `temperature` and the
nodal heat rates as scalars), cell data one scalar per named component (`strain_xx`,
`strain_yy`, `engineering_shear_strain_xy`, `stress_xx`, `stress_yy`, `stress_xy`;
thermoelastic: `heat_flux`, `stress_zz`, `strain_zz` and the `thermal_strain_…` and
`elastic_strain_…` components), and the FieldData `units` and `conventions` blocks; the export
copies the saved arrays and adds nothing else to this contract.

## Validation

`tests/simcase/test_mechanics.py` holds the pre-registered gates. The values below are from
Linux, Python 3.12, NumPy 2.5.4, SciPy 1.18.1 (2026-11-02, format 0.2); the rows marked format
0.3 were measured on 2026-11-10.

| Gate | Criterion | Measured |
|---|---|---|
| J1 | document run equals direct `solve_elasticity` on the same mesh, byte for byte (plane stress and strain, offset millimetre domain, body force and two tractions) | identical bytes for all six arrays |
| J2 | `refsol.elasticity_traction.uniaxial` and `shear` for `m`, `mm`, `um`, `nm`, both planes: relative error ≤ 1e-10 on displacement and stress | ≤ 4.6e-15 displacement, ≤ 1.3e-14 stress, ≤ 9.1e-15 strain |
| J3 | constant-body-force bar u = f/(λ+2μ)(Lx − x²/2, 0) with x, y fixed at x = 0 and y fixed on bottom and top: centroid displacement order ≥ 1.8 over subdivisions 8, 16, 32 | orders 1.95, 1.97 (plane stress) and 1.94, 1.97 (plane strain); element stress orders 0.95–0.98 |
| J4 | 33 invalid documents (hinges, one component only, corner conflict, a bare displacement, the `units` block, a missing or unknown length unit, bad plane, ν = 0.5 and −1, tagged lists, traction on a prescribed component, …) refused with exit 2 and no output; the rigid-body rule matches the solver's rank test on 12 constraint sets | all refused |
| J5 | CLI validate/run/save, fresh output refused with the existing summary untouched, partial-save cleanup leaves nothing, result copies and the document snapshot are immutable | passed |
| J6 | Studio `/api/validate` and `_require_studio_physics` refuse the type; the Studio Node checks stay green | passed |
| J7 | `tools/wheel_consumers/test_mechanics_wheel.py` (uniaxial plate and thermoelastic bar CLI, hinge refusal, VTU export) run with `python -I` from a temporary directory, as `check_platform_install.py` does | passed |
| K1 | thermoelastic document run equals `solve_steady_heat` + `freeze_temperature` + `solve_thermoelasticity` on the same mesh, byte for byte (both planes, heat source, flux and convection sides, body force, two tractions) | identical bytes for all 16 arrays, same snapshot hash |
| K2 | `refsol.thermoelastic_traction.uniform_combined` with zero shear (normal stresses 8 and −2 MPa, +20 K), uniform temperature from four prescribed sides, for `m`, `mm`, `um`, `nm` and both planes: relative error ≤ 1e-10 on temperature, displacement, in-plane and zz stress and total strain | temperature exact, ≤ 3.4e-15 displacement, ≤ 3.1e-14 stress, ≤ 1.1e-14 σ_zz, ≤ 1.1e-14 strain; physical energy to 1e-10 |
| K3 | confined bar with the linear temperature of two prescribed sides, u_x = k α((T₁−T₀)x + Gx²/2), k = 1+ν or (1+ν)/(1−ν), T₀ the stress-free temperature, stress from `refsol.thermoelastic_traction.parent_state`: displacement order ≥ 1.8 over subdivisions 8, 16, 32 | orders 1.95, 1.97 (plane stress) and 1.94, 1.97 (plane strain); stress orders 0.97–1.00; temperature reproduced to 1e-9 K |
| K4 | 16 invalid thermoelastic documents (the `units` block, a Fahrenheit temperature, missing or zero conductivity, missing or nonfinite α, negative or missing stress-free temperature, pure Neumann heat, negative or conflicting temperatures, flux on a fixed side, negative h, hinge, Joule-only keys) refused with exit 2 and no output; heat keys refused on `mechanics.elasticity2d` | all refused |
| J2, K2 (format 0.3) | the same gates on format 0.3 documents, whose length-unit copies are read on the picometre grid | J2 ≤ 3.6e-15 displacement, ≤ 1.0e-14 stress, ≤ 9.1e-15 strain; K2 temperature exact, ≤ 2.5e-15 displacement, ≤ 2.7e-14 stress, ≤ 8.6e-15 σ_zz, ≤ 7.8e-15 strain |
| J3, K3 (format 0.3) | the same gates on format 0.3 documents | the same orders: displacement 1.95, 1.97 and 1.94, 1.97; element stress 0.94–0.98 (J3) and 0.97–1.00 (K3) |
| Spelling (format 0.3) | `elastic_plate`, `thermoelastic_regions` and the K1 rectangle rewritten in every other spelling and menu unit of their values (`"200000 MPa"`, `"29000 ksi"` = `"29000000 psi"`, `"23 um/(m K)"`, `"20 degC"`, `"100 barg"`, tagged arrays, …) and with character aliases: the same SI tree, saved arrays and summary | bit-identical; aliases carry a fix |
| Length unit (format 0.3) | the four examples' shape numbers in m, mm, µm and nm, and a 4 × 0.8 in plate against 101.6 × 20.32 mm: the same picometre counts, arrays and summary; mm numbers declared in m warn (rectangles, `W-GEOMETRY-SCALE`) or are refused before meshing (regions, `E-MESH-ESTIMATE`) | bit-identical, the region angle within 1e-13 relative (at most 61 ulp); warned and refused |
| Depth (format 0.3) | `depth` `null`, `"1 m"`, `"10 mm"`, `"40 mm"`: identical per-depth arrays and values, totals equal per depth × depth exactly; `"0 m"` and a missing depth refused | bit-identical; refused |
| Refusals and diagnostics (format 0.3) | 111 refusals of G3 M5 and §4.6–4.7 with code and path; `I-PM-ROUNDING`, `W-PM-ROUNDING`, `W-MAGNITUDE` (acknowledged or not), `I-UNUSED-PROPERTY`, `W-GAUGE-ATMOSPHERIC` and `I-DEFAULT-BOUNDARY` reach validate, run, `log.txt`, `summary.json` and `metadata_json` | all as specified |
| Gauge pressure sign (format 0.3) | a positive `gauge_pressure` in the bore of `elastic_regions` moves the bore outward | radial displacement > 0 at every bore node |

The `refsol.elasticity_traction.polynomial_manufactured` and
`refsol.thermoelastic_traction.polynomial_manufactured` fields need position
dependent body forces, tractions and temperatures, and `uniform_combined` with its
shear term has no side with a constant displacement component; a side-constant
document cannot express them. J3 and K3 therefore use the quadratic bars above,
derived in the tests from the Navier equation, independent of the solver, and K2
uses the shear-free `uniform_combined` state.

Spelling and length-unit invariance, depth totals, the refusals and their paths, the
diagnostics, the result names and the export are checked in
`tests/simcase/test_units_mechanics.py`. Since the units and naming batch these checks run on
format 0.3 documents; the 0.2 documents on the code before the batch and the converted
documents give the same solver inputs and saved bytes for the shipped examples and the J1, K1,
R1, R2, R4 and R5 cases (`tools/units_batch`), so J1, K1 and the region numbers below are
unchanged.

## Material regions and named boundaries

A `mechanics.elasticity2d` or `mechanics.thermoelastic2d` document whose `geometry`
has `background` or `shapes`, or a [version 1 geometry block](geometry_document.md)
with features or a background material, describes several materials. It uses the
geometry, mesh and boundary names of [region heat](thermal_regions2d.md):
`mesh.element_size` (and `minimum_angle`, default `"28 deg"`), shapes or features over a
background, later features winning. A version 1 homogeneous rectangle without a background
material is still a rectangle document.

The shipped examples are `elastic_regions` (a quarter of a thick steel pipe under
inner pressure, the bore and outer surface named through `boundary_tags`) and
`thermoelastic_regions` (a steel–aluminium bimetal strip heated by 50 K, clamped at
the left end):

```json
{
  "openphysics": "0.3",
  "name": "Quarter of a thick steel pipe under 10 MPa inner pressure",
  "geometry": {"version": 1, "components": {"main": {
    "dimension": "2d", "length_unit": "mm", "depth": null,
    "domain": {"xmin": 0, "xmax": 9, "ymin": 0, "ymax": 9},
    "background": {"material": "steel"},
    "features": [
      {"name": "outside", "type": "rect", "x": 0, "y": 0, "w": 9, "h": 9, "material": null},
      {"name": "wall", "type": "circle", "cx": 0, "cy": 0, "r": 9, "material": "steel"},
      {"name": "bore", "type": "circle", "cx": 0, "cy": 0, "r": 3, "material": null}],
    "finalize": "later_wins",
    "boundary_tags": [
      {"tag": "inner", "select": {"boundary": {"of": "bore"}}},
      {"tag": "outer_wall", "select": {"boundary": {"between": ["wall", "outside"]}}}]}}},
  "materials": {"steel": {"youngs_modulus": "200 GPa", "poisson_ratio": 0.3, "source": "document value"}},
  "mesh": {"element_size": "0.5 mm"}, "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false},
  "physics": {"pipe": {"type": "mechanics.elasticity2d", "plane": "strain",
    "prescribed_displacement": {"left": {"x": "0 mm"}, "bottom": {"y": "0 mm"}},
    "gauge_pressure": {"inner": "10 MPa"}}}
}
```

**Materials.** Every used material gives `youngs_modulus` (> 0) and `poisson_ratio`
(−1 < ν < 0.5); a thermoelastic document also needs `linear_expansion_coefficient` (finite,
signed) and `thermal_conductivity` (> 0), the name region heat reads (format 0.2 named it
`conductivity_w_mk` in the table and refused `thermal_conductivity_w_mk` there; both are one
name now). A missing property is `E-PROPERTY-MISSING`; a property this run does not read
(such as `thermal_conductivity` for an elasticity document) is reported as
`I-UNUSED-PROPERTY`. `shear_modulus`, `bulk_modulus`, `elasticity_tensor` and the mean or
volumetric expansion coefficients are refused by name. The `materials` table is shared with the
other region physics; library materials (`physmat:...`) carry no mechanical properties for
these kinds yet and are refused by name. In `physics`, `youngs_modulus`, `poisson_ratio`,
`linear_expansion_coefficient` and `thermal_conductivity` are refused by name ("from
materials.<m>").

**Physics keys.** `type`, `plane`, `prescribed_displacement` (required), and optionally
`traction`, `gauge_pressure` and `body_force_density`. A thermoelastic document adds
`stress_free_temperature` (required) and the region heat keys `heat_source_density` (one value
or `{region name: value}`), `prescribed_temperature`, `inward_heat_flux` and `convection`,
with the region heat rules (a prescribed temperature or a positive convection coefficient;
a prescribed temperature may fix an interface selection, flux and convection may not).

**Boundary names.** `prescribed_displacement`, `traction` and `gauge_pressure` take the
names region heat takes for its exterior data: the four domain sides, a
`boundary_tags` name, `outer` on the border of a void feature, and a boundary
selection whose curves all lie on the exterior. An interface selection is refused
by name: galerkin fixes exterior nodes only, and a traction needs exterior edges.
An unnamed exterior boundary, a void border included, is traction free; the domain sides
among them are reported as `I-DEFAULT-BOUNDARY`.

- `prescribed_displacement`: `{name: {"x": "0 mm", "y": "0 mm"}}`; each listed component is
  prescribed on every node of that boundary. Two names that fix a shared node to
  different values are refused when the document runs.
- `traction`: `{name: ["1 MPa", "0 MPa"]}`, a constant global Cartesian vector.
- `gauge_pressure`: `{name: "10 MPa"}`, the pressure above the surroundings (menu
  `Pa kPa MPa GPa bar mbar psi ksi barg psig`), applied as the traction
  `−gauge_pressure · n` with `n` the outward normal of each boundary edge: **a positive gauge
  pressure pushes into the body**. It is the 0.2 `pressure_pa` with the same sign (the
  galerkin `−p·normal` callback on the reference boundary; no follower update). An absolute
  pressure (`"10 bara"`, `"10 psia"`, or an `absolute_pressure` key) is refused
  (`E-ABSOLUTE-AS-LOAD`), `atm` is not on the menu, and a value between 90 and 110 kPa warns
  (`W-GAUGE-ATMOSPHERIC`: it looks like an absolute atmospheric pressure).
- One boundary takes one load: a name in both `traction` and `gauge_pressure`, or
  two names that share mesh edges and both carry a load, are refused. A nonzero
  traction or pressure component on an edge whose same displacement component is
  prescribed is refused, as on the rectangle.

**Rigid-body rule.** At load, some boundary must fix `x` and some `y`. When the
document runs, every connected part of the mesh (a void can cut the body in
pieces) must be held against all three planar rigid motions; a part that is not is
refused by name with its regions. This is the rank test galerkin applies.

**Refused.** An axisymmetric component (plane mechanics does not describe a body
of revolution), a void background, a feature or shape that the domain cuts away or
that is a sliver, `mesh.subdivision_count`, plots, and a study other than single. The
refusals found at load leave the CLI with exit 2; those found on the mesh (an
unheld part, a shared node fixed twice, a name without mesh edges, a doubled load)
with exit 1, as for region heat. Mesh limits (`max_input_vertices`, `max_nodes`,
`max_triangles`, see [mesh limits for callers](thermal_regions2d.md#mesh-limits-for-callers))
apply to region documents; the rectangle documents refuse them. A region document whose
millimetre numbers are declared in metres is refused before meshing by the element estimate
(`E-MESH-ESTIMATE`: about 6.5e8 triangles for `elastic_regions`, 3.2e9 for
`thermoelastic_regions`, against the limit 600,000).

**Run and results.** The runner meshes the regions once, as region heat does: a
micrometre copy of the document is meshed by meshine and the nodes are converted to
metres once, maps E, ν and α by region name and calls `solve_elasticity`, or
`solve_steady_heat` with conductivity by region, `freeze_temperature` and
`solve_thermoelasticity`. The result IDs are `mechanics.elasticity2d-regions-result-v2`
(layout `mechanics2d-p1-regions-v2`) and `mechanics.thermoelastic2d-regions-result-v2`
(layout `thermoelastic2d-p1-regions-v2`). The arrays are those of the rectangle
layouts plus `triangle_regions` (one region id per triangle, `int64`). In place of
the scalar material entries, the summary holds `region_names` (the index order of
`triangle_regions`), `regions` (material, triangle count and meshed `area` per region), the
`materials` table in SI, the boundary data (`prescribed_displacement`, `traction`,
`gauge_pressure` and `gauge_pressure_sign`, and for thermoelasticity the heat data, the
`inward_heat_flux` echo positive into the body) and the mesh (`nodes`, `triangles`,
`minimum_triangle_angle` in rad). Diagnostics, `balance` and saving are those of the
rectangle results. `simcase.export` does not yet take the two region layouts (it refuses them
as an unsupported field layout).

Only the shape numbers follow `length_unit` (domain and features); every other value carries
its own unit. The same document written in m, mm, µm or nm gives bit-identical saved arrays and
summaries, except the achieved minimum triangle angle, which is measured on the triangulation
of the document's own numbers and moves within 1e-13 relative (at most 61 ulp on these
examples). Saved coordinates come from the micrometre mesh times 1e-6 and can differ from a
round number in the last digit (0.1 m may read 0.09999999999999999): select nodes with a
tolerance.

**Validation** (`tests/simcase/test_mechanics_regions.py`; checks R0 to R7
pre-registered in the HQ work record on 2026-11-08 before the code; measured the
same day on Linux, Python 3.12, the pinned environment):

| Check | Criterion | Measured |
|---|---|---|
| R0 | `elastic_plate` and `thermoelastic_bar`: saved arrays and summary (timings and versions aside) SHA-256 identical before and after | identical |
| R1 | a region run equals the direct galerkin calls on the same mesh, byte for byte (elastic with gauge pressure, traction and body force, and thermoelastic with per-region source, flux and convection, both in both planes); the mechanical arguments are rebuilt in the test the way the runner builds them, so R1 checks the hand-off, and R2–R5 the physics (R4 the pressure sign) | identical bytes |
| R2 | two layers in series (ν = 0, E 200 and 70 GPa), version 1 and flat regions, both planes: end displacement s(L₁/E₁ + L₂/E₂) and σxx = s within 1e-10 | ≤ 2.7e-15 displacement, ≤ 1.8e-14 stress |
| R3 | two layers in parallel (ν = 0.3) under a prescribed end displacement: end reaction Σ E′ᵢhᵢ d/L within 1e-10 (E′ = E plane stress, E/(1−ν²) plane strain) | ≤ 2.2e-14 |
| R4 | Lamé pipe (a = 3, b = 9 mm, plane strain, inner gauge pressure through a `boundary_tags` name): largest nodal radial error ≤ 1e-2 of u_r(a) at h = 0.25 mm; order ≥ 1.8 over h = 0.5, 0.25, 0.125 mm; the bore selection gives the same displacement as the tag | 1.4e-2, 3.1e-3, 8.4e-4 (orders 2.22, 1.89); identical |
| R5 | confined bilayer free expansion (+50 K, ν = 0, both planes): end displacement ΔT(α₁L₁ + α₂L₂) and σyy = −EᵢαᵢΔT per region within 1e-10 | ≤ 1.5e-14, ≤ 6.3e-15 |
| R5b | series conduction (k 45 and 237 W/(m K), 400 to 300 K): interface temperature within 1e-9, end displacement against the closed-form integral within 2e-3 | 3.7e-16, 2.5e-6 |
| R6 | refusals by name, with their codes and paths (interface selections for displacement, traction and gauge pressure; unknown names; material keys in physics; missing or invalid material keys; void background; dropped features and shapes; axisymmetric; `subdivision_count`; the `units` block; a missing length unit; an unheld part; a shared node fixed twice; a doubled load; a gauge pressure or traction on a prescribed component under its own or another name; a side without mesh edges; thermoelastic heat refusals); CLI exit 2 at load and 1 on the mesh, no output; a boundary held tangentially and pressed normally is accepted | all refused; accepted |
| R7 | mesh limits reach region mechanics; the rectangle documents refuse them | passed |

R4's sizes were chosen after a first measurement at h = 1 mm (a 16-sided bore,
about two elements across the wall), whose order to 0.5 mm is 0.97; that level is
before the asymptotic range and is kept out of the gate. A check outside the
pre-registration: the bimetal example's tip deflection is within 1.3 % of
Timoshenko's bimetal formula (beam theory), gated at 2 %.

## Limits

Rectangle documents: one homogeneous isotropic rectangle, side-constant data.
Region documents: piecewise constant isotropic materials, constant tractions and
gauge pressures per named boundary, no interface displacement or load, no axisymmetric
component. Both: static small strain, a single study, no general normal/tangential
or distributed traction, no point loads, no gravity from a mass density, no dynamics, 3D or
Studio form. Thermal stress is one-way from a
steady heat solve on the same mesh: no mechanical feedback, no temperature-dependent
properties, no transient temperatures, no prescribed external temperature field
(the Python [transient](../galerkin/transient_thermal_mechanical.md) and
[prescribed-temperature](../galerkin/prescribed_temperature_thermoelasticity.md)
workflows stay Python-only). A structurally valid model can still fail
numerically (near-incompressible plane strain, extreme aspect ratios); validation
does not certify accuracy.
