# physmat — material properties for physics solvers

**English** | [한국어](../../locales/ko/pages/packages/physmat/overview.md)

[English / 한국어 documentation and translation status](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Optical dispersion first (complex refractive index and permittivity versus
wavelength), with a slot for the thermal and mechanical constants a
multiphysics solver will need later. Independent of any solver: numpy + scipy,
and PyYAML if you read the refractiveindex.info database.

```python
import numpy as np, physmat

si = physmat.get("Si")            # aliases work too: "silicon", "c-Si"
si.n(1.55)                        # 3.4777  — wavelength in micrometres
si.eps(1.55)                      # (n + i k)^2, exp(-i w t) convention: Im eps >= 0 is loss
si.source                         # 'C. D. Salzberg and J. J. Villa, J. Opt. Soc. Am. 47, 244 (1957) ...'
si.range_um                       # (1.357, 11.04): evaluating outside raises OutOfRange
si.get("thermal_conductivity")    # 148.0  (W/(m K)); the multiphysics slot
physmat.get("Cu").get("thermal_conductivity", 77.0)   # 544: Hust & Lankford 1984 equation, RRR 100

au = physmat.get("Au")            # Johnson & Christy 1972 table
au.index(0.8)                     # 0.154 + 4.908j

# fit a table to Drude + Lorentz poles for time-domain or broadband solvers
fit = physmat.fit_drude_lorentz(au.optical, np.linspace(0.4, 1.0, 60), n_lorentz=2)
fit.model.eps(0.8), fit.rms_eps, fit.max_rel_index    # passive by construction

# the full refractiveindex.info database (3500+ records, CC0 1.0)
db = physmat.rii.Database("/path/to/refractiveindex.info-database")   # or Database.download()
db.search("silicon nitride")                  # -> entries (shelf, book, page, name)
rec = db.load("main/Si3N4/Luke")
rec.dispersion.n(1.55), rec.references

# your own material
glass = physmat.constant(1.5, name="my glass")
custom = physmat.Material("doped SiO2", physmat.Sellmeier(B=[...], C=[...], range_um=(0.3, 2.0)))
```

## Units and the quantity registry

`physmat.units` is the quantity registry and exact unit converter of the
OpenPhysics units convention: `physmat.units.q("200 GPa", "youngs_modulus")`
gives `2e11` (Pa), and `"10 mPa"` for a pressure is refused by name. It uses
only the Python standard library. Nothing uses it yet: model documents and the
solvers keep their current units, and the functions on this page keep their
current arguments (wavelengths in micrometres, temperatures in kelvin, and Celsius
`temperature_c` for the Ciddor air model). See [physmat.units](units.md).

## Built-in materials

| name | model | source |
|---|---|---|
| vacuum / air | n = 1 | definition |
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
temperature from a published equation ([below](#thermal-conductivity-of-metals-versus-temperature-hust--lankford-1984)).

Each record also states the temperature of its optical data,
`Material.datum_temperature` in K, as its refractiveindex.info record gives it (the
pinned database revision of `tools/rii-revision.txt`). Where the source says only
"room temperature" or gives none, `datum_temperature` is `None` and
`datum_assumed` is True, so that a reader can report the assumption (units
convention, answer 3.8). `vacuum` has neither: n = 1 holds at every temperature.
`standard_air(...)` states the temperature it is built for.

| Datum | Records |
|---|---|
| 288.15 K (15 °C) | `standard_air` |
| 292.15 K (19 °C) | `MgF2` |
| 293.15 K (20 °C) | `SiO2`, `Al2O3` |
| 294.15 K (21 °C) | `LiNbO3` |
| 295 K | `Ge` (database conditions) |
| 295.15 K (22 °C) | `GaAs` |
| 297.15 K (24 °C) | `CaF2` |
| 298.15 K (25 °C) | `H2O` |
| 299.15 K (26 °C) | `Si` |
| 300 K | `Si_visible` |
| assumed ("room temperature" or none stated) | `Si3N4`, `InP`, `TiO2`, `Au`, `Ag`, `Cu`, `Al` |

## Air (Ciddor 1996)

`air` is vacuum (n = 1). `standard_air` is moist air after P. E. Ciddor,
"Refractive index of air: new equations for the visible and near infrared",
*Appl. Opt.* **35**, 1566–1573 (1996), implemented from the published equations:
dispersion of standard dry air with the CO2 correction, dispersion of water
vapour, the BIPM 1981/91 moist-air density (saturation vapour pressure,
enhancement factor, compressibility Z) and the density-ratio mixing rule.

```python
std = physmat.get("standard_air")                     # 15 °C, 101325 Pa, 0 % RH, 450 ppm CO2
std.n(0.633)                                          # 1.00027653
lab = physmat.standard_air(20.0, 101325.0, humidity=0.5, co2_ppm=450.0)   # RH as a fraction
lab.n(0.633), lab.optical.refractivity(0.633)         # n and n − 1 at full precision
lab.optical.at(temperature_c=25.0).n(0.633)           # same model, other conditions
lab.get("density", 293.15)                            # kg/m³, BIPM 1981/91 (Property, T in kelvin)
physmat.air.refractive_index(0.633, temperature_c=np.linspace(-40, 100, 5), pressure_pa=90e3)
```

Conditions are temperature in °C, pressure in Pa, relative humidity as a
fraction (or `vapour_pressure_pa`, the partial pressure of water vapour) and
CO2 in ppm (µmol/mol). Ciddor states the equations for 0.3–1.69 µm, −40 to
+100 °C, 80–120 kPa, 0–100 % RH and 0–2000 ppm CO2 with an uncertainty of
2–5e-8 in n under laboratory conditions (NIST estimates about 2e-8 at k = 2,
up to 1e-7 at the extremes). Wavelengths outside the range raise `OutOfRange`
unless `n(wl, strict=False)`; conditions outside the ranges raise when the
material is built unless `strict=False`, which extrapolates the formulas. The
density `Property` is the BIPM equation at the material's pressure, humidity
and CO2 as a function of temperature in kelvin. The humidity model uses
Ciddor's Davis (1992) saturation vapour pressure over water; below 0 °C NIST
uses a different, over-ice formula, so humid sub-zero air differs at the
1e-9 level.

## Thermal conductivity of metals versus temperature (Hust & Lankford 1984)

The `thermal_conductivity` property of Cu and Al, and `physmat.thermal` for W,
evaluate the equation of J. G. Hust and A. B. Lankford, *Thermal conductivity of
aluminum, copper, iron, and tungsten for temperatures from 1 K to the melting
point*, NBSIR 84-3007, National Bureau of Standards (1984),
[doi:10.6028/NBS.IR.84-3007](https://doi.org/10.6028/NBS.IR.84-3007). One
equation per metal, with the residual resistivity ratio RRR = ρ(273 K)/ρ(0 K) as
the purity parameter (report Eqs. 1.1.3–1.1.6 and 1.2.2; T in K, λ in W/(m K)):

```
λ    = 1 / (W0 + Wi + Wi0)
W0   = β / T,            β = ρ0 / L0,   ρ0 = ρi,273 / (RRR − 1),   L0 = 2.443e-8 V²/K²
Wi   = P1 T^P2 / (1 + P1 P3 T^(P2+P4) exp(−(P5/T)^P6)) + Wc(T)
Wi0  = P7 Wi W0 / (Wi + W0)
```

W0 is the electron–defect (residual) resistivity, Wi the intrinsic
electron–phonon resistivity, Wi0 their interaction term and Wc a small empirical
correction; the parameters P1–P7 and Wc are the report's (Sections 2.1, 3.1, 5.1;
for copper P7 = 0.838/βr^0.1661 with βr = β/0.0003), ρi,273 = 15.4, 24.8 and
48.4 nΩ m for Cu, Al and W (Section 1.5). No table of the report is stored.

```python
cu = physmat.get("Cu")
cu.get("thermal_conductivity", np.array([4.0, 20.0, 77.0, 300.0]))   # 628, 2420, 544, 397  (RRR 100)
physmat.HustLankford("Cu", rrr=300)(20.0)                            # 5073: purer copper
physmat.HustLankford("Al", rrr=1000).range_k                         # (1.0, 933.47): 1 K to the melting point
physmat.thermal.thermal_conductivity("W", 300.0)                     # 175.6  (RRR 100)
physmat.thermal.conductivity_property("W", rrr=50)                   # a Property for your own Material("W", ...)
```

- **Default RRR 100** for all three metals: a column of the report's own tables,
  the OFHC-copper grade of the NIST cryogenic fits (Hust & Lankford put commercial
  copper wire at RRR 50–500), and within 2 % of the handbook 300 K constants it
  replaces (Cu 397 vs 401, Al 234 vs 237, W 176 vs 174 W/(m K)). Pass `rrr=` for
  another purity; below ~100 K the value depends strongly on it (Cu at 20 K: 843,
  2408, 5054 W/(m K) for RRR 30, 100, 300).
- **Validity**: 1 K to the melting point (Cu 1357.77 K, Al 933.47 K, W 3695 K),
  annealed bulk specimens; the report represents its primary data within about
  ±15 % (Cu; 20 % for unannealed specimens), random deviations without an RRR trend
  (Al) and ±7 % (W), and notes that the copper fit becomes progressively less valid
  below RRR 20. Temperatures outside the range raise `OutOfRange` unless
  `strict=False`. RRR must exceed 1 (`ValueError`); outside the RRR range of the
  fitted data (Cu 20–1800, Al 13–16800, W 30–170) the model raises `OutOfRange`
  unless built with `strict=False`, which extrapolates (the report's own tables
  extend to RRR 3000, 10000 and 300).
- **Checks** (`tests/physmat/test_conductivity_temperature.py`, pre-registered
  gates): the report's Tables 2.4.1 (Cu) and 3.4.1 (Al) are reproduced within
  1.5 % (one Al entry, 229 W/(m K) at 700 K for RRR 100, is a misprint above the
  purer columns and excluded); Cu RRR 100 agrees with the NIST Cryogenic Material
  Properties OFHC fit (RRR 100; data from NIST Monograph 177) within 2.3 % at 4,
  20, 77, 150 and 300 K (RRR 50 and 300: 3.0 % and 0.6 %) and with the Ho, Powell &
  Liley (1972) recommended values within 4.3 % from 100 to 1300 K; Al and W agree
  with Ho, Powell & Liley within 3.8 % (150–900 K) and 4.0 % (100–3000 K), and at
  100 K at the purity of their specimens within 2 %. For tungsten the report's
  printed parameters reproduce its Table 5.4.1 within 2 % except around the
  conductivity maximum of the purer columns, where the table lies above the
  equation by up to 3.5 % (RRR 100, 14–50 K) and 7.2 % (RRR 300, 9–50 K); the
  parameters were re-read from a high-resolution rendering of the scan and are
  as printed, so this is an inconsistency of the source, recorded and not
  corrected. Cu and W have a single maximum (22 K, 2447 and 786 W/(m K) at RRR
  100) and fall monotonically to 300 K; Al (24 K, 1630 W/(m K)) falls to a shallow
  minimum near 242 K and rises 0.5 % to 300 K, as in the report's table and in Ho,
  Powell & Liley.
- **Provenance**: the report is a work of the United States Government and not
  subject to copyright in the United States (17 U.S.C. 105); its status outside
  the US is not settled by that statute and is recorded in the package `NOTICE`
  and [third-party software](../../third-party.md#data-and-published-numbers),
  not decided here. Tungsten is not yet a built-in material (it has no optical
  model); use the `physmat.thermal` functions directly.

## Models (`physmat.dispersion`)

`Constant`, `Sellmeier`, `Tabulated` (linear interpolation), `Composite`
(n from one model, k from another), `Drude`, `DrudeLorentz` (Rakić form,
energies in eV), and `RIIFormula` implementing the nine dispersion formulas of
refractiveindex.info exactly as stored there. All expose `index`, `n`, `k`,
`eps`, `group_index`, and a validity range.

## Data license

The refractiveindex.info database is dedicated to the public domain
(CC0 1.0); its maintainer asks for citation:
M. N. Polyanskiy, "Refractiveindex.info database of optical constants",
*Sci. Data* **11**, 94 (2024). Every built-in record also names the original
measurement. `tools/build_physmat_tables.py` regenerates the embedded tables from a
local copy of the database. The Ciddor air model and the Hust & Lankford
conductivity model hold no database data: they evaluate the published
equations and their constants.

## Self-checks

```bash
# From the repository root
python -m pip install pytest -e "packages/physmat[rii]"
python -m pytest -q tests/physmat
```

Checked against published values (fused-silica n_d = 1.4585, Si n(1.55) =
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
in pressure, falling with temperature, normal dispersion). The thermal
conductivity gates are listed in [the section above](#thermal-conductivity-of-metals-versus-temperature-hust--lankford-1984).

## License

Apache License 2.0 - see [LICENSE](../../../packages/physmat/LICENSE) and [NOTICE](../../../packages/physmat/NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

The embedded optical data is not covered by that grant. It comes from the
refractiveindex.info database and is CC0 1.0 (public domain) - see
[Data license](#data-license) above and [NOTICE](../../../packages/physmat/NOTICE). The Apache-2.0 grant
covers the code.
