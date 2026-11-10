# Shape derivatives: moving the mesh with a design parameter

**English** | [한국어](../../locales/ko/pages/packages/galerkin/shape_derivative.md)

[galerkin overview](overview.md) · [Derivatives with JAX and PyTorch](differentiation.md)

`galerkin.shape` gives derivatives with respect to a design parameter that moves
the mesh, such as a layer thickness or a hole radius. It covers steady Cartesian
heat (`galerkin.thermal.solve_steady_heat`, 2026-11-09) and steady electric
conduction (`galerkin.electric.solve_steady_electric`, 2026-11-10). The other
solvers follow the same frame later.

## What is differentiated

A design parameter t moves every node: **X(t) = X₀ + t·W**.
- **W** is a fixed NumPy mesh velocity of shape (N, 2): node motion in the
  mesh's length unit per unit of t.
- **t** is the only live value, a JAX or PyTorch scalar. Its number is the step
  at which the solve runs, usually 0, i.e. the mesh as given.
- Connectivity, tags and regions stay fixed.

The derivative is the exact derivative of the discrete solution on that moving
mesh: moving the nodes by ±h·W and solving again gives the same value up to
finite-difference truncation.

The solve runs once on the moved mesh with the ordinary solver, so every input
check, residual tolerance and heat balance applies unchanged. One more live
solve then attaches the derivative: T = T₀ + A(t)⁻¹ (b(t) − A(t) T₀). Here A(t)
and b(t) are assembled from X₀ + t·W in the live library (P1 stiffness, region
sources, and the flux and Robin terms on the moving edges), and T equals T₀ up to
rounding. `temperature`, `heat_flux`, `load`, `reaction` and `residual` carry the
derivative.

```python
import jax
import jax.numpy as jnp
from galerkin.shape import MeshMotion, admissible_interval, extend_velocity
from galerkin.thermal import solve_steady_heat

jax.config.update("jax_enable_x64", True)
W = extend_velocity(mesh, boundary_velocity, on_curve)   # (N, 2)
lo, hi = admissible_interval(mesh, W)                    # no element inverts for lo < t < hi


def heat_in(t):
    r = solve_steady_heat(mesh, conductivity=k, dirichlet=dirichlet, motion=MeshMotion(W, t))
    return jnp.sum(r.reaction[hot])


dQ = jax.grad(heat_in)(jnp.asarray(0.0))
```

With PyTorch, pass `torch.tensor(0.0, dtype=torch.float64, requires_grad=True)`
and call `.backward()`.

## Steady electric conduction

`solve_steady_electric(mesh, ..., motion=MeshMotion(W, t))` works the same way:
- The ordinary solve runs on the moved mesh, with its residual, current-balance
  and power-balance checks.
- One live solve re-assembles the system from X₀ + t·W: P1 stiffness with region
  conductivity, and the outward current on moving edges.
- Every field carries d/dt: `potential`, `electric_field`, `current_density`,
  `joule_heating`, `joule_load`, `joule_power_per_length`, `reaction`,
  `prescribed_outward_load`, `residual` and `supplied_power_per_length`.
  `result.mesh` is the NumPy snapshot of the moved mesh; its coordinates carry no
  derivative.
- Dirichlet volts and `reference_potential` gauges (components with only current
  data) are both taken. On a gauge component the motion must keep the net imposed
  current at zero, for example by keeping the current-carrying sides' lengths.
  Otherwise the problem has no solution next to t, and the call is refused.
- As in the solver, volts are taken relative to each component's offset, so a
  large common-mode voltage does not reach the power or its derivative.
- The discrete power identity, Joule power = supplied power, also holds for the
  derivatives (validation E5).

## The mesh velocity

