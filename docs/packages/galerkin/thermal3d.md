# Steady heat conduction on tetrahedral meshes

**English** | [한국어](../../locales/ko/pages/packages/galerkin/thermal3d.md)

Explicit imports are `galerkin.thermal3d` and `refsol.thermal3d`. The module
solves isotropic stationary conduction with P1 tetrahedra on any mesh of the
[tetrahedral mesh format](mesh3d_format.md):

```text
-div(k grad T) = Q,       q = -k grad T
T = prescribed value on Dirichlet nodes
q.n = 0 on every other face (insulation, the natural condition)
```

It reuses `Mesh3D`, the P1 tetrahedron stiffness `assemble_stiffness_3d` and
the Dirichlet solver; the source load is assembled in the module. It is the 3D
counterpart of [steady 2D heat](thermal_steady2d.md) without the flux and Robin
extensions, and the solver behind the layered conduction check of
`meshine.extrude`.

## API and SI units

```python
from meshine import Domain, box_sides, extrude, generate, rectangle
from galerkin import from_mesher
from galerkin.thermal3d import dirichlet_from_faces, solve_steady_heat_3d

d = Domain(size=0.1)
d.add_region("chip", rectangle(0, 0, 1.0, 0.8))
mesh = from_mesher(extrude(generate(d, box_sides(0, 1.0, 0, 0.8)), [0.0, 0.2, 0.3, 0.6],
                           {"chip": ["substrate", "die", "mold"]}, size=0.1))
result = solve_steady_heat_3d(
    mesh,
    conductivity={"substrate": 1.0, "die": 0.01, "mold": 0.5},
    dirichlet=dirichlet_from_faces(mesh, {"z0": 320.0, "z1": 300.0}),
    heat_source={"substrate": 0.0, "die": 2e5, "mold": 0.0},
)
```

| Input | Contract / units |
| --- | --- |
| mesh | `galerkin.Mesh3D` in metres: `from_mesher` of a meshine or gmshio mesh, or `box_mesh`. Face tags are needed only by `dirichlet_from_faces`. |
| conductivity | finite k > 0 in W/(m K), or `{region name: k}` with exactly the entries of `mesh.region_names` |
| dirichlet | `{node index: temperature K}`; every node on the exterior boundary and every connected component of the mesh anchored by at least one |
| heat_source | Q in W/m^3, `{region name: Q}`, or a callable taking the read-only `(T, 3)` tetrahedron centroids and returning `(T,)` values; default zero |

`dirichlet_from_faces(mesh, {face tag: T})` turns tags into the node map and
refuses a node that two tags would set to different temperatures.

| Result field | Meaning and units |
| --- | --- |
| `temperature` | `(N,)` K |
| `heat_flux` | `(T, 3)` W/m^2, `-k grad T` per tetrahedron |
| `load` | `(N,)` W, the source load `Q V / 4` per node of each tetrahedron |
| `reaction` | `(N,)` W, `K T - load` on the Dirichlet nodes, zero elsewhere; positive injects heat |
| `residual` | `(N,)` W, `K T - load` everywhere |
| `conductivity`, `heat_source` | `(T,)` values used |
| `balance_error` | `abs(sum(load) + sum(reaction))` over the total absolute nodal heat |
| `dirichlet_nodes` | sorted node indices that were fixed |

Nodal heat rates are watts, not per depth. The solver raises `ValueError` when
the free residual exceeds `1e-10` of the system scale or the heat balance exceeds
`1e-10`, so a returned result has passed both. NumPy only: JAX or PyTorch values
raise `TypeError`; no derivative path exists here.

## Validation

`refsol.thermal3d` provides two independent closed forms:

- `sine_product(points, lengths, conductivity, reference_temperature, amplitude)`:
  `T = T0 + A sin(pi x/Lx) sin(pi y/Ly) sin(pi z/Lz)` with its flux and source
  `Q = k pi^2 (1/Lx^2 + 1/Ly^2 + 1/Lz^2) (T - T0)`, `T = T0` on the six faces.
- `layered_slab(points, interfaces, conductivities, bottom_temperature, top_temperature)`:
  series conduction along z without a source; piecewise-linear temperature and a
  uniform flux `(T_bottom - T_top) / sum(d_i / k_i)`, exact in P1 when the layer
  boundaries are node planes.

`tests/galerkin/test_thermal3d.py` grades the solver on meshes that
`meshine.extrude` builds from an unstructured footprint of the 1.0 x 0.8 x 0.6 m
box (no Gmsh), with the pre-registered gates of the 3D opening:

| Check | Gate | Measured (Linux, this change) |
| --- | --- | --- |
| Sine product, k = 2.5, sizes 0.2, 0.1, 0.05 m, source at centroids | L2 order >= 1.8, H1 order >= 0.9 (least-squares slope over the three meshes) | L2 errors 6.12e-2, 1.70e-2, 4.46e-3 (order 1.889); H1 errors 8.17e-1, 4.30e-1, 2.20e-1 (order 0.946) |
| Three-layer slab 0.2 / 0.1 / 0.3 m with k = 1, 0.01, 0.5, 320 K to 300 K, size 0.15 m | temperature error <= 1e-10 of the 20 K drop; flux <= 1e-9; hot-face reaction = flux x area | passes (roundoff) |
| Every solve | `balance_error <= 1e-10` | enforced by the solver |

`tests/refsol/test_thermal3d_reference.py` checks the references themselves:
flux and source against finite differences, the slab against the series formula,
and that the module imports only NumPy.

Run from the repository root:

```sh
python -m pytest -q tests/galerkin/test_thermal3d.py tests/refsol/test_thermal3d_reference.py
```

## Limits

- Isotropic, temperature-independent conductivity, constant within a region;
  no tensors, flux, Robin, transient or coupling to mechanics. The 2D module
  keeps those; they are not ported to 3D here.
- A callable source is sampled once per tetrahedron (its centroid), which keeps
  the P1 orders above but is not an exact integral of a varying source.
- Dirichlet nodes must lie on the exterior boundary; interior nodes are refused.
