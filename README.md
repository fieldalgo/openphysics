# OpenPhysics

**English** | [한국어](README.ko.md) · [Documentation / 문서](docs/README.md)

A simulation suite with six implementation packages in one repository. Each
package has its own distribution, version and dependencies.

| Package | Current role |
|---|---|
| [galerkin](packages/galerkin/README.md) | 2D electromagnetic FEM, vector waveguide modes, steady heat conduction, static 2D elasticity and a 3D PEC box cavity solver |
| [galerkin-refsol](packages/galerkin-refsol/README.md) | Independent analytical solutions and published benchmarks; imported as `refsol` |
| [meshine](packages/meshine/README.md) | 2D triangle meshing for material regions |
| [gmshio](packages/gmshio/README.md) | Gmsh executable runner, MSH 4.1 ASCII reader and FEM mesh adapters |
| [physmat](packages/physmat/README.md) | Optical dispersion, material data and Drude-Lorentz fitting |
| [simcase](packages/simcase/README.md) | JSON model document, headless runner and optional browser studio |

The seventh distribution, [openphysics](packages/openphysics/README.md), is a
name reservation (`0.0.1`). It contains no engine and does not install the suite.
The repository root is not an installable distribution.

## Install from this checkout

Package metadata allows Python 3.10 or newer. Full automated regression covers
CPython 3.12.14 on Ubuntu 24.04. The separate Windows 2022 / Python 3.12.10
gate covers only installed headless heat API/CLI and selected save I/O; it is
not full Windows regression or Gmsh validation. Other environments are outside
these measured scopes. Windows save/cleanup acceptance remains incomplete;
the narrow GitHub-runner verification is stopped, and Linux results do not
establish Windows support. The `OS Independent` classifiers and
`py3-none-any` wheels describe package metadata, not a tested platform matrix.
The pinned validation environment in [ci/README.md](ci/README.md) targets Linux
and Python 3.12; its dependency versions cannot be reused on Python 3.10/3.11.

Run these commands from the repository root in a virtual environment:

```bash
python -m pip install -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine -e packages/gmshio -e "packages/physmat[rii]" -e "packages/simcase[studio,test]"
```

This installs the local implementations together with their dependencies.
Gmsh is an optional external executable: mesh generation tests need `gmsh` on
PATH or `GMSH_EXECUTABLE` pointing to it. Reading existing MSH files does not.
The full refractiveindex.info database is optional; built-in materials and
fixture-based reader tests work without downloading it.

## Run a model

After installation, stay at the repository root:

```bash
python -m simcase validate packages/simcase/examples/slab_te_check.json
python -m simcase run packages/simcase/examples/slab_te_check.json -o slab_results
python -m simcase.studio --no-browser
```

The studio is available at `http://127.0.0.1:8765`. CLI commands are `simcase`,
`simcase-run` and `simcase-studio`; Python imports use `simcase`. The JSON format
still uses the version field `"openphysics": "0.2"`.

