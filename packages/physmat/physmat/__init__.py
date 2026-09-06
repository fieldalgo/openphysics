# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""physmat — material properties for physics solvers, starting with optical dispersion.

    import physmat
    si = physmat.get("Si")                 # built-in, with citation in si.source
    si.n(1.55)                             # 3.4757  (wavelength in micrometres)
    si.eps(1.55)                           # complex permittivity (n + i k)^2, exp(-i w t)
    physmat.get("Au").index(0.8)           # 0.15 + 4.9j from Johnson & Christy

    db = physmat.rii.Database("path/to/refractiveindex.info-database")   # CC0 database
    rec = db.load("main/SiO2/Malitson"); rec.dispersion.n(0.5876)

    fit = physmat.fit_drude_lorentz(physmat.get("Au").optical, np.linspace(0.4, 1.0, 60), n_lorentz=2)
    fit.model.eps(0.8), fit.rms_eps

Conventions: wavelength in um; n~ = n + i k with k >= 0 for loss; eps = n~^2.
"""

from . import dispersion, fit, library, rii
from .dispersion import (Composite, Constant, Dispersion, Drude, DrudeLorentz, OutOfRange, RIIFormula,
                         Sellmeier, Tabulated, ev_to_um, um_to_ev)
from .fit import FitResult, fit_drude_lorentz
from .library import constant, get, names
from .material import Material, Property

__version__ = "0.1.0"
__all__ = ["get", "names", "constant", "Material", "Property", "Dispersion", "Constant", "Sellmeier",
           "Tabulated", "Composite", "Drude", "DrudeLorentz", "RIIFormula", "OutOfRange", "ev_to_um",
           "um_to_ev", "fit_drude_lorentz", "FitResult", "dispersion", "fit", "library", "rii", "__version__"]
