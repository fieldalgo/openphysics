# OpenPhysics documentation

**English** | [한국어](locales/ko/pages/index.md)

New users should start with the [overview](overview.md): what OpenPhysics
solves, installation, a first example and current limits. Contributors should
read the [development guide](development.md) (environment, repository layout,
checks, CI and the required `tests` check) and the
[contributing guide](contributing.md) (branches, review and releases).

English is the repository default. READMEs and contribution/security entry
points are English. Bilingual documentation lives under `docs/`: English pages
at `docs/<name>.md` and Korean counterparts at `docs/locales/ko/pages/<name>.md`.
Each package's pages, including its overview, are in `docs/packages/<package>/`
and `docs/locales/ko/pages/packages/<package>/`. Code
identifiers, equations, commands and recorded outputs keep their meaning in both
languages; a translation does not establish a new numerical result.

## Getting started

| Page | English | 한국어 |
|---|---|---|
| Suite overview and installation | [Overview](overview.md) | [한국어](locales/ko/pages/overview.md) |
| Tutorial: analyse your own waveguide | [Tutorial](packages/simcase/waveguide_tutorial.md) | [한국어](locales/ko/pages/packages/simcase/waveguide_tutorial.md) |
| Architecture and package map | [Architecture](architecture.md) | [한국어](locales/ko/pages/architecture.md) |
| Development and validation | [Development guide](development.md) | [한국어](locales/ko/pages/development.md) |
| Contributing | [Contributing](contributing.md) | [한국어](locales/ko/pages/contributing.md) |
| Security | [Security](security.md) | [한국어](locales/ko/pages/security.md) |
| Releases and stability | [Changelog](../CHANGELOG.md) | [한국어](locales/ko/pages/changelog.md) |
| Bundled images, fixtures and data | [Asset provenance](assets.md) | [한국어](locales/ko/pages/assets.md) |
| Third-party software, data and licenses | [Third-party list](third-party.md) | [한국어](locales/ko/pages/third-party.md) |
| Reference-tool comparisons | [Comparisons](reference-comparisons.md) | [한국어](locales/ko/pages/reference-comparisons.md) |
| Example gallery (pictures and the script that draws them) | [Gallery](gallery.md) | [한국어](locales/ko/pages/gallery.md) |

## Current implementation contracts and evidence

Each contract defines inputs, outputs, units and limits; each validation report
records its independent references, fixed thresholds and measured scope. For the
results of a specific commit, inspect that commit's CI run and artifacts.

