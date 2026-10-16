# Steady heat in Studio

[한국어](locales/ko/pages/thermal_studio.md)

## Availability

**Implementation candidate; integration and acceptance pending.** Server
`533c5e8c3f50d05f52323588e81b4997500e00e5` implements the dedicated thermal
routes and typed capture/encoding. Frontend candidate `4aa8beac` is being aligned
with this wire contract. Use the exact combined candidate, not these components
independently. The documentation base main still has generic heat refusal.
No numerical, HTTP, browser, installed or platform pass is asserted here.

The wire format below is fixed. Capability `run_enabled` and terminal eviction
describe the required integration policy; the initial server candidate does not
yet emit that flag or implement early terminal eviction. Follow-up source and
tests must confirm them before acceptance. `run_enabled=true` means valid
configured limits and supported public API, **not completed performance measurement**.
`resource_policy="candidate-unmeasured"` remains a separate declaration.

The intended scope is JSON-first `thermal.steady2d`: homogeneous rectangle/P1,
constant isotropic k and source, prescribed side temperatures, insulation and
the separately integrated constant outward-flux/Robin contract.
There is no transient UI, mesh-only preview, new solver, result-saving endpoint,
arbitrary geometry or automatic coupling. Existing optical behavior remains.
The [headless steady guide](thermal_steady2d.md) remains the starting point for
model units and the existing Python/CLI workflow.

## Start and planned user flow

After installing matching packages and the optional Studio dependencies from a
repository checkout, start from the repository root:

```sh
python -m pip install -e "packages/simcase[studio]"
python -m simcase.studio --no-browser
```

Open the printed localhost address. These existing startup commands do not
enable an unimplemented thermal capability.

1. Open a complete steady heat JSON document or paste it into the JSON editor.
   Apply it explicitly. A thermal form-based material/boundary editor is outside
   this scope; generic optical examples remain optical.
2. Validate the current applied JSON through the dedicated thermal action.
   Invalid JSON, unsupported physics or a limit refusal cannot authorize a run
   of an earlier valid document. Editing/importing immediately invalidates old
   validation, mesh and result ownership, even before parsing succeeds.
3. Run only the current validated steady document, when the server advertises
   the matching capability and configured limits. Run revalidates independently.
   Do not silently coarsen the mesh to fit a limit.
4. After success, inspect the **actual result mesh**. The thermal Mesh action
   remains unavailable before solving; do not use optical meshing or run merely
   to generate a preview.
5. Select temperature or cell heat-flux components/magnitude locally, without
   rerunning. Model edits require validation and a new run; view changes do not
   modify the result document.
6. On error, correct the current input or explicitly retry the current operation.
   Old asynchronous success, error and finalization callbacks must not replace
   current controls, messages, mesh, field or colorbar.

## Units and physical meaning

| Display/data | Intended contract |
| --- | --- |
| Coordinates | Raw `arrays.nodes_m` in m; axes divide by top-level `display_length_in_m`, the captured positive metres-per-document-length-unit scale |
| Temperature | `temperature_k`, nodal P1, K; linear interpolation and labelled colorbar |
| Flux | `heat_flux_w_m2`, constant per triangle, W/m²; global qx/qy or magnitude |
| Arrows | Actual cell centroids and global directions; labelled view gain, no physical rescaling |
| Source/reaction/rates | Nodal W/m of out-of-plane depth, distinct from W/m² flux |

```text
q = -k grad(T)
q.n = g_out + h*(T-T_ambient)
rhs = fQ+B-G
total_outward = sum(G+C-reaction)
thermostat_outward = -sum(reaction)
```

Positive prescribed flux is outward. Do not substitute thermostat heat for total
outward heat when flux/convection exists. Input prescribed/ambient K is finite
and nonnegative under the document contract. A finite negative computed K is
retained and shown, without clamp or optical-mode normalization; this linear
mathematical result is not proof of physical material validity at that temperature.
Constant temperatures need a constant-range display, not division by zero.
Cell flux is not averaged into a nodal field. Overflow in converted coordinates
or derived flux magnitude is a view error, not permission to change raw data.

The intended typed payload separates wire format from headless v1/v2 result and
layout IDs. V1 has nine raw arrays, v2 thirteen; Robin-only v2 can have zero
Dirichlet nodes. Require the exact allowed version pair, units, locations,
shapes, finite nonboolean arrays and valid CCW connectivity. Unknown layouts,
missing fields and malformed payloads must not reach the display.

## Fixed wire envelope

```text
payload_format = "studio-thermal-steady-v1"
kind = "thermal.steady2d"
job, result_id, client_revision, request_seq
result_format, field_layout
display_length_in_m
summary
arrays
```

