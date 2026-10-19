# Headless transient heat in a rectangle

[한국어](locales/ko/pages/thermal_transient2d.md)

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
below; it is not a new test result. A reported 41-case source subset does
not certify the public API, installed distributions, complete numerical
gates or platform acceptance. Inspect the exact combined candidate's command
exits, original logs and artifacts. Do not carry an engine-only pass forward
as a headless save/CLI pass.

## Strict input document

Use format `"openphysics": "0.2"` and explicit
`units.length`, `units.temperature: "K"`, `units.time: "s"`.
Length symbols such as `m`, `mm` and `um` apply to the four geometry bounds.
Fixed SI suffixes are not converted by the geometry length unit.

| Section / field | Accepted contract |
|---|---|
| geometry.domain | Only finite xmin/xmax/ymin/ymax; strictly positive, representable extents before and after SI conversion |
| materials | Empty object; no optical materials or region-specific coefficients |
| mesh.subdivisions | Exactly [nx,ny], positive nonboolean JSON integers; 4.0 is not an integer count |
| physics | Exactly one named thermal.transient2d entry; its name is an identifier |
| conductivity_w_mk | Required finite positive constant, W/(m K) |
| volumetric_heat_capacity_j_m3k | Required finite positive constant, J/(m³ K) |
| heat_source_w_m3 | Finite signed constant Q, W/m³; default 0 |
| initial_temperature_k | Required finite scalar K or the affine object below |
| dirichlet_temperature_k | Required side mapping; an empty object means complete insulation |
| study | Only type="transient" and time_s |
| study.time_s | At least two finite nonnegative real seconds; strictly increasing with finite positive differences; nonzero start allowed |
| results | Boolean save_fields and plots; defaults true and false; plots=true rejected |

Unknown keys, bool-as-number, nonfinite/complex values, spatially varying
sources, tagged quantities, shapes, sweeps and mixed physics are rejected.
The document loader applies defaults, but it does not supply missing units,
material constants, initial data or time samples.

A scalar initial temperature is uniform. The only structured initial field is:

```json
{
  "type": "affine",
  "origin_temperature_k": 300.0,
  "gradient_k_per_m": [5.0, 0.0]
}
```

It means `T0(x,y)=origin_temperature_k + gx*(x-xmin_m) + gy*(y-ymin_m)`.
The origin is the lower-left SI domain corner, not global (0,0).
The two gradients are K/m even when geometry uses mm or um. Initial values
are evaluated at actual mesh coordinates, not assumed node ordering.
Arbitrary nodal arrays, expressions and serialized Python callbacks are not
part of this document format.

### Boundary samples and initial agreement

Only `left`, `right`, `bottom`, `top` are accepted. Each selected side
covers its complete exterior and receives a spatially constant value.
Its value is a finite scalar K, repeated at all requested times, or
`{"values_k":[...]}` with exactly one value per `study.time_s`.
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

Finite negative initial, boundary and computed K are allowed by the linear
mathematical model. They do not certify physical material validity.
Consistent mass does not promise positivity or a discrete maximum principle.
Signed Q permits heating and cooling. The separate heat-to-mechanics
transfer still rejects negative K; this adapter does not change it.

## Complete minimal JSON

This is the supplied `transient_thermal_uniform` example:

```json
{
  "openphysics": "0.2",
  "name": "Insulated constant-source transient heat",
  "units": {"length": "m", "temperature": "K", "time": "s"},
  "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {
    "heat1": {
      "type": "thermal.transient2d",
      "conductivity_w_mk": 2.5,
      "volumetric_heat_capacity_j_m3k": 4.0,
      "initial_temperature_k": 300.0,
      "dirichlet_temperature_k": {},
      "heat_source_w_m3": 8.0
    }
  },
  "mesh": {"subdivisions": [4, 4]},
  "study": {"type": "transient", "time_s": [0.0, 0.1, 0.3]},
  "results": {"save_fields": true, "plots": false}
}
```

The independent mathematical expectation is `T=300+(8/4)*t` K,
zero flux and zero thermostat reaction. It is an analytic expectation,
not output observed by this page.

