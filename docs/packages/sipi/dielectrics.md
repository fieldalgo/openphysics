# Frequency-dependent dielectric extraction

**English** | [한국어](../../locales/ko/pages/packages/sipi/dielectrics.md)

[Cross-sections](overview.md) · [Uniform-line networks](network.md)

`sipi.dielectric` evaluates a material at each requested frequency and solves
the layered cross-section's complex electrostatic problem on one fixed mesh.
It computes frequency-dependent capacitance and dielectric conductance; it does
not substitute one effective dielectric constant for a heterogeneous section.

```python
import json
import numpy as np
from sipi import microstrip
from sipi.dielectric import WidebandDielectric, dispersive_line, dielectric_to_dict

section = microstrip(width=.5e-3, substrate_height=1e-3, eps_r=4)
material = WidebandDielectric(eps_ref=4, tan_delta_ref=.02, reference_hz=1e9)
sweep = dispersive_line(section, [1e6, 1e8, 1e9, 1e10],
                        materials={'substrate': material})
network = sweep.network(length=.1, R=np.zeros((1, 1)), z_ref=50)
material_json = json.dumps(dielectric_to_dict(material), allow_nan=False)
```

R=0 explicitly assumes perfect conductors. Use the same resolved mesh for a
direct comparison; separately check finer meshes and box truncation over the
frequency range. The executable [example](../../../examples/sipi/dispersive_line.py)
prints sampled material values, capacitance, conductance and transmission.

## Material contracts

The convention is exp(+jωt), with relative permittivity εr=ε′−jε″. Frequencies
are Hz, strengths and relative permittivities are dimensionless. Models reject
boolean, complex, nonfinite and invalid-sign inputs. `permittivity` accepts a
nonnegative scalar or nonempty one-dimensional real frequency array; arrays
need not be sorted for a material evaluation. Extraction requires strictly
increasing samples. Real permittivity is at least one in these models.

| Model | Inputs and behavior |
|---|---|
| `ConstantDielectric(eps_r, tan_delta=0)` | εr=eps_r(1−j tan_delta). This preserves the existing constant-tangent model; nonzero constant tangent is not a causal broadband model. |
| `DebyeDielectric(eps_inf, strengths, relaxation_hz)` | εr=eps_inf+Σ strength_k/(1+j f/f_k). Nonempty equal-length pole/strength arrays; strengths >=0, f_k>0, eps_inf>=1. At DC εr=eps_inf+Σstrength; at infinity εr→eps_inf. |
| `WidebandDielectric(eps_ref, tan_delta_ref, reference_hz, low_hz=1e3, high_hz=1e12)` | Finite-band log relaxation, calibrated to ε′ and tanδ at the reference frequency. low<high and low<=reference<=high; calibration must yield eps_inf>=1. Zero loss becomes constant εr. |
| `TabulatedDielectric(frequency, eps_r, tan_delta)` | At least two positive, increasing frequencies and equal-length value arrays. Linearly interpolate ε′ and ε″=eps_r·tan_delta against log(f), including endpoints. No extrapolation or DC evaluation. Sampled passivity does not establish causality. |

For the wideband model, let `D(f)=log((high+j*f)/(low+j*f))`. Then
`strength=eps_ref*tan_delta_ref/(-Im D(reference))`,
`eps_inf=eps_ref-strength*Re D(reference)` and
`εr(f)=eps_inf+strength*D(f)`.
This is a continuum of nonnegative Debye relaxation strengths. Its rolloffs
control the asymptotes; **they are not a measured validity interval**.
Frequency scaling and log-magnitude evaluation avoid avoidable overflow.
Numerical stability at extreme finite inputs does not imply physical validity
at those frequencies. No DC conductivity or magnetic dispersion is included.

## Strict material JSON

`dielectric_to_dict(model)` and `dielectric_from_dict(value)` use exactly:

```json
{
  "schema": "sipi.dielectric/1",
  "kind": "wideband",
  "parameters": {
    "eps_ref": 4.0,
    "tan_delta_ref": 0.02,
    "reference_hz": 1000000000.0,
    "low_hz": 1000.0,
    "high_hz": 1000000000000.0
  }
}
```

