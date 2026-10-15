# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytic Cartesian-traction fields, independent of FEM code and its solver.

Coordinates/displacement: m; stress/traction/E: Pa; body force: N/m^3.
Strain uses (exx, eyy, gamma_xy), gamma_xy=2*exy.
"""
from dataclasses import dataclass
import numpy as np


def _real(value, shape, name):
    a = np.asarray(value)
    if a.shape != shape or a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be finite real with shape {shape}")
    return a.astype(float)


def _material(young_modulus, poisson_ratio, plane):
    e = float(_real(young_modulus, (), "E"))
    nu = float(_real(poisson_ratio, (), "nu"))
    if e <= 0 or not -1 < nu < .5 or plane not in ("stress", "strain"):
        raise ValueError("require E>0, -1<nu<0.5, and plane='stress' or 'strain'")
    mu = e/(2*(1+nu))
    lam = e*nu/(1-nu*nu) if plane == "stress" else e*nu/((1+nu)*(1-2*nu))
    return e, nu, mu, lam


def _points(points):
    p = np.asarray(points)
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError("points must have shape (Q, 2)")
    return _real(p, p.shape, "points")


@dataclass
class TractionFields:
    displacement: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    body_force: np.ndarray


def traction_from_stress(stress, normals):
    """Evaluate t=sigma*n for (Q,3) stresses and outward unit (Q,2) normals."""
    n = _points(normals)
    sigma = _real(stress, (len(n), 3), "stress")
    if not np.allclose(np.linalg.norm(n, axis=1), 1., rtol=0, atol=1e-10):
        raise ValueError("normals must have unit length")
    return np.column_stack([sigma[:, 0]*n[:, 0]+sigma[:, 2]*n[:, 1],
                            sigma[:, 2]*n[:, 0]+sigma[:, 1]*n[:, 1]])


def uniaxial(points, axial_stress, *, young_modulus, poisson_ratio, plane):
    """Uniform sigma_xx=P, sigma_yy=sigma_xy=0; left-x/bottom-y supports."""
    p = _points(points)
    e, nu, _, _ = _material(young_modulus, poisson_ratio, plane)
    applied = float(_real(axial_stress, (), "axial_stress"))
    ex, ey = ((applied/e, -nu*applied/e) if plane == "stress" else
              ((1-nu*nu)*applied/e, -nu*(1+nu)*applied/e))
    return TractionFields(p*[ex, ey], np.tile([ex, ey, 0.], (len(p), 1)),
                           np.tile([applied, 0., 0.], (len(p), 1)), np.zeros_like(p))


def shear(points, shear_stress, *, young_modulus, poisson_ratio, plane):
    """Uniform sigma_xy=tau, u=(tau/mu*y,0), fixed bottom displacement."""
    p = _points(points)
    _, _, mu, _ = _material(young_modulus, poisson_ratio, plane)
    tau = float(_real(shear_stress, (), "shear_stress"))
    gamma = tau/mu
    return TractionFields(np.column_stack([gamma*p[:, 1], np.zeros(len(p))]),
                           np.tile([0., 0., gamma], (len(p), 1)),
                           np.tile([0., 0., tau], (len(p), 1)), np.zeros_like(p))


def polynomial_manufactured(points, *, young_modulus, poisson_ratio, plane):
    """Cubic mixed-boundary MMS on the unit square, A=1e-3 m.

    u=A*(x^2+x*y+x*y^2, .6*x^2*y+.2*x*y^2+.3*x^3).
    At x=0 both displacements vanish; other walls carry analytic sigma*n.
    Force is differentiated explicitly from the Navier equation, not FEM.
    """
    p = _points(points)
    _, _, mu, lam = _material(young_modulus, poisson_ratio, plane)
    length, amplitude = 1., 1e-3  # fixed reference length (m), displacement (m)
    x, y, a = p[:, 0]/length, p[:, 1]/length, amplitude/length
    u = amplitude*np.column_stack([x*x+x*y+x*y*y, .6*x*x*y+.2*x*y*y+.3*x*x*x])
    ex, ey = a*(2*x+y+y*y), a*(.6*x*x+.4*x*y)
    gamma = a*(x+3.2*x*y+.2*y*y+.9*x*x)
    strain = np.column_stack([ex, ey, gamma])
    sigma = np.column_stack([(lam+2*mu)*ex+lam*ey,
                              lam*ex+(lam+2*mu)*ey, mu*gamma])
    force = -amplitude/length**2*np.column_stack([2*(lam+2*mu)+2*mu*x+(lam+mu)*(1.2*x+.4*y),
                                mu*(1.2*y+1.8*x)+.4*x*(lam+2*mu)+(lam+mu)*(1+2*y)])
    return TractionFields(u, strain, sigma, force)


def polynomial_traction(points, normals, *, young_modulus, poisson_ratio, plane):
    """Analytic nonuniform boundary traction in global Cartesian coordinates."""
    fields = polynomial_manufactured(points, young_modulus=young_modulus,
                                      poisson_ratio=poisson_ratio, plane=plane)
    return traction_from_stress(fields.stress, normals)


def polynomial_resultants(*, young_modulus, poisson_ratio, plane):
    """Applied force and origin moment per thickness, excluding the left wall.

    For the unit-square MMS, the resultant of body plus other three walls
    is minus the left-wall analytic traction integral. Units N/m and N.
    """
    _, _, mu, lam = _material(young_modulus, poisson_ratio, plane)
    length, amplitude = 1., 1e-3  # metres
    return (np.array([5*amplitude*(lam+2*mu)/6, amplitude*mu/15]),
            -7*amplitude*length*(lam+2*mu)/12)
