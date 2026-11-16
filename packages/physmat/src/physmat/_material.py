# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Material = a name, an optical dispersion model, and a bag of other physical properties.

The public record classes ``physmat.Material`` and ``physmat.Property`` (this module is
private; ``physmat.material(name)`` is the library look-up). Their arguments are SI:
the optical methods take ``vacuum_wavelength`` in metres, and a property is evaluated
at a ``temperature`` in kelvin, which is required.

The optical model in ``Material.optical`` is a kernel of ``physmat.kernels`` (internal,
consistent units: micrometres). ``refractive_index`` and ``relative_permittivity``
convert the vacuum wavelength to the kernel's micrometre double with the decimal rule,
``float(Fraction(repr(float(x))) * 10**6)`` per element (exact for a value of at most 15
significant digits), and evaluate the kernel unchanged: n + i k with k >= 0 for loss,
and n~^2, under exp(-i omega t).

The ``properties`` slot holds the thermal and mechanical data (thermal conductivity,
specific heat, Young's modulus, ...). Each property is a ``Property`` with a value
(constant, or a callable of temperature in kelvin), a unit string, and a source. Its
keys, its unit strings and the datum fields are today's; the materials step after
0.0.2 moves them to the registry's names.

``datum_temperature`` is the temperature (K) at which the source of the optical
data states them; ``datum_assumed`` is True for a library record whose source
states none, so that a reader can report the assumption (units convention,
answer 3.8). ``vacuum`` has neither: it is exact at every temperature.
``aliases`` are other names a library record is known by; ``physmat.material``
matches names exactly and never uses them.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import _si
from .dispersion import Dispersion, OutOfRange


@dataclass
class Property:
    """One property of a material: a value, its unit string and its source.

    ``value`` is a constant or a callable of temperature in kelvin. Calling the
    property, ``prop(temperature=300.0)``, evaluates it; a constant returns its value
    at every temperature (that is not a temperature law).
    """
    value: float | Callable[[np.ndarray], np.ndarray]
    unit: str
    source: str = ""

    def __call__(self, *, temperature):
        _si.refuse_text("temperature", temperature)
        return self.value(np.asarray(temperature, dtype=float)) if callable(self.value) else self.value


@dataclass
class Material:
    """A material: its name, optical model, citation, properties and datum.

    ``refractive_index(vacuum_wavelength=...)`` and ``relative_permittivity(...)`` take
    the vacuum wavelength in metres (a number or an array) and raise ``OutOfRange``
    outside ``valid_vacuum_wavelength``. ``property(key, temperature=...)`` evaluates
    one of ``properties`` at a temperature in kelvin.
    """
    name: str
    optical: Dispersion | None = None
    source: str = ""                       # citation for the optical model
    properties: dict[str, Property] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    datum_temperature: float | None = None    # K at which the optical source states its data
    datum_assumed: bool = False               # a library record whose source states no temperature

    # -- optical ------------------------------------------------------------

    @builtins.property
    def valid_vacuum_wavelength(self) -> tuple[float, float]:
        """The optical model's validity range ``(low, high)`` of the vacuum wavelength, in metres."""
        low, high = self._need_optical().range_um
        return (_si.metres(low), _si.metres(high))

    def refractive_index(self, *, vacuum_wavelength):
        """Complex refractive index n + i k (k >= 0 for loss, exp(-i omega t)) at vacuum wavelengths in m."""
        model = self._need_optical()
        return self._evaluate(model.index, _si.micrometres("vacuum_wavelength", vacuum_wavelength))

    def relative_permittivity(self, *, vacuum_wavelength):
        """Complex relative permittivity (n + i k)^2 (Im >= 0 for loss, exp(-i omega t)) at vacuum wavelengths in m."""
        model = self._need_optical()
        return self._evaluate(model.eps, _si.micrometres("vacuum_wavelength", vacuum_wavelength))

    def _evaluate(self, method, wavelength_um):
        try:
            return method(wavelength_um, True)
        except OutOfRange:
            low, high = self.valid_vacuum_wavelength
            raise OutOfRange(f"material {self.name!r}: vacuum_wavelength outside its valid range "
                             f"[{low:g}, {high:g}] m") from None

    def _need_optical(self) -> Dispersion:
        if self.optical is None:
            raise ValueError(f"material {self.name!r} has no optical model")
        return self.optical

    # -- other physics -----------------------------------------------------

    def property(self, key: str, *, temperature):
        """The property ``key`` at ``temperature`` in kelvin (required; a constant ignores it)."""
        if key not in self.properties:
            raise KeyError(f"material {self.name!r} has no property {key!r}; available: {sorted(self.properties)}")
        return self.properties[key](temperature=temperature)

    def __repr__(self) -> str:
        if self.optical is None:
            opt = "no optical model"
        else:
            low, high = self.valid_vacuum_wavelength
            opt = f"{type(self.optical).__name__}, vacuum_wavelength {low:g} to {high:g} m"
        return f"Material({self.name!r}, {opt}, properties={sorted(self.properties)})"
