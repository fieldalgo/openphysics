# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Planar (slab) dielectric waveguide — guided TE and TM modes.

Geometry (x is the transverse direction, propagation along z):

        cover      n_c            x > d/2
        film       n_f  (core)    |x| < d/2
        substrate  n_s            x < -d/2

with n_f > max(n_s, n_c). Guided modes have effective index
n_eff in (max(n_s, n_c), n_f).

Dispersion relations (k0 = 2 pi / wavelength):
    kappa   = k0 sqrt(n_f^2 - n_eff^2)        transverse wavenumber in the film
    gamma_s = k0 sqrt(n_eff^2 - n_s^2)        decay constant into the substrate
    gamma_c = k0 sqrt(n_eff^2 - n_c^2)        decay constant into the cover

    TE_m:  kappa d = m pi + atan(gamma_s / kappa) + atan(gamma_c / kappa)
    TM_m:  kappa d = m pi + atan((n_f/n_s)^2 gamma_s / kappa)
                          + atan((n_f/n_c)^2 gamma_c / kappa)

For fixed m the left side decreases and the right side increases with n_eff,
so each mode is a simple root that brentq finds reliably.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def _residual(neff, m, pol, n_f, n_s, n_c, d, k0):
    kappa = k0 * np.sqrt(n_f ** 2 - neff ** 2)
    gs = k0 * np.sqrt(neff ** 2 - n_s ** 2)
    gc = k0 * np.sqrt(neff ** 2 - n_c ** 2)
    if pol == "TE":
        fs, fc = 1.0, 1.0
    else:  # TM
        fs, fc = (n_f / n_s) ** 2, (n_f / n_c) ** 2
    return kappa * d - m * np.pi - np.arctan(fs * gs / kappa) - np.arctan(fc * gc / kappa)


def modes(n_f: float, n_s: float, n_c: float, d: float, wavelength: float,
          pol: str = "TE", max_modes: int = 50) -> list[float]:
    """All guided mode effective indices of the slab, highest (m = 0) first.

    pol: "TE" or "TM".  Units of d and wavelength must match.
    """
    pol = pol.upper()
    if pol not in ("TE", "TM"):
        raise ValueError("pol must be 'TE' or 'TM'")
    if not n_f > max(n_s, n_c):
        raise ValueError("film index must exceed substrate and cover indices")

    k0 = 2.0 * np.pi / wavelength
    lo = max(n_s, n_c) * (1 + 1e-12) + 1e-12
    hi = n_f * (1 - 1e-12) - 1e-12

    out = []
    for m in range(max_modes):
        f_lo = _residual(lo, m, pol, n_f, n_s, n_c, d, k0)
        f_hi = _residual(hi, m, pol, n_f, n_s, n_c, d, k0)
        # residual is decreasing in neff; a root exists iff f(lo) > 0 > f(hi)
        if f_lo <= 0.0:
            break
        if f_hi >= 0.0:
            break
        out.append(brentq(_residual, lo, hi, args=(m, pol, n_f, n_s, n_c, d, k0),
                          xtol=1e-14, rtol=1e-14, maxiter=200))
    return out


def num_modes_symmetric(n_f: float, n_s: float, d: float, wavelength: float) -> int:
    """Number of guided modes (per polarization) of a symmetric slab.

    With V = (k0 d / 2) sqrt(n_f^2 - n_s^2), mode m exists iff V > m pi / 2,
    so the count is floor(2V/pi) + 1. Used as an independent cross-check of
    modes(); the two must agree for any parameters.
    """
    k0 = 2.0 * np.pi / wavelength
    V = 0.5 * k0 * d * np.sqrt(n_f ** 2 - n_s ** 2)
    return int(np.floor(2.0 * V / np.pi)) + 1


def field_te(x, neff: float, n_f: float, n_s: float, n_c: float, d: float,
             wavelength: float):
    """E_y(x) profile of a TE mode with effective index neff (unnormalized).

    Continuous with continuous derivative across both interfaces.
    """
    x = np.asarray(x, dtype=float)
    k0 = 2.0 * np.pi / wavelength
    kappa = k0 * np.sqrt(n_f ** 2 - neff ** 2)
    gs = k0 * np.sqrt(neff ** 2 - n_s ** 2)
    gc = k0 * np.sqrt(neff ** 2 - n_c ** 2)
    # film: cos(kappa x - phi); phase phi fixed by the cover-side condition
    phi = np.arctan(gc / kappa) - kappa * d / 2.0
    E = np.empty_like(x)
    film = np.abs(x) <= d / 2
    cover = x > d / 2
    subst = x < -d / 2
    E[film] = np.cos(kappa * x[film] + phi)
    E_top = np.cos(kappa * d / 2 + phi)
    E_bot = np.cos(-kappa * d / 2 + phi)
    E[cover] = E_top * np.exp(-gc * (x[cover] - d / 2))
    E[subst] = E_bot * np.exp(gs * (x[subst] + d / 2))
    return E
