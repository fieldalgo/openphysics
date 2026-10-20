# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Hollow metallic (PEC) structures with closed-form solutions.

- rectangular waveguide cutoff wavenumbers (TE_mn, TM_mn)
- rectangular cavity resonant wavenumbers (TE_mnp / TM_mnp)
- coaxial cable electrostatic potential
"""

from __future__ import annotations

import numpy as np


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


def coax_potential(r, a: float, b: float, v_inner: float = 1.0,
                   v_outer: float = 0.0):
    """Electrostatic potential between coaxial conductors at radii a < b.

    V(r) = v_outer + (v_inner - v_outer) ln(b/r) / ln(b/a).
    """
    r = np.asarray(r, dtype=float)
    return v_outer + (v_inner - v_outer) * np.log(b / r) / np.log(b / a)


def coax_field_magnitude(r, a: float, b: float, v_inner: float = 1.0,
                         v_outer: float = 0.0):
    """|E|(r) = (v_inner - v_outer) / (r ln(b/a)) for the coaxial cable."""
    r = np.asarray(r, dtype=float)
    return abs(v_inner - v_outer) / (r * np.log(b / a))
