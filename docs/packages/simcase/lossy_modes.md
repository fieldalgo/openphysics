# Absorbing waveguide modes

**English** | [한국어](../../locales/ko/pages/packages/simcase/lossy_modes.md)

`em.modes2d` accepts passive complex isotropic permittivity for scalar and
full-vector finite-window modes. The scalar approximation is exact for the TE
slab equation, not for general high-contrast 2D structures or surface plasmons.
Use full-vector modes for those structures. PML, radiation/leakage and constant-radius
bends have a [separate contract](pml_modes.md). Gain media and exceptional-point
tracking remain unsupported.

## Phasor, input and units

Documents and results use `exp(-i omega t+i beta z)`, with
`beta = (2*pi/lambda0)*n_eff`. Forward passive absorption has **Im n_eff > 0**, and a
material written as `n + i k` absorbs for k ≥ 0 (a negative k is gain and is refused with
`E-GAIN`). The mode kernel, the low-level `galerkin.solve_modes(..., eps_r, ...)` and the
kernel-frame `simcase.physics_em_modes2d.solve(..., eps_tri, ...)`, keeps
`exp(+i omega t-i beta z)`, where passive epsilon has a negative imaginary part: simcase
conjugates every material value once on the way in and every complex result once on the way
out. Do not conjugate a document material or a result yourself.

For beta in inverse metres, amplitude decays as `exp(-a*z)` with `a=Im beta`;
power decays as `exp(-alpha*z)` with `alpha=2*a`.
`propagation_loss = 10*alpha/ln(10)` dB/m `= (40 pi / ln 10) Im(n_eff) / lambda0`, with the
vacuum wavelength in metres. Positive loss means attenuation.
`RunResult.propagation_loss()` returns it per study point and mode.
Indices are dimensionless. Fields have relative amplitude, not V/m or unit power.

## Python and JSON

```python
import copy
from simcase import Document, examples, run

data = copy.deepcopy(examples.VECTOR_SLAB)
data["materials"]["film"] = {"refractive_index": {"n": 3.48, "k": 0.01}}
data["study"] = {"type": "single"}
result = run(Document.from_dict(data), verbose=False)
print(result.effective_index)            # complex, Im > 0
print(result.propagation_loss())         # dB/m, positive power attenuation
result.save("absorbing_slab")
```

`result.effective_index` and the NPZ `effective_index` retain complex values. Scalar
`unnormalized_mode_field` and the vector line-integral, z and centroid arrays also retain
their complex components. JSON cannot encode Python complex numbers: a complex result
declares `mode_result_schema: "openphysics.modes2d/3"` and writes `effective_index` as
`{"unit": "1", "re": [...], "im": [...], "time_convention": "exp(-i omega t)"}`, with
`propagation_loss` (dB/m) beside it; `time_convention` and `propagation` record the sign
convention. A complex group index takes the same `re`/`im` form. Lossless numeric outputs keep
the plain tagged form (`{"unit": "1", "values": [...]}`).

Studio shows Re n_eff, Im n_eff and dB/m for each returned mode. Its scalar
display is magnitude; `unnormalized_mode_field` retains real/imaginary nodal data
in the response. Vector components keep separate `real`/`imag` arrays.
Saved PNG sweep curves show the real parts of effective and group indices,
with explicit Re labels; JSON/NPZ retain both complex components.

VTK has no complex arrays either: `simcase.export` writes a complex scalar mode
as the point data `unnormalized_mode_field_mode_<k>_real` and `_imag`, and vector modes as
`unnormalized_electric_field_mode_<k>_real`/`_imag` (centroid cell data) and
`unnormalized_electric_field_z_mode_<k>_real`/`_imag` (nodal point data), with the
saved values unchanged. `effective_index` and the attenuation stay in the summary and NPZ.

The saved post-processing ([overview](overview.md#mode-post-processing)) is
complex where the field is: a lossy vector mode has a nonzero imaginary
`unnormalized_mode_power` (reactive part; `Re` is the +z power) and lossy modes are not
power-orthogonal; a lossy scalar result keeps a real `unnormalized_mode_field_square_integral`
(`int |phi|^2 dA`) and a complex Hermitian `unnormalized_field_overlap`.
See [viewing in ParaView](overview.md#viewing-in-paraview).

## Selection, normalization and tracking

Without `target_effective_index`, the dielectric vector search uses
`effective_index_threshold < Re n_eff < sqrt(max Re epsilon)` and descending Re n_eff.
This is a candidate filter, not a proof of confinement or search completeness.
For non-positive Re epsilon, explicitly set the physics `target_effective_index` to a positive
real index: candidates nearest this target are selected and then sorted by
Re n_eff. No dielectric upper bound is applied. `effective_index_threshold` remains required for
vector documents. Low-level `galerkin.solve_modes` additionally accepts a complex
shift target. Refine both the mesh and the outer window before interpreting a
candidate as a guided mode. There is no automatic attenuation cutoff.

Scalar normalization fixes the peak coefficient to one. Vector normalization
sets the largest sampled centroid |E| to one, preserving relative components;
physical `Ez = i*ez` in the low-level (kernel-frame) return. A mode's overall phase is arbitrary.
No nearby eigenvectors are mixed to manufacture an orthogonal eigenbasis.

Resolved vector wavelength sweeps and absorbing scalar wavelength sweeps use
conjugated, positive electric/scalar L2 overlap on the fixed mesh, with assignment,
overlap/margin and complex-eigenvalue separation guards. This geometric measure
is not power orthogonality or a left/right eigenvector pairing. Absorbing scalar
sweeps require at least three strictly monotone wavelengths and use the default
assignment settings. Existing lossless scalar sweeps retain their historical
rank ordering. Scalar tracking settings are not yet configurable through JSON.

`n_g = n_eff-lambda0*d(n_eff)/d(lambda0)` is a complex spectral derivative, not an
energy or signal velocity. Check wavelength-step convergence. Untracked complex
sweeps have no group-index result. `electric-l2-subspace-v1` assumes a real
spectrum and explicitly rejects absorbing materials; use separated branches or
single studies. Near degeneracy, failed overlap and incomplete searches are
errors, not silently continued mode identities.

## Validation and limits

`tests/simcase/test_lossy_modes.py` compares scalar TE and vector TE/TM with
independently solved complex slab dispersion equations over three meshes,
checks weak-loss and zero-loss limits, residuals, saved complex fields and loss
units, and compares a full-vector metal interface with
`n_eff=sqrt(epsilon_m*epsilon_d/(epsilon_m+epsilon_d))`.
The scikit-fem waveguide comparison uses independent assembly and dense QZ
against the sparse product solver. Agreement is not a convergence proof.
Acceptance on particular fixtures is not a universal error bound. See the
[comparison contract](../../reference-comparisons.md); required CI remains
necessary before integration.
