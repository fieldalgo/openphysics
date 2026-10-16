# Independent steady thermal Studio validation

[한국어](locales/ko/pages/studio_thermal_independent_validation.md)

## Current scope and evidence

This feature checkout implements JSON-first steady thermal validation and
execution, typed HTTP results and independent acceptance tests. The reviewed
candidate is `14063f8a010639ca016d9d8b5e864e9e2339d366` (PR11), based on main
`6e9be99a10fba77d329063da973401f26d4ed0b5`. This is a candidate validation
contract, not a claim that Studio has landed on main.

Reported CI status: the Studio preflight step succeeded; final exact-candidate
source and isolated-installed acceptance are still pending. No complete
numerical, browser, resource or three-platform acceptance is claimed here.
This documentation update ran no tests. A preflight subset, synthetic fixture,
TestClient check or Node VM result cannot substitute for the remaining evidence.

See [the Studio guide](thermal_studio.md) for use and
[the validation guide](../../../ci/docs/README.md) for environment/distribution
requirements. Intermediate implementation reviews are historical and do not
define the current runtime or its acceptance status.

## What the HTTP suite checks

`test_studio_thermal_acceptance.py` consumes public
`Document`, `run`, `ThermalRunResult` and the actual HTTP application.
It exercises `/api/capabilities`, `/api/thermal/validate`,
`/api/thermal/run` and the existing job status/result routes.
Generic optical behavior and generic validate/mesh/run heat refusal remain.
Transient UI, thermal mesh-only preview, a new solver, coupling, material
extensions and saving endpoints are outside this scope.

Positive HTTP cases use the real public solver and audit returned arrays with
the existing independent `Elements/model/audit/slab` assets. Those assets
derive triangle gradients, original stiffness actions and consistent exterior
edge integrals without production assembly or refsol helpers as truth.
Summary metadata is checked for consistency; its totals never generate the
expected physics.

## Analytic cases and unchanged gates

- **Linear additive cooling:** unit square, k=2 W/(m K), Q=0,
  left300 K, right g=2 W/m², h=4 W/(m² K), ambient290 K.
  With x relative to the left edge, T=300−7x K and q=(14,0) W/m².
  Integrated prescribed G=2, convective C=12 and inward thermostat reaction14
  W/m give right outward14, left thermostat outward−14 and total outward0.
- **Quadratic source:** L=.03 m, H=.02 m, k=12.5 W/(m K),
  Q=100000 W/m³, a=300 K, right g=100, h=20, ambient290.
  T=a+bx−Qx²/(2k), where
  b=(QL−g−h(a−Ta)+hQL²/(2k))/(k+hL). Integrated source is60 W/m of depth.
- **Robin-only and h=0 control:** the independent slab families derive ambient
  values from left/right outward fluxes. Empty Dirichlet arrays are valid for
  v2 with positive Robin anchoring; h=0 on one side retains the opposite
  positive anchor. No hidden fixed node is introduced.
- **SI equivalence:** m/mm/um documents describe the same physical rectangle,
  including origin(.1,.2)m. Coordinates stay in metres and field units do not
  change with the display length unit.

The oracle reconstructs K,H,fQ,G,B and checks
`rhs=fQ+B−G`, `C=HT−B`, `residual=(K+H)T−rhs`,
fixed reaction=residual, free reaction0 and
`sum(G+C−reaction)=sum(fQ)`. `load_w_per_m` remains source-only.
Rates are W/m of depth, not W or mechanical N/m.

The quadratic HTTP case runs subdivisions **8/16/32/64 sequentially**.
The last two intervals require temperature L2 order **>=1.8** and cell-flux L2
order **>=.9**. Independent Gauss8/10 error differences must be **<1%**;
finest relative domain flux L2 must be **<=2%**.
Normalized algebra/conservation checks retain **1e-10** and SI invariance
**1e-9**. These gates and fixtures are unchanged. Domain flux L2 is distinct
from a boundary-normal-gradient measurement.

## Typed wire and negative controls

The wire uses `payload_format="studio-thermal-steady-v1"`,
`kind="thermal.steady2d"`, paired headless result/layout IDs,
top-level `display_length_in_m`, `arrays`, `summary` and
`job/result_id/client_revision/request_seq` identity.
Nested `coordinates` metadata is not accepted.
The display factor must be finite positive and agree with the declared length;
`run_enabled=true` means configured policy/public API availability, not a
performance guarantee.

V1 has exactly nine raw quantities: nodes, triangles, temperature, cell flux,
source load, reaction, residual, Dirichlet IDs and prescribed temperatures.
V2 adds `prescribed_outward_load_w_per_m`, `ambient_load_w_per_m`,
`convective_outward_w_per_m` and `system_rhs_w_per_m`, giving thirteen.
Absence of new boundary keys retains v1; presence of either mapping, even empty,
selects v2. Empty D is accepted only where the version/physics contract permits.

The consumer checks exact field sets, shapes, units and locations:
temperature(N,), flux(M,2), nodes(N,2), triangles(M,3) and fixed arrays(D,).
Numeric values must be finite real nonbool. Connectivity/fixed IDs are safe
integers in range; fixed IDs are sorted unique. Metadata dimensions are exact
integer lists, not equal-valued floats/bools. Response identity is typed and
matched to the accepted request.

Twenty malformed-wire controls cover layout/unit/shape, NaN/infinity/bool,
invalid/fractional indices, missing/extra fields, display scale/declaration,
obsolete coordinates and metadata/identity types. The independent N5/M4 fixture
tests parser distinctions and is not a solver result.
Six separate actors corrupt an actual public result's layout, units, shape,
finite values, dtype or indices through captured public properties.
The worker's public `server.run` binding is the injection point.
Required outcome: job error, `has_result=false`, result request409;
no malformed payload is published. These actors are not replacement solvers.

Dedicated routes reject unsupported optical/transient documents and malformed
envelopes, including duplicate keys, nonfinite JSON, unknown keys and invalid
counters. The public-export AST check rejects private numerical imports and
`_raw_arrays` calls in Studio consumers.

## Reproduce and interpret results

From the repository root in the configured validation environment:

```sh
python -m pytest -q packages/simcase/tests/test_studio_thermal_acceptance.py
```

For the separate shipped-script/page-handler Node checks:

```sh
node --test packages/simcase/tests/studio_steady_thermal.cjs
```

HTTP tests poll real asynchronous jobs with a bounded timeout. Each current
result is fully received/audited before the next run. Admission/publication may
evict oldest released terminal done/error records;300s TTL is a maximum,
active and optical records are preserved and evicted IDs return404.
Do not reset the store, wait out TTL, reduce meshes or skip a resource refusal.
Short status polling waits are not retention workarounds.

Record the exact commit, command/exit, environment, failures/skips, original
convergence JSON and source/installed origins/hashes. Review the coordinated
exact CI rather than start duplicate whole-suite runs. Keep existing
steady-boundary, transient and generic Studio gates.

Still required for final acceptance: completed exact source and
isolated-installed results, all physical/negative controls, distribution/origin
audits, resource/lifetime evidence and supported-platform checks.
Frontend revision/render ownership, actual Canvas behavior and measured
resource/serialization limits are separate evidence; this physics suite alone
does not certify them. A universal wheel or another OS pass is not platform
validation. Prior headless steady-boundary acceptance does not establish Studio
HTTP or rendering acceptance.
