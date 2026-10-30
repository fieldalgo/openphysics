# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Causal Huray surface correction; exp(+j omega t), SI radii.

This is a constitutive half-space model, not a resolved rough surface or a
finite-metal DC solve. The base matte/flat area ratio is fixed to one.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .network import _real

__all__ = ['CausalHuray']


@dataclass(frozen=True)
class CausalHuray:
    """Sphere radii (m) and full-sphere area ratios N*4*pi*a**2/A_flat.

    Each of 1..64 populations needs a positive radius and nonnegative area
    ratio. Caller arrays are copied into tuples. No conversion from Ra/Rq/Rz
    or assumption about sphere packing is made.
    """
    radii_m: tuple[float, ...]
    surface_ratios: tuple[float, ...]

    def __post_init__(self):
        radii = _real('radii_m', self.radii_m)
        ratios = _real('surface_ratios', self.surface_ratios)
        if (radii.ndim != 1 or not 1 <= radii.size <= 64
                or ratios.shape != radii.shape
                or np.any(radii <= 0) or np.any(ratios < 0)):
            raise ValueError('Huray needs 1..64 positive radii and matching nonnegative surface ratios')
        # Bound the entire high-frequency response before evaluating any input.
        try:
            saturation = 1 + 1.5*math.fsum(ratios)
        except OverflowError as exc:
            raise ValueError('Huray saturation cannot be represented') from exc
        if not np.isfinite(saturation):
            raise ValueError('Huray saturation cannot be represented')
        object.__setattr__(self, 'radii_m', tuple(float(x) for x in radii))
        object.__setattr__(self, 'surface_ratios', tuple(float(x) for x in ratios))

    def factor(self, skin_depth):
        """Complex multiplier H for nonempty positive skin depths (m).

        H = 1 + sum(1.5*SR*q/(1+q)), q=(1+j)*a/delta. The principal
        square root q=sqrt(s*mu*sigma*a**2) defines its causal continuation.
        Input order is retained. This multiplier is NOT the resistance ratio.
        """
        delta = _real('skin_depth', skin_depth)
        if delta.ndim != 1 or not delta.size or np.any(delta <= 0):
            raise ValueError('skin_depth must be a nonempty positive one-dimensional array')
        result = np.ones(delta.shape, dtype=complex)
        for radius, ratio in zip(self.radii_m, self.surface_ratios):
            # Normalize before division: even extreme finite a/delta must not
            # overflow, square to infinity or produce an indeterminate inf/inf.
            scale = np.maximum(radius, delta)
            a, d = radius/scale, delta/scale
            q = (1+1j)*a
            result += (1.5*ratio)*(q/(d+q))
        if not np.all(np.isfinite(result)):
            raise ValueError('Huray response cannot be represented')
        return result

    def _impedance_factors(self, skin_depth):
        """Evaluate R/X ratios without subtracting nearly equal large values."""
        delta = np.asarray(skin_depth, dtype=float)
        resistance, reactance = np.ones(delta.shape), np.ones(delta.shape)
        for radius, ratio in zip(self.radii_m, self.surface_ratios):
            scale = np.maximum(radius, delta)
            a, d = radius/scale, delta/scale
            denominator = d*d+2*a*d+2*a*a
            weighted = (1.5*ratio)*a
            resistance += weighted*(2*a/denominator)
            reactance += weighted*(2*(d+a)/denominator)
        return resistance, reactance
