# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Material = a name, an optical dispersion model, and a bag of other physical properties.

Only the optical part is populated in depth for now; the ``properties`` slot
is where thermal and mechanical data (thermal conductivity, specific heat,
Young's modulus, ...) go as the solver grows into other physics. Each property
is a ``Property`` with a value (constant, or a callable of temperature), a
unit string, and a source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .dispersion import Dispersion


@dataclass
class Property:
    value: float | Callable[[np.ndarray], np.ndarray]
    unit: str
    source: str = ""

    def __call__(self, T: float | np.ndarray = 293.15):
        return self.value(np.asarray(T, dtype=float)) if callable(self.value) else self.value


@dataclass
class Material:
    name: str
    optical: Dispersion | None = None
    source: str = ""                       # citation for the optical model
    properties: dict[str, Property] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()

    # -- optical shortcuts -------------------------------------------------

    def index(self, wavelength_um, strict: bool = True):
        self._need_optical()
        return self.optical.index(wavelength_um, strict)

    def n(self, wavelength_um, strict: bool = True):
        self._need_optical()
        return self.optical.n(wavelength_um, strict)

    def k(self, wavelength_um, strict: bool = True):
        self._need_optical()
        return self.optical.k(wavelength_um, strict)

    def eps(self, wavelength_um, strict: bool = True):
        self._need_optical()
        return self.optical.eps(wavelength_um, strict)

    @property
    def range_um(self):
        self._need_optical()
        return self.optical.range_um

    def _need_optical(self):
        if self.optical is None:
            raise ValueError(f"material {self.name!r} has no optical model")

    # -- other physics -----------------------------------------------------

    def get(self, prop: str, T: float | np.ndarray = 293.15):
        if prop not in self.properties:
            raise KeyError(f"material {self.name!r} has no property {prop!r}; available: {sorted(self.properties)}")
        return self.properties[prop](T)

    def __repr__(self) -> str:
        opt = f"{type(self.optical).__name__} {self.optical.range_um} um" if self.optical else "no optical model"
        return f"Material({self.name!r}, {opt}, properties={sorted(self.properties)})"
