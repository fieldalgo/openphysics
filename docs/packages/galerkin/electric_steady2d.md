# Steady 2D electric conduction

## Coupling contract (version 1)

The explicit Python entry point is
`galerkin.electric.solve_steady_electric(mesh, *, conductivity, dirichlet,
outward_current=None, reference_potential=None)`.
It solves `div(J)=0`, `E=-grad(V)`, `J=sigma*E` on conforming P1 triangles.
There are no volume current sources. Conductivity is finite and strictly positive:
a scalar or an exact `{region_name: scalar}` table, in S/m. Interfaces must follow
element edges; potential is continuous and normal current is conserved weakly.
Temperature dependence, contact resistance, anisotropy, 3D and UI are outside this API.

`dirichlet` maps exterior node indices to scalar volts. `outward_current` maps
exterior edge tags to `J.n` in A/m², positive **out of** the domain. Values are
scalars or callbacks `(points_m, outward_normals) -> (Q,)`, integrated with four
Gauss points per edge. Unspecified edges are insulated; explicit zero also means
insulation. Reversed edges get geometrically outward normals. Duplicate selected
edges, interior edges and natural conditions on fully voltage-constrained edges
are rejected. Adjacent voltage and current edges may share an endpoint.

Every connected component without a voltage constraint must have zero integrated
outward current (relative tolerance `1e-12` against the integral of `abs(J.n)`;
no absolute current floor). An incompatible component is rejected **before**
adding a gauge. `reference_potential` is a node-to-voltage mapping with exactly
one node in each such component, including interior nodes. A missing, duplicate
or unnecessary gauge is rejected. This fixes an additive constant, supplies no
physical current, and must not appear in electrode reactions. Disconnected
components are tested separately; global cancellation is insufficient.

The returned `SteadyElectricResult` carries the following SI fields. All arrays
and its copied mesh arrays are read-only snapshots, independent of input arrays.
Node/triangle order and region identifiers are preserved without remeshing.

| Field | Shape | Unit / meaning |
|---|---|---|
| `mesh` | `Mesh` | copied input topology, coordinates in m, boundary and region identities |
| `potential` | `(N,)` | V, P1 nodal potential including specified gauge |
| `electric_field` | `(M,2)` | V/m, constant per triangle, Cartesian x/y |
| `current_density` | `(M,2)` | A/m², constant per triangle |
| `conductivity` | `(M,)` | S/m, expanded material table |
| `joule_heating` | `(M,)` | W/m³, `J·E = sigma*abs(E)**2`, nonnegative |
| `joule_load` | `(N,)` | W/m, consistent P1 load, each cell contributes `Q*A/3` to its nodes |
| `joule_power_per_length` | scalar | W/m, `sum(Q*A)`, equal to `sum(joule_load)` |
| `reaction` | `(N,)` | A/m, current injected by voltage electrodes; zero at other nodes |
| `prescribed_outward_load` | `(N,)` | A/m, integrated prescribed outward current against shape functions |
| `residual` | `(N,)` | A/m, `K*V + prescribed_outward_load`, evaluated before restoring offsets |
| `supplied_power_per_length` | scalar | W/m, electrode/current-source input power |

The thermal consumer must use **this same mesh**, with unchanged node and cell
ordering, and transfer `joule_heating` as an explicitly elementwise volumetric
source or use `joule_load` as the assembled source. It must not pass the cell
array to a scalar/region-only `heat_source` API, average it by region or node,
interpolate it across material interfaces, or multiply it by conductivity again.
It must verify `sum(Q*A) == sum(joule_load)` within roundoff. The electric module
does not modify the heat solver. Thermal conductivity and thermal boundary
conditions belong to the consumer. For a physical extrusion depth `d` in metres,
current A and power W are the per-length quantities multiplied by `d`; Q stays
W/m³ and no implicit thickness or unit conversion occurs.

