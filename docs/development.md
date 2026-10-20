# Development and validation

**English** | [한국어](locales/ko/pages/development.md)

How to set up a development environment, run the checks CI runs, and read CI
results. Branch, review and release flow is in [contributing](contributing.md).
Each feature's acceptance criteria and evidence are in its own contract and
validation documents, listed in the [documentation index](README.md).

## Environment

CI pins Python 3.12.14 and Node.js 24.19.0 on Ubuntu 24.04. From the repository
root, in a Python 3.12 virtual environment:

```bash
python -m pip install -r ci/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pip check
```

`ci/requirements-py312-linux.txt` pins the validation tools and their transitive
dependencies, not the packages' runtime requirements. Update pins deliberately
in a reviewed change and rerun the source and distribution checks. Package
metadata declares Python >=3.10; Python 3.10 and 3.11 are not tested in CI.

Always run from the repository root: running Python inside `packages/` or
`tests/` can shadow installed modules with directories of the same name.

Optional tools and data:

- **Gmsh**: mesh generation needs `gmsh` on PATH (Linux also needs the system
  libraries the workflow installs). It is a separate process and is not bundled.
- **refractiveindex.info database**: `ci/rii-revision.txt` pins a full commit of
  [polyanskiy/refractiveindex.info-database](https://github.com/polyanskiy/refractiveindex.info-database).
  `python ci/fetch_rii.py <dir>` fetches exactly that commit and rejects a dirty
  or different cache. Set `PHYSMAT_RII_PATH=<dir>/database`; an explicitly set
  but invalid path fails the two database tests instead of skipping them. The
  data is CC0 1.0, stays outside the source tree and is not shipped. Citation:
  M. N. Polyanskiy, *Refractiveindex.info database of optical constants*,
  Scientific Data **11**, 94 (2024), https://doi.org/10.1038/s41597-023-02898-2.
- **Chrome or Chromium**: the installed Studio browser check uses an already
  installed browser. If none is found, the check fails; it is never skipped.

## Repository layout

Each package keeps its code, examples and docs in `packages/<name>/`. Its tests
are outside the package, in `tests/<import name>/`, so nothing a test uses can
enter a distribution:

| Package | Tests |
|---|---|
| `packages/galerkin` | `tests/galerkin/` |
| `packages/galerkin-refsol` | `tests/refsol/` |
| `packages/meshine` | `tests/meshine/` |
| `packages/gmshio` | `tests/gmshio/`, with its `.geo`/`.msh` fixtures in `tests/gmshio/data/` |
| `packages/physmat` | `tests/physmat/` |
| `packages/simcase` | `tests/simcase/`, including the Studio JavaScript checks (`*.cjs`) |

The empty `openphysics` name reservation has no tests. From the root,
`python -m pytest` collects `tests/` and `ci/tests/` (`testpaths` in the root
`pyproject.toml`, which also declares the `slow` marker). The root `conftest.py`
puts this checkout's packages first on the import path.

To run one package's tests, from the repository root:

```bash
python -m pytest -q tests/galerkin                 # one package
python -m pytest -q tests/galerkin -m "not slow"   # without convergence studies
python -m pytest -q tests/gmshio/test_msh.py       # one file
node --test tests/simcase/*.cjs                    # Studio JavaScript checks
```

## Running the checks

```bash
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -q -ra                    # full source suite
node --test tests/simcase/*.cjs            # Studio JavaScript checks
python ci/check_distributions.py           # build, inspect and install all packages
python ci/run_installed_tests.py           # every Python test in tests/ against installed wheels
python ci/check_licenses.py                # installed licenses vs. the reviewed inventory
python ci/check_markdown_links.py          # relative links and #anchors in all Markdown files
```

For a quick loop, run the tests related to your change and leave the full suite
to CI. Tests marked `slow` (mesh-convergence studies) are included in the full
run; `-m "not slow"` skips them locally. A subset pass does not replace CI.

Output directories of the CI scripts must be new or empty, so results from an
earlier run cannot mix in. `check_distributions.py` writes to `.validation/dist/`
and `run_installed_tests.py` to `.validation/installed/`, unless `--output` names
another directory.

The installed-package check runs on any OS from a clean Python 3.12 environment:

```bash
python -m pip install -r ci/requirements-py312-windows-thermal.txt
python -X utf8 ci/tools/check_platform_install.py
```

The requirements file's historical name does not limit it to Windows.

## What CI runs

The `Validate packages` workflow (`.github/workflows/validate.yml`) runs on main
pushes, Ready pull requests and manual dispatch. Branch pushes and draft PRs do
not run it. It has four parts, run in parallel:

| Job | Platform | What it checks |
|---|---|---|
| `linux-py312` | Ubuntu 24.04 | Markdown link check, fast preflight groups, then the full source suite with the pinned RII database; all seven distributions; Studio Node checks; one Studio resource observation |
| `installed-tests` | Ubuntu 24.04 | Every Python test in `tests/` against all seven wheels, built from sdists and installed with all their extras outside the checkout |
| `blas-kernels` | Ubuntu 24.04, two jobs | Numerically sensitive tracking, eigenspace, fiber-reference and length-unit independence tests under two forced OpenBLAS kernels |
| `installed-platforms` | Ubuntu 24.04, macOS 14, Windows 2022 | Six packages built from sdists into wheels and tested in a fresh environment outside the checkout |

The single required check is **`tests`**. It passes only when all four parts
succeed; a failed, cancelled or skipped part fails it. Every change, including
documentation, needs it.

**Linux job.** After the license check, a Markdown link check runs: every relative link and
`#anchor` in the repository's tracked Markdown files must resolve (external URLs
are not fetched). Preflight groups (steady boundary, transient documents, steady
and transient Studio, transient thermomechanics) run next so a broken
contract fails within minutes. The full suite then runs everything again. The
distribution and Node steps still run after a failed source suite so their
evidence is kept, but the job stays failed. The job usually takes 16 to 22
minutes; its 45-minute limit only stops hung runs, since hosted runner speed
varies.

