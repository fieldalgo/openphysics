# Contributing

OpenPhysics is under active development. Start with the [package overview](README.md)
and [implementation and validation contracts](docs/README.md). The `main`
branch is the only trunk and the default branch; target pull requests there. Feature branches may contain work that has not passed acceptance.

Reports of suspected bugs, accuracy questions, research questions and proposed
changes are welcome. Search existing issues first and use the closest issue form.
Include available observations, the exact release/commit, Python/platform versions
and expected behavior; mark missing evidence honestly. A complete reproducer or
confirmed defect is helpful but is not required to open an issue. Distinguish
main behavior from a PR-only candidate. Remove credentials, personal information
and confidential models before attaching files. Report vulnerabilities through the private
channel in [SECURITY.md](SECURITY.md).

Install and run from the repository root as described in [README.md](README.md).
Use [validation guide](ci/docs/README.md) for the pinned Linux validation environment,
optional tools and data, and isolated distribution checks. GitHub Actions runs on main pushes, Ready pull requests and explicit manual dispatch. Review the exact
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

`main` is the only trunk and the default branch. Create a feature branch from
current `origin/main`, push it and open a pull request targeting `main`. Preserve
shared or submitted history; use a new branch if replaying it is necessary.
Every change, including documentation, requires the `tests` completion check
(Linux source, distributions, Studio and all three installed-platform checks)
and `windows-py312-thermal` from GitHub Actions. Review the exact candidate's logs and artifacts, not only its badge.

Land green PRs through GitHub **Rebase and merge**. Direct pushes, merge commits,
squash merges, force pushes and deleting main are blocked. No approving review
is required. GitHub replays the commits onto current main with new commit IDs;
record the landed main SHA. Only conflicting PRs require manual rebasing and
another validation run. There is no merge queue or pre-landing rerun of the
combined state. Main push runs validate that state and must not be cancelled by
later pushes; branch/PR runs may be superseded. Investigate failed main validation
and fix or revert through a PR before releasing that state.
Merged feature branches are deleted automatically; preserve any remaining work
on a separate branch before merging.

Combine work in one temporary branch only when changes depend on each other or
conflict. There is no permanent integration branch. To release, land the version
change through the same PR process, then wait for successful required checks on
the resulting main commit before tagging it `vX.Y.Z` and publishing release notes
and verified artifacts. Branch updates alone never publish packages. Automated
PyPI/documentation publication is not configured in this repository; release
credentials and publication gates require separate setup. Create
`maintenance/X.Y.x` from a released tag only when that release needs a patch,
and carry reviewed fixes from main.

## Repository structure and agent entry points

The six implementation packages retain separate distribution names, metadata,
licenses and notices. Third-party integrations belong in a separate package with
an explicit API and documented external dependencies, following `gmshio`.
Run Python from the repository root, not inside `packages/`: package directory
names can shadow installed imports and produce empty namespace packages.

This guide and the implementation/validation documents hold the shared contributor
contract. `AGENTS.md` contains short navigation, essential commands and technical
pitfalls; `CLAUDE.md` imports it. Keep personal preferences, account settings, private
paths, session coordination and operational history outside the public repository.
