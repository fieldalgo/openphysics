# Results, export and trust

**English** | [한국어](../locales/ko/pages/results/index.md)

[Documentation home](../README.md)

A completed solve and a trustworthy physical result are different claims. Preserve
the model/settings and check units, conservation, independent references and convergence.

1. **Run record:** preserve the input model, settings and summary in the documented save format.
2. **Fields and coordinates:** check complex mode coefficients, physical/PML coordinates and stored time indices.
3. **Physical checks:** inspect the contract’s conservation tests or independent reference comparisons.
4. **Convergence:** vary model-specific axes such as mesh, time step and PML settings independently.
5. **Evidence scope:** distinguish historical measurements from CI on the current commit.

## Saving and export

JSON/CLI saved files and export support depend on the model. Installing
`simcase[export]` does not make every result convertible to VTU/PVD. Read the
simcase overview and the specific physics contract for the supported scope.

## Result formats and interpretation

- [simcase — the model document and its headless runner](../packages/simcase/overview.md)
- [Electric and Joule heating documents](../packages/simcase/electric_joule.md)
- [Vector eigenspace reliability](../packages/galerkin/eigenspace_reliability.md)
- [Modal complex coordinates](../packages/galerkin/modal_coordinates.md)
- [Headless transient heat in a rectangle](../packages/simcase/thermal_transient2d.md)


## Independent evidence and reproducibility

- [Validation and benchmarks](../validation/index.md)
- [Stored reference values](../stored-reference-values.md)
- [Reference-tool comparisons](../reference-comparisons.md)
- [Development and validation](../development.md)
