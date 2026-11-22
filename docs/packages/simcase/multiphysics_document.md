# Multiphysics documents: several physics on one geometry, and couplings

**English** | [한국어](../../locales/ko/pages/packages/simcase/multiphysics_document.md)

[Documentation home](../../README.md) · [simcase overview](overview.md) ·
[Document format 0.3](document_format.md) · [Physics providers](providers.md)

A *multiphysics document* holds several physics entries on one geometry, the couplings
between them and the accepted iteration settings. One document runs them all: `simcase
validate` checks every entry and every coupling before anything runs, and `simcase run`
solves the physics in the order the couplings give and writes one result folder per physics.
The implementation is [`simcase.multiphysics`](../../../packages/simcase/src/simcase/multiphysics.py).

The first coupling in this release carries a steady temperature into the optical modes:
`thermal.steady2d` → n(T) → `em.modes2d`.

```json
{
  "openphysics": "0.3/multiphysics.1",
  "name": "Heated slab waveguide",
  "geometry": {"version": 1, "components": {"xs": {"dimension": "2d", "length_unit": "um", "depth": null,
    "domain": {"xmin": -0.5, "xmax": 0.5, "ymin": -1.2, "ymax": 1.2},
    "background": {"material": "clad"},
    "features": [{"name": "core", "type": "rect", "x": -0.5, "y": 0.0, "w": 1.0, "h": 0.22, "material": "core"}]}}},
  "materials": {
    "core": {"refractive_index": 3.48, "thermal_conductivity": "148 W/(m K)",
             "thermo_optic_coefficient": "1.8e-4 1/K", "reference_temperature": "300 K"},
    "clad": {"refractive_index": 1.444, "thermal_conductivity": "1.38 W/(m K)",
             "thermo_optic_coefficient": "1.0e-5 1/K", "reference_temperature": "300 K"}},
  "physics": {
    "heat1": {"type": "thermal.steady2d", "prescribed_temperature": {"bottom": "300 K", "top": "330 K"}},
    "modes1": {"type": "em.modes2d", "formulation": "scalar", "vacuum_wavelength": "1.55 um", "mode_count": 1,
               "boundary": {"left": "pmc", "right": "pmc", "top": "pec", "bottom": "pec"}}},
  "couplings": {
    "heat_to_optics": {"from": "heat1.temperature", "to": "modes1.temperature", "transfer": "same_mesh"}},
  "mesh": {"element_size": "0.02 um"}
}
```

The shipped example is [`multiphysics_heated_slab.json`](../../../examples/simcase/multiphysics_heated_slab.json):

```sh
python -m simcase validate examples/simcase/multiphysics_heated_slab.json
python -m simcase run examples/simcase/multiphysics_heated_slab.json -o heated_slab_results
```

## The envelope

A document declares the multiphysics envelope, `"openphysics": "0.3/multiphysics.1"`, when
it has `couplings` or physics entries of more than one kind. The envelope sits on top of
format 0.3: every value follows the [format 0.3 rules](document_format.md) (units with every
dimensioned value, registry key names, no `units` block). A reader that does not know the
envelope refuses the document at its format check (`E-FORMAT` at `openphysics`), so a
coupling is never dropped silently.

- A `"0.3"` document with `couplings`, or with entries of two kinds, is `E-FORMAT` at
  `openphysics`, naming the envelope to write.
- An envelope document with entries of one kind and no couplings is `E-FORMAT` too: it is
  written in the single-physics form, `"0.3"`. Every document has one spelling.
- Single-physics documents are unchanged: they stay `"0.3"`, with the same reader, slot
  table, validation and results.

The envelope names its base format and its own version. A later change of the multiphysics
envelope would be `"0.3/multiphysics.2"`, and the envelope on a later base format
`"0.4/multiphysics.1"`.

Top-level keys: `openphysics name display_units geometry materials physics mesh study
results couplings`. The geometry is a version 1 block ([geometry documents](geometry_document.md));
the physics share its regions and its one mesh. `results` takes `save_fields` (default true)
and `plots` (default false); `study.type` is `"single"` (the default) or `"sweep"`.

## Each physics entry is validated by its own kind

