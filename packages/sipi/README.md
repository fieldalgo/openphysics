# sipi — signal and power integrity of PCB cross-sections

[Documentation](../../docs/packages/sipi/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Per-unit-length parameters of printed-circuit-board transmission lines from
their cross-section: layered dielectrics, rectangular traces, quasi-static
(quasi-TEM) analysis on the galerkin finite-element engine with meshes from
meshine. Depends on numpy, scipy, galerkin and meshine.

```python
from sipi import CrossSection, Layer, Trace

cs = CrossSection(
    layers=[Layer("FR-4", 0.2e-3, eps_r=4.3, tan_delta=0.02), Layer("air", 4e-3)],
    traces=[Trace("sig", x=0.0, width=0.35e-3, y=0.2e-3, thickness=35e-6)],
    width=8e-3)
line = cs.analyze()
line.z0, line.eps_eff        # about 50.8 ohm and 3.13
line.C, line.L, line.G(1e9)  # per-metre matrices
```

It computes the capacitance, inductance and dielectric-conductance matrices,
single-line impedance, effective permittivity and delay, and coupled-line
even/odd modes. Results are checked against exact parallel-plate, coaxial and
Cohn stripline solutions and the Hammerstad–Jensen microstrip formulas; the
[documentation](../../docs/packages/sipi/overview.md) lists the measured errors
and the checks a user should run (mesh refinement and box truncation).

Power integrity: `PowerPlane` solves the DC voltage drop (IR drop) on a copper
plane fed by regulators and loaded by devices, checked against exact strip,
annulus and two-pad references.

Not implemented: conductor loss, frequency-dependent dielectrics, S-parameters
and Touchstone files, AC PDN impedance, vias, several layers and layout import.

Licensed under Apache-2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE).
