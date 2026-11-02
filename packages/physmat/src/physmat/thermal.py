# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Thermal conductivity of pure metals versus temperature: Hust and Lankford (1984).

J. G. Hust and A. B. Lankford, "Thermal conductivity of aluminum, copper, iron,
and tungsten for temperatures from 1 K to the melting point", NBSIR 84-3007,
National Bureau of Standards, Boulder (1984), https://doi.org/10.6028/NBS.IR.84-3007.
The report fits one equation per metal to the critically selected literature data,
with the residual resistivity ratio RRR (electrical resistivity at the ice point
over the residual resistivity at 0 K) as the purity parameter. Implemented here for
copper, aluminium and tungsten from the report's Eqs. 1.1.3-1.1.6, 1.2.2 and the
parameters of Sections 2.1, 3.1 and 5.1:

    lambda = 1 / (W_0 + W_i + W_i0)                                          (1.1.3)
    W_0    = beta / T,  beta = rho_0 / L_0                                   (1.1.4)
    W_i    = P1 T^P2 / (1 + P1 P3 T^(P2 + P4) exp(-(P5 / T)^P6)) + W_c      (1.1.5)
    W_i0   = P7 W_i W_0 / (W_i + W_0)                                        (1.1.6)
    rho_0  = rho_i,273 / (RRR - 1)                                           (1.2.2)

W_0 is the electron-defect (residual) thermal resistivity, W_i the intrinsic
electron-phonon resistivity, W_i0 their interaction term and W_c a small empirical
correction of W_i; L_0 = 2.443e-8 V^2/K^2 is the Sommerfeld Lorenz number and
rho_i,273 the intrinsic resistivity at 273 K that the report adopts for each metal
(Section 1.5). All quantities are SI: T in K, lambda in W/(m K).

The report states the equations for annealed bulk specimens from 1 K to the melting
point and represents its primary data within about +-15 % (copper), random
deviations (aluminium) and +-7 % (tungsten); the fit for copper becomes
progressively less valid below RRR 20. The RRR ranges of the fitted data are copper
20-1800, aluminium 13-16800 and tungsten 30-170; the report's own tables extend to
RRR 3000 (copper), 10000 (aluminium) and 300 (tungsten). Outside the stated
temperature range or the fitted RRR range the equation is extrapolated only when
``strict=False``.

The report is a work of the United States Government (NBS, now NIST). Such works are
not subject to copyright in the United States (17 U.S.C. 105); the status elsewhere
is not settled by that statute. physmat ships only the published equations and
their parameters, with this citation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .dispersion import OutOfRange
from .material import Property

CITATION = ('J. G. Hust and A. B. Lankford, "Thermal conductivity of aluminum, copper, iron, and tungsten for '
            'temperatures from 1 K to the melting point", NBSIR 84-3007, National Bureau of Standards (1984), '
            "https://doi.org/10.6028/NBS.IR.84-3007")

LORENZ_NUMBER = 2.443e-8          # V^2/K^2, Sommerfeld value L_0 used by the report (Section 1.3, 1.5)


@dataclass(frozen=True)
class _MetalParameters:
    name: str
    rho_i273: float                # intrinsic electrical resistivity at 273 K, ohm m (Section 1.5)
    p: tuple[float, ...]           # P1 .. P7 of Eq. 1.1.5/1.1.6; P7 is a function of beta for copper
    wc: tuple[tuple[float, float, float, float], ...]   # terms  a ln(T/b) exp(-(ln(T/c)/d)^2)  of W_c
    wc_extra: tuple[tuple[float, float, float], ...]    # terms  a exp(-(ln(T/c)/d)^2)  of W_c (tungsten)
    rrr_fitted: tuple[float, float]    # RRR range of the primary data the equation was fitted to
    melting_k: float                   # upper end of the stated validity, "the melting point"
    deviation: str                     # the report's statement of how well the equation represents its data


