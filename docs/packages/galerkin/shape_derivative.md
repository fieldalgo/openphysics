# Shape derivatives: moving the mesh with a design parameter

**English** | [한국어](../../locales/ko/pages/packages/galerkin/shape_derivative.md)

[galerkin overview](overview.md) · [Derivatives with JAX and PyTorch](differentiation.md)

`galerkin.shape` gives derivatives with respect to a design parameter that moves
the mesh, such as a layer thickness or a hole radius. It covers steady heat
(`galerkin.thermal.solve_steady_heat`, Cartesian 2026-11-09, axisymmetric
2026-11-21), steady electric
conduction (`galerkin.electric.solve_steady_electric`, 2026-11-10), linear
elasticity (`galerkin.elasticity.solve_elasticity`, 2026-11-10),
thermoelasticity (`galerkin.thermoelasticity.solve_thermoelasticity` and
`galerkin.thermal_mechanical.solve_steady_thermoelasticity`, 2026-11-10),
transient heat (`galerkin.transient_heat.solve_transient_heat`, Cartesian
2026-11-10, axisymmetric 2026-11-21) and waveguide modes (`galerkin.kernels.solve_modes`, 2026-11-11; with a modal PML
2026-11-21). The
other
solvers follow the same frame later. In 3D it covers steady heat
(`galerkin.thermal3d.solve_steady_heat_3d`, 2026-11-21).

## What is differentiated

A design parameter t moves every node: **X(t) = X₀ + t·W**.
- **W** is a fixed NumPy mesh velocity of shape (N, 2) ((N, 3) on a `Mesh3D`), `MeshMotion.design_velocity`
  (keyword-only, like `t`): node motion in the mesh's length unit per unit of t.
- **t** is the only live value, a JAX or PyTorch scalar. Its number is the step
  at which the solve runs, usually 0, i.e. the mesh as given.
- Connectivity, tags and regions stay fixed.

The derivative is the exact derivative of the discrete solution on that moving
mesh: moving the nodes by ±h·W and solving again gives the same value up to
finite-difference truncation.

The solve runs once on the moved mesh with the ordinary solver, so every input
check, residual tolerance and heat balance applies unchanged. One more live
solve then attaches the derivative: T = T₀ + A(t)⁻¹ (b(t) − A(t) T₀), computed on
the increments over the offsets below. Here A(t)
and b(t) are assembled from X₀ + t·W in the live library (P1 stiffness, region
sources, and the flux and Robin terms on the moving edges), and T equals T₀ up to
rounding. `temperature`, `heat_flux`, `generated_heat_rate_per_depth`,
`reaction_heat_rate_per_depth` and `residual_heat_rate_per_depth` carry the derivative.
As in the solver, temperatures are taken relative to each component's offset (its
first Dirichlet value, else the ambient of its first convection side with h > 0), so
a large common temperature does not reach the reactions, convection, flux or their
derivatives (S9).

```python
import jax
import jax.numpy as jnp
from galerkin.shape import MeshMotion, admissible_interval, extend_velocity
from galerkin.thermal import solve_steady_heat

jax.config.update("jax_enable_x64", True)
W = extend_velocity(mesh, boundary_velocity, on_curve)   # (N, 2)
lo, hi = admissible_interval(mesh, design_velocity=W)                    # no element inverts for lo < t < hi


def heat_in(t):
    r = solve_steady_heat(mesh, thermal_conductivity=k, prescribed_temperature=dirichlet,
                          motion=MeshMotion(design_velocity=W, t=t))
    return jnp.sum(r.reaction_heat_rate_per_depth[hot])


dQ = jax.grad(heat_in)(jnp.asarray(0.0))
```

With PyTorch, pass `torch.tensor(0.0, dtype=torch.float64, requires_grad=True)`
and call `.backward()`.

## Steady electric conduction

`solve_steady_electric(mesh, ..., motion=MeshMotion(design_velocity=W, t=t))` works the same way:
- The ordinary solve runs on the moved mesh, with its residual, current-balance
  and power-balance checks.
- One live solve re-assembles the system from X₀ + t·W: P1 stiffness with region
  conductivity, and the current density on moving edges (the inward value,
  negated once before the motion is applied, as for heat).
- Every field carries d/dt: `electric_potential`, `electric_field`, `current_density`,
  `electrical_conductivity`, `joule_power_density`, `generated_heat_rate_per_depth`,
  `joule_power_per_depth`, `reaction_current_per_depth`,
  `outward_prescribed_current_per_depth`, `residual_current_per_depth` and
  `inward_electric_power_per_depth`.
  `result.mesh` is the NumPy snapshot of the moved mesh; its coordinates carry no
  derivative.
- Prescribed volts and `reference_electric_potential` gauges (components with only current
  data) are both taken. On a gauge component the motion must keep the net imposed
  current at zero, for example by keeping the current-carrying sides' lengths.
  Otherwise the problem has no solution next to t, and the call is refused.
- As in the solver, volts are taken relative to each component's offset, so a
  large common-mode voltage does not reach the power or its derivative.
- The discrete power identity, Joule power = supplied power, also holds for the
  derivatives (validation E5).

## Linear elasticity

