# Linear elasticity documents

**English** | [한국어](../../locales/ko/pages/packages/simcase/mechanics2d.md)

This is the normative JSON/CLI contract of `mechanics.elasticity2d`. The existing
[2D elasticity](../galerkin/elasticity2d.md) and [Cartesian traction](../galerkin/elasticity_traction.md)
contracts define the numerical solve and its unchanged acceptance tolerances; this
adapter adds no discretization.

## Scope and input

Format `openphysics: "0.2"`. One named physics entry, `study: {"type":"single"}`,
a homogeneous 2D rectangle `geometry.domain` (`xmin,xmax,ymin,ymax`),
`mesh.subdivisions: [nx,ny]` positive integers, and `materials: {}`. There are no
shapes, regions, sweeps, remeshing or thickness. `units` holds exactly `length`
(the existing length vocabulary); SI-suffixed values always use the indicated SI
unit, independently of the length unit. Unknown keys, nonfinite numbers, booleans
as numbers and conflicting corners are rejected. At most 200,000 triangles are
accepted before allocation. `results` defaults to `save_fields:true, plots:false`;
plots and Studio execution are unsupported. The rectangle, unit, mesh, study and
result checks are the ones of the [steady heat contract](thermal_steady2d.md).

Physics keys of `mechanics.elasticity2d`:

- `plane`: `"stress"` or `"strain"`.
- `young_modulus_pa` (> 0) and `poisson_ratio` (−1 < ν < 0.5, both exclusive).
  Plane-strain P1 elements lock as ν approaches 0.5; passing the range check is not
  an accuracy guarantee there.
- `displacement_m` (required): `{side: {"x": m, "y": m}}` with sides
  `left,right,bottom,top` and at least one of `x`, `y` per listed side. Each
  listed component is prescribed on every node of that side, in metres; the other
  component of the side stays free. Adjacent sides prescribing the same component
  must agree at their shared corner.
- `body_force_n_m3` (optional): constant `[fx, fy]` in N/m³; default `[0, 0]`.
- `traction_pa` (optional): `{side: [tx, ty]}`, global Cartesian in Pa, constant
  along the side (not normal/tangential). Unlisted sides are traction free. A
  traction component on a side whose same displacement component is prescribed
  must be zero; it would only be a reaction.

**Rigid-body rule.** The constraints must hold all three planar rigid motions
u = (a − θy, b + θx). The document is refused unless some side prescribes `x`,
some side prescribes `y`, and the rotation θ is blocked, which happens exactly when
`x` is prescribed on `left` or `right`, or `y` on `bottom` or `top`, or `x` on both
`bottom` and `top`, or `y` on both `left` and `right`. Prescribing only `x` on one
horizontal side and `y` on one vertical side leaves a hinge about their corner and
is refused. The rule is decided from the document alone, before meshing; the
solver's rank test on the generated mesh agrees with it (checked for every
combination in the test set).

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
document's plane, E, ν, body force and tractions. A document run and a direct call
with these arguments give byte-identical arrays.

Success writes `model.json`, `log.txt`, `summary.json`, and (unless disabled)
`fields.npz`, using the existing exclusive output ownership/cleanup protocol.
Existing paths, including empty directories and symlinks, are refused. A successful
summary is written last; `.incomplete` identifies an interrupted save. NPZ contains
only numeric arrays and Unicode metadata and loads with `allow_pickle=False`.

Result ID `mechanics.elasticity2d-result-v1`; layout `mechanics2d-p1-v1`;
`mesh_length_unit` is `m`. Saved arrays:

| Array | Shape | Unit | Meaning |
|---|---|---|---|
| `nodes_m` | (N,2) | m | node coordinates |
| `triangles` | (T,3) | 1 | connectivity |
| `displacement_m` | (N,2) | m | nodal (u_x, u_y) |
| `strain` | (T,3) | 1 | element engineering strain `exx, eyy, gxy` (γ_xy = 2 ε_xy) |
| `stress_pa` | (T,3) | Pa | element stress `sxx, syy, sxy` |
| `load_n_per_m`, `reaction_n_per_m`, `residual_n_per_m` | (N,2) | N/m | consistent body plus traction load; K·u − load at prescribed DOFs (zero elsewhere); K·u − load at all DOFs |
| `dirichlet_node_ids`, `dirichlet_components`, `dirichlet_displacement_m` | (K,) | 1, 1, m | the prescribed DOFs (component 0 = x, 1 = y) and values |

