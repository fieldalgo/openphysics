# Transient heat to quasistatic mechanics

[한국어](locales/ko/pages/transient_thermal_mechanical.md)

`galerkin.transient_thermal_mechanical.solve_transient_thermoelasticity` composes
existing temperature snapshots and linear small-strain mechanics on a fixed
reference mesh. First call `galerkin.transient_heat.solve_transient_heat`, then
pass its result and the same mesh to this function. The runnable
[example](../examples/transient_thermal_mechanical.py) uses two explicit calls.
There is no new heat solver, inertia, damping, dynamic equilibrium, mechanical
feedback to heat, deformed geometry, or temporal interpolation.

## Inputs and selection

`mesh` must have exactly the heat result's ordered coordinates in metres and
triangle connectivity, including node and element order. A distinct but identical
mesh object is allowed. No remeshing, mapping, unit conversion or unit inference
is performed. `units` is required and must be exactly
`{'length': 'm', 'time': 's', 'temperature': 'K'}`.

`heat` must be a `TransientHeatResult`. The consumed time, geometry and temperature
fields are checked: at least two finite nonnegative strictly increasing seconds,
finite positive increments, and finite real temperature array `(Nt,N)`.
Unconsumed flux/rate/energy diagnostics and solver provenance are not certified.
The public result class can be constructed manually; structural checks do not
prove that the heat calculation completed or that its data are authentic.

`time_indices=None` selects all stored indices, including the initial field at
index 0. Otherwise supply a nonempty 1D list, tuple or array of strictly increasing
integer indices. Booleans, floats, repeats, reversed order and out-of-range values
are rejected. There is no nearest-time lookup. Nonuniform time grids and nonzero
initial time are supported; `time_s[0]` is preserved without resetting the clock.
The initial temperature is not advanced before its mechanical solve.

Every selected temperature must be nonnegative absolute Kelvin. A selected
negative value is rejected, never clipped. Unselected finite negative values are
allowed, consistent with the mathematical heat API. `reference_temperature_k`
is one finite nonnegative Kelvin scalar, fixed over the run. `thermal_expansion_per_k`
is a finite signed scalar in 1/K; zero and negative expansion are supported.
`young_modulus` is finite positive Pa and `-1 < poisson_ratio < 0.5`.
`plane` is explicitly `'stress'` or `'strain'`.

`mechanical_dirichlet` maps exterior `(node, component)` indices to fixed scalar
displacements in metres; component 0 is x and 1 is y. Every disconnected component
must have enough independent constraints to remove its three rigid modes.
`body_force` is a constant finite Cartesian pair in N/m³, default `(0.,0.)`.
All other mechanical boundaries have zero **total physical traction**. Do not
subtract a thermal traction. Time-dependent supports, body callbacks and applied
traction are outside this minimal adapter; use the separate prescribed-temperature
mechanical API for its broader load contract. Fixed supports and constant body
force avoid introducing a second time-sampling protocol.

## Outputs, ownership and failures

The frozen aggregate has `reference_mesh` and a tuple `steps`. `time_indices` and
`time_s` return tuples in selection order. Each step stores the original
`time_index`, exact stored `time_s`, immutable `temperature_snapshot` and
`mechanics` (`ThermoelasticResult`). Displacement is m, in-plane stress and
`sigma_zz` Pa; engineering strain order is `(exx,eyy,gamma_xy)`. Stress and thermal
strain arrays are sampled at triangle centroids. The physical stress generally
varies within each P1 triangle. Loads/reactions/residuals are N/m of out-of-plane
depth, and physical elastic energy is J/m.

For uniform unconstrained in-plane heating, plane stress gives `u=alpha*DeltaT*x`
and zero stress. Plane strain gives `u=(1+nu)*alpha*DeltaT*x`, zero in-plane stress
and `sigma_zz=-E*alpha*DeltaT`. Plane strain does not imply free expansion in z.
Near-incompressible P1 locking remains possible; this adapter adds no remedy.

