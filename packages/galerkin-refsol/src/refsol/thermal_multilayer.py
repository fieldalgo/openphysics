# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact steady conduction through layered walls; no engine imports.

Two closed forms with piecewise-constant conductivity k_i and uniform source
Q_i in each layer, temperature and normal heat flux continuous at every
interface (perfect contact, no contact resistance):

layered_slab        series wall x_0 < x_1 < ... < x_n, T(x_0)=T_L, T(x_n)=T_R.
                    q(x) = q_0 + S(x), S' = Q; T' = -q/k.
composite_cylinder  concentric shells r_0 < r_1 < ... < r_n, T(r_0)=T_i,
                    T(r_n)=T_o.  r q_r = C + W(r), W' = Q r; T' = -q_r/k.

Each takes the layer boundaries as one ``position`` sequence (x_0 ... x_n, or the
radii r_0 ... r_n, r_0 > 0), the per-layer ``thermal_conductivity`` and optional
``heat_source_density``, and the end temperatures as the pair ``prescribed_temperature``.

The unknown constant (q_0 or C) follows from the far boundary temperature;
with Q = 0 this is the familiar series thermal-resistance formula
q_0 = (T_L-T_R)/sum(L_i/k_i), resp. C = (T_i-T_o)/sum(ln(r_i/r_{i-1})/k_i).
layer=None picks each point's layer from its coordinate. A mesh whose curved
interfaces are inscribed polygons can instead pass the (Q,) layer index of the
triangle holding each point; the layer's closed form is then evaluated as its
analytic continuation, so the comparison keeps the O(h^2) polygon error
instead of hiding it.

All quantities are SI: m, K, W/(m K), W/m^3 and W/m^2, keyword-only registry names
after the leading positional ``points``; a str for a quantity raises TypeError.
"""
from dataclasses import dataclass

import numpy as np

from ._checks import pair, refuse_text

__all__ = ["LayeredHeatFields", "layered_slab", "composite_cylinder"]


@dataclass
class LayeredHeatFields:
    temperature: np.ndarray
    heat_flux: np.ndarray
    heat_source_density: np.ndarray
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


def _layers(position, conductivities, sources):
    edges = np.asarray(position)
    k = np.asarray(conductivities)
    if (edges.ndim != 1 or len(edges) < 2 or edges.dtype.kind not in "iuf"
            or not np.all(np.isfinite(edges))):
        raise ValueError("position must be a finite 1D sequence of at least two layer boundaries")
    edges = edges.astype(float)
    if np.any(np.diff(edges) <= 0):
        raise ValueError("position must increase strictly from the first face")
    if k.shape != (len(edges)-1,) or k.dtype.kind not in "iuf" or not np.all(np.isfinite(k)) or np.any(k <= 0):
        raise ValueError("thermal_conductivity must be one finite value > 0 per layer")
    q = np.zeros(len(k)) if sources is None else np.asarray(sources)
    if q.shape != k.shape or q.dtype.kind not in "iuf" or not np.all(np.isfinite(q)):
        raise ValueError("heat_source_density must be one finite value per layer")
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


def layered_slab(points, *, position, thermal_conductivity, prescribed_temperature,
                 heat_source_density=None, layer=None):
    """Exact 1D series-wall temperature and heat flux q=(q_x,0) at points.

    position: x_0 < x_1 < ... < x_n, the faces of the wall and its interfaces;
    prescribed_temperature: the pair (T_L, T_R) at x_0 and x_n; heat_source_density:
    one value per layer, or None for none.
    """
    refuse_text(position=position, thermal_conductivity=thermal_conductivity,
                prescribed_temperature=prescribed_temperature, heat_source_density=heat_source_density)
    p = _points(points)
    edges, k, Q = _layers(position, thermal_conductivity, heat_source_density)
    left, right = pair(prescribed_temperature, "prescribed_temperature")
    left = _scalar(left, "prescribed_temperature[0]")
    right = _scalar(right, "prescribed_temperature[1]")
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


def composite_cylinder(points, *, position, thermal_conductivity, prescribed_temperature,
                       heat_source_density=None, layer=None):
    """Exact radial conduction in concentric shells; heat_flux is the (Q,2) vector.

    position: the radii r_0 < r_1 < ... < r_n of the shell boundaries (r_0 > 0);
    prescribed_temperature: the pair (T_i, T_o) at r_0 and r_n; heat_source_density:
    one value per layer, or None for none.
    """
    refuse_text(position=position, thermal_conductivity=thermal_conductivity,
                prescribed_temperature=prescribed_temperature, heat_source_density=heat_source_density)
    p = _points(points)
    edges, k, Q = _layers(position, thermal_conductivity, heat_source_density)
    if edges[0] <= 0:
        raise ValueError("position must start at an inner radius > 0")
    t_in, t_out = pair(prescribed_temperature, "prescribed_temperature")
    t_in = _scalar(t_in, "prescribed_temperature[0]")
    t_out = _scalar(t_out, "prescribed_temperature[1]")
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
