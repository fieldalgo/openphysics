# Independent validation plan: vacuum PEC rectangular cavities

Scope: a vacuum rectangular box with PEC on all six walls, one modal solve,
lowest-order tetrahedral Nedelec elements. No dielectric loading, losses, open
boundaries, arbitrary CAD, or renderer validation is covered.

This is a validation plan and a reproducible **existing low-level baseline**.
It does not define a new public solver, document schema, or persistence API.
Product acceptance tests must use the separately approved interface and record
the exact implementation commit they grade.

## Analytic oracle and multiplicity

For side lengths a, b, d in metres,

    k² = π²[(m/a)² + (n/b)² + (p/d)²]
    f_Hz = 299792458 sqrt(k²) / (2π).

`refsol.metallic.rect_cavity_resonances` returns k², not Hz.
Its TE index rules are p >= 1 and (m,n) != (0,0); TM requires m,n >= 1,
p >= 0. Independently, the standing-wave amplitudes give one polarization
when exactly two indices are positive and two when all three are positive.
Zero or one positive index gives no physical mode. This is a useful second
enumeration independent of the reference implementation and solver.

The unit cube has complete low clusters k²/π² = 2, 3, 5 with multiplicities
3, 2, 6. The rectangular (1, 0.8, 0.6) case tests the first three simple
modes and the TE111/TM111 pair. A finite index cap is sufficient only when
the smallest possible omitted index has k² above the comparison band:
for an index cap N, π²(N+1)² / max(a,b,d)² is a conservative lower bound.

Compare sorted spectra **with multiplicity**, not only nearest-reference
distances. Cluster count and cumulative count are required. Split numerical
clusters may be assigned using midpoints between distinct analytic clusters,
but must also meet accuracy and convergence gates. A frequency-targeted
shift-invert search does not prove that the lowest N modes were returned.
Requests ending inside an analytic cluster require an explicit partial-cluster
policy; these validation cases request complete clusters.

A degenerate eigenspace permits arbitrary basis rotation and sign/phase.
Individual eigenvectors or TE/TM labels are not stable comparison targets.
Do not generalize an accidental doublet in a box with unequal sides into a
claim that every degeneracy of the cube is accidental.

## Gates fixed before running new acceptance tests

| Quantity | Gate |
|---|---|
| Analytic amplitude enumeration vs refsol | Same count, sorted k² relative error <= 1e-13 |
| k²-to-Hz conversion | Relative error <= 1e-12 against the SI formula above |
| Structured refinement | n = 4, 8, 16 per axis, unchanged box |
| Cluster mean k² error | Decreases at each step; last observed order > 1.8 |
| Relative cluster width | Last observed order > 1.8, or finest width < 1e-10 |
| Individual frequency accuracy | Every compared mode within 1% at n = 16 |
| Free-DOF eigenpair residual | Every mode rho <= 1e-9 |
| Mass orthogonality | max abs(U* M U - I) <= 1e-8 after mass normalization |
| Gradient coupling | Each normalized interior-node gradient overlap <= 1e-9 |
| Small-mesh nullspace | Exactly (n-1)^3 zero modes for n = 2, 3, 4 |
| Discrete curl of gradients | Relative matrix max norm <= 1e-11 |
| Boundary raw edge coefficients | Relative max <= 1e-12 |
| Independent wall tangential trace | Relative max <= 1e-10 |
| Equivalent m/um/nm inputs | Frequency and dimensionless k² relative difference <= 1e-9 |
| Actual geometric scaling s = 1e-6, 1, 1e3 | f*s invariant within 1e-9 |
| Degenerate subspace under equivalent models | Normalized mass-overlap singular values >= 1 - 1e-7 |
| Saved primitive arrays/raw coefficients | dtype, shape, value exactly preserved |
| Reconstructed centroid field | Relative difference <= 1e-12; residual and PEC gates pass again |

A failed gate remains a failure. Do not widen a tolerance, reduce multiplicity,
drop a difficult cluster, or change refinement meshes after inspecting a failure.

For K_ff u = lambda M_ff u, use

    rho = ||K_ff u - lambda M_ff u||₂ /
          (||K_ff u||₂ + |lambda| ||M_ff u||₂).

The rows eliminated by PEC can contain reaction residuals. They must not be
included in this eigenpair residual test. Construct the oriented node-to-edge
incidence C independently from low-node to high-node edge pairs. Restrict
its columns to interior nodes and rows to free edges. For each column c_j,
check abs(c_j* M u) / sqrt((c_j* M c_j)(u* M u)) <= 1e-9.
A zero denominator is an error, not a passing value.

On small systems, independently diagonalize the full constrained generalized
pencil. Count the gradient kernel using a dimensionless eigenvalue scale and
verify the integer nullity and K C identity. Positive values alone do not
establish completeness or the absence of spurious nonzero modes.

## PEC and raw-field reconstruction

