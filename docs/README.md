# OpenPhysics documentation

**English** | [한국어](locales/ko/pages/index.md)

New users should start with the [overview](overview.md): what OpenPhysics
solves, installation, a first example and current limits. Contributors should
read the [development guide](development.md) (environment, checks, CI and the
required `tests` check) and the [contributing guide](contributing.md) (branches,
review and releases).

English is the repository default. READMEs and contribution/security entry
points are English. Bilingual documentation lives under `docs/` directories:
English pages at `docs/<name>.md` and Korean counterparts at
`docs/locales/ko/pages/<name>.md`, including package overviews. Code
identifiers, equations, commands and recorded outputs keep their meaning in both
languages; a translation does not establish a new numerical result.

## Getting started

| Page | English | 한국어 |
|---|---|---|
| Suite overview and installation | [Overview](overview.md) | [한국어](locales/ko/pages/overview.md) |
| Architecture and package map | [Architecture](architecture.md) | [한국어](locales/ko/pages/architecture.md) |
| Development and validation | [Development guide](development.md) | [한국어](locales/ko/pages/development.md) |
| Contributing | [Contributing](contributing.md) | [한국어](locales/ko/pages/contributing.md) |
| Security | [Security](security.md) | [한국어](locales/ko/pages/security.md) |
| Bundled images, fixtures and data | [Asset provenance](assets.md) | [한국어](locales/ko/pages/assets.md) |
| Third-party software, data and licenses | [Third-party list](third-party.md) | [한국어](locales/ko/pages/third-party.md) |
| Reference-tool comparisons | [Comparisons](reference-comparisons.md) | [한국어](locales/ko/pages/reference-comparisons.md) |

## Current implementation contracts and evidence

Each contract defines inputs, outputs, units and limits; each validation report
records its independent references, fixed thresholds and measured scope. For the
results of a specific commit, inspect that commit's CI run and artifacts.

