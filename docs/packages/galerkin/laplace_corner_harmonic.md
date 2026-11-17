# Static wedge current self integrals

[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_harmonic.md)

`galerkin.laplace_corner_harmonic` provides two explicit mathematical primitives
for square-integrable current at a convex conductor corner. It does not select
or change a field solver's basis.

For length `h` in metres, `u=s/h`, and exponent `0.5 < p <= 1`, define
`rho_a(s) = a/h * u^(a-1)`, `phi0 = rho_p`, and
`phi1 = sqrt(3) * (rho_(2p) - rho_p)`. Their integrated masses are `[1, 0]`.
The powers follow the first two static wedge radial branches. Here “harmonic”
describes a Laplace wedge expansion, not a temporal frequency harmonic.
At `p=1`, the modes are the uniform and zero-mean linear densities.

- `power_panel_harmonic_gram(h, p)` returns the immutable symmetric 2×2
  matrix `integral phi_i(s) phi_j(s) ds`, in inverse metres.
- `power_panel_harmonic_self_log(h, p)` returns the immutable symmetric 2×2
  integral of `phi_i(s) phi_j(t) log(|s-t| / 1 metre)`, dimensionless.

Rows and columns follow `phi0, phi1`. Length scaling multiplies the current
Gram by the inverse scale; only self-log entry `00` gains the log of that
scale. All modes use their physical normalization. Invalid real scalar
inputs and unrepresentable current matrices are refused; small nonzero
cross terms are not clipped.

## Stable self moments

Let `delta=1-p` and
`f=sum(k>=1) (2^k-1)*zeta(k+1,2)*delta^k`. The cross term is `f/sqrt(3)`
and entry `11` is `f-3/(4*p)`. The implementation sums 64 positive terms.
Since each coefficient is at most `3/2`, the remaining scalar series is
bounded by `1.5*delta^65/(1-delta) < 8.14e-20` on the admitted interval.
This is a series-truncation bound, not an overall floating-point or field
accuracy guarantee. The scalar `00` moment retains the existing closed form.

## Validation and limits

Exact rational density-product integrals cover 72 binary64 exponents, including
values immediately above `0.5` and below `1`. Tests check physical scaling,
positive current energy, exact uniform modes, immutable storage and numerical
refusals. Twelve stored self-log references use separately evaluated 60/80-digit
mpmath angular quadrature after a Duffy split. The reference shares the radial
mathematical decomposition, but does not evaluate the product series, digamma
or zeta functions. Nonzero entries are compared with strict relative `1e-12`;
uniform cross moments are checked as analytic zeros. Provenance includes the
exact reference version, license, inputs, generator and comparison-only replay.

These are self integrals only. Interaction blocks, assembled fields, fixed
internal guards, arbitrary dielectric interfaces, loss validity and complete
2D coverage require separate validation. No physical measurement or other
execution-platform qualification follows from this primitive.

See [corner panel primitives](laplace_boundary.md) for the existing
constant and linear density families and their separate contracts.

See the separate [harmonic interaction contracts](laplace_corner_harmonic_interactions.md) for explicit far, shared-origin, separated and mixed-source blocks.

[Private physical moments](laplace_corner_harmonic_moments.md) retain the same masses through polynomial and plane Fourier projection; they do not expose a field solver.
