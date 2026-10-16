# Independent prescribed-temperature thermoelastic traction acceptance

[전체 한국어](locales/ko/pages/thermoelastic_traction_independent_validation.md)

Exact production candidate **b3e8d7291f7c82788bf813d5d85bca21244f1df5**; independent
code checkpoint **5c08599ac0ffd8b16808e6d37eb4d312f75557b3**. The original-3D
oracle and numerical gates were fixed before inspecting the implementation.
Producer62 and preparation arithmetic are not independent FEM acceptance.
Only dedicated oracle, pytest suite, isolated consumer and this EN/KO report are
added. Production/refsol/original tests/shared configuration remain unchanged.

This extension adds explicit TOTAL mechanical traction to prescribed nodal-P1
Kelvin thermoelasticity. Heat conduction, the separate one-way workflow, Robin,
CLI/Studio, persistence, feedback/transient/nonlinear/3D and locking remedies
are outside this acceptance. It is an endpoint mechanical calculation at fixed T,
not a thermodynamic heating-path work or stored-heat model.

## Independent law, loads and energy

The frozen oracle imports NumPy only. It derives full3D stress/energy by eliminating
PS z or fixing PE z, and obtains the uniform patch by inverse3D compliance. Cubic
MMS body uses explicit Hessian derivatives of the parent stress, with a separately
checked complex-step divergence. No producer/refsol constitutive, load, quadrature,
geometry or reference function supplies truth. Public component solves are targets;
private producer aliases are patched only as runtime fault actors.
```text
mu=E/[2(1+nu)], lambda=E nu/[(1+nu)(1-2nu)], a=alpha(T-Tref)
sigma=2mu(epsilon-aI)+lambda tr(epsilon-aI)I
psi=mu(epsilon-aI):(epsilon-aI)+.5lambda tr(epsilon-aI)^2
PS: (2mu+lambda)ezz+lambda(exx+eyy)-(2mu+3lambda)a=0
PE: ezz=0
q_PS=Ea/(1-nu), q_PE=Ea/(1-2nu), m=(1,1,0)
K u=f_body+f_traction+g, g=integral B^T q m
F=f_body+f_traction, r=K u-F-g
U=integral psi=.5uKu-u.g+CT
2U=u.F+u_D.r_D-u.g+2CT
CT_PS=integral Ea^2/(1-nu), CT_PE=integral 1.5Ea^2/(1-2nu)
```

Engineering shear gamma_xy=2epsilon_xy. Traction is already physical TOTAL
sigma*n: no q*n adjustment. g is a positive thermal equivalent load, not a
second physical external force. It has zero rigid resultant/moment; therefore
zero global balance alone cannot detect misclassification. Nodal load split and
nonrigid work are independently checked. Input traction is Cartesian Pa; body is
N/m³; assembled body/traction/g/reaction/residual are N/m per thickness, moment N,
physical U/work J/m. Heat W/m must not be added to these forces.

Independent Cartesian Vandermonde gradients and Duffy integration reconstruct
actual P1 displacement strain and interpolated temperature inside cells. They
evaluate stiffness actions, body loads, positive g, original residual and reactions.
Independent owner-side segment normals and8-point line integrals audit the4-point
production loader. Degree0..6 traction monomials additionally use exact rational
nodal moments L/[(k+1)(k+2)] and L/(k+2), not a second quadrature implementation.

Full3D stress/energy includes PE sigma_zz and residual .5Ea². Returned total strain
is element constant, while thermal/elastic strain, stress, sigma_zz and epsilon_zz
are centroid samples, checked at those locations. Full stress norms use interior
parent-law reconstruction with actual P1 T; centroid-T squared is not an energy
integral. Nonzero prescribed displacement requires support work. Independently
integrated U, .5uKu-u.g+CT and endpoint external/support work all agree.

## Frozen cases and gates

Uniform theta=20K and target S=[[8e6,3e6],[3e6,-2e6]]Pa, body0. In3D compliance
(epsilon-aI)=[(1+nu)sigma-nu tr(sigma)I]/E, use PS sigma_zz=0 or PE
sigma_zz=nu*tr(S)-Ea, then u=(exx*x+gamma_xy*y,eyy*y)+c. Prescribe exact both
left components, total S*n on right/top/bottom, and separately include left-edge
traction on prescribed components. Heating/cooling, signed/zero alpha, None/{},
zero-S free expansion and joint T/Tref shifts exercise existing contracts.

