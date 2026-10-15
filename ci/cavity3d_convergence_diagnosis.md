# Rectangular PEC 111 doublet: signed-mean convergence diagnosis

**Historical candidate analysis:** the source SHAs below identify the earlier
uniform-diagonal core. For the subsequent alternating-mesh candidate, see
[the independent revalidation](cavity3d_alternating_validation.md). The earlier
failure and measurements are preserved; they do not describe the latest core.

For that earlier candidate, the n=4,8,16 cluster-mean order gate **fails**: 1.22837 is
below the fixed 1.8 threshold. These diagnostics neither change that test nor
certify numerical acceptance. No solver or simcase implementation is modified.

## Exact sources and reproduction

The actual-candidate snapshot consists of baseline
`75df651457b8f78540e9050b27c276ab8b07aaf1`, the nonoverlapping changed files from
core `3b850a8d7e303fd45a6b77f85571d45ab7c51114`, simcase
`cd4071a5685fcdf6d21d19c5d382461685c2e501`, validation
`db9367e90518bd92f5f72fbd87fd65b58fcd069c` and reference
`ce74a783e0cf679e9e031360b6bd9d556346a575`. Each source blob was checked against
its Git SHA. This describes a component snapshot, not a single integrated commit.

Python 3.12, NumPy 2.3.5, SciPy 1.17.0 and pytest 9.1.1 were used, with BLAS and
OpenMP limited to one thread. NumPy/SciPy differ from the CI lock's 2.5.4/1.18.1.

From a source checkout containing those implementations and this diagnostic:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ci/cavity3d_convergence_diagnosis.py \
  --meshes 4 6 8 12 16 --quadrature-orders 4 5 --output /tmp/cavity111.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ci/cavity3d_convergence_diagnosis.py \
  --meshes 4 --quadrature-orders 5 6 --output /tmp/cavity111-quadrature.json
```

The extra n=6,12 points are diagnostic only. The unchanged acceptance sequence
is n=4,8,16 and its test remains a failure. The diagnostic's exit code indicates
successful measurement; its JSON explicitly reports `fixed_gate_pass=false`.

## Signed spectral errors

For the (1,0.8,0.6) metre box, let lambda* be the analytic 111 squared wave
number and e_j=lambda_h,j/lambda*-1. The target remains
sigma=1.3 times the analytic fundamental squared wave number; five modes are
requested, including the whole doublet. No target, mesh or tolerance is changed
to turn a failure into a pass.

| n | Lower mode e_- | Upper mode e_+ | Signed mean | RMS eigenvalue error | Maximum principal sine |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4 | -0.02524079 | +0.01758909 | -0.00382585 | 0.02175401 | 0.49427265 |
| 6 | -0.00890694 | +0.00983691 | +0.00046499 | 0.00938345 | 0.33155918 |
| 8 | -0.00435797 | +0.00593389 | +0.00078796 | 0.00520591 | 0.23868157 |
| 12 | -0.00169328 | +0.00276145 | +0.00053408 | 0.00229050 | 0.14708055 |
| 16 | -0.00090306 | +0.00157566 | +0.00033630 | 0.00128417 | 0.10526656 |

Over n=8 to 16, the individual absolute eigenvalue-error orders are 2.27077
and 1.91302, the RMS-error order is 2.01931, and the split-width order is
2.05384. The signed-mean absolute-error order is only 1.22837. The supplementary
n=6 to 8 mean order is negative (-1.83340), even though both individual errors,
the RMS error and the independently measured subspace gap decrease.

This is cancellation, not a missing polarization: the two errors have opposite
signs. Their mean discards their magnitude. The ratio
abs(mean(e))/mean(abs(e)) is 0.04962 at n=6, 0.15312 at n=8 and 0.27135 at n=16.
A small average at one mesh therefore does not imply a proportionately small
individual eigenvalue or field error.

For illustration, fit the two finest signed means to A/n^2+B/n^4. This gives
A=0.09798119 and B=-3.04330988, predicting a sign crossing near n=5.57 and
an n=12 mean of 0.0005336604; the measured n=12 value is 0.0005340835
(0.0792% discrepancy). Fitting two points is not an asymptotic proof. It is
consistent with opposite leading/higher-order contributions dominating on this
finite ladder, and explains why the mean's finite-range rate is sensitive.

## Independent continuum-subspace check

For 111, the exact electric fields have component factors

    (cos(kx*x) sin(ky*y) sin(kz*z),
     sin(kx*x) cos(ky*y) sin(kz*z),
     sin(kx*x) sin(ky*y) cos(kz*z)),

multiplied by an amplitude vector A satisfying k dot A=0. An orthonormal basis
of that two-dimensional amplitude nullspace, multiplied by sqrt(8/volume),
is an exact continuum L2-orthonormal basis. It does not use the computed
eigenvectors to define the reference subspace.

The diagnostic reconstructs FE Whitney fields independently from raw oriented
edge integrals at tetrahedron vertices, then integrates their overlaps B with
the exact basis using a tensor Gauss rule under a Duffy tetrahedron map.
Both exact and FE Gram matrices are checked as reported diagnostics. If both
bases are L2-orthonormal, the singular values of B are cosines of principal
angles. The maximum sine is sqrt(1-sigma_min(B)^2). This is invariant to signs,
polarization rotation and the choice of basis within either doublet.

The measured maximum sine decreases as shown above; its n=8 to 16 order is
1.18104. Individual FE modes' distances to the exact subspace decrease too:
at n=8 they are 0.23638 and 0.16971, and at n=16 0.10513 and 0.08068.
These field errors are much larger than the signed-mean eigenvalue error;
the latter is not a field-accuracy certificate. No new field acceptance
threshold is inferred from these measurements.

The largest order-4 vs order-5 change in the reported principal sine is
1.93e-7 (n=4); the additional order-5 vs order-6 check at n=4 changes it by
4.88e-10. These quadrature effects are negligible relative to the reported
0.1-to-0.5 gaps, and cannot explain the convergence-gate failure.

For each FE mode, an additional curl-distance diagnostic uses integration by
parts, <curl u_h,curl u_exact>=lambda* <u_h,u_exact>, with PEC traces. Its
squared distance to the L2-projected exact field, divided by lambda*, is
lambda_h/lambda* - sum_l abs(B_lj)^2. This denominator is lambda*, not the
norm of the projected field; it is explicitly a diagnostic, not a new gate.

## Discretization versus eigensolver error, and the remaining decision

An independent complete dense generalized eigendecomposition at n=4 finds
exactly 27 gradient modes. Its first five positive eigenvalues agree with
the production projected sparse solve within 4.56e-14 relative. The unchanged
independent residual, gradient, PEC and mass-orthogonality checks also pass.
This localizes the observed spectral-average behavior to the discretized
spectrum, rather than a missing mode or an inaccurate sparse eigensolve in
this checked case. It does not prove all targets or meshes correct.

A fixed finite-ladder mean-order requirement is an empirical acceptance rule,
not a theorem guaranteed by good individual eigenvalue convergence. In
particular, a signed trace error can contain opposite contributions and pass
through zero. A universal >1.8 expectation on n=4,8,16 cannot be justified
from an assumed asymptotic second-order error alone. This does **not** make
the already agreed test pass, and does not establish a universal alternative.

The original failing assertion is retained. Possible future acceptance-design
review should distinguish signed cluster bias from noncancelling RMS/maximum
spectral errors, splitting and continuum-subspace accuracy. Any revised plan
requires an explicit, evidence-backed decision and fresh validation; this
diagnostic does not replace the test, change the solver, or authorize integration.
