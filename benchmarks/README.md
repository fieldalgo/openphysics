# Benchmarks

Timing and memory measurements of the solvers that people run by hand. CI does
not run them and they are not performance gates. Each script records the
checkout commit and the hash of the pinned requirements with its results, so a
result can be compared with another run.

| Script | Guide |
|---|---|
| `benchmark_vector.py` | [Vector waveguide benchmark](../docs/benchmark_vector.md) |
| `benchmark_cavity.py` | [3D PEC cavity benchmark](../docs/benchmark_cavity.md) |
| `benchmark_thermal.py` | [Steady and transient heat conduction](../docs/benchmark_thermal.md) |
| `benchmark_elasticity.py` | [Elasticity and the thermoelastic workflow](../docs/benchmark_elasticity.md) |
| `benchmark_electric.py` | [Electric conduction and Joule heating](../docs/benchmark_electric.md) |
| `benchmark_derivatives.py` | [Cost of derivatives](../docs/benchmark_derivatives.md): forward solve, adjoint gradient (JAX, PyTorch) and central differences |
| `benchmark_extrude.py` | [Layered tetrahedral meshes](../docs/packages/meshine/overview.md#layered-tetrahedral-meshes) (V33 of the [3D plan](../docs/packages/meshine/validation3d.md)) |
| `benchmark_delaunay.py` | [meshloom kernel building blocks](../docs/packages/meshloom/overview.md#kernel-building-blocks) (V17 throughput and V15 counters of the [3D plan](../docs/packages/meshine/validation3d.md)) |

Run them from the repository root in the pinned environment of the
[development guide](../docs/development.md), and write results outside the
checkout, for example
`python benchmarks/benchmark_vector.py --repeats 3 --output ../vector.json`.
The thermal, elasticity, electric and derivative benchmarks share the worker
launching, provenance and summary code in `_harness.py`; each runs every
sample in a fresh process and checkpoints its JSON report after each one.
