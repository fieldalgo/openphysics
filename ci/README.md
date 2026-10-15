# Validation and distribution checks

[한국어](locales/ko/pages/README.md)

GitHub Actions is currently disabled by user instruction. Do not enable, dispatch
or rerun it. Workflow commands below describe retained definitions, not current
GitHub-runner execution. Current verification runs only in the Work cloud.

## Narrow Windows headless thermal gate

`thermal-windows.yml` runs Python 3.12.10 on GitHub-hosted windows-2022. It
builds four local wheels (galerkin, meshine, physmat, simcase), installs them
without an index or dependency resolution into a consumer venv, and runs the
dedicated heat document consumers plus selected shipped save/I/O tests outside
the checkout with `python -I`. The selected tests exercise actual API/CLI saves,
numeric raw output, existing files/directories/dangling links, partial failures,
file/directory replacement and concurrent ownership. Failures are not skipped.
The consumer venv reuses the pinned job dependencies through system-site-packages;
this is not a clean-room dependency installation.

The Windows requirements reuse a minimal subset of the Linux exact versions.
The Windows pytest/build transitive `colorama==0.4.6` is pinned separately; its
upstream tag identifies BSD-3-Clause in pyproject metadata and LICENSE.txt.
No runtime requirement or package version is changed. This gate does not certify
Windows full regression, optical/Gmsh behavior or broader OS/Python support.
Windows save/cleanup acceptance remains incomplete, with two shipped replacement
cases unresolved in the last executed native-handle candidate. GitHub-runner
verification is stopped. This retained workflow is a reproducibility definition,
not a passing Windows support claim; Linux passes cannot substitute for it.
Windows logs/JUnit/environment and four wheel checksums use the separate
`windows-thermal-installed-and-io-<run_id>` artifact. Linux full source, all seven
sdist-to-wheel/strict/metadata/byte/link gates and the existing 88 consumers remain
required. The Linux Node step also runs the shipped `studio_thermal.cjs` guards.

The headless heat consumer adds independent SI slab and signed mixed-source
closed forms, unique corner constraints, numeric version/units/shape checks and
verified archived JSON examples. Its finite-element smoke bounds use analytic
source curvature and cell size, not summary-to-summary comparisons. These
installation checks do not replace independent convergence/ownership acceptance.
The save implementation's platform validation and any observed failures must
be assessed from the exact candidate's CI, rather than inferred from this workflow.

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
node --test packages/simcase/tests/studio_vector.cjs packages/simcase/tests/studio_thermal.cjs packages/simcase/tests/thermal_simcase_independent_stale.cjs
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

## Installed prescribed-temperature mechanical stage

`test_thermoelasticity_wheel.py` supplements the existing 58 installed consumers.
The checker includes the prescribed-temperature contract and English example in
the galerkin sdist and requires the automatically included
`refsol/thermoelasticity.py` to match the source byte-for-byte. It executes the
verified archived example outside the checkout with `python -I`.

The additional consumers use an independently written original isotropic 3D law
at E=70 GPa, nu=0.3, alpha=12e-6/K and delta T=20 K. Free plane stress has
u=alpha*deltaT*(x,y), zero stress and zero physical energy. Free plane strain has
u=(1+nu)*alpha*deltaT*(x,y), zero in-plane stress, sigma_zz=-16.8 MPa and
2016 J/m physical elastic energy on a one-square-metre domain. Constrained
uniform fields independently check consistent boundary reactions and physical
energy. Cooling, negative/zero alpha, nonzero support work, reference-temperature
shift, copied immutable snapshots, stale geometry/unit metadata, invalid Kelvin
data and rigid modes supplement those cases. Error normalization uses nonzero
eigenstrain or mechanical stress/force/energy scales, never absolute Kelvin
temperature or the computed zero-energy answer.

These are installation/contract consumers, not independent convergence acceptance
or validation of a complete heat-to-mechanics workflow. The API accepts a supplied
same-mesh nodal-P1 Kelvin field; it does not solve heat, automatically connect a
heat result, authenticate provenance, or add simcase/Studio support. Dedicated
independent acceptance remains a separate gate.
The dedicated independent acceptance document, NumPy oracle and tests are
included verbatim and required byte-for-byte in the galerkin sdist. Their
historical candidate and harness-failure records remain unchanged. The six
dedicated implementation/reference/test/doc/example blobs are identical in
the original candidate, its production merge and this release combination;
the final combined source CI separately validates the integrated tree.

## Installed steady heat and boundary traction (existing gate)

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

The independent heat document, JSON acceptance manifest, oracle and tests are
also required sdist assets. The manifest is a historical record for candidate
`aaf948ae38aa82907ca16ef7cdeed75dfa7484ba`; its candidate, environment and failure
fields remain verbatim. The six thermal implementation, reference, document,
example and original-test blobs in recovery
`3102c32874e89c300f21647291db57626c000982` and the historical integrated
`0a44797f73cf67bab14429c982144f0e0e4338aa` / `6cdfa6ca40ac7b7313d3768e3b7ac59c71338e9f`
trees are identical to that inspected candidate. This preserves acceptance
evidence for that unchanged historical thermal implementation. Later thermal
extensions require their own independent acceptance and Dirichlet regression;
the historical manifest does not certify changed implementation blobs. Final
combined CI separately checks interactions. It does not relabel the historical 699 passed / 9 failed / 9 skipped
whole-environment run as passing. The independently reported installed 45 and
original-pair 84 results have their own scopes in that manifest.

Output ownership requires exclusive caller control until save and cleanup finish.
Protection against replacements observed before cleanup is tested; a foreign
replacement between an ownership check and unlink is not guaranteed safe.
Hostile filesystem races and atomic rollback are outside acceptance. Do not let
another writer mutate the output during this interval. Windows save verification
is stopped with two unresolved failures; Linux results do not establish Windows
acceptance. GitHub Actions is disabled; do not dispatch or rerun workflows.

## Combined review candidate: packaged independent acceptance

All seven Korean package READMEs and received Korean guide counterparts are
required byte assets. The standalone outward-flux/Robin contract, example,
independent report/oracle/test and `refsol.thermal_boundary` are included verbatim.
The headless independent EN/KO report, oracle, test and stale-state Node file
are likewise required. The current required-byte list contains 68 entries.
The installed suite preserves the original 105 consumers and adds the original
headless and Robin independent Python acceptance files without editing their
thresholds; report actual counts and skips for each execution. The Node command
runs 22 tests (existing vector 8, thermal guards 6, independent stale guards 8).
These are distinct scopes, not a single physics certification count.

The current Robin implementation and thermal contract differ from aaf. The
six-blob identity statement above applies only to historical 0a/6cdf trees.
The historical JSON and frozen English acceptance documents remain unchanged;
Robin has its own independent acceptance and Dirichlet regression. Headless JSON
still rejects flux/Robin and does not gain thermal Studio UI or automatic coupling.
The candidate awaits owner review and final integration; it is not published.

Work-cloud checks use the available Linux/Python 3.12.14 environment with
numpy 2.3.5 and scipy 1.17.0, not the retained pinned CI environment. Gmsh and
an explicit RII database are unavailable; record actual skips. Twine is absent,
so its strict check is unexecuted unless an existing tool becomes available.
Do not infer Windows acceptance from Linux results. Actions remains disabled.
