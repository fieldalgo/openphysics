# Validation and distribution checks

[한국어](locales/ko/pages/README.md)

## Queued main validation

Each `main` run of a validation workflow shares a stable workflow/ref concurrency
group with `queue: max` and `cancel-in-progress: false`. One run executes at a time
in that group, preserving up to 100 pending runs instead of replacing them on a
new push. Further runs can be cancelled when that queue is full. Queue entry order
determines processing order; commit or push order is not guaranteed.

Other refs use `queue: single` and cancel superseded runs for the same ref. Different
validation workflows and repositories can still run concurrently, subject to runner
capacity; this does not reserve slots or give PRs scheduling priority. Existing runs
keep their original workflow configuration. Test selection, numerical criteria,
required checks and release gates are unchanged. A release still requires successful
validation of its exact commit. This is a CI execution queue, not a PR merge queue.

## CI policy and installed platform matrix

Validation runs on main pushes, Ready PRs (`opened`, `synchronize`, `reopened`,
`ready_for_review`) and explicit manual dispatch. Feature-branch pushes do not
run CI; every validation job excludes draft PRs, including the Linux aggregate.
Reviewed Ready PRs can use automatic Rebase and merge after relevant checks.
All required checks remain mandatory. Main runs share a stable workflow/ref
group with `queue: max` and cancellation disabled; other refs use `queue: single`
and supersede earlier runs. This is a workflow queue, not a PR merge queue.

| Workflow | Platform | Coverage |
|---|---|---|
| `validate.yml` | Ubuntu 24.04, Python 3.12.14 | Full source suite, seven distributions, strict archive/document checks, installed consumers and Studio Node checks |
| `thermal-windows.yml` | Windows 2022, Python 3.12.10 | Existing installed heat and save-ownership regressions |
| `platform-install.yml` | Ubuntu 24.04, macOS 14, Windows 2022; Python 3.12.10 | Six implementation sdists rebuilt as wheels; fresh isolated consumer environment; package bytes, module origins, bundled assets and public API/CLI/save smoke |

The installed matrix reuses the exact portable pins in
`ci/requirements-py312-windows-thermal.txt`; that historical filename does not
limit this matrix to Windows. It installs dependencies into a fresh venv without
system site packages, installs only the locally built wheels with `--no-index
--no-deps`, then runs outside the checkout with `python -I`. Existing thermal
closed-form/units/save consumers and the scalar slab/reference and Gmsh parser
tests retain their numerical bounds. Consumer tests, examples and MSH fixtures
are copied from the exact checkout and hashed separately; they are not an
assertion that test fixtures ship inside each sdist. A separate public mesh smoke checks
positive element areas and unit total area. No external Gmsh process, full
macOS/Windows regression, RII download or browser runtime is claimed by this
matrix; these checks complement full Linux acceptance.

Each OS uploads `installed-packages-<os>-<run_id>` containing command exits/logs,
environment details, twelve archive checksums, package-byte and consumer-test
hashes, installed origins and pytest JUnit. Run locally or on another runner with:

```bash
python -m pip install -r ci/requirements-py312-windows-thermal.txt
python -X utf8 ci/tools/check_platform_install.py
```

The output directory must be new. Configuration is not proof of a pass: verify
the exact commit's three matrix jobs and artifacts before claiming acceptance.
Python 3.10/3.11 remain outside this CI matrix despite the package metadata floor.

## Current checkout and evidence

This page describes the implementation in this checkout. Named historical snapshots retain their original results and limitations. For validation of another commit, inspect that commit's CI logs and artifacts.

The retained GitHub Actions Linux, narrow Windows and platform-install workflows
run on main pushes, Ready
pull requests and explicit manual dispatch. Check each exact run, exit status and artifact; enabling
CI does not itself establish acceptance. Earlier Work-cloud results retain
their original source, environment and scope.

