# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""SI arguments of physmat's public functions: the string refusal and the decimal rule.

Private helpers. The kernels (``physmat.kernels``) keep their micrometres, electronvolts,
degrees Celsius and ppm; a public function refuses a ``str`` for each quantity, converts
its SI value to the kernel's unit with the **decimal rule** and calls the kernel unchanged.

The decimal rule (phase-3 decision D31) scales the shortest decimal that names a double,
``Fraction(repr(float(x)))``, exactly and rounds once: metres to micrometres is
``float(Fraction(repr(float(x))) * 10**6)``. For a value written with at most 15
significant digits this is the double of the exact decimal value in the kernel's unit
(``1.6e-06`` m gives 1.6 µm, where ``1.6e-06 * 1e6`` gives 1.5999999999999999). A
value that is not finite is passed through unchanged.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

#: The example text of the TypeError for a quantity given as a string (dimensional
#: quantities name a unit of their menu; dimensionless ones a bare number).
_EXAMPLES = {
    "vacuum_wavelength": "1550 nm",
    "temperature": "300 K",
    "absolute_pressure": "101.325 kPa",
    "relative_humidity": "50 %",
    "co2_mole_fraction": "450 ppm",
    "vapor_pressure": "1.2 kPa",
    "resonance_wavelength": "68.4043 nm",
    "resonance_wavelength_squared": "0.00467914825849 um^2",
}
_NUMBERS = {"refractive_index": "1.45", "residual_resistivity_ratio": "100", "strength": "0.6961663",
            "constant": "1"}

_CELSIUS_ZERO = Fraction(27315, 100)          # 273.15 K, exact


def _has_text(value) -> bool:
    if isinstance(value, (str, bytes)):
        return True
    if isinstance(value, np.ndarray):
        if value.dtype.kind in "SU":
            return True
        return value.dtype.kind == "O" and any(_has_text(v) for v in value.ravel())
    if isinstance(value, (list, tuple)):
        return any(_has_text(v) for v in value)
    return False


def refuse_text(name: str, value, quantity: str | None = None) -> None:
    """``TypeError`` when ``value`` (the argument ``name``) is or holds a ``str``: SI numbers only."""
    if not _has_text(value):
        return
    quantity = quantity or name
    if quantity in _NUMBERS:
        raise TypeError(f"{name}: SI numbers only; {quantity} is dimensionless, so give a number such as "
                        f"{_NUMBERS[quantity]}")
    example = _EXAMPLES.get(quantity, "1 m")
    raise TypeError(f"{name}: SI numbers only; convert with physmat.units.q({example!r}, {quantity!r})")


def _scale(x: float, power: int) -> float:
    if not math.isfinite(x):
        return x
    return float(Fraction(repr(x)) * Fraction(10) ** power)


def scaled(value, power: int) -> np.ndarray:
    """``value * 10**power`` by the decimal rule, element by element (an array of the input's shape)."""
    arr = np.asarray(value, dtype=float)
    return np.array([_scale(float(v), power) for v in arr.ravel()], dtype=float).reshape(arr.shape)


def scaled_scalar(value, power: int) -> float:
    """``float(value) * 10**power`` by the decimal rule, for one number."""
    return _scale(float(value), power)


def micrometres(name: str, value) -> np.ndarray:
    """A vacuum wavelength in metres as the kernels' micrometre doubles (decimal rule, per element)."""
    refuse_text(name, value, "vacuum_wavelength")
    return scaled(value, 6)


def metres(micrometre: float) -> float:
    """A kernel bound in micrometres in metres (the decimal rule back; ``inf`` stays ``inf``)."""
    return scaled_scalar(micrometre, -6)


def celsius(name: str, kelvin) -> float:
    """A temperature in K in degrees Celsius for the Ciddor kernels: ``Fraction(repr(T)) - 273.15``, rounded once."""
    refuse_text(name, kelvin, "temperature")
    x = float(kelvin)
    if not math.isfinite(x):
        return x - 273.15
    return float(Fraction(repr(x)) - _CELSIUS_ZERO)