V2 mixed polynomial and exactly-linear-T control:
```text
L0=1 m; X=x/L0, Y=y/L0; c0=1e-4; c=(2e-5,-1e-5) m
E=70e9 Pa, nu=.3, alpha=12e-6/K, Tref=293.15 K
u=c0 L0(X^3+2XY^2+XY, 2X^2Y+Y^3+X^2)+c
theta=12+9X-4Y+6XY+3Y^2 K
linear-T control: theta=12+9X-4Y K
e=c0(3X^2+2Y^2+Y, 2X^2+3Y^2, 8XY+3X)
d_x e=c0/L0(6X,4X,8Y+3), d_y e=c0/L0(4Y+1,6Y,8X)
b=-(d_x sigma_xx+d_y sigma_xy, d_x sigma_xy+d_y sigma_yy)
```

Left both-component u is prescribed, other sides receive analytic sigma*n.
Analytic T defines body/traction; exact nodal T is frozen as P1. Compare actual
u_h and reconstructed stress against continuum u/T, and audit self-consistency
with P1 T separately. Nonlinear T interpolation error is included in mechanical
consistency; it is not a heat-solver or transfer error. The linear-T control has
exact interpolation and is a distinct manufactured load problem.

The unshifted continuum polynomial has ux=0 and sigma_xy=0 on the left, hence
zero support work. Preserve that exact continuum control. V2 rigid translation
makes work observable without changing strain/stress/body/traction. Actual FE
reactions need not give exactly zero old work on a finite mesh: the acceptance
instead verifies constant u difference, unchanged stress/U and support-work
change c·sum(reaction). It does not impose an unsupported discrete-zero assertion.

Both planes use **n8/16/32/64**. Last TWO intervals16→32 and32→64 EACH require
u L2>=1.8, full-gradient H1/strain-tensor/full3D stress/tangent-energy norm>=.9.
Quadratic-T interpolation requires L2>=1.8/H1>=.9. No rigid/affine fitting.

- Uniform fields, independent body/traction/g split, sample stress, work/U and
  direct edge resultant/moment: normalized<=1e-10.
- Free residual and physical force/moment: <=1e-9; no normalization by cancelling
  net load or zero expected energy.
- Norm quadrature8/10 difference<=1% measured nonzero error; reference physical
  U12/16 difference<=1e-8 characteristic energy.
- Physical-U error decreases on every refinement and final normalized<=.02.
  No new raw-energy convergence-order threshold.
- Exact snapshot identity and invalid refusal controls; no skips/xfails.

Scales: c0L displacement, strain*=max(c0,|alpha|20), sigma*=E strain*,
force*=sigma*L, moment*=sigma*L², U*=E strain*²L²=4032J/m for the1m nominal case.
All thresholds remain the preregistered values;8→16 is diagnostic, not a gate.

## Actual convergence and geometry evidence

Each row lists8→16,16→32,32→64; only the final two are mandatory.
| Plane / T | u L2 orders | H1 orders | strain orders | full3D stress orders | energy-norm orders |
|---|---|---|---|---|---|
| stress / quadratic | 1.954155, 1.985643, 1.995543 | 1.005310, 1.002097, 1.000678 | 0.988719, 0.996472, 0.998937 | 0.994224, 0.998273, 0.999498 | 0.991440, 0.997357, 0.999212 |
| strain / quadratic | 1.949089, 1.983482, 1.994629 | 1.004486, 1.001814, 1.000580 | 0.989446, 0.996717, 0.999015 | 0.996137, 0.998885, 0.999687 | 0.992733, 0.997773, 0.999340 |
| stress / linear | 1.954585, 1.985797, 1.995595 | 1.005252, 1.002074, 1.000671 | 0.988656, 0.996457, 0.998933 | 0.994307, 0.998296, 0.999504 | 0.991405, 0.997349, 0.999210 |
| strain / linear | 1.949738, 1.983731, 1.994720 | 1.004404, 1.001781, 1.000571 | 0.989341, 0.996692, 0.999008 | 0.996302, 0.998929, 0.999698 | 0.992665, 0.997756, 0.999336 |

