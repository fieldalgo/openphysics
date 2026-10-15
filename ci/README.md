# Validation and distribution checks

The root `validate.yml` workflow runs on pushes, pull requests and manual dispatch.
It tests CPython 3.12.14 and Node.js 24.19.0 on Ubuntu 24.04. Python 3.10/3.11
and other operating systems remain outside this CI coverage; the package metadata
still declares Python >=3.10. `requirements-py312-linux.txt` pins the validation
tools and their transitive dependencies, not the packages' runtime requirements.
Review and update the pins deliberately, then rerun both source and wheel checks.

Repeatable vector timing, memory and profiling commands are documented in
[benchmark_vector.md](benchmark_vector.md). Performance measurements supplement
the numerical checks; they are not CI timing gates.

From the repository root, with a Python 3.12 virtual environment active:

```bash
python -m pip install -r ci/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pip check
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python ci/fetch_rii.py /tmp/openphysics-rii
export PHYSMAT_RII_PATH=/tmp/openphysics-rii/database
gmsh --version
python -m pytest -q -ra
node --test packages/simcase/tests/studio_vector.cjs
python ci/check_distributions.py
```

Linux Gmsh also needs the system libraries installed by the workflow. The Gmsh
executable is a separate process; it is not bundled into our distributions.

## Pinned optical database

