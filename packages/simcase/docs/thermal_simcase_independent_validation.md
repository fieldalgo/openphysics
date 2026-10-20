# Independent headless thermal document validation

**At a glance**

- **What it checks:** independent acceptance of the headless `thermal.steady2d` document path (document, run, saved arrays) on a translated rectangle with a closed-form quadratic-source solution. The oracle reconstructs stiffness, load, flux and residuals from the saved raw arrays; metadata never generates the expected answer.
- **Fixed gates:** on n=8/16/32/64, the last two intervals need temperature L2 order ≥ 1.8 and vector-flux order ≥ 0.9; independent 6×6 and 8×8 interior integration are compared; array, stiffness, load, reaction and heat criteria are ≤ 1e-10, and m/mm/µm equivalence ≤ 1e-9.
- **Scope:** the current-status note directly below supersedes present-tense statements in the historical sections, which stay as evidence for their exact candidates. For a specific commit, see its CI run.

## Current final Linux status — 2026-10-16

This current note supersedes present-tense status statements in the historical
6080/4ec sections below. Those sections, equations, thresholds and failures are
preserved as evidence for their exact candidates, not as the current result.

The independent submission is commit
**9b43ae368e89e7e840541d21201e56a311a465b3**, based on explicit producer
**929ac8eb90d5598724ad066e7f8b8fc579ea8cd8** through a normal merge.
This addendum changes documentation only. Against that producer, the submitted
independent work added eight dedicated files and preserved all 232 producer
blobs. This is the independent validator's evidence, not a producer test summary.

In the reconstructed Linux cloud environment, the final dedicated source
suite passed **139 tests**, and the actual sdist-to-wheel installed suite passed
**139 tests** using `python -I`, copied tests outside the checkout and an external
confcutdir. Each had zero failures/skips and one existing Starlette deprecation
warning. The executable and six module origins (simcase, simcase.thermal,
galerkin, galerkin.thermal, meshine, physmat) were checked inside the installed
venv. Installed serializer and shipped HTML bytes were compared to exact Git
blobs. The independent delayed-response Node suite passed **8 source + 8
installed** checks, zero failures/skips. It executes the actual shipped script
in a VM/DOM harness; it is not live-browser acceptance.

The exact929 Linux reruns resolved the original five intentional corrupted-result
save counterexamples and the later constructor/required-artifact checks.
All nine raw arrays, both field flags, original K/f/reaction/heat balances,
fixed convergence and SI gates, CLI exits, existing/replaced/foreign output
protection and bounded two-writer checks remained enforced. An additional actual
installed CLI run with save_fields=false exited zero, emitted model/summary/log
without NPZ and agreed with the analytic 60 W/m balance. No tolerance relaxation
or skip/xfail converted the old failures into passes.

Seven sdists were built into seven wheels. Existing seven sdist asset gates and
wheel runtime/static byte comparisons passed (before 2026-10-20 sdists also
carried tests, docs and examples). The integrated
`ci/check_distributions.py` command failed because **twine was unavailable**;
full strict distribution validation is not claimed. No new dependency was
installed. After environment recovery, the whole-root numerical suite was not
repeated; these dedicated results do not certify a new complete combined build.

The original scratch became unavailable despite the same hostname. Old
unuploaded raw logs, venvs and uncommitted work were **not recovered**.
Consequently “All original failure logs remain retained” below describes an
observation at the historical run time, not current raw-log availability.
Committed source, recorded counts and failure traces survived remotely.
The exact929 source was reconstructed from verified remote blobs, and the
results above are new executions with new logs. Compact evidence records
commands, environment, hashes, counts and this loss limitation; neither that
record nor a rerun is the missing original raw log. The historical initial
cancelled CI and all old failures remain historical, not retroactive successes.

Follow-up producer **94bd34b5711521d805bdce4bee17852895041344** changes only
the producer fault-injection test and its English/Korean guide relative to929;
production `simcase/thermal.py` is byte-identical, blob
**7823d39f451cad1c6b53d2f8dde7899fd854321c**. The independent Linux review
ran its stricter five fault cases in source and actual installed environments:
**5 + 5 passed**. Selected original independent storage/CLI cases separately
passed **34 + 34**, with 105 deselected per run, not a repeated139-case run.
The new assertions require the intended injected error and completed replacement
stage; a fixture rename/replace OSError must not count as cleanup acceptance.

