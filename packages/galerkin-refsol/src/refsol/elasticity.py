# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent analytic 2D isotropic elasticity fields; no FEM imports.

Coordinates/displacement are m, stress/E are Pa, force density is N/m^3.
Strain ordering is (exx, eyy, gamma_xy), with engineering shear gamma_xy=2*exy.
"""
from dataclasses import dataclass
import numpy as np


def _parameters(young_modulus, poisson_ratio, plane):
    e, nu = np.asarray(young_modulus), np.asarray(poisson_ratio)
    if (e.shape != () or nu.shape != () or e.dtype.kind not in "iuf"
            or nu.dtype.kind not in "iuf" or not np.isfinite(e) or not np.isfinite(nu)
            or e <= 0 or not -1 < nu < .5):
        raise ValueError("require finite scalar E > 0 and -1 < nu < 0.5")
    if plane not in ("stress", "strain"):
        raise ValueError("plane must be 'stress' or 'strain'")
    return float(e), float(nu)


def _points(points):
    a = np.asarray(points)
    if a.ndim != 2 or a.shape[1] != 2 or a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError("points must be finite real (Q, 2)")
    return a.astype(float)


def stress_from_strain(strain, *, young_modulus, poisson_ratio, plane):
    """Closed-form in-plane stress, independent of the engine material routine."""
    e, nu = _parameters(young_modulus, poisson_ratio, plane)
    s = np.asarray(strain)
    if s.ndim < 1 or s.shape[-1] != 3 or s.dtype.kind not in "iuf" or not np.all(np.isfinite(s)):
        raise ValueError("strain must be finite real (..., 3)")
    ex, ey, g = np.moveaxis(s, -1, 0)
    if plane == "stress":
        sx, sy = e/(1-nu**2)*(ex+nu*ey), e/(1-nu**2)*(ey+nu*ex)
    else:
        c = e/((1+nu)*(1-2*nu))
        sx, sy = c*((1-nu)*ex+nu*ey), c*((1-nu)*ey+nu*ex)
    return np.stack([sx, sy, e/(2*(1+nu))*g], axis=-1)


@dataclass
class ElasticityFields:
    displacement: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    body_force: np.ndarray


def affine(points, gradient, offset=(0., 0.), *, young_modulus, poisson_ratio, plane):
    """u_i = gradient[i,j]*x_j + offset_i; constant strain/stress, zero force."""
    p = _points(points)
    g, c = np.asarray(gradient), np.asarray(offset)
    if (g.shape != (2, 2) or c.shape != (2,) or g.dtype.kind not in "iuf"
            or c.dtype.kind not in "iuf" or not np.all(np.isfinite(g)) or not np.all(np.isfinite(c))):
        raise ValueError("gradient/offset must be finite real (2,2)/(2,) arrays")
    strain = np.broadcast_to([g[0, 0], g[1, 1], g[0, 1]+g[1, 0]], (len(p), 3)).copy()
    stress = stress_from_strain(strain, young_modulus=young_modulus,
                               poisson_ratio=poisson_ratio, plane=plane)
    return ElasticityFields(p @ g.T+c, strain, stress, np.zeros_like(p))


def sine_manufactured(points, *, young_modulus, poisson_ratio, plane):
    """Unit-square smooth solution u=1e-3*sin(pi*x)*sin(pi*y)*(1,0.6).

    Force follows the Navier equation -mu*Laplacian(u)-(lambda+mu)*grad(div u).
    Boundary displacement vanishes; boundary traction generally does NOT vanish.
    Thus prescribe BOTH components on the whole boundary for this benchmark.
    """
    e, nu = _parameters(young_modulus, poisson_ratio, plane)
    p = _points(points)
    x, y = np.pi*p[:, 0], np.pi*p[:, 1]
    sx, sy, cx, cy = np.sin(x), np.sin(y), np.cos(x), np.cos(y)
    a, b = 1e-3, .6e-3
    u = np.column_stack([a*sx*sy, b*sx*sy])
    strain = np.pi*np.column_stack([a*cx*sy, b*sx*cy, a*sx*cy+b*cx*sy])
    mu = e/(2*(1+nu))
    lam = (e*nu/((1+nu)*(1-2*nu)) if plane == "strain" else e*nu/(1-nu**2))
    force = np.pi**2*np.column_stack([(lam+3*mu)*a*sx*sy-(lam+mu)*b*cx*cy,
                                     (lam+3*mu)*b*sx*sy-(lam+mu)*a*cx*cy])
    stress = stress_from_strain(strain, young_modulus=e, poisson_ratio=nu, plane=plane)
    return ElasticityFields(u, strain, stress, force)
