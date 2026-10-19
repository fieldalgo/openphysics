# Piecewise-constant materials on named regions

**English** | [한국어](locales/ko/pages/multimaterial.md)

Heat conduction can assign a different material to each named region of a 2D
mesh. This page holds the shared input rule, the steady-heat contract and its
independent validation. Further physics will be added here as it is
validated; until then their pages state that only one homogeneous material is
accepted.

## Input rule

Each material property argument accepts exactly one of:

| Form | Meaning |
| --- | --- |
| finite real scalar | One homogeneous material (the original contract, unchanged) |
| `{region name: scalar}` | One value per region; keys must equal `mesh.region_names` exactly |

```python
from galerkin.mesh import layered_rectangle_mesh
from galerkin.thermal import solve_steady_heat

mesh = layered_rectangle_mesh([0.02, 0.05], 0.02, [4, 6], 4, ["steel", "foam"])
dirichlet = {int(i): 400.0 for i in mesh.boundary["left"]}
dirichlet.update({int(i): 300.0 for i in mesh.boundary["right"]})
result = solve_steady_heat(
    mesh,
    conductivity={"steel": 45.0, "foam": 0.04},   # W/(m K)
    heat_source={"steel": 2e5, "foam": 0.0},      # W/m^3
    dirichlet=dirichlet,
)
```

- Region names come from `Mesh.region_names`: `disk_mesh`,
  `layered_rectangle_mesh`, `layered_annulus_mesh`, or gmsh physical groups
  read through gmshio. `mesh.regions` holds one region id per triangle.
- A missing name, an unknown name, a non-string key, or a value that fails the
  property's own check (for example k <= 0) raises `ValueError` naming the
  region. A mapping on a mesh without region data is rejected.
- Bare per-triangle arrays are **not** accepted by the physics APIs. A
  length-M sequence is ambiguous with vector or tensor input, and the original
  contract rejects such sequences. Low-level assembly routines
  (`assemble_stiffness`, the electromagnetic mode solvers' `eps_r`) keep their
  per-triangle array input.
- Units are those of the scalar argument. A mapping never converts units.
- A scalar input follows the original code path, so homogeneous results are
  unchanged bit for bit; a mapping with the same value in every region gives
  the same arrays as the scalar.

Material properties are constant within each triangle. Interfaces must lie on
element edges (meshes that follow region boundaries, as all generators above
do); a region that cuts through triangles is not representable.

## Steady heat conduction

`galerkin.thermal.solve_steady_heat` accepts per-region `conductivity` k > 0
in W/(m K) and per-region constant `heat_source` Q in W/m^3. Scalars and the
existing coordinate callback for Q are unchanged. The weak form is the same
with k and Q constant on each triangle:

```text
K_ij = sum_e k_e integral_e grad(N_i).grad(N_j) dA,   f_i = sum_e Q_e integral_e N_i dA
heat_flux_e = -k_e grad(T_h) on triangle e
```

Temperature is continuous (P1). The exact normal heat flux is continuous across
an interface while the gradient jumps by the conductivity ratio; the
element-constant P1 flux satisfies this only in the limit, with an O(h)
jump. Perfect thermal contact is assumed: no contact resistance and no
interface heat source. Boundary conditions, reactions and balance checks are
those of [thermal_steady2d](thermal_steady2d.md) and
[thermal_flux_robin](thermal_flux_robin.md).

## Independent references

`refsol.thermal_multilayer` evaluates two closed forms and imports only NumPy:

- `layered_slab`: series wall 0 < x_1 < ... < x_n = L with k_i and uniform
  Q_i per layer, T(0)=T_L, T(L)=T_R. The flux is q(x) = q_0 + integral of Q,
  T' = -q/k, and q_0 follows from T(L); without sources this is the series
  thermal resistance q_0 = (T_L-T_R)/sum(L_i/k_i).
- `composite_cylinder`: concentric shells r_0 < ... < r_n with k_i and Q_i,
  T(r_0)=T_i, T(r_n)=T_o. r q_r = C + integral of Q r dr and
  T = A_i - (C + offset_i) ln(r)/k_i - Q_i r^2/(4 k_i) in each shell.

The reference tests check, by finite differences only, Fourier's law and
energy balance in every layer, temperature and flux continuity at every
interface, boundary values, the series/log resistance formulas without source,
radial direction of the flux, and the single-layer textbook formulas. An
optional `layer=` index evaluates a layer's closed form as its analytic
continuation, so points of a polygonal mesh triangle just beyond a curved
interface are compared with their own triangle's material.

## Acceptance (fixed before the comparison)

`packages/galerkin/tests/test_thermal_multimaterial.py`:

| Case | Mesh | Gate |
| --- | --- | --- |
| Uniform mapping vs scalar | 2-region rectangle | Every result array identical |
| Three-layer wall, no source (k 15/0.8/45) | layered rectangle | Nodal T error <= 1e-10 of 420 K; flux equal in all layers; side reactions = exact q·height to 1e-10 |
| Three-layer wall with sources Q 2e5/-3e4/6e5 | layered rectangle, n=1,2,4,8 | T L2 order >= 1.8 and flux L2 order >= 0.9 on the last two intervals; variational interface heat rate from each side within 1e-9 of the exact rate |
| Three-shell cylinder, k 50/0.25/16, Q 1e6/0/-2e5 | layered annulus, n=1,2,4,8 | T L2 order >= 1.8, flux L2 order >= 0.9, interface heat rate order >= 1.8, mean normal-flux jump order >= 0.9 (last two intervals) |
| Invalid regions | — | Missing/unknown/nonpositive/nonfinite/complex/boolean/sequence values, integer keys, bare arrays, no region data and out-of-range region ids raise `ValueError` |

Errors use an independent 8x8 Duffy quadrature in every triangle. The
variational interface heat rate is the residual of one side's own stiffness
and load summed over the interface nodes.

Observed when the gates were first run (Linux, Python 3.12):

| Quantity | n=1 → 2 → 4 → 8 | Orders |
| --- | --- | --- |
| Wall T L2 (K m) | 8.77e-3, 2.24e-3, 5.63e-4, 1.41e-4 | 1.97, 1.99, 2.00 |
| Wall flux L2 (W/m) | 26.1, 13.4, 6.76, 3.39 | 0.96, 0.99, 1.00 |
| Wall interface rate (relative) | 2.5e-13, 2.6e-13, 2.0e-13, 1.5e-13 | roundoff |
| Cylinder T L2 (K m) | 5.40e-2, 1.35e-2, 3.39e-3, 8.47e-4 | 2.00, 2.00, 2.00 |
| Cylinder flux L2 (W/m) | 19.0, 9.41, 4.70, 2.35 | 1.01, 1.00, 1.00 |
| Cylinder interface rate (relative) | 8.5e-3, 2.1e-3, 5.3e-4, 1.3e-4 | 2.00, 2.00, 2.00 |
| Cylinder normal-flux jump (relative) | 0.186, 0.092, 0.046, 0.023 | 1.01, 1.00, 1.00 |

The wall data are independent of y, so P1 nodal values and the variational
interface rate are exact there; the cylinder's interface rate converges at
second order through the inscribed polygon. Run them with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s \
  packages/galerkin/tests/test_thermal_multimaterial.py \
  packages/galerkin-refsol/tests/test_thermal_multilayer_reference.py
```

## Limits

- Piecewise constant per region only: no conductivity varying inside a region,
  no anisotropic tensors, no temperature-dependent properties.
- No contact resistance or interface sources.
- Elasticity, thermoelasticity, the heat-to-mechanics workflows, transient heat
  and simcase documents still accept one homogeneous material.
