# Steady outward-flux and convection documents

[한국어](locales/ko/pages/thermal_steady_boundary2d.md)

## Implementation and validation status

This page describes the boundary-extension candidate for `thermal.steady2d`.
Schema candidate `4bd15626fe37c306eb6265f1db1b308c6b580460` implements
`Document.from_dict`, JSON loading, validation and document summaries.
Runtime candidate `11f2d2ba893a7c103effc9025f75fea615a636f6` implements
`run(Document)`, `ThermalRunResult`, CLI dispatch and JSON/NPZ saving with
the existing thermal engine. These are submitted implementations, not a claim
that this feature is already on main. Use their combined exact checkout.
The [legacy guide](thermal_steady2d.md) retains the original v1 contract.

P2 numerical and installed acceptance are not complete. Independent and platform
tests are submitted separately; their existence is not a passing result.
Examples below are reproduction procedures and analytical expectations, not
measurements made for this document. Check the exact combined candidate's CI,
artifacts and platform results before treating it as accepted.

## Inputs and supported scope

Use format `"openphysics": "0.2"`, one `thermal.steady2d` physics,
a homogeneous rectangle, P1 triangles, constant isotropic
`conductivity_w_mk > 0` in W/(m K), and signed constant
`heat_source_w_m3` in W/m³ (default zero). Declare length units and
`temperature: "K"`; geometry is converted to metres, while SI suffixes
are independent of the declared length unit. Mesh subdivisions are positive,
nonboolean JSON integers. Study is single and plots are false.

| Physics field | Contract |
| --- | --- |
| `dirichlet_temperature_k` | Required side-to-temperature mapping; finite input K >= 0 |
| `outward_flux_w_m2` | Optional side-to-signed-constant g mapping, W/m² |
| `convection` | Optional side-to-object mapping with exactly `h_w_m2k` and `ambient_temperature_k` |
| `h_w_m2k` | Finite h >= 0, W/(m² K) |
| `ambient_temperature_k` | Finite ambient K >= 0, including when h=0 |

Side names are exactly left/right/bottom/top. Missing natural conditions mean
insulation. Null, booleans in numeric fields, nonfinite numbers, unknown keys,
callbacks and arrays instead of side constants are rejected. Signed sources
and outward flux are valid. Input nonnegative Kelvin is a document policy;
finite negative computed temperatures are retained, without clamp.

Equal prescribed corner temperatures deduplicate; conflicting values reject.
A side may carry both flux and convection, which add. Each condition kind must
select complete unique exterior edges, not interior or repeated/reversed edges.
An edge with both endpoints Dirichlet rejects even for zero flux or h.
One Dirichlet endpoint is allowed and retains the full consistent edge load;
side-name disjointness alone does not prove endpoint disjointness.

Empty Dirichlet is valid only with positive h on a real nonempty boundary.
Zero h does not anchor temperature. Compatible pure Neumann data still have
a constant nullspace and are rejected, as are incompatible data. No artificial
pin or mean-temperature gauge is inserted. Arbitrary/disconnected geometry,
temperature-dependent material, transient flux/Robin, coupling and Studio
thermal rendering are outside this contract.

## Signs, units and balance

Positive g is heat leaving the domain. Robin heat is positive outward when
T exceeds ambient Ta. With q=-k grad(T), the weak form is:

```text
q.n = g + h*(T-Ta)
A = K+H
rhs = fQ+B-G
G_i = integral_boundary(g*N_i)
B_i = integral_boundary(h*Ta*N_i)
C = H*T-B
r = (K+H)*T-(fQ+B-G)
reaction = r on Dirichlet nodes, zero on free nodes
total_outward = sum(G+C-reaction)
sum(fQ) = total_outward
```

K and H have units W/(m K). All nodal loads, rhs, residual, reaction and
integrated heat rates are W/m of out-of-plane depth; q is W/m².
`load_w_per_m` remains the volumetric source fQ, not the combined rhs.
The thermostat contribution alone is -sum(reaction); it is not total outward
heat when flux or convection is present. No transient storage or heat-content
quantity is introduced.

For a straight edge of length ell, consistent line integration gives:

```text
H_e = h*ell/6 * [[2,1],[1,2]]
G_e = g*ell/2 * [1,1]
B_e = h*Ta*ell/2 * [1,1]
```

Do not lump the boundary mass or discard fixed-end loads. The engine's shifted
evaluation and physical residual/balance guards remain authoritative.

## Contract example

This unit-square linear solution has T=300-7x K and qx=14 W/m².
The built-in `thermal_boundary` example uses h=4 W/(m² K) and Ta=290 K.
On the right, T=293 K, g=2 and h*(T-Ta)=12; the left thermostat contributes
-14 W/m. These are analytical expectations, not measurements.

```json
{
  "openphysics": "0.2",
  "name": "Steady additive outward flux and convection",
  "units": {"length": "m", "temperature": "K"},
  "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {"heat1": {
    "type": "thermal.steady2d",
    "conductivity_w_mk": 2,
    "heat_source_w_m3": 0,
    "dirichlet_temperature_k": {"left": 300},
    "outward_flux_w_m2": {"right": 2},
    "convection": {"right": {"h_w_m2k": 4, "ambient_temperature_k": 290}}
  }},
  "mesh": {"subdivisions": [8, 8]},
  "study": {"type": "single"},
  "results": {"save_fields": true, "plots": false}
}
```

## API, CLI and output files

After installing the matching packages from the combined checkout, run this
portable Python example from the repository root. It uses the same interpreter
for CLI subprocesses, writes UTF-8 explicitly and chooses fresh temporary paths.
It is a reproduction recipe; it has not been executed for this document.

```python
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from simcase import Document, ThermalRunResult, run

env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    env[key] = "1"
with tempfile.TemporaryDirectory(prefix="steady-boundary-") as directory:
    root = Path(directory)
    model = root / "thermal_boundary.json"
    example = subprocess.run(
        [sys.executable, "-m", "simcase", "example", "thermal_boundary"],
        check=True, capture_output=True, text=True, encoding="utf-8", env=env,
    )
    model.write_text(example.stdout, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "simcase", "validate", str(model)],
        check=True, env=env,
    )
    subprocess.run(
        [sys.executable, "-m", "simcase", "run", str(model),
         "-o", str(root / "cli_results")],
        check=True, env=env,
    )
    document = Document.load(model)
    result = run(document, verbose=False)
    assert isinstance(result, ThermalRunResult)
    summary = result.summary()
    result.save(root / "api_results")
    assert summary["result_format"] == "thermal.steady2d-result-v2"
    json.dumps(summary, allow_nan=False)
```

The temporary output is removed when the context ends; choose an owned,
nonexistent persistent target to retain results. CLI exit codes are 0 for
success, 2 for invalid input and 1 for solver/save or existing-target failures.
No thermal PNG is produced. Studio rejects thermal documents and clears stale
optical state; headless support does not imply Studio support.

`summary()` returns a JSON-safe dictionary. `result_format`, `field_layout`
and `boundary_enabled` identify the captured layout. Public array properties
use the names below, except `nodes_m` is `mesh_nodes_m` and `triangles` is
`mesh_triangles`. `dirichlet_node_ids` and `dirichlet_temperature_k` are
public result attributes. No optical effective index or modal normalization is
attached to temperature.

## Version and raw-field contract

Presence of either new mapping key, even an empty object, selects
`thermal.steady2d-result-v2` and `thermal2d-p1-node-cell-boundary-v2`.
Absence of both retains legacy v1 identifiers and nine arrays. Do not insert
empty defaults or infer versions from nonempty values. Null is invalid.
Input format remains 0.2.

| NPZ array | Shape | Location / meaning | Unit |
| --- | --- | --- | --- |
| `nodes_m` | (N,2) | nodes, SI coordinates | m |
| `triangles` | (M,3) | integer CCW connectivity | 1 |
| `temperature_k` | (N,) | nodes | K |
| `heat_flux_w_m2` | (M,2) | triangle centroids, -k grad(T) | W/m² |
| `load_w_per_m` | (N,) | nodes, source fQ only | W/m |
| `reaction_w_per_m` | (N,) | nodes, inward thermostat reaction | W/m |
| `residual_w_per_m` | (N,) | nodes, A*T-rhs | W/m |
| `dirichlet_node_ids` | (D,) | sorted unique prescribed integer IDs | 1 |
| `dirichlet_temperature_k` | (D,) | matching prescribed values | K |
| `prescribed_outward_load_w_per_m` | (N,) | nodes, G; v2 only | W/m |
| `ambient_load_w_per_m` | (N,) | nodes, B; v2 only | W/m |
| `convective_outward_w_per_m` | (N,) | nodes, C; v2 only | W/m |
| `system_rhs_w_per_m` | (N,) | nodes, fQ+B-G; v2 only | W/m |

