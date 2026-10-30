# Third-party software, data and references

**English** | [한국어](locales/ko/pages/third-party.md)

OpenPhysics code and documentation are Apache-2.0 ([LICENSE](../LICENSE),
[NOTICE](../NOTICE)). This page lists every third-party component the
repository uses, how it is used, and under which terms. The Apache-2.0 license
does not relicense any of them.

The machine-readable inventory is
[`tools/third_party_licenses.json`](../tools/third_party_licenses.json).
`tools/check_licenses.py` compares it with the installed metadata and file lists
of each validation environment (see [Automated check](#automated-check)).

## How a component is used

| Use | Meaning |
|---|---|
| runtime | Base requirement of a package; imported at run time. Installed separately by pip, never bundled. |
| optional | Non-test extra (`simcase[studio]`, `simcase[export]`, `physmat[rii]`, plotting extras). Python libraries in it meet the runtime terms here. A GPL program that an extra installs (`gmshio[gmsh]`) is an external process instead. |
| test | Test-only extras (`test`, and `crosscheck` for reference-tool comparisons) or test-only tools; not needed by users. |
| tool | CI build, packaging or upload tool; never imported by package code. |
| external process | Separately installed program run as a separate process; only its output files are read. Its Python module, if it has one, is never imported by package code. |
| bundled | Native library, statically linked code, font or runtime file that a third-party wheel's publisher ships inside that wheel. |
| data | Numbers or records reproduced in or fetched by the repository. |

## License policy

This is a project policy, not legal advice. License terms are judged at three
levels.

1. **What this repository creates, copies, builds, links or distributes**: the
   source tree, the sdists and wheels of its packages (package code, README,
   LICENSE, NOTICE and build files; tests, docs and examples are not shipped),
   and CI artifacts. They
   are original Apache-2.0 work apart from the third-party data recorded under
   [data and published numbers](#data-and-published-numbers) (CC0-1.0
   refractive-index tables embedded in physmat, published benchmark numbers in
   galerkin-refsol), which keeps its own terms. No third-party source code is
   copied into the repository, no package contains compiled code, and the
   distributions declare their dependencies without including them.
2. **Each dependency, by the license its own distribution declares**: base
   requirements, extras, test and tool dependencies, including transitive ones.
   - Permissive licenses are the default.
   - Weak copyleft (LGPL, MPL, CeCILL-C) is acceptable at most in optional
     extras, test extras and tools, installed separately and unmodified. It is
     never a base requirement, and OpenPhysics never modifies, copies or
     statically links it or loads it directly from its own code (ctypes, cffi
     or compiled extensions).
   - MPL-2.0 alone may also be a base requirement or a file served to a
     browser, if it stays unmodified and in its own files (never merged into a
     file with OpenPhysics code), its notice and exact source location are
     published, and it is not marked "Incompatible With Secondary Licenses".
     MPL-2.0 copyleft applies per file, so this places no terms on OpenPhysics
     code (MPL-2.0 sections 1.7, 3.2 and 3.3).
   - This repository is currently stricter than both rules above: runtime
     and optional dependencies are all permissive and the
     [automated check](#automated-check) keeps them so, and the `crosscheck`
     test extra installs only permissive reference tools.
   - GPL programs run only as separate processes: as external reference tools,
     or as the backend of an optional extra (`gmshio[gmsh]`). They are never
     imported, linked or bundled, and their source is neither read nor copied.
   - AGPL and other network-copyleft licenses (SSPL, EUPL, OSL and similar) are
     not used by the packages, their CI or any hosted service. They are run, if
     at all, only as separately executed reference tools in private research
     repositories.
   - A license with a runtime exception, such as
     `GPL-3.0-or-later WITH GCC-exception-3.1`, is judged by the exception's
     terms, which are recorded. For a dual license, the option relied on is
     recorded (FreeType: the FreeType License, FTL).
3. **Components bundled inside separately installed third-party wheels**: native
   libraries, statically linked code, fonts and redistributable runtimes that a
   wheel's publisher ships inside it. They are part of that publisher's
   distribution and covered by its notices. They are recorded and reviewed in
   [bundled components](#bundled-components), not banned. OpenPhysics does not
   modify, rebuild, relink, copy or redistribute them, and its package code
   reaches them only through the owning package's public Python API. The one
   recorded exception is a CI diagnostic, `tools/report_numeric_runtime.py`:
   it loads numpy's bundled OpenBLAS with ctypes only to read its kernel name
   for the job log (on Linux this also loads the bundled GCC runtime and
   libquadmath). It is not package code; only its text report is kept with the
   CI results. A wheel whose main purpose is to expose a bundled copyleft
   library's API (a thin binding) is reviewed as if OpenPhysics depended on
   that library directly. A bundled library that loads into the same process
   as OpenPhysics is never plain GPL: GPL code there needs a runtime exception
   (the GCC exception) or another license option (FreeType's FTL). Only a
   separate-process tool such as Gmsh may bundle GPL libraries.

Running software on a server is not distribution, but JavaScript, CSS, fonts and
WebAssembly sent to a browser are. OpenPhysics distributes no third-party
binaries. Before anything that contains third-party binaries is distributed
(container or virtual-machine images, installers, frozen applications,
wheelhouses or wheel mirrors, browser-based Python sites, customer deliveries),
it needs a redistribution checklist and legal review: complete license texts and
notices, corresponding source or a written offer for LGPL and GPL components,
LGPL libraries kept replaceable, and terms that permit modification and reverse
engineering for debugging.

## Python distributions

Version ranges are the package requirements; the exact CI versions are pinned in
`tools/requirements-py312-linux.txt` (Linux) and
`tools/requirements-py312-windows-thermal.txt` (installed-platform checks).

### Runtime

| Distribution | Required by (range) | SPDX | Notes |
|---|---|---|---|
| `numpy` | all except openphysics (`>=1.26`) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Wheels bundle OpenBLAS and GCC runtime libraries, including libquadmath (LGPL-2.1-or-later, not covered by the GCC exception): separate shared libraries on Linux and on macOS before 14, none on macOS 14 and later (Apple Accelerate is used), and on Windows an OpenBLAS DLL with the GCC runtime statically linked, plus `msvcp140.dll`. See [bundled components](#bundled-components) |
| `scipy` | galerkin, galerkin-refsol, meshine, physmat, simcase (`>=1.11.2`) | BSD-3-Clause | Wheels bundle GCC runtime libraries, including libquadmath (LGPL-2.1-or-later), as shared libraries on Linux and every macOS version, with OpenBLAS except on macOS 14 and later. On Windows the GCC runtime is static in the OpenBLAS DLL and in one extension module. Qhull is statically linked. See [bundled components](#bundled-components) |
| `shapely` | simcase (`>=2.0.2`) | BSD-3-Clause | Wheels bundle GEOS (LGPL-2.1) as separate shared libraries on Linux, macOS and Windows, loaded dynamically by shapely's own extension modules; Windows wheels also bundle `msvcp140.dll`. OpenPhysics calls only shapely's Python API and redistributes neither. See [bundled components](#bundled-components) |
| `matplotlib` | simcase and plotting extras (`>=3.8`) | LicenseRef-Matplotlib | PSF-based permissive license agreement. Extension modules statically include FreeType (FTL OR GPL-2.0-or-later, used under the FTL), HarfBuzz, libraqm, SheenBidi and Qhull; data files include fonts under OFL-1.1, BaKoMa and Bitstream Vera terms |
| `contourpy`, `cycler`, `kiwisolver` | matplotlib | BSD-3-Clause | |
| `fonttools`, `pyparsing`, `six` | matplotlib | MIT | |
| `pillow` | matplotlib | MIT-CMU | Bundles image, font and compression libraries under permissive terms (FreeType: FTL OR GPL-2.0-or-later, used under the FTL): shared libraries on Linux and macOS, statically linked on Windows |
| `packaging` | matplotlib | Apache-2.0 OR BSD-2-Clause | |
| `python-dateutil` | matplotlib | Apache-2.0 AND BSD-3-Clause | |
| `array-api-compat` | galerkin (`>=1.15`) | MIT | Pure Python; lets one implementation run on NumPy, JAX and PyTorch arrays (`galerkin.core.backend`) |

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
| `jax`, `jaxlib` | `galerkin[jax]` (`>=0.12.0.1`) | Apache-2.0 |
| `ml-dtypes` | jax | Apache-2.0 |
| `opt-einsum` | jax | MIT |
| `torch` | `galerkin[torch]` (`>=2.14.1`) | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| `filelock` | torch | MIT |
| `networkx`, `jinja2`, `fsspec` | torch | BSD-3-Clause |
| `markupsafe` | jinja2 | BSD-3-Clause |
| `sympy`, `mpmath` | torch | see [Test](#test) |

`pydantic-core` statically links Rust crates under MIT, Apache-2.0,
Unlicense OR MIT and Unicode-3.0 (icu_normalizer); its wheel carries only its
own MIT license. `pyyaml` statically includes libyaml (MIT).

CI installs the CPU build of `torch` from `download.pytorch.org/whl/cpu`, and its
bundled libraries are recorded for that wheel. On Linux the PyPI `torch` wheel
instead requires NVIDIA CUDA packages (`cuda-toolkit`, `nvidia-*-cu13`); they are
torch's own dependencies and are neither installed by CI nor listed here.

### Test

| Distribution | Reached through | SPDX | Notes |
|---|---|---|---|
| `pytest`, `iniconfig`, `pluggy` | `test` extras | MIT | |
| `pygments` | pytest | BSD-2-Clause | |
| `colorama` | pytest, click (Windows only) | BSD-3-Clause | |
| `httpx`, `httpcore` | `simcase[test]` | BSD-3-Clause | |
| `certifi` | httpx, requests | MPL-2.0 | CA bundle used unmodified (certifi's bundle is itself derived from Mozilla's); test and tool only |
| `scikit-rf` | `sipi[test]` (`==2.2.0`) | BSD-3-Clause | Network/Touchstone reference only. Wheel/sdist omit LICENSE.txt; exact v2.2.0 tag text verified. Not a shipped/runtime dependency |
| `pandas` | scikit-rf, CI 3.0.3 | BSD-3-Clause | Test-only; exact sdist license and vendored permissive notices checked; not redistributed |
| `scikit-fem` | `galerkin[crosscheck]` (`>=12,<13`) | BSD-3-Clause | Reference tool for [solver comparisons](reference-comparisons.md); pure Python, needs only numpy and scipy |
| `symfem` | `galerkin[crosscheck]` (`==2025.12.0`) | MIT | Exact element definitions for [element comparisons](reference-comparisons.md#element-definitions); pure Python. Its wheel metadata has no license field; the MIT text ships as its license file |
| `sympy` | symfem | BSD-3-Clause AND MIT | Pure Python. Metadata says BSD; the license file adds code from Diofant, multipledispatch and PyDy (BSD-3-Clause) and latex2sympy (MIT) |
| `mpmath` | sympy | BSD-3-Clause | Pure Python |
| `appdirs` | symfem | MIT | Pure Python |

First-party test extras also require `galerkin-refsol`, `meshine` and `gmshio`,
which are Apache-2.0 packages of this repository.

### CI tools

| Distribution | Purpose | SPDX |
|---|---|---|
| `build`, `pyproject-hooks`, `wheel`, `setuptools`, `pip` | Build and install distributions | MIT |
| `maturin` | Build meshloom's compiled kernel; not shipped | MIT OR Apache-2.0 |
| `twine`, `id`, `readme-renderer`, `requests`, `requests-toolbelt`, `rfc3986` | `twine check --strict` | Apache-2.0 |
| `docutils` | README rendering in twine | LicenseRef-Public-Domain AND BSD-2-Clause AND 0BSD (its GPL classifier covers files that are not in the wheel) |
| `nh3`, `rich`, `markdown-it-py`, `mdurl`, `keyring`, `jaraco-classes`, `jaraco-context`, `jaraco-functools`, `more-itertools`, `jeepney`, `urllib3`, `charset-normalizer` | twine dependencies | MIT |
| `cffi` | cryptography | MIT-0 |
| `cryptography` | secretstorage | Apache-2.0 OR BSD-3-Clause |
| `secretstorage`, `pycparser` | keyring, cffi | BSD-3-Clause |

pip vendors a copy of certifi's CA bundle (MPL-2.0), used unmodified. pip and
setuptools also ship Windows launcher executables, and cryptography, cffi and
nh3 statically link native code (OpenSSL, libffi, Rust crates including two
under MPL-2.0); see [bundled components](#bundled-components).

## Bundled components

What the third-party wheels pinned in CI ship inside themselves (policy level 3).
Survey basis: CPython 3.12 wheels of the versions pinned in
`tools/requirements-py312-linux.txt`, on the platforms CI tests (manylinux x86_64,
macOS 14 arm64, Windows amd64), covering runtime, optional, test and tool
wheels. Tool wheels that only the Linux job installs (cryptography, cffi, nh3)
were read on manylinux x86_64 only. The numpy and scipy wheels for macOS
before 14 and the macOS x86_64 wheels of numpy, scipy, shapely, matplotlib and
pillow were also listed. Static linkage was read from the Linux, macOS arm64
and Windows binaries without running them. Header-only libraries and compiler
support code built into extension modules (pybind11 in contourpy and
matplotlib; Cython and mypyc output in fonttools and charset-normalizer) are
not listed. Wheels for other platforms, Python versions or package versions can
differ.

Not surveyed: Linux aarch64, musllinux, Windows arm64, 32-bit Windows (win32),
CPython versions other than 3.12, and versions inside the declared ranges other
than the pins. The packages require Python 3.12 or later with no upper bound;
the pinned numpy, scipy and shapely also publish cp313 to cp315 wheels.

| Wheel | Component | License (SPDX) | Platforms and linkage |
|---|---|---|---|
| `numpy` | OpenBLAS with LAPACK | BSD-3-Clause, BSD-3-Clause-Open-MPI | Shared library on Linux (`numpy.libs/`) and macOS before 14 (`numpy/.dylibs/`); DLL on Windows (`numpy.libs/`). Not bundled on macOS 14 and later, where numpy uses Apple Accelerate |
| | GCC runtime: libgfortran, and libgcc_s on macOS | GPL-3.0-or-later WITH GCC-exception-3.1 | Shared libraries on Linux and macOS before 14. On Windows statically linked into the OpenBLAS DLL, as the wheel's notice states |
| | libquadmath | LGPL-2.1-or-later; the GCC exception does not cover it | Shared library on Linux and macOS before 14. The wheel's notice names the license with a URL but does not include the LGPL text. On Windows it was not found in the stripped DLL, which is inconclusive |
| | winpthreads | MIT AND BSD-3-Clause | Windows: statically linked into the OpenBLAS DLL; not named in the wheel's notice |
| | Microsoft C++ runtime `msvcp140.dll` | Microsoft redistributable terms | Windows: separate DLL; the wheel carries no notice for it |
| `scipy` | OpenBLAS with LAPACK | BSD-3-Clause, BSD-3-Clause-Open-MPI | Shared library on Linux (`scipy.libs/`) and macOS before 14 (`scipy/.dylibs/`); DLL on Windows. Not bundled on macOS 14 and later (Apple Accelerate) |
| | GCC runtime: libgfortran, and libgcc_s on macOS | GPL-3.0-or-later WITH GCC-exception-3.1 | Shared libraries on Linux (two libgfortran builds) and every macOS version. On Windows statically linked into the OpenBLAS DLL and into the `scipy/odr/__odrpack` extension module; the notice mentions only the DLL |
| | libquadmath | LGPL-2.1-or-later | Shared library on Linux (two copies) and every macOS version. On Windows `scipy/odr/__odrpack` very likely contains it statically (byte-level match, not confirmed by symbols); the notice does not mention it |
| | winpthreads | MIT AND BSD-3-Clause | Windows: statically linked into the OpenBLAS DLL and several extension modules |
| | Qhull | Qhull | All platforms: statically linked into `scipy/spatial` |
| `shapely` | GEOS | LGPL-2.1 (the notice states no "or later" option) | Separate shared libraries `geos` and `geos_c` on Linux (`shapely.libs/`), macOS (`shapely/.dylibs/`) and Windows (`shapely.libs/`), loaded by shapely's extension modules. Built by shapely from the upstream release without patches; wheel repair tools rename the files and rewrite their library paths. `LICENSE_GEOS` includes the full LGPL-2.1 text but no GEOS copyright line |
| | `msvcp140.dll` | Microsoft redistributable terms | Windows: separate DLL, notice in `LICENSE_win32` |
| `matplotlib` | FreeType | FTL OR GPL-2.0-or-later; used under the FTL | All platforms: statically linked into `ft2font` |
| | HarfBuzz, libraqm, SheenBidi | MIT-Modern-Variant, MIT, Apache-2.0 | All platforms: statically linked into `ft2font` |
| | Qhull | Qhull | All platforms: statically linked into `_qhull` |
| | Fonts and font metrics | OFL-1.1 (STIX, Last Resort), BaKoMa Fonts Licence, Bitstream Vera terms (DejaVu), Adobe terms (AFM files) | Data files |
| `pillow` | libjpeg-turbo, libpng, libtiff, libwebp (with sharpyuv, mux and demux), OpenJPEG, Little CMS, libavif (with aom, dav1d and libyuv), Brotli, liblzma, zstd (Linux) or zlib-ng (macOS), FreeType, HarfBuzz, libxcb, libXau | Permissive, as stated in the wheel's notice; FreeType is FTL OR GPL-2.0-or-later, used under the FTL | 18 shared libraries on Linux (`pillow.libs/`) and macOS (`PIL/.dylibs/`); statically linked on Windows. The xz section's LGPL and GPL text covers command-line tools that are not included; the bundled liblzma (xz 5.8.3) is 0BSD upstream, although the notice keeps the older public-domain wording. FriBiDi (LGPL) is not bundled; Pillow loads it at run time only if the system provides it |
| `pydantic-core` | Rust crates (pyo3, regex, serde_json, icu_normalizer and others) | MIT, Apache-2.0, Unlicense OR MIT, Unicode-3.0 | Statically linked; the wheel carries only pydantic-core's own license |
| `pyyaml` | libyaml | MIT | Statically linked into `_yaml` |
| `pip` | certifi CA bundle | MPL-2.0 | Vendored data file, used unmodified |
| | Windows launcher executables (`pip/_vendor/distlib/t*.exe`, `w*.exe`) | BSD-2-Clause (distlib's `PC/launcher.c`) | Installed on every OS, run only on Windows; they import no C runtime DLL. The wheel carries distlib's PSF-2.0 license text but not the launcher's BSD notice |
| `setuptools` | Windows launcher executables (`setuptools/cli*.exe`, `gui*.exe`) | MIT (setuptools' `launcher.c`) | Installed on every OS, run only on Windows; they load the Microsoft C runtime (`VCRUNTIME140.dll`, Universal CRT) from the system |
| `cryptography` | OpenSSL 4.0.3 | Apache-2.0 | Linux job only: statically linked into the `_rust` extension module (the wheel's SBOM records a `no-shared` build) |
| `jaxlib` | BoringSSL, gRPC, Abseil, Protocol Buffers, Eigen, LLVM, oneDNN and the other components its `LICENSE.txt` reproduces | Apache-2.0 for jaxlib's own modules; statically contained components under their own permissive terms, Eigen MPL-2.0 (file-level weak copyleft, compiled and shipped by jaxlib's publisher) | Linux job only (`galerkin[jax]`): statically linked into jaxlib's own modules (`jaxlib/*.so`, including `cpu/` and `mlir/_mlir_libs/`); no separately built third-party library. Read from jaxlib 0.12.0.1 |
| `torch` | Third-party code reproduced in `dist-info/licenses/third_party/`; GNU libgomp | torch's declared expression; libgomp GPL-3.0-or-later WITH GCC-exception-3.1 | Linux job only (`galerkin[torch]`, CPU wheel): static in torch's own `torch/lib/lib*.so`; libgomp as a separate shared library. Read from torch 2.14.1+cpu (`torch/lib/`: torch's own libraries, four of them test or example libraries, and `libgomp.so.1`) |
| | Rust crates (pyo3, asn1, the openssl bindings and others) | Mostly MIT OR Apache-2.0; also BSD-3-Clause, Unicode-3.0 (unicode-ident) and Apache-2.0 OR GPL-2.0-only (self_cell, used under Apache-2.0) | Statically linked; listed in the wheel's CycloneDX SBOM |
| `cffi` | libffi | MIT | Linux job only: statically linked into `_cffi_backend`; the wheel carries only cffi's own MIT-0 license |
| `nh3` | Rust crates (ammonia, html5ever, ICU4X and others) | Mostly MIT OR Apache-2.0 or MIT; Unicode-3.0 (ICU4X); MPL-2.0 (cssparser, dtoa-short) | Linux job only (twine dependency): statically linked into the extension module and listed in the wheel's CycloneDX SBOM. MPL-2.0 is file-level weak copyleft; the crates are used as the wheel's publisher compiled them |
| `gmsh` | libgmsh, with OpenCASCADE, FLTK and other libraries inside | GPL-2.0-or-later with the Gmsh exception | Shared library installed under the environment's `lib/` directory, loaded only by Gmsh's own Python module inside the separate `gmsh` process (see [external programs](#external-programs)) |

The gaps in upstream notices noted above (libquadmath without the LGPL text, no
notice for numpy's `msvcp140.dll` or for winpthreads, the static GCC runtime and
libquadmath in scipy's Windows extension module, no GEOS copyright line, no
libffi notice in cffi, no BSD notice for pip's launchers) do not create
obligations for OpenPhysics while it redistributes none of these wheels.
They matter for anyone who redistributes them.

Re-check this section on all three CI platforms when a pin changes, when CI adds
a platform, wheel tag or Python version, when a dependency is added, when a
package gains compiled code, or before OpenPhysics code would load a bundled
library directly.

## External programs

| Program | License | How it is used |
|---|---|---|
| Gmsh (pip distribution `gmsh` in `gmshio[gmsh]` and CI, or a [`gmsh`](https://gmsh.info) executable installed by the user) | GPL-2.0-or-later, with an exception that permits combining Gmsh with Netgen, METIS, OpenCASCADE and ParaView (Gmsh `LICENSE.txt`) | `gmshio` writes a `.geo` script, runs `gmsh` as a separate process and reads the `.msh` file with an original parser written from the published format description. The pip distribution's `gmsh` command is a launcher script that loads Gmsh's own Python module and `libgmsh` in that separate process. Package code never imports `gmsh` (checked) and nothing is bundled; see [gmshio NOTICE](../packages/gmshio/NOTICE) |
| NGSolve with Netgen (pip distributions `ngsolve` and `netgen-mesher`) | LGPL-2.1-only (their package metadata) | Reference tool for the [material cavity comparison](packages/galerkin/material_cavity.md#reference-tool-comparisons). Installed from PyPI wheels into a separate environment and run as a separate process; not a dependency and not installed by this repository's CI. Only numerical results are reported and no code is copied. Its wheels also install `netgen-occt` (LGPL by its classifier) and, outside macOS, `ngsolve-openblas` (BSD-3-Clause) |
| Node.js | MIT | Runs the Studio JavaScript checks in CI |
| Chrome or Chromium | Chrome terms / BSD-3-Clause | Already-installed browser for the Studio browser check in CI |
| GitHub Actions `actions/checkout`, `actions/setup-python`, `actions/setup-node`, `actions/upload-artifact` | MIT | CI only, pinned by commit |

## Data and published numbers

| Source | Terms | How it is used |
|---|---|---|
| [refractiveindex.info database](https://github.com/polyanskiy/refractiveindex.info-database) | CC0-1.0 | A subset of tables and dispersion coefficients is embedded in physmat (`physmat/_tables.py`, `physmat/library.py`). CI fetches the commit pinned in `tools/rii-revision.txt`; that copy is not shipped. Citation and per-record sources: [physmat NOTICE](../packages/physmat/NOTICE) |
| G. R. Hadley, J. Lightwave Technol. 20(7), 1210 (2002) | Published facts | Benchmark values in `galerkin-refsol`, cross-checked against tables published with femwell (GPL-3.0); only the numbers are reproduced, no code or text. See [galerkin-refsol NOTICE](../packages/galerkin-refsol/NOTICE) |
| NAFEMS T4 benchmark target (18.3 °C at (0.6, 0.2) m), as quoted by the DIANA FEA tutorial (citing NAFEMS, *The Standard NAFEMS Benchmarks*, 1990) and FEATool `ex_heattransfer4.m` (citing Cameron, Casey and Simpson, *Benchmark Tests for Thermal Analysis*, NAFEMS, 1986) | Published facts | Problem statement and target in `refsol.thermal_convection`; only the numbers are reproduced, no text or code from either document. See [galerkin-refsol NOTICE](../packages/galerkin-refsol/NOTICE) |
| Handbook-type thermal and mechanical constants | Approximate example inputs | Not certified measurements; see [asset provenance](assets.md) |

## Reference tools for comparisons

Solver comparisons that run other finite-element tools are recorded separately
from the analytical acceptance references. Agreement between two tools is not
used as convergence evidence. Only permissive tools are installed through the
test-only `crosscheck` extra, by choice, and listed above; the record format and
current cases are in [reference comparisons](reference-comparisons.md).
Weak-copyleft tools (NGSolve, listed under [external programs](#external-programs))
and GPL tools are not imported or installed by this repository: they run, if at
all, as separately installed, unmodified programs in their own environment and
process, their source is not read or copied, and only numerical results are
reported. AGPL tools are not used here.

## Automated check

```bash
python tools/check_licenses.py --report .validation/licenses.json
```

The check reads installed metadata and each distribution's RECORD file list with
`importlib.metadata`, so no license scanning tool is installed. It fails when:

- an installed distribution has no reviewed entry in the inventory;
- installed metadata declares a different SPDX expression, or mentions a
  copyleft license the entry does not record (unless the entry explains why);
- a runtime or optional dependency of a first-party package is not permissive
  (external processes are checked by the GPL rule below instead);
- a weak-copyleft test or tool dependency is not marked `test_only`;
- a GPL distribution is not an external process, is a base runtime
  requirement, or is imported by first-party code;
- an identifier of the AGPL family or another network-copyleft family (SSPL,
  EUPL, OSL, CPAL, RPL), in any version, deprecated or `+` form or LicenseRef-
  name, appears in an inventory entry or `bundled_files` record, or installed
  metadata names one, even for an external process;
- a first-party package does not declare Apache-2.0, or a first-party
  distribution contains any native file (`.so`, `.dylib`, `.dll`, `.pyd`);
- a third-party distribution installs a shared library (`.so`, `.dylib`,
  `.dll`) other than its own Python extension modules that matches no
  `bundled_files` glob of its inventory entry, or matches one that is not
  recorded for the current OS;
- a `bundled_files` record has no review although its SPDX expression is
  copyleft or not plainly permissive (proprietary or non-standard terms such as
  LicenseRef- ids, FTL or Qhull), or a distribution has no RECORD file list to
  check;
- a `bundled_files` record of a distribution that is not an external process
  leaves only GPL terms without a runtime exception listed in the policy (such
  a library would load into the OpenPhysics process);
- this page or its Korean translation does not list every inventory entry.

CI runs it on the pinned Linux environment, on the fresh environments holding the
installed wheels (distribution check and installed tests), and in the
installed-platform check on Linux, macOS and Windows, so the bundled shared
libraries are compared on each of those OSes. Statically linked code inside
third-party wheels (such as the GCC runtime in the Windows OpenBLAS DLLs, or
FreeType in matplotlib) is not visible this way; it is reviewed by hand and
recorded in [bundled components](#bundled-components).

To add a dependency: confirm the license in the upstream repository's LICENSE
file, add an entry with the SPDX expression and source URL to the inventory,
list what its wheels bundle on each CI platform, add a row here and in the
Korean page, and record its package NOTICE if it is bundled or copied.

## Stored-tool inventory

`external_tools` in `tools/third_party_licenses.json` records provenance separately from installed dependencies.
NGSolve is stored-only and has no value records yet. The loader and audit follow
[stored reference values](stored-reference-values.md); dependency admission rules are unchanged.

## Reference import boundaries

| Tool | Mode | Scope |
|---|---|---|
| `scikit-rf` | live | Frequency networks and Touchstone; required CI, [scope/cost](packages/sipi/network_validation.md) |
| `scikit-fem` | live | Existing permissive comparison tests; required CI |
| `symfem` | live | Existing permissive element comparisons; required CI |
| `ngsolve` | stored | Separate generation environment; no value records committed yet |

The static zone check reads git-tracked Python source without importing it.
Non-permissive references may be loaded only lazily inside listed test functions,
or in listed generators/studies. Shipped code, examples, conftest files and shared
helpers cannot load them. Gmsh remains a separate-process backend and cannot be
imported anywhere in this tree. Only `gmsh` has the inventory policy's
`external_process_allowlist` exemption; adding an entry cannot grant one.
These boundaries do not admit a new installed tool: the installed-license checker
still rejects in-process GPL/AGPL until an actual qualifying tool is adopted.

Run `python tools/check_reference_zones.py` or
`python -m pytest -q tools/tests/test_reference_zones.py` from the repository root.
See [development](development.md#reference-import-checks) for limits and examples.
