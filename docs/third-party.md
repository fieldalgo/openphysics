# Third-party software, data and references

**English** | [한국어](locales/ko/pages/third-party.md)

OpenPhysics code and documentation are Apache-2.0 ([LICENSE](../LICENSE),
[NOTICE](../NOTICE)). This page lists every third-party component the
repository uses, how it is used, and under which terms. The Apache-2.0 license
does not relicense any of them.

The machine-readable inventory is
[`ci/third_party_licenses.json`](../ci/third_party_licenses.json).
`ci/check_licenses.py` compares it with the installed metadata of each
validation environment (see [Automated check](#automated-check)).

## How a component is used

| Use | Meaning |
|---|---|
| runtime | Base requirement of a package; imported at run time. Installed separately by pip, never bundled. |
| optional | Non-test extra (`simcase[studio]`, `physmat[rii]`, plotting extras). Same terms as runtime. |
| test | Test-only extras (`test`, and `crosscheck` for reference-tool comparisons) or test-only tools; not needed by users. |
| tool | CI build, packaging or upload tool; never imported by package code. |
| external process | Separately installed program run as a subprocess; only its output files are read. |
| data | Numbers or records reproduced in or fetched by the repository. |

Policy: runtime and optional components must be permissive. LGPL or MPL is
accepted only for unmodified, separately installed test or tool components.
GPL programs are used only as external processes, never imported, linked or
bundled, and their source is not copied. AGPL is not used. No third-party source
code is copied into the repository.

## Python distributions

Version ranges are the package requirements; the exact CI versions are pinned in
`ci/requirements-py312-linux.txt` (Linux) and
`ci/requirements-py312-windows-thermal.txt` (installed-platform checks).

### Runtime

| Distribution | Required by (range) | SPDX | Notes |
|---|---|---|---|
| `numpy` | all except openphysics (`>=1.24`) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Wheels bundle OpenBLAS (BSD-3-Clause) and, on Linux/Windows, the GCC Fortran runtime (GPL-3.0-or-later WITH GCC-exception-3.1, which permits this use) |
| `scipy` | galerkin, galerkin-refsol, meshine, physmat, simcase (`>=1.10`) | BSD-3-Clause | Same bundled libraries as numpy |
| `shapely` | simcase (`>=2.0`) | BSD-3-Clause | Wheels bundle the GEOS shared library (LGPL-2.1-only), loaded dynamically and unmodified; OpenPhysics does not redistribute it |
| `matplotlib` | simcase (any); plotting extras (`>=3.7`) | LicenseRef-Matplotlib | PSF-based permissive license agreement |
| `contourpy`, `cycler`, `kiwisolver` | matplotlib | BSD-3-Clause | |
| `fonttools`, `pyparsing`, `six` | matplotlib | MIT | |
| `pillow` | matplotlib | MIT-CMU | Bundles image codecs under permissive terms |
| `packaging` | matplotlib | Apache-2.0 OR BSD-2-Clause | |
| `python-dateutil` | matplotlib | Apache-2.0 AND BSD-3-Clause | |

### Optional extras

| Distribution | Extra | SPDX |
|---|---|---|
| `fastapi` | `simcase[studio]` (`>=0.100`) | MIT |
| `uvicorn` | `simcase[studio]` (`>=0.20`) | BSD-3-Clause |
| `starlette`, `idna` | fastapi | BSD-3-Clause |
| `click` | uvicorn | BSD-3-Clause |
| `pydantic`, `pydantic-core`, `annotated-types`, `annotated-doc`, `typing-inspection`, `anyio`, `h11` | fastapi, uvicorn | MIT |
| `typing-extensions` | fastapi, pydantic | PSF-2.0 |
| `opentelemetry-api` | fastapi | Apache-2.0 |
| `pyyaml` | `physmat[rii]` | MIT |
| `meshio` | `simcase[export]` (`>=5.3,<6`) | MIT |
| `rich`, `markdown-it-py`, `mdurl` (and `pygments`, BSD-2-Clause) | meshio | MIT |

### Test

| Distribution | Reached through | SPDX | Notes |
|---|---|---|---|
| `pytest`, `iniconfig`, `pluggy` | `test` extras | MIT | |
| `pygments` | pytest | BSD-2-Clause | |
| `colorama` | pytest, click (Windows only) | BSD-3-Clause | |
| `httpx`, `httpcore` | `simcase[test]` | BSD-3-Clause | |
| `certifi` | httpx, requests | MPL-2.0 | Unmodified CA bundle; test and tool only |
| `scikit-fem` | `galerkin[crosscheck]` (`>=12,<13`) | BSD-3-Clause | Reference tool for [solver comparisons](reference-comparisons.md); pure Python, needs only numpy and scipy |

First-party test extras also require `galerkin-refsol`, `meshine` and `gmshio`,
which are Apache-2.0 packages of this repository.

### CI tools

| Distribution | Purpose | SPDX |
|---|---|---|
| `build`, `pyproject-hooks`, `wheel`, `setuptools`, `pip` | Build and install distributions | MIT |
| `twine`, `id`, `readme-renderer`, `requests`, `requests-toolbelt`, `rfc3986` | `twine check --strict` | Apache-2.0 |
| `docutils` | README rendering in twine | LicenseRef-Public-Domain AND BSD-2-Clause AND 0BSD (its GPL classifier covers files that are not in the wheel) |
| `nh3`, `rich`, `markdown-it-py`, `mdurl`, `keyring`, `jaraco-classes`, `jaraco-context`, `jaraco-functools`, `more-itertools`, `jeepney`, `urllib3`, `charset-normalizer` | twine dependencies | MIT |
| `cffi` | cryptography | MIT-0 |
| `cryptography` | secretstorage | Apache-2.0 OR BSD-3-Clause |
| `secretstorage`, `pycparser` | keyring, cffi | BSD-3-Clause |

## External programs

| Program | License | How it is used |
|---|---|---|
| Gmsh ([`gmsh`](https://gmsh.info) executable, pip distribution `gmsh` in `gmshio[gmsh]` and CI) | GPL-2.0-or-later | `gmshio` writes a `.geo` script, runs `gmsh` as a separate process and reads the `.msh` file with an original parser written from the published format description. Never imported or bundled; see [gmshio NOTICE](../packages/gmshio/NOTICE) |
| Node.js | MIT | Runs the Studio JavaScript checks in CI |
| Chrome or Chromium | Chrome terms / BSD-3-Clause | Already-installed browser for the Studio browser check in CI |
| GitHub Actions `actions/checkout`, `actions/setup-python`, `actions/setup-node`, `actions/upload-artifact` | MIT | CI only, pinned by commit |

## Data and published numbers

| Source | Terms | How it is used |
|---|---|---|
| [refractiveindex.info database](https://github.com/polyanskiy/refractiveindex.info-database) | CC0-1.0 | A subset of tables and dispersion coefficients is embedded in physmat (`physmat/_tables.py`, `physmat/library.py`). CI fetches the commit pinned in `ci/rii-revision.txt`; that copy is not shipped. Citation and per-record sources: [physmat NOTICE](../packages/physmat/NOTICE) |
| G. R. Hadley, J. Lightwave Technol. 20(7), 1210 (2002) | Published facts | Benchmark values in `galerkin-refsol`, cross-checked against tables published with femwell (GPL-3.0); only the numbers are reproduced, no code or text. See [galerkin-refsol NOTICE](../packages/galerkin-refsol/NOTICE) |
| Handbook-type thermal and mechanical constants | Approximate example inputs | Not certified measurements; see [asset provenance](assets.md) |

## Reference tools for comparisons

Solver comparisons that run other finite-element tools are recorded separately
from the analytical acceptance references. Agreement between two tools is not
used as convergence evidence. Permissive tools are installed through the
test-only `crosscheck` extra and listed above; the record format and current
cases are in [reference comparisons](reference-comparisons.md). GPL tools are run, if at all, as separately
installed unmodified executables outside this repository; their source is not
read or copied, and only numerical results are reported.

## Automated check

```bash
python ci/check_licenses.py --report .validation/licenses.json
```

The check reads installed metadata with `importlib.metadata`, so no license
scanning tool is installed. It fails when:

- an installed distribution has no reviewed entry in the inventory;
- installed metadata declares a different SPDX expression, or mentions a
  copyleft license the entry does not record (unless the entry explains why);
- a runtime or optional dependency of a first-party package is not permissive;
- a weak-copyleft test or tool dependency is not marked `test_only`;
- a GPL distribution is not an external process, is a base runtime
  requirement, or is imported by first-party code;
- AGPL or SSPL appears anywhere;
- a first-party package does not declare Apache-2.0;
- this page or its Korean translation does not list every inventory entry.

CI runs it on the pinned Linux environment, on the fresh environment holding the
installed wheels, and in the installed-platform check on Linux, macOS and
Windows. Bundled native libraries inside third-party wheels (such as GEOS in
shapely) are not visible in metadata and are reviewed by hand in the notes
above.

To add a dependency: confirm the license in the upstream repository's LICENSE
file, add an entry with the SPDX expression and source URL to the inventory,
add a row here and in the Korean page, and record its package NOTICE if it is
bundled or copied.
