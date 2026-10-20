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
electric conductor on all six walls. It uses a conforming alternating Kuhn mesh (six
tetrahedra per Cartesian cell) and the existing lowest-order Nedelec edge elements. It has no
material, loss, open-boundary, arbitrary-CAD or sweep options.

The fixed cube and rectangular-box convergence gates below pass with the
alternating mesh. Algebraic residuals and continuum discretization error are
checked separately; a small residual alone does not certify mesh accuracy.

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

The mesh starts with `box_mesh` vertices and its six-tetrahedron Kuhn cell
pattern. Within cell `(i,j,k)`, reflect each local coordinate whose cell index is
odd. This alternates the body diagonals without changing vertices, Cartesian
cell counts, tetrahedron counts, or tetrahedron shapes. Shared faces use the same
tangential parities and therefore identical diagonals. Even subdivision counts
restore reflection symmetry across the corresponding box mid-plane. Odd counts
are also conforming, though they need not have that global reflection symmetry.
No eigenvalue, reference answer, target or requested mode count affects the mesh.

This mesh family avoids a single preferred body diagonal throughout the box.
It changes discretization errors rather than correcting computed eigenvalues.
The public `box_mesh` generator itself is unchanged. Consumers must use the
returned mesh and topology, rather than assuming the cavity has that generator's
original connectivity. A rectangular 111 doublet can still split: the rectangular
box's reflection symmetries do not enforce its accidental polarization degeneracy.

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

## Reproducible validation and convergence repair

From the repository root, with the local test dependencies installed:

```bash
python -m pytest -q tests/galerkin/test_cavity_solver.py
python -m pytest -q
```

Tests compare refsol TE/TM enumeration with independent transverse-amplitude
counting, complete dense discrete spectra, the 343-dimensional gradient kernel
in a low-target sparse search, full PEC zeros, SI reassembly and reconstruction,
physical scaling and degenerate subspaces, and injected numerical failures.

The fixed convergence sequence is `n=4,8,16` in every direction, target squared
wave number `1.3 * analytic_fundamental`, comparing complete clusters. With the
alternating mesh, at n=16:

| Box (m) | Cluster multiplicities | Last mean k² error orders | Maximum individual f error |
| --- | --- | --- | --- |
| `(1,1,1)` | `3,2,6` | `2.0880, 1.9627, 2.0639` | `0.1657%` |
| `(1,.8,.6)` | `1,1,1,2` | `1.9393, 2.0296, 1.9988, 1.8929` | `0.1881%` |

All mean errors decrease at every step and the final orders exceed the unchanged
**1.8** gate. The rectangular 111 cluster width contracts at order `2.0103`;
all three cube widths are at roundoff (relative width at most `2.1e-14`).
The rectangular 111 signed mean relative errors are `+0.0066232970`,
`+0.0025322041`, `+0.0006818301`.

The original parallel-diagonal Kuhn mesh failed this exact gate: its rectangular
111 signed mean errors were `-0.0038258485`, `+0.0007879605`, `+0.0003363018`,
giving final order **1.2284**. The negative/positive individual errors converged
at orders `2.2708` and `1.9130`; cancellation in their mean obscured the expected
rate on this fixed sequence. The repair changes the actual mesh family, with no
hidden refinement, spectral correction, tolerance change, skip or xfail. The
original fixed convergence test body is retained unchanged.

Separate diagnostics distinguish selection and eigensolver error from this mesh
error. At n=4 both mesh families agree with the complete dense generalized
spectrum within `4.7e-14` relative and both have exactly 27 gradient modes. Raising
the requested count from 5 to 11 leaves the first five values unchanged within
`6.7e-16` and preserves the 111 mass-normalized eigenspace to roundoff.

An independent volume quadrature compares the 111 field subspace with the exact
standing waves. Their amplitude vectors are perpendicular to `(pi/a,pi/b,pi/c)`
and normalized by `sqrt(8/(a*b*c))`. The comparison uses both singular values of
the continuous L2 overlap, rather than assigning unique TE/TM vectors. At n=8:

| Mesh | Two overlap singular values | Relative subspace projection error |
| --- | --- | --- |
| Parallel diagonals | `0.98605, 0.97110` | `0.20576` |
| Alternating diagonals | `0.98928, 0.98206` | `0.16866` |

At n=4 the alternating values are `0.95618, 0.92750` (parallel:
`0.93536, 0.86931`), confirming both polarizations even on the coarse mesh.
Five-point tensor Gauss quadrature under a tetrahedral Duffy map is checked
against six-point quadrature at absolute tolerance `1e-9`. The projection error
is `sqrt(1 - mean(singular_values**2))`. These checks, raw Maxwell residuals,
mesh conformity/reflection tests and the fixed spectral gates are complementary;
none is substituted for another.
