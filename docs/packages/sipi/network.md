# Uniform transmission-line networks

**English** | [한국어](../../locales/ko/pages/packages/sipi/network.md)

[Cross-section overview](overview.md) · [Validation](network_validation.md)

`rlgc_network` converts supplied per-unit-length RLGC into a uniform line's
frequency-dependent scattering matrix. `quasistatic_network` connects the
existing cross-section extraction to it. Neither API extracts conductor loss,
roughness, skin effect, internal inductance or dispersive dielectric properties.
[Conductor surface loss](conductor.md) is a separate extraction API with a
high-frequency validity gate and a bridge using external plus internal L.

```python
import numpy as np
from sipi import stripline, quasistatic_network

parameters = stripline(width=0.5e-3, plane_spacing=1e-3,
                      eps_r=4, tan_delta=0.02).analyze()
network = quasistatic_network(parameters, [1e6, 1e8, 1e9],
                             length=0.1, R=np.zeros((1, 1)), z_ref=50)
# R=0 explicitly selects perfect conductors; dielectric loss remains present.
s21 = network.s[:, 1, 0]
insertion_loss_db = -20*np.log10(np.abs(s21))
text = network.touchstone()  # save this text as line.s2p; no implicit file writes
```

## Input and output contract

- Frequencies: nonempty, strictly increasing one-dimensional Hz array, >=0.
  The DC sample uses the supplied DC R/G. A constant loss tangent contributes
  G=0 at DC; it does not model DC leakage or broadband causality.
- R, L, G, C: real symmetric `(N,N)` constants or `(F,N,N)` samples, respectively
  ohm/m, H/m, S/m and F/m. Scalars are not matrices, even for a single line.
  L/C must be positive definite; R/G positive semidefinite. Symmetry and
  semidefiniteness allow relative roundoff of 1e-12 times the matrix's largest
  absolute entry. Small asymmetric roundoff is averaged; eigenvalues are not
  clipped. Indefinite/complex/nonfinite inputs and boolean numbers are rejected.
- `length`: finite metres >=0. `z_ref`: finite positive real ohms, common to all
  input ports. Complex and frequency-dependent reference impedances are unsupported.
- Optional `names`: one unique single-line string per signal conductor.
- `LineNetwork.frequency`, `.s`, `.z_ref` are copied, read-only arrays. S has
  shape `(F,2N,2N)`. `.port_names` specifies the port order. A user-constructed
  `LineNetwork` checks shape and finiteness, not passivity or causality.
- `quasistatic_network(parameters, frequency, length=..., R=..., z_ref=50)`
  reuses C/L and computes G(f)=2*pi*f*C_loss. R is mandatory: a zero matrix is
  an explicit perfect-conductor assumption, never an extracted resistance.

The time convention is exp(+j*omega*t). Ports are `near:1 ... near:N`, then
`far:1 ... far:N`, with currents directed **into** the network at both ends.
`S[i,j]` is outgoing at i for an incident wave at j. For a matched lossless line,
S21 has negative phase, exp(-j*beta*length). A zero-length line connects each
near port to its corresponding far port, without reflection or permutation.

## Calculation

For positive-forward conductor current I, the telegrapher equations are
`dV/dz = -(R+j*omega*L) I`, `dI/dz = -(G+j*omega*C) V`.
Normalize V by sqrt(Zref) and I by its reciprocal before evaluating the transfer
matrix. A short section is obtained by a matrix exponential, converted to S,
and repeatedly doubled by scattering connection. This avoids growing
hyperbolic transfer entries on long, strongly attenuating lines. No modal
symmetry or simultaneous diagonalization is assumed.

The norm of the length-scaled normalized generator must be finite and <=2^50;
otherwise the calculation raises `ValueError`. This is an overflow guard, not
an accuracy guarantee near that limit. Extremely ill-conditioned inputs and
very long electrical lengths require independent error assessment. No spatial
mesh is introduced in this uniform-line propagation stage. Cross-section mesh,
box truncation, constitutive model and quasi-TEM validity remain separate errors.

## Differential and common mode

For **two conductors**, `.mixed_mode()` maps near+/near-/far+/far- to
`d_near, d_far, c_near, c_far`. It requires four equal-reference single-ended
ports. Differential voltage is V+ - V-, differential current (I+ - I-)/2;
common voltage (V+ + V-)/2, common current I+ + I-. Accordingly the reference
impedances are `2*Zref, 2*Zref, Zref/2, Zref/2`. Power-wave transformation is
orthogonal and preserves power. Unequal reference impedances are rejected;
conversion does not assume the pair is geometrically symmetric.

## Touchstone output

`.touchstone()` returns Touchstone **2.0**, Hz, S, real/imaginary, full matrix,
with explicit port count, frequency count and real per-port references. Two-port
order is S11,S21,S12,S22 (`21_12`); N>=3 uses row-major order. Save as `.sNp`
where N is the number of ports. Port names appear only as ASCII-safe comments.
The independent reader tests include nonreciprocal data to expose transposition.

Only single-ended export is supported. Mixed-mode export,
measurement plotting UI, time-domain conversion and a general circuit solver are
not implemented. The Python APIs do not add a website interface or alter the
cross-section JSON schema.

For layer-dependent dispersive extraction, see [dielectric models](dielectrics.md).

[Touchstone input and explicit measured-network comparison](touchstone.md) are available through a separate API.
