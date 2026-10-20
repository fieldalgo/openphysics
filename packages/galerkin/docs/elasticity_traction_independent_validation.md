# Independent acceptance of boundary traction

The inspected implementation is `8bb3df93c657c4d8e3a3eb496b805da6bf10b936`.
This validation changes no production implementation, reference solution,
existing acceptance test, tolerance, dependency or CI setting. Its oracle uses
explicit continuum formulas, independent Cartesian polynomial fits, and
separately written surface/interior integrals. It does not call the engine's
constitutive, strain, load, normal or traction assembly helpers to generate
expected answers, and does not use the original traction reference fields.

## An independent mixed-boundary solution

Let L0=1 m, X=x/L0, Y=y/L0, a=.002 m, E=17e6 Pa and nu=.23. Set:

    ux/a = X^2 Y + X Y^2 + X^3/3 + .4 + .2 X - .3 Y
    uy/a = X Y^2 - 2 X^2 Y + Y^3/4 - .25 + .35 X + .1 Y

The engineering strains, multiplied below by L0/a, are:

    exx:   2XY + Y^2 + X^2 + .2
    eyy:   2XY - 2X^2 + .75Y^2 + .1
    gamma: (X-Y)^2 + .05

Use sigma_xx=C exx+D eyy, sigma_yy=D exx+C eyy and sigma_xy=G gamma:

| Plane | C | D | G |
|---|---|---|---|
| Stress | E/(1-nu^2) | E nu/(1-nu^2) | E/[2(1+nu)] |
| Strain | E(1-nu)/[(1+nu)(1-2nu)] | E nu/[(1+nu)(1-2nu)] | E/[2(1+nu)] |

Directly differentiating this stress, rather than using an assembled residual,
gives the force density in N/m^3:

    fx = -a/L0^2 [C(2X+2Y) + D(2Y-4X) + G(-2X+2Y)]
    fy = -a/L0^2 [G(2X-2Y) + D(2X+2Y) + C(2X+1.5Y)]

The affine terms change the nonzero trace and constant stress without changing
the force density. Central differences separately check both the displacement
and stress derivatives of this oracle away from boundaries.

Prescribe only ux on the left and uy on the bottom. These traces are nonzero.
On all four sides supply the derived Cartesian traction:

    t = (sigma_xx nx + sigma_xy ny, sigma_xy nx + sigma_yy ny).

For free components this is the natural boundary datum. On prescribed components
it is an applied external load retained by the API, with the support reaction
computed from the original Ku-load. This intentionally exercises overlap instead
of silently dropping applied forces at fixed nodes/corners. The two scalar roller
traces suppress the rigid modes. Their constraints must not be naively rotated
as if one global Cartesian component were an arbitrary rotated direction.

This field and boundary selection differ from the original traction benchmark's
polynomial field and two-component homogeneous clamp on the left.

## Independent integrals and fixed criteria

The square mesh sequence is n=6,12,24 in both plane models, fixed before any solve.
Separate Duffy tensor Gauss rules of orders 5 and 7 integrate inside triangles.
The expected P1 displacement L2 and tensor-strain/energy orders are two and one.
All errors must decrease; last-pair L2 order must be at least 1.8 and the last
strain/energy orders at least .9. Orders 5/7 must agree within relative 1e-9.
These are smooth, fixed-material fixture criteria, not universal singular-domain
or near-incompressible performance bounds.

FE strain is recovered by fitting the Cartesian affine displacement in each cell
with basis [1,x,y]. The tensor Frobenius density is
`dexx^2+deyy^2+dgamma^2/2`. The energy error uses the directly calculated stress
of the strain error, without the production material helper.

The complete expected nodal load is independently integrated: body terms with
order-7 interior quadrature and each boundary facet with an order-10 line rule
and its known square normal. It must match every assembled nodal component to
relative 1e-11 with absolute floor 1e-8 N/m. This is stronger than checking only
a zero resultant. Symmetric analytic stress gives zero total body+full-surface
force and moment; consistent shape functions reproduce constant and linear
virtual displacements, hence those resultants are preserved by nodal loads.

Every MMS solve also checks independently fitted strain and stress, total
force/moment balance, affine virtual work, and:

    2 U_h = sum_i load_i dot u_i + sum_fixed reaction_i * prescribed_i.

Here load includes body and traction terms and U_h is J/m of out-of-plane
thickness. Support work cannot be omitted with nonzero prescribed displacement.
The work/balance tolerance is relative 1e-9. Stress/strain/displacement absolute
floors are 1e-6 Pa, 1e-12 and 1e-12 m respectively. Mesh-transformation comparisons
use relative 1e-10 and force floor 1e-8 N/m. The values were fixed before results.

