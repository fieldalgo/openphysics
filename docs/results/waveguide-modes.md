# Interpret waveguide modes and loss

**English** | [한국어](../locales/ko/pages/results/waveguide-modes.md)

[Documentation home](../README.md)

This guide covers `em.modes2d` waveguide results. For complex cavity frequencies
and Q, use the separate [cavity contract](../packages/simcase/cavity3d.md).
A returned eigenpair is a numerical candidate; check its field, convergence and
selection settings before identifying it as the physical mode of interest.

## Effective index and attenuation

The retained waveguide field convention is `exp(+iωt − iβz)`, with
`β = 2π n_eff / λ₀`. Forward passive attenuation therefore has
`Im(n_eff) < 0`. JSON material extinction `k` and `physmat` use `n + ik` with
positive `k` for absorption. The document runner performs the conversion at the
solver boundary; do not conjugate JSON inputs yourself. Direct low-level
permittivity calls use the solver convention: see
[absorbing modes](../packages/simcase/lossy_modes.md).

Run this small absorbing slab after installing simcase:

```python
import copy
import numpy as np
from simcase import Document, examples, run

data = copy.deepcopy(examples.VECTOR_SLAB)
data["materials"]["film"] = {"n": 3.48, "k": 0.01}
data["study"] = {"type": "single"}
result = run(Document.from_dict(data), verbose=False)
neff = np.asarray(result.neff)
loss_db_cm = result.propagation_loss_db_cm()
print(neff)
print(loss_db_cm)

wavelength_m = 1.55e-6
beta_per_m = 2 * np.pi * neff / wavelength_m
power_decay_per_m = -2 * beta_per_m.imag
expected_db_cm = 10 * power_decay_per_m / (100 * np.log(10))
np.testing.assert_allclose(loss_db_cm, expected_db_cm)
```

For propagation distance `z` in metres, field amplitude decays as
`exp(−a z)`, where `a = −Im(β)`. Power decays as `exp(−2a z)`.
The conversion above uses the power coefficient and reports **dB/cm**, not dB/m.
The slab's returned index depends on its finite window and mesh; the check
verifies the unit/sign conversion, not independent accuracy of the eigensolver.

## Read fields without inventing a power scale

Scalar modes use a peak coefficient normalization; vector modes use the maximum
centroid electric-field magnitude. These relative fields are not calibrated V/m
or one-watt modes. Global complex phase is arbitrary. Compare field patterns
after accounting for phase, and do not equate identical plot colors across
independently normalized modes with identical optical power.

The low-level longitudinal vector coordinate needs the documented `Ez = i*ez`
conversion. High-level physical electric arrays already follow their documented
field representation: consult [modal coordinates](../packages/galerkin/modal_coordinates.md)
before transforming coefficients. Saved PNG sweep curves show real effective and group indices; JSON/NPZ
preserve complex information. In the version-2 summary, `neff` and `neff_imag` are separate
arrays; reading only `neff` drops absorption. NPZ retains complex `neff`.

## Identify a mode across runs

Without an explicit target, the dielectric candidate filter and descending real
index order are not a proof of confinement or completeness. Scalar TE slab
solutions are useful controls, but a scalar approximation does not represent a
general high-contrast 2D vector waveguide. Nonpositive-real-permittivity problems
require the documented explicit target and appropriate formulation.

For sweeps, use the supported tracking metadata and check overlap, assignment
margin and spectral separation. A candidate's array index is not a universal
branch identity. Absorbing sweeps use a positive conjugated L2 overlap, not power
orthogonality. Complex `n_g = n_eff − λ d(n_eff)/dλ` is a spectral derivative;
it is not automatically an energy or signal velocity. Refine wavelength spacing
as well as the mesh. See [tracking](../packages/simcase/lossy_modes.md) and
[vector subspace tracking limits](../packages/simcase/vector_subspace_tracking.md).

## Treat PML loss as a convergence question

PML and constant-radius results include numerical candidates whose stability is
`not_checked` after one run. Refine the mesh, physical window, PML thickness and
stretch settings separately while following the same physical branch. PML-region
fields use artificial coordinates; interpret physical fields in the physical
window. Diagnostic PML overlap is not stored physical energy.

With both absorption and radiation, the reported propagation loss is total loss.
Subtracting unrelated runs does not uniquely separate the two mechanisms. The
[PML contract](../packages/simcase/pml_modes.md) defines the physical window,
target requirements and bend-loss conversion. Keep those settings with the
[saved run](saved-results.md) and record
[convergence evidence](../validation/convergence.md) for the quantity you report.
