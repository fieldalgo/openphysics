# Voltage-driven transient 3D Joule heating

**English** | [한국어](../../locales/ko/pages/packages/galerkin/transient_joule_heat3d.md)

Import `solve_transient_joule_heat_3d` from `galerkin.transient_joule_heat3d`.
Use one metre-based `Mesh3D` for the DC and thermal fields. Supply increasing
`time` in seconds and a nodal `initial_temperature` in K. Electrode potentials
are volts keyed by exterior face tag. A voltage callback takes an interval
midpoint in seconds and returns this mapping. The solver calls it once per
interval. Put each voltage switch on the time grid.

Electrical conductivity is in S/m. Supply a positive scalar, a
`galerkin.temperature_joule_heating.ConductivityModel`, or a named region
mapping with a scalar or model per region. A model evaluates conductivity at
each tetrahedron's mean nodal temperature. Choose a Kelvin validity interval
that covers the initial state and trial temperatures during iteration.
Thermal conductivity is W/(m K), volumetric heat capacity is J/(m³ K),
inward heat flux is W/m², and the film coefficient is W/(m² K). The thermal
boundary inputs follow the [3D heat solver](thermal3d.md). Positive inward
electric power supplies heat. The thermal audit reports prescribed and
convective rates as positive outward, and generation and support reactions
as positive into the body.

Backward Euler uses interval-end temperatures for the electrical feedback.
Each Picard trial solves DC and applies its element Joule density in W/m³.
The solver checks the undamped temperature change against
`temperature_tolerance` in K and the maximum relative conductivity change
against `relative_tolerance`. The relative change divides the absolute
difference by the larger of the two positive conductivities. Use
`relaxation_factor` in (0, 1] to damp updates. An invalid model state or
exhausted `iteration_limit` raises an interval-specific error.

The result exposes `heat`, `electric`, and `iteration_count`. Thermal
temperatures include the initial row. Electric results and counts have one
entry per interval. Each electric entry supplies exactly the Joule density
used in that interval's thermal solve. Its conductivity agrees with the
model at the stored end temperature within the relative tolerance.
Compare the integrated Joule input with the heat storage change, prescribed
and convective export, and fixed-temperature reactions to audit energy.
The tests include an insulated constant-voltage slab with a closed-form
backward Euler update, an off switch, and a convective energy balance.

A finite thermal contact uses matching, separately numbered thermal faces and a constant `thermal_contact_conductance` for each tag pair. Thermal coupling leaves the electrical terminal map independent. Give each electrically disconnected component a reference potential. The [heater pulse example](../../../examples/galerkin/transient_thermal_contact_3d.py) switches the voltage off and integrates the heat that continues to cross the interface from stored energy. Read interval-end rates from `result.heat.contact_heat_rate`. [Thermal signs, units and energy integration](transient_heat3d.md#finite-thermal-contact-during-a-pulse).
