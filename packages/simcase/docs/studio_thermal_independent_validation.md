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