`platform-install.yml` is a reusable workflow called by `validate.yml`, so the
existing required `tests` aggregate waits for both full Linux acceptance and
every installed-platform matrix job. A failed or skipped platform prevents that
aggregate from passing. This preserves the existing protection names and avoids
an independent, non-blocking platform workflow. It also supports explicit manual
dispatch; a standalone manual run does not replace PR validation.

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
The hard-link file-pin candidate `636a23a` passed 36 installed API/CLI/save cases
and 3 source target-protection cases on this runner
([run](https://github.com/fieldalgo/openphysics/actions/runs/38858254797)).
The unchanged replacement fixtures now pass; previous failures remain historical
evidence. This is narrow acceptance, not full Windows or macOS support.
Saving on Windows requires a filesystem supporting same-volume hard links and
exclusive caller control of temporary sibling pin directories. Unsupported
filesystems fail explicitly. See the [save contract](../../packages/simcase/docs/thermal_steady2d.md).
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

The root `validate.yml` workflow runs on main pushes, Ready pull requests and manual dispatch.
It tests CPython 3.12.14 and Node.js 24.19.0 on Ubuntu 24.04. Python 3.10/3.11
remain outside this CI coverage; the separate installed matrix covers three operating systems; the package metadata
still declares Python >=3.10. `requirements-py312-linux.txt` pins the validation
tools and their transitive dependencies, not the packages' runtime requirements.
Review and update the pins deliberately, then rerun both source and wheel checks.

Repeatable vector timing, memory and profiling commands are documented in
[benchmark_vector.md](benchmark_vector.md). Performance measurements supplement
the numerical checks; they are not CI timing gates.

POSIX-shell Linux validation commands, from the repository root with a Python 3.12 virtual environment active (these Linux dependencies are not a portable platform matrix):

```bash
python -m pip install -r ci/requirements-py312-linux.txt
python -m pip install --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pip check
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python ci/fetch_rii.py .validation-rii
export PHYSMAT_RII_PATH="$PWD/.validation-rii/database"
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
known integrated revision; they require network access. A passing check does not certify fully offline
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
another writer mutate the output during this interval. Windows replacement fixtures recovered at `636a23a` in the narrow gate described
above; this does not expand the ownership contract or establish full platform
support. GitHub Actions is enabled; evaluate every candidate against its own runs.

## Packaged independent acceptance

All seven English/Korean package overviews under docs/ and received Korean guide
counterparts are required byte assets. Entry-point READMEs remain English. The standalone outward-flux/Robin contract, example,
independent report/oracle/test and `refsol.thermal_boundary` are included verbatim.
The headless independent EN/KO report, oracle, test and stale-state Node file
are likewise required. The current required-byte list contains 136 entries;
the headless transient additions are detailed below.
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
Distribution validation does not publish a release or expand platform support.

Work-cloud checks use the available Linux/Python 3.12.14 environment with
numpy 2.3.5 and scipy 1.17.0, not the retained pinned CI environment. Gmsh and
an explicit RII database are unavailable; record actual skips. Twine is absent,
so its strict check is unexecuted unless an existing tool becomes available.
Do not infer Windows acceptance from Linux results. Actions is enabled; inspect the exact workflow result.

## Explicit workflow source reproduction assets

The steady heat-to-mechanics workflow module, EN/KO guide and English example,
plus the original producer test files `test_thermal_mechanical_workflow.py`,
`test_thermal_mechanical_workflow_physics.py` and their
`thermal_mechanical_workflow_oracle.py` helper are explicit byte-checked sdist
assets. The guide's `packages/galerkin/...` physics commands are repository-root
commands; an extracted galerkin sdist has a package root with `tests/` and
`examples/`, not the monorepo's `packages/galerkin/` layout. Including the helper
preserves the producer tests' imports; inclusion alone is not a new test result.

Installed validation uses the original independent acceptance suite and the
verified archived English example. It does not add a duplicate physics oracle
or rerun every producer case. The source engine dependency guard is not copied
blindly outside its package tree: its `ENGINE` path must point to actual engine
modules, or an empty-directory scan could pass vacuously. Source guard execution,
explicit installed-ENGINE checks and wheel module-byte checks have separate scopes.

The explicit workflow's independent EN/KO report, original oracle and test are
required verbatim source assets. Installed checks retain all 299 existing cases
and add the original 90-case independent workflow suite without mirroring its
physics formulas or changing gates. Counts, failures and optional skips must be
reported from the actual execution. The verified sdist English workflow example
is also run with installed wheels under `python -I`, outside the checkout.
The guard stays in source; its six tests scan actual engine files. Installed
module origins and wheel module bytes are checked separately. This packaging
check does not add schema/CLI/Studio support or certify thermodynamic coupling.

## Prescribed-temperature total-traction distribution contract

At the pre-publication traction snapshot, the required byte inventory contained92 entries: the previous79 plus13 exact traction implementation/reference/guide/example/producer/independent assets. Publication then replaced seven Korean READMEs with fourteen docs overview pages, giving99 entries before the transient implementation's15 additions. Original independent reports and tests retain their historical counts and failures. The installed suite preserves389 prior cases and adds the original producer/reference/convergence files and independent90; report actual collected counts, failures and optional skips rather than treating planned totals as passing. The four standalone original `python -I` consumer checks run separately, as does the actual archived English example. No copied engine guard may scan an empty directory; source guard6 and installed origins/module bytes remain separate checks.

The new Python API applies total physical `sigma*n` on the prescribed-temperature mechanical stage. There is no scalar-pressure keyword/local-frame/follower API; global Pa `-p*normal` callbacks on fixed reference geometry are valid. The one-way heat workflow and JSON/CLI/Studio remain unchanged. Producer reproduction commands use the repository root; extracted sdists have package-local `tests/` and `examples/` paths. Both original test files and required oracle/reference sources are shipped explicitly.

Individual candidate measurements90/90/isolated4/related208/wrong17 do not establish a combined whole or installed result. The independent report preserves the original whole1385pass/7CLI-environment failures/16skip/+9subtests and target7 recovery as distinct evidence. New results must identify the exact source and real archives, actual failures and optional skips. GitHub Actions is enabled; distinguish new workflow results from these historical measurements. Linux results cannot establish Windows acceptance, and core metadata parsing does not substitute for unavailable twine strict checks.

Both workflows gate every main-targeted PR, including documentation changes.
Their required check names are `tests` (the always-run Linux completion job)
and `windows-py312-thermal`. Green PRs land via GitHub Rebase and merge;
record the new main SHA and require green main checks before releasing.
Main push runs are never cancelled by a newer push; branch/PR runs may be superseded.
Tags do not trigger these workflows, and neither workflow publishes packages.
## Transient heat distribution checks

This checkout contains the transient heat implementation and its verification gates.
Full physical, independent and distribution acceptance requires exact current CI
evidence; implementation alone is not a validated release. The [implementation contract](../../packages/galerkin/docs/transient_heat.md)
and [independent report](../../packages/galerkin/docs/transient_heat_independent_validation.md)
separate the producer's recorded 70 small source tests from the remaining gates.

The engine-only stage had 114 required entries: the public baseline's 99 plus 15 transient
assets. These cover six EN/KO pages, the English convergence example, both new
runtime modules, original producer/reference tests and all four independent
oracle/cases/pytest-wrapper/consumer files. Existing metadata/license, archive
link, historical-JSON and traction acceptance checks remain intact.
Both new runtime modules must also match wheel bytes. An isolated installed
preflight verifies venv origins and source SHA256 and writes
`transient-module-origins.json` alongside the artifacts.

Existing installed pytest files remain unchanged; the two original transient
producer/reference test files are added. The independent discovery wrapper is
a source-reproduction asset and is not additionally copied into installed pytest.
Instead, the original standalone consumer and its oracle/cases are read from the
verified sdist and run once with `--suite all`, including the frozen PDE,
companion and quadrature gates. The complete archived English convergence
program then runs with `python -I`. Neither `core` nor a shortened smoke
replaces these gates. Each stage runs sequentially; failure leaves later stages
unexecuted and must retain the original exit/logs.

```python
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path.cwd()  # Run this script from the repository root.
env = os.environ.copy()
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    env[name] = "1"
output = Path(tempfile.mkdtemp(prefix="openphysics-transient-")) / "distributions"
print("Validation output:", output)
subprocess.run([sys.executable, "ci/check_distributions.py", "--output", str(output)], cwd=root, env=env, check=True)
```

Use an empty owned output directory and the documented validation dependencies.
This is a reproducibility command, not evidence that the candidate has built or
passed. Report pytest JUnit, independent unittest cases/subtests, archive program
results and native prerequisites separately. Existing 541-case traction history
and its standalone consumer4 are baseline evidence, not new transient counts.
That engine-only stage did not add transient JSON/CLI or persistence. The current
headless API, JSON/CLI and saved histories are covered below. Transient Studio,
Robin/flux input and automatic thermal-mechanical coupling remain unsupported. CI and any cloud
experiments require exact-source evidence before acceptance; Linux results do not
establish Windows support.

## Headless transient distribution validation

The Linux job first runs the tiny-domain and general-state engine regressions,
transient document, runtime, independent acceptance,
Studio refusal and portable save tests. Their JUnit report is
`transient-preflight.xml`. A failure stops that job before the expensive full
suite; it is a failed check, not a successful subset or a skipped acceptance
requirement. On success, the complete source and installed suites below still
run with their existing numerical gates.

The helper preserves the existing engine independent `--suite all` PDE and complete
archived convergence example. It additionally requires 20 simcase source assets
(runtime/dispatch and ownership modules, two usage pages, the JSON example,
producer/contract/Studio/Windows tests and four independent acceptance files),
plus the two original tiny-domain/general-state engine regression files, for
136 required assets in this checkout. Both regression files also run from the
verified sdist in installed pytest. These are inclusion gates, not measured
pass counts.

The two new runtime modules and the existing dispatch/schema/ownership modules
are checked against wheel bytes and imported with `python -I` outside the
checkout; `installed-module-hashes.json` and `transient-module-origins.json`
record their expected hashes and actual installed origins. Original contract,
runtime, Studio and save tests are extracted from the verified simcase sdist
into installed pytest. The original independent headless consumer and its
oracle/cases are extracted separately and run with
`--expected-installed-root` and `--expected-module-hashes`; its unittest count
is separate from installed pytest and the engine's 17-case independent suite.
The verified JSON example is consumed by isolated CLI validate/run with a fresh
output directory. Source tests remain part of the complete root pytest command.

The narrow Windows job adds all 12 tests in
`test_transient_headless_windows.py` to its existing installed selection and
retains the existing steady installed and source target-protection tests.
It records explicit installed module origins/hashes before consumers. These
checks do not constitute full Windows transient PDE or macOS acceptance; inspect
the exact run's failures, skips, counts and artifacts.

After a successful build/consumer run, the Linux workflow independently audits
the retained archive bytes without repeating consumers:

```text
python ci/tools/audit_distribution_artifacts.py --artifacts .validation/dist --report .validation/distribution-audit.json
```

The report path must not already exist. This audit reuses the checkout's required
asset/link checks and validates all 14 checksums and configured runtime wheel
bytes. It does not replace twine strict, installed execution, independent physics
or verification of the exact source commit. Never present a configured command
or historical baseline as a new candidate pass.

## Steady boundary contract and independent distribution gates

The published boundary helper and its original test, the English/Korean usage
and independent-report pages, and all four original independent acceptance files
are required byte assets. The existing steady engine module is additionally
required and checked in wheel bytes because the independent installed consumer
requires its exact identity. The current inventory is 153 assets: the retained
P1 136, two boundary contract assets, eight documentation/acceptance assets,
one steady engine source and six schema/runtime/example/platform assets. Counts describe configuration, not passes.

A separate steady boundary preflight runs the original contract, schema, runtime,
independent, save/platform and Studio source entry points before the unchanged P1 preflight and whole suite. Failure
fails the job and leaves later stages unexecuted. Successful preflights do not
replace the whole suite. Required completion checks and main run preservation
remain unchanged.

The steady preflight also runs the legacy `test_thermal.py` and
`test_thermal_simcase_independent_validation.py` consumers. Save tests configure
names and `save_fields` before solving: editing a completed result's document
invalidates its captured calculation. Concurrent-writer tests retain their
single-winner and complete-artifact checks; nonfinite-metadata tests must fail
for nonfinite data, not an unrelated document edit.

The original independent oracle/cases/consumer are extracted from the verified
simcase sdist and run outside the checkout using `python -I`,
`--expected-installed-root` and `--expected-module-hashes`. The original contract, schema, runtime,
save/platform and Studio tests are also consumed by installed pytest. The hash manifest includes all six
identities required by the steady consumer; there are 13 configured runtime
modules including existing transient and dispatch identities. Standalone
unittest, installed pytest, preflight and whole-source counts are separate.
Existing transient independent 17/headless 9/full archived convergence and
Windows regressions remain intact.

These connections require a combined boundary-enabled schema/runtime candidate.
Published draft documents and defined tests do not certify current API/CLI,
build, installed or platform success. The schema/runtime tests, thermal_boundary.json and platform tests now refer to
reviewed, published files; no unposted path is required here. The verified JSON
example is validated and run through the installed isolated CLI with a fresh output. Inspect the exact combined CI and artifacts.
The retained-artifact audit command above applies to this inventory without
repeating numerical consumers. No package publication is performed.

The Node source gate additionally runs `studio_steady_boundary.cjs`; its original
bytes are required in the simcase sdist. This is source UI validation, not a claim
of a separate installed Node execution. The Windows installed selection includes
the complete standalone `test_steady_boundary_platform.py` alongside every
existing selected case. Both steady boundary module identities are added to the
existing Windows origin probe (11 modules total). A separate source target-
protection step consumes the same platform file's three existing-target cases,
retaining the previous source protection step and using separate log/JUnit names
`windows-steady-boundary-source-target.log` and
`windows-steady-boundary-source-target-tests.xml`. Actual counts and skips must
come from exact CI. No new dependency or platform support is implied.

## Steady thermal Studio distribution and browser checks

The checker requires the exact Studio adapter, shipped page/thermal JavaScript,
three original HTTP/acceptance/lifecycle test files, independent fixture, Node
script and both pairs of usage/independent EN/KO pages in the simcase sdist.
Python modules and static resources must match source bytes in wheels; installed
module hashes and `studio-resource-origins.json` verify the isolated venv too.
The original tests are extracted from the verified archive without source
conftest; the independent fixture also requires the unchanged P2 steady-boundary
cases/oracle in that archive. Combine these changes with that feature before
acceptance: the distribution-only branch does not supply production dependencies.
No old engine all17, full convergence, headless or Windows gate is removed.

The Linux preflight writes `studio-thermal-preflight.xml`; a failure remains a
failed check before whole acceptance. Source Node additionally runs the actual
`studio_steady_thermal.cjs`. Browser acceptance is distinct: inside the verified
wheel environment, `ci/tools/studio_thermal_browser.mjs` starts an owned isolated
uvicorn server and uses Node24 built-in WebSocket/fetch CDP with an already
installed Chrome/Chromium discovered by which/version. No npm/Python/browser
download is added. It drives a small real model through Apply JSON, Validate,
Run, temperature/flux, Results/Mesh and dirty-input stale-run rejection. Visible
canvas CSS/backing sizes, console exceptions, PNGs, origins, environment and
owned subprocess exits go to `dist/studio-browser/`. Browser absence is recorded
as unavailable with nonzero exit, never hidden as a passing mock or skip.

Dirty-input checks accept a discarded zero-size canvas backing store without
calling getImageData on an empty region. They also require the result and hover
owner to be absent, thermal controls hidden and Run disabled, both while hidden
and after returning to the visible Results tab. The test never clears or resizes
the canvas itself; dirty-results.png records that return. Positive dimensions
and painted pixels remain required for all successful result-render stages.

After successful validation, one Linux source-server observation runs:

```text
python ci/tools/profile_studio_thermal.py --source-root "$GITHUB_WORKSPACE" --expected-commit "$GITHUB_SHA" --output .validation/studio-resource-observation
```

Fresh owned server processes measure n2/32/100 public API and real HTTP phases,
actual capture_result/encode_json hooks, ten result reads, encoded bytes,
tracemalloc and RSS, additional job admission/oldest terminal eviction and server
shutdown. Hook timings overlap; never sum nested times. TTL300s is a maximum,
not minimum retention; evicted/expired jobs return404 without automatic rerun.
run_enabled describes configured public API availability, independently of
candidate-unmeasured resource policy. Fixed workloads and shared runner metrics
are observations, not capacity/performance certification. No fake physics or
limit patch is used. Partial reports are retained by the existing always-upload
step. These configured commands are not evidence of a completed exact run;
report actual CI exits, counts and artifacts. Browser, numerical independence,
source resource observation and Windows remain separate acceptance scopes.


## Transient Studio distribution and numerical evidence

The transient Studio preflight runs the published producer HTTP, independent
acceptance and lifecycle tests before the full source suite. A preflight failure
fails the job; later stages are not acceptance evidence when they did not run.
The independent fixtures and their original headless cases/oracle are extracted
from the byte-verified simcase sdist before isolated installed pytest. Their
SHA256 values are retained in `dist/transient-studio-consumer-assets.json`.
The shipped transient CJS runs with the existing source Node scripts and with
the steady CJS against verified installed static bytes. Node fixtures are not
physical, installed-Python or native-browser acceptance.

Successful numerical diagnostic JSON printed by a test must remain available,
not just failed-test output. The transient preflight and the existing installed
pytest invocation both use these options, without a second test run:

```text
-o junit_logging=all -o junit_log_passing_tests=true
```

The always-uploaded `studio-transient-preflight.xml` and
`dist/wheel-tests.xml` contain passing-test captured stdout in testcase
`system-out` (and captured logging/stderr where applicable). Preserve the
original XML and its hash; decode the JSON records without rounding or changing
thresholds. Report actual testcase, subtest and suite-reported counts separately,
and inspect failure/error/skip elements. Configuration alone is not evidence of
an executed or passing numerical case. The full source, existing installed,
independent all-suite/full-convergence and required platform gates remain intact.


The installed browser check also consumes the verified archived
`transient_thermal_uniform.json` through the shipped transient page. It checks
exact last/first/nonuniform-middle stored indices, T and qx/qy/magnitude with
current-frame raw ranges, explicit bounded H/V pages and their displayed raw
values/units, then Mesh/Results visibility. A real in-flight frame is invalidated
by dirty JSON before its asynchronous success/finally can publish. An explicit
second user run followed by a browser-local offline negative control checks an
obsolete transport error/finally without fabricating response bodies or physics.
The offline condition is restored in a finally block. Report this negative
control separately from the successful real HTTP solve/read evidence.
`browser-report.json` retains transient frames/history/raw labels, transport
failures, hidden/visible invalidation and the existing owned-process cleanup.
`transient-dirty-results.png` and `transient-error-dirty-results.png` retain the
empty visible result after each obsolete read. Existing steady browser checks
remain mandatory. Configured browser scenarios still require exact CI execution;
a syntax check or Node fixture is not native-browser acceptance.


## Transient Studio resource workload artifacts

After the preserved steady resource observation succeeds, Linux runs the exact
transient wrapper once with the same successful-job condition:

```text
python ci/tools/run_transient_resource_workloads.py --source-root "$GITHUB_WORKSPACE" --expected-commit "$GITHUB_SHA" --output .validation/transient-resource-observation
```

The existing always-upload of `.validation/` retains
`transient-resource-observation/workload-summary.json`, each workload's stdout
and stderr, generated input documents and each `*-observation/instrumented-report.json`
with raw HTTP evidence. The small, medium and near-raw-candidate workloads use
separate fresh processes. The near workload also supplies the over-budget actor
and requires its 413 refusal before solve; completed capture requires each of
13 public getters exactly once. Preserve failed or partial stages and original
exit codes. An absent stage after earlier failure is not a successful measurement.
These are instrumented workload observations, not physical acceptance, maximum
capacity, RSS bounds, leak proof or dedicated performance baselines. Review the
exact source commit, all three exits, getter counts, raw responses and accounting
reports separately from source/installed/browser/platform gates. No extra CI
run is created by this step, and the existing steady observation remains intact.
