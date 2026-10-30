# Validation and benchmarks

**English** | [한국어](../locales/ko/pages/validation/index.md)

[Documentation home](../README.md)

Validation records describe independent references, fixed thresholds and measured
scope. Check the exact commit’s CI logs and artifacts for its pass status. Historical
records and plans do not establish a current pass; resource observations are not performance guarantees.

## galerkin acceptance and references

- [Independent acceptance of 2D elasticity](../packages/galerkin/elasticity2d_independent_validation.md)
- [Independent acceptance of boundary traction](../packages/galerkin/elasticity_traction_independent_validation.md)
- [Independent prescribed-temperature mechanical-stage acceptance](../packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md)
- [Public-reference benchmarks: bimetal strip and NAFEMS T4](../packages/galerkin/public_benchmarks.md)
- [Independent outward-flux and Robin thermal acceptance](../packages/galerkin/thermal_flux_robin_independent_validation.md)
- [Independent acceptance: steady heat conduction](../packages/galerkin/thermal_independent_validation.md)
- [Independent steady heat → mechanical workflow acceptance](../packages/galerkin/thermal_mechanical_independent_validation.md)
- [Independent prescribed-temperature thermoelastic traction acceptance](../packages/galerkin/thermoelastic_traction_independent_validation.md)
- [Transient heat independent acceptance](../packages/galerkin/transient_heat_independent_validation.md)
- [Transient heat validation contract](../packages/galerkin/transient_heat_validation.md)

## simcase acceptance and references

- [Independent steady boundary headless acceptance](../packages/simcase/steady_boundary_independent_validation.md)
- [Independent steady thermal Studio validation](../packages/simcase/studio_thermal_independent_validation.md)
- [Transient Studio independent acceptance](../packages/simcase/studio_transient_thermal_independent_validation.md)
- [Independent headless thermal document validation](../packages/simcase/thermal_simcase_independent_validation.md)

## Evidence included in newer contracts

- [Steady 2D electric conduction](../packages/galerkin/electric_steady2d.md)
- [Steady Joule heating](../packages/galerkin/joule_heating.md)
- [Temperature-dependent steady Joule heating](../packages/galerkin/temperature_joule_heating.md)
- [Modal complex coordinates](../packages/galerkin/modal_coordinates.md)
- [Absorbing waveguide modes](../packages/simcase/lossy_modes.md)
- [PML, leaky and constant-radius modes](../packages/simcase/pml_modes.md)

## Mesh generation plans

- [Pre-registered validation plan: 3D tetrahedral meshing](../packages/meshine/validation3d.md)

## Historical cavity and milestone records

- [Independent validation plan: vacuum PEC rectangular cavities](../packages/galerkin/cavity3d_validation.md)
- [Independent validation of the alternating Kuhn cavity mesh](../packages/galerkin/cavity3d_alternating_validation.md)
- [Rectangular PEC 111 doublet: signed-mean convergence diagnosis](../packages/galerkin/cavity3d_convergence_diagnosis.md)
- [galerkin milestone validation (2026-09-05)](../packages/galerkin/milestone_validation.md)

## External references and stored values

- [Reference-tool comparisons](../reference-comparisons.md)
- [Stored reference values](../stored-reference-values.md)

## Benchmarks and resource observations

- [Measuring vector mode performance](../benchmark_vector.md)
- [Measuring 3D PEC cavity time and memory](../benchmark_cavity.md)
- [Transient Studio resource observer](../transient_resource_probe.md)
- [Region Studio resource observation](../region_resource_probe.md)

## Apply this to your model

- [Check convergence of your calculation](convergence.md)

- [Verify a waveguide against the slab solution](slab-tutorial.md)

- [Line-network analytical and independent-tool checks](../packages/sipi/network_validation.md)
- [Tapered conductors and planar coating: contract and validation](../packages/sipi/manufacturing_sections.md)
- [Dispersive dielectrics: analytical, independent-tool and mesh checks](../packages/sipi/dielectrics.md#validation-and-reproduction)
