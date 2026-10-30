# meshloom — tetrahedral meshing with an exact-arithmetic compiled kernel

**English** | [한국어](../../locales/ko/pages/packages/meshloom/overview.md)

[Documentation home](../../README.md)

**Status: packaging skeleton.** meshloom will be OpenPhysics's general
tetrahedral mesher for multi-material piecewise-linear inputs: constrained Delaunay
tetrahedralization with exact predicates, boundary recovery, quality refinement
and mesh improvement, in a compiled Rust kernel. This release ships only what the
packaging needs to prove: the kernel loads on every wheel platform, reports its
version, and computes IEEE double products without fused multiply-add, which the
exact predicates rely on. `generate3d` raises `NotImplementedError`.

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
extension: it is an abi3 module of the package's version, and its error-free
product agrees with exact rational arithmetic.

## Licenses

meshloom is Apache-2.0. The extension statically links PyO3, its small
dependencies and the Rust standard library, all under permissive licenses and
with no third-party C or C++ code; their license texts ship in
`THIRD_PARTY_NOTICES`, generated and checked by `tools/build_meshloom_notices.py`.
See [third-party software](../../third-party.md).

## Limits

- No mesh generation yet.
- No musllinux, 32-bit or free-threaded CPython wheels.
- Dekker's error-free product, used by the probe, is exact for operands below
  2^996 in magnitude whose error term does not underflow; the mesher will scale its
  input to unit size.
