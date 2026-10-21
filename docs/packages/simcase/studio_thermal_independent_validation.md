# Independent steady thermal Studio validation

[한국어](../../locales/ko/pages/packages/simcase/studio_thermal_independent_validation.md)

**At a glance**

- **What it checks:** the steady heat Studio HTTP routes (`/api/capabilities`, `/api/thermal/validate`, `/api/thermal/run`, job status and result) with the real public solver. Returned arrays are audited by independent element assets, not production assembly or refsol helpers.
- **Fixed gates:** a quadratic-source case on 8/16/32/64 needs temperature L2 order ≥ 1.8 and cell-flux L2 order ≥ 0.9; Gauss 8/10 error differences < 1%; finest relative domain flux L2 ≤ 2%; algebra and conservation 1e-10; SI invariance 1e-9.
- **Scope:** transient UI, mesh-only preview, a new solver, coupling, material extensions and saving endpoints are outside it. For a specific commit, see its CI run.

## Current scope and evidence

This checkout implements JSON-first steady thermal validation and execution,
typed HTTP results and independent acceptance tests. This document describes
the checks and their unchanged numerical criteria. Use the exact checkout's
CI logs and artifacts to establish observed source, installed, browser,
resource and platform results. Test definitions and preflight subsets do not
establish complete acceptance or a release.

See [the Studio guide](thermal_studio.md) for use and
[the development guide](https://github.com/fieldalgo/openphysics/blob/main/docs/development.md) for environment/distribution
requirements.

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

## Region documents

`tests/simcase/test_studio_region_acceptance.py` checks steady region documents
through the same HTTP routes, on the decoded wire arrays only. Studio adds no
physics, so the references are closed-form states that P1 reproduces exactly and
a direct `simcase.run` of the same document; mesh convergence of region documents
stays with the engine's [region tests](thermal_regions2d.md#validation). The
thresholds were fixed before the implementation; the measured values are from one
Linux run (Python 3.12, numpy 2.5).

| Case | Gate | Measured |
| --- | --- | --- |
| A1 two-layer slab, 30 x 10 mm, `layer_a` (x < 10 mm, k 45) and background (k 1.5), left 400 K, right 300 K, top and bottom insulated, no source, mesh 2 and 1 mm; q = 100/(0.01/45 + 0.02/1.5) W/m² | max nodal \|T - T_exact\| / 100 K <= 1e-9; every cell \|qx - q\|/q <= 1e-9 and \|qy\| <= 1e-9 q; a cell is `layer_a` exactly when its centroid has x < 0.01 m; summed left-side reaction = q x 0.01 m to rtol 1e-9 | 2.8e-15; 3.6e-14 and 2.9e-14; exact; 6.4e-15 |
| A2 the shipped steady example | summed source load = 5e6 W/m³ x the heater area from the wire mesh (rtol 1e-12); that area = `summary.regions.heater.area_m2` (rtol 1e-12); \|area/(π 4e-6 m²) - 1\| < 0.01; normalized heat-balance defect < 1e-10; outward = source (rtol 1e-10) | 1.1e-16; 0; 0.0064; 6.8e-12; 1.4e-11 |
| A4 transport identity, steady example | every wire array, `triangle_regions` included, equals the direct run's array after the JSON round trip (`np.array_equal`) | equal |
| A5 node cap | with `max_nodes` = the mesh's node count N the job finishes; with N - 1 it ends `mesh_limit_exceeded` and the solver is never called | as required |

The region path's protocol, limits, refusals and capture faults are in
`tests/simcase/test_studio_region_http.py` (criteria S1-S15).

## Reproduce and interpret results

From the repository root in the configured validation environment:

```sh
python -m pytest -q tests/simcase/test_studio_thermal_acceptance.py
```

For the separate shipped-script/page-handler Node checks:

```sh
node --test tests/simcase/studio_steady_thermal.cjs
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

Final acceptance requires completed exact source and
isolated-installed results, all physical/negative controls, distribution/origin
audits, resource/lifetime evidence and supported-platform checks.
Frontend revision/render ownership, actual Canvas behavior and measured
resource/serialization limits are separate evidence; this physics suite alone
does not certify them. A universal wheel or another OS pass is not platform
validation. Prior headless steady-boundary acceptance does not establish Studio
HTTP or rendering acceptance.
