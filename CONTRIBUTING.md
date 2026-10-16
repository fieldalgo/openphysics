# Contributing

**English** | [한국어](CONTRIBUTING.ko.md)

OpenPhysics is under active development. Start with the [package overview](README.md)
and [implementation and validation contracts](docs/README.md). The `develop`
branch is the integration branch and the default branch; target pull requests
there. Feature branches may contain work that has not passed acceptance.

Open an issue for a reproducible bug or a proposed change. Include the commit,
Python and platform versions, input units, a minimal example, and the expected
and actual results. Remove credentials, personal information and confidential
models before attaching files. Report vulnerabilities through the private
channel in [SECURITY.md](SECURITY.md).

Install and run from the repository root as described in [README.md](README.md).
Use [ci/README.md](ci/README.md) for the pinned Linux validation environment,
optional tools and data, and isolated distribution checks. GitHub Actions is
currently disabled; do not enable or dispatch workflows as part of a contribution.
Record the exact commands, exits, failures and optional skips from your own checks.

Physics changes need independent analytical references and mesh-convergence
checks. Preserve existing numerical thresholds and report limitations. Keep
production code, comments, APIs and executable examples in English; update
complete English and Korean usage and validation documents together. A passing
subset or a documentation change does not establish new platform support.

Keep changes focused. Do not commit credentials, generated build directories,
local environment files or private research material. Preserve upstream notices
and verify the terms and provenance of any added dependency, data or copied code.
Contributions are submitted under the repository's [Apache-2.0 license](LICENSE),
with third-party exceptions recorded in [NOTICE](NOTICE) and package notices.
