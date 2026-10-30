# High-frequency conductor surface loss

**English** | [한국어](../../locales/ko/pages/packages/sipi/conductor.md)

[Cross-sections](overview.md) · [Uniform-line networks](network.md)

`sipi.conductor.surface_conductor_loss` extracts conductor R and high-frequency
internal L from the signal **and reference** surfaces of a finite-thickness
cross-section. This is a leading-order surface-impedance perturbation of the
perfect-conductor field. It does not solve current diffusion inside the metal.
Existing `CrossSection.analyze()` continues to return external L and dielectric
C/G; it does not silently add conductor loss.

```python
import numpy as np
from sipi import coupled_microstrip
from sipi.conductor import surface_conductor_loss

section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                            thickness=50e-6, eps_r=4)
mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
f = np.array([1e9, 4e9, 10e9])
loss = surface_conductor_loss(section, f, conductivity=58e6,
                             ground_thickness=35e-6, **mesh)
dielectric = section.analyze(**mesh)
network = loss.network(C=dielectric.C, G=np.zeros((2, 2)), length=.03)
loss.R, loss.L_internal, loss.skin_depth, loss.factors.current_error
```

The example uses a smooth metal and lossless, frequency-independent dielectrics.
All values are SI. A runnable example is
[`conductor_loss.py`](../../../examples/sipi/conductor_loss.py).

## Contract and validity

- Frequency is a nonempty, strictly increasing one-dimensional Hz array with
  **f > 0**. Conductivity (S/m), relative permeability and reference-plane
  `ground_thickness` (m) must be positive finite real numbers, not booleans.
  There is no implicit copper choice or reference-plane thickness.
- All signal and reference conductors share the specified metal. The exterior
  is nonmagnetic. `relative_permeability` applies to the metal surface model.
- Every trace must have positive thickness. The largest skin depth must be at
  most one fifth of **each** trace thickness, bottom/top face width, reference
  thickness and box width. Also require `sigma/(omega*eps0) >= 1000`.
  These necessary conditions do not bound corner curvature, proximity,
  perturbation, truncation or discretization errors. Sharp corners still need
  refinement, even when the thickness/skin-depth check passes.
- `roughness_rms` defaults to zero. When positive, Hammerstad's empirical
  factor `1 + (2/pi)*atan(1.4*(Rq/delta)**2)` multiplies **R only**. Smooth-metal
  reactance is retained. This is not a causal broadband roughness model, a
  measured surface fit, or a correction to the geometry. Alternatively,
  [causal Huray roughness](roughness.md) changes both R and internal L using
  explicit sphere radii/area ratios; choose `roughness=CausalHuray(...)`.
  Gradient and Groisse models are not implemented.
- Invalid material/skin inputs are rejected before meshing. A discrepancy of
  more than 0.05 in the integrated unit-current matrix raises `ValueError`
  requesting refinement. This flux check is **not a 5% resistance guarantee**.
  Check R itself under refinement and separately enlarge the outer box.

`ConductorLoss` contains copied, read-only frequency, `skin_depth` (m),
`roughness_factor` (real resistance ratio), `R` (ohm/m) and `L_internal` (H/m). R and L are `(F,N,N)`;
off-diagonal terms are retained. `.factors` exposes C0, the `(N+1,N,N)`
surface integrals and `(N+1,N)` integrated currents: one surface group per
signal in `.names` order, followed by **all reference conductors together**.
User-created result objects validate shape and finiteness; they are not proof
that a solve was performed or that the physical model applies.

`.network(C=..., G=..., length=..., z_ref=50)` uses this R and
`L_external + L_internal` with the existing RLGC network solver. The caller
must supply C/G for the **same geometry, conductor order and frequencies**.
Shapes alone cannot establish that match. This API does not import measurements,
alter geometry JSON, add a browser screen or package an executable.

## Method

The smooth half-space impedance, with exp(+j omega t), is

```text
delta = 1 / sqrt(pi f mu sigma)
Zs = (1+j) sqrt(pi f mu / sigma)
```

Solve a vacuum electrostatic potential basis V and its energy capacitance C0.
For the unit longitudinal signal-current vector i, magnetic/electric duality
gives the surface current `K = eps0 d_n(V) inv(C0) i`, where n points out of
the dielectric into the metal. Tangential magnetic field follows the same
vacuum geometry, not a dielectric-weighted field. Integrate **every** signal
and return boundary:

```text
A_ij = integral K_i K_j ds
R(f) = Re(Zs(f)) A
L_internal(f) = Im(Zs(f)) A / (2 pi f)
L_external = mu0 eps0 inv(C0)
```

The Gram form preserves reciprocal positive-semidefinite loss, and includes
the leading-order perfect-conductor return/proximity distribution. It does
not resolve the redistribution caused by finite conductivity. P1 element
gradients are evaluated on dielectric boundary edges; internal zero-thickness
strips are rejected. The lower-level `surface_current_factors(mesh, signals,
ground)` allows custom dielectric-only meshes such as an annulus. It reports
the flux discrepancy without enforcing the cross-section adapter's 5% gate.
An open electric boundary is insulated in this dual problem, not infinity.

## Validation and limits

`tests/sipi/test_conductor.py`, Linux, Python 3.12.14, NumPy 2.5.4,
SciPy 1.18.1, 2026-10-30. Criteria were set before the tests.

| Check | Criterion | Result |
|---|---|---|
| Parallel plate, width 2 mm, height 1 mm | Each surface factor 1/width and integrated currents ±1, 1e-10 | Passed; total factor 1000 /m |
| Coax a=.5 mm, b=2 mm; radial cells 64/128/256, angular 256 | Total factor approaches `(1/a+1/b)/(2pi)`, finest error <1% | 3.3833%, 1.7224%, 0.8681% |
| Coupled microstrip above, all three mesh settings halved | R matrix max change / max fine R <5%; flux <5% | 4.08%; fine flux 2.22% |
| Coarser coupled mesh 10 µm/.4 mm/.2 | Reject flux >5% | 5.83%, rejected |
| Smooth Rs and skin depth vs scikit-rf 2.2.0 | Relative difference <1e-12 | 2.00e-15 and 2.22e-15 |
| R/L reciprocity, PSD and resulting S reciprocity/passivity | 1e-10 | Passed |

The scikit-rf check is an independent **half-space law** comparison, not a
whole-PCB field-solver or roughness comparison. It runs only in tests using
the already inventoried BSD-3-Clause dependency; no runtime dependency or
third-party binary is added. The plate/coax references independently check the
geometry integrals. The finite-thickness PCB check demonstrates convergence
for that case, not measured loss accuracy or a universal error bound.

Missing: DC/low-frequency transition, interior skin/proximity diffusion,
different metals per surface, finite reference-plane redistribution,
measured-coupon calibration and full-wave radiation.
Do not extrapolate this model to DC or substitute it for an AC PDN solver.

References: E. Hammerstad and Ø. Jensen, “Accurate models for microstrip
computer-aided design,” IEEE MTT-S Digest, 1980 (empirical roughness factor);
standard good-conductor surface impedance and quasi-TEM electric/magnetic
duality, checked here by the stated plate and coax limits.

Run the related validation with the test extra installed:

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_conductor.py
```

[Shared-mesh frequency-line input](line_model.md) combines this extraction with
the other material/conductor components and saves the complete input as JSON.
