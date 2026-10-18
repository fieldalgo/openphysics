# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Step-index optical fiber — scalar LP modes and exact vector modes.

Core radius a, core index n1, cladding index n2 (n1 > n2), free-space
wavenumber k0 = 2 pi / wavelength. Standard normalized quantities:

    V = k0 a sqrt(n1^2 - n2^2)                normalized frequency
    u = k0 a sqrt(n1^2 - n_eff^2)             core transverse parameter
    w = k0 a sqrt(n_eff^2 - n2^2)             cladding decay parameter
    u^2 + w^2 = V^2
    b = w^2 / V^2                             normalized propagation constant

Scalar (weakly guiding) LP_lm modes, Gloge 1971:
    u J_{l-1}(u) / J_l(u) = -w K_{l-1}(w) / K_l(w)
Cutoff of LP_lm: the m-th zero of J_{l-1} (LP_01 has no cutoff).

Exact vector modes (Snyder & Love; Okamoto eq. 3.53), with
    X = J'_l(u) / (u J_l(u)),    Y = K'_l(w) / (w K_l(w)),   q = (n2/n1)^2:
    (X + Y) (X + q Y) = l^2 (1/u^2 + 1/w^2) (1/u^2 + q / w^2)
l = 0 splits into TE_0m (X + Y = 0) and TM_0m (X + q Y = 0). For l >= 1 the
roots are HE_lm / EH_lm; in the weak-guidance limit HE_{l,m} -> LP_{l-1,m} and
EH_{l,m} -> LP_{l+1,m}, which is how roots are labeled here.

Root finding uses pole-free residuals (multiplied through by J_l K_l) for the
scalar problem, and pole-skipping bracket scans for the vector problem.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.special import jv, kve, jn_zeros


@dataclass(frozen=True)
class Mode:
    label: str      # e.g. "LP01", "HE11", "TE01"
    l: int          # azimuthal order
    m: int          # radial order (1-based)
    neff: float
    u: float
    w: float

    @property
    def b(self) -> float:
        return self.w ** 2 / (self.u ** 2 + self.w ** 2)


def v_number(a: float, n1: float, n2: float, wavelength: float) -> float:
    k0 = 2.0 * np.pi / wavelength
    return k0 * a * np.sqrt(n1 ** 2 - n2 ** 2)


def _neff_from_u(u, a, n1, wavelength):
    k0 = 2.0 * np.pi / wavelength
    return float(np.sqrt(n1 ** 2 - (u / (k0 * a)) ** 2))


def _scan_roots(F, lo, hi, n_grid, skip=None):
    """Bracket sign changes of F on [lo, hi] and refine with brentq.

    skip(u0, u1) -> True marks an interval that contains a pole and must be ignored.
    """
    us = np.linspace(lo, hi, n_grid)
    vals = np.array([F(u) for u in us])
    roots = []
    for i in range(len(us) - 1):
        a_, b_ = vals[i], vals[i + 1]
        if not (np.isfinite(a_) and np.isfinite(b_)):
            continue
        if a_ == 0.0:
            roots.append(us[i]); continue
        if a_ * b_ < 0.0:
            if skip is not None and skip(us[i], us[i + 1]):
                continue
            roots.append(brentq(F, us[i], us[i + 1], xtol=1e-13, rtol=1e-13, maxiter=200))
    return roots


# --------------------------------------------------------------------------
# Scalar LP modes
# --------------------------------------------------------------------------

def lp_modes(a: float, n1: float, n2: float, wavelength: float,
             l_max: int = 10) -> list[Mode]:
    """All guided LP_lm modes, sorted by descending n_eff.

    Pole-free residual for each l:
        F(u) = u J_{l-1}(u) K_l(w) + w K_{l-1}(w) J_l(u),   w = sqrt(V^2 - u^2)
    (K's are exponentially scaled by the same factor, which does not move roots).
    """
    V = v_number(a, n1, n2, wavelength)
    modes = []
    for l in range(0, l_max + 1):
        def F(u, l=l):
            w = np.sqrt(max(V ** 2 - u ** 2, 1e-300))
            return u * jv(l - 1, u) * kve(l, w) + w * kve(l - 1, w) * jv(l, u)
        n_grid = max(2000, int(600 * V))
        roots = _scan_roots(F, 1e-9, V * (1 - 1e-12), n_grid)
        if not roots:
            break   # no LP_l1 means no higher l either (cutoffs increase with l)
        for m, u in enumerate(roots, start=1):
            w = float(np.sqrt(V ** 2 - u ** 2))
            modes.append(Mode(f"LP{l}{m}", l, m, _neff_from_u(u, a, n1, wavelength), u, w))
    return sorted(modes, key=lambda md: -md.neff)


def lp_cutoff_v(l: int, m: int) -> float:
    """Normalized cutoff frequency of LP_lm: the m-th zero of J_{l-1}.

    LP_01 has no cutoff (returns 0). For l = 0, m >= 2 the cutoffs are the zeros of
    J_1 (J_{-1} = -J_1), skipping the trivial zero at the origin.
    """
    if l == 0:
        return 0.0 if m == 1 else float(jn_zeros(1, m - 1)[-1])
    return float(jn_zeros(l - 1, m)[-1])


