# Measuring 3D PEC cavity time and memory

Use the pinned Python environment in [README.md](README.md) and run from the
repository root. This source benchmark loads `packages/galerkin` from its own
checkout explicitly and checks that import location. No new dependency, solver
optimization, API change or CI timing gate is involved.

```bash
python ci/benchmark_cavity.py --output /tmp/cavity-baseline.json
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
python ci/benchmark_cavity.py --case cube --subdivisions 4 --repeats 1 \
  --output /tmp/cavity-smoke.json
python ci/benchmark_cavity.py --case cube --subdivisions 1 --repeats 1 \
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
the uninstrumented baseline; the worker marks `profiled=true` under cProfile.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_THREAD_LIMIT=1 \
python -m cProfile -o /tmp/cavity-rectangle16.prof ci/benchmark_cavity.py \
  --worker rectangle --subdivisions 16 > /tmp/cavity-rectangle16-profile.json
python -m pstats /tmp/cavity-rectangle16.prof
```

The profile includes imports/reporting as well as the solve. Attribute cumulative
times without summing nested entries: `solve_cavity_box`, sparse factorization,
ARPACK/linear solves, assembly, topology and field reconstruction overlap in the
call tree. cProfile cannot attribute peak RSS to individual phases. Establish
such attribution in a separate follow-up before choosing a memory optimization.

Run the full root test suite described in [README.md](README.md) separately from
timing, so tests do not compete for benchmark CPU or memory. This tool supplements
the existing fixed numerical acceptance gates and does not replace them.
