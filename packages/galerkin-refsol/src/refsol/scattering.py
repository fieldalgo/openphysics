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

Units and names (galerkin step, L3 commit 11e). The public functions take SI keyword-only
registry names after the leading ``points`` ((..., 2) metre coordinates, the cylinder's axis
at the origin): ``vacuum_angular_wavenumber`` k = 2 pi / lambda_0 in rad/m (the exterior is
vacuum), ``radius`` the cylinder radius a in m, ``refractive_index`` the interior index n
of a dielectric cylinder, ``kind`` and the series length ``terms``. Only k a, k r and n enter, so any consistent
scale gives the same field. The formulas above are written in exp(-i omega t), the public
convention, so nothing is converted: a passive (absorbing) cylinder has Im n >= 0, and the
scattered field is outgoing, H^(1)_m(k r) ~ exp(+i k r). ``scattering_width`` is in m.
"""

from __future__ import annotations

import numpy as np
from scipy.special import jv, jvp, hankel1, h1vp

from ._checks import refuse_text

__all__ = ["incident", "scattered", "total", "scattering_width"]


def _points(points):
    """x and y of real (..., 2) metre coordinates."""
    refuse_text(points=points)
    p = np.asarray(points, dtype=float)
    if p.ndim < 1 or p.shape[-1] != 2:
        raise ValueError("points must be an array (..., 2) of x, y coordinates in m")
    return p[..., 0], p[..., 1]


def _number(value, name):
    if np.ndim(value) != 0 or np.iscomplexobj(value):
        raise ValueError(f"{name} must be one real number in SI units")
    value = float(value)
    if not (np.isfinite(value) and value > 0):
        raise ValueError(f"{name} must be a finite positive number in SI units")
    return value


def _cylinder(vacuum_angular_wavenumber, radius, kind, refractive_index, terms):
    """k, a, kind, n and the series length as checked values."""
    refuse_text(vacuum_angular_wavenumber=vacuum_angular_wavenumber, radius=radius,
                refractive_index=refractive_index)
    k = _number(vacuum_angular_wavenumber, "vacuum_angular_wavenumber")
    a = _number(radius, "radius (the cylinder radius)")
    if refractive_index is not None and np.ndim(refractive_index) != 0:
        raise ValueError("refractive_index must be one (real or complex) index")
    if isinstance(terms, bool) or not isinstance(terms, (int, np.integer)) or terms < 1:
        raise ValueError("terms must be a positive integer")
    return k, a, kind, refractive_index, terms


def _polar(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    return np.sqrt(x ** 2 + y ** 2), np.arctan2(y, x)


def incident(points, *, vacuum_angular_wavenumber):
    """The incident plane wave exp(i k x) at ``points`` (..., 2) in m."""
    x, _ = _points(points)
    refuse_text(vacuum_angular_wavenumber=vacuum_angular_wavenumber)
    return _incident(x, _number(vacuum_angular_wavenumber, "vacuum_angular_wavenumber"))


def _incident(x, k):
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
            raise ValueError("a dielectric cylinder needs its refractive_index")
        nka = n * ka
        num = n * jvp(m, nka) * jv(m, ka) - jv(m, nka) * jvp(m, ka)
        den = n * jvp(m, nka) * hankel1(m, ka) - jv(m, nka) * h1vp(m, ka)
        c = -num / den
        d = (jv(m, ka) + c * hankel1(m, ka)) / jv(m, nka)
    else:
        raise ValueError("kind must be 'pec_tm', 'pec_te' or 'dielectric'")
    eps = np.where(m == 0, 1.0, 2.0)
    return m, eps * (1j ** m) * c, (eps * (1j ** m) * d) if d is not None else None


def scattered(points, *, vacuum_angular_wavenumber, radius, kind: str = "pec_tm", refractive_index=None,
              terms: int = 60):
    """Scattered field u_s at ``points`` (..., 2) in m with r >= a (``radius``)."""
    x, y = _points(points)
    return _scattered(x, y, *_cylinder(vacuum_angular_wavenumber, radius, kind, refractive_index, terms))


def _scattered(x, y, k, a, kind="pec_tm", n=None, n_terms=60):
    r, th = _polar(x, y)
    m, cm, _ = _coeffs(k, a, kind, n, n_terms)
    u = np.zeros_like(r, dtype=complex)
    for mi, ci in zip(m, cm):
        u += ci * hankel1(mi, k * r) * np.cos(mi * th)
    return u


def total(points, *, vacuum_angular_wavenumber, radius, kind: str = "pec_tm", refractive_index=None,
          terms: int = 60):
    """Total field at ``points`` (..., 2) in m: incident + scattered outside, interior series inside (dielectric)."""
    x, y = _points(points)
    return _total(x, y, *_cylinder(vacuum_angular_wavenumber, radius, kind, refractive_index, terms))


def _total(x, y, k, a, kind="pec_tm", n=None, n_terms=60):
    r, th = _polar(x, y)
    m, cm, dm = _coeffs(k, a, kind, n, n_terms)
    u = np.zeros_like(r, dtype=complex)
    outside = r >= a
    u[outside] = _incident(np.asarray(x)[outside], k) \
        + _scattered(np.asarray(x)[outside], np.asarray(y)[outside], k, a, kind, n, n_terms)
    inside = ~outside
    if np.any(inside):
        if dm is None:
            u[inside] = 0.0          # PEC interior
        else:
            for mi, di in zip(m, dm):
                u[inside] += di * jv(mi, n * k * r[inside]) * np.cos(mi * th[inside])
    return u


def scattering_width(*, vacuum_angular_wavenumber, radius, kind: str = "pec_tm", refractive_index=None,
                     terms: int = 60) -> float:
    """Total scattering width (2D cross-section, m) sigma = (4/k) sum eps_m |c_m|^2."""
    return _scattering_width(*_cylinder(vacuum_angular_wavenumber, radius, kind, refractive_index, terms))


def _scattering_width(k, a, kind="pec_tm", n=None, n_terms=60):
    m, cm_full, _ = _coeffs(k, a, kind, n, n_terms)
    eps = np.where(m == 0, 1.0, 2.0)
    cm = cm_full / (eps * (1j ** m))
    return float(4.0 / k * np.sum(eps * np.abs(cm) ** 2))
