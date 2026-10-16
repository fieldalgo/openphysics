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
- English is the default language for the repository, READMEs, contribution and security entry points, code, comments and executable examples. Bilingual English/Korean content belongs only under `docs/` directories: English pages at `docs/<name>.md` and complete Korean counterparts at `docs/locales/ko/pages/<name>.md`. Package overview translations belong there, not in separate Korean READMEs. Preserve equations, units, commands, numerical gates and limitations; translations do not imply new tests. Keep language navigation inside documentation, verify relative links and include both documentation versions in source distributions. This follows the explicit user correction of 2026-10-16.
- Every new physics feature is validated against refsol (analytic) with a mesh-convergence check.
- Run the whole suite from the repository root: `python -m pytest -q`. A single package is
  `python -m pytest -q packages/<name>/tests` — still the fast inner loop.
- Never run Python from inside `packages/`. The folder names there equal the package names and
  shadow the installed packages: the import succeeds but yields an empty namespace package whose
  `__file__` is None, and the failure surfaces far away. The repository root is safe.
- Third-party integrations are their own package (`gmshio` is the pattern: it shells out to Gmsh,
  with its external executable and upstream license documented separately). A new backend is a new folder under
  `packages/` with its own pyproject, not a new repository.

## Setup

    pip install numpy scipy matplotlib shapely fastapi uvicorn pyyaml pytest httpx
    pip install --no-deps -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
                          -e packages/gmshio -e packages/physmat -e packages/simcase

## Run the UI

From the repository root after installing the packages:

    python -m simcase.studio      -> http://127.0.0.1:8765

## Contributions

Use `main` as the only trunk and default branch. Branch from current `origin/main`,
rebase unpublished work onto it before opening a PR to `main`, and require both
`linux-py312` and `windows-py312-thermal` on the exact commit, including documentation
changes. Land that tested commit with a fast-forward push only after PR review.
If the base moves or a push is rejected, update the candidate and rerun CI.
Do not force-push shared work. Combine branches only when their changes depend
on one another; there is no permanent integration branch. Releases use version
tags on validated `main` commits. Never infer a release or PyPI upload from a
branch update. Main CI runs must not be cancelled by newer pushes. Read CONTRIBUTING.md and SECURITY.md
before submitting changes or reporting vulnerabilities. Keep implementation and
validation contracts with the code; do not commit private plans, credentials,
research records or session handoffs. GitHub Actions is enabled with owner approval. Use the retained validation
workflows and record exact commits, command exits and artifacts.
