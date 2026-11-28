# Steady heat conduction on tetrahedral meshes

**English** | [한국어](../../locales/ko/pages/packages/galerkin/thermal3d.md)

Explicit imports are `galerkin.thermal3d` and `refsol.thermal3d`. The module
solves isotropic stationary conduction with P1 tetrahedra on any mesh of the
[tetrahedral mesh format](mesh3d_format.md):

```text
-div(k grad T) = Q,       q = -k grad T
T = prescribed value on Dirichlet nodes
q.n = h (T - T_ambient) - inward_heat_flux on specified natural faces
q.n = 0 on the remaining faces
```

It reuses `Mesh3D`, the P1 tetrahedron stiffness `assemble_stiffness_3d` and
the Dirichlet solver; the source load is assembled in the module. It is the 3D
counterpart of [steady 2D heat](thermal_steady2d.md), and the solver behind the layered conduction check of
`meshine.extrude`.

## API and SI units

```python
from meshine import Domain, box_sides, extrude, generate, rectangle
from galerkin import from_mesher
from galerkin.kernels import dirichlet_from_faces
from galerkin.thermal3d import solve_steady_heat_3d

d = Domain(size=0.1)
d.add_region("chip", rectangle(0, 0, 1.0, 0.8))
mesh = from_mesher(extrude(generate(d, box_sides(0, 1.0, 0, 0.8)), [0.0, 0.2, 0.3, 0.6],
                           {"chip": ["substrate", "die", "mold"]}, size=0.1))
result = solve_steady_heat_3d(
    mesh,
    thermal_conductivity={"substrate": 1.0, "die": 0.01, "mold": 0.5},
    prescribed_temperature=dirichlet_from_faces(mesh, {"z0": 320.0, "z1": 300.0}),
    heat_source_density={"substrate": 0.0, "die": 2e5, "mold": 0.0},
)
```

| Input | Contract / units |
| --- | --- |
| mesh | `galerkin.Mesh3D` in metres: `from_mesher` of a meshine or gmshio mesh, or `box_mesh`. Natural boundary maps use `mesh.tagged_faces`. |
| thermal_conductivity | finite k > 0 in W/(m K), or `{region name: k}` with exactly the entries of `mesh.region_names` |
| prescribed_temperature | `{node index: temperature K}`; every node on the exterior boundary and each connected component needs a fixed node or a face with positive h |
| heat_source_density | Q in W/m^3, `{region name: Q}`, a finite real `(T,)` array in `mesh.tets` order, or a callable taking the read-only `(T, 3)` tetrahedron centroids and returning `(T,)` values; default `None`, no source |
| inward_heat_flux | `{face tag: flux}` in W/m^2, positive into the body |
| convection | `{face tag: (h, T_ambient)}`, h >= 0 in W/(m^2 K), ambient in K |
| thermal_contact_conductance | Map each pair of matching face tags to its finite contact conductance per area in W/(m² K). Zero insulates the pair. |

Values are constant on each selected tag. Flux and convection on the same triangle
are additive. Unknown, empty, or non-exterior selections, duplicate faces within
one condition type, and natural data on fully fixed triangles raise `ValueError`.
Natural boundary data are supported on static meshes. For elementwise Joule
heating, pass the one-dimensional J·E array from the same mesh as
`heat_source_density`. Its total power is `density @ mesh.volumes()` in W.

`dirichlet_from_faces(mesh, {face tag: T})` turns tags into the node map and
refuses a node that two tags would set to different temperatures. It is a helper of
the internal `galerkin.kernels` (consistent units: kelvin here), not of the public API.

| Result field (`SteadyHeat3DResult`, frozen) | Meaning and units |
| --- | --- |
| `temperature` | `(N,)` K |
| `heat_flux` | `(T, 3)` W/m^2, `-k grad T` per tetrahedron |
| `generated_heat_rate` | `(N,)` W, the source load `Q V / 4` per node of each tetrahedron |
| `reaction_heat_rate` | `(N,)` W, the full system residual on the Dirichlet nodes, zero elsewhere; positive injects heat |
| `residual_heat_rate` | `(N,)` W, the full system residual, including natural boundary terms |
| `thermal_conductivity`, `heat_source_density` | `(T,)` values used |
| `outward_prescribed_heat_rate` | `(N,)` W, nodal integrals of minus the prescribed inward flux |
| `outward_convective_heat_rate` | `(N,)` W, nodal integrals of h (T - T_ambient) |
| `relative_conservation_residual` | absolute sum of generated plus reaction minus both outward rates, divided by the sum of absolute nodal rates |
| `prescribed_node_ids` | sorted node indices that were fixed |
| `contact_heat_rate` | With a contact pair, signed nodal heat rates in W, positive leaving that side. Zero away from the contacts. Omitted contact data give `None`. |

