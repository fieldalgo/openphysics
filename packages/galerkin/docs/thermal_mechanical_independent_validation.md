# Independent steady heat → mechanical workflow acceptance

[한국어](locales/ko/pages/thermal_mechanical_independent_validation.md)

This report covers the public Python workflow on explicit production candidate
**b4131d0dab425c2ba54380492e33109f78a92a0b**, a normal successor of initial
**48920cc066708784864c95eb5bae597b0e2a2abd**. Independent test code is fixed at
**ecc924b80603426cd751cf3fc0fa62b25cedd976**. Preparation math and gates were frozen
before inspecting this implementation. Producer checks are regression evidence,
not the independent oracle. No production/refsol/original test/settings changes.

The workflow runs Dirichlet/insulated steady heat, exact same-mesh nodal-P1
snapshot transfer, then prescribed-temperature mechanics. Robin, outward flux,
mechanical traction, remeshing, iterations, feedback, transient heat, CLI/Studio
and persistence are outside this acceptance. This is one-way endpoint mechanics,
not a thermodynamically coupled simulation or a heating-path energy balance.

## Independent law and weak functionals

The oracle imports only NumPy. Geometry uses Cartesian Vandermonde inverses,
independent Duffy quadrature and an independently constructed square topology.
No production D/thermal-load/assembly/geometry helper or refsol supplies truth.
The producer's separately added oracle is not imported. Public component solves
are called only to measure the two discrete mechanical contributions.

Let a=alpha(T-Tref), mu=E/[2(1+nu)] and lambda=E nu/[(1+nu)(1-2nu)]. Starting
from the full original three-dimensional tensor law,

```text
elastic strain = epsilon - a I
sigma = 2 mu (epsilon-a I) + lambda tr(epsilon-a I) I
psi = mu (epsilon-a I):(epsilon-a I) + .5 lambda tr(epsilon-a I)^2
PS: sigma_zz=0 -> epsilon_zz=((2mu+3lambda)a-lambda(exx+eyy))/(2mu+lambda)
PE: epsilon_zz=0
```

Engineering gamma_xy is twice tensor epsilon_xy. The parent law is evaluated
pointwise, including z; its unit-strain probes define the in-plane tangent for
norms and compliance. The PE physical thermal eigenstrain remains aI, even
though the reduced in-plane free-expansion factor is (1+nu)a.

For in-plane e=(exx,eyy,gamma_xy) and m=(1,1,0), q=E a/(1-nu) for PS and
q=E a/(1-2nu) for PE. Independent virtual-work integrals evaluate stiffness
actions, positive g=integral B^T q m, body f=integral N^T b, heat K_T(T-Tref)
and f_Q=integral N Q. These are assembled from the test's geometry/integrals,
without returned residuals or producer heat-balance summaries as truth.
Uniform q has zero volume divergence but a nonzero boundary functional; a
body-only shortcut loses uniform free expansion. H=0 in this Dirichlet/insulated
workflow; no Robin matrix is assumed.

```text
mechanical residual = K u-f-g
reaction = residual on prescribed components, zero on free components
U = integral psi = .5 u^T K u-u^T g+CT
2U = u^T f+u_D^T r_D-u^T g+2CT
CT_PS = integral E a^2/(1-nu)
CT_PE = integral 1.5 E a^2/(1-2nu)
heat: residual=K_T T-f_Q, sum(f_Q+reaction)=0
outward integrated heat = -sum(heat reaction)
```

Both support work and the PE z/residual contribution are essential. P1 T varies
inside elements, so physical U integrates T squared, rather than squaring the
centroid T. Total strain is element constant; returned stress/thermal strain/
elastic strain/epsilon_zz/sigma_zz are centroid samples and are checked there.
Full stress errors use the parent-law reconstruction with the actual P1 T at
interior quadrature points. Heat load/reaction/residual has W/m, flux W/m²;
mechanical forces have N/m and physical U has J/m. Heat quadratic work has
W K/m and must not be labelled elastic energy or stored heat.

## Cases, error separation and immutable gates

The 1m square uses k=10 W/(m K), E=70e9 Pa, nu=.3, alpha=12e-6/K and
Tref=293.15 K. Both planes use n=8/16/32/64 with **all three adjacent intervals**.