**Distribution checks** (`ci/check_distributions.py`). Builds all seven packages
(including the empty `openphysics` name reservation), each wheel from its sdist,
with pinned build tools, and checks metadata with `twine check --strict`.
Distributions ship package code only. Each sdist holds exactly its import
package, `README.md`, `LICENSE`, `NOTICE` and build files (`pyproject.toml`,
`setup.py`, `MANIFEST.in`, and the generated `PKG-INFO`, `setup.cfg` and
egg-info); each wheel holds exactly its import package and dist-info, with
`LICENSE` and `NOTICE` under `.dist-info/licenses/`. Docs, examples and tools
stay in `packages/<name>/` and are never shipped (every `MANIFEST.in` prunes
them); tests are in the root `tests/` folder. The expected contents come from
the Git-tracked files of `packages/<name>/`, not from a hand-written list: every
tracked file of the import package, and in the sdist each tracked top-level file
above, must be present and byte-identical to the checkout, `LICENSE` and
`NOTICE` included. Any other file in an archive fails the check, as does a
tracked top-level file or folder of `packages/<name>/` the checker does not
know, such as a `tests/` folder.

Wheels are then installed into a fresh environment outside the checkout. Every
shipped module (except `__main__`) and Studio static file must load from that
environment with the checked-out bytes. This check does not run the pytest
suites in `tests/`; `installed-tests` runs them. It runs the wheel-specific
consumers (`ci/test_*_wheel.py`), selected galerkin and simcase examples and the
independent acceptance consumers, which exercise the public API, CLI and saved
files. They are copied from the checkout's tracked files to a temporary
directory outside it (their hashes are recorded in `consumer-file-hashes.json`)
and run with `python -I` against the installed wheels, so the checkout cannot
leak in. The installed environment must pass `ci/check_licenses.py`. The Studio
Node checks run against the installed Studio files, and the Studio browser check
runs a small real model in Chrome. Finally
`ci/tools/audit_distribution_artifacts.py` re-checks the retained archives'
checksums and their exact sdist and wheel contents.

**Installed tests** (`ci/run_installed_tests.py`). Builds every package, each
wheel from its sdist, and checks the archives with the same rules as the
distribution check. All seven wheels are installed, each with every extra its
metadata declares, into a fresh environment in a temporary directory outside the
checkout. Next to it, the script copies the tracked files under `tests/`,
`packages/*/examples/` and `packages/*/docs/` and the root `pyproject.toml`, but
no package code; their hashes are recorded in `suite-file-hashes.json`. Every
Python test in `tests/` then runs with `python -I -m pytest`; no test is
selected by name. Besides any failing test, the run fails if a first-party
module does not load from the installed environment, if any test is skipped or
xfailed, or if a test file (`test_*.py`, `*_test.py`) produced no results. The installed environment must
also pass `ci/check_licenses.py`. The job uses the pinned requirements, Gmsh,
the pinned RII database and required reference cross-checks
(`OPENPHYSICS_REQUIRE_CROSSCHECK=1`). A local Linux run took about 25
minutes; the 50-minute limit only stops hung runs. Running it locally needs Gmsh
and `PHYSMAT_RII_PATH`, because tests that need them skip otherwise and a skip
fails the run. It is verified on Linux only. The source suite still runs in
`linux-py312`.

