# Document format 0.3: the exact reader, the slot table and diagnostics

**English** | [한국어](../../locales/ko/pages/packages/simcase/document_format.md)

[Documentation home](../../README.md) · [simcase overview](overview.md) ·
[physmat.units](../physmat/units.md)

Status: **the shared reader of format 0.3 is in place, and every kind reads format 0.3 only:
heat (`thermal.steady2d`, `thermal.transient2d`), electric conduction and Joule heating
(`electric.steady2d`, `joule.steady2d`, `joule.temperature2d`), mechanics
(`mechanics.elasticity2d`, `mechanics.thermoelastic2d`), waveguide modes (`em.modes2d`) and
rectangular cavities (`em.cavity3d`).** A document whose envelope is the JSON string `"0.3"` takes
the reader described here. A format 0.2 document of any kind is refused by name (`E-FORMAT`,
with what to write instead). The kinds moved one at a time (heat, electric and Joule,
mechanics, `em.modes2d`, `em.cavity3d`); the internal 0.2 helpers that the kernel hand-offs
still use are retired in a later step. A kind registered without physics slots refuses its
0.3 document with `E-CONTRACT` ("documents are not read in format 0.3 yet").

Format 0.3 keeps today's document skeleton (`geometry`, `materials`, `physics.<name>`,
`mesh`, `study`, `results`) and changes only what the units and naming rules require:

- **Every dimensional value carries its unit**, as on a datasheet: `"200 GPa"`, `"25 degC"`,
  `"0.25 um"`. A bare number in a dimensional slot is `E-UNIT-MISSING`, zero included
  (`"0 V"`). Dimensionless values and counts stay bare numbers (`0.3`, `2`).
- **Keys are full registry quantity names**: `thermal_conductivity`, `youngs_modulus`,
  `element_size`, `minimum_angle`. No unit suffixes, no symbols.
- **There is no `units` block.** Each geometry component declares its `length_unit`, in which
  its bare shape numbers are read, and a planar component declares its `depth`.
- **Diagnostics are coded and never dropped**: each is `{code, severity, path, message, fix,
  suggestions, acknowledged}`, printed by `simcase validate` and `simcase run`.

Units, menus, codes and the exact conversion are those of
[`physmat.units`](../physmat/units.md); this page is how documents use them.

## Reading: exact JSON

`simcase.reader` reads the document text:

| Input | Result |
|---|---|
| a number with a fraction or exponent | `decimal.Decimal` of its text (`0.1000000000000000000001` stays that decimal) |
| an integer | `int` |
| `NaN`, `Infinity`, malformed JSON, an undecodable byte | `E-JSON` |
| a UTF-16 or UTF-32 text | `E-JSON` ("save it as UTF-8") |
| a leading UTF-8 byte order mark | accepted and dropped |
| a duplicate key at any depth | `E-KEY-DUPLICATE` at the object's path |
| a number literal longer than 1000 characters | `E-DOMAIN` at its path, before any arithmetic |
| `-0`, `-0.0` | +0.0 in the resolved tree |

`Document.from_dict` reads a Python object the same way: a float through its shortest
`repr` (`0.1` is the decimal 0.1), a non-finite float or a non-string key as `E-JSON`.
`reader.dumps` writes what `json.dumps` writes with the same arguments, and a `Decimal` as its
own text; for a tree without `Decimal` the bytes are identical.

## The envelope

`"openphysics"` must be the JSON **string** `"0.3"`. A missing key, the number `0.3`, `"0.2"`
or any other value is `E-FORMAT` at `openphysics`, and reading stops: format 0.2 documents are
not read by this reader. The document's physics types choose its kind as today; a kind that
does not read format 0.3 yet refuses with `E-CONTRACT` at `physics.<name>.type`, and a type that
no kind claims is `E-VALUE-FORM` there, naming the physics types this release reads.

Top-level keys: `openphysics name geometry materials physics mesh study results
display_units`. `units` is `E-KEY-UNKNOWN` with "units travel with each value".
`display_units` (optional) maps a quantity name or the display group `length` to a unit on
its menu; it changes no value and is used only for display (the extent lines).

## The slot table

