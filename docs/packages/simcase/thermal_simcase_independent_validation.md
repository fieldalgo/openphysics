# Independent headless thermal document validation

**At a glance**

- **What it checks:** independent acceptance of the headless `thermal.steady2d` document path (document, run, saved arrays) on a translated rectangle with a closed-form quadratic-source solution. The oracle reconstructs stiffness, load, flux and residuals from the saved raw arrays; metadata never generates the expected answer.
- **Fixed gates:** on n=8/16/32/64, the last two intervals need temperature L2 order ≥ 1.8 and vector-flux order ≥ 0.9; independent 6×6 and 8×8 interior integration are compared; array, stiffness, load, reaction and heat criteria are ≤ 1e-10, and m/mm/µm equivalence ≤ 1e-9.
- **Scope:** headless heat documents only; thermal plotting, Studio heat UI and heat-to-mechanical coupling are outside it. For a specific commit, see its CI run.

## Evidence

This page defines the gates and how to reproduce them. Results for a specific
commit are that commit's CI exits, logs and artifacts; the commands below
reproduce the checks and are not themselves a pass result.

## What the suite checks

This dedicated suite checks the actual public Document/run/ThermalRunResult API,
original weak algebra, saved numeric arrays, installed CLI and output ownership.
It does not use a producer summary or existing thermal reference helper as its
numerical answer.

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

Analytic nodal P1 samples and synthetic storage are mathematical preparation,
not a product solve. This suite independently obtains actual runner fields and
installed artifacts; synthetic interpolation evidence is not substituted for
actual execution.

## Measured values

Measured reference values, not gates: on n8/16/32/64 the normalized errors are
approximately T=[2.93423e-4,7.33557e-5,1.83389e-5,4.58473e-6] and
flux=[7.42307e-3,3.71154e-3,1.85577e-3,9.27884e-4], giving orders 2/1.

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

## Covered controls

Numerical controls cover actual slab/mixed positive and negative Q, original
matrix/load/residual/reactions, signed side heat/global 60 W/m, unit invariance,
raw NPZ/metadata, equal/conflicting corners and source convergence. All nine raw
arrays are checked under both field flags, together with CCW/index/unique
IDs/value-shape/bool/integer controls. With save_fields=false the CLI emits
model/summary/log without NPZ.

Intentional mutable-result corruption must be refused: run a valid document,
then set one public solution heat_flux/load/reaction/residual entry to NaN, or
replace cell heat_flux with shape (M,) instead of (M,2), then call save(fresh).
The expected result is ValueError with no completed summary. This is
serialization validation, not evidence that the normal heat solve produces NaN.
Cached finite diagnostics and object-dtype rejection alone do not establish
finite correctly shaped numeric output.

The delayed-response Node tests require that, after a thermal JSON apply, a late
old EM result does not repopulate resultData, a late mesh does not repopulate
meshData, and a late successful validation does not replace the raw thermal
document with old EM. Server-side headless refusal does not by itself establish
client revision safety.

Save protection covers existing file/empty/nonempty directory/dangling symlink
refusal, both field flags, post-NPZ/pre-summary failure cleanup,
unexpected-file+incomplete preservation, replaced-target preservation and a
bounded two-writer exclusive-ownership test. Storage checks also require:

1. If os.open on the freshly created directory raises OSError during ownership
   construction, the empty exclusively owned target is cleaned up.
2. If model.json is removed after the summary is written but before finish, save
   refuses because a required owned artifact is missing.
3. The same refusal applies to fields.npz when save_fields=true.

Fault-injection assertions require the intended injected error and the completed
replacement stage; a fixture rename/replace OSError must not count as cleanup
acceptance. No skip/xfail/tolerance relaxation hides these checks. Changes to
save, guards or validation require relevant independent source and installed
reruns.

## Limits

**Windows is unverified.** Windows acceptance requires fresh runner evidence;
diagnosing a Windows failure needs actual errno/winerror/stage evidence. Linux
execution and static inspection do not prove Windows support or a fix.

A deterministic Linux interleaving diagnostic shows a remaining pathname TOCTOU
limit: replacing model.json after cleanup's ownership check but before its
unlink deletes the foreign replacement. Inode pinning and checks protect the
tested already-replaced cases but do not make pathname operations atomic. The
supported fresh-output contract requires a caller-controlled exclusive output:
do not allow another writer to modify it until save and any cleanup have
completed. Preservation of replacements already observed before a check is
distinct from preservation during a check/use race; the latter is not
guaranteed. The bounded simultaneous-save test establishes exclusive
fresh-target acquisition, not general concurrent-writer protection. Save
protection does not certify a portable atomic transaction. Hostile filesystem
races, crash recovery, thermal Studio UI and heat-to-mechanical coupling are
outside this acceptance claim.
