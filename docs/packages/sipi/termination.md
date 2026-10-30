# Terminated networks and frequency crosstalk

**English** | [한국어](../../locales/ko/pages/packages/sipi/termination.md)

[Overview](overview.md) · [Line networks](network.md)

`terminate_network` solves terminal voltages and currents for a `LineNetwork`
with explicitly named Thevenin sources and finite passive source/load impedances.
`loaded_crosstalk` uses the same solution for frequency-dependent NEXT and FEXT.
Both are Python APIs in `sipi.termination`; no UI or JSON interface is implied.

```python
from sipi import rlgc_network
from sipi.termination import terminate_network

network = rlgc_network([0, 1e6, 1e9], R=[[10]], L=[[400e-9]],
                       G=[[0]], C=[[100e-12]], length=1)
response = terminate_network(network, source_voltages={'near:1': 1},
                             terminations={'near:1': 50, 'far:1': 100})
# DC: 10 ohm line + 50 ohm source + 100 ohm load.
# response.voltage[0] = [110/160, 100/160] V
# response.current[0] = [1/160, -1/160] A, into the network at both ends.
```

## Inputs and results

- The network uses finite S and positive, real, frequency-independent reference
  impedances. It can be single-ended or mixed-mode. Loads are independent in the
  supplied basis: modal loads do not automatically represent physical terminal loads.
- `source_voltages` is a nonempty mapping of explicit port names to finite complex
  scalars or length-F arrays in V. Several simultaneous sources are supported.
  Unspecified sources are zero. Zero excitation is valid.
- `terminations` maps port names to finite complex scalars or length-F arrays in
  ohms. Real parts must be >=0. Missing ports use their own `z_ref`, including
  source ports. Zero is a short/ideal voltage source. Infinity/open circuits,
  negative resistance and coupled load matrices are unsupported.
- Boolean/string numbers, unknown names, wrong array shapes and nonfinite input
  are rejected. Frequency values and ordering come from the network.
- Results retain copied, read-only network and input arrays. `a`, `b`, `voltage`,
  `current`, `source_voltages`, `terminations` have shape `(F, ports)`.
  `condition_number`, `kvl_residual`, `wave_residual` have shape `(F,)`.
  `frequency`, `port_names`, `basis` describe the solved network.
- Voltages/currents use exp(+j omega t), peak phasors; currents point **into** the
  network. At DC, entries represent constant complex amplitudes; physical DC
  inputs should be real. Average power uses Re(V I*) at DC and Re(V I*)/2 at
  positive frequencies. This avoids halving the dissipation of a DC resistor.
- `network_power`, `termination_power`, `source_power` are read-only `(F,)` W
  arrays. Source power equals network power plus dissipation in every source/load
  impedance. Reactive power is not reported. Arbitrary externally supplied S can
  be active: a negative network power is not clipped or treated as passivity proof.
  A power overflow raises `ValueError` when that property is accessed.

## Circuit equations and failure checks

For real reference R, b=S a, V=sqrt(R)(a+b), I=(a-b)/sqrt(R).
A Thevenin source obeys Vs=V+Zt I. Therefore

```text
Gamma = (Zt-R)/(Zt+R)
a_source = sqrt(R) Vs/(Zt+R)
(I - diag(Gamma) S) a = a_source
```

The implementation solves this system at each frequency. Its 2-norm condition
number must be <=1e12. Singular, ill-conditioned or nonfinite systems raise
`ValueError`; no partial solution is returned. The reported normalized residuals
check Vs-V-Zt I and a-Gamma b-a_source, each relative to the maximum infinity
norm of its terms. They must be <=1e-10. Zero excitation has zero residual.
A small residual is a backward-error check, not a guarantee of forward accuracy
for a condition number close to the limit. Extremely large impedances can lose
accuracy through cancellation and fail this check; they are not an open circuit API.

## Explicit NEXT and FEXT

```python
from sipi.termination import loaded_crosstalk
# coupled_network has four ports near:1, near:2, far:1, far:2.
# result = loaded_crosstalk(coupled_network, aggressor='near:1',
#     near_victim='near:2', far_victim='far:2',
#     terminations={'near:1': 25+10j, 'near:2': 50, 'far:1': 50, 'far:2': 100})
```

The three names must be distinct. The caller supplies their physical meaning;
port ordering or geometry is not inferred. A 1 V peak Thevenin source drives only
`aggressor`. The returned `Crosstalk.response` holds all waves and terminal values.
`next_ratio` and `fext_ratio` divide victim **terminal voltage** by the aggressor's
actual **incident voltage**, sqrt(R_aggressor) a_aggressor. They are complex,
read-only length-F arrays, dimensionless, not divided by source open-circuit
voltage or total aggressor voltage. Incident magnitude <=1e-14 V is rejected.

With matched ports and equal references these ratios equal the corresponding
S entries. Unequal references include sqrt(R_victim/R_aggressor); mismatched
loads include all reflections. Use `20*log10(abs(ratio))` for amplitude dB,
with -infinity at zero. These are frequency ratios, not time-domain peak noise,
rise-time-dependent crosstalk, eye diagrams or a guarantee of physical port placement.

## Validation and reproduction

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_termination.py
python examples/sipi/loaded_crosstalk.py
```

The fixed criteria in the tests are:

| Check | Independent reference | Criterion |
|---|---|---|
| DC terminal V/I and dissipated power | 10 ohm series line, 50 ohm source, 100 ohm load | relative 1e-10 |
| Complex source and load, 1 kHz–5 GHz | scalar hyperbolic ABCD solution | relative 1e-10 with 1e-14 V / 1e-16 A absolute floor |
| Coupled-line matched NEXT/FEXT | separate scalar even/odd ABCD modes | absolute 1e-10 |
| Nonreciprocal 2/4-port, unequal references, multiple sources | scikit-rf 2.2.0 s2z followed by an independent impedance circuit solve | relative infinity-norm V/I error <=1e-10 |
| Power and residuals | circuit conservation; source=network+termination | relative 1e-10 |

The reference is BSD-3-Clause, lazily imported only in tests; it adds no shipped
runtime dependency. On Linux/Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1, the synthetic
2/4-port comparison's largest relative V/I difference was 4.23e-16 (2026-10-30).
This validates the network/circuit arithmetic, not extracted material accuracy,
measurement agreement, a frequency bandwidth, or a new spatial discretization.
Input network mesh/domain/material limitations still apply. Open loads, coupled
termination networks, time-domain conversion, nonlinear drivers and vias are not
implemented here. See the executable [coupled example](../../../examples/sipi/loaded_crosstalk.py).
