# Transient heat independent acceptance

[전체 한국어판](locales/ko/pages/transient_heat_independent_validation.md)

**At a glance**

- **What it checks:** independent acceptance of `solve_transient_heat` with its own oracle (no producer or refsol code) and preregistered families: uniform insulation, moving affine field, accepted initial mismatch, discrete source endpoint, temporal eigenmode, PDE sine, temporal companion and independent quadrature.
- **Fixed gates:** temporal orders 0.9–1.1 with the full history matching the backward-Euler product to ≤ 1e-10; PDE sine temperature L2 order ≥ 1.8 and flux L2 order ≥ 0.9; companion change ≤ 5%; quadrature 8 vs 10 within 1%.
- **Scope:** algebra, temporal, spatial and quadrature errors are reported separately, and a failed gate stays a failure; neither time steps nor thresholds are retuned. The historical registration notes below are kept as recorded; for a specific commit, see its CI run.

## Current checkout and evidence

This page describes the implementation in this checkout. Named historical snapshots retain their original results and limitations. For validation of another commit, inspect that commit's CI logs and artifacts.

## Historical registration and current reproduction

2026-10-16. This report covers exact initial production candidate
`d21e083d9723eec71ab5e32777ecd331d75cd981`, whose
`galerkin/transient_heat.py` Git blob is
`426015f84e2c43db964f3063c734d47aca41a9fa`.
The independent acceptance branch was
created at that exact candidate. Its initial code checkpoint is
`55afd565b9f6feea38896dc567eef574adf21371`.
That historical submission changed no production code, producer tests, refsol, existing tests or shared release configuration.

**Historical submission evidence:** no Python parse/compile, collection, NumPy diagnostic, source/installed test, runtime negative, PDE convergence, whole regression or Windows test was executed for the original d21 acceptance submission. It supplied no pass count, measured order, artifact hash or clean-whole claim. These are historical limits, not current execution restrictions; Actions is enabled and present-checkout results require exact CI evidence.

The numerical contract was frozen before reading the new producer module:
independent preregistration `d42b43360bcaff9fe1d98c44105b15ab74ceec90`.
The oracle blob `69238292eb72c58c3d3385cc0a60a1db8c7fcd2b` is copied
**byte for byte**, not adapted from producer/refsol. All frozen gates remain.
Earlier tiny n3 248 checks/41 names and producer self-checks are not this
acceptance. Existing thermoelastic traction/whole-run histories are separate.

## Ownership and files

All executable files are in `packages/galerkin/tests/`:

| File | Role |
|---|---|
| transient_heat_independent_oracle.py | unchanged NumPy/stdlib mathematical truth |
| transient_heat_independent_cases.py | public API adapter and unittest acceptance classes |
| test_transient_heat_independent_validation.py | pytest discovery wrapper only |
| transient_heat_independent_consumer.py | stdlib isolated installed-module loader/origin/hash checks |

This English report and its complete Korean counterpart are the other two
additions. No producer test or tolerance is edited. The source currently declares
17 test methods; this is a static text count, **not** a collected or passed
count. unittest subtests and future pytest/subtest counts must be reported as
actually observed.

## Independent derivation and scales

The scalar SI problem is c*Tdot-div(k*gradT)=Q with prescribed fixed exterior
nodes, all other edges insulated. Coordinates are metres, k W/(m K),
c J/(m^3 K), Q W/m^3 and T Kelvin. Original barycentric geometry gives

```text
M_e = c*A/12 * [[2,1,1],[1,2,1],[1,1,2]]
K_e,ij = k*A*(grad N_i dot grad N_j)
f_e,i(t) = integral N_i*Q(x,t) dA
q_e = -k*sum_i T_i*grad N_i
```

The oracle constructs deterministic CCW square/disconnected meshes directly,
uses opposite-edge gradients and Duffy tensor-Gauss integration. It does not
call production geometry, assembly, load, solver, postprocessing or refsol
functions as truth. Public Mesh is an input adapter. Wrong-runtime actors may
observe/patch a producer helper, but its return is never a reference solution.

