# Coupling layer and kernel interface

**English** | [한국어](../../locales/ko/pages/packages/galerkin/coupling.md)

`galerkin.coupling` carries values from one physics to the next. It defines
what a *kernel* (a solver for one physics) must expose so that another kernel
can consume its result. The finite-element engine in this package is the first
kernel behind this contract. The API may change during 0.x
([stability](../../../CHANGELOG.md#stability-in-0x)).

```python
import numpy as np
from galerkin.coupling import Field, OneWayChain, transfer
from galerkin.mesh import rectangle_mesh

mesh = rectangle_mesh(.02, .01, 4, 2)  # metres
temperature = Field(mesh, np.full(mesh.num_nodes, 300.), location="node", unit="K")
same = transfer(temperature, mesh)     # identity on the same mesh
```

## Mesh contract

A kernel works on a `galerkin.mesh.Mesh`: 2D, linear (P1) triangles, SI
coordinates in metres. Two meshes are the same for coupling when
`MeshSignature` matches:

- node coordinates are exactly equal, without tolerance;
- triangle connectivity is equal, in the same triangle order and the same
  node order within each triangle;
- by default, triangle region indices and region names are equal too.
  `regions=False` compares geometry and connectivity only.

Boundary tags are not part of the signature: each physics sets its own
boundary conditions on the shared mesh. An exactly equal copy of a mesh
matches. Any other mesh is a different mesh.

## Field contract

A `Field` is bound to the signature of the mesh it was built on.

| Item | Contract |
|---|---|
| `location` | `"node"`: one value per mesh node, shape (N,). `"element"`: one value per triangle, constant on it, shape (M,). |
| `values` | Read-only float64 copy; finite real numbers. Booleans, complex, non-numeric, nonfinite and out-of-range values raise `ValueError`. |
| `unit` | Nonempty SI unit string, for example `"K"` or `"W/m^3"`. It is recorded, never converted or inferred. |
| Array library | NumPy only. JAX and PyTorch arrays raise `TypeError`: a field between physics would cut their derivative. |

The optional `name` labels the values in these error messages. `Field.on_mesh(mesh)`
returns the values after checking the signature, and raises `ValueError` with
the caller's message when the mesh differs.

## Transfer

`transfer(field, mesh)` returns a field bound to `mesh` with the same values,
location and unit: the identity on the same mesh. A different mesh raises
`ValueError`. There is no interpolation, averaging or projection between
meshes. Conservative projection between a grid and a mesh is planned together
with a second kernel and does not exist yet.

## One-way chain

`OneWayChain(error)` runs the stages of a one-way workflow in order:

```python
chain = OneWayChain(lambda stage, exc, **context: RuntimeError(f"[{stage}] {exc}"))
with chain.stage("heat"):
    ...
with chain.stage("mechanics", time_index=3):
    ...
chain.completed  # ("heat", "mechanics")
```

A failing stage raises the exception built by `error(stage, exc, **context)`,
chained from the original cause. Each finished stage is recorded in order.
The chain has no iteration or feedback; fixed-point coupling (for example
[temperature-dependent Joule heating](temperature_joule_heating.md)) keeps its
own loop.

## Limits

- 2D P1 triangle meshes only; 3D meshes (`Mesh3D`) and edge (Nédélec) fields
  are not fields of this layer.
- Same mesh only; no mesh-to-mesh or grid-to-mesh transfer.
- NumPy only; derivatives do not cross a field.
- One-way only; no general fixed-point driver.

The existing workflows ([Joule heating](joule_heating.md),
[temperature-dependent Joule heating](temperature_joule_heating.md),
[steady heat to mechanics](thermal_mechanical_workflow.md) and
[transient heat to mechanics](transient_thermal_mechanical.md)) keep their own
contracts.
