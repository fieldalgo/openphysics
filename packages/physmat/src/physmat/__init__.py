# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""physmat — material properties for physics solvers, starting with optical dispersion.

    import physmat
    si = physmat.material("Si")                                  # built-in, exact name; citation in si.source
    si.refractive_index(vacuum_wavelength=1.55e-6)               # (3.4777+0j): n + i k, metres in
    si.relative_permittivity(vacuum_wavelength=1.55e-6)          # (n + i k)^2, exp(-i w t): Im >= 0 is loss
    si.valid_vacuum_wavelength                                   # (1.357e-06, 1.104e-05) m
    si.property("thermal_conductivity", temperature=300.0)       # 148.0 W/(m K); temperature required
    physmat.material("Au").refractive_index(vacuum_wavelength=8e-7)   # 0.15 + 4.9j, Johnson & Christy
    physmat.ciddor_air(temperature=293.15, absolute_pressure=101325.0, relative_humidity=0.5,
                       co2_mole_fraction=450e-6)                 # moist air, Ciddor 1996
    physmat.metal_thermal_conductivity("W", temperature=300.0, residual_resistivity_ratio=100.0)
    glass = physmat.Material("my glass", physmat.constant_model(refractive_index=1.5))

Conventions: SI arguments (vacuum wavelength in m, temperature in K, pressure in Pa,
mole fractions); n~ = n + i k with k >= 0 for loss; eps = n~^2, under exp(-i omega t).
A quantity given as a str raises TypeError: convert text with physmat.units.q.

    from physmat.units import q              # quantity registry and exact unit converter
    q("200 GPa", "youngs_modulus")           # 200000000000.0 (Pa)

The optical models and their micrometre and electronvolt helpers are physmat.kernels:
internal, consistent units, not part of this API. ``physmat.rii`` reads the
refractiveindex.info database (CC0) into such a model.

Submodules and names load on first use, so ``import physmat.units`` needs only the
standard library (numpy and scipy are imported by the material modules).
"""

import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:                                   # the eager imports, for static tools only
    from . import rii, units
    from ._api import ciddor_air, constant_model, material, metal_thermal_conductivity, names, sellmeier_model
    from ._material import Material, Property
    from .dispersion import OutOfRange
    from .thermal import MINIMUM_TEMPERATURE

__version__ = "0.0.2"
__all__ = ["material", "names", "Material", "Property", "OutOfRange", "ciddor_air", "metal_thermal_conductivity",
           "MINIMUM_TEMPERATURE", "constant_model", "sellmeier_model", "rii", "units", "__version__"]

_SUBMODULES = ("rii", "units")
_NAMES = {
    "material": "_api", "names": "_api", "ciddor_air": "_api", "metal_thermal_conductivity": "_api",
    "constant_model": "_api", "sellmeier_model": "_api",
    "Material": "_material", "Property": "_material",
    "OutOfRange": "dispersion",
    "MINIMUM_TEMPERATURE": "thermal",
}


def __getattr__(name):
    # Load a submodule or a public name on first use and keep it.
    if name in _SUBMODULES:
        return _importlib.import_module(f"{__name__}.{name}")
    if name in _NAMES:
        value = getattr(_importlib.import_module(f"{__name__}.{_NAMES[name]}"), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    # The names of the eager package: module globals without the loader's helpers, plus everything loadable.
    return sorted((set(globals()) - {"_importlib", "TYPE_CHECKING", "_SUBMODULES", "_NAMES"}) | set(__all__)
                  | set(_SUBMODULES))