`simcase.slots` maps every path of a document to one slot: a structural object or list, a
registry quantity (in document or in material place), a shape number, a `length_unit`, a
`depth`, an enum, a name, a material reference, a selector, a boolean, a string, a study
path, a list of counts, an acknowledgement or a refused key. The shared slots (envelope,
the three geometry forms, materials, mesh, study, results) are in `simcase.slots`; each
physics kind brings the slots of its `physics.<name>` entries as data
(`PhysicsKind.slots`). Pattern syntax: dotted segments, `*` for one map key, `[]` for one
list item, `["a.b"]` for a literal key, `{type}` after `physics.*` for entries of that
type, and `<rect>`, `<regions>` or `<v1>` after `geometry` for that geometry form.

```bash
python -m simcase.slots --check      # exit 1 when slot_table.json differs from the generator
python -m simcase.slots --write      # regenerate it (deterministic, sorted)
```

`slot_table.json` is generated, frozen and shipped; `tests/simcase/test_slots.py` runs
`--check`. Today it lists the shared slots and no kind.

**The walk.** For every authored path, in document order, exactly one slot must match, and
the first rule that applies gives the path its one error:

1. a refused key, with its own code and message (`units`; `base` in a material record;
   `absolute_pressure` in a load slot is `E-ABSOLUTE-AS-LOAD`);
2. an unknown key: `E-KEY-UNKNOWN` at that path, with "did you mean" from the sibling
   names, the registry's symbols and refused aliases of the sibling quantities (`E`
   suggests `youngs_modulus`) and the closed table of 0.2 names (`mesh.size` names
   `element_size`; `outward_flux_w_m2` names `inward_heat_flux` and says that the value
   changes sign, as a message, never as a fix);
3. the value form: `E-VALUE-FORM` (a boolean for a number, an object for a quantity string,
   a list of more than 3 strings, `{"in_m": ...}`);
4. the value itself, converted once through `physmat.units`, which gives the unit, menu,
   domain and band codes.

Then the requirements (`E-KEY-MISSING` at the missing path) and the defaults below.

## Value forms

| Form | Example | Where |
|---|---|---|
| quantity string | `"0.25 um"`, `"45 W/(m K)"` | every dimensional scalar |
| tagged array | `{"unit": "s", "values": [0, 0.1, 0.3]}` | series (`study.time`, swept values) |
| short list of at most 3 quantity strings | `["0 um", "0.11 um"]` | vectors (`position`, `traction`) |
| component object | `{"x": "0 mm"}` | displacement components |
| annotated value | `{"value": "4 J/(m^3 K)", "accept": {"W-MAGNITUDE": "manufactured solution"}}` | any quantity slot |
| bare number | `0.3`; a count `2` (never `2.0`) | dimensionless values and counts |
| complex | `{"re": 4.0, "im": 0.04}`; `{"n": 3.48, "k": 0.01}` inside `refractive_index` | under exp(−iωt); a negative imaginary part is `E-GAIN` |

An annotated value acknowledges a warning: it is still printed and stored, marked
`acknowledged` with its reason. Errors cannot be acknowledged.

## Geometry: three forms, one `length_unit` each

| Form | Recognised by | `length_unit` | `depth` |
|---|---|---|---|
| flat rectangle | `geometry: {length_unit, depth, domain}` | `geometry.length_unit` | `geometry.depth` |
| flat regions | a `background` or `shapes` key | `geometry.length_unit` | `geometry.depth` (2D); `E-KEY-UNKNOWN` for a 3D `domain` with `zmin`/`zmax` |
| version 1 components | `"version": 1` | `geometry.components.<c>.length_unit` | `geometry.components.<c>.depth` on a `2d` component; `E-KEY-UNKNOWN` on `axisymmetric` and `3d` |

- `length_unit` is required and is one of `pm nm Angstrom um mm cm m in mil`; `µm` and `Å`
  are read through the character map; `km` is `E-UNIT-NOT-ACCEPTED`, `{"in_m": x}`
  `E-VALUE-FORM`. In the component form, `geometry.length_unit` and `geometry.depth` are
  `E-KEY-UNKNOWN`.
- `depth` is a length (`"40 mm"`, `> 0`) or `null`, which means per metre of depth.
- **Shape numbers** are bare numbers in the component's unit, put on the 1 pm integer grid
  once (`physmat.units.length_to_pm`). A value that moves is `I-PM-ROUNDING` (below
  1e-3 pm) or `W-PM-ROUNDING`. In the resolved tree a shape number is `pm_to_m` of its pm
  count, and the mesher receives the same grid value, so a moved number is meshed where the
  diagnostic says it is stored.
