# Steady 3D DC electric conduction

**English** | [한국어](../../locales/ko/pages/packages/galerkin/electric_steady3d.md)

`galerkin.electric3d.solve_steady_electric_3d` solves
∇·J = 0, J = σE, and E = −∇V on conforming linear tetrahedra in SI units.
Pass a [Mesh3D](mesh3d_format.md) with metre coordinates and tagged exterior
faces. Conductivity is a finite positive scalar in S/m or a mapping with
one finite positive scalar for each `mesh.region_names` entry. Conductivity
is constant within each element.

Prescribe scalar voltages with `{exterior_face_tag: voltage}`. Terminal node
sets must be disjoint, and every connected component must contain a terminal.
All other exterior faces have natural zero normal current. This initial API
uses NumPy and SciPy with isotropic materials and voltage boundaries.

```python
from galerkin import box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.thermal3d import solve_steady_heat_3d

mesh = box_mesh(0.4, 0.2, 0.3, 4, 2, 2)
electric = solve_steady_electric_3d(
    mesh, electrical_conductivity=8.0,
    prescribed_electric_potential={"x0": 6.0, "x1": 1.0},
)
thermal = solve_steady_heat_3d(
    mesh, thermal_conductivity=4.0,
    prescribed_temperature={int(i): 300.0 for i in mesh.boundary["x0"]},
    heat_source_density=lambda centroids: electric.joule_power_density,
)
```

| Result | Shape and SI unit |
|---|---|
| `electric_potential` | (N,) V in node order |
| `electric_field`, `current_density` | (T, 3) V/m and A/m² |
| `electrical_conductivity`, `joule_power_density` | (T,) S/m and W/m³ |
| `terminal_current` | Face tag → A, positive into the body |
| `joule_power`, `inward_electric_power` | W integrated over the volume and W supplied by the terminals |

The solver sums reactions from the assembled stiffness matrix at each terminal.
The supplied power is Σ Vₖ Iₖ, computed relative to a voltage datum per connected
component to avoid cancellation under a common voltage shift. For each
tetrahedron the dissipated power density is J·E. All element values follow
`mesh.tets` in its original order, and their volume-weighted sum is
`joule_power`. The heat callback above returns this array on the same mesh
without interpolation. Re-solve before using the array on changed geometry or
after reordering elements.

## Validation

- A 0.4 m × 0.2 m × 0.3 m bar with σ = 8 S/m and ΔV = 5 V has
  R = L/(σA) = 5/6 Ω, 6 A through the bar, and 30 W dissipated. Three
  mesh resolutions check the linear voltage and constant E, J and J·E.
- Two serial slabs with lengths 0.1 m and 0.3 m and conductivities 2 and
  8 S/m check the piecewise linear voltage and continuous normal current.
  The test reverses tetrahedron order and checks that the heat solver
  consumes each J·E value in that order and generates the terminal power.
- A graded bar with σ(x) = 2 + x (x in metres from 0 to 1) checks the
  converging current against the logarithmic resistance. Doubling the
  number of midpoint-sampled material slabs gives second-order convergence.
- scikit-fem assembles and solves an independent P1 model on the same
  tetrahedra with a two-material checkerboard and nonzero transverse field.
  It independently selects the regions and terminal nodes from coordinates.
  The gate is 10⁻¹⁰ global relative difference for V, E, J, J·E, both
  terminal currents and both integrated powers.
