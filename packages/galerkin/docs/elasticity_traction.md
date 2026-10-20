# Cartesian boundary traction for 2D elasticity

This extends `galerkin.elasticity.solve_elasticity` with optional boundary
traction in the existing P1 vector nodal displacement space. Import the
submodule explicitly; no top-level export or simcase integration is added.
The formulation, plane selection, engineering shear, material range and
locking limits in [the initial guide](elasticity2d.md) still apply. This
guide supersedes its earlier statement that nonzero traction is unsupported.

## API and units

```python
from galerkin.mesh import rectangle_mesh
from galerkin.elasticity import solve_elasticity

mesh = rectangle_mesh(1.2, .7, 12, 7)  # metres
bc = {(int(i), 0): 0. for i in mesh.boundary["left"]}
bc.update({(int(i), 1): 0. for i in mesh.boundary["bottom"]})
r = solve_elasticity(mesh, young_modulus=70000., poisson_ratio=.3,
                     plane="stress", dirichlet=bc,
                     traction={"right": (123., 0.)})
print(r.load.sum(axis=0), r.reaction.sum(axis=0))  # N/m of thickness
```

`traction=None` (the default) or `{}` preserves the previous zero-traction
behavior. The existing `body_force` parameter and component-wise Dirichlet
mapping are unchanged. Nonselected boundaries carry zero applied traction
on their unconstrained components. E and nu remain homogeneous; plane must
be explicitly `"stress"` or `"strain"`.

| Quantity | Definition | SI unit |
|---|---|---|
| Coordinates / prescribed and returned displacement | existing Mesh / nodal u | m |
| Traction | global Cartesian vector t=sigma*n | Pa = N/m^2 |
| Edge integration measure | ds | m |
| Consistent boundary nodal load | integral(N_i*t)ds | N/m of thickness |
| Body force | existing volume density b | N/m^3 |
| result.load | **total body plus boundary** nodal load, `(N,2)` | N/m of thickness |
| result.reaction / residual | original K*u-load, reaction only at prescribed DOFs | N/m of thickness |
| Moment about an in-plane point | sum(r_x*f_y-r_y*f_x) | N = (N*m)/m of thickness |
| Elastic strain energy / external work | per thickness | J/m = N |

Multiply load and reaction by physical thickness in metres to obtain total
force in N; multiply moment and energy by thickness to obtain N*m and J.
For one-metre thickness the numerical values equal those totals. One-millimetre
thickness requires multiplying by 0.001. No implicit thickness parameter or
nodal force input is introduced.

## Tags, edges, normals and input data

`traction` is a mapping `{tag: vector_or_callable}`. A tag must have an explicit
`mesh.boundary_edges[tag]`: a nonempty integer `(E,2)` array of node pairs.
The `mesh.boundary` node sets alone do not define a traction boundary. To
select only a subset, define a new boundary_edges tag containing exactly the
desired mesh edges. Merely joining a sequence of boundary node indices can
produce an invalid edge selection.

Each selected edge must belong to exactly one triangle. Interior edges,
non-mesh segments, zero-length edges, invalid indices, invalid shape/type
and repeated edges are rejected with ValueError. The same geometric edge
may not be selected twice, either in one tag or across different selected
tags; there is no implicit summation of overlapping tags. Shared vertices
between adjacent edges are valid. Unselected tag definitions are not used.
As in the initial API, Mesh construction itself casts supplied connectivity
to integers; callers must supply integer connectivity, rather than relying
on truncation. Validation examines the actual arrays on the Mesh.

The tangent direction of a tag edge is arbitrary. The unit normal is the
perpendicular pointing **away from the unique owning triangle**. It points
outside an outer boundary and into a hole on an inner boundary. Reversing
tag node pairs, reordering edges, or reversing triangle orientations does
not reverse the physical normal. The existing global geometry/manifold
checks run before traction integration.

The supported field forms are:

- A finite real constant array of exactly shape `(2,)`, e.g. `(123.,0.)`.
  Components are global x/y tractions in Pa.
- A callable `field(points, normals)`. Both arguments have shape `(Q,2)`;
  points are coordinates in m and normals are outward dimensionless unit
  vectors. The return must be a finite real array of exactly `(Q,2)` in Pa.
  The callback is called once per selected tag for all its quadrature points.
  Geometry-dependent, side-effect-free callbacks are recommended; no global
  point ordering is part of the public contract.

