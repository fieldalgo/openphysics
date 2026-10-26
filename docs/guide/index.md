# User guide

**English** | [한국어](../locales/ko/pages/guide/index.md)

[Documentation home](../README.md)

Choose the calculation you want to perform. Each link leads to the maintained usage
and result contract. Python features do not automatically imply JSON/CLI or Studio support.

## First Python calculations

- [First heat calculation: a conducting slab](../packages/galerkin/thermal_tutorial.md)
- [First Joule calculation: electric power becomes heat](../packages/galerkin/joule_tutorial.md)
- [First thermal expansion calculation: heat then mechanics](../packages/galerkin/thermoelastic_tutorial.md)

- [Transient heat tutorial: where the input energy goes](../packages/galerkin/transient_tutorial.md)
- [Temperature-dependent Joule tutorial: feedback and convergence](../packages/galerkin/temperature_joule_tutorial.md)

## Choose an execution interface

First choose the [model](../modeling/index.md) and [physical problem](../physics/index.md).

| Route | Use it for |
|---|---|
| Python | Low-level engines, mechanics, explicit coupling and model-specific numerical control |
| JSON/CLI | Validation, execution and saving of models defined by simcase |
| Studio | Browser editing and visualization of supported optical/rectangular heat models |

After running, follow [results, export and trust](../results/index.md).

## Model documents and results

- [simcase — the model document and its headless runner](../packages/simcase/overview.md)
- [Tutorial: analyse your own waveguide](../packages/simcase/waveguide_tutorial.md)

## Waveguides and cavities

- [Absorbing waveguide modes](../packages/simcase/lossy_modes.md)
- [PML, leaky and constant-radius modes](../packages/simcase/pml_modes.md)
- [Opt-in subspace tracking for vector wavelength sweeps](../packages/simcase/vector_subspace_tracking.md)
- [Rectangular cavity document and results](../packages/simcase/cavity3d.md)

## Heat and material regions

- [Headless steady heat in a rectangle](../packages/simcase/thermal_steady2d.md)
- [Steady outward-flux and convection documents](../packages/simcase/thermal_steady_boundary2d.md)
- [Headless transient heat in a rectangle](../packages/simcase/thermal_transient2d.md)
- [Heat documents with material regions](../packages/simcase/thermal_regions2d.md)

## Electric conduction and Joule heating

- [Electric and Joule heating documents](../packages/simcase/electric_joule.md)

## Studio

- [Steady heat in Studio](../packages/simcase/thermal_studio.md)
- [Transient heat in Studio](../packages/simcase/thermal_transient_studio.md)

## Python mechanics and coupled workflows

- [Two-dimensional small-strain elasticity](../packages/galerkin/elasticity2d.md)
- [Cartesian boundary traction for 2D elasticity](../packages/galerkin/elasticity_traction.md)
- [Prescribed-temperature thermoelasticity (2D mechanical stage)](../packages/galerkin/prescribed_temperature_thermoelasticity.md)
- [Prescribed-temperature thermoelasticity with total mechanical traction](../packages/galerkin/thermoelastic_traction.md)
- [Explicit steady heat → thermoelastic mechanics](../packages/galerkin/thermal_mechanical_workflow.md)
- [Transient heat to quasistatic mechanics](../packages/galerkin/transient_thermal_mechanical.md)
- [Steady Joule heating](../packages/galerkin/joule_heating.md)
- [Temperature-dependent steady Joule heating](../packages/galerkin/temperature_joule_heating.md)

## Experimental model workspace

[Workspace guidance](../packages/simcase/workspace.md) covers the bounded optical
runner and input/session saving. The heated-waveguide screen is a setup preview,
not a coupled solve. Its file formats and capabilities differ from the original
optical and thermal Studio editors.

## Apply this to your model

- [Model a two-material wall, run it and inspect the heat flow](../packages/simcase/layered_wall_tutorial.md)
- [Choose units, signs and boundary conditions](../modeling/boundaries-units.md)
- [Read saved fields and export them to ParaView](../results/saved-results.md)
- [Check convergence of your calculation](../validation/convergence.md)
- [Diagnose model, solver and result errors](troubleshooting.md)

- [Choose Python, JSON/CLI or Studio](execution-paths.md)

- [Verify a waveguide against the slab solution](../validation/slab-tutorial.md)
- [Interpret thermal expansion, stress and reactions](../results/thermoelastic-controls.md)
- [Keep a reproducible calculation record](../results/run-records.md)