For 2D, the document runner solves one lossless `em.modes2d` problem with PEC/PMC
boundaries. Scalar runs support physics-parameter sweeps. Full-vector runs
support single study points and wavelength sweeps of resolved modes, an explicit
exterior guiding threshold, complex field storage and component display in Studio.
Sweeps use electric-field overlap to track branches and reject missing,
ambiguous or near-degenerate matches before reporting group index. See the
`vector_slab`, `vector_fiber` and `vector_slab_sweep` examples and the
[tracking contract](packages/simcase/README.md#tracked-vector-wavelength-sweeps).
A single `em.cavity3d` study solves a vacuum rectangular box with PEC on all six
walls through the same document runner:

```bash
python -m simcase validate packages/simcase/examples/cavity_box.json
python -m simcase run packages/simcase/examples/cavity_box.json -o cavity_results
```

Use a fresh output directory for each cavity run. The result contains frequencies
in Hz, SI mesh coordinates, and mass-normalized edge coefficients and centroid
fields in JSON/NPZ. The required frequency target selects a finite set of nearby
modes; it does not certify the complete lowest spectrum or every degenerate
partner. Studio supports 2D models only and rejects 3D mesh/run requests. See the
[cavity document contract](packages/simcase/docs/cavity3d.md) and the reusable
[Python cavity API](packages/galerkin/docs/cavity_solver.md).

Coupled multiphysics, geometry sweeps and lossy mode solves are not implemented
in the document runner.

## Standalone heat, elasticity and vector fields

Steady homogeneous isotropic 2D conduction uses `galerkin.thermal` and the
independent `refsol.thermal`. See the [Kelvin/heat-flux contract](packages/galerkin/docs/thermal_steady2d.md).
Static elasticity supports [global Cartesian boundary traction](packages/galerkin/docs/elasticity_traction.md),
with [independent traction validation](packages/galerkin/docs/elasticity_traction_independent_validation.md).
After installation, run from the repository root:

```bash
python packages/galerkin/examples/thermal_steady2d.py
python packages/galerkin/examples/elasticity_traction.py
```

Both English examples are also in the galerkin sdist. Heat load/reaction is W/m
of out-of-plane thickness; mechanical load/reaction is N/m of thickness. These
standalone APIs do not add transient heat, thermal expansion or coupled models.

An additional [prescribed-temperature mechanical stage](packages/galerkin/docs/prescribed_temperature_thermoelasticity.md)
uses `galerkin.thermoelasticity` and `refsol.thermoelasticity` with an explicitly
supplied, immutable same-mesh nodal temperature field in Kelvin. Run the
[English example](packages/galerkin/examples/prescribed_temperature_thermoelasticity.py)
after installation. It reports physical three-dimensional elastic energy per
thickness (J/m), including the plane-strain out-of-plane contribution. This
stage does not solve heat, automatically connect a heat result, authenticate
temperature provenance, or add simcase/Studio support.

For standalone static 2D elasticity, use `galerkin.elasticity` and the independent
`refsol.elasticity` submodule. The [elasticity contract](packages/galerkin/docs/elasticity2d.md)
defines plane stress/strain, SI units, constraints and the near-incompressibility
limit. From the repository root after installation:

```bash
python packages/galerkin/examples/elasticity2d.py
```

The contract and [English example](packages/galerkin/examples/elasticity2d.py) are
also included in the galerkin sdist. This API has no simcase/Studio or thermal
coupling integration. The [vector eigenspace notes](packages/galerkin/docs/eigenspace_reliability.md)
explain complex-field preservation and the limits of degenerate-basis reliability.

## Validate this checkout

Headless JSON/API/CLI heat documents use the separate
[`thermal.steady2d` contract](packages/simcase/docs/thermal_steady2d.md).
The [slab](packages/simcase/examples/thermal_slab.json) and
[mixed-source](packages/simcase/examples/thermal_mixed.json) JSON examples specify
Kelvin, SI-suffixed thermal coefficients and explicit geometry length units.
This rectangular steady-heat path has no thermal Studio forms, plots, Robin
boundary or automatic thermoelastic coupling. Consult the contract for fresh
output ownership, incomplete-output detection and platform validation limits.
A separate Windows 2022 / Python 3.12.10 gate covers installed headless API/CLI
and selected save I/O only; it does not establish Windows full-regression or Gmsh support.

Reproducible Linux validation, pinned optical data, and checks of installed
wheel/sdist artifacts are documented in [ci/README.md](ci/README.md).

```bash
python -m pytest -q
python -m pytest -q -m "not slow"
python -m pytest -q packages/simcase/tests
```

The root `conftest.py` imports packages from this checkout, including when it is
a worktree. Run Python from the repository root, not from `packages/`, whose
directory names can shadow the installed modules.

Tests cover analytical references, mesh topology and scale, FEM convergence,
material models, document runs and the studio HTTP API. Some integration tests
skip when optional tools or data are absent; a passing subset is not evidence
that those integrations were exercised. Browser interaction and package release
workflows are separate checks.

Historical numerical measurements in package READMEs retain their stated dates;
they are not reports from a new test run.

Output ownership requires exclusive caller control until save and cleanup finish.
Protection against replacements observed before cleanup is tested; a foreign
replacement between an ownership check and unlink is not guaranteed safe.
Hostile filesystem races and atomic rollback are outside acceptance. Do not let
another writer mutate the output during this interval. Windows save verification
is stopped with two unresolved failures; Linux results do not establish Windows
acceptance. GitHub Actions is disabled; do not dispatch or rerun workflows.

This checkout includes standalone outward-flux/Robin heat boundaries; see [contract](packages/galerkin/docs/thermal_flux_robin.md) and [independent acceptance](packages/galerkin/docs/thermal_flux_robin_independent_validation.md). Headless JSON does not accept these boundaries. The contracts and validation reports describe the implemented and measured scope.

The explicit Python-only [steady heat→mechanics workflow](packages/galerkin/docs/thermal_mechanical_workflow.md) connects same-mesh heat and prescribed-temperature mechanics through an immutable nodal-P1 Kelvin copy. Its [independent report](packages/galerkin/docs/thermal_mechanical_independent_validation.md) separates measured acceptance from implementation. It adds no JSON/CLI/Studio integration, persistence, Robin/flux/traction workflow, transient feedback or thermodynamic coupling.

The standalone [transient heat Python API](packages/galerkin/docs/transient_heat.md) uses fixed P1 triangles, consistent mass and backward Euler. Its [producer validation contract](packages/galerkin/docs/transient_heat_validation.md) and [independent report](packages/galerkin/docs/transient_heat_independent_validation.md) distinguish authored gates from measured evidence. Distribution checks are configured to consume the complete archived convergence example and independent `--suite all`; configuration is not an execution result. This adds no transient JSON/CLI/Studio, Robin/flux input, persistence or automatic heat-to-mechanics connection.
