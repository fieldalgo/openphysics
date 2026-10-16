# Independent steady thermal Studio acceptance

[한국어](locales/ko/pages/studio_thermal_independent_validation.md)

## Evidence level

Prepared against main `6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`.
The implementation at this base refuses heat in generic Studio endpoints and has
no dedicated steady thermal endpoint. This document defines prospective
acceptance, not an implemented endpoint or a measured pass. The separate
steady-boundary independent assets are required when the features are combined;
they are referenced, not duplicated or replaced here.

No Python parse/compile, collection, HTTP, solver, source/installed suite,
browser, Node or platform execution was performed during preparation.
Ten top-level test functions plus parameterized cases are definitions only.
Neither synthetic wire fixtures nor TestClient definitions prove rendering,
package installation or platform support.

## Scope and preserved boundaries

The target is additive JSON-first steady validation/run, followed by the actual
result mesh, nodal P1 temperature in K and triangle-constant flux in W/m².
The accepted design uses capabilities plus dedicated /api/thermal/validate and
/api/thermal/run routes, existing job/status/result routes and strict typed
steady result data. Generic optical behavior and generic heat refusal remain.
Transient UI, mesh-only thermal preview, a new solver, saving endpoints,
coupling and material extensions are excluded.

The tests use public Document/run/ThermalRunResult and HTTP. No production
assembly, private raw arrays or refsol helper supplies a correct answer.
The existing independent steady boundary Elements/model/audit/slab assets are
dependencies; the numerical oracle and its fixed thresholds remain unchanged.

## Physical expectations

The linear unit-square model has k=2, source0, left300 K, right outward g=2 W/m²,
h=4 W/(m² K), ambient290 K. T=300-7x and q=(14,0).
Integrated G=2,C=12 and inward thermostat reaction14 W/m give total outward0.
The coordinates may have a nonzero origin; x in the formula is relative to the
left edge. Equivalent m/mm/um documents retain the same physical SI arrays.

The quadratic slab has L=.03 m,H=.02 m,k=12.5,Q=100000 W/m³,left300 K,
right g=100,h=20,ambient290. T=a+b x-Qx²/(2k), where
b=(QL-g-h(a-Ta)+hQL²/(2k))/(k+hL). Source is60 W/m of depth.
Source-driven Robin-only and zero-h-with-opposite-positive-anchor families use
independently derived left/right outward flux and ambient data. Empty D is valid
for Robin-only v2, without a hidden fixed node.

Original element actions reconstruct K,H,fQ,G,B from coordinates and exterior
edge incidence. The returned field contract is:
rhs=fQ+B-G, C=HT-B, residual=(K+H)T-rhs, fixed reaction=residual,
free reaction0 and total outward=sum(G+C-reaction)=sum(fQ).
load_w_per_m is source only. A metadata or summary total never defines truth.

Fixed subdivisions8/16/32/64 preserve last-two temperature L2 orders>=1.8 and
cell-flux L2 orders>=.9. Gauss8/10 error differences must be<1%; finest relative
domain flux L2<=2%. Normalized algebra checks use1e-10 and SI invariance1e-9.
These are original gates, not adjustable Studio preview tolerances. A resource
refusal must be reported rather than converted into a smaller mesh or a skip.

## Wire contract and rejection controls

The draft binding expects studio-thermal-steady-v1 plus thermal.steady2d,
paired headless result/layout IDs, echoed job/result/revision/sequence,
an arrays mapping and copied summary metadata. Exact field bindings must be
checked against the explicit server candidate before execution. This draft is
not evidence that a particular implementation already uses these keys.

V1 carries exactly nine raw physical/geometry quantities; v2 carries exactly
thirteen. Numeric scalars must be finite real nonbool; connectivity/fixed IDs
must be safe integer, in range and sorted/unique where required. Shapes,
units and locations are exact. Temperature is(N,), flux(M,2), coordinates(N,2)
and triangles(M,3). The independent N5/M4 synthetic fixture detects node/cell
confusion without claiming a physical solver test.

Prepared negative payloads alter layout, W/m units, flux shape, NaN/infinity,
bool temperature, invalid/fractional indices, missing v2 fields and extra time
data. The client-side audit must reject them before a numerical comparison.
A second group corrupts an actual public result through a deliberate subclass
actor using captured public properties only. The server must produce job error,
has_result=false and no result payload. This is malformed-result injection,
not a substitute numerical implementation. Its run hook must be bound to the
actual server's public producer call after source review.

Absence of new headless boundary keys remains v1; presence of either mapping,
even empty, selects v2 with unchanged physics where appropriate.
The dedicated routes refuse optical/transient inputs and malformed envelopes;
generic validate/mesh/run retain heat refusal. Existing unrelated optical tests
remain authoritative. Strict duplicate/NaN/unknown/counter input rejection is
separate from headless physical validity.

The public-export AST test inspects Studio Python consumers: imports from
simcase must be in __all__, no direct galerkin/refsol/private simcase numerical
imports or _raw_arrays calls. Runtime resource retention/peak measurements and
frontend revision/render truth tables are separately required evidence; this
physics suite does not certify them.

## Execution and outstanding work

After exact server/adapter binding and combination, run from repository root:

```sh
python -m pytest -q packages/simcase/tests/test_studio_thermal_acceptance.py
```

Positive HTTP tests use the actual public solver, bounded polling and independent
returned-array audits. They do not read a summary to generate expected physics.
The suite does not duplicate the whole repository run; coordinated exact CI
must preserve existing steady boundary/transient/generic Studio gates.

