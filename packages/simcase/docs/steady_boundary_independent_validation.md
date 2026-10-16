# Independent steady boundary headless acceptance

[한국어](locales/ko/pages/steady_boundary_independent_validation.md)

## Status and scope

Acceptance code prepared from main `6d6eac56d1dddb8bdfe3f23d6db78d674487a42b`.
This report describes fixed expectations, not measured passes. The boundary-enabled
schema/runtime implementation has not yet been bound to an exact combined candidate.
The current base supports legacy Dirichlet-only steady documents. The new tests
intentionally require the approved boundary contract; no fake implementation,
skip or weakened tolerance substitutes for that implementation.

No Python parsing, pytest, solver, installed consumer or platform execution was
available during preparation. Source review is not numerical acceptance. Existing
transient and standalone Robin engine tests and tolerances remain unchanged.

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
and consumer from verified source archives. The mandatory nonempty UTF-8 hash
mapping includes simcase.schema, simcase.steady_boundary_contract, simcase.thermal,
simcase.runner, simcase.cli and galerkin.thermal. The consumer rejects origins
outside the expected installed root or byte mismatches, prints identities and
counts, and fails if any test is skipped.

Source/isolated-installed, exact CI, Windows/macOS, whole regression, source
archive inclusion and main integration are all unverified for this new scope.
The release coordinator owns archive/CI integration and full regression scheduling.

The prepared suite now declares eleven test methods (not collected passes). It also
includes omitted reference-offset, fixed-corner-load removal, thermostat-only
total-outward, and saved format/layout/unit/object/nonfinite actors. Source review
alone has not executed any of these controls.
