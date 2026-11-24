# Two active conductors with a fixed-potential finite guard

`galerkin.laplace_corner_harmonic_guard_field.solve_two_ground_harmonic_corner_guard_edges`
is an explicit static 2D API for exactly three finite conductors between two
grounded planes. The required `signals` argument selects two distinct ordered
indices from0,1,2. The remaining conductor is held at zero voltage; its induced
current and losses remain part of the result. Homogeneous Neumann side walls
retain the existing bounded rectangular Green-function contract.

Supply a list/tuple of three convex disjoint polygons strictly inside the
rectangle, metre `width`/`height`, and the explicit signal indices. For example,
`signals=(0,2)` makes conductor1 the fixed-potential guard. The geometry array
order is independent of the active-current coordinate order. A floating guard
would require a different physical model: this calculation does not eliminate
a floating voltage by a Schur complement. In a full three-voltage capacitance
matrix, the active capacitance is C_SS and full currents are
T I_active with T=C[:,S] inv(C_SS).

The selected active basis drives the same accepted compact harmonic assembly.
Two physical radial modes per panel retain corner exponents and Gram weights.
Controls are even `panels_per_edge`10..512, even `ground_modes`64..4096 and
`interpolation_degree=24`. Defaults are48 subdivisions and256 ground modes.
Cubic corner merging leaves n-6 physical panels per edge, with a maximum of
512 physical panels and1024 density modes. The default fits three quadrilaterals;
more vertices require explicitly smaller controls. Unresolved geometry or
quadrature is refused without fallback. Matrix condition remains below1e10;
raw reciprocity, refinement, residual/energy, plane-current balance, face
partition and Gram consistency retain1e-10 gates.

The immutable `TwoGroundRectangleEdgesResult` uses two active current
coordinates in the supplied `signals` order:

- `whole.capacitance_per_permittivity` is a dimensionless2x2 matrix. Multiply
  by uniform physical permittivity for F/m.
- `whole.current_gram` contains three finite-conductor and two plane2x2
  matrices in inverse metres. Finite-conductor rows retain polygon order.
- `whole.current_integrals` retains signed current on every finite conductor
  and plane. Active rows form the identity; the guard row need not vanish.
- Edge Grams, signed integrated currents, original polygon owners and metre
  endpoints retain all conductor faces, including guard faces.

Frequency-dependent metal laws, roughness, skin-depth admission and separate
nonuniform dielectric extraction belong to consumers. This static API does
not supply those material models or a target search by itself.

Validation requires current conservation, positive Grams, exact face partition,
explicit signal/polygon permutations, reflection, physical scales,32->48 panel
comparison and two separate larger domains. The registered tapered-guard case
also has separate independent same-mesh degree4/5/6 finite-element evidence;
its older unresolved reference comparisons remain historical failures.
A second geometry family uses independently solved Fourier charges on three
circles. Fixed-voltage current coefficients are re-integrated on every circle
and on the infinite ground plane, with independent Fourier order/rule checks
and multiprecision ground integrals. Polygon, density and finite-outer studies
precede the final21-gon comparison. Finite boxes/polygons are approximations,
and these registered cases do not certify arbitrary geometry or measurements.

The existing three-active API continues to require all three active conductors.
Other platforms, product consumer integration and UI require separate checks.

The panel (32 to 48 per edge) and outer-width (8, 16, 32 mm) convergence study of
this page's test module takes from tens of minutes to hours on one CPU, longer than
a validate.yml test partition. It is marked `slow`, runs only with
`OPENPHYSICS_PANEL_STUDIES=1` in the dispatch-only job `panel-studies` of validate.yml (input `panel_studies=true`), and
keeps its 1% criteria. The regular suite checks that the 32-panel, 8 mm
resolution its other tests solve reproduces the values recorded with the study
(`tests/galerkin/two_ground/evidence/corner-field-studies.json`, within 1e-9 of
each matrix's largest entry); see `tests/_support/panel_studies.py`.

[Three-active fields](laplace_corner_harmonic_field.md) ·
[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_harmonic_guard_field.md)


A separate [one-active/two-fixed-guard API](laplace_corner_harmonic_single_active_field.md) selects one active current coordinate and retains induced guard currents. This does not change the two-active guard contract above.
