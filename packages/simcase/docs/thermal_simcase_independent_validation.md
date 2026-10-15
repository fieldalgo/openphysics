# Independent headless thermal document validation

This dedicated suite checks the actual public Document/run/ThermalRunResult API,
original weak algebra, saved numeric arrays, installed CLI and output ownership.
It does not use a producer summary or existing thermal reference helper as its
numerical answer. No production code or existing test/configuration is changed.

## Fixed independent equations and criteria

The translated rectangle is [0.007,0.037] x [-0.004,0.016] m,
L=.03m,H=.02m,k=12.5W/(m K),Q=100000W/m^3, left280K/right315K.
With xi=x-.007, direct differentiation yields

`T=280+35xi/L+Qxi(L-xi)/(2k)`,
`q=(-k35/L-Q(L-2xi)/2,0)`, `-div(k grad T)=Q`.

Outward heat is +321.6666666667W/m left, -261.6666666667W/m right,
zero on top/bottom and60W/m total. Weak reactions are inward, so have opposite
signs. Q0 slab and negative-Q sink cases are separate controls. These are
per-depth heat rates, not W for an unspecified physical thickness.

The dedicated oracle obtains P1 gradients by inverting `[1,x,y]`, independently
forms uneliminated additive COO K_ij=k A gradNi dot gradNj and f_i=Q A/3,
and evaluates residual=K(T-T_offset)-f. Reaction is residual only on prescribed
nodes and zero on free nodes. Constant-offset evaluation avoids unnecessary
absolute-temperature cancellation without changing the original K/f problem.
Raw cell flux is reconstructed as -k grad(P1T). Unique sorted prescribed nodes
are derived from physical boundary coordinates, not a producer's tag summary.
Left/right are disjoint; general overlapping-corner tag sums cannot uniquely
split corner reactions and must not double count global heat.

Gates were fixed before receiving the product candidate:

- Original `(nx,ny)=(n,n)`, n8/16/32/64. Last two intervals16->32 and32->64
  require L2 temperature order>=1.8 and vector-flux order>=.9. Independent
  interior6x6 Duffy integration is checked against8x8. Both flux components
  matter, including zero transverse flux.
- Normalize by35K, k35/L, L and nonzero absolute source/reaction heat scales;
  no division by280K or cancelling net heat. Array/original K/f/reaction/
  continuous heat criteria<=1e-10; equivalent m/mm/um physical arrays<=1e-9.
  Connectivity/IDs compare exactly. Only geometry changes units, including
  translated origin. k/Q/temperature/subdivisions remain fixed SI inputs.
- Independent raw consumers load with allow_pickle=False, validate layout,
  units, shapes, finiteness, integer CCW connectivity, unique fixed nodes,
  then reconstruct K/f/flux/residual. Metadata corroborates arrays; it never
  creates the expected physical answer.
- Expected refusal tests are normal assertions, not skip/xfail. Save failures
  must preserve unrelated content and cannot publish a completed invalid result.

The stage1 mathematical preparation used analytic nodal P1 samples and synthetic
storage, not a product solve. This product suite independently obtains actual
runner fields and installed artifacts; synthetic interpolation evidence is not
substituted for actual execution.

## Dedicated files and execution

From the repository root, with existing dependencies:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest packages/simcase/tests/test_thermal_simcase_independent_validation.py \
  --basetemp=/absolute/own/records/unused-pytest-directory -q -s
node --test packages/simcase/tests/thermal_simcase_independent_stale.cjs
```

The Python oracle/test files are copied outside the checkout for installed
validation. Run the copied tests using the actual wheel venv's `python -I -m
pytest`, with confcutdir outside the source and a fresh role-owned basetemp.
Verify simcase,simcase.thermal,galerkin,galerkin.thermal,meshine and physmat
module.__file__ paths are inside that installed venv and record sys.executable.
CLI tests launch real `sys.executable -I -m simcase` subprocesses. Existing
optional test dependencies can be reused explicitly; no source-tree PYTHONPATH
fallback or new dependency is required. Build through sdist->wheel first.

The Node test executes the shipped inline Studio script in a deterministic
DOM/canvas harness with delayed API responses. It checks actual state after
thermal JSON apply, not merely the presence of revision-token variable names.
For a copied installed test, set SIMCASE_INDEPENDENT_HTML to the actual installed
simcase/studio/static/index.html. The harness is not a live-browser integration
claim. Server capability checks use actual FastAPI endpoints and ensure no
optical worker, mesh builder or new job is created.

## Initial candidate evidence and open failures

Initial producer candidate: **6080eb86bbd70b668e9952c99ec21802af6ed5cd**,
parent0a44797f73cf67bab14429c982144f0e0e4338aa. This candidate is **not accepted**.
No later moving branch head inherits this status without blob comparison and
relevant re-execution.

The first related run passed84 tests and failed1 because an independent test
mistook the metadata Dirichlet tag-temperature map for a raw array with the same
key. The assertion was corrected to validate that permitted finite tag map;
physical tolerances were unchanged. An expanded run passed90 and failed6:
five actual save-state refusals plus an isolated-environment missing existing
Shapely import. The existing dependency path was made explicit in the own venv,
without installing anything. Re-execution passed91 and failed the same five
save-state cases. Initial copied installed-wheel tests independently reproduced
91pass/5fail. All original failure logs remain retained.

Numerical checks pass for actual slab/mixed positive and negative Q, original
matrix/load/residual/reactions, signed side heat/global60W/m, unit invariance,
raw NPZ/metadata, equal/conflicting corners and source convergence. Actual
n8/16/32/64 normalized errors are approximately
T=[2.93423e-4,7.33557e-5,1.83389e-5,4.58473e-6] and
flux=[7.42307e-3,3.71154e-3,1.85577e-3,9.27884e-4], giving orders2/1.

Five refusal failures have a precise **intentional mutable-result corruption**
precondition: run a valid document, then set one public solution heat_flux/load/
reaction/residual entry toNaN, or replace cell heat_flux with shape(M,) instead
of(M,2), then call save(fresh). Expected ValueError/no completed summary; actual
6080 saves invalid raw arrays with a complete summary and removes .incomplete.
This is serialization validation, not evidence that the normal heat solve
produced NaN. Cached finite diagnostics and object-dtype rejection alone do
not establish finite correctly shaped numeric output.

All three actual-script delayed-response tests fail on6080: after a thermal JSON
apply, a late old EM result repopulates resultData, a late mesh repopulates
meshData, and a late successful validation replaces the raw thermal document
with old EM. Server-side headless refusal passes; it does not establish client
revision safety. The initial candidate explicitly has incomplete frontend guards;
these are concrete reproduced acceptance failures in that disclosed area.

Actual save protection passes existing file/empty/nonempty directory/dangling
symlink refusal, both field flags, post-NPZ/pre-summary failure cleanup,
unexpected-file+incomplete preservation, replaced-target preservation and a
bounded two-writer exclusive-ownership test. These do not certify a portable
atomic transaction, hostile filesystem races or crash recovery. Later candidate
changes to save/guards/validation require relevant independent reruns.

Whole-source, additional boundary/CLI controls and final artifact inspection are
reported separately once complete. No unfinished stage or failed initial
candidate is labelled green. This suite covers headless heat documents, not
thermal plotting, Studio heat UI or heat-to-mechanical coupling.
