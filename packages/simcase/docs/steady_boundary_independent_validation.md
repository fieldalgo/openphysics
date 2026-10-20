# Independent steady boundary headless acceptance

[한국어](locales/ko/pages/steady_boundary_independent_validation.md)

## Status and scope

The acceptance code was prepared from main
`6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`, before the boundary extension was
integrated. Fixed expectations, subsequent exact-source binding reviews and
supplemental direct-path measurements are recorded separately below. These are
bounded evidence snapshots, not a live CI status report. Consult the exact
checkout's CI logs and artifacts for full source, installed and platform results.

The tests require the boundary contract; no fake implementation, skip or weakened
tolerance substitutes for it. The original preparation environment could not run
Python parsing, pytest, solvers or installed consumers. Later direct-path
measurements do not retroactively establish that original suite's execution.
Existing transient and standalone Robin engine tests and tolerances are unchanged.

## Independent mathematics

For `q=-k grad(T)` and outward `q.n=g+h(T-Ta)`:
`A=K+H`, `rhs=fQ+B-G`, `r=A T-rhs`,
`C=H T-B`. Reaction equals fixed-node residual, zero on free nodes.
Signed total outward heat is `sum(G+C-reaction)=sum(fQ)`, in W/m of depth.

The NumPy-only oracle derives triangle area and P1 gradients directly from
coordinates and connectivity, applies original stiffness element actions and
assembles source integrals. Exterior edges come from one-owner triangle incidence,
not producer boundary tags. For edge length ell it independently uses
`H_e=h ell [[2,1],[1,2]]/6`, `G_e=g ell [1,1]/2`,
`B_e=h Ta ell [1,1]/2`. No production/refsol assembly, summary or solution
creates an expected answer. Returned geometry is audited against the physical
rectangle; this does not independently certify arbitrary topology.

## Fixed exact cases and gates

- Linear: unit square, k=2, Q=0, left300 K, right g=2 W/m²,
  h=4 W/(m² K), Ta=290 K. T=300-7x K, qx=14 W/m².
  Right removal14 W/m, left thermostat outward -14 W/m, total0.
- Quadratic: L=.03 m,H=.02 m,k=12.5,Q=100000 W/m³,a=300 K,
  g=100,h=20,Ta=290. T=a+b x-Q x²/(2k), with
  b=(QL-g-h(a-Ta)+h QL²/(2k))/(k+hL). Source integral60 W/m.
- Robin-only: same geometry/k/Q, a=300,b=-10; independent left/right
  outward fluxes k b and QL-kb determine ambient temperatures.
  Empty fixed arrays are valid. A zero-h left edge with matching g retains
  the positive-h right anchor.
- m/mm/um encode the same SI rectangle, including nonzero origin (.1,.2)m.

Mesh subdivisions are 8,16,32,64. Last two interval temperature L2 orders >=1.8
and element-flux L2 orders >=.9; finest relative flux error <=2%. Independent
Duffy-product triangle quadrature degrees8 and10 must differ by <1% of error.
Exact linear/algebraic checks use normalized1e-10; SI invariance1e-9.
No threshold may be adjusted to match a producer result. Weak integrated rates
can be exact at roundoff and are checked algebraically, without demanding
meaningless monotonic convergence.

## Public adapter and saved consumer

The cases exercise public Document/run/save and separately CLI subprocesses,
using argv, python -I, temporary external working directories and UTF-8.
Numeric fields use np.load(...,allow_pickle=False) and context-managed handles.

The nine legacy fields retain their meanings; v2 adds prescribed_outward_load_w_per_m,
ambient_load_w_per_m, convective_outward_w_per_m, system_rhs_w_per_m.
Their units, shapes, locations and metadata identifiers are checked.
load_w_per_m remains fQ, not rhs. Absent new keys require v1 IDs;
presence of either new mapping, even empty, requires v2 IDs.
Caller document mutation must not relabel the copied calculation, and changes
to result.doc must prevent summary/save. fields=false must omit NPZ.

Strict inputs cover malformed/new keys, bool/nonfinite data, negative h/ambient,
h0 with invalid ambient, missing Robin member, compatible/incompatible pure
Neumann and zero-h-only anchoring, and actual two-fixed-endpoint overlap even
when side names differ. One fixed corner retains its complete edge load.
CLI output reuse must fail while preserving existing bytes.

Wrong-physics diagnostics distinguish sign(G), omitted/negative H, omitted B and
consistent versus lumped H using a nonconstant edge probe. Saved-result actors
target load-as-rhs, missing B, sign(G) and geometry-unit corruption. These are
prepared controls; no runtime rejection is claimed before execution.
Additional exact-candidate metadata/summary and negative controls will be
reviewed against the published implementation without changing the oracle gates.

## Reproduction and remaining checks

From repository root, after the exact implementation is combined:

```sh
python -m pytest -q packages/simcase/tests/test_steady_boundary_independent_validation.py
python -I /external/steady_boundary_independent_consumer.py --expected-installed-root /wheel/venv --expected-module-hashes /external/source-hashes.json
```

