# Two-dimensional small-strain elasticity

Use the explicit submodule imports `galerkin.elasticity` and `refsol.elasticity`.
This first implementation is a homogeneous, isotropic, linear, static
displacement formulation on a conforming `galerkin.mesh.Mesh` of P1 triangles.
There are two displacement DOFs per node; scalar and electromagnetic edge
spaces are not used. E and nu may also be piecewise constant on named mesh
regions, `{region name: value}`; that extension, its references and gates are
in [multimaterial](multimaterial.md). Everything below describes one
homogeneous material unless stated otherwise.

## Equations and conventions

For in-plane displacement u=(u_x,u_y),

    -div(sigma) = b,
    epsilon = (grad(u) + grad(u).T)/2,
    sigma = 2*mu*epsilon + lambda_eff*trace(epsilon)*I.

The engineering-strain vector is `(epsilon_xx, epsilon_yy, gamma_xy)`,
where **gamma_xy = 2*epsilon_xy = du_x/dy + du_y/dx**. The in-plane
stress vector is `(sigma_xx, sigma_yy, sigma_xy)`. Thus the shear matrix
entry is mu, not 2*mu, and stress work is `stress @ strain`.

    mu = E / (2*(1+nu))
    D = [[lambda_eff+2*mu, lambda_eff,      0],
         [lambda_eff,      lambda_eff+2*mu,0],
         [0,               0,             mu]]

The required argument `plane` selects one of two different models:

| plane | Out-of-plane condition | lambda_eff | Unreturned out-of-plane quantity |
|---|---|---|---|
| `"stress"` | sigma_zz=sigma_xz=sigma_yz=0 | E*nu/(1-nu^2) | epsilon_zz=-nu*(epsilon_xx+epsilon_yy)/(1-nu) |
| `"strain"` | epsilon_zz=epsilon_xz=epsilon_yz=0 | E*nu/((1+nu)*(1-2*nu)) | sigma_zz=lambda_eff*(epsilon_xx+epsilon_yy) |

No model is chosen automatically. Both use the stable three-dimensional
parent material domain: finite scalar **E>0, -1<nu<0.5**. Auxetic nu<0 is
allowed. The two models give different lateral strain and axial stiffness
even for uniaxial extension with free lateral surfaces.

With shape-function gradients and interleaved local DOFs,

    B = [[N0,x, 0,    N1,x, 0,    N2,x, 0],
         [0,    N0,y, 0,    N1,y, 0,    N2,y],
         [N0,y, N0,x, N1,y, N1,x, N2,y, N2,x]]
    K_e = area * B.T @ D @ B
    f_e = integral_over_triangle(N_vector.T @ b) dA

Global DOF `2*i` is node i's x displacement, and `2*i+1` is its y
displacement. Element strain and stress are constant on each triangle.
Body-force integration uses a 6x6 Gauss-Legendre Duffy rule, exact for
constant body force. Smooth nonpolynomial loads are approximated; discontinuous
or highly oscillatory loads require a mesh/quadrature study outside these gates.

## Input and output units

The two-dimensional weak form is **per unit out-of-plane thickness**. No
thickness parameter is accepted. This avoids hiding a length factor in loads.

| Quantity | Shape / convention | SI unit |
|---|---|---|
| Mesh coordinates | `(N,2)` | m |
| E, stress | scalar E or `{region name: E}`; stress `(T,3)` | Pa = N/m^2 |
| nu, strain | scalar nu or `{region name: nu}`; strain `(T,3)`, engineering shear | dimensionless |
| Prescribed/result displacement | scalar per `(node,component)`; result `(N,2)` | m |
| body_force | constant `(2,)`, or callback `(Q,2)->(Q,2)` | N/m^3 |
| stiffness matrix, internal | `(2N,2N)` | N/m^2 |
| result.load | total consistent body and boundary nodal load `(N,2)` | N/m of thickness |
| result.reaction | support force ON the body, `(N,2)` | N/m of thickness |
| result.residual | `K*u-load` at all DOFs, `(N,2)` | N/m of thickness |
| `0.5*u.T*K*u`, if reconstructed | energy per thickness | J/m = N |

