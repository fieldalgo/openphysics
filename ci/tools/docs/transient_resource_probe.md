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