For time-dependent side data, an otherwise compatible model can use
`"left": {"values_k": [300.0, 300.2, 300.6]}`.
Every sample aligns with the corresponding requested time; selecting a
second adjacent side requires the same sequence at the shared corner.

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
exposes `doc`, `solution`, `timings`, `log` and the field arrays below.
`mesh_nodes_m`/`mesh_triangles` alias the solution geometry. The caller's original document is isolated by the run snapshot. If any value
in `result.doc` changes after run, including name or results options,
summary/save reject the result; set all options before run. Mapping order alone
does not change the document's meaning. Raw arrays and metadata are revalidated
before serialization. This is not hostile-code immutability or authentication.
EM-only `build_mesh` and `solve_point` reject this physics; use `run`.

## Raw histories and units

`result_format="thermal.transient2d-result-v1"` and
`field_layout="thermal2d-transient-p1-node-cell-v1"` are separate from input
format 0.2 and the steady result format. N is nodes, M triangles,
Nt requested times and D sorted unique Dirichlet nodes.

| Numeric NPZ key | Shape | Location / time axis | Unit |
|---|---|---|---|
| nodes_m | (N,2) | nodes / static | m |
| triangles | (M,3) | CCW integer connectivity / static | 1 |
| time_s | (Nt,) | requested_times / time_s | s |
| temperature_k | (Nt,N) | nodes / time_s | K |
| heat_flux_w_m2 | (Nt,M,2) | triangle_centroids / time_s | W/m² |
| source_load_w_per_m | (Nt,N) | nodes / time_s | W/m |
| reaction_w_per_m | (Nt-1,N) | nodes / time_s[1:] | W/m |
| residual_w_per_m | (Nt-1,N) | nodes / time_s[1:] | W/m |
| storage_rate_w_per_m | (Nt-1,N) | nodes / time_s[1:] | W/m |
| heat_content_j_per_m | (Nt,) | domain / time_s | J/m |
| quadratic_functional_jk_per_m | (Nt,) | domain / time_s | J K/m |
| dirichlet_node_ids | (D,) | dirichlet_nodes / static | 1 |
| dirichlet_temperatures_k | (Nt,D) | dirichlet_nodes / time_s | K |

The initial frame includes exact accepted T0, its flux and diagnostic f0.
There is no initial reaction, residual-step or storage rate; the Nt-1
arrays align with `rate_time_s=time_s[1:]`. Empty Dirichlet maps give
D=0 and an (Nt,0) prescribed-temperature history.

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

- `name`, `physics_name`, `physics_type`, result/layout identifiers,
  declared `units`, `mesh_length_unit="m"`, `mesh`, `study` and k/c/Q.
- `field_units`, `field_locations`, `field_time_axes`, `field_shapes`
  for every numeric array; declared geometry units do not change SI raw fields.
- `temperature_min_k`, `temperature_max_k`, `source_heat_w_per_m`,
  H and V at all Nt times.
- `storage_heat_w_per_m`, `outward_heat_w_per_m`,
  `heat_balance_defect_w_per_m` and `rate_time_s` on Nt-1 steps.
  Balance defect is sum(storage)-sum(source at step end)-sum(reaction).
- `dirichlet_nodes`, `save_fields`, `timings_s`, and text definitions
  `reaction_sign`, `balance_equation`, `heat_content_definition`,
  `quadratic_functional_definition`.

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
`result_format`, `field_layout`, `mesh_length_unit`, `metadata_json`.
The last contains the same encoded summary metadata. Read without pickle:

```python
import json
import numpy as np

with np.load(work / "api-results" / "fields.npz", allow_pickle=False) as fields:
    times = fields["time_s"]
    temperature = fields["temperature_k"]
    rates = fields["storage_rate_w_per_m"]
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

This interface does not add transient flux/Robin/radiation, variable or
region-dependent k/c, arbitrary mesh/nodal/expression serialization,
adaptive time steps, Crank–Nicolson, thermal Studio rendering, automatic
coupling or restart. It does not broaden the separate steady flux/Robin
or heat-to-mechanics document contracts.

The existing [engine numerical gates](https://github.com/fieldalgo/openphysics/blob/main/packages/galerkin/docs/transient_heat_validation.md)
remain unchanged; the cross-package link requires network access.
Record separately: schema validation, source adapter tests, independent
serializable analytic/unit/history/negative controls, isolated installed
consumers, real archive inclusion/bytes/links, Studio refusal/stale-state
checks, and native save regressions. An implementation, static count or
manifest entry is not an observed pass. Final public-API acceptance requires
the exact integrated source and installed/CI evidence; release additionally
requires green checks on the resulting main commit.
