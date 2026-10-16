# OpenPhysics documentation

**English** | [한국어](locales/ko/pages/index.md)

[Suite overview and installation](../README.md) · [한국어 overview](../README.ko.md)

English source documents remain at their existing package paths. Complete Korean counterparts use each package's `docs/locales/ko/pages/<same-name>.md`; package overviews use `README.ko.md`. Code identifiers, equations, commands and recorded outputs retain their meaning in both languages. A translation does not establish a new numerical result. Pending entries below are not advertised as completed translations.

## Current implementation contracts and evidence

| Topic | English source | Korean status |
|---|---|---|
| 3D PEC cavity engine | [API, units and convergence](../packages/galerkin/docs/cavity_solver.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/cavity_solver.md) |
| Cavity document and CLI | [Input and saved fields](../packages/simcase/docs/cavity3d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/cavity3d.md) |
| Complex vector eigenspaces | [Preservation and limits](../packages/galerkin/docs/eigenspace_reliability.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/eigenspace_reliability.md) |
| Static elasticity | [Plane models and constraints](../packages/galerkin/docs/elasticity2d.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity2d.md) |
| Elasticity acceptance | [Independent continuum checks](../packages/galerkin/docs/elasticity2d_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity2d_independent_validation.md) |
| Boundary traction | [Loads and normals](../packages/galerkin/docs/elasticity_traction.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity_traction.md) |
| Traction acceptance | [Independent forces, work and convergence](../packages/galerkin/docs/elasticity_traction_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity_traction_independent_validation.md) |
| Steady conduction | [Kelvin, heat flux and boundary signs](../packages/galerkin/docs/thermal_steady2d.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_steady2d.md) |
| Conduction acceptance | [Independent source/wheel evidence](../packages/galerkin/docs/thermal_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_independent_validation.md) |
| Prescribed-temperature mechanics | [Snapshots, 3D reduction and energy](../packages/galerkin/docs/prescribed_temperature_thermoelasticity.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity.md) |
| Mechanical-stage acceptance | [Independent original 3D law](../packages/galerkin/docs/prescribed_temperature_thermoelasticity_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity_independent_validation.md) |

Package READMEs describe their own dependencies, public entry points and scope. The suite contains six implementations and one name-reservation distribution; installing the `openphysics` reservation does not install the suite. [CI documentation](../ci/README.md) distinguishes declared metadata from tested environments and source acceptance from installed consumers.

This checkout includes headless thermal documents and standalone prescribed-flux/Robin boundaries. The contracts and validation reports below describe their respective implementation and measured scope. Headless JSON still rejects flux/Robin boundaries. See the [validation guide](../ci/README.md) for Work-cloud Linux results, disabled Actions and unresolved Windows verification.

## Package overviews: complete Korean counterparts

| Package | English | 한국어 |
|---|---|---|
| galerkin | [English](../packages/galerkin/README.md) | [한국어](../packages/galerkin/README.ko.md) |
| galerkin-refsol | [English](../packages/galerkin-refsol/README.md) | [한국어](../packages/galerkin-refsol/README.ko.md) |
| meshine | [English](../packages/meshine/README.md) | [한국어](../packages/meshine/README.ko.md) |
| gmshio | [English](../packages/gmshio/README.md) | [한국어](../packages/gmshio/README.ko.md) |
| physmat | [English](../packages/physmat/README.md) | [한국어](../packages/physmat/README.ko.md) |
| simcase | [English](../packages/simcase/README.md) | [한국어](../packages/simcase/README.ko.md) |
| openphysics | [English](../packages/openphysics/README.md) | [한국어](../packages/openphysics/README.ko.md) |

## Headless thermal implementation contract

| English | 한국어 | Scope / 범위 |
|---|---|---|
| [Contract](../packages/simcase/docs/thermal_steady2d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md) | Headless only; consult the contract and independent report for measured scope and ownership limits |

## Implementation contracts and validation reports

| English | 한국어 |
|---|---|
| [thermal_flux_robin](../packages/galerkin/docs/thermal_flux_robin.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md) |
| [thermal_flux_robin_independent_validation](../packages/galerkin/docs/thermal_flux_robin_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin_independent_validation.md) |
| [thermal_simcase_independent_validation](../packages/simcase/docs/thermal_simcase_independent_validation.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_simcase_independent_validation.md) |
| [README](../ci/README.md) | [한국어](../ci/locales/ko/pages/README.md) |
| [benchmark_cavity](../ci/benchmark_cavity.md) | [한국어](../ci/locales/ko/pages/benchmark_cavity.md) |
| [benchmark_vector](../ci/benchmark_vector.md) | [한국어](../ci/locales/ko/pages/benchmark_vector.md) |

These pages describe this checkout. Actions is disabled and two Windows failures remain unresolved; Linux results do not establish Windows acceptance. Standalone Robin boundaries are separate from the headless JSON contract.

## Explicit steady heat-to-mechanics workflow

The Python-only workflow freezes a same-mesh nodal-P1 Kelvin field before the mechanical stage. It is steady and one-way; it adds no JSON/CLI/Studio integration, persistence or transient solve.

| English | 한국어 |
|---|---|
| [thermal_mechanical_workflow](../packages/galerkin/docs/thermal_mechanical_workflow.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_workflow.md) |
| [thermal_mechanical_independent_validation](../packages/galerkin/docs/thermal_mechanical_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_independent_validation.md) |

## Prescribed-temperature total mechanical traction

The Python mechanical API accepts optional global Cartesian total traction `sigma*n` in Pa on a fixed reference mesh with prescribed nodal-P1 Kelvin temperatures. Body and traction loads form the external load; the positive thermal-equivalent load remains separate. The contract retains the original 18 positional result fields and appends two optional load fields. It reports per-depth forces in N/m and physical elastic energy in J/m, including plane-strain out-of-plane stress and support work.

A global Pa callback `-p*normal` is valid on the fixed boundary; no dedicated scalar-pressure, local-frame or follower API is added. This does not add traction to the heat-to-mechanics workflow or JSON/CLI/Studio, and does not run heat conduction or authenticate temperature or boundary-tag provenance.

| English | 한국어 |
|---|---|
| [thermoelastic_traction](../packages/galerkin/docs/thermoelastic_traction.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction.md) |
| [thermoelastic_traction_independent_validation](../packages/galerkin/docs/thermoelastic_traction_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction_independent_validation.md) |

Implementation contracts, independent candidate evidence and combined release validation have different scopes. Linked reports retain their exact candidates and original failures; targeted recovery does not turn an earlier failed whole run into a passing one. A completed combined result requires the corresponding final command exit and complete JUnit evidence. Missing final evidence or a transport interruption establishes neither numerical success nor the interruption's cause. Linux checks do not establish Windows acceptance.

For source snapshot `0bc4419f4cfaf9e1185872d14232f1644639fc72`, Linux cloud validation recorded 1536 source tests passed, 9 subtests passed and 16 skipped, with command exit0. The skips were 14 optional Gmsh cases and 2 local refractiveindex.info database cases. A separate sdist-to-wheel installed run passed 541 cases with no failures or skips. The original distribution helper completed all 16 commands with exit0, including seven sdist-to-wheel builds and strict Twine checks of 14 artifacts. This snapshot was integrated as `da811aec95f6695f6d7b9988a7d3e9055736ff97`. These results are limited to the recorded Linux environment and do not establish Windows/other-OS acceptance or resolve the cause of earlier transport interruptions. Earlier failed and unknown runs remain separate evidence.

## Asset provenance

See [bundled images, fixtures and data](assets.md) for source history and licensing boundaries.
