# OpenPhysics

A multiphysics simulation suite. One repository, six implementation packages,
each its own PyPI distribution, plus the empty `openphysics` name reservation.

```
packages/galerkin/         FEM engine (layers 3-6)
packages/galerkin-refsol/  analytic reference solutions for validation (import name: refsol)
packages/meshine/          2D quality mesher
packages/gmshio/           Gmsh runner + MSH reader (3D meshes)
packages/physmat/          materials: optical dispersion, refractiveindex.info reader
packages/simcase/      model document (JSON) + headless runner, plus the optional
                           web UI in simcase/studio/ (FastAPI + static/index.html)
```

Packages stay independent where it matters: separate PyPI names, versions, LICENSE, NOTICE and
README. They share one git history, one test run and one install.

## Rules

- Code, comments, docstrings, API identifiers and executable examples remain English.
- User-facing READMEs, usage guides and validation explanations are maintained in English and complete Korean versions. Keep the existing English source paths; use README.ko.md for overviews and docs/locales/ko/pages/<same-name>.md for package documentation. Preserve equations, units, commands, numerical gates and limitations; translations do not imply new tests. Link languages through the documentation index, verify relative links and include both versions in source distributions. This follows the explicit user instruction of 2026-10-15.
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
                          -e packages/gmshio -e packages/physmat -e packages/simcase

## Run the UI

From the repository root after installing the packages:

    python -m simcase.studio      -> http://127.0.0.1:8765

## Contributions

Use `develop` as the integration branch. Read CONTRIBUTING.md and SECURITY.md
before submitting changes or reporting vulnerabilities. Keep implementation and
validation contracts with the code; do not commit private plans, credentials,
research records or session handoffs. GitHub Actions is disabled; do not enable
or dispatch workflows.