| Topic | English source | Korean status |
|---|---|---|
| Transient heat to quasistatic mechanics | [Stored-index API and independent gates](packages/galerkin/transient_thermal_mechanical.md) | [한국어](locales/ko/pages/packages/galerkin/transient_thermal_mechanical.md) |
| 3D PEC cavity engine | [API, units and convergence](packages/galerkin/cavity_solver.md) | [한국어](locales/ko/pages/packages/galerkin/cavity_solver.md) |
| 3D PEC cavity validation records (historical) | [Plan](packages/galerkin/cavity3d_validation.md), [mesh revalidation](packages/galerkin/cavity3d_alternating_validation.md), [convergence diagnosis](packages/galerkin/cavity3d_convergence_diagnosis.md) | [한국어](locales/ko/pages/packages/galerkin/cavity3d_validation.md) |
| Lossy material cavity | [Complex resonances, Q, wall loss and references](packages/galerkin/material_cavity.md) | [한국어](locales/ko/pages/packages/galerkin/material_cavity.md) |
| Cavity document and CLI | [Input and saved fields](packages/simcase/cavity3d.md) | [한국어](locales/ko/pages/packages/simcase/cavity3d.md) |
| Vector subspace tracking | [Opt-in cluster sweeps](packages/simcase/vector_subspace_tracking.md) | [한국어](locales/ko/pages/packages/simcase/vector_subspace_tracking.md) |
| Complex vector eigenspaces | [Preservation and limits](packages/galerkin/eigenspace_reliability.md) | [한국어](locales/ko/pages/packages/galerkin/eigenspace_reliability.md) |
| Static elasticity | [Plane models and constraints](packages/galerkin/elasticity2d.md) | [한국어](locales/ko/pages/packages/galerkin/elasticity2d.md) |
| Elasticity acceptance | [Independent continuum checks](packages/galerkin/elasticity2d_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/elasticity2d_independent_validation.md) |
| Boundary traction | [Loads and normals](packages/galerkin/elasticity_traction.md) | [한국어](locales/ko/pages/packages/galerkin/elasticity_traction.md) |
| Traction acceptance | [Independent forces, work and convergence](packages/galerkin/elasticity_traction_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/elasticity_traction_independent_validation.md) |
| Steady electric conduction | [API, SI units, Neumann and Joule contract](packages/galerkin/electric_steady2d.md) | [한국어](locales/ko/pages/packages/galerkin/electric_steady2d.md) |
| Steady conduction | [Kelvin, heat flux and boundary signs](packages/galerkin/thermal_steady2d.md) | [한국어](locales/ko/pages/packages/galerkin/thermal_steady2d.md) |
| Conduction acceptance | [Independent source/wheel evidence](packages/galerkin/thermal_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/thermal_independent_validation.md) |
| Steady Joule heating | [Explicit electric to heat workflow](packages/galerkin/joule_heating.md) | [한국어](locales/ko/pages/packages/galerkin/joule_heating.md) |
| Region materials | [Per-region heat, elastic and thermoelastic materials; layered references](packages/galerkin/multimaterial.md) | [한국어](locales/ko/pages/packages/galerkin/multimaterial.md) |
| Public-reference benchmarks | [Timoshenko bimetal strip and NAFEMS T4 against exact references](packages/galerkin/public_benchmarks.md) | [한국어](locales/ko/pages/packages/galerkin/public_benchmarks.md) |
| Prescribed-temperature mechanics | [Snapshots, 3D reduction and energy](packages/galerkin/prescribed_temperature_thermoelasticity.md) | [한국어](locales/ko/pages/packages/galerkin/prescribed_temperature_thermoelasticity.md) |
| Mechanical-stage acceptance | [Independent original 3D law](packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/prescribed_temperature_thermoelasticity_independent_validation.md) |
| Prescribed flux and Robin boundaries | [Outward flux and convection](packages/galerkin/thermal_flux_robin.md) | [한국어](locales/ko/pages/packages/galerkin/thermal_flux_robin.md) |
| Flux/Robin acceptance | [Independent boundary checks](packages/galerkin/thermal_flux_robin_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/thermal_flux_robin_independent_validation.md) |
| Steady heat document | [Headless JSON/API/CLI](packages/simcase/thermal_steady2d.md) | [한국어](locales/ko/pages/packages/simcase/thermal_steady2d.md) |
| Heat region documents | [Steady and transient, materials table and shapes](packages/simcase/thermal_regions2d.md) | [한국어](locales/ko/pages/packages/simcase/thermal_regions2d.md) |
| Thermal document acceptance | [Independent document checks](packages/simcase/thermal_simcase_independent_validation.md) | [한국어](locales/ko/pages/packages/simcase/thermal_simcase_independent_validation.md) |
| Steady boundary document | [Side-constant flux/convection, v1/v2 fields](packages/simcase/thermal_steady_boundary2d.md) | [한국어](locales/ko/pages/packages/simcase/thermal_steady_boundary2d.md) |
| Steady boundary acceptance | [Analytic, element and convergence gates](packages/simcase/steady_boundary_independent_validation.md) | [한국어](locales/ko/pages/packages/simcase/steady_boundary_independent_validation.md) |
| Steady heat Studio | [Dedicated view, errors and resource policy](packages/simcase/thermal_studio.md) | [한국어](locales/ko/pages/packages/simcase/thermal_studio.md) |
| Steady Studio acceptance | [Independent Studio checks](packages/simcase/studio_thermal_independent_validation.md) | [한국어](locales/ko/pages/packages/simcase/studio_thermal_independent_validation.md) |
| Transient heat engine | [Backward Euler, Dirichlet and insulation](packages/galerkin/transient_heat.md) | [한국어](locales/ko/pages/packages/galerkin/transient_heat.md) |
| Transient heat validation | [Temporal and spatial gates](packages/galerkin/transient_heat_validation.md) | [한국어](locales/ko/pages/packages/galerkin/transient_heat_validation.md) |
| Transient heat acceptance | [Independent references](packages/galerkin/transient_heat_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/transient_heat_independent_validation.md) |
| Transient heat document | [Input, time axes and saved histories](packages/simcase/thermal_transient2d.md) | [한국어](locales/ko/pages/packages/simcase/thermal_transient2d.md) |
| Transient heat Studio | [Time index, field and history views](packages/simcase/thermal_transient_studio.md) | [한국어](locales/ko/pages/packages/simcase/thermal_transient_studio.md) |
| Transient Studio acceptance | [Independent Studio checks](packages/simcase/studio_transient_thermal_independent_validation.md) | [한국어](locales/ko/pages/packages/simcase/studio_transient_thermal_independent_validation.md) |
| Steady heat-to-mechanics workflow | [Same-mesh one-way workflow](packages/galerkin/thermal_mechanical_workflow.md) | [한국어](locales/ko/pages/packages/galerkin/thermal_mechanical_workflow.md) |
| Workflow acceptance | [Independent workflow checks](packages/galerkin/thermal_mechanical_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/thermal_mechanical_independent_validation.md) |
| Prescribed-temperature traction | [Total traction with thermal strain](packages/galerkin/thermoelastic_traction.md) | [한국어](locales/ko/pages/packages/galerkin/thermoelastic_traction.md) |
| Thermoelastic traction acceptance | [Independent loads and energy](packages/galerkin/thermoelastic_traction_independent_validation.md) | [한국어](locales/ko/pages/packages/galerkin/thermoelastic_traction_independent_validation.md) |

