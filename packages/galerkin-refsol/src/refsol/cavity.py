# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent Cartesian standing-wave spectrum of a vacuum PEC box.

Unlike a FEM target search, this reference enumerates every analytic mode up to
an explicit frequency ceiling, retaining polarization and geometric degeneracy.
It does not use a solver, mesh, or the TE/TM enumeration in ``metallic``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
from numbers import Real


C0 = 299_792_458.0  # exact SI speed of light, metres / second


@dataclass(frozen=True)
class AnalyticCavityMode:
    """One independent polarization, including repeated frequencies.

    ``polarization`` is an ordinal in the transverse Cartesian subspace, not a
    TE/TM label. ``eigenvalue_m2`` denotes inverse square metres (k squared).
    """

    indices: tuple[int, int, int]
    polarization: int
    frequency_hz: float
    eigenvalue_m2: float


def _positive(value, name):
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name} must be a finite positive real number")
    return float(value)


def rectangular_cavity_modes(lengths_m, max_frequency_hz) -> list[AnalyticCavityMode]:
    """All vacuum PEC modes at or below ``max_frequency_hz`` in an SI box.

    Electric components have the standing-wave form
    ``Ex = Ax cos(kx*x) sin(ky*y) sin(kz*z)`` and cyclic permutations.
    With three positive indices, divergence freedom leaves two independent
    amplitudes. With exactly two positive indices, only the electric component
    along the zero index survives. Fewer than two positive indices give no
    electric field, so neither a static kernel nor a TEM mode is enumerated.

    Each index obeys ``n_i <= 2*f_max*L_i/c``. Enumerating those independent
    bounds and then applying the frequency ceiling gives a complete finite
    analytic list; it makes no assertion about completeness of a FEM search.
    Frequencies at the ceiling are included within floating-point rounding.
    """
    try:
        lengths = tuple(lengths_m)
    except TypeError as exc:
        raise ValueError("lengths_m must contain three positive lengths") from exc
    if len(lengths) != 3:
        raise ValueError("lengths_m must contain three positive lengths")
    lengths = tuple(_positive(v, "lengths_m") for v in lengths)
    ceiling = _positive(max_frequency_hz, "max_frequency_hz")
    bounds = [2 * (ceiling / C0) * length for length in lengths]
    if not all(math.isfinite(bound) for bound in bounds):
        raise ValueError("frequency and lengths exceed representable index bounds")
    # One extra index protects an exactly integral floating-point boundary.
    ranges = [range(math.floor(bound) + 2) for bound in bounds]
    modes = []
    for indices in product(*ranges):
        positive = sum(n > 0 for n in indices)
        if positive < 2:
            continue
        inverse_wavelength = math.hypot(*(n / length for n, length in zip(indices, lengths)))
        frequency = 0.5 * C0 * inverse_wavelength
        if frequency > ceiling and not math.isclose(frequency, ceiling, rel_tol=1e-14):
            continue
        eigenvalue = (math.pi * inverse_wavelength) ** 2
        for polarization in range(positive - 1):
            modes.append(AnalyticCavityMode(indices, polarization, frequency, eigenvalue))
    return sorted(modes, key=lambda mode: (mode.frequency_hz, mode.indices, mode.polarization))