def num_lp_modes(V: float, l_max: int = 20, m_max: int = 20) -> int:
    """Count of guided LP modes below normalized frequency V (from cutoffs alone).

    Independent of the root finder, so it serves as a cross-check of lp_modes().
    """
    count = 0
    for l in range(l_max + 1):
        for m in range(1, m_max + 1):
            if lp_cutoff_v(l, m) < V:
                count += 1
            else:
                break
    return count


# --------------------------------------------------------------------------
# Exact vector modes
# --------------------------------------------------------------------------

def _XY(l, u, w, q):
    """X = J'_l/(u J_l), Y = K'_l/(w K_l), plus J_l for pole detection."""
    Jl = jv(l, u)
    Jp = 0.5 * (jv(l - 1, u) - jv(l + 1, u))
    X = Jp / (u * Jl)
    # K'_l / K_l = -K_{l-1}/K_l - l/w  (ratio of exponentially scaled K's)
    Y = (-kve(l - 1, w) / kve(l, w) - l / w) / w
    return X, Y, Jl


def vector_modes(a: float, n1: float, n2: float, wavelength: float,
                 l_max: int = 6) -> list[Mode]:
    """All guided exact vector modes (TE, TM, HE, EH), sorted by descending n_eff."""
    V = v_number(a, n1, n2, wavelength)
    q = (n2 / n1) ** 2
    modes = []

    def pole_between(l):
        def skip(u0, u1):
            return jv(l, u0) * jv(l, u1) < 0.0
        return skip

    # ---- l = 0: TE_0m and TM_0m ----
    def F_te(u):
        w = np.sqrt(max(V ** 2 - u ** 2, 1e-300))
        X, Y, _ = _XY(0, u, w, q)
        return X + Y

    def F_tm(u):
        w = np.sqrt(max(V ** 2 - u ** 2, 1e-300))
        X, Y, _ = _XY(0, u, w, q)
        return X + q * Y

    n_grid = max(4000, int(800 * V))
    for label, F in (("TE", F_te), ("TM", F_tm)):
        roots = _scan_roots(F, 1e-6, V * (1 - 1e-12), n_grid, skip=pole_between(0))
        for m, u in enumerate(roots, start=1):
            w = float(np.sqrt(V ** 2 - u ** 2))
            modes.append(Mode(f"{label}0{m}", 0, m, _neff_from_u(u, a, n1, wavelength), u, w))

    # ---- l >= 1: hybrid HE / EH ----
    for l in range(1, l_max + 1):
        def F(u, l=l):
            w = np.sqrt(max(V ** 2 - u ** 2, 1e-300))
            X, Y, _ = _XY(l, u, w, q)
            return (X + Y) * (X + q * Y) - l ** 2 * (1 / u ** 2 + 1 / w ** 2) * (1 / u ** 2 + q / w ** 2)

        roots = _scan_roots(F, 1e-6, V * (1 - 1e-12), n_grid, skip=pole_between(l))
        if not roots:
            break
        he_count = eh_count = 0
        # Classify each root by the weak-guidance reduced equations:
        #   HE: J_{l-1}/(u J_l) - K_{l-1}/(w K_l) = 0
        #   EH: J_{l+1}/(u J_l) + K_{l+1}/(w K_l) = 0
        for u in roots:
            w = float(np.sqrt(V ** 2 - u ** 2))
            Jl = jv(l, u)
            r_he = abs(jv(l - 1, u) / (u * Jl) - kve(l - 1, w) / (w * kve(l, w)))
            r_eh = abs(jv(l + 1, u) / (u * Jl) + kve(l + 1, w) / (w * kve(l, w)))
            if r_he <= r_eh:
                he_count += 1
                label = f"HE{l}{he_count}"
                m = he_count
            else:
                eh_count += 1
                label = f"EH{l}{eh_count}"
                m = eh_count
            modes.append(Mode(label, l, m, _neff_from_u(u, a, n1, wavelength), u, w))

    return sorted(modes, key=lambda md: -md.neff)


def fundamental_neff(a: float, n1: float, n2: float, wavelength: float) -> float:
    """n_eff of the exact HE11 mode (always guided)."""
    for md in vector_modes(a, n1, n2, wavelength, l_max=1):
        if md.label == "HE11":
            return md.neff
    raise RuntimeError("HE11 not found — check parameters")


# --------------------------------------------------------------------------
# Group index of exact vector modes (implicit differentiation)
# --------------------------------------------------------------------------

