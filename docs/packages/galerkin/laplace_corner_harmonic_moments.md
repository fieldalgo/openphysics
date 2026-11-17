# Physical static wedge moments

The private `_laplace_corner_harmonic_moments` module prepares polynomial
projection and plane-current Fourier moments for previously admitted geometry.
It is not a public field solver or a new geometry/material admission route.
It uses the [static wedge basis](laplace_corner_harmonic.md): rho_p and
sqrt(3)*(rho_2p−rho_p), with physical masses1 and0 and first moments
p/(p+1) and sqrt(3)*p/((p+1)*(2*p+1)). No quadrature weights are rescaled.

Positive Jacobi measures integrate each power branch. The zero-mass projection
subtracts a common anchor; smooth bilinear projection uses analytic masses.
Plane zero modes are analytic and preserve total unit/zero charge. Nonzero
Fourier modes use physical quadrature at the explicitly selected order.
Small exponential differences use `expm1` to retain near-plane and thin-height
values. The caller remains responsible for admitted geometry, finite budgets
and separate matrix, field, panel and outer comparisons.

Checks compare low-degree polynomial moments with exact binary-rational
integrals, constant/affine/bilinear kernels, uniform-panel closed Fourier
moments and exact plane charges. Additional distances2^-40 from either plane
and height2^-20 are compared with hyperbolic-sine amplitudes and closed
spherical-Bessel moments, at relative1e-12 with zero absolute allowance.
Invalid numerical mass/nonfinite projection is refused. Existing linear
helpers and field solvers remain unchanged. These private checks alone do not
qualify a complete field, fixed guard, measured accuracy or another platform.

[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_harmonic_moments.md)
