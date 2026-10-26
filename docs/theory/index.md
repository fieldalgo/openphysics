# Theory and numerical methods

**English** | [한국어](../locales/ko/pages/theory/index.md)

[Documentation home](../README.md)

Formulations and numerical methods currently live alongside their implementation
contracts. Use these paths to read them, and the [validation index](../validation/index.md)
for independent evidence. This reading route does not establish additional accuracy or convergence.

## Electromagnetic modes and coordinates

- [Vacuum rectangular PEC cavity solver](../packages/galerkin/cavity_solver.md)
- [Material-loaded rectangular cavity solver](../packages/galerkin/material_cavity.md)
- [Vector eigenspace reliability](../packages/galerkin/eigenspace_reliability.md)
- [Modal complex coordinates](../packages/galerkin/modal_coordinates.md)

## Heat and electric conduction

- [Steady two-dimensional heat conduction](../packages/galerkin/thermal_steady2d.md)
- [Steady 2D outward heat flux and convection](../packages/galerkin/thermal_flux_robin.md)
- [Transient heat on a fixed P1 mesh](../packages/galerkin/transient_heat.md)
- [Steady 2D electric conduction](../packages/galerkin/electric_steady2d.md)
- [Steady Joule heating](../packages/galerkin/joule_heating.md)
- [Temperature-dependent steady Joule heating](../packages/galerkin/temperature_joule_heating.md)

## Mechanics, materials and coupling

- [Two-dimensional small-strain elasticity](../packages/galerkin/elasticity2d.md)
- [Cartesian boundary traction for 2D elasticity](../packages/galerkin/elasticity_traction.md)
- [Piecewise-constant materials on named regions](../packages/galerkin/multimaterial.md)
- [Prescribed-temperature thermoelasticity (2D mechanical stage)](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
- [Prescribed-temperature thermoelasticity with total mechanical traction](../packages/galerkin/thermoelastic_traction.md)
- [Explicit steady heat → thermoelastic mechanics](../packages/galerkin/thermal_mechanical_workflow.md)
- [Transient heat to quasistatic mechanics](../packages/galerkin/transient_thermal_mechanical.md)

## Independent reference implementations

- [galerkin-refsol — reference solutions for validating galerkin](../packages/galerkin-refsol/overview.md)
