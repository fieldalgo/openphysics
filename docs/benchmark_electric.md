# Measuring electric conduction and Joule heating time

**English** | [한국어](locales/ko/pages/benchmark_electric.md)

From the repository root, in the pinned environment of the
[development guide](development.md), with the packages installed from this
checkout. No additional dependency is needed:

```bash
python benchmarks/benchmark_electric.py --output /tmp/electric-baseline.json
python benchmarks/benchmark_electric.py --case thermistor_picard --case thermistor_newton \
  --sizes 16 32 --repeats 5 --output /tmp/thermistor.json
```

The output file must be new; it is checkpointed after every worker. Each sample
runs in a fresh Python process with the BLAS/OpenMP thread variables set to one
before NumPy and SciPy import; one repetition runs every case at every size
before the next repetition. A failed solve, including a `JouleConvergenceError`,
is recorded with its traceback and gives a nonzero final exit status. The
default is three repetitions of four cases at `n = 8, 16, 32, 64`. Windows
reports RSS as null.

## Cases

| Case | Workload |
|---|---|
| `conduction` | `galerkin.electric.solve_steady_electric` on the 20 mm × 10 mm strip of the [Joule tutorial](packages/galerkin/joule_tutorial.md) with `2n × n` cells, σ = 3 S/m, 0 V left and 2 V right |
| `joule` | the same DC solve, then `galerkin.joule_heating.solve_steady_joule_heat` with k = 5 W/(m K) and both ends at 300 K, the two stages timed apart |
| `thermistor_picard` | `galerkin.temperature_joule_heating.solve_temperature_joule_heat(method="picard")` on the current-driven thermistor of the [temperature-dependent tutorial](packages/galerkin/temperature_joule_tutorial.md): 1 m × 0.25 m with `4n × n` cells, ρ(T) = 1 + 0.5 (T − 300 K) Ω m on [300, 400] K, 1 A/m² into the right end, both ends at 300 K, `--relaxation` 1.0 by default (the tutorial's value) |
| `thermistor_newton` | the same problem with `method="newton"`; the `ConductivityModel` carries the analytic dσ/dT, so the Newton step uses no difference quotient |

Current density is per unit depth; the exact Joule power of the strip,
σV²H/L = 6 W/m, is recorded beside the computed value.

## What is measured

- `mesh_seconds`: the mesh constructor.
- `stiffness_assembly_seconds`, `dirichlet_solve_seconds` (`conduction`):
  `assemble_stiffness(mesh, σ)` and `solve_dirichlet` of that matrix with both
  ends fixed, on the same mesh: one sparse factorization and solve without the
  solver's checks or postprocessing (`stiffness_nonzeros` records the size).
- `solver_call_seconds`: the complete `solve_steady_electric` call (`conduction`)
  or the complete `solve_temperature_joule_heat` call (both thermistor cases),
  including every inner electric and heat solve.
- `electric_seconds`, `heat_seconds` (`joule`): the DC solve and the heat
  transfer, which copies the electrical snapshot and checks the balances.
- `iterations`, `seconds_per_iteration` (thermistor): the length of the
  returned history and the call time divided by it. Picard and Newton
  iterations cost differently (Newton assembles a Jacobian and may halve
  steps), so compare the call time, not only the counts.
- `peak_rss_mib`: the worker's own `resource.getrusage(RUSAGE_SELF).ru_maxrss`
  read right after the solve: the process lifetime high-water mark including
  imports, not solver-only memory.

Each sample records node and triangle counts, the Joule power, the maximum
temperature, the largest residual on a free node and, for the thermistor, the
final temperature defect and nonlinear heat residual. Both thermistor methods
must agree on the converged temperature and power; check that before comparing
their times.

## Provenance and reading

The report records the Git revision and dirty state at start and end, the
hashes of the benchmark, its shared `_harness.py` and every galerkin source
file, the pin-file hash, Python/platform/CPU, visible affinity and cgroup-v2
limits, and per worker its PID, checked import paths, NumPy/SciPy versions and
BLAS build configurations, thread environment and profiler state. The final
command fails if the source identity changed during the run.

`summary` groups samples by case and size with median, minimum and maximum
over the successful, unprofiled samples. Compare medians and ranges on the
same otherwise idle machine with identical sizes, relaxation and dependency
versions. A changed relaxation or mesh defines a new workload. There is no
CI wall-time threshold.

For a profile, run one worker under cProfile (the worker records that a
profiler was active) and keep it apart from the uninstrumented samples:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m cProfile -o /tmp/thermistor32.prof benchmarks/benchmark_electric.py \
  --worker thermistor_newton --size 32 > /tmp/thermistor32-profile.json
python -m pstats /tmp/thermistor32.prof
```

## Reference run (2026-11-02)

One repetition at `n = 8, 16, 32` with relaxation 1.0 on a shared cloud
container: Linux x86-64, Intel Xeon 2.10 GHz, CPython 3.12,
NumPy 2.5.4, SciPy 1.18.1, one BLAS thread. The scripts were those of commit `92b6e15`; the checkout was flagged dirty only by the
then-untracked guide pages of this change. Four CPUs were visible to the process, no
cgroup CPU or memory limit was reported, and other sessions shared the host.
Single samples, so no range; a tool
check, not a baseline. Times in seconds, memory in MiB.

| Case | n | Nodes | Stiffness assembly | Dirichlet solve | Solver call (electric + heat) | Iterations | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `conduction` | 8 | 153 | 0.0053 | 0.0010 | 0.038 | — | 85.9 |
| `conduction` | 16 | 561 | 0.0067 | 0.0027 | 0.153 | — | 87.9 |
| `conduction` | 32 | 2145 | 0.0082 | 0.0068 | 0.525 | — | 95.5 |
| `joule` | 8 | 153 | — | — | 0.039 + 0.038 | — | 86.4 |
| `joule` | 16 | 561 | — | — | 0.160 + 0.176 | — | 88.5 |
| `joule` | 32 | 2145 | — | — | 0.562 + 0.513 | — | 96.1 |
| `thermistor_picard` | 8 | 297 | — | — | 1.787 | 8 | 87.4 |
| `thermistor_picard` | 16 | 1105 | — | — | 7.990 | 8 | 92.4 |
| `thermistor_picard` | 32 | 4257 | — | — | 26.629 | 8 | 108.7 |
| `thermistor_newton` | 8 | 297 | — | — | 0.795 | 3 | 88.4 |
| `thermistor_newton` | 16 | 1105 | — | — | 3.081 | 3 | 97.0 |
| `thermistor_newton` | 32 | 4257 | — | — | 12.368 | 3 | 129.7 |

Both thermistor methods converged to the same maximum temperature and Joule
power (to 10⁻¹¹ relative) at every size; Newton needed 3 states against 8
Picard passes and about half the time. The `joule` heat transfer costs about
as much as the DC solve it follows.
