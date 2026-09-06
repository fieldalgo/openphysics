# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Dispersion models: complex refractive index and permittivity as functions of wavelength.

Conventions (fixed for the whole package)
-----------------------------------------
* Wavelength is the vacuum wavelength in micrometres.
* Time dependence exp(-i omega t). The complex index is  n~ = n + i k  with k >= 0
  for a lossy material, and eps = n~^2, so Im(eps) >= 0 means absorption.
  (Codes using exp(+i omega t) take the complex conjugate.)
* Every model reports a validity range; evaluating outside it raises unless
  ``strict=False`` is passed, in which case the value is extrapolated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

HC_EV_UM = 1.239841984  # h c in eV*um: E[eV] = HC_EV_UM / wavelength[um]


def ev_to_um(energy_ev):
    return HC_EV_UM / np.asarray(energy_ev, dtype=float)


def um_to_ev(wavelength_um):
    return HC_EV_UM / np.asarray(wavelength_um, dtype=float)


class OutOfRange(ValueError):
    pass


class Dispersion:
    """Base class. Subclasses implement ``_index(wl)`` returning complex n~."""

    range_um: tuple[float, float] = (0.0, np.inf)
    label: str = ""

    # -- public API ----------------------------------------------------------

    def index(self, wavelength_um, strict: bool = True) -> np.ndarray:
        """Complex refractive index n + i k."""
        wl = np.asarray(wavelength_um, dtype=float)
        if strict:
            self.check_range(wl)
        return np.asarray(self._index(wl), dtype=complex)

    def n(self, wavelength_um, strict: bool = True) -> np.ndarray:
        return self.index(wavelength_um, strict).real

    def k(self, wavelength_um, strict: bool = True) -> np.ndarray:
        return self.index(wavelength_um, strict).imag

    def eps(self, wavelength_um, strict: bool = True) -> np.ndarray:
        """Complex relative permittivity (n + i k)^2."""
        return self.index(wavelength_um, strict) ** 2

    def check_range(self, wl) -> None:
        lo, hi = self.range_um
        wl = np.asarray(wl, dtype=float)
        if (wl < lo - 1e-12).any() or (wl > hi + 1e-12).any():
            raise OutOfRange(f"{self.label or type(self).__name__}: wavelength outside validity range "
                             f"[{lo}, {hi}] um; pass strict=False to extrapolate")

    def group_index(self, wavelength_um, strict: bool = True, h: float = 1e-4) -> np.ndarray:
        """n_g = n - lambda dn/dlambda (real part, central difference)."""
        wl = np.asarray(wavelength_um, dtype=float)
        dn = (self.n(wl * (1 + h), strict) - self.n(wl * (1 - h), strict)) / (2 * h * wl)
        return self.n(wl, strict) - wl * dn

    def _index(self, wl: np.ndarray) -> np.ndarray:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# simple analytic models
# ---------------------------------------------------------------------------

@dataclass
class Constant(Dispersion):
    n0: float = 1.0
    k0: float = 0.0
    label: str = ""
    range_um: tuple[float, float] = (0.0, np.inf)

    def _index(self, wl):
        return np.full(np.shape(wl), self.n0 + 1j * self.k0, dtype=complex)


@dataclass
class Sellmeier(Dispersion):
    """n^2 = A + sum_i B_i lambda^2 / (lambda^2 - C_i)   (C_i in um^2)."""
    B: Sequence[float]
    C: Sequence[float]
    A: float = 1.0
    range_um: tuple[float, float] = (0.0, np.inf)
    label: str = ""

    def _index(self, wl):
        l2 = wl ** 2
        n2 = self.A + sum(b * l2 / (l2 - c) for b, c in zip(self.B, self.C))
        return np.sqrt(n2.astype(complex))


@dataclass
class Tabulated(Dispersion):
    """Measured (lambda, n, k) table with linear interpolation in wavelength."""
    wavelength: np.ndarray
    n_values: np.ndarray
    k_values: np.ndarray | None = None
    label: str = ""

    def __post_init__(self):
        order = np.argsort(self.wavelength)
        self.wavelength = np.asarray(self.wavelength, dtype=float)[order]
        self.n_values = np.asarray(self.n_values, dtype=float)[order]
        self.k_values = None if self.k_values is None else np.asarray(self.k_values, dtype=float)[order]
        self.range_um = (float(self.wavelength[0]), float(self.wavelength[-1]))

    def _index(self, wl):
        n = np.interp(wl, self.wavelength, self.n_values)
        k = 0.0 if self.k_values is None else np.interp(wl, self.wavelength, self.k_values)
        return n + 1j * k


@dataclass
class Composite(Dispersion):
    """Real part from one model, imaginary part from another (e.g. Sellmeier n + tabulated k)."""
    n_model: Dispersion
    k_model: Dispersion
    label: str = ""

    def __post_init__(self):
        # the n model defines validity; k outside its own table is held at the edge value
        self.range_um = tuple(self.n_model.range_um)

    def _index(self, wl):
        return self.n_model.index(wl, strict=False).real + 1j * self.k_model.index(wl, strict=False).imag


# ---------------------------------------------------------------------------
# metals: Drude and Drude-Lorentz (energies in eV)
# ---------------------------------------------------------------------------

