# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Hollow metallic (PEC) structures with closed-form solutions.

- rectangular waveguide cutoff wavenumbers (TE_mn, TM_mn)
- rectangular cavity resonant wavenumbers (TE_mnp / TM_mnp)
- coaxial cable electrostatic potential and field magnitude

The coaxial closed forms take SI keyword-only registry names after the leading
positional ``points`` ((Q,2) metre coordinates around the axis at the origin); a str
for a quantity raises TypeError. ``refsol.electrostatics`` re-exports them.
``rect_waveguide_cutoffs`` takes the cross-section as ``box_size`` (a, b) in m (L3 commit
11e) and ``rect_cavity_resonances`` the box as ``box_size`` (a, b, d) in m (L3 commit 12);
both return real k**2 in 1/m**2.
"""

from __future__ import annotations

import numpy as np

from ._checks import pair, refuse_text

__all__ = ["rect_waveguide_cutoffs", "rect_cavity_resonances", "coax_potential",
           "coax_field_magnitude"]


def rect_waveguide_cutoffs(*, box_size, n_max: int = 5, include_tm: bool = False) -> list[tuple[float, str]]:
    """Sorted list of (k_c^2, label) for a PEC rectangular waveguide a x b (``box_size`` (a, b), m).

    k_c^2 = (m pi / a)^2 + (n pi / b)^2 in 1/m^2, for m, n <= ``n_max``.
    TE requires (m, n) != (0, 0); TM requires m >= 1 and n >= 1.
    The 2D curl-curl eigenproblem  curl curl E_t = k_c^2 E_t  with n x E = 0
    returns exactly the TE set, which is why include_tm defaults to False.
    """
    refuse_text(box_size=box_size)
    a, b = (float(v) for v in pair(box_size, "box_size"))
    if not (np.isfinite(a) and np.isfinite(b) and a > 0 and b > 0):
        raise ValueError("box_size must be the cross-section (a, b), two finite positive lengths in m")
    if isinstance(n_max, bool) or not isinstance(n_max, (int, np.integer)) or n_max < 0:
        raise ValueError("n_max must be a non-negative integer")
    return _rect_waveguide_cutoffs(a, b, n_max, include_tm)


def _rect_waveguide_cutoffs(a, b, n_max=5, include_tm=False):
    out = []
    for m in range(n_max + 1):
        for n in range(n_max + 1):
            kc2 = (m * np.pi / a) ** 2 + (n * np.pi / b) ** 2
            if (m, n) != (0, 0):
                out.append((kc2, f"TE{m}{n}"))
            if include_tm and m >= 1 and n >= 1:
                out.append((kc2, f"TM{m}{n}"))
    return sorted(out)


def rect_cavity_resonances(*, box_size, n_max: int = 3) -> list[tuple[float, str]]:
    """Sorted list of (k^2, label) for a PEC box a x b x d (``box_size`` (a, b, d), m).

    k^2 = (m pi/a)^2 + (n pi/b)^2 + (p pi/d)^2 in 1/m^2, for m, n, p <= ``n_max``, with the usual
    existence rules: TE_mnp needs p >= 1 and (m, n) != (0, 0); TM_mnp needs m, n >= 1 and p >= 0.
    A 3D Nedelec eigen-solver (M3b) must reproduce this spectrum exactly.
    """
    refuse_text(box_size=box_size)
    message = "box_size must be the box (a, b, d), three finite positive lengths in m"
    if isinstance(box_size, (bytes, dict)) or np.ndim(box_size) != 1 or len(box_size) != 3 \
            or np.iscomplexobj(box_size):
        raise ValueError(message)
    try:
        a, b, d = (float(v) for v in box_size)
    except (TypeError, ValueError) as exc:
        raise ValueError(message) from exc
    if not all(np.isfinite(v) and v > 0 for v in (a, b, d)):
        raise ValueError(message)
    if isinstance(n_max, bool) or not isinstance(n_max, (int, np.integer)) or n_max < 0:
        raise ValueError("n_max must be a non-negative integer")
    return _rect_cavity_resonances(a, b, d, n_max)


def _rect_cavity_resonances(a, b, d, n_max=3):
    out = []
    for m in range(n_max + 1):
        for n in range(n_max + 1):
            for p in range(n_max + 1):
                k2 = (m * np.pi / a) ** 2 + (n * np.pi / b) ** 2 + (p * np.pi / d) ** 2
                if p >= 1 and (m, n) != (0, 0):
                    out.append((k2, f"TE{m}{n}{p}"))
                if m >= 1 and n >= 1:
                    out.append((k2, f"TM{m}{n}{p}"))
    return sorted(out)


def _radius(points):
    """r = hypot(x, y) of finite real (Q,2) metre coordinates."""
    p = np.asarray(points)
    if p.ndim != 2 or p.shape[1] != 2 or p.dtype.kind not in "iuf" or not np.all(np.isfinite(p)):
        raise ValueError("points must be finite real (Q,2) metre coordinates")
    p = p.astype(float)
    return np.hypot(p[:, 0], p[:, 1])


def _coax(position, prescribed_electric_potential):
    a, b = pair(position, "position")
    if not 0.0 < a < b:
        raise ValueError("position must be the coax radii (a, b) with 0 < a < b")
    v_inner, v_outer = pair(prescribed_electric_potential, "prescribed_electric_potential")
    return a, b, v_inner, v_outer


def coax_potential(points, *, position, prescribed_electric_potential):
    """Electrostatic potential (V) at ``points`` between coaxial conductors at radii a < b.

    position: the radii (a, b) of the inner and outer conductor (m);
    prescribed_electric_potential: the pair (V_a, V_b) on them (V).
    V(r) = V_b + (V_a - V_b) ln(b/r) / ln(b/a), r = hypot(x, y).
    """
    refuse_text(position=position, prescribed_electric_potential=prescribed_electric_potential)
    r = _radius(points)
    a, b, v_inner, v_outer = _coax(position, prescribed_electric_potential)
    return v_outer + (v_inner - v_outer) * np.log(b / r) / np.log(b / a)


def coax_field_magnitude(points, *, position, prescribed_electric_potential):
    """|E| (V/m) at ``points``: |V_a - V_b| / (r ln(b/a)) for the coaxial cable (arguments of coax_potential)."""
    refuse_text(position=position, prescribed_electric_potential=prescribed_electric_potential)
    r = _radius(points)
    a, b, v_inner, v_outer = _coax(position, prescribed_electric_potential)
    return abs(v_inner - v_outer) / (r * np.log(b / a))
