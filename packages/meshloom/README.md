# meshloom

Tetrahedral meshing for [OpenPhysics](https://github.com/fieldalgo/openphysics)
with an exact-arithmetic compiled kernel (Rust, through PyO3). Apache-2.0.

**First mesher, not yet accepted.** `meshloom.generate3d(points, facets, h=...)`
meshes a piecewise-linear complex (closed polyhedral surfaces, several regions,
tagged facets) with constrained Delaunay refinement to a size and a radius-edge bound
(`quality="practical"` or `"guaranteed"`), and returns the tetrahedral mesh fields that
`galerkin.from_mesher` reads, after removing slivers and improving the mesh by
smoothing and flips. It meets the plan's quality gates measured so far on polyhedral
inputs, but has no graded sizes or curved surfaces yet and is slower than the baseline;
for layered geometry `meshine.extrude` and for other shapes Gmsh through `gmshio` stay
the tested routes.

```python
import meshloom
meshloom.kernel_available(), meshloom.kernel_version()
```

The criteria the mesher will be accepted by are fixed in advance in the
[pre-registered 3D validation plan](https://github.com/fieldalgo/openphysics/blob/main/docs/packages/meshine/validation3d.md).

The compiled extension statically links the Rust standard library and PyO3
(MIT or Apache-2.0); their notices are in `THIRD_PARTY_NOTICES`.
