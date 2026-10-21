# Repository tools

Checks, pins and maintainer scripts for this repository. Nothing here ships in a
distribution. The [development guide](../docs/development.md) explains what each
check covers and how to run it locally.

Run each script as a file from the repository root, for example
`python tools/check_licenses.py`; do not run them with `python -m`. Keep this
folder free of `__init__.py` and `conftest.py` files, and do not name a script
after a standard-library or third-party module.

| Path | What it holds | Run by required CI |
|---|---|---|
| `tools/*.py` | Checks (`check_*.py`, including `check_release_version.py`, `run_installed_tests.py`, `audit_distribution_artifacts.py`, `fetch_rii.py`, `report_numeric_runtime.py`, `diagnose_transient_conditioning.py`), the release install check (`check_release_install.py`) and maintainer scripts (`build_physmat_tables.py`) | The checks, yes; `check_release_install.py` runs only in the release workflow (`.github/workflows/release.yml`); maintainer scripts, no |
| `tools/requirements-*.txt`, `tools/rii-revision.txt` | Pinned validation environments and the pinned refractiveindex.info revision | Yes |
| `tools/third_party_licenses.json` | Reviewed third-party license inventory read by `check_licenses.py` | Yes |
| `tools/tests/` | Tests of these tools, collected by the root `pytest` run | Yes |
| `tools/wheel_consumers/` | Consumers of the installed wheels (`wheel_smoke.py`, `test_*_wheel.py`, `test_platform_install.py`). `check_distributions.py` and `check_platform_install.py` copy them outside the checkout and run them against the installed packages. The root `pytest` run does not collect them, but `check_platform_install.py` also runs `test_thermal_simcase_wheel.py` in place, from the repository root with the root conftest, for its source-target check | Yes |
| `tools/studio_browser/` | Real-browser Studio acceptance (Node and Chrome DevTools), run by `check_distributions.py` against the installed Studio | Yes |
| `tools/studio_resources/` | Studio resource observers (`profile_studio_thermal.py`, `run_transient_resource_workloads.py` and the transient profiler) and the stdlib-only probe for an already running server ([guide](../docs/transient_resource_probe.md)) | The steady and transient observations, yes (one fixed run each, not a performance gate). The probe's own command line, no, but the transient observers import and run its functions, so it stays beside them |

Scripts that people run but required CI does not are elsewhere: timing benchmarks in
[benchmarks/](../benchmarks/README.md) and diagnostic studies in
[studies/](../studies/README.md).
