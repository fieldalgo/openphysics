# meshloom — tetrahedral meshing with an exact-arithmetic compiled kernel

**English** | [한국어](../../locales/ko/pages/packages/meshloom/overview.md)

[Documentation home](../../README.md)

**Status: kernel building blocks, no mesher yet.** meshloom will be OpenPhysics's
general tetrahedral mesher for multi-material piecewise-linear inputs: constrained
Delaunay tetrahedralization with exact predicates, boundary recovery, quality
refinement and mesh improvement, in a compiled Rust kernel. The kernel now has its
first two stages, exact geometric predicates and the Delaunay tetrahedralization
of a point set (below). They are internal building blocks for the mesher, not
public API yet. `generate3d` raises `NotImplementedError`.

```python
import meshloom
meshloom.kernel_available()   # True when the compiled kernel loaded
meshloom.kernel_version()     # the kernel's version, equal to meshloom.__version__
```

Use [`meshine.extrude`](../meshine/overview.md#layered-tetrahedral-meshes) for layered
geometry and Gmsh through [`gmshio`](../gmshio/overview.md) for other shapes until
meshloom generates meshes. The criteria it will be accepted by are fixed in
advance in the [pre-registered 3D validation plan](../meshine/validation3d.md); its
output will have the fields `galerkin.from_mesher` reads, like `meshine.TetMesh`.

## Kernel building blocks

`meshloom._core` wraps the first kernel stages for tests and benchmarks. Its
names may change before the mesher's public API.

- **Exact predicates.** `predicate_signs(kind, coords, ids=None)` returns exact
  signs of `orient3d(a, b, c, d) = det[b − a, c − a, d − a]`, `insphere` (positive
  when e is inside the sphere through a positively oriented a, b, c, d), its
  symbolically perturbed form `insphere_sos`, and `incircle3d` (positive when
  coplanar d is inside the circle through a, b, c, computed in 3D without
  projecting). A floating-point filter with Shewchuk's error bounds decides most
  cases; the rest are evaluated exactly with floating-point expansions.
  Coordinates must be 0 or between 2⁻¹²⁰ and 2¹²⁰ in magnitude, where the exact
  evaluation cannot underflow or overflow; others are refused with `ValueError`.
- **Delaunay tetrahedralization.** `delaunay(points, order=None)` returns
  positively oriented tetrahedra, for each point the index of the equal point that
  became the vertex (the lowest index), and kernel counters. Cospherical ties are
  broken by a symbolic perturbation ordered by point index, so the result depends on
  the points and their indices, not on the insertion order. Points are inserted by
  Bowyer–Watson in a biased randomized order with Hilbert rounds.
- **Verifier.** `verify_delaunay(points, tetrahedra)` checks from the arrays alone,
  with exact predicates, that every tetrahedron is positive, every interior face is
  locally Delaunay under the perturbation, the hull is locally convex, the Euler
  characteristic is 1 and every distinct point is a vertex.

```python
import numpy as np
from meshloom._core import delaunay, verify_delaunay

points = np.random.default_rng(0).random((10_000, 3))
tetrahedra, vertex_of, stats = delaunay(points)
verify_delaunay(points, tetrahedra)   # raises ValueError on any violation
```

These stages are graded by V16 and V17 of the
[3D plan](../meshine/validation3d.md). `cargo test` compares every predicate with
big-integer determinants on 10⁴ random and 10⁴ adversarial cases each, and
`tests/meshloom` cross-checks them with Python `Fraction` and runs the verifier and
three insertion orders on the C12 point sets. `benchmarks/benchmark_delaunay.py`
measures throughput on 10⁶ uniform points, with the V15 counters per vertex.

## Platforms and build

meshloom is the one OpenPhysics package with compiled code. It depends on numpy
only. Wheels use the stable ABI (`cp312-abi3`, one wheel per platform for
CPython 3.12 and later) and are built for manylinux 2.17 x86_64 and aarch64,
macOS 11 x86_64 and arm64, and Windows x64. Elsewhere `pip` builds the sdist,
which needs a Rust toolchain and maturin; without a kernel, `kernel_available()`
is `False` and `generate3d` raises `KernelUnavailable`.

From a checkout (repository root):

```bash
rustup toolchain install 1.97.0 --profile minimal --component rust-src
python -m pip install maturin -e packages/meshloom
python -m pytest -q tests/meshloom
(cd packages/meshloom && cargo test --locked)
```

The kernel's unit tests run with `cargo test`; `tests/meshloom` checks the built
extension: it is an abi3 module of the package's version, its error-free product
agrees with exact rational arithmetic, and its predicates and Delaunay
tetrahedralization pass the checks above.

## Licenses

meshloom is Apache-2.0. The extension statically links PyO3, its small
dependencies and the Rust standard library, all under permissive licenses and
with no third-party C or C++ code; their license texts ship in
`THIRD_PARTY_NOTICES`, generated and checked by `tools/build_meshloom_notices.py`.
See [third-party software](../../third-party.md).

## Limits

- No mesh generation yet: no input facets, boundary recovery, refinement or
  improvement. Flips and the predicates on points stored on segments and facets
  come with boundary recovery.
- The kernel refuses fewer than four affinely independent points and
  coordinates outside 0 or [2⁻¹²⁰, 2¹²⁰] in magnitude. It runs on one thread.
- No musllinux, 32-bit or free-threaded CPython wheels.