The mesh, supports, parameters and consumed temperature history are copied.
All selected snapshots are validated and frozen before the first mechanics call.
The function does not mutate caller inputs; callers must not mutate inputs
concurrently. Snapshot geometry and temperatures use immutable byte backing.
The owned result mesh and mechanical arrays remain mutable and are not certified
after return. Mutating them does not alter the immutable snapshots.

`TransientThermoelasticError` provides `stage` (`input`, `transfer`, `mechanics`),
`time_index` and `time_s`. Global input failures have no index/time. Selected
transfer and mechanics failures carry the original stored index/time and chain
the cause in `__cause__`. No successful partial aggregate is returned. A later
mechanics failure can follow earlier completed solves; exception tracebacks may
retain their temporary memory until released.

The result retains only selected snapshots and mechanics, not the input heat
object or its diagnostics. With S selected times, N nodes and M elements, retained
storage is O(S*(N+M)); each snapshot includes a geometry copy. The caller's full
heat history still uses O(Nt*(N+M)), and validation temporarily copies the full
temperature array. This is not streaming or a bounded-memory guarantee. Each
mechanics call assembles and factors independently; no reuse/speed claim is made.

## Independent validation and reproduction

From the repository root with the normal development dependencies installed:

```sh
python -m pytest -q packages/galerkin/tests/test_transient_thermal_mechanical.py
python -m pytest -q -s packages/galerkin/tests/test_transient_thermal_mechanical_physics.py
python packages/galerkin/examples/transient_thermal_mechanical.py
python -m pytest -q
```

The physics tests use independent NumPy-only `refsol.transient_heat` and
`refsol.thermoelasticity` fields derived from the original 3D law. Production
solver-to-solver agreement is not a physics oracle. Preregistered cases/gates:

- Uniform insulated constant-source heating/cooling on nonuniform times starting
  at 2 s: `T=T0+Q*(t-t0)/c`, free expansion and full exterior constraint in both
  planes, negative/zero alpha and a common T/Tref shift. Absolute temperature
  error <=1e-9 K, displacement <=1e-10*(alpha_scale*20 m), stress/reaction
  <=1e-9*(E*alpha_scale*20 Pa), where alpha_scale=1e-5/K. Check out-of-plane stress,
  physical energy and integrated support reactions independently.
- Time error alone: uniform `T=300+t²`, `Q=2ct`, affine mechanics with no spatial
  error. BE temperature error equals `sum(dt²)`; free displacement and constrained
  stress errors have the corresponding analytic factors. 8/16/32 uniform steps
  require order in [0.99,1.01]. A nonuniform grid checks every index as well.
- Space error alone and stationary limit: `T=310+20x` is exact for the heat P1/BE
  discretization at all times; zero body force and the compatible quadratic
  expansion field from `refsol.thermoelasticity.linear_temperature` prescribe the full boundary.
  Independent Gauss-4 Duffy integration on 8/16/32 meshes requires displacement
  L2 order >=1.8, gradient and reconstructed full stress order >=0.9, and finest
  displacement error/(alpha_scale*20 m)<0.01. Both initial and final states and
  both plane reductions are tested. This stationary case does not demonstrate
  convergence of spatially nonuniform time-dependent heating.
- Dedicated regressions cover stored index/time correspondence, exact mesh order,
  invalid consumed fields, mutation isolation, snapshot backing, unsupported
  configuration, insufficient constraints and atomic per-index failures.

The Linux source suite includes these tests; its dedicated preflight records
numerical metrics in logs/JUnit. The installed Linux/macOS/Windows consumer checks
the same public composition against closed forms and verifies module origin.
Distribution checks require both language documents, tests and the example and
run the archived example. Existing full Linux and narrow Windows checks remain
required. Configuration is not proof of acceptance: inspect the exact candidate
and resulting main workflow logs/artifacts. No new platform, performance or
resource guarantee follows from this guide.
