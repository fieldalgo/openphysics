# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Closed-form 2D electrostatics: capacitances per metre of depth (F/m).

- coaxial line between radii a < b filled with eps_r: C = 2 pi eps0 eps_r / ln(b/a)
- parallel plates with two dielectric layers in series (exact in P1, since the
  potential is linear in each layer)
- the coaxial potential and field magnitude are re-exported from ``metallic``

SI throughout, keyword-only registry names; a str for a quantity raises TypeError.
The radii are the pair ``position`` (inner, outer) and the layers give one
``thickness`` and one ``relative_permittivity`` each, as refsol's other layered
closed forms do. Each function returns a ``capacitance_per_depth`` value, the 2D
cross-section quantity galerkin's ``capacitance_matrix`` is checked against.

``relative_permittivity`` may be complex under exp(-i omega t), with
``Im(eps_r) >= 0`` for a loss (``eps' (1 + i tan d)``); the capacitance is then complex
with ``Im C >= 0``, the loss. Both closed forms are the same formula in either time
convention, so nothing is converted.
"""

from __future__ import annotations

import numpy as np
from scipy.constants import epsilon_0

from ._checks import pair, refuse_text
from .metallic import coax_field_magnitude, coax_potential

__all__ = ["coax_capacitance", "two_layer_plate_capacitance", "coax_potential",
           "coax_field_magnitude", "epsilon_0"]


def coax_capacitance(*, position, relative_permittivity=1.0):
    """Capacitance per metre of depth (F/m) of a coaxial line.

    position: the radii (a, b) of the inner and outer conductor, 0 < a < b (m;
    only their ratio enters). C = 2 pi eps0 eps_r / ln(b/a); a complex
    ``relative_permittivity`` (exp(-i omega t)) gives a complex C.
    """
    refuse_text(position=position, relative_permittivity=relative_permittivity)
    a, b = pair(position, "position")
    if not 0.0 < a < b:
        raise ValueError("position must be the coax radii (a, b) with 0 < a < b")
    return 2.0 * np.pi * epsilon_0 * relative_permittivity / np.log(b / a)


def two_layer_plate_capacitance(*, thickness, relative_permittivity, length):
    """Capacitance per metre of depth (F/m) of a parallel-plate capacitor with two layers.

    Plates of extent ``length`` (m, along the cross-section) are separated by a
    layer of ``thickness[0]`` and ``relative_permittivity[0]`` followed by one of
    ``thickness[1]`` and ``relative_permittivity[1]``: the series combination
    C = eps0 length / (h1/eps1 + h2/eps2), without fringing (the field is
    normal to the plates and the side boundaries are insulated). The potential
    is linear in each layer, so a P1 mesh whose interface follows element
    edges reproduces this value to roundoff.
    """
    refuse_text(thickness=thickness, relative_permittivity=relative_permittivity, length=length)
    h1, h2 = pair(thickness, "thickness")
    eps1, eps2 = pair(relative_permittivity, "relative_permittivity")
    if h1 <= 0 or h2 <= 0 or length <= 0:
        raise ValueError("the layer thicknesses and the plate length must be positive")
    return epsilon_0 * length / (h1 / eps1 + h2 / eps2)
