# Contributing

**English** | [한국어](locales/ko/pages/contributing.md)

OpenPhysics is under active development. Start with the [package overview](overview.md)
and the [documentation index](README.md). The [development guide](development.md)
covers the environment, the checks and how to read CI results.

## Reporting issues and asking questions

Reports of suspected bugs, accuracy questions, research questions and proposed
changes are welcome. Search existing issues first and use the closest issue form.

- Include the observations you have, the exact release or commit, Python and
  platform versions, and the expected behavior. Mark missing evidence honestly.
- A complete reproducer or confirmed defect is helpful but not required.
- Say whether the behavior is on `main` or only in a pull-request candidate.
- Remove credentials, personal information and confidential models before
  attaching files.

Report vulnerabilities through the private channel in [SECURITY.md](security.md).

## Making a change

Install and run from the repository root as described in the [overview](overview.md).
Run Python from the root, not inside `packages/`: package directory names can
shadow installed imports and produce empty namespace packages. Run the checks
related to your change and record the exact commands, exits, failures and
optional skips; a passing subset does not replace the required CI check.

- **Physics.** New or changed physics needs independent analytical references and
  mesh-convergence checks. Preserve existing numerical thresholds and report
  limitations.
- **Language.** Keep production code, comments, APIs and executable examples in
  English. Update English and Korean usage and validation documents under `docs/`
  together. Repository READMEs and the contribution and security entry points stay
  English.
- **Platforms.** Keep file paths, temporary directories, subprocesses and cleanup
  portable. A passing subset or a documentation change does not establish new
  platform support, and a pass on one OS or a universal wheel says nothing about
  another OS.
- **Scope.** One topic per PR. Changes on the same topic go in one PR, each as its
  own self-contained commit; unrelated changes go in separate PRs. The test is
  whether a later reader -- a person or an agent -- can follow what changed and
  why from the PR and its commits, not how many CI runs it takes. Do not commit
  credentials, generated build directories, local environment files or private
  research material.
- **Licensing.** Preserve upstream notices and verify the terms and provenance of
  any added dependency, data or copied code against the policy in
  [third-party software](third-party.md), including what its wheels bundle.
  Contributions are submitted under the repository's [Apache-2.0 license](../LICENSE),
  with third-party exceptions recorded in [NOTICE](../NOTICE) and package notices.

## Pull requests and landing

`main` is the only trunk and the default branch. Feature branches may contain
work that has not passed acceptance.

1. Create a feature branch from current `origin/main` and open a pull request
   targeting `main` as a **draft**. Branch pushes and draft PRs run no validation.
2. After reviewing the change and running relevant checks, mark it **Ready for
   review**. Validation runs on Ready PRs, main pushes and explicit manual dispatch.
3. Every change, including documentation, needs the required **`tests`** check.
   Review the exact run's logs and artifacts, not only its badge. The
   [development guide](development.md#what-ci-runs) lists what it covers.
4. Land green PRs with GitHub **Rebase and merge**; enable it as automatic merge
   only after review and relevant validation, with every required check kept. No
   approving review is required. Direct pushes, merge commits, squash merges,
   force pushes and deleting `main` are blocked.
5. GitHub replays the commits onto current `main` with new commit IDs; record the
   landed `main` SHA. Only conflicting PRs need a manual rebase and another
   validation run. There is no merge queue or pre-landing rerun of the combined
   state: the `main` push run validates it and is never cancelled by later pushes.
   Investigate a failed `main` run and fix or revert it through a PR before
   releasing that state.

Merged feature branches are deleted automatically; keep any remaining work on a
separate branch before merging. Preserve shared or submitted history; use a new
branch if replaying it is necessary. Combine work in one temporary branch only
when changes depend on each other or conflict; there is no permanent integration
branch.

**Ported work.** When a commit lands work first written in another commit
(replayed onto a new base, rewritten, squashed before submission or ported by
another contributor), name each original in the commit or PR body with one
`Ports: <sha>` line, without private branch names or paths. A PR's own commits
landed by Rebase and merge need no such line. A commit that is not an ancestor
of `main` may still have landed under a new ID: check `Ports:` lines, the PR
record or the behavior on `main` before reporting it missing.

## Releases

All nine distributions share one version. The version change sets it in every
package, keeps the requirements between them inside that minor series and dates
the [changelog](../CHANGELOG.md)'s `[Unreleased]` section; `tools/check_release_version.py`
checks it. Land the version change through the same PR process, wait for the required
checks on the resulting `main` commit, then tag it `vX.Y.Z` and publish release
notes and verified artifacts. Build release artifacts with `OPENPHYSICS_DOCS_REF` set
to that tag so the PyPI description links to the released files (see the
[development guide](development.md#publishing)). Branch updates and tags alone never publish
packages: publishing the GitHub release starts the `Release` workflow, which
uploads to PyPI only after the release commit's validation has passed. Run it by
hand on `main` first as a dry run; it then uploads nothing. Documentation is not
published automatically. Create `maintenance/X.Y.x` from a released
tag only when that release needs a patch, and carry reviewed fixes from `main`.

## Repository structure

The eight implementation packages keep separate distribution names, metadata,
licenses and notices. Third-party integrations belong in a separate package with
an explicit API and documented external dependencies, following `gmshio`. A GPL
program can back such an integration only as a separate process, installed through
an optional extra (as `gmshio[gmsh]` installs Gmsh): it is never imported, linked or
bundled.

This guide and the implementation and validation documents hold the shared
contributor rules. `AGENTS.md` holds short navigation, essential commands and
technical pitfalls; `CLAUDE.md` imports it. Keep personal preferences, account
settings, private paths, session coordination and operational history outside
the public repository.
