# Changelog

All seven OpenPhysics distributions (`galerkin`, `galerkin-refsol`, `meshine`,
`gmshio`, `physmat`, `simcase` and the `openphysics` meta distribution) release
together under one version number. This file records what each release changes.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
[한국어](docs/locales/ko/pages/changelog.md)

## Stability in 0.x

0.x releases are alphas.

- The Python API of every package may change in any minor release (0.1 to 0.2).
  Patch releases (0.1.x) fix bugs and are not meant to change the API.
- The JSON model document format `"openphysics": "0.2"` is a contract: a document
  that is valid in this format keeps validating and keeps its meaning. A change
  that would break that gets a new format version.
- Saved result format and field layout identifiers, such as
  `thermal.steady2d-result-v1` or `cavity3d-edge-v1`, are contracts: a file
  carrying an identifier keeps that layout. A changed layout gets a new identifier.

What each package implements, and its limits, is in the
[overview](docs/overview.md).

## [Unreleased]

- Add the explicit `galerkin.electric` steady 2D conduction API with region
  conductivity, outward current boundaries, componentwise Neumann gauges and
  elementwise Joule heating for same-mesh thermal consumers.

The first release of the six implementation packages and the `openphysics` meta
distribution on PyPI, planned as 0.1.0.

### Changed

- `openphysics` is a meta distribution: it has no code and requires the six
  implementation packages. Its extras `studio`, `export` and `rii` install
  `simcase[studio]`, `simcase[export]` and `physmat[rii]`. No extra installs Gmsh.
  The earlier `openphysics` 0.0.1 was an empty name reservation, like the 0.0.1
  of the other six names.
- Every package requires Python 3.12 or later. The minimum numpy, scipy, shapely
  and matplotlib are now 1.26, 1.11.2, 2.0.2 and 3.8, their first releases with
  Python 3.12 wheels.
- Requirements between the packages are limited to the 0.1 series
  (`>=0.1.0,<0.2`).
