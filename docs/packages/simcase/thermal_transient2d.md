# Headless transient heat in a rectangle

[한국어](../../locales/ko/pages/packages/simcase/thermal_transient2d.md)

**At a glance**

- **What it does:** `thermal.transient2d` connects the transient heat engine to the `simcase` document API, CLI and versioned JSON/NPZ histories: one fixed homogeneous rectangle, P1 triangles, consistent mass and backward Euler, explicit times in seconds, uniform or affine initial Kelvin, side-constant or sampled Dirichlet values, constant outward flux or convection sides (the steady boundary contract's keys, time-independent) and insulation elsewhere, per unit depth.
- **Limits:** no time-dependent flux or convection, no radiation, variable or region-dependent k/c, adaptive time steps, Crank–Nicolson, automatic coupling or restart. Initial values are not projected and finite negative Kelvin is not clamped.
- **Validation:** the engine's numerical gates are in the galerkin transient heat validation contract (linked below, unchanged); this page lists the document, adapter, installed and save checks separately. For a specific commit, see its CI run.

## Scope and evidence

`thermal.transient2d` connects the existing transient heat engine to the
`simcase` document API, CLI and versioned JSON/NPZ output. It solves
`c*dT/dt - div(k*grad T) = Q` in one fixed homogeneous 2D rectangle using
conforming P1 triangles, consistent mass and backward Euler. Geometry is
converted to metres; requested times are explicit seconds. The calculation
is per unit out-of-plane depth. Documents whose geometry has `background` or
`shapes` follow the [region document contract](thermal_regions2d.md) instead.

This page describes the headless interface. Generic optical Studio routes keep
their thermal guards; dedicated [steady Studio](thermal_studio.md) is separate.
The [transient Studio integration guide](thermal_transient_studio.md) distinguishes
its capability, time views and implementation/validation status.
Schema acceptance alone does not enable a browser route or renderer.

Implementation, source tests, installed consumers, exact CI and main
integration are different evidence stages. The code defines the contract
below; it is not a new test result. A source-test subset does not certify
the public API, installed distributions, complete numerical gates or
platform acceptance. For a specific commit, inspect its command exits,
original logs and artifacts. Do not carry an engine-only pass forward
as a headless save/CLI pass.

## Strict input document

Use format `"openphysics": "0.3"`: every value carries its unit
([document format](document_format.md)). The flat rectangle geometry declares
`length_unit` (`m`, `mm`, `um`, ...); the four bounds are numbers in that unit, converted
exactly to metres. `depth` is `null` (per metre of depth) or a length, which adds totals.

| Section / field | Accepted contract |
|---|---|
| geometry.domain | Only xmin/xmax/ymin/ymax; strictly positive extents |
| materials | Empty object; no optical materials or region-specific coefficients |
| mesh.subdivision_count | Exactly [nx,ny], positive JSON integers; 4.0 is not an integer count |
| physics | Exactly one named thermal.transient2d entry; its name is an identifier |
| thermal_conductivity | Required positive constant, such as `"2.5 W/(m K)"` |
| volumetric_heat_capacity | Required positive constant, such as `"3600000 J/(m^3 K)"` |
| heat_source_density | Signed constant Q, such as `"8 W/m^3"`; absent means no source |
| initial_temperature | Required: a temperature above 0 K, such as `"300 K"`, or the affine object below |
| prescribed_temperature | Required side mapping; an empty object means complete insulation |
| inward_heat_flux | Optional side-to-signed-constant mapping, W/m^2, positive into the body; its presence selects the boundary layout |
| convection | Optional side-to-object mapping with exactly heat_transfer_coefficient (h >= 0) and ambient_temperature (above 0 K); its presence selects the boundary layout |
| study | Only type="transient" and time |
| study.time | A tagged array such as `{"unit": "s", "values": [0, 0.1, 0.3]}`: at least two nonnegative times, strictly increasing; nonzero start allowed |
| results | Boolean save_fields and plots; defaults true and false; plots=true rejected |

Unknown keys (with "did you mean" and the new name of a format 0.2 key), bool-as-number,
non-finite values, spatially varying sources, shapes, sweeps and mixed physics are refused
with a coded diagnostic and its path. A format 0.2 rectangle document is refused by name
(`E-FORMAT`); region documents are read in format 0.2 until their commit of the units batch.
The reader echoes every default in `defaults_applied`; it does not supply missing material
constants, initial data or time samples.

A temperature initial is uniform. The only structured initial field is:

```json
{
  "type": "affine",
  "reference_temperature": "300 K",
  "temperature_gradient": {"unit": "K/m", "values": [5.0, 0.0]}
}
```

It means `T0(x,y)=reference_temperature + gx*(x-xmin_m) + gy*(y-ymin_m)`.
The origin is the lower-left SI domain corner, not global (0,0). The gradient is read in
K/m whatever the geometry's length_unit. Initial values are evaluated at actual mesh
coordinates, not assumed node ordering. Arbitrary nodal arrays, expressions and serialized
Python callbacks are not part of this document format.

### Boundary samples and initial agreement

Only `left`, `right`, `bottom`, `top` are accepted. Each selected side
covers its complete exterior and receives a spatially constant value.
Its value is a temperature such as `"300 K"`, repeated at all requested times, or a tagged
array `{"unit": "K", "values": [...]}` with exactly one value per study time.
These are requested-time samples: no interpolation or extrapolation.
Unspecified sides are insulated; complete insulation needs no artificial
Dirichlet anchor because the mass/time term makes the transient system
well posed.

Adjacent prescribed sides share corner nodes. Their complete sampled
sequences must agree exactly; equal selections are deduplicated independently
of mapping order. Every selected node's initial temperature and first
boundary sample must satisfy:

```text
abs(initial_i - d_i(t0)) <= 32*eps*max(1 K, abs(initial_i), abs(d_i(t0)))
```

Accepted initial values are preserved exactly: no projection, overwrite or
clamp. A time-independent side value must also agree at t0. An affine
initial field that varies along a prescribed side cannot be represented by
one side-constant boundary unless the agreement condition holds.

Since the units batch every absolute input temperature (initial, prescribed, ambient) must
be above 0 K (`E-DOMAIN`); before it, finite negative kelvin inputs were accepted. A computed
temperature may still go below 0 K: the linear model does not clamp it. Consistent mass does
not promise positivity or a discrete maximum principle. Signed Q permits heating and
cooling.

### Inward heat flux and convection sides

`inward_heat_flux` and `convection` are the keys of the
[steady boundary contract](thermal_steady_boundary2d.md), read by the same
code: `{side: "-2 W/m^2"}` (positive heats the body) and
`{side: {"heat_transfer_coefficient": "500 W/(m^2 K)", "ambient_temperature": "300 K"}}`.
Only `left`, `right`, `bottom`, `top` are accepted, each condition covers its complete
exterior side, one flux plus one convection on the same side add, and a side that also
appears in `prescribed_temperature` is refused (`natural condition overlaps a fully
prescribed-temperature side`). The engine takes the outward flux g = `0.0 - inward_heat_flux`
(an exact sign flip) and the condition is `q.n = g + h*(T - T_a)` as in
`galerkin.transient_heat.solve_transient_heat`.

The values are constants: no tagged-array samples, callbacks or radiation. Unlike the steady
document, no anchor is needed: the mass/time term keeps the system well posed, so a document
with an empty prescribed mapping and h=0 is a valid insulated slab. The presence of either
key, even as an empty mapping, selects the boundary result pair
`thermal.transient2d-result-v4` / `thermal2d-transient-p1-node-cell-boundary-v2` described
below; a document without both keys saves `thermal.transient2d-result-v3` /
`thermal2d-transient-p1-node-cell-v2`.

The transient Studio route shows the plain pair only and refuses such documents
before validation (`unsupported_physics`, no job); run them headless with the
API or CLI. Region documents do not take these keys.

## Complete minimal JSON

This is the supplied `transient_thermal_uniform` example:

```json
{
  "openphysics": "0.3",
  "name": "Insulated constant-source transient heat",
  "geometry": {"length_unit": "m", "depth": null,
               "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {
    "heat1": {
      "type": "thermal.transient2d",
      "thermal_conductivity": "2.5 W/(m K)",
      "volumetric_heat_capacity": {"value": "4 J/(m^3 K)",
                                   "accept": {"W-MAGNITUDE": "manufactured solution"}},
      "initial_temperature": "300 K",
      "prescribed_temperature": {},
      "heat_source_density": "8 W/m^3"
    }
  },
  "mesh": {"subdivision_count": [4, 4]},
  "study": {"type": "transient", "time": {"unit": "s", "values": [0.0, 0.1, 0.3]}},
  "results": {"save_fields": true, "plots": false}
}
```

The heat capacity of 4 J/(m^3 K) is far below any material's; the `accept` annotation keeps the
`W-MAGNITUDE` warning, acknowledged, in every output instead of hiding it.

The independent mathematical expectation is `T=300+(8/4)*t` K,
zero flux and zero thermostat reaction. It is an analytic expectation,
not output observed by this page.

For time-dependent side data, an otherwise compatible model can use
`"left": {"unit": "K", "values": [300.0, 300.2, 300.6]}`.
Every sample aligns with the corresponding requested time; selecting a
second adjacent side requires the same sequence at the shared corner.

The shipped `transient_thermal_boundary` example (`python -m simcase example
transient_thermal_boundary`) is a 0.05 m x 0.01 m slab at 400 K, insulated
except for `"convection": {"right": {"heat_transfer_coefficient": "500 W/(m^2 K)", "ambient_temperature": "300 K"}}`
(k = 50 W/(m K), c = 3.6e6 J/(m^3 K), Bi = 0.5), saved at 10, 20, 40 and 80 s.
Its field is one-dimensional in x and comparable with the convective slab
series of `refsol.transient_heat_robin`; the
[gates](#limitations-and-validation-stages) below record the measured agreement.

## Python API and portable CLI reproduction

After installing the packages, run this Python snippet from the repository
root. It creates its own temporary parent, writes UTF-8 JSON and uses fresh,
distinct output paths. It demonstrates both public API and CLI; it is not a
record that these commands ran on any OS.

```python
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

from simcase import Document, TransientThermalRunResult, examples, run

work = Path(tempfile.mkdtemp(prefix="openphysics-transient-"))
model = copy.deepcopy(examples.TRANSIENT_THERMAL_UNIFORM)
model_path = work / "model.json"
model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
doc = Document.load(model_path)
result = run(doc, verbose=False)
assert isinstance(result, TransientThermalRunResult)
summary = result.summary()
result.save(work / "api-results")
subprocess.run([sys.executable, "-m", "simcase", "validate", str(model_path)],
               check=True)
subprocess.run([sys.executable, "-m", "simcase", "run", str(model_path),
                "-q", "-o", str(work / "cli-results")], check=True)
print(work)
```

The equivalent CLI entry points are
`python -m simcase example transient_thermal_uniform`,
`python -m simcase validate model.json` and
`python -m simcase run model.json -q -o fresh_results`.
Without `-o`, output defaults to `<model-stem>_results` beside the model.
Use a fresh path even when fields are disabled.
Handled document/JSON/missing-file load errors return CLI exit2; handled
run/save/fresh-output errors return exit1; success returns exit0.
An exit code is actual evidence only when observed from the exact run.

`run(Document, verbose=False)` validates and copies the document before
constructing an SI rectangle, sampling serializable initial/boundary data and
calling the existing transient engine once. `TransientThermalRunResult`
exposes `doc`, `solution` (the engine's arrays under their galerkin names), `timings`, `log`
and the field arrays below under their registry names. The caller's original document is isolated by the run snapshot. If any value
in `result.doc` changes after run, including name or results options,
summary/save reject the result; set all options before run. Mapping order alone
does not change the document's meaning. Raw arrays and metadata are revalidated
before serialization. This is not hostile-code immutability or authentication.
EM-only `build_mesh` and `solve_point` reject this physics; use `run`.

## Raw histories and units

`result_format="thermal.transient2d-result-v3"` and
`field_layout="thermal2d-transient-p1-node-cell-v2"` (the format 0.2 identifiers
`-result-v1`/`-cell-v1` are retired). N is nodes, M triangles, Nt requested times and D
sorted unique prescribed nodes.

| Numeric NPZ key | Shape | Location / time axis | Unit |
|---|---|---|---|
| node_coordinates | (N,2) | nodes / static | m |
| triangles | (M,3) | CCW integer connectivity / static | (structural) |
| time | (Nt,) | requested_times / time | s |
| temperature | (Nt,N) | nodes / time | K |
| heat_flux | (Nt,M,2) | triangle_centroids / time | W/m^2 |
| generated_heat_rate_per_depth | (Nt,N) | nodes / time | W/m |
| reaction_heat_rate_per_depth | (Nt-1,N) | nodes / time[1:] | W/m |
| residual_heat_rate_per_depth | (Nt-1,N) | nodes / time[1:] | W/m |
| heat_storage_rate_per_depth | (Nt-1,N) | nodes / time[1:] | W/m |
| stored_heat_per_depth | (Nt,) | domain / time | J/m |
| thermal_energy_functional_per_depth | (Nt,) | domain / time | J K/m |
| prescribed_node_ids | (D,) | prescribed_nodes / static | (structural) |
| prescribed_temperature | (Nt,D) | prescribed_nodes / time | K |

The initial frame includes exact accepted T0, its flux and diagnostic f0.
There is no initial reaction, residual-step or storage rate; the Nt-1
arrays have the time axis `time[1:]` (the former `rate_time_s` is gone). An empty prescribed
mapping gives D=0 and an (Nt,0) prescribed-temperature history.

With `inward_heat_flux` or `convection` the identifiers are
`result_format="thermal.transient2d-result-v4"` and
`field_layout="thermal2d-transient-p1-node-cell-boundary-v2"`, and the NPZ
holds the thirteen arrays above plus two per-step histories:

| Numeric NPZ key | Shape | Location / time axis | Unit |
|---|---|---|---|
| outward_prescribed_heat_rate_per_depth | (Nt-1,N) | nodes / time[1:] | W/m |
| outward_convective_heat_rate_per_depth | (Nt-1,N) | nodes / time[1:] | W/m |

They are the engine's G (the integrated prescribed outward flux, the same at
every step) and C_n = H*T_n - B (the convective outward rate at the step end),
and the balance becomes `storage_n = source_n + reaction_n - G - C_n`; the
summary's `outward_heat_rate_per_depth` is then `sum(G + C_n - reaction_n)` and its
`heat_rate_imbalance_per_depth` the defect of that equation. Prescribed-temperature
reactions keep their sign.

Positive fixed-node reaction injects heat; free-node reaction is zero.
Outward heat is the Dirichlet thermostat contribution, not a separately
reconstructed boundary-flux integral:

```text
storage_n = M*(T_n-T_n-1)/dt_n
residual_n = storage_n + K*T_n - source_load_n
reaction_n = residual_n on fixed DOFs; zero on free DOFs
(H_n-H_n-1)/dt_n = sum(source_load_n) + sum(reaction_n)
outward_D,n = -sum(reaction_n)
H_n = 1^T*M*T_n                  [J/m]
V_n = .5*T_n^T*M*T_n             [J K/m; not stored heat]
```

Rates and H are per out-of-plane depth: multiply by physical thickness in m
to obtain W and J. Do not multiply temperature or flux by thickness.
H uses a chosen zero at 0K for constant-capacity sensible content, not a
universal absolute enthalpy model. Do not assert general H/V monotonicity
or equate direct element-flux integration with the finite-mesh weak reaction.

## Summary and saved files

`summary()` returns JSON-finite metadata including:

- `name`, `physics_name`, `physics_type`, result/layout identifiers, the `diagnostics` list,
  `defaults_applied`, `resolved_inputs`, the `extent` line, `mesh`, `study` (its `time` as a
  tagged array) and the inputs as `{"value", "unit"}` objects.
- `field_units` (none for the structural arrays), `field_locations`, `field_time_axes` (none
  for the static arrays), `field_shapes` and `field_components`.
- `minimum_temperature`, `maximum_temperature`, `generated_heat_rate_per_depth`,
  `stored_heat_per_depth` and `thermal_energy_functional_per_depth` at all Nt times, as
  tagged arrays `{"unit", "values"}`.
- `heat_storage_rate_per_depth`, `outward_heat_rate_per_depth` and
  `heat_rate_imbalance_per_depth` on Nt-1 steps. The imbalance is
  sum(storage)-sum(source at step end)-sum(reaction).
- `prescribed_nodes`, `save_fields`, `timing.wall_time`, and text definitions
  `reaction_sign`, `balance_equation`, `heat_content_definition`,
  `quadratic_functional_definition`.
- With the boundary layout also `inward_heat_flux`, `convection`,
  `outward_prescribed_heat_rate_per_depth`, `outward_convective_heat_rate_per_depth` and
  `outward_reaction_heat_rate_per_depth` on Nt-1 steps, `outward_sign` and
  `natural_condition`; `outward_heat_rate_per_depth`, `heat_rate_imbalance_per_depth`,
  `reaction_sign` and `balance_equation` then describe the three-term total.
- With a `depth`, each `*_per_depth` value is followed by its total for that depth.

Timings distinguish adapter meshing/preparation and solver call; they are not
a dedicated-host performance baseline or portable timing guarantee.
Summary creation checks finite arrays, dimensions/indices/CCW geometry,
time validity and document/material/time consistency. It is validation,
not source authentication or an independent physical proof.

Saving writes UTF-8 `model.json`, `log.txt`, optional `fields.npz`,
then `summary.json` last. A temporary `.incomplete` marker remains on
preserved incomplete output and is removed on successful completion.
With `save_fields=false`, JSON/log/summary still exist but NPZ does not;
the solve still retains full histories and summary/save still copy and
validate arrays. Disabling fields is not streaming or a memory bound.
No plot is generated.

NPZ includes the numeric fields plus non-object scalar strings
`result_format`, `field_layout`, `metadata_json`.
The last contains the same encoded summary metadata. Read without pickle:

```python
import json
import numpy as np

with np.load(work / "api-results" / "fields.npz", allow_pickle=False) as fields:
    times = fields["time"]
    temperature = fields["temperature"]
    rates = fields["heat_storage_rate_per_depth"]
    metadata = json.loads(str(fields["metadata_json"]))
    assert temperature.shape[0] == len(times)
    assert rates.shape[0] == len(times) - 1
```

The saved model and histories support inspection; there is no loader that
restarts or resumes the solver from this output.

## Output ownership, failures and memory

Output must not already exist: files, empty/nonempty directories and dangling
symlinks are refused without overwriting them. CLI checks freshness before
solving, and save claims its own directory using the shared steady save
ownership implementation. The caller must exclusively control the output and
temporary sibling pin paths until save/cleanup returns. Observed foreign
files or directory/file replacements are preserved rather than deleted as
owned output. Ordinary failures clean only known-owned data. A completion
summary is not written after an earlier failure; log or incomplete files alone
are not success evidence.

This is not atomic protection against a hostile external writer swapping
paths between an ownership check and use, nor crash rollback. Windows saving
requires same-volume hard-link support and the shared native resource-lifetime
contract; unsupported filesystems fail explicitly. Native rename/replace/
cleanup success must be measured on the actual platform. Linux passes,
classifiers or universal wheels do not certify Windows/macOS acceptance.

The adapter does not project initial data, clamp temperatures, interpolate
boundary samples, downsample history or change the solver gates. Engine
step errors retain a chained cause with time context under a physics-named
adapter error; no partial result is returned on failure. Post-run document value changes are rejected, and arrays/metadata are
revalidated before serializing; concurrent caller mutation is unsupported.

Full histories cost O(Nt*(N+M)) memory plus sparse factors and temporaries.
Save and summary create additional validation copies and compression buffers.
Large requests can fail allocation; no hidden restart/streaming guarantee
exists.

## Limitations and validation stages

This interface does not add time-dependent flux or convection, radiation,
variable or region-dependent k/c, arbitrary mesh/nodal/expression
serialization, adaptive time steps, Crank–Nicolson, thermal Studio rendering
of the boundary layout, automatic coupling or restart. It does not broaden the
heat-to-mechanics document contract.

Pre-registered gates for the boundary keys (`tests/simcase/test_transient_boundary.py`):
S1 a document run equals the direct `solve_transient_heat` call bit for bit;
S2 documents without boundary keys keep the plain identifiers, arrays, summary keys and
values; S3 the convective slab document on 40×2 cells with dt = 1 s to 80 s
(Fo = 0.44, Bi = 0.5) matches the `refsol.transient_heat_robin` series at 80 s
with a relative L2 error on the 100 K rise scale <= 2e-3 (2.0e-4 measured on
2026-11-02, Linux; the shipped [20,2] example with four steps gives 5.6e-3 and
is an illustration, not a gate; the format 0.3 rewrite of the test reproduces 1.978e-4 on
2026-11-10, Linux); S4 invalid keys are refused with the steady contract's codes and paths and
no output; S5 the boundary layout exports through
meshio with its two arrays per step while the earlier layouts are unchanged.

The existing [engine numerical gates](../galerkin/transient_heat_validation.md)
remain unchanged.
Record separately: schema validation, source adapter tests, independent
serializable analytic/unit/history/negative controls, isolated installed
consumers, exact sdist/wheel contents and bytes, Studio refusal/stale-state
checks, and native save regressions. An implementation or static count is not
an observed pass. Final public-API acceptance requires
the exact integrated source and installed/CI evidence; release additionally
requires green checks on the resulting main commit.
