# Mechanics and thermal coupling

**English** | [한국어](../locales/ko/pages/physics/mechanics.md)

[Documentation home](../README.md)

Choose plane stress or plane strain and define displacement constraints and loads. Prescribed-temperature mechanics, steady heat-to-mechanics and selected transient-heat snapshots are distinct explicit workflows on the same mesh.

## First Python calculations

- [First thermal expansion calculation: heat then mechanics](../packages/galerkin/thermoelastic_tutorial.md)

## Execution routes and limits

Python only: no mechanics JSON/CLI or Studio forms. Mechanics is linear and small-strain; heat-to-mechanics is one-way, with no mechanical feedback to heat. The steady coupled workflow does not inherit the separate flux/Robin/traction extensions. Transient snapshots are quasistatic, not structural dynamics.

## Python contracts and formulations

- [Two-dimensional small-strain elasticity](../packages/galerkin/elasticity2d.md)
- [Cartesian boundary traction for 2D elasticity](../packages/galerkin/elasticity_traction.md)
- [Prescribed-temperature thermoelasticity (2D mechanical stage)](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
- [Prescribed-temperature thermoelasticity with total mechanical traction](../packages/galerkin/thermoelastic_traction.md)
- [Explicit steady heat → thermoelastic mechanics](../packages/galerkin/thermal_mechanical_workflow.md)
- [Transient heat to quasistatic mechanics](../packages/galerkin/transient_thermal_mechanical.md)
- [Piecewise-constant materials on named regions](../packages/galerkin/multimaterial.md)


## Validation records

- [Independent acceptance of 2D elasticity](../packages/galerkin/elasticity2d_independent_validation.md)
- [Independent acceptance of boundary traction](../packages/galerkin/elasticity_traction_independent_validation.md)
- [Independent prescribed-temperature mechanical-stage acceptance](../packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md)
- [Independent prescribed-temperature thermoelastic traction acceptance](../packages/galerkin/thermoelastic_traction_independent_validation.md)
- [Independent steady heat → mechanical workflow acceptance](../packages/galerkin/thermal_mechanical_independent_validation.md)
- [Public-reference benchmarks: bimetal strip and NAFEMS T4](../packages/galerkin/public_benchmarks.md)


[Build a model](../modeling/index.md) · [Results and trust](../results/index.md) · [All physics](index.md)
