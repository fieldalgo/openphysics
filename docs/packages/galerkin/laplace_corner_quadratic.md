# Three radial-density self integrals

`galerkin.laplace_corner_quadratic` exposes
`power_panel_quadratic_gram(length, exponent)` and
`power_panel_quadratic_self_log(length, exponent)`. They return immutable
symmetric 3×3 arrays for one physical straight panel. They do not assemble
interactions between different panels or select a field method.

For h>0, p in (0.5,1], and rho_a(s)=a/h·(s/h)^(a−1), the ordered modes are
rho_p, sqrt(3)·(rho_2p−rho_p), and sqrt(5)·(2rho_3p−3rho_2p+rho_p).
Their integrated masses are [1,0,0]. These are static radial branches;
quadratic refers to the polynomial in (s/h)^p. At p=1 they are the first
three shifted Legendre densities.

The Gram integrates the physical current-density product and has units 1/m.
The self-log block integrates the same densities against log(|s−t| / 1 metre)
and is dimensionless. Only its 00 entry changes under length scaling. The
upper 2×2 blocks retain the exact binary64 values of the existing
[harmonic primitives](laplace_corner_harmonic.md). Physical weights are not
normalized after evaluation.

New Gram entries use rational expressions with explicit (p−1) factors.
New self-log entries use 64 Taylor coefficients about p=1, obtained from
split-domain logarithmic moments. Each untransformed coefficient has magnitude
below one; the largest transformed coefficient bound is 180. The omitted tail
is below 180·2^−64 on 0≤1−p<0.5, separately from floating-point roundoff.
Exact uniform parity gives a zero 12 moment; nearby nonzero values are not
snapped to zero. Nonfinite and unrepresentable results are refused.

Checks include direct physical-density quadrature, uniform polynomial
identities, exact old-subspace bytes, symmetry, positive Gram eigenvalues,
immutable arrays and powers-of-two scaling. Stored mpmath 1.3.0 references
use 70/100-digit Duffy angular integration and beta power integrals without
product imports or its zeta series. The reference shares mathematical
definitions and a split-domain identity: it provides partial mathematical
independence, not a separate field simulator. The fixture and compare-only
generator retain provenance and exact numerical hashes.

The registered range has nine exponents from 0.500001 to 1 and lengths
2^−20, 1 and 2^20 metres. Entry comparisons use 1e−12·max(1,|reference|), plus
1e−12 relative checks on selected representable nonzero cross moments.
This does not establish universal relative accuracy, a complete current solver,
fixed-guard accuracy, mesh convergence or another platform.

[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_quadratic.md)
