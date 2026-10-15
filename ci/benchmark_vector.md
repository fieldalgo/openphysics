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
