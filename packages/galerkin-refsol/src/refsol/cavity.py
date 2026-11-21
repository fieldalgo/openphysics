# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent Cartesian standing-wave spectrum of a vacuum PEC box.

Unlike a FEM target search, this reference enumerates every analytic mode up to
an explicit frequency ceiling, retaining polarization and geometric degeneracy.
It does not use a solver, mesh, or the TE/TM enumeration in ``metallic``.

Public API (galerkin step, L3 commit 12): ``rectangular_cavity_modes(*, box_size,
frequency_limit)`` takes the box's side lengths (a, b, c) in m and the frequency ceiling
in Hz under registry names, keyword-only; a str for either raises TypeError. Each mode's
``frequency`` (Hz) and ``wavenumber_squared`` (k**2, 1/m**2) are real, so no time
convention enters.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
from numbers import Real

from ._checks import refuse_text

__all__ = ["C0", "AnalyticCavityMode", "rectangular_cavity_modes"]


C0 = 299_792_458.0  # exact SI speed of light, metres / second


@dataclass(frozen=True)
class AnalyticCavityMode:
    """One independent polarization, including repeated frequencies.

    ``polarization`` is an ordinal in the transverse Cartesian subspace, not a
    TE/TM label. ``frequency`` is in Hz and ``wavenumber_squared`` is k**2 in 1/m**2.
    """

    indices: tuple[int, int, int]
    polarization: int
    frequency: float
    wavenumber_squared: float


def _positive(value, name):
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name} must be a finite positive real number")
    return float(value)


def rectangular_cavity_modes(*, box_size, frequency_limit) -> list[AnalyticCavityMode]:
    """All vacuum PEC modes at or below ``frequency_limit`` (Hz) in a box of ``box_size`` (a, b, c) in m.

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
    refuse_text(box_size=box_size, frequency_limit=frequency_limit)
    try:
        lengths = tuple(box_size)
    except TypeError as exc:
        raise ValueError("box_size must contain three positive lengths in m") from exc
    if len(lengths) != 3:
        raise ValueError("box_size must contain three positive lengths in m")
    lengths = tuple(_positive(v, "box_size") for v in lengths)
    ceiling = _positive(frequency_limit, "frequency_limit")
    bounds = [2 * (ceiling / C0) * length for length in lengths]
    if not all(math.isfinite(bound) for bound in bounds):
        raise ValueError("frequency_limit and box_size exceed representable index bounds")
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
    return sorted(modes, key=lambda mode: (mode.frequency, mode.indices, mode.polarization))
