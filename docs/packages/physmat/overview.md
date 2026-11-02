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
| Au, Ag, Cu | n,k table 0.19–1.94 µm | Johnson & Christy 1972, via refractiveindex.info (CC0) |
| Al | n,k table 0.2–12 µm | Rakić 1995, via refractiveindex.info (CC0) |
| H2O (water) | n,k table 0.2–200 µm | Hale & Querry 1973, via refractiveindex.info (CC0) |

Room-temperature density, thermal conductivity, specific heat, Young's
modulus, Poisson ratio, thermal expansion and thermo-optic coefficient are
attached to Si, SiO2, Si3N4 and the metals as handbook-level starting values;
each carries its `source` string. Check them before relying on them.

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
local copy of the database. The Ciddor air model holds no database data: it
evaluates the published equations and their constants.

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
in pressure, falling with temperature, normal dispersion).

## License

Apache License 2.0 - see [LICENSE](../../../packages/physmat/LICENSE) and [NOTICE](../../../packages/physmat/NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

The embedded optical data is not covered by that grant. It comes from the
refractiveindex.info database and is CC0 1.0 (public domain) - see
[Data license](#data-license) above and [NOTICE](../../../packages/physmat/NOTICE). The Apache-2.0 grant
covers the code.
