# Derivatives with JAX and PyTorch

**English** | [한국어](../../locales/ko/pages/packages/galerkin/differentiation.md)

[galerkin overview](overview.md)

Steady heat conduction (`galerkin.thermal.solve_steady_heat`), steady electric
conduction (`galerkin.electric.solve_steady_electric`), transient heat conduction
(`galerkin.transient_heat.solve_transient_heat`), elasticity
(`galerkin.elasticity.solve_elasticity`), thermoelasticity
(`galerkin.thermoelasticity.solve_thermoelasticity`) and waveguide modes
(`galerkin.waveguide.solve_modes`) accept JAX or PyTorch values
in place of NumPy numbers. The result arrays are then arrays of that library, and
derivatives with respect to those inputs flow through the solve. NumPy remains the
default and computes exactly as before; it does not differentiate.

Install an array library with the matching extra, `pip install "galerkin[jax]"` or
`pip install "galerkin[torch]"`. JAX must run in double precision
(`jax.config.update("jax_enable_x64", True)`); single precision is refused.

## What may be live

| Solver | Inputs that may be JAX or PyTorch values |
|---|---|
| `solve_steady_heat` | `conductivity` (scalar or `{region name: value}`); `heat_source` (scalar, region table or a callback returning live values); `dirichlet` temperatures; `outward_flux` and both members of each `convection` pair (scalars or callbacks returning live values) |
| `solve_steady_electric` | `conductivity` (scalar or region table); `dirichlet` and `reference_potential` volts; `outward_current` (scalar or callback returning live values) |
| `solve_transient_heat` | `conductivity` and `volumetric_heat_capacity` (scalars or region tables); `heat_source` (scalar, region table or a callback `(points, time)` returning live values); `dirichlet` temperatures (scalars or callbacks `(time)` returning live values); `initial_temperature_k` |
| `solve_elasticity` | `young_modulus` and `poisson_ratio` (scalars or region tables); `dirichlet` displacements; `body_force` and `traction` (constant vectors or callbacks returning live values) |
| `solve_thermoelasticity` | as `solve_elasticity`, plus `reference_temperature_k` and `thermal_expansion_per_k` (scalar or region table); the temperature snapshot stays a NumPy record |
| `solve_modes` | `eps_r` and `mu_r` (scalars or per-element arrays, real or complex) and `k0`; `n_eff`, `et` and `ez` are returned in that library. `n_target` only selects the modes and has no derivative; `coordinate_factors` must be NumPy |

The time grid `time_s` is structure, like the mesh. A transient callback must
return values of one library for the whole run: a callback that returns NumPy
numbers at the first time and live values later is refused.

Mesh coordinates, connectivity, boundary tags and region ids are fixed structure;
derivatives with respect to node positions are not provided. `ElementHeatSource`
and `ElementConductivity` hold NumPy values. A callback receives NumPy coordinates
and normals and may return live values; lift the coordinates into the same library
when they enter the expression (PyTorch does not combine tensors with NumPy arrays).

All live inputs must come from one library. NumPy constants may sit beside them.

## Example

```python
import jax
import jax.numpy as jnp
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat

jax.config.update("jax_enable_x64", True)
mesh = rectangle_mesh(1.0, 0.5, 6, 4)
left = [int(i) for i in mesh.boundary["left"]]
right = jnp.asarray(mesh.boundary["right"])


def right_temperature(k, h):
    result = solve_steady_heat(mesh, conductivity=k, dirichlet={i: 350.0 for i in left},
                               convection={"right": (h, 300.0)})
    return result.temperature[right].mean()


dk, dh = jax.grad(right_temperature, argnums=(0, 1))(2.0, 5.0)
# One-dimensional slab, exact for P1: T(L) = 300 + 50 / (h (L/k + 1/h)).
# With L = 1 and R = L/k + 1/h = 0.7:
# dk = 50 L / (k^2 h R^2) = 5.1020, dh = -50 L / (k (h R)^2) = -2.0408,
# in K per W/(m K) and K per W/(m^2 K).
```

The same function written with `torch.tensor(..., dtype=torch.float64,
requires_grad=True)` inputs gives the same gradients through `.backward()`.

## How the derivative is computed

The steady heat and electric solvers assemble and solve their live systems
directly. Transient heat, elasticity and thermoelasticity first run their NumPy
solve on the numbers of the inputs, with every check, and then attach the
derivative to that solution x0 with one more solve: x = x0 + A⁻¹(b − A x0), equal
to x0 up to rounding. Callbacks run once; their results are kept for the live pass.
Waveguide modes do the same with an eigenpair (next section).