For Robin-only anchoring, both Dirichlet arrays have shape (0,); node IDs
remain integer. Full residual uses A and rhs above. Consumers must check
format/layout, units, shapes, finite numeric types and metadata, using
`allow_pickle=False`. Missing v2 fields must not be replaced with invented
zeros. Summary metadata includes `field_units`, `field_locations`,
`field_shapes`, `mesh_length_unit="m"`, original document units,
boundary mappings, fixed-node count, temperature extrema and mesh/solve timings.
NPZ additionally stores Unicode scalars `result_format`, `field_layout`,
`mesh_length_unit` and `metadata_json`; metadata JSON matches the summary.
It does not contain Python object arrays.

V2 diagnostics are `source_heat_w_per_m`,
`prescribed_outward_heat_w_per_m`, `convective_outward_heat_w_per_m`,
`thermostat_outward_heat_w_per_m`, `outward_heat_w_per_m`,
`heat_balance_defect_w_per_m`, `normalized_heat_balance_defect` and
`free_residual_max_w_per_m`. The signed defect is total outward minus source.
The normalized defect divides its absolute value by the sum of absolute nodal
source, reaction, G and C contributions, with a positive floating-point floor.
The free residual maximum is dimensional W/m (zero when no free nodes exist).
V2 does not publish the v1 `normalized_free_residual` diagnostic: a K-only
normalization is not the Robin engine's guard. These summary checks do not
replace the engine's unchanged physical residual/balance guards or independent
acceptance. Diagnostic-scale follow-ups must be reviewed at their exact SHA.

## Geometry, lifetime and validation limits

Finite coordinates alone do not guarantee distinguishable sides. The helper
uses 64 machine eps times the larger absolute coordinate/extent per axis.
It rejects a tolerance reaching half an extent, overlapping side-edge
classification, incomplete rectangles and incorrect node/edge tags.
Dirichlet identity comes from verified exterior-edge endpoints, not a broad
coordinate mask that can include nearby interior nodes. Large origins and
very short edges may be rejected for insufficient coordinate precision;
choose a smaller coordinate origin rather than relaxing geometry guards.

The runtime copies the input document and captures canonical JSON, mesh nodes,
triangles and prescribed data. Summary/save reject ordinary post-run value
changes in `result.doc`, including name/results options; key order alone is
irrelevant. Set output options before running. The saved model describes that
captured calculation. Caller input changes are isolated. This is consistency
checking, not cryptographic authentication or authorization, and concurrent
mutation during run/capture is unsupported. Further snapshot changes require
review of the actual runtime follow-up.

Saving preserves the [fresh-output ownership contract](thermal_steady2d.md#output-ownership-and-failures).
A fresh target receives `.incomplete`, `model.json`, UTF-8 `log.txt`,
optional `fields.npz` and `summary.json` last. `save_fields=false` omits NPZ,
not raw finite/shape/connectivity/CCW and finite-JSON validation. The complete
solution remains in memory. Nonfinite reductions/JSON are refused, not emitted
as NaN/Infinity. Caller exclusivity is required throughout save and cleanup;
check/use replacement races, atomic publication and crash rollback are outside
the guarantee. Windows hard-link capability and actual Windows/macOS execution
must be assessed separately. Original ownership failures remain evidence.

Preserve n8/16/32/64 final-two temperature L2 order >=1.8 and flux order >=0.9,
normalized residual/balance 1e-10 and SI similarity 1e-9. Existing quadrature
and independent negative controls remain separate gates. Constant JSON boundary
data do not serialize sine/callback MMS. Test declarations, helper diagnostics,
public API/CLI, installed consumers and exact CI are different evidence levels.
Linux results do not establish Windows/macOS acceptance.