| Topic | English source | Korean status |
|---|---|---|
| Transient heat to quasistatic mechanics | [Stored-index API and independent gates](../packages/galerkin/docs/transient_thermal_mechanical.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/transient_thermal_mechanical.md) |
| 3D PEC cavity engine | [API, units and convergence](../packages/galerkin/docs/cavity_solver.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/cavity_solver.md) |
| Lossy material cavity | [Complex resonances, Q, wall loss and references](../packages/galerkin/docs/material_cavity.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/material_cavity.md) |
| Cavity document and CLI | [Input and saved fields](../packages/simcase/docs/cavity3d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/cavity3d.md) |
| Vector subspace tracking | [Opt-in cluster sweeps](../packages/simcase/docs/vector_subspace_tracking.md) | [한국어](../packages/simcase/docs/locales/ko/pages/vector_subspace_tracking.md) |
| Complex vector eigenspaces | [Preservation and limits](../packages/galerkin/docs/eigenspace_reliability.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/eigenspace_reliability.md) |
| Static elasticity | [Plane models and constraints](../packages/galerkin/docs/elasticity2d.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity2d.md) |
| Elasticity acceptance | [Independent continuum checks](../packages/galerkin/docs/elasticity2d_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity2d_independent_validation.md) |
| Boundary traction | [Loads and normals](../packages/galerkin/docs/elasticity_traction.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity_traction.md) |
| Traction acceptance | [Independent forces, work and convergence](../packages/galerkin/docs/elasticity_traction_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/elasticity_traction_independent_validation.md) |
| Steady conduction | [Kelvin, heat flux and boundary signs](../packages/galerkin/docs/thermal_steady2d.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_steady2d.md) |
| Conduction acceptance | [Independent source/wheel evidence](../packages/galerkin/docs/thermal_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_independent_validation.md) |
| Region materials | [Per-region heat, elastic and thermoelastic materials; layered references](../packages/galerkin/docs/multimaterial.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/multimaterial.md) |
| Prescribed-temperature mechanics | [Snapshots, 3D reduction and energy](../packages/galerkin/docs/prescribed_temperature_thermoelasticity.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity.md) |
| Mechanical-stage acceptance | [Independent original 3D law](../packages/galerkin/docs/prescribed_temperature_thermoelasticity_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/prescribed_temperature_thermoelasticity_independent_validation.md) |
| Prescribed flux and Robin boundaries | [Outward flux and convection](../packages/galerkin/docs/thermal_flux_robin.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md) |
| Flux/Robin acceptance | [Independent boundary checks](../packages/galerkin/docs/thermal_flux_robin_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin_independent_validation.md) |
| Steady heat document | [Headless JSON/API/CLI](../packages/simcase/docs/thermal_steady2d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md) |
| Thermal document acceptance | [Independent document checks](../packages/simcase/docs/thermal_simcase_independent_validation.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_simcase_independent_validation.md) |
| Steady boundary document | [Side-constant flux/convection, v1/v2 fields](../packages/simcase/docs/thermal_steady_boundary2d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_steady_boundary2d.md) |
| Steady boundary acceptance | [Analytic, element and convergence gates](../packages/simcase/docs/steady_boundary_independent_validation.md) | [한국어](../packages/simcase/docs/locales/ko/pages/steady_boundary_independent_validation.md) |
| Steady heat Studio | [Dedicated view, errors and resource policy](../packages/simcase/docs/thermal_studio.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_studio.md) |
| Steady Studio acceptance | [Independent Studio checks](../packages/simcase/docs/studio_thermal_independent_validation.md) | [한국어](../packages/simcase/docs/locales/ko/pages/studio_thermal_independent_validation.md) |
| Transient heat engine | [Backward Euler, Dirichlet and insulation](../packages/galerkin/docs/transient_heat.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/transient_heat.md) |
| Transient heat validation | [Temporal and spatial gates](../packages/galerkin/docs/transient_heat_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/transient_heat_validation.md) |
| Transient heat acceptance | [Independent references](../packages/galerkin/docs/transient_heat_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/transient_heat_independent_validation.md) |
| Transient heat document | [Input, time axes and saved histories](../packages/simcase/docs/thermal_transient2d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_transient2d.md) |
| Transient heat Studio | [Time index, field and history views](../packages/simcase/docs/thermal_transient_studio.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_transient_studio.md) |
| Transient Studio acceptance | [Independent Studio checks](../packages/simcase/docs/studio_transient_thermal_independent_validation.md) | [한국어](../packages/simcase/docs/locales/ko/pages/studio_transient_thermal_independent_validation.md) |
| Steady heat-to-mechanics workflow | [Same-mesh one-way workflow](../packages/galerkin/docs/thermal_mechanical_workflow.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_workflow.md) |
| Workflow acceptance | [Independent workflow checks](../packages/galerkin/docs/thermal_mechanical_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_mechanical_independent_validation.md) |
| Prescribed-temperature traction | [Total traction with thermal strain](../packages/galerkin/docs/thermoelastic_traction.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction.md) |
| Thermoelastic traction acceptance | [Independent loads and energy](../packages/galerkin/docs/thermoelastic_traction_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction_independent_validation.md) |

## Benchmarks

| English | 한국어 |
|---|---|
| [Vector waveguide benchmark](benchmark_vector.md) | [한국어](locales/ko/pages/benchmark_vector.md) |
| [Cavity benchmark](benchmark_cavity.md) | [한국어](locales/ko/pages/benchmark_cavity.md) |

## Package overviews

Package READMEs describe their own dependencies, public entry points and scope.
The suite contains six implementations and one name-reservation distribution;
installing the `openphysics` reservation does not install the suite.

| Package | English | 한국어 |
|---|---|---|
| galerkin | [English](../packages/galerkin/docs/overview.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/overview.md) |
| galerkin-refsol | [English](../packages/galerkin-refsol/docs/overview.md) | [한국어](../packages/galerkin-refsol/docs/locales/ko/pages/overview.md) |
| meshine | [English](../packages/meshine/docs/overview.md) | [한국어](../packages/meshine/docs/locales/ko/pages/overview.md) |
| gmshio | [English](../packages/gmshio/docs/overview.md) | [한국어](../packages/gmshio/docs/locales/ko/pages/overview.md) |
| physmat | [English](../packages/physmat/docs/overview.md) | [한국어](../packages/physmat/docs/locales/ko/pages/overview.md) |
| simcase | [English](../packages/simcase/docs/overview.md) | [한국어](../packages/simcase/docs/locales/ko/pages/overview.md) |
| openphysics | [English](../packages/openphysics/docs/overview.md) | [한국어](../packages/openphysics/docs/locales/ko/pages/overview.md) |
