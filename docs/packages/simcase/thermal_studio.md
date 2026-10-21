# Steady heat in Studio

[한국어](../../locales/ko/pages/packages/simcase/thermal_studio.md)

**At a glance**

- **What it does:** a dedicated, JSON-first Studio view for rectangular `thermal.steady2d` documents (homogeneous rectangle, P1, constant isotropic k and source, side Dirichlet, insulation, constant outward flux and Robin). It validates and runs through its own routes and shows the result mesh, nodal Kelvin and cell heat flux. Steady heat documents with material regions are validated, run and shown the same way within Studio's region limits, with region colours, boundaries, a legend and a region table (see [Region documents](#region-documents)).
- **Limits:** no transient documents (see the separate transient Studio guide), pre-solve mesh preview, arbitrary geometry beyond region documents, coupling or result-saving endpoints. Configured resource limits are `candidate-unmeasured`, not capacity guarantees. Studio is a local tool, not a multi-user service.
- **Validation:** see the [independent steady Studio validation](studio_thermal_independent_validation.md). For a specific commit, see its CI run.

## Availability

This checkout implements JSON-first steady heat in Studio: dedicated validation
and run routes, typed SI results, the actual result mesh, nodal Kelvin and cell
heat-flux views. It uses the existing homogeneous rectangle/P1 headless solver
with constant isotropic k and source, side Dirichlet, insulation and constant
outward-flux/Robin conditions. Existing optical behavior and generic-route heat
guards remain. This steady interface excludes transient documents and time/history
selection; see the separate [transient Studio guide](thermal_transient_studio.md).
Pre-solve mesh preview, arbitrary geometry beyond the region documents below,
automatic coupling and new result-saving endpoints are outside this interface.
Steady documents with
material regions (`geometry.shapes` or `geometry.background`) take a separate
path on the same routes, described in [Region documents](#region-documents).

Implementation is separate from validation and release status. Inspect the
exact checkout's CI results and artifacts for source, installed-platform,
browser and resource evidence. This page does not assert a new pass or release.
`run_enabled=true` indicates valid configured limits and public API availability,
not completed performance measurement. Resource policy remains
`candidate-unmeasured`; configured limits are not a capacity or performance
guarantee. See the [headless steady guide](thermal_steady2d.md) for model units
and Python/CLI use.

## Start and user flow

After installing matching packages and the optional Studio dependencies from a
repository checkout, start from the repository root:

```sh
python -m pip install -e "packages/simcase[studio]"
python -m simcase.studio --no-browser
```

Open the printed localhost address. Startup does not bypass capability checks
or configured resource limits.

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

The editor preserves original JSON text for strict validation, including duplicate-key
detection; normalized model data is a separate snapshot. After success, the
summary table shows the raw temperature range, result node/cell counts and
the server's named source/outward/balance quantities. Expand **Full result
metadata** to inspect the complete summary; it is not an independent physical
oracle. Hidden tabs are not rasterized at zero layout size: switching to a
visible Mesh/Results tab redraws the current accepted result without solving.

## Units and physical meaning

| Display/data | Contract |
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

The typed payload separates wire format from headless v1/v2 result and
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

This checkout implements the following dedicated steady routes. Implementation
and exact-checkout validation are distinct, as described above:

| Route | Steady behavior |
| --- | --- |
| `GET /api/capabilities` | Versioned steady capability and configured resource policy |
| `POST /api/thermal/validate` | Strict JSON envelope, public document validation and preflight |
| `POST /api/thermal/run` | Revalidation, capacity reservation, captured input and public run |
| `GET /api/jobs/{job}` | Bounded thermal status/log/error and response-ownership tags |
| `GET /api/jobs/{job}/result` | One fully validated/encoded steady payload after success |

Existing `/api/validate` keeps heat `ok=false`; generic `/api/mesh` and
`/api/run` keep heat/cavity execution refusal. Existing cavity schema-validation
behavior is distinct from execution. Thermal support must use dedicated routes,
not remove generic optical guards. These steady endpoints reject transient
documents and time/history selectors; the separate
[transient Studio interface](thermal_transient_studio.md) defines their dedicated
routes and views. Missing/malformed steady capabilities disable steady actions
without disabling existing optical startup.

Errors distinguish malformed input (400), logical validation failure
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
terminal retention at most 300 s. Logs are capped at 64 KiB, errors at 4 KiB,
summary metadata at 64 KiB and status encoding at 128 KiB. Final capabilities must expose the actual configured
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
For rectangle documents, preflight exact node/cell counts before job/thread/solver
allocation. For region documents, the raw geometry caps and the loop-vertex count
come before the job, and the exact node and cell counts after meshing, before the
solve (see [Region documents](#region-documents)). Raw scalar counts are
v1=6N+5M+2D, v2=10N+5M+2D and regions 10N+6M+2D, but neither raw-byte estimates
nor encoded caps bound Python/solver peak memory. Copies, lists, sparse factorization,
serialization and concurrent work add overhead. Actual shared-host measurements
must disclose load; no dedicated performance baseline is claimed.
Retain bounded encoded results rather than repeated full array serialization.
There is no new save/upload/path/overwrite API or automatic retry queue.

## Region documents

A `thermal.steady2d` document whose `geometry` has `shapes` or `background`
(the engine's own rule, see [heat documents with material regions](thermal_regions2d.md))
takes Studio's region path on `/api/thermal/validate` and `/api/thermal/run`.
Every other document follows the rectangle path, whose code, bytes and errors
are unchanged; `tests/simcase/test_studio_rectangle_invariants.py` pins them.
A region document with `mesh.subdivisions` is refused (`invalid_document`,
path `mesh.subdivisions`), and so is a rectangle document with a stray
`geometry.shapes` key, because that key makes it a region document.

### Wire format

| Item | Region result |
| --- | --- |
| Result and layout IDs | `thermal.steady2d-regions-result-v1`, `thermal2d-p1-node-cell-regions-v1` |
| Payload | `payload_format = "studio-thermal-steady-regions-v1"`, the same 11 top-level fields as the rectangle payload |
| `arrays` | The thirteen v2 arrays plus `triangle_regions`: one region index per triangle (unit `1`, location `triangles`, shape `[M]`); D=0 is allowed (Robin-only anchoring) |
| `summary` | The producer's summary, including `region_names` (the order of the indices), `regions` (per name: `material`, `triangles`, `area_m2`), the whole `materials` table, `heat_source_w_m3`, `conductivity_range_w_mk` and `mesh` (`nodes`, `triangles`, `size`, `min_angle_deg`, `size_unit`) |
| Capability | A nested `regions` key in the steady block: `supported`, `run_enabled`, `result_formats`, `field_layouts`, `payload_formats` and the five `limits` below |

The region pair is not added to the block's outer `result_formats`, which the
rectangle client reads, so a page without region support ignores the nested
block and refuses a region payload after the job (the format and pair are new).
The page pins a document's family (rectangle or regions) when it validates it,
refuses a region document before any request when the server advertises no
valid `regions` block, runs it only while that block's `run_enabled` is true,
and refuses a result of the other family.

Before publishing, the capture checks the pair before reading any array, reads
each public property once, checks shapes and node/cell caps before copying,
then checks the regions: 1 to 65 unique nonempty names equal to the summary's;
indices in range; each region's triangle count; each region's area equal to the
producer's own sum over the captured mesh (exactly, as the same expression on
the same numbers); the areas adding up to the domain within 1e-9; each region's
material as the document assigns it; and summary materials and heat sources
equal to the document's. Any failure is the job error `invalid_result`, and
nothing is published.

### Limits and where they apply

| Stage | Check | Refusal |
| --- | --- | --- |
| Event loop, cost linear in the JSON | One `thermal.steady2d` entry; no `mesh.subdivisions` | `unsupported_physics` (400); `invalid_document` (200 with `ok=false` on validate, 400 on run) |
| Event loop | The steady boundary (v2) result runtime is installed, since region results always carry the boundary arrays | `unsupported_result_format` (400) |
| Event loop, run only | The public result API for region runs is available (the block's `run_enabled`) | `unsupported_public_api` (400) |
| Worker thread, before `Document.from_dict` | At most 64 shapes, 16 circles and 512 polygon points in total, then at most 1024 boundary crossings (`simcase.region_complexity`) | `geometry_limit_exceeded` (413), path `geometry.shapes` |
| Worker thread | `Document.from_dict` | `invalid_document` |
| Worker thread | At most 2048 loop vertices after the shapes' booleans (`simcase.check_mesh_limits`) | `geometry_limit_exceeded` (413), path `geometry.shapes` |
| Worker thread | The document's name, units, materials and heat sources encode within 64 KiB (`metadata_bytes`); the summary copies them | `payload_limit_exceeded` (413), path `materials` |
| Job, before the solve | Meshing stops past 10201 nodes (`max_nodes`); the exact node and cell counts are then compared with 10201 and 20000 | Job error `mesh_limit_exceeded` |
| Job | A document error found after meshing, such as a heat source on a shape that later shapes cover completely | Job error `invalid_document` |
| Job | Any other run failure, such as a geometry meshine cannot resolve or a refinement that does not converge within meshine's 80 rounds | Job error `solver_failed` |

The four geometry caps and the loop-vertex cap are the capability's
`limits` (`max_shapes`, `max_circles`, `max_polygon_points`,
`max_boundary_crossings`, `max_input_vertices`); the node and cell caps are the
steady block's `max_nodes` and `max_triangles`. Every refusal message names the
count and the limit; when meshing stops at the node cap the count is unknown
and the message says "more than". All values are candidates
(`candidate-unmeasured`).

- A **boundary crossing** is a pair of boundary segments of different shapes
  whose interiors meet in exactly one point (a rect is 4 segments, a circle the
  128-gon the engine builds, a polygon its edges). Touching and collinear
  overlap do not count. Crossings cost validation time even where later shapes
  cover them, so they are counted on the raw JSON before validation.
- A **loop vertex** is one point of a loop given to the mesher, after the
  booleans: a shape inside the background counts as itself and as the
  background's hole, and a circle that touches or crosses another boundary is a
  128-gon, so at most 7 such circles fit within 2048. A circle clear of every
  other boundary is meshed as an exact circle with max(16, 4πr/`mesh.size`)
  points from the global `mesh.size`, even when it sets its own `mesh_size`,
  so a tiny global size is refused here.

See [mesh limits for callers](thermal_regions2d.md#mesh-limits-for-callers)
for the engine functions Studio uses.

### Validation thread and concurrency

Region validation (the raw counts, `Document.from_dict`, the loop-vertex count
and, for a run, the run copy) runs in a worker thread, so long geometry work does
not block the event loop; Python-level shapely and numpy calls that hold the GIL
can still delay it briefly. The request keeps the shared thermal ingress permit
until that thread returns, also when the client disconnects or the request is
cancelled, so at most one region validation runs at a time and other thermal
requests get 429 meanwhile; a cancelled request then ends without starting a job.
A run validates again in the same way, then reserves the single job slot.

The loop-vertex count is taken on the micrometre copy a run meshes, and
`check_mesh_limits` validates that copy as a run does, so validation resolves
the shapes' booleans three times: in `Document.from_dict`, in the copy's
validation and for the count. In local runs the count took about twice as long
as `Document.from_dict`: about 0.6 s against 0.3 s for the covered crossings at
the crossing cap.

### Views

- **Mesh tab:** each triangle is filled with its region's colour (Okabe-Ito,
  eight colours cycled by region index) under the mesh lines, and region
  boundaries are drawn as thicker lines. The legend lists every region as
  "name — material", and the mesh line reads "N nodes, M cells, R regions".
- **Results tab:** the temperature and flux views also draw the region
  boundaries. Hovering adds "; region name (material)" to the value line.
- **Summary panel:** the quantity rows leave out the region, material and heat
  source maps (a region name is not a quantity); the full metadata stays in
  **Full result metadata**, and a region table follows it with colour, region,
  material, k, Q, cells, area and the material's `source` text.
- Region names and material text are shown as text only, never as HTML.

### Known limits

- An over-fine mesh fails in the job, after meshing and before the solve, not
  at validation: validation refuses only on geometry, the summary floor and, for
  transient documents, history length. The job slot is held meanwhile.
- A refinement that does not converge within meshine's 80 rounds before the
  node cap stops it also fails in the job, as `solver_failed`, and also holds
  the job slot while it runs.
- Isolated circles take their point count from the global `mesh.size` (see above).
- The loop-vertex count is taken before the mesher splits loops at T-junctions,
  so the mesher can process somewhat more points than counted.
- Region results always carry 14 arrays; D=0 is legal.
- The summary copies the whole materials table, including unused materials and
  their `source` text, and must fit in 64 KiB. Certain overflows are refused at
  validation; the rest end as a job error.
- meshine can fail closed with "cannot resolve" (`solver_failed`), for example
  for acute star polygons or crossing polygons with near-coincident boundaries.
- Colours repeat after eight regions; the legend, boundaries, table and hover
  still name every region.
- A page cached from before region support refuses region results after the
  job (`/static` has no `Cache-Control`); reload the page.
- Region examples are not listed in `/api/examples`, because the generic routes
  refuse heat documents.
- With a meshine older than this checkout's (no `MeshSizeLimitError`), region
  runs end as `solver_failed` while `run_enabled` stays true.
- Measurements are Linux only; macOS and Windows are unverified.

## Contribution and validation lifecycle

All changes, including documentation, follow the same main/PR validation policy.
Open work as a Draft PR; Draft PRs and feature-branch pushes do not run validation
CI. After relevant checks pass in an authorized development environment, mark
the reviewed candidate Ready. Do not run numerical workloads on a user's PC.
Missing execution remains an explicit gap, not a pass. Ready PR and main
validation must preserve the scientific gates and required checks.
Reviewed Ready PRs use automatic **Rebase and merge** after required checks;
automatic landing does not replace review or post-merge evidence. Record the
landed main SHA, which may differ from the submitted commit.

Main validation uses a stable workflow/ref concurrency key,
`cancel-in-progress: false` and `queue: max`. Non-main/PR supersession uses
`queue: single` with cancellation of superseded runs. The main pending limit
is 100; queue-entry order is not commit order, unlimited retention, reserved
capacity or a deployment guarantee. A green PR is distinct from green landed
main. Release only from the appropriate green main commit; validation does not
publish packages.

Full Linux scientific acceptance and installed-distribution validation on
Linux, macOS and Windows are distinct requirements. A configured matrix is not
three observed passes; inspect each exact job, environment, import origins,
archive/wheel identities, failures, skips and artifacts. Narrow
Windows checks do not certify full Windows physics or macOS. A universal wheel
does not establish OS behavior. Report unavailable platforms as unverified;
do not turn platform failures into unexplained skips. Actual browser interaction
and resource measurements remain separate from HTTP/Node/installed checks.

## Test map and evidence status

| Layer | Required evidence, not a claimed pass |
| --- | --- |
| Server | Strict JSON/limits before allocation; public API positive controls; v1/v2/D0 metadata; copied properties validated once; all terminal paths bounded; rectangle bytes and errors pinned before region support (`test_studio_rectangle_invariants.py`); region limits, refusals, worker thread, cancellation and capture faults (`test_studio_region_http.py`) |
| Physics | Independent linear/additive and source/Robin solutions, SI conversion, original convergence and negative controls; region documents through the wire (`test_studio_region_acceptance.py`) |
| Frontend | Deterministic dirty/revision/sequence/capability/render truth-table; stale success/error/finally ignored; nested region capability, family pin and region payload parsing (`studio_steady_thermal.cjs`, `studio_transient_thermal.cjs`) |
| Display | Distinct node/cell fixtures, nodal interpolation, flat flux/global signs, constant and negative K |
| Resource | Capacity release, failed-job retention, byte/count/TTL edges and separately measured peak/serialization |
| Distribution/platform | Shipped assets/imports, source and installed consumers, exact required CI and separate OS results |
| Browser | Actual Canvas interaction, separate from HTTP TestClient and Node tests |

Preserve n8/16/32/64 final-two L2 temperature order >=1.8 and flux order >=0.9,
normalized residual/balance 1e-10 and SI similarity 1e-9. Studio refusals do not
waive physics gates. Numerical, HTTP, Node, installed, browser and platform acceptance each require
observed execution on the exact checkout. Linux passes do not imply Windows/macOS
passes; test definitions do not imply execution, acceptance or main integration.