Independently enumerate the faces belonging to one tetrahedron and their edge
pairs. Both endpoints being boundary nodes is insufficient to identify a
boundary edge in 3D; a diagonal with boundary endpoints can be interior.

For a tetrahedron and local barycentric coordinates lambda_i, reconstruct

    E = sum_edges u_edge sign_edge
        (lambda_i grad(lambda_j) - lambda_j grad(lambda_i)).

Evaluate at each boundary triangle's vertices and centroid in its adjacent
tetrahedron, using independently computed barycentric gradients and normals.
Scale max ||n cross E|| by the maximum magnitude over all tetrahedron vertices.
This is a polynomial trace check for the lowest-order element, rather than
an inference from volume-centroid samples. For raw boundary DOFs, divide by
max absolute full edge coefficient; all-zero modes are invalid.

Restoration must preserve or deterministically reconstruct nodes, tetrahedra,
global edge direction/order, local orientation, full edge coefficients,
eigenvalues, and unit metadata. Load arrays with allow_pickle=False.
Reassemble matrices and check residuals, PEC, and reevaluated fields after
restoration. A saved picture or centroid array cannot replace raw coefficients.

For actual geometric scaling, K scales as 1/s, M as s, and k² as 1/s²
when the same edge-integral convention is used. Normalize a mapped pair of
bases in a common mass metric before comparing their overlap singular values.
Exact array equality is required for one saved/restored basis; it is not
required for separate eigensolver calls inside a degenerate subspace.

## Reproduce the existing baseline

Run from the repository root. These commands use existing packages and NumPy/
SciPy; no additional dependency or solver code is introduced. The source baseline
is commit `75df651457b8f78540e9050b27c276ab8b07aaf1`.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python - <<'PY'
import itertools
import sys
from pathlib import Path
import numpy as np

root = Path.cwd()
for package in (root / "packages").iterdir():
    if (package / "pyproject.toml").exists():
        sys.path.insert(0, str(package))
sys.path.insert(0, str(root / "packages/galerkin/examples"))
import cavity_modes as example
from refsol.metallic import rect_cavity_resonances

example.check_mesh()
example.check_whitney_identities()
example.check_kernel_dimension(sizes=((2, 2, 2), (3, 3, 3), (4, 4, 4)))
for sides in ((1, 1, 1), (1, .8, .6)):
    independent = []
    for indices in itertools.product(range(5), repeat=3):
        positive = sum(i > 0 for i in indices)
        multiplicity = {0: 0, 1: 0, 2: 1, 3: 2}[positive]
        k2 = sum((np.pi * i / a)**2 for i, a in zip(indices, sides))
        independent.extend([k2] * multiplicity)
    expected = [k2 for k2, _ in rect_cavity_resonances(*sides, n_max=4)]
    assert len(independent) == len(expected) == 176
    assert np.allclose(sorted(independent), sorted(expected), rtol=1e-13, atol=0)
    if sides == (1, 1, 1):
        q = np.asarray(independent) / np.pi**2
        for value, count in ((2, 3), (3, 2), (5, 6)):
            assert np.count_nonzero(np.isclose(q, value, rtol=1e-13, atol=0)) == count
print("Existing mesh/identity/kernel checks and independent oracle: PASS")
PY
```

For the convergence baseline, set the existing example's A_BOX/B_BOX/C_BOX
in memory to each box above. For each n in (4,8,16), call
`solve_cavity(n,n,n,num_modes=20,sigma=1.3*analytic_lowest_k2)`.
Group the returned sorted eigenvalues into the analytic multiplicities above
(first 11 cube modes, first 5 rectangular modes), and compute all gates in
the table rather than comparing only their averages. Reassemble full K/M
with `assemble_curlcurl_3d` and `assemble_edge_mass_3d`, restrict to the
returned free edges, and calculate each mode's residual. This is an exploratory
check of the existing example, not acceptance of a new lowest-N public API.

## Current evidence and limits

The existing mesh checks passed on (1,0.8,0.6): volume 0.48, 132 expected
boundary faces, Euler characteristic 1, positive volumes, and refinement-
invariant dihedral angles. Relative Whitney identity errors were at most
6.8e-16. Kernel counts were exactly 1, 8, 27. Both independent analytic
enumerations matched all 176 modes at index cap 4; cube counts were 3/2/6.

These initial direct checks preceded API validation and pytest installation.
The subsequent targeted results below describe the current evidence and failures;
a full suite pass is not claimed.


## Approved technical contract and executable tests

The callable is
`galerkin.solve_cavity_box(lengths_m, subdivisions, *, num_modes=6, target_frequency_hz)`.
Lengths and mesh coordinates are SI metres; frequencies are Hz. Selection is
`near_target` in squared frequency and returns exactly the requested count on
success. It can split a degenerate cluster. Results and saved metadata declare
`cluster_completeness="not_certified"` and
`mode_count_policy="exact_count_may_split_cluster"`.
Saved data declare `field_layout="cavity3d-edge-v1"` and must load without pickle.
With `save_fields=false`, raw edge/centroid arrays are omitted; spectra and
search/normalization metadata remain available.

Public solver rejection limits are residual 1e-8 and mass orthogonality 1e-7.
The stricter independent benchmark limits in the table remain 1e-9 and 1e-8.
The normalized coefficients obey Q* M_SI Q = I; edge coefficients have arbitrary
normalization units m^-1/2 and centroid fields m^-3/2, rather than calibrated V/m.

Run the new independent tests against a source checkout containing the approved
API and simcase implementation. Select the root configuration explicitly when
selecting package test files, to avoid package-local pytest discovery bypassing
the root conftest path setup:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q \
  packages/galerkin/tests/test_cavity3d_validation.py \
  packages/simcase/tests/test_cavity3d_persistence_validation.py
```

