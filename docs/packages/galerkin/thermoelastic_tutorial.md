# First thermal expansion calculation: heat then mechanics

**English** | [한국어](../../locales/ko/pages/packages/galerkin/thermoelastic_tutorial.md)

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

## 1. Separate thermal and mechanical conditions

The [example](../../../examples/galerkin/thermal_mechanical_workflow.py) uses a
1 m × 1 m rectangle, with 303.15 K on the left, 323.15 K on the right and
insulation elsewhere. Thermal conductivity is 10 W/(m K).
Mechanics uses E=70 GPa, nu=0.3, linear expansion alpha=12e-6 /K and a
stress-free reference temperature of 293.15 K. The selected model is **plane strain**.

A fixed temperature does not fix displacement. The mechanical mapping is
`{(0,0):0., (0,1):0., (n,1):0.}`: node 0 has x/y displacement fixed,
and node n has y displacement fixed. For this structured mesh, node 0 is the
bottom-left corner and node n the bottom-right. These three scalar constraints
remove in-plane translations and rotation. Do not reuse those IDs on an arbitrary mesh;
select the intended physical points and components there.
The other mechanical boundaries have zero total thermoelastic natural traction.

## 2. Run the two stages

```sh
python examples/galerkin/thermal_mechanical_workflow.py
```

The JSON printed to the terminal includes:

| Field | Approximate result | Interpretation |
|---|---|---|
| `temperature_range_k` | [303.15, 323.15] | The steady heat field transferred to mechanics |
| `net_outward_heat_w_per_m` | Near zero, about 1e-13 | Net heat flow is zero without a source, though heat crosses the slab |
| `max_displacement_m` | 4.8693e-4 | About 0.487 mm under this mesh, model and constraints |
| `sigma_zz_range_pa` | [−2.4641e7, −8.9588e6] | Out-of-plane stress is generally nonzero under plane strain |
| `physical_elastic_energy_j_per_m` | 2206.0 | Physical elastic energy per extrusion depth |
| `stages` | heat, mechanics, transfer completed | All requested stages completed |
| `authentication` | `not_certified` | Not a certification of external inputs or physical accuracy |

The reference temperature enters thermal strain through `alpha*(T-Tref)`.
It is not subtracted from the heat boundary values: the heat solver receives absolute kelvin.
Plane strain imposes zero out-of-plane strain, not zero out-of-plane stress.
Use the [mechanical-stage contract](prescribed_temperature_thermoelasticity.md)
for the three-dimensional constitutive reduction and energy definition.

## 3. Change a parameter and check the interpretation

Copy the script to a local working file outside `packages/`, then make one change at a time.

- Set `thermal_expansion_per_k=0.`. With the example's zero displacement supports
  and no body force, displacement, stress and elastic energy become zero;
  the heat result stays unchanged.
- Double alpha to `24e-6` with all other inputs fixed. In this linear problem,
  displacement and stress double and elastic energy quadruples. This is a useful
  consistency check, not an independent validation of the constitutive law.
- Increase `n` from 8 to 16, then 32. Keep `n` in the support map so the second
  support remains at the bottom-right corner. Compare displacement, stress and
  energy, not only the unchanged end temperatures. This example does not prescribe
  an acceptance tolerance or claim a converged stress field.

## 4. Understand the coupling boundary

Heat is solved first and its nodal field is transferred on the same isolated
reference mesh. The mechanical deformation does not remesh the heat problem or
feed back into temperature. These are steady, small-strain, one-way calculations,
not structural dynamics. This workflow is Python-only; it has no JSON/CLI or Studio form.
The separate heat flux/Robin and mechanical traction extensions are not arguments
of this steady workflow.

For exact units, checks and provenance read the
[workflow contract](thermal_mechanical_workflow.md) and
[independent acceptance](thermal_mechanical_independent_validation.md).
For quasistatic mechanics at selected stored heat times, use the separate
[transient thermal-mechanical workflow](transient_thermal_mechanical.md).