Nodes on the geometry's curves move as the design moves them. For a version 1
geometry document, `simcase.geometry_velocity.design_velocity(document,
p).node_velocity(meshine_mesh)` gives them
([design velocity](../simcase/geometry_engine.md#design-velocity-stage-4)). Its
`values` are dimensionless (∂x/∂p, with x and p in the document unit), so t is
then the parameter change in the mesh's length unit. `galerkin.interop.from_mesher`
keeps the meshine node order.

`extend_velocity(mesh, values, known, method="harmonic")` moves every other node.
It solves a Laplace problem per component on the same mesh, with the known
nodes' values as Dirichlet data:
- `"harmonic"` (the default) uses unit diffusivity. It reproduces an affine
  motion exactly.
- `"stiffened"` divides the diffusivity by the element area, so that small
  elements move more rigidly.

The choice changes the discrete derivative only at discretisation level; the
difference vanishes as the mesh is refined (validation S4 below). It mainly
decides how far a step can go before an element inverts.

## Element inversion and remeshing

Each element's signed area under X₀ + t·W is a quadratic in t.
`admissible_interval(mesh, W)` returns the nearest roots on each side over all
elements: the open interval in which no element inverts. A solve at a step
outside it raises `galerkin.shape.ElementInversion`, which names the interval.
The derivative at t = 0 is always defined.

galerkin never remeshes: a derivative belongs to the mesh it was computed on.
The caller regenerates the mesh from the geometry at the new parameter value.
The recommended trigger is a step that leaves half of the admissible interval, or
a minimum angle that falls below the mesher's `min_angle`. Across a remesh the
functional and its derivative change at discretisation level, the size of the
convergence errors below.

## Refused

Each refusal names the reason:
- a NumPy `t` (`TypeError`): NumPy does not differentiate. To solve on a moved
  mesh, move the nodes and solve that mesh;
- a live mesh velocity; a velocity of the wrong shape, or one that is not finite;
- a step outside the admissible interval (`ElementInversion`);
- coordinate callbacks for the heat source, outward flux, convection or outward
  current, also inside a convection pair, and `ElementHeatSource` and
  `ElementConductivity`: their sample points move with the mesh;
- live conductivity, source, boundary, Dirichlet or reference values together
  with a motion: t is the one live input of such a call;
- `coordinate_system="axisymmetric"`;
- `motion=` on any other solver: it is not a keyword there;
- second derivatives: JAX forward mode and PyTorch `create_graph=True` raise, as for every galerkin solve
  ([refused](differentiation.md#refused-not-approximated)).

## Validation

`tests/galerkin/test_shape_derivative.py` holds checks S1–S8, pre-registered
before the implementation. They were measured on 2026-11-09 on Linux with JAX
0.12.0.1 and PyTorch 2.14.1+cpu.

| Check | Criterion | Result |
|---|---|---|
| S1 discrete consistency | derivative vs central differences of moved meshes (h = 1e-4) for a probe temperature, the Dirichlet heat and the mean temperature, with a source, convection and flux on moving sides; relative 1e-6, JAX and PyTorch | 1.7e-9, 9.2e-10, 4.1e-9 |
| S2 two-layer slab | dR/dL₁ = 1/k₁ − 1/k₂, relative 1e-10 | exact to about 1e-14 |
| S3 annulus | inner radius from the geometry engine's node velocities; dQ/da = 2πk/(a ln²(b/a)); observed order ≥ 1.5, finest within 1e-3 | 8.1e-3, 2.1e-3, 5.8e-4 at sizes 0.8, 0.4, 0.2; order 1.97 and 1.84 |
| S4 extension independence | harmonic vs stiffened derivative gap: order ≥ 1, finest within 1e-3 | 2.4e-4, 5.4e-5, 1.6e-5; order 2.1 and 1.8 |
| S5 rigid translation | dJ/dt = 0 within 1e-12 · \|J\| | pass |
| S6 inversion bound | the interval equals the exact roots; a step beyond it is refused | pass |
| S7 unchanged | without `motion` the result equals the previous code | sha256 of the result arrays equal to main `627eb28` (measured); `motion=None` equals no keyword (test) |
| S8 refusals | as listed above | pass |

`tests/galerkin/test_shape_derivative_electric.py` holds checks E1–E8 for
steady electric conduction, pre-registered on 2026-11-10 and measured that day
with the same versions.

| Check | Criterion | Result |
|---|---|---|
| E1 discrete consistency | derivative vs central differences of moved meshes (h = 1e-4) for a probe potential, the terminal current and the Joule power, with region conductivity and an outward current on a moving side; relative 1e-6, JAX and PyTorch | 7.2e-10, 1.9e-9, 1.2e-9 |
| E2 two-layer resistor | dR/dL₁ = (1/σ₁ − 1/σ₂)/H, relative 1e-10 | pass |
| E3 coaxial conductor | inner radius from the geometry engine's node velocities; dI/da = 2πσΔV/(a ln²(b/a)); observed order ≥ 1.5, finest within 1e-3 | 8.1e-3, 2.1e-3, 5.8e-4 at sizes 0.8, 0.4, 0.2 |
| E4 rigid translation | dJ/dt = 0 within 1e-12 · \|J\| (power, sum of potentials) | pass |
| E5 power identity | d(Joule power)/dt = d(supplied power)/dt, relative 1e-10 | 9e-14 (JAX), 5e-14 (PyTorch) |
| E6 unchanged | without `motion` the result equals the previous code | sha256 of the result arrays equal to main `a0a432b` (measured); `motion=None` equals no keyword (test) |
| E7 gauge component | a component with only current data and a `reference_potential`: E1 criterion | pass |
| E8 refusals | as listed above | pass |

An independent review then added regression tests: a common-mode voltage up to
1e9 V (E5 criterion), and a motion that changes a current-only component's
balance (refused).
