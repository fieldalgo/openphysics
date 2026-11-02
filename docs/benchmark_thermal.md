# Measuring steady and transient heat conduction time

**English** | [한국어](locales/ko/pages/benchmark_thermal.md)

From the repository root, in the pinned environment of the
[development guide](development.md), with the packages installed from this
checkout. No additional dependency is needed:

```bash
python benchmarks/benchmark_thermal.py --output /tmp/thermal-baseline.json
python benchmarks/benchmark_thermal.py --case steady --case transient --sizes 32 64 \
  --repeats 5 --steps 100 --output /tmp/thermal-fine.json
```

The output file must be new; it is checkpointed after every worker, so an
interrupted or failed run keeps its samples (`completed=false`). Each sample
runs in a fresh Python process with the BLAS/OpenMP thread variables set to
one before NumPy and SciPy import. One repetition runs every case at every
size before the next repetition starts. A failed solve is recorded with its
traceback and gives a nonzero final exit status; the remaining samples still
run. The default is three repetitions of four cases at `n = 16, 32, 64, 128`.
Windows reports RSS as null.

## Cases

All cases use a 1 m × 0.5 m rectangle with `2n × n` cells
(`galerkin.rectangle_mesh`), k = 2 W/(m K), a uniform source of
10³ W/m³, 350 K on the left edge and the other edges insulated unless noted.

| Case | Workload |
|---|---|
| `steady` | `galerkin.thermal.solve_steady_heat` with convection h = 5 W/(m² K) to 300 K on the right edge |
| `steady_regions` | the same problem on `layered_rectangle_mesh` with four conductivity layers (2, 4, 6, 8 W/(m K)) given as a region table |
| `transient` | `galerkin.transient_heat.solve_transient_heat`, c = 4 J/(m³ K), `--steps` backward Euler steps over 1 s (default 50) from 300 K, left edge held at 350 K |
| `document` | the headless `simcase.run` on the shipped `THERMAL_BOUNDARY` example (outward flux plus convection on the right) with its `subdivisions` set to `[2n, n]` |

These are representative regression workloads, not a survey of geometries,
boundary types or time-step counts.

## What is measured

Besides the complete solver call, the three galerkin cases time the public
assembly functions on the same mesh, so the share of assembly in a solve can
be read without profiling:

- `mesh_seconds`: the mesh constructor.
- `stiffness_assembly_seconds`, `mass_assembly_seconds`, `load_assembly_seconds`:
  `assemble_stiffness`, `assemble_mass` and `assemble_load` on the mesh with the
  case's coefficients (`stiffness_nonzeros` records the matrix size).
- `dirichlet_solve_seconds`: `galerkin.solve_dirichlet` of that stiffness matrix
  and load with the left edge fixed: one sparse factorization and solve, without
  convection, checks or postprocessing.
- `solver_call_seconds`: the complete `solve_steady_heat` or
  `solve_transient_heat` call, including its own assembly, boundary system,
  input checks, residual and balance checks and result construction. For the
  transient case `seconds_per_step` divides it by the number of steps and
  `history_bytes` is the size of the returned temperature and flux histories.
- `run_seconds` (`document`): the complete `simcase.run`, including meshine mesh
  generation; `timings` keeps the runner's own mesh/solve split.
- `peak_rss_mib`: the worker's own `resource.getrusage(RUSAGE_SELF).ru_maxrss`,
  read right after the solver call (Linux KiB and macOS bytes converted to MiB).
  It is the process lifetime high-water mark including imports, not solver-only
  memory.

The difference between `solver_call_seconds` and the sum of the assembly and
Dirichlet-solve times is the cost of the solver's boundary handling, checks
and postprocessing; it is a measurement of this code, not an upper bound.
Each sample also records node, triangle and nonzero counts, the temperature
range and the largest residual on a free node (`max_abs_free_residual_w_per_m`),
so numerical agreement can be checked before times are compared.

## Provenance

The report records the Git revision and dirty state at start and end, the
hashes of the benchmark, its shared `_harness.py` and every galerkin source
file, the pin-file hash, Python/platform/CPU, visible affinity and cgroup-v2
CPU and memory limits, and per worker its PID, checked import paths,
NumPy/SciPy versions and BLAS build configurations, thread environment and
profiler state. The final command fails if the source identity changed during
the run. Commit the tool before collecting a baseline.

`summary` groups samples by case and size and gives median, minimum and
maximum of each metric over the successful, unprofiled samples. Compare
medians and ranges on the same otherwise idle machine with the same sizes,
steps and dependency versions. There is deliberately no CI wall-time threshold.

## Profiling

Profile one worker, not the waiting parent, and keep it apart from the
uninstrumented samples (the worker records that a profiler was active):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m cProfile -o /tmp/thermal-steady64.prof benchmarks/benchmark_thermal.py \
  --worker steady --size 64 > /tmp/thermal-steady64-profile.json
python -m pstats /tmp/thermal-steady64.prof
```

## Reference run (2026-11-02)

One repetition at `n = 16, 32, 64` with the default 50 steps on a shared
cloud container: Linux x86-64, Intel Xeon 2.10 GHz, CPython
3.12, NumPy 2.5.4, SciPy 1.18.1, one BLAS thread. The scripts were those of commit `92b6e15`; the checkout was flagged dirty only by the
then-untracked guide pages of this change. Four CPUs were visible to the process, no
cgroup CPU or memory limit was reported, and other sessions shared the host.
Single samples, so no range;
a tool check, not a baseline. Times in seconds, memory in MiB.

| Case | n | Nodes | Assembly (K, M, f) | Dirichlet solve | Solver call / run | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| `steady` | 16 | 561 | 0.0067 | 0.0024 | 0.129 | 87.8 |
| `steady` | 32 | 2145 | 0.0102 | 0.0083 | 0.631 | 94.7 |
| `steady` | 64 | 8385 | 0.0198 | 0.0337 | 2.460 | 112.6 |
| `steady_regions` | 16 | 561 | 0.0065 | 0.0021 | 0.126 | 87.8 |
| `steady_regions` | 32 | 2145 | 0.0091 | 0.0066 | 0.519 | 94.9 |
| `steady_regions` | 64 | 8385 | 0.0188 | 0.0321 | 2.303 | 113.0 |
| `transient` | 16 | 561 | 0.0067 | 0.0022 | 0.342 | 90.4 |
| `transient` | 32 | 2145 | 0.0095 | 0.0066 | 1.143 | 105.1 |
| `transient` | 64 | 8385 | 0.0200 | 0.0326 | 4.668 | 158.2 |
| `document` | 16 | 561 | — | — | 0.282 | 87.8 |
| `document` | 32 | 2145 | — | — | 1.077 | 94.1 |
| `document` | 64 | 8385 | — | — | 5.405 | 115.5 |

At these sizes the public assembly functions and the Dirichlet-only solve
together take about 2 % of the complete steady solver call (0.054 s of 2.46 s
at 8385 nodes), and the call grows about linearly with the node count, about
0.3 ms per node; most of the call is the solver's boundary system, checks and
postprocessing, not the factorization. The transient call, 50 steps, costs
about twice the steady call on the same mesh. The `document` run time includes
meshine mesh generation (`timings` splits it about evenly between mesh and
solve). These are observations of this environment, not scaling claims.
