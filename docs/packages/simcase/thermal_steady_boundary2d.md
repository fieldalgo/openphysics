# Steady outward-flux and convection documents

[한국어](../../locales/ko/pages/packages/simcase/thermal_steady_boundary2d.md)

## Implementation and validation status

This checkout implements the boundary extension for `thermal.steady2d` through
`Document.from_dict`, JSON loading, validation, document summaries,
`run(Document)`, `ThermalRunResult`, the CLI and JSON/NPZ saving with the existing
thermal engine. The [rectangle guide](thermal_steady2d.md) describes the plain layout
without boundary keys. Use matching packages from the same checkout.

The [independent validation report](steady_boundary_independent_validation.md)
separates fixed acceptance gates, source review and bounded direct-path
measurements. Full source, installed and platform acceptance must be checked
against the exact commit's CI logs and artifacts. Test definitions alone do not
establish a pass. Examples below give reproduction procedures and analytical
expectations; they do not expand the measured validation scope.

## Inputs and supported scope

Use format `"openphysics": "0.3"`, one `thermal.steady2d` physics,
a homogeneous rectangle, P1 triangles, constant isotropic positive
`thermal_conductivity` (such as `"2 W/(m K)"`), and signed constant
`heat_source_density` (such as `"0 W/m^3"`; absent means no source). The geometry declares
its `length_unit`; every value carries its own unit and is read in SI. `subdivision_count` is
two positive JSON integers. Study is single and plots are false.

| Physics field | Contract |
| --- | --- |
| `prescribed_temperature` | Required side-to-temperature mapping; each above 0 K |
| `inward_heat_flux` | Optional side-to-signed-constant mapping, W/m^2, positive into the body |
| `convection` | Optional side-to-object mapping with exactly `heat_transfer_coefficient` and `ambient_temperature` |
| `heat_transfer_coefficient` | h >= 0, such as `"4 W/(m^2 K)"` |
| `ambient_temperature` | Above 0 K, including when h=0 |