`solve_elasticity(mesh, ..., motion=MeshMotion(design_velocity=W, t=t))` takes plane stress and
plane strain, scalar or region Young's modulus and Poisson ratio, a constant body
force, constant tractions on boundary tags (they move with their edges) and
prescribed displacements `{(node, component): value}`. The displacement, strain,
stress and the applied, reaction and residual forces per depth carry d/dt.
- The Dirichlet values stay attached to their nodes as the nodes move.
- A large rigid displacement offset (Dirichlet values far larger than the
  elastic deformation) costs precision in the result and its derivative, as it
  does in the solver itself.

## Thermoelasticity

Two paths take `motion=`. They differ in how the temperature field moves with the
mesh.
- **A prescribed temperature**, `solve_thermoelasticity(mesh, snapshot, ...,
  motion=MeshMotion(design_velocity=W, t=t))`:
  - The snapshot belongs to the mesh as given (X₀) and is checked against it, as
    without a motion.
  - Its nodal temperatures stay attached to their nodes as they move, like
    Dirichlet displacements. The derivative therefore comes from the geometry
    alone: strain matrices, element areas and loaded edge lengths.
  - It takes what linear elasticity takes, plus scalar or region thermal expansion
    and the reference temperature.
- **The heat-then-mechanics workflow**, `solve_steady_thermoelasticity(...,
  motion=MeshMotion(design_velocity=W, t=t))`:
  - The ordinary workflow runs once on the moved mesh, with every stage check and
    its manifest.
  - The heat stage is then solved again on the moving mesh (as in steady heat
    above), and its live temperature drives the live mechanical stage. The
    derivative therefore includes the change of the temperature field.
  - `result.heat` and `result.mechanics` both carry d/dt.
  - `result.reference_mesh`, `result.temperature_snapshot` and the manifest
    describe the moved mesh and carry no derivative.
- Both paths: displacement, the three strains, stress, `stress_zz`, `strain_zz`,
  the external and thermal loads, reaction, residual and the strain energy (each
  per depth) carry d/dt. `result.temperature_snapshot` is the moved mesh's snapshot.
- A temperature field fixed in space and sampled at the moving nodes is not
  offered: that needs a coordinate callback (refused below).

## Transient heat

`solve_transient_heat(mesh, ..., motion=MeshMotion(design_velocity=W, t=t))` takes region
conductivity and heat capacity, a constant or region heat source, the inward heat flux and
convection on boundary tags (they move with their edges), and Dirichlet values.
- The ordinary backward-Euler solve runs once on the moved mesh, with every step
  check.
- Each step then gets one live correction from the mass, stiffness and Robin
  matrices and loads assembled from X₀ + t·W. Every history carries d/dt:
  temperature, heat flux, source load, reaction, residual, storage rate, heat
  content, quadratic functional, and the prescribed and convective outward rates.
- The initial temperatures and the Dirichlet values stay attached to their nodes
  as they move, as in thermoelasticity.
- Callbacks of time alone, `callback(time)`, are taken for the Dirichlet values,
  the inward heat flux and the convection h and ambient. They do not depend on node
  positions. A callback of time must return NumPy numbers and must be pure: it is
  called once for the ordinary solve and once more for the derivative. (A
  time-dependent h that returns a live value gets the solver's own refusal of a
  live time-dependent h.)
- Coordinate callbacks are taken too (2026-11-22): the source `callback(position, time)`
  and the boundary `callback(position, outward_normal)` (sampled once) or
  `callback(position, outward_normal, time)` (sampled at the end of every step, as the
  ordinary solve does). They are called once more at the live points and normals, as in
  steady heat (next section), so they must compute with the JAX or PyTorch points they get.
  `tests/galerkin/test_shape_derivative_transient_callbacks.py` holds ET1–ET7: every history
  equals the moved mesh's ordinary solve within 1e-12, the derivative equals Richardson
  differences within 1e-8, JAX and PyTorch agree within 1e-12, and a fixed time-dependent
  source and a field flux on a growing side give their closed-form rates and derivatives
  within 1e-10. Coordinate callbacks of the Dirichlet values stay refused.
- `checkpoint_every` is refused with a motion: every step is kept.

## Coordinate callbacks in steady heat

`solve_steady_heat` takes coordinate callbacks with a motion (Cartesian and axisymmetric, 2026-11-22): the heat
source `callback(points)`, the inward heat flux `callback(points, normals)` and the convection
h and ambient `callback(points, normals)`, alone or inside a convection pair.
- The callback describes a field fixed in space. Its sample points move with the mesh, so
  the derivative includes the callback's own change along the motion, ∇f·W.
- The ordinary solve on the moved mesh calls it once with NumPy points. The live assembly
  calls it once more with the live points and unit outward normals of the same rules (the
  6 × 6 Duffy rule on triangles, 4-point Gauss on edges), as JAX arrays or PyTorch tensors.
  With `coordinate_system="axisymmetric"` the weights carry 2πr at the live points, as in
  the ordinary solve.
- It must therefore compute with array operations on the points it is given, and be pure.
  A callback that returns NumPy numbers for live points (`np.asarray`, `np.ones(len(p))`),
  or raises on them, is refused with a `TypeError` that names it.
- Not covered yet: coordinate callbacks in steady electric conduction, elasticity and 3D heat, and callable coefficients
  (conductivity and the rest) or Dirichlet values.