- Uniform theta=20 K: minimal three scalar supports, and separately all-exterior
  zero displacement. Free PS u=a(x,y), sigma=U=0. Free PE u=(1+nu)a(x,y),
  in-plane stress0, sigma_zz=-Ea=-16.8MPa, U/area=.5Ea²=2016 J/m³.
  Fully constrained PS normal stress=-24MPa/U density5760; PE all normal
  stress=-42MPa/U density15120. Side/corner reactions use sigma*n with exact
  half-edge corner contributions. Cooling, signed alpha and alpha0 are separate.
- Linear T=Tref+10+20x, Q=0, left/right heat supports and top/bottom insulation.
  v=(alpha10x+.5alpha20(x²-y²),alpha10y+alpha20xy); PS u=v, PE u=(1+nu)v.
  Heat is P1-exact, displacement quadratic; do not mistake its mechanical error
  for transfer error. Only mass-weighted additive rigid translation/infinitesimal
  rotation may be fitted, with support values checked before fitting. No affine,
  shear/scale/strain fit or finite Procrustes rotation is permitted.
- Sine T=Tref+20S, u=(1e-4,.6e-4)S m, S=sin(pi x)sin(pi y), whole-boundary
  heat Tref and prescribed analytic u. Q=2 k20 pi² S. The body is derived by
  differentiating the parent total stress: -mu Laplacian(u)-
  (lambda_eff+mu)grad(div u)+beta grad T, with parent-law beta/elastic probes.
  Original-3D divergence was also checked by independent centered differences
  during the separately frozen preparation; that is not substituted for FEM.

The ledger distinguishes analytic T/u, interpolant I_hT, actual heat T_h,
exact snapshot S_h=T_h, prescribed u_h[I_hT] and chain u_h[T_h]. Temperature
interpolation and nodal heat correction add as fields to total heat error.
Mechanical prescribed error plus heat-induced delta_u equals chain error as
vectors; norms are not additive. Exact transfer is array equality, not a fitted
rate. The same production mechanical component is solved twice to isolate a
contribution, not to establish the analytic truth.

For identical body/supports, delta_u has homogeneous prescribed values. With
independently evaluated thermal-stress delta(qm),

```text
||delta_u||_K <= ||D^(-1/2) delta(qm)||_L2
```

uses constant1 and sqrt(J/m) units. The fixed normalized 1e-10 roundoff allowance
is explicit; near-zero linear heat differences do not support a fitted slope.
Uniform preparation saturated this bound; actual sine discrete pairs satisfy it.

The unchanged gates are:

- L2 T/u order>=1.8; H1 seminorm/flux/strain/full3D stress/tangent energy-norm
  order>=.9 on **every** interval, for prescribed and chain mechanics as applicable.
- Exact uniform/linear heat and normalized uniform fields/reactions/U <=1e-10;
  heat residual/component balance<=1e-10; mechanical residual/physical force/
  moment<=1e-9; parent3D stress/U/support-work identities<=1e-10.
- Norm quadrature8×8 vs10×10 difference <1% of measured nonzero error,
  continuum physical U12×12 vs16×16 difference<=1e-8 fixed energy scale.
- Sine physical-U relative error decreases and final<=.02. No invented
  second-order raw-energy gate. Explicit external m/mm/um conversion<=1e-9.

Normalization uses L=1m, theta*=20 K (linear30 K), strain*=max(|alpha|theta*,
1e-4/L,.6e-4/L), sigma*=E strain*, force*=sigma*L, moment*=force*L,
U*=E strain*² area. Heat scale=max(k30,integral |Q|); never divide by an exact
zero energy/stress, absolute Tref or a cancelling net force. Support-gradient
variants use their actual comparable mechanical scale.

## Actual numerical evidence

