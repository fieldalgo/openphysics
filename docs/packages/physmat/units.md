# physmat.units — quantity registry and exact unit converter

**English** | [한국어](../../locales/ko/pages/packages/physmat/units.md)

[Documentation home](../../README.md)

Status: **first step of the OpenPhysics units and naming convention, with the
registry entries and converter functions the document reader needs.**
`physmat.units` holds the quantity registry and the one converter from
human-written units to SI. **Only the format 0.3 reader of `simcase` calls it so far**
([document format 0.3](../simcase/document_format.md)), and no physics kind reads that
format yet: model documents, the `simcase` runners,
`galerkin`, `sipi` and Studio keep their current key names and units, and the
other physmat functions keep their current arguments (wavelengths in micrometres,
temperatures in kelvin, and Celsius `temperature_c` for the Ciddor air model),
until later steps of the convention change them together. The module uses only
the Python standard library.

```python
from physmat.units import q, q_array, convert, convert_array, convert_complex

q("200 GPa", "youngs_modulus")                   # 200000000000.0  (Pa)
q("200000 MPa", "youngs_modulus")                # the same double
q("25 degC", "ambient_temperature")              # 298.15  (K)
q("12 ppm/K", "linear_expansion_coefficient")    # 1.2e-05  (1/K)
q("220 ㎚", "length")                             # 2.2e-07  (m)
q(0.3, "poisson_ratio")                          # a bare number: dimensionless quantities only
q_array({"unit": "nm", "values": [1500, 1550]}, "vacuum_wavelength")   # [1.5e-06, 1.55e-06]
q("1550 THz", "vacuum_wavelength")               # UnitError E-UNIT-DIMENSION: Did you mean frequency?

q("10 mPa", "gauge_pressure")                    # UnitError E-UNIT-NOT-ACCEPTED: millipascal
convert("10 mPa", "gauge_pressure").error        # the same diagnostic, returned instead of raised
convert("30 deg", "minimum_angle").number_text   # "30": the number as written, beside the SI value

convert_array({"unit": "nm", "values": [1500, -1]}, "vacuum_wavelength")    # every entry's diagnostics
convert_complex({"re": 4.0, "im": 0.04}, "relative_permittivity").value     # (4+0.04j), exp(-i omega t)
convert_complex({"n": 3.48, "k": -0.002}, "refractive_index").error         # E-GAIN: k >= 0 is loss
```

## The rules for values

- **A dimensional number carries its unit**, as on a datasheet: `"10 MPa"`,
  `"1550 nm"`, `"25 degC"`, `"12 ppm/K"`. A bare number is accepted only for a
  dimensionless quantity or a count; `200000` for `youngs_modulus` is
  `E-UNIT-MISSING`. There is no zero exception: write `"0 V"`. Angles always say
  `deg` or `rad`.
- **Each quantity has a closed unit menu.** Look-alikes are left off: there is no
  `mPa` for a modulus or a load and no `mS/m` for a conductor. No menu holds two
  spellings that are equal when case is ignored, so a case slip such as `mPa` for
  `MPa` is always refused by name, never read.
- **`degC` is a point on the Celsius scale.** It is accepted only as the whole unit
  of an absolute temperature. A temperature difference, a tolerance and every
  compound unit use `K` or `mK`: `"1 mK"`, `"W/(m K)"`, `"ppm/K"`.
- **Every value is converted once, exactly, to the quantity's canonical unit**:
  coherent SI, except `propagation_loss` (dB/m) and `bend_loss` (dB/(90 deg)).
- **A `fix` never changes a value; a `suggestion` may.** A fix keeps every SI value
  and tools may apply it without asking. A suggestion changes the meaning, shows the
  SI value before and after, and is applied only when a person confirms it.

## Quantity strings

```
quantity = number 1*SP unit            ; "25 degC", "1.2e-3 1/K"
         / number ("%" / "°C" / "°")   ; "40%", "25°C", "8°" are read as "40 %", "25 degC", "8 deg"
number   = ["+" / "-"] 1*DIGIT ["." 1*DIGIT] [("e" / "E") ["+" / "-"] 1*DIGIT]
unit     = one entry of the spelling table
```

- A leading digit is required (`0.5`, not `.5`); there is no decimal comma and no
  thousands separator.
- One space between the number and the unit is required: `"2eV"` and `"25K"` are
  refused with the fix `"2 eV"`, `"25 K"`. Only the three attached forms above are
  accepted, because they cannot be misread; `"25℃"` is refused with the fix
  `"25 degC"`, while `"25 ℃"` is accepted.