- **Version 1 blocks** ([geometry document](geometry_document.md)) keep their grammar, read
  per component: each component's numbers and the literals of its expressions are in its
  own `length_unit`, so two components may use different units. Geometry `parameters` stay
  outside every component and carry their unit: a length parameter's `value` and `range`
  are quantity strings (`"0.5 um"`) or expressions of other parameters; a bare length value is
  `E-UNIT-MISSING`, a parameter named like a unit (`nm`, `h`, `bar`) is `E-ID-CLASH`, a unit
  inside an expression (`"220 nm + gap"`) is `E-EXPRESSION-KIND` ("declare a parameter"),
  and a bare number added to a length inside a parameter expression is `E-UNIT-MISSING`.
  Parameter values are exact picometres, so the design velocity V = dx/dp is the same number
  as in 0.2.
- **Element sizes** are quantity strings, never expressions: `element_size` on the
  background, a shape, a feature, `mesh` and a mesh control (today's `mesh_size` and
  `size`).
- A geometry-level warning is acknowledged with `accept` on the flat block or the component
  (`{"W-GEOMETRY-SCALE": "<reason>"}`).

## Materials

`materials: {<name>: <record>}` as today. A local name is any non-empty string without `:`
(`E-ID-CLASH`). A record's keys are registry property names (`thermal_conductivity`,
`volumetric_heat_capacity`, `electrical_conductivity`, `youngs_modulus`, `poisson_ratio`,
`linear_expansion_coefficient`, `mass_density`, `refractive_index`,
`relative_permittivity`, `relative_permeability`) and `source`. Every property present is
converted and checked; one that no physics of the run reads is `I-UNUSED-PROPERTY`. Registry
properties that this release does not read (`shear_modulus`, `bulk_modulus`,
`elasticity_tensor`, `mean_linear_expansion_coefficient`, `volumetric_expansion_coefficient`,
`specific_heat_capacity`, `loss_tangent`, `reference_resistivity`) are `E-CONTRACT`; `base`
and `description` are `E-KEY-UNKNOWN`. `refractive_index` also takes the Sellmeier model
form `{"model": "sellmeier", "constant", "terms": [{"strength",
"resonance_wavelength_squared"}], "valid": {"vacuum_wavelength": [lo or null, hi]},
"reference_medium": "vacuum"}`.

A **material reference** is a local name, which resolves only to its record
(`E-MATERIAL-UNKNOWN` otherwise, suggesting `"physmat:<Name>"` for a library name), or
`physmat:<Name>`, matched exactly against `physmat.names()` without case folding or aliases
(`E-LIBRARY-UNKNOWN` with "did you mean": `physmat:sio2` → `physmat:SiO2`). Each kind sets
which library references its documents may use (waveguide modes: any; the cavity:
`physmat:vacuum`; heat, electric, Joule and mechanics: none, `E-CONTRACT`). A library record
whose source states no temperature is `I-DATUM-ASSUMED` at the reference.

## Defaults

No dimensioned value has a default. The reader applies only these, and echoes each in
`defaults_applied` as `{path, value, reason}`; the authored tree is never changed:

| Path | Default |
|---|---|
| `materials` | `{}` |
| `geometry.shapes` (flat regions) | `[]` |
| `mesh.minimum_angle` (with `mesh.element_size`) | `"28 deg"`; at most `"33 deg"` |
| `mesh.element_count_limit` (with `mesh.element_size`) | `600000` |
| `materials.*.refractive_index.constant` | `1` |
| each kind's own (`name`, `study`, `results`, counts, boundary conditions) | with that kind |

## Cross-checks and the extent line

Before anything is meshed, each geometry component gets one **extent line**, which says
what its numbers mean:

```text
geometry (length_unit mm): 40 mm x 20 mm = 0.04 m x 0.02 m; depth per metre (null); element_size 2 mm, about 760 triangles
```

A rectangle ends with `subdivision_count 32 x 16 = 1024 triangles`, a cavity with
`cavity size x f/c = ...`. Then:

