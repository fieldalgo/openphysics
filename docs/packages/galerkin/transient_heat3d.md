# Transient heat conduction in 3D

[한국어](../../locales/ko/pages/packages/galerkin/transient_heat3d.md)

Call `galerkin.transient_heat3d.solve_transient_heat_3d` with a conforming
`Mesh3D` in metres. The solver uses P1 tetrahedra, consistent heat capacity
and backward Euler. Set `thermal_conductivity` in W/(m K) and
`volumetric_heat_capacity` in J/(m³ K) as positive scalars or maps covering all
material regions. The strictly increasing `time` array contains at least two
times in seconds and can use unequal steps. Set `initial_temperature` to an
array of N Kelvin values.

The optional `prescribed_temperature` maps exterior nodes to fixed Kelvin
values that agree with the initial state. `inward_heat_flux` maps exterior
face tags to W/m² entering the body. `convection` maps tags to
`(h, ambient_temperature)` in W/(m² K) and K. These boundary data follow the
[steady solver contract](thermal3d.md). An entirely insulated body is valid.

`heat_source_density` is in W/m³ and accepts a scalar, region map or array
in tetrahedron order. A callable takes the interval midpoint in seconds and
returns one of these forms. Include each heater switching time in the time grid.
Equal step sizes can reuse their sparse factorization.

The result stores `time` (S,) and `temperature` (S, N), including the initial
state. Each nodal rate is (S−1, N) in W. For each interval, the sum of
`heat_storage_rate` equals the sum of `generated_heat_rate` plus
`reaction_heat_rate` minus `outward_prescribed_heat_rate` and
`outward_convective_heat_rate`, up to numerical residual. Multiplying by the
interval duration gives the change in `stored_heat` (J). Reaction is positive
into the body and vanishes at free nodes. `residual_heat_rate` is storage plus
conduction and outward rates minus generation before subtracting the reaction.

Validation uses a switched insulated source with a closed-form temperature
and energy ledger, an independent consistent-mass tetrahedral eigenmode with
first-order time convergence, a linear mixed-boundary equilibrium and a cooling
case with a Robin boundary. A separate scikit-fem assembly cross-checks every
nodal temperature for a partially heated, two-material body with convection
and unequal time steps.

## Finite thermal contact during a pulse

Pass the same `thermal_contact_conductance` map as in [steady thermal contact](thermal3d.md#finite-thermal-contact-between-solids). Each value is a constant conductance per unit area in W/(m² K) on two matching, separately numbered faces. Initial temperatures may differ across the interface. The bodies may be externally insulated because their heat capacities determine the time evolution. A zero coefficient insulates the contact.

`contact_heat_rate[i]` gives the nodal contact rates in watts at `time[i+1]`, positive out of each body. Opposing rates cancel in the combined energy balance. To find the energy crossing from a heater into the substrate for a pulse with a single contact on the heater, sum the heater-side rates and multiply by each interval duration.

```python
import numpy as np

dt = np.diff(result.time)
power_to_substrate = result.contact_heat_rate[:, mesh.boundary["heater_z0"]].sum(axis=1)
energy_to_substrate = np.dot(dt, power_to_substrate)  # J
```

The rate history has shape (S−1, N) and is read-only. Omitting the contact map gives `None`. The [pulsed heater example](../../../examples/galerkin/transient_thermal_contact_3d.py) uses the Joule solver and reads these fields from `result.heat`.

On the example's 2,304 tetrahedra, a 1 V pulse supplies 2 W for 1 s. With a contact area of 80 mm², conductance of 5,000 W/(m² K) and a base held at 300 K, the heater and substrate faces reach 306.386 K and 301.462 K at switch-off using a 1/128 s step. Electrical input then drops to zero. During the next second 0.4163 J crosses from the heater into the substrate. A 1/32 s step gives 0.4135 J for the same interval.
