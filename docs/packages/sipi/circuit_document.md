# Saved circuit inputs

**English** | [한국어](../../locales/ko/pages/packages/sipi/circuit_document.md)

[Overview](overview.md) · [Terminations](termination.md) · [Touchstone](touchstone.md)

`CircuitDocument` in `sipi.circuit_document` stores the network definition,
excitation and all explicit source/load impedances in strict `sipi.circuit/1`
JSON. It runs the existing line and termination engines. It introduces no new
material model, file I/O, network access or UI.

```python
from sipi.circuit_document import CircuitDocument

network = dict(kind='rlgc', frequency_hz=[0, 1e6, 1e9],
    R=[[10]], L=[[400e-9]], G=[[0]], C=[[100e-12]],
    length_m=1, reference_ohms=50, names=['signal'])
doc = CircuitDocument(network,
    excitation={'kind': 'sources', 'voltages': {'near:signal': 1}},
    terminations={'near:signal': 50, 'far:signal': 100})
restored = CircuitDocument.loads(doc.dumps())
result = restored.analyze()
# DC: source 1 V, total series resistance 160 ohms.
# result.response.voltage[0] = [0.6875, 0.625] V
# result.response.current[0] = [0.00625, -0.00625] A (into network)
# result.response.network_power[0] = 0.000390625 W
```

## Schema

The top-level object has exactly `schema`, `network`, `excitation`, `terminations`.
`schema` is `"sipi.circuit/1"`. Every object rejects unknown or missing fields;
JSON duplicate keys and NaN/Infinity are rejected. `from_dict` accepts JSON values,
not Python complex numbers, NumPy arrays or non-string object keys. No text is
executed. `to_dict()` returns a fresh copy; construction snapshots all inputs.

`network` is exactly one of:

| `kind` | Other required keys | Meaning |
|---|---|---|
| `rlgc` | `frequency_hz`, `R`, `L`, `G`, `C`, `length_m`, `reference_ohms`, `names` | Existing uniform-line API; explicit conductor name array, SI RLGC, scalar common reference |
| `touchstone` | `text`, `ports`, `port_names` | Embedded supported single-ended Touchstone S text; positive integer count and explicit name array, in file order |
| `transmission-line` | `document` | Complete [shared-mesh line document](line_model.md), including its schema; explicit perfect/surface conductor choice |
| `volume-line` | `document` | Complete [matched finite-metal/dielectric document](volume_line.md), including its schema and all volume mesh settings |

The first two kinds hold supplied network data. The last two retain the geometry,
materials, sampling, length and reference; they extract RLGC/S during `analyze()`.
Resolved nested defaults are saved by the original document validators. Sources
and loads are checked against the documented port names and frequency count
**before meshing**. The result's actual port order and frequency samples must
match those inputs. Input acceptance does not bypass later extraction failures.

`excitation` has one of two exact shapes:

- `{"kind":"sources", "voltages":{...}}`: nonempty map of port names to
  Thevenin peak voltages in V; multiple sources and zero excitation are supported.
- `{"kind":"crosstalk", "aggressor":"...", "near_victim":"...", "far_victim":"..."}`:
  three distinct explicit names. It uses a 1 V peak Thevenin source at the
  aggressor and the incident-voltage normalization in the termination contract.

`terminations` is a map, possibly empty, of names to finite passive impedances in
Ω. A missing port uses its own reference impedance. An absent source is zero.
Zero impedance is supported. Opens/infinity, active negative resistance, coupled
load matrices, nonlinear drivers and automatic physical pairing are unsupported.

A source or impedance value is a finite real scalar/length-F array, or
`{"real":..., "imag":...}` with both components finite real scalars or both
length-F arrays of the same shape. Booleans, strings and null are not numbers.
Scalars apply at every frequency. Canonical output writes all complex values as
explicit real/imag objects; it never serializes language-specific complex syntax.

## Execution and outputs

`CircuitDocument.from_dict(data)` and `.loads(text)` validate inputs.
`.dumps()` returns deterministic sorted JSON; `.to_dict()` copies it.
`.analyze()` returns `CircuitResult`:

- `input_json`: exact canonical input used for this calculation.
- `response`: `TerminatedNetwork`, including terminal V/I, waves, source/load
  arrays, power and residual diagnostics with the original peak/DC conventions.
- `network`: that response's network snapshot.
- `crosstalk`: `Crosstalk` for that excitation, otherwise `None`.
- `extraction`: the underlying line result for either geometry-backed kind,
  otherwise `None`; this retains RLGC and existing extraction diagnostics.

Exceptions from mesh, material, skin-resolution, conditioning and residual checks
remain failures; no partial-success fallback, extrapolation or silent model change
is introduced. This is an **input** schema, not a persistent result format.
Input identity alone does not make different engine versions bitwise identical.

## Verification and reproduction

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_circuit_document.py
python examples/sipi/circuit_document.py
```

The DC circuit above is checked against an independent series-resistor solution
at relative tolerance 1e-10. Four input routes are restored from JSON and checked
against their direct APIs: S absolute difference <=1e-12, terminal V/I relative
1e-10; the deliberately nonreciprocal four-port fixture also checks NEXT/FEXT
absolute difference <=1e-12 and unequal references. Tests cover complex arrays,
multiple sources, input isolation, duplicate/unknown fields, invalid ports before
meshing and propagation of the finite-metal skin-depth rejection.

Those direct-API checks verify composition and serialization, not independent
physics accuracy. Use the linked line, material, network and termination contracts
for their analytical/reference-tool acceptance and geometry/frequency limits.
No measurement agreement or browser/portable execution is established by these
Python checks. [Executable example](../../../examples/sipi/circuit_document.py).