| Code | When |
|---|---|
| `E-MESH-ESTIMATE` | the estimated triangle count (2A/h² over the domain, plus the same for every shape, feature or control with its own size, plus the radial grading) exceeds `mesh.element_count_limit`; the message names a `length_unit` that would give a sane count |
| `W-GEOMETRY-SCALE` | the estimate is below 10; or `length_unit` `m`, every shape number a whole number and a diagonal above 10 m (millimetres written as metres); or, with a vacuum wavelength, a smallest feature outside 1e-3..1e3 wavelengths or a domain above 1e4 |
| `W-CAVITY-SCALE` | cavity size × target frequency / c outside 0.1..100 |
| `W-DEPTH-RATIO` | depth over the in-plane diagonal outside 1e-6..1e6 |
| `W-CELSIUS-AS-KELVIN` | an absolute temperature written in K or mK below 150 K while another one is at least 250 K |

Not checked yet: `W-TIME-SCALE`, `W-WIEDEMANN-FRANZ`, `W-SOUND-SPEED`, `W-STRAIN-LARGE`,
`W-DATUM-FAR`, `W-LIBRARY-RATIO`, `W-TEMPERATURE-RANGE`, `W-EFFECTIVE-INDEX-RANGE`,
`W-ANISOTROPY-MISSING`, `E-TEMPERATURE-NONPOSITIVE`, `I-VERTEX-SNAPPED`, `E-SCALE-MISMATCH`.
A rectangle document has no tagged length, so only the extent line and the
millimetres-as-metres pattern show a mis-declared rectangle.

## Diagnostics

The diagnostics of a document form one append-only list (`doc.diagnostics`): no stage
removes or replaces an entry, and validating a document again appends only what is new.
Codes are physmat's closed list. A **fix** keeps every SI value and may be applied
without asking (`"25K"` → `"25 K"`, `"12 ppm/degC"` → `"12 ppm/K"`, `2.0` → `2` for a count,
and a character alias `"1 µm"` → `"1 um"`); a **suggestion** may change the meaning (`"10 mPa"`
→ `"10 MPa"`) and is applied only by a person.

Severities: an error refuses the document; a warning is printed; an info is listed. Exit
codes of the command line: **0** valid (and the run succeeded), **1** run failure, **2**
document errors (also unreadable JSON and a missing file), **3** refused only because of
`--strict` (an unacknowledged warning, or `I-DATUM-ASSUMED`).

`DocumentError` and `GeometryError` take `(message, *, path=None, code="E-CONTRACT",
diagnostics=())`. A refusal raised from one message, as every kind refusal is, prints exactly
that message and is recorded as one `E-CONTRACT` diagnostic (at the path the message starts
with). A refusal of the reader prints one line per error: an `E-CONTRACT` line as its
message, any other code as `<path>: <message> (<code>)`. Warnings and infos are in
`.diagnostics`, not in `str()`.

## Command line

```bash
python -m simcase validate model.json [--json] [--strict]
python -m simcase run model.json [-o out] [-q] [--strict]
python -m simcase explain model.json [--json]
python -m simcase fix model.json [--in-place]
```

- `validate` prints the extent lines, the summary and every diagnostic; `--json` prints
  `{"valid", "extent", "diagnostics", "defaults_applied", "resolved_inputs"}`.
- `run` prints the extent lines and the diagnostics before it meshes, and refuses as
  `validate` would; its `log.txt` starts with the same lines.
- `explain` lists one row per input: path, authored text, SI value, canonical unit, the
  `length_unit` of a shape number, and each default with its reason.
- `fix` applies every fix by replacing only the JSON string or number token at its path:
  every other byte (spacing, key order, line endings, a byte order mark) stays. It never
  applies a suggestion, lists what it did, and refuses to write unless every SI value the
  document resolved before is bit-identical after. Without `--in-place` it prints the result.

A format 0.2 document is refused by every command (exit code 2): `validate` and `run` print
its `E-FORMAT` refusal with what to write instead, and `explain` and `fix` refuse it. `simcase
geometry` refuses it by name too.

## Python

```python
from simcase import Document
from simcase import reader

doc = Document.load("model.json")       # .loads(text), .from_dict(obj); DocumentError on any error
doc, diagnostics = reader.check(text)    # without raising: for validate, explain, fix
```

