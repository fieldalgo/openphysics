# Independent acceptance: steady heat conduction

Candidate implementation: `aaf948ae38aa82907ca16ef7cdeed75dfa7484ba`.
This independent suite adds a quartic manufactured solution and a mixed-boundary
quadratic solution, rather than using the implementation's sine answer key.
Production thermal/refsol code, original tests and tolerances remain unchanged.
The smooth-solution mesh ladder and gates were recorded before this candidate
was available. The new tests import only Mesh and the public thermal solver;
their answer key imports no production assembly, gradient, solver or refsol helper.

## Oracle and fixed gates

On [0,Lx]×[0,Ly], freeze Lx=0.03 m, Ly=0.02 m, k=12.5 W/(m K),
T0=293.15 K and A=7 K. With xi=x/Lx, eta=y/Ly,

```text
T = T0 + A*(xi^3-xi + 2*eta^3+eta + xi^2*eta^2)
Tx = A/Lx*(3*xi^2-1 + 2*xi*eta^2)
Ty = A/Ly*(6*eta^2+1 + 2*xi^2*eta)
Q = -k*A*((6*xi+2*eta^2)/Lx^2 + (12*eta+2*xi^2)/Ly^2)
q = -k*(Tx,Ty)
```

Prescribe the exact nonzero, nonuniform trace on all four sides. The independent
oracle derives Q by differentiation, not by applying a discrete operator to T.
Its source integral is -k A [11 Ly/(3 Lx)+20 Lx/(3 Ly)].
Finite negative Q is a supported heat sink. Unequal lengths detect exchanged
coordinate/metric factors; the mixed term tests genuine two-coordinate variation.

For left TL=280 K and right TR=315 K with top/bottom insulated, use

```text
T = TL + (TR-TL)*x/Lx + Q0*x*(Lx-x)/(2*k)
qx = -k*(TR-TL)/Lx - Q0*Lx/2 + Q0*x; qy = 0
```

Q0=1e5 W/m³ gives a second, mixed-boundary convergence test. Q0=0 gives an
exactly representable affine P1 patch. The left is colder: its inward reaction
is negative, while the right inward reaction is positive. Individual side heats
are tested, since their globally zero affine total alone proves little.

The unchanged primary mesh ladder has n=8,16,32,64 uniform rectangle cells,
each split on the same diagonal. Both manufactured solutions must have strictly
decreasing interior-integrated errors and satisfy, on **each final two intervals**,
temperature L2 order >=1.8 and volume vector-flux L2 order >=0.9. Smooth convex-
domain P1 approximation predicts asymptotic orders two and one respectively;
these margins are fixture-specific finite gates, not universal rates for rough
solutions. Positive norms prevent signed-error cancellation.

## Independent integration and conservation

The oracle computes barycentric gradients from coordinate cofactors and checks
the coordinate identity. It independently assembles constant-k element stiffness
and Q Ni loads with an 8×8 Duffy rule. Its Duffy parameterization differs from
the production source integration. The test evaluates P1 T and the returned
element flux at interior quadrature points; errors from orders six and eight
must agree within relative 1e-10. For the quartic, squared temperature/gradient
errors have degrees eight/six and source times Ni degree three, so these rules
are exact in exact arithmetic. Nodal error or centroid-only integration is not
substituted for these norms.

The original independent matrix K and load f are compared to the result,
including free residuals, fixed reactions and

```text
R = K*T-f; outward boundary heat = -sum(R_fixed)
sum(load)+sum(reaction) = 0
theta^T K theta = theta^T f + theta_fixed^T reaction_fixed
```

theta=T-T0 avoids absolute-Kelvin cancellation when checking the mathematical
constant-nullspace equivalence. Differences caused by restoring the reported
absolute temperature are checked against the same physical fluctuation scale.
The normalized residual/reaction/balance/weak identity budget is 1e-10.
Boundary temperatures and affine T/flux use normalized 1e-10 checks.
No normalization by the large T0 conceals fluctuation errors.

Loads/reactions are W/m of out-of-plane depth; q is W/m². Multiplying by a
physical depth in metres gives watts. The quadratic weak functional is W K/m,
not stored thermal energy in joules. Raw piecewise-constant P1 flux is not an
H(div) conservative reconstruction: nonlinear-case boundary flux must not be
required to equal reactions at roundoff. Strict discrete conservation uses
reactions, while physical flux accuracy uses the volume norm and affine patch.

