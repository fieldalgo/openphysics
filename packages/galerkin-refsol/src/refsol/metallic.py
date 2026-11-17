# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Hollow metallic (PEC) structures with closed-form solutions.

- rectangular waveguide cutoff wavenumbers (TE_mn, TM_mn)
- rectangular cavity resonant wavenumbers (TE_mnp / TM_mnp)
- coaxial cable electrostatic potential and field magnitude

The coaxial closed forms take SI keyword-only registry names after the leading
positional ``points`` ((Q,2) metre coordinates around the axis at the origin); a str
for a quantity raises TypeError. ``refsol.electrostatics`` re-exports them.
"""

from __future__ import annotations

import numpy as np

from ._checks import pair, refuse_text

__all__ = ["rect_waveguide_cutoffs", "rect_cavity_resonances", "coax_potential",
           "coax_field_magnitude"]


def rect_waveguide_cutoffs(a: float, b: float, n_max: int = 5,
                           include_tm: bool = False) -> list[tuple[float, str]]:
    """Sorted list of (k_c^2, label) for a PEC rectangular waveguide a x b.

    k_c^2 = (m pi / a)^2 + (n pi / b)^2.
    TE requires (m, n) != (0, 0); TM requires m >= 1 and n >= 1.
    The 2D curl-curl eigenproblem  curl curl E_t = k_c^2 E_t  with n x E = 0
    returns exactly the TE set, which is why include_tm defaults to False.
    """
    out = []
    for m in range(n_max + 1):
        for n in range(n_max + 1):
            kc2 = (m * np.pi / a) ** 2 + (n * np.pi / b) ** 2
            if (m, n) != (0, 0):
                out.append((kc2, f"TE{m}{n}"))
            if include_tm and m >= 1 and n >= 1:
                out.append((kc2, f"TM{m}{n}"))
    return sorted(out)


def rect_cavity_resonances(a: float, b: float, d: float, n_max: int = 3
                           ) -> list[tuple[float, str]]:
    """Sorted list of (k^2, label) for a PEC box a x b x d.

    k^2 = (m pi/a)^2 + (n pi/b)^2 + (p pi/d)^2 with the usual existence rules:
    TE_mnp needs p >= 1 and (m, n) != (0, 0); TM_mnp needs m, n >= 1 and p >= 0.
    A 3D Nedelec eigen-solver (M3b) must reproduce this spectrum exactly.
    """
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
