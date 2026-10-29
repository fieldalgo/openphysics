# Temperature-dependent steady Joule heating

**English (normative contract)** | [한국어](../../locales/ko/pages/packages/galerkin/temperature_joule_heating.md)

## Scope and equations

Python solver: fixed conforming 2D P1 triangles in metres, DC, isotropic sigma(T),
constant positive thermal conductivity k (scalar or named-region table).
Solve div(J)=0, E=-grad(V), J=sigma E, Q=J.E and -div(k grad(T))=Q.
The existing [electric contract](electric_steady2d.md) and
[one-way transfer](joule_heating.md) define boundaries, gauges and power signs.
No transient, 3D, mesh motion, extra heating, Studio or release is included.

## Material and iteration contract

`galerkin.temperature_joule_heating.ConductivityModel(evaluate, temperature_range,
derivative=None)` contains a deterministic vector callback accepting a
one-dimensional Kelvin array and returning exactly that shape in S/m, plus finite
inclusive `(T_min, T_max)` with `0 <= T_min < T_max`. The optional `derivative`
callback receives the same read-only element-mean arrays and returns dsigma/dT in
S/(m K) as a finite real array of that shape; only the
[Newton method](#newton-method) uses it, to form its step. Use one model or an exact named-region mapping.
Every incident nodal temperature must be in its material's range (including both
materials at interfaces). Evaluate sigma at the arithmetic mean of the triangle's
three nodal temperatures, once per element; do not average evaluated nodal sigma.
All evaluated conductivities must be finite, real and strictly positive. No
clipping, extrapolation or Celsius conversion occurs. Callbacks must not mutate
inputs or depend on call count. General positivity between evaluations is the
material author's responsibility.

