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

- `galerkin`: `material_cavity` and `mode_coordinates` assemble through `galerkin.core` kernels instead of the public assembly functions; their matrices and results are unchanged bit for bit.
- Docs: the [architecture](docs/architecture.md#inside-galerkin-core-physics-and-coupling) page describes galerkin's core, physics and coupling layers, what does not differentiate yet, and the steps for adding a physics.
- `galerkin`: `galerkin.core` no longer imports modules above it. Material lookup moved to `galerkin.core.materials` (`galerkin.materials` keeps the same public names), and `core.loads` takes element heat sources as checked values (`ElementSource`) instead of importing `ElementHeatSource`. A test checks the import direction. Results are unchanged.

- `simcase` Studio: the steady and transient heat routes validate and run heat region documents, in a worker thread and within limits on shapes, circles, polygon points, boundary crossings and loop vertices before a run and on nodes and cells in the job. Region results have their own formats, `studio-thermal-steady-regions-v1` and `studio-thermal-transient-regions-v1`; rectangle documents keep their responses. The page shows region results with region colours, boundaries, a legend, a material table and the region under the pointer. [Documentation](docs/packages/simcase/thermal_studio.md#region-documents).

- `simcase`: `region_complexity` reads a raw heat region document before `Document.from_dict` and counts its shapes, circles and polygon points and, when none passes its given maximum, the boundary crossings between shapes, which drive the cost of `from_dict`'s booleans. It never raises on malformed data. [Documentation](docs/packages/simcase/thermal_regions2d.md#mesh-limits-for-callers).

- `simcase`: `run` takes optional `max_input_vertices`, `max_nodes` and `max_triangles` for steady and transient heat region documents, checks them before the solve and refuses with `MeshLimitError`; `check_mesh_limits` returns a document's loop-vertex count without building the domain. Only `max_input_vertices` bounds the work before meshing. The two heat kinds take the limits through the physics registry (`PhysicsKind.accepts_mesh_limits`); with no limit a run is unchanged. [Documentation](docs/packages/simcase/thermal_regions2d.md#mesh-limits-for-callers).

- `meshine`: `generate` raises `MeshSizeLimitError`, a `RuntimeError` subclass, when an insertion would pass `max_points`, and checks the input domain as built against the cap before any refinement work, so an input with more points is refused there instead of being refined or, when it needs no insertion, returned over the cap. Building the domain, O(V²) in its vertices, still comes first. [Documentation](docs/packages/meshine/overview.md#safeguards).

- `galerkin`: the steady and transient heat-to-mechanics workflows run their stages as a coupling-layer `OneWayChain` and pass each nodal Kelvin field through the same-mesh `transfer` before freezing it. Results, manifest JSON, stage errors and messages are unchanged. [Documentation](docs/packages/galerkin/thermal_mechanical_workflow.md#stage-errors-and-failure-boundary).

- `galerkin`: the one-way Joule workflow and `ElementHeatSource` run on the coupling layer. The Joule heat is an element `Field` on the electrical mesh, carried to the thermal mesh by the same-mesh transfer; `ElementHeatSource.field` exposes it. Results, checks and error messages are unchanged. [Documentation](docs/packages/galerkin/joule_heating.md#element-source-api).

- `galerkin`: new `galerkin.coupling` layer: `Field` holds node or element values of one mesh with an SI unit, `transfer` carries it to the same mesh unchanged, and `OneWayChain` runs the stages of a one-way workflow with stage-labelled failures. It documents the kernel interface; the finite-element engine is the first kernel. Existing workflows are unchanged. [Documentation](docs/packages/galerkin/coupling.md).

- `galerkin`: the PEC box cavity (`solve_cavity_box`) accepts JAX or PyTorch box lengths and returns frequencies, eigenvalues, edge coefficients and centroid fields in that library with reverse-mode derivatives, exact through the axis scaling of the mesh. Degenerate modes get NaN derivatives and a `DegenerateModeWarning`. NumPy results are unchanged. [Documentation](docs/packages/galerkin/differentiation.md#box-cavity-derivatives-with-respect-to-the-lengths).

- `galerkin`: waveguide modes (`solve_modes`) accept JAX or PyTorch values for eps_r, mu_r (scalars or element arrays, real or complex) and k0, and return n_eff and both field arrays in that library with reverse-mode derivatives of eigenvalues and fields. Degenerate modes get NaN derivatives and a `DegenerateModeWarning`. NumPy results are unchanged. [Documentation](docs/packages/galerkin/differentiation.md#waveguide-modes-eigenvalues-fields-and-degenerate-modes).

- `galerkin`: elasticity and thermoelasticity accept JAX or PyTorch values for E, nu, alpha, the reference temperature, Dirichlet displacements, body force and traction, with reverse-mode derivatives. NumPy results are unchanged. [Documentation](docs/packages/galerkin/differentiation.md).

- `galerkin`: transient heat conduction accepts JAX or PyTorch values for conductivity, heat capacity, heat source, Dirichlet temperatures and the initial field, with reverse-mode derivatives through every time step; `checkpoint_every` trades recomputation for memory. NumPy results are unchanged. [Documentation](docs/packages/galerkin/differentiation.md#transient-heat-memory-and-checkpointing).

- `galerkin`: steady heat and steady electric conduction accept JAX or PyTorch values for conductivity, heat source, Dirichlet and reference potentials and boundary data, and return results in that library with derivatives (reverse mode, through an adjoint sparse solve). NumPy results are unchanged. Solvers that do not differentiate yet refuse JAX and PyTorch values instead of silently dropping the derivative. [Documentation](docs/packages/galerkin/differentiation.md).

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
