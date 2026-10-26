# Physics problems

**English** | [한국어](../locales/ko/pages/physics/index.md)

[Documentation home](../README.md)

Choose the physical problem before the execution interface. Several OpenPhysics
packages participate in a calculation, but not every physics combination or interface is supported.

| Physics | Reading route |
|---|---|
| [Electromagnetics](electromagnetics.md) | Start with a waveguide cross-section, then choose scalar/vector modes, a wavelength sweep or a rectangular cavity. Electrostatics and scattering use the Python engine. PML/leaky modes are candidates requiring independent mesh and PML checks, not certified physical poles. |
| [Heat conduction](heat.md) | Choose steady or transient heat, then rectangular or material-region geometry. Boundary signs, Kelvin temperatures, time samples and per-depth quantities are part of the model contract. |
| [Electric conduction and Joule heating](electric-joule.md) | Distinguish a DC electric solve, one-way electric-to-heat transfer and temperature-dependent conductivity iteration. They have different inputs and convergence requirements; the latter is not a general coupled multiphysics framework. |
| [Mechanics and thermal coupling](mechanics.md) | Choose plane stress or plane strain and define displacement constraints and loads. Prescribed-temperature mechanics, steady heat-to-mechanics and selected transient-heat snapshots are distinct explicit workflows on the same mesh. |


## Distinguish coupling direction first

1. **Electric → heat:** transfer the electric result’s Joule source into heat on the same mesh.
2. **Temperature-dependent Joule:** iterate temperature-dependent conductivity for the bounded steady electric/heat problem.
3. **Heat → mechanics:** call mechanics separately with steady or stored transient temperatures; no feedback to heat.

Each route links its exact inputs and rejection conditions. The suite-wide availability table is in the [overview](../overview.md).
