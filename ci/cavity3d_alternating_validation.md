# Independent validation of the alternating Kuhn cavity mesh

The new cavity implementation passes the **unchanged 27 independent/reference
tests**, with no failures or skips. The original n=4,8,16 mean-error order
threshold remains >1.8. The rectangular 111 doublet's independently measured
final mean-error order is **1.89290945**. No test, tolerance, cluster count or
refinement sequence was relaxed.

## Exact source and environment

| Component | Commit |
| --- | --- |
| Base | `75df651457b8f78540e9050b27c276ab8b07aaf1` |
| Core | `a660233cc224ccf9b7f8c121b4dc0ded9271bb55` |
| simcase | `1747aaffc6d1b9b0adec53c1b2166864a472ec6b` |
| Independent validation, including reference helper | `076a25df74e6581b933577bc0ceebb9d0992cf82` |

The [manifest](cavity3d_alternating_manifest.json) records every one of the 25
nonoverlapping changed source paths and blob SHAs, plus the additional mesh-audit
test's blob SHA. Each base and changed blob was verified. This is an exact
component source composition, not a single integrated commit. No previous
core/simcase handoff source is used. The analytic helper is already included
in the validation component.

Environment: Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, pytest 9.1.1, BLAS/OpenMP
one thread. The numerical libraries differ from CI's NumPy 2.5.4/SciPy 1.18.1.

## Unchanged acceptance and independent mesh checks

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q \
  packages/galerkin/tests/test_cavity3d_validation.py \
  packages/simcase/tests/test_cavity3d_persistence_validation.py \
  packages/galerkin-refsol/tests/test_cavity_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q \
  packages/galerkin/tests/test_cavity3d_mesh_validation.py
```

The first command gave **27 passed in 30.79s**, including analytic multiplicity,
complete reference clusters, free-DOF residuals, mass orthogonality, gradient
exclusion, independent wall traces, physical scaling, degenerate subspaces,
m/um/nm representations, translated SI coordinates, exact raw-array restoration
and restored physics, JSON/NPZ metadata and save_fields=false. NPZ data and
metadata are read with allow_pickle=False. The 17 reference tests are included
in this count, not added again.

The second command gave **3 passed, 9 subtests passed in 0.40s**. These new tests
inspect meshes returned by the public solve API at subdivisions (2,2,2), (3,3,3)
and (4,3,2). They independently verify:

- Original grid node count and coordinates, exactly six tetrahedra per cell,
  positive equal volumes, and the correct total volume.
- A convex separating-axis test for all 15 tetrahedron pairs in each cell:
  interiors are disjoint. Each tetrahedron stays inside its assigned cell.
  Six such disjoint tetrahedra have exactly the cell volume.
- Shared-face incidence of one or two, opposite orientation of interior faces,
  connected tetrahedron adjacency, and no spurious interior boundary faces.
- Correct triangulated area counts on each of the six physical walls and
  surface Euler characteristic two.
- A full dense generalized eigenproblem on each actual returned topology:
  nullity prod(subdivisions-1), no significant negative eigenvalues, and
  independent node-edge incidence satisfying K C to relative 1e-11.

The geometric checks do not reproduce the parity-reflection mesh recipe.
They cover even, odd and mixed counts and local parity-neighbor configurations.
They are bounded tests of this box mesher, not a certificate for arbitrary meshes
or CAD. Existing generic box_mesh is not substituted for the returned cavity mesh.

## Continuum eigenspace and fixed convergence

The existing independent diagnostic reconstructs Whitney fields from raw edge
integrals and integrates overlap with both exact continuum 111 polarizations.
The exact reference uses k dot A=0 and L2 normalization sqrt(8/volume).
Singular values of the overlap yield basis-independent principal angles.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ci/cavity3d_convergence_diagnosis.py \
  --meshes 4 8 16 --quadrature-orders 4 5 --output /tmp/alternating111.json
```

| n | Lower signed relative k² error | Upper signed relative k² error | Signed mean | Maximum principal sine |
| --- | ---: | ---: | ---: | ---: |
| 4 | -0.01309442 | +0.02634101 | +0.00662330 | 0.37382373 |
| 8 | -0.00223671 | +0.00730112 | +0.00253220 | 0.18858890 |
| 16 | -0.00050188 | +0.00186554 | +0.00068183 | 0.09460838 |

The final mean-error order is 1.89290945; individual mode orders are 2.15597
and 1.96853; RMS order is 1.98283. The maximum-principal-sine order is 0.99520,
consistent with the measured decrease toward the exact continuum subspace.
No new field-accuracy acceptance threshold is inferred from these values.
The largest reported free-DOF residual at n=16 is 2.37e-13.

Order-4 vs order-5 quadrature changes the maximum principal sine by at most
2.80e-7 (n=4), and 3.43e-10 at n=16, much smaller than the measured field gaps.
These measurements check field subspaces rather than asserting that individual
TE/TM labels or signs must match across solves.

## History and limits

The [earlier cancellation diagnosis](cavity3d_convergence_diagnosis.md) remains
valid for its explicitly recorded earlier core candidate. Its failed 1.22837
mean-order result is not reclassified. The current pass follows a solver-owned
cavity mesh change under the same numerical acceptance rule.

This task changed only validation tests and documents. It found no independent
mesh or physics defect in the checked cases. Full source regression, CLI,
build/wheel checks, remote CI and a final integrated-commit check were not run
by this independent task in this round. Reports from other tasks are not counted
as these independent results. Product integration remains a separate step.
