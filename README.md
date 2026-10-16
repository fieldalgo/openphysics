# OpenPhysics

OpenPhysics is a Python simulation toolkit for electromagnetic fields, heat
conduction and solid mechanics. It brings finite-element solvers, meshing,
material models and independent reference solutions into one repository.
Use the Python APIs directly, run supported models from JSON, or explore 2D
optical models in the local browser Studio.

The project is under active development. Each feature has an explicit contract
and a measured validation scope; the name does not imply a general-purpose
coupled multiphysics solver.

## What you can solve

| Area | Implemented scope | Guide |
|---|---|---|
| Electromagnetics | 2D scalar and full-vector waveguide modes; resolved-mode wavelength sweeps with complex fields and mode tracking | [Model runner](packages/simcase/README.md), [vector reliability](packages/galerkin/docs/eigenspace_reliability.md) |
| 3D cavities | Vacuum rectangular PEC-box eigenmodes through a Python API or a single JSON study | [Cavity API](packages/galerkin/docs/cavity_solver.md), [JSON contract](packages/simcase/docs/cavity3d.md) |
| Heat conduction | Steady homogeneous isotropic 2D conduction; standalone Dirichlet, prescribed-flux and Robin boundaries; a separate rectangular headless JSON path | [Heat API](packages/galerkin/docs/thermal_steady2d.md), [flux/Robin](packages/galerkin/docs/thermal_flux_robin.md), [thermal JSON](packages/simcase/docs/thermal_steady2d.md) |
| Transient heat | Standalone 2D Python API on a fixed P1 mesh; consistent mass and backward Euler, constant isotropic properties, time-dependent Dirichlet values and insulated edges | [Transient heat](packages/galerkin/docs/transient_heat.md), [validation](packages/galerkin/docs/transient_heat_validation.md) |
| Solid mechanics | Static 2D linear elasticity, plane stress/strain and global Cartesian boundary traction | [Elasticity](packages/galerkin/docs/elasticity2d.md), [traction](packages/galerkin/docs/elasticity_traction.md) |
| Thermal expansion | Prescribed nodal-temperature mechanics, optional total traction, and an explicit same-mesh steady heat→mechanics workflow | [Prescribed temperature](packages/galerkin/docs/prescribed_temperature_thermoelasticity.md), [total traction](packages/galerkin/docs/thermoelastic_traction.md), [workflow](packages/galerkin/docs/thermal_mechanical_workflow.md) |

The JSON runner supports lossless `em.modes2d`, `em.cavity3d` and the documented
`thermal.steady2d` subset. Python-only capabilities do not automatically appear
in JSON or Studio. Studio supports 2D optical models; it rejects 3D models and
has no thermal forms or plots. Transient heat is Python-only, with no transient
JSON, persistence, flux/Robin input or automatic coupling. Nonlinear mechanics, geometry
sweeps, lossy document-mode solves and fully coupled thermal feedback are not
part of the integrated scope. The steady heat→mechanics workflow does not yet
accept the separate Robin/flux/traction extensions.

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
(`0.0.1`), reserves the project name. It contains no engine and does not install
these packages. The repository root is not an installable distribution.
**Use the checkout installation below; `pip install openphysics` does not install
the simulation toolkit.** Publishing this repository is separate from publishing
new package versions to PyPI.

## Install from source

The measured full-regression environment is CPython 3.12.14 on Ubuntu 24.04.
For a Linux checkout:

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
For reproducible dependency and database versions, use the [validation setup](ci/docs/README.md).

## Run an example

Validate and run the supplied slab-waveguide document:

```bash
python -m simcase validate packages/simcase/examples/slab_te_check.json
python -m simcase run packages/simcase/examples/slab_te_check.json -o slab_results
```

Explore 2D optical models in Studio:

```bash
python -m simcase.studio --no-browser
```

Open `http://127.0.0.1:8765`. Studio is a local tool, not an authenticated
multi-user service. Keep it off untrusted networks. CLI entry points are
`simcase`, `simcase-run` and `simcase-studio`; the document format retains
`"openphysics": "0.2"` as its version field.

Try a headless heat document or standalone Python examples:

```bash
python -m simcase run packages/simcase/examples/thermal_slab.json -o thermal_results
python packages/galerkin/examples/thermal_steady2d.py
python packages/galerkin/examples/elasticity_traction.py
python packages/galerkin/examples/thermoelastic_traction.py
```

Use a fresh output directory for each saved run and retain exclusive control
until saving and cleanup finish. Hostile filesystem races and atomic rollback
are outside acceptance. Read each contract for units: thermal APIs use Kelvin,
heat flow per depth is W/m, mechanical force per depth is N/m and physical
elastic energy per depth is J/m.

## Validation and current limits

Physics features are checked against independent analytical references,
conservation identities, negative controls and mesh-convergence studies. Run
checks from the repository root:

```bash
python -m pytest -q
python -m pytest -q -m "not slow"
python -m pytest -q packages/simcase/tests
```

The recorded Linux snapshot `0bc4419` passed **1,536 source tests plus 9 subtests**,
with **16 optional skips**: 14 Gmsh-absence cases and 2 local-database cases.
A separate installed-wheel run passed **541 tests without skips**. Seven
sdist→wheel builds and strict metadata checks of 14 artifacts also passed.
See the [validation index](docs/README.md) for the exact snapshot and scope.
Historical numbers are not a claim that every later documentation commit reran
the full suite, and a passing subset does not validate skipped integrations.

Package metadata permits Python 3.10+, but the pinned Linux validation dependencies
are for Python 3.12 and cannot be reused unchanged on 3.10/3.11. Other environments
are outside the measured full-regression scope. The narrow Windows 2022 /
Python 3.12.10 gate passed 36 installed API/CLI/save cases and 3 source
target-protection cases at `636a23a` ([run](https://github.com/fieldalgo/openphysics/actions/runs/38858254797)).
This recovers two historical replacement failures; it does not establish full
Windows regression, other filesystems or macOS support. `OS Independent` classifiers
and `py3-none-any` wheels describe metadata, not a tested platform matrix.
GitHub Actions is enabled. Recorded cloud results remain evidence for their
original snapshots; check the exact workflow run for newer commits.

## Documentation and contributions

Start with the [documentation index](docs/README.md) and the
[architecture and package map](docs/architecture.md). Usage and validation guides
have complete Korean counterparts. [Asset provenance](docs/assets.md) identifies
historical figures, fixtures and data sources.

The default branch, `main`, contains reviewed integrations. Feature branches
may contain unvalidated work. See [CONTRIBUTING.md](CONTRIBUTING.md) for changes
and reproducible bug reports, or [SECURITY.md](SECURITY.md) for private vulnerability
reporting. No separate private repository is needed to use this checkout.

## License

Original code and documentation are licensed under **[Apache-2.0](LICENSE)**,
the same license used by Wavebit. [NOTICE](NOTICE) and package notices preserve
third-party terms: embedded refractiveindex.info optical data is CC0 1.0,
Gmsh is separately installed under its own license, and dependency licenses
are not replaced by this repository's license.
