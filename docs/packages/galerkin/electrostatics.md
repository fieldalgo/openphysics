# 2D electrostatics and the capacitance matrix

**English** | [한국어](../../locales/ko/pages/packages/galerkin/electrostatics.md)

## Formulation and conventions

`galerkin.electrostatics` solves, on a conforming P1 triangle mesh in metres and
per unit length along the out-of-plane axis,

```text
-div(eps0 eps_r grad V) = rho,   E = -grad V,   D = eps0 eps_r E
```

with conductors as node sets at a prescribed potential. The exterior boundary not
on a conductor is insulated (`D.n = 0`, natural condition). The weak form is
`int eps0 eps_r grad V . grad phi_i = int rho phi_i`; the stiffness matrix `K`
carries the absolute permittivity, so the residual `K V - f` is a charge in C/m.
Conventions:

- `eps_r` is the relative permittivity, finite with `Re > 0`. A lossy dielectric
  is `eps' (1 - j tan d)` with `Im(eps_r) <= 0` (`exp(+j omega t)` convention, as
  in [sipi](../sipi/overview.md)); `Im > 0` is rejected. Complex values are
  accepted on the NumPy path only.
- Conductor charge is the sum of the assembled reaction `(K V - f)_i` over the
  conductor's nodes: positive when the conductor carries positive charge, that is
  when `D` points from the conductor into the dielectric. With `rho = 0` the
  conductor charges sum to zero; with free charge they sum to `-int rho`.
- Energy per length is `W = V^T K V / 2` in J/m (no conjugate, so it is analytic
  in `eps_r` and complex for a lossy dielectric), evaluated with a componentwise
  potential offset removed. For one conductor at `U` volts against ground,
  `W = Q U / 2`.
- Conductor nodes may be anywhere in the mesh: a zero-thickness trace is an
  interior line of nodes, a solid conductor is the boundary of a hole.

## API

```python
from galerkin import solve_electrostatics, capacitance_matrix, ElementPermittivity
```

`solve_electrostatics(mesh, *, permittivity, conductors, ground=None, charge_density=0.0, reference_potential=None)`

| Argument | Meaning |
|---|---|
| `permittivity` | `eps_r`: positive scalar, exact `{region name: value}` table ([input rule](multimaterial.md)) or a mesh-bound `ElementPermittivity(mesh, values)` (real, strictly positive, same geometry, order and regions). Scalar and table entries may be complex with `Im <= 0`. Bare element arrays are rejected. |
| `conductors` | `{name: (node ids, volts)}`: node sets, `sipi` style; or a plain `{node: volts}` Dirichlet mapping, whose charges are then reported per node under the node index. One form per call. Conductors must not share nodes, every node must exist, a set must not be empty. |
| `ground` | node ids held at 0 V, reported as conductor `"ground"`; a user conductor of that name is rejected when `ground` is given. |
| `charge_density` | free charge `rho` in C/m³: scalar, region table or callback `(x, y) -> rho` at the triangle centroids (centroid rule, consistent P1 load). |
| `reference_potential` | `{node: volts}`, exactly one gauge per connected component without a conductor node. That component must carry zero net free charge to `1e-12` relative to `sum(abs(load))` (checked before adding the gauge); a gauge on a conductor component is rejected. The gauge supplies no charge and never appears in `reaction`. |

`ElectrostaticsResult` fields (read-only snapshots in the input mesh order; JAX or
PyTorch arrays when an input was live):

| Field | Shape | Unit / meaning |
|---|---|---|
| `mesh` | `Mesh` | copied input topology, coordinates, boundary and region identities |
| `potential` | `(N,)` | V, nodal P1 potential including gauges |
| `electric_field` | `(M,2)` | V/m, constant per triangle, `-grad V` |
| `displacement` | `(M,2)` | C/m², `eps0 eps_r E` |
| `relative_permittivity` | `(M,)` | expanded `eps_r` table |
| `energy_per_length` | scalar | J/m, `V^T K V / 2` |
| `load` | `(N,)` | C/m, `int rho phi_i` |
| `reaction` | `(N,)` | C/m, `K V - f` at conductor nodes; zero elsewhere, also at gauges |
| `residual` | `(N,)` | C/m, `K V - f` at every node, offsets removed |
| `conductors` | dict | name -> sorted read-only node ids (`"ground"` included) |
| `charge` | dict | name -> C/m, the reaction summed over the conductor |
| `total_free_charge` | scalar | C/m, `sum(load)` |

Checks that raise `ValueError`: nonfinite stiffness, load or solution; free
residual above `1e-10` of `max(abs(K) abs(V) + abs(f))`; per-component charge
balance `abs(sum(reaction) + sum(load)) <= 1e-10 (sum(abs(reaction)) + sum(abs(load)))`;
singular systems. Nothing is repaired.

`capacitance_matrix(mesh, *, permittivity, conductors, ground)` returns the Maxwell
capacitance matrix in F/m of the conductors `{name: node ids}` in their dictionary
order, against the required nonempty `ground`. Column `j` is the solve with
conductor `j` at 1 V and every other conductor and the ground at 0 V. Entry
`(i, j)` is the **charge route**, the reaction sum on conductor `i`. The **energy
route** `eps0 V_i^T K_r V_j` is computed from the same potentials and an
independent assembly, and the two must agree to `1e-10` of the largest entry
(`ValueError` otherwise); only then is the charge matrix symmetrised to
`(C + C^T)/2` and returned. The matrix is symmetric positive definite for a real
permittivity. For `eps' (1 - j tan d)` the matrix is complex, `C - j C_loss`, with
`C_loss = -Im C` positive semidefinite: diagonal `Im C_ii < 0`, while an off-diagonal
`Im C_ij` is positive because the mutual capacitance is negative. `sipi` keeps its
own routine (`sipi.capacitance_matrix`) for line parameters; this module does
not change it.