**Windows is unverified.** Two previously reported Windows failures have no
established cause in this review: actual errno/winerror/stage evidence is needed.
Linux execution and static inspection do not prove Windows support or a fix.
GitHub Actions is enabled as of 2026-10-16. Windows acceptance still requires
fresh runner evidence; the earlier failures remain part of this report.

A separate deterministic Linux interleaving diagnostic found a remaining
pathname TOCTOU limit: replacing model.json after cleanup's ownership check
but before its unlink deleted the foreign replacement in both source and
installed runs. This schedules a second writer at the check/use gap; it does
not diagnose the two Windows failures. Inode pinning and checks protect the
tested already-replaced cases but do not make pathname operations atomic.
No production fix is claimed. The supported fresh-output contract requires a
caller-controlled exclusive output: do not allow another writer to modify it
until save and any cleanup have completed. Preservation of replacements already
observed before a check is distinct from preservation during a check/use race;
the latter is not guaranteed. The bounded simultaneous-save test establishes
exclusive fresh-target acquisition, not general concurrent-writer protection. Hostile races, crash recovery, thermal Studio UI
and heat-to-mechanical coupling remain outside this acceptance claim.

## Historical evidence begins below

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
  python -m pytest tests/simcase/test_thermal_simcase_independent_validation.py \
  --basetemp=/absolute/own/records/unused-pytest-directory -q -s
node --test tests/simcase/thermal_simcase_independent_stale.cjs
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

## Explicit Linux reacceptance candidate 4ec9da9

Candidate4ec9da9fcba661958a12f37bc445a543cb4ffc1c is a direct child of6080.
It is normally merged into the independent branch, preserving the original
failed candidate and dedicated tests. Read-only production delta contains the
thermal serializer, inline Studio script, public thermal document and producer
tests. The independent suite reads the new document's nine-array metadata
vocabulary; physical shape, finiteness and numerical thresholds are unchanged.

The original106 Python cases now pass on Linux, including all five original
save-state counterexamples. All three identical actual-script stale-response
cases pass. Thus the original failures are fixed **for this exact Linux
candidate**, without retroactively passing6080. An expanded134-case suite adds
all-nine metadata verification, nine nonfinite arrays under both field flags,
CCW/index/unique IDs/value-shape/bool/integer controls and preservation of a
replaced previously owned file. It reports131pass/3fail: the remaining failures
are in the candidate's disclosed pending storage work, not numerical convergence.

The three concrete remaining checks are:

1. Inject OSError from os.open on the freshly created directory during ownership
   construction. Expected cleanup of the empty exclusively owned target; actual
   empty directory remains without an incomplete marker.
2. Remove model.json after summary is written but before finish. Expected
   refusal because a required owned artifact is missing; actual save succeeds
   and removes the marker.
3. Do the same for fields.npz when save_fields=true. Actual save also succeeds
   despite the absent mandatory raw archive.

No skip/xfail/tolerance relaxation hides these checks. The current directory-fd
and dup pinning design is POSIX-specific; Linux results do not establish Windows
support. Portable handles, constructor-failure cleanup and required-owned-file
checks are separately pending producer changes. Their later exact blobs require
new source/installed storage and metadata/CLI tests. The suite does not select a
moving branch head or assume later candidates pass because4ec improved.

For the original6080 evidence, the first full-root run collected the then-current
96 independent cases before the final10 controls were added:875pass/5fail/
16optional skips plus9subtests. All106 were separately run in source and actual
installed venvs:101pass/5fail. Whole-test collection is not misreported as
including those later10. Existing Studio vector tests8pass are distinct from
the independent stale-response tests3fail on6080. Initial independent-branch CI
38742590017 was cancelled by normal branch-merge workflow concurrency, not
reported as a green run. All earlier test/environment errors remain described
above. The original raw/module/ownership evidence applies only to6080.