For a physical thickness t in metres, multiply load, reaction and energy by t
to obtain N, N and J. For a **one-metre thickness**, the numerical values equal
those totals. A one-millimetre plate requires multiplication by 0.001.
Displacement, strain and stress do not change under uniform thickness scaling.
Body force is a volume density, not a total nodal force or an edge line load.

## API and boundary conditions

```python
from galerkin.mesh import rectangle_mesh
from galerkin.elasticity import solve_elasticity

mesh = rectangle_mesh(.1, .02, 20, 4)  # coordinates in metres
bc = {(int(i), c): 0. for i in mesh.boundary["left"] for c in (0, 1)}
r = solve_elasticity(mesh, young_modulus=70e9, poisson_ratio=.3,
                     plane="stress", dirichlet=bc,
                     body_force=(0., -2700*9.81))
print(r.displacement[:, 1].min())
print(r.load.sum(axis=0), r.reaction.sum(axis=0))
```

`dirichlet` is a mapping `{(node_index, component): value_in_metres}`;
component 0 is x, component 1 is y. Nonzero values are supported. Indices must
be integers (not booleans), and nodes must be on the geometric boundary,
including hole boundaries. It does not depend on the names in `mesh.boundary`.
Boundary node tags are merely a convenient way to construct the mapping.
Without an applied traction mapping, the corresponding traction is zero on all
unconstrained boundary components.
Prescribing only x leaves the y traction zero there unless a boundary load is
provided. Nonzero global Cartesian boundary traction is supported through the
optional `traction` mapping; see the [traction guide](elasticity_traction.md)
for tags, callable normals, consistent integration and loads on prescribed DOFs.
Point forces, periodic constraints and multipoint constraints are not supported.
Interior prescribed displacement is rejected in this first API.

A body-force callback receives all quadrature coordinates as a real `(Q,2)`
array and must return a finite real array of exactly the same shape. The
callback is evaluated once; stateful callbacks are discouraged. Constant
forces must have exactly shape `(2,)`. Arrays of per-node/per-element loads
are not interpreted implicitly.

`ElasticityResult` contains `displacement`, `strain`, `stress`, `load`,
`reaction`, `residual`, and the explicit `plane` string. Reaction is `K*u-load`
at prescribed DOFs and zero at free DOFs. Residual at free DOFs should be small;
its prescribed entries are physical reactions, not a convergence failure.
For zero applied traction, `sum(reaction)+sum(load)=0`, up to solve roundoff.
The reaction uses the original system, before constraint elimination.

For the example script, install the existing packages in your own environment
and run from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python examples/galerkin/elasticity2d.py
python -m pytest -q -s tests/galerkin/test_elasticity2d.py \
  tests/galerkin/test_mesh_overlap_candidates.py \
  tests/refsol/test_elasticity_reference.py
