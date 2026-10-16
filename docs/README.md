# OpenPhysics documentation

**English** | [한국어](locales/ko/pages/index.md)

## Current checkout and evidence

The current CI configuration adds installed-package checks on Linux, macOS and
Windows. Each builds six implementation sdists into wheels and validates isolated
consumer imports, package bytes, bundled assets and selected public API/CLI/save
behavior. The required `tests` aggregate waits for full Linux acceptance and all
three installed platforms; the existing Windows thermal gate also remains required.
This is configured coverage, not a new historical pass claim. See the
[validation guide](../ci/docs/README.md) for scope, commands and exact-run artifacts.

This page describes the implementation in this checkout. Named historical snapshots retain their original results and limitations. For validation of another commit, inspect that commit's CI logs and artifacts.

[Suite overview and installation](overview.md) · [한국어 overview](locales/ko/pages/overview.md)

[Architecture and package map](architecture.md) · [한국어 구조도](locales/ko/pages/architecture.md)

English is the repository default. READMEs and contribution/security entry points are English. Bilingual documentation lives under `docs/` directories: English pages at `docs/<name>.md` and Korean counterparts at `docs/locales/ko/pages/<name>.md`, including package overviews. Code identifiers, equations, commands and recorded outputs retain their meaning in both languages. A translation does not establish a new numerical result.

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

Package READMEs describe their own dependencies, public entry points and scope. The suite contains six implementations and one name-reservation distribution; installing the `openphysics` reservation does not install the suite. [CI documentation](../ci/docs/README.md) distinguishes declared metadata from tested environments and source acceptance from installed consumers.

This checkout includes headless thermal documents and standalone prescribed-flux/Robin boundaries. The contracts and validation reports below describe their respective implementation and measured scope. Steady rectangular JSON accepts side-constant outward flux and convection through the [boundary document contract](../packages/simcase/docs/thermal_steady_boundary2d.md); transient flux/Robin remains unsupported. See the [validation guide](../ci/docs/README.md) for Work-cloud Linux results, enabled Actions and the measured scope of Windows verification.

## Package overviews: complete Korean counterparts

| Package | English | 한국어 |
|---|---|---|
| galerkin | [English](../packages/galerkin/docs/overview.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/overview.md) |
| galerkin-refsol | [English](../packages/galerkin-refsol/docs/overview.md) | [한국어](../packages/galerkin-refsol/docs/locales/ko/pages/overview.md) |
| meshine | [English](../packages/meshine/docs/overview.md) | [한국어](../packages/meshine/docs/locales/ko/pages/overview.md) |
| gmshio | [English](../packages/gmshio/docs/overview.md) | [한국어](../packages/gmshio/docs/locales/ko/pages/overview.md) |
| physmat | [English](../packages/physmat/docs/overview.md) | [한국어](../packages/physmat/docs/locales/ko/pages/overview.md) |
| simcase | [English](../packages/simcase/docs/overview.md) | [한국어](../packages/simcase/docs/locales/ko/pages/overview.md) |
| openphysics | [English](../packages/openphysics/docs/overview.md) | [한국어](../packages/openphysics/docs/locales/ko/pages/overview.md) |

## Headless thermal implementation contract

| English | 한국어 | Scope |
|---|---|---|
| [Contract](../packages/simcase/docs/thermal_steady2d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md) | Headless only; consult the contract and independent report for measured scope and ownership limits |
| [Steady boundary JSON/API/CLI](../packages/simcase/docs/thermal_steady_boundary2d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_steady_boundary2d.md) | Side-constant flux/convection, v1/v2 and saved numeric fields |
| [Steady boundary independent acceptance](../packages/simcase/docs/steady_boundary_independent_validation.md) | [한국어](../packages/simcase/docs/locales/ko/pages/steady_boundary_independent_validation.md) | Analytic/element checks and fixed convergence gates; inspect exact execution evidence |

## Implementation contracts and validation reports

| English | 한국어 |
|---|---|
| [thermal_flux_robin](../packages/galerkin/docs/thermal_flux_robin.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin.md) |
| [thermal_flux_robin_independent_validation](../packages/galerkin/docs/thermal_flux_robin_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermal_flux_robin_independent_validation.md) |
| [thermal_simcase_independent_validation](../packages/simcase/docs/thermal_simcase_independent_validation.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_simcase_independent_validation.md) |
| [README](../ci/docs/README.md) | [한국어](../ci/docs/locales/ko/pages/README.md) |
| [benchmark_cavity](../ci/docs/benchmark_cavity.md) | [한국어](../ci/docs/locales/ko/pages/benchmark_cavity.md) |
| [benchmark_vector](../ci/docs/benchmark_vector.md) | [한국어](../ci/docs/locales/ko/pages/benchmark_vector.md) |

These pages describe this checkout. Actions is enabled. The narrow Windows gate at `636a23a` passed 36 installed and 3 source cases ([run](https://github.com/fieldalgo/openphysics/actions/runs/38858254797)); this is not full Windows regression or macOS acceptance. The older Windows result does not validate the newer steady boundary JSON extension; inspect its exact CI artifacts separately.

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

## Contribution and security guides

| English | 한국어 |
|---|---|
| [Contributing](contributing.md) | [한국어](locales/ko/pages/contributing.md) |
| [Security](security.md) | [한국어](locales/ko/pages/security.md) |

## Transient heat: implementation and acceptance evidence

The explicit `galerkin.transient_heat.solve_transient_heat` function implements fixed P1 triangles, consistent mass and backward Euler with constant isotropic conductivity/heat capacity, time-dependent Dirichlet values and insulation. Finite Kelvin inputs do not certify physical validity or a maximum principle. The engine function itself does not add document dispatch or saving; the separate headless interface is described below. Studio, restart and automatic heat-to-mechanics coupling remain unsupported.

| English | 한국어 |
|---|---|
| [transient_heat](../packages/galerkin/docs/transient_heat.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/transient_heat.md) |
| [transient_heat_validation](../packages/galerkin/docs/transient_heat_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/transient_heat_validation.md) |
| [transient_heat_independent_validation](../packages/galerkin/docs/transient_heat_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/transient_heat_independent_validation.md) |

The historical b2 snapshot's 70 small producer/reference source passes are evidence for that snapshot. This checkout wires usage, producer-validation and independent-validation pages and distribution gates. Assess current full temporal/PDE, independent acceptance, build and installed validation from the exact CI run, exits and artifacts. Fixed gates and implemented checks are distinct from observed success or release approval.

| English | 한국어 |
|---|---|
| [thermoelastic_traction](../packages/galerkin/docs/thermoelastic_traction.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction.md) |
| [thermoelastic_traction_independent_validation](../packages/galerkin/docs/thermoelastic_traction_independent_validation.md) | [한국어](../packages/galerkin/docs/locales/ko/pages/thermoelastic_traction_independent_validation.md) |

## Headless transient heat

The rectangular `thermal.transient2d` document connects fixed-P1, consistent-mass backward-Euler heat to the Python API, CLI and versioned JSON/NPZ histories. It accepts explicit seconds, uniform/affine initial Kelvin and side-constant or requested-time sampled Dirichlet values with insulation elsewhere. Initial/boundary agreement is checked without projection; finite negative K is not clamped. Studio, transient flux/Robin, restart and automatic coupling remain unsupported. Read the [complete input/API/CLI/save contract](../packages/simcase/docs/thermal_transient2d.md) ([한국어](../packages/simcase/docs/locales/ko/pages/thermal_transient2d.md)). Implemented interfaces and packaging rules require exact combined source, installed and CI evidence; the older engine results are not headless acceptance.
