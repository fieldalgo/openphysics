# Temperature-dependent Joule tutorial: feedback and convergence

**English** | [한국어](../../locales/ko/pages/packages/galerkin/temperature_joule_tutorial.md)

Read the [constant-property Joule tutorial](joule_tutorial.md) first. That example
solves electricity once; here conductivity changes with temperature and the
steady electric/heat problem is solved repeatedly. Iterations are **not time steps**.

## 1. Define a current-driven model

Use Python 3.12 or newer and an activated virtual environment. From the repository root:

```sh
python -m pip install -e packages/galerkin
python examples/galerkin/temperature_joule_heating.py
```

The [example](../../../examples/galerkin/temperature_joule_heating.py) uses a
1 m × 0.25 m rectangle with 16 × 4 cells. The left potential is 0 V and the
right outward current density is 1 A/m². The other electric natural boundaries
are insulated. Both thermal ends are 300 K, the top/bottom are insulated,
and k=1 W/(m K). Current density is not total current: the right edge carries
0.25 A/m of extrusion depth.

The illustrative resistivity law is `rho(T)=1+0.5*(T-300)` ohm m, so
`sigma(T)=1/rho(T)` S/m. `ConductivityModel` declares the valid range [300,400] K.
A deterministic callback accepts a 1D temperature array and returns the same
shape of positive finite conductivities. The solver checks nodal ranges and
evaluates conductivity at each triangle's mean nodal temperature; it does not
average three independently evaluated conductivities. No clipping or extrapolation
is used to force a solution into the range.

## 2. Read a converged calculation

A run with the example's `relaxation=1.` gives approximately:

```text
Maximum temperature: 300.131806613 K
Joule power: 0.260917862 W/m
Iterations: 8
Unrelaxed defect: 1.049e-10 K
Nonlinear heat residual: 6.216e-12
```

Last digits and the iteration count may vary with numerical runtime. Under fixed
current, increasing resistivity increases `Q=J²*rho`, which raises temperature
and feeds back into resistivity. This is different from holding voltage fixed;
do not carry over the previous tutorial's voltage-squared scaling rule to this problem.

For this one-dimensional continuous thermistor, the reference formula is
`T=300+(cos(beta*(x-L/2))/cos(beta*L/2)-1)/alpha`, with
`beta²=J²*rho0*alpha/k`, L=1 m and alpha=0.5 /K. The finite mesh approximates
that solution; the [contract's validation](temperature_joule_heating.md) records
independent refinement evidence. A successful iteration alone is not that evidence.

## 3. Understand the stopping checks

Each Picard step computes a trial heat solution H(T) from conductivity evaluated
at T, then updates `T_next=T+relaxation*(H(T)-T)`.

- The temperature defect measures **H(T)−T before relaxation**, in kelvin.
- A separate relative conductivity-defect check must pass.
- A refreshed electric solve checks the dimensionless nonlinear heat residual.
- Current and power/heat balance checks from the subsolves remain in force.

Tiny relaxation cannot manufacture convergence by merely making the update small.
`result.history` contains scalar diagnostics, while `result.coupled` holds the
accepted electric/heat result. The evaluated-temperature snapshot and the returned
trial temperature differ within the accepted checks; they are not an exact nonlinear root.

## 4. Try controlled changes and failures

Copy the script outside `packages/` and change one setting at a time.

| Change | What to examine |
|---|---|
| `relaxation=.5` | Same solution within tolerance; a local run took 33 iterations rather than 8 |
| Replace `.5*(t-300)` by `0.*(t-300)` | Constant sigma=1 S/m: maximum 300.125 K, power 0.25 W/m |
| Add `max_iterations=1` to the solver call | `JouleConvergenceError`: the budget is insufficient; one completed history record is retained |
| Change the model range to `(300., 300.05)` | A trial exceeds the valid material range; no successful partial result is returned |

For diagnostics, import `JouleConvergenceError` from
`galerkin.temperature_joule_heating` and catch it around the solve. Inspect
`reason`, `history` and `last_temperature`. These are failure diagnostics, not an
accepted coupled result. In the narrow-range experiment, the first trial can fail
before any history record is completed.

Do not loosen acceptance tolerances or widen a material range just to hide failure.
Use physically justified inputs and, where appropriate, initial temperature,
relaxation and iteration budget. Failure of this particular fixed-point solve
does not establish physical thermal runaway, nor provide a transient trajectory.

## 5. Scope and next reading

This is steady DC on a fixed 2D mesh with constant thermal conductivity and a
bounded temperature-dependent electric law. It provides neither uniqueness nor
convergence guarantees for arbitrary inputs. For definitions and failure policy,
read the [normative contract](temperature_joule_heating.md).

The separate [JSON/CLI contract](../simcase/electric_joule.md) provides a
homogeneous rectangle and declared linear-resistivity model, not arbitrary Python
callbacks. Neither route supplies a temperature-dependent Joule Studio view.
