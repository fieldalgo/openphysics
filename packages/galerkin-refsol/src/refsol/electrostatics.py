# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Closed-form 2D electrostatics: per-unit-length capacitances (F/m).

- coaxial line between radii a < b filled with eps_r: C = 2 pi eps0 eps_r / ln(b/a)
- parallel plates with two dielectric layers in series (exact in P1, since the
  potential is linear in each layer)
- the coaxial potential and field magnitude are re-exported from ``metallic``

``eps_r`` may be complex with ``Im(eps_r) <= 0`` (``eps' (1 - j tan d)``); the
capacitance is then complex with the same sign convention.
"""

from __future__ import annotations

import numpy as np
from scipy.constants import epsilon_0

from .metallic import coax_field_magnitude, coax_potential

__all__ = ["coax_capacitance", "two_layer_plate_capacitance", "coax_potential",
           "coax_field_magnitude", "epsilon_0"]


def coax_capacitance(a: float, b: float, eps_r=1.0):
    """Per-unit-length capacitance (F/m) of a coaxial line, radii 0 < a < b.

    C = 2 pi eps0 eps_r / ln(b/a); complex ``eps_r`` gives complex C.
    """
    if not 0.0 < a < b:
        raise ValueError("coax radii must satisfy 0 < a < b")
    return 2.0 * np.pi * epsilon_0 * eps_r / np.log(b / a)


def two_layer_plate_capacitance(h1: float, eps1, h2: float, eps2, width: float):
    """Per-unit-length capacitance (F/m) of a parallel-plate capacitor with two layers.

    Plates of extent ``width`` (m, along the cross-section) are separated by a
    layer of thickness ``h1`` and relative permittivity ``eps1`` followed by a
    layer ``h2``, ``eps2``: the series combination
    C = eps0 width / (h1/eps1 + h2/eps2), without fringing (the field is
    normal to the plates and the side boundaries are insulated). The potential
    is linear in each layer, so a P1 mesh whose interface follows element
    edges reproduces this value to roundoff.
    """
    if h1 <= 0 or h2 <= 0 or width <= 0:
        raise ValueError("layer thicknesses and the plate width must be positive")
    return epsilon_0 * width / (h1 / eps1 + h2 / eps2)
