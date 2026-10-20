# Independent acceptance of 2D elasticity

This validation adds independent polynomial fields and tests without changing
`galerkin.elasticity`, `refsol.elasticity`, or their existing tests. The inspected
implementation is commit `52ede82a5e1390c3a14b41be0b7fa70d4f035c08`.
It covers homogeneous isotropic small-strain P1 triangles, unit out-of-plane
thickness, both explicit plane models, component Dirichlet conditions and the
existing natural zero-traction boundary. It does not validate nonzero applied
surface tractions, heterogeneous materials, nonlinear elasticity or locking-free
behavior near incompressibility.

## Direct material and force formulas

Use metres, pascals and force density N/m^3. Let E=17e6, nu=.23 and a=.002.
The oracle uses engineering strain (exx, eyy, gamma), gamma=ux,y+uy,x.
It imports no engine/refsol constitutive, stress, gradient or load helper.

Write sigma_xx=A exx+B eyy, sigma_yy=B exx+A eyy, sigma_xy=G gamma.
The directly evaluated constants are:

| Model | A | B | G |
|---|---|---|---|
| Plane stress | E/(1-nu^2) | E nu/(1-nu^2) | E/[2(1+nu)] |
| Plane strain | E(1-nu)/[(1+nu)(1-2nu)] | E nu/[(1+nu)(1-2nu)] | E/[2(1+nu)] |

These follow from the 3D isotropic stress law with sigma_zz=0 or epsilon_zz=0,
respectively. Out-of-plane strains/stresses are not returned by the solver and
are not confused with the in-plane engineering shear convention.

## Cubic vector manufactured solution

On the unit square choose a nonzero boundary field, different from the existing
sine benchmark:

    ux = a (x^2 y + x y^2 + x^3/3)
    uy = a (x y^2 - 2 x^2 y + y^3/4)

Differentiation gives:

    exx   = a (2xy + y^2 + x^2)
    eyy   = a (2xy - 2x^2 + 3y^2/4)
    gamma = a (x-y)^2

Applying force=-div(sigma) directly yields:

    fx = -a [A(2y+2x) + B(2y-4x) + G(-2x+2y)]
    fy = -a [G(2x-2y) + B(2x+2y) + A(2x+3y/2)]

Both displacement components are prescribed on every boundary node. Boundary
tractions generally do not vanish. The load is evaluated at interior quadrature
points, not fitted to the solver's residual. Central differences independently
check the displacement derivatives and the divergence of the analytic stress.
Sign-reversed force, halved engineering shear and the opposite plane model are
explicit negative controls that must fail these comparisons. They are oracle
consistency controls, not a claim that every possible implementation defect is
covered by mutation testing.

## Quadratic mixed-component, zero-traction solution

Let k=B/A and M=A-B^2/A. The separate closed form is:

    ux = a (x^2 + k y^2),    uy = -2 a k x y
    exx = 2ax,              eyy = -2akx,    gamma = 0
    sigma_xx = 2aMx,        sigma_yy = sigma_xy = 0
    body force = (-2aM, 0)

For plane stress, k=nu and M=E. For plane strain, k=nu/(1-nu) and
M=E/(1-nu^2). Prescribe ux on left/right and uy=0 on the bottom.
Unprescribed top traction is exactly zero. On left/right the free y component
has zero traction; on the bottom the free x component has zero traction.
This is a genuinely non-affine mixed-boundary problem, not an assumption of
nodal exactness. Separate differentiation checks the analytic field and stress.

The exact continuum energy per unit thickness is:

    U = (1/2) integral sigma:epsilon dA = 2 a^2 M / 3.

For constant fx=-2aM, total body force is (-2aM,0) and its moment about the
origin is +aM. The boundary reactions balance these resultants. A transposed
vertical affine extension on a 1.3 by .7 rectangle additionally checks exact
component constraints and the resultant top reaction 1.3*a*M.

## Interior integration and checks fixed before the first run

The mesh sequence is n=6,12,24 on the unit square for both solutions and both
plane models. A separately written Duffy tensor Gauss rule at orders 5 and 7
integrates within triangles. The errors are:

- displacement L2: square root of integral |u_h-u|^2;
- tensor strain L2: square root of integral (dexx^2+deyy^2+dgamma^2/2);
- energy norm: square root of integral delta_epsilon:delta_sigma, with the
  directly evaluated oracle stress law.

All errors must decrease; the last displacement order must be at least 1.8 and
the strain/energy orders at least .9. Quadrature orders 5/7 must agree within
relative 1e-9. These polynomials have sufficient degree for exact integration at
both orders. The expected P1 orders are two and one; this is a regular, smooth,
fixed-material acceptance fixture, not a claim for singular or arbitrary meshes.
The numerical thresholds were fixed before computing the results below.

Each FE element's strain is independently recovered by solving for the affine
Cartesian displacement coefficients in [1,x,y], then differentiating that fit.
This avoids reusing the production B matrix and tests engineering shear explicitly.

