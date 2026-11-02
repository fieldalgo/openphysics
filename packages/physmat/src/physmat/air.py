# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Refractive index of moist air: the equations of Ciddor (1996).

P. E. Ciddor, "Refractive index of air: new equations for the visible and near
infrared", Appl. Opt. 35, 1566-1573 (1996), implemented from the published
equations (Appendices A and B). The procedure is

1. dispersion of standard dry air (15 C, 101325 Pa, 450 ppm CO2) and a CO2
   correction, Eqs. (1), (12);
2. dispersion of pure water vapour at 20 C, 1333 Pa, Eq. (3);
3. the BIPM 1981/91 moist-air density equation (P. Giacomo, Metrologia 18, 33
   (1982); R. S. Davis, Metrologia 29, 67 (1992)): saturation vapour pressure,
   enhancement factor, compressibility Z and the density of the dry-air and
   water-vapour components;
4. the Lorentz-Lorenz mixing rule in the form n - 1 = (rho_a/rho_axs)(n_axs - 1)
   + (rho_w/rho_ws)(n_ws - 1), Eq. (5).

Ciddor states the equations for 0.3-1.69 um, -40 to +100 C, 80-120 kPa, 0-100 %
relative humidity and 0-2000 ppm CO2, with an overall uncertainty of 2-5e-8 in n
under laboratory conditions (NIST estimates about 2e-8 at k = 2, up to 1e-7 at
the extremes). Outside those ranges the formulas are extrapolated when the
``strict`` flags allow it. Conventions follow the rest of physmat: wavelength
is the vacuum wavelength in micrometres; temperatures of the air model are in
degrees Celsius as in Ciddor's paper, while ``Property`` callables keep the
package convention of kelvin.

The molar gas constant is Ciddor's R = 8.314510 J/(mol K); it cancels in the
density ratios, so the value does not affect n.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .dispersion import Dispersion, OutOfRange

# ---- Ciddor's standard conditions and stated validity ------------------------
STANDARD_TEMPERATURE_C = 15.0
STANDARD_PRESSURE_PA = 101325.0
STANDARD_CO2_PPM = 450.0
RANGE_UM = (0.3, 1.69)
VALID_TEMPERATURE_C = (-40.0, 100.0)
VALID_PRESSURE_PA = (80.0e3, 120.0e3)
VALID_HUMIDITY = (0.0, 1.0)
VALID_CO2_PPM = (0.0, 2000.0)

CITATION = ('P. E. Ciddor, "Refractive index of air: new equations for the visible and near infrared", '
            "Appl. Opt. 35, 1566-1573 (1996); density from the BIPM 1981/91 equation, R. S. Davis, "
            "Metrologia 29, 67 (1992)")

# ---- constants of Ciddor (1996), Appendix A ---------------------------------
_K0, _K1, _K2, _K3 = 238.0185, 5792105.0, 57.362, 167917.0          # um^-2 ; Eq. (1)
_W0, _W1, _W2, _W3 = 295.235, 2.6422, -0.032380, 0.004028           # um^2i ; Eq. (3)
_CF = 1.022                                                          # water-vapour correction factor
_A0, _A1, _A2 = 1.58123e-6, -2.9331e-8, 1.1043e-10                  # K/Pa, 1/Pa, 1/(K Pa)
_B0, _B1 = 5.707e-6, -2.051e-8                                       # K/Pa, 1/Pa
_C0, _C1 = 1.9898e-4, -2.376e-6                                      # K/Pa, 1/Pa
_D, _E = 1.83e-11, -0.765e-8                                         # K^2/Pa^2
_P_R1, _T_R1 = 101325.0, 288.15                                      # reference dry air
_Z_A = 0.9995922115                                                  # Z of standard dry air
_P_WS, _T_WS = 1333.0, 293.15                                        # reference water vapour
_R = 8.314510                                                        # J/(mol K)
_M_V = 0.018015                                                      # kg/mol
# saturation vapour pressure over water (Davis 1992), Pa, T in K
_SVP_A, _SVP_B, _SVP_C, _SVP_D = 1.2378847e-5, -1.9121316e-2, 33.93711047, -6.3431645e3
# enhancement factor f = alpha + beta p + gamma t^2
_F_ALPHA, _F_BETA, _F_GAMMA = 1.00062, 3.14e-8, 5.6e-7


# ---- component equations (vectorised over numpy arrays) ----------------------

def saturation_vapour_pressure(temperature_c):
    """Saturation vapour pressure of water in Pa (Davis 1992 form used by Ciddor), T in degrees C."""
    T = np.asarray(temperature_c, dtype=float) + 273.15
    return np.exp(_SVP_A * T * T + _SVP_B * T + _SVP_C + _SVP_D / T)


def enhancement_factor(temperature_c, pressure_pa):
    """Enhancement factor f(p, t) of water vapour in air."""
    t = np.asarray(temperature_c, dtype=float)
    return _F_ALPHA + _F_BETA * np.asarray(pressure_pa, dtype=float) + _F_GAMMA * t * t


