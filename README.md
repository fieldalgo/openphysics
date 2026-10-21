# OpenPhysics

OpenPhysics is a Python simulation toolkit for electromagnetic fields, heat
conduction and solid mechanics. It brings finite-element solvers, meshing,
material models and independent reference solutions into one repository.
Use the Python APIs directly, run supported models from JSON, or explore 2D
optical models and rectangular heat documents in the local browser Studio.

The project is under active development. Each feature has an explicit contract
and validation scope; the name does not imply a general-purpose coupled
multiphysics solver.

## What you can solve

| Area | Implemented scope | Guide |
|---|---|---|
| Electromagnetics | 2D scalar and full-vector waveguide modes; resolved-mode wavelength sweeps with complex fields and mode tracking | [Model runner](packages/simcase/README.md), [vector reliability](docs/packages/galerkin/eigenspace_reliability.md) |
| Electrostatics and scattering | 2D electrostatic potential and frequency-domain Helmholtz scattering with a first-order absorbing boundary or a cylindrical PML, through the Python API | [galerkin](packages/galerkin/README.md), [milestone validation](docs/packages/galerkin/milestone_validation.md) |
| 3D cavities | Rectangular-box eigenmodes, vacuum PEC or with lossy box materials and conducting walls (complex frequencies and Q), through a Python API or a single JSON study | [Cavity API](docs/packages/galerkin/cavity_solver.md), [material cavity](docs/packages/galerkin/material_cavity.md), [JSON contract](docs/packages/simcase/cavity3d.md) |
| Heat conduction | Steady isotropic 2D conduction; Dirichlet, prescribed-flux and Robin boundaries; rectangular headless JSON with side-constant boundary data and a dedicated Studio view | [Heat API](docs/packages/galerkin/thermal_steady2d.md), [flux/Robin](docs/packages/galerkin/thermal_flux_robin.md), [thermal JSON](docs/packages/simcase/thermal_steady2d.md), [boundary JSON](docs/packages/simcase/thermal_steady_boundary2d.md), [Studio](docs/packages/simcase/thermal_studio.md) |
| Transient heat | 2D Python engine and rectangular headless JSON/API/CLI/save; fixed P1, consistent mass/backward Euler, constant isotropic properties, explicit times and sampled Dirichlet/insulation; dedicated Studio time/field/history views | [Transient heat](docs/packages/galerkin/transient_heat.md), [document](docs/packages/simcase/thermal_transient2d.md), [validation](docs/packages/galerkin/transient_heat_validation.md), [Studio](docs/packages/simcase/thermal_transient_studio.md) |
| Material regions | Piecewise-constant isotropic materials on named 2D mesh regions for steady and transient heat, elasticity, thermal expansion and both heat→mechanics workflows in Python; steady and transient heat JSON documents with shapes over a background | [Region materials](docs/packages/galerkin/multimaterial.md), [region documents](docs/packages/simcase/thermal_regions2d.md) |
| Solid mechanics | Static 2D linear elasticity, plane stress/strain and global Cartesian boundary traction | [Elasticity](docs/packages/galerkin/elasticity2d.md), [traction](docs/packages/galerkin/elasticity_traction.md) |
| Thermal expansion | Prescribed nodal-temperature mechanics, optional total traction, and an explicit same-mesh steady heat→mechanics workflow | [Prescribed temperature](docs/packages/galerkin/prescribed_temperature_thermoelasticity.md), [total traction](docs/packages/galerkin/thermoelastic_traction.md), [workflow](docs/packages/galerkin/thermal_mechanical_workflow.md) |
| Transient thermal stress | Quasistatic linear small-strain mechanics at selected stored transient-heat times on the same fixed mesh, through an explicit second Python call | [Transient heat→mechanics](docs/packages/galerkin/transient_thermal_mechanical.md) |

### Where each feature is available

| Feature | Python API | JSON / CLI | Studio |
|---|---|---|---|
| 2D waveguide modes and sweeps | Yes | `em.modes2d` (lossless) | Yes |
| 2D electrostatics and scattering | Yes | No | No |
| 3D cavity: vacuum PEC, lossy materials and walls | Yes | `em.cavity3d` | No |
| Steady heat | Yes | Rectangular `thermal.steady2d` | Dedicated view |
| Transient heat | Yes | Rectangular `thermal.transient2d` | Dedicated views |
| Heat with material regions | Yes | `thermal.steady2d`, `thermal.transient2d` with shapes | No |
| Elasticity, thermal expansion, heat→mechanics | Yes | No | No |

Python-only capabilities do not automatically appear in JSON or Studio.

