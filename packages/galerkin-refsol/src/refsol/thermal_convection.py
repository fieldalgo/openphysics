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

SI: m, K, W/(m K), W/(m^2 K), W/m^2, keyword-only registry names; a str for a
quantity raises TypeError. The published NAFEMS T4 numbers are stored as published
(degrees Celsius) in the private ``refsol._published``; ``nafems_t4()`` and
``nafems_t4_target()`` return them in SI, each Celsius value converted at run time by
the decimal rule K = float(Fraction(repr(value)) + 273.15) (100 C -> 373.15 K,
0 C -> 273.15 K, 18.3 C -> 291.45 K, each the double nearest the exact decimal) and
the quoted precision, a temperature difference, unchanged (0.1 C -> 0.1 K).
"""
from dataclasses import dataclass
from fractions import Fraction
import numpy as np
from scipy.optimize import brentq

from . import _published
from ._checks import pair, refuse_text

__all__ = ["ConvectionRectangle", "PublishedTarget", "nafems_t4", "nafems_t4_target", "eigenvalues",
           "ConvectionFields", "series"]

_CELSIUS_ZERO = Fraction(27315, 100)          # 273.15 K, exact


@dataclass(frozen=True, kw_only=True)
class ConvectionRectangle:
    """Rectangle 0 <= x <= W, 0 <= y <= H: length (W, H) in m, k, h, the bottom edge's
    prescribed_temperature T_b and the ambient_temperature T_a in K."""
    length: tuple
    thermal_conductivity: float
    heat_transfer_coefficient: float
    prescribed_temperature: float
    ambient_temperature: float

    def __post_init__(self):
        refuse_text(length=self.length, thermal_conductivity=self.thermal_conductivity,
                    heat_transfer_coefficient=self.heat_transfer_coefficient,
                    prescribed_temperature=self.prescribed_temperature, ambient_temperature=self.ambient_temperature)

    def biot(self):
        return self.heat_transfer_coefficient*self.length[0]/self.thermal_conductivity


@dataclass(frozen=True, kw_only=True)
class PublishedTarget:
    """A published benchmark temperature in SI with its provenance: the position (m), the
    temperature (K) and the quoted precision as a temperature_tolerance (K)."""
    position: tuple
    temperature: float
    temperature_tolerance: float
    source: str


def _kelvin(celsius):
    """The decimal rule: the double nearest the exact decimal value + 273.15."""
    return float(Fraction(repr(float(celsius))) + _CELSIUS_ZERO)


def nafems_t4():
    """NAFEMS T4's rectangle in SI, computed from the published literals at run time."""
    record = _published.NAFEMS_T4
    assert record.unit == "degC"
    return ConvectionRectangle(length=(record.width, record.height), thermal_conductivity=record.conductivity,
                               heat_transfer_coefficient=record.convection,
                               prescribed_temperature=_kelvin(record.bottom_temperature),
                               ambient_temperature=_kelvin(record.ambient))


def nafems_t4_target():
    """NAFEMS T4's published target in SI (291.45 K at (0.6, 0.2) m, quoted to 0.1 K)."""
    record = _published.NAFEMS_T4_TARGET
    assert record.unit == "degC"
    return PublishedTarget(position=record.point, temperature=_kelvin(record.value),
                           temperature_tolerance=record.quoted_precision, source=record.source)


def _check(problem):
    if not isinstance(problem, ConvectionRectangle):
        raise ValueError("problem must be a ConvectionRectangle")
    width, height = pair(problem.length, "length")
    for name, v in (("length[0]", width), ("length[1]", height),
                    ("thermal_conductivity", problem.thermal_conductivity),
                    ("heat_transfer_coefficient", problem.heat_transfer_coefficient),
                    ("prescribed_temperature", problem.prescribed_temperature),
                    ("ambient_temperature", problem.ambient_temperature)):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not np.isfinite(v):
            raise ValueError(f"{name} must be a finite real number")
    if min(width, height, problem.thermal_conductivity) <= 0 or problem.heat_transfer_coefficient <= 0:
        raise ValueError("length, thermal_conductivity and heat_transfer_coefficient must be positive")
    return width, height


def eigenvalues(problem, terms):
    """The first `terms` roots lam_n of lam tan(lam W) = h/k, increasing."""
    W, _ = _check(problem)
    if not isinstance(terms, (int, np.integer)) or isinstance(terms, bool) or terms < 1:
        raise ValueError("terms must be a positive integer")
    bi = problem.heat_transfer_coefficient/problem.thermal_conductivity
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
    W, H = _check(problem)
    p = _points(points)
    k, h = problem.thermal_conductivity, problem.heat_transfer_coefficient
    if np.any(p[:, 0] < -1e-9*W) or np.any(p[:, 0] > W*(1+1e-9)) or np.any(p[:, 1] < -1e-9*H) or np.any(p[:, 1] > H*(1+1e-9)):
        raise ValueError("points must lie inside the rectangle")
    lam = eigenvalues(problem, terms)
    norm = W/2+np.sin(2*lam*W)/(4*lam)
    A = (problem.prescribed_temperature-problem.ambient_temperature)*np.sin(lam*W)/(lam*norm)
    d0 = lam*k*(1+np.exp(-2*lam*H))+h*(1-np.exp(-2*lam*H))      # Y_n(0) e^{-lam H}
    T = np.empty(len(p)); q = np.empty((len(p), 2))
    for s in range(0, len(p), chunk):
        x, y = p[s:s+chunk].T
        ex = np.exp(-lam[None, :]*y[:, None])
        e2 = np.exp(-2*lam[None, :]*(H-y)[:, None])
        R = ex*(lam*k*(1+e2)+h*(1-e2))/d0                      # Y_n(y)/Y_n(0)
        dR = -lam*ex*(lam*k*(1-e2)+h*(1+e2))/d0                 # Y_n'(y)/Y_n(0)
        cos, sin = np.cos(lam[None, :]*x[:, None]), np.sin(lam[None, :]*x[:, None])
        T[s:s+chunk] = problem.ambient_temperature+np.sum(A*cos*R, axis=1)
        q[s:s+chunk, 0] = k*np.sum(A*lam*sin*R, axis=1)
        q[s:s+chunk, 1] = -k*np.sum(A*cos*dR, axis=1)
    return ConvectionFields(T, q, int(terms))
