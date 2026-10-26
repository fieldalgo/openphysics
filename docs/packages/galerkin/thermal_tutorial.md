# First heat calculation: a conducting slab

**English** | [한국어](../../locales/ko/pages/packages/galerkin/thermal_tutorial.md)

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

## 1. Define the problem

A 2 m × 0.7 m rectangle has its left side at 350 K and right side at 300 K.
The top and bottom are insulated. The thermal conductivity is 12 W/(m K),
with no internal heat source. We want temperature and heat flux, not a time history.
All coordinates passed to this Python engine are metres; temperatures are kelvin.

The maintained [example](../../../examples/galerkin/thermal_steady2d.py) builds
`rectangle_mesh(2., .7, 8, 5)`: 8 × 5 cells, each split into two P1 triangles.
It selects actual left/right boundary node IDs for `dirichlet`; unselected
natural edges are insulated. `solve_steady_heat` returns nodal temperature
and one constant flux vector per triangle.

## 2. Run and interpret

```sh
python examples/galerkin/thermal_steady2d.py
```

The script prints the following quantities. Roundoff-sized values may vary by machine.

| Printed quantity | Expected scale | Meaning |
|---|---|---|
| Maximum temperature error | About 1e-13 K | Comparison with the independent `refsol.thermal.slab` solution |
| Mean heat flux | [300, 0] W/m² | Heat flows toward positive x, from hot to cold |
| Left/right heat input | +210, −210 W/m | Positive reaction injects heat; negative reaction removes it |
| Heat imbalance | About 1e-12 W/m or smaller | Sum of source load and boundary reactions |

For this homogeneous slab, the independent answer is
`T(x) = 350 - 25*x` K and `q_x = -k*dT/dx = 300` W/m².
Integrating over the 0.7 m side gives 210 W/m of extrusion depth. A physical
depth of 0.01 m therefore carries **2.1 W**, not 210 W. Depth is an explicit
external multiplication; it is not an implicit solver parameter.

## 3. Change one input

Make a local copy of the example outside `packages/` and change one item at a time.
Generated copies and outputs are local experiments, not shipped validation evidence.

- Set both boundaries to 300 K, including `left_temperature` in the reference call.
  With no source, temperature is constant and flux is zero.
- Double conductivity from 12 to 24 in both the solver and reference calls.
  Temperature stays the same; flux becomes 600 W/m² and the reactions become ±420 W/m.
- Refine `rectangle_mesh` from `(8, 5)` to `(16, 10)`. The exact temperature is linear,
  already representable by P1 elements, so this case remains near roundoff. It is
  a useful sign/unit check, not a measurement of general convergence order.

If the reference call still contains the old inputs, the reported error compares
two different physical problems. Keep both calls consistent when modifying this example.

## 4. Know what this checks

Global energy balance does not prove local flux accuracy. Nonuniform sources,
material interfaces and curved geometry need their own resolution studies.
A boundary reaction is an integrated weak quantity (W/m), not flux density (W/m²).

Continue with the [heat contract](thermal_steady2d.md),
[flux and convection](thermal_flux_robin.md),
[independent acceptance](thermal_independent_validation.md) or
[heat documents](../simcase/thermal_steady2d.md) for the separate JSON/CLI route.
Next: [generate heat electrically](joule_tutorial.md) or
[transfer temperature to mechanics](thermoelastic_tutorial.md).
