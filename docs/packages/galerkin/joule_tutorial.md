# First Joule calculation: electric power becomes heat

**English** | [한국어](../../locales/ko/pages/packages/galerkin/joule_tutorial.md)

Run a maintained Python example, explain its physical output, then change one input.
This tutorial uses the engine directly; no Studio or plotting extra is needed.

## Before you start

Use Python 3.12 or newer and an activated virtual environment. From the repository
root, install the two local packages used by these tutorials:

```sh
python -m pip install -e packages/galerkin -e packages/galerkin-refsol
```

For checkout/environment setup, see the [suite overview](../../overview.md).
Run commands from the repository root, not inside `packages/`. These examples
print to the terminal and do not save plots or result files.

## 1. Define two solves on one mesh

A 0.02 m × 0.01 m rectangle has left/right voltages 0 V and 2 V. Its electric
conductivity is 3 S/m. Both ends are held at 300 K, with thermal conductivity
5 W/(m K). The top and bottom have zero normal current and are thermally insulated.

The [example](../../../examples/galerkin/joule_heating.py) first calls
`solve_steady_electric`, then passes that result to `solve_steady_joule_heat`
on the same mesh. Electric `conductivity` is in S/m; thermal `conductivity` is
in W/(m K). They are different properties even though the keyword is the same.
The thermal call uses a new boundary map in kelvin; voltages are not temperatures.

## 2. Run and interpret

```sh
python examples/galerkin/joule_heating.py
```

```text
Maximum temperature: 300.300000 K
Joule power per length: 6.000000 W/m
Outward heat per length: 6.000000 W/m
```

These are the reference-scale outputs of this example; last digits can vary.
The electric field is `E_x = -2/0.02 = -100` V/m, and `J_x = sigma*E_x = -300` A/m².
Their dot product is positive: `Q = J·E = 30000` W/m³.
The power per depth is `Q*0.02*0.01 = 6` W/m. With 1 mm physical depth it is
0.006 W. There is no AC averaging factor of 1/2 in this DC problem.

With fixed end temperature `T0`, the continuous solution is
`T(x) = T0 + Q*x*(L-x)/(2*k)`, giving a centre rise `Q*L²/(8*k) = 0.3` K.
The P1 solution samples this temperature field; its elementwise flux is still
an approximation. Agreement of the maximum alone does not establish field convergence.

## 3. Change voltage, then conductivity

Copy the example to a local working file outside `packages/`. Change one item at a time.

| Change | Expected maximum | Power per depth | Reason |
|---|---|---|---|
| Right voltage 4 V | 301.2 K | 24 W/m | At fixed conductivity, Q scales with voltage squared |
| Right voltage −2 V | 300.3 K | 6 W/m | E and J reverse together; their dot product is unchanged |
| Thermal conductivity 10 W/(m K), voltage 2 V | 300.15 K | 6 W/m | Better heat conduction lowers the rise, not the electrical power |

These predictions apply to this constant-property model and these boundaries.
They are not scaling rules for temperature-dependent conductivity or convection in general.
For another mesh, rerun the electrical solve before passing its result into heat:
geometry, ordering and region correspondence must match; the workflow does not interpolate.

## 4. Decide whether one-way transfer is enough

This example solves electricity once, then heat. Temperature does not change
conductivity. For that feedback use the separate
[temperature-dependent Joule contract](temperature_joule_heating.md), which has
material validity ranges and nonlinear iteration acceptance checks.

Read the [electric contract](electric_steady2d.md) and
[Joule contract and validation](joule_heating.md) for current/power signs and evidence.
The [JSON/CLI route](../simcase/electric_joule.md) supports a bounded homogeneous
rectangle model and has no Studio execution. Its example uses different dimensions
and coefficients, so it does not reproduce the numbers above unchanged.