Entries below list 8→16, 16→32, 32→64, not a selected final pair.
| Case / plane | u L2 orders | u H1 orders | strain orders | full 3D stress orders | tangent energy-norm orders |
|---|---|---|---|---|---|
| linear / stress | 1.880927, 1.957799, 1.986410 | 1.017262, 1.011588, 1.005117 | 0.962522, 0.987473, 0.996022 | 0.980940, 0.993448, 0.997904 | 0.976221, 0.991961, 0.997442 |
| linear / strain | 1.875303, 1.957907, 1.987224 | 1.017359, 1.011805, 1.005215 | 0.963903, 0.987991, 0.996198 | 0.983130, 0.993985, 0.998045 | 0.978170, 0.992552, 0.997622 |
| sine / stress | 1.974154, 1.992991, 1.998197 | 0.994778, 0.998802, 0.999708 | 0.996900, 0.999346, 0.999844 | 1.018590, 1.004798, 1.001208 | 0.997224, 0.999433, 0.999867 |
| sine / strain | 1.965368, 1.990436, 1.997520 | 0.999449, 1.000082, 1.000037 | 1.001758, 1.000724, 1.000200 | 1.060010, 1.016053, 1.004083 | 1.002938, 1.001041, 1.000281 |

Prescribed-mechanics rates also pass every interval. Minimum prescribed u L2
orders are linear1.880927/1.875303 and sine1.977839/1.972497 (PS/PE).
Sine heat L2 orders are1.974492,1.993493,1.998363; heat H1/flux orders are
.989101,.997254,.999312. Linear heat/flux is exact within the fixed normalized
1e-10 gate, with no rate claimed. Snapshot transfer is exactly zero on all meshes.

| Sine / plane, n64 | heat L2 K | interpolation L2 K | nodal-correction L2 K | prescribed u L2 m | heat-induced u L2 m | total u L2 m |
|---|---:|---:|---:|---:|---:|---:|
| stress | 0.006759846697 | 0.0049176047 | 0.002040899385 | 3.173073191e-08 | 2.655169708e-09 | 3.234097101e-08 |
| strain | 0.006759846697 | 0.0049176047 | 0.002040899385 | 3.170303274e-08 | 3.852302631e-09 | 3.299352745e-08 |

At n64 the sine perturbation energy norms/bounds are PS .005092452628/.01095261542
and PE .008094146270/.01651994279 sqrt(J/m). Relative physical-U errors over
all meshes are PS [.04493895740,.01139003516,.002857136716,.0007148822010] and
PE [.05036883381,.01279098160,.003210043739,.0008032724247].

Actual runtime wrong-physics controls reject **9 alternatives**: thermal RHS
sign, 3alpha, naive PE in-plane-alpha shortcut, absolute T instead of T-Tref,
omitted sigma_zz, omitted PE residual energy, centroid-T-squared energy,
omitted support work and body-only thermal load. Public stage aliases are
patched in memory to run wrong numerical parameters or corrupt outputs; the
independent audit must fail. Production files are unchanged. These are separate
from preparation's22 algebraic wrong alternatives and invalid-input rejection.

## Runtime contracts and scope of provenance

Actual checks cover raw float/bool/clockwise/nonfinite/out-of-range geometry or
metadata, exact SI declarations, bad scalar/body/source shape/nonfinite values,
per-component thermal and rigid mechanical anchoring, stage-labelled chained
input/heat/transfer/mechanics/manifest failures, and no mechanics after invalid
transfer. Negative K is rejected even at -finfo(float).tiny; actual heat-produced
negative K and injected malformed transfer are tested. Linux extended-range
cast overflow reports the offending node. Finite20K and0K remain valid; no
Celsius inference, clipping, offset or reference-temperature repair is claimed.

All stages see the same isolated owned mesh. Caller callback mutation cannot
rewrite captured geometry/supports/region metadata. Observed owned geometry or
region mutation fails at the stage boundary. Region validation/lifetime and
cast-overflow checks are the b413 code delta; core thermal/thermoelastic blobs
are unchanged from489. Snapshot keeps canonical immutable bytes, independent
of later heat/caller/reference-mesh mutations. Reordered/scaled/stale geometry,
changed schema/units/hash fail component reuse. Mutable results after return
are expressly not recertified.

Manifest canonical JSON and fresh decoded accessors record actual SI/materials/
supports, constant-vs-unfingerprinted callback labels, exact-copy policy, hashes,
completed stages, origin and quantity units. Hashes are identifiers, not
signatures. A workflow-owned heat call does not authenticate callback behavior,
physical units or pre-freeze intent. A finite20K or falsely metre-labelled mesh
cannot reveal its intended provenance. No automatic cross-mesh repair, thread
safety, input-source authentication or post-return integrity certification.

## Reproduction, failures and verification boundary