These are top-level fields; there is **no nested coordinates object**.
`arrays` contains exactly the nine v1 or thirteen v2 headless arrays.
`summary` carries matching units, locations and shapes; coordinates are metres
(`summary.mesh_length_unit="m"`), while `summary.units.length` supplies the
document display declaration. Run identity is kind/job/result_id plus the two
nonnegative safe-integer counters. Status adds status/log/error/has_result.
Requests contain exactly doc/client_revision/request_seq and use UTF-8
application/json. Duplicate keys, nonfinite JSON, malformed envelopes and
unsupported physics are refused. No field/time selector is accepted on thermal
status/result routes. Arrays, summary and identity use this single contract.

## Route boundaries and recovery

The server candidate implements these dedicated routes; they are not yet
accepted main functionality:

| Route | Planned behavior |
| --- | --- |
| `GET /api/capabilities` | Versioned steady capability and configured resource policy |
| `POST /api/thermal/validate` | Strict JSON envelope, public document validation and preflight |
| `POST /api/thermal/run` | Revalidation, capacity reservation, captured input and public run |
| `GET /api/jobs/{job}` | Bounded thermal status/log/error and response-ownership tags |
| `GET /api/jobs/{job}/result` | One fully validated/encoded steady payload after success |

Existing `/api/validate` keeps heat `ok=false`; generic `/api/mesh` and
`/api/run` keep heat/cavity execution refusal. Existing cavity schema-validation
behavior is distinct from execution. Thermal support must use dedicated routes,
not remove generic optical guards. Transient documents and time/history selectors
remain unsupported. Missing/malformed capabilities disable thermal actions
without disabling existing optical startup.

Planned errors distinguish malformed input (400), logical validation failure
(200 with `ok=false`), request/resource limits (413/429), expired/unknown result
(404), and unavailable running/error result (409). HTTP200 alone is not validation
success. Network/non-JSON errors require an explicit current retry; expiration
must not automatically solve again. No partial result or stale optical fallback
is published after a failed job. Error strings are displayed as plain text.

Revision/sequence/job/result tags select which response may update this view;
they are not authentication. Same-revision retries and field-render changes
also require operation ownership. Ignoring stale responses does not cancel the
server solve or authorize deleting another job. Localhost/auth/CORS behavior is
not upgraded into multi-tenant isolation.

## Resource policy and limits

All limits remain **candidate settings, not measured capacity**:
request 1 MiB; N<=10201 nodes; M<=20000 cells; encoded result 16 MiB;
one active thermal job; at most two terminal thermal records and 32 MiB total;
terminal retention at most 300 s. Final capabilities must expose the actual configured
policy. Thermal run stays disabled if required policy is not configured.
Admission/publication reclaim the oldest terminal records (done **or** error)
when count/byte space is needed, preserving active thermal and all optical jobs.
TTL 300 s is a maximum retention, **not a minimum availability guarantee**.
A result may be evicted earlier; evicted/expired status or result returns 404,
with no automatic rerun. There is no policy that blocks every third run for
five minutes. UI invalidation never deletes global jobs.
Limits cover successful and failed terminal metadata, logs and errors; capacity
must be released after success and every failure, including thread-start,
encoding and publication failures. Active/optical jobs are not evicted.

Bound streamed request bytes before full parsing, without trusting Content-Length.
Preflight node/cell counts before job/thread/solver allocation. Raw scalar counts
are v1=6N+5M+2D and v2=10N+5M+2D, but neither raw-byte estimates nor encoded
caps bound Python/solver peak memory. Copies, lists, sparse factorization,
serialization and concurrent work add overhead. Actual shared-host measurements
must disclose load; no dedicated performance baseline is claimed.
Retain bounded encoded results rather than repeated full array serialization.
There is no new save/upload/path/overwrite API or automatic retry queue.

## Test map and evidence status

| Layer | Required evidence, not a claimed pass |
| --- | --- |
| Server | Strict JSON/limits before allocation; public API positive controls; v1/v2/D0 metadata; copied properties validated once; all terminal paths bounded |
| Physics | Independent linear/additive and source/Robin solutions, SI conversion, original convergence and negative controls |
| Frontend | Deterministic dirty/revision/sequence/capability/render truth-table; stale success/error/finally ignored |
| Display | Distinct node/cell fixtures, nodal interpolation, flat flux/global signs, constant and negative K |
| Resource | Capacity release, failed-job retention, byte/count/TTL edges and separately measured peak/serialization |
| Distribution/platform | Shipped assets/imports, source and installed consumers, exact required CI and separate OS results |
| Browser | Actual Canvas interaction, separate from HTTP TestClient and Node tests |

Preserve n8/16/32/64 final-two L2 temperature order >=1.8 and flux order >=0.9,
normalized residual/balance 1e-10 and SI similarity 1e-9. Studio refusals do not
waive physics gates. No new numerical, HTTP, Node, installed, browser or platform
tests were executed for this draft. Linux passes do not imply Windows/macOS
passes; test definitions do not imply execution, acceptance or main integration.
