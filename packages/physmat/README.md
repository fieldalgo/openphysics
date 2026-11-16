# physmat — material properties for physics solvers

[Documentation](../../docs/packages/physmat/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Optical dispersion first (complex refractive index and permittivity versus
wavelength), with a slot for the thermal and mechanical constants a
multiphysics solver will need later. Independent of any solver: numpy + scipy,
and PyYAML if you read the refractiveindex.info database.

```python
import numpy as np, physmat

si = physmat.material("Si")       # exact names (physmat.names()): no case folding, no aliases
si.refractive_index(vacuum_wavelength=1.55e-6)        # (3.4777+0j): n + i k, the vacuum wavelength in m
si.relative_permittivity(vacuum_wavelength=1.55e-6)   # (n + i k)^2, exp(-i w t) convention: Im >= 0 is loss
si.source                         # 'C. D. Salzberg and J. J. Villa, J. Opt. Soc. Am. 47, 244 (1957) ...'
si.valid_vacuum_wavelength        # (1.357e-06, 1.104e-05) m: evaluating outside raises OutOfRange
si.property("thermal_conductivity", temperature=300.0)   # 148.0 W/(m K); the temperature in K is required
physmat.material("Cu").property("thermal_conductivity", temperature=77.0)   # 544: Hust & Lankford 1984, RRR 100

au = physmat.material("Au")       # Johnson & Christy 1972 table
au.refractive_index(vacuum_wavelength=np.array([6e-7, 8e-7]))   # arrays too; at 800 nm 0.154 + 4.908j

# the full refractiveindex.info database (3500+ records, CC0 1.0)
db = physmat.rii.Database("/path/to/refractiveindex.info-database")   # or Database.download()
db.search("silicon nitride")                  # -> entries (shelf, book, page, name)
rec = db.load("main/Si3N4/Luke")
physmat.Material("Si3N4 (Luke)", rec.dispersion).refractive_index(vacuum_wavelength=1.55e-6), rec.references

# your own material: an optical model of a form a document accepts, in SI
glass = physmat.Material("my glass", physmat.constant_model(refractive_index=1.5))
custom = physmat.Material("doped SiO2", physmat.sellmeier_model(
    strength=[...], resonance_wavelength=[...],       # in m (or resonance_wavelength_squared in m²)
    valid_vacuum_wavelength=(3e-7, 2e-6)))
```

## SI arguments

Every quantity argument is a keyword-only name of the quantity registry in its SI
unit: `vacuum_wavelength` in m (a number or an array), `temperature` in K,
`absolute_pressure` in Pa, mole fractions and other dimensionless values as numbers.
A quantity given as a string raises `TypeError` ("SI numbers only; convert with
physmat.units.q('1550 nm', 'vacuum_wavelength')"); convert text with
[`physmat.units.q`](../../docs/packages/physmat/units.md). There are no dimensional defaults: a property needs
its `temperature` (`property("density", temperature=293.15)`), and the four Ciddor
air conditions are required.

The optical models compute in micrometres, as their sources and the
refractiveindex.info database state them. `refractive_index` and
`relative_permittivity` convert the vacuum wavelength to that micrometre double with
the decimal rule, `float(Fraction(repr(x)) * 10**6)` for each element, and evaluate
the model unchanged. For a value written with at most 15 significant digits this is
the micrometre double of its exact decimal value (`1.45e-06` m gives 1.45 µm, where
`1.45e-06 * 1e6` would give 1.4500000000000002), so a wavelength written in nm, µm or
m gives the same result. `valid_vacuum_wavelength` gives the model's range in m by
the same rule. There is no public switch to extrapolate past the range.

The models themselves, the micrometre and electronvolt helpers (`ev_to_um`,
`um_to_ev`, `HC_EV_UM`), the Drude–Lorentz fitter `fit_drude_lorentz`, the Ciddor
equations in °C and ppm and the Hust–Lankford model are the internal namespace
`physmat.kernels` ("internal, consistent units"): not part of the API, and free to
change in any release. `simcase` calls them with its own micrometre doubles and
therefore pins `physmat` to its own version. The library's property keys
(`density`, `specific_heat`, `thermal_expansion`, `thermo_optic_dn_dT`, ...), their
unit strings and the datum fields keep today's names until the materials step after
0.0.2.

## Built-in materials

Names are exact (`physmat.material("SiO2")`); the other names in parentheses are
kept on each record as `aliases`, as data only.

| name | model | source |
|---|---|---|
| vacuum (air) | n = 1 | definition |
| standard_air (standard air, Ciddor air) | Ciddor equations 0.3–1.69 µm; n(λ) at a chosen temperature, pressure, humidity and CO2 | Ciddor 1996, computed from the published equations (no stored data) |
| SiO2 (silica, fused silica) | Sellmeier 0.21–6.7 µm | Malitson 1965, via refractiveindex.info (CC0) |
| Si (silicon) | Sellmeier 1.357–11.04 µm | Salzberg & Villa 1957, via refractiveindex.info (CC0) |
| Si_visible | n,k table 0.25–1.45 µm | Green 2008, via refractiveindex.info (CC0) |
| Si3N4 (silicon nitride) | Sellmeier 0.31–5.5 µm | Luke et al. 2015, via refractiveindex.info (CC0) |
| GaAs, InP, Ge | Sellmeier | Skauli 2003, Pettit & Turner 1965, Burnett 2016, via refractiveindex.info (CC0) |
| Al2O3 (sapphire), MgF2, CaF2, LiNbO3, TiO2 | Sellmeier / formula 4 | Malitson & Dodge 1972, Dodge 1984, Malitson 1963, Zelmon 1997, DeVore 1951, via refractiveindex.info (CC0) |
| Au, Ag, Cu | n,k table 0.19–1.94 µm | Johnson & Christy 1972, via refractiveindex.info (CC0); Cu thermal conductivity λ(T): Hust & Lankford 1984, RRR 100 |
| Al | n,k table 0.2–12 µm | Rakić 1995, via refractiveindex.info (CC0); thermal conductivity λ(T): Hust & Lankford 1984, RRR 100 |
| H2O (water) | n,k table 0.2–200 µm | Hale & Querry 1973, via refractiveindex.info (CC0) |

Room-temperature density, thermal conductivity, specific heat, Young's
modulus, Poisson ratio, thermal expansion and thermo-optic coefficient are
attached to Si, SiO2, Si3N4 and the metals as handbook-level starting values;
each carries its `source` string. Check them before relying on them. The
exception is the thermal conductivity of Cu and Al, which is a function of
temperature from a published equation (next section).

## Thermal conductivity of metals versus temperature (Hust & Lankford 1984)

The `thermal_conductivity` property of Cu and Al, and
`physmat.metal_thermal_conductivity` for Cu, Al and W, evaluate the equation of
J. G. Hust and A. B. Lankford, *Thermal conductivity of aluminum, copper, iron,
and tungsten for temperatures from 1 K to the melting point*, NBSIR 84-3007, National Bureau of Standards (1984),
[doi:10.6028/NBS.IR.84-3007](https://doi.org/10.6028/NBS.IR.84-3007). One
equation per metal, with the residual resistivity ratio RRR = ρ(273 K)/ρ(0 K)
as the purity parameter (report Eqs. 1.1.3–1.1.6, 1.2.2; T in K, λ in W/(m K)):

```
λ    = 1 / (W0 + Wi + Wi0)
W0   = β / T,            β = ρ0 / L0,   ρ0 = ρi,273 / (RRR − 1),   L0 = 2.443e-8 V²/K²
Wi   = P1 T^P2 / (1 + P1 P3 T^(P2+P4) exp(−(P5/T)^P6)) + Wc(T)
Wi0  = P7 Wi W0 / (Wi + W0)
```

with the report's parameters P1–P7, the small correction terms Wc and
ρi,273 = 15.4, 24.8 and 48.4 nΩ m for Cu, Al and W. No table of the report is
stored; the equation is evaluated.

```python
cu = physmat.material("Cu")
cu.property("thermal_conductivity", temperature=np.array([4.0, 20.0, 77.0, 300.0]))   # 628, 2420, 544, 397 (RRR 100)
physmat.metal_thermal_conductivity("Cu", temperature=20.0, residual_resistivity_ratio=300.0)   # 5073: purer copper
physmat.metal_thermal_conductivity("W", temperature=300.0, residual_resistivity_ratio=100.0)   # 175.6
physmat.MINIMUM_TEMPERATURE                                         # 1.0 K: the validity starts at 1 K
```

- **RRR 100 in the library** for Cu and Al: a column of the report's own tables,
  the OFHC-copper grade of the NIST cryogenic fits, and within 2 % of the handbook
  300 K constants it replaces (Cu 397 vs 401, Al 234 vs 237, W 176 vs 174 W/(m K)).
  `metal_thermal_conductivity` takes the purity as `residual_resistivity_ratio`
  (required); below ~100 K the value depends strongly on it. The metal name is
  exact: `"Cu"`, `"Al"` or `"W"`.
- **Validity**: `MINIMUM_TEMPERATURE` (1 K) to the melting point (Cu 1357.77 K,
  Al 933.47 K, W 3695 K), for annealed bulk specimens; the report represents its
  primary data within about ±15 % (Cu), random deviations (Al) and ±7 % (W).
  Temperatures outside raise `OutOfRange` unless `strict=False`. RRR must exceed 1;
  outside the RRR range of the fitted data (Cu 20–1800, Al 13–16800, W 30–170) the
  function raises `OutOfRange` unless `strict=False`.
- **Checks** (`tests/physmat/test_conductivity_temperature.py`): the report's
  Tables 2.4.1 and 3.4.1 are reproduced within 1.5 % (one misprinted Al entry
  excluded); Cu RRR 100 agrees with the NIST Cryogenic Material Properties OFHC
  fit within 2.3 % over 4–300 K and with the Ho, Powell & Liley (1972)
  recommended values within 4.3 % from 100 to 1300 K; Al and W agree with Ho,
  Powell & Liley within 3.8 % (150–900 K) and 4.0 % (100–3000 K). For tungsten
  the report's printed parameters reproduce its Table 5.4.1 within 2 % except
  near the conductivity maximum of the purer columns (table up to 3.5 % above
  the equation at RRR 100, 7.2 % at RRR 300), an inconsistency of the source
  that is recorded, not corrected. Aluminium has a shallow minimum near 242 K
  (+0.5 % to 300 K), as in the report's table and in Ho, Powell & Liley.
- **Provenance**: the report is a work of the United States Government, not
  subject to copyright in the United States (17 U.S.C. 105); its status elsewhere
  is not settled by that statute and is recorded in `NOTICE`, not decided here.
  Tungsten is not yet a built-in material (it has no optical model); use
  `physmat.metal_thermal_conductivity("W", ...)`.

## Air (Ciddor 1996)

`vacuum` is n = 1. `standard_air` is moist air after P. E. Ciddor,
"Refractive index of air: new equations for the visible and near infrared",
*Appl. Opt.* **35**, 1566–1573 (1996), implemented from the published equations:
dispersion of standard dry air with the CO2 correction, dispersion of water
vapour, the BIPM 1981/91 moist-air density (saturation vapour pressure,
enhancement factor, compressibility Z) and the density-ratio mixing rule.

```python
std = physmat.material("standard_air")                # 15 °C, 101325 Pa, 0 % RH, 450 ppm CO2
std.refractive_index(vacuum_wavelength=6.33e-7)       # 1.00027653
lab = physmat.ciddor_air(temperature=293.15, absolute_pressure=101325.0,
                         relative_humidity=0.5, co2_mole_fraction=450e-6)   # 20 °C; all four required
lab.refractive_index(vacuum_wavelength=6.33e-7)       # 1.00027137
lab.property("density", temperature=293.15)           # 1.19925 kg/m³, BIPM 1981/91 (temperature in K)
warm = physmat.ciddor_air(temperature=298.15, absolute_pressure=101325.0,
                          relative_humidity=0.5, co2_mole_fraction=450e-6)  # the same air at 25 °C
physmat.ciddor_air(temperature=293.15, absolute_pressure=101325.0, relative_humidity=None,
                   co2_mole_fraction=450e-6, vapor_pressure=1200.0)   # the water as its partial pressure in Pa
```

The conditions are `temperature` in K, `absolute_pressure` in Pa,
`relative_humidity` as a fraction (or `vapor_pressure`, the partial pressure of
water vapour in Pa, with `relative_humidity=None`) and `co2_mole_fraction`
(450e-6 is 450 ppm). Ciddor's equations take °C and ppm; `ciddor_air` derives them
with the decimal rule, `Fraction(repr(T)) − 273.15` and `Fraction(repr(x)) · 10⁶`, so
233.15 K is exactly −40 °C (`233.15 − 273.15` would give −39.99999999999997) and
`ciddor_air(temperature=288.15, ...)` is the `standard_air` record bit for bit. The
material's `datum_temperature` is the given `temperature`. Ciddor states the
equations for 0.3–1.69 µm, 233.15–373.15 K (−40 to +100 °C), 80–120 kPa, 0–100 % RH
and a CO2 mole fraction of 0–0.002 (0–2000 ppm) with an uncertainty of 2–5e-8 in n
under laboratory conditions (NIST estimates about 2e-8 at k = 2, up to 1e-7 at the
extremes). Wavelengths outside the range raise `OutOfRange`; conditions outside
the ranges raise when the material is built unless `strict=False`, which
extrapolates the formulas. The density `Property` is the BIPM equation at the
material's pressure, humidity and CO2 as a function of temperature in kelvin.
The humidity model uses Ciddor's Davis (1992) saturation vapour pressure over
water; below 0 °C NIST uses a different, over-ice formula, so humid sub-zero air
differs at the 1e-9 level.

## Optical models

`physmat.constant_model(refractive_index=...)` and
`physmat.sellmeier_model(strength=..., resonance_wavelength_squared=... or
resonance_wavelength=..., constant=1.0, valid_vacuum_wavelength=None)` build the two
forms a document's `refractive_index` accepts, from SI values: n + i k (a `-0.0`
imaginary part is kept), and n² = constant + Σ strengthᵢ λ²/(λ² − Cᵢ) with Cᵢ in m² or
the resonance wavelength in m, and the validity range in m (`(None, high)` for an
open lower bound). Wrap one in `physmat.Material(name, model)`. They convert the
coefficients to the model's square micrometres with the decimal rule, so a
coefficient spelled with 17 digits in µm² can differ from the micrometre double in its
last bit (measured: 1.5e-16 relative in n).

The library's models are the internal kernels `Constant`, `Sellmeier`, `Tabulated`
(linear interpolation), `Composite` (n from one model, k from another), `Drude`,
`DrudeLorentz` (Rakić form, energies in eV), `RIIFormula` (the nine dispersion
formulas of refractiveindex.info exactly as stored there) and `CiddorAir`, in
`physmat.kernels`. They take micrometres in `index`, `n`, `k`, `eps` and
`group_index`; a material's `optical` is one of them, and so is a
`physmat.rii` record's `dispersion`.

## Data license

The refractiveindex.info database is dedicated to the public domain
(CC0 1.0); its maintainer asks for citation:
M. N. Polyanskiy, "Refractiveindex.info database of optical constants",
*Sci. Data* **11**, 94 (2024). Every built-in record also names the original
measurement. `tools/build_physmat_tables.py` regenerates the embedded tables from a
local copy of the database. The Ciddor air model and the Hust & Lankford
conductivity model hold no database data: they evaluate the published
equations and their constants (see `NOTICE` for the US-government-work note on
the latter).

## Self-checks

```bash
# From the repository root
python -m pip install pytest -e "packages/physmat[rii]"
python -m pytest -q tests/physmat
```

Checked against published values (fused-silica n_d = 1.4585, Si n(1.55 µm) =
3.4777, sapphire/MgF2/CaF2 n_d, gold ε(800 nm) ≈ −24 + 1.5i), physical
constraints (Im ε ≥ 0, Drude zero crossing at ω_p, ε → ε∞), hand-evaluated
formulas 2–9, a synthetic Drude–Lorentz fit recovered to 1e-3, a gold fit
within 5 % over 400–1000 nm, and — when a local copy of the database is
present — every one of its 3500+ records parsing and agreeing with the
built-ins. The Ciddor air model reproduces the 14 values of the NIST
Engineering Metrology Toolbox table (Stone & Zimmerman; 300–1700 nm, −40 to
50 °C, 60–120 kPa, 0–100 % RH) within 1.5e-9 (measured at most 0.75e-9, the
table's rounding), agrees with an independent Birch & Downs 1994 modified
Edlén implementation within 1.5e-8 at ambient conditions (measured at most
5.7e-9), reproduces Ciddor's published Z_a = 0.9995922115 and
ρ_ws = 0.00985938 kg/m³, and has the right limits (n → 1 as p → 0, monotonic
in pressure, falling with temperature, normal dispersion). The Hust & Lankford
conductivity gates are listed in the section above.

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

The embedded optical data is not covered by that grant. It comes from the
refractiveindex.info database and is CC0 1.0 (public domain) - see
[Data license](#data-license) above and [NOTICE](NOTICE). The Apache-2.0 grant
covers the code.
