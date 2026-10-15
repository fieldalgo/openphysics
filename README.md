# OpenPhysics

A simulation suite with six implementation packages in one repository. Each
package has its own distribution, version and dependencies.

| Package | Current role |
|---|---|
| [galerkin](packages/galerkin/README.md) | 2D electromagnetic FEM, vector waveguide modes and 3D cavity elements |
| [galerkin-refsol](packages/galerkin-refsol/README.md) | Independent analytical solutions and published benchmarks; imported as `refsol` |
| [meshine](packages/meshine/README.md) | 2D triangle meshing for material regions |
| [gmshio](packages/gmshio/README.md) | Gmsh executable runner, MSH 4.1 ASCII reader and FEM mesh adapters |
| [physmat](packages/physmat/README.md) | Optical dispersion, material data and Drude-Lorentz fitting |
| [simcase](packages/simcase/README.md) | JSON model document, headless runner and optional browser studio |

The seventh distribution, [openphysics](packages/openphysics/README.md), is a
name reservation (`0.0.1`). It contains no engine and does not install the suite.
The repository root is not an installable distribution.

## Install from this checkout

Run these commands from the repository root, using Python 3.10 or newer:

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

The document runner solves one lossless `em.modes2d` problem with PEC/PMC
boundaries. Scalar runs support physics-parameter sweeps. Full-vector runs
support single study points and wavelength sweeps of resolved modes, an explicit
exterior guiding threshold, complex field storage and component display in Studio.
Sweeps use electric-field overlap to track branches and reject missing,
ambiguous or near-degenerate matches before reporting group index. See the
`vector_slab`, `vector_fiber` and `vector_slab_sweep` examples and the
[tracking contract](packages/simcase/README.md#tracked-vector-wavelength-sweeps).
The FEM engine's 3D cavity routines remain a separate Python capability.
Coupled multiphysics, geometry sweeps and lossy mode solves are not implemented
in the document runner.

## Validate this checkout

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
