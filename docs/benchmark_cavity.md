# Measuring 3D PEC cavity time and memory

Use the pinned Python environment in the [development guide](development.md) and run from the
repository root. This source benchmark loads `packages/galerkin/src` from its own
checkout explicitly and checks that import location. No new dependency, solver
optimization, API change or CI timing gate is involved.

```bash
python benchmarks/benchmark_cavity.py --output /tmp/cavity-baseline.json
```

The default is three repetitions of each of eight conditions: cube `(1,1,1)` m
and rectangle `(1,0.8,0.6)` m, with `(n,n,n)` Cartesian subdivisions for
`n=4,8,12,16`. Each solve requests six individual modes near **210 MHz**. This
is the solver's finite `near_target` search, not an assertion that the returned
set is the complete lowest spectrum or contains every degenerate partner.
The exact-count policy can split a cluster. Every invocation uses the same
fixed target, mode count and solver tolerances.

Each repetition uses a fresh Python subprocess, run sequentially, with
BLAS/OpenMP environment limits set to one **before NumPy/SciPy imports**. Runs
are ordered by repetition, subdivision, then geometry; no warm-up is discarded.
The output must be a new file. It is checkpointed after every worker, retaining
all successful, failed and timed-out attempts. A failure gives a nonzero final
exit status, but subsequent scheduled cases still run. A 300-second per-worker
timeout kills and reaps that worker; its RSS is unavailable, not copied from
the parent. An interrupted report has `completed=false`. Preserve raw reports
outside the source checkout.

For a short check or a deliberately failed solve:

```bash
python benchmarks/benchmark_cavity.py --case cube --subdivisions 4 --repeats 1 \
  --output /tmp/cavity-smoke.json
python benchmarks/benchmark_cavity.py --case cube --subdivisions 1 --repeats 1 \
  --output /tmp/cavity-insufficient-dofs.json
```

The second command requests six modes from a mesh with insufficient physical
DOFs and must fail. It is not a performance sample. Case/mesh/count/target and
timeout can be changed explicitly via `--help`; changes define a new workload
and must be disclosed in comparisons.

## Measurements and provenance

- `solve_wall_seconds`: the complete `solve_cavity_box` call, including mesh
  construction, topology, assembly, kernel projection, factorization,
  eigensolving, quality checks and returned field/mesh construction. Imports,
  report construction and serialization are excluded. Failed attempts instead
  have `failed_solve_wall_seconds` when the call was reached.
- `subprocess_wall_seconds`: the parent's elapsed time launching and waiting
  for that child, including imports, reporting and process teardown. It is a
  separate metric; it is not added to the solve time.
- `peak_rss_mib`: **the worker's own** `resource.getrusage(RUSAGE_SELF).ru_maxrss`,
  read immediately after the solve. Linux reports KiB, macOS bytes; both are
  converted to MiB (2^20 bytes), with the raw value/unit retained. This is the
  process lifetime high-water mark through the solve, including imports. It
  is neither solver-only incremental memory, current RSS, Python allocation
  accounting, nor the parent's peak. Unsupported platforms report null.

The report includes all individual samples and median/min/max for successful
samples, with explicit attempted/succeeded/failed counts. It retains input
hashes, node/tet/total edge/PEC/free DOF counts, returned frequencies and squared
wave numbers, all residuals, cluster metadata, and sizes of the two returned
field arrays. These array sizes are not total solver memory.

Provenance includes Git SHA and dirty state at both ends, benchmark and engine
file hashes, pin-file hash, Python/platform/CPU, visible affinity and cgroup-v2
CPU/memory limits when available. Each worker records its PID, checked import
path, NumPy/SciPy versions, both libraries' BLAS build configurations and thread environment.
Thread variables request one thread; build configuration is not an independent
measurement of the actual number of native threads. The final command fails
if source identity changes during measurement. Commit the tool before collecting
a baseline, and keep the checkout unchanged throughout that run.

Use medians **and ranges**, on the same otherwise idle machine. Do not infer a
speedup or memory reduction from this single-version baseline. Repeated fresh
processes do not guarantee cold filesystem caches or isolated host resources.
Inspect residuals, returned counts and frequency consistency before comparing
time; finite near-target selection still needs separate physical acceptance.

## Separate profiling

Profile a single worker, not the waiting parent. Keep its time/RSS separate from
the uninstrumented baseline.

The worker detects the legacy `sys.getprofile()` hook and active events in
`sys.monitoring.PROFILER_ID` (CPython 3.12+). It records the monitoring tool name,
event mask and legacy hook state in `profiling`. A reserved monitoring tool with
no enabled events is not marked active. This fixes cProfile detection on
CPython 3.12, where the legacy hook alone returns `None`. It is not a universal
detector for native/external profilers or tools using other monitoring slots;
retain the actual profiling command and artifact as provenance.

