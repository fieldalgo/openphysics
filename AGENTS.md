# Working on OpenPhysics

Read [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and release policy,
the [package overview](README.md) for setup and architecture, and the
[development guide](docs/development.md) for dependencies, commands and CI scope.
The [documentation home](docs/README.md) links reader routes and implementation
contracts. Follow the [documentation map](docs/development/documentation.md) when
adding or organizing pages.

- The seven implementation packages live under `packages/` and retain independent
  distribution metadata and licenses; their tests are in `tests/<import name>/`,
  examples in `examples/<name>/` and docs in `docs/packages/<name>/`.
  Keep integrations behind their package API.
- Run from the repository root: package directory names can shadow installed imports.
- Validate new physics against independent analytical references and mesh convergence.
  Preserve numerical thresholds and document limitations.
- Keep code and examples in English; update English and Korean docs together.

From the repository root in a configured environment:

```sh
python -m pytest -q
```

Use the development guide for required data, optional tools and isolated wheel checks.
Follow CONTRIBUTING for PRs; a subset pass does not replace required CI.