For every convergence mesh the tests compare total assembled load and its moment
against the direct force integral (relative 1e-10), load+reaction force/moment
balance (1e-9), zero free-DOF reactions, independently calculated strain/stress,
and the following discrete work identity (1e-9):

    2 U_h = sum_i body_load_i dot u_i + sum_fixed reaction_i * prescribed_i.

The support work is essential with nonzero prescribed displacement. An independent
affine virtual displacement also checks integral sigma:epsilon(v) against
sum_i (load_i+reaction_i) dot v_i. Balance identities alone would not establish
physical accuracy; polynomial convergence and direct stress checks are separate.

Rigid translation/infinitesimal rotation is superposed on a strained solution;
displacement must shift by that motion while strain, stress and reaction remain.
A pure rigid motion with exactly three independent component constraints must
also be recovered; removing the third support must reject the rigid nullspace.
A combined proper rotation (.37 radians), scale two, translation (2.3,-1.7),
node/cell permutation and reversed connectivity checks the transformations:

    x' = s Q x + c, u' = s Q u, f' = Q f / s,
    sigma' = Q sigma Q^T, load' = s Q load, reaction' = s Q reaction.

Comparison tolerances are relative 1e-9 with displacement/strain absolute 1e-12,
stress absolute 1e-6 Pa and force absolute 1e-9 N/m. This checks mesh-coordinate
covariance, not an arbitrary component-wise rotation of mixed boundary supports.

## Observed source results

First registered execution: ten independent cases passed without changing the
criteria. Adding the separate mixed-oracle/minimal-rigid checks gives twelve
independent cases. The original elasticity tests and package-independence tests
are unchanged: combined related run, 84 passed, zero failed/skipped.

| Solution | Plane | Last L2 order | Last strain order | Last energy order |
|---|---|---:|---:|---:|
| Cubic | stress | 1.9996468 | .9995067 | .9994900 |
| Cubic | strain | 1.9996468 | .9995067 | .9994846 |
| Mixed quadratic | stress | 1.9886895 | .9988464 | .9978539 |
| Mixed quadratic | strain | 1.9856805 | .9983809 | .9966891 |

The mixed numerical energies approach the closed form from below:
stress 45.01863,45.25394,45.31342 versus 45.33333;
strain 47.53282,47.78104,47.84421 versus approximately 47.86541 J/m.
These are measured results, not newly fitted acceptance bounds.

From the repository root, with the existing packages installed:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -c pyproject.toml -q -s -ra \
  tests/galerkin/test_elasticity2d_independent_validation.py \
  tests/galerkin/test_elasticity2d.py \
  tests/refsol/test_elasticity_reference.py \
  tests/galerkin/test_independence.py
```

No new dependency or external solver implementation is used. The direct
polynomial/continuum identities are derived here; the existing NumPy/SciPy
runtime performs the arithmetic and solves. Source and installed-wheel results,
full-suite environmental failures and unexecuted distribution gates must be
reported separately; passing these cases alone does not certify all packaging,
platforms, or physics models.

## Installed artifact and negative controls

A galerkin wheel built from its sdist with the existing build tools contains
`elasticity.py` byte-identical to the inspected source. Running the twelve new
independent tests outside the source tree with `python -I` imports galerkin
from that wheel and gives **12 passed, zero failed/skipped**. The environment
reuses already installed NumPy/SciPy/pytest tools; it is not a clean dependency
resolver or a cross-platform compatibility certification.

Three additional isolated processes deliberately corrupt the installed module
in memory, leaving source/wheel bytes unchanged. They run the unchanged
`polynomial-stress` convergence case with the same tolerances:

| Injected implementation error | Observed rejection |
|---|---|
| Shear constitutive coefficient multiplied by .5 | Independent stress comparison fails; shear relative mismatch .5 |
| Plane stress/strain selection exchanged | Independent stress comparison fails in normal components |
| Supplied body force multiplied by -1 | Total load differs from direct force integral by relative 2 |

Each process exits with one expected failed assertion. These failures are negative
controls, not defects observed in the unmodified candidate. The injection wrapper
may call the original routine to create the defective variant; no expected-value
oracle calls that routine.

The complete source run reports **564 passed, 7 failed, 9 skipped**, plus nine
passed subtests and one existing FastAPI/Starlette deprecation warning. All seven
failures require the missing Gmsh executable (unstructured cavities, mesh interop
and mesh-file generation). Skips are seven Gmsh integration cases and two absent
local refractiveindex.info database cases. This is not an all-green full-suite
claim. The original candidate's remote CI result is a separate verification.
No Gmsh skip helper, existing physics tolerance, packaging configuration or
production/refsol implementation was changed to remove these environmental
failures. Strict multi-package distribution/metadata validation was not rerun
here; the wheel check above addresses this independent acceptance scope.
