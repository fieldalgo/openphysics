# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Built-in materials with their sources.

Optical models are taken from the refractiveindex.info database (CC0 1.0), which
cites the original measurements; the citation of each record is kept in
``Material.source``. Sellmeier-type coefficients are stored as refractiveindex.info
formulas so they can be compared 1:1 with the database. A handful of thermal and
mechanical constants (room temperature, order-of-magnitude reference values from
standard handbooks) are attached to the most common materials as a starting
point for multiphysics — check them against your own data before relying on them.

Look-up is case-insensitive and accepts aliases: ``get("sio2")``, ``get("silica")``,
``get("fused silica")`` all return the same material.
"""

from __future__ import annotations

import numpy as np

from . import _tables
from .dispersion import Constant, RIIFormula, Tabulated
from .material import Material, Property

RII_CITE = 'via refractiveindex.info (CC0): M. N. Polyanskiy, Sci. Data 11, 94 (2024)'


def _f(kind, coeffs, lo, hi, label):
    return RIIFormula(kind, coeffs, (lo, hi), label)


def _tab(key, label):
    t = _tables.TABLES[key]
    return Tabulated(t[:, 0], t[:, 1], t[:, 2], label), _tables.REFERENCES[key] + "; " + RII_CITE


_MATERIALS: list[Material] = []


def _add(m: Material):
    _MATERIALS.append(m)
    return m


# ---- vacuum / air ---------------------------------------------------------
_add(Material("vacuum", Constant(1.0, 0.0, "vacuum"), "definition", aliases=("air",)))

# ---- dielectrics: Sellmeier-type formulas ----------------------------------
_add(Material(
    "SiO2", _f(1, [0, 0.6961663, 0.0684043, 0.4079426, 0.1162414, 0.8974794, 9.896161], 0.21, 6.7, "SiO2:Malitson"),
    "I. H. Malitson, J. Opt. Soc. Am. 55, 1205 (1965) [fused silica, 20 C]; " + RII_CITE,
    properties={
        "density": Property(2203.0, "kg/m^3", "handbook value, fused silica"),
        "thermal_conductivity": Property(1.38, "W/(m K)", "handbook value, 300 K"),
        "specific_heat": Property(740.0, "J/(kg K)", "handbook value, 300 K"),
        "youngs_modulus": Property(72.0e9, "Pa", "handbook value"),
        "poisson_ratio": Property(0.17, "-", "handbook value"),
        "thermal_expansion": Property(0.55e-6, "1/K", "handbook value, 300 K"),
        "thermo_optic_dn_dT": Property(1.0e-5, "1/K", "typical value at 1.55 um, 300 K"),
    },
    aliases=("silica", "fused silica", "silicon dioxide", "glass")))

_add(Material(
    "Si", _f(1, [0, 10.6684293, 0.301516485, 0.0030434748, 1.13475115, 1.54133408, 1104], 1.357, 11.04, "Si:Salzberg"),
    "C. D. Salzberg and J. J. Villa, J. Opt. Soc. Am. 47, 244 (1957) [transparent IR range]; " + RII_CITE,
    properties={
        "density": Property(2329.0, "kg/m^3", "handbook value"),
        "thermal_conductivity": Property(148.0, "W/(m K)", "handbook value, 300 K"),
        "specific_heat": Property(700.0, "J/(kg K)", "handbook value, 300 K"),
        "youngs_modulus": Property(170.0e9, "Pa", "handbook value, <110>"),
        "poisson_ratio": Property(0.28, "-", "handbook value"),
        "thermal_expansion": Property(2.6e-6, "1/K", "handbook value, 300 K"),
        "thermo_optic_dn_dT": Property(1.8e-4, "1/K", "typical value at 1.55 um, 300 K"),
    },
    aliases=("silicon", "c-Si")))

_si_green, _si_green_ref = _tab("Si_Green2008", "Si:Green2008")
_add(Material("Si_visible", _si_green, _si_green_ref + " [n and k, 0.25-1.45 um, 300 K]",
              aliases=("silicon visible", "si-nk")))

_add(Material(
    "Si3N4", _f(1, [0, 3.0249, 0.1353406, 40314, 1239.842], 0.310, 5.504, "Si3N4:Luke"),
    "K. Luke et al., Opt. Lett. 40, 4823 (2015) [LPCVD stoichiometric]; " + RII_CITE,
    properties={
        "density": Property(3170.0, "kg/m^3", "handbook value"),
        "thermal_conductivity": Property(20.0, "W/(m K)", "handbook value, film, order of magnitude"),
        "youngs_modulus": Property(250.0e9, "Pa", "handbook value"),
        "poisson_ratio": Property(0.23, "-", "handbook value"),
        "thermal_expansion": Property(3.3e-6, "1/K", "handbook value"),
    },
    aliases=("silicon nitride", "sin", "nitride")))

_add(Material(
    "GaAs", _f(1, [4.372514, 5.466742, 0.4431307, 0.02429960, 0.8746453, 1.957522, 36.9166], 0.97, 17, "GaAs:Skauli"),
    "T. Skauli et al., J. Appl. Phys. 94, 6447 (2003); " + RII_CITE,
    properties={"density": Property(5317.0, "kg/m^3", "handbook value"),
                "thermal_conductivity": Property(55.0, "W/(m K)", "handbook value, 300 K")},
    aliases=("gallium arsenide",)))

_add(Material(
    "InP", _f(1, [6.255, 2.316, 0.6263, 2.765, 32.935], 0.95, 10, "InP:Pettit"),
    "G. D. Pettit and W. J. Turner, J. Appl. Phys. 36, 2081 (1965); " + RII_CITE,
    aliases=("indium phosphide",)))

_add(Material(
    "Ge", _f(2, [0, 0.4886331, 1.393959, 14.5142535, 0.1626427, 0.0091224, 752.190], 2, 14.0, "Ge:Burnett"),
    "J. H. Burnett et al., Proc. SPIE 9974, 99740X (2016); " + RII_CITE,
    aliases=("germanium",)))

_add(Material(
    "Al2O3", _f(1, [0, 1.4313493, 0.0726631, 0.65054713, 0.1193242, 5.3414021, 18.028251], 0.20, 5.0, "Al2O3:Malitson-o"),
    "I. H. Malitson and M. J. Dodge, J. Opt. Soc. Am. 62, 1405 (1972) [sapphire, ordinary ray]; " + RII_CITE,
    properties={"density": Property(3980.0, "kg/m^3", "handbook value"),
                "thermal_conductivity": Property(35.0, "W/(m K)", "handbook value, 300 K")},
    aliases=("sapphire", "alumina")))

_add(Material(
    "MgF2", _f(1, [0, 0.48755108, 0.04338408, 0.39875031, 0.09461442, 2.3120353, 23.793604], 0.2, 7.0, "MgF2:Dodge-o"),
    "M. J. Dodge, Appl. Opt. 23, 1980 (1984) [ordinary ray]; " + RII_CITE,
    aliases=("magnesium fluoride",)))

_add(Material(
    "CaF2", _f(1, [0, 0.5675888, 0.050263605, 0.4710914, 0.1003909, 3.8484723, 34.649040], 0.23, 9.7, "CaF2:Malitson"),
    "I. H. Malitson, Appl. Opt. 2, 1103 (1963); " + RII_CITE,
    aliases=("calcium fluoride",)))

_add(Material(
    "LiNbO3", _f(2, [0, 2.6734, 0.01764, 1.2290, 0.05914, 12.614, 474.60], 0.4, 5.0, "LiNbO3:Zelmon-o"),
    "D. E. Zelmon et al., J. Opt. Soc. Am. B 14, 3319 (1997) [ordinary ray, congruent]; " + RII_CITE,
    aliases=("lithium niobate", "LN")))

_add(Material(
    "TiO2", _f(4, [5.913, 0.2441, 0, 0.0803, 1, 0, 0, 0, 1], 0.43, 1.53, "TiO2:Devore-o"),
    "J. R. DeVore, J. Opt. Soc. Am. 41, 416 (1951) [rutile, ordinary ray]; " + RII_CITE,
    aliases=("titanium dioxide", "rutile")))

# ---- metals and water: measured tables -------------------------------------
for _key, _name, _aliases in (("Au_Johnson", "Au", ("gold",)), ("Ag_Johnson", "Ag", ("silver",)),
                              ("Cu_Johnson", "Cu", ("copper",)), ("Al_Rakic", "Al", ("aluminum", "aluminium")),
                              ("H2O_Hale", "H2O", ("water",))):
    _disp, _ref = _tab(_key, _name)
    _props = {}
    if _name == "Au":
        _props = {"density": Property(19300.0, "kg/m^3", "handbook value"),
                  "thermal_conductivity": Property(317.0, "W/(m K)", "handbook value, 300 K"),
                  "electrical_conductivity": Property(4.1e7, "S/m", "handbook value, 300 K")}
    elif _name == "Cu":
        _props = {"density": Property(8960.0, "kg/m^3", "handbook value"),
                  "thermal_conductivity": Property(401.0, "W/(m K)", "handbook value, 300 K"),
                  "electrical_conductivity": Property(5.96e7, "S/m", "handbook value, 300 K")}
    elif _name == "Al":
        _props = {"density": Property(2700.0, "kg/m^3", "handbook value"),
                  "thermal_conductivity": Property(237.0, "W/(m K)", "handbook value, 300 K"),
                  "electrical_conductivity": Property(3.5e7, "S/m", "handbook value, 300 K")}
    elif _name == "Ag":
        _props = {"density": Property(10490.0, "kg/m^3", "handbook value"),
                  "thermal_conductivity": Property(429.0, "W/(m K)", "handbook value, 300 K"),
                  "electrical_conductivity": Property(6.3e7, "S/m", "handbook value, 300 K")}
    _add(Material(_name, _disp, _ref, properties=_props, aliases=_aliases))


# ---------------------------------------------------------------------------

def _key(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


_INDEX: dict[str, Material] = {}
for _m in _MATERIALS:
    for _n in (_m.name, *_m.aliases):
        _INDEX[_key(_n)] = _m


def get(name: str) -> Material:
    """Built-in material by name or alias (case/space-insensitive)."""
    try:
        return _INDEX[_key(name)]
    except KeyError:
        raise KeyError(f"unknown material {name!r}; available: {names()}") from None


def names() -> list[str]:
    return [m.name for m in _MATERIALS]


def constant(n: float, k: float = 0.0, name: str | None = None) -> Material:
    """A user-defined non-dispersive material."""
    return Material(name or f"n={n}", Constant(n, k), "user-defined")