Assembly runs in the input's library through the closed-form element kernels of
`galerkin.core.kernels` and `galerkin.core.forms`. The sparse system is still
solved by SciPy's sparse LU; its derivative is supplied by the adjoint
(`galerkin.core.solve`): one more solve with the transposed matrix, whatever the
number of inputs. JAX uses `jax.custom_vjp` and PyTorch an `autograd.Function`.

Input checks, residual tolerances and the heat, current and power balances run on
a snapshot of the numbers, with the same thresholds as for NumPy inputs.

## Transient heat: memory and checkpointing

The reverse pass needs every step's intermediate values. By default they are all
kept (as JAX and PyTorch record them); this is the fastest choice and uses the
most memory. `solve_transient_heat(..., checkpoint_every=m)` keeps only every
m-th state and recomputes the steps in between during the backward pass, through
`jax.checkpoint` or `torch.utils.checkpoint`. Values and derivatives do not
change, NumPy inputs ignore it, and callbacks are not called again (their
values are kept).

Each step first runs on NumPy numbers, refined and checked exactly as for NumPy
inputs; its solution x0 then gets the adjoint correction x = x0 + A⁻¹(b − A x0),
equal to x0 up to rounding, with exact derivatives.

Peak resident memory above an idle process, for the derivative of the final mean
temperature (`tests/galerkin/test_transient_gradients.py` setup on larger
meshes; 2026-10-27, Linux, JAX 0.12.0.1, PyTorch 2.14.1 CPU). The result histories
themselves take O(Nt (N + M)), the first row:

| Case | 861 nodes, 400 steps | 3321 nodes, 200 steps |
|---|---|---|
| result histories (computed size) | 23 MiB | 45 MiB |
| NumPy run | 48 MiB | 99 MiB |
| JAX gradient, every step kept | 590 MiB | 786 MiB |
| JAX gradient, `checkpoint_every=20` | 333 MiB | 453 MiB |
| PyTorch gradient, every step kept | 363 MiB | 700 MiB |
| PyTorch gradient, `checkpoint_every=20` | 202 MiB | 302 MiB |

These are single measurements on one machine, not limits. Peak memory grows
linearly with the number of steps in both modes; checkpointing lowers the slope.

## Waveguide modes: eigenvalues, fields and degenerate modes

`solve_modes` runs the NumPy eigensolve on the numbers of the inputs. Each
returned pair (λ0, x0), with λ0 = −(k0 n_eff)² and x0 = [et β, ez] on the free
degrees of freedom, then takes one Newton step on the eigenproblem A x = λ B x
bordered by the normalization xᵀ B x = 1, solved with the live A and B:

    [x; λ] = [x0; λ0] − J⁻¹ F,   J = [[A − λ0 B, −B x0], [−x0ᵀ B, 0]],
    F = [(A − λ0 B) x0, ½ (1 − x0ᵀ B x0)].

The values stay those of the NumPy solve up to rounding; the derivatives are the
exact implicit ones, for real and lossy (complex) problems alike.

Fields carry a gauge: an eigenvector is fixed only up to a complex factor. The
solver returns x with unit 2-norm and its largest entry real and positive; the
live pass applies the same rule to x again, so `et` and `ez` and their
derivatives follow that gauge. When several entries are equally largest (a
symmetric mode), the one the NumPy solve left with zero phase is kept. A
quantity that does not depend on the gauge, such as an overlap magnitude or the
ratio |E_z|²/|E_t|², has a gauge-free derivative; prefer such quantities in an
objective.

A degenerate eigenvalue has no derivative: its eigenvectors are any combination
of the pair. When a returned eigenvalue lies within 1e-8 relative
(`galerkin.waveguide.DEGENERATE_GAP`) of another eigenvalue of the discrete
problem, whether or not that one was returned (`num_modes` may cut a pair), the
mode keeps its exact values and gets a `DegenerateModeWarning` and NaN
derivatives, so a backward pass that uses it gives NaN instead of a wrong
number. The nearest other eigenvalue is found densely for small problems and by
shift-invert Arnoldi next to each mode otherwise, one more factorization per
mode. Outputs that the objective does not
use contribute nothing, so the other modes keep their derivatives. Break the
symmetry or use a quantity of the whole degenerate subspace instead.

Only the 2D waveguide is covered. Cavities (`solve_cavity_box`,
`solve_material_cavity_box`) and the other electromagnetic solvers do not
differentiate yet.

## Refused, not approximated

- `jax.jit` around these solvers: checks need concrete numbers
  (`galerkin.core.backend.TracedValueError`). `jax.grad` and PyTorch autograd work
  without `jit`.
- JAX or PyTorch `coordinate_factors` in `solve_modes` (a `TypeError`): derivatives
  with respect to PML stretching or bend coordinates are not provided.