For example, this nonuniform global Cartesian field is allowed:

```python
import numpy as np

def traction_xy(points, normals):
    y = points[:, 1]  # metres
    return np.column_stack([100. + 20.*y, -30. + 10.*y*y])  # Pa
```

The constants in such expressions must carry the units needed to produce Pa.
Scalars are rejected: there is **no pressure API**, scalar normal load, local
normal/tangent coordinate mode, follower load or load depending on the unknown
displacement. An analytic stress field can explicitly return sigma*n using
the supplied normals. The callable must not treat normals as tangents or
assume tag orientation defines their sign.

## Consistent integration and Dirichlet overlap policy

For an edge from a to b, q(s)=(1-s)*p_a+s*p_b, 0<=s<=1,

    f_a = length * integral_0^1 ((1-s)*t(q(s),n)) ds
    f_b = length * integral_0^1 (s*t(q(s),n)) ds.

The integral uses a fixed four-point Gauss-Legendre rule. Constant traction
is split equally between the endpoint DOFs. Linear traction has nonuniform
consistent weights; simple equal splitting is incorrect. The rule integrates
the shape-function times any polynomial traction of degree <=6 exactly on
a straight edge. General smooth loads require mesh/quadrature verification;
oscillatory or discontinuous loads are not automatically integrated accurately.
There is no nodal interpolation assumption for callable tractions.

**Loads on prescribed displacement components are allowed and retained.**
They are interpreted as applied external forces at those DOFs. The prescribed
displacement still determines that component, and its support reaction is
computed from the original system `reaction=(K*u-load)` there. Such a load
does not additionally impose an independent stress boundary condition on
the constrained component. Loads are neither silently discarded nor used
to overwrite the Dirichlet value. This also applies to shared corner nodes
and to a fully prescribed edge. Increasing a load at a fixed DOF changes its
reaction; if all affected DOFs are fixed, it need not change displacement.

`result.load` includes both body and boundary loads, even at constrained
DOFs. `result.reaction` is zero at free DOFs. `result.residual` retains K*u-load
at all DOFs; its prescribed entries are physical reactions. Force and moment
balance use **load plus reaction**, not either term alone.

All three rigid modes must still be removed in each disconnected component.
Balanced pure traction does not make a displacement solution unique and is
rejected without sufficient prescribed displacement. No automatic node pins,
weak springs, penalty regularization or least-squares solutions are added.

For homogeneous linear elasticity with loads and prescribed displacements
ramped proportionally from zero,

    U = .5 * integral(epsilon:sigma) dA
      = .5 * sum(u * (load + reaction)) = W_external.

This energy/work is per thickness. With zero prescribed displacement the
support work vanishes. With nonzero prescribed displacement, ignoring
reaction work gives an incorrect balance. The equality does not describe
an arbitrary load history or an arbitrary product of final forces and
displacements; the factor 1/2 assumes the proportional linear ramp.

## Independent analytic validation

`refsol.elasticity_traction` imports no FEM engine. It supplies:

- `uniaxial`: sigma=(P,0,0), with plane-stress strain
  `(P/E,-nu*P/E,0)` or plane-strain strain
  `((1-nu^2)*P/E,-nu*(1+nu)*P/E,0)`;
- `shear`: sigma=(0,0,tau), u=(tau/mu*y,0), for either plane selection;
- `polynomial_manufactured` and `polynomial_traction`: directly differentiated
  cubic displacement, quadratic stress/traction and linear body force;
- `polynomial_resultants`: closed-form body-plus-three-wall force and moment;
- `traction_from_stress`: direct Cartesian tensor-normal multiplication.