With the optional `simcase[export]` extra, saved results can be written as VTU
files for ParaView: rectangular steady heat with Dirichlet and insulated sides,
rectangular transient heat (one time, or every stored time as a `.pvd` series)
and the vacuum PEC cavity. See [Viewing in ParaView](docs/packages/simcase/overview.md#viewing-in-paraview).

### Current limits

- Heat→mechanics coupling is one-way: an explicit second Python call with no
  feedback to heat. Fully coupled thermal feedback is not supported.
- Transient heat has no restart, transient flux/Robin input or automatic coupling.
- The steady heat→mechanics workflow does not yet accept the separate
  Robin/flux/traction extensions.
- Mechanics (elasticity, thermal expansion, heat→mechanics) and 2D
  electrostatics and scattering are Python-only.
- 2D heat and mechanics are plane models per unit depth. JSON heat documents
  set boundary conditions only on the four outer sides of the domain.
- `em.modes2d` is lossless: lossy optical materials are rejected. Nonlinear
  mechanics and geometry sweeps are not supported.
- Studio rejects 3D models and heat documents with material regions, and has
  no mechanics forms.
- The VTU export rejects region documents, steady documents with flux or
  convection sides, lossy cavities and waveguide modes.

## Packages

All implementation sources and their documentation are available here. Each
package has its own distribution, version, dependencies and license notices.

| Package | Purpose |
|---|---|
| [galerkin](packages/galerkin/README.md) | Finite-element engines and field postprocessing |
| [galerkin-refsol](packages/galerkin-refsol/README.md) | Independent analytical references and published benchmarks; import as `refsol` |
| [meshine](packages/meshine/README.md) | 2D triangle meshes for material regions |
| [gmshio](packages/gmshio/README.md) | Optional Gmsh executable integration, MSH reader and mesh adapters |
| [physmat](packages/physmat/README.md) | Material properties, optical dispersion and Drude–Lorentz fitting |
| [simcase](packages/simcase/README.md) | JSON documents, headless runner and optional local Studio |

The seventh distribution, [openphysics](packages/openphysics/README.md)
(`0.0.1`), only reserves the project name: it contains no engine and does not
install these packages. The repository root is not an installable distribution.
**Use the checkout installation below; `pip install openphysics` does not install
the simulation toolkit.**

## Install from source

CI runs the full regression on CPython 3.12 and Ubuntu 24.04. For a Linux checkout:

```bash
git clone https://github.com/fieldalgo/openphysics.git
cd openphysics
python -m venv .venv
source .venv/bin/activate
python -m pip install -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine -e packages/gmshio -e "packages/physmat[rii]" -e "packages/simcase[studio,test]"
```

Run commands from the repository root. Running Python inside `packages/` can
shadow installed modules with the directories of the same name.

Gmsh is optional and separately installed: mesh generation needs `gmsh` on PATH
or `GMSH_EXECUTABLE`; reading existing MSH files does not. Built-in optical
materials work without downloading the full refractiveindex.info database.
For pinned dependency and database versions, use the [development guide](docs/development.md).

## Run an example

Validate and run the supplied slab-waveguide document:

```bash
python -m simcase validate examples/simcase/slab_te_check.json
python -m simcase run examples/simcase/slab_te_check.json -o slab_results
```

Explore 2D optical models and rectangular heat documents in Studio:

```bash
python -m simcase.studio --no-browser
```

Open `http://127.0.0.1:8765`. Studio is a local tool, not an authenticated
multi-user service. Keep it off untrusted networks. CLI entry points are
`simcase`, `simcase-run` and `simcase-studio`; the document format retains
`"openphysics": "0.2"` as its version field.

Try a headless heat document or standalone Python examples:

```bash
python -m simcase run examples/simcase/thermal_slab.json -o thermal_results
python examples/galerkin/thermal_steady2d.py
python examples/galerkin/elasticity_traction.py
python examples/galerkin/thermoelastic_traction.py
```

More documents are in [`examples/simcase`](examples/simcase) and
more scripts in [`examples/galerkin`](examples/galerkin).

Use a fresh output directory for each saved run and retain exclusive control
until saving and cleanup finish. Hostile filesystem races and atomic rollback
are outside acceptance. Read each contract for units: thermal APIs use Kelvin,
heat flow per depth is W/m, mechanical force per depth is N/m and physical
elastic energy per depth is J/m.

## Validation and platform support

Physics features are checked against independent analytical references,
conservation identities, negative controls and mesh-convergence studies. Each
feature's criteria and limits are in its contract and validation documents,
linked from the [documentation index](docs/README.md). Run the full source suite
from the repository root:

```bash
python -m pytest -q
```

| Scope | Platforms | What it covers |
|---|---|---|
| Full source regression | Linux, Python 3.12 | Full source suite, Studio JavaScript checks, all seven distributions built and installed, numerically sensitive tests under two forced BLAS kernels |
| Installed-package acceptance | Linux, macOS, Windows, Python 3.12 | Linux: every Python test against all seven wheels, built from sdists and installed with their extras outside the checkout. Each OS: six implementation sdists built into wheels and tested in a fresh environment for package bytes, bundled assets, public API/CLI/save behavior and heat save/I-O robustness |

Installed acceptance is not a full macOS or Windows regression. Package metadata
requires Python 3.12 or later, and CI tests only Python 3.12; `OS Independent` classifiers
and `py3-none-any` wheels describe metadata, not a tested platform matrix. A
commit's results are in its required `tests` check on GitHub Actions. The
[development guide](docs/development.md) lists the checks and commands.

## Documentation

| Page | Content |
|---|---|
| [Documentation index](docs/README.md) | Every feature contract and validation report, English and Korean |
| [Architecture](docs/architecture.md) | Package map and entry points |
| [Development guide](docs/development.md) | Environment, repository layout, checks, CI and results |
| [Asset provenance](docs/assets.md) | Sources of bundled figures, fixtures and data |

Usage and validation guides under `docs/` have complete Korean counterparts;
start from the [Korean index](docs/locales/ko/pages/index.md).

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for changes, bug reports and questions, and
[SECURITY.md](SECURITY.md) for private vulnerability reporting. The default
branch, `main`, contains reviewed changes; feature branches may contain
unvalidated work.

## License

Original code and documentation are licensed under **[Apache-2.0](LICENSE)**.
[NOTICE](NOTICE) and package notices preserve third-party terms: embedded
refractiveindex.info optical data is CC0 1.0, Gmsh is separately installed under
its own license, and dependency licenses are not replaced by this repository's
license.

Every dependency, external program, dataset and published reference, with its
license and how it is used, is listed in
[third-party software](docs/third-party.md).
