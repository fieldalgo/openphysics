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
| `tools/*.py` | Checks (`check_*.py`, `fetch_rii.py`, `report_numeric_runtime.py`, `diagnose_transient_conditioning.py`) and maintainer scripts (`build_physmat_tables.py`) | The checks, yes; maintainer scripts, no |
| `tools/requirements-*.txt`, `tools/rii-revision.txt` | Pinned validation environments and the pinned refractiveindex.info revision | Yes |
| `tools/third_party_licenses.json` | Reviewed third-party license inventory read by `check_licenses.py` | Yes |
| `tools/tests/` | Tests of these tools, collected by the root `pytest` run | Yes |
