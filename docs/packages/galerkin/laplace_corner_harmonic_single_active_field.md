# One active conductor and two fixed-potential finite guards

`galerkin.laplace_corner_harmonic_single_active_field.solve_two_ground_harmonic_corner_single_active_edges`
solves a static 2D field with exactly three convex, disjoint, strictly interior
finite conductors. The required integer `signal` selects index0,1 or2. Both
remaining conductors and the upper/lower planes are held at zero potential.
Side walls have homogeneous Neumann conditions. Geometry order is independent
of which conductor is active; this is not a floating-reference model.

The result retains one active current coordinate and all physical boundaries.
`whole.capacitance_per_permittivity` is a1x1 dimensionless matrix. Whole current
Grams contain three finite conductors and two planes, in inverse metres; signed
integrated currents retain nonzero induced currents on both guards. Every
finite-conductor edge has its own Gram and current integral. Multiplication by
physical permittivity gives capacitance per metre. No consumer capacitance
reduction or discarded guard loss is needed.

Controls and numerical gates retain the compact harmonic method: even
`panels_per_edge`10..512, even `ground_modes`64..4096 and
`interpolation_degree=24`, default48/256/24. The full geometry must remain within
512 physical panels and1024 density modes; three quadrilaterals at48 use504
physical panels. Each panel keeps two physical radial modes and their original
Gram weights. Unresolved geometry/quadrature is refused without a retry or
fallback. Internal reciprocity, refinement, current/energy and face-partition
checks use1e-10, with condition below1e10. These checks are consistency gates,
not absolute error estimates.

Registered validation uses unequal tapered conductors and independent same-mesh
P4/P5/P6 finite-element references, plus three independently solved Fourier
circles. Selected-current coefficients are reintegrated on circles and the
infinite plane, with Fourier order/rule and multiprecision ground checks.
Direct fields must reproduce fixed-voltage algebraic reductions, including
induced guard current. Physical panel, polygon, density and separate finite
outer-domain comparisons, reflection, scales and conductor-order permutations
retain their stated gates. Original failed research/harness records remain
separate. Tested cases do not certify arbitrary geometry or measured accuracy.

All three possible active indices are checked against full capacitance data;
result snapshots are immutable and invalid controls fail before assembly.
Metal surface laws, nonuniform dielectric extraction, manufacturing templates,
SIPI consumers and other platforms require separate integration and validation.
The existing two-active guard and three-active APIs remain unchanged.

[Two-active guard field](laplace_corner_harmonic_guard_field.md) ·
[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_harmonic_single_active_field.md)
