# Transient Studio independent acceptance

[한국어](locales/ko/pages/studio_transient_thermal_independent_validation.md)

## Evidence level
These are independent test definitions for an integrated checkout that contains the
dedicated transient Studio API. The test-only branch adds no server implementation.
Collection, HTTP numerical execution, installed acceptance and platform/browser
results must be reported for an exact integrated commit; none is claimed here.
The existing engine and headless numerical/convergence tests remain required.
A synthetic wire or malformed producer actor is not a successful physical solve.

From the repository root in the configured test environment:

```sh
python -m pytest -q -s packages/simcase/tests/test_studio_transient_thermal_acceptance.py
```

The successful-case JSON labelled studio_transient_independent_exact records exact
requested times, per-field maximum absolute errors and raw H/V histories. Keep this
output together with JUnit, command exit, environment and source/module hashes.
Without -s, successful pytest capture can hide those numbers: report missing values
rather than borrowing measurements from another API or commit. As a separate
acceptance stage, copy these tests and their independent oracle dependencies from
the checkout to a directory outside it and run them with python -I against the
installed wheels.

## Physical truth and unchanged gates
studio_transient_independent_fixtures.py imports the existing
transient_headless_independent_oracle.py and transient_headless_independent_cases.py.
It uses independent P1 element geometry/mass/stiffness actions and analytic states;
production matrices, reduced helpers, refsol and summary totals never define truth.
A separate public Document/run result checks identical public histories only after
independent physical acceptance. It is a consistency check, not an oracle.

The rectangle is .002 by .001 m with k=2.5 W/(m K),c=4 J/(m³ K), and nonuniform
saved times[2,2.03,2.1,2.4,3]s. Each case runs in m/mm/um:

| Case | Independent expectation |
|---|---|
|Shifted uniform heating|initial300 K,Q8 W/m³,T=300+2(t-2),q=0|
|Absolute uniform heating|initial304 K,Q8,T=300+2t; do not confuse time origins|
|Signed cooling|initial300 K,Q=-1600,T=300-400(t-2),final-100 K without clamp|
|Sampled exterior ramp|initial290 K,Q12,all-side290+3(t-2),uniform exact P1 state|
|All-fixed support|n1,initial290 K,Q2,same ramp,inward reaction20e-6 W/m|
|Affine|T=290+5000x,left290/right300,q=(-12500,0) W/m²,H=.00236 J/m,V=.3481333333333333 J K/m|

H=1^T M T and V=.5T^T M T have different units and meanings. Storage is M deltaT/dt;
the original residual is storage+KT-fQ. Reactions are inward on fixed nodes;
outward heat=-sum(reaction). Rates are on Nt-1 intervals, not an initial zero row.
No initial projection, negative-K clamp, time interpolation or downsampling is allowed.
The original normalized1e-10,SI1e-9,coordinate1e-12 and per-field scales remain.
The existing transient engine --suite all, temporal/spatial sequences, all interval
thresholds and5% companion-error separation remain separate regression requirements.
These backward-Euler/P1 exact HTTP controls do not replace or redefine PDE convergence.

## Transport and independent controls
The consumer validates all thirteen public fields. Manifest static arrays are
nodes_m/triangles/dirichlet_node_ids; time_s is a top-level exact axis.
Descriptors cover shapes/units/locations/time axes and initial availability.
Default frame is Nt-1. Every dynamic field is reconstructed from all saved frames
and compared with its paged history, then the independent expected arrays.
Temperature is nodal; supplied q is cell-centered, not averaged through nodes.
H/V frames are numeric scalars with shape[], not one-element vectors.
Nt2 checks the sole interval; actual Nt17 H/V pages[0,16)/[16,17) check partial
last-page handling and rejection of a17-row request without silent truncation.

Manifest/frame/history carry paired result/layout identifiers, job/result identity,
original client_revision/request_seq and a separate view frame_seq.
Every frame/history query requires result_id. Integer index i selects state rowi;
rate i>=1 selects rowi-1 and interval[t[i-1],t[i]]. Rate i0 is422.
Identical complete frame queries including frame_seq must return identical bytes.
This does not require equality across distinct view sequences or an encoded cache.
Queries and strict raw JSON test duplicate/unknown/missing keys, bool/fractional/
out-of-range indices, stale identity, invalid times/units and initial/BC mismatch.

Eight malformed producer actors first capture an actual public result, then damage
layout/unit/shape/nonfinite/bool/index/time/rate axis. They require job error and
no published result. The frozen result subclass is constructed explicitly without
mutating production objects. Seven numerical negative controls damage H/V, storage,
source/flux/support signs, time origin or the initial rate axis and must be rejected
by the independent mathematics. Their counts are definitions, not observed passes.

No reset, TTL wait, synthetic positive solver, skip/xfail or tolerance relaxation
bypasses capacity. Cases run sequentially and finish reading a result before the
next job can evict it. The60s bounded asynchronous poll is a test observation limit,
not a solver cancellation or production timeout. Shared admission, pinned-response
accounting, real browser Canvas/current-frame minmax and supported-platform resource
measurements remain separate acceptance suites; passing these tests alone does not
prove capacity, RSS, browser rendering or cross-platform support.