python -m pytest -q
```

## Independent reference and fixed acceptance gates

`refsol.elasticity` imports no FEM engine or solver. `affine` evaluates
`u=gradient*x+offset`; `stress_from_strain` uses closed-form plane-specific
stress equations; `sine_manufactured` directly differentiates the analytic
Navier equation. All return engineering strain and in-plane stress, with no
out-of-plane components. The FEM implementation imports no reference solution.

The nontrivial manufactured case on the unit square is

    u = 1e-3*sin(pi*x)*sin(pi*y)*(1, 0.6)
    s = sin(pi*x)*sin(pi*y), c = cos(pi*x)*cos(pi*y)
    b_x = pi^2*((lambda_eff+3*mu)*1e-3*s-(lambda_eff+mu)*0.6e-3*c)
    b_y = pi^2*((lambda_eff+3*mu)*0.6e-3*s-(lambda_eff+mu)*1e-3*c)

E=70000 Pa, nu=0.3. Both components are prescribed on the entire boundary;
zero displacement does **not** imply zero traction for this exact solution.
The structured mesh uses n=8,16,32 subdivisions per direction. Displacement
L2 error and the tensor strain Frobenius error are integrated with an
independent 8x8 Duffy rule. Energy error is
`sqrt(integral((epsilon_h-epsilon):D:(epsilon_h-epsilon)) dA)`, without a
factor 1/2. The strain norm uses `exx^2+eyy^2+gamma_xy^2/2`.

These gates were recorded before running the implementation:

| Check | Fixed gate |
|---|---|
| Affine displacement / constant strain / stress patch, both planes | relative error <=1e-10 (small absolute roundoff floors) |
| Rigid translation plus infinitesimal rotation | strain absolute <=1e-12 |
| Component-wise uniaxial extension with free lateral traction | plane-specific analytic lateral displacement/stress, <=1e-10 relative |
| Smooth manufactured displacement, both planes | decreasing errors, last L2 order >=1.8 |
| Same manufactured strain and energy | decreasing errors, last orders >=0.9 |
| Global load/reaction balance | relative imbalance <=1e-9 |
| Moment equilibrium, clamped body-force rectangle | relative scaled imbalance <=1e-9 |
| Invalid material/force/geometry/index/rigid modes | explicit ValueError |

Initial cloud results on Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0:

| Plane | n=8 L2 / n=16 L2 / n=32 L2 (m^2) | Last L2 order | Last strain order | Last energy order |
|---|---|---|---|---|
| stress | 1.95006e-5 / 4.94136e-6 / 1.23990e-6 | 1.99469 | 0.99808 | 0.99817 |
| strain | 1.88764e-5 / 4.79193e-6 / 1.20324e-6 | 1.99368 | 0.99816 | 0.99820 |

The integrated displacement L2 norm has units m^2 on this two-dimensional
domain; it is not a pointwise displacement. Strain L2 has units m, and the
energy norm has units sqrt(J/m). These are accuracy checks, not timing baselines.
The reference tests also check known stress coefficients and a finite-difference
negative stress divergence independently of the assembled system.

## Rejections and limits

The solver checks finite real coordinate and force data, shapes, integer
connectivity and indices, unused/coincident nodes, duplicate or numerically
degenerate triangles, edge/vertex nonmanifold topology, overlapping interiors
and hanging nodes. Mesh construction itself can raise before the solver when
given invalid connectivity; `Mesh` casts input connectivity to integers, so
callers must not use that constructor to silently truncate fractional indices.
The solver validates the actual arrays present on the Mesh at call time.
Numerical topology checks use local geometric tolerances (1e-12) and reject
triangles whose determinant is <=1e-14 times squared edge scale. Features
below floating-point geometric resolution are outside the contract. The
overlap test considers two triangles only when their centroids lie within twice
the larger of their centroid radii (largest centroid-to-vertex distance), which
every overlapping pair satisfies, so its cost follows the local mesh grading,
not the largest triangle.

Each disconnected component needs independent removal of x/y translation and
in-plane rotation. The prescribed-DOF restriction of these three rigid modes
must have rank three (dimensionless rank tolerance 1e-10). Otherwise the solver
raises with the component number; it does not pin a node, add springs, silently
regularize or accept a least-squares displacement. Numerically ambiguous
near-collinear supports can therefore be rejected. A sparse direct solve and
a backward residual check follow this geometric check.

**Near incompressibility:** standard displacement-only P1 triangles exhibit
volumetric locking in plane strain as nu approaches 0.5. They can substantially
underpredict displacement despite small algebraic residuals. nu=0.5 is rejected;
passing the strict nu<0.5 input check is not an accuracy guarantee. Use a
validated mixed formulation for nearly incompressible materials; none is
provided here. The reported convergence covers nu=0.3, not that regime.
Thin bending-dominated structures can also be too stiff on coarse P1 meshes.
Large translations with tiny strains may lose floating-point accuracy.

No nonlinear constitutive law, large deformation, contact, dynamics, 3D,
thermal expansion, multiphysics coupling, simcase or Studio integration is
included. Small strain and infinitesimal rotation are modeling assumptions,
not automatically enforced amplitude limits. Rigid rotations in these tests
are infinitesimal rotation fields, not finite rotations.

This module uses only existing NumPy/SciPy dependencies and original formulas;
no external solver implementation is copied. The example/document live in the
source tree and are not shipped in the distributions; the installed checks copy
the example from the checkout and run it against the installed wheels.

JAX and PyTorch inputs and the derivatives they carry are described in
[Derivatives with JAX and PyTorch](differentiation.md).