Nodal heat rates are watts, not per depth, so the fields have no `_per_depth`
(asking for one raises an `AttributeError` that says why); `.units` maps each
quantity field to its SI unit. The solver raises `ValueError` when
the free residual exceeds `1e-10` of the system scale or the heat balance exceeds
`1e-10`, so a returned result has passed both. JAX or PyTorch values raise
`TypeError`; the one derivative path is a shape derivative, `motion=MeshMotion(...)` with a
JAX or PyTorch t ([shape derivatives](shape_derivative.md#3d-steady-heat)).

## Finite thermal contact between solids

Give the two sides separate node IDs so that their temperatures can differ. Tag each side as an outward-facing surface of its own solid. Both sides must have the same triangle geometry and vertex coordinates, with opposite outward normals. The solver matches triangles geometrically, so the tags can list their faces in different orders. Shared nodes enforce continuous temperature for a perfectly bonded interface.

For tags named `heater_contact` and `substrate_contact`, pass `thermal_contact_conductance={("heater_contact", "substrate_contact"): 2000.0}` to the steady solver. Heat flux leaving the heater is the conductance times the local heater-to-substrate temperature difference. This example coefficient gives an area-specific thermal resistance of 0.0005 m² K/W. To obtain total power leaving the heater through this contact, sum `result.contact_heat_rate` over the heater-side nodes. The substrate receives the same power. Where several contact patches meet at a node, the reported nodal rate includes all of them. For a uniform interface flux the temperature jump equals the flux divided by the conductance.

Positive conductance thermally connects the bodies. Each connected assembly needs a prescribed temperature or positive external convection. Zero conductance leaves the bodies separately anchored. Apply external flux or convection to faces outside the chosen contact. The [heater and substrate example](../../../examples/galerkin/thermal_contact_3d.py) builds the two sets of nodes and compares their interface temperatures with a series thermal resistance calculation.

The example applies 2 W over 80 mm² and holds the substrate base at 300 K. At contact conductances of 500, 5,000 and 50,000 W/(m² K), the computed area-mean interface jumps are 50, 5 and 0.5 K. Each agrees with the series resistance result. Both sides carry 2 W in opposite directions. The [analytical tests](../../../tests/galerkin/test_thermal_contact3d.py) also check a slab with a volume source and an external convective sink. An [independent scikit-fem comparison](../../../tests/galerkin/test_crosscheck_skfem_thermal_contact3d.py) uses an oblique interface where the heat flow changes direction across the surface.

## Validation

`tests/galerkin/test_thermal3d_boundaries.py` also compares a homogeneous
slab at three mesh resolutions with a direct linear solution and the independent
`refsol.thermal_boundary` references. It checks face-integrated rates, the signed
balance, and the total elementwise source power. With a uniform volume source and both
natural terms on the same face, comparison with the independent SciPy
`solve_bvp` collocation solver gives observed orders of 2.18 for RMS nodal
temperature and 0.975 for volume-weighted RMS axial flux at element centroids.

`refsol.thermal3d` provides two independent closed forms:

- `sine_product(points, *, length, thermal_conductivity, reference_temperature, temperature_difference)`:
  `T = T0 + A sin(pi x/Lx) sin(pi y/Ly) sin(pi z/Lz)` with its flux and source
  `Q = k pi^2 (1/Lx^2 + 1/Ly^2 + 1/Lz^2) (T - T0)`, `T = T0` on the six faces.
- `layered_slab(points, *, position, thermal_conductivity, prescribed_temperature)`:
  series conduction along z without a source (`position` the layer boundaries from the
  bottom face, `prescribed_temperature` the pair (bottom, top)); piecewise-linear temperature and a
  uniform flux `(T_bottom - T_top) / sum(d_i / k_i)`, exact in P1 when the layer
  boundaries are node planes.

`tests/galerkin/test_thermal3d.py` grades the solver on meshes that
`meshine.extrude` builds from an unstructured footprint of the 1.0 x 0.8 x 0.6 m
box (no Gmsh), with the pre-registered gates of the 3D opening:

| Check | Gate | Measured (Linux, this change) |
| --- | --- | --- |
| Sine product, k = 2.5, sizes 0.2, 0.1, 0.05 m, source at centroids | L2 order >= 1.8, H1 order >= 0.9 (least-squares slope over the three meshes) | L2 errors 6.12e-2, 1.70e-2, 4.46e-3 (order 1.889); H1 errors 8.17e-1, 4.30e-1, 2.20e-1 (order 0.946) |
| Three-layer slab 0.2 / 0.1 / 0.3 m with k = 1, 0.01, 0.5, 320 K to 300 K, size 0.15 m | temperature error <= 1e-10 of the 20 K drop; flux <= 1e-9; hot-face reaction = flux x area | passes (roundoff) |
| Every solve | `relative_conservation_residual <= 1e-10` | enforced by the solver |

`tests/refsol/test_thermal3d_reference.py` checks the references themselves:
flux and source against finite differences, the slab against the series formula,
and that the module imports only NumPy.

Run from the repository root:

```sh
python -m pytest -q tests/galerkin/test_thermal3d.py tests/refsol/test_thermal3d_reference.py
```

## Limits

- The steady solver uses isotropic, temperature-independent conductivity, constant within a region. Finite thermal contact uses matching faces on a static mesh.
- A callable source is sampled once per tetrahedron (its centroid), which keeps
  the P1 orders above but is not an exact integral of a varying source.
- Dirichlet nodes must lie on the exterior boundary; interior nodes are refused.