The engine takes the outward flux g; simcase hands it `0.0 - inward_heat_flux`, an exact sign
flip. A format 0.2 `outward_flux_w_m2` key is refused with this rule in its message.

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
`generated_heat_rate_per_depth` remains the volumetric source fQ, not the combined rhs.
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
  "openphysics": "0.3",
  "name": "Steady additive outward flux and convection",
  "geometry": {"length_unit": "m", "depth": null,
               "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
  "materials": {},
  "physics": {"heat1": {
    "type": "thermal.steady2d",
    "thermal_conductivity": "2 W/(m K)",
    "heat_source_density": "0 W/m^3",
    "prescribed_temperature": {"left": "300 K"},
    "inward_heat_flux": {"right": "-2 W/m^2"},
    "convection": {"right": {"heat_transfer_coefficient": "4 W/(m^2 K)",
                             "ambient_temperature": "290 K"}}
  }},
  "mesh": {"subdivision_count": [8, 8]},
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
    assert summary["result_format"] == "thermal.steady2d-result-v4"
    json.dumps(summary, allow_nan=False)
```

The temporary output is removed when the context ends; choose an owned,
nonexistent persistent target to retain results. CLI exit codes are 0 for
success, 2 for invalid input and 1 for solver/save or existing-target failures.
No thermal PNG is produced. Studio validates, runs and shows these documents
through its own heat routes; see [Steady heat in Studio](thermal_studio.md).

`summary()` returns a JSON-safe dictionary. `result_format`, `field_layout`
and `boundary_enabled` identify the captured layout. Public array properties
use the names below. No optical effective index or modal normalization is
attached to temperature.

## Version and raw-field contract

Presence of either mapping key, even an empty object, selects
`thermal.steady2d-result-v4` and `thermal2d-p1-node-cell-boundary-v3`.
Absence of both gives `thermal.steady2d-result-v3`, `thermal2d-p1-node-cell-v2` and nine
arrays. Do not insert empty defaults or infer versions from nonempty values. Null is invalid.
The format 0.2 identifiers (`-result-v1`, `-result-v2`, `-cell-v1`, `-boundary-v2`) are retired.

| NPZ array | Shape | Location / meaning | Unit |
| --- | --- | --- | --- |
| `node_coordinates` | (N,2) | nodes, SI coordinates | m |
| `triangles` | (M,3) | integer CCW connectivity | (structural) |
| `temperature` | (N,) | nodes | K |
| `heat_flux` | (M,2) | triangle centroids, -k grad(T) | W/m^2 |
| `generated_heat_rate_per_depth` | (N,) | nodes, source fQ only | W/m |
| `reaction_heat_rate_per_depth` | (N,) | nodes, heat the constraint injects | W/m |
| `residual_heat_rate_per_depth` | (N,) | nodes, A*T-rhs | W/m |
| `prescribed_node_ids` | (D,) | sorted unique prescribed integer IDs | (structural) |
| `prescribed_temperature` | (D,) | matching prescribed values | K |
| `outward_prescribed_heat_rate_per_depth` | (N,) | nodes, G; boundary layout only | W/m |
| `ambient_convective_heat_rate_per_depth` | (N,) | nodes, B; boundary layout only | W/m |
| `outward_convective_heat_rate_per_depth` | (N,) | nodes, C; boundary layout only | W/m |
| `applied_heat_rate_per_depth` | (N,) | nodes, fQ+B-G; boundary layout only | W/m |

For Robin-only anchoring, both prescribed arrays have shape (0,); node IDs
remain integer. Full residual uses A and rhs above. Consumers must check
format/layout, units, shapes, finite numeric types and metadata, using
`allow_pickle=False`. Missing boundary fields must not be replaced with invented
zeros. The summary carries `field_units` (structural arrays have none), `field_locations`,
`field_shapes`, `field_components`, the `diagnostics`, `defaults_applied` and
`resolved_inputs`, the boundary mappings as `{"value", "unit"}` objects, fixed-node count,
temperature extrema and `timing.wall_time`. NPZ additionally stores the scalars
`result_format`, `field_layout` and `metadata_json`; metadata JSON matches the summary.
It does not contain Python object arrays.

Boundary-layout balance values (each `{"value", "unit"}`) are
`generated_heat_rate_per_depth`, `outward_prescribed_heat_rate_per_depth`,
`outward_convective_heat_rate_per_depth`, `outward_reaction_heat_rate_per_depth`,
`outward_heat_rate_per_depth`, `heat_rate_imbalance_per_depth`,
`relative_conservation_residual` and `maximum_residual_heat_rate_per_depth`. The signed
imbalance is total outward minus source.
The normalized defect divides its absolute value by the sum of absolute nodal
source, reaction, G and C contributions, with a positive floating-point floor.
The residual maximum is dimensional W/m (zero when no free nodes exist).
The boundary layout does not publish the plain layout's `relative_residual`: a K-only
normalization is not the Robin engine's guard. These summary checks do not
replace the engine's unchanged physical residual/balance guards or independent
acceptance. The reviewed implementation keeps the dimensional residual maximum of the
boundary layout separate from the plain layout's normalization.

## Geometry, lifetime and validation limits

Finite coordinates alone do not guarantee distinguishable sides. The helper
uses 64 machine eps times the larger absolute coordinate/extent per axis.
It rejects a tolerance reaching half an extent, overlapping side-edge
classification, incomplete rectangles and incorrect node/edge tags.
Dirichlet identity comes from verified exterior-edge endpoints, not a broad
coordinate mask that can include nearby interior nodes. Large origins and
very short edges may be rejected for insufficient coordinate precision;
choose a smaller coordinate origin rather than relaxing geometry guards.

The runtime copies and validates the input document, restoring its declared
unit scale immediately, and captures canonical JSON, mesh nodes, triangles
and prescribed data. Summary/save compare document values before validation,
then check again after normalization: deleting a defaulted field cannot hide
an edit by having validation restore it. Name/results changes are rejected;
key order alone is irrelevant. Mesh and prescribed arrays must match captured
values and dtypes. Set output options before running. The saved model describes
that calculation, and changes to the caller's original document are isolated.

Raw real-numeric/finite checks run before document and mesh-snapshot checks.
Thus a nonfinite raw value is refused as such even if another input was also
changed. Snapshot checks do not bypass raw validation when fields are disabled.
This is consistency checking, not cryptographic authentication or authorization;
it does not freeze every exposed result object or independently re-solve and
certify a caller-modified finite solution. Concurrent mutation during
run/capture/save is unsupported.

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