## Exact line loads and affine physical answers

For the unit right edge use the independent nonuniform traction:

    t(y) = (3+2y^6, -4+y^5) Pa.

For one full edge, integral N0*y^p=1/[(p+1)(p+2)] and
integral N1*y^p=1/(p+2). On an interval [a,b], exact antiderivatives of y^p and
y^(p+1) give the two linear-shape loads. Tests use 1,3,9 edge subdivisions and
compare every nodal component. The resultant is (3+2/7,-4+1/6), and the moment
about the origin is `-4+1/6-3/2-2/8`. Degree-six traction times a linear shape has
degree seven, so the specified four-point Gauss rule should integrate it exactly.
This check detects line-weight errors that total-force-only tests could miss.

For each plane, separate physical checks use vertical uniaxial tension P=127 Pa
and transposed shear tau=91 Pa. Vertical compliance is:

| Plane | exx | eyy |
|---|---|---|
| Stress | -nu P/E | P/E |
| Strain | -nu(1+nu) P/E | (1-nu^2) P/E |

The uniaxial roller solution is u=(exx*x,eyy*y), sigma=(0,P,0). For shear,
u=(0,tau*x/G) with both left components fixed; right/top/bottom tractions follow
from sigma=(0,0,tau). Both answers are affine, reproduced to numerical roundoff.
They use direct compliance, not refsol or the engine material helper.

## Normals, pressure, overlap, transformations and rejection

The Cartesian callback `t=-P*n`, P>0, compresses the material. The API has no
implicit scalar-pressure convention; `+P*n` has the opposite sign. Both signs
are tested on a rectangle and a polygonal annulus. The annulus's material outward
normal points into the hole on the inner boundary. Expected facet normals come
from the known geometry: axis normals for the rectangle and normalized facet
midpoints for the regular concentric polygons, with reversed sign at the hole.
Every nodal pressure load is checked against half the facet length times its
constant traction; net zero alone would not detect an inverted normal.

Pressure-load tests combine edge reversal, tag ordering, reversed triangle
connectivity, arbitrary node/cell ordering, rotation .41 radians, translation
(1.7,-2.1) and length scale two. They check individual loads and reactions.
An additional non-affine MMS with both left displacement components clamped
checks actual displacement and stress covariance under the same transformations:

    x' = s Q x+c, u' = s Q u, body' = Q body/s, traction' = Q traction,
    sigma' = Q sigma Q^T, load' = s Q load, reaction' = s Q reaction,
    U' = s^2 U.

The two-component clamp can be transformed as a complete vector condition.
This does not assert covariance of an unchanged one-component global roller
under arbitrary rotations.

A fully prescribed nonzero affine boundary plus extra nonuniform traction checks
unchanged displacement and reaction change equal to minus the added nodal load.
Both None and {} preserve every result array exactly. Rejection cases cover
selected-tag duplication, reversed duplicate edges, an interior edge, malformed
shapes, noninteger/negative indices, self edges, a node-only tag, wrong callback
shape/transposition, nonfinite or complex values and insufficient rigid supports.
All use the original ValueError contract without changing production validation.

## Observed source evidence

First independent run: 31 passed, zero failed/skipped, with all pre-registered
criteria unchanged. Adding two displacement/stress covariance cases gives 33 new
checks. Together with the original traction, elasticity and package-independence
checks: **150 passed, zero failed/skipped**.

| Plane | Last L2 order | Last strain order | Last energy order |
|---|---:|---:|---:|
| Stress | 1.9416220 | .9756523 | .9746632 |
| Strain | 1.9409472 | .9764219 | .9742340 |

These observed orders differ from the original benchmark and are not fitted
tolerances. No production defect was observed in this scope. Limits remain:
only homogeneous isotropic linear small-strain 2D behavior, a polygonal hole,
fixed smooth fields and the specified material. This is not a validation of all
traction regularities, curved-boundary geometries, large deformations, materials,
platforms or locking-free near-incompressible formulations.

Run from the repository root with the existing packages installed:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -c pyproject.toml -q -s -ra \
  tests/galerkin/test_traction_independent_validation.py \
  tests/galerkin/test_elasticity_traction.py \
  tests/refsol/test_elasticity_traction_reference.py \
  tests/galerkin/test_elasticity2d.py \
  tests/refsol/test_elasticity_reference.py \
  tests/galerkin/test_independence.py
```

No external solver source or new dependency is used. Installed-wheel checks,
negative implementation controls and full-suite/CI results must be distinguished
from these source observations.
