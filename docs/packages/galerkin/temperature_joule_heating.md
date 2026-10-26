# Temperature-dependent steady Joule heating

**English (normative contract)** | [한국어](../../locales/ko/pages/packages/galerkin/temperature_joule_heating.md)

## Scope and equations

Python only: fixed conforming 2D P1 triangles in metres, DC, isotropic sigma(T),
constant positive thermal conductivity k (scalar or named-region table).
Solve div(J)=0, E=-grad(V), J=sigma E, Q=J.E and -div(k grad(T))=Q.
The existing [electric contract](electric_steady2d.md) and
[one-way transfer](joule_heating.md) define boundaries, gauges and power signs.
No transient, 3D, mesh motion, extra heating, Studio or release is included.

## Material and iteration contract

`galerkin.temperature_joule_heating.ConductivityModel(evaluate, temperature_range)`
contains a deterministic vector callback accepting a one-dimensional Kelvin array
and returning exactly that shape in S/m, plus finite inclusive `(T_min, T_max)`
with `0 <= T_min < T_max`. Use one model or an exact named-region mapping.
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
relative_tolerance=1e-10, max_iterations=100)` uses relaxed Picard iteration.
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
At most `max_iterations` coupled solves are performed; no hidden retry or
adaptive relaxation. Tolerances are finite positive, max_iterations is a positive
integer. Multiple solutions, uniqueness and convergence are not guaranteed.

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

Invalid static options raise ValueError. A material, range, subsolve or iteration
failure raises `JouleConvergenceError` with `reason`, completed `history`,
`last_temperature`, and the chained original cause where applicable. No partial
successful result is returned. Maximum-iteration failure retains the last
completed trial's history. Range errors identify material and offending extrema.
Rates are per unit out-of-plane depth; multiply W/m by depth in m for W.

## Validation

Constant models must match the existing workflow to 1e-10 relative. Compare with
independent scikit-fem assembly (1e-9 relative), and a one-dimensional analytic
current-driven thermistor embedded in 2D: rho(T)=rho0*(1+alpha*(T-T0)),
T=T0+(cos(beta*(x-L/2))/cos(beta*L/2)-1)/alpha,
beta²=J²*rho0*alpha/k. Refine n=8,16,32; final temperature L2 order >1.8.
Check current conservation, power/heat balance and strong feedback, relaxation,
range and maximum-iteration failure. Verification results and executable example
are exercised by `test_temperature_joule_heating.py` and
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
It reuses the mesh-binding machinery of element sources; bare arrays remain
invalid. This does not change thermal conductivity inputs.

For prescribed current, positive resistivity feedback can approach a thermal
runaway or a loss of steady solutions. Failure is not evidence of a transient
trajectory or of physical instability; it only establishes failure of this
specified fixed-point solve. Try a justified initial condition, relaxation and
iteration budget without changing acceptance tolerances. Model ranges remain
hard constraints. Boundary callbacks must be deterministic as well.

Validation: 28 feature tests; scikit-fem maximum relative difference 1.04e-12 (<1e-9);
continuous-temperature RMS L2 errors 1.52995e-3, 3.83592e-4, 9.59884e-5 K
at n=8/16/32 (final order 1.999). Strong feedback alpha=7 converged in
59/128 iterations at relaxation 1/0.5. Failure histories are tested.
