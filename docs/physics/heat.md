# Heat conduction

**English** | [한국어](../locales/ko/pages/physics/heat.md)

[Documentation home](../README.md)

Choose steady or transient heat, then rectangular or material-region geometry. Boundary signs, Kelvin temperatures, time samples and per-depth quantities are part of the model contract.

## First Python calculations

- [First heat calculation: a conducting slab](../packages/galerkin/thermal_tutorial.md)

- [Transient heat tutorial: where the input energy goes](../packages/galerkin/transient_tutorial.md)

## Execution routes and limits

Python and JSON/CLI support rectangular and region models. Studio supports rectangular heat only. Transient heat has no flux/Robin input or restart. For a subsequent mechanical solve, use the explicit coupling route below.

## Model documents and workflows

- [Headless steady heat in a rectangle](../packages/simcase/thermal_steady2d.md)
- [Steady outward-flux and convection documents](../packages/simcase/thermal_steady_boundary2d.md)
- [Headless transient heat in a rectangle](../packages/simcase/thermal_transient2d.md)
- [Heat documents with material regions](../packages/simcase/thermal_regions2d.md)
- [Steady heat in Studio](../packages/simcase/thermal_studio.md)
- [Transient heat in Studio](../packages/simcase/thermal_transient_studio.md)


## Python contracts and formulations

- [Steady two-dimensional heat conduction](../packages/galerkin/thermal_steady2d.md)
- [Steady 2D outward heat flux and convection](../packages/galerkin/thermal_flux_robin.md)
- [Transient heat on a fixed P1 mesh](../packages/galerkin/transient_heat.md)
- [Piecewise-constant materials on named regions](../packages/galerkin/multimaterial.md)


## Validation records

- [Independent acceptance: steady heat conduction](../packages/galerkin/thermal_independent_validation.md)
- [Independent outward-flux and Robin thermal acceptance](../packages/galerkin/thermal_flux_robin_independent_validation.md)
- [Transient heat validation contract](../packages/galerkin/transient_heat_validation.md)
- [Transient heat independent acceptance](../packages/galerkin/transient_heat_independent_validation.md)
- [Independent headless thermal document validation](../packages/simcase/thermal_simcase_independent_validation.md)
- [Independent steady boundary headless acceptance](../packages/simcase/steady_boundary_independent_validation.md)
- [Independent steady thermal Studio validation](../packages/simcase/studio_thermal_independent_validation.md)
- [Transient Studio independent acceptance](../packages/simcase/studio_transient_thermal_independent_validation.md)


[Build a model](../modeling/index.md) · [Results and trust](../results/index.md) · [All physics](index.md)

[Heat-to-mechanics coupling](mechanics.md)

## Apply this to your model

- [Model a two-material wall, run it and inspect the heat flow](../packages/simcase/layered_wall_tutorial.md)
- [Choose units, signs and boundary conditions](../modeling/boundaries-units.md)
