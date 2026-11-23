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
rustup toolchain install 1.97.0 --profile minimal --component rust-src
python -m pip install -r tools/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/meshloom \
  -e packages/gmshio -e packages/physmat -e packages/simcase -e packages/sipi
python -m pip check
```

`meshloom` is the one package with compiled code. Its editable install builds the
Rust kernel with maturin (pinned in the requirements) and the toolchain of
`packages/meshloom/rust-toolchain.toml`, and places the extension next to its
sources, where the tests import it. Without a build, `tests/meshloom` skips. After
changing `Cargo.lock` or the toolchain, regenerate the license notices with
`python tools/build_meshloom_notices.py`; CI checks them with `--check`.

`tools/requirements-py312-linux.txt` pins the validation tools and their transitive
dependencies, not the packages' runtime requirements. Update pins deliberately
in a reviewed change and rerun the source and distribution checks. Package
metadata declares Python >=3.12; CI tests Python 3.12 only. The lower bounds
numpy 1.26, scipy 1.11.2, shapely 2.0.2 and matplotlib 3.8 are the first
releases with Python 3.12 wheels. The non-slow suite passed on exactly those
versions once, by hand (2026-10-21, Linux, Python 3.12); CI tests only the pins.

The optional array libraries for `galerkin[jax]` and `galerkin[torch]` are pinned
separately. CI installs the CPU build of torch first, because the PyPI Linux
wheel pulls CUDA packages:

```bash
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu
python -m pip install -r tools/requirements-py312-linux-backends.txt
```

Without them the JAX and PyTorch cases of the backend tests skip; the Linux CI
job checks that both import before it runs the suite, and the installed-wheel
run fails on any skip. The array-api-compat floor 1.15 was checked once by hand
with `tests/galerkin/test_core_backend.py` (2026-10-26, Linux, NumPy and JAX).

Always run from the repository root: running Python inside `packages/` or
`tests/` can shadow installed modules with directories of the same name.

Optional tools and data:

- **Gmsh**: mesh generation needs `gmsh` on PATH (Linux also needs the system
  libraries the workflow installs). It is a separate process and is not bundled.
- **refractiveindex.info database**: `tools/rii-revision.txt` pins a full commit of
  [polyanskiy/refractiveindex.info-database](https://github.com/polyanskiy/refractiveindex.info-database).
  `python tools/fetch_rii.py <dir>` fetches exactly that commit and rejects a dirty
  or different cache. Set `PHYSMAT_RII_PATH=<dir>/database`; an explicitly set
  but invalid path fails the two database tests instead of skipping them. The
  data is CC0 1.0, stays outside the source tree and is not shipped. Citation:
  M. N. Polyanskiy, *Refractiveindex.info database of optical constants*,
  Scientific Data **11**, 94 (2024), https://doi.org/10.1038/s41597-023-02898-2.
- **Chrome or Chromium**: the installed Studio browser check uses an already
  installed browser. If none is found, the check fails; it is never skipped. The workspace,
  multiphysics and multiphysics session scripts start it through
  `tools/studio_browser/browser_launch.mjs`: they wait up to 60 s for its DevTools endpoint to list
  a page and, when it does not, stop it and start it once more on a new port with a new profile
  directory. Every failed attempt is recorded in `report.json` (`browserLaunch`: the command line,
  the exit code or signal and the last 4000 characters of stderr), and a second failure fails the
  check. Only the launch is retried, never a Studio stage; `tests/simcase/studio_browser_launch.cjs`
  checks this with a fake browser.

The source Studio Node step runs every `tests/simcase/*.cjs` contract, including
the experimental workspace. Distribution validation additionally copies the
`studio_workspace_*.cjs` tests and checks them against verified installed static bytes.

## Repository layout

`packages/<name>/` holds what the distribution `<name>` ships and nothing else:
`pyproject.toml`, `setup.py`, `README.md`, `LICENSE`, `NOTICE` and the import
package in a src layout, `packages/<name>/src/<import name>/`. Tests, examples,
package docs and tools live at the repository root, so nothing they use can
enter a distribution:

| Package | Code | Tests | Examples |
|---|---|---|---|
| `packages/galerkin` | `src/galerkin/` | `tests/galerkin/` | `examples/galerkin/` |
| `packages/galerkin-refsol` | `src/refsol/` | `tests/refsol/` | `examples/galerkin-refsol/` |
| `packages/meshine` | `src/meshine/` | `tests/meshine/` | `examples/meshine/` |
| `packages/meshloom` | `src/meshloom/` (Python), `rust/` (kernel) | `tests/meshloom/` | — |
| `packages/gmshio` | `src/gmshio/` | `tests/gmshio/`, with its `.geo`/`.msh` fixtures in `tests/gmshio/data/` | `examples/gmshio/` |
| `packages/physmat` | `src/physmat/` | `tests/physmat/` | `examples/physmat/` |
| `packages/sipi` | `src/sipi/` | `tests/sipi/` | `examples/sipi/` |
| `packages/simcase` | `src/simcase/`, with the Studio static files in `src/simcase/studio/static/` | `tests/simcase/`, including the Studio JavaScript checks (`*.cjs`) | `examples/simcase/` (JSON documents, and `gallery.py`, which draws `docs/gallery/`) |

Each package's pages (contracts and validation reports) are in
`docs/packages/<name>/`, with the Korean pages in
`docs/locales/ko/pages/packages/<name>/`. `tools/` holds the repository checks,
the pinned validation environments, the reviewed license inventory and
maintainer scripts such as `tools/build_physmat_tables.py`, which regenerates
physmat's embedded tables; [tools/README.md](../tools/README.md) says which of
them required CI runs. `physmat/unit_tables.json` is generated from
`physmat/quantities.json` by `python -m physmat.units --write` (`--check`
compares); the generator ships in the package, so that
`tests/physmat/test_units.py` (R3) checks it against installed wheels too. [benchmarks/](../benchmarks/README.md) holds timing benchmarks and
[studies/](../studies/README.md) diagnostic scripts; people run them and
required CI does not. The `openphysics` meta distribution has no code, tests or examples; it requires seven packages (`simcase` with its `studio` and `export` extras, `physmat` with `rii`) and provides the `openphysics` command, which opens Studio.
From the root, `python -m pytest` collects `tests/` and `tools/tests/`, the tests
of the tools (`testpaths` in the root
`pyproject.toml`, which also declares the `slow` marker). The root `conftest.py`
puts each package's `src/` folder first on the import path, so the tests use
this checkout's code.

To run one package's tests, from the repository root:

```bash
python -m pytest -q tests/galerkin                 # one package
python -m pytest -q tests/galerkin -m "not slow"   # without convergence studies
python -m pytest -q tests/gmshio/test_msh.py       # one file
node --test tests/simcase/*.cjs                    # Studio JavaScript checks
```

**API units scan.** `tests/galerkin`, `tests/refsol` and `tests/physmat` each run
`test_api_units_scan_<package>.py`, which checks every parameter of the public API (the
`__all__` of the public modules) against the units convention. A parameter is either a
`physmat.units` registry name with an `api` place, keyword-only and without a dimensional
default, or a structural name, and no name ends in a unit token. Public methods include
`__call__`; the constructors of the result classes that solvers return are not scanned.
The shared logic and its data are in `tests/_support/`: `api_scan.py`, the public and
internal module lists, the closed lists of structural names and result classes, and the
removed names. Every other module is internal and says "Internal module, consistent
units" in its docstring. Each package's `api_units_allowlist.json` is empty and may
not grow: a new violation fails. So every public module is clean: every name
of the removed-name list is asserted absent, and a `str` given to any public quantity
parameter must raise `TypeError`. A removed name with a scope (and a note that
says why) is asserted absent only in those modules: `refsol.bent_slab` no longer takes
`radius` (now `bend_radius`), while `refsol.fiber` takes the registry name `radius`.
`galerkin.kernels` and `physmat.kernels` are
internal namespaces that re-export kernels in consistent units for simcase and sipi: no
public name equals one of their names, and no public name is one of their objects. A structural name added after the list was frozen
carries a reviewer note; the category "deferred to the materials step" (physmat's record
arguments, such as `datum_temperature`) also names the condition that ends it.

**Complex conventions.** Public complex values of galerkin and refsol follow
exp(−iωt); a kernel that computes in exp(+iωt) is converted only by `to_kernel` and
`to_public` of the package's private `_conventions` module.
`tests/galerkin/test_conventions.py` reads the package code of galerkin, refsol and
simcase (not sipi, not the tests) and allows a conjugation (`conj`, `conjugate`, or
`0.0 - x.imag` and `-x.imag`) only there, in simcase's boundary functions, and on the
closed list `tests/galerkin/conventions_allowlist.json` of mathematical conjugations,
each with its function, source line and reason; an entry that no longer matches fails.
It also checks the passive signs of each converted output (electrostatics so far) and
that a JAX and a PyTorch gradient pass through the conversions.

## Running the checks

```bash
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -q -ra                    # full source suite
node --test tests/simcase/*.cjs            # Studio JavaScript checks
python tools/check_distributions.py        # build, inspect and install all packages
python tools/run_installed_tests.py        # every Python test in tests/ against installed wheels
python tools/check_licenses.py             # installed licenses vs. the reviewed inventory
python tools/check_markdown_links.py       # relative links and #anchors in all Markdown files
python tools/check_release_version.py      # one version across the nine distributions
python tools/changelog.py --check          # changelog fragments in changelog.d/
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
python -m pip install -r tools/requirements-py312-windows-thermal.txt
python -X utf8 tools/check_platform_install.py
```

The requirements file's historical name does not limit it to Windows. Its last step,
the installed Studio workspace browser check, needs Node 22 or newer on `PATH` and a
preinstalled Chrome, Chromium or Edge (found in the usual places, or named by
`CHROME_PATH`); without them the check fails rather than skips.

## What CI runs

The `Validate packages` workflow (`.github/workflows/validate.yml`) runs on main
pushes, Ready pull requests and manual dispatch. Branch pushes and draft PRs do
not run it. It has five parts, run in parallel:

| Job | Platform | What it checks |
|---|---|---|
| `linux-py312` | Ubuntu 24.04 | License, release-version, changelog fragment, meshloom kernel and Markdown link checks; fast preflight groups; all nine distributions; Studio Node checks; one steady, transient and region Studio resource observation each |
| `linux-py312-tests` | Ubuntu 24.04, eight jobs | The full source suite with the pinned RII database, in eight time-balanced parts run at the same time |
| `installed-tests` | Ubuntu 24.04, eight jobs | Every Python test in `tests/` against all nine wheels, built from sdists and installed with all their extras outside the checkout, in eight time-balanced parts run at the same time |
| `blas-kernels` | Ubuntu 24.04, two jobs | Numerically sensitive tracking, eigenspace, material-cavity (complex dense and sparse eigensolves), fiber-reference and length-unit independence tests under two forced OpenBLAS kernels |
| `installed-platforms` | Ubuntu 24.04, macOS 15, Windows 2022 | Eight packages built from sdists into wheels and tested in a fresh environment outside the checkout |

The single required check is **`tests`**. It passes only when all five parts
succeed (all eight jobs of each split part among them); a failed, cancelled or skipped part fails it. Every change, including
documentation, needs it.

**Linux job.** After the license check, `tools/check_release_version.py` checks that
the nine distributions share one version (see [Publishing](#publishing)) and
`tools/changelog.py --check` checks the [changelog fragments](#changelog-fragments), then a
Markdown link check runs: every relative link and
`#anchor` in the repository's tracked Markdown files must resolve (external URLs
are not fetched; fragment links are resolved by the fragment check). Preflight groups (steady boundary, transient documents, steady
and transient Studio, transient thermomechanics) run next so a broken
contract fails within minutes. The distribution checks, the Studio Node checks
and the resource observations follow. Without the source suite the job took 8 to
11 minutes on 2026-11-20; its 45-minute limit only stops hung runs, since hosted
runner speed varies.

**Source tests** (`linux-py312-tests`). The whole suite, `python -m pytest` with
the root configuration (every test in `tests/` and `tools/tests/`), runs in eight
jobs at once. Each job collects the whole suite and keeps the test files that
`tools/shards/openphysics_shard.py` assigns to its part: whole files, largest
first, each to the part with the least time so far, by the per-file seconds in
`tools/shards/durations.json` (a file missing from the table counts as the
median). Every part computes the same assignment from the same collected files,
so together the eight run every collected test exactly once; no test is
selected by name. The end of each log names the part's files, tests and
estimated time. On one job the suite took 44 to 70 minutes on 2026-11-20,
depending on the runner CPU, and its four parts 10 to 21 minutes on 2026-11-21;
a part of eight is about 5.5 minutes of tests by the table plus about 3 minutes
of setup, and its 45-minute limit only stops hung runs. Since files are
assigned whole, the largest file is a part's floor
(`tools/tests/test_examples_smoke.py`, 5.7 minutes, whose examples run in an
order that the file keeps); the 5.5-minute M3 slab refinement study has its own
file (`tests/galerkin/test_cavity_mesh_slab_refinement.py`) for this reason. To
run a part locally:

```bash
PYTHONPATH=tools/shards python -m pytest -q -p openphysics_shard --shard 2/8
```

When the suite's balance drifts, rebuild the table from the JUnit files of one
complete run (the eight `source-tests-<k>-of-8` artifacts, unpacked in one
folder), from the repository root:

```bash
python tools/shards/openphysics_shard.py --update source-tests-*.xml --source "Validate packages run <id> (main <sha>)"
```

**Distribution checks** (`tools/check_distributions.py`). Builds all nine packages
(including the `openphysics` meta distribution), each wheel from its sdist,
with pinned build tools, and checks metadata with `twine check --strict`.
Distributions ship package code only. Each sdist holds exactly its import
package under `src/`, `README.md`, `LICENSE`, `NOTICE` and build files
(`pyproject.toml`, `setup.py`, and the generated `PKG-INFO`, `setup.cfg` and
egg-info); each wheel holds exactly its import package, at the top level, and
dist-info, with `LICENSE` and `NOTICE` under `.dist-info/licenses/`. Tests,
docs, examples and tools are outside `packages/`, so no package needs a
`MANIFEST.in`. The expected contents come from the Git-tracked files of
`packages/<name>/`, not from a hand-written list: every tracked file under
`src/` (in the sdist at `src/<import name>/…`, in the wheel at
`<import name>/…`), and in the sdist each tracked top-level file above, must be
present and byte-identical to the checkout, `LICENSE` and `NOTICE` included.
Any other file in an archive fails the check, as does any other tracked file or
folder in `packages/<name>/` (only `.gitignore` is allowed besides the files
above and `src/`), such as a `tests/` or `docs/` folder, or anything in `src/`
that is not an import package.

Wheels are then installed into a fresh environment outside the checkout. Every
shipped module (except `__main__`) and Studio static file must load from that
environment with the checked-out bytes. This check does not run the pytest
suites in `tests/`; `installed-tests` runs them. It runs the wheel-specific
consumers (`tools/wheel_consumers/test_*_wheel.py`), selected galerkin and
simcase examples and the independent acceptance consumers, which exercise the
public API, CLI and saved files. They are copied from the checkout's tracked files to a temporary
directory outside it (their hashes are recorded in `consumer-file-hashes.json`)
and run with `python -I` against the installed wheels, so the checkout cannot
leak in. The installed environment must pass `tools/check_licenses.py`. The
Studio Node checks run against the installed Studio files, and the Studio browser check
runs small real models in Chrome: a steady and a transient rectangle document,
then the shipped steady and transient region examples (region colours, legend,
region table and hover). Finally
`tools/audit_distribution_artifacts.py` re-checks the retained archives'
checksums and their exact sdist and wheel contents.

**Installed tests** (`tools/run_installed_tests.py`). Builds every package, each
wheel from its sdist, and checks the archives with the same rules as the
distribution check. All nine wheels are installed, each with every extra its
metadata declares, into a fresh environment in a temporary directory outside the
checkout. Next to it, the script copies the tracked files under `tests/`,
`examples/` and `docs/`, the units batch's fixture documents
(`tools/units_batch/fixtures/`, JSON data the tests read) and the root
`pyproject.toml`, but nothing under `packages/` and no other file under `tools/`;
their hashes are recorded in `suite-file-hashes.json`. Every
Python test in `tests/` then runs with `python -I -m pytest`; no test is
selected by name. Besides any failing test, the run fails if a first-party
module does not load from the installed environment, if any test is skipped or
xfailed, or if a test file (`test_*.py`, `*_test.py`) produced no results. The installed environment must
also pass `tools/check_licenses.py`. The job uses the pinned requirements, Gmsh,
the pinned RII database and required reference cross-checks
(`OPENPHYSICS_REQUIRE_CROSSCHECK=1`). Running it locally needs Gmsh
and `PHYSMAT_RII_PATH`, because tests that need them skip otherwise and a skip
fails the run. It is verified on Linux only. The source suite runs in
`linux-py312-tests`.

In CI the job runs as eight parts, `installed-tests (1/8)` to `(8/8)`, with
`--shard K/8`. Each part builds and installs its own wheels (about 2 minutes)
and passes pytest the test files `tools/shards/openphysics_shard.py` assigns to
it from every copied test file, by the same table as the source tests; the
result check then requires results from each of those files. The eight parts
together run every test file once, and each writes `shard.json` with its files
and estimated time. In one job the run took 39 to 71 minutes on 2026-11-20,
depending on the runner CPU; the eight parts of a 63-minute run would be 7.1 to
10.9 minutes each, the longest being the M3 slab refinement study alone, and
the 45-minute limit only stops hung runs. Without `--shard`,
as locally, the script runs every test file.

**Licenses** (`tools/check_licenses.py`). Before the tests, the pinned validation
environment, and later each fresh installed environment, is compared with the
reviewed inventory in `tools/third_party_licenses.json`: declared licenses, and
every shared library a third-party wheel installs, file by file, on each OS.
Policy and the full list are in [third-party software](third-party.md).

**Installed platforms** (`tools/check_platform_install.py`). On each OS:
installed licenses, package bytes, installed module origins, bundled assets, public API/CLI/save
smoke tests, the heat save/I-O robustness tests (partial-failure cleanup,
simultaneous writers, existing targets) and two source target-protection
fixtures, plus region VTU/PVD export consumers (the export extra is installed).
The wheel consumers it copies and runs are `test_thermal_simcase_wheel.py`,
`test_electric_joule_wheel.py`, `test_transient_thermomechanical_wheel.py`,
`test_cavity_wheel.py` (without its Studio check, which runs in
`check_distributions.py`), `test_sipi_wheel.py` (stripline, microstrip, JSON
document and DC plane against Cohn, Hammerstad–Jensen and exact resistances on
coarse meshes with stated bounds) and `test_vector_modes_wheel.py` (full-vector
slab modes against `refsol.slab`, a PML leaky slab against its outgoing-root
dispersion equation, and the `vector_slab` example with and without PML through
the `simcase` CLI). The other `test_*_wheel.py` consumers run on Linux only, in
the distribution check. The three consumers added on 2026-11-02 were verified
on Linux; their first macOS and Windows runs are the CI jobs themselves.
This is installed acceptance, not a full macOS or Windows regression.
It also installs the Studio extra's pins (`tools/requirements-py312-studio.txt`, the
Linux versions) and runs the installed workspace in the runner's browser
(`tools/studio_browser/studio_workspace_browser.mjs`): two designs, Compare, Save
session, a server restart with the page open and recovery from the start page, Compare's
mode matching on two more designs (500 → 450 nm: both modes matched with overlap ≥ 0.95, the
picker listing matched pairs), the number of modes (Modes to find refusing 0, 9 and 2.5 and holding
Run, accepting 1 and 8, in Optical modes and Study; the template asking for 8 reads *Found 3 of 8
modes above n = 1.45* with three rows; two 2000 × 400 nm cores of 8 modes matched pair by pair, the
template against one reading *no match*, the picker listing every pair and fitting at 1440 × 900 and
390 × 844; a version 9 session saved and opened with the engine's values; six 8-mode runs over
16 MiB asking first, Cancel writing nothing and the kept file opening a run without fields), then the Joule heating application: the default strip by Picard and by Newton (iteration counts,
balances, temperature and potential ranges, the two methods agreeing within 1e-6 K; the region
mesh differs between macOS arm64 and the other platforms, so mesh-dependent values are
checked within the discretization error), a
non-converging Newton run whose refusal is shown with its text, and constant materials
(`joule.steady2d`, 20 W/m, the uniform strip's exact power). Uncaught page exceptions and
`console.error` calls fail the check (other browser log entries are not collected).
It also checks the model builder as an ARIA tree with the keyboard alone (Tab to its one tab
stop, Up, Down, Home, End, Enter, Space, Left and Right) and finds every node of the optical and
Joule heating trees by role and accessible name in the browser's accessibility tree, and it checks
Compare's absorption loss columns, plots framed on the core with the probe line under them at
1440 × 900 and 1280 × 800, a run clicked on Compare staying on Compare with **Open in Results**,
one selected run card, the session file still named after a page, run or mode is chosen and after
a restore, and a restore opening the page that was shown. Since round 11 it also checks no
tree node selected on Results or Compare and a node under the pointer keeping the plain fill,
the title's short *(other inputs)* only on Results and Compare, **Use this run's inputs** without a question
and Undo taking it back, the Study settings naming the next run's inputs and editing the
wavelength (1300 nm refused there as in Optical modes), and a restore card naming the file's
save time. It also checks the study settings saved with the model: Undo and Redo over a Modes to
find change, a group index box change and **Use this run's inputs** of a run with another count
and box; **File › Export › Model file…** (`optical-waveguide.json`) writing version 7 with 2 modes and the box off (the same bytes as the
version 8 file without its settings key; `tests/simcase/studio_project_study.cjs` checks the
template's file against `tests/simcase/studio_session_fixtures/inputs-v7-optical.json`), version 8 with
`modeCount` 4 or `groupIndex` true, each reopening with its settings; and a session of version 8
inputs saved as version 9. Since round 12 it also checks the page tabs as a tab list named
*Pages* (Library first, one selected tab and one Tab stop, Left, Right, Home and End opening the
next, previous, first and last page; since round 13 one `role=tabpanel` page panel that every tab
controls, named by the selected tab after each key); the Compare table at 1440 × 900 and 390 × 844 with two
header rows (short labels, then A | B), the run names in the line above it, *1 ↔ 1* row headers
whose accessible names are the full pairs, the first column frozen while the others scroll inside
the table's box, every column reachable there and headers and row headers on one line; the group
index box's plain note, the same box in Physics › Optical modes, synced with Study both ways and
through Undo, a Messages line each way, *· group index on* in the next run's inputs, and the
*Off · turn on in Study or Optical modes* hint under an n_g header when no run shown computed n_g.
Since round 13 the Compare table fits at 1440 × 900 (pre-registered): on the 500 → 450 nm table and
the two 8-mode tables, with the Settings pane open (Compare hides the model tree), the box's
clientWidth exceeds the table's width by at least 24 px (42 to 44 px measured on Linux) and its
scrollWidth by none, no header or cell text is clipped or outside its cell, every cell is inside
the box, the Polarization cells have two lines and the n_g hint is on the line above the table; at
390 × 844 the table scrolls in its box with the line *Scroll sideways for all 14 columns ›* and a
right-edge shadow that goes at the right end.
Since the File menu it checks the menus by role and name in the accessibility tree and by keyboard
(Enter, Up, Down, Home, End, Right and Left through the Export and Browser copy submenus and the
Edit menu, Escape closing one level and returning focus), the shortcuts shown and in
`aria-keyshortcuts`, the open menus inside the page at 1440 × 900 and 390 × 844, and the one
**Open session file…** at the top of the Library at both sizes, with and without a resume offer.
The browser's real save dialog cannot be answered in a headless run, so the scripts remove
`window.showSaveFilePicker` at document start and Save goes through Studio's name dialog (Download
keeps the suggested name, so file names and bytes are checked as before); then a stub at that
boundary, whose file changes only on close as in Chromium, checks Save As (the picker options:
the suggested name, one JSON type and `id` `openphysics-project`, with no `startIn` until a file
is chosen and then the current file), the written bytes equal to the download of the same state, Save writing the same
file with no second picker call, a cancel writing nothing, a failed write aborted with the old
content whole, and a picker that throws `NotAllowedError` falling back to the name dialog. The
headless browser reports `navigator.webdriver`, where Studio never calls the picker (a stub that
would throw is not called and Save As downloads under the typed name); the picker checks set
`navigator.webdriver` to false at that boundary. The
name dialog's typed name is sanitised (`my run/<x>?` downloads as `my runx.json`). Since round 13
it checks the model's current file name on the download path: Save As *design-a-ng*, a Width edit,
then Save and Ctrl+S downloading under `design-a-ng.json` again with no name dialog (the bytes
holding the new width, Messages saying *Downloaded design-a-ng.json again* with the “ (1)” note),
the header naming the file (since round 14 *design-a-ng.json · downloaded …* and *· changed since
downloaded*, with the title text *Your browser may have added “ (1)” to the file name.*, which the
picker path does not have, and the Save As dialog's line *Later saves download again under this
name; your browser may add “ (1)”.*),
Save As prefilled with it, **File › Open…** of that file setting it (*Opened design-a-ng.json*,
then *· changed since opened*, and Save keeping the name), **Reset design** dropping it so Save asks
with the model-based name, and a model file over 64 KiB opened through **File › Open…** refused
with *Model file exceeds 64 KiB*. Saves after an opened file keep its name in the other flows too. The real save
dialog of desktop Chrome is not driven by any check.
A second script (`tools/studio_browser/studio_multiphysics_browser.mjs`) then drives the
multiphysics model: the Heated silicon waveguide template, a coupling removed and added back
through the port pickers, a material problem and its one-click fix, a Run whose coupled n_eff
must equal the engine's run of the same document exactly, the coupling check, the heater-off
column solved with the run and its Δn_eff equal to the difference of the engine's two runs, the
run marked out of date by an edit and current again for the same content (the column staying
valid on a second run), only the optical step out of date when the coupling alone is removed, the template's two modes (TE-like, then a TM-like cell that names its TM share), the warning and Undo of a removed coupling, no horizontal overflow at 1440 × 900 and 390 px wide,
the multiphysics model tree with the keyboard alone and by role and name, and the results page
marked in the tree on Results. Since round 11 it also checks *New model · not saved* for a
fresh template, the From list of a coupling added for the temperature input holding only
the temperature, and *No need to run: Run 1 already has these results*.
A third script (`tools/studio_browser/studio_multiphysics_session_browser.mjs`) checks
multiphysics session files (version 8): one Save session and one Open session in every model,
the template, a 0.12 µm mesh and a two-run session saved, opened and saved again (the second
file byte-identical, every stored array equal to the server's separately fetched reply as
Float64 bits), six runs of a 0.08 µm mesh against the 16 MiB limit (the question and the
refusal), the refusals of damaged and newer files, browser recovery after a reload, three
earlier sessions, the conflict of two tabs, and a restart: two optical runs, the heated session
file opened over them, a reload and the same file opened again. After it, the title keeps
*Opened …* through tab clicks, the recovery lists show each session once, and the Optical
waveguide card offers the optical runs, which come back with the same n_eff. It also checks a
named run in the dock and the footer (*Run 1 · Heater 2e14 · …*) and the heated session's save
message naming the optical runs that are not in its file. Since round 11 the Heated silicon
waveguide card restores its own newest record after a reload (the box above not listing it),
naming the session file's save time, the restored title reads *same as file …*, and the
Workspace tools say *Restore earlier session from this browser*. Since round 13 it checks Save after a Save As
name downloading under it again with no dialog (*Downloaded heated-design.json again*, the footer
*heated-design.json · downloaded …* with the “ (1)” title text), and Save after an opened model or
session file keeping that file's name. Since round 14 both scripts check that a restore whose title
reads *same as file X* makes X the current file: Save As suggests X (the workspace script then
reads *X · changed since restored* after an input edit and after a run is renamed).

**Resource observations.** After a green Linux run, the steady and transient
Studio servers, and Studio with heat region documents, are measured once with
fixed workloads. These are observations, not performance gates: the region
observation fails only when a workload's outcome code differs from the fixed one
or a stage fails. The observers are in `tools/studio_resources/`; the
[transient resource observer guide](transient_resource_probe.md) describes the
transient ones and the [region resource observation](region_resource_probe.md)
the region one.
Timing and profiling commands for the solvers are in the
[vector](benchmark_vector.md), [cavity](benchmark_cavity.md),
[heat](benchmark_thermal.md), [elasticity](benchmark_elasticity.md),
[electric](benchmark_electric.md) and [derivative](benchmark_derivatives.md)
benchmark guides.

**Units-batch equivalence (manual dispatch only).** The `units-batch-equivalence`
job runs `tests/simcase/test_units_batch_equivalence.py` with
`OPENPHYSICS_BATCH_BASELINE` set to the merge base with `main` and
`OPENPHYSICS_BATCH_PHASE=3`, on Ubuntu 24.04, macOS 15 and Windows 2022, one
platform at a time. It records every `examples/simcase` document and frozen
fixture, the same documents, on the baseline and on the dispatched commit and
requires the same saved bytes and the same solver and mesher inputs, compared by
parameter name under the rule entries of the
[units-batch harness](../tools/units_batch/README.md#phase-3-the-galerkin-step)
(check P3-1 of the galerkin step). Phase 2 of the harness, the units batch's own
check, needs that batch's baseline and runs locally. Only a manual dispatch runs
the job (`gh workflow run validate.yml --ref <branch>`); pushes and pull requests
skip it. It is not part of `tests`, so each platform's result is read on its own,
from the run of the commit it is claimed for.

**Queueing.** Main runs share one concurrency group per workflow with
`queue: max` and are never cancelled by a newer push. Other refs use
`queue: single`, so a new push supersedes the older run.

### Latest dependencies canary

The `Latest dependencies` workflow (`.github/workflows/latest-deps.yml`) runs
once a day (21:47 UTC) and on manual dispatch. It is **not** part of the
required `tests` check and never gates a PR or `main`. It installs the eight
packages editable with the extras the pinned environment provides
(`galerkin[test,figures,jax,torch,crosscheck]`, `galerkin-refsol[test]`,
`meshine[test,plot]`, `meshloom[test]`, `gmshio[test,gmsh,plot]`,
`physmat[test,rii,plot]`, `simcase[test,studio,export]`, `sipi[test]`) without
the pinned requirements and without `--no-deps`, so pip resolves the newest
versions the `pyproject.toml` bounds allow. The PyTorch CPU index is an extra
index without a version pin, and the step checks that the installed torch is the
`+cpu` build; meshloom builds with the newest maturin its pyproject allows while
its Rust crates stay at `Cargo.lock` (`--locked`). It then runs
`python -m pip check`, the license check (a new transitive distribution without
a reviewed inventory entry fails it, which is part of the point), the same
preflight groups as the Linux job, the non-slow suite with the pinned RII
database and required reference-tool comparisons, and the `blas-kernels` file
list under both forced OpenBLAS kernels. Once the install has succeeded, each
check runs even if an earlier one failed, so one failure does not hide the
others. `pip freeze` goes to the step summary and, with the license report and
the JUnit files, to the `latest-deps-results` artifact. Left out: the Node
Studio checks (Node is pinned by the workflow and not resolved by pip, so it
cannot drift here), the distribution builds, meshloom's Cargo tests and notices,
and the slow studies.

A failed scheduled or manual run opens the issue **Latest dependencies canary
failed**, or comments on it when it is already open, with the run URL and the
resolved versions of the key packages next to their pins; a passing run closes
it. A cancelled run, including one stopped by the 90-minute limit, is not
reported. The canary is a heads-up, not a verdict on the commit: the pins in
`tools/requirements-py312-linux*.txt` are still updated deliberately, in a
reviewed change that reruns the source and distribution checks.

## Reading results

Each job uploads its artifacts, even after a failure:

- Linux: `distributions-and-test-results`, the `.validation/` directory with
  JUnit XML per preflight group, distribution checksums and reports, and
  `numeric-runtime.json`.
- Source tests: `source-tests-<k>-of-8` for each part, the `.validation/`
  directory with `source-tests-<k>.xml`, the cross-check records and
  `numeric-runtime.json`.
- Installed tests: `installed-test-results-<k>-of-8` for each part, the
  `.validation/` directory with the built distributions, `installed-tests.xml`,
  `shard.json`, `installed-origins.json`, `suite-file-hashes.json`, the license
  report and the cross-check records.
- Installed platforms: `installed-packages-<os>-<run_id>` with every command's
  exit and log, environment details, checksums, installed origins, JUnit XML and
  `numeric-runtime.json`.
- Units-batch equivalence (manual dispatch only):
  `units-batch-equivalence-<os>-<run_id>` with the comparison report (a SHA-256
  table per document and array, and the rule entries applied), the document list
  and both recording manifests.

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

- `tools/report_numeric_runtime.py` records the CPU model, the OpenBLAS kernel
  and `numpy.show_runtime()` in each job (`numeric-runtime.json`). macOS arm64
  uses Accelerate, so no OpenBLAS kernel is reported there.
- `blas-kernels` forces `OPENBLAS_CORETYPE=Haswell` (AVX2, also the kernel used
  on AMD Zen) and `Sandybridge` (AVX). It first confirms the forced kernel is
  active, so a fallback cannot pass silently. The job also sets
  `OPENBLAS_L2_SIZE=2048`: OpenBLAS 0.3.34 otherwise enlarges GEMM blocking on
  AVX-512 AMD runners (Zen 4/5) even under a forced kernel, which crashes the
  Haswell kernel
  ([OpenMathLib/OpenBLAS#6021](https://github.com/OpenMathLib/OpenBLAS/issues/6021)).
  Remove it once the pinned numpy bundles a fixed OpenBLAS
  ([#78](https://github.com/fieldalgo/openphysics/issues/78)). To reproduce locally:

  ```bash
  OPENBLAS_CORETYPE=Sandybridge python -m pytest -q -m "not slow" <test files>
  ```

Write tests that do not depend on last-bit rounding: compare with explicit
tolerances well clear of roundoff, never exactly at a boundary roundoff can reach.
An exact comparison is sound only when it follows from identical inputs to the
same code on one machine, as in `tests/simcase/test_length_canonical.py` (the
same mesher input in nm, um and m); say why in the test.

## Publishing

The `Release` workflow (`.github/workflows/release.yml`) uploads the nine
distributions to PyPI when a GitHub release is published. Pushing a tag alone
uploads nothing, and validation never starts it. Its jobs run in order:

1. **gate**: `validate.yml` has already passed on the release commit; the suite
   is not run again. A release published before that fails here and uploads
   nothing; re-run the workflow once validation has passed.
2. **build**: `tools/check_release_version.py --tag <tag>`, then
   `tools/check_distributions.py --build-only` with `OPENPHYSICS_DOCS_REF` set to
   the tag.
   **kernel** and **assemble**: meshloom's wheels are built from its sdist on each
   release platform (manylinux 2.17 x86_64 and aarch64, macOS 11 x86_64 and arm64,
   Windows x64) with the pinned toolchain and maturin; `check_distributions.py
   --assemble` replaces the local meshloom wheel by them, checks each one and
   writes `SHA256SUMS`.
3. **install**: `tools/check_release_install.py --wheels` on Linux, macOS and
   Windows with Python 3.12 and 3.15, third-party requirements resolved from
   PyPI. It is a smoke check of the installed packages, not the test suite.
4. **publish**: PyPI trusted publishing (OIDC; no token is stored) from the
   `pypi` GitHub environment, which accepts only `v*` tags. Dependencies are
   uploaded before the packages that require them, `openphysics` last. Each PyPI
   project lists the publisher: owner `fieldalgo`, repository `openphysics`,
   workflow `release.yml`, environment `pypi`.
5. **verify**: PyPI's files must have the build's SHA-256, and installing from
   PyPI passes step 3 again on the same platforms.

Running it by hand (Actions → Release → Run workflow) is a dry run: steps 1–3 on
the chosen branch's commit, descriptions linked to that commit, no upload. To
release: land the version change, wait for validation of that `main` commit,
dry-run the workflow on `main`, then tag the commit `vX.Y.Z` and publish a GitHub
release from the tag.

Each package builds from `packages/<name>`; the repository root is not a
distribution, and `packages/openphysics` is the meta distribution that requires
seven of the other eight (with the Studio, export and RII extras) and provides the
`openphysics` command; `meshloom` is not part of it yet. A build-only check for one
package:

```bash
python -m build --no-isolation --outdir .validation/simcase packages/simcase
python -m twine check --strict .validation/simcase/*
```

All nine distributions release together under one version. A version change
sets it in every `packages/<name>/pyproject.toml` and in each import package's
`__version__`, and meshloom's `Cargo.toml`, keeps the requirements between our own distributions inside that
minor series (`>=0.0.2,<0.1` for 0.0.2; `>=0.1.0,<0.2` for 0.1.x), except that `simcase` pins
`physmat` and `galerkin`, and `sipi` pins `galerkin`, to the exact version (`physmat==0.0.2`,
`galerkin==0.0.2`) because they call the internal `physmat.kernels` and `galerkin.kernels`, runs
`python tools/changelog.py --assemble` to merge the [changelog fragments](#changelog-fragments), and renames the
[changelog](../CHANGELOG.md)'s `[Unreleased]` section to `[X.Y.Z] - YYYY-MM-DD`.
`python tools/check_release_version.py --tag vX.Y.Z` checks all of that for a
release (it refuses a tag while `changelog.d/` still holds a fragment), and also refuses package READMEs and documentation pages (other than
changelogs) that still say the release is not on PyPI yet, because a package README
becomes its PyPI description; without `--tag`, as required CI runs it, it accepts an
`[Unreleased]` section and that wording. The changelog also says what 0.x keeps stable.

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
`tools/tests/test_readme_links.py` checks that the eight `setup.py` files are identical
and that no relative link is left in any package description. `meshloom` is built by
maturin, which does not run `setup.py`, so its README uses absolute links only; the
same test checks that.

### Changelog fragments

A change does not edit `CHANGELOG.md`: each commit carries its changelog entry as
one fragment, `changelog.d/<slug>.md`, so concurrent PRs do not conflict at the top
of `[Unreleased]`. The slug is a short name in lowercase letters, digits and hyphens
(no PR number is needed). The `#` heading is one Keep a Changelog category (`Added`,
`Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`), and the two sections hold
the English and Korean bullets exactly as they will appear in the
[changelog](../CHANGELOG.md) and its [Korean page](locales/ko/pages/changelog.md),
with links relative to that page:

```markdown
# Fixed

## English

- `galerkin`: what changed and why, with the checks. [Shape derivatives](docs/packages/galerkin/shape_derivative.md).

## 한국어

- `galerkin`: 바뀐 내용과 이유, 검사. [형상 미분](packages/galerkin/shape_derivative.md).
```

`python tools/changelog.py --check` (run in CI) checks the name, the category, both
sections and the links. The version-change PR runs `python tools/changelog.py --assemble`:
it inserts each category's bullets, in slug order, at the top of that `###`
subsection of `[Unreleased]` in both pages (adding the subsection when it is missing)
and deletes the fragments. Lines already in `[Unreleased]` stay where they are,
including the bullets above its first `###` subsection, which have no category.
`changelog.d/` holds only fragments.

## Stored-value test support

`tests/_support/` contains unshipped modules only (no subdirectories). Root pytest `pythonpath`
makes the [stored-value loader](stored-reference-values.md) available without a `tests/conftest.py`.
The installed suite copies that configuration and the support modules, validating without a reference-tool install.

<a id="reference-import-checks"></a>

## Reference import checks

`tools/check_reference_zones.py` checks only `git ls-files -z` paths. Stage new
files before checking. Untracked environments do not participate. Every tracked
`.py` must belong to packages, examples, tools, tests, studies or benchmarks;
all conftest files are always-loaded. Test helpers are always-loaded; only
`test_*.py`/`*_test.py` are test modules. Stored generators are
`tests/<import>/reference_values/<tool>/generate_*.py`.

The checker recognizes import statements, literal `__import__`,
`importlib.import_module`, `pytest.importorskip`, `require_tool`, and import aliases.
A module-level try/if/class is still eager. Function defaults and decorators are
also eager; function bodies and the exact `if __name__ == "__main__":` body are not.
A default-loaded module cannot eagerly import a helper with eager non-permissive
imports (one level, resolved from the repository root and caller directory).
Each reference importer must match its inventory `reference.imported_by` globs.

For example, a listed test can call `require_tool("scikit-fem")` inside its fixture.
A future restricted tool must follow that same lazy pattern; placing its import
in a shared fixture module or module-level `try` fails. No new tool is installed
by this checker. It checks literal syntax, not arbitrary generated names, alias
reassignment, function-call execution or indirect chains beyond one import edge;
manual review still covers those cases. It never reads installed solver source.

Published non-test dependencies and extras cannot reach a test extra or any
reference tool through first-party dependency edges. Non-permissive references
cannot occur in any published dependency, including test extras. Environment
markers are conservatively treated as reachable on some supported environment.
Third-party transitive dependency licenses remain checked from installed metadata.
The meta distribution cannot reach Gmsh. The scan is required in Linux source CI;
installed-platform jobs keep their existing license-scan trigger.

This is a source-policy API, not a physical solver API: there are no physical
units or boundary conditions. Stored numerical units and comparison boundaries
remain in [stored reference values](stored-reference-values.md).