# Parameters transcribed from NBSIR 84-3007: copper Section 2.1 (pp. 15-16), aluminium Section 3.1
# (pp. 87-88), tungsten Section 5.1 (pp. 199-200). rho_i,273 from Section 1.5 (p. 12, in nano-ohm m
# there). Melting points: CRC Handbook values Cu 1357.77 K, Al 933.47 K, W 3695 K.
_COPPER = _MetalParameters(
    "copper", 15.4e-9,
    (1.754e-8, 2.763, 1102.0, -0.165, 70.0, 1.765, float("nan")),     # P7 = 0.838 / beta_r^0.1661 (below)
    ((-0.00012, 420.0, 470.0, 0.7), (-0.00016, 73.0, 87.0, 0.45), (-0.00002, 18.0, 21.0, 0.5)),
    (), (20.0, 1800.0), 1357.77, "primary data within +-15 % (unannealed specimens within 20 %)")
_ALUMINIUM = _MetalParameters(
    "aluminium", 24.8e-9,
    (4.716e-8, 2.446, 623.6, -0.16, 130.9, 2.5, 0.8168),
    ((-0.0005, 330.0, 380.0, 0.6), (-0.0013, 110.0, 94.0, 0.5)),
    (), (13.0, 16800.0), 933.47, "random deviations of the primary data, no systematic trend with RRR")
_TUNGSTEN = _MetalParameters(
    "tungsten", 48.4e-9,
    (31.70e-8, 2.29, 541.3, -0.22, 69.94, 3.557, 0.0),
    ((-0.00085, 130.0, 230.0, 0.7), (0.0006, 90.0, 80.0, 0.4), (0.0003, 24.0, 33.0, 0.5)),
    ((0.00015, 3500.0, 0.8),), (30.0, 170.0), 3695.0, "primary data within +-7 %")

METALS: dict[str, _MetalParameters] = {"Cu": _COPPER, "Al": _ALUMINIUM, "W": _TUNGSTEN}
_ALIASES = {"cu": "Cu", "copper": "Cu", "al": "Al", "aluminum": "Al", "aluminium": "Al",
            "w": "W", "tungsten": "W", "wolfram": "W"}

# Default purity used for the built-in materials: RRR 100 is a column of the report's tables for all
# three metals and the typical grade of annealed, commercially pure metal (OFHC copper per the NIST
# cryogenic material properties fits; Hust and Lankford put commercial copper wire at RRR 50-500).
DEFAULT_RRR = 100.0
MIN_TEMPERATURE_K = 1.0


def _metal(metal: str) -> _MetalParameters:
    try:
        return METALS[_ALIASES[metal.strip().lower()]]
    except KeyError:
        raise KeyError(f"no Hust-Lankford parameters for {metal!r}; available: {sorted(METALS)}") from None


def _check_rrr(m: _MetalParameters, rrr: float, strict: bool) -> float:
    rrr = float(rrr)
    if not np.isfinite(rrr) or rrr <= 1.0:
        raise ValueError(f"RRR must be a finite number greater than 1 (got {rrr!r}); "
                         "RRR = rho(273 K) / rho(0 K) is the residual resistivity ratio")
    lo, hi = m.rrr_fitted
    if strict and not lo <= rrr <= hi:
        raise OutOfRange(f"Hust-Lankford {m.name}: RRR {rrr:g} outside the fitted range [{lo:g}, {hi:g}]; "
                         "pass strict=False to extrapolate")
    return rrr


def _correction(m: _MetalParameters, T: np.ndarray) -> np.ndarray:
    wc = np.zeros_like(T)
    for a, b, c, d in m.wc:
        wc += a * np.log(T / b) * np.exp(-(np.log(T / c) / d) ** 2)
    for a, c, d in m.wc_extra:
        wc += a * np.exp(-(np.log(T / c) / d) ** 2)
    return wc