@dataclass
class DrudeLorentz(Dispersion):
    """eps(w) = eps_inf - f0 wp^2 / (w^2 + i G0 w) + sum_j f_j wp^2 / (w_j^2 - w^2 - i G_j w)

    The Lorentz-Drude form of Rakic et al., Appl. Opt. 37, 5271 (1998). All
    energies (wp, G0, w_j, G_j) in eV; f are dimensionless oscillator strengths.
    ``lorentz`` is a sequence of (f_j, w_j, G_j). With ``lorentz=()`` this is a
    plain Drude metal. Im(eps) >= 0 for positive damping (exp(-i w t)).
    """
    eps_inf: float
    wp: float
    f0: float
    gamma0: float
    lorentz: Sequence[tuple[float, float, float]] = ()
    range_um: tuple[float, float] = (0.0, np.inf)
    label: str = ""

    def eps_of_energy(self, energy_ev) -> np.ndarray:
        w = np.asarray(energy_ev, dtype=float).astype(complex)
        eps = self.eps_inf - self.f0 * self.wp ** 2 / (w ** 2 + 1j * self.gamma0 * w)
        for f, wj, gj in self.lorentz:
            eps = eps + f * self.wp ** 2 / (wj ** 2 - w ** 2 - 1j * gj * w)
        return eps

    def _index(self, wl):
        eps = self.eps_of_energy(um_to_ev(wl))
        nk = np.sqrt(eps)
        # choose the root with k >= 0 (passive medium)
        return np.where(nk.imag < 0, -nk, nk)

    def parameters(self) -> np.ndarray:
        """Flat parameter vector [eps_inf, wp, f0, G0, f1, w1, G1, ...] (used by the fitter)."""
        return np.array([self.eps_inf, self.wp, self.f0, self.gamma0, *np.ravel(self.lorentz)], dtype=float)

    @classmethod
    def from_parameters(cls, p, **kw) -> "DrudeLorentz":
        p = np.asarray(p, dtype=float)
        lor = [tuple(p[i:i + 3]) for i in range(4, len(p), 3)]
        return cls(p[0], p[1], p[2], p[3], lor, **kw)


def Drude(eps_inf: float, wp_ev: float, gamma_ev: float, **kw) -> DrudeLorentz:
    """Plain Drude metal eps = eps_inf - wp^2/(w^2 + i G w)."""
    return DrudeLorentz(eps_inf, wp_ev, 1.0, gamma_ev, (), **kw)


# ---------------------------------------------------------------------------
# refractiveindex.info formulas 1-9 (wavelength in um)
# ---------------------------------------------------------------------------

@dataclass
class RIIFormula(Dispersion):
    """The nine dispersion formulas of the refractiveindex.info database.

    1 Sellmeier (C_{2i+1} squared in the denominator), 2 Sellmeier-2,
    3 Polynomial, 4 RefractiveIndex.INFO, 5 Cauchy, 6 Gases, 7 Herzberger,
    8 Retro, 9 Exotic. Coefficients exactly as stored in the database.
    """
    kind: int
    coefficients: Sequence[float]
    range_um: tuple[float, float] = (0.0, np.inf)
    label: str = ""

    def _index(self, wl):
        c = list(self.coefficients) + [0.0] * 17
        l = np.asarray(wl, dtype=float)
        k = self.kind
        if k == 1:
            n2 = 1 + c[0] + sum(c[i] * l ** 2 / (l ** 2 - c[i + 1] ** 2) for i in range(1, 17, 2))
            return np.sqrt(n2.astype(complex))
        if k == 2:
            n2 = 1 + c[0] + sum(c[i] * l ** 2 / (l ** 2 - c[i + 1]) for i in range(1, 17, 2))
            return np.sqrt(n2.astype(complex))
        if k == 3:
            n2 = c[0] + sum(c[i] * l ** c[i + 1] for i in range(1, 17, 2))
            return np.sqrt(n2.astype(complex))
        if k == 4:
            n2 = c[0] + sum(c[i] * l ** c[i + 1] for i in range(9, 17, 2))
            if c[1] != 0:
                n2 = n2 + c[1] * l ** c[2] / (l ** 2 - c[3] ** c[4])
            if c[5] != 0:
                n2 = n2 + c[5] * l ** c[6] / (l ** 2 - c[7] ** c[8])
            return np.sqrt(np.asarray(n2, dtype=complex))
        if k == 5:
            return (c[0] + sum(c[i] * l ** c[i + 1] for i in range(1, 11, 2))).astype(complex)
        if k == 6:
            return (1 + c[0] + sum(c[i] / (c[i + 1] - l ** -2) for i in range(1, 11, 2))).astype(complex)
        if k == 7:
            q = 1.0 / (l ** 2 - 0.028)
            return (c[0] + c[1] * q + c[2] * q ** 2 + c[3] * l ** 2 + c[4] * l ** 4 + c[5] * l ** 6).astype(complex)
        if k == 8:
            r = c[0] + c[1] * l ** 2 / (l ** 2 - c[2]) + c[3] * l ** 2
            n2 = (1 + 2 * r) / (1 - r)
            return np.sqrt(n2.astype(complex))
        if k == 9:
            n2 = c[0] + c[1] / (l ** 2 - c[2]) + c[3] * (l - c[4]) / ((l - c[4]) ** 2 + c[5])
            return np.sqrt(n2.astype(complex))
        raise ValueError(f"unknown refractiveindex.info formula {k}")
