# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""physmat's public functions in SI (re-exported by the top level; this module is private).

Every quantity argument is a keyword-only registry name in its canonical SI unit and
refuses a ``str`` ("SI numbers only"). Each function converts its SI values to the unit
of a kernel of ``physmat.kernels`` (micrometres, degrees Celsius, ppm) with the decimal
rule of ``physmat._si`` and builds or calls that kernel unchanged:

- ``material(name)``, ``names()``: the built-in library, exact names;
- ``ciddor_air(...)``: moist air at chosen conditions (kelvin, pascal, mole fraction);
- ``metal_thermal_conductivity(metal, ...)``: the Hust and Lankford (1984) equation;
- ``constant_model(...)`` and ``sellmeier_model(...)``: optical models of the two forms a
  document's ``refractive_index`` accepts, for ``Material(name, optical=...)``.
"""

from __future__ import annotations

import math
from fractions import Fraction

from . import _si, air, library, thermal
from ._material import Material
from .dispersion import Constant, OutOfRange, Sellmeier


def names() -> list[str]:
    """The names of the built-in materials (``physmat.material`` takes exactly these)."""
    return library.names()


def material(name: str) -> Material:
    """The built-in material ``name``, matched exactly (no case folding, no aliases)."""
    if not isinstance(name, str):
        raise TypeError(f"a material name is a str, not {type(name).__name__}")
    try:
        return library.BY_NAME[name]
    except KeyError:
        raise KeyError(f"unknown material {name!r}; names are exact (no case folding, no aliases); "
                       f"available: {library.names()}") from None


def ciddor_air(*, temperature, absolute_pressure, relative_humidity, co2_mole_fraction, vapor_pressure=None,
               strict: bool = True, name: str | None = None) -> Material:
    """Moist air after Ciddor (1996) at the given conditions, as a Material (0.3-1.69 µm).

    ``temperature`` in K, ``absolute_pressure`` in Pa, ``relative_humidity`` as a fraction
    (0.5 = 50 %) and ``co2_mole_fraction`` as a mole fraction (450e-6 = 450 ppm), all required.
    Give the partial pressure of water vapour ``vapor_pressure`` (Pa) instead of the humidity
    with ``relative_humidity=None``. ``strict=False`` accepts conditions outside Ciddor's stated
    ranges (-40 to +100 degC, 80-120 kPa, 0-100 % RH, 0-2000 ppm CO2). The ``density`` property
    (kg/m^3) is the BIPM 1981/91 moist-air density at the same pressure, humidity and CO2, as a
    function of temperature in K. The kernel takes degrees Celsius and ppm, computed with the
    decimal rule: ``Fraction(repr(T)) - 273.15`` and ``Fraction(repr(x)) * 10**6``, each rounded once.
    """
    for key, value in (("absolute_pressure", absolute_pressure), ("relative_humidity", relative_humidity),
                       ("co2_mole_fraction", co2_mole_fraction), ("vapor_pressure", vapor_pressure)):
        _si.refuse_text(key, value)
    temperature_c = _si.celsius("temperature", temperature)
    co2_ppm = _si.scaled_scalar(co2_mole_fraction, 6)
    if relative_humidity is None and vapor_pressure is None:
        raise ValueError("give relative_humidity, or vapor_pressure with relative_humidity=None")
    if relative_humidity is not None and vapor_pressure is not None and relative_humidity != 0.0:
        raise ValueError("give either relative_humidity or vapor_pressure (with relative_humidity=None), not both")
    try:
        model = air.CiddorAir(temperature_c, absolute_pressure, relative_humidity, co2_ppm, vapor_pressure, strict)
    except OutOfRange as exc:
        raise OutOfRange(_kelvin_message(str(exc))) from None
    rest = f"{absolute_pressure:g} Pa, "
    rest += f"pv = {vapor_pressure:g} Pa" if vapor_pressure is not None else f"RH {100 * relative_humidity:g} %"
    rest += f", CO2 mole fraction {co2_mole_fraction:g}"
    conditions = f"{temperature:g} K, {rest}"
    return Material(name or f"ciddor_air ({conditions})", model, f"{air.CITATION} [{conditions}]",
                    properties={"density": library._density_property(model, rest)},
                    datum_temperature=float(temperature))


def _kelvin_message(message: str) -> str:
    """The Ciddor kernel's validity message with its stated ranges in the public units."""
    return (message.replace("temperature outside [-40, 100] C", "temperature outside [233.15, 373.15] K")
                   .replace("pressure outside", "absolute_pressure outside")
                   .replace("CO2 content outside [0, 2000] ppm", "co2_mole_fraction outside [0, 0.002]")
                   .replace("relative humidity outside", "relative_humidity outside")
                   .replace("water vapour pressure above saturation", "vapor_pressure above saturation"))


