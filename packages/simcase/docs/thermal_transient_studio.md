# Transient heat in Studio

[한국어](locales/ko/pages/thermal_transient_studio.md)

## Availability and scope

This checkout implements the transient Studio interface with a dedicated
capability, HTTP validation/run and manifest/frame/history routes, and shipped-page
time/field/H/V controls. The capability advertises supported formats, views,
routes and configured limits. `run_enabled` reflects runtime availability and
valid limit configuration, not measured capacity or performance. Implementation
and validation are distinct: inspect the exact checkout's CI results and artifacts
for observed runtime, installed, browser, resource and platform scope. Configured
limits remain `candidate-unmeasured`; this description asserts no new pass count
or release.
The [headless transient guide](thermal_transient2d.md) defines existing input and
saved-history behavior; [steady Studio](thermal_studio.md) remains separate.

The contract uses the existing fixed homogeneous rectangle/P1 engine,
consistent mass/backward Euler, constant k/c/source and explicit requested times.
Initial data are scalar or affine; side Dirichlet values are constant or sampled
at those times, otherwise insulated. Initial/BC agreement is checked without
projection. Finite negative K is retained without clamp or DMP/positivity promise.
There is no new solver, interpolation, downsampling, transient flux/Robin,
arbitrary geometry/material expansion, restart, coupling, cancel/delete/save or
NPZ endpoint. A view change never reruns the solver or modifies its document.

## User workflow

After installing matching runtime packages and the optional Studio extra, start
from the repository root:

```sh
python -m pip install -e "packages/simcase[studio]"
python -m simcase.studio --no-browser
```

Open the printed localhost address. Startup alone does not enable an absent or
unsupported transient capability.

1. Open/paste complete transient JSON and explicitly apply it. Preserve original
   text for strict duplicate-key/finite-JSON validation. Declare length, K and s,
   positive k/c, initial field, BC and increasing nonnegative time_s. Nonzero
   first time is valid. Dirty/invalid text invalidates old validation and results.
2. Validate the current input through the dedicated transient capability. HTTP200
   is valid only with body ok=true. Run revalidates, takes a captured snapshot and
   uses public simcase APIs; no optical mesh-only preview.
3. Run explicitly. After completion, accept a typed manifest containing the actual
   static mesh, exact requested times and descriptors. The default selection is
   the final requested integer index Nt-1, not time0 or a rounded-time lookup.
4. Select temperature K or cell qx/qy/magnitude at exact time_s[i]. Current-frame
   min/max and units are labelled. The same colour at different frames need not
   mean the same absolute value. No global-extrema scan/API is introduced.
5. Explicitly open H or V history pages, at most16 rows. Pages use half-open
   [start,stop) integer indices; no automatic next-page fetch or silent clipping.
   Selected-time/field changes request data only, without solving again.
6. On a current view error, clear wrong-time field/hover/labels and show an explicit
   retry. A new solve requires explicit new run. Edits/import/new run/type switches
   invalidate old views; stale success/error/finally cannot change current state.

The initial UI exposes T/q and H/V only, not rate spatial fields or a rate table.
Original rate API semantics are preserved for independent consumers. No animation,
invented substeps or nearest-time extrapolation is implied.

## Time axes, units and physical meaning

N nodes, M triangles, Nt requested times, D unique prescribed nodes:

| Quantity | Shape | Axis / unit |
|---|---|---|
| nodes_m, triangles | (N,2), (M,3) | static / m, integer CCW connectivity |
| time_s | (Nt,) | requested times / s |
| temperature_k | (Nt,N) | time_s / nodal K |
| heat_flux_w_m2 | (Nt,M,2) | time_s / cell-centroid W/m² |
| source_load_w_per_m | (Nt,N) | time_s / nodal W/m of depth |
| reaction_w_per_m, residual_w_per_m, storage_rate_w_per_m | (Nt-1,N) | time_s[1:] / nodal W/m |
| heat_content_j_per_m | (Nt,) | time_s / H in J/m |
| quadratic_functional_jk_per_m | (Nt,) | time_s / V in J K/m |
| dirichlet_node_ids | (D,) | static / sorted unique integer IDs |
| dirichlet_temperatures_k | (Nt,D) | time_s / K; D0 gives (Nt,0) |

At index0, T, flux and diagnostic source f0 exist; reaction/residual-step/storage
rate do not. For i>=1, the rate row is i-1 over [time_s[i-1],time_s[i]].
Initial-rate API requests refuse422 rather than inventing a zero.
For [2,2.03,2.1,2.4,3], default i4 means exactly3s; i2 means2.1s.
Nearby times with identical formatted labels remain different indices.

```text
q = -k grad(T)
storage_n = M*(T_n-T_(n-1))/dt_n
residual_n = storage_n + K*T_n - source_n
reaction_n = residual_n on fixed nodes; zero on free nodes
(H_n-H_(n-1))/dt_n = sum(source_n)+sum(reaction_n)
outward_D,n = -sum(reaction_n)
H_n = 1^T*M*T_n            [J/m]
V_n = .5*T_n^T*M*T_n       [J K/m; not stored heat]
```

Reaction is inward heat injection; outward_D is the thermostat contribution,
not a direct integral of element flux. H uses constant-c sensible content with
zero at0 K, not universal enthalpy. V is not stored heat or mechanical energy.
No general H/V monotonicity is guaranteed. Multiplying H/rates by physical depth
in metres yields J/W, but depth conversion is outside this UI.
Raw coordinates remain metres; axes use top-level display_length_in_m and the
document length declaration. Temperature is nodal linear P1, flux flat per cell,
global +y upward; arrows are view scaling. Derived overflow refuses the view.