`rii-revision.txt` is a full commit ID in
[polyanskiy/refractiveindex.info-database](https://github.com/polyanskiy/refractiveindex.info-database).
`fetch_rii.py` fetches exactly that commit and rejects dirty or different cached
checkouts. Change the pin in a reviewed change and run both database tests before
accepting an update. The data has a CC0 1.0 dedication; see its `LICENSE`.
Citation: M. N. Polyanskiy, *Refractiveindex.info database of optical constants*,
Scientific Data **11**, 94 (2024), https://doi.org/10.1038/s41597-023-02898-2.
Data stays outside the source tree and is not included in release artifacts.

Tests honor `PHYSMAT_RII_PATH`. An explicitly configured but invalid path fails
the two database tests, preventing CI from silently skipping them. Without an
explicit path, local tests retain their optional cached-database behavior.

## Distribution validation

`check_distributions.py` builds all seven packages separately, including the empty
`openphysics` name reservation. Each wheel is built from its sdist, using the
pinned build tools (`--no-isolation`). It checks metadata with `twine check --strict`,
checks LICENSE/NOTICE and Studio assets, and writes artifact SHA256 checksums.
It also checks sdist LICENSE/NOTICE, README, build metadata and the Studio page,
and requires the seven wheel identities and versions to match their sdists.
The galerkin cavity solver document and simcase cavity document/JSON file example
must also be present in their sdists and byte-identical to the checked-out files.
A missing or stale document/example fails validation before installed-wheel tests.
The two screenshots linked by the simcase README must also be present and
byte-identical in its sdist; these user documents are not runtime wheel assets.
The galerkin eigenspace contract, both static-elasticity contracts and English
elasticity example must be byte-identical in its sdist. The reference module is
also required byte-for-byte in the refsol sdist; it is automatically packaged
Python code, so no additional refsol manifest entry is needed.
The independent elasticity test and its helper, and the eigenspace test helper,
must also match the checkout in the sdist. Setuptools already includes the test
files; the manifest explicitly includes their otherwise omitted helper modules.
These are source-validation assets and are not runtime wheel modules.
All included Markdown files are checked for inline relative link/image targets
against regular archive members, including percent-decoded paths and fragments.
Current package docs use unspaced inline targets. Reference-style links, Markdown
parsing beyond that syntax, fragment-anchor existence, and external URL reachability
are outside this check. Cross-package/root links use explicit repository URLs at a
known integrated revision; they require network access and repository permission
while this repository is private. A passing check does not certify fully offline
documentation. Neither a wheel nor a single sdist is a monorepo checkout: editable
`packages/...` setup commands require the repository root.

A temporary virtual environment outside the checkout then installs only those
wheels and their declared dependencies, with pinned versions and the optional
Studio, test, RII and Gmsh extras. It checks import locations, absence of editable
installs, all CLI entry points, a scalar slab run and saved results, and the
existing Studio API and Gmsh integration tests. No source `conftest.py` is copied.
The dedicated `test_cavity_wheel.py` additionally requires the cavity-enabled
galerkin and simcase candidates. From installed wheels it reproduces the public
API example and the `cavity_box` CLI workflow, checks JSON/NPZ SI metadata and
field reconstruction with `allow_pickle=False`, checks spectral-only output,
safe rejection of a reused output directory and unsupported plotting, and
confirms that Studio hides and rejects 3D models.
An absent cavity API fails this gate; it is not skipped. These consumer checks
do not certify the numerical mesh-convergence or complete-cluster acceptance
criteria, which remain separate source/independent validation gates. Until the
cavity candidates are integrated, this extension must be tested on a checkout
combining those candidates with these CI changes.
This complements the full source suite; it does not rerun every physics test
against the wheels or exercise browser layout.

The additional `test_multiphysics_wheel.py` consumer requires installed
`galerkin.elasticity` and `refsol.elasticity`. It checks plane stress and plane
strain against a direct uniaxial closed form, rejects unconstrained rigid modes,
and runs the actual English example read from the verified sdist using isolated
Python imports. It also checks complex vector solver outputs and exact NPZ/JSON
preservation, including deterministic non-real phase controls. These checks add
no convergence or completeness claim and do not change existing acceptance
thresholds. Missing modules and examples fail instead of skipping. Static
elasticity has no simcase/Studio or thermal-coupling integration in this gate.

Artifacts default to `.validation/dist/`; use `--output /absolute/empty/directory`
to choose another location. A nonempty output is rejected to avoid stale files.
CI uploads artifacts and JUnit reports even after failures. These are validation
artifacts, not a published release. Build reproducibility here means pinned inputs
and repeatable checks, not byte-identical archives across machines.
The distribution and Node steps also run after a failed source test step, provided
that source testing started and the job was not cancelled. Source failure still
fails the job; independent package evidence must not hide a failed physics gate.

## Preparing a release

The obsolete nested standalone-repository publish workflows have been removed.
GitHub only discovers workflows in the root `.github/workflows/` directory.
No workflow here uploads to PyPI, and no release tag triggers a publication.

Before publishing, select the package and version, check whether that version
already exists on PyPI, validate from a clean checkout, and configure that PyPI
project's trusted publisher for an explicitly reviewed root publishing workflow
and GitHub environment. Each package builds from `packages/<name>`; the repository
root is not a distribution. The name reservation is not an umbrella installer.

For a single package's build-only check, with the pinned build tools installed:

```bash
python -m build --no-isolation --outdir .validation/simcase packages/simcase
python -m twine check --strict .validation/simcase/*
```

Version changes, ownership checks, trusted-publisher registration and actual
publication are separate release tasks. The validation workflow needs only
read access to repository contents and does not request an OIDC upload token.

The archived elasticity example's printed reaction and imbalance checks use the
nonzero applied-load vector norm as a force scale. The total balance tolerance
is relative 1e-9; component comparisons use relative 1e-9 and a dimensionless
1e-12 zero-component floor. This avoids treating roundoff in a zero horizontal
resultant as an absolute N/m accuracy promise. Source convergence, residual and
independent force/moment/energy acceptance gates remain separate.

## Installed steady heat and boundary traction

The existing 37 consumers, including the dimensionless force comparison, remain
unchanged. `test_thermal_traction_wheel.py` adds 21 installed consumers. The checker
copies the two new English examples from their byte-verified sdists, alongside
the existing elasticity example, and executes them outside the checkout with
`python -I`. New contracts, examples and independent acceptance helpers/tests
must match their checked-out bytes in the galerkin sdist; both new refsol modules
must match the refsol sdist and import from the installed environment.

Heat consumers use Kelvin and direct slab/constant-source mixed-insulation
closed forms. They check q in W/m^2, heat load/reaction in W/m of thickness,
outward heat equal to minus reaction, constant/callback source agreement,
constant-temperature offsets, and explicit invalid/nullspace rejection. One
small 8-to-16 mesh interval checks the existing regular-solution P1 order margins
against an independently integrated quadratic closed form. It does not replace
the independent multi-interval source convergence and quadrature acceptance.
Heat balance divides by the sum of absolute loads and reactions, rather than
their potentially zero signed sum. Zero-scale conditions are tested separately.

Traction consumers check both plane models against direct uniaxial/shear formulas,
consistent linear edge loads, outward callback normals under edge reversal,
retained applied loads on prescribed DOFs, duplicate/interior edge rejection,
and None/empty-mapping regression. Mechanical balance uses a nonzero force norm;
energy/work comparisons use their own nonzero energy scale. These comparisons
do not promise an absolute N/m or W/m accuracy floor across unit changes.
The independent source force/moment/work, convergence and error-injection gates
remain distinct requirements. No new platform matrix, dependency or publication
is introduced by these distribution checks.
