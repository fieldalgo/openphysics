# Reproducible frequency-dependent line models

**English** | [한국어](../../locales/ko/pages/packages/sipi/line_model.md)

[Geometry JSON](design.md) · [Dielectrics](dielectrics.md) ·
[Conductor loss](conductor.md) · [Networks](network.md)

`sipi.line_model.TransmissionLineDocument` combines geometry, layer materials,
an explicit conductor model, frequencies, line length and port reference in one
input snapshot. `analyze()` meshes **once** and uses that same geometry and
conductor ordering for dielectric C/G, conductor R/internal L and uniform-line
S. For surface conductors it also shares the vacuum C0 solve. This avoids
accidentally combining matrices from different cross-sections.

```python
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.dielectric import WidebandDielectric
from sipi.line_model import TransmissionLineDocument

geometry = CrossSectionDocument(
    coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                       thickness=50e-6, eps_r=4),
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1))
model = TransmissionLineDocument(
    geometry, [1e9, 4e9, 10e9],
    materials={'substrate': WidebandDielectric(4, .02, 1e9)},
    conductor=dict(kind='surface', conductivity=58e6, ground_thickness=35e-6,
                   relative_permeability=1, roughness_rms=1e-6),
    length=.03, z_ref=50)
saved = model.dumps()  # text; writing a file is the caller's decision
result = TransmissionLineDocument.loads(saved).analyze()
result.R, result.L, result.G, result.C
result.network.s, result.network.mixed_mode().s
touchstone = result.network.touchstone()
```

The example is illustrative, not a measured material/copper fit. A runnable
version is [`frequency_line.py`](../../../examples/sipi/frequency_line.py).

## Input schema

`sipi.transmission-line/1` has **exactly** these required fields:

| Field | Contract |
|---|---|
| `schema` | Literal `sipi.transmission-line/1` |
| `cross_section` | Existing strict `sipi.cross-section/1` or `/2` object; lengths in metres |
| `frequency_hz` | Nonempty, strictly increasing finite real array, >=0; surface metal requires >0 |
| `materials` | Object keyed by existing layer names, each a strict `sipi.dielectric/1` record; other layers use their constant values |
| `conductor` | Explicit perfect or surface record below; there is no default metal |
| `length_m` | Finite real length >=0 |
| `reference_ohms` | One finite positive real reference for every single-ended port |

Perfect metal is exactly `{"kind":"perfect"}`. It sets R and internal L to
zero. A surface record requires **all** of `kind="surface"`, `conductivity`
(S/m), `ground_thickness` (m), `relative_permeability` and `roughness_rms` (m),
including explicit values for 1 and 0. It retains the conductor model's skin,
good-conductor, finite-thickness and flux gates. DC does not silently switch
to another model. Empirical roughness adjusts resistance, not causal reactance.

Unknown versions/fields, missing fields, duplicate JSON keys at any nesting
level, nonfinite or boolean numbers, invalid material tables and unsupported
frequency/skin-depth combinations fail before meshing. `materials={}` is an
explicit choice to retain constant layer values. Constitutive samples are
preflighted over **all** requested frequencies.

Construction copies all inputs. `to_dict()` and `.cross_section` return fresh
objects; changing them cannot change the stored input. Geometry defaults are
resolved into explicit `edge_size`, `far_size`, `grade` and `min_angle` at
construction and saved. This fixes the requested settings, not results across
future solver/library versions. Save the engine revision and environment with
an engineering report when reproducing a calculation across installations.
This schema stores inputs, not calculated results. It does not replace or
change the older geometry JSON contracts.

Version 2 (`sipi.transmission-line/2`) keeps these top-level fields and replaces
only the surface `roughness_rms` with an explicit smooth/Hammerstad/causal-Huray
object. Its [roughness contract](roughness.md#versioned-line-input) defines all
fields. Version 1 and the constructor default remain unchanged; saved versions
are preserved.

## Results

`TransmissionLineResult` retains `.input_json`, read-only `.mesh_settings`,
`.dielectric`, `.conductor` (None for perfect metal), and `.network`.
`.frequency` and `.names` specify the sample/conductor order. R/L/G/C have
shape `(F,N,N)` and are read-only, in ohm/m, H/m, S/m and F/m respectively.
L includes external **plus** internal inductance exactly once. Layer complex
permittivity samples and surface-current error/skin depth remain available
through the extraction objects. The network retains its near-then-far port
order, mixed-mode and single-ended Touchstone export contracts.

The shared solver reuses the existing material/surface algorithms through
private mesh-level helpers; the standalone extraction APIs remain available.
The input model controls identity of geometry, mesh and ordering. It does not
automatically establish mesh convergence, box independence, material accuracy,
surface-perturbation accuracy or quasi-TEM validity. A separately constructed
result object is not evidence that these checks were performed.

## Verification

The checks in `tests/sipi/test_line_model.py` require:

- JSON roundtrip RLGC relative agreement within 1e-12 and S absolute 1e-10;
  preserved tapered geometry v2, isolated input copies and resolved settings.
- Agreement with separately called public dielectric/conductor extraction:
  RLGC relative 1e-10, S absolute 1e-10; the same C0 and conductor ordering.
- One mesh construction for the two extractions; perfect-metal DC connection,
  independent scalar ABCD comparison, reciprocal/passive S within 1e-10.
- Rejection of malformed, duplicate, nonfinite, out-of-table and invalid
  conductor inputs before meshing; explicit metal choice is mandatory.

The new 23 checks plus the 56 dielectric/conductor checks passed together on
Linux, Python 3.12.14, NumPy 2.5.4 and SciPy 1.18.1 (2026-10-30), with the
independent reference tools required. Review then exposed a rectangular-v2 input
being normalized to v1; preserving the input schema fixed it, and all 24
input-model checks passed. The extraction pages state their
analytical and external-reference evidence. This composition adds no new
physical accuracy claim, runtime dependency or browser/EXE deployment.

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_line_model.py tests/sipi/test_dielectric.py tests/sipi/test_conductor.py
```