`tests/galerkin/test_shape_derivative_callbacks.py` holds E1–E7, pre-registered on 2026-11-22:
the numbers equal the moved mesh's ordinary solve within 1e-12 (E1); the derivative of a
reaction-plus-temperature objective with all three kinds of callback equals Richardson central
differences within 1e-8 (E2), as does a flux callback on a side moving along its normal (E5);
JAX and PyTorch agree within 1e-12 (E3); a strip with the fixed source Q0·x gives the
analytic dQ/dL = −Q0·L·H/3 at x = 0 within 1e-10 (E4); NumPy-only callbacks are refused by
name (E6); and a call without a motion is unchanged (E7).
`tests/galerkin/test_shape_derivative_callbacks_axisymmetric.py` holds EA1–EA7 for the
axisymmetric solve, with the same bounds; EA4 checks a hollow cylinder insulated except at
z = 0, where heat balance gives the reaction and its derivative in the length and in the
outer radius in closed form, within 1e-10.

## Axisymmetric heat

`solve_steady_heat` and `solve_transient_heat` with `coordinate_system="axisymmetric"`
take a motion with the same inputs as the Cartesian solves (2026-11-21). The coordinates are (r, z), and the 2πr measure moves with the
nodes. The live assembly uses exact closed forms, since r is linear on each triangle and
edge (no quadrature):
- stiffness k(bbᵀ + ccᵀ)/(4A) · 2πr̄, with r̄ the mean of the three vertex radii;
- region source 2πQA(2rᵢ + rⱼ + rₖ)/12;
- edge flux and convection ambient 2πgL(2rₐ + r_b)/6;
- Robin edge matrix 2πhL/12 · [[3rₐ + r_b, rₐ + r_b], [rₐ + r_b, rₐ + 3r_b]];
- consistent mass 2πcA Σₘ rₘ ∫φᵢφⱼφₘ/A, the cubic moments of the NumPy mass.

Nodes on the symmetry axis (r = 0 at the step t) must stay on it: a design velocity
with a radial component there is refused by name. Negative radii and Dirichlet values only on the
axis keep the ordinary solve's refusals on the moved mesh. Results are the
axisymmetric classes, with rates in W over the full revolution; they carry the
derivative as in the Cartesian solves.

`tests/galerkin/test_shape_derivative_axisymmetric.py` holds A1–A8, pre-registered
on 2026-11-21 before the implementation ran, and measured that day:

| Check | Criterion | Result |
|---|---|---|
| A1 numbers | the motion's temperature and rates equal the ordinary solve on the moved mesh, relative 1e-12 | 5.3e-16 |
| A2 steady consistency | r–z section with a region source, inward flux and convection on moving sides: dT/dt against a Richardson central difference of moved meshes (h = 2e-3), within 1e-8 · max \|dT/dt\| | 3.1e-12 |
| A3 libraries | JAX and PyTorch within 1e-12 | 1.9e-15 |
| A4 rigid translation along z | dT/dt = 0 within 1e-10 · max \|T\| | 2.3e-16 |
| A5 hollow cylinder | a = 1, b = 2, T(a) = 400, T(b) = 300: the inner-wall heat rate differentiated in b against −2πkH(T₁ − T₂)/(b ln²(b/a)); order ≥ 1.5, finest within 1 % | 8.6e-4, 2.2e-4, 5.4e-5 at 8, 16, 32 radial cells; order 1.99 and 2.00 |
| A6 transient | the same section, five backward-Euler steps: the last temperatures as A2 | 2.4e-10 |
| A7 refusals | a radial velocity on the axis (steady and transient), a live conductivity, an unknown coordinate system | pass |
| A8 unchanged | without a motion the results equal main `54485b12` | sha256 equal for steady and transient (measured on one machine); `motion=None` equals no keyword (test) |

## Waveguide modes

The public `galerkin.solve_waveguide_modes(mesh, *, ..., motion=MeshMotion(design_velocity=W, t=t))`
passes the motion to its kernel with the converted inputs; it refuses a motion together with a
`Bend`, and live materials or a live wavelength with a motion (a `ModalPML` takes a motion that
leaves the layer in place, below). The kernel:

`solve_modes(mesh, eps_r, k0, n_target, ..., motion=MeshMotion(design_velocity=W, t=t))` takes eps_r
and mu_r as scalars or per-element arrays (real or complex), PEC nodes and edges as
without a motion, and numbers for k0 and n_target.
- The NumPy eigensolve runs on the moved mesh.
- Each mode then takes the bordered Newton step of the live-input path
  ([waveguide modes](differentiation.md#waveguide-modes-eigenvalues-fields-and-degenerate-modes)).
  Its A(t) and B(t) are assembled from X₀ + t·W: the Nédélec curl-curl, mass and
  coupling blocks and the P1 stiffness and mass.
- `n_eff`, `et` and `ez` carry d/dt. The fields keep the same gauge (unit 2-norm,
  largest entry real and positive), so gauge-free quantities have gauge-free
  derivatives. The returned space belongs to the moved mesh.
- `eval_edge_field(space, et[i])` uses the space's NumPy geometry, so with a
  motion the centroid field carries only the coefficients' part of the
  derivative, not the moving basis functions'. Differentiate quantities of the
  coefficients (n_eff, overlaps built from et and ez) instead.
- Degenerate modes keep exact values and get NaN derivatives and a
  `DegenerateModeWarning`, as for material derivatives (decision 2026-11-11). A
  sorted mode has no derivative where two modes cross: on a square silicon core
  the upper mode's one-sided slopes in the width are 2.28 and 5.70 µm⁻¹ (a
  0.3 × 0.3 µm silicon core in silica, λ = 1.55 µm, a 3 × 3 µm PEC window, mesh
  size 0.02 µm, second-order one-sided differences; the finite-difference mode
  solver modesolverpy gave 2.25 and 5.53 on a 0.01 µm grid).
- Each branch through the crossing is smooth, and
  `galerkin.waveguide.degenerate_branch_derivatives(mesh, *, ..., motion,
  relative_tolerance=DEGENERATE_GAP)` gives its slope (decision 2026-11-21). It
  takes the arguments of `solve_waveguide_modes` with a motion. For a group of
  returned modes within `relative_tolerance` of each other, with V their
  eigenvectors:
  - M = Vᵀ(dA/dt − λ dB/dt)V and N = VᵀBV (no conjugate);
  - the generalized eigenvalues of (M, N) are dλ/dt of the branches, and
    dn_eff/dt = −dλ/dt / (2 k0² n_eff);
  - their eigenvectors combine the returned modes into the branch modes.

  The result is one `DegenerateModeBranches(mode_index, effective_index,
  effective_index_derivative, mode_combination)` per group, or an empty list.
  The slopes come largest first, as NumPy numbers per unit of t, under
  exp(−iωt). dA/dt and dB/dt are taken in t's library.
- Refused by name:
  - a group with a member that was not returned (raise `search_mode_count`);
  - a group whose members chain farther apart than `relative_tolerance`;
  - a `relative_tolerance` outside (0, 1e-3];
  - complex slopes on a real problem.

  `ElementInversion` from the motion passes unchanged.
- A `relative_tolerance` above `DEGENERATE_GAP` also groups nearly degenerate
  modes, such as a symmetric pair that a mesh splits slightly. Their slopes are
  then those of the exactly degenerate limit, which the modes follow over steps
  much larger than the split. They are not the derivatives at t of either
  returned mode; `solve_waveguide_modes` with the motion gives those, without NaN,
  once the split exceeds `DEGENERATE_GAP`. On the D6 mesh (split 3.1e-5) the
  branches are 5.696 and 2.280 µm⁻¹, while the sorted modes' derivatives at t = 0
  are 2.300 (upper) and 5.676 (lower), with the same sum (independent review,
  2026-11-21). Finite differences pass from one regime to the other near a step
  of 1e-5 µm.
- A modal PML takes a motion (2026-11-21) that leaves the layer in place:
  `solve_waveguide_modes(..., pml=ModalPML(...), motion=)`, or `coordinate_factors`
  with `solve_modes`.
  - The design velocity must be 0 on every node of an element whose factors are
    not 1. Otherwise it is refused by name.
  - With a `ModalPML`, the outer faces must stay where they are: a normal velocity on
    a node of the left, right, bottom or top face is refused by name. Moving one
    would leave the rectangular window that the layer needs, and the solve would be
    undefined at every t ≠ 0 (independent review, 2026-11-21).
  - At kernel level, `solve_modes(..., coordinate_factors=f, motion=)` takes f as
    the factors of the mesh at the step t, held fixed. The rule above applies, and
    f carries no derivative.
  - Each PML element then keeps its centroid and so its factors. The factors of the
    physical window are 1, and the profile (order ≥ 2) is flat where the window
    ends. The factors therefore carry no derivative.
  - The public function places the layer on the mesh at the step t. The moving
    pencil weighs its blocks with the factors as numbers, using the same
    coefficients as the static assembly.
  - A bend takes a motion too (2026-11-22). The window elements (sx = sy = 1) may move,
    and their bend factor h = 1 + (centroid − origin)/R follows the live centroid. PML
    elements keep every node in place, so their complex factors stay fixed. The kernel's
    `solve_modes` takes `coordinate_bend=(radius, axis, origin)` with a motion for this.
    `tests/galerkin/test_shape_derivative_bend.py` holds BD1–BD6, pre-registered on
    2026-11-22 (radius 2 µm bent silicon film, film thickness motion):

    | Check | Criterion | Result |
    |---|---|---|
    | BD1 numbers | all returned n_eff equal the ordinary bend solve on the moved mesh within 1e-12 | pass, against a reference polished by the same Newton step (residual ≤ 2e-13). Against the raw eigensolver numbers it failed first: 1.85e-12 on PML candidates, 1.2e-15 on the physical mode |
    | BD2 consistency | complex dn_eff/dt against a Richardson central difference of moved meshes within 1e-7 | 5.7e-11 |
    | BD3 libraries | JAX and PyTorch within 1e-12 | 1.3e-15 |
    | BD4 Bessel–Hankel pole | dn/dd of the bent film's analytic pole: the error falls on meshes 0.04, 0.02, 0.01 µm, finest within 2e-2, imaginary part within 5e-2 | 2.4e-3, 6.2e-4, 1.6e-4; imaginary part 9.4e-3 |
    | BD5 refusals | a velocity on a PML node or normal to an outer face | pass |
    | BD6 unchanged | `motion=None` equals no keyword bit for bit | pass |

  `tests/galerkin/test_shape_derivative_pml.py` holds P1–P7, pre-registered on
  2026-11-21 before the implementation ran, and measured that day:

  | Check | Criterion | Result |
  |---|---|---|
  | P1 numbers | n_eff equal the ordinary PML solve on the moved mesh, relative 1e-12 | 3.9e-15 |
  | P2 strip in a PML window | 0.6 × 0.2 µm Si strip, PML 0.5 µm on every side, core-width motion: complex dn_eff/dt against a Richardson central difference of moved meshes within 1e-7 | 8.5e-10 (1.9426 + 2.5e-6i) |
  | P3 libraries | JAX and PyTorch within 1e-12 | 6.9e-16 |
  | P4 refusals | a velocity on a PML node (also with a bend, since 2026-11-22); the first P4 refused a motion with a bend | pass |
  | P5 unchanged | without a motion, `motion=None` equals no keyword bit for bit | pass |
  | P6 leaky slab | the outgoing TE pole of the PML tests, first core thickness d₁ = 0.22 µm (the substrate stays at 0.47 µm): dn/dd₁ against the derivative of the analytic root; the error falls on meshes 0.04, 0.02 and 0.01 µm, finest within 2e-2, imaginary part within 5e-2 | 6.2e-3, 1.8e-3, 4.7e-4 (3.3319 − 0.01428i against 3.3303 − 0.01427i); imaginary part 1.1e-3 |
  | P7 layer independence | the slope on mesh 0.02 for PML thickness 0.75 and 1.5 µm and strength 2 and 6 within 1e-2 of the default | ≤ 3.2e-6 |

  The analytic slope is in the kernel's exp(+iωt) convention; the public index is
  its conjugate. P6 first failed (2026-11-21): the reference root kept the gap
  at 0.25 µm, while the motion keeps the substrate at 0.47 µm. Once the root
  used the moved geometry (gap 0.47 − d₁), the criteria were met as
  pre-registered.

## 3D steady heat

`solve_steady_heat_3d(mesh3d, ..., motion=MeshMotion(design_velocity=W, t=t))` takes a
`Mesh3D` with an (N, 3) design velocity and the solver's own inputs. Those are a region
or scalar conductivity, a region or scalar heat source, and Dirichlet values attached to
their nodes (the 3D solver has no flux or convection).
- The numbers come from the ordinary solve on the moved `Mesh3D`.
- The live correction assembles the P1 system from the live coordinates. The barycentric
  gradients are the cofactor rows (e₂ × e₃, e₃ × e₁, e₁ × e₂)/det and the volume is
  det/6. The stiffness is kV GGᵀ and the source load QV/4.
- As in 2D, the correction is solved on the increment over each component's first
  Dirichlet value.
- `admissible_interval` and `extend_velocity` take a `Mesh3D`.
  - A tetrahedron's volume is a cubic in t. Its real roots, polished by Newton steps,
    bound the interval (vectorized over the tetrahedra). A cluster of roots, as in a
    uniform scaling, splits under rounding into a real root and a nearly real complex
    pair. Those real parts count too, so there the interval is conservative (inside
    the true one). The moved volumes are also tested directly, so an inverted step is
    always refused.
  - The extension solves the P1 Laplace problem in 3D per component (`"stiffened"`
    divides by the volume).
- A source callback is refused with a motion: its sample points move.

`tests/galerkin/test_shape_derivative_3d.py` holds T1–T10, pre-registered on
2026-11-21 before the implementation ran, and measured that day:

| Check | Criterion | Result |
|---|---|---|
| T1 numbers | temperatures, rates and flux equal the ordinary solve on the moved mesh, relative 1e-12 | 5.7e-14 |
| T2 consistency | two-region box with a source, interior bump plus a moving face: dT/dt against a Richardson central difference of moved meshes (h = 2e-3) within 1e-8 · max \|dT/dt\| | 1.2e-10 |
| T3 libraries | JAX and PyTorch within 1e-12 | 2.3e-16 |
| T4 rigid motions | a translation and an infinitesimal rotation ω × x: dT/dt = 0 within 1e-10 · max \|T\| | 1.5e-16, 5.4e-17 |
| T5 two-layer box | dQ/dL₁ = −AΔT (1/k₁ − 1/k₂)/R², relative 1e-10 | 4.7e-15 |
| T6 hollow cylinder | inner radius a against 2πkH(T₁ − T₂)/(a ln²(b/a)); order ≥ 1.5, finest within 1e-2 | 9.7e-3, 2.4e-3, 5.9e-4 at 4 × 16, 8 × 32, 16 × 64 cells; order 2.03 and 2.01 |
| T7 inversion interval | volumes positive at (1 − 1e-9) of each end, some ≤ 0 at (1 + 1e-9); a step beyond is refused | pass; a triple root (uniform contraction) gives a bound 4e-6 inside the root and a step past it is refused (independent review) |
| T8 extension | harmonic: linear data reproduced within 1e-12 | pass on a perturbed mesh; `"stiffened"` reproduces constants and differs from harmonic there (it does not reproduce linear data, by design) |
| T9 refusals | a 2-column velocity, live conductivity or Dirichlet value, a source callback, a NumPy t | pass |
| T10 unchanged | `motion=None` equals no keyword bit for bit | pass |

## The mesh velocity

Nodes on the geometry's curves move as the design moves them. For a version 1
geometry document, `simcase.geometry_velocity.design_velocity(document,
p).node_velocity(meshine_mesh)` gives them
([design velocity](../simcase/geometry_engine.md#design-velocity-stage-4)). Its
`values` are dimensionless (∂x/∂p, with x and p in the document unit), so t is
then the parameter change in the mesh's length unit. `galerkin.interop.from_mesher`
keeps the meshine node order. For a steady heat document whose runner builds the
mesh, `simcase.shape_derivative.shape_problem(document, p)` joins these steps in one
call ([document shape derivative](../simcase/geometry_engine.md#shape-derivative-of-a-document)).

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
`admissible_interval(mesh, design_velocity=W)` returns the nearest roots on each side over all
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
- a `t` that is not a real float64 scalar (`TypeError`, naming its dtype): a complex
  `t` would lose its imaginary part, and a float32, float16 or bfloat16 `t` is not
  promoted, so the derivative is never taken in another precision. JAX without
  `jax_enable_x64` keeps its own refusal (`ValueError`);
- a live mesh velocity; a velocity of the wrong shape, or one that is not finite;
- a step outside the admissible interval (`ElementInversion`);
- coordinate callbacks for the heat source, boundary heat flux, convection, current
  density, body force or traction, also inside a convection pair, and
  `ElementHeatSource` and `ElementConductivity`: their sample points move with
  the mesh. Callbacks of time alone are taken in transient heat, and coordinate
  callbacks that compute with the live points in steady and transient heat (above);
- callable coefficients or Dirichlet values (other than callbacks of time in
  transient heat): a motion takes constants;
- live conductivity, source, boundary, Dirichlet, reference, elastic-constant,
  thermal-expansion, reference-temperature, body-force, traction, heat-capacity,
  initial-temperature, permittivity, permeability, wavenumber or `n_target` values together
  with a motion: t is the one live input of such a call;
- a temperature snapshot of another mesh, including the moved one: the snapshot
  belongs to the mesh as given;
- a radial design velocity on the symmetry axis with `coordinate_system="axisymmetric"`;
  `checkpoint_every` in transient heat; in waveguide modes a design velocity on a PML
  element or normal to an outer face;
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
| S9 large temperature offset (2026-11-21) | offsets 300 K, 1e6 K, 1e9 K with Dirichlet sides, a Dirichlet and a convection side, convection only: t = 0 reactions, convection and flux equal the plain solve's within 1e-12 of their largest value; dQ/dt equals the offset-free value within 1e-9; JAX and PyTorch | pass (about 1e-15). Before the fix the error grew as ε·c: at 1e9 K, 2e-8 in flux and 7e-8 in dQ/dt |

`tests/galerkin/test_shape_derivative_electric.py` holds checks E1–E8 for
steady electric conduction, pre-registered on 2026-11-10 and measured that day
with the same versions.

| Check | Criterion | Result |
|---|---|---|
| E1 discrete consistency | derivative vs central differences of moved meshes (h = 1e-4) for a probe potential, the terminal current and the Joule power, with region conductivity and a current density on a moving side; relative 1e-6, JAX and PyTorch | 7.2e-10, 1.9e-9, 1.2e-9 |
| E2 two-layer resistor | dR/dL₁ = (1/σ₁ − 1/σ₂)/H, relative 1e-10 | pass |
| E3 coaxial conductor | inner radius from the geometry engine's node velocities; dI/da = 2πσΔV/(a ln²(b/a)); observed order ≥ 1.5, finest within 1e-3 | 8.1e-3, 2.1e-3, 5.8e-4 at sizes 0.8, 0.4, 0.2 |
| E4 rigid translation | dJ/dt = 0 within 1e-12 · \|J\| (power, sum of potentials) | pass |
| E5 power identity | d(Joule power)/dt = d(supplied power)/dt, relative 1e-10 | 9e-14 (JAX), 5e-14 (PyTorch) |
| E6 unchanged | without `motion` the result equals the previous code | sha256 of the result arrays equal to main `a0a432b` (measured); `motion=None` equals no keyword (test) |
| E7 gauge component | a component with only current data and a `reference_electric_potential`: E1 criterion | pass |
| E8 refusals | as listed above | pass |

An independent review then added regression tests: a common-mode voltage up to
1e9 V (E5 criterion), and a motion that changes a current-only component's
balance (refused).

`tests/galerkin/test_shape_derivative_elasticity.py` holds checks M1–M8 for linear
elasticity, pre-registered on 2026-11-10 and measured that day with the same
versions.

| Check | Criterion | Result |
|---|---|---|
| M1 discrete consistency | derivative vs central differences of moved meshes (h = 1e-4) for a tip displacement, the clamped-side reaction and the strain energy, with two materials, gravity and a traction on a moving side, plane stress and plane strain; relative 1e-6, JAX and PyTorch | 2.6e-10 to 9.6e-9 |
| M2 uniaxial bar | dδ/dL = σ/E, relative 1e-10 | pass |
| M3 two materials in series (ν = 0) | dδ/dL₁ = σ(1/E₁ − 1/E₂), relative 1e-10 | pass |
| M4 thick cylinder (plane strain) | inner radius from the geometry engine's node velocities, radial displacement U₀ on it, outer face free; dF/da against the Lamé solution; observed order ≥ 1.0, finest within 1e-2 | 4.4e-2, 1.0e-2, 2.6e-3 at sizes 0.4, 0.2, 0.1 (order about 2) |
| M5 rigid translation | dJ/dt = 0 within 1e-12 · \|J\| (strain energy, sum of displacements) | pass |
| M6 energy identity | d(½∫σ:ε)/dt = d(½ load · u)/dt, relative 1e-10 | pass |
| M7 unchanged | without `motion` the result equals the previous code | sha256 of the result arrays equal to main `6f80a73` (measured); `motion=None` equals no keyword (test) |
| M8 refusals | as listed above | pass |

`tests/galerkin/test_shape_derivative_thermoelastic.py` holds checks T1–T8 for
thermoelasticity (path 1: a prescribed snapshot; path 2: the workflow), pre-registered
on 2026-11-10 with T3's mesh sizes, and measured that day with the same versions.

| Check | Criterion | Result |
|---|---|---|
| T1 discrete consistency | derivative vs central differences of moved meshes (h = 1e-4) for a tip displacement, the clamped side's reaction sum and the physical elastic energy (path 2 also the mean temperature), with two materials, a nonuniform temperature, gravity and (path 1) a traction on a moving side, plane stress and plane strain; relative 1e-6, JAX and PyTorch | path 1: 1.9e-9 to 4.9e-8; path 2: 2.6e-10 to 2.0e-8, except the reaction sum in plane strain (below) |
| T2 free thermal expansion | dδ/dL = αΔT (plane stress), (1+ν)αΔT (plane strain), relative 1e-10 | pass |
| T3 thick cylinder, heat chained (path 2) | inner radius from the geometry engine's node velocities; logarithmic steady temperature between the faces, inner face clamped, outer free, plane strain; dF/da of the inner radial reaction against the closed form; sizes 0.4, 0.2, 0.1; observed order ≥ 1.0, finest within 1e-2 | 1.4e-1, 3.4e-2, 8.8e-3 (order 2.1 and 1.9) |
| T4 clamped two-material bar (ν = 0) | dσ/dL₁ with σ = −ΔT(α₁L₁ + α₂L₂)/(L₁/E₁ + L₂/E₂), relative 1e-10 | pass |
| T5 rigid translation | dJ/dt = 0 within 1e-12 · \|J\| (energy, sum of displacements), both paths | pass |
| T6 no temperature change | with T = T_ref the derivative equals linear elasticity's, relative 1e-12 | pass |
| T7 unchanged | without `motion` both paths equal the previous code | sha256 of the result arrays (and the manifest) equal to main `e9bb438` (measured); `motion=None` equals no keyword (test) |
| T8 refusals | as listed above | pass |

T1, path 2: the clamped side's reaction sum is 10 800 N/m (the body force times
the area), while the reactions it sums are about 1e7 N/m. The ordinary workflow's
own rounding moves it by about 2e-6 N/m between two solves at t = 0 and t = 1e-12,
and the derivative is about 1.2e3 N/m per unit t. At the pre-registered h = 1e-4
the central difference therefore differs from the derivative by 4.2e-6 in plane
strain, above 1e-6 (plane stress: 2.0e-8). As h grows the difference falls
(h = 1e-2: 4.8e-9), and the derivative equals the equilibrium value
d(ΣR_y)/dt = −f_y dA/dt to 1.2e-10 to 4.5e-10. The test therefore takes this sum's
central difference at h = 1e-2, in both planes, and adds the equilibrium check.
This is a deviation from the pre-registered step, recorded here and in the HQ
record. An extra moment check, not pre-registered, is treated the same way (at
h = 1e-4: 7.0e-6 in plane strain, 4.5e-7 in plane stress) and is also checked
against its equilibrium value, f_y times the derivative of Σ area · x_centroid.

The pre-registration fixed M4's criteria, not its mesh sizes. A first run with sizes
0.8, 0.4 and 0.2 gave 1.6e-1, 4.4e-2 and 1.016e-2: order about 2, but the finest
just above 1e-2. The test uses the next finer three sizes; the criteria are
unchanged.

`tests/galerkin/test_shape_derivative_transient_heat.py` holds checks H1–H8 for
transient heat, pre-registered on 2026-11-10 with H3's mesh and step counts, and
measured that day with the same versions.

| Check | Criterion | Result |
|---|---|---|
| H1 discrete consistency | derivative vs central differences of moved meshes (h = 1e-4) for a final probe temperature, the final Dirichlet reaction sum, the final heat content and a weighted sum of the whole temperature history, with two materials, a source, a nonuniform initial temperature, a Dirichlet side and a boundary heat flux that depend on time, and convection on a moving side; relative 1e-6, JAX and PyTorch | 1.2e-11 to 3.5e-9 |
| H2 uniform solution | insulated, uniform initial temperature and source: the discrete solution is T₀ + Q t_n/c on any mesh, so dC_n/dt = (c T₀ + Q t_n) dA/dt; relative 1e-10 | pass |
| H3 decaying sine, bar length | Dirichlet ends, initial sin(πx/L) on the nodes, the bar stretched; d/dL of the final heat content against the closed form; (nx, steps) = (10, 10), (20, 40), (40, 160); observed order ≥ 1.0, finest within 1e-2 | 2.0e-2, 5.1e-3, 1.3e-3 (order 2.0 and 2.0) |
| H4 steady limit | after the solution reaches steady state, the probe derivative equals steady heat's, relative 1e-8 | pass |
| H5 rigid translation | dJ/dt = 0 within 1e-12 · \|J\| (heat content, sum of temperatures) | pass |
| H6 heat balance | d(Σ reaction)/dt = d(Σ storage − Σ load + Σ outward)/dt at the final step, relative 1e-10 | pass |
| H7 unchanged | without `motion` the result equals the previous code | sha256 of the result arrays equal to main `3afaaa6` (measured); `motion=None` equals no keyword (test) |
| H8 refusals | as listed above | pass |

`tests/galerkin/test_shape_derivative_modes.py` holds checks W1–W8 for waveguide
modes, pre-registered on 2026-11-11 with W2's mesh levels, and measured that day with
the same versions.

| Check | Criterion | Result |
|---|---|---|
| W1 discrete consistency | derivative vs central differences of moved meshes (h = 1e-4) for n_eff (real part, and imaginary part for a lossy core) and a gauge-free field share of the two lowest modes of a silicon strip; relative 1e-6, JAX and PyTorch | 3.0e-12 to 6.1e-10 against the Richardson-extrapolated difference (below) |
| W2 hollow PEC guide, TE10 | width a stretched; dn/da = λ²/(4a³ n_eff); nx = 8, 16, 32; observed order ≥ 1.0, finest within 1e-2 | 1.3e-2, 3.4e-3, 8.4e-4 (order 2.0 and 2.0) |
| W3 independent mode solver | strip width derivative against stored modesolverpy 0.4.4 values (finite differences, grid 0.005 µm), within 3% | 9.8e-3 |
| W4 rigid translation | dn_eff/dt = 0 within 1e-10 · \|n_eff\| | pass |
| W5 uniform scaling | X(t) = (1 + t) X₀ gives dn_eff/dt = k0 ∂n_eff/∂k0 (the k0 derivative path), relative 1e-8 | 4.2e-16 (JAX), 2.1e-15 (PyTorch) |
| W6 degenerate modes | on a mesh with the square's symmetry the fundamental pair gets NaN and a warning; the non-degenerate mode of the same call stays finite | pass |
| W7 unchanged | without `motion` the result equals the previous code | sha256 of n_eff, et and ez equal to main `e6c5826` for a real and a lossy core (measured); `motion=None` equals no keyword (test) |
| W8 refusals | as listed above | pass |

`tests/galerkin/test_degenerate_branches.py` holds the branch checks D1–D9 (D7–D9 pre-registered after the independent review),
pre-registered on 2026-11-21 and measured that day as above (micrometre meshes,
k0 in rad/µm, so the slopes are per micrometre):

| Check | Criterion | Result |
|---|---|---|
| D1 symmetric square (W6 problem) | sorted slopes equal one-sided differences of the sorted indices on both sides (two Richardson levels, h = 5e-4) within 1e-6 | 5.6403 and 2.2760 per unit; ≤ 3.2e-9 |
| D2 smooth sum | the slopes' sum equals the central difference of n₁ + n₂ (one Richardson level) within 1e-6 | pass (a plain central difference at h = 5e-4 is 2.2e-6 off by truncation) |
| D3 nondegenerate strip | no group | pass |
| D4 refusals | a partner that was not returned; a `relative_tolerance` of 0 | pass |
| D5 libraries | JAX and PyTorch within 1e-12 | pass |
| D6 the 2026-11-11 square (geometry-engine motion, mesh 0.02 µm, pair split by 3.1e-5, tolerance 1e-4) | slopes within 3 % of that day's galerkin differences (5.70–5.82, 2.276–2.283 µm⁻¹) and 5 % of modesolverpy's (5.53–5.63, 2.251–2.254) | 5.696 and 2.280 µm⁻¹ (the degenerate limit, see above) |
| D7 incomplete or chained group (pre-registered after the review) | a group of 2 from a triple eigenvalue, and 1, 1 + 6e-4, 1 + 1.2e-3 at tolerance 1e-3, are refused | pass |
| D8 refusals | `relative_tolerance` 2e-3 or `None`, `motion=None` by name; t = 2 raises `ElementInversion` unchanged | pass |
| D9 lossy core (public ε = 3.48² + 0.01i) | public slopes equal one-sided differences of the public indices on both sides (two Richardson levels, h = 5e-4) within 1e-6 | 5.6403 + 0.0059i and 2.2760 + 0.0022i per unit; ≤ 3.2e-9 |

W1: the pre-registration named the plain central difference at h = 1e-4. For the
imaginary part of the lossy mode 0 its truncation error is 1.5e-6 (the second
derivative is large); a sweep of h from 1e-2 to 1e-4 converges to the derivative,
and its Richardson extrapolation from h and h/2 agrees to 6.1e-10. The test uses the
extrapolated difference for every case (plain difference: 7.1e-9 to 1.5e-6); the
criterion is unchanged. This deviation is recorded here and in the HQ record. W3's
stored value was measured before the registration (it records that measurement;
the independent check with a criterion fixed beforehand is W2).
