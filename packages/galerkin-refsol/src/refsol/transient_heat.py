# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""NumPy-only transient heat reference fields and small dense P1 algebra.

Independent of engine, existing references and production assembly. SI metres,
seconds, Kelvin, keyword-only registry names after the leading positional ``points``
(or ``nodes``); a str for a quantity raises TypeError. Dense matrix/mode helpers are
for small reference meshes.
"""
from dataclasses import dataclass
import numpy as np

from ._checks import refuse_text

__all__ = ["TransientHeatFields", "uniform_insulated", "moving_affine", "sine_manufactured",
           "p1_matrices", "smallest_dirichlet_mode", "backward_euler_amplitude"]


def _real(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be finite real")
    out = np.asarray(a, dtype=float)
    if not np.all(np.isfinite(out)):
        raise ValueError(f"{name} exceeds finite floating-point range")
    return out


def _scalar(value, name, positive=False):
    a = _real(value, name)
    if a.shape != () or (positive and a <= 0):
        raise ValueError(f"{name} must be a finite {'positive ' if positive else ''}scalar")
    return float(a)


def _points(points):
    p = _real(points, "points")
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError("points must have shape (Q,2)")
    return p


@dataclass
class TransientHeatFields:
    temperature: np.ndarray
    heat_flux: np.ndarray
    heat_source_density: np.ndarray
    temperature_gradient: np.ndarray


def uniform_insulated(points, *, time, volumetric_heat_capacity, heat_source_density, initial_temperature,
                      initial_time):
    """Continuous and BE-exact constant-source insulated uniform field (T0 at initial_time)."""
    refuse_text(time=time, volumetric_heat_capacity=volumetric_heat_capacity,
                heat_source_density=heat_source_density, initial_temperature=initial_temperature,
                initial_time=initial_time)
    p = _points(points)
    c = _scalar(volumetric_heat_capacity, "volumetric_heat_capacity", True)
    q = _scalar(heat_source_density, "heat_source_density")
    initial = _scalar(initial_temperature, "initial_temperature")
    dt = _scalar(time, "time")-_scalar(initial_time, "initial_time")
    temp = np.full(len(p), initial+q*dt/c)
    return TransientHeatFields(temp, np.zeros_like(p), np.full(len(p),q), np.zeros_like(p))


def moving_affine(points, *, time, thermal_conductivity, volumetric_heat_capacity, initial_time):
    """T=290+5*x+3*(t-t0), Q=3*c, flux=(-5*k,0), all SI; t0 is initial_time."""
    refuse_text(time=time, thermal_conductivity=thermal_conductivity,
                volumetric_heat_capacity=volumetric_heat_capacity, initial_time=initial_time)
    p = _points(points)
    k = _scalar(thermal_conductivity, "thermal_conductivity", True)
    c = _scalar(volumetric_heat_capacity, "volumetric_heat_capacity", True)
    dt = _scalar(time, "time")-_scalar(initial_time, "initial_time")
    grad = np.tile([5.,0.], (len(p),1))
    return TransientHeatFields(290+5*p[:,0]+3*dt, -k*grad, np.full(len(p),3*c), grad)


def sine_manufactured(points, *, time, thermal_conductivity, volumetric_heat_capacity):
    """Unit-square PDE MMS, 300K baseline, 1K amplitude, gamma=.7/s.

    T=300+(1+.7*t)*sin(pi*x)*sin(pi*y). This is a PDE field, not the
    generalized discrete eigenmode, and does not imply zero FE time error.
    """
    refuse_text(time=time, thermal_conductivity=thermal_conductivity,
                volumetric_heat_capacity=volumetric_heat_capacity)
    p = _points(points)
    now = _scalar(time, "time")
    k = _scalar(thermal_conductivity, "thermal_conductivity", True)
    c = _scalar(volumetric_heat_capacity, "volumetric_heat_capacity", True)
    x,y = p.T
    phi = np.sin(np.pi*x)*np.sin(np.pi*y)
    grad_phi = np.pi*np.column_stack([np.cos(np.pi*x)*np.sin(np.pi*y),
                                     np.sin(np.pi*x)*np.cos(np.pi*y)])
    gradient = (1+.7*now)*grad_phi
    return TransientHeatFields(300+(1+.7*now)*phi, -k*gradient,
        (c*.7+2*k*np.pi**2*(1+.7*now))*phi, gradient)


def p1_matrices(nodes, triangles, *, thermal_conductivity, volumetric_heat_capacity):
    """Small dense independent triangle integrals, no geometry repair.

    The caller supplies a conforming used-node CCW mesh (nodes in m); this reference
    performs local shape/index/positive-area checks, not full mesh intersection validation.
    """
    refuse_text(thermal_conductivity=thermal_conductivity, volumetric_heat_capacity=volumetric_heat_capacity)
    p = _points(nodes)
    t = np.asarray(triangles)
    if (t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in "iu"
            or np.any(t < 0) or np.any(t >= len(p))):
        raise ValueError("triangles must be nonempty valid integer (M,3)")
    k = _scalar(thermal_conductivity, "thermal_conductivity", True)
    c = _scalar(volumetric_heat_capacity, "volumetric_heat_capacity", True)
    mass = np.zeros((len(p),len(p)))
    stiffness = np.zeros_like(mass)
    for ids in t:
        a,b,d = p[ids]
        jac = np.column_stack([b-a,d-a])
        det = np.linalg.det(jac)
        if not np.isfinite(det) or det <= 0:
            raise ValueError("triangles must have finite positive area")
        area = det/2
        gradients = np.array([[-1.,-1.],[1.,0.],[0.,1.]])@np.linalg.inv(jac)
        local_m = c*area/12*(np.ones((3,3))+np.eye(3))
        local_k = k*area*(gradients@gradients.T)
        mass[np.ix_(ids,ids)] += local_m
        stiffness[np.ix_(ids,ids)] += local_k
    if not np.all(np.isfinite(mass)) or not np.all(np.isfinite(stiffness)):
        raise ValueError("reference matrix overflow")
    return mass,stiffness


def smallest_dirichlet_mode(mass, stiffness, fixed_node_ids):
    """Smallest mode of a positive-definite Dirichlet K_FF/M_FF pencil.

    Return (lambda, phi), phi_C=0 and max(abs(phi))=1. This helper requires
    positive reduced stiffness; it does not select an insulated zero mode.
    """
    m = _real(mass,"mass"); k = _real(stiffness,"stiffness")
    fixed = np.asarray(fixed_node_ids)
    if (m.ndim != 2 or m.shape[0] != m.shape[1] or k.shape != m.shape
            or fixed.ndim != 1 or fixed.dtype.kind not in "iu"
            or np.any(fixed < 0) or np.any(fixed >= len(m))):
        raise ValueError("square M/K and valid integer fixed nodes required")
    free = np.setdiff1d(np.arange(len(m)),fixed)
    if not len(free):
        raise ValueError("mode requires free nodes")
    mm,kk = m[np.ix_(free,free)],k[np.ix_(free,free)]
    lower = np.linalg.cholesky(mm)
    left = np.linalg.solve(lower,kk)
    reduced = np.linalg.solve(lower,left.T).T
    values,vectors = np.linalg.eigh((reduced+reduced.T)/2)
    if values[0] <= 0:
        raise ValueError("mode requires positive Dirichlet reduced stiffness")
    vector = np.linalg.solve(lower.T,vectors[:,0])
    vector /= vector[np.argmax(abs(vector))]
    phi = np.zeros(len(m)); phi[free] = vector
    return float(values[0]),phi


def backward_euler_amplitude(*, decay_rate, time):
    """Exact scalar semidiscrete BE product prod 1/(1 + lambda dt), not a continuous PDE solution.

    decay_rate is lambda in 1/s (for example from smallest_dirichlet_mode), time the
    nonnegative increasing step ends in s.
    """
    refuse_text(decay_rate=decay_rate, time=time)
    value = _scalar(decay_rate,"decay_rate",True)
    times = _real(time,"time")
    if times.ndim != 1 or len(times) < 2 or np.any(times < 0):
        raise ValueError("time must be a nonnegative 1D sequence")
    step = np.diff(times)
    if not np.all(np.isfinite(step)) or np.any(step <= 0):
        raise ValueError("time must be strictly increasing with finite dt")
    return np.r_[1.,np.cumprod(1/(1+value*step))]
