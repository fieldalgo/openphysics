# Opt-in subspace tracking for vector wavelength sweeps

**English** | [한국어](locales/ko/pages/vector_subspace_tracking.md)

The default vector sweep tracker (`electric-l2-assignment-v1`, see the
[overview](overview.md#tracked-vector-wavelength-sweeps)) follows individual
modes and rejects near-degenerate partners such as the two HE11 polarizations of
a circular fiber. `electric-l2-subspace-v1` is an explicit opt-in that tracks the
**span** of an isolated cluster of nearby modes instead. It is available through
Python, the CLI and Studio.

```bash
python -m simcase example vector_fiber_subspace_sweep > fiber_pair.json
python -m simcase run fiber_pair.json -o fiber_pair_results
```

```json
"study": {"type": "sweep", "parameter": "physics.em1.wavelength",
          "values": [1.5, 1.525, 1.55, 1.575, 1.6],
          "tracking": {"method": "electric-l2-subspace-v1",
                       "cluster_span_max": 1e-4, "external_gap_min": 1e-3}}
```

The sweep rules of the default tracker still apply: one vector physics entry,
at least three finite positive strictly monotone wavelengths, a fixed mesh and
a conservative `n_cladding` over the whole interval.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `method` | `electric-l2-assignment-v1` | `electric-l2-subspace-v1` selects this tracker |
| `cluster_span_max` | required | Largest absolute n_eff span of one cluster; neighbours closer than this are joined |
| `external_gap_min` | required | Smallest absolute n_eff gap to every neighbouring candidate; must exceed `cluster_span_max` |
| `search_modes` | `max(2*num_modes, num_modes+4)` | Guided candidate budget; integer greater than `num_modes` |
| `min_overlap` | `0.8` | Minimum of the **smallest** squared principal value of each cluster |
| `min_margin` | `0.1` | Minimum loss of the best alternative complete cluster assignment |

The two n_eff thresholds have no default because no value is right for every
guide, mesh and interval. `degeneracy_tolerance` belongs to the default method
and is rejected together with this one.

## What is tracked

At every wavelength the guided candidates, in descending n_eff, are joined into
clusters wherever adjacent candidates are at most `cluster_span_max` apart.
`num_modes` counts **vectors**: the first `num_modes` candidates must consist of
complete clusters. A cluster member is never selected alone.

A selected cluster is accepted only if:

- its span is at most `cluster_span_max` (a chain of near neighbours wider than
  that is refused rather than split or merged);
- its gap to each neighbouring candidate is greater than `external_gap_min`;
- a **lower guard** candidate is observed below it. Without one the search
  boundary is unresolved and the sweep fails, even when the candidate budget was
  not exhausted. For the example fiber this means the pair must be followed by
  the observed TE01/TM01/HE21 family; a fundamental-only interval is refused.

Each cluster's raw fields `U` are whitened in the electric L2 metric of the
fixed document mesh, `W = diag(M_edge, M_node)`: with `G = U^H W U`, the frame
`Q = U G^(-1/2)` satisfies `Q^H W Q = I`. A rank-deficient or ill-conditioned
Gram matrix (condition number above 1e6) fails; there is no pseudoinverse
(see [Numerical guards](#numerical-guards)).

Against the previous frame `P`, the cross Gram `P^H W Q = L diag(sigma) V^H`
gives cosines of the principal angles. Equal-rank clusters are matched by a
global one-to-one assignment maximizing the mean of `sigma^2` per cluster.
A match must keep its smallest `sigma^2` at least `min_overlap`, so one lost
direction fails even when the mean is high. For every match the margin is the
score lost by the best complete assignment that excludes it (`null` when none
exists). A cluster that loses or gains a member, merges with a neighbour or
splits fails with the wavelength, cluster and reason; a successful partial
sweep is never returned.

The frame is aligned to the previous one by the closest unitary rotation
`R = V L^H`, so `P^H W (Q R)` is Hermitian positive semidefinite. The seed
orientation is arbitrary. For a single-member cluster the score equals the
default tracker's squared normalized overlap and `R` is its phase factor.

## Results

`run` returns `SubspaceSweepResult`. Three different objects are kept apart:

| Object | Access | Meaning |
|---|---|---|
| Raw eigenpairs | `neff`, `vector_fields` | Solver eigenfields with the usual max-centroid normalization; columns in seed cluster order, members by descending n_eff **at each point**. Member columns are not branch identities. |
| Clusters | `cluster_ids`, `cluster_ranks`, `cluster_offsets` | Constant ranks and column ranges |
| Transport frames | `frame_transforms`, `frame_fields(i)` | Block-diagonal `T` with `frame = raw @ T`; electric-L2-orthonormal in document length coordinates. **Not eigenmodes.** |

Cluster quantities:

- `cluster_mean_index()`: mean raw n_eff per cluster, shape (points, clusters).
- `cluster_mean_group_index()`: `n_bar - lambda * d(n_bar)/d(lambda)` with the
  same second-order differences as the default tracker. This is the derivative
  of the cluster mean index; it is not the group index of any frame column and
  not a power-weighted average. For rank one it is the ordinary group index
  (`singleton_group_index()`).
- `group_index()` returns `None`: there is no per-column group index.
- `subspace_density(i, cluster_id)`: `sum_j |F_j|^2` over the frame at triangle
  centroids, divided by its maximum. It is invariant under unitary changes of
  frame. It is not electromagnetic energy density or a polarized mode.

`summary.json` uses `field_representation="vector-subspace-edge-nodal-v1"` and
contains `clusters`, `raw_neff`, `cluster_mean_neff`, `cluster_mean_group_index`
and `mode_tracking`. Per point and cluster, tracking evidence records candidate
ranks, span, upper/lower gaps, guard rank, Gram condition, orthonormality defect
of the committed frame,
all squared principal values, the score, margin and the sine of the largest
angle. There is no `neff` or `group_index` key, so a consumer of the default
layout cannot misread raw member columns as branches.

`fields.npz` (loadable with `allow_pickle=False`) contains the mesh,
`values`, `cluster_ids`, `cluster_offsets`, `raw_neff`, `edges`,
`raw_transverse`, `raw_longitudinal`, `raw_electric`, `frame_transform`
(points x vectors x vectors, complex), `cluster_mean_neff`,
`cluster_mean_group_index` and `mode_tracking_json`. `save_fields=false` omits
the file. `save` and the CLI refuse an existing output path so new metadata is
never mixed with fields from an earlier run.

`simcase.physics_em_modes2d.vector_pencil_residuals(mesh, eps_tri, wavelength,
boundary, neff, field)` evaluates each column as an eigenpair of the original
vector pencil, with the same wavelength scaling and PEC constraints as the
solve. Raw columns are eigenpairs to roundoff (about 1e-14 on the example).
A frame column that mixes members with different n_eff is not: its residual is
about the members' relative eigenvalue spread, for example 2e-6 inside the
example's HE11 pair and 3e-3 when an HE11 member is mixed with TE01.

The evidence field `sin_max_angle` is computed from the projection residual
`Q - P (P^H W Q)` rather than `sqrt(1 - sigma^2)`, avoiding cancellation at
small angles. The frames' orthonormality defects `d_P`, `d_Q` still limit it:
the absolute error of `sin^2` is at most about `r (d_P + d_Q)`, so small angles
are resolved to about `sqrt(r (d_P + d_Q))`: about 1e-7 on the example (defects
below 1e-15) and, at the Gram condition limit, about 1e-4 for rank 2 and 3e-4
for rank 8.

## Numerical guards

Four guards protect the small cluster matrices. They separate roundoff from rank
loss or a wrong metric; they are not accuracy claims about the physics. With
unit roundoff `u` (1.1e-16), cluster rank `r`, Gram condition number `kappa` and
`N` mesh degrees of freedom, the roundoff budget is:

| Guard | Value | Roundoff budget | A failure looks like |
|---|---|---|---|
| Hermitian defect of `G`, relative Frobenius | 1e-10 | about `sqrt(N) u` (2e-14 at N = 2e5); worst case `2 N u`, below the guard up to N = 4e5 | order one (wrong metric) |
| Gram condition `kappa` | 1e6 | none; a limit chosen so the next row stays consistent | near-duplicate fields |
| Orthonormality defect `max abs(Q^H W Q - I)` of each formed frame | 1e-8 | `8 r u (kappa + sqrt(N))`; at most 7e-9 for kappa = 1e6, r = 8, N = 1e6 | well above the budget |
| `sigma^2` above one | `(1 + r d_P)(1 + r d_Q) - 1 + 1e-12` | defects `d` of the two frames, plus about `u (r + sqrt(N))` of SVD and product roundoff, covered by 1e-12 for N up to about 1e7 | frames not orthonormal |

Where the budget terms come from. `G` is a sum of sparse products, so its
entries carry relative roundoff of order `sqrt(N) u`. The Hermitian
eigendecomposition used for `G^(-1/2)` is backward stable, and `G^(-1/2)`
amplifies both its backward error and the Gram roundoff by up to `kappa`. The
frame is then formed and its defect measured with fresh products, which adds
the `sqrt(N)` term. The spectral defect of a frame is at most `r` times its
largest entry defect, which bounds `sigma_max^2` by `(1 + r d_P)(1 + r d_Q)`.

Measured on generic random fields (ranks 1 to 12, `kappa` up to 1e6, N from
153 to 2e5, both CI OpenBLAS kernels), the defect reached 2.3 of the 8 in the
budget and the remaining `sigma^2` excursion reached 0.45 of `u (r + sqrt(N))`.
The tests check the budget with these margins. The factor of the `sqrt(N)` term
also grows with the conditioning of the mass matrices (strongly graded meshes);
only quasi-uniform meshes were measured.

Changes from the first version, both stricter: the condition limit was 1e8,
where the defect budget is about 1e-6, so the defect guard, not the stated
limit, decided; and the defects were measured from `H^H G H` against the Gram
matrix the whitening came from. That misses the Gram roundoff amplified by
`kappa`, and identical spans in coordinates with `kappa` between about 1e6 and
3e7 were refused as "principal value exceeds one". Defects are now measured on
the frames that are actually stored and compared, and the evidence field
`orthonormal_defect` is that of the committed frame.

## Studio

Studio shows a cluster selector ("cluster 1 (rank 2)") instead of branches. The
field view draws the normalized subspace field density and reports the n_eff
band, mean, mean-index derivative and the smallest squared principal value at
the selected wavelength. The sweep chart plots cluster mean n_eff. The table
lists the mean n_eff, band width and mean-index n_g per cluster; no member group
index is shown. The HTTP result carries a separate `subspace` object with
`field_representation="vector-subspace-edge-nodal-v1"`; `neff` and
`group_index` are null, so the branch views cannot display it. The page refuses
any other layout version, and a failed run clears the previous display.

## Limits

- Physical validation is narrow so far. On the symmetric polar fiber fixture
  (a = 4 um, n1 = 1.45, n2 = 1.44, radius 6a, 1.53 to 1.57 um), the HE11 pair's
  cluster mean-index derivative at 1.55 um differs from the exact vector group
  index (implicit differentiation, `refsol.fiber.vector_group_index`) by
  2.1e-5, 6.4e-6 and 2.9e-6 at mesh scales 1, 2 and 3. The pre-registered
  gate is below 2e-4 at scale 2, decreasing at scale 3. Tracking TE01 and
  TM01 as separate singletons on the same fixture failed: the mesh resolves
  their 9.6e-6 splitting only to about 1e-6. On the same HE11 case, enlarging
  the domain to 8a or 10a changed the result by 1e-11. Halving or doubling the
  wavelength step changed it exactly as the analytic stencil truncation
  predicts (about 1e-7). A larger candidate budget and random rotations of the
  solver's degenerate bases changed nothing beyond roundoff. Writing the
  same fixture's coordinates and wavelengths in nm or m instead of um changed
  the result by about 1e-13. The example document written in nm or m agrees
  with the um document to 5e-8; its mesh differs slightly, because the
  mesher's refinement rounds differently at another scale. The FEM HE11
  eigenvector span approaches the exact two-polarization field span
  (`refsol.fiber.vector_mode_field`) at first order: sin of the largest
  principal angle 0.097, 0.049 and 0.033 at scales 1 to 3. A dispersive
  Sellmeier core/cladding case agrees with the exact dispersive n_g to 6.0e-6
  and 2.6e-6 at scales 2 and 3, and its material-dispersion contribution
  matches the exact one to 2.5e-7. On a higher-V fiber (n1 = 1.47, V = 4.79), an accidental rank-3 cluster
  (HE21 pair and TM01, 2.2e-5 apart) tracked with HE11 and TE01 gives mean-index
  errors below 3.5e-5 at mesh scale 3, decreasing at scale 4. At scale 2 the
  same settings were refused, because the coarser mesh joins TE01 to that
  cluster. Other guides and geometries remain open.
- Splitting, merging, rank changes, cutoff continuation, individual
  polarization labels and individual slopes inside a cluster are out of scope.
- The candidate search is bounded. A guard shows only that something was
  observed below the cluster, not that the spectrum is complete. Repeat with
  two larger `search_modes` before relying on a cluster identification.
- Sampled overlaps cannot certify behavior between samples; refine the
  wavelength step. Identity is field continuity at the samples. Near an
  avoided crossing between clusters, a coarse step follows the field
  character (diabatic) and a fine step follows the instantaneous eigenvector
  (adiabatic). The tracker does not choose between these meanings for you.
- The example's circular core sits in a square PEC box with an unstructured
  mesh, so its HE11 pair is split by about 4e-6 in n_eff. That is a numerical
  splitting, not a physical one.