```bash
# Run from the repository root, using an environment with existing dependencies.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1
python -m pip install --no-index --no-deps --no-build-isolation \
  -e packages/galerkin -e packages/galerkin-refsol -e packages/meshine \
  -e packages/gmshio -e packages/physmat -e packages/simcase
python -m pytest -c pyproject.toml -q -s \
  packages/galerkin/tests/test_thermal_mechanical_independent_validation.py
python -m pytest -c pyproject.toml -q -ra
```
```bash
python -m pip wheel --no-index --no-deps --no-build-isolation \
  packages/galerkin -w wheelhouse
# Install the wheel into a separate environment; do not use an editable install.
python -m pip install --no-index --no-deps wheelhouse/galerkin-0.1.0-py3-none-any.whl
# Copy the independent oracle and test together into an external test directory.
# ACCEPTANCE_TEST_DIR denotes that directory, outside the source checkout.
python -m pytest -c pyproject.toml --confcutdir="$ACCEPTANCE_TEST_DIR" -q -s \
  "$ACCEPTANCE_TEST_DIR/test_thermal_mechanical_independent_validation.py"
```

For installed acceptance, remove source PYTHONPATH and do not collect source
conftests: root conftest intentionally forces checkout imports. Copy only this
independent oracle/test outside the checkout and use confcutdir as above. Record
actual module __file__ and hashes; successful import alone is insufficient.

Linux Python3.12.14 / NumPy2.3.5 / SciPy1.17.0, isolated existing-dependency
venvs, all six thread variables1. Source origin is this checkout; installed origin
is the separate venv's site-packages. Both workflow files have Git blob
**28ecea0150234cff77bcd3d7a0a2c39252a8caa1** and SHA256
**77e196d31ffa99b396a54169794ece6a947d5bbc3db12a4bbaea8de85469d648**.
The b413 wheel SHA256 is
**44d63f83196503dc3d1e5a5ec41b2bd7c539a672ba907de14a9c074c2ce15391**.
No new dependencies or GPL solver implementation sources were used.

- Initial489 independent source81pass/0skip; this is historical, before b413.
- First b413 independent source89pass/1fail/0skip: the region-name negative
  fixture assigned the same already-mutated name, so no actual change occurred.
  Changing the fixture to a different name fixed it; targeted3pass/87deselected.
  No producer or gate change. Original failed log is preserved.
- Final installed independent90pass/0fail/0skip, including all meshes and9runtime
  wrong alternatives. Related source component/previous-independent/API
  regression226pass/0fail/0skip; producer results are not independent counts.
- Final first root run: **1001pass / 3fail / 16skip / 9subtests pass**,
  1 Starlette deprecation warning. The independent90 cases all pass in its JUnit.
  One failure is the unchanged dependency guard rejecting standard-library
  collections/contextlib/copy/json. Two cavity CLI failures were this source
  venv missing local simcase; installing the six existing local packages
  no-index/no-deps fixed the two targeted CLI checks (2pass). The original
  full-run result remains failed, not re-labelled as a clean whole run.
  The owner assigned the guard correction separately; exact follow-up acceptance
  is pending. Broad numerical reruns are unnecessary if production bytes stay
  unchanged. Final combined full regression belongs to release review.

Other original invocation failures are preserved: first explicit-file pytest
selected package configuration and failed collection with ModuleNotFoundError
(galerkin); explicit root -c pyproject.toml fixes collection. One heredoc used
an incorrect relative path and wrote nothing; its following16pass were only the
old uniform tests, not the new contracts. An origin script initially had a wrong
sibling path (two cannot-open errors), then ran correctly. The first489 wheel binary was overwritten by the later build; its
build log/hash survives, not the original binary. It built successfully but pip's subsequent network check was blocked; final b413
wheel build/install used no-index and disabled pip version checks. These are
invocation/fixture failures, not numerical gate relaxations.

Source text/configuration was verified against exact candidate blobs. Seven
unrelated binary PNG assets were absent in the hydrated source; no figure-asset
packaging completeness is claimed. The galerkin numerical wheel contains the
verified modules; shared release manifests/doc-asset shipping need separate
release review. Timing on a shared host is metadata, not a performance baseline.
Actions were not queried or run. Windows runner acceptance is stopped/unverified;
Linux cannot substitute for it. No develop integration or deployment is claimed.
