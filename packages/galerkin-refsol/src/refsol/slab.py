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

Units and names. The public functions take SI keyword-only registry names
(galerkin step, L3 commit 11c): ``refractive_index`` is the sequence of the three
layers in order of increasing x, ``(substrate, film, cover)``; ``thickness`` is
the film's in m and ``vacuum_wavelength`` is in m (only k0 d enters, so any
consistent scale gives the same index). The indices are real, so the time
convention does not enter; refsol's complex values follow exp(-i omega t).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from ._checks import refuse_text

__all__ = ["modes", "num_modes_symmetric", "field_te"]


def _layers(refractive_index, count=3):
    """The real layer indices (substrate, film, cover) of a slab."""
    if isinstance(refractive_index, (str, bytes)) or np.ndim(refractive_index) != 1 \
            or len(refractive_index) != count:
        raise ValueError(f"refractive_index must hold {count} real indices (substrate, film, cover)")
    values = tuple(float(v) for v in refractive_index)
    if not all(np.isfinite(v) and v > 0 for v in values):
        raise ValueError("refractive_index must hold finite positive real indices")
    return values


def _positive(value, name):
    value = float(value)
    if not (np.isfinite(value) and value > 0):
        raise ValueError(f"{name} must be a finite positive number in SI units")
    return value


def _residual(neff, m, pol, n_f, n_s, n_c, d, k0):
    kappa = k0 * np.sqrt(n_f ** 2 - neff ** 2)
    gs = k0 * np.sqrt(neff ** 2 - n_s ** 2)
    gc = k0 * np.sqrt(neff ** 2 - n_c ** 2)
    if pol == "TE":
        fs, fc = 1.0, 1.0
    else:  # TM
        fs, fc = (n_f / n_s) ** 2, (n_f / n_c) ** 2
    return kappa * d - m * np.pi - np.arctan(fs * gs / kappa) - np.arctan(fc * gc / kappa)


def modes(*, refractive_index, thickness, vacuum_wavelength, pol: str = "TE",
          mode_count: int = 50) -> list[float]:
    """All guided mode effective indices of the slab, highest (m = 0) first.

    refractive_index: (substrate, film, cover); thickness: the film's, in m; vacuum_wavelength
    in m. pol: "TE" or "TM". At most ``mode_count`` modes are returned.
    """
    refuse_text(refractive_index=refractive_index, thickness=thickness, vacuum_wavelength=vacuum_wavelength,
                mode_count=mode_count)
    n_s, n_f, n_c = _layers(refractive_index)
    return _modes(n_f, n_s, n_c, _positive(thickness, "thickness"),
                  _positive(vacuum_wavelength, "vacuum_wavelength"), pol, mode_count)


def _modes(n_f, n_s, n_c, d, wavelength, pol="TE", max_modes=50):
    """``modes`` in the positional form refsol's other slab modules call (any consistent length unit)."""
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


def num_modes_symmetric(*, refractive_index, thickness, vacuum_wavelength) -> int:
    """Number of guided modes (per polarization) of a symmetric slab.

    refractive_index: (cladding, film, cladding), the two claddings equal; thickness and
    vacuum_wavelength in m. With V = (k0 d / 2) sqrt(n_f^2 - n_s^2), mode m exists iff
    V > m pi / 2, so the count is floor(2V/pi) + 1. Used as an independent cross-check of
    modes(); the two must agree for any parameters.
    """
    refuse_text(refractive_index=refractive_index, thickness=thickness, vacuum_wavelength=vacuum_wavelength)
    n_s, n_f, n_c = _layers(refractive_index)
    if n_c != n_s:
        raise ValueError("a symmetric slab has equal cladding indices: refractive_index[0] == refractive_index[2]")
    d = _positive(thickness, "thickness")
    wavelength = _positive(vacuum_wavelength, "vacuum_wavelength")
    k0 = 2.0 * np.pi / wavelength
    V = 0.5 * k0 * d * np.sqrt(n_f ** 2 - n_s ** 2)
    return int(np.floor(2.0 * V / np.pi)) + 1


def field_te(points, *, effective_index, refractive_index, thickness, vacuum_wavelength):
    """E_y(x) profile of a TE mode with effective index ``effective_index`` (unnormalized).

    points: positions x in m across the slab, whose film is |x| <= thickness / 2;
    refractive_index: (substrate, film, cover). Continuous with continuous derivative across
    both interfaces.
    """
    refuse_text(points=points, effective_index=effective_index, refractive_index=refractive_index,
                thickness=thickness, vacuum_wavelength=vacuum_wavelength)
    n_s, n_f, n_c = _layers(refractive_index)
    neff, d = float(effective_index), _positive(thickness, "thickness")
    wavelength = _positive(vacuum_wavelength, "vacuum_wavelength")
    x = np.asarray(points, dtype=float)
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
