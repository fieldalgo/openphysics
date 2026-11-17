# Three-active static corner-harmonic fields

`galerkin.laplace_corner_harmonic_field.solve_two_ground_harmonic_corner_three_active_edges`
is an explicit 2D electrostatic/current-density API for exactly three active
finite conductors between two grounded planes. Each conductor supplies one
independent voltage basis. There is no internal fixed-ground or floating-guard
selection. Homogeneous Neumann side walls retain the existing rectangular
Green-function contract. This does not calculate longitudinal transitions or
full-wave propagation.

Coordinates are in metres. Polygons must be convex, disjoint and strictly
inside the rectangle, with the existing side-clearance admission. The caller
supplies `width`, `height`, even `panels_per_edge` in 10..512, even
`ground_modes` in 64..4096, and `interpolation_degree=24`. Defaults are 48
subdivisions and 256 ground modes. Cubic corner merging leaves `n-6` physical
panels per edge. At most 512 physical panels and 1024 density modes are
admitted. Thus the default fits three quadrilaterals; a polygon with many
vertices needs explicitly smaller controls. Invalid budgets are refused before
dense assembly; no automatic geometry or accuracy fallback is applied.

The two static spatial modes are `rho_p` and `sqrt(3)*(rho_(2p)-rho_p)`.
They retain physical masses, corner exponents and surface-current Gram weights.
The word harmonic describes these spatial wedge modes, not time harmonics.
Raw half-space blocks use the existing accepted integrals; the private compact
wrapper changes geometry partition admission only. Smooth upper-plane/side
corrections and grounded-plane Fourier currents retain their refinements.
The matrix condition bound must be below 1e10. Raw reciprocity, matrix and
ground refinements, residual/energy identities, current balance and face
partition checks remain 1e-10. The result preserves numerical evidence.

The returned `TwoGroundRectangleEdgesResult` contains:

- `whole.capacitance_per_permittivity`: dimensionless 3 by 3 capacitance divided
  by permittivity; multiply by physical uniform permittivity for F/m.
- `whole.current_gram`: three conductor and two grounded-plane 3 by 3 matrices,
  in inverse metres, normalized to independent unit conductor currents.
- Edge Gram matrices and signed integrated currents, edge ownership and metre
  endpoints. Whole and edge arrays are immutable snapshots.

Physical face-metal laws and frequency-dependent dielectric extraction belong
to consumers. These static matrices do not themselves include conductivity,
roughness, skin-depth admission, material dispersion or a target search.

Validation separates numerical identities from physical approximation. A
three-tapered-conductor family is checked at 16/32/48 subdivisions, with two
separate larger boxes, reflection, conductor permutation and exact binary
length scales. Full-basis independent degree-four finite-element references
are recorded separately. A three-circle limit uses independent orthonormal
Fourier charges, analytical self eigenvalues and ground multipole integrals.
Its single-circle analytic control and Fourier order/rule convergence precede
the finite 21-gon comparison. Polygon, density and outer-domain studies remain
separate; finite boxes and polygons are not exact circles. Neither these cases
nor internal residuals establish arbitrary-geometry or measured accuracy.

Existing public geometry/solvers and their minimum controls are unchanged.
The unresolved fixed-ground guard cases are not qualified by this API. No
other-platform, product-integration or deployment qualification is implied.

[Two-ground fields](two-ground.md) ·
[Compact geometry](laplace_corner_compact_geometry.md) ·
[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_harmonic_field.md)