`solve_temperature_joule_heat(mesh, *, electrical_conductivity,
thermal_conductivity, electric_dirichlet, thermal_dirichlet,
initial_temperature, outward_current=None, reference_potential=None,
outward_flux=None, convection=None, relaxation=0.5, temperature_atol=1e-8,
relative_tolerance=1e-10, max_iterations=100, method="picard")` uses relaxed
Picard iteration by default; `method="newton"` is described [below](#newton-method),
and *Choosing a method* below says when to use it.
The initial value is a finite scalar K or `(N,)` nodal K vector; impose thermal
Dirichlet values before the first evaluation. Initial values are required:
there is no implicit choice of a thermal branch. Relaxation is fixed in `(0,1]`.
Each iteration evaluates sigma(T_i), calls the existing electrical solver and
one-way heat solver to obtain H(T_i), then forms
`T_(i+1) = T_i + relaxation * (H(T_i)-T_i)`.

Convergence requires the **unrelaxed** infinity defect to be at most
`temperature_atol + relative_tolerance * max(abs(T_i), abs(H(T_i)))` and the
maximum elementwise relative change `abs(sigma(H(T_i))-sigma(T_i))/max(sigma(H(T_i)),sigma(T_i))` to be at most
`relative_tolerance`. Both the trial heat solution and relaxed state are checked
against material ranges. Tiny relaxation cannot manufacture convergence.
A further electric solve at H(T_i) verifies the nonlinear heat residual
`r_heat + load(T_i) - load(H(T_i))` on free thermal nodes. Its infinity norm
divided by the largest infinity norm of the two Joule loads and thermal
reaction/prescribed-outward/convective loads (machine tiny floor)
must be <= 1e-8. This dimensionless diagnostic is `nonlinear_heat_residual`.
Picard performs at most `max_iterations` coupled solves, with no hidden retry or
adaptive relaxation; the [Newton method](#newton-method) states its own bound.
Tolerances are finite positive, max_iterations is a positive integer. Multiple solutions, uniqueness and convergence are not guaranteed.

**Choosing a method.** Start with the default, `"picard"`: it is the established
path, the one JSON documents use, and the one the macOS and Windows installation
checks run (through the simcase `joule_temperature` example). With weak feedback
it converges in a few iterations, and an iteration costs less than a Newton state. Use `"newton"` when
Picard is slow or stops at `max_iterations` under strong feedback; for the
contract thermistor at alpha = 7 or 9 per K Newton needs 4 states (see
[Validation](#validation)). Pass `derivative` when dsigma/dT is known. Both
methods return a result only through the same convergence tests. Newton has been
run on Linux only.

## Newton method

`method="newton"` solves the same discrete equations by Newton's method on the
potential V and the temperature T together. Every state T_i is evaluated exactly
as above: sigma(T_i), the electric and one-way heat solves giving H(T_i), the
electric refresh at H(T_i), the history record and both convergence tests. The
step then comes from one sparse direct solve of the joint residual linearized at
(V(T_i), T_i):

- electric: `K(sigma(T)) V + outward current loads`;
- heat: `(K_t + H) T - Q(V, T) - (ambient - prescribed outward loads)`,
  with `Q` the centroid-rule Joule load and `H` the Robin matrix of the heat
  solve;
- electric Dirichlet and gauge nodes and thermal Dirichlet nodes held fixed.

Element blocks of the Jacobian are computed by a complex step through the
element kernels (`galerkin.core.kernels.p1_stiffness` and `p1_joule`), with sigma
extended to first order by dsigma/dT. `derivative` supplies dsigma/dT. Without
it, differences of `evaluate` with step `eps**(1/3)*max(1 K, |T|)` give it:
central inside the material range, second-order one-sided where the element mean
lies within a step of a range end, and first order where that two-step stencil
does not fit (ranges narrower than three steps). Apart from the element mean,
where sigma is evaluated anyway, every point lies inside the range. Their
relative error grows with the square of the step over the temperature in which
sigma changes: for the steepest thermistor below, about 1e-4 near the solution
and 5e-4 at its one-sided start from 300 K. dsigma/dT only shapes the step.

The next state is `T_i + alpha*dT` for the first alpha in `1, 1/2, ..., 2**-30`
whose evaluation succeeds and that either passes the convergence tests or has a
Euclidean temperature defect `norm(H(T)-T)` at most `(1-1e-4*alpha)` times that
of T_i. Halving stops early once a shorter step no longer changes T. A candidate
whose evaluation raises, for example outside a material range or at a subsolve
gate, is shortened; any exception counts, and one raised by a longer candidate
is not reported once a shorter candidate is accepted. If no alpha qualifies,
`JouleConvergenceError` reports `Newton step does not reduce the temperature
defect` with T_i's maximum-norm defect in K, as in its history record, followed,
when the last evaluated candidate failed, by that failure, chained as the cause.
A defect of a few ulp of the temperatures (about 1e-13 K at 300 K on the
contract's meshes, more on finer ones) may mean the tolerances ask for more than
floating point resolves. `relaxation` does not apply. `max_iterations` bounds the
accepted states, one history record each; each step evaluates at most 31
candidates, so at most `1 + 31*(max_iterations-1)` states are evaluated.

Convergence is decided only by the tests above, so a Newton result satisfies
the same bounds as a Picard result. With an exact `derivative` the defect falls
quadratically near a solution; with differences the last steps shrink it by
about their relative error. As with Picard, the initial value selects the solution branch;
the method does not diagnose stability or thermal runaway, and a failure from
a poor initial value is not evidence that no steady state exists (continuation
from a nearby solved load may succeed).

## Results, residuals and failure

Return a `TemperatureJouleHeatResult` containing `coupled` (the existing
`SteadyJouleHeatResult`), `evaluated_temperature` (T_i), and immutable scalar
`history` records. The returned thermal temperature is H(T_i); sigma belongs to
T_i. Their discrepancy is explicitly bounded by both convergence tests above,
not claimed to be an exact nonlinear root. Each record reports iteration,
unrelaxed temperature defect K, relative conductivity defect, temperature extrema
K, electric and thermal free residual infinity norms A/m and W/m, current balance
A/m, supplied/Joule/outward heat W/m, and electric/heat power defects W/m.
Existing subsolves retain their normalized 1e-10 residual and per-component
current/heat and electric-power gates; the one-way transfer retains its 1e-10
power gates. These checks do not replace the nonlinear fixed-point tests.
Arrays are owned snapshots. The evaluated-temperature array is read-only.
Rates are per unit out-of-plane depth; multiply W/m by depth in m for W.

### Errors

Before anything is evaluated, the solver checks the mesh and these options and
raises ValueError: the mesh is a valid triangle mesh (no coincident nodes, for
example); `method` is `"picard"` or `"newton"`; `relaxation` is in (0,1] and
both tolerances are finite and positive; `max_iterations` is a positive integer;
`electrical_conductivity` is one `ConductivityModel` or a table of them whose
keys are exactly the mesh region names; `initial_temperature` is a finite real
scalar or `(N,)` vector in K; and `thermal_dirichlet` maps exterior integer node
indices to finite K. A JAX or PyTorch value passed directly in any other input
(or inside its tables) raises TypeError before that
([refused, not approximated](differentiation.md#refused-not-approximated));
`method` and `electrical_conductivity` accept only a string and
`ConductivityModel`s, so a live value there is the ValueError above.

Everything else is checked when a state T_i is evaluated, by the solver's sigma
checks or by the subsolves: the thermal conductivity, the electric Dirichlet and
reference potentials, the outward current, flux and convection data, and every
value a conductivity or boundary callback returns. Any `Exception` raised during
an evaluation is wrapped in `JouleConvergenceError` with the original exception
chained as `__cause__`; KeyboardInterrupt and SystemExit pass through. That
covers a ValueError for a negative or nonfinite thermal conductivity, an
electric Dirichlet node outside the mesh or an unknown boundary tag, a sigma
callback value that is not positive, a material range violation, any
`Exception` a callback raises, and the TypeError for a live value a callback
returns. `JouleConvergenceError` is a
RuntimeError, so `except ValueError` and `except TypeError` do not catch these
failures; read the cause instead. An invalid input usually fails in the first
evaluation, before any record exists, so `history` may be empty. Newton also
raises `JouleConvergenceError` when its step cannot be formed (the Jacobian,
dsigma/dT or the linear solve), chaining that cause, and when its line search
accepts no step (above). Reaching `max_iterations` raises it without a cause.
No partial successful result is returned.

The error carries `reason` (its message), `history` (the completed records, one
per Picard iteration or accepted Newton state) and `last_temperature`, a
read-only `(N,)` array in K whose state depends on how the solve ended:

| How the solve ended | `last_temperature` |
|---|---|
| Picard reaches `max_iterations` | the relaxed next state `T_i + relaxation*(H(T_i)-T_i)`; it is not evaluated and not in `history` |
| Newton reaches `max_iterations` | the last accepted state T_i, whose H(T_i) is the last record of `history` |
| Newton cannot form a step, or its line search accepts none | the last accepted state T_i |
| An evaluation fails before its heat solution exists (sigma(T_i), the electric solve or the heat solve) | the state being evaluated, T_i |
| An evaluation fails after its heat solution exists (for example H(T_i) outside a material range) | that trial heat solution H(T_i) |

The last two rows apply to every Picard iteration and to Newton's first state;
a Newton candidate that fails to evaluate is shortened instead (above). Range
errors identify the material and the offending extrema.

## Validation

Both methods run every check below that applies to them (relaxation is Picard's). Constant models must match the existing
workflow to 1e-10 relative. Compare with
independent scikit-fem assembly (1e-9 relative), and a one-dimensional analytic
current-driven thermistor embedded in 2D: rho(T)=rho0*(1+alpha*(T-T0)),
T=T0+(cos(beta*(x-L/2))/cos(beta*L/2)-1)/alpha,
beta²=J²*rho0*alpha/k. Refine n=8,16,32; final temperature L2 order >1.8.
Check current conservation, power/heat balance and strong feedback, relaxation,
range and maximum-iteration failure. Newton must agree with Picard to 2e-8 K where
Picard converges, converge where Picard at its default settings does not (alpha = 7 and
9 per K), handle every boundary kind with region models, and its element and
assembled Jacobians must match central differences of the residual (1e-7
relative). Verification results and executable example are exercised by
`test_temperature_joule_heating.py`, `test_temperature_joule_newton.py` and
`test_crosscheck_skfem_temperature_joule.py`. These run in source and installed
CI. Local validation passed; complete platform evidence depends on CI.

## Example and limitations

Run [the example](../../../examples/galerkin/temperature_joule_heating.py) from the
repository root with galerkin installed:

```bash
python examples/galerkin/temperature_joule_heating.py
```

The example prescribes 1 A/m² outward on the right, V=0 on the left, T=300 K
at both ends, k=1 W/(m K), sigma=1/(1+0.5*(T-300)) S/m and a [300,400] K
valid interval. It prints temperature, W/m power, iteration count and defects.
`ElementConductivity(mesh, values)` in `galerkin.electric` also accepts explicit
positive finite `(M,)` S/m snapshots with exact geometry/order/region checks.
It holds them in an element [`Field`](coupling.md) in S/m, and its shape and
mesh mismatch errors begin with `element conductivity`; bare arrays remain
invalid.
This does not change thermal conductivity inputs.

For prescribed current, positive resistivity feedback can approach a thermal
runaway or a loss of steady solutions. Failure is not evidence of a transient
trajectory or of physical instability; it only establishes failure of this
specified solve. Try a justified initial condition, relaxation and iteration
budget, or `method="newton"`, without changing acceptance tolerances. Model ranges remain
hard constraints. Boundary callbacks must be deterministic as well.

Picard (2026-10-26): 28 feature tests; scikit-fem maximum relative difference 1.04e-12 (<1e-9);
continuous-temperature RMS L2 errors 1.52995e-3, 3.83592e-4, 9.59884e-5 K
at n=8/16/32 (final order 1.999). Strong feedback alpha=7 converged in
59/128 iterations at relaxation 1/0.5 with n=8. Failure histories are tested.

Newton (2026-10-29, Linux): the same L2 errors and order in 3 states at every
n; scikit-fem maximum relative difference 1.06e-12 (<1e-9). With n=16, alpha=7
and 9 per K converge in 4 states, against 63/136 and 206/422 Picard iterations
at relaxation 1/0.5 (the default relaxation 0.5 needs more than the default 100
iterations); the results agree with Picard to 1.4e-9 K. The Jacobian matches
central differences to better than 1e-7 relative.

[Homogeneous rectangle JSON/CLI input and save contract](../simcase/electric_joule.md). This exposes a subset of the Python API.
