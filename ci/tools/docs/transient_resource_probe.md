# Transient Studio resource observer
[한국어](locales/ko/pages/transient_resource_probe.md)

The stdlib-only `ci/tools/probe_transient_studio_resources.py` observes an already running, explicitly selected loopback server. It does not start/install a server, import a solver, replace numerical acceptance or certify capacity. Use a new evidence directory for every attempt.

```sh
python ci/tools/probe_transient_studio_resources.py --plan --output records/transient-shapes
python ci/tools/probe_transient_studio_resources.py --base-url http://127.0.0.1:8000 --document input.json --source-commit FULL_SERVER_SHA --output records/transient-http
```

The input is a document object, not the request envelope. HTTP mode records capabilities, validates, submits exactly one solve (never retries it), polls with bounded timeout/request count, saves the manifest and last temperature frame, repeats the identical complete frame query ten times (eleven frame GETs total: first1+repeat10), and reads one H history page of at most sixteen rows. Same-query status/length/hash must match. Transient frame encoding on demand is permitted; matching hashes cannot establish zero producer getter or solve calls. Status errors and non-2xx bodies remain evidence, never successful capacity samples. A timeout does not cancel the server solve.

Reports include operator-supplied source SHA (not source verification), Python/platform, input hash, HTTP paths/status/bytes/hash/time, selected raw responses, failure and exit. Redirects/proxies/credentials/nonliteral nonloopback addresses are excluded. Requests are <=1MiB, individual reads <=4MiB (status <=128KiB), request count<=160; no encoded frame cache is created. Reports and input copies can contain user model data; use an appropriate local records directory. Output must not already exist.

## Workloads and accounting
Plan mode only calculates shapes, without allocating arrays or executing physics. For subdivisions n, N=(n+1)^2, M=2n^2, Nt requested times and D unique fixed nodes, the thirteen-array scalar count is
`S=2N+3M+D+Nt*(2N+2M+D+3)+3*(Nt-1)*N`.
The estimate8S assumes eight-byte dtypes. Actual capture must sum dtype itemsize*size. Use D=N as a conservative preflight upper bound until complete boundary validation proves a smaller unique D. Metadata, sampled BC input, summaries/copies, reservations, list/JSON workspace, sparse/native memory and transport buffers are additional.

Small n2/Nt3 and medium n16/Nt8 are preparation shapes. The script searches legal n/Nt pairs for a conservative-D estimate nearest below/above the16MiB raw candidate. These are arithmetic candidates, not validated physical inputs, exact cap+1 actors or measured capacity. Use the actual implementation's preflight and independently valid physical documents before execution; preserve any conservative rejection. Do not reduce BC/D or rescale inputs to turn a rejection into acceptance.

## Pair with instrumented evidence
| Obligation | This observer / required companion evidence |
|---|---|
| Thirteen shapes, D, combined products | Plan algebra only; compare actual preflight estimates and captured dtype/shape/nbytes. |
| BC/input/metadata expansion | Bounded request/client read; server ingress-before-buffer, decoded Document and metadata accounting require instrumentation. |
| Raw+manifest+shared reservations | Record lock-protected retained/reserved/pinned totals and allocation identities before/after publish/evict/reject. Positive HTTP cannot prove them. |
| Slow readers and eviction pins | Hold an ASGI send deterministically, then test cross-job admission/eviction. Charge raw AND immutable encoded responses until final reference release. Socket backpressure alone is not deterministic proof. |
| Read slot/workspace | Observe slot acquired before slice/list/encode, held through send-finally; second read429; send-error/disconnect releases exactly once. Instrument transient workspace independently of retained bytes. |
| Same-query reads | HTTP bytes/hash observed; companion getter/capture/solve counters must remain0 after capture. Per-frame encode may occur; steady byte-cache rules stay unchanged. |
| Ingress and failure recovery | Shared steady/transient ingress1 before buffering, solver1 independent; cross-route held-stream/error/submit tests, token owner and next successful request. |
| Memory/timing | Companion server current RSS, cumulative highwater, traced live/phase peak, native coverage and overlapping clocks. Client wall times include transport and polling; client allocations are not server RSS. |
| Provenance | Exact source/origin/byte manifests and instrumented patch hash; operator SHA alone is not verification. |

No private store access or guessed metric endpoints are used. Memory/lease/counter measurements are explicitly unavailable in this tool. A future instrumented runner must preserve exact production source, numerical gates and existing steady behavior; companion lifecycle/physics tests and supported-platform CI remain separate.

## Fresh-process instrumented companion
The separate `ci/tools/profile_transient_studio_resources.py` starts the actual source Studio server in a fresh child, runs the HTTP client in the parent and writes `instrumented-report.json` plus raw selected responses and `child.stderr`. It is opt-in, not wired to duplicate steady CI runs.

```sh
python ci/tools/profile_transient_studio_resources.py --source-root . --expected-commit FULL_CHECKOUT_SHA --document small-valid-transient.json --output records/transient-instrumented-small
python ci/tools/profile_transient_studio_resources.py --source-root . --expected-commit FULL_CHECKOUT_SHA --document near-valid-transient.json --reject-document over-budget-transient.json --output records/transient-instrumented-near
```

