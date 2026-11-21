# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""physmat's kernels: today's optical models and their micrometre and electronvolt helpers.

Internal module, consistent units: not part of physmat's public API (the ``__all__``
of its public modules). Nothing here is in ``physmat.__all__``, and no public name
equals a name of this namespace.

The kernels compute in the units of their sources: vacuum wavelengths in micrometres,
energies in electronvolts, the Ciddor air model in degrees Celsius, pascal, a humidity
fraction and ppm of CO2, and the Hust and Lankford conductivity in kelvin. They are
re-exported here unchanged from their modules (``physmat.dispersion``, ``physmat.air``,
``physmat.fit`` and ``physmat.thermal``). The public functions (``physmat.material``,
``physmat.Material.refractive_index``, ``physmat.ciddor_air``, the ``*_model``
constructors, ...) take SI values, convert them with the decimal rule and build or call
these kernels. ``simcase`` calls them directly with its own exact-derived micrometre
doubles (an inter-package contract: simcase pins physmat to one version).

- dispersion models (``Dispersion`` and its subclasses): ``index(wavelength_um, strict)``,
  ``n``, ``k``, ``eps``, ``group_index`` and ``range_um``, under exp(-i omega t) with k >= 0
  for loss; ``DrudeLorentz.eps_of_energy`` in eV; ``ev_to_um``, ``um_to_ev`` and ``HC_EV_UM``;
- ``fit_drude_lorentz`` and its ``FitResult``;
- ``CiddorAir`` and the module ``air`` with Ciddor's component equations and constants
  (``air.refractive_index``, ``air.refractivity``, ``air.density``, ``air.STANDARD_CO2_PPM``, ...);
- ``HustLankford``, ``thermal_conductivity``, ``conductivity_property``, ``METALS``,
  ``DEFAULT_RRR`` and ``LORENZ_NUMBER``.
"""

from . import air
from .air import CiddorAir
from .dispersion import (HC_EV_UM, Composite, Constant, Dispersion, Drude, DrudeLorentz, RIIFormula, Sellmeier,
                         Tabulated, ev_to_um, um_to_ev)
from .fit import FitResult, fit_drude_lorentz
from .thermal import DEFAULT_RRR, LORENZ_NUMBER, METALS, HustLankford, conductivity_property, thermal_conductivity

__all__ = ["Dispersion", "Constant", "Sellmeier", "Tabulated", "Composite", "Drude", "DrudeLorentz", "RIIFormula",
           "HC_EV_UM", "ev_to_um", "um_to_ev", "fit_drude_lorentz", "FitResult", "CiddorAir", "air", "HustLankford",
           "thermal_conductivity", "conductivity_property", "METALS", "DEFAULT_RRR", "LORENZ_NUMBER"]
