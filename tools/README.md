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
| `tools/*.py` | Checks (`check_*.py`, including `check_release_version.py`, `run_installed_tests.py`, `audit_distribution_artifacts.py`, `fetch_rii.py`, `report_numeric_runtime.py`, `diagnose_transient_conditioning.py`), the release install check (`check_release_install.py`) and maintainer scripts (`build_physmat_tables.py`, `build_meshloom_notices.py`) | The checks, yes; `check_release_install.py` runs only in the release workflow (`.github/workflows/release.yml`); maintainer scripts, no, except `build_meshloom_notices.py --check`, which the Linux job runs |
| `tools/requirements-*.txt`, `tools/rii-revision.txt` | Pinned validation environments and the pinned refractiveindex.info revision | Yes |
| `tools/third_party_licenses.json` | Reviewed third-party license inventory read by `check_licenses.py` | Yes |
| `tools/tests/` | Tests of these tools, collected by the root `pytest` run, and `test_examples_smoke.py`, which runs every script and JSON document under `examples/` (see below) | Yes |
| `tools/wheel_consumers/` | Consumers of the installed wheels (`wheel_smoke.py`, `test_*_wheel.py`, `test_platform_install.py`). `check_distributions.py` and `check_platform_install.py` copy them outside the checkout and run them against the installed packages. The root `pytest` run does not collect them, but `check_platform_install.py` also runs `test_thermal_simcase_wheel.py` in place, from the repository root with the root conftest, for its source-target check | Yes |
| `tools/studio_browser/` | Real-browser Studio acceptance (Node and Chrome DevTools): the thermal pages, run by `check_distributions.py` against the installed Studio, and the optical workspace (`studio_workspace_browser.mjs`), run by `check_platform_install.py` on every OS | Yes |
| `tools/units_batch/` | The equivalence harness of the units and naming batch: a recorder of solver and mesher inputs and saved bytes, a comparator with a closed list of transforms, the 0.2-to-0.3 document converter, the comparison maps and frozen 0.2 fixtures ([README](units_batch/README.md)) | Its self-checks, yes (`tests/simcase/test_units_batch_equivalence.py`); the full baseline comparison runs only in the `units-batch-equivalence` job, on manual dispatch and outside the required `tests` check |
| `tools/studio_resources/` | Studio resource observers (`profile_studio_thermal.py`, `run_transient_resource_workloads.py` and the transient profiler, `run_region_resource_workloads.py` for region documents ([guide](../docs/region_resource_probe.md))) and the stdlib-only probe for an already running server ([guide](../docs/transient_resource_probe.md)) | The steady, transient and region observations, yes (one fixed run each, not a performance gate). The probe's own command line, no, but the transient observers import and run its functions, so it stays beside them |

## Examples smoke test

`tools/tests/test_examples_smoke.py` runs each example once and requires exit
code 0: every `examples/*/*.py` script in its own `sys.executable` process, and
every `examples/simcase/*.json` document through `python -m simcase validate`
and `python -m simcase run -q -o <folder>`. It copies `examples/` into a
temporary directory and runs from there with `MPLBACKEND=Agg`, one BLAS thread
and the package `src/` folders on `PYTHONPATH`, so plots, `.npz` files and
result folders never land in the checkout. Scripts that read the `.npz` another
example saves (`visualize*.py`) run after that example. The scripts with an
output argument get a folder in the temporary directory; `gallery.py` and
`public_benchmarks.py` run with `--quick`. `hadley_rib_mesh.py` skips without a
Gmsh executable; the examples that take more than about 20 s carry the `slow`
marker. This is a smoke check, not a validation: the worked-tutorial tests and
the package suites check the numbers. It runs from the source tree only;
`run_installed_tests.py` does not copy `tools/tests/`.

```bash
python -m pytest -q tools/tests/test_examples_smoke.py                  # all examples
python -m pytest -q tools/tests/test_examples_smoke.py -m "not slow"    # the quick ones
```

Scripts that people run but required CI does not are elsewhere: timing benchmarks in
[benchmarks/](../benchmarks/README.md) and diagnostic studies in
[studies/](../studies/README.md).