Let C be prescribed nodes, F free and h=t_n-t_old:

```text
(M_FF/h+K_FF)*T_F,n =
 f_F,n + M_FF*T_F,old/h - K_FC*d_n
 + M_FC*T_C,old/h - M_FC*d_n/h
r = M*(T_n-T_old)/h + K*T_n - f_n
reaction_C=r_C; reaction_F=0
H=1^T*M*T                         [J/m]
V=.5*T^T*M*T                      [J K/m]
(H_n-H_old)/h=sum(f_n)+sum(reaction_n)
outward_D=-sum(reaction_n)
(V_n-V_old)/h + .5*deltaT^T*M*deltaT/h + T_n^T*K*T_n
 = T_n dot (f_n+reaction_n)
```

The first old constrained state is the **accepted actual initial field**,
not necessarily the sampled d0 within the allowed mismatch bound. Later old
constrained states are prior solved BC values. Positive reaction is inward
heat; transient outward rate is source minus storage. V is not stored heat.
Recovered cell flux need not reproduce weak thermostat balance on a finite
mesh. Per-component balance is audited independently; insulation does not
require the steady solver's anchor rule.

Original M/K actions, source load, storage, full residual, reactions, H/V,
heat/functional identities, shift and exact controls use normalized <=1e-10;
explicit SI conversion <=1e-9. Tscale=max(1K,amplitude/change),
mass scale c*area, Hscale=c*area*Tscale, flux scale=k*Tscale/L.
Rate scale uses absolute source+reaction+storage magnitudes with a positive
unit floor, never cancelling net source. The W K/m functional identity uses
absolute term scales, including absolute temperature times rate.
Direct and algebraically stable V differences are both audited.
No tolerance is selected from an observed result.

## Fixed numerical families and separation

| Family | Fixed definition and gate |
|---|---|
| Uniform insulation | T0+Q*(t-t0)/c; Q8,-1600; irregular[0,.03,.1,.4,1]s; single/disconnected domains with distinct component constants; exact nodal T, zero q/r, component H |
| Moving affine | n8; T=290+5x+3*(t-t0), Q=3c, full exterior exact BC, starts0/2s; exact T/q and original weak reaction |
| Accepted initial mismatch | n3, zero baseline, fixed node1 initial16eps, d0=0, h1e-12; preserve initial bits and independent nonzero storage;64eps rejected |
| Discrete source endpoint | T=300+2t+7t^2; prescribed lookup Q_n=c*[2+7*(t_n+t_old)], Q0=2c; right-end BE control, not continuous derivative |
| Temporal eigenmode | n8 smallest positive generalized Dirichlet mode, max(abs(phi))=1;300K baseline+1K mode, Q0; tau1/lambda, steps8/16/32/64; last two endpoint mass-norm orders .9–1.1; full history BE-product<=1e-10 |
| PDE sine | n8/16/32/64, dt1/256,end1s, observations .25/.5/1s; last two intervals T L2>=1.8 and flux L2>=.9 at each time |
| Temporal companion | n64 dt1/512; abs(E_half-E_primary)/E_primary<=5% for both norms at every observation |
| Independent integration | Gauss8/10 interior norms differ<=1% of each measured nonzero error |

PDE truth, with k=2.5,c=4,A1K,gamma=.7/s,L1m:

```text
T = 300+(1+.7t)*sin(pi*x)*sin(pi*y)
Q = [c*.7+2*k*pi^2*(1+.7t)]*sin(pi*x)*sin(pi*y)
q = -k*(1+.7t)*grad(sin(pi*x)*sin(pi*y))
```

Initial values are exact nodal values and exterior T300. The oracle evaluates
P1 temperature and cell flux over physical interior quadrature. It does not
use nodal/centroid-only error or producer summary as truth.
All meshes use the same deterministic diagonal. Dense algebra is confined to
small controls/n8 eigenmode; n64 audit uses element tensors/scatter actions.
The continuum's affine time dependence does not establish zero semidiscrete
time error. A failed 5% gate remains a failure; neither dt nor thresholds are
retuned. Roundoff-exact affine/uniform fields use exactness, not fabricated
convergence rates.