### JAX and PyTorch

`permittivity` (scalar or region table), conductor potentials, reference
potentials and `charge_density` (scalar, table or a callback returning live
values) may be JAX or PyTorch float64 values, as in
[steady electric conduction](electric_steady2d.md) and the
[differentiation contract](differentiation.md). Results and the capacitance matrix
are then in that library and carry the derivative with respect to those inputs;
the free-residual, balance and route checks read snapshots of the numbers. A
complex live permittivity raises `TypeError`: complex permittivity is NumPy only.
`ElementPermittivity` values are NumPy.

## Example

```python
import numpy as np
from galerkin import annulus_mesh, capacitance_matrix, solve_electrostatics

mesh = annulus_mesh(1.0, 3.0, 16, 96)                       # metres
C = capacitance_matrix(mesh, permittivity=2.2,
                       conductors={"inner": mesh.boundary["inner"]},
                       ground=mesh.boundary["outer"])
print(C[0, 0])   # 1.1150e-10 F/m; exact 2 pi eps0 2.2 / ln 3 = 1.1141e-10

r = solve_electrostatics(mesh, permittivity=2.2,
                         conductors={"inner": (mesh.boundary["inner"], 1.0)},
                         ground=mesh.boundary["outer"])
print(r.charge["inner"] + r.charge["ground"])   # 0 to roundoff; C[0, 0] == r.charge["inner"]
```

## Validation

```sh
python -m pytest -q -s tests/galerkin/test_electrostatics_capacitance.py
```

The gates were fixed before the implementation and the thresholds are not tuned.
References are `refsol.electrostatics` (`coax_capacitance`,
`two_layer_plate_capacitance`) and `refsol.metallic.coax_potential`, which never
import the engine. Measured on Linux, Python 3.12, NumPy 2.5.4, SciPy 1.18.1:

| Gate | Criterion | Measured |
|---|---|---|
| E1 energy vs charge route | `<= 1e-10` relative to the largest entry, built into `capacitance_matrix` and recomputed in the test with `assemble_stiffness` | `6.9e-16` (two interior traces over a ground plane) |
| E2 coax `C = 2 pi eps0 eps_r / ln(b/a)` on `annulus_mesh(1, 3, n, 6n)`, n = 4, 8, 16, 32 | observed order `>= 1.8` over the last two refinements, finest `<= 1e-3` | errors `1.39e-2 / 3.52e-3 / 8.83e-4 / 2.21e-4`, orders `1.984 / 1.995 / 1.999` |
| E3 two-layer plate (0.3 mm at 2.0, 0.7 mm at 5.0, width 2 mm), series combination, exact in P1 | `<= 1e-12` | `6.7e-16`; also with loss tangents 0.01/0.002 against the complex closed form |
| E4 real `eps_r` | `C` symmetric (exact after symmetrisation), positive definite, `C_ij < 0 < C_ii` | passed |
| E4 complex `eps_r (1 - 0.02 j)` | `Im C_ii < 0`, `-Im C` positive definite; `Re C` within `1e-12` of the lossless `C` | `Re` gap `6.1e-16`; `Im C + tan d C` gap `2.4e-17` |
| E5 `dC/d eps_r = C / eps_r` on JAX and PyTorch | relative `1e-10`; also the two-layer `dC/d eps_1` against the closed form | **skipped**: neither library is installed in the validation environment; the live path is unverified here |
| E6 charge balance with `rho = 1e-6 C/m³` in the coax | `abs(sum(charge) + total_free_charge) <= 1e-10` relative | `6.7e-16` |
| E6 with `rho = 0` | `abs(sum(charge)) <= 1e-12` of the largest charge | `2.4e-16` |

Error paths covered: touching conductors (also with the ground), nodes outside the
mesh, empty and non-integer sets, mixed key forms, non-scalar volts, a missing or
unnecessary gauge, incompatible net charge on a gauge component, invalid
permittivities (zero, negative, nonfinite, boolean, `Im > 0`, non-scalar), region
tables not matching the mesh, an `ElementPermittivity` from another mesh, the
`"ground"` name clash and the route check itself (forced by a zero tolerance).
`tests/galerkin/test_electrostatics.py` grades the underlying coax potential at
second order. A local pass does not establish CI or macOS/Windows acceptance.

## Limits

- 2D per-unit-length only; no 3D, no axisymmetry, no finite-thickness along z.
- Free charge is a prescribed density: no space-charge transport, no
  semiconductor or electrolyte physics, no nonlinear permittivity.
- Anisotropic permittivity is not accepted here (the tensor path of
  `assemble_stiffness` remains available to callers assembling by hand).
- P1 element fields are not an equilibrated flux: conductor charges come from the
  assembled reactions, not from integrating `D.n` along edges.
- `sipi` line parameters (`C`, `C0`, `L`, `G`) keep using `sipi.capacitance_matrix`.
- Complex permittivity is NumPy only; JAX and PyTorch inputs are real.
