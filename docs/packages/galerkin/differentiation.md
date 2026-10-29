# Derivatives with JAX and PyTorch

**English** | [한국어](../../locales/ko/pages/packages/galerkin/differentiation.md)

[galerkin overview](overview.md)

Steady heat conduction (`galerkin.thermal.solve_steady_heat`), steady electric
conduction (`galerkin.electric.solve_steady_electric`), transient heat conduction
(`galerkin.transient_heat.solve_transient_heat`), elasticity
(`galerkin.elasticity.solve_elasticity`), thermoelasticity
(`galerkin.thermoelasticity.solve_thermoelasticity`), waveguide modes
(`galerkin.waveguide.solve_modes`) and the PEC box cavity
(`galerkin.cavity.solve_cavity_box`) accept JAX or PyTorch values
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
| `solve_cavity_box` | `lengths_m` (an array of three, or a sequence mixing numbers and live values); frequencies, eigenvalues, edge coefficients and centroid fields are returned in that library with derivatives, the residuals (a diagnostic of the NumPy solve) without. `target_frequency_hz` only selects the modes |
| `eval_edge_field` | `dofs` (real or complex), such as `et[i]` of `solve_modes`; the centroid field is returned in that library as float64 or complex128. The `EdgeSpace` is NumPy structure: its geometry and edge signs carry no derivative |

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

The steady heat, electric, elasticity and thermoelasticity solvers build their
system once, in the inputs' library, and solve it once with
`galerkin.core.solve`, for NumPy and live inputs alike. Transient heat runs each
step on the numbers first, refined and checked as a NumPy run; one more solve
then attaches the derivative to that solution x0: x = x0 + A⁻¹(b − A x0), equal
to x0 up to rounding. Callbacks run once. Waveguide modes do the same with an
eigenpair (next section).

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
objective. `galerkin.edge.eval_edge_field(space, et[i])` turns the live edge
coefficients into the transverse field at the triangle centroids in the same
library, with the derivative with respect to the coefficients; the space's
geometry carries no derivative.

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

