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
  "n_target": 2.85,
  "pml": {
    "thickness": {"bottom": 0.5, "top": 0.5},
    "strength": 3.0,
    "order": 2,
    "min_physical_fraction": 0.1
  },
  "bend": {"radius": 5.0, "axis": "y", "origin": 0.0}
}
```

Omit `bend` for a straight guide. Thickness, radius and origin use the declared
length unit. `strength` and the fraction are dimensionless; order is integer
2, 3 or 4. Missing face thicknesses are zero. At least one is positive, and
the strips must leave a nonempty physical window resolved by the mesh.
The declared geometry includes the PML; extend materials through it. PML
outer faces must be PEC; other faces retain PEC/PMC behavior. Refinement must
resolve material interfaces, PML and the transverse field, in both directions.
A face or physical-window boundary cutting elements is represented by centroid
coefficients/membership; include this error in refinement checks.

`n_target` must be explicitly positive. Search near that value replaces the
closed-guide dielectric interval. `n_cladding` remains descriptive for vector
input; it does not classify open candidates. Metal/absorbing materials retain
the complex material contract. The bend axis points outward; `radius` is the
positive radius at `origin`, and every point in the domain must have positive
radius. Propagation distance is reference arc length `z=R theta`.

## API and results

```python
from simcase import Document, run
result = run(Document.load("model.json"), verbose=False)
print(result.neff)                       # complex, point x mode
print(result.propagation_loss_db_cm())   # signed total power attenuation
print(result.bend_loss_db_90deg())       # None for a straight guide
print(result.open_boundary)              # all searched candidates per point
result.save("results")
```

`simcase.physics_em_modes2d.solve(..., n_target=2.85, pml=..., bend=...)`
provides the same coordinate settings on an existing mesh, using mesh length
units. `solve_point` diagnostics and `run` diagnostics use document units.
The JSON summary retains `openphysics.modes2d/2`, real `neff` plus `neff_imag`,
and adds `open_boundary` and optional `bend_loss_db_90deg`. NPZ retains complex
arrays and `open_boundary_json` without pickles. No releases are implied by a
feature-branch implementation.

Each `openphysics.pml-candidates/1` point records all searched candidates,
one-based candidate numbers, complex index, original-pencil relative residual,
positive physical/PML L2 fractions, selected numbers, and reasons. Search uses
at least six candidates, otherwise twice the requested count, limited by free
DOFs. Eligible candidates have positive real index, residual <=1e-8, physical
fraction >= the configured threshold (default0.1, permitted0..1), and imaginary
index <=1e-10 max(1,|Re n|). The nearest eligible candidates to the target are
returned, ordered by descending real index at the seed point. Rejected and
unselected candidates remain in diagnostics. A nonfinite/zero propagation root
stops the low-level solve; it is not silently discarded.

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
Vector representation is `pml-vector-edge-nodal-v1`: transverse edge integrals
are computational covariant coefficients (physical Et in the unstretched
window), longitudinal nodal values are physical Ez after division by h, and
centroid electric components are divided by their Jacobian factors. Fields
inside PML are artificial. Scalar representation is `pml-scalar-nodal-v1`.

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

The convention is `exp(+i omega t-i beta z)`, `beta=k0 n_eff`. Passive material
has Im epsilon<=0 and passive forward attenuation has Im n_eff<0. Power loss
is `-40 pi Im(n_eff)/(100 ln(10) wavelength_m)` dB/cm. For bends,
`loss_db_90deg = loss_db_cm pi R_cm/2` at the specified reference radius.
These are **total** absorption plus radiation losses. Subtracting unrelated
runs does not uniquely separate material, leakage and bending losses.

Studio exposes PML faces, strength/order/fraction, target and bend settings.
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
