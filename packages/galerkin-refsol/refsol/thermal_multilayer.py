# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact steady conduction through layered walls; no engine imports.

Two closed forms with piecewise-constant conductivity k_i and uniform source
Q_i in each layer, temperature and normal heat flux continuous at every
interface (perfect contact, no contact resistance):

layered_slab        series wall 0 < x_1 < ... < x_n = L, T(0)=T_L, T(L)=T_R.
                    q(x) = q_0 + S(x), S' = Q; T' = -q/k.
composite_cylinder  concentric shells r_0 < r_1 < ... < r_n, T(r_0)=T_i,
                    T(r_n)=T_o.  r q_r = C + W(r), W' = Q r; T' = -q_r/k.

The unknown constant (q_0 or C) follows from the far boundary temperature;
with Q = 0 this is the familiar series thermal-resistance formula
q_0 = (T_L-T_R)/sum(L_i/k_i), resp. C = (T_i-T_o)/sum(ln(r_i/r_{i-1})/k_i).
layer=None picks each point's layer from its coordinate. A mesh whose curved
interfaces are inscribed polygons can instead pass the (Q,) layer index of the
triangle holding each point; the layer's closed form is then evaluated as its
analytic continuation, so the comparison keeps the O(h^2) polygon error
instead of hiding it.

All quantities are SI: m, K, W/(m K), W/m^3 and W/m^2.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class LayeredHeatFields:
    temperature: np.ndarray
    heat_flux: np.ndarray
    heat_source: np.ndarray
    layer: np.ndarray


def _points(points):
    a = np.asarray(points)
    if a.ndim != 2 or a.shape[1] != 2 or a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError("points must be finite real (Q,2) metre coordinates")
    return a.astype(float)


def _scalar(value, name):
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or not np.isfinite(a):
        raise ValueError(f"{name} must be a finite real scalar")
    return float(a)


def _layers(start, interfaces, conductivities, sources):
    edges = np.asarray(interfaces)
    k = np.asarray(conductivities)
    if (edges.ndim != 1 or not len(edges) or edges.dtype.kind not in "iuf"
            or not np.all(np.isfinite(edges))):
        raise ValueError("interfaces must be a nonempty finite 1D sequence")
    edges = np.concatenate([[start], edges.astype(float)])
    if np.any(np.diff(edges) <= 0):
        raise ValueError("interfaces must increase strictly from the first face")
    if k.shape != (len(edges)-1,) or k.dtype.kind not in "iuf" or not np.all(np.isfinite(k)) or np.any(k <= 0):
        raise ValueError("conductivities must be one finite value > 0 per layer")
    q = np.zeros(len(k)) if sources is None else np.asarray(sources)
    if q.shape != k.shape or q.dtype.kind not in "iuf" or not np.all(np.isfinite(q)):
        raise ValueError("sources must be one finite value per layer")
    return edges, k.astype(float), q.astype(float)


def _locate(s, edges, label, layer=None):
    if layer is not None:
        i = np.asarray(layer)
        if i.shape != s.shape or i.dtype.kind not in "iu" or np.any(i < 0) or np.any(i >= len(edges)-1):
            raise ValueError("layer must give one valid layer index per point")
        return i.astype(int)
    span = edges[-1]-edges[0]
    if np.any(s < edges[0]-1e-9*span) or np.any(s > edges[-1]+1e-9*span):
        raise ValueError(f"points lie outside the layered {label}")
    return np.clip(np.searchsorted(edges, s, side="right")-1, 0, len(edges)-2)


def layered_slab(points, *, interfaces, conductivities, left_temperature,
                 right_temperature, sources=None, layer=None):
    """Exact 1D series-wall temperature and heat flux q=(q_x,0) at points."""
    p = _points(points)
    edges, k, Q = _layers(0., interfaces, conductivities, sources)
    left = _scalar(left_temperature, "left_temperature")
    right = _scalar(right_temperature, "right_temperature")
    width = np.diff(edges)
    S = np.concatenate([[0.], np.cumsum(Q*width)])[:-1]       # integral of Q to layer start
    drop = (S*width+Q*width**2/2)/k                            # T drop from the source part
    q0 = (left-right-np.sum(drop))/np.sum(width/k)
    drop_full = np.concatenate([[0.], np.cumsum(q0*width/k+drop)])[:-1]
    i = _locate(p[:, 0], edges, "slab", layer)
    d = p[:, 0]-edges[i]
    flux = q0+S[i]+Q[i]*d
    temperature = left-drop_full[i]-((q0+S[i])*d+Q[i]*d**2/2)/k[i]
    return LayeredHeatFields(temperature, np.column_stack([flux, np.zeros(len(p))]),
                             Q[i], i)


def composite_cylinder(points, *, inner_radius, interfaces, conductivities,
                       inner_temperature, outer_temperature, sources=None, layer=None):
    """Exact radial conduction in concentric shells; heat_flux is the (Q,2) vector."""
    p = _points(points)
    r0 = _scalar(inner_radius, "inner_radius")
    if r0 <= 0:
        raise ValueError("inner_radius must be > 0")
    edges, k, Q = _layers(r0, interfaces, conductivities, sources)
    t_in = _scalar(inner_temperature, "inner_temperature")
    t_out = _scalar(outer_temperature, "outer_temperature")
    a, b = edges[:-1], edges[1:]
    W = np.concatenate([[0.], np.cumsum(Q*(b**2-a**2)/2)])[:-1]   # integral of Q r to a_i
    offset = W-Q*a**2/2                     # r q_r = C + offset_i + Q_i r^2/2 in layer i
    log = np.log(b/a)
    drop = (offset*log+Q*(b**2-a**2)/4)/k
    C = (t_in-t_out-np.sum(drop))/np.sum(log/k)
    drop_full = np.concatenate([[0.], np.cumsum(C*log/k+drop)])[:-1]
    r = np.hypot(p[:, 0], p[:, 1])
    i = _locate(r, edges, "cylinder", layer)
    temperature = t_in-drop_full[i]-((C+offset[i])*np.log(r/a[i])+Q[i]*(r**2-a[i]**2)/4)/k[i]
    q_r = (C+offset[i])/r+Q[i]*r/2
    return LayeredHeatFields(temperature, (q_r/r)[:, None]*p, Q[i], i)
