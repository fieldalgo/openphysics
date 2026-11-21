# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent exact steady-heat fields; no engine, solver or assembly imports.

SI throughout, keyword-only registry names after the leading positional ``points``
((Q,2) metre coordinates); a str for a quantity raises TypeError.
"""
from dataclasses import dataclass
import numpy as np

from ._checks import pair, refuse_text

__all__ = ["HeatFields", "slab", "sine_manufactured"]


def _scalar(value, name, positive=False):
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or not np.isfinite(a) or (positive and a <= 0):
        raise ValueError(f"{name} must be finite real scalar" + (" > 0" if positive else ""))
    return float(a)


def _points(points):
    a = np.asarray(points)
    if a.ndim != 2 or a.shape[1] != 2 or a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError("points must be finite real (Q,2) metre coordinates")
    return a.astype(float)


@dataclass
class HeatFields:
    temperature: np.ndarray
    heat_flux: np.ndarray
    heat_source_density: np.ndarray


def slab(points, *, length, thermal_conductivity, prescribed_temperature):
    """T=TL+(TR-TL)*x/L; q=(-k*(TR-TL)/L,0); Q=0, in SI units.

    prescribed_temperature is the pair (TL, TR) at x = 0 and x = length.
    """
    refuse_text(length=length, thermal_conductivity=thermal_conductivity,
                prescribed_temperature=prescribed_temperature)
    p = _points(points)
    length = _scalar(length, "length", True)
    k = _scalar(thermal_conductivity, "thermal_conductivity", True)
    left, right = pair(prescribed_temperature, "prescribed_temperature")
    left = _scalar(left, "prescribed_temperature[0]")
    right = _scalar(right, "prescribed_temperature[1]")
    gradient = (right-left)/length
    return HeatFields(left+gradient*p[:, 0],
                      np.broadcast_to([-k*gradient, 0.], p.shape).copy(), np.zeros(len(p)))


def sine_manufactured(points, *, length, thermal_conductivity, reference_temperature, temperature_difference):
    """T=T0+A sin(pi*x/Lx)sin(pi*y/Ly), Q=-k*Laplacian(T).

    length is the pair (Lx, Ly) of the rectangle [0,Lx]x[0,Ly], T0 the
    reference_temperature and A the temperature_difference (amplitude). Prescribe
    T0 on all four rectangle boundaries. Independent flux follows direct analytic
    differentiation, not a discrete gradient operator.
    """
    refuse_text(length=length, thermal_conductivity=thermal_conductivity,
                reference_temperature=reference_temperature, temperature_difference=temperature_difference)
    p = _points(points)
    lengths = np.asarray(length)
    if lengths.shape != (2,) or lengths.dtype.kind not in "iuf" or not np.all(np.isfinite(lengths)) or np.any(lengths <= 0):
        raise ValueError("length must be finite positive real (2,) metre values")
    k = _scalar(thermal_conductivity, "thermal_conductivity", True)
    ref = _scalar(reference_temperature, "reference_temperature")
    amp = _scalar(temperature_difference, "temperature_difference")
    wave = np.pi/lengths
    x, y = (p*wave).T
    sx, sy, cx, cy = np.sin(x), np.sin(y), np.cos(x), np.cos(y)
    delta = amp*sx*sy
    flux = -k*amp*np.column_stack([wave[0]*cx*sy, wave[1]*sx*cy])
    return HeatFields(ref+delta, flux, k*np.sum(wave**2)*delta)