| Member | Meaning |
|---|---|
| `doc.data` | the authored tree, never changed (numbers are `Decimal`, so `json.dumps` refuses it) |
| `doc.si` | the resolved SI tree: the keys of `data` without `accept`; a quantity string is its SI float, a tagged array or short list a list, a complex value a `complex`, a count an `int`, a shape number metres |
| `doc.exact(path)`, `doc.pm(path)`, `doc.um(path)` | the exact rational SI value; the pm count of a shape number; micrometres from the exact value (never `si / 1e-6`) |
| `doc.degrees(path)` | the angle number the mesher takes: the authored number when written in `deg` |
| `doc.authored(path)`, `doc.resolved_inputs()` | the authored token; `{path: {authored, value, unit[, length_unit]}}` |
| `doc.defaults_applied`, `doc.diagnostics`, `doc.extent_lines()` | as above |
| `doc.canonical_json(separators=(",", ":"))` | sorted, decimal-preserving JSON of `data`; for a 0.2 document the bytes `json.dumps(data, sort_keys=True, ...)` gave, used by the result-snapshot guards |
| `doc.source_bytes`, `doc.save(path)` | the bytes read; a 0.3 document saves them as read |
| `doc.with_value(path, si, exact)` | a copy with one resolved value replaced (a sweep point) |

`simcase.quantities` re-exports the registry functions (`q`, `convert`, `menu`, `quantity`,
`names`, `format`). `simcase.results_common` holds what every 0.3 result shares: value
objects `{"value", "unit"}`, tagged arrays, complex values under exp(−iωt), the
`field_*` maps, the summary envelope (`diagnostics`, `defaults_applied`, `resolved_inputs`,
`extent`, `timing.wall_time`), `metadata_json`, `model.json` (the authored bytes) and the
`log.txt` header. `simcase.export.inject_field_data` adds the VTU unit metadata: a
`<FieldData>` block with two `UInt8` arrays in ASCII, `units` and `conventions`, each the UTF-8
bytes of a JSON object (not `String`, which meshio 5.3 cannot read back; meshio drops field
data when it writes VTU itself). A `fields.npz` whose layout is in `export.RETIRED_LAYOUTS`
is refused by name; each kind's step fills that table when it replaces its identifiers.

## Checks

| Check | Test |
|---|---|
| Exact reading: one double for `"200 GPa"`, `"200000 MPa"`, `"2e11 Pa"`; `"25 degC"` is the double nearest 298.15; long literals from their text; micrometres and degrees handed on from the exact and authored values; `model.json` equals the bytes read; a Python dict resolves like its JSON text; BOM and UTF-16; `-0`; no shipped negative zero; `json.dumps` never called on `doc.data`; `str()` of refusals | `tests/simcase/test_reader.py` |
| `canonical_json()` gives `json.dumps`'s bytes for every example, built-in example and harness fixture | `tests/simcase/test_reader.py` |
| The frozen slot table equals its generator; quantity slots name registry quantities placed in documents or materials; every path of every converted example and fixture outside `physics`, `study.tracking` and `results.mode_overlap` (the kinds' own slots) matches exactly one slot; a path in no slot is `E-KEY-UNKNOWN` | `tests/simcase/test_slots.py` |
| `validate`, `run`, `explain`, `fix` and the exit codes; the result helpers; the VTU metadata read back through `xml.etree` and meshio; retired layouts | `tests/simcase/test_cli_units.py` |
| Version 1 geometry in 0.3: the same pm model, design velocity, summary and geometry-lab view as the same geometry in 0.2; refusals with code and path | `tests/simcase/test_geometry_units.py` |

They run on a test-only kind (`tests/simcase/units_toy_kind.py`), so that they do not depend
on which built-in kinds read format 0.3 yet.

## Not done yet

- The retirement of `simcase.units` and of the internal format 0.2 helpers that the kernel
  hand-offs still use (the micrometre copy, the unit-declared geometry reading and the
  `em.modes2d` 0.2 validator as the kernel contract). (Every kind, `em.cavity3d` last, has its
  physics slots, examples and results under registry names; Studio reads raw bytes and serves
  the quantities endpoint; the format 0.2 reader of user documents, `simcase.unit_vocabulary`
  and `simcase.void_area_m2` are retired: `simcase.quantities` and `simcase.void_area`.)
- Each remaining code is raised by the kind that needs it, with its step (`E-SPECTRAL` is
  raised by `em.modes2d` for an entry with more than one spectral key, `I-DEFAULT-BOUNDARY` by
  heat, electric/Joule, mechanics and `em.modes2d`, `E-OUTSIDE-VALID` by `joule.temperature2d`,
  `W-GAUGE-ATMOSPHERIC` and `E-ABSOLUTE-AS-LOAD` by mechanics).
- The JSON Schema and generated documentation tables of the slots.
