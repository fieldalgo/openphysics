# Vacuum rectangular PEC cavity solver

```python
from galerkin import solve_cavity_box

result = solve_cavity_box(
    lengths_m=(1.0, 1.0, 1.0),
    subdivisions=(8, 8, 8),
    num_modes=6,
    target_frequency_hz=210e6,
)
print(result.frequencies_hz)
```

This API solves a vacuum rectangular box starting at `(0, 0, 0)`, with a perfect
electric conductor on all six walls. It uses the existing Kuhn box mesh (six
tetrahedra per Cartesian cell) and lowest-order Nedelec edge elements. It has no
material, loss, open-boundary, arbitrary-CAD or sweep options.

**Validation status:** the fixed rectangular-box cluster-mean convergence gate
below currently fails. Passing algebraic residual checks does not certify mesh
accuracy. The solver is not yet accepted against all declared numerical gates.

## Arguments and search

`solve_cavity_box(lengths_m, subdivisions, *, num_modes=6, target_frequency_hz)`
returns a `CavityResult`.

- `lengths_m`: three finite, strictly positive real lengths in metres
  (Python or NumPy numeric scalars).
- `subdivisions`: three strictly positive integers.
- `num_modes`: strictly positive integer, counting individual eigenvectors and
  retaining repeated eigenvalues. Booleans are not accepted as numeric inputs.
- `target_frequency_hz`: required finite, strictly positive frequency in Hz.

Search is `near_target`. Among a finite set of computed physical candidates,
select the requested number nearest the target in **squared** wave number
(equivalently squared frequency). Return the selected modes in ascending frequency
order. This does not certify a complete lowest spectrum, all modes in an interval,
or every partner of a degenerate cluster. In particular, the smallest returned
frequency need not be the fundamental frequency.

The requested count is exact on success and may cut a cluster. Every result states
`cluster_completeness="not_certified"` and
`mode_count_policy="exact_count_may_split_cluster"`, even when a particular
validation example includes complete reference clusters. These strings describe
search limitations, not a diagnosis of whether that result has missing partners.

## Arrays, orientation and units

Let K be the requested mode count, E the total edge count, and T the tetrahedron
count. All modes are real standing waves.

| Attribute | Shape / meaning | Units |
| --- | --- | --- |
| `mesh` | `Mesh3D`, nodes and tetrahedral connectivity | nodes in m |
| `space` | `EdgeSpace3D` on that same mesh | oriented topology |
| `frequencies_hz` | `(K,)`, positive and ascending | Hz |
| `eigenvalues_m2` | `(K,)`, squared wave numbers | m^-2 |
| `edge_coefficients` | `(E,K)`, full vectors including exact PEC zeros | m^-1/2 |
| `electric_field` | `(K,T,3)`, vectors at tetrahedron centroids | m^-3/2 |
| `relative_residuals` | `(K,)`, free-edge equations | dimensionless |
| `pec_edge_ids` | indices into the full edge ordering | indices |
| `requested_modes` | K | count |
| `target_frequency_hz` | supplied target | Hz |
| `search` | `"near_target"` | metadata |

The two cluster-policy attributes above are also carried by `CavityResult`.
The exact vacuum speed of light is `c0 = 299792458 m/s`, and
`f = c0 * sqrt(eigenvalues_m2) / (2*pi)`.

Each global edge points from its lower node ID to its higher node ID.
`space.edges`, `space.tet_edges` and `space.signs` describe the ordering and the
local-to-global orientations. Boundary edges are those contained in boundary
faces. An interior edge whose endpoints both lie on the boundary remains free.

With Q the full coefficient array and M_SI the vacuum edge mass matrix on the
returned SI mesh, `Q.T @ M_SI @ Q = I` within the tolerance below. These coefficients
are line integrals under an arbitrary mathematical normalization; their units
are **not volts**, and the reconstructed field is **not calibrated V/m or power**.
The largest absolute edge coefficient of each mode is positive. Degenerate
subspaces can rotate their basis between solves; individual polarization labels,
vector signs and eigenvectors are not unique physical identifiers.

Internally, coordinates are divided by `L=max(lengths_m)`. Returned coefficients
are `q_normalized/sqrt(L)`, eigenvalues `k2_normalized/L**2`, and centroid fields
`E_normalized/L**1.5`. A uniform physical enlargement by s divides frequency by s.
Reconstruct each centroid field with
`eval_edge_field_3d(result.space, result.edge_coefficients[:, j])`.

Serialization belongs to the caller. To preserve the technical field contract,
store SI coordinates, tetrahedra, edge ordering/orientation, PEC indices and full
raw coefficients with the declared normalization and search metadata. The 3D
layout identifier is `cavity3d-edge-v1`; NPZ readers must work with
`allow_pickle=False`. When fields are disabled, omit raw edge and centroid arrays
while retaining spectral results and their normalization/search metadata.

