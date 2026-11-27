# Steady 3D DC electric conduction

**English** | [한국어](../../locales/ko/pages/packages/galerkin/electric_steady3d.md)

`galerkin.electric3d.solve_steady_electric_3d` solves
∇·J = 0, J = σE, and E = −∇V on conforming linear tetrahedra in SI units.
Pass a [Mesh3D](mesh3d_format.md) with metre coordinates and tagged exterior
faces. Conductivity is in S/m and must be finite and positive. Pass a scalar,
a mapping with one scalar per `mesh.region_names` entry, or a (T,) array in
the exact order of `mesh.tets`. Conductivity is constant within each element.

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
    heat_source_density=electric.joule_power_density,
)
```

| Result | Shape and SI unit |
|---|---|
| `electric_potential` | (N,) V in node order |
| `electric_field`, `current_density` | (T, 3) V/m and A/m² |
| `electrical_conductivity`, `joule_power_density` | (T,) S/m and W/m³ |
| `inward_current` | Face tag → A, positive into the body |
| `joule_power`, `inward_electric_power` | W integrated over the volume and W supplied by the terminals |

The solver sums reactions from the assembled stiffness matrix at each terminal.
The supplied power is Σ Vₖ Iₖ, computed relative to a voltage datum per connected
component to avoid cancellation under a common voltage shift. For each
tetrahedron the dissipated power density is J·E. All element values follow
`mesh.tets` in its original order, and their volume-weighted sum is
`joule_power`. The heat solver accepts that array directly on the same mesh.
Re-solve the electric problem after changing the geometry or reordering elements.
For a complete run with a convection-cooled terminal, see the
[3D Joule heating example](../../../examples/galerkin/joule_heating_3d.py).
The transfer is one-way and the electrical conductivity is independent of temperature.

## Temperature-dependent material evaluation

The coupled solver can use the existing
`galerkin.temperature_joule_heating.ConductivityModel`, alone or mixed with
constant conductivities in a named-region mapping. For each material law, all
nodes of its tetrahedra must lie inside the model's inclusive Kelvin range.
The callback receives the arithmetic mean of the four nodal temperatures of
each tetrahedron and returns one finite positive S/m value per mean.
The steady DC solve uses the resulting conductivity array for one voltage
state. The transient coupling determines when to sample voltage and temperature.
For an isolated conductor at fixed voltage, greater resistance means lower
total Joule power. Terminal current is positive into the conductor, and the
element source J·E in W/m³ is nonnegative.

## Validation

- The [3D coupling regression](../../../tests/galerkin/test_joule_heating_3d_coupling.py)
  uses a 20 mm bar with two equally long layers, conductivities 1 and 3 S/m,
  thermal conductivities 1 and 2 W/(m K), and a 10 × 10 mm cross-section.
  A 2 V drop gives 15 mA and 0.030 W. One end rejects heat to 300 K with
  h = 100 W/(m² K), giving an analytical peak of 305.4375 K at the insulated end.
  The test checks local source values in both materials, independent integration
  at the cooled face, and temperature at nodes and element centroids across three meshes.
- The [scikit-fem coupling comparison](../../../tests/galerkin/test_crosscheck_skfem_joule_heating_3d.py)
  uses an electrode covering half an end face. Each solver independently computes the
  voltage, the heat source and the temperature rise. The relative tolerance for those
  fields, terminal power, volume heating and convective cooling is 10⁻⁹.

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

- A fixed-voltage two-layer resistor with a temperature-dependent heater and a constant lead is checked at three temperatures and three spatial refinements against the series resistance, piecewise voltage, and local J·E.
