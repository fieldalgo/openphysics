# Changelog

All eight OpenPhysics distributions (`galerkin`, `galerkin-refsol`, `meshine`,
`gmshio`, `physmat`, `simcase`, `sipi` and the `openphysics` meta distribution) release
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

- Add `sipi`, a signal- and power-integrity package: quasi-static (quasi-TEM) PCB cross-sections with layered dielectrics and rectangular traces, giving C, L and dielectric-loss G matrices, single-line impedance and effective permittivity, and coupled-pair even/odd modes. Validated against exact parallel-plate, coaxial and Cohn stripline solutions and Hammerstad–Jensen microstrip; conductor loss is not included. Installed with `openphysics[sipi]`; [documentation](docs/packages/sipi/overview.md).

- Add an experimental model workspace at `/workspace`, with fixed optical runs, editable model history, session files and a versioned capability contract. Existing optical and heat editors remain available.

- Add headless rectangle electric and constant/temperature-dependent Joule JSON/CLI documents, SI result snapshots and failed-iteration evidence; reuse the existing solvers.

- Scalar/full-vector modal PML and constant-radius bends, with complex candidate diagnostics, physical-window tracking, total attenuation, Studio controls and independent slab/cylindrical validation.


- Add temperature-dependent 2D steady Joule heating with bounded material models,
  relaxed Picard iteration, failure histories and independent reference tests.

- Add public-reference benchmarks against exact references: the Timoshenko
  (1925) bimetal strip (`refsol.bimetal`) and NAFEMS T4 convective heat transfer
  (`refsol.thermal_convection`, with the published 18.3 °C target), with mesh
  convergence gates, a figure script and the validation page
  `docs/packages/galerkin/public_benchmarks.md`. No engine code changed.

- Add the explicit `galerkin.electric` steady 2D conduction API with region
  conductivity, outward current boundaries, componentwise Neumann gauges and
  elementwise Joule heating for same-mesh thermal consumers.

The first release of the six implementation packages and the `openphysics` meta
distribution on PyPI, planned as 0.1.0.

### Added

- Passive complex scalar/full-vector waveguide modes, complex resolved sweeps, dB/cm attenuation, and Studio/JSON/NPZ output; [signs and limits](docs/packages/simcase/lossy_modes.md).

- Add explicit same-mesh steady electric-to-heat coupling and mesh-bound
  element heat sources, with analytical and independent reference validation.

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
