# OpenPhysics

A multiphysics simulation suite. One repository, six packages, each its own PyPI distribution.

```
packages/galerkin/         FEM engine (layers 3-6)
packages/galerkin-refsol/  analytic reference solutions for validation (import name: refsol)
packages/meshine/          2D quality mesher
packages/gmshio/           Gmsh runner + MSH reader (3D meshes)
packages/physmat/          materials: optical dispersion, refractiveindex.info reader
packages/openphysics/      model document (JSON) + headless runner, plus the optional
                           web UI in openphysics/studio/ (FastAPI + static/index.html)
```

Packages stay independent where it matters: separate PyPI names, versions, LICENSE, NOTICE and
README. They share one git history, one test run and one install.

## Rules

- Code, comments, docstrings, READMEs: English only. This repository is intended to go public.
- Every new physics feature is validated against refsol (analytic) with a mesh-convergence check.
- Run the whole suite from the repository root: `python -m pytest -q`. A single package is
  `python -m pytest -q packages/<name>/tests` — still the fast inner loop.
- Never run Python from inside `packages/`. The folder names there equal the package names and
  shadow the installed packages: the import succeeds but yields an empty namespace package whose
  `__file__` is None, and the failure surfaces far away. The repository root is safe.
- Third-party integrations are their own package (`gmshio` is the pattern: it shells out to Gmsh,
  so the GPL stays isolated and the core never implies it). A new backend is a new folder under
  `packages/` with its own pyproject, not a new repository.

## Setup

    pip install numpy scipy matplotlib shapely fastapi uvicorn pyyaml pytest httpx
    pip install --no-deps -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
                          -e packages/gmshio -e packages/physmat -e packages/openphysics

## Run the UI

    cd packages/openphysics && python -m openphysics.studio      -> http://127.0.0.1:8765

## Elsewhere

Study notes, concept demos and experiments live in the sibling repository `../openphysics-lab`
(personal account, never published). A path inside it is never public; everything in this
repository ships with a product one day. When unsure where a file goes, it goes in the lab.

Background, decisions and validation values: Claude Project "FieldAlgo".
