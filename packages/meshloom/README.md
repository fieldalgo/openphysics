# meshloom

Tetrahedral meshing for [OpenPhysics](https://github.com/fieldalgo/openphysics)
with an exact-arithmetic compiled kernel (Rust, through PyO3). Apache-2.0.

**This release is a packaging skeleton.** The compiled kernel loads and reports
its version, and `meshloom.generate3d` raises `NotImplementedError`. For layered
geometry today use `meshine.extrude`; for other shapes use Gmsh through `gmshio`.

```python
import meshloom
meshloom.kernel_available(), meshloom.kernel_version()
```

The criteria the mesher will be accepted by are fixed in advance in the
[pre-registered 3D validation plan](https://github.com/fieldalgo/openphysics/blob/main/docs/packages/meshine/validation3d.md).

The compiled extension statically links the Rust standard library and PyO3
(MIT or Apache-2.0); their notices are in `THIRD_PARTY_NOTICES`.
