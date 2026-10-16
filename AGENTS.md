# OpenPhysics contributor instructions

This file is the shared source of repository instructions for coding agents. Keep common rules here; `CLAUDE.md` imports this file.

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

- Agent-authored commits include `Co-authored-by: Codex <noreply@openai.com>` (or the authoring agent's equivalent attribution).

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

Open pull requests as drafts. Branch pushes do not run validation, and draft PRs
allocate no validation runners. After reviewing the change and running relevant
checks in an appropriate local or remote environment, mark the PR Ready for
review. Validation runs on Ready PR changes, main pushes and explicit manual
dispatch. Enable automatic Rebase and merge only after review and relevant
validation, with every required check preserved.

Main validation uses a stable workflow/ref concurrency group with `queue: max`
and cancellation disabled. Non-main runs use `queue: single` and supersede older
runs. This Actions queue is separate from a pull-request merge queue.

Keep file paths, temporary directories, subprocesses and cleanup portable.
The validation structure is full Linux acceptance plus installed-distribution
checks on Linux, macOS and Windows. Do not infer a platform pass from another
OS or a universal wheel; inspect the exact run and retain failures and artifacts.

Use `main` as the only trunk and default branch. Branch from current `origin/main`
and open a PR to `main`. Every change, including documentation, requires the
`tests` completion check, `windows-py312-thermal`, and all three
`platform-install` matrix checks from GitHub Actions.
Land green PRs using GitHub Rebase and merge, with no required approving review;
record the resulting main SHA because GitHub creates new commit IDs. Rebase and
rerun manually only for conflicts. Do not push directly to main, force-push shared
work, create merge commits or squash on landing. Merged branches are automatically
deleted, so preserve any remaining work first. Main push CI validates the combined
state and must not be cancelled by newer pushes. Fix a failed main the same day;
if a fix cannot be completed within one hour, submit a revert PR. No merge queue.
Combine branches only when needed; there is no permanent integration branch.
Release tags require green checks on the resulting main commit. Branch updates
alone do not publish packages. Read CONTRIBUTING.md and SECURITY.md
before submitting changes or reporting vulnerabilities. Keep implementation and
validation contracts with the code; do not commit private plans, credentials,
research records, generated artifacts or session handoffs. GitHub Actions is enabled with owner approval. Use the retained validation
workflows and record exact commits, command exits and artifacts.
Review the exact workflow run and its artifacts before treating a candidate as validated.