## Additional observations

- Independent length factors 1e-3/1/1e3 and conductivity/source factors test
  T'=T0+(d/c)(T-T0), q'=(d/s)q, load'=d load and reaction'=d reaction.
- Fixed Q with constant trace tests inverse-conductivity temperature rise and
  unchanged heat flux. A +11 K offset tests gradient/reaction invariance.
- Rotation/translation, node/cell permutations and reflected diagonals test
  scalar/vector covariance and the documented constructor orientation repair.
- All-node Dirichlet data exercises the valid empty-free-system case with Q.
  Separate components have independent constants; an unanchored component is
  rejected even if another component has prescribed data.
- Twenty-two explicit invalid cases cover material, source callback shape,
  nonfinite/complex/boolean input, boundary IDs/interior constraints and mutated
  mesh connectivity, orientation, duplicates, unused/degenerate/nonfinite nodes.
- Real negative controls solve with the wrong Q sign or different k: although
  they solve their own equations, the independent original K/f checks reject
  them. Returned flux reversal and interior-temperature damage are also detected.

Metamorphic discrepancies use the fixed normalized 1e-9 budget. No new API,
nonzero-Neumann/Robin condition, variable k or thermoelastic coupling is tested.

## Executed evidence and reproduction

The independent source and installed-wheel suites contain 45 tests each.
The original thermal/refsol pair was separately rerun: 84 passed, zero failures
or skips. Those are directly observed counts, not a repeated implementation-owner
claim. Detailed exact-candidate results and scope are in the companion manifest.

An initial independent execution had 42 passes and one failure because the
affine test expected hot-left reaction signs for the cold-left 280/315 K fixture.
Only that erroneous expectation was corrected from [1,-1] to [-1,1], as required
by q=-k grad T. No production code or tolerance changed. The initial full
redirected log was accidentally overwritten after a relative-path move failed;
the observed failure/trace and an explicit retained summary record this limitation.
It is not reported as a production defect or silently replaced by a passing run.

From the repository root, using existing dependencies:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest -c pyproject.toml -q -s \
  packages/galerkin/tests/test_thermal_independent_validation.py
```

For installed consumption, build an sdist in a separate staging copy, build its
wheel, and install it without dependencies into a private venv using existing
NumPy/SciPy. Copy only the two independent test/oracle files to an external test
directory. Run pytest there with `--confcutdir=.` and verify that imports resolve
to that venv's site-packages, not the source checkout or its root conftest.
All sixteen Python modules in the tested wheel were byte-compared with candidate
source. This validates the core installed consumer, not every distribution or
platform. New documentation asset inclusion remains a packaging responsibility;
this independent work does not change the shared MANIFEST or release configuration.

Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, pytest 9.1.1; BLAS/OpenMP/MKL threads
one on a shared Linux host. Timings are not performance baselines. Logs, source
hashes, build artifacts and initial-failure summary are retained separately.
Whole-environment status, skipped native prerequisites and installed-core results
are reported separately in the manifest. No arbitrary geometry, transient,
nonconstant/anisotropic conductivity, prescribed-flux or coupled physics claim is
made by these tests.

## Whole-environment run retained separately

The full source run completed with **699 passed, 9 failed, 9 skipped**, nine
subtests passed and one FastAPI/Starlette deprecation warning. It collected the
preceding 43-case independent revision; the final two added metamorphic cases
were separately covered by the final 45-case source and installed runs.
Seven failures are Gmsh-dependent legacy optional-helper paths that proceed when
find_gmsh returns None. Seven additional Gmsh tests and two local optical-database
tests skipped. No native prerequisite was installed and those helpers were not
modified in this independent branch. Two other failures were real cavity CLI
subprocesses unable to import simcase: root conftest inserts source paths only
in the parent process, while this private venv installed no simcase package.
The original nine failures are retained; an explicit candidate-only PYTHONPATH
rerun of the two subprocess cases is reported separately in the manifest.
This run does not certify the whole environment as passing and does not replace
the integration owner's exact remote CI.

The two cavity CLI cases passed when rerun with the explicit candidate package
paths inherited by subprocesses (2 passed, zero failures/skips). This is an
environment-only correction with no product edit. It does not erase the first
full-run failures, rerun the entire suite, or resolve the seven Gmsh failures.
