# Three-mode far logarithmic interactions

`power_panel_quadratic_far_log` from `galerkin.laplace_corner_quadratic_far`
adds far interactions for the [three radial self modes](laplace_corner_quadratic.md):
rho_p, sqrt(3)*(rho_2p-rho_p), sqrt(5)*(2rho_3p-3rho_2p+rho_p),
where rho_a(s)=a/h*(s/h)^(a-1). Their physical masses are [1,0,0].

```python
from galerkin.laplace_corner_quadratic_far import power_panel_quadratic_far_log
result = power_panel_quadratic_far_log(
    [1., 0.], [.3, .4], [8., 2.], .6, .875, quadrature_order=32)
assert result.mean_log_distance.shape == (3, 3)
```

The first segment starts at zero; the second starts at `offset`. All three
vectors are planar metres. Both exponents must lie in (0.5,1], the length
ratio must not exceed 64, and the offset norm must be at least four times
the sum of the segment lengths. Geometry is normalized internally without
changing the physical measure. Results integrate log(|x-y| / 1 metre) and
are dimensionless, immutable 3x3 arrays ordered by the three modes. Scaling
all lengths by lambda adds log(lambda) to entry00 only.

Explicit n/2n physical Jacobi rules support n=4..64. No weight normalization
or automatic retry is performed. Physical mass residuals must not exceed
1e-12; every coarse/fine entry must agree within1e-12*max(1,abs(fine)). This
normalized primitive bound is not relative accuracy for tiny entries or a
field-error bound. Both upper2x2 blocks preserve the existing harmonic
interaction exactly. New zero-mass entries use log1p centering.

Eight registered reference arrays use an independent100term complex Taylor
expansion with analytic density moments at70/100decimal digits. With
rho=(|first|+|second|)/|offset|<=1/4, the omitted scalar contribution is bounded
by5*rho^101/(101*(1-rho)); numerical roundoff is separate. The generator
loads no product modules and only compares with stored values. It preserves
fixture bytes and removes temporary output. References, exact old subspace,
exchange transpose, reflection, rotation and physical scale are checked.
Low-order rules converged for the registered far cases; rejection/no-retry is
checked by explicit fault injection, not presented as an observed physical
quadrature failure. Physical-weight corruption is also rejected.

This primitive does not add separated-near, touching or uniform-mixed
interactions, matrix assembly, a field solution, fixed-ground qualification
or another platform. Independent field and convergence checks remain needed
before a consumer can use a complete higher-order method.

[한국어](../../locales/ko/pages/packages/galerkin/laplace_corner_quadratic_far.md)
