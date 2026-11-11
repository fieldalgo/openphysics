# Electric conduction and Joule heating

**English** | [한국어](../locales/ko/pages/physics/electric-joule.md)

[Documentation home](../README.md)

Distinguish a DC electric solve, one-way electric-to-heat transfer and temperature-dependent conductivity iteration. They have different inputs and convergence requirements; the latter is not a general coupled multiphysics framework.

## First Python calculations

- [First Joule calculation: electric power becomes heat](../packages/galerkin/joule_tutorial.md)

- [Temperature-dependent Joule tutorial: feedback and convergence](../packages/galerkin/temperature_joule_tutorial.md)

## Execution routes and limits

The Python electric API supports region conductivity and explicit Neumann gauges. JSON/CLI documents are [format 0.3](../packages/simcase/document_format.md): every value carries its unit, and `inward_current_density` and `inward_heat_flux` are positive entering the body. They take homogeneous rectangles for `electric.steady2d`, `joule.steady2d` and `joule.temperature2d` and material regions for the first two; they have no sweeps, plots or Studio execution. Temperature-dependent JSON gives `electrical_conductivity` as the declared `linear_resistivity` model, not arbitrary Python callbacks, and always uses the Picard loop; Newton's method (`method="newton"`) is Python only.

## Model documents and workflows

- [Electric and Joule heating documents](../packages/simcase/electric_joule.md)


## Python contracts and formulations

- [Steady 2D electric conduction](../packages/galerkin/electric_steady2d.md)
- [Steady Joule heating](../packages/galerkin/joule_heating.md)
- [Temperature-dependent steady Joule heating](../packages/galerkin/temperature_joule_heating.md)
- [PCB power planes: DC voltage drop with sipi.PowerPlane](../packages/sipi/overview.md#power-planes-dc-voltage-drop-ir-drop), built on the steady 2D conduction above


## Validation evidence

The three Python contracts and the JSON/CLI contract above record independent references, conservation checks and iteration acceptance conditions. Use their original thresholds.

[Build a model](../modeling/index.md) · [Results and trust](../results/index.md) · [All physics](index.md)