Report four error categories separately: original-system algebra residual;
fixed-mesh temporal error vs exponential with discrete BE product; continuum
T/flux error with fixed primary/companion dt; independent quadrature error.
Raw errors/orders and every companion ratio are printed when executed.

## B contract review incorporated without changing gates

The pre-implementation review at
`420bd73ea202eef65354b65ee0042598934cb0c2`,
review blob `114a828d5d3b74cb66801c017000b36170e9812d`, was read.
R2 actual initial/old M_FC is tested using a tiny accepted mismatch and small
finite h with zero baseline. Temperature tolerance alone could miss it;
storage magnifies the witness without relaxing the original scale.
A projected-input actor calls the actual solve and is compared to independent
storage truth, not to producer output as an oracle.

R5 tests captured-copy timing, later input mutation, heterogeneous bool,
malformed callback/array shapes, used nodes and derived overflow. Validation
uses actual current mesh arrays; it does not reconstruct what a previously
casting Mesh constructor erased.
R6 defines the entire discrete source lookup first. Wrong left/average/frozen
lookup actors are applied to that same function/history; averaging continuous
derivatives of a quadratic would be an invalid negative discriminator.

R1 actual captured accessors are nodes_m/triangles. R3 tests each requested
time and equal sampled-point totals, not one invented Python-call count or
batch order. R4 expects TransientHeatStepError with time_index/time_s and
nonempty chained cause. R7 normalization/5% error-ratio interpretation matches
the original frozen plan. No producer numerical conformance is inferred.

## Contract and wrong-runtime coverage

The adapter checks exact result shapes Nt or Nt-1, initial flux/source f0,
no fabricated initial reaction/rate, empty BC histories, captured coordinates
and connectivity, read-only arrays, immutable result attributes and no mutable
caller aliases. Controlled callback mutation is a copy-timing diagnostic,
not a concurrent-mutation guarantee. Pure deterministic callbacks remain
a precondition; external side effects are not rolled back.

Finite negative initial/BC/computed Kelvin is accepted mathematically.
This neither certifies physical validity nor changes the separate mechanical
transfer gate. Bool/complex/nonfinite/malformed values, invalid BC IDs,
used-node violations, invalid time grids and derived numeric overflow are
rejection cases. t0 invalid source is rejected even though f0 is not used in
evolution. Later source/BC sentinel errors must identify the exact step/cause
and produce no successful partial result.

Frame rotation/translation transforms flux as a vector; node/cell permutation
and explicit mm-to-m representation are compared to the same physical problem.
Constant T/BC/initial shift preserves q/storage/reaction and shifts H linearly.
No units/provenance authentication or DMP is promised.

| Actor category | Authored discriminator; check exact CI for execution |
|---|---|
| Runtime mass assembly mutation | row-sum lumped M must fail independent n8 BE-product comparison; self-consistent wrong residual alone is insufficient |
| Runtime wrong reduced solve | independent omitted old/new/both M_FC free solution injected through splu actor; original-system free-residual rejection with expected step/cause |
| Actual solve, wrong source input | left/average/frozen deterministic lookup vs discrete endpoint truth |
| Actual solve, silent initial projection | R2 nonzero independent first storage |
| Returned result mutation | storage omission, residual without storage, reaction sign reversal, V mislabeled as H; expected assertion label required |
| Independent matrix alternatives | omitted old/new/both M_FC in independent BE; explicitly not runtime injections |

Actors never edit production files. Unexpected imports, fixture/type errors or
unrelated exceptions are **not** successful wrong-physics rejection.
The original failure and named physical witness must be retained on execution.
Clamp, missing f0, missing copy, unanchored refusal, stale dt and sign/storage
errors are also discriminated by the fixed positive/control/contract tests;
the frozen lab contains additional matrix actors.

## Planned reproduction, source and installed evidence