- Value forms here: a quantity string; a bare number (JSON number, `int`, `float`,
  `Decimal`, `Fraction`, or a numpy scalar); a tagged array
  `{"unit": "nm", "values": [...]}` (nested lists keep their shape; any sequence, or
  an array with `tolist()` such as a numpy array); a dimensionless array
  `{"values": [...]}`; a short vector of at most 3 quantity strings
  (`["0 MPa", "-5 MPa"]`). `"unit": "1"` is never written: a dimensionless value is
  a bare number.
- A string that holds only a number (`"0.3"`, `"2"`) is not a bare number. For a
  dimensionless quantity or a count it is `E-UNIT-UNKNOWN` with the JSON number as
  its fix (`0.3`, `2`); for a dimensional quantity it is `E-UNIT-MISSING`.
- A Python float is read through its shortest `repr`, so `0.1` means the decimal 0.1,
  as the JSON text `0.1` does. A numpy `float32` is read as its exact double
  (`0.30000001192092896`). numpy is never imported.
- A count (`mode_count`, `pml_order`, ...) is an integer literal: `2`, never `2.0`.
  `2.0`, `Decimal("2E+1")` or `Fraction(2)` is `E-DOMAIN` with the integer as its fix.
- `Conversion.number_text` is the number as written and `Conversion.unit_text` the
  unit as written after the character map (`"28.5 °"`: `"28.5"` and `"deg"`;
  `"148 W/m/K"`: `"W/m/K"`, while `text` is `"148 W/(m K)"`). A caller that needs
  the authored number, such as a mesher that takes degrees, reads it from there:
  `math.degrees(q("30 deg", "minimum_angle"))` is not exactly 30.
- `is_quantity_text(s)` is True for a number, one space and a unit that either
  table lists (`"0.5 um"`, `"10 mPa"`, `"40%"`), and False for an expression
  (`"w/2"`, `"220 nm + gap"`) or a bare number. A document reader uses it to tell
  a tagged value from an expression.

## Arrays and complex values

`convert_array(values, quantity, path=...)` takes the array forms above and returns
an `ArrayConversion`: the SI values in the shape written (`None` where an entry
failed), one `Conversion` per entry and every diagnostic, the array's own first
(an unknown key, a missing `values`, a refused unit), then each entry's in order.
It never raises for a bad value: a string or a bool in a tagged array, a list of
more than 3 strings or an object that is no array is `E-VALUE-FORM` at its path.
`q_array` is `convert_array` that raises: `TypeError` for a value of the wrong
form, `UnitError` for the first error, and a `UnitWarning` for each warning.

`convert_complex(value, quantity, path=..., allow_gain=False)` reads a complex
quantity under the one time convention exp(−iωt):

| Form | Quantities | Example |
|---|---|---|
| a real value, as `convert` takes it | any | `1.45`, `4`, `"50 Ohm"` |
| `{"re": .., "im": ..}` of bare numbers | a dimensionless complex quantity other than `refractive_index` (`relative_permittivity`, `relative_permeability`) | `{"re": 4.0, "im": 0.04}` |
| `{"n": .., "k": ..}` of bare numbers | `refractive_index` only | `{"n": 3.48, "k": 0.01}` |

The real part (`re`, `n`) is checked against the quantity's domain and band
(`"n": 0` is `E-DOMAIN`); the imaginary part is a bare number, checked for range
only. For a passive material quantity (`refractive_index`,
`relative_permittivity`, `relative_permeability`) a negative imaginary part or
`k` is `E-GAIN` at that part's path, with the hint "if your source uses
exp(+jωt), negate the imaginary part" and the negated number as a suggestion,
never a fix; `allow_gain=True` accepts it. A `[re, im]` pair, `{"re", "im"}` for
`refractive_index`, `{"n", "k"}` elsewhere and an object for a real or
dimensional quantity are `E-VALUE-FORM`; a missing or unknown key is
`E-KEY-MISSING` or `E-KEY-UNKNOWN`. The result, a `ComplexConversion`, holds the
complex SI value, the exact real and imaginary parts, the form read (`"real"`,
`"re_im"` or `"n_k"`) and the diagnostics.

## Exact conversion

The number is read from its decimal text with `fractions.Fraction`, multiplied by
the exact rational factor of its unit (plus the offset 273.15 for `degC`), divided
by the factor of the canonical unit and rounded **once** to a double.

- `"200 GPa"`, `"200000 MPa"` and `"2e11 Pa"` give the bit-identical double.
  `"25 degC"` gives the double nearest 298.15.
- Factors are exact: `in` = 0.0254 m, `mil` = 25.4 µm,
  `psi` = 44482216152605/6451600000 Pa, `atm` = 101325 Pa,
  `eV` = 1.602176634e-19 J. `deg` is π/180 with π rounded once to 40 digits,
  so `"180 deg"` gives `math.pi`. `dB/(180 deg)` is exactly half of `dB/(90 deg)`.
