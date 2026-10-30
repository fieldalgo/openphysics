# Causal conductor surface roughness

**English** | [한국어](../../locales/ko/pages/packages/sipi/roughness.md)

[Surface extraction](conductor.md) · [Frequency-line JSON](line_model.md)

`sipi.roughness.CausalHuray` describes spherical surface populations using
explicit radii in metres and full-sphere surface-area ratios. It modifies both
resistance and reactance of the good-conductor half-space. All conductor
surfaces share this model; no individual top/bottom face selection is implied.

```python
from sipi.roughness import CausalHuray
from sipi.conductor import surface_impedance

roughness = CausalHuray(radii_m=[.5e-6, 1.5e-6], surface_ratios=[1.2, .3])
zs = surface_impedance([1e9, 4e9, 10e9], conductivity=58e6, roughness=roughness)
```

The same `roughness=` argument is accepted by `surface_conductor_loss`.
`ConductorLoss.roughness_factor` remains the **real resistance ratio**,
`Re(Zrough)/Re(Zsmooth)`, rather than the complex multiplier. Existing
`roughness_rms` still uses the empirical Hammerstad resistance-only correction;
nonzero RMS and a `CausalHuray` object cannot be combined.

## Parameters and formulation

There must be 1..64 matching finite real populations: radius `a > 0` and
`SR >= 0`, where `SR = N*4*pi*a^2/Aflat`. Ratios describe the entire spherical
surface, not projected disc area. The base matte/flat area ratio is fixed to
one. Booleans, complex values, nulls and nonrepresentable total saturation
are rejected. Inputs are copied into immutable tuples. Zero-area populations
are permitted and contribute nothing. No Ra, Rq, Rz or packing conversion is
inferred. `factor(skin_depth)` takes a nonempty positive finite real 1D array
in metres and preserves its order.

With `s=j*omega`, exp(+j omega t), `mu=mu0*mu_r` and positive skin depth:

```text
delta = 1/sqrt(pi*f*mu*sigma)
q_i = sqrt(s*mu*sigma*a_i^2) = (1+j)*a_i/delta
H(s) = 1 + sum_i (1.5*SR_i)*q_i/(1+q_i)
Zrough = sqrt(s*mu/sigma)*H(s)
```

The square root is its principal branch. The independently specified real
loss ratio is `1 + sum_i 1.5*SR_i/(1+delta/a_i+delta^2/(2*a_i^2))`.
Multiplying smooth impedance by that **real** ratio would miss the reactance.
Implementation evaluates real/imaginary impedance corrections separately to
avoid cancellation, and normalizes radius/depth before squaring to avoid
overflow. Mathematically H approaches 1 at low frequency and
`1+1.5*sum(SR)` at high frequency. The added low-frequency inductance per
square approaches `sum(1.5*SR*mu*a)`.

This formulation is attributed to J. Eric Bracken, *A Causal Huray Model for
Surface Roughness*, DesignCon 2012. Its complex multiplier, sphere coefficients
and corner frequency are explicitly given in Yong Wang and Scott Langdon,
[FDTD Simulation of Multilayer-Coated and Rough Surface Metals Using Surface
Impedance Method](https://zh.remcom.com/hubfs/Blog%20Images/Remcom_ArbitrarilyShapedThinResistiveSheets_Presentation_ACES2019.pdf),
ACES 2019, slide 6. That presentation's `omega_i=2/(a_i^2*mu*sigma)` gives
the same q above. This implementation uses the stated base-area-one case.
No source code, figures or fitted measurements from that work are distributed.

## Versioned line input

Keep existing `sipi.transmission-line/1` unchanged. Select
`schema='sipi.transmission-line/2'` explicitly in the Python constructor or
JSON. Version 2 has the same top-level fields, geometry/material contracts and
perfect-metal record. Its surface record replaces `roughness_rms` with exactly
one `roughness` object:

| Kind | Exact required fields |
|---|---|
| Smooth | `{"kind":"smooth"}` |
| Empirical Hammerstad | `{"kind":"hammerstad","rms_m":1e-6}` |
| Causal Huray | `{"kind":"causal-huray","radii_m":[5e-7,1.5e-6],"surface_ratios":[1.2,0.3]}` |

`rms_m` is a finite nonnegative real scalar. Surface conductivity, ground
thickness and relative permeability remain mandatory. Missing/unknown fields,
version-mixed fields, duplicate keys and invalid populations fail before
meshing. `dumps()` preserves the selected input version and resolved mesh.
There is no automatic migration or result serialization. The constructor still
defaults to version 1. See the runnable
[`causal_roughness.py`](../../../examples/sipi/causal_roughness.py).

## Validation and limits

`tests/sipi/test_roughness.py` checks the implementation independently using
SciPy quadrature of a continuum of positive first-order relaxation responses:

```text
q/(1+q) = (2/pi) integral_0^(pi/2) z/(z+tan(theta)^2) dtheta
z = s*mu*sigma*a^2
```

The test does not evaluate another copy of the closed-form square root. For
`omega*mu*sigma*a^2 = 1e-6..1e6` it requires relative and absolute complex
agreement within 1e-10. Additional criteria are real-loss identity and
conductivity/permeability/radius scaling within 1e-12, zero-area smooth
identity, low/high-frequency limits, finite extreme inputs, strict JSON,
input isolation and rejection before meshing.

The geometry checks use the exact coax surface factor `(1/a+1/b)/(2*pi)`:
radial cells 64/128/256, angular cells 256, a=.5 mm and b=2 mm; rough R and
internal L errors must decrease and end below 1%. The coupled microstrip
example halves edge/far/grade 5 µm/.2 mm/.1 to 2.5 µm/.1 mm/.05; R and
internal-L changes must be below 5%, with integrated-current error below 5%.
JSON replay requires RLGC relative 1e-12 and S absolute 1e-10; separate
surface extraction agreement, S reciprocity and passivity use 1e-10.
Version-2 smooth/Hammerstad results must reproduce version 1 exactly.

On Linux with Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1 (2026-10-30),
all 55 new checks and the complete related selection of 250 checks passed
with no skips. The executable example at 1/4/10 GHz returns resistance ratios
1.26314496/1.57338324/1.85601051 and surface-current error 0.03224846.
These are illustrative input results, not a measured foil fit.

These checks test the stated constitutive law and surface-current assembly.
They do not establish agreement with measured foil/coupon data or a commercial
field solver. SciPy's existing BSD-3-Clause quadrature implementation is the
numerical reference; no new dependency or binary is added.

The surface adapter's good-conductor, finite-thickness, skin-depth and flux
gates are unchanged. They do not prove that roughness scale is small enough
relative to conductor dimensions, curvature or gaps; the homogenized surface
model and perturbation still need physical justification. Low-frequency
limits above are mathematical checks, **not permission to use the surface
adapter at DC**. Finite-metal diffusion is a separate smooth-metal model and
receives no roughness multiplier. Unequal face roughness, arbitrary base area,
parameter fitting, resolved 3D texture, time-domain propagation and measured
accuracy are outside this contract. A causal conductor law alone does not
certify causality of an arbitrary dielectric model or full line input.

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_roughness.py tests/sipi/test_conductor.py tests/sipi/test_line_model.py
```
