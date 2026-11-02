# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent exact steady-heat fields in three dimensions; no engine imports.

sine_product   T = T0 + A sin(pi x/Lx) sin(pi y/Ly) sin(pi z/Lz) on the box
               [0,Lx]x[0,Ly]x[0,Lz], Q = -k Laplacian(T) = k pi^2 (1/Lx^2 + 1/Ly^2 + 1/Lz^2) (T - T0);
               T = T0 on all six faces. A manufactured solution: P1 converges at
               second order in L2 and first order in H1.
layered_slab   conduction along z through layers 0 = z_0 < z_1 < ... < z_n = L with
               conductivity k_i and no source, T(0) = T_bottom, T(L) = T_top:
               the heat flux q = (T_bottom - T_top) / sum(d_i / k_i) is uniform and
               T is piecewise linear, which P1 reproduces exactly on a mesh whose
               layer boundaries are node planes.

All quantities are SI: m, K, W/(m K), W/m^3 and W/m^2.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class HeatFields3D:
    temperature: np.ndarray        # (Q,)
    heat_flux: np.ndarray          # (Q, 3)
    heat_source: np.ndarray        # (Q,)


def _points(points):
    a = np.asarray(points)
    if a.ndim != 2 or a.shape[1] != 3 or a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError("points must be finite real (Q, 3) metre coordinates")
    return a.astype(float)


def _scalar(value, name, positive=False):
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or not np.isfinite(a) or (positive and a <= 0):
        raise ValueError(f"{name} must be a finite real scalar" + (" > 0" if positive else ""))
    return float(a)


def sine_product(points, *, lengths=(1.0, 1.0, 1.0), conductivity=1.0,
                 reference_temperature=300.0, amplitude=1.0):
    """Temperature, flux -k grad T and source -k Laplacian(T) of the sine product."""
    p = _points(points)
    lengths = np.asarray(lengths)
    if (lengths.shape != (3,) or lengths.dtype.kind not in "iuf" or not np.all(np.isfinite(lengths))
            or np.any(lengths <= 0)):
        raise ValueError("lengths must be finite positive real (3,) metre values")
    k = _scalar(conductivity, "conductivity", True)
    ref = _scalar(reference_temperature, "reference_temperature")
    amp = _scalar(amplitude, "amplitude")
    wave = np.pi / lengths
    s, c = np.sin(p * wave), np.cos(p * wave)
    delta = amp * s[:, 0] * s[:, 1] * s[:, 2]
    flux = -k * amp * np.column_stack([wave[0] * c[:, 0] * s[:, 1] * s[:, 2],
                                       wave[1] * s[:, 0] * c[:, 1] * s[:, 2],
                                       wave[2] * s[:, 0] * s[:, 1] * c[:, 2]])
    return HeatFields3D(ref + delta, flux, k * np.sum(wave ** 2) * delta)


def layered_slab(points, *, interfaces, conductivities, bottom_temperature, top_temperature,
                 start=0.0):
    """Series conduction along z: temperature, flux (0, 0, q) and zero source at ``points``.

    interfaces: z_1 < ... < z_n, the top of each layer (z_n is the top of the stack);
    conductivities: k_1 ... k_n. Points must lie in [start, z_n] up to roundoff.
    """
    p = _points(points)
    z_top = np.asarray(interfaces, dtype=float)
    k = np.asarray(conductivities, dtype=float)
    start = _scalar(start, "start")
    if z_top.ndim != 1 or not len(z_top) or not np.all(np.isfinite(z_top)):
        raise ValueError("interfaces must be a nonempty finite 1D sequence")
    edges = np.concatenate([[start], z_top])
    if np.any(np.diff(edges) <= 0):
        raise ValueError("interfaces must increase strictly from start")
    if k.shape != z_top.shape or not np.all(np.isfinite(k)) or np.any(k <= 0):
        raise ValueError("conductivities must be finite positive, one per layer")
    bottom = _scalar(bottom_temperature, "bottom_temperature")
    top = _scalar(top_temperature, "top_temperature")
    thickness = np.diff(edges)
    resistance = thickness / k
    flux = (bottom - top) / resistance.sum()                    # W/m^2 along +z
    drop = np.concatenate([[0.0], np.cumsum(flux * resistance)])  # temperature drop at each edge
    z = p[:, 2]
    tolerance = 1e-12 * max(abs(edges[-1] - edges[0]), 1.0)
    if np.any(z < edges[0] - tolerance) or np.any(z > edges[-1] + tolerance):
        raise ValueError("points must lie within the stack")
    layer = np.clip(np.searchsorted(edges, z, side="right") - 1, 0, len(k) - 1)
    temperature = bottom - drop[layer] - flux * (z - edges[layer]) / k[layer]
    heat_flux = np.zeros_like(p)
    heat_flux[:, 2] = flux
    return HeatFields3D(temperature, heat_flux, np.zeros(len(p)))
