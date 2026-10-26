# Electric conduction and Joule heating

**English** | [한국어](../locales/ko/pages/physics/electric-joule.md)

[Documentation home](../README.md)

Distinguish a DC electric solve, one-way electric-to-heat transfer and temperature-dependent conductivity iteration. They have different inputs and convergence requirements; the latter is not a general coupled multiphysics framework.

## Execution routes and limits

The Python electric API supports region conductivity and explicit Neumann gauges. JSON/CLI is restricted to homogeneous rectangles and the documented conductivity models; it has no shapes, sweeps, plots or Studio execution. Temperature-dependent JSON uses the declared linear-resistivity model, not arbitrary Python callbacks.

## Model documents and workflows

- [Electric and Joule heating documents](../packages/simcase/electric_joule.md)


## Python contracts and formulations

- [Steady 2D electric conduction](../packages/galerkin/electric_steady2d.md)
- [Steady Joule heating](../packages/galerkin/joule_heating.md)
- [Temperature-dependent steady Joule heating](../packages/galerkin/temperature_joule_heating.md)


## Validation evidence

The three Python contracts and the JSON/CLI contract above record independent references, conservation checks and iteration acceptance conditions. Use their original thresholds.

[Build a model](../modeling/index.md) · [Results and trust](../results/index.md) · [All physics](index.md)
