# Static wedge harmonic half-space assembly

`assemble_harmonic_corner_half_space` in `galerkin.laplace_corner_harmonic_assembly`
returns `HarmonicCornerHalfSpaceMatrix`. It assembles the logarithmic Green
function above the infinite grounded line y=0 for convex disjoint polygons
strictly inside the supplied SI rectangle. Width and height admit and normalize
geometry; this kernel has no upper or side boundary. It does not solve charges.

Each physical panel uses rho_p=p/h*u^(p−1) and
sqrt(3)*(rho_2p−rho_p), with integrated masses1 and0. These are static spatial
wedge modes. Indices2*i and2*i+1 identify those modes. The unchanged geometry
preparation merges four cubic intervals at each edge end. Subdivisions are
even16–512; total physical panels must be at most512, before dense allocation.
There are at most1024 density unknowns. No resource failure selects a fallback.

Exact self, explicitly admitted far/shared-origin/separated and partitioned
unit-source primitives retain their physical measure and budgets. Both pair
orientations are assembled. Fine/coarse difference and raw reciprocity must
be at most1e-10 relative to matrix magnitude before any caller's symmetry
averaging. Coarse/fine matrices and geometry arrays are detached and immutable.
An unresolved interaction reports its panel indices and stops assembly.

Checks preserve the constant-mode subspace, positive energy, reflection,
translation, orientation, conductor permutation and exact common scale.
Circular conductor comparisons use C/epsilon=2*pi/acosh(h/a), signal squared
unit-current integral h/(2*pi*a*sqrt(h²−a²)) and infinite-ground integral
1/(2*pi*sqrt(h²−a²)). The ground value is evaluated separately by a converged
Fourier integral. Circumscribed polygons approach the circular limit; a finite
polygon is not the exact circle. These checks do not establish a finite
upper-boundary solver, fixed-guard accuracy, physical measurement agreement,
an arbitrary dielectric-interface corner model or other-platform support.

See [primitive interaction contracts](laplace_corner_harmonic_interactions.md)
and [self/Gram contracts](laplace_corner_harmonic.md).

[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_harmonic_assembly.md)