Electrode outward current is `-sum(reaction)` on the electrode's distinct nodes.
Total current balance is `sum(reaction) = sum(prescribed_outward_load)` separately
per component. Electrode sets sharing nodes must not double-count reactions.
Supplied power is `V·reaction - V·prescribed_outward_load`, evaluated with a
componentwise potential offset removed for numerical stability. It equals Joule
power for the discrete solution. P1 cell gradients are not an equilibrated
H(div) flux: raw boundary `J.n` and individual interelement jumps need mesh
convergence and must not be substituted for assembled electrode reactions.

## Example

```python
from galerkin.mesh import rectangle_mesh
from galerkin.electric import solve_steady_electric

mesh = rectangle_mesh(2., 1., 8, 4)  # metres
volts = {int(i): 2. for i in mesh.boundary['left']}
volts.update({int(i): 0. for i in mesh.boundary['right']})
r = solve_steady_electric(mesh, conductivity=3., dirichlet=volts)
# V=2-x, E=(1,0) V/m, J=(3,0) A/m², Q=3 W/m³, power=6 W/m.
print(round(r.joule_power_per_length, 10))  # 6.0

# Same current with pure Neumann data; a reference is required.
n = solve_steady_electric(mesh, conductivity=3., dirichlet={},
                         outward_current={'left': -3., 'right': 3.},
                         reference_potential={0: 2.})
```

The executable [two-material example](../../../examples/galerkin/electric_steady2d.py)
prints 0.026666667 W/m of Joule/supplied power and 0.133333333 A/m injected current.
Import this submodule explicitly; it is not re-exported from `galerkin`.

## Validation and limits

Run from the repository root with the test and crosscheck dependencies installed:

```sh
python -m pytest -q tests/galerkin/test_electric_steady2d.py
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q -s tests/galerkin/test_crosscheck_skfem_electric.py
python examples/galerkin/electric_steady2d.py
```

The gates are linear slab and series/parallel material-interface solutions
(relative `1e-10`), component current and discrete power balance (`1e-10`), and
interior L2 convergence for `V=sin(pi*x)*sinh(pi*y)/sinh(pi)` on the unit square
(potential order >1.8; E and hence J order >0.9). A local Linux run on 4/8/16/32
cells per side gave potential errors 0.02113/0.005517/0.001396/0.0003501 V
and E errors 0.4790/0.2454/0.1235/0.06184 V/m; final rates 1.996/0.998.
Integrated Joule power is also compared to the exact `sigma*pi*coth(pi)/2`.
Tests include current signs, reversed edges, disconnected components, missing or
unnecessary gauges, tiny incompatible currents, zero current, and offset/sign/
voltage-squared invariance. Results preserve the original mesh and region order.

The independent scikit-fem 12.0.2 (BSD-3-Clause) tests assemble their own weak
forms, facet loads, constraints and Joule loads on shared geometric inputs.
Voltage-only heterogeneous, mixed heterogeneous and pure Neumann cases compare
V/E/J/Q/load/power and physical electrode reactions, gated at `1e-10` relative.
Local maximum differences were 3.69e-15/4.89e-14/1.42e-14 respectively
(Python 3.12, NumPy 2.5.4, SciPy 1.18.1). These are same-process code-to-code
comparisons, not independent convergence evidence; JSON records are emitted by
the [reference comparison machinery](../../reference-comparisons.md).
Existing source and installed-wheel CI collect both new test modules; required
CI fails when the reference dependency is absent. A local pass does not establish
CI or macOS/Windows acceptance; inspect the exact commit's workflow results.

No pointwise normal-current continuity or local equilibrated flux guarantee is
made for P1 fields. Four-point edge quadrature samples callbacks, so callers must
resolve rapidly varying boundary functions. Extreme contrasts and ill-conditioned
meshes have no universal accuracy guarantee; finite-system, free-residual, current
and power checks reject detected failures. Discontinuous geometry, nonconforming
meshes, zero-conductivity subregions and nonlinear materials are unsupported.

For explicit mesh-bound element conductivities and temperature feedback, see
[temperature-dependent Joule heating](temperature_joule_heating.md). Bare arrays remain invalid.