## Benchmarks and resource observations

| English | 한국어 |
|---|---|
| [Vector waveguide benchmark](benchmark_vector.md) | [한국어](locales/ko/pages/benchmark_vector.md) |
| [Cavity benchmark](benchmark_cavity.md) | [한국어](locales/ko/pages/benchmark_cavity.md) |
| [Transient Studio resource observer](transient_resource_probe.md) | [한국어](locales/ko/pages/transient_resource_probe.md) |

## Package overviews

Package READMEs describe their own dependencies, public entry points and scope.
The suite contains six implementations and the `openphysics` meta distribution,
which from 0.1.0 installs all six. Until 0.1.0 is published, the `openphysics` on
PyPI is the empty 0.0.1 name reservation and installs nothing.

| Package | English | 한국어 |
|---|---|---|
| galerkin | [English](packages/galerkin/overview.md) | [한국어](locales/ko/pages/packages/galerkin/overview.md) |
| galerkin-refsol | [English](packages/galerkin-refsol/overview.md) | [한국어](locales/ko/pages/packages/galerkin-refsol/overview.md) |
| meshine | [English](packages/meshine/overview.md) | [한국어](locales/ko/pages/packages/meshine/overview.md) |
| gmshio | [English](packages/gmshio/overview.md) | [한국어](locales/ko/pages/packages/gmshio/overview.md) |
| physmat | [English](packages/physmat/overview.md) | [한국어](locales/ko/pages/packages/physmat/overview.md) |
| simcase | [English](packages/simcase/overview.md) | [한국어](locales/ko/pages/packages/simcase/overview.md) |
| openphysics | [English](packages/openphysics/overview.md) | [한국어](locales/ko/pages/packages/openphysics/overview.md) |

- [Temperature-dependent Joule heating](packages/galerkin/temperature_joule_heating.md)