| Plane / T | Reference U (J/m) | normalized U errors n8/16/32/64 |
|---|---:|---|
| stress / quadratic | 3291.810598290596 | 0.007927270097, 0.002010066652, 0.0005043863928, 0.0001262097426 |
| strain / quadratic | 5673.107521367519 | 0.006360377024, 0.001623915604, 0.0004081910488, 0.0001021809346 |
| stress / linear | 3762.290598290595 | 0.01169039278, 0.002961166698, 0.000742922836, 0.000185896445 |
| strain / linear | 5446.867521367519 | 0.01293195082, 0.003276914363, 0.0008221117274, 0.0002056986806 |

The energy column is |U_h-U|/U*, not division by continuum U. All refinements
decrease. Quadratic-T interpolation has L2 order2 and H1 order1 within roundoff;
linear-T errors are at roundoff and no slope is claimed. Both norms and reference
energy satisfy their independent quadrature cross-checks.

Actual tests include affine combined exact patches, cubic overlap/reaction
change=-added consistent left load, and nonzero support-work identity. A square
ring has outward normals into its inner void; uniform shear/thermal and inward
pressure-vector -p*n patches are exact. Pressure scalar is not a new API. Edge
endpoint/cell/tag order, node permutation, rotated translated Cartesian frames
and explicit similarity scales.1/10 transform u,body,stress/normal/load/U together.
Similarity changes physical size with consistent SI scaling; it is not automatic
unit inference. Material-component support tests reject pure-Neumann balanced
loads, an unanchored second component and three distinct but rank2 scalar supports.

## Runtime compatibility and negative controls

All original18 ThermoelasticResult field positions are preserved, followed by
load_body/load_traction with defaultNone. A real18-positional construction retains
old meanings and leaves new fields None. Normal solver outputs have(N,2) arrays,
external=body+traction and total=external+g. None/{} preserve original18 numerical
fields exactly. Output arrays remain mutable; snapshot is an independent immutable
bytes copy rather than a post-return certification of mutable results.

Snapshot exact geometry/order/T binding rejects scale/node/cell order, schema,
unit, changed-T/hash and mutable backing. Forced checksum-collision actors still
fail exact-array mismatch. Current tags are NOT hashed: changing a valid selected
edge map changes loads with the same snapshot hash; invalid replacement is rejected.
No load/tag/temperature provenance signature or automatic mapping is promised.

The complete selected edge set is validated before callbacks: malformed/bool/
float/empty/out-of-range/zero/interior/non-edge and duplicate selected edges are
rejected with a preceding valid callback never invoked. Callback exact(Q,2)
shape/realness/finiteness and accumulated overflow are tested. Pure deterministic
callbacks and no concurrent input mutation remain caller preconditions; callback
batch/order/purity is not authenticated.

**17 actual runtime wrong alternatives** are rejected at named intended audit
assertions: thermal sign/omittedg, q*n added/subtracted,3alpha, naive PE, PE-as-PS,
omittedzz, omitted PE residual energy, centroid-T², omitted support work,
line-weight error, endpoint lumping, dropped fixed-component line load, flipped
hole normal, g labelled external, body/traction fields swapped. Wrong parameters/
thermal-line aliases run the actual solver, or specific returned fields are
corrupted in memory. No source files are changed. Expected assertion labels
exclude an unrelated import/fixture failure as a successful negative control.

## Reproduction and exact artifact boundary

```bash
# Repository root; use existing dependencies and an isolated source environment.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
python -m pip install --no-index --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pytest -c pyproject.toml -q -s \
  packages/galerkin/tests/test_thermoelastic_traction_independent_validation.py
python -m pytest -c pyproject.toml -q -ra
```
```bash
# Build from the exact clean source inventory; these paths are illustrative.
python -m build --sdist --no-isolation --outdir dist-source packages/galerkin
python -m pip wheel --no-index --no-deps --no-build-isolation \
  dist-source/galerkin-0.1.0.tar.gz -w wheelhouse
# Use a separate installed environment for the following commands.
python -m pip install --no-index --no-deps --force-reinstall \
  wheelhouse/galerkin-0.1.0-py3-none-any.whl
# Copy the independent oracle and pytest file together outside the source tree.
# Remove source PYTHONPATH, and avoid source conftests forcing checkout imports.
python -m pytest -c pyproject.toml --confcutdir="$ACCEPTANCE_TEST_DIR" -q -s \
  "$ACCEPTANCE_TEST_DIR/test_thermoelastic_traction_independent_validation.py"
python -I packages/galerkin/tests/thermoelastic_traction_independent_consumer.py
```

