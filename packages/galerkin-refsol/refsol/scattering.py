# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Plane-wave scattering off an infinite circular cylinder (2D, partial-wave series).

Time convention exp(-i omega t); incident wave travelling in +x:
    u_inc = exp(i k x) = sum_m eps_m i^m J_m(k r) cos(m theta),   eps_0 = 1, eps_m = 2

Scattered field outside the cylinder (r > a):
    u_s = sum_m eps_m i^m c_m H^(1)_m(k r) cos(m theta)

with scattering coefficients c_m depending on the cylinder:
    PEC, TM_z  (u = E_z, u = 0 on r = a):        c_m = -J_m(ka) / H_m(ka)
    PEC, TE_z  (u = H_z, du/dr = 0 on r = a):    c_m = -J'_m(ka) / H'_m(ka)
    dielectric (index n, non-magnetic), TM_z:     continuity of u and du/dr
        c_m = -[n J'_m(nka) J_m(ka) - J_m(nka) J'_m(ka)]
             / [n J'_m(nka) H_m(ka) - J_m(nka) H'_m(ka)]
        interior field: u_in = sum eps_m i^m d_m J_m(n k r) cos(m theta),
        d_m = [J_m(ka) + c_m H_m(ka)] / J_m(nka)
"""

from __future__ import annotations

import numpy as np
from scipy.special import jv, jvp, hankel1, h1vp


def _polar(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    return np.sqrt(x ** 2 + y ** 2), np.arctan2(y, x)


def incident(x, y, k: float):
    return np.exp(1j * k * np.asarray(x, dtype=float))


def _coeffs(k, a, kind, n=None, n_terms=60):
    ka = k * a
    m = np.arange(n_terms)
    if kind == "pec_tm":
        c = -jv(m, ka) / hankel1(m, ka)
        d = None
    elif kind == "pec_te":
        c = -jvp(m, ka) / h1vp(m, ka)
        d = None
    elif kind == "dielectric":
        if n is None:
            raise ValueError("dielectric cylinder needs a refractive index n")
        nka = n * ka
        num = n * jvp(m, nka) * jv(m, ka) - jv(m, nka) * jvp(m, ka)
        den = n * jvp(m, nka) * hankel1(m, ka) - jv(m, nka) * h1vp(m, ka)
        c = -num / den
        d = (jv(m, ka) + c * hankel1(m, ka)) / jv(m, nka)
    else:
        raise ValueError("kind must be 'pec_tm', 'pec_te' or 'dielectric'")
    eps = np.where(m == 0, 1.0, 2.0)
    return m, eps * (1j ** m) * c, (eps * (1j ** m) * d) if d is not None else None


def scattered(x, y, k: float, a: float, kind: str = "pec_tm", n: float | None = None,
              n_terms: int = 60):
    """Scattered field u_s at points (x, y) with r >= a."""
    r, th = _polar(x, y)
    m, cm, _ = _coeffs(k, a, kind, n, n_terms)
    u = np.zeros_like(r, dtype=complex)
    for mi, ci in zip(m, cm):
        u += ci * hankel1(mi, k * r) * np.cos(mi * th)
    return u


def total(x, y, k: float, a: float, kind: str = "pec_tm", n: float | None = None,
          n_terms: int = 60):
    """Total field: incident + scattered outside, interior series inside (dielectric)."""
    r, th = _polar(x, y)
    m, cm, dm = _coeffs(k, a, kind, n, n_terms)
    u = np.zeros_like(r, dtype=complex)
    outside = r >= a
    u[outside] = incident(np.asarray(x)[outside], np.asarray(y)[outside], k) \
        + scattered(np.asarray(x)[outside], np.asarray(y)[outside], k, a, kind, n, n_terms)
    inside = ~outside
    if np.any(inside):
        if dm is None:
            u[inside] = 0.0          # PEC interior
        else:
            for mi, di in zip(m, dm):
                u[inside] += di * jv(mi, n * k * r[inside]) * np.cos(mi * th[inside])
    return u


def scattering_width(k: float, a: float, kind: str = "pec_tm", n: float | None = None,
                     n_terms: int = 60) -> float:
    """Total scattering width (2D cross-section) sigma = (4/k) sum eps_m |c_m|^2."""
    m, cm_full, _ = _coeffs(k, a, kind, n, n_terms)
    eps = np.where(m == 0, 1.0, 2.0)
    cm = cm_full / (eps * (1j ** m))
    return float(4.0 / k * np.sum(eps * np.abs(cm) ** 2))
