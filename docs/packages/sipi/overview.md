# sipi — signal and power integrity of PCB cross-sections

**English** | [한국어](../../locales/ko/pages/packages/sipi/overview.md)

[Documentation home](../../README.md)

`sipi` computes the per-unit-length parameters of printed-circuit-board
transmission lines from their cross-section. A cross-section is a stack of
dielectric layers with rectangular traces; `sipi` meshes it with
[meshine](../meshine/overview.md) and solves two-dimensional electrostatic
problems with the [galerkin](../galerkin/overview.md) engine. It depends on
numpy, scipy, galerkin and meshine.

```python
from sipi import CrossSection, Layer, Trace

cs = CrossSection(
    layers=[Layer("FR-4", 0.2e-3, eps_r=4.3, tan_delta=0.02),   # from y = 0 upward
            Layer("air", 4e-3)],
    traces=[Trace("sig", x=0.0, width=0.35e-3, y=0.2e-3, thickness=35e-6)],
    width=8e-3)                       # box from x = -4 mm to +4 mm
line = cs.analyze()
line.z0, line.eps_eff, line.delay     # ohm, -, s/m
line.C, line.L, line.G(1e9)           # F/m, H/m, S/m matrices
```

All lengths are in metres and all results are per metre of line.
[`examples/sipi/pcb_lines.py`](../../../examples/sipi/pcb_lines.py) prints the
impedance of a 50-ohm-class microstrip and of an edge-coupled differential pair.

[Templates, JSON documents and target-impedance design](design.md).

## What is computed

The conductors run along z and the cross-section is small compared with the
wavelength, so the line carries a quasi-TEM wave. For N signal conductors:

| Quantity | Meaning | How |
|---|---|---|
| `C` | Maxwell capacitance matrix (F/m) | Electrostatics with the real dielectrics; `C[i, j]` is the charge on conductor i with conductor j at 1 V and the rest at 0 V |
| `C0` | The same matrix in vacuum (F/m) | Every dielectric replaced by vacuum |
| `L` | Inductance matrix (H/m) | `L = mu0 eps0 inv(C0)` |
| `C_loss`, `G(f)` | Dielectric loss (F/m), conductance (S/m) | A lossy layer has `eps0 eps_r (1 - j tan_delta)`; the solved capacitance is `C - j C_loss` and `G = 2 pi f C_loss` |

For a single line, `z0 = sqrt(L / C)`, `eps_eff = C / C0`, `phase_velocity` and
`delay` (s/m) are properties, and `loss_tangent()` is the effective
`C_loss / C`. For two lines, `even_odd()` gives `z_even`, `z_odd`,
`z_diff = 2 z_odd`, `z_common = z_even / 2` and both modal `eps_eff`; it averages
the two self terms, which differ by the discretization error on a mesh that is
not mirror-symmetric, and refuses a pair whose self terms differ by more than
`rtol` (1 %). `modes()` gives the modal effective permittivities and voltage
eigenvectors of any N-conductor line.

The capacitance entries are the discrete energy `eps0 V_i^T K V_j`, so the
matrices are symmetric and the conforming finite-element solution approaches
the exact `C` from above.

## Model

- `Layer(name, thickness, eps_r=1, tan_delta=0)`: layers stack from `y = 0`
  upward. `tan_delta` is frequency-independent, so `G` is linear in frequency.
- `Trace(name, x, width, y, thickness=0, ground=False)`: `x` is the centre, `y`
  the bottom face. A zero-thickness trace is a strip on the line `y`; a trace
  with thickness is a solid conductor that the mesh leaves out. `ground=True`
  makes it a reference conductor at 0 V (for example a coplanar ground).
- `CrossSection(layers, traces, width, bottom="ground", top="open", sides="open")`:
  each box side is either a ground (`"ground"`) or an insulating wall
  (`"open"`, zero normal D). Traces must lie strictly inside the box and must
  not touch each other.
- A microstrip is `bottom="ground"` with a substrate and an air layer; a
  stripline adds `top="ground"`.

`analyze()` accepts the mesh options of `mesh()`:

| Option | Default | Meaning |
|---|---|---|
| `edge_size` | smallest feature / 100 | Target edge length at trace corners, where the field is singular. Features are layer thicknesses, trace widths and thicknesses, and gaps between traces. |
| `grade` | 0.15 | Growth of the edge length per unit distance from the traces |
| `far_size` | max(width, height) / 24 | Largest edge length |

`mesh()` returns a `MeshedCrossSection` (galerkin mesh, per-triangle `eps_r` and
`tan_delta`, conductor node sets) for inspection. `line_parameters()` and
`capacitance_matrix()` accept any galerkin mesh with node sets, for example a
coaxial mesh built directly with meshine.

## Accuracy and checks to run

Two errors remain in every result and both are the user's to check:

1. **Discretization.** Halve `edge_size`, `grade` and `far_size` together and
   compare. With the default options, impedance errors on the V3–V5 geometries
   below were 0.07–0.44 %.
2. **Box truncation.** An `"open"` wall is an insulator, a `"ground"` wall a
   conductor; an open-space line lies between the two. Solve both or move the
   walls outward. For the example microstrip, doubling the box width and the
   air layer changed `z0` by 0.14 %, and open and grounded walls differed by
   0.4 %.

## Validation

`tests/sipi/test_sipi_references.py` holds these comparisons. The criteria were
fixed before the first run. Measured on 2026-10-26, Linux, Python 3.12, with
the pinned environment `tools/requirements-py312-linux.txt`.

| Case | Reference | Criterion | Measured |
|---|---|---|---|
| V1 two-layer parallel plate, insulating sides, lossy layers | Series capacitors (exact in P1) | C, C_loss, C0, L, `eps_eff`, G within 1e-9 | Passed |
| V2 coaxial line, `b/a = 3`, `eps_r = 2.2` | `C = 2 pi eps / ln(b/a)` | Error ≤ 1e-3 at the finest mesh; fitted order ≥ 1.5 | +3.9e-3, +1.8e-4, −1.1e-4 at sizes 0.2, 0.1, 0.05 mm. The sign changes because the polygonal circle and the conforming solution err in opposite directions, so the fitted order (2.5) is not a clean asymptotic rate |
| V3 zero-thickness stripline, `w/b = 0.5`, `eps_r = 4` | Cohn's exact conformal map, Z0 = 50.216 ohm | Error ≤ 0.5 % at the finest of three meshes; decreasing | −1.0 %, −0.24 %, −0.061 % |
| V4 zero-thickness coupled stripline, `w/b = 0.4`, `s/b = 0.3`, `eps_r = 3.5` | Cohn's exact even/odd maps, 68.591 / 51.077 ohm | Each within 0.5 % | −0.21 % / −0.35 % |
| V5 zero-thickness microstrip, `w/h` 0.5, 1, 2 and `eps_r` 4.3, 9.8 | Hammerstad and Jensen (1980), quoted accuracy 0.01–0.03 % (Z0), 0.2 % (`eps_eff`) | Z0 and `eps_eff` within 1 % with open and with grounded walls; the two within 1 % of each other | Z0 −0.22 % to −0.57 %, `eps_eff` −0.27 % to +0.30 %; walls 0.16–0.33 % apart |

The free-space impedance in every reference is `sqrt(mu0 / eps0)` = 376.730 ohm.
Textbook forms with 120 pi = 376.991 ohm are 6.9e-4 higher and would bias these
comparisons by that amount.

References: S. B. Cohn, "Characteristic impedance of the shielded-strip
transmission line," *IRE Trans. MTT* 2(2), 1954, and "Shielded coupled-strip
transmission line," *IRE Trans. MTT* 3(5), 1955; E. Hammerstad and Ø. Jensen,
"Accurate models for microstrip computer-aided design," *IEEE MTT-S Digest*,
1980.

## Not implemented

- Conductor loss `R` (skin effect, surface roughness). `R` is not returned.
- Frequency-dependent dielectrics (for example Djordjevic–Sarkar); `tan_delta`
  is constant.
- S-parameters, Touchstone files, time-domain responses.
- 3D structures: vias, plane resonances, power-delivery networks.
- Layout import (Gerber, ODB++, IPC-2581), non-rectangular conductors in
  `CrossSection`, JSON documents and a Studio view.
- Magnetic substrates: `L` assumes `mu = mu0` everywhere.