The manufactured unit-square case uses reference length L0=1 m, amplitude
A=1e-3 m, E=70000 Pa and nu=0.3. Write the dimensionless coordinates
X=x/L0, Y=y/L0:

    u_x = A*(X^2+X*Y+X*Y^2)
    u_y = A*(.6*X^2*Y+.2*X*Y^2+.3*X^3)
    exx = A/L0*(2*X+Y+Y^2)
    eyy = A/L0*(.6*X^2+.4*X*Y)
    gamma_xy = A/L0*(X+3.2*X*Y+.2*Y^2+.9*X^2)
    sigma_xx = (lambda+2*mu)*exx + lambda*eyy
    sigma_yy = lambda*exx + (lambda+2*mu)*eyy
    sigma_xy = mu*gamma_xy
    b_x = -A/L0^2*(2*(lambda+2*mu)+2*mu*X+(lambda+mu)*(1.2*X+.4*Y))
    b_y = -A/L0^2*(mu*(1.2*Y+1.8*X)+.4*X*(lambda+2*mu)+(lambda+mu)*(1+2*Y))

The reference accepts metre coordinates on this fixed domain; it is not a
unit conversion mechanism. The explicit A/L0 and A/L0^2 factors ensure strain
is dimensionless and b has units Pa/m = N/m^3. L0 is numerically one in SI.
Lambda is the effective value for the explicitly selected plane, as in the
initial guide. Both components are fixed to zero at x=0; the other three walls
carry the analytic sigma*n, rather than zero traction. No computed FEM
solution is used to generate the oracle.

The exact applied resultant, excluding support on the left wall, is

    F = A*(5*(lambda+2*mu)/6, mu/15)
    M_origin = -7*A*L0*(lambda+2*mu)/12.

These are the negative left-wall traction integrals, in N/m and N for the
fixed unit-metre domain. They independently check global boundary sign and
body/edge integration. Reference tests finite-difference the displacement
kinematics and negative stress divergence; the reference is also checked
against known plane-specific uniaxial and tensor-normal answers.

The following criteria and meshes were fixed before numerical results:

| Check | Gate |
|---|---|
| Uniform P=123 Pa uniaxial and tau=87 Pa shear, both planes | affine displacement/strain/stress relative <=1e-10 with roundoff floors |
| Consistent linear and degree-six edge weights / resultants / moments | scaled error <=1e-12 |
| Polynomial MMS, n=8,16,32 in each direction, both planes | decreasing L2/strain/energy errors; final L2 order >=1.8, strain/energy orders >=0.9 |
| Total force / moment balance | relative <=1e-9 |
| Proportional external work vs strain energy | relative <=1e-10 |
| Homogeneous-Dirichlet Galerkin identity 2*(U_exact-U_h)=energy_error^2 | defect / U_exact <=1e-8 |
| Edge/tag orientation, rigid coordinate rotation/translation and size scaling | relative <=1e-10 |
| Hole normal direction, fixed-DOF load retention, invalid data and rigid modes | explicit checks / ValueError |

An independent 8x8 interior Duffy rule measures displacement L2, tensor
strain L2 (engineering shear contributes gamma_xy^2/2) and energy error
`sqrt(integral(delta_epsilon:delta_sigma)dA)`. Their units are m^2, m and
sqrt(J/m), respectively. U_exact is integrated from the analytic fields;
it is not obtained by invoking the solver on a fine mesh.

| Plane | n=8 / n=16 / n=32 displacement L2 | Last L2 order | Last strain order | Last energy order |
|---|---|---:|---:|---:|
| stress | 3.2716170e-5 / 8.5427956e-6 / 2.1627088e-6 | 1.98187 | 0.99567 | 0.99546 |
| strain | 3.3961009e-5 / 8.9269633e-6 / 2.2655929e-6 | 1.97828 | 0.99624 | 0.99523 |

These are numerical accuracy results, not performance baselines. The
existing zero-traction tests and answer key are unchanged. The old sine MMS
and the new mixed-boundary polynomial case provide separate regression gates.

## Reproduce and limits

Run from the repository root, using your installed local packages:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python packages/galerkin/examples/elasticity_traction.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q -s tests/galerkin/test_elasticity_traction.py tests/refsol/test_elasticity_traction_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q
```

Near-incompressible plane-strain P1 locking, coarse-mesh bending stiffness,
small-strain assumptions and floating-point mesh limits are unchanged.
Passing a small algebraic residual is not an accuracy certificate near
nu=0.5. This extension adds no pressure model, thermal expansion, nonlinear
material, large deformation, contact, dynamics, 3D, simcase or Studio feature.
It introduces no dependency and copies no external solver implementation.
The guide and example stay in the source tree and are not shipped in the sdist;
the installed checks copy the example from the checkout and run it against
the installed wheels.