Summary `succeeded` counts all successful solves; `unprofiled_succeeded` and
`profiled_succeeded` split that count. Time/RSS median/min/max use only successful
samples without `profiled=true`; `failed` counts unsuccessful attempts, including
timeouts. An all-profiled or all-failed group has null time/RSS statistics.
Historical reports from the old tool can incorrectly label CPython 3.12 cProfile
as false: the summarizer cannot repair missing provenance. Keep those reports
separate based on their external commands, even after updating the tool.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_THREAD_LIMIT=1 \
python -m cProfile -o /tmp/cavity-rectangle16.prof benchmarks/benchmark_cavity.py \
  --worker rectangle --subdivisions 16 > /tmp/cavity-rectangle16-profile.json
python -m pstats /tmp/cavity-rectangle16.prof
```

The profile includes imports/reporting as well as the solve. Attribute cumulative
times without summing nested entries: `solve_cavity_box`, sparse factorization,
ARPACK/linear solves, assembly, topology and field reconstruction overlap in the
call tree. cProfile cannot attribute peak RSS to individual phases. Establish
such attribution in a separate follow-up before choosing a memory optimization.

Run the full root test suite described in the [development guide](development.md) separately from
timing, so tests do not compete for benchmark CPU or memory. This tool supplements
the existing fixed numerical acceptance gates and does not replace them.

## Inherited baseline evidence (2026-10-15)

The previous operator reported 24/24 default uninstrumented solves from clean
source `88ee02c2bfc49ebfa6df4b55260310790613ea2c`, with six returned modes each,
a maximum relative residual of 2.01e-12 and identical frequencies across the
three repetitions of each condition. The successor has **not inspected those
raw reports or profiles**; the following values are inherited reports, not
independently reproduced measurements.

| n=16, inherited report | Cube | Rectangle |
| --- | ---: | ---: |
| Solve median, seconds | 13.0385 | 12.8399 |
| Solve min–max, seconds | 12.4931–13.8035 | 12.8333–14.1168 |
| Process wall median, seconds | 13.3233 | 13.1404 |
| Process lifetime peak RSS median, MiB | 625.1875 | 628.3828 |
| Peak RSS min–max, MiB | 621.9688–626.4336 | 626.8477–628.4414 |
| Total/free edge DOFs | 31024/26416 | 31024/26416 |
| Tetrahedra | 24576 | 24576 |

Reported environment: Linux x86-64, CPython 3.12.14, NumPy 2.5.4, SciPy 1.18.1,
one requested BLAS/OpenMP thread, AMD EPYC 9V74, four-CPU quota, 32 GiB memory
limit. The archived operator's recorded command output was subsequently recovered
without restarting its session. It contains all eight group summaries below and
the original baseline JSON digest
`dca2d01105934093269c3e5c5b6210ad5f2cdc327c29e68d08f32efb8dec6fb8`.
This recovers the printed medians/ranges, not the raw 24-sample JSON or binary
profile; sample-level audit and original artifact transfer remain pending.
No cross-machine speedup or memory reduction is claimed.

| Geometry | n | Free edge DOFs | Solve seconds: median [min, max] | Process median, s | Worker lifetime RSS MiB: median [min, max] |
| --- | ---: | ---: | --- | ---: | --- |
| Cube | 4 | 316 | 0.0316 [0.0271, 0.0331] | 0.3455 | 66.3125 [65.3438, 66.5352] |
| Cube | 8 | 3032 | 0.2548 [0.2268, 0.2808] | 0.5634 | 80.8359 [80.7930, 81.1445] |
| Cube | 12 | 10836 | 2.3142 [2.0294, 2.3908] | 2.6945 | 166.1484 [166.0078, 167.3359] |
| Cube | 16 | 26416 | 13.0385 [12.4931, 13.8035] | 13.3233 | 625.1875 [621.9688, 626.4336] |
| Rectangle | 4 | 316 | 0.0309 [0.0273, 0.0343] | 0.3843 | 66.0273 [65.6641, 66.4336] |
| Rectangle | 8 | 3032 | 0.2490 [0.2345, 0.2641] | 0.5915 | 81.1641 [79.6836, 81.3789] |
| Rectangle | 12 | 10836 | 2.2943 [2.1346, 2.3477] | 2.6291 | 166.7148 [166.6250, 167.1484] |
| Rectangle | 16 | 26416 | 12.8399 [12.8333, 14.1168] | 13.1404 | 628.3828 [626.8477, 628.4414] |

The printed summary reports zero frequency differences between repetitions and
maximum relative residuals below 2.01e-12. Over n=8 to n=16, free DOFs grow by
about 8.7 times, solve medians by about 51 times, and lifetime RSS by about
7.7 times for either geometry. These are observed ratios on these inputs,
not an asymptotic complexity fit, a solver-only memory measurement, or evidence
of an optimization. The small n=4 process time is dominated by work outside the
solver call. Combined with the separately reported factorization profile below,
the larger cases motivate studying factorization memory/time before choosing
an iterative method; such a replacement still needs the existing physical gates.

The previous operator separately reported one rectangle n=16 cProfile:
13.278 s total, 12.856 s cumulative in the solve, 7.962 s across two `splu`
calls and 4.342 s in `eigsh`. The original metadata incorrectly said
`profiled=false`; its command and profile artifact, rather than that flag,
identify it as instrumented. These nested cumulative values must not be added.
The original profile-analysis JSON was not produced after a metadata assertion
failed. The uninstrumented 24-run report was not invalidated by that separate
flag error.

## Successor verification and limits

The successor uses a separate checkout, environment and records directory on
a host shared with other development sessions. Other numerical workloads can
affect timing; exclusive load is not established. Verification is limited to
metadata/CLI/summarizer checks, fresh cube/rectangle n=4 smoke solves and a
separate rectangle n=4 profile. These are tool checks, **not a new baseline**.
The environment has Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0, so the
numerical-library versions also differ from the inherited timing environment.
All six listed BLAS/OpenMP variables are requested as one thread before imports.

The metadata checks cover real cProfile enable/disable, an inactive monitoring
reservation, legacy-hook fallback, mixed success/error/timeout/profile summaries,
CLI validation and overwrite refusal. Linux KiB and macOS bytes conversion are
also checked with mocked resource values; this is not native macOS validation.

The bounded fresh-worker check on clean source
`2223528cc3f46f24471399e2288618751023f424` returned six modes for both n=4
geometries, with 384 tetrahedra and 316 free edge DOFs. Maximum residuals were
2.682e-13 (cube) and 5.282e-15 (rectangle). Both uninstrumented workers were
marked false, and the separate rectangle n=4 cProfile worker was marked true
with tool `cProfile` and active monitoring events. The report recorded unchanged
source identity. Current visible limits were an eight-CPU quota and 8 GiB
memory, with nine affinity CPUs; these differ from the inherited environment.

The first smoke command printed two successful workers and exited zero, but a
subsequent read saw only its first incomplete checkpoint. That file was retained
and rejected as completed evidence. A bounded retry verified the final JSON in
the same invocation, copied it to a separate final artifact, and confirmed both
completed reports on a later read. A separate atomic-replace probe also passed.
The original discrepancy has no established cause.

At the code revision above, remote
[CI 38727103372](https://github.com/fieldalgo/openphysics/actions/runs/38727103372)
passed 498 source tests (zero skips, nine subtests), built/validated seven
sdist-to-wheel distributions, passed 28 installed-wheel tests and eight Node
tests. These checks used CI's pinned environment. The successor's local root
suite instead reported 480 passed, nine failed and nine skipped: seven failures
and seven skips required unavailable Gmsh, two skips required the unavailable RII
database, and two CLI subprocesses could not import the uninstalled source
packages. This local result is not a full pass. Local distribution validation
was not run because twine/Gmsh were absent; no dependencies were installed.
Package/build/CI inputs are unchanged by the benchmark-only code revision.

## Recommendations and remaining analysis

The inherited profile makes sparse factorization the first **candidate** for a
future investigation. First inspect the original profile call tree, matrix
dimensions/nonzero counts and factorization setup versus repeated solves.
Then compare suitable preconditioned iterative shifted solves against sparse
direct factorization on the same workloads and controlled machine. The cavity
operator has a gradient nullspace and shifted systems need not be positive
definite: do not assume conjugate gradients or a generic preconditioner applies.
Any later method needs independent residual, nullspace exclusion, orthogonality,
degenerate-subspace and convergence checks before accepting timing improvements.
No iterative solver or preconditioner is implemented here.

The n=16 factorization report does not establish asymptotic scaling or identify
a memory owner. Recover all eight conditions and their raw samples before
fitting trends or extending the workload. Separate import/process overhead from
solver wall time; do not call lifetime RSS incremental factorization memory.
A small-mesh profile verifies metadata but does not confirm the n=16 bottleneck.
Keep profiling separate and establish phase memory attribution in a follow-up.

The original raw results remain external records requiring transfer through
an authorized private channel. Final baseline analysis remains pending that
transfer; a fresh complete run is unnecessary unless the original data cannot
be recovered and a controlled performance environment is explicitly available.