`solve_material_cavity_box` and the electromagnetic solvers other than
`solve_modes` and `solve_cavity_box` do not differentiate yet; they refuse JAX
and PyTorch values ([refused](#refused-not-approximated)).

## Box cavity: derivatives with respect to the lengths

A vacuum box has no material to vary; its inputs are the three lengths.
Moving a wall moves every node, which in general would need derivatives with
respect to node positions. A box mesh only scales along the axes, x_a → d_a x_a
with d_a = L_a / L_a0, and edge functions transform covariantly under that map,
so the curl-curl and mass matrices are exactly

    K = Σ_a d_a² / (d_x d_y d_z) K_a,   M = (d_x d_y d_z) Σ_a M_a / d_a²,

with component matrices K_a, M_a of the solved mesh
(`galerkin.core.kernels.nedelec3d_components`). Each mode then takes the
bordered Newton step of the waveguide with these live K and M. The solver's
normalization xᵀ M x = 1 is the one the step keeps, and its sign rule (largest
coefficient positive) does not change under a small step, so field derivatives
follow the returned convention without a further gauge. Centroid fields are
evaluated on the solved mesh and divided by d_a, component by component.

Boxes have many degenerate modes (any two equal side lengths give pairs); they
follow the same rule as the waveguide: NaN derivatives and a
`DegenerateModeWarning`, also when `num_modes` cuts the pair. `result.mesh` and
`result.space` hold the numbers of the solved geometry; node coordinates carry
no derivative.

## Iterative solvers

Some solvers find their solution by iteration instead of one linear solve. The
temperature-dependent Joule solve (`solve_temperature_joule_heat`) repeats
"conductivity from temperature, then potential, heat and a new temperature"
until nothing changes. A derivative attached to such a solution must be the
implicit derivative of the residual R(x, p) = 0 that the solution satisfies:

    dx/dp = −(∂R/∂x)⁻¹ ∂R/∂p.

Compute it as one Newton step of the complete residual, with the exact Jacobian
in every unknown and the live inputs, or as the adjoint of that residual (for a
fixed point x = G(x, p), the adjoint of the converged fixed point). A transient
problem uses the system of the whole step; an eigenpair uses the bordered system,
whose λ column is T′(λ) x when the operator T depends on λ.

Never attach the derivative by running the iteration map once more, or a few
more times, on live inputs from the converged numbers. That excludes an extra
Picard pass, relaxed or not, a pass with frozen coefficients or a frozen
factorization, and an extra step of residual inverse iteration.

Such a pass returns the right values and the wrong derivative. From the
converged x\*, one more pass of x ← G(x, p) changes the values by rounding only,
but it differentiates only G's direct dependence on p, the first term of

    dx*/dp = (I − G_x)⁻¹ G_p = G_p + G_x G_p + G_x² G_p + …

Its relative error is about μ, the spectral radius of G_x: the feedback
strength, the fraction of an error that one pass of the iteration leaves. k
passes leave about μᵏ. A relaxed pass x ← (1 − ω) x + ω G(x, p) is off by about
1 − ω (1 − λ), with λ the signed dominant eigenvalue of G_x: about one half at
ω = 0.5 even without feedback. A test that compares only values cannot see this.

Solvers that differentiate already follow the rule. The live step of transient
heat is one solve of the whole backward Euler system M/Δt + K
([above](#how-the-derivative-is-computed)), and waveguide modes and the box
cavity take one Newton step of the bordered eigenproblem
(`galerkin.core.eigen.refine`). `solve_temperature_joule_heat` does not
differentiate: both methods refuse live inputs ([refused](#refused-not-approximated)).

A gradient test of an iterative solver needs at least one case whose
coefficients depend on the state, with feedback μ well above the test tolerance
(for example μ ≥ 0.05). With μ = 0 an extra pass is exact and such a test
cannot fail.

## Assembling core kernels yourself

The public assembly functions take NumPy values. To assemble with JAX or PyTorch
coefficients, build element matrices with `galerkin.core.kernels`, place them
with `galerkin.core.forms` and solve with `galerkin.core.solve`, whose adjoint
gives the derivative. `galerkin.core` follows the same 0.x rule as the rest of the
Python API ([stability in 0.x](../../../CHANGELOG.md#stability-in-0x)): it may
change in a minor release (0.1 to 0.2), and patch releases are not meant to change
it.

`forms.matrix(row_dofs, col_dofs, element, shape)` checks only shapes: that the
cell-to-DOF tables are 2-D integer arrays and that the element matrices match
them. It cannot tell which space a table belongs to. A table of the right shape
from another space, or with its local order permuted (a triangle's vertices
rotated, displacement components blocked instead of interleaved), is accepted
without an error and gives a wrong matrix. Pass each kernel the tables of the mesh
or space it was given:

| Kernel | Element shape | Row table | Column table | Global shape |
|---|---|---|---|---|
| `p1_stiffness`, `p1_mass` | (T, 3, 3) | `mesh.triangles` | `mesh.triangles` | (N, N) |
| `p1_boundary_mass(mesh, edges)` | (E_b, 2, 2) | `edges` | `edges` | (N, N) |
| `p1_load`, the load of `p1_joule` (with `forms.vector`) | (T, 3) | `mesh.triangles` | — | (N,) |
| `tet_stiffness`, `tet_mass` | (T, 4, 4) | `mesh.tets` | `mesh.tets` | (N, N) |
| `nedelec_curlcurl`, `nedelec_mass` | (T, 3, 3) | `space.tri_edges` | `space.tri_edges` | (E, E) |
| `nedelec_grad` | (T, 3, 3) | `space.tri_edges` | `mesh.triangles` | (E, N) |
| `nedelec3d_curlcurl`, `nedelec3d_mass`, the components of `nedelec3d_components` | (T, 6, 6) | `space.tet_edges` | `space.tet_edges` | (E, E) |
| `nedelec3d_grad` | (T, 6, 4) | `space.tet_edges` | `mesh.tets` | (E, N) |
| `vector_p1_stiffness` | (T, 6, 6) | `dofs` of `galerkin.core.triangles.vector_strain` (DOF 2 × node + component) | the same | (2N, 2N) |

T is the number of cells, N of nodes, E of edges and E_b of the boundary edges
passed in; for the edge kernels `mesh` is `space.mesh`. The edge kernels apply
the orientation signs of their `EdgeSpace` or `EdgeSpace3D`, so the edge tables
must come from that same space. Tables and mesh coordinates are NumPy
structure; only coefficients may be live.

## Refused, not approximated

- `jax.jit` around these solvers: checks need concrete numbers
  (`galerkin.core.backend.TracedValueError`). `jax.grad` and PyTorch autograd work
  without `jit`.
- JAX or PyTorch `coordinate_factors` in `solve_modes` (a `TypeError`): derivatives
  with respect to PML stretching or bend coordinates are not provided.
- `eval_edge_field_3d` with JAX or PyTorch coefficients (a `TypeError`). With
  live box lengths the cavity field also depends on the lengths through the
  geometry, which `result.space` holds as numbers, so evaluating it from live
  coefficients alone would miss that part of the derivative. `solve_cavity_box`
  returns the field with its full derivative in `result.electric_field`.
- Forward-mode differentiation (`jax.jvp`, `jax.jacfwd`) and second derivatives.
- JAX without `jax_enable_x64`, and JAX and PyTorch values in one call.
- Solvers that do not differentiate yet refuse JAX and PyTorch values with a
  `TypeError` rather than silently cutting the derivative: the NumPy containers
  `ElementHeatSource`, `ElementConductivity` and `freeze_temperature`'s
  `TemperatureSnapshot`, the one-way Joule transfer (`solve_steady_joule_heat`)
  and the heat-to-mechanics workflows (the latter reports it as a
  `WorkflowStageError` of the heat stage), and transient
  mechanics given a live heat history (a `TransientThermoelasticError`). So do
  `solve_material_cavity_box`, the modal coordinate functions
  (`mode_coordinates`, `scalar_coordinate_system`, `solve_scalar_coordinates`),
  `assemble_mode_system` (`solve_modes` differentiates), `solve_dirichlet`,
  `l2_error` and `radial_pml_coeffs` (its `k`, `r0`, `d` and `sigma_max`; no
  solver differentiates with respect to PML parameters).
  JSON documents and the command line run on NumPy.
- `solve_temperature_joule_heat`, with either method, raises a `TypeError` for a
  JAX or PyTorch value in any input before it copies or solves anything,
  including values inside region tables and boundary tables such as
  `{node: volts}` and `{tag: (h, ambient)}`. Callbacks run only inside the
  iteration, so a live value that one returns surfaces as a
  `JouleConvergenceError` whose cause is that `TypeError`: the conductivity
  callbacks `ConductivityModel.evaluate` and `derivative`, and boundary callbacks
  given for `outward_flux`, `convection` or `outward_current`. See [iterative solvers](#iterative-solvers) for the derivative
  such a solver would need.

## Limits

- The low-level assembly functions (`galerkin.assembly`, `assembly3d`, `edge`,
  `edge3d`) refuse live values with a `TypeError`. The core kernels they are
  built from keep values live when assembled directly, but `forms.matrix` checks
  only shapes, so the DOF tables are the caller's responsibility
  ([assembling core kernels yourself](#assembling-core-kernels-yourself)).
- On JAX, a singular sparse system fails inside the host callback of the solve:
  JAX logs the callback's traceback (`jax.pure_callback failed`) before the
  solver raises its `ValueError`. PyTorch prints nothing.
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

`tests/galerkin/test_cavity_gradients.py` (same date and versions):

- Frequencies, eigenvalues, edge coefficients, centroid fields and residuals on JAX
  and PyTorch match NumPy to 1e-12, on the dense (43 free edges) and iterative
  (291 free edges) eigensolver paths.
- The identity the discretization keeps exactly, Σ_a L_a ∂λ/∂L_a = −2λ (and −f for
  frequencies), to 1e-12 for four modes.
- Central differences of the NumPy solve for an eigenvalue, a frequency, an edge
  coefficient and a field quantity with respect to all three lengths, on both
  paths, and for one live length beside two numbers.
- A box with a square cross-section: the degenerate pair warns and gives NaN, the
  simple fundamental matches central differences, and a pair cut by
  `num_modes=1` still warns and gives NaN.

`tests/galerkin/test_edge_field_gradients.py` (2026-10-29, Linux, NumPy 2.5, JAX
0.12.0.1, PyTorch 2.14.1 CPU):

- `eval_edge_field` on JAX and PyTorch dofs matches the NumPy evaluation to 1e-12,
  for real and complex dofs, and float32 or complex64 dofs are computed in float64
  or complex128.
- The derivative of a weighted sum of |E|² with respect to every real and imaginary
  part of the dofs matches central differences of the NumPy evaluation to 1e-6.
- A waveguide mode solved with a live core permittivity, through
  `eval_edge_field(space, et[0])` into the gauge-free share Σ w|E_t|² / Σ |E_t|²,
  matches central differences of the NumPy solve to 1e-6.
- JAX without `jax_enable_x64` and dofs of another length than the number of edges
  are refused with a `ValueError`.

The adjoint solve itself is checked against each library's automatic
differentiation of its dense `linalg.solve` and against central differences in
`tests/galerkin/test_core_solve.py`.