## Typed reads and response ownership

Transient result/layout IDs are thermal.transient2d-result-v1 and
thermal2d-transient-p1-node-cell-v1. Manifest/frame/history use separate wire IDs:
studio-thermal-transient-v1, studio-thermal-transient-frame-v1 and
studio-thermal-transient-history-v1. No optical or steady-layout fallback.

The manifest contains static mesh, top-level time_s, immutable summary, default
last index and all13 field descriptors: full shape, unit, location, axis,
available_views, initial_available and ui_supported. Only T/q/H/V are initial UI
fields. Frame carries one captured row; H/V frame shape is scalar[], page shape
[rows], vector page shape[rows,M,2]. Static mesh is not repeated per frame.

Frame/history require result_id and exact integer index or range. Run counters
client_revision/request_seq remain separate from view frame_seq. Only matching
job/result/revision/run sequence/field/index-or-range/frame_seq may commit.
Manifest URL templates must be relative same-origin accepted-job paths; use
safe query substitution, never scheme/host/fragment/traversal.
Identical complete queries, including frame_seq, encode identical data/bytes.
Transient reads may encode captured immutable rows on demand, with no producer
getter reread or re-solve and no encoded-frame cache. Existing steady immutable
encoded-response behavior is unchanged.

## Concurrency, memory and recovery

| Limit | Contract |
|---|---|
| Shared thermal ingress1 | Steady+transient validate/run acquire before body buffering/Document copies; excess429, no waiting queue |
| Shared solver1 | Independent admission; current active solve is not cancelled by client edits |
| Shared transient read1 | Frame and history, including H/V, acquire before slicing/list/JSON; excess429, hold through send-finally |
| Retention | Shared terminal2, retained32MiB, oldest released done/error reclamation; active/optical preserved; TTL maximum300s |
| Candidate byte/time caps | request1MiB, raw16MiB, manifest4MiB, frame/page4MiB, Nt128, N10201/M20000, page16 |

Limits are candidate-unmeasured policy, not measured capacity, RSS or timing
guarantees. Shared ingress can explicitly refuse concurrent steady requests;
optical routes remain unchanged. Permits release on success, schema/stream errors,
disconnect/cancellation and all exceptions; stale duplicate release cannot free
a later owner. No hidden retry queue or artificial solver cancellation.

Readers pin immutable raw backing or encoded responses through send completion.
Logical eviction does not release the charge while a slow client still references
it. Same allocation references are deduplicated; distinct copies count.
Read output/workspace reservations are separate from retained logical data.
If pinned+retained+reservations cannot fit, refuse429, not oversubscribe.
Full solver histories, sparse factors, decoded Documents, summary/capture copies
and HTTP buffers remain extra memory. Bounded frame transfer is not streaming.

| Error | User meaning / recovery |
|---|---|
| validate200 ok=false; run400 | Invalid current document; correct it, no old snapshot run |
| malformed400/media415 | Fix JSON/envelope or application/json; no job |
| resource413/429 | Explicit request/ingress/solver/read/budget refusal; no automatic retry or mesh/time reduction |
| pending409 / stale409 | Not ready or wrong result identity; never silently substitute another result |
| range/initial-rate422 | Invalid index/range or no initial rate; no rounding/fabricated data |
| evicted/expired/unknown404 | Result unavailable, possibly before TTL; explicit new run only |
| unexpected500/invalid payload | Failed current operation; no partial successful history or optical fallback |

Error echoes use only validated safe counters and authoritative accepted identity.
Untrusted stale IDs never replace accepted IDs; unknown404 does not invent them.
Errors are bounded plain text. Expiry, view retries and client abort do not delete
global jobs or grant multi-tenant authentication/isolation.
Headless saving remains separate: options before run, document snapshot bound,
fresh caller-owned target, incomplete marker/summary-last, no hostile race or
crash rollback guarantee. See the headless guide; no Studio save API is added.

## Reproduction and validation checklist

These are required checks, not results produced by this document. Separate
implementation, actual test execution, exact integrated CI, main landing and release.

- Uniform headless control k2.5/c4/Q8/T0=300 at t0=0 expects300+2t.
  At t0=2 with T0=300 it is300+2*(t-2); global300+2t requires T0=304.
- Nt2, nonuniform/nonzero times, first/last, D0, affine and sampled BC, initial
  agreement32eps/no projection, signed K/no clamp, exact descriptor/ID/time axes.
- Independent public numerical/oracle and original n8/16/32/64 final-two
  L2 temperature order>=1.8, flux>=.9, normalized residual/balance1e-10, SI1e-9;
  retain original temporal/quadrature/negative controls.
- Dirty/duplicate JSON, validation200 failure/run400, reverse frame/page replies,
  same-index retry, field changes, hidden tabs, stale success/error/finally,
  explicit429 recovery, no accidental solver rerun/global job deletion.
- Distinct N/M synthetic indexing fixtures are display/axis checks, not PDE,
  browser, resource or complete13-field acceptance.
- Cross-route held-stream ingress, all failure releases, slow send/disconnect
  pins, eviction, byte accounting and steady cached-byte preservation.
- Exact source/installed origins, archive assets/bytes/links, shipped Node,
  actual browser/HTTP and Linux/macOS/Windows outcomes. Node/HTTP are not actual
  Canvas evidence; Linux or universal wheels do not establish other OS passes.

For exact validation commands and artifacts use the
[development guide](https://github.com/fieldalgo/openphysics/blob/main/docs/development.md).
Cross-package/root links require network access. Missing runs remain unverified;
do not convert unavailable tools, declared fixtures or prior steady passes into
transient acceptance.
