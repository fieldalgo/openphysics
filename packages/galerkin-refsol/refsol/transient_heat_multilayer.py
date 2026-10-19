# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact transient conduction through a layered wall by eigenfunction series.

NumPy only; no engine, solver or assembly imports. SI: m, s, K, W/(m K),
J/(m^3 K). Layers 0 < x_1 < ... < x_n = L with k_i, c_i; perfect contact;
fixed end temperatures T(0)=T_L, T(L)=T_R; insulated in y.

    c dT/dt = d/dx(k dT/dx),   T = T_s(x) + sum_m A_m X_m(x) exp(-lambda_m t)

T_s is the series-resistance steady state. X_m solve -(k X')' = lambda c X
with X(0) = X(L) = 0 and X, k X' continuous. In layer i, with
w_i = sqrt(lambda c_i / k_i) and d = x - x_{i-1}, the transfer relations

    X = X0 cos(w d) - F0 sin(w d)/(k w),  F = F0 cos(w d) + k w X0 sin(w d)

carry (X, F = -k X') across the layer. Eigenvalues are the roots of
X(L; lambda) = 0, bracketed on a fine sqrt(lambda) grid and bisected. Each
mode is scaled to max |X| = 1 on a dense grid. The initial field is
T_s + sum A_m X_m, so the series is exact with the given finite amplitudes.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class LayeredTransientFields:
    temperature: np.ndarray     # (Q,) K
    heat_flux: np.ndarray       # (Q,2) W/m^2
    layer: np.ndarray           # (Q,)


def _vector(values, name, n=None, positive=False):
    a = np.asarray(values)
    if (a.ndim != 1 or not len(a) or a.dtype.kind not in "iuf" or not np.all(np.isfinite(a))
            or (n is not None and len(a) != n) or (positive and np.any(a <= 0))):
        raise ValueError(f"{name} must be a finite 1D sequence" + (" > 0" if positive else ""))
    return a.astype(float)


def _scalar(value, name):
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or not np.isfinite(a):
        raise ValueError(f"{name} must be a finite real scalar")
    return float(a)


class LayeredWall:
    """Eigenvalues and modes of one layered wall; reuse for many evaluations."""

    def __init__(self, interfaces, conductivities, capacities):
        x = _vector(interfaces, "interfaces")
        self.edges = np.concatenate([[0.], x])
        if np.any(np.diff(self.edges) <= 0):
            raise ValueError("interfaces must increase strictly from 0")
        n = len(x)
        self.k = _vector(conductivities, "conductivities", n, True)
        self.c = _vector(capacities, "capacities", n, True)
        self.width = np.diff(self.edges)
        self._eigen = np.array([])

    def _end_value(self, s):
        """X(L) for sqrt(lambda) = s > 0, starting from X=0, F=-1 at x=0."""
        X, F = 0., -1.
        for k, c, d in zip(self.k, self.c, self.width):
            w = s*np.sqrt(c/k)
            X, F = X*np.cos(w*d)-F*np.sin(w*d)/(k*w), F*np.cos(w*d)+k*w*X*np.sin(w*d)
        return X

    def eigenvalues(self, count):
        """The first `count` eigenvalues lambda_m (1/s), increasing."""
        if not isinstance(count, (int, np.integer)) or count < 1:
            raise ValueError("count must be a positive integer")
        if len(self._eigen) >= count:
            return self._eigen[:count].copy()
        phase = np.sum(self.width*np.sqrt(self.c/self.k))     # s * phase = total optical length
        step = np.pi/phase/400
        roots, s, f = [], step*1e-3, self._end_value(step*1e-3)
        while len(roots) < count:
            s2 = s+step
            f2 = self._end_value(s2)
            if f == 0.:
                roots.append(s)
            elif f*f2 < 0:
                lo, hi, flo = s, s2, f
                for _ in range(200):
                    mid = .5*(lo+hi)
                    fm = self._end_value(mid)
                    if fm == 0. or hi-lo <= 4*np.finfo(float).eps*hi:
                        break
                    if flo*fm < 0:
                        hi = mid
                    else:
                        lo, flo = mid, fm
                roots.append(.5*(lo+hi))
            s, f = s2, f2
        self._eigen = np.asarray(roots)**2
        return self._eigen[:count].copy()

    def _state(self, s, x, layer):
        """(X, F) at x for sqrt(lambda) = s, unscaled."""
        starts = [(0., -1.)]
        for k, c, d in zip(self.k, self.c, self.width):
            w = s*np.sqrt(c/k)
            X0, F0 = starts[-1]
            starts.append((X0*np.cos(w*d)-F0*np.sin(w*d)/(k*w), F0*np.cos(w*d)+k*w*X0*np.sin(w*d)))
        X0 = np.array([starts[i][0] for i in layer])
        F0 = np.array([starts[i][1] for i in layer])
        k, w = self.k[layer], s*np.sqrt(self.c[layer]/self.k[layer])
        d = x-self.edges[layer]
        return X0*np.cos(w*d)-F0*np.sin(w*d)/(k*w), F0*np.cos(w*d)+k*w*X0*np.sin(w*d)

    def mode(self, m, x, layer):
        """Mode m (0-based) X_m and its flux -k X_m' at x, scaled to max |X| = 1."""
        s = np.sqrt(self.eigenvalues(m+1)[m])
        dense = np.concatenate([np.linspace(a, b, 400) for a, b in zip(self.edges[:-1], self.edges[1:])])
        dl = np.repeat(np.arange(len(self.k)), 400)
        X_dense, _ = self._state(s, dense, dl)
        scale = X_dense[np.argmax(abs(X_dense))]
        X, F = self._state(s, x, layer)
        return X/scale, F/scale

    def locate(self, x, layer=None):
        if layer is not None:
            i = np.asarray(layer)
            if i.shape != x.shape or i.dtype.kind not in "iu" or np.any(i < 0) or np.any(i >= len(self.k)):
                raise ValueError("layer must give one valid layer index per point")
            return i.astype(int)
        span = self.edges[-1]
        if np.any(x < -1e-9*span) or np.any(x > span*(1+1e-9)):
            raise ValueError("points lie outside the layered wall")
        return np.clip(np.searchsorted(self.edges, x, side="right")-1, 0, len(self.k)-1)

    def fields(self, points, time_s, *, left_temperature, right_temperature, amplitudes,
               layer=None):
        """Exact T and q at points (Q,2) and time t >= 0 (s)."""
        p = np.asarray(points)
        if p.ndim != 2 or p.shape[1] != 2 or p.dtype.kind not in "iuf" or not np.all(np.isfinite(p)):
            raise ValueError("points must be finite real (Q,2) metre coordinates")
        t = _scalar(time_s, "time_s")
        if t < 0:
            raise ValueError("time_s must be >= 0")
        tl, tr = _scalar(left_temperature, "left_temperature"), _scalar(right_temperature, "right_temperature")
        amp = _vector(amplitudes, "amplitudes")
        x = p[:, 0].astype(float)
        i = self.locate(x, layer)
        q0 = (tl-tr)/np.sum(self.width/self.k)
        drop = np.concatenate([[0.], np.cumsum(q0*self.width/self.k)])[:-1]
        T = tl-drop[i]-q0*(x-self.edges[i])/self.k[i]
        q = np.full(len(x), q0)
        lam = self.eigenvalues(len(amp))
        for m, (a, l) in enumerate(zip(amp, lam)):
            X, F = self.mode(m, x, i)
            T = T+a*np.exp(-l*t)*X
            q = q+a*np.exp(-l*t)*F
        return LayeredTransientFields(T, np.column_stack([q, np.zeros(len(x))]), i)

    def _steady(self, x, i, temperature, sources):
        """Steady state with both ends at `temperature` and per-layer sources."""
        S = np.concatenate([[0.], np.cumsum(sources*self.width)])[:-1]
        drop = (S*self.width+sources*self.width**2/2)/self.k
        q0 = -np.sum(drop)/np.sum(self.width/self.k)
        full = np.concatenate([[0.], np.cumsum(q0*self.width/self.k+drop)])[:-1]
        d = x-self.edges[i]
        T = temperature-full[i]-((q0+S[i])*d+sources[i]*d**2/2)/self.k[i]
        return T, q0+S[i]+sources[i]*d

    def _quadrature(self, panels=64, order=20):
        g, w = np.polynomial.legendre.leggauss(order)
        xs, ws, layer = [], [], []
        for i, (lo, hi) in enumerate(zip(self.edges[:-1], self.edges[1:])):
            cuts = np.linspace(lo, hi, panels+1)
            for a, b in zip(cuts[:-1], cuts[1:]):
                xs.append(a+(b-a)*(g+1)/2)
                ws.append(w*(b-a)/2)
                layer.append(np.full(order, i))
        return np.concatenate(xs), np.concatenate(ws), np.concatenate(layer)

    def source_amplitudes(self, *, temperature, sources, count):
        """A_m for T(x,0) = temperature: c-weighted projections of T0 - T_s."""
        T0 = _scalar(temperature, "temperature")
        Q = _vector(sources, "sources", len(self.k))
        key = (T0, tuple(Q), int(count))
        cache = getattr(self, "_amplitude_cache", {})
        if key in cache:
            return cache[key]
        self.eigenvalues(count)
        x, w, layer = self._quadrature()
        Ts, _ = self._steady(x, layer, T0, Q)
        weight = w*self.c[layer]
        amp = np.empty(count)
        for m in range(count):
            X, _ = self.mode(m, x, layer)
            amp[m] = np.sum(weight*(T0-Ts)*X)/np.sum(weight*X*X)
        cache[key] = amp
        self._amplitude_cache = cache
        return amp

    def source_driven(self, points, time_s, *, temperature, sources, count, layer=None):
        """Wall at uniform `temperature` with fixed ends; sources switched on at t = 0.

        T = T_s + sum_{m<count} A_m X_m exp(-lambda_m t). The truncated tail is
        not bounded here; compare two counts to measure it.
        """
        p = np.asarray(points)
        if p.ndim != 2 or p.shape[1] != 2 or p.dtype.kind not in "iuf" or not np.all(np.isfinite(p)):
            raise ValueError("points must be finite real (Q,2) metre coordinates")
        t = _scalar(time_s, "time_s")
        if t < 0:
            raise ValueError("time_s must be >= 0")
        amp = self.source_amplitudes(temperature=temperature, sources=sources, count=count)
        x = p[:, 0].astype(float)
        i = self.locate(x, layer)
        T, q = self._steady(x, i, float(temperature), np.asarray(sources, dtype=float))
        for m, (a, l) in enumerate(zip(amp, self.eigenvalues(count))):
            X, F = self.mode(m, x, i)
            T = T+a*np.exp(-l*t)*X
            q = q+a*np.exp(-l*t)*F
        return LayeredTransientFields(T, np.column_stack([q, np.zeros(len(x))]), i)
