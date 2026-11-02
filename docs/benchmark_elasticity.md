# Measuring elasticity and thermoelastic workflow time

**English** | [한국어](locales/ko/pages/benchmark_elasticity.md)

From the repository root, in the pinned environment of the
[development guide](development.md), with the packages installed from this
checkout. No additional dependency is needed:

```bash
python benchmarks/benchmark_elasticity.py --output /tmp/elasticity-baseline.json
python benchmarks/benchmark_elasticity.py --case elasticity --sizes 32 64 --repeats 5 \
  --output /tmp/elasticity-fine.json
```

The output file must be new; it is checkpointed after every worker. Each sample
runs in a fresh Python process with the BLAS/OpenMP thread variables set to one
before NumPy and SciPy import; one repetition runs every case at every size
before the next repetition. A failed solve is recorded with its traceback and
gives a nonzero final exit status. The default is three repetitions of three
cases at `n = 8, 16, 32, 64`. Windows reports RSS as null.

## Cases

All cases use a 1 m × 0.25 m bar with `4n × n` cells (`galerkin.rectangle_mesh`),
E = 70 GPa, ν = 0.3, plane stress, both displacement components fixed on the
left end (`2(n+1)` constrained degrees of freedom).

| Case | Workload |
|---|---|
| `elasticity` | `galerkin.elasticity.solve_elasticity` with a constant traction of (10⁶, 0) Pa on the right end |
| `thermoelastic_traction` | `solve_steady_heat` (k = 50 W/(m K), 300 K left, 350 K right), `freeze_temperature`, then `galerkin.thermoelasticity.solve_thermoelasticity` with α = 12·10⁻⁶ /K, T_ref = 293.15 K and a total traction of (8·10⁶, 3·10⁶) Pa on the right end, the three stages timed apart |
| `workflow` | `galerkin.thermal_mechanical.solve_steady_thermoelasticity`: the same heat problem and materials in one call, with zero natural traction |

The mechanics problems are linear static P1 solves; no contact, large strain
or 3D case is covered.

## What is measured

- `mesh_seconds`: the mesh constructor.
- `solver_call_seconds` (`elasticity`): the complete `solve_elasticity` call,
  including assembly, the sparse factorization and solve, residual checks and
  strain/stress postprocessing.
- `heat_seconds`, `freeze_seconds`, `mechanics_seconds` (`thermoelastic_traction`):
  the heat solve, the snapshot (which hashes the mesh and field) and the
  mechanical stage.
- `workflow_seconds` (`workflow`): the complete one-call workflow, including its
  mesh isolation, both stages and the manifest.
- `peak_rss_mib`: the worker's own `resource.getrusage(RUSAGE_SELF).ru_maxrss`
  read right after the last stage: the process lifetime high-water mark
  including imports, not solver-only memory.

Each sample records node, triangle and DOF counts, the largest residual on a
free degree of freedom (`max_abs_free_residual_n_per_m`), and a quantity of
the solution for agreement checks: the mean end displacement (with the
uniaxial bar value σL/E beside it for orientation; the P1 solution of the
clamped bar is not expected to equal it), the maximum displacement, the
maximum temperature and the physical elastic energy. Check these before
comparing times.

## Provenance and reading

The report records the Git revision and dirty state at start and end, the
hashes of the benchmark, its shared `_harness.py` and every galerkin source
file, the pin-file hash, Python/platform/CPU, visible affinity and cgroup-v2
limits, and per worker its PID, checked import paths, NumPy/SciPy versions and
BLAS build configurations, thread environment and profiler state. The final
command fails if the source identity changed during the run.

`summary` groups samples by case and size with median, minimum and maximum
over the successful, unprofiled samples. Compare medians and ranges on the
same otherwise idle machine with identical sizes and dependency versions; do
not infer a speedup from one repetition. There is no CI wall-time threshold.

For a profile, run one worker under cProfile (the worker records that a
profiler was active) and keep it apart from the uninstrumented samples:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m cProfile -o /tmp/elasticity32.prof benchmarks/benchmark_elasticity.py \
  --worker elasticity --size 32 > /tmp/elasticity32-profile.json
python -m pstats /tmp/elasticity32.prof
```

## Reference run (2026-11-02)

One repetition at `n = 8, 16, 32` on a shared cloud container: Linux x86-64,
Intel Xeon 2.10 GHz, CPython 3.12, NumPy 2.5.4, SciPy 1.18.1,
one BLAS thread. The scripts were those of commit `92b6e15`; the checkout was flagged dirty only by the
then-untracked guide pages of this change. Four CPUs were visible to the process, no
cgroup CPU or memory limit was reported, and other sessions shared the host.
Single samples, so no range; a tool check, not a baseline.
Times in seconds, memory in MiB.

| Case | n | DOFs | Mechanics / call | Heat | Freeze | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| `elasticity` | 8 | 594 | 0.089 | — | — | 87.9 |
| `elasticity` | 16 | 2210 | 0.302 | — | — | 94.4 |
| `elasticity` | 32 | 8514 | 1.228 | — | — | 121.5 |
| `thermoelastic_traction` | 8 | 594 | 0.076 | 0.069 | 0.0617 | 88.4 |
| `thermoelastic_traction` | 16 | 2210 | 0.283 | 0.261 | 0.2501 | 95.5 |
| `thermoelastic_traction` | 32 | 8514 | 1.125 | 0.975 | 0.9616 | 123.5 |
| `workflow` | 8 | 594 | 0.220 | — | — | 88.7 |
| `workflow` | 16 | 2210 | 0.813 | — | — | 95.1 |
| `workflow` | 32 | 8514 | 3.673 | — | — | 124.5 |