The commands below are reproduction instructions, not measured results. Run from the repository root in an isolated environment with the existing dependencies. Record exact source and environment evidence. The first example is portable Python; the artifact/consumer snippets explicitly use a POSIX shell. Set numerical threads to 1.

```python
import os
from pathlib import Path
import subprocess
import sys

root = Path.cwd()  # Run this script from the repository root.
env = os.environ.copy()
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    env[name] = "1"
subprocess.run([sys.executable, "-m", "pytest", "-c", "pyproject.toml", "-q", "-s",
                "packages/galerkin/tests/test_transient_heat_independent_validation.py"],
               cwd=root, env=env, check=True)
```

Preserve exact checked-out commit, dirty/unapproved-file audit, host/OS/Python,
versions/module origins, stdout/stderr/exit and first failure/skip. Do not use
an old checkout's retained files to claim an exact artifact.
The source oracle file must retain its frozen blob. Record all declared vs
collected vs passed tests separately.

Build the actual sdist then wheel from that sdist, using own record paths
assigned to ACCEPTANCE_RECORDS and ACCEPTANCE_SDIST, not an existing wheel
of unknown provenance:

```bash
python -m build --no-isolation --sdist --outdir "$ACCEPTANCE_RECORDS/artifacts" packages/galerkin
python -m pip wheel --no-deps --no-build-isolation --no-index --no-cache-dir --wheel-dir "$ACCEPTANCE_RECORDS/wheels" "$ACCEPTANCE_SDIST"
```

Install into a separate own venv with already available dependencies.
Hash-check source/sdist/wheel/installed runtime filenames and bytes,
particularly exact transient_heat.py. Record real hashes, not the Git blob
as if it were a SHA256. Copy oracle/cases/consumer into an external own
consumer directory, never add the source checkout to PYTHONPATH.
Set ACCEPTANCE_INSTALLED_PYTHON, ACCEPTANCE_INSTALLED_ROOT,
ACCEPTANCE_MODULE_SHA256 and ACCEPTANCE_CONSUMER_DIR from observed installation.

```bash
"$ACCEPTANCE_INSTALLED_PYTHON" -I "$ACCEPTANCE_CONSUMER_DIR/transient_heat_independent_consumer.py" --expected-installed-root "$ACCEPTANCE_INSTALLED_ROOT" --expected-module-sha256 "$ACCEPTANCE_MODULE_SHA256" --suite all
```

The isolated consumer uses stdlib unittest plus existing NumPy and the installed
solver, not pytest. It explicitly loads only its own external oracle/cases,
checks installed root and module SHA256, and prints module origin/isolated flag/
oracle/cases hashes and actual counts. Default all includes the unchanged
four-mesh PDE gate; core omits PDE only as a labelled diagnostic and cannot
stand in for full acceptance.

Only after relevant execution succeeds and when authorized, record related
regression and one final whole-root run separately:

```bash
python -m pytest -q
```

Current manifests, documentation indexes and the distribution helper connect these reports, original oracle/cases/wrapper/consumer, runtime modules and example to archive/byte/origin checks. The helper runs the isolated archived consumer with `--suite all` and the complete convergence example. This is implemented verification, not evidence of a successful artifact run; inspect exact CI exits and artifacts.
Subsequent producer SHAs require original blob comparison and impact-specific
retesting; identical code does not justify automatic whole-run repetition.

## Historical d21 evidence boundary

| Scope | Original d21 submission result |
|---|---|
| Candidate API/source reading | completed; exact module blob recorded |
| Acceptance oracle/cases/consumer and EN/KO report | written; static review only |
| Frozen oracle/gates | preserved; producer/refsol truth dependency absent |
| Python syntax/pytest collection/NumPy/source/installed/runtime negatives | unexecuted; no pass claim |
| Temporal/PDE/5% separation and quadrature gates | unexecuted |
| Whole regression/artifact/build/deployment/Windows | unexecuted |
| Actions | no query, execution or activation |

No original numerical failure is replaced by a pass. The table records the historical source-only submission, not the current checkout's CI status. Preserve first-run failures and exact evidence; assess current source, installed, independent and platform results separately before main integration or release.