Each `physics.<name>` entry is read by the kind that claims its type, exactly as that kind
reads a single-physics document. The reader builds the entry's *view*: a `"0.3"` document with
the shared `geometry`, `mesh` and `results`, that one entry, `study` (a sweep only in the
view of the physics it varies), and the material records cut down to what that kind reads. A
property another physics reads is left out of a view (it is that physics' to check); a
property no physics reads stays, so its value is checked and reported unused
(`I-UNUSED-PROPERTY`). Diagnostics keep their document paths, and a diagnostic two views give
for a shared block is reported once.

Physics names are identifiers (letters, digits and `_`). In this release a multiphysics
document takes the kinds with a coupling hook, `thermal.steady2d` and `em.modes2d`; another
type is `E-CONTRACT` at `physics.<name>.type` ("is not coupled in this release"). The
compound kinds (`joule.temperature2d`, `mechanics.thermoelastic2d`) stay single-physics
documents with their own loops.

## Couplings

```json
"couplings": {"heat_to_optics": {"from": "heat1.temperature", "to": "modes1.temperature", "transfer": "same_mesh"}}
```

- `from` is `<physics name>.<output port>` and `to` is `<physics name>.<input port>`, ports
  of the kinds' [manifests](providers.md#the-built-in-kinds-and-their-ports). One coupling
  carries one quantity in one direction; a two-way exchange is two couplings.
- The two ports have the same `quantity` and the same `unit` string. A coupling converts no
  unit (`E-COUPLING-PAIR` otherwise).
- A node output may feed a node or an element input; an element output feeds an element
  input. For a node field into an element input, the receiving kind takes the mean of the
  three node values of each triangle (the P1 mean).
- `transfer` is `"same_mesh"`: the identity on one mesh (`galerkin.coupling.transfer`), with
  exact `MeshSignature` equality of nodes and triangles and the same region on every
  triangle. Projection between different meshes is a later, separately approved transfer.
- An input with `combine: "single"` takes at most one coupling; `"sum"` adds the fields of
  every coupling into it.
- A physics does not couple to itself.

### Validation before running

`simcase validate` reports each of these before anything runs, naming the coupling or the
physics and what to change:

| Problem | Code and path |
|---|---|
| a physics or port name the document does not have | `E-CONTRACT` at `couplings.<name>.from` / `.to`, listing the physics or ports there are |
| an input named in `from`, an output in `to` | `E-CONTRACT` at `couplings.<name>.from` / `.to` |
| an output the kind saves but does not couple in this release (`thermal.steady2d` couples `temperature`, not `heat_flux`) | `E-CONTRACT` at `couplings.<name>.from` |
| a quantity, unit or location mismatch | `E-COUPLING-PAIR` at `couplings.<name>` |
| a second coupling into a `single` input | `E-CONTRACT` at `couplings.<name>.to`, naming the coupling already there |
| a self-coupling | `E-CONTRACT` at `couplings.<name>` |
| a transfer other than `same_mesh` | `E-CONTRACT` at `couplings.<name>.transfer` |
| a `same_mesh` coupling whose physics would build different meshes | `E-CONTRACT` at `couplings.<name>.transfer`, naming the `mesh` key one physics does not read |
| a cycle without an accepted loop | `E-COUPLING-CYCLE` at `study.loops`, with the proposed loop entry |
| an optical material without a thermo-optic model when its `temperature` input is coupled | `E-PROPERTY-MISSING` at `materials.<name>` (or `physics.<name>` for a library material) |

The two meshes are compared once more when they exist: `simcase run` refuses a coupling
whose meshes differ (`couplings.<name>: same_mesh needs one mesh, …`) and never interpolates.
Today `thermal.steady2d` and `em.modes2d` build the identical mesh from the same geometry
and `mesh` block, except that `mesh.grading` (the radial grading of `em.modes2d`) is not read
by the heat kind; a `same_mesh` coupling between them refuses `mesh.grading`, and
`mesh.controls`, which both read, grades the mesh instead.

## Heat → n(T) → optical modes

The `em.modes2d` input `temperature` (K, element, `single`) takes the node temperature of a
`thermal.steady2d` entry (its output `temperature`, K, node). For each triangle the modes kind
takes the P1 mean T of its three node temperatures and uses

n = n₀(λ) + (dn/dT) (T − T_ref)

where n₀(λ) is the material's refractive index (a constant, n + i k, or the Sellmeier model).
Only the real part changes; the extinction coefficient k is unchanged. A triangle whose index
change is exactly zero keeps its material's permittivity bit for bit.

Every optical material of a coupled entry needs a thermo-optic model:

- a local record gives both `thermo_optic_coefficient` (dn/dT, for example `"1.8e-4 1/K"`)
  and `reference_temperature` (T_ref, for example `"300 K"`); one without the other is
  `E-KEY-MISSING`;
- `physmat:Si` and `physmat:SiO2` carry the model: dn/dT is physmat's `thermo_optic_dn_dT`
  (1.8e-4 and 1.0e-5 1/K) and T_ref is 300 K. Another library material has none.

The two keys are material keys of multiphysics documents only: in a single-physics document
they stay unknown keys (`E-KEY-UNKNOWN`). Without a coupled temperature input they are checked
and reported unused.

Limitations of this coupling:

- A heat → modes document may use `physmat:Si` and `physmat:SiO2`: steady heat reads their
  constant 300 K handbook `thermal_conductivity` (148 and 1.38 W/(m K);
  [heat regions](thermal_regions2d.md)), and the modes kind their thermo-optic model. The
  conductivity does not follow the temperature; where the rise is large, write local records.
- physmat's Sellmeier data are given at 293.15 K (SiO2) and 299.15 K (Si); the thermo-optic
  shift is taken from 300 K, and n₀ is the Sellmeier value at the run's wavelength.
- The thermo-optic model is linear in T; there is no thermal expansion or stress-optic effect.

## Solve order and loops

The solve order is derived, not stored. The runner orders the physics by the coupling graph:
its strongly connected groups, then topological order; among groups that are ready, the one
whose first physics comes first in the `physics` block goes first, and the members of a group
keep that order. A group of two or more physics is a cycle.

A cycle runs only with an accepted loop: an entry of `study.loops` for exactly that group.

```json
"study": {"type": "single", "loops": [
  {"physics": ["a", "b"], "method": "fixed_point",
   "tolerance": {"port": "a.y", "norm": "max_abs", "value": "1e-6 K"},
   "max_iterations": 30, "relaxation": 0.5}]}
```

A cycle without one is `E-COUPLING-CYCLE` at `study.loops`; its message names the group and
its couplings and gives the entry above as a suggestion (the defaults: `fixed_point`, the
first member's first output in the cycle with `max_abs` and `1e-6` in that port's unit, 30
iterations, relaxation 0.5). A loop entry is checked: its physics are exactly one cycle, one
entry per cycle, `method` `"fixed_point"`, a tolerance port that is an output of the loop with
a positive value in that port's unit, `norm` `"max_abs"`, `max_iterations` a whole number of at
least 2 and `relaxation` in (0, 1]. The tolerance port is the source of a coupling inside the
loop, and its value is a change: a temperature tolerance is a temperature difference (`"1e-6 K"`
or mK; `degC` is refused as ambiguous).

An accepted loop runs as an under-relaxed fixed point, x ← (1 − w) x + w G(x), on the fields of
the couplings inside the cycle. Each iteration solves the members in their order; the field of
a coupling inside the loop enters the next solve relaxed by w (the first iteration takes it as
sent). The residual of an iteration is the fixed-point residual |G(x) − x| of the field the
tolerance port sends: the largest difference (`max_abs`, in that port's unit) between what the
port sends now and the relaxed field the loop carried into this iteration. It does not shrink
with a small relaxation, so a small w cannot end the loop early. The first residual is
measured at the second iteration. The loop has converged when the residual is at most the
tolerance; the result then records each residual. A loop that reaches
`max_iterations` fails with `E-LOOP-DIVERGED` at `study.loops` and its residual history; it
never returns the last iterate as a result, and nothing is written.

No pair of built-in kinds forms a cycle yet: the loop is tested with test-local kinds only.

## Results: `multiphysics-run-v1`

```
<out>/
  summary.json    result "multiphysics-run-v1", format, name, diagnostics, defaults_applied,
                  solve_order, physics, couplings, loops, timing
  model.json      the document as read
  log.txt
  heat1/          the heat result, with its own identifier (summary.json, fields.npz, log.txt;
                  results.png when results.plots is true and the kind plots)
  modes1/         the modes result, with its own identifier
```

- `solve_order` is the order used, a list of groups (`[["heat1"], ["modes1"]]`).
- `physics.<name>` gives the type, the result identifier of that physics' own result and its
  folder. Each folder holds that kind's usual result files, computed with the coupled inputs;
  a single-physics result keeps its identifier. There is no `model.json` per physics: the
  view a physics was solved as is not a document the user wrote, and without its coupled
  inputs it would not give that result.
- `couplings.<name>` records `from`, `to`, `quantity`, `unit`, `transfer`, the field
  `location`, `mesh_signature` (`"match"`) and `max_abs_difference` (the largest change the
  transfer made, `{"value": 0.0, "unit": "K"}` for `same_mesh`; a nonzero value fails the run).
  `conservation_residual` is |Σ sent − Σ received| / |Σ sent| for a power quantity (W, W/m,
  W/m², W/m³: an element field integrated as value × area, a node field as its lumped P1
  integral); it is null for any other quantity, temperature included.
- `loops` lists each loop that ran: `physics`, `method`, `tolerance`, `relaxation`,
  `iterations`, `converged` and `residuals` (one `{"value", "unit"}` per iteration after the
  first). It is empty for a document without cycles.
- The modes folder's `fields.npz` adds the coupled input: `temperature` (K, one value per
  triangle, the P1 mean used) and `refractive_index` (one row per study point, one value per
  triangle, n + i k under exp(−iωt) when lossy).

## Python

```python
from simcase import Document, multiphysics, run

doc = Document.load("examples/simcase/multiphysics_heated_slab.json")
doc.views["modes1"]                       # the single-physics view of one entry
result = run(doc, verbose=False)          # a multiphysics.MultiphysicsRunResult
result.solve_order                        # [['heat1'], ['modes1']]
result.results["modes1"].effective_index  # the modes result, computed with the coupled temperature
result.couplings["heat_to_optics"]        # the coupling record
result.save("heated_slab_results")
```

`multiphysics.run(doc, on_event=callback)` calls `callback` with one JSON-data dict per step,
in order, for a progress display: `physics_started` and `physics_finished` (with `seconds`)
for each physics, and for an accepted loop `loop_started`, one `loop_iteration` per measured
residual (`iteration`, `residual`, `unit`) and `loop_finished` (`iterations`).

## The coupling hook is internal

A kind takes part in a multiphysics document through its coupling hook
(`PhysicsKind.coupling`, a `multiphysics.CouplingHook`). The hook is internal to simcase in
this release: it is not part of the [provider protocol](providers.md), so the kinds of other
providers cannot take part in couplings yet. Their manifests may already declare input ports.

## Validation

Pre-registered before implementation, on the geometry of the example (a 0.22 µm core of n₀
3.48 and dn/dT 1.8e-4 1/K across the whole 1.0 µm width of a 2.4 µm window of cladding n₀
1.444 and dn/dT 1.0e-5 1/K, T_ref 300 K, λ 1.55 µm, scalar formulation, PMC left and right,
PEC top and bottom). With PMC sides the mode does not depend on x, so the 2D problem is the 1D
TE slab between PEC walls. The tests are
[`tests/simcase/test_multiphysics_heat_optics.py`](../../../tests/simcase/test_multiphysics_heat_optics.py)
and [`tests/simcase/test_multiphysics_document.py`](../../../tests/simcase/test_multiphysics_document.py).

| Check | Independent reference | Threshold |
|---|---|---|
| V1 uniform ΔT = 10 K (310 K top and bottom, insulated sides) | exact PEC-bounded slab dispersion kd = atan(γ coth(γ t_s)/κ) + atan(γ coth(γ t_c)/κ): n_eff 2.851738985 → 2.853529512, shift 1.79053e-3 | h = 0.04 µm: n_eff 3e-3, shift 5e-3 relative; h = 0.02 µm: 1e-3 and 2e-3 |
| V1 consistency (scalar and vector) | not independent: a run with the raised indices written in | \|Δn_eff\| ≤ 1e-12 |
| V2a 300 K / 400 K, insulated sides | closed-form series-layer conduction (piecewise linear in y) | every node within 1e-8 K (h = 0.02 µm) |
| V2b coupled n_eff, h = 0.04, 0.02, 0.01 µm | 1D P1 FEM of the TE equation with the exact n(y), 48 000 elements: 2.86159710 | observed order in [1.8, 2.2]; the finest error within 0.5–2 × the Richardson estimate; the extrapolation within 1e-5 relative; the finest mesh within 2.5e-4 |
| V3a dn/dT = 0 with the V2a heat (scalar and vector) | the uncoupled single-physics document | bit for bit: n_eff, fields, mesh arrays, postprocessing, summary values |
| V3b 300 K on every side, no source | the uncoupled single-physics document | bit for bit, as V3a |
| V4 single physics unchanged | every shipped example before and after | validate output, fields.npz arrays, summary and metadata without timing, model.json, results.png identical |

## Not in this release

- Running a multiphysics sweep: `study.type: "sweep"` and its parameter path (a value of one
  physics entry, `physics.<name>.…`) are validated, and `simcase run` refuses the sweep with
  `E-CONTRACT` at `study.type` ("a multiphysics sweep is validated but not run in this
  release").
- Transfers other than `same_mesh`.
- Other providers' kinds in couplings (the hook is internal).