def water_mole_fraction(temperature_c, pressure_pa, humidity=0.0, vapour_pressure_pa=None):
    """Mole fraction of water vapour from relative humidity (0-1) or from its partial pressure in Pa."""
    p = np.asarray(pressure_pa, dtype=float)
    if vapour_pressure_pa is None:
        pv = np.asarray(humidity, dtype=float) * saturation_vapour_pressure(temperature_c)
    else:
        pv = np.asarray(vapour_pressure_pa, dtype=float)
    return enhancement_factor(temperature_c, p) * pv / p


def compressibility(temperature_c, pressure_pa, water_mole_fraction=0.0):
    """Compressibility Z of moist air (BIPM 1981/91)."""
    t = np.asarray(temperature_c, dtype=float)
    T = t + 273.15
    p = np.asarray(pressure_pa, dtype=float)
    xw = np.asarray(water_mole_fraction, dtype=float)
    q = p / T
    return (1.0 - q * (_A0 + _A1 * t + _A2 * t * t + (_B0 + _B1 * t) * xw + (_C0 + _C1 * t) * xw * xw)
            + q * q * (_D + _E * xw * xw))


def molar_mass_dry_air(co2_ppm=STANDARD_CO2_PPM):
    """Molar mass of dry air in kg/mol as a function of the CO2 content."""
    return 1e-3 * (28.9635 + 12.011e-6 * (np.asarray(co2_ppm, dtype=float) - 400.0))


def _component_densities(temperature_c, pressure_pa, xw, co2_ppm):
    T = np.asarray(temperature_c, dtype=float) + 273.15
    p = np.asarray(pressure_pa, dtype=float)
    Z = compressibility(temperature_c, p, xw)
    rho_a = p * molar_mass_dry_air(co2_ppm) * (1.0 - xw) / (Z * _R * T)
    rho_w = p * _M_V * xw / (Z * _R * T)
    return rho_a, rho_w


def density(temperature_c, pressure_pa, humidity=0.0, co2_ppm=STANDARD_CO2_PPM, vapour_pressure_pa=None):
    """Density of moist air in kg/m^3 from the BIPM 1981/91 equation (the density step of Ciddor's procedure)."""
    xw = water_mole_fraction(temperature_c, pressure_pa, humidity, vapour_pressure_pa)
    rho_a, rho_w = _component_densities(temperature_c, pressure_pa, xw, co2_ppm)
    return rho_a + rho_w


def _refractivity_standard_air(wavelength_um, co2_ppm):
    s2 = 1.0 / np.asarray(wavelength_um, dtype=float) ** 2
    n_as = 1e-8 * (_K1 / (_K0 - s2) + _K3 / (_K2 - s2))                      # Eq. (1)
    return n_as * (1.0 + 0.534e-6 * (np.asarray(co2_ppm, dtype=float) - 450.0))  # Eq. (12)


def _refractivity_water_vapour(wavelength_um):
    s2 = 1.0 / np.asarray(wavelength_um, dtype=float) ** 2
    return _CF * 1e-8 * (_W0 + _W1 * s2 + _W2 * s2 ** 2 + _W3 * s2 ** 3)      # Eq. (3)


def _check_conditions(temperature_c, pressure_pa, humidity, co2_ppm, vapour_pressure_pa, strict):
    t, p, xc = (np.asarray(v, dtype=float) for v in (temperature_c, pressure_pa, co2_ppm))
    h = None if humidity is None else np.asarray(humidity, dtype=float)
    pv = None if vapour_pressure_pa is None else np.asarray(vapour_pressure_pa, dtype=float)
    if h is not None and pv is not None and np.any(h != 0.0):
        raise ValueError("give either humidity (relative, 0-1) or vapour_pressure_pa, not both")
    if np.any(t <= -273.15):
        raise ValueError("temperature below absolute zero")
    if np.any(p <= 0.0):
        raise ValueError("pressure must be positive")
    if np.any(xc < 0.0) or (h is not None and np.any(h < 0.0)) or (pv is not None and np.any(pv < 0.0)):
        raise ValueError("CO2 content, humidity and vapour pressure must be non-negative")
    xw = water_mole_fraction(t, p, 0.0 if h is None else h, pv)
    if np.any(xw > 1.0):
        raise ValueError("water vapour partial pressure exceeds the total pressure")
    if not strict:
        return
    problems = []
    for name, value, (lo, hi), unit in (("temperature", t, VALID_TEMPERATURE_C, "C"),
                                        ("pressure", p, VALID_PRESSURE_PA, "Pa"),
                                        ("CO2 content", xc, VALID_CO2_PPM, "ppm")):
        if np.any(value < lo) or np.any(value > hi):
            problems.append(f"{name} outside [{lo:g}, {hi:g}] {unit}")
    if h is not None and (np.any(h < VALID_HUMIDITY[0]) or np.any(h > VALID_HUMIDITY[1])):
        problems.append("relative humidity outside [0, 1]")
    if pv is not None and np.any(pv > saturation_vapour_pressure(t)):
        problems.append("water vapour pressure above saturation")
    if problems:
        raise OutOfRange("Ciddor 1996 air: " + "; ".join(problems)
                         + " (the stated validity of the equations); pass strict=False to extrapolate")


