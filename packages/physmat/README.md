# physmat — material properties for physics solvers

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

| name | model | source (all via refractiveindex.info, CC0) |
|---|---|---|
| vacuum / air | n = 1 | definition |
| SiO2 (silica, fused silica) | Sellmeier 0.21–6.7 µm | Malitson 1965 |
| Si (silicon) | Sellmeier 1.357–11.04 µm | Salzberg & Villa 1957 |
| Si_visible | n,k table 0.25–1.45 µm | Green 2008 |
| Si3N4 (silicon nitride) | Sellmeier 0.31–5.5 µm | Luke et al. 2015 |
| GaAs, InP, Ge | Sellmeier | Skauli 2003, Pettit & Turner 1965, Burnett 2016 |
| Al2O3 (sapphire), MgF2, CaF2, LiNbO3, TiO2 | Sellmeier / formula 4 | Malitson & Dodge 1972, Dodge 1984, Malitson 1963, Zelmon 1997, DeVore 1951 |
| Au, Ag, Cu | n,k table 0.19–1.94 µm | Johnson & Christy 1972 |
| Al | n,k table 0.2–12 µm | Rakić 1995 |
| H2O (water) | n,k table 0.2–200 µm | Hale & Querry 1973 |

Room-temperature density, thermal conductivity, specific heat, Young's
modulus, Poisson ratio, thermal expansion and thermo-optic coefficient are
attached to Si, SiO2, Si3N4 and the metals as handbook-level starting values;
each carries its `source` string. Check them before relying on them.

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
measurement. `tools/build_tables.py` regenerates the embedded tables from a
local copy of the database.

## Self-checks

```bash
pip install pytest pyyaml
PYTHONPATH=. python3 -m pytest -q tests
```

Checked against published values (fused-silica n_d = 1.4585, Si n(1.55) =
3.4777, sapphire/MgF2/CaF2 n_d, gold ε(800 nm) ≈ −24 + 1.5i), physical
constraints (Im ε ≥ 0, Drude zero crossing at ω_p, ε → ε∞), hand-evaluated
formulas 2–9, a synthetic Drude–Lorentz fit recovered to 1e-3, a gold fit
within 5 % over 400–1000 nm, and — when a local copy of the database is
present — every one of its 3500+ records parsing and agreeing with the
built-ins.

## License

Apache License 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Yongha Kim (FieldAlgo)

The embedded optical data is not covered by that grant. It comes from the
refractiveindex.info database and is CC0 1.0 (public domain) - see
[Data license](#data-license) above and [NOTICE](NOTICE). The Apache-2.0 grant
covers the code.
