# Temperature-dependent 3D heater at fixed voltage

**English** | [한국어](../../locales/ko/pages/packages/galerkin/temperature_dependent_heater_3d.md)

Run `python examples/galerkin/temperature_dependent_heater_3d.py` from the
repository root. The [example](../../../examples/galerkin/temperature_dependent_heater_3d.py)
uses `galerkin.transient_joule_heat3d.solve_transient_joule_heat_3d` and passes
the resulting nodal temperatures directly to
`galerkin.transient_thermoelasticity3d.solve_thermoelasticity_history_3d` on
the same tetrahedra. It compares a temperature-dependent conductor with its
constant-conductivity counterpart.

The resistivity is ρ(T) = ρ₀[1 + β(T − T₀)], so the callback returns
σ(T) = σ₀/[1 + β(T − T₀)] in S/m. The callback receives absolute Kelvin
at each tetrahedron's mean temperature. The model's inclusive range is
298–320 K, within which the denominator is positive. Here σ₀ = 10 S/m,
T₀ = 300 K and β = 0.25 K⁻¹. This deliberately large coefficient
makes the negative feedback visible at fixed voltage. A warmer conductor
draws less current and electrical power.

The bar is 0.20 m long and 0.05 m wide and thick. Its left thermal end is
held at 300 K and its right end convects to 300 K with a surface coefficient
of 40 W/(m² K). The other faces are thermally insulated. The voltage
difference is 2 V from 1 s until 3 s and 0 V otherwise. Both switches are
time-grid points. The solver samples voltage at the interval midpoint
and evaluates conductivity using the converged temperature at the interval
end. The table associates the prior interval's power (W) with that end
time (s). Temperature and stress are continuous across a switch, whereas
the applied voltage can jump.

Positive electrical terminal current enters the body. Positive surface heat
loss leaves it. The energy audit in joules compares the time integral of
electrical input with stored heat and boundary losses. Stored temperatures
are K. With both ends fixed axially and every transverse displacement fixed,
the solid's mean axial stress is negative in compression (Pa), and the
support forces (N) at the hot bar's left and right ends point into the bar.
This example uses E = 70 GPa, ν = 0 and α = 12 × 10⁻⁶/K.

## Independent insulated reference

An insulated uniform bar at constant voltage starts at T₀ with no spatial
temperature gradients. Putting θ = T − T₀, the electrical input is
P₀/(1 + βθ), where P₀ = σ₀A ΔV²/L = 0.5 W. The total heat capacity is
Cᵥ Vol = 0.5 J/K. Integrating Cᵥ Vol dθ/dt = P₀/(1 + βθ) gives

```text
θ + βθ²/2 = P₀ t / (Cᵥ Vol)
I = P₀ / [ΔV (1 + βθ)]
σₓₓ = −Eαθ
(F_left, F_right) = (−Aσₓₓ, Aσₓₓ)
```

At 2 s this gives a rise of 1.65685 K, 0.17678 A, and −1.39176 MPa
in mean axial stress. The test checks first-order time convergence at 8,
16 and 32 intervals and checks the current against the numerical end
temperature as an audit of implicit coupling. The lossy run checks
thermal and electrical energy balance, reduced input energy, temperature
and compression compared with fixed conductivity, and relaxation after
cutoff. Use `python -m pytest -q tests/galerkin/test_temperature_dependent_heater_3d.py`
to run the checks.

## Example output

The insulated bar's maximum temperature error on the three time grids is
0.029590, 0.015050 and 0.007591 K. The following lossy-pulse samples use
a 1/16 s time step and 12 axial cells. Power is from the preceding interval.
The two forces are opposite, so the table gives the left support force.

| Time (s) | Conductivity | Power (W) | Input (J) | Peak rise (K) | Mean axial stress (MPa) | Left force (N) |
|---:|---|---:|---:|---:|---:|---:|
| 3 | Temperature dependent | 0.391277 | 0.861223 | 1.478605 | −0.933912 | 2334.78 |
| 3 | Constant | 0.500000 | 1.000000 | 1.693215 | −1.084457 | 2711.14 |
| 7 | Temperature dependent | 0 | 0.861223 | 0.411612 | −0.247403 | 618.51 |
| 7 | Constant | 0 | 1.000000 | 0.476033 | −0.286124 | 715.31 |
