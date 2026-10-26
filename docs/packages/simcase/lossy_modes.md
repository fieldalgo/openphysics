# Absorbing waveguide modes

**English** | [한국어](../../locales/ko/pages/packages/simcase/lossy_modes.md)

`em.modes2d` accepts passive complex isotropic permittivity for scalar and
full-vector finite-window modes. The scalar approximation is exact for the TE
slab equation, not for general high-contrast 2D structures or surface plasmons.
Use full-vector modes for those structures. PML, radiation/leakage loss, bent
guides, gain media and exceptional-point tracking are outside this contract.

## Phasor, input and units

The retained field convention is `exp(+i omega t-i beta z)`, with
`beta = (2*pi/lambda0)*n_eff`. Forward passive absorption has **Im n_eff < 0**.
The low-level `galerkin.solve_modes(..., eps_r, ...)` and
`simcase.physics_em_modes2d.solve(..., eps_tri, ...)` use this same convention:
passive epsilon has a negative imaginary part. JSON/physmat materials use the
usual positive extinction coefficient `n+ik`; the document runner conjugates
their epsilon at the solver boundary. Do not conjugate a document material again.

For beta in inverse metres, amplitude decays as `exp(-a*z)` with `a=-Im beta`;
power decays as `exp(-alpha*z)` with `alpha=2*a`.
`loss_dB_cm = 10*alpha/(100*ln(10))`. Positive loss means attenuation.
`RunResult.propagation_loss_db_cm()` performs the wavelength-to-SI conversion.
Indices are dimensionless. Fields have relative amplitude, not V/m or unit power.

## Python and JSON

```python
import copy
from simcase import Document, examples, run

data = copy.deepcopy(examples.VECTOR_SLAB)
data["materials"]["film"] = {"n": 3.48, "k": 0.01}
data["study"] = {"type": "single"}
result = run(Document.from_dict(data), verbose=False)
print(result.neff)                       # complex, Im < 0
print(result.propagation_loss_db_cm())   # positive power attenuation
result.save("absorbing_slab")
```

`result.neff` and the NPZ `neff` retain complex values. Scalar `fields` and vector
transverse/longitudinal/electric arrays also retain their complex components.
JSON cannot encode Python complex numbers: a complex result declares
`mode_result_schema: "openphysics.modes2d/2"`, keeps the existing numeric `neff`
array as its **real part**, and supplies the same-shaped `neff_imag` and
`propagation_loss_db_cm`. `phasor` records the sign convention. Complex spectral
derivatives likewise use `group_index` and `group_index_imag`. The input document
version and existing lossless numeric outputs are unchanged.

Studio shows Re n_eff, Im n_eff and dB/cm for each returned mode. Its scalar
display is magnitude; `scalar_fields_complex` retains real/imaginary nodal data
in the response. Vector components retain their existing complex encoding.
Saved PNG sweep curves show the real parts of effective and group indices,
with explicit Re labels; JSON/NPZ retain both complex components.

## Selection, normalization and tracking

Without `n_target`, the dielectric vector search uses
`n_cladding < Re n_eff < sqrt(max Re epsilon)` and descending Re n_eff.
This is a candidate filter, not a proof of confinement or search completeness.
For non-positive Re epsilon, explicitly set the physics `n_target` to a positive
real index: candidates nearest this target are selected and then sorted by
Re n_eff. No dielectric upper bound is applied. `n_cladding` remains required for
vector documents. Low-level `galerkin.solve_modes` additionally accepts a complex
shift target. Refine both the mesh and the outer window before interpreting a
candidate as a guided mode. There is no automatic attenuation cutoff.

Scalar normalization fixes the peak coefficient to one. Vector normalization
sets the largest sampled centroid |E| to one, preserving relative components;
physical `Ez = i*ez` in the low-level return. A mode's overall phase is arbitrary.
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