External paths are placeholders, not fixed machine paths. Copy the oracle, cases
and consumer from the checkout's tracked files to a directory outside it. The
mandatory nonempty UTF-8 hash mapping includes simcase.schema,
simcase.steady_boundary_contract, simcase.thermal, simcase.runner, simcase.cli
and galerkin.thermal. The consumer rejects origins
outside the expected installed root or byte mismatches, prints identities and
counts, and fails if any test is skipped.

Source/isolated-installed, exact CI, Windows/macOS, whole regression and main
integration are all unverified for this new scope.
The release coordinator owns CI integration and full regression scheduling.

The prepared suite now declares eleven test methods (not collected passes). It also
includes omitted reference-offset, fixed-corner-load removal, thermostat-only
total-outward, and saved format/layout/unit/object/nonfinite actors. Source review
alone has not executed any of these controls.

## Exact implementation binding review

Static review read schema/contract at 4bd15626fe37c306eb6265f1db1b308c6b580460
and runtime at 56238cd76ab09e422344ef54e89d68f5a1aa579e. These are parallel
submissions, not an executed combined checkout. The numerical engine remains
thermal.py blob4633e03953d8f6369bdf0e7398d2ebd85b2b4684.

The observed names match the independent consumer. Runtime thermal.py539–598
validates/copies the document, maps the five boundary keywords, captures inputs
before the solve and checks the four returned boundary arrays. Lines600–619
separate source, prescribed outward, convection and thermostat rates; total
outward includes all three boundary contributions. Lines430–472 allow empty
fixed indices for v2 and retain thirteen finite numeric fields. Lines352–386
capture copied canonical data before later validation; ordinary document edits
fail before defaults can be restored. Lines498–529 publish the adopted v2
metadata and original model snapshot. No confirmed production blocker was
identified by this source review.

Contract validation distinguishes absence from empty-map presence, h0 from a
positive Robin anchor, and one fixed endpoint from a fully fixed natural edge.
Its edge identity checks all six side-pair intersections and derives selected
Dirichlet nodes from actual exterior edge endpoints.

The engine directly implements rhs=fQ+B-G, stable shifted Robin offsets,
C=H*increment-shifted_B, original fixed-node reactions and both original
normalized1e-10 guards. The independent oracle still uses original absolute
mathematical forms and analytic solutions rather than these helpers as truth.
Source inspection does not establish floating-point accuracy.

A test-interface defect in the initial snapshot test was corrected: Document
does not implement item assignment; mutation now uses doc.data["name"] and
result.doc.data["name"]. The original expectation and all gates are unchanged.
No numerical reproduction, source/installed pass or CLI execution is claimed.
Actual combined-candidate CI and original diagnostic arrays are still required.

## Supplemental direct-path measurements

A separate source composition using schema4bd15626fe37c306eb6265f1db1b308c6b580460,
runtime56238cd76ab09e422344ef54e89d68f5a1aa579e and the unchanged historical
independent Robin oracle was exercised in Python3.12.14/NumPy2.3.5/SciPy1.17.0.
It used actual Document.from_dict and direct run_thermal while bypassing package
root initializers. This is neither the official new Elements/eleven-case suite
nor public root-runner/CLI/installed acceptance.

Ten logical groups covered linear n2, constant Robin-only empty D, legacy versus
explicit-empty v2, mm/um saves and quadratic meshes8/16/32/64. An initial run
completed all ten solves, then failed reporting a NumPy boolean to JSON (exit1).
Only serialization was repaired; the final ten-group run exited0 with empty
stderr in3.050654208999731s. Including an earlier probe there were21 solve
invocations, not21 independent tests.

C audited the original archive, all14 source SHA256/Git blob identities and
eight saved artifact hashes, then independently decoded numeric NPZ arrays and
reintegrated them without running a new solve. Direct raw signs give linear
G=2,C=12,R=14 W/m, hence right outward14, left thermostat outward-14 and
total approximately0. Every quadratic raw source sum is60 W/m; the finest
total outward differs by about1.04e-11 W/m. Componentwise rhs=fQ+B-G agrees.

Reported last-two orders are T1.9988550488612653/1.999656433643703 and
flux.9994821862440284/.9998446426372463. Separate raw-array quadrature gives
T1.9988550488799535/1.9996564337200657 and
flux.9994821862440356/.9998446426372037. Both satisfy fixed1.8/.9.
Reported Gauss8/10 maximumrelative8.650446906980553e-11 and independent
reintegration1.3590626820738625e-11 both satisfy <.01.
Finest dimensional domain flux L2 is .3314417618241207;
exact analytic flux norm35.166282766624136 gives relative
.009424987111196404 (<.02). This is domain relative L2, not a boundary-gradient
measurement. Supplemental normalized diagnostic5.6282662146672146e-14
uses its disclosed constituent-sum scale and does not replace official gates.

These data support only the ten direct-path groups. Their origin is0 rather
than this suite's (.1,.2)m, linear/units use n2 rather than n8 and Robin-only
is constant rather than the additional nonzero-source/h0 families.
Snapshot checks cover caller-name isolation and result-name refusal, not all
value mutations. No new wrong-actor, fields=false, CLI, public runner, isolated
installed or platform acceptance follows. The exact integrated candidate
still requires its own original suite and CI. No gate was changed.