Strain and stress are constant per P1 element (`field_locations` says
`triangle_centroids`); the summary repeats the component orders. Forces are per
metre of out-of-plane depth, never N. The summary records `status: "solved"`, the
plane and material, `field_units`, `field_locations`, `field_shapes`, timings and
software versions, and diagnostics: the free-DOF residual norm (N/m), the summed
applied load, support reaction and their balance per component (N/m), strain
energy ½ uᵀKu (J/m), the largest displacement magnitude (m) and the largest stress
component (Pa).

Invalid input: CLI exit 2 and no output directory. Solve or I/O failure (a singular
system the rule did not foresee, nonfinite values, an occupied output): exit 1.
Success: exit 0. Saved fields can be viewed in ParaView through `simcase.export`
([Viewing in ParaView](overview.md#viewing-in-paraview)): point data
`displacement_m` and the three nodal N/m arrays as vectors with z = 0, cell data
`exx`, `eyy`, `gxy` and `sxx_pa`, `syy_pa`, `sxy_pa`; the export copies the saved
arrays and adds nothing to this contract.

## Validation

`tests/simcase/test_mechanics.py` holds the pre-registered gates; the values below
are from Linux, Python 3.12, NumPy 2.5.4, SciPy 1.18.1 (2026-11-02).

| Gate | Criterion | Measured |
|---|---|---|
| J1 | document run equals direct `solve_elasticity` on the same mesh, byte for byte (plane stress and strain, offset millimetre domain, body force and two tractions) | identical bytes for all six arrays |
| J2 | `refsol.elasticity_traction.uniaxial` and `shear` for `m`, `mm`, `um`, `nm`, both planes: relative error ≤ 1e-10 on displacement and stress | ≤ 4.6e-15 displacement, ≤ 1.3e-14 stress, ≤ 9.1e-15 strain |
| J3 | constant-body-force bar u = f/(λ+2μ)(Lx − x²/2, 0) with x, y fixed at x = 0 and y fixed on bottom and top: centroid displacement order ≥ 1.8 over subdivisions 8, 16, 32 | orders 1.95, 1.97 (plane stress) and 1.94, 1.97 (plane strain); element stress orders 0.95–0.98 |
| J4 | 32 invalid documents (hinges, one component only, corner conflict, missing or extra units, bad plane, ν = 0.5 and −1, tagged quantities, traction on a prescribed component, …) refused with exit 2 and no output; the rigid-body rule matches the solver's rank test on 12 constraint sets | all refused |
| J5 | CLI validate/run/save, fresh output refused with the existing summary untouched, partial-save cleanup leaves nothing, result copies and the document snapshot are immutable | passed |
| J6 | Studio `/api/validate` and `_require_studio_physics` refuse the type; the Studio Node checks stay green | passed, 247 Node tests |
| J7 | `tools/wheel_consumers/test_mechanics_wheel.py` (uniaxial plate CLI, hinge refusal, VTU export) run with `python -I` from a temporary directory, as `check_platform_install.py` does | passed |

The `refsol.elasticity_traction.polynomial_manufactured` field needs a position
dependent body force and traction, which this side-constant document cannot
express; J3 therefore uses the quadratic bar above, derived in the test from the
Navier equation, independent of the solver.

## Limits

One homogeneous isotropic rectangle, side-constant data, static small strain, a
single study. No regions or shapes, no normal/tangential traction, no distributed
or point loads, no thermal expansion or heat→mechanics coupling (the Python
[thermoelastic](../galerkin/thermoelastic_traction.md) workflows stay Python-only),
no dynamics, 3D or Studio form. A structurally valid model can still fail
numerically (near-incompressible plane strain, extreme aspect ratios); validation
does not certify accuracy.
