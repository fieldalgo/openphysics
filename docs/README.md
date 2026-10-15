# OpenPhysics documentation

**English** | [한국어](locales/ko/pages/index.md)

[Suite overview and installation](../README.md) · [한국어 overview](../README.ko.md)

English source documents remain at their existing package paths. Complete Korean counterparts use each package's `docs/locales/ko/pages/<same-name>.md`; package overviews use `README.ko.md`. Code identifiers, equations, commands and recorded outputs retain their meaning in both languages. A translation does not establish a new numerical result. Pending entries below are not advertised as completed translations.

## Current implementation contracts and evidence

| Topic | English source | Korean status |
|---|---|---|
| 3D PEC cavity engine | [API, units and convergence](../packages/galerkin/docs/cavity_solver.md) | In preparation |
| Cavity document and CLI | [Input and saved fields](../packages/simcase/docs/cavity3d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/cavity3d.md) |
| Complex vector eigenspaces | [Preservation and limits](../packages/galerkin/docs/eigenspace_reliability.md) | In preparation |
| Static elasticity | [Plane models and constraints](../packages/galerkin/docs/elasticity2d.md) | In preparation |
| Elasticity acceptance | [Independent continuum checks](../packages/galerkin/docs/elasticity2d_independent_validation.md) | In preparation |
| Boundary traction | [Loads and normals](../packages/galerkin/docs/elasticity_traction.md) | In preparation |
| Traction acceptance | [Independent forces, work and convergence](../packages/galerkin/docs/elasticity_traction_independent_validation.md) | In preparation |
| Steady conduction | [Kelvin, heat flux and boundary signs](../packages/galerkin/docs/thermal_steady2d.md) | In preparation |
| Conduction acceptance | [Independent source/wheel evidence](../packages/galerkin/docs/thermal_independent_validation.md) | In preparation |
| Prescribed-temperature mechanics | [Snapshots, 3D reduction and energy](../packages/galerkin/docs/prescribed_temperature_thermoelasticity.md) | In preparation |
| Mechanical-stage acceptance | [Independent original 3D law](../packages/galerkin/docs/prescribed_temperature_thermoelasticity_independent_validation.md) | In preparation |

Package READMEs describe their own dependencies, public entry points and scope. The suite contains six implementations and one name-reservation distribution; installing the `openphysics` reservation does not install the suite. [CI documentation](../ci/README.md) distinguishes declared metadata from tested environments and source acceptance from installed consumers.

Headless thermal documents and prescribed-flux/Robin boundaries are separate development candidates until reviewed and integrated. Their new manuals and acceptance reports will appear in both languages when the corresponding implementation is accepted. Do not infer feature support from a planned translation.

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

## Headless thermal review candidate / 헤드리스 열전도 검토 후보

| English | 한국어 | Scope / 범위 |
|---|---|---|
| [Contract](../packages/simcase/docs/thermal_steady2d.md) | [한국어](../packages/simcase/docs/locales/ko/pages/thermal_steady2d.md) | Headless only; Windows save/independent acceptance remain separate gates / 헤드리스 전용·Windows 저장 및 독립수용은 별도 gate |