The convergence fixture uses the original fixed shift sigma = 1.3 times the
analytic fundamental k², expressed as target_frequency_hz. This stays away from
the gradient kernel while retaining the complete reference clusters under test.
It does not change the numerical gates or guarantee completeness for other targets.
The raw restoration test reconstructs Mesh3D/EdgeSpace3D from saved primitive
arrays, without requiring or inventing a product load API.

## Measured candidate results (2026-10-15)

Source base: `75df651457b8f78540e9050b27c276ab8b07aaf1`. The temporary test
snapshot used exact changed blobs from core commit
`163239a5ae03c05a1b8f49c78c2a1277c42ca3e6`, simcase commit
`1837b46b4f533ca97279e29004ecba39b48b8044` and reference commit
`ce74a783e0cf679e9e031360b6bd9d556346a575`. This was a component-source
composition, not a single integrated Git commit or a built-wheel validation.
Python 3.12, NumPy 2.3.5, SciPy 1.17.0, pytest 9.1.1 were used; the numerical
library versions differ from the CI lock. No runtime dependency declaration changed.

| Independent check | Observed result |
|---|---|
| Amplitude/refsol oracle and dense generalized nullity | Passed |
| Raw eigenpair residual, mass orthogonality, gradient overlap, independent wall traces | Passed on the small cube and unequal-sided box fixtures |
| Actual geometric scaling and degenerate subspace | Passed |
| m/um/nm document representations and translated SI coordinates | Passed |
| Saved raw array dtype/shape/value and restored residual/PEC/field | Passed |
| Core required cluster metadata | Failed: cluster_completeness attribute absent |
| Saved contract metadata | Failed: cluster_completeness value differs from contract; required layout/count-policy keys also absent on source inspection |
| Cube n=4,8,16 complete-cluster convergence | Passed; mean orders 1.9184, 1.9568, 1.9836 |
| Unequal box n=4,8,16 complete-cluster convergence | Failed: 111 cluster mean order 1.22837, below 1.8 |

The failed unequal-box cluster's mean k² relative errors were 0.0038258485,
0.0007879605 and 0.0003363018. Its width converged at order 2.05384, and its
finest individual frequency accuracy was good; neither fact overrides the failed
mean-order gate. The cube's finest maximum frequency error was 0.32417%; the
unequal box's was 0.18691%. No tolerance or refinement ladder was relaxed.

The finite-cutoff reference handoff's 17 dedicated tests were rerun on these
sources after code review; this does not replace the independent amplitude/count
checks above. Full source regression, CLI acceptance, build/wheel tests, and
remote CI remain unrun by this validation task. Known failures require review
before product acceptance can be claimed.


## Actual implementation candidate rerun (2026-10-15)

The original handoff results above remain historical. A fresh exact-file snapshot
used core `3b850a8d7e303fd45a6b77f85571d45ab7c51114`, simcase
`cd4071a5685fcdf6d21d19c5d382461685c2e501`, validation
`db9367e90518bd92f5f72fbd87fd65b58fcd069c` and reference
`ce74a783e0cf679e9e031360b6bd9d556346a575`, against the same base.
The unchanged independent tests plus the 17 reference tests gave **26 passed,
1 failed**, no skips. The one failure is still the rectangular 111 mean-order
gate. The earlier three metadata failures are resolved on these actual sources.

The NPZ metadata assertions after summary validation now execute and pass:
cluster completeness, exact-count policy, layout identifier, coordinate/frequency
units and normalization agree between JSON and NPZ loaded without pickle.
The raw-array restoration and save_fields=false checks also pass.

The signed-average and continuum-subspace diagnosis is reproduced by
[cavity3d_convergence_diagnosis.py](cavity3d_convergence_diagnosis.py) and explained
in [the diagnosis](cavity3d_convergence_diagnosis.md). It retains the failure and
identifies the finite-mesh signed cancellation; it does not introduce an automatic
replacement acceptance rule. Tool/environment differences from CI are unchanged.
