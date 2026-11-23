# PML, leaky and constant-radius modes

[한국어](../../locales/ko/pages/packages/simcase/pml_modes.md) · [Complex material modes](lossy_modes.md) · [Coordinate formulation](../galerkin/modal_coordinates.md)

`em.modes2d` supports scalar and full-vector complex-coordinate PML on a
rectangular domain, including constant-radius bends. PML truncates an open
exterior; its eigenvalues include artificial modes. Returned modes are
**candidates**, not certified physical resonances. Refine the mesh and vary
physical window, PML thickness and strength independently before interpreting
attenuation. A single run always reports `stability: "not_checked"`.

## Input and units

Add these settings to an existing `physics.em1` entry:

```json
{
  "target_effective_index": 2.85,
  "pml": {
    "pml_thickness": {"bottom": "0.5 um", "top": "0.5 um"},
    "pml_strength": 3.0,
    "pml_order": 2,
    "pml_minimum_physical_fraction": 0.1,
    "pml_search_mode_count": 16
  },
  "bend": {"bend_radius": "5 um", "axis": "y", "bend_origin": "0 um"}
}
```

Omit `bend` for a straight guide. Thickness, radius and origin are lengths with their unit.
`pml_strength` and the fraction are dimensionless; `pml_order` is the integer 2, 3 or 4.
Missing face thicknesses are zero. At least one is positive (a face written as `"0 um"` is
refused), and the strips must leave a nonempty physical window resolved by the mesh.
`pml_strength` (default 3), `pml_order` (default 2), the fraction (default 0.1, in (0, 1]) and
`bend.axis` (default `x`) are echoed in `defaults_applied` when omitted.
The declared geometry includes the PML; extend materials through it. PML
outer faces must be PEC; other faces retain PEC/PMC behavior. Refinement must
resolve material interfaces, PML and the transverse field, in both directions.
A face or physical-window boundary cutting elements is represented by centroid
coefficients/membership; include this error in refinement checks.

`target_effective_index` must be explicitly positive. Search near that value replaces the
closed-guide dielectric interval. `effective_index_threshold` remains descriptive for vector
input; it does not classify open candidates. Metal/absorbing materials retain
the complex material contract. The bend axis points outward; `bend_radius` is the
positive radius at `bend_origin`, and every point in the domain must have positive
radius. Propagation distance is reference arc length `z=R theta`.

## API and results

```python
from simcase import Document, run
result = run(Document.load("model.json"), verbose=False)
print(result.effective_index)            # complex, point x mode; Im > 0 is attenuation
print(result.propagation_loss())         # dB/m, signed total power attenuation
print(result.bend_loss())                # dB per 90 degrees; None for a straight guide
print(result.open_boundary)              # all searched candidates per point
result.save("results")
```