Kinds are `constant`, `debye`, `wideband`, `table`. `parameters` contains every
declared constructor field, including defaults, and no extras; array fields
are JSON arrays. Unknown schema/kind/keys or missing fields are rejected.
These are material inputs, not an extended cross-section document: existing
`sipi.cross-section/1` and `/2` remain unchanged. A caller stores the layer-name
mapping and geometry alongside these material documents; the browser UI does
not yet load this new material schema.

## Extraction and network output

`dispersive_line(section, frequency, materials=..., **mesh_options)` accepts a
mapping from existing layer names to these model objects. Unspecified layers
retain their section's constant eps_r/tan_delta. Unknown names, unsupported
models, frequency errors and out-of-table samples fail before meshing. The mesh
is generated once; vacuum C0 is solved once. Each frequency gets a new complex
electrostatic solve with the actual per-element permittivity, including both
field redistribution and dielectric loss in heterogeneous layers.

`DielectricSweep` records copied read-only `frequency`, signal `names`,
`C_complex` of shape `(F,N,N)`, `C0` and external `L=mu0*eps0*inv(C0)` of shape
`(N,N)`, and a read-only mapping of sampled `layer_permittivity`. `C` is the
real part in F/m; `G=-2*pi*f*Im(C_complex)` is S/m. `network(length=..., R=...,
z_ref=50)` delegates to the existing full-matrix RLGC solver. R is mandatory;
no symmetric-pair averaging or material-dependent scaling of vacuum L occurs.

This is a quasi-TEM approximation, not a full-wave dispersion solver. It does
not extract conductor resistance, skin/proximity effect, copper roughness,
internal conductor inductance or radiation. Causal material formulas do not
by themselves certify a finite sampled network's time-domain causality or an
actual laminate's behavior. Material fitting and measurement validation remain
separate work. General mixed-mode conventions and Touchstone output follow
the [network contract](network.md).

## Validation and reproduction

```sh
python -m pytest -q -s tests/sipi/test_dielectric.py
```

The tests preserve the following distinct gates:

- Exact single/multiple Debye values, DC/high-frequency limits, wideband
  calibration, table endpoints/interpolation and input/schema rejection: 1e-12.
- Existing constant-material C/L/G reproduction and homogeneous
  `C_complex=εr(f)*C0`: relative 1e-10. The uniform complex-TEM scalar ABCD
  reference, reciprocity and passivity use absolute 1e-10.
- Independent scikit-rf 2.2.0 `MLine.analyse_dielectric`: complex permittivity
  relative 1e-12; observed maximum 1.82e-16 over DC and 1 Hz–1 PHz samples.
  These are formula comparisons, not a claim that PCB quasi-TEM remains valid
  across that interval.
- Independent scikit-fem 12.0.2 complex P1 assembly/solve on the same layered,
  asymmetric two-conductor mesh at 1 MHz, 100 MHz, 10 GHz: complex C relative
  1e-9; observed maximum 5.75e-15. Shared mesh agreement does not replace
  discretization convergence.
- A finite-thickness, inhomogeneous coupled microstrip at 1 MHz/1 GHz/100 GHz
  changes complex C by 0.498% under halved edge/far/grade settings, below the
  preregistered 1% gate. This checks mesh sensitivity, not full-wave accuracy
  or convergence of the finite box size.

The reference tools are test-only, never imported or bundled by shipped code.
Cross-check records use `openphysics.crosscheck/1`; set
`OPENPHYSICS_CROSSCHECK_DIR` to retain them. Existing acceptance thresholds and
goldens are unchanged. Initial extreme-frequency tests exposed `hypot` overflow;
normalizing before squares and evaluating log magnitude directly fixed those
tests without relaxing criteria. Windows/macOS and installed-wheel support
still depend on the required CI of the exact revision.

Sources: C. Svensson and G. E. Dermer, *Time domain modeling of lossy
interconnects*, IEEE Transactions on Advanced Packaging 24(2), 191–196 (2001);
A. R. Djordjevic et al., *Wideband frequency-domain characterization of FR-4
and time-domain causality*, IEEE Transactions on EMC 43(4), 662–667 (2001).
The independent formula is also documented in
[scikit-rf's MLine implementation](https://github.com/scikit-rf/scikit-rf/blob/v2.2.0/skrf/media/mline.py).
