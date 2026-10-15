# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent exact steady-heat fields; no engine, solver or assembly imports."""
from dataclasses import dataclass
import numpy as np


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
    heat_source: np.ndarray


def slab(points, *, length, conductivity, left_temperature, right_temperature):
    """T=TL+(TR-TL)*x/L; q=(-k*(TR-TL)/L,0); Q=0, in SI units."""
    p = _points(points)
    length = _scalar(length, "length", True)
    k = _scalar(conductivity, "conductivity", True)
    left = _scalar(left_temperature, "left_temperature")
    right = _scalar(right_temperature, "right_temperature")
    gradient = (right-left)/length
    return HeatFields(left+gradient*p[:, 0],
                      np.broadcast_to([-k*gradient, 0.], p.shape).copy(), np.zeros(len(p)))


def sine_manufactured(points, *, lengths=(1., 1.), conductivity=1.,
                      reference_temperature=300., amplitude=1.):
    """T=T0+A sin(pi*x/Lx)sin(pi*y/Ly), Q=-k*Laplacian(T).

    Prescribe T0 on all four rectangle boundaries. Independent flux follows
    direct analytic differentiation, not a discrete gradient operator.
    """
    p = _points(points)
    lengths = np.asarray(lengths)
    if lengths.shape != (2,) or lengths.dtype.kind not in "iuf" or not np.all(np.isfinite(lengths)) or np.any(lengths <= 0):
        raise ValueError("lengths must be finite positive real (2,) metre values")
    k = _scalar(conductivity, "conductivity", True)
    ref = _scalar(reference_temperature, "reference_temperature")
    amp = _scalar(amplitude, "amplitude")
    wave = np.pi/lengths
    x, y = (p*wave).T
    sx, sy, cx, cy = np.sin(x), np.sin(y), np.cos(x), np.cos(y)
    delta = amp*sx*sy
    flux = -k*amp*np.column_stack([wave[0]*cx*sy, wave[1]*sx*cy])
    return HeatFields(ref+delta, flux, k*np.sum(wave**2)*delta)