**Licenses** (`ci/check_licenses.py`). Before the tests, the pinned validation
environment, and later each fresh installed environment, is compared with the
reviewed inventory in `ci/third_party_licenses.json`: declared licenses, and
every shared library a third-party wheel installs, file by file, on each OS.
Policy and the full list are in [third-party software](third-party.md).

**Installed platforms** (`ci/tools/check_platform_install.py`). On each OS:
installed licenses, package bytes, installed module origins, bundled assets, public API/CLI/save
smoke tests, the heat save/I-O robustness tests (partial-failure cleanup,
simultaneous writers, existing targets) and two source target-protection
fixtures. This is installed acceptance, not a full macOS or Windows regression.

**Resource observations.** After a green Linux run, the steady and transient
Studio servers are measured once with fixed workloads. These are observations,
not performance gates. Timing and profiling commands for the solvers are in the
[vector](benchmark_vector.md) and [cavity](benchmark_cavity.md) benchmark guides.

**Queueing.** Main runs share one concurrency group per workflow with
`queue: max` and are never cancelled by a newer push. Other refs use
`queue: single`, so a new push supersedes the older run.

## Reading results

Each job uploads its artifacts, even after a failure:

- Linux: `distributions-and-test-results`, the `.validation/` directory with
  JUnit XML per stage, distribution checksums and reports, and
  `numeric-runtime.json`.
- Installed tests: `installed-test-results`, the `.validation/` directory with
  the built distributions, `installed-tests.xml`, `installed-origins.json`,
  `suite-file-hashes.json`, the license report and the cross-check records.
- Installed platforms: `installed-packages-<os>-<run_id>` with every command's
  exit and log, environment details, checksums, installed origins, JUnit XML and
  `numeric-runtime.json`.

Some stages store the stdout of passing tests in JUnit `system-out`
(`-o junit_logging=all -o junit_log_passing_tests=true`). This keeps numerical
diagnostics printed by passing tests.

Configured checks are not evidence. Before stating that a commit passed,
check that commit's own runs, counts, skips and artifacts. A result on one OS
says nothing about another.

## Numerical reproducibility

Hosted runners are fresh virtual machines whose CPU model changes between runs.
numpy's bundled OpenBLAS picks its kernel from the CPU, so last-bit results can
differ for the same commit, pins and seeds, even with one thread.

- `ci/tools/report_numeric_runtime.py` records the CPU model, the OpenBLAS kernel
  and `numpy.show_runtime()` in each job (`numeric-runtime.json`). macOS arm64
  uses Accelerate, so no OpenBLAS kernel is reported there.
- `blas-kernels` forces `OPENBLAS_CORETYPE=Haswell` (AVX2, also the kernel used
  on AMD Zen) and `Sandybridge` (AVX). It first confirms the forced kernel is
  active, so a fallback cannot pass silently. To reproduce locally:

  ```bash
  OPENBLAS_CORETYPE=Sandybridge python -m pytest -q -m "not slow" <test files>
  ```

Write tests that do not depend on last-bit rounding: compare with explicit
tolerances well clear of roundoff, never exactly at a boundary roundoff can reach.
An exact comparison is sound only when it follows from identical inputs to the
same code on one machine, as in `tests/simcase/test_length_canonical.py` (the
same mesher input in nm, um and m); say why in the test.

## Publishing

No workflow publishes to PyPI, and tags trigger nothing. Before a release, choose
the package and version, check that the version is not already on PyPI, validate
the exact main commit, and set up that PyPI project's trusted publisher for an
explicitly reviewed publishing workflow and GitHub environment. Each package
builds from `packages/<name>`; the repository root is not a distribution and the
`openphysics` reservation is not an umbrella installer. A build-only check for one
package:

```bash
python -m build --no-isolation --outdir .validation/simcase packages/simcase
python -m twine check --strict .validation/simcase/*
```

The README is also the PyPI description, but its links are relative to the
package directory and would break there. Each package's `setup.py` therefore
stores a copy of the README with the links rewritten to GitHub URLs pinned to
one revision (links to `blob/<ref>/…`, images to raw files); `README.md` itself
is unchanged. The revision is `OPENPHYSICS_DOCS_REF` if set, otherwise the
checkout's commit. For a release, build with the tag that will be pushed, so the
description points at the released files:

```bash
OPENPHYSICS_DOCS_REF=v0.2.0 python -m build --no-isolation --outdir .validation/simcase packages/simcase
```

A wheel built from an unpacked sdist reuses the sdist's description.
`ci/test_readme_links.py` checks that the seven `setup.py` files are identical
and that no relative link is left in any package description.
