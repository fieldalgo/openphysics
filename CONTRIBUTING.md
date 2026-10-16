# Contributing

OpenPhysics is under active development. Start with the [package overview](README.md)
and [implementation and validation contracts](docs/README.md). The `main`
branch is the only trunk and the default branch; target pull requests there. Feature branches may contain work that has not passed acceptance.

Open an issue for a reproducible bug or a proposed change. Include the commit,
Python and platform versions, input units, a minimal example, and the expected
and actual results. Remove credentials, personal information and confidential
models before attaching files. Report vulnerabilities through the private
channel in [SECURITY.md](SECURITY.md).

Install and run from the repository root as described in [README.md](README.md).
Use [validation guide](ci/docs/README.md) for the pinned Linux validation environment,
optional tools and data, and isolated distribution checks. GitHub Actions is enabled for pushes and pull requests. Review the exact
workflow results and artifacts when validating a contribution.
Record the exact commands, exits, failures and optional skips from your own checks.

Physics changes need independent analytical references and mesh-convergence
checks. Preserve existing numerical thresholds and report limitations. Keep
production code, comments, APIs and executable examples in English; update
English and Korean usage and validation documents under `docs/` together.
Repository READMEs and contribution/security entry points remain English. A passing
subset or a documentation change does not establish new platform support.

Keep changes focused. Do not commit credentials, generated build directories,
local environment files or private research material. Preserve upstream notices
and verify the terms and provenance of any added dependency, data or copied code.
Contributions are submitted under the repository's [Apache-2.0 license](LICENSE),
with third-party exceptions recorded in [NOTICE](NOTICE) and package notices.

## Branches and releases

`main` is the only trunk and the default branch. Create a feature branch from
current `origin/main`. Before review, fetch and rebase your own unpublished work
onto `origin/main`, push it and open a pull request targeting `main`. Preserve
shared or submitted history; use a new branch if replaying it is necessary.

Every change, including documentation, requires successful `linux-py312` and
`windows-py312-thermal` checks from GitHub Actions on the exact proposed commit.
Review their logs and artifacts, not only the badge. Once the PR is reviewed,
fast-forward that tested commit with `git push origin <branch>:main`. Never
force-push. If the base moved or a required check rejects the push, update the
candidate, push and validate again. Do not create an untested merge commit or
squash after validation. The PR remains the review record for the landed commit.
Main runs are retained when later pushes arrive; branch/PR runs may be superseded.

Combine work in one temporary branch only when changes depend on each other or
conflict. There is no permanent integration branch. To release, land the version
change through the same PR and CI process, then tag that validated main commit
`vX.Y.Z` and publish release notes and verified artifacts. Branch updates alone
never publish packages. Automated PyPI/documentation publication is not configured
in this repository; release credentials and publication gates require separate
setup. Create `maintenance/X.Y.x` from a released tag only when that release needs
a patch, and carry reviewed fixes from main.
