# Steady Joule heating

The explicit one-way workflow is `galerkin.joule_heating.solve_steady_joule_heat`.
It consumes a `SteadyElectricResult` produced by
`galerkin.electric.solve_steady_electric` and passes elementwise Joule heat to the
existing steady heat solver. The electrical result contract is defined in
[steady electric conduction](electric_steady2d.md).

```python
from galerkin.electric import solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.mesh import rectangle_mesh

mesh = rectangle_mesh(.02, .01, 16, 8)  # metres
voltage = {int(i): 0. for i in mesh.boundary['left']}
voltage.update({int(i): 2. for i in mesh.boundary['right']})
electric = solve_steady_electric(mesh, conductivity=3., dirichlet=voltage)
temperature = {i: 300. for i in voltage}
result = solve_steady_joule_heat(
    mesh, electrical_result=electric, conductivity=5., dirichlet=temperature)
print(result.thermal.temperature.max())
print(result.source_power_per_length)  # W/m, not W
```

The electrical solve is explicit and runs once. Electrical conductivity (S/m)
and thermal conductivity (W/(m K)) are positive constants, scalar or by named
region, independent of temperature. This is not a nonlinear coupled solve.
The mesh is unchanged between solves, with SI coordinates, identical node and
triangle order, and identical region identities. Exactly equal copies are
accepted; changed geometry or ordering raises `ValueError`.

`Q = J·E` is W/m³ on each triangle. It is transferred without interpolation,
region averaging or an AC factor of 1/2. Each vertex receives `Q * area / 3`.
The workflow independently checks the electric nodal load and integrated power
against heat assembly. `source_power_per_length` and `outward_heat_per_length`
are W/m; multiply by an explicit extrusion depth in metres to obtain watts.
The returned electrical and thermal results own their arrays independently of
input data. No additional heat source is implicitly added.

`dirichlet` maps exterior nodes to kelvin. `outward_flux` and `convection`
follow [steady heat boundary conventions](thermal_flux_robin.md): outward
`q·n = g + h(T-Tambient)`, in W/m², with h in W/(m² K). Unspecified edges are
insulated. Each disconnected component requires fixed temperature or positive
Robin support. Total outward heat is minus the Dirichlet reaction plus the
prescribed outward and convective loads; a positive reaction injects heat.

## Element source API

`galerkin.thermal.ElementHeatSource(mesh, values)` explicitly binds a finite real
`(M,)` array in W/m³ to a snapshot of mesh geometry, connectivity and region
ordering. Pass it to `solve_steady_heat(..., heat_source=source)`. It supports
signed heat/cooling for general thermal use; the Joule workflow rejects negative
Q. Scalar, region-mapping and coordinate-function heat inputs retain their
existing meaning. A bare array remains invalid. Boundary tags may change for a
new thermal problem, but geometry/order/region correspondence may not.

## Validation and limits

Element transfer checks cover exact local loads, total power, geometry and order
mismatch, owned data, invalid values, signed cooling and zero heat. Preparatory
analytical electric sources give heat convergence near order 2 for temperature
and order 1 for flux. They are not evidence of the final electric-to-heat API.
Actual public-API tests cover uniform and two-material bars, voltage sign and
squared scaling, zero voltage, pure Neumann electrical data, thermal Robin/flux
boundaries, mesh mismatch, input mutation and corrupted result rejection.
For V=5000(x²-y²) on a 0.02 m × 0.01 m rectangle, sigma=3 S/m and k=5 W/(m K),
use exact boundary temperatures from
T=300+sigma*5000²/(3k)*(0.02⁴+0.01⁴-x⁴-y⁴). On 8/16/32 grids, final interior
L2 temperature/flux orders were 1.99897/0.99884 (gates >1.8/>0.9); powers were
9.9609375/9.990234375/9.99755859375 W/m, converging to 10 W/m.
Independent scikit-fem 12.0.2 electrical and thermal assembly with two materials,
voltage/current input and mixed thermal boundaries agreed to 1.54e-12 maximum
relative difference (gate 1e-9). These Linux results used Python 3.12.14,
NumPy 2.3.5 and SciPy 1.17.0; they do not establish cross-platform acceptance.

Run from the repository root with test and crosscheck dependencies installed:

```sh
python -m pytest -q tests/galerkin/test_element_heat_source.py tests/galerkin/test_joule_heating.py
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/galerkin/test_crosscheck_skfem_joule.py
python examples/galerkin/joule_heating.py
```

The [executable example](../../../examples/galerkin/joule_heating.py) prints
300.300000 K maximum temperature and 6.000000 W/m for both generated and outward
power. Existing source and installed-wheel CI discover all three test modules;
the required crosscheck setting fails if the reference tool is missing.
No claim is made for temperature-dependent materials, feedback iteration,
transient heating, arbitrary mesh transfer, 3D or a UI. The 2D rates are per unit
out-of-plane depth. Raw P1 boundary flux is not an exactly equilibrated flux;
use assembled reactions for the discrete energy budget.
