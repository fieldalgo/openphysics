# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady conduction in a rectangle with one hot edge and convective cooling.

Rectangle 0 <= x <= W, 0 <= y <= H, conductivity k, no source. The edge y = 0 is
held at T_b, the edge x = 0 is insulated, and the edges x = W and y = H convect
to the ambient T_a with coefficient h: -k dT/dn = h (T - T_a). Separation of
variables gives the exact series (theta = T - T_a)

    theta(x, y) = sum_n A_n cos(lam_n x) R_n(y),
    lam_n tan(lam_n W) = h/k,            one root in each ((n) pi/W, (n+1/2) pi/W)
    R_n(y) = Y_n(y)/Y_n(0),  Y_n(y) = lam_n k cosh(lam_n (H-y)) + h sinh(lam_n (H-y))
    A_n = (T_b - T_a) sin(lam_n W) / (lam_n N_n),  N_n = W/2 + sin(2 lam_n W)/(4 lam_n).

R_n is evaluated through exp(-lam_n y) ratios so large lam_n never overflow. At
y > 0 the series converges geometrically; on y = 0 it converges like a Fourier
series of a constant, so the truncation is largest next to the hot edge.

NAFEMS T4 ("Two-dimensional heat transfer with convection") is this problem
with W = 0.6 m, H = 1.0 m, k = 52 W/(m K), h = 750 W/(m^2 K), T_b = 100 C,
T_a = 0 C and the target temperature 18.3 C at (0.6, 0.2) m. The statement and
target are reproduced from two public benchmark documents that cite NAFEMS:
DIANA FEA, "Two-Dimensional Heat Transfer with Convection"
(https://tutorials.dianafea.com/2DHeatTransferConvection.pdf, citing NAFEMS,
"The Standard NAFEMS Benchmarks", 1990) and FEATool Multiphysics
`ex_heattransfer4.m` (https://www.featool.com/doc/ex__heattransfer4_8m, citing
A. D. Cameron, J. A. Casey and G. B. Simpson, "Benchmark Tests for Thermal
Analysis", NAFEMS, 1986); both accessed 2026-10-22. Only the published numbers
are reproduced; see NOTICE. The NAFEMS target is quoted to 0.1 C; the series
gives the exact value of the same boundary-value problem.

SI: m, K (or any consistent temperature offset), W/(m K), W/(m^2 K), W/m^2.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import brentq


@dataclass(frozen=True)
class ConvectionRectangle:
    width: float
    height: float
    conductivity: float
    convection: float
    bottom_temperature: float
    ambient: float

    def biot(self):
        return self.convection*self.width/self.conductivity


@dataclass(frozen=True)
class PublishedTarget:
    """A published benchmark number with its provenance."""
    point: tuple
    value: float
    unit: str
    quoted_precision: float
    source: str


NAFEMS_T4 = ConvectionRectangle(width=.6, height=1., conductivity=52., convection=750.,
                                bottom_temperature=100., ambient=0.)
NAFEMS_T4_TARGET = PublishedTarget(
    point=(.6, .2), value=18.3, unit="degC", quoted_precision=.1,
    source="NAFEMS T4 target as quoted by DIANA FEA (2DHeatTransferConvection.pdf, "
           "citing NAFEMS 1990) and FEATool ex_heattransfer4.m (citing Cameron, "
           "Casey and Simpson, NAFEMS 1986); accessed 2026-10-22")


def _check(problem):
    if not isinstance(problem, ConvectionRectangle):
        raise ValueError("problem must be a ConvectionRectangle")
    for name in ("width", "height", "conductivity", "convection", "bottom_temperature", "ambient"):
        v = getattr(problem, name)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not np.isfinite(v):
            raise ValueError(f"{name} must be a finite real number")
    if min(problem.width, problem.height, problem.conductivity) <= 0 or problem.convection <= 0:
        raise ValueError("width, height, conductivity and convection must be positive")


def eigenvalues(problem, terms):
    """The first `terms` roots lam_n of lam tan(lam W) = h/k, increasing."""
    _check(problem)
    if not isinstance(terms, (int, np.integer)) or isinstance(terms, bool) or terms < 1:
        raise ValueError("terms must be a positive integer")
    W, bi = problem.width, problem.convection/problem.conductivity
    f = lambda lam: lam*np.sin(lam*W)-bi*np.cos(lam*W)   # tan without poles
    roots = []
    for n in range(terms):
        lo, hi = n*np.pi/W, (n+.5)*np.pi/W
        roots.append(brentq(f, lo+1e-14*hi, hi-1e-14*hi, xtol=1e-15*hi, rtol=4*np.finfo(float).eps, maxiter=200))
    return np.asarray(roots)


def _points(points):
    p = np.asarray(points)
    if p.ndim != 2 or p.shape[1] != 2 or p.dtype.kind not in "iuf" or not np.all(np.isfinite(p)):
        raise ValueError("points must be finite real (Q,2) metre coordinates")
    return p.astype(float)


@dataclass
class ConvectionFields:
    temperature: np.ndarray      # (Q,)
    heat_flux: np.ndarray        # (Q,2) W/m^2, q = -k grad T
    terms: int


def series(points, problem, terms=120, chunk=4096):
    """Exact temperature and heat flux at (Q,2) points inside the rectangle."""
    _check(problem)
    p = _points(points)
    W, H, k, h = problem.width, problem.height, problem.conductivity, problem.convection
    if np.any(p[:, 0] < -1e-9*W) or np.any(p[:, 0] > W*(1+1e-9)) or np.any(p[:, 1] < -1e-9*H) or np.any(p[:, 1] > H*(1+1e-9)):
        raise ValueError("points must lie inside the rectangle")
    lam = eigenvalues(problem, terms)
    norm = W/2+np.sin(2*lam*W)/(4*lam)
    A = (problem.bottom_temperature-problem.ambient)*np.sin(lam*W)/(lam*norm)
    d0 = lam*k*(1+np.exp(-2*lam*H))+h*(1-np.exp(-2*lam*H))      # Y_n(0) e^{-lam H}
    T = np.empty(len(p)); q = np.empty((len(p), 2))
    for s in range(0, len(p), chunk):
        x, y = p[s:s+chunk].T
        ex = np.exp(-lam[None, :]*y[:, None])
        e2 = np.exp(-2*lam[None, :]*(H-y)[:, None])
        R = ex*(lam*k*(1+e2)+h*(1-e2))/d0                      # Y_n(y)/Y_n(0)
        dR = -lam*ex*(lam*k*(1-e2)+h*(1+e2))/d0                 # Y_n'(y)/Y_n(0)
        cos, sin = np.cos(lam[None, :]*x[:, None]), np.sin(lam[None, :]*x[:, None])
        T[s:s+chunk] = problem.ambient+np.sum(A*cos*R, axis=1)
        q[s:s+chunk, 0] = k*np.sum(A*lam*sin*R, axis=1)
        q[s:s+chunk, 1] = -k*np.sum(A*cos*dR, axis=1)
    return ConvectionFields(T, q, int(terms))