## Numerical method and failure policy

The free-edge generalized problem is `S q = k2 M q`. For this simply connected
PEC box, the gradient nullspace has dimension `(nx-1)*(ny-1)*(nz-1)`. Let C map
interior nodal potentials (zero on the boundary) to free-edge circulations,
`H=C.T @ M @ C`, and `P=I-C H^-1 C.T M`. H is positive definite.

For at most 256 free edges, compute the full dense generalized spectrum and check
its kernel dimension. Otherwise use symmetric projected shift-invert
`OPinv=P (S-sigma*M)^-1 P.T`, with `sigma=(2*pi*f_target*L/c0)**2`.
Then `OPinv M` annihilates gradients and preserves the physical transformed
eigenvalues `1/(k2-sigma)`. No penalty changes the Maxwell eigenproblem. Direct
sparse factorizations are used for H and the shifted matrix.

For N requested modes, the sparse candidate budget is
`min(max(2*N, N+8), physical_dofs, free_edges-1)`, with
`physical_dofs=free_edges-interior_nodes`. ARPACK uses
`ncv=min(free_edges,max(6*candidates,90))`, tolerance `1e-10`, at most 50000
iterations, and a seeded (`0`) random initial vector. A single bounded search is
performed; repeated eigenvalues are never deduplicated.

The kernel screen is `1e-8` times the analytic box fundamental k² in normalized
coordinates. This scale is independent of target and supplies no returned
eigenvalues. Selected vectors must satisfy:

- free-edge relative residual
  `||S q-lambda M q|| / (||S q||+abs(lambda)*||M q||) <= 1e-8`;
- maximum entrywise error in `Q.T M Q-I <= 1e-7`;
- M-norm of the gradient projection `<= 1e-9`.

These residuals exclude constrained boundary rows, which can carry wall reactions.
They measure the discrete equations, not error relative to the continuum answer.

Invalid arguments or unrepresentable internal scales raise `ValueError`.
Insufficient physical degrees of freedom/candidates, significant negative
eigenvalues, non-finite output, failed factorization, nonconvergence, or failed
quality checks raise `RuntimeError` with no partial result. A target at a discrete
eigenvalue can make the shifted factorization singular; choose a nearby target.
No silent count reduction, zero padding or tolerance relaxation is performed.

## Reproducible validation and current limitation

From the repository root, with the local test dependencies installed:

```bash
python -m pytest -c pyproject.toml -q packages/galerkin/tests/test_cavity_solver.py
python -m pytest -q
```

The explicit root configuration on the focused command prevents a nested package
configuration from selecting an editable install in a different checkout.
Tests compare refsol TE/TM enumeration with independent transverse-amplitude
counting, complete dense discrete spectra, the 343-dimensional gradient kernel
in a low-target sparse search, full PEC zeros, SI reassembly and reconstruction,
physical scaling and degenerate subspaces, and injected numerical failures.

The fixed convergence sequence is `n=4,8,16` in every direction, target squared
wave number `1.3 * analytic_fundamental`, comparing complete clusters. At n=16:

| Box (m) | Cluster multiplicities | Last mean k² error orders | Maximum individual f error |
| --- | --- | --- | --- |
| `(1,1,1)` | `3,2,6` | `1.9184, 1.9568, 1.9836` | `0.3242%` |
| `(1,.8,.6)` | `1,1,1,2` | `1.9865, 2.0441, 1.9357, 1.2284` | `0.1869%` |

The rectangular 111 doublet fails the fixed final cluster-mean order **>1.8**
gate. Its signed relative mean errors are `-0.0038258485`, `+0.0007879605`,
`+0.0003363018`. The sign change and cancellation in the mean merit investigation;
small individual frequency errors or residuals do not replace this failed gate.
The test remains a failure, without skip/xfail or changed meshes/tolerances.
The rectangular cluster width contracts at order `2.0538`; the cube cluster
widths also pass their fixed checks (an unsplit doublet is at roundoff).

For diagnosis, the n=4 projected sparse eigenvalues agree with the complete
dense generalized spectrum to `4.7e-14` relative; its nullity is exactly 27.
The two individual rectangular 111 eigenvalue errors contract at orders
`2.2708` and `1.9130` over n=8 to n=16, approaching the exact value from opposite
sides. This isolates the observed failure to the cluster-mean discretization
behavior on this mesh sequence, rather than a missing mode or a changed projected
eigenproblem. These diagnostics do not turn the fixed mean-order gate into a pass.