def _conductivity(m: _MetalParameters, T: np.ndarray, rrr: float) -> np.ndarray:
    rho0 = m.rho_i273 / (rrr - 1.0)                                   # Eq. 1.2.2
    beta = rho0 / LORENZ_NUMBER                                       # Eq. 1.1.4, beta = rho_0 / L_0
    p1, p2, p3, p4, p5, p6, p7 = m.p
    if m is _COPPER:
        p7 = 0.838 / (beta / 0.0003) ** 0.1661
    w0 = beta / T                                                     # Eq. 1.1.4
    wi = p1 * T ** p2 / (1.0 + p1 * p3 * T ** (p2 + p4) * np.exp(-(p5 / T) ** p6)) + _correction(m, T)   # Eq. 1.1.5
    wi0 = p7 * wi * w0 / (wi + w0)                                    # Eq. 1.1.6
    return 1.0 / (w0 + wi + wi0)                                      # Eq. 1.1.3


@dataclass(frozen=True)
class HustLankford:
    """Thermal conductivity lambda(T) in W/(m K) of a pure metal after Hust and Lankford (1984).

    ``metal`` is ``"Cu"``, ``"Al"`` or ``"W"`` (names and aliases accepted), ``rrr`` the
    residual resistivity ratio of the specimen. Calling the model with a temperature in
    kelvin evaluates Eq. 1.1.3; it raises ``OutOfRange`` outside 1 K to the melting point
    unless ``strict=False``. The model is a plain callable of T, so it fits a
    ``physmat.Property`` directly (``property()`` builds one with the citation).
    """
    metal: str = "Cu"
    rrr: float = DEFAULT_RRR
    strict: bool = True
    _m: _MetalParameters = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        m = _metal(self.metal)
        object.__setattr__(self, "metal", _ALIASES[self.metal.strip().lower()])
        object.__setattr__(self, "_m", m)
        _check_rrr(m, self.rrr, self.strict)
        object.__setattr__(self, "rrr", float(self.rrr))

    @property
    def range_k(self) -> tuple[float, float]:
        """Stated validity in kelvin: 1 K to the melting point."""
        return (MIN_TEMPERATURE_K, self._m.melting_k)

    @property
    def rrr_fitted(self) -> tuple[float, float]:
        """RRR range of the primary data the equation was fitted to."""
        return self._m.rrr_fitted

    @property
    def residual_resistivity(self) -> float:
        """rho_0 in ohm m implied by the RRR through Eq. 1.2.2."""
        return self._m.rho_i273 / (self.rrr - 1.0)

    def check_range(self, T) -> None:
        T = np.asarray(T, dtype=float)
        lo, hi = self.range_k
        if np.any(T < lo - 1e-12) or np.any(T > hi + 1e-12):
            raise OutOfRange(f"Hust-Lankford {self._m.name}: temperature outside the stated validity "
                             f"[{lo:g}, {hi:g}] K (1 K to the melting point); pass strict=False to extrapolate")

    def __call__(self, T, strict: bool | None = None):
        """lambda(T) in W/(m K); T in kelvin, broadcasting over arrays."""
        T = np.asarray(T, dtype=float)
        if np.any(T <= 0.0):
            raise ValueError("temperature must be positive (kelvin)")
        if self.strict if strict is None else strict:
            self.check_range(T)
        return _conductivity(self._m, T, self.rrr)

    @property
    def source(self) -> str:
        return f"{CITATION}; Eq. 1.1.3 for {self._m.name}, RRR = {self.rrr:g}, 1 K to the melting point"

    def property(self) -> Property:
        """The model as a ``physmat.Property`` (W/(m K), temperature in kelvin) with its citation."""
        return Property(self, "W/(m K)", self.source)


def thermal_conductivity(metal: str, T, rrr: float = DEFAULT_RRR, strict: bool = True):
    """lambda(T) in W/(m K) of Cu, Al or W after Hust and Lankford (1984); T in kelvin, RRR as purity."""
    return HustLankford(metal, rrr, strict)(T)


def conductivity_property(metal: str, rrr: float = DEFAULT_RRR, strict: bool = True) -> Property:
    """A ``Property`` holding the Hust-Lankford model, for ``Material.properties['thermal_conductivity']``."""
    return HustLankford(metal, rrr, strict).property()
