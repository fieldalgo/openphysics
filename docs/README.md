# OpenPhysics documentation

**English** | [한국어](locales/ko/pages/index.md)

OpenPhysics combines finite-element engines, meshing, material properties, a model
runner and independent reference solutions. Read along the calculation lifecycle:
**build a model → choose physics → run → verify results**. Find APIs by package
and formulations/evidence by physical problem.

<a id="getting-started"></a>

## Follow a calculation

| Step | Read |
|---|---|
| 1 | [Install and run a first example](getting-started/index.md) |
| 2 | [Geometry, materials and mesh](modeling/index.md) |
| 3 | [Physical problem and coupling direction](physics/index.md) |
| 4 | [Python, JSON/CLI or Studio execution](guide/index.md) |
| 5 | [Saved fields, export and physical checks](results/index.md) |


## Browse by physics

- [Electromagnetics](physics/electromagnetics.md)
- [Heat conduction](physics/heat.md)
- [Electric conduction and Joule heating](physics/electric-joule.md)
- [Mechanics and thermal coupling](physics/mechanics.md)

Python, JSON/CLI and Studio have different support boundaries. Each physics route
explains available interfaces and limits. Heat-to-mechanics is one-way;
temperature-dependent Joule iteration is a separate, bounded coupling contract.

<a id="current-implementation-contracts-and-evidence"></a>

## APIs, formulations, evidence and development

- <a id="package-overviews"></a>[Package API and document contracts](reference/index.md)
- [Formulations and numerical methods](theory/index.md)
- <a id="benchmarks-and-resource-observations"></a>[Independent validation and benchmarks](validation/index.md)
- [Development, CI and contribution](development/index.md)

[Package architecture](architecture.md) · [Example gallery](gallery.md) · [Documentation and translations](development/documentation.md)

English is canonical with maintained Korean counterparts. Canonical package pages
remain at `packages/<package>/`; each reading route links to the same source.
