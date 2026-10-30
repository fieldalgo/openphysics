# Axisymmetric steady heat

**English** | [한국어](../../locales/ko/pages/packages/galerkin/thermal_axisymmetric.md)

`solve_steady_heat(..., coordinate_system="axisymmetric")` solves scalar steady
conduction on a P1 triangle mesh whose coordinates are **(r,z) in metres**.
The default `"cartesian"` keeps the existing per-thickness formulation.

```python
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat

R, L, k, Q, Tb = .003, .001, 1.114, 1e5, 293.15
mesh = rectangle_mesh(R, L, 64, 32)
result = solve_steady_heat(
    mesh, conductivity=k, heat_source=Q,
    dirichlet={int(i): Tb for i in mesh.boundary["right"]},
    coordinate_system="axisymmetric",
)
assert result.nodal_heat_rate_unit == "W"
absorbed_W = result.load.sum()
outward_W = -result.reaction.sum()
exact_rise = Q*(R**2-mesh.nodes[:, 0]**2)/(4*k)
```

## Measure and boundaries

The weak form integrates `k grad(T)·grad(v)` and `Q v` with volume measure
`2*pi*r dr dz`. Boundary flux and Robin terms use `2*pi*r ds`. These are full
revolutions, not per-radian or per-thickness results. The same scalar conductivity,
region maps, callbacks, `ElementHeatSource`, Dirichlet, flux and Robin contracts
of [steady heat](thermal_steady2d.md) apply.

`core.measure.ScalarMeasure` supplies the static geometry weights to the existing
element kernels, `core.forms` assembly and load quadrature. The stiffness weight
is exact for P1 with elementwise constant conductivity; the source integrates
`Q N_i 2*pi*r` consistently, including when Q is constant per element. It is not
an equal three-way split of the element power. Boundary weights are evaluated
at the existing Gauss points. No separate thermal solver is used.

All radii must be nonnegative. At `r=0`, finite P1 functions and the weighted weak
form provide natural axis regularity without a `1/r` evaluation or an axis heat
source. A nonzero flux or convection coefficient on an axis edge is rejected.
Dirichlet data at nodes lying only on the axis are rejected; an axis endpoint
on a physical end-face boundary may carry that face's Dirichlet temperature.
Annular domains with strictly positive r are also permitted.

Unselected physical edges are insulated. Every connected component still needs
Dirichlet or positive Robin support. Pure-Neumann solves are not supported.

## Units and coupling

`temperature` is K, and `heat_flux` is `(q_r,q_z)` in W/m². All integrated nodal
rates (`load`, `reaction`, `residual`, boundary loads and `system_rhs`) are W.
The result records `coordinate_system` and `nodal_heat_rate_unit`. Cartesian
results record `"cartesian"` and `"W/m"`. The outward heat balance is
`sum(load + reaction - prescribed_outward_load - convective_outward) = 0`.

An element [Field](coupling.md) in W/m³ still means volume density, never
power per meridional area. Its cell volume is `2*pi*mean(r_vertices)*area`.
`Field` stores its mesh and unit, **not the coordinate interpretation**; the
caller must preserve the axisymmetric coordinate/measure metadata in its own
workflow record. Same-mesh `transfer` does not infer it. This option introduces
no simcase JSON schema, Studio workflow or mesh-to-grid projection. Do not label
these rates with the existing Cartesian saved-result identifier.

Coefficients and boundary values retain the existing JAX/PyTorch reverse-mode
paths, with static geometry. Fields between physics remain NumPy-only. No
geometry derivative or differentiable Field transfer is claimed.

## Verification and limits

`tests/galerkin/test_thermal_axisymmetric.py` checks:

- Exact cylinder `T-Tb=Q(R²-r²)/(4k)`, full absorbed power `Q*pi*R²*L`,
  and reaction balance at relative tolerance 1e-10.
- Cylinder and curved-domain manufactured solutions on radial subdivisions
  16/32/64/128: weighted L2 orders 1.8–2.2, H1 orders 0.9–1.2,
  finest relative L2 ≤0.5%. The curved manufactured solution imposes
  `q_out=Q*r*n_r/2` on the sloping face; it is not an insulated-face test.
- Exact linear axial temperature with nonzero prescribed flux or Robin data,
  a Robin-only cylinder, four source forms, zero heating, and axis input guards.
- Exact constant-source shape-function moments, logarithmic annular conduction,
  and full-revolution length scaling (nodal power scales with length).
- JAX and PyTorch conductivity/source gradients against the exact discrete
  scaling `T ∝ Q/k` (relative tolerance 1e-6).

The added pointwise cylinder gates initially failed at nr32 (0.02444 K versus
0.02 K) and the Robin gate at nr64 (0.00007059 K versus 0.00006 K). Refining to
nr64/nr128 met the **same** tolerances; this does not make coarse meshes accurate.
The local related run passed 213 tests, including both array libraries. It used
Linux/Python3.12.14, NumPy2.3.5, SciPy1.17.0, JAX0.12.0.1 and PyTorch2.15.0+cpu.
PyTorch emitted its upstream `asarray` default warning. Required CI and other
platform results are separate from this local evidence. An additional related
thermal/Joule/Field/forms run passed 261 tests; the final axisymmetric file alone
passed 21 tests. These overlapping runs are not summed.

This is steady scalar axisymmetric conduction. It does not add angular modes,
structural deformation, transient heat, optical propagation or thermal radiation.