Still unverified: exact wire names and producer injection point, execution and
collection, malformed-result behavior, physical HTTP convergence, installed
origin/archive consumption, actual Canvas behavior, Windows/macOS and final
integration. Existing steady-boundary C11/CLI/installed acceptance is a separate
feature result and must be confirmed from its exact CI logs.

## Early exact server binding

Source review now binds these tests to server/adapter commit
533c5e8c3f50d05f52323588e81b4997500e00e5. The worker calls public server.run;
the malformed-public-result injection point is therefore confirmed.
The wire uses top-level display_length_in_m, arrays, summary and identity
(kind,job,result_id,client_revision,request_seq). Nested coordinates metadata
is obsolete and rejected by the independent consumer.

The consumer now checks finite positive display scale against the declared
m/mm/um or explicit in_m length, exact metadata field sets and echoed status/
result identities. Additional malformed cases cover boolean/zero/nonfinite
display scales and a declaration/scale mismatch. The malformed-layout result
actor changes summary.field_layout as well as the public field_layout property:
the early adapter reads the summary pair, so changing only the property would
not exercise the intended rejection. This was a test-definition correction;
neither producer guards nor physical gates changed. A missing UNITS import
introduced during binding was found statically and corrected before execution.

The required resource policy evicts oldest terminal done/error records under
admission/publication pressure, preserves active and optical jobs, makes evicted
IDs404, and treats300s TTL as a maximum retention time. The original meshes
8/16/32/64 must run sequentially without store reset, reduced meshes, TTL waits
or skips. Existing short polling waits observe real asynchronous job progress;
they are not retention workarounds. run_enabled=true advertises valid configured
policy and public API availability, not measured performance.

The early533 source still lacks run_enabled and refuses admission after two
retained terminal records until TTL expiry; a producer follow-up is expected.
No acceptance is granted to that early resource behavior and the tests do not
hide it. All exact HTTP/physics/installed/CI results remain unexecuted here.
Later producer changes require a separate source-delta review and exact combined
CI. The separate writer-fixture correction does not enter this branch.

## Follow-up exact binding decision

Static review of f8506b7490b52105c37a55e656dc8f23baa98647 supersedes the
early533 pending-resource observations above. Server source is unchanged
(blob6c750aa452ae78a21f5a470bc0c1d6fb5aaeee0b); the adapter is now
blob4fd5633340ca945aff9c3fb878aeb40a2f6c106e.

The adapter captures public result_format/field_layout and requires equality
with the summary pair, preserves the same top-level display factor and
arrays/summary/identity, checks array shape/dtype/finite bounds before copies,
and publishes only strict encoded data. The existing malformed layout, unit,
shape, nonfinite, bool and index actors still target the consumed values.

Capabilities now expose run_enabled from public result API availability under
the validated resource configuration. Admission/publication make room by evicting
oldest released done/error records; active leases are excluded. Thermal records
are separate from optical records, TTL remains a maximum and evicted IDs404.
This statically resolves the early two-terminal admission issue without resets,
TTL waits, reduced mesh sequences or skipped tests.

No further independent test or physical-gate change was needed for this source
binding. Static scope is approved with no confirmed binding blocker found.
Actual HTTP/source/installed execution, malformed-result rejection and resource
behavior still require exact integrated CI. This is not a measured performance,
browser or platform acceptance.

## Landed steady-boundary and resumed Studio review

The steady-boundary independent oracle and cases on main
49ff59874af3c5140d0e8126b1feb18964953e7e have blobs
8957c5663e4dfacb62331c46c215f5872732c6bc and
963e6850099c1b5ffe458c9bd31b373327546f04, respectively: the previously reviewed
mathematics, fixtures and gates are unchanged. Their imports are now present
on the landed base rather than an unpublished dependency.

Reviewed server/adapter submission c762c4e5fdb9700978a24f639e694630477b8679:
server remains blob6c750aa452ae78a21f5a470bc0c1d6fb5aaeee0b; adapter is
blob6ecec32a623d7f92ba6f4543d46b3fb1d3bd8170. Its stricter log/error status
byte accounting does not alter physical payload fields or the public run hook.

The sequential HTTP mesh loop fully receives and audits each current result
before submitting the next. Eviction of older terminal results therefore does
not change the expected arrays or require fetching old job IDs. n64 uses4225
nodes/8192 cells, within configured10201/20000 limits; v2 has83340 raw scalars
for the quadratic left-side D=65. These are static size facts, not measured
encoding capacity or peak-memory guarantees. Admission/publication pressure
may evict old released done/error records before300s; active/optical records
remain separate. No reset, TTL sleep, skip or reduced mesh was introduced.

Static inspection found a gap in the independent consumer: Python equality
would accept float metadata dimensions such as5.0 as equal to integer5.
The consumer now explicitly requires list dimensions of exact int type, excluding
bool, and checks mapping forms, unit keys and safe integer/nonempty response
identity. Five new malformed controls cover float/bool dimensions and float/
bool/empty identities. The previous fifteen malformed-wire controls and six
malformed-public-result actors remain unchanged; the physical expected values,
four meshes and every numerical tolerance remain unchanged.

Conditional static approval: no confirmed main49ff/Fc762 binding blocker found.
The new metadata assertion gap was a consumer test-definition issue, not a
confirmed production defect. No Python parse/pytest/HTTP/solver/installed/browser
or platform execution was performed. Exact combined Studio source/installed
CI, including real repeated runs and all negative controls, is still required.
