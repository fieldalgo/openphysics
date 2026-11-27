# 3D thermoelasticity with a prescribed temperature

**English** | [한국어](../../locales/ko/pages/packages/galerkin/thermoelasticity3d.md)

Pass the nodal temperature array in K from the same metre-based `Mesh3D` to
`galerkin.thermoelasticity3d.solve_thermoelasticity_3d`. The array has shape
`(N,)` and follows mesh node order. `stress_free_temperature` is a scalar in K.
Both temperatures are finite and nonnegative. Each of
`linear_expansion_coefficient` (1/K), `youngs_modulus` (Pa) and
`poisson_ratio` can be a scalar or a mapping over the material region names.
The expansion coefficient may be signed.

The P1 mean temperature on each tetrahedron is the average of its four nodal
values. The local free strain is α(mean(T) − Tref) times the identity. The
elastic solver computes stress from total strain minus this free strain.
`prescribed_displacement` maps `(node, component)` to metres.
`body_force_density` (N/m³) and tagged `traction` (Pa) use the elastic
solver's conventions. Traction is the total physical stress times the outward normal.

The elastic result provides displacement `(N, 3)` in metres and element
total strain and stress `(T, 3, 3)`. These are symmetric tensors with physical
shear strain and tension-positive stress in Pa. The support reactions are in N.

The independent checks use a free uniform expansion, a fully fixed unit
tetrahedron with hydrostatic stress −E α ΔT/(1 − 2ν), and support reactions
equal to volume times stress acting on each barycentric basis gradient. The
tests also cover zero temperature rise and signed region-specific expansion.