The checkout must match the full expected HEAD and have no tracked package modifications. Use the existing declared runtime dependencies. Missing imports/startup fail once with evidence; the tool does not install or retry. Every invocation uses a fresh server process and one real solve. Choose independently valid small/medium/near-preflight inputs separately; no synthetic replacement producer is installed. The optional over-budget document must elicit413 without another public solve; a429 is preserved as a failure of this expected actor, not capacity success.

Runtime wrappers count the actual public run, capture, public forwarded getters, strict/view encoding, pin/reserve/read-allocation publication and releases while calling originals unchanged. Imports of producer implementation modules are not used. Hooks and a scalar-only cache snapshot inspect the actual Studio transport, not a modeled store. The first phase runs the public observer (eleven frame GETs plus one H page). A separate phase sends eleven identical frame GETs and checks zero added run/capture/getter calls with eleven allowed view encodes. Counts across both phases must not be mistaken for one eleven-read workload.

For a bounded slow-reader control, an ASGI observation wrapper holds one actual frame body at send for at most30s. The parent sends another frame expecting429, then releases the first send and checks a subsequent read200 and cleared read pins/workspace. The wrapper does not edit response bytes or solver results. This is a deterministic transport hold, not natural socket throughput; eviction during a held history, disconnect/send exceptions, TTL expiry and all lifecycle actors remain separate tests.

Artifact schema `transient-instrumented-resource-v1`:
- `child_start`: PID, Python/platform/versions, baseline, pre-run module origins+SHA256.
- `requests`: parent HTTP timings/status/bytes/hash/raw-file references; total includes the public observer and instrumented phases.
- `phases`: before/after server memory, store and cumulative counter snapshots; repeated-read counter deltas; held-send/refusal snapshots.
- `store`: active/pending/reserved/retained/read-workspace, live/retired/snapshot counts, record pins, raw/manifest byte lists and allocation-ID byte inventory. IDs are process-local, not reproducible identifiers.
- `cleanup`: owned-server stop status, final snapshot and post-run origins. No global cache clear is performed; this is not a leak/TTL proof.
- `failure`, `exit_code`, `child_exit`, optional `forced_stop`: preserve refused/startup/timeout/failed attempts. A forced child stop invalidates acceptance; it is harness cleanup, not a server cancellation endpoint.

Current RSS is available on Linux through /proc; cumulative ru_maxrss is normalized on Linux/macOS and unavailable elsewhere. Traced live/phase peak starts after imports/server startup and may omit native allocations. Six native thread variables are fixed to1. Nested hook clocks overlap; the bounded256 hook events include observation overhead, while counters continue. RAM highwater, encoded bytes and logical retained accounting are different measurements. Origin hashes require comparison to exact Git/package bytes; declared HEAD alone does not prove every imported byte. Do not call these observations numerical or maximum-capacity acceptance.

## Retained Linux workload wrapper
Run once for the exact integrated checkout, in the configured Linux validation environment:
```sh
python ci/tools/run_transient_resource_workloads.py --source-root . --expected-commit FULL_CHECKOUT_SHA --output .validation/transient-resource-observation
```
Do not dispatch an extra workflow solely for this tool when an authorized validation run is already scheduled. Retain the entire output directory in that run's existing artifact.

The wrapper uses the exact `workload_plan()` choices: small n2/Nt3, medium n16/Nt8, near n85/Nt28 and the over-preflight n46/Nt96 actor (subject to the source's candidate policy). It writes standard uniform-source insulated2mm×1mm documents, initial300K, k2.5/c4/Q8, times2+0.01i, no boundary constraints. These are concrete resource inputs, not copied independent oracle expectations. D0 actual raw estimates and conservative D=N preflight estimates are both retained. The over actor exceeds the conservative preflight bound even though its D0 byte estimate is below16MiB; it is not an actual-D capacity rejection or exact cap+1 fixture.

Each of the three stages launches a separate profiler process and fresh actual-server child, with its own report/stdout/stderr. Only the near stage also submits the supplied over document and requires413/no extra solve. A failed stage stops the wrapper without retry or later stages. No source preflight, numerical tolerance, boundary data or policy limit is altered.

The companion asserts at completed capture that every one of the thirteen public array getter counters increases exactly1, and the first completed workload records all thirteen counts==1. Later identical-frame reads require zero getter/solve/capture increments; allowed on-demand encoding remains counted. `server_internal_measurements` explicitly describes companion instrumentation rather than inheriting the public observer's unavailable marker.

Retained paths:
- `.validation/transient-resource-observation/workload-summary.json` (`transient-resource-workloads-v1`): exact plan/input hashes, attempted/completed stage status, subprocess argv/exits/report hashes.
- `small-observation/instrumented-report.json`, `medium-observation/instrumented-report.json`, `near_raw_candidate-observation/instrumented-report.json`: fresh-process measurements.
- Stage stdout/stderr, child.stderr, original input/reject documents, selected response*.bin and terminal-state.json within those directories.
Use `--prepare-only --output NEW_DIRECTORY` to write documents/shape arithmetic without importing runtime dependencies; its success is preparation only. Runtime reports and artifact provenance must be independently audited before acceptance.