- Forward-mode differentiation (`jax.jvp`, `jax.jacfwd`) and second derivatives.
- JAX without `jax_enable_x64`, and JAX and PyTorch values in one call.
- Solvers that do not differentiate yet refuse JAX and PyTorch values with a
  `TypeError` rather than silently cutting the derivative: the NumPy containers
  `ElementHeatSource`, `ElementConductivity` and `freeze_temperature`'s
  `TemperatureSnapshot`, the Joule and heat-to-mechanics workflows (the latter
  reports it as a `WorkflowStageError` of the heat stage), and transient
  mechanics given a live heat history (a `TransientThermoelasticError`). JSON
  documents and the command line run on NumPy.

## Limits

- Not yet guarded: the low-level assembly functions (`galerkin.assembly`,
  `assembly3d`, `edge`, `edge3d`) and the electromagnetic solvers other than
  `solve_modes` convert their
  inputs with NumPy. A JAX value passed to them loses its derivative; do not pass
  live values there.
- With live inputs, `joule_power_per_length` and `supplied_power_per_length` are
  0-d arrays of that library instead of Python floats, and result arrays are not
  made read-only.
- Tested on CPU only. Static data is lifted to CPU tensors; tensors on another
  PyTorch device are not supported.

## Validation

`tests/galerkin/test_steady_gradients.py` (2026-10-26, Linux, NumPy 2.5, JAX 0.12.0.1,
PyTorch 2.14.1 CPU):

- Every result field on JAX and PyTorch matches the NumPy solve to 1e-12 relative.
- Closed forms where P1 is exact: the right-hand temperature of a Dirichlet–convection
  slab with respect to k, h and both temperatures, and the Joule power of two
  conductors in series with respect to both conductivities and both voltages, to
  1e-10 relative.
- Central differences of the NumPy solve for each kind of live input, including
  region tables, source and boundary callbacks, and a current-driven component with a
  live reference potential.

`tests/galerkin/test_transient_gradients.py` (same date and versions):

- Every history on JAX and PyTorch matches the NumPy run to 1e-12 relative.
- An insulated body with uniform initial temperature and source, where backward
  Euler reproduces T0 + Q t / c exactly: the final temperature and its derivatives
  with respect to k, c, Q and T0 to 1e-10.
- Central differences of the NumPy run for k, c, Q, the Dirichlet ramp, the initial
  field and region tables of k, c and Q.
- `checkpoint_every` of 1 and 3 on 4 steps gives the same values (1e-14) and
  gradients (1e-12) as keeping every step.

`tests/galerkin/test_mechanics_gradients.py` (same date and versions):

- Every field of elasticity and thermoelasticity on JAX and PyTorch matches NumPy to
  1e-12, for scalar and region materials in plane strain and plane stress.
- Closed forms that P1 reproduces exactly, to 1e-10: a plane-stress bar under end
  traction (u = sigma L / E, lateral -nu sigma H / E) with respect to E, nu and
  sigma, and free thermal expansion (u = alpha (T - Tref) L) with respect to Tref,
  alpha and E.
- Central differences for E, nu, Dirichlet displacements, body-force and traction
  callbacks and constants, region tables, and for thermoelasticity Tref and alpha.

`tests/galerkin/test_mode_gradients.py` (2026-10-27, Linux, NumPy 2.5, JAX 0.12.0.1,
PyTorch 2.14.1 CPU):

- `n_eff`, `et` and `ez` on JAX and PyTorch match NumPy to 1e-12, for a real guide,
  a lossy core and complex coordinate factors (a stretched quarter and a bend-like h).
- A homogeneous PEC guide, where the discretization keeps (k0 n_eff)² = k0² ε μ − kc²
  with kc fixed by the mesh (checked to 1e-11): the derivatives of three modes with
  respect to ε, μ and k0 match μ/(2 n_eff), ε/(2 n_eff) and kc²/(k0³ n_eff) to 1e-9.
- Central differences of the NumPy solve for n_eff (real and imaginary parts), the
  gauge-free ratio |ez|²/|et|² and a raw `ez` entry in the returned gauge, with
  respect to the core and cladding indices, μ, k0 and the core loss; a directional
  difference for per-element ε and μ arrays.
- A square guide on a mesh with the square's symmetry: the degenerate fundamental
  pair warns and gives NaN derivatives; a non-degenerate mode in the same call
  matches central differences. With `num_modes=1`, which returns one member of
  the pair, that mode still warns and gives NaN.

The adjoint solve itself is checked against each library's automatic
differentiation of its dense `linalg.solve` and against central differences in
`tests/galerkin/test_core_solve.py`.