- **Range.** A converted value that is not finite, or whose magnitude is not 0 and
  below 1e-300 (subnormal or 0.0 as a double), is `E-DOMAIN`: `"1e400 Pa"`,
  `"1e-330 m"`. A number with a decimal exponent beyond ±1000 (read from the text,
  so `"1e999999999999999999999 Pa"` too), and an integer or a fraction of more than
  1100 bits, is refused before any arithmetic.
- Messages and `format()` build their numbers from the digits, so the caller's
  `decimal` context (precision, traps) has no effect.

## How a unit string is resolved

There is no unit grammar at run time. The converter takes four steps.

1. **Character map.** A fixed alias map is applied to the whole text; no Unicode
   normalisation (NFC, NFKC) is applied, because NFKC would turn `m²` into `m2`.

   | Written | Read as |
   |---|---|
   | `µ` (U+00B5), `μ` (U+03BC) | `u` |
   | `Ω` (U+03A9), `Ω` (U+2126) | `Ohm` |
   | `Å` (U+00C5), `Å` (U+212B) | `Angstrom` |
   | `K` (Kelvin sign U+212A) | `K` |
   | `°C`, `℃` (U+2103) | `degC` |
   | a lone `°` | `deg` |
   | `㎚ ㎛ ㎜ ㎝ ㎞ ㎟ ㎠ ㎡` (U+339A–U+33A1, from Korean input methods and PDF copies) | `nm um mm cm km mm^2 cm^2 m^2` |
   | superscript `⁰`–`⁹` and `⁻` | `^` and ASCII: `m⁻³` → `m^-3` |
   | `−` (U+2212) | `-`, in numbers and exponents |
   | `·`, `⋅` | a space |
   | no-break and thin spaces (U+00A0, U+2007, U+2009, U+200A, U+202F) | a space; runs of spaces collapse |

   So `"220 ㎚"`, `"25 ℃"`, `"3 µΩ·cm"` and `"148 W/(m·K)"` are accepted as written.
2. **Spelling lookup.** The whole unit text is looked up in the frozen spelling
   table, which maps every accepted spelling to one canonical unit: `W/(m K)`,
   `W/(m*K)`, `W/m/K`, `W m^-1 K^-1` and `W/(K m)` are all `W/(m K)`. A spelling that
   is not accepted is looked up in the known-refused list. A spelling in neither is
   `E-UNIT-UNKNOWN`; its "did you mean" candidates are the menu spellings equal to it
   when case is ignored (`Mpa` → `MPa`), given as suggestions. When a spelling off
   the menu is equal to it under case folding as well, the message names every
   reading with its value: `"1 ms/m"` matches `MS/m` (1e6 S/m, on the menu) and
   `mS/m` (0.001 S/m, not on the `electrical_conductivity` menu).
3. **Dimension, kind and menu.** The unit must have the quantity's dimension
   (`E-UNIT-DIMENSION`), pass the `degC` rule (`E-DEGC-NOT-ABSOLUTE`) and be on the
   quantity's menu (`E-UNIT-NOT-ACCEPTED`, listing the menu). A dimension error
   names the quantities whose menu holds the unit, and asks "Did you mean" for the
   primary quantity of that dimension (`electrical_conductivity` for `MS/m`,
   `length` for `mm`); the spectral keys name each other first (`"1550 THz"` for
   `vacuum_wavelength`: "Did you mean frequency?"). Model parameters
   (`lower_corner_frequency`, `plasma_energy`, ...) and `air_wavelength` are never
   named. A refused spelling only names the quantities of its dimension (`"MW"` is
   megawatt, "which has the dimension of heat_rate"); angles count, so `dB` is never
   called a unit of `bend_loss`.
4. **Conversion** as above, then the hard domain (`E-DOMAIN`) and the plausibility
   band (`W-MAGNITUDE`).

**Spelling table.** A build-time generator writes it from a small grammar: factors
separated by one space or `*`; a denominator as `/x`, `/(x y)` or `/x/y`; negative
powers on one line; every factor ordering. It never writes a run-together form
(`W/mK`, `Nm`) and never an unparenthesised `a/b c` form (`W/m K`). The canonical
form, which tools write, is ASCII with factors separated by one space, at most one
`/`, a parenthesised denominator of more than one factor and `^n` exponents:
`W/(m K)`, `J/(kg K)`, `kg/m^3`, `S/m`, `1/K`, `Ohm m`, `dB/m`. Two output-only
units have a half-integer power, written in parentheses: `1/m^(1/2)` and
`1/m^(3/2)` (also read as `m^(-1/2)`, `m^(-3/2)`); they are on no input menu.