def _vector_residual_and_partials(family: str, l: int, n: float, wavelength: float, a: float,
                                  n1: float, n2: float) -> tuple[float, dict]:
    """Exact vector dispersion residual F and its analytic partial derivatives.

    F is the equation vector_modes solves, written in X = J'_l/(u J_l) and
    Y = K'_l/(w K_l). Their derivatives follow from the Bessel equations
        J'' = -J'/u - (1 - l^2/u^2) J,     K'' = -K'/w + (1 + l^2/w^2) K,
    giving
        dX/du = -2X/u - (1 - l^2/u^2)/u - u X^2,
        dY/dw = -2Y/w + (1 + l^2/w^2)/w - w Y^2.
    With k = 2 pi a / wavelength, u = k sqrt(n1^2-n^2), w = k sqrt(n^2-n2^2) and
    q = (n2/n1)^2, the chain rule gives partials with respect to n, wavelength,
    n1 and n2. No finite differences are used.
    """
    k = 2.0 * np.pi * a / wavelength
    u = k * np.sqrt(n1 ** 2 - n ** 2)
    w = k * np.sqrt(n ** 2 - n2 ** 2)
    q = (n2 / n1) ** 2
    X = 0.5 * (jv(l - 1, u) - jv(l + 1, u)) / (u * jv(l, u))
    Y = (-kve(l - 1, w) / kve(l, w) - l / w) / w
    X_u = -2 * X / u - (1 - l ** 2 / u ** 2) / u - u * X ** 2
    Y_w = -2 * Y / w + (1 + l ** 2 / w ** 2) / w - w * Y ** 2
    if family == "TE":
        F, F_X, F_Y, F_q, F_u, F_w = X + Y, 1.0, 1.0, 0.0, 0.0, 0.0
    elif family == "TM":
        F, F_X, F_Y, F_q, F_u, F_w = X + q * Y, 1.0, q, Y, 0.0, 0.0
    else:
        A = 1 / u ** 2 + 1 / w ** 2
        B = 1 / u ** 2 + q / w ** 2
        F = (X + Y) * (X + q * Y) - l ** 2 * A * B
        F_X = (X + q * Y) + (X + Y)
        F_Y = (X + q * Y) + q * (X + Y)
        F_q = (X + Y) * Y - l ** 2 * A / w ** 2
        F_u = -l ** 2 * (-2 / u ** 3) * (B + A)
        F_w = -l ** 2 * ((-2 / w ** 3) * B + A * (-2 * q / w ** 3))
    dF_du = F_X * X_u + F_u
    dF_dw = F_Y * Y_w + F_w
    partials = {
        "n": dF_du * (-k ** 2 * n / u) + dF_dw * (k ** 2 * n / w),
        "wavelength": dF_du * (-u / wavelength) + dF_dw * (-w / wavelength),
        "n1": dF_du * (k ** 2 * n1 / u) + F_q * (-2 * q / n1),
        "n2": dF_dw * (-k ** 2 * n2 / w) + F_q * (2 * q / n2),
    }
    return float(F), {name: float(value) for name, value in partials.items()}


def vector_group_index(a: float, n1: float, n2: float, wavelength: float, label: str,
                       dn1_dwavelength: float = 0.0, dn2_dwavelength: float = 0.0) -> tuple[float, float]:
    """(n_eff, n_g) of the exact vector mode ``label`` by implicit differentiation.

    For F(n, lambda, n1, n2) = 0,
        dn/dlambda = -(F_lambda + F_n1 n1' + F_n2 n2') / F_n,   n_g = n - lambda dn/dlambda,
    with analytic partials from the Bessel equations (_vector_residual_and_partials).
    No FEM output and no finite differences are used. ``n1``, ``n2`` and their
    wavelength derivatives are material values at ``wavelength``, in the length
    unit of ``a``.

    Raises ValueError near cutoff, near a Bessel pole of the residual, or when
    the implicit derivative is ill conditioned.
    """
    l_needed = int(label[2]) if label[:2] in ("HE", "EH") else 1
    mode = next((md for md in vector_modes(a, n1, n2, wavelength, l_max=max(1, l_needed))
                 if md.label == label), None)
    if mode is None:
        raise ValueError(f"{label} is not guided at wavelength {wavelength}")
    V = v_number(a, n1, n2, wavelength)
    if mode.w < 1e-3 * V:
        raise ValueError(f"{label} is too close to cutoff for a reliable derivative (w = {mode.w:.3g})")
    if abs(jv(mode.l, mode.u)) < 1e-6:
        raise ValueError(f"{label} root is too close to a pole of the residual")
    _, d = _vector_residual_and_partials(label[:2], mode.l, mode.neff, wavelength, a, n1, n2)
    total = d["wavelength"] + d["n1"] * dn1_dwavelength + d["n2"] * dn2_dwavelength
    scale = abs(d["wavelength"]) * wavelength + abs(d["n1"]) * n1 + abs(d["n2"]) * n2
    if not np.isfinite(d["n"]) or abs(d["n"]) * mode.neff < 1e-8 * scale:
        raise ValueError(f"{label}: implicit derivative is ill conditioned (dF/dn = {d['n']:.3g})")
    return mode.neff, float(mode.neff + wavelength * total / d["n"])