def refractive_index(wavelength_um, temperature_c=STANDARD_TEMPERATURE_C, pressure_pa=STANDARD_PRESSURE_PA,
                     humidity=0.0, co2_ppm=STANDARD_CO2_PPM, vapour_pressure_pa=None, strict=True):
    """Phase refractive index of moist air after Ciddor (1996); every argument broadcasts.

    ``humidity`` is the relative humidity as a fraction (0.5 = 50 %); give the
    partial pressure of water vapour in Pa as ``vapour_pressure_pa`` instead if you
    have that. With ``strict=True`` the wavelength and the conditions must lie in
    the stated validity ranges; ``strict=False`` extrapolates the formulas.
    """
    return 1.0 + refractivity(wavelength_um, temperature_c, pressure_pa, humidity, co2_ppm, vapour_pressure_pa, strict)


def refractivity(wavelength_um, temperature_c=STANDARD_TEMPERATURE_C, pressure_pa=STANDARD_PRESSURE_PA,
                 humidity=0.0, co2_ppm=STANDARD_CO2_PPM, vapour_pressure_pa=None, strict=True):
    """n - 1 of moist air after Ciddor (1996), kept separate from 1 for full double precision."""
    wl = np.asarray(wavelength_um, dtype=float)
    if strict and ((wl < RANGE_UM[0] - 1e-12).any() or (wl > RANGE_UM[1] + 1e-12).any()):
        raise OutOfRange(f"Ciddor 1996 air: wavelength outside validity range [{RANGE_UM[0]}, {RANGE_UM[1]}] um; "
                         "pass strict=False to extrapolate")
    _check_conditions(temperature_c, pressure_pa, humidity, co2_ppm, vapour_pressure_pa, strict)
    xw = water_mole_fraction(temperature_c, pressure_pa, humidity, vapour_pressure_pa)
    rho_a, rho_w = _component_densities(temperature_c, pressure_pa, xw, co2_ppm)
    rho_axs = _P_R1 * molar_mass_dry_air(co2_ppm) / (_Z_A * _R * _T_R1)
    rho_ws = _P_WS * _M_V / (compressibility(_T_WS - 273.15, _P_WS, 1.0) * _R * _T_WS)
    return (rho_a / rho_axs * _refractivity_standard_air(wl, co2_ppm)
            + rho_w / rho_ws * _refractivity_water_vapour(wl))                 # Eq. (5)


# ---- dispersion model -----------------------------------------------------------

@dataclass
class CiddorAir(Dispersion):
    """Moist air at fixed conditions as a physmat dispersion model (Ciddor 1996).

    Temperature in degrees C, pressure in Pa, relative humidity as a fraction
    (or the water-vapour partial pressure in Pa), CO2 in ppm (umol/mol). The
    wavelength range 0.3-1.69 um is enforced like every other model through
    ``n(wl, strict=...)``; the conditions are checked once, when the model is
    built, against Ciddor's stated ranges unless ``strict=False``. ``at(...)``
    returns a copy with changed conditions.
    """
    temperature_c: float = STANDARD_TEMPERATURE_C
    pressure_pa: float = STANDARD_PRESSURE_PA
    humidity: float = 0.0
    co2_ppm: float = STANDARD_CO2_PPM
    vapour_pressure_pa: float | None = None
    strict: bool = True
    label: str = "air:Ciddor1996"
    range_um: tuple[float, float] = RANGE_UM

    def __post_init__(self):
        _check_conditions(self.temperature_c, self.pressure_pa, self.humidity, self.co2_ppm,
                          self.vapour_pressure_pa, self.strict)

    def at(self, **changes) -> "CiddorAir":
        """The same model at other conditions, e.g. ``air.at(temperature_c=20, humidity=0.5)``."""
        return replace(self, **changes)

    @property
    def water_mole_fraction(self) -> float:
        return float(water_mole_fraction(self.temperature_c, self.pressure_pa, self.humidity, self.vapour_pressure_pa))

    def density(self, temperature_c=None) -> np.ndarray:
        """Air density in kg/m^3 at the model's pressure, humidity and CO2 (at another temperature if given)."""
        t = self.temperature_c if temperature_c is None else temperature_c
        return density(t, self.pressure_pa, self.humidity, self.co2_ppm, self.vapour_pressure_pa)

    def refractivity(self, wavelength_um, strict: bool = True) -> np.ndarray:
        """n - 1 at full double precision."""
        wl = np.asarray(wavelength_um, dtype=float)
        if strict:
            self.check_range(wl)
        return refractivity(wl, self.temperature_c, self.pressure_pa, self.humidity, self.co2_ppm,
                            self.vapour_pressure_pa, strict=False)

    def _index(self, wl):
        return (1.0 + self.refractivity(wl, strict=False)).astype(complex)
