# Measuring the cost of derivatives

**English** | [한국어](locales/ko/pages/benchmark_derivatives.md)

How much a gradient costs next to the solve it differentiates, through the
public [differentiation API](packages/galerkin/differentiation.md): the adjoint
of the sparse solve on JAX and PyTorch against central differences of the
NumPy solve, for a parameter vector of four. From the repository root, in the
pinned environment of the [development guide](development.md):

```bash
python benchmarks/benchmark_derivatives.py --output /tmp/derivatives-baseline.json
python benchmarks/benchmark_derivatives.py --case heat --backend numpy --backend jax \
  --sizes 32 64 --repeats 5 --output /tmp/derivatives-heat.json
```

JAX and PyTorch are optional (`pip install "galerkin[jax]"`, `"galerkin[torch]"`;
the development guide lists the pins). A backend whose library is not installed
is recorded as `status: "skipped"` with the reason in every sample of that
backend and in `summary.skip_reasons`; skipped samples do not fail the run. The
output file must be new and is checkpointed after every worker. Each sample
runs in a fresh Python process with the BLAS/OpenMP thread variables set to one;
one repetition runs every case, size and backend before the next repetition.
The default is three repetitions of three cases at `n = 8, 16, 32, 64` on all
three backends.

## Cases

Each case is a scalar objective of four parameters; the gradient tests of the
differentiation page use the same kinds of inputs.

| Case | Mesh | Parameters | Objective |
|---|---|---|---|
| `heat` | `layered_rectangle_mesh`, four layers across 1 m × 0.5 m, `n × n` cells per layer | the four layer conductivities (2, 3, 4, 5 W/(m K)) as a region table; 350 K left, convection h = 5 W/(m² K) to 300 K right | mean temperature of the right edge |
| `transient` | `rectangle_mesh`, `2n × n` cells | k = 2.5, c = 4, the amplitude q of a source q (1 + x) W/m³ given as a callback, and T₀ = 300 K used both as the uniform initial field and the left Dirichlet value; `--steps` backward Euler steps over 1 s (default 20) | mean final temperature of the right half |
| `elasticity` | `rectangle_mesh`, 1 m × 0.25 m, `4n × n` cells, left end clamped, plane stress | E = 70 GPa, ν = 0.3 and the traction (10⁶, 2·10⁵) Pa on the right end as a live vector | mean x displacement of the right end |

## What is measured

- `forward_seconds`: the first call of the objective on this backend's values
  (NumPy floats; JAX float64 scalars; PyTorch float64 leaves with
  `requires_grad`). `second_forward_seconds` is the second call, which excludes
  one-time costs such as lazily imported SciPy modules or JAX compilation of
  small primitives.
- `gradient_seconds`: on NumPy, central differences with a relative step of
  10⁻⁶ in each parameter, eight solves (`gradient_solves`); on JAX, one
  `jax.grad` call; on PyTorch, one forward call plus `.backward()`
  (`backward_seconds` is the backward part alone). On the live backends the
  gradient is the forward solve plus one adjoint solve with the transposed
  matrix, whatever the number of parameters; its cost should not grow with
  the number of parameters, while finite differences grow linearly.
- `gradient_to_forward_ratio`: `gradient_seconds / second_forward_seconds`.
  For finite differences of four parameters a ratio near 8 means the solve
  dominates; a lower ratio means fixed per-call overhead does.
- `peak_rss_mib`: the worker's own `resource.getrusage(RUSAGE_SELF).ru_maxrss`
  after the gradient: the process lifetime high-water mark including imports
  and, on the live backends, the recorded reverse pass. For transient
  problems the differentiation page reports how `checkpoint_every` trades that
  memory for time; this benchmark keeps every step.

Each sample records the objective value and the gradient, so the finite
differences and the adjoint gradients of one size can be compared across
backends (to about 10⁻⁶ relative, the accuracy of the central differences).
The values of JAX and PyTorch match the NumPy solve to rounding; a disagreement
is a defect to investigate before any time is compared.

## Provenance and reading

The report records the Git revision and dirty state at start and end, the
hashes of the benchmark, its shared `_harness.py` and every galerkin source
file, the pin-file hash, Python/platform/CPU, visible affinity and cgroup-v2
limits, and per worker its PID, checked import paths, NumPy/SciPy versions and
BLAS build configurations, the live library's version, thread environment and
profiler state. The final command fails if the source identity changed during
the run.

`summary` groups samples by case, size and backend with median, minimum and
maximum over the successful, unprofiled samples. Compare medians and ranges on
the same otherwise idle machine with identical sizes, steps and library
versions. JAX and PyTorch run on CPU; a GPU is not used. There is no CI
wall-time threshold.

## Reference run (2026-11-02)

One repetition at `n = 8, 16, 32` with 20 transient steps on a shared cloud
container: Linux x86-64, Intel Xeon 2.10 GHz, CPython 3.12,
NumPy 2.5.4, SciPy 1.18.1, one BLAS thread. JAX and PyTorch were not installed
in that environment, so their samples are recorded as skipped and the table
holds the NumPy forward solve and central differences only.
The scripts were those of commit `92b6e15`; the checkout was flagged dirty only by the
then-untracked guide pages of this change. Four CPUs were visible to the process, no
cgroup CPU or memory limit was reported, and other sessions shared the host.
Single samples, so no range; a tool check, not a baseline. Times in seconds, memory in MiB.

| Case | n | Nodes | Forward (first) | Forward (second) | Central differences (8 solves) | Ratio | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `heat` | 8 | 297 | 0.074 | 0.068 | 0.653 | 9.63 | 73.7 |
| `heat` | 16 | 1105 | 0.312 | 0.267 | 1.982 | 7.42 | 79.6 |
| `heat` | 32 | 4257 | 1.269 | 1.206 | 8.893 | 7.38 | 92.3 |
| `transient` | 8 | 153 | 0.114 | 0.098 | 0.852 | 8.72 | 73.5 |
| `transient` | 16 | 561 | 0.283 | 0.285 | 2.301 | 8.07 | 77.2 |
| `transient` | 32 | 2145 | 1.030 | 1.206 | 8.611 | 7.14 | 89.5 |
| `elasticity` | 8 | 297 | 0.077 | 0.065 | 0.667 | 10.29 | 75.0 |
| `elasticity` | 16 | 1105 | 0.297 | 0.260 | 2.372 | 9.14 | 82.1 |
| `elasticity` | 32 | 4257 | 1.235 | 1.118 | 9.503 | 8.50 | 109.3 |

The finite-difference gradient costs 7 to 10 forward solves for four
parameters, as expected (eight solves plus overhead). The adjoint columns
could not be measured in this environment; on JAX and PyTorch the
differentiation page's tests show the gradient as one forward plus one
adjoint solve, which this benchmark will time when those extras are
installed. The gradients agree with the closed form where one exists: the
`heat` objective's derivatives with respect to the four layer conductivities
are 2.304, 1.024, 0.576 and 0.369 K per W/(m K) at every size (the layered
slab is exact for P1).
