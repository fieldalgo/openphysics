# Three-dimensional small-strain elasticity

[한국어](../../locales/ko/pages/packages/galerkin/elasticity3d.md)

Use `galerkin.elasticity3d.solve_elasticity_3d` with a conforming `Mesh3D` in metres.
This is a static isotropic linear elastic solve with P1 tetrahedra and three
Cartesian displacement components per node. Pass `youngs_modulus` in Pa
(E > 0) and dimensionless `poisson_ratio` (−1 < ν < 0.5) as scalars or mappings
covering every named material region.

The `prescribed_displacement` mapping takes `(node, component)` keys and
displacements in m. Components 0, 1 and 2 denote x, y and z. The constraints
must eliminate three translations and three rotations on each disconnected
component. Supply an optional constant Cartesian `body_force_density` in N/m³
and a `traction` mapping from exterior face tags to constant Cartesian vectors
in Pa. Omitted loads are zero. Traction is the force per area applied to the
body, so it can contribute to a support reaction on a prescribed component.

The result gives nodal `displacement` in m and symmetric element `strain`
and `stress` tensors with shape (T, 3, 3). Strain is total infinitesimal
strain with physical shear components. Stress is in Pa with tension positive.
The nodal `applied_force`, `reaction_force` and `residual_force` arrays are
(N, 3) in N. Residual is internal minus applied force. Reaction is the
force exerted by a constraint on the body and is zero on free components.

Validation covers uniaxial traction and Poisson contraction, simple shear,
force and moment balance, and three refinements of a quadratic manufactured
displacement. An independent scikit-fem P1 solve compares displacement, stress,
and reactions under both volume and surface loading.