**Known-refused list.** The same generator writes the spellings that are recognised
but refused, each with its code and reading:

| Spelling | Code | Example message content |
|---|---|---|
| SI-prefixed symbols that are not on the closed symbol list (`mPa`, `Mm`, `MW`, `MV`, `MOhm`, `dam`, `Tm`, ...) | `E-UNIT-NOT-ACCEPTED` | "`mPa` is millipascal"; suggestions `"10 MPa"` and the same value in a menu unit |
| `degC` inside a compound (`W/(m degC)`, `ppm/degC`, `1/degC`, `degC/m`) | `E-DEGC-NOT-ABSOLUTE` | fix: the same number with `K` (`"12 ppm/K"`) |
| `degC` inside a run-together or `a/b c` form (`J/kg°C`, `W/m°C`, `W/m degC`) | `E-UNIT-AMBIGUOUS` | the readings with `K` (`J/(kg K)`), and "write K"; never a fix |
| case look-alikes of menu compounds (`MW/(m K)` for `mW/(m K)`, `MOhm/mm`, `W/Mm^2`) | `E-UNIT-NOT-ACCEPTED` | "`MW/(m K)` is megawatt per metre kelvin" |
| a compound of an input menu with one factor in another common prefix (`p n u m k M G`, and `c` on the metre; kelvin factors excepted): `MW/m^3`, `mW/(m^2 K)`, `kW/m^3`, `V/cm`, `mS/cm`, `1/mm`, `km^2` | `E-UNIT-NOT-ACCEPTED` | "`MW/m^3` is megawatt per cubic metre. As written it is 5e6 W/m^3"; the same value in a menu unit as a suggestion |
| foreign units (`degF`, `Mpsi`, `R`, `Np`, `Np/m`, `Btu`, `kgf/mm^2`, `oz`, `ft`, `lb`, `lbf`, `Torr`, `mmHg`, `cal`, `micron`, ...) | `E-UNIT-NOT-ACCEPTED` | the exact conversion, as a suggestion where one exists |
| powers without `^` (`m2`, `m3`, `um2`, `W/m2`) | `E-UNIT-NOT-ACCEPTED` | fix: `m^2` |
| the unit `1` | `E-UNIT-NOT-ACCEPTED` | a dimensionless value is a bare number |
| run-together and `a/b c` forms (`W/mK`, `J/kgK`, `Ohmm`, `Nm`, `kWh`, `W/m K`, `W/m^2 K`) | `E-UNIT-AMBIGUOUS` | every reading (`W/mK`: W/(m K), or watt per millikelvin); never a fix |

`bara` and `psia` are accepted for `absolute_pressure`; in a `gauge_pressure` they
are `E-ABSOLUTE-AS-LOAD`. `barg` and `psig` are not on the `absolute_pressure`
menu, and no gauge- or absolute-marked value is re-expressed in another unit,
because absolute = gauge + ambient. A unit text in neither list that contains
`degC` (`kW/(m degC)`) stays `E-UNIT-UNKNOWN`, and the message says that `degC` is
never used inside a compound unit.

**Closed symbol list.** Prefixed symbols are listed one by one; none is generated.

| Family | Symbols |
|---|---|
| length | `pm nm Angstrom um mm cm m km in mil` |
| mass | `mg g kg` |
| time | `fs ps ns us ms s min h` |
| temperature | `mK K degC` (offset 273.15, absolute only) |
| current | `uA mA A kA` |
| angle | `urad mrad rad deg` |
| frequency | `Hz kHz MHz GHz THz` |
| force | `mN N kN` |
| pressure, stress | `Pa kPa hPa MPa GPa bar mbar atm psi ksi`; gauge-marked `barg psig`, absolute-marked `bara psia` |
| energy | `meV eV mJ J kJ MJ` |
| power | `pW nW uW mW W kW` |
| potential | `uV mV V kV` |
| resistance | `nOhm uOhm mOhm Ohm kOhm` |
| conductance | `uS mS S kS MS` |
| capacitance, inductance, charge | `fF pF nF uF F`; `pH nH uH mH H`; `pC nC uC mC C` |
| amount, magnetic (reserved) | `mol`; `mT T Wb` |
| ratio, logarithmic | `1 % ppm dB` (`dB` is always 10·log₁₀ of a power ratio) |

`MS` (megasiemens) is only on the `electrical_conductivity` menu (`MS/m`) and `mS`
only on conductance menus, so the two never meet.

## Diagnostics

A diagnostic is `{code, severity, path, message, fix, suggestions, acknowledged}`
and prints as `<severity> <CODE> at <path>`, then what is wrong, what it means and
the literal fix or suggestions:

```
error E-UNIT-NOT-ACCEPTED at physics.solid.conditions.bore.gauge_pressure
  "10 mPa": "mPa" is millipascal. As written it is 0.01 Pa. It is not accepted for gauge_pressure. Accepted: Pa kPa MPa GPa bar mbar psi ksi barg psig.
  Suggestion (not applied automatically): "10 MPa" (1e7 Pa; as written 0.01 Pa)
  Suggestion (not applied automatically): "0.01 Pa" (0.01 Pa)
```

Each value gets at most one error, from the first rule that applies:

1. (document reader, later) a key refused in its context;
2. an unknown key (here: an unknown quantity name, `E-KEY-UNKNOWN`, with "did you
   mean" from the registry's symbols and refused aliases: `E` → `youngs_modulus`);
3. a bare number in a dimensional slot: `E-UNIT-MISSING`;
4. character map, then lookup; in neither list: `E-UNIT-UNKNOWN`;
5. an ambiguous spelling: `E-UNIT-AMBIGUOUS`;
6. a unit of another dimension: `E-UNIT-DIMENSION` (`"58 MS/m"` for
   `thermal_conductivity`: "a unit of electrical_conductivity");
7. `degC` as a difference or inside a compound: `E-DEGC-NOT-ABSOLUTE` (a fix for a
   compound, a suggestion only for a difference);
8. any other known-refused spelling: its code (`E-UNIT-NOT-ACCEPTED` naming the
   reading; `E-ABSOLUTE-AS-LOAD` for `bara`/`psia` in a gauge slot);
9. an accepted spelling of the right dimension off the menu: `E-UNIT-NOT-ACCEPTED`,
   listing the menu (`"6451.6 1/cm"` for `vacuum_angular_wavenumber`: "1/cm is a unit
   of vacuum_wavenumber");
10. exact conversion and the range check: `E-DOMAIN`;
11. the hard domain: `E-DOMAIN`;
12. the plausibility band: `W-MAGNITUDE`, with likely prefix slips as suggestions
    (`"210000 Pa"` for steel; `"1.2e-5 ppm/K"`, a 1/K number written with `ppm/K`).

`gauge_pressure` between 90 and 110 kPa also warns `W-GAUGE-ATMOSPHERIC`. `q()`
raises `UnitError` for an error and issues each warning as a `UnitWarning`;
`convert()` returns them. The registry lists all 66 diagnostic codes of the
convention with a one-line English and Korean title (`DIAGNOSTIC_CODES`): the 58
of the design and 8 for the document reader (`E-FORMAT`, `E-JSON`,
`E-VALUE-FORM`, `E-MATERIAL-UNKNOWN`, `E-CONTRACT`, `W-SHAPE-DROPPED`,
`W-PIECE-DROPPED`, `I-MESH-CONTROL-RAISED`). This module raises 16 of them
(`E-VALUE-FORM` and `E-GAIN` from `convert_array` and `convert_complex`), and
messages are English.

**Fixes** come only from a closed list: `degC` inside a compound written as `K`, a
missing space (`"2eV"` → `"2 eV"`, `"25℃"` → `"25 degC"`), a power without `^`
(`m2` → `m^2`), a string holding only a number for a dimensionless quantity or a
count (`"0.3"` → `0.3`) and a whole count not written as an integer (`2.0` → `2`). Attached
forms, character aliases and non-canonical spellings are accepted as written;
`Conversion.text` holds the normalised text (`"148 W/(m K)"` for `"148 W/m/K"`).
Everything else is a **suggestion**: a case or prefix candidate (`"10 MPa"` for
`"10 mPa"`), the same value in a plainer menu unit (`"2000 kW"` for `"2 MW"`), the
same number in `K` for a `degC` difference, a likely slip outside the band. A
re-expression is written with the shortest number that converts back to exactly
the same double.

## The registry

Two JSON files ship as package data next to the module:

- `physmat/quantities.json`: the reviewed source. Each quantity gives its
  dimension, canonical unit, closed menu (`"1"` means a bare number), kind
  (`ordinary`, `absolute`, `difference`, `fraction`, `count`), rank, hard domain,
  plausibility band, places, allowed name qualifiers, symbols and refused aliases
  for "did you mean", the dimension-error hint flags (`hint`: true for the primary
  quantity of a dimension, false for one never named; `family`: `spectral`) and an
  English and Korean description. Where they apply it also gives `sign`, the sign
  sentence of each name (`inward_heat_flux`: "positive enters the body"),
  `statistic_definitions` (`maximum_stress`), `name_rank`, the rank of a name that
  differs from its base (`inward_heat_flux` is a scalar normal component), and
  `scope`, the model a model parameter belongs to. It also holds the closed symbol
  list with exact factors (and the `gauge`/`absolute` marks of
  `barg psig bara psia`), the prefixes, the foreign units, the character map, the
  diagnostic codes, the output-only qualifier words and the display groups.
- `physmat/unit_tables.json`: generated from it. Canonical units with dimension,
  exact factor, angle exponent and name; every accepted spelling; the known-refused
  list; every legal quantity name; the places and rank of each name that differs
  from its base; the members of each display group.

```bash
python -m physmat.units --check                    # exit 1 if unit_tables.json is stale
python -m physmat.units --write                    # regenerate it (deterministic, sorted)
python -m physmat.units youngs_modulus             # describe a quantity
python -m physmat._unit_tables --write             # regenerate without reading unit_tables.json
```

The generator ships inside the package, so that the R3 check runs against an
installed wheel too. If `unit_tables.json` does not parse (for example after a
merge conflict), `physmat.units` cannot be imported; `python -m
physmat._unit_tables --write` reads only `quantities.json` and repairs it.

**Names.** A quantity name is a full ISO-style name in `lower_snake_case`, never a
symbol or a unit: `thermal_conductivity`, `electrical_conductivity`,
`youngs_modulus`, `linear_expansion_coefficient`, `thermo_optic_coefficient`. A
generated name adds at most one direction, role or statistic word in front and one
component word behind, where the registry allows it: `ambient_temperature`,
`stress_free_temperature`, `maximum_temperature`, `inward_heat_flux`,
`outward_heat_rate_per_depth`, `stress_xy`, `displacement_x`, `minimum_overlap`,
`prescribed_temperature`, `outward_reaction_heat_rate_per_depth`.
`_per_depth` quantities are entries of their own. A name with an output-only
role word (`evaluation`, `unnormalized`, `mass_normalized`) is an output: its
places are `api` and `result` only, so `evaluation_temperature` is never read from
a document. A role word that changes the unit makes a base of its own
(`unnormalized_electric_field` has no unit, `mass_normalized_electric_field` is in
1/m^(3/2)), as `reference_conductivity` does. The registry has 242 entries and 367
names (`physmat.units.names()`).

Selected menus:

| Quantity | Canonical | Menu |
|---|---|---|
| `length`, `depth`, `element_size`, ... | m | `pm nm Angstrom um mm cm m km in mil` |
| `temperature` (+ `ambient_`, `reference_`, `initial_`, `stress_free_`, `prescribed_`; output `evaluation_`) | K | `K mK degC` |
| `temperature_difference`, `temperature_tolerance` | K | `K mK` |
| `thermal_conductivity` | W/(m K) | `W/(m K) mW/(m K) W/(cm K)` |
| `electrical_conductivity` | S/m | `S/m kS/m MS/m S/cm` |
| `youngs_modulus` | Pa | `Pa kPa MPa GPa psi ksi` |
| `gauge_pressure` | Pa | `Pa kPa MPa GPa bar mbar psi ksi barg psig` |
| `absolute_pressure` | Pa | `Pa kPa hPa bar mbar atm bara psia` |
| `linear_expansion_coefficient` | 1/K | `1/K ppm/K um/(m K)` |
| `vacuum_wavelength` | m | `nm um m` |
| `vacuum_wavenumber` (1/λ₀) | 1/m | `1/cm 1/m` |
| `vacuum_angular_wavenumber` (2π/λ₀) | rad/m | `rad/m rad/um` |
| `propagation_loss` | dB/m | `dB/m dB/cm dB/mm` |
| `relative_humidity` | 1 | a bare number, `%` |

`physmat.units.menu(name)` gives any menu. Notes on the data:

- Every menu holds its canonical unit (checked). Where the starter tables listed
  only prefixed units, the canonical unit was added: `F/m` for
  `capacitance_per_length`, `H/m` for `inductance_per_length`, `m` for
  `huray_sphere_radius`, `rms_roughness` and `air_wavelength`, `J` for
  `photon_energy` and the Drude–Lorentz energies. The closed symbol list gains `F`
  for the same reason (the starter list has `fF pF nF uF` only). Every other menu
  equals the starter tables (tested entry by entry).
- `overlap` takes the result statistics, so `minimum_overlap`, `maximum_overlap` and
  `mean_overlap` are names; `overlap_threshold` is the input bound.
- Angles are dimensionless, as in SI, but each unit records its angle exponent, so a
  suggestion never turns `1/cm` into `rad/m`. The canonical unit of
  `vacuum_angular_wavenumber` is written `rad/m` (the same number as 1/m), so that
  its menu holds it and stays disjoint from `vacuum_wavenumber`.
- `dB` is kept as a dimension of its own, so a logarithmic value never converts to
  or from a plain ratio (`"2 dB/m"` for `vacuum_wavenumber` is a dimension error).
- Every closed-list symbol is a known unit even if no menu uses it, so `"5 mg"` is
  refused by dimension instead of being unknown.
- Bands apply to |value| or a signed range as each entry states; an exact zero is
  exempt from lower bounds on |value|. Vector norms and tensor eigenvalues are for
  the document reader; here every number is checked on its own, and a complex value
  has its real part checked.
- **Sign sentences** (`Quantity.sign`, English and Korean) are on every name with a
  direction word, on the nodal reactions, loads and balance terms of heat,
  current and force, on `heat_flux`, `gauge_pressure`, `traction`, and on the
  complex quantities: `refractive_index` (k ≥ 0 is loss),
  `relative_permittivity` and `effective_index` (Im ≥ 0 is loss),
  `resonant_frequency` (Im < 0 decays), `propagation_loss` and `bend_loss`. The
  reactions keep the sense "exerted on the body by the constraint", and
  `ambient_convective_heat_rate` (the ambient term of the convective load) "enters
  the body"; every reported boundary sum is `outward_`.
- **Statistic definitions.** `maximum_displacement` is the largest nodal Euclidean
  norm and `maximum_stress` the largest absolute in-plane Cartesian component over
  elements (`Quantity.definition`); both are scalars.
- **Sellmeier parameters** `constant` (A, a band of ≥ 1), `strength` (Bᵢ ≥ 0),
  `resonance_wavelength` (`nm um m`) and `resonance_wavelength_squared`
  (Cᵢ, `nm^2 um^2 m^2`) have `scope` `refractive_index` model `sellmeier` and are
  never named in a dimension hint.
- Output entries for the balance defects (`heat_rate_imbalance`,
  `current_imbalance`, `electric_power_imbalance`, `force_imbalance`), nodal
  currents and forces, `stiffness_energy_functional` (½ uᵀKu of the total strain,
  not the stored elastic energy), `minimum_triangle_angle` (rad), the mode-tracking
  settings and evidence, and the unnormalised and mass-normalised mode fields.
  `target_frequency` is > 0, `subdivision_count` is a vector (2 or 3 counts), and
  every input that a result summary echoes is also placed in `result`
  (`heat_transfer_coefficient`, `body_force_density`, `traction`,
  `gauge_pressure`, `target_frequency`, `mode_count`, the `pml_` settings, the
  tracking thresholds, `beam_waist_radius`, `position`).
- **Display groups** (`display_groups()`): `length` holds every length quantity
  name and the bare shape numbers; its unit is one of `LENGTH_UNITS`. A document's
  `display_units` may name a group or a quantity.
- **Library datum.** Each built-in material states the temperature of its optical
  data, `Material.datum_temperature` in K, or `datum_assumed` where its source does
  not ([physmat overview](overview.md#built-in-materials)).

## Geometry picometre grid

`length_to_pm(value, length_unit)` puts a geometry length on the signed int64
picometre grid. A bare shape number is read in `length_unit` (`pm nm Angstrom um mm
cm m in mil`, all whole numbers of pm); a quantity string with its own unit
(`"0.5 nm"`) is read in that unit. The exact value is rounded half to even once;
a shift below 1e-3 pm is `I-PM-ROUNDING` (binary noise such as
`0.30000000000000004`), a larger one `W-PM-ROUNDING`, and both name the written
value, the stored value and the shift. `pm_to_m(k)` gives `float(Fraction(k,
10**12))`, so a vertex written as `100` in a `mm` component is exactly `0.1`.
Values beyond about ±9.2e6 m are `E-DOMAIN`.

## Python API

| Name | Use |
|---|---|
| `q(value, quantity)` | SI float; raises `UnitError`, warns `UnitWarning` |
| `q_array(values, quantity)` | SI list of a tagged array, a dimensionless array or a list of quantity strings |
| `convert(value, quantity, path=...)` | `Conversion` with `value`, `exact` (Fraction), `unit`, `text`, `diagnostics`, `number_text` and `unit_text`; never raises for a bad value |
| `convert_array(values, quantity, path=...)` | `ArrayConversion` with `values`, one `Conversion` per entry and every diagnostic; never raises for a bad value |
| `convert_complex(value, quantity, path=..., allow_gain=False)` | `ComplexConversion` under exp(−iωt): real value, `{re, im}` or `{n, k}`; `E-GAIN` for a passive material |
| `is_quantity_text(s)` | number, space and a unit of either table |
| `format(value, quantity, unit)` | quantity string with the shortest number that converts back to exactly `value` |
| `quantity(name)`, `menu(name)`, `names()` | registry lookups; `Quantity` objects are read-only and give the name's `rank`, `places`, `sign`, `definition` and `scope` |
| `display_groups()` | the display groups, read-only |
| `normalize(text)` | the character map, attached forms and space rules |
| `length_to_pm(value, length_unit)`, `pm_to_m(k)` | geometry grid |
| `generate_tables()` | text of `unit_tables.json` from `quantities.json` |
| `Diagnostic`, `Fix`, `Suggestion`, `DIAGNOSTIC_CODES` | diagnostics; `Fix.patch(pointer)` gives a JSON Patch operation |

`format` and `names` are not in `__all__`, so `from physmat.units import *` does
not hide the builtin `format` or `physmat.names`; call them as `units.format(...)`
and `units.names()`. `pm_to_m` takes an integer only (an `int` or a numpy
integer).

`import physmat.units` needs only the standard library: `physmat` now loads its
other submodules and names on first use, so numpy and scipy are imported only by
the material modules.

## Checks

`tests/physmat/test_units.py` implements the checks fixed before the
implementation, against an independent table of exact SI factors:

| Check | Test |
|---|---|
| R1 every unit on every menu converts sample decimals bit for bit to `float(Fraction(text) × factor)` (+ the `degC` offset); `"200 GPa"`, `"200000 MPa"`, `"2e11 Pa"` agree; `"25 degC"` == 298.15 | `test_r1_*` |
| R2 no menu holds two spellings equal under `str.casefold()` | `test_r2_*` |
| R3 the frozen table equals the generator output byte for byte, across hash seeds | `test_r3_*` |
| R4 every character-map entry, superscript and space, table-driven; no NFKC | `test_r4_*` |
| R5 every known-refused entry yields its code and its reading; every spelling the design names is pinned | `test_r5_*` |
| R6 `degC` in a compound: refused with a K fix that keeps the value; for a difference: a suggestion, never a fix | `test_r6_*` |
| R7 `"58 MS/m"` for `thermal_conductivity` names `electrical_conductivity`; exact hints | `test_r7_*` |
| R8 `"1e400 Pa"` and `"1e-330 m"` are `E-DOMAIN` | `test_r8_*` |
| R9 standard library only, with numpy and scipy blocked | `test_r9_*` |
| R10 `q()` gives a float, `q_array()` a list; bare numbers only for dimensionless quantities | `test_r10_*` |
| R11 each canonical unit is on its menu; every menu unit has the quantity's dimension; every menu equals the starter tables | `test_r11_*` |
| R12 the existing physmat tests pass unchanged | `test_r12_*` |
| Registry additions for the document reader: every new name with its unit and places, the reader's codes, sign sentences on every direction-qualified name, statistic definitions and ranks, half-power output units, the `length` display group, re-prefixed input compounds refused by reading (never unknown), `convert_array`, `convert_complex` and `E-GAIN`, the library datum, and generator refusals of broken name fields | `test_p2_*` |

The file also has one test per precedence rule and per raised code, and checks
fixes, suggestions (every suggestion converts back to the SI value it shows),
messages, bands, the pm grid, numpy inputs, the caller's decimal context, `format`
round trips on every menu unit and the repair of a broken `unit_tables.json`.

```bash
python -m pytest -q tests/physmat
```

## Not done yet

- Only the format 0.3 reader of `simcase` calls the converter (with its slot table,
  decimal-preserving JSON reader and writer, component objects, ranges, model
  coefficients and annotated values with `accept`;
  [document format 0.3](../simcase/document_format.md)), and no document kind reads that
  format yet; `galerkin`, `sipi` and Studio do not call it. The JSON Schema, tables,
  impedances and the generated documentation tables are not done.
- Checks that need more than one value (sound speed, Celsius-as-kelvin, mesh
  estimate, ...) and `E-SPECTRAL`, `E-BASIS` are not here.
- The list of echoed inputs placed in `result` comes from today's result summaries
  as the step-2 specification maps them; each document kind's step checks it
  against its converted results.
- Messages are English; the registry has English and Korean titles for every code.
  Unicode display forms (`µm`, `°C`, `W/(m·K)`) and display profiles are not here.
- Physical constants, the same-unit pairs list and the coupling table are not in the
  registry yet, and the entries have no `display`, `depth_exponent` or
  `not_to_be_confused_with` fields yet (display forms and the integration basis
  come later).
- Left out of the registry: `design_velocity` (its unit depends on the parameter),
  `huray_populations` (a list of roughness entries) and the cavity kernel
  coefficients (internal).