def metal_thermal_conductivity(metal: str, *, temperature, residual_resistivity_ratio, strict: bool = True):
    """Thermal conductivity in W/(m K) of ``"Cu"``, ``"Al"`` or ``"W"`` after Hust and Lankford (1984).

    ``temperature`` in K (a number or an array), ``residual_resistivity_ratio`` the purity
    (RRR = rho(273 K) / rho(0 K), above 1). The stated validity is ``MINIMUM_TEMPERATURE``
    (1 K) to the melting point and the RRR range of the fitted data; outside it the
    function raises ``OutOfRange`` unless ``strict=False``. The metal name is exact.
    """
    _si.refuse_text("temperature", temperature)
    _si.refuse_text("residual_resistivity_ratio", residual_resistivity_ratio)
    if not isinstance(metal, str) or metal not in thermal.METALS:
        raise KeyError(f"no Hust-Lankford parameters for {metal!r}; metals are exact: {sorted(thermal.METALS)}")
    return thermal.HustLankford(metal, residual_resistivity_ratio, strict)(temperature)


def constant_model(*, refractive_index):
    """A non-dispersive optical model n + i k (k >= 0 for loss), for ``Material(name, optical=...)``.

    ``refractive_index`` is a real or complex number; its real and imaginary parts are kept as
    given (a ``-0.0`` imaginary part stays ``-0.0``) and evaluated as ``n + 1j * k``, as the
    kernel ``Constant`` does. The model is valid at every vacuum wavelength.
    """
    _si.refuse_text("refractive_index", refractive_index)
    z = complex(refractive_index)
    return Constant(float(z.real), float(z.imag))


def sellmeier_model(*, strength, resonance_wavelength_squared=None, resonance_wavelength=None, constant=1.0,
                    valid_vacuum_wavelength=None):
    """A Sellmeier optical model, n^2 = constant + sum_i strength_i lambda^2 / (lambda^2 - C_i).

    ``strength`` is the sequence of B_i (dimensionless). Give exactly one of
    ``resonance_wavelength_squared`` (the C_i in m^2) and ``resonance_wavelength`` (lambda_i in m,
    C_i = lambda_i^2), with one value per term. ``constant`` is the whole n^2 offset (default 1).
    ``valid_vacuum_wavelength`` is ``(low, high)`` in m, ``low`` None for an open lower bound;
    without it the model is valid at every wavelength. The kernel takes micrometres: each
    C_i is ``Fraction(repr(C)) * 10**12`` (or ``(Fraction(repr(lambda)) * 10**6)**2``) and each
    bound ``Fraction(repr(x)) * 10**6``, rounded once (the decimal rule).
    """
    for key, value in (("strength", strength), ("resonance_wavelength_squared", resonance_wavelength_squared),
                       ("resonance_wavelength", resonance_wavelength), ("constant", constant)):
        _si.refuse_text(key, value)
    _si.refuse_text("valid_vacuum_wavelength", valid_vacuum_wavelength, "vacuum_wavelength")
    if (resonance_wavelength_squared is None) == (resonance_wavelength is None):
        raise ValueError("give exactly one of resonance_wavelength_squared and resonance_wavelength")
    strengths = [float(b) for b in strength]
    if resonance_wavelength_squared is not None:
        squares = [_si.scaled_scalar(c, 12) for c in resonance_wavelength_squared]
    else:
        squares = [_squared_micrometres(r) for r in resonance_wavelength]
    if not strengths or len(strengths) != len(squares):
        raise ValueError(f"a Sellmeier model needs one resonance per strength and at least one term "
                         f"({len(strengths)} strengths, {len(squares)} resonances)")
    if valid_vacuum_wavelength is None:
        bounds = (0.0, math.inf)
    else:
        low, high = valid_vacuum_wavelength
        bounds = (0.0 if low is None else _si.scaled_scalar(low, 6), math.inf if high is None else
                  _si.scaled_scalar(high, 6))
    return Sellmeier(strengths, squares, float(constant), bounds)


def _squared_micrometres(metres) -> float:
    x = float(metres)
    if not math.isfinite(x):
        return x * x
    return float((Fraction(repr(x)) * 10 ** 6) ** 2)