`solve_point` and `run` report in SI under exp(−iωt). The kernel-frame
`simcase.physics_em_modes2d.solve(..., n_target=2.85, pml=..., bend=...)` (micrometres,
exp(+iωt), the kernel's own names) is internal. The JSON summary records
`mode_result_schema="openphysics.modes2d/3"`, `effective_index` as `re`/`im` value objects with
`time_convention`, `propagation_loss` (dB/m), `open_boundary` and, for a bend, `bend_loss`
(dB per 90 degrees). NPZ retains complex arrays and `open_boundary_json` without pickles. No
releases are implied by a feature-branch implementation. PML results save none of the
`unnormalized_mode_power`/`confinement_factor`/`unnormalized_field_overlap`/`coupling_efficiency` arrays of
[closed-window results](overview.md#mode-post-processing): the transverse
coefficients are covariant integrals in the stretched coordinates, so the
lossless Poynting formula over the whole window is not the physical power and
a physical-window variant is not offered. A `results.mode_overlap` block is
validated but ignored for them.

Each `openphysics.pml-candidates/2` point records all searched candidates,
one-based candidate numbers, the complex `effective_index`, the original-pencil
`relative_residual`, positive physical/PML L2 fractions, selected numbers, reasons and
`physical_bounds` in metres. Without `pml_search_mode_count` the search uses
at least six candidates, otherwise twice the requested count; with it, exactly that many
(an integer from 1 to 64 and at least `mode_count`; in a sweep, at least the tracker's
`study.tracking.search_mode_count`, else `E-CONTRACT`). Either way it is limited by free
DOFs. A wider search finds physical modes that a narrow one misses near the target; the
key is never recorded in `defaults_applied`, so documents without it give the results they
gave before it existed. Eligible candidates have positive real index, residual <=1e-8 (`relative_residual_threshold`), physical
fraction >= `pml_minimum_physical_fraction` (default 0.1, in (0, 1]), and imaginary
index >= -1e-10 max(1,|Re n|) (a gain-like candidate is rejected as `negative_imaginary_index`). The nearest eligible candidates to the target are
returned, ordered by descending real index at the seed point. Rejected and
unselected candidates remain in diagnostics. A nonfinite propagation root
stops the low-level solve; it is not silently discarded. Roots of the vector
formulation's static `beta^2 = 0` family with `|beta^2| <= 1e-10 |sigma|` are not
candidates, and a search of only such roots is refused like any search without
an eligible candidate ([waveguide formulation](../galerkin/waveguide_formulation.md#3-full-vector-mixed-nédélecnodal-formulation)).

### Further searches

One search near one target can miss a physical mode far from it: a strip over a substrate has a
mode near the cladding index (n ≈ 1.486 + 7.9e-3i) that a search of 32 near 2.46 does not find.
`pml.pml_additional_searches` lists 1 to 3 further searches beside the primary one
(`target_effective_index` with `pml_search_mode_count`):

```json
"pml": {"pml_thickness": {"bottom": "1 um", "top": "1 um"}, "pml_search_mode_count": 32,
        "pml_additional_searches": [{"target_effective_index": 1.95, "pml_search_mode_count": 16}]}
```

- Each entry gives both keys. Each target is finite, positive and differs, as written (exact
  decimals: `1.95` and `1.950` are the same target), from the primary target and from every other
  entry. Each count is an integer from 1 to 64, limited by the free DOFs like the primary count; it
  need not hold `mode_count`. Errors are `E-CONTRACT` or `E-DOMAIN` at the key's path.
- The key is read with the vector formulation and a single study (a bend is allowed). A sweep is
  refused (`E-CONTRACT`): "pml_additional_searches is not read with a study sweep in this release;
  give one target".
- The searches run in order on the same mesh and pencil, one factorization per target (each
  search assembles the pencil again). Candidates are numbered in that order and each is judged
  eligible as above.
- A candidate b of a later search is a **duplicate** of an earlier candidate a (one of an earlier
  search that is itself no duplicate, eligible or not) when |n_b − n_a| ≤ 1e-9 max(1, |n_a|) and
  η_w(a, b) = |⟨a, b⟩| / (‖a‖ ‖b‖) ≥ 0.99, with the transverse edge coefficients and the edge mass
  matrix of the whole computational mesh. When several earlier candidates lie within the index
  tolerance, b is a duplicate when its projection on their span holds at least 0.99 of its squared
  norm. A duplicate keeps its record and is never selected: its reasons add `duplicate_candidate`
  to its own, with `duplicate_of`, `duplicate_effective_index_distance`,
  `duplicate_field_overlap` (the square root of the span fraction in the degenerate case) and, in
  that case only, `duplicate_span`.
- The `mode_count` eligible non-duplicate candidates with the **highest Re n_eff** are returned
  in descending Re (`selected_descending_real_index`; the others `outside_requested_count`), not
  the nearest to a target. None eligible raises `ModeSelectionError` with the merged diagnostics.
- The record is `openphysics.pml-candidates/3`: every /2 key, plus `searches` (`search`,
  `target_effective_index`, `search_mode_count`, `candidate_count`), `selection:
  "descending_real_index"`, `duplicate_rule` and each candidate's `search` (1-based). The
  summary's `selection` is `pml_heuristic_descending_real_index`; `mode_result_schema` and the
  field layout do not change, and `resolved_inputs` echoes the searches. Without the key nothing
  changes (schema /2, `selected_near_target`). A simcase older than the key refuses it by name
  (`E-KEY-UNKNOWN`).
- Descending Re leans on the physical-fraction filter alone. With the low default fraction 0.1 a
  lossy box or PML candidate above the physical mode can pass and be returned first (the leaky
  slab example with a further search near 2.0 returns 3.4396 + 0.0513i, not 2.8521); Studio's
  documents use 0.5. Read the candidate fractions before trusting the first mode.

`abs(Im n)<=1e-10 max(1,|Re n|)` is labelled `numerically_unresolved`; its signed
value and attenuation are preserved, never clamped to zero. This threshold is
a numerical sign diagnostic, not an accuracy claim. Fewer eligible candidates
are reported explicitly; zero raises `ModeSelectionError` with `.diagnostics`.
The finite search does not guarantee completeness. The fraction threshold
alone cannot separate every PML mode from a physical pole.

## Fields, normalization and tracking

Scalar fields have unit peak over physical nodes. Vector fields have unit
maximum centroid |E| over physical elements. Both have relative amplitude,
not unit power. Physical membership is determined at element centroids.
Vector representation is `pml-vector-edge-nodal-v2`: transverse edge integrals
are computational covariant coefficients (physical Et in the unstretched
window), longitudinal nodal values are physical Ez after division by h, and
centroid electric components are divided by their Jacobian factors. Fields
inside PML are artificial. Scalar representation is `pml-scalar-nodal-v2`.
Both save the file layout `em-modes2d-p1-node-centroid-v2`, so `simcase.export`
writes them like any mode result: the VTU holds the whole computational mesh,
and its arrays cover the absorbing layer too, where they are artificial.
`physical_bounds` in `open_boundary` marks the physical window and is not copied
to VTU; clip to it in the viewer.

The positive L2 diagnostic uses the transverse computational edge mass and
nodal interpolation of physical Ez; on the physical window sx=sy=1. The PML
contribution is a diagnostic extension of this metric, not electromagnetic
energy. It is neither a biorthogonal product nor a mode orthogonality claim.
The physical subset of this same positive metric controls wavelength tracking.
Only wavelength may be swept, with fixed geometry/PML/bend. Scalar and vector
sweeps require at least three positive strictly monotone wavelengths; missing,
ambiguous or nearly degenerate matches stop the run. Resolved assignment
preserves each eigenfield, updates candidate selections and does not mix
nondegenerate eigenvectors. `electric-l2-subspace-v1` is unsupported for these
complex spectra. Complex group index is a spectral derivative, not energy
velocity. Refine wavelength spacing and candidate budget too.

## Signs, attenuation and limitations

The convention is `exp(-i omega t+i beta z)`, `beta=k0 n_eff`. Passive material
has Im epsilon>=0 and passive forward attenuation has Im n_eff>0. Power loss
is `40 pi Im(n_eff)/(ln(10) wavelength)` dB/m with the vacuum wavelength in metres. For bends,
`bend_loss = propagation_loss pi R/2` (dB per 90 degrees, R in metres) at the specified
reference radius. The kernel works under exp(+iωt); simcase conjugates every complex value
once at its boundary.
These are **total** absorption plus radiation losses. Subtracting unrelated
runs does not uniquely separate material, leakage and bending losses.

Studio exposes PML faces, strength/order/fraction, target and bend settings (lengths as
quantity strings).
Results show all candidate reasons and residuals; artificial PML fields are
grey. Scalar is exact for the invariant-axis TE slab polarization, an
approximation for general 2D high-contrast guides. Variable curvature, 3D open
modes, automatic PML convergence certification and non-Hermitian degenerate
subspace tracking are outside this contract.

Validation uses independent outgoing slab transfer roots, complex-order
cylindrical J/Y/Hankel matching, three meshes, independent PML/window variation,
bound lossless and large-radius limits, and separate scikit-fem assembly with
dense QZ. `tests/galerkin/test_pml_modes.py`,
`tests/galerkin/test_crosscheck_skfem_pml_modes.py` and
`tests/simcase/test_pml_contract.py` contain the relevant checks; no existing
lossless numerical gate or golden is changed.

Runnable examples: [substrate-leaky slab](../../../examples/simcase/pml_leaky_slab.json), [constant-radius slab](../../../examples/simcase/pml_bent_slab.json).
