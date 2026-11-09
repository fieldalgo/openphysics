# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""physmat — material properties for physics solvers, starting with optical dispersion.

    import physmat
    si = physmat.get("Si")                 # built-in, with citation in si.source
    si.n(1.55)                             # 3.4757  (wavelength in micrometres)
    si.eps(1.55)                           # complex permittivity (n + i k)^2, exp(-i w t)
    physmat.get("Au").index(0.8)           # 0.15 + 4.9j from Johnson & Christy
    physmat.standard_air(20, 101325, humidity=0.5).n(0.633)   # moist air, Ciddor 1996
    physmat.get("Cu").get("thermal_conductivity", 77.0)        # 544 W/(m K), Hust & Lankford 1984, RRR 100
    physmat.thermal.thermal_conductivity("W", 300.0, rrr=100)  # tungsten, same equation

    db = physmat.rii.Database("path/to/refractiveindex.info-database")   # CC0 database
    rec = db.load("main/SiO2/Malitson"); rec.dispersion.n(0.5876)

    fit = physmat.fit_drude_lorentz(physmat.get("Au").optical, np.linspace(0.4, 1.0, 60), n_lorentz=2)
    fit.model.eps(0.8), fit.rms_eps

Conventions: wavelength in um; n~ = n + i k with k >= 0 for loss; eps = n~^2.

    from physmat.units import q              # quantity registry and exact unit converter
    q("200 GPa", "youngs_modulus")           # 200000000000.0 (Pa)

Submodules and names load on first use, so ``import physmat.units`` needs only the
standard library (numpy and scipy are imported by the material modules).
"""

import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:                                   # the eager imports, for static tools only
    from . import air, dispersion, fit, library, rii, thermal, units
    from .air import CiddorAir
    from .dispersion import (Composite, Constant, Dispersion, Drude, DrudeLorentz, OutOfRange, RIIFormula,
                             Sellmeier, Tabulated, ev_to_um, um_to_ev)
    from .fit import FitResult, fit_drude_lorentz
    from .library import constant, get, names, standard_air
    from .material import Material, Property
    from .thermal import HustLankford

__version__ = "0.0.2"
__all__ = ["get", "names", "constant", "standard_air", "CiddorAir", "Material", "Property", "Dispersion", "Constant",
           "Sellmeier", "Tabulated", "Composite", "Drude", "DrudeLorentz", "RIIFormula", "OutOfRange", "ev_to_um",
           "um_to_ev", "fit_drude_lorentz", "FitResult", "HustLankford", "air", "dispersion", "fit", "library", "rii",
           "thermal", "units", "__version__"]

_SUBMODULES = ("air", "dispersion", "fit", "library", "material", "rii", "thermal", "units")
_NAMES = {
    "CiddorAir": "air",
    "Composite": "dispersion", "Constant": "dispersion", "Dispersion": "dispersion", "Drude": "dispersion",
    "DrudeLorentz": "dispersion", "OutOfRange": "dispersion", "RIIFormula": "dispersion", "Sellmeier": "dispersion",
    "Tabulated": "dispersion", "ev_to_um": "dispersion", "um_to_ev": "dispersion",
    "FitResult": "fit", "fit_drude_lorentz": "fit",
    "constant": "library", "get": "library", "names": "library", "standard_air": "library",
    "Material": "material", "Property": "material",
    "HustLankford": "thermal",
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