The90-case installed pytest run uses real site-packages, a copied oracle/test
outside the source checkout and confcutdir. It is NOT run under-I: the first-I
attempt failed before test collection because pytest was unavailable when user-site
was disabled. No dependency was added. The separate standalone unittest/NumPy
consumer really runs under-I and asserts site-packages origin at each test.
It is supplementary smoke evidence, not a replacement for the90 fixed gates.

Python3.12.14/NumPy2.3.5/SciPy1.17.0, isolated existing-dependency venvs, Linux
shared Work cloud and six thread variables1. Source inventory and source/sdist/
wheel/installed **17 runtime Python modules** have exactly matching names and
bytes; no extra module is allowed. Thermoelasticity Git blob
**e91cfa089bc09dfc0c646841190f536ae5412333**, SHA256
**3ebe7f891113c09f27b03b9c9ab0be759e73e4fb50dfa5ac01a325f7091303a2**.
Clean sdist SHA256 **d8caef3170de33bcc4bc8dad628c93423ed580ed234ae887c2879602d506d9bc**;
clean wheel SHA256 **3f7b7ac69943514abd7fca2b65c4ec03ef749a89de799da37c7c04cbc29a57de**.
Actual __file__/per-module hashes are recorded. No new dependencies/GPL solver
implementation sources were adopted.

## Original failures, recovery and final results

A checkout copy initially retained11 files from an earlier workflow, including
one extra runtime module. Checking only matching tracked blobs missed these
untracked files. Initial90/isolated4/related208 observations used the correct
traction core but that unclean artifact; they are **provisional**, not final exact
candidate acceptance. The first whole attempt showed a dependency-guard failure
caused by the extra old module and was interrupted through its own managed session
(exit130); it has no completed whole-suite counts. An earlier direct-PID stop
attempt failed with ProcessLookupError; no successful signal is inferred from it.
This is a validation-environment error, not a producer defect.

The11 files and initial sdist/wheel/origins/logs are archived separately. They
were removed; generated build/egg-info caches were cleared in the owned checkout.
Exact Python inventory now equals candidate files plus the three owned test files,
with zero unapproved Python and17 runtime modules. Source/sdist/wheel/installed
filename-set and byte equality were rechecked. The clean artifact was rebuilt
and reinstalled; recovery reruns were necessary, not unexplained duplicate runs.

- Clean installed independent **90pass/0fail/0skip**, including all17 wrong-runtime
  controls and four fixed-mesh/plane manufactured cases.
- Clean installed **python-I consumer4tests OK**: both planes' combined patch,
  legacy18/snapshot lifetime and consistent linear edge loading.
- Clean source independent **90cases pass**, and related component/previous-independent/
  producer/reference regression **208cases pass**, counted directly in whole-run JUnit.
  Completed clean root whole: **1385pass / 7fail / 16skip / 9subtests pass / 1warning**
  (Starlette deprecation),335.66s shared-host metadata. All7 failures are existing
  thermal CLI-I subprocess cases failing before execution because Shapely is
  unavailable with user-site disabled. Exact preinstalled required Shapely2.2.0
  (BSD-3-Clause) distribution files were copied into only the owned source venv,
  with byte hashes recorded; no download/project dependency/version change.
  The failed7 targeted cases then pass (**7pass/132deselected**). The original
  whole result remains failed; no second clean whole run or invented new total.
  Skips are14Gmsh and2local refractiveindex.info database. Numerical acceptance,
  target environment recovery and owner/release whole-combination acceptance
  are separate scopes; no production numerical defect was found by these gates.

The original-I pytest import failure and unclean interrupted run remain preserved;
they are not relabelled successful. Initial pip used its default build cache;
subsequent commands disable caching and no shared cache was inspected/deleted.
Seven unrelated binary PNG assets are absent from the hydrated checkout; no
figure-asset distribution completeness is claimed. New report/consumer asset
shipping, all-package release metadata and final combined release belong to
separate release review. No develop integration/deployment is claimed. Shared-host
timing is metadata, not a performance baseline. Actions were not queried/run;
Windows is stopped/unverified, and Linux is not a substitute.
