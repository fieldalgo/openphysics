# Measuring vector mode performance

From the repository root, use the editable installation and pinned environment
described in [README.md](README.md). No additional dependency is needed:

```bash
python ci/benchmark_vector.py --repeats 3 --output /tmp/vector-baseline.json
python ci/benchmark_vector.py --case te --case tm --repeats 5 \
  --output /tmp/vector-slab.json --snapshots /tmp/vector-slab-fields
```

Output files and the optional snapshot directory must be new. Each repetition
runs in a fresh Python process with BLAS/OpenMP thread limits set to one. Imported
implementation packages must come from this checkout. The report records the
Git revision, dirty state, Python/platform/dependency versions, validation-pin
hash, exact documents and their hashes, mesh sizes, raw timings, numerical
results, tracking evidence and process peak RSS. An exception fails the command;
failed solves are not timed as successful samples. Windows reports RSS as null.

The cases are slab TE and TM five-point sweeps, a three-point two-mode slab
sweep, single-point slab TE, six-mode fiber, single-point Hadley rib, and a TE
sweep with half the mesh size. These are representative regression workloads,
not a comprehensive benchmark of all geometries or mode counts.

`seconds` measures the complete `run` call, including mesh generation and
tracking. It excludes imports, input parsing, output serialization and the
optional snapshot write. `timings` contains the runner's own mesh/solve timing
breakdown; it does not cover all setup and tracking costs. `peak_rss_mib` is the
process high-water mark after the solve, including imports. RSS is not isolated
solver memory. The separate `topology_seconds_median` measures 21 complete
`EdgeSpace` constructions on the solved mesh after the run and RSS measurements.

Compare medians and ranges on the same otherwise idle machine, using identical
documents, dependency versions and thread limits. Retain all samples and inspect
numerical results before comparing time. Do not combine a mesh, dependency or
solver-setting change into a timing comparison without identifying it. A small
whole-run difference can be noise even when an isolated operation improves.
There is deliberately no CI wall-time threshold.

For a profile, invoke the single-case worker directly (the parent mostly waits
for child processes). Keep these measurements separate from uninstrumented runs:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python -m cProfile -o /tmp/vector-te.prof ci/benchmark_vector.py --worker te
python -m pstats /tmp/vector-te.prof
```

The profile includes imports and the separate topology measurement. Inspect
the `run`, `solve_modes`, `eigs`, assembly and `EdgeSpace` entries separately.
The worker is an internal measurement entry point, not a solver configuration API.

## Numerical verification

Time alone is insufficient. Compare effective indices, group indices, candidate
ranks and overlaps between reports. With `--snapshots`, the first repetition of
each case also saves the edge ordering and raw complex field arrays. An
implementation that preserves assembly and solver inputs should preserve these
arrays. More general solver changes require phase-invariant field comparison;
degenerate eigenfields can rotate within a subspace.

Run the full suite and distribution checks in [README.md](README.md). Existing
checks cover analytic TE/TM and fiber references, Hadley, mesh/domain/wavelength
convergence, physical field reconstruction and Maxwell residuals, units,
dispersion, mixed boundaries, and conservative tracking failures. Keep solver
tolerances, candidate counts and tracking thresholds fixed during performance
work unless the numerical contract is separately reviewed and validated.

## Edge numbering measurement (2026-10-15)

The 2D `EdgeSpace` constructor sorts the two integer endpoint columns directly,
then labels adjacent unique pairs and maps them back to each triangle. This
preserves the previous lexicographic numbering and orientation signs without
NumPy's structured-row sorting overhead. It does not pack node ids into a
single integer, change the eigenproblem, or change solver/tracking tolerances.

The comparison below used the solver at `44d0339` before this optimization and
the same solver with the new constructor. The benchmark tool was introduced in
`d84268f`; uncommitted tool/document changes account for the baseline report's
dirty flag. Linux x86-64, CPython 3.12.14, NumPy 2.5.4, SciPy 1.18.1 and Shapely
2.2.0 were used, with a four-CPU quota, 32 GiB memory limit and one BLAS thread.
Each case had three fresh-process runs and 21 separate topology constructions
per run. Values below are medians. Runs were collected sequentially, so the
whole-run comparison also includes machine-load and timing variation.

| Case | Triangles | Topology before (ms) | Topology after (ms) | Ratio | Run before (s) | Run after (s) |
|---|---:|---:|---:|---:|---:|---:|
| TE sweep | 1,381 | 1.780 | 0.405 | 4.40 | 0.6210 | 0.6203 |
| TM sweep | 1,381 | 1.774 | 0.403 | 4.40 | 1.1685 | 1.2036 |
| Two-mode sweep | 1,381 | 1.773 | 0.451 | 3.93 | 0.4160 | 0.3792 |
| Single TE | 1,381 | 1.771 | 0.450 | 3.94 | 0.1217 | 0.1159 |
| Fiber | 1,792 | 2.248 | 0.538 | 4.17 | 0.2371 | 0.2460 |
| Hadley | 8,284 | 12.531 | 2.648 | 4.73 | 1.8987 | 1.8842 |
| Fine TE sweep | 5,509 | 7.669 | 1.795 | 4.27 | 6.7156 | 6.9678 |

The improvement is established for topology construction; these samples do not
establish a consistent whole-run speedup. Eigensolving dominates the tested
sweeps. For example, fine TE run times ranged from 6.539–6.755 s before and
6.526–7.353 s after. Median process peak RSS ranged from 92.0–131.8 MiB before
and 91.6–133.1 MiB after; this is not evidence of a memory reduction.

All repetitions had exactly equal effective indices, group indices and tracking
evidence before/after. The first-run snapshots of all seven cases had exactly
equal edge maps and transverse, longitudinal and centroid electric arrays.
Tests additionally verify physical field reconstruction and zero curl after
node/triangle reordering, including empty topology. These measurements describe
this environment and these inputs, not a performance guarantee.
