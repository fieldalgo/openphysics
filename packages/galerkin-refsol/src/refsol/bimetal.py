# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Thermal bending of a bonded two-layer strip (bimetal thermostat); no engine imports.

Geometry: layer 1 on 0 <= x <= t1, layer 2 on t1 <= x <= t1+t2 = h, perfectly
bonded; strip axis along y, 0 <= y <= L; uniform temperature change dT from the
stress-free state. Plane stress in (x, y): the strip is a beam, so only
sigma_yy(x) is nonzero.

Beam model (S. Timoshenko, "Analysis of Bi-Metal Thermostats", J. Opt. Soc.
Am. 11, 233-255 (1925), doi:10.1364/JOSA.11.000233): the axial strain is
eps_yy = a + b x across both layers, sigma_yy = E_i (a + b x - alpha_i dT), and
a, b follow from zero axial force and zero bending moment on every cross
section. b is the curvature of the strip.

That field is an EXACT plane-stress solution of the two-dimensional problem
whose end faces y = 0 and y = L carry the traction sigma_yy(x) n_y
(self-equilibrated: zero resultant force and moment). For traction-free ends it
is the Saint-Venant solution: the difference decays exponentially with the
distance from the ends measured in thicknesses h.

Closed forms cross-checked in the tests (they are the same number):
  the thickness/modulus-ratio form usually quoted from Timoshenko (1925),
    kappa = 6 (alpha2-alpha1) dT (1+m)^2 / (h [3 (1+m)^2 + (1+m n)(m^2 + 1/(m n))]),
    m = t1/t2, n = E1/E2, h = t1+t2;
  the form printed in the Wikipedia article "Bimetallic strip" (Villarceau 1863),
    kappa = 3 (alpha2-alpha1) dT / (2 a h),
    a = 1 + (E1 t1^2 - E2 t2^2)^2 / (4 E1 t1 E2 t2 h^2);
  the thin-film limit t1 -> 0 is the uniaxial (beam) form of Stoney's relation
    kappa = 6 sigma_f t_f / (E_s t_s^2), sigma_f = E1 (alpha2-alpha1) dT
    (G. G. Stoney, Proc. R. Soc. Lond. A 82, 172-175 (1909),
    doi:10.1098/rspa.1909.0021). The equibiaxial plate form with (1-nu_s) is a
    plate result and is not represented by a plane model.

SI units: m, Pa, 1/K, K. Stress order (sxx, syy, sxy). kappa > 0 bends the
strip towards -x, i.e. towards the layer with the smaller expansion when
alpha2 > alpha1.

Keyword-only registry names (after the leading positional ``points`` and ``normals``
where a function takes them): ``thickness``, ``youngs_modulus`` and
``linear_expansion_coefficient`` hold one value per layer, in stacking order from x = 0
(a pair for the two-layer closed forms); ``temperature_change`` is dT. A str for a
quantity raises TypeError.
"""
from dataclasses import dataclass
import numpy as np

from ._checks import pair, refuse_text

__all__ = ["BimetalCurvature", "curvature", "timoshenko_curvature", "villarceau_curvature",
           "stoney_uniaxial_curvature", "StripFields", "strip_fields", "end_traction"]


@dataclass(frozen=True)
class BimetalCurvature:
    strain_yy: float             # a: the axial strain eps_yy at x = 0
    curvature: float             # b = kappa, 1/m
    position: float              # x of the neutral axis, where eps_yy = 0 (may lie outside the strip), m
    thickness: tuple
    youngs_modulus: tuple
    linear_expansion_coefficient: tuple
    temperature_change: float

    def strain_yy_at(self, points):
        """The axial strain eps_yy = a + b x at (Q, 2) points (x, y)."""
        p = np.asarray(points, dtype=float)
        if p.ndim != 2 or p.shape[1] != 2:
            raise ValueError("points must have shape (Q, 2)")
        return self.strain_yy+self.curvature*p[:, 0]


def _pairs(thickness, youngs_modulus, linear_expansion_coefficient):
    refuse_text(thickness=thickness, youngs_modulus=youngs_modulus,
                linear_expansion_coefficient=linear_expansion_coefficient)
    t, e, al = (np.asarray(v, dtype=float) for v in (thickness, youngs_modulus, linear_expansion_coefficient))
    if t.shape != e.shape or t.shape != al.shape or t.ndim != 1 or len(t) < 2:
        raise ValueError("thickness, youngs_modulus and linear_expansion_coefficient need one value per layer, "
                         "at least two layers")
    if not (np.all(np.isfinite(t)) and np.all(np.isfinite(e)) and np.all(np.isfinite(al))):
        raise ValueError("layer data must be finite")
    if np.any(t <= 0) or np.any(e <= 0):
        raise ValueError("thickness and youngs_modulus must be positive")
    return t, e, al


def _scalar(value, name):
    refuse_text(**{name: value})
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or not np.isfinite(a):
        raise ValueError(f"{name} must be a finite real scalar")
    return float(a)


def curvature(*, thickness, youngs_modulus, linear_expansion_coefficient, temperature_change):
    """Force and moment balance of the layered beam: eps_yy = a + b x.

    Works for any number of bonded layers stacked along x (one value per layer of
    thickness, youngs_modulus and linear_expansion_coefficient); the two-layer case
    is Timoshenko's thermostat.
    """
    t, e, al = _pairs(thickness, youngs_modulus, linear_expansion_coefficient)
    dt = _scalar(temperature_change, "temperature_change")
    x1 = np.concatenate([[0.], np.cumsum(t)])
    x0, x1 = x1[:-1], x1[1:]
    s0 = np.sum(e*(x1-x0))
    s1 = np.sum(e*(x1**2-x0**2)/2)
    s2 = np.sum(e*(x1**3-x0**3)/3)
    p0 = np.sum(e*al*dt*(x1-x0))
    p1 = np.sum(e*al*dt*(x1**2-x0**2)/2)
    a, b = np.linalg.solve([[s0, s1], [s1, s2]], [p0, p1])
    neutral = -a/b if b != 0 else np.inf
    return BimetalCurvature(float(a), float(b), float(neutral), tuple(t), tuple(e), tuple(al), dt)


def _two_layers(thickness, youngs_modulus, linear_expansion_coefficient, temperature_change):
    """(t1, t2, e1, e2, alpha1, alpha2, dT) of the two-layer closed forms, from pairs."""
    refuse_text(thickness=thickness, youngs_modulus=youngs_modulus,
                linear_expansion_coefficient=linear_expansion_coefficient)
    t1, t2 = (_scalar(v, f"thickness[{i}]") for i, v in enumerate(pair(thickness, "thickness")))
    e1, e2 = (_scalar(v, f"youngs_modulus[{i}]") for i, v in enumerate(pair(youngs_modulus, "youngs_modulus")))
    if min(t1, t2, e1, e2) <= 0:
        raise ValueError("thickness and youngs_modulus must be positive")
    a1, a2 = (_scalar(v, f"linear_expansion_coefficient[{i}]")
              for i, v in enumerate(pair(linear_expansion_coefficient, "linear_expansion_coefficient")))
    return t1, t2, e1, e2, a1, a2, _scalar(temperature_change, "temperature_change")


def timoshenko_curvature(*, thickness, youngs_modulus, linear_expansion_coefficient, temperature_change):
    """Thickness-ratio / modulus-ratio closed form, m = t1/t2, n = E1/E2.

    thickness, youngs_modulus and linear_expansion_coefficient are the pairs
    (layer 1, layer 2).
    """
    t1, t2, e1, e2, a1, a2, dt = _two_layers(thickness, youngs_modulus, linear_expansion_coefficient,
                                             temperature_change)
    m, n, h = t1/t2, e1/e2, t1+t2
    return 6*(a2-a1)*dt*(1+m)**2/(h*(3*(1+m)**2+(1+m*n)*(m*m+1/(m*n))))


def villarceau_curvature(*, thickness, youngs_modulus, linear_expansion_coefficient, temperature_change):
    """Form printed in the Wikipedia article "Bimetallic strip" (Villarceau 1863).

    thickness, youngs_modulus and linear_expansion_coefficient are the pairs
    (layer 1, layer 2).
    """
    t1, t2, e1, e2, a1, a2, dt = _two_layers(thickness, youngs_modulus, linear_expansion_coefficient,
                                             temperature_change)
    h = t1+t2
    a = 1+(e1*t1*t1-e2*t2*t2)**2/(4*e1*t1*e2*t2*h*h)
    return 3*(a2-a1)*dt/(2*a*h)


def stoney_uniaxial_curvature(*, thickness, youngs_modulus, stress):
    """Uniaxial (beam) Stoney relation kappa = 6 sigma_f t_f / (E_s t_s^2).

    thickness is the pair (t_f, t_s) of the film and the substrate, youngs_modulus the
    substrate's E_s and stress the film's axial stress sigma_f.
    """
    refuse_text(thickness=thickness)
    tf, ts = (_scalar(v, f"thickness[{i}]") for i, v in enumerate(pair(thickness, "thickness")))
    es, sf = _scalar(youngs_modulus, "youngs_modulus"), _scalar(stress, "stress")
    if min(tf, ts, es) <= 0:
        raise ValueError("thickness and youngs_modulus must be positive")
    return 6*sf*tf/(es*ts*ts)


@dataclass
class StripFields:
    displacement: np.ndarray     # (Q,2) m
    stress: np.ndarray           # (Q,3) Pa, (sxx, syy, sxy); only syy is nonzero
    strain_yy: np.ndarray        # (Q,) the axial strain eps_yy
    layer: np.ndarray            # (Q,) layer index
    curvature: float             # 1/m


def _points(points):
    p = np.asarray(points)
    if p.ndim != 2 or p.shape[1] != 2 or p.dtype.kind not in "iuf" or not np.all(np.isfinite(p)):
        raise ValueError("points must be finite real (Q,2) metre coordinates")
    return p.astype(float)


def _locate(x, edges, layer):
    if layer is not None:
        i = np.asarray(layer)
        if i.shape != x.shape or i.dtype.kind not in "iu" or np.any(i < 0) or np.any(i >= len(edges)-1):
            raise ValueError("layer must give one valid layer index per point")
        return i.astype(int)
    span = edges[-1]
    if np.any(x < -1e-9*span) or np.any(x > span*(1+1e-9)):
        raise ValueError("points lie outside the strip thickness")
    return np.clip(np.searchsorted(edges, x, side="right")-1, 0, len(edges)-2)


def strip_fields(points, *, thickness, youngs_modulus, poisson_ratio, linear_expansion_coefficient,
                 temperature_change, length, layer=None):
    """Exact plane-stress fields of the uniformly curved strip at points (x, y).

    Rigid-body motion is fixed by u(0, 0) = 0 and u_x(0, length) = 0, so the
    chord of the x = 0 face stays on the y axis. `layer` may give the layer
    index of each point (for points on an interface). thickness, youngs_modulus,
    poisson_ratio and linear_expansion_coefficient hold one value per layer.
    """
    refuse_text(poisson_ratio=poisson_ratio)
    p = _points(points)
    t, e, al = _pairs(thickness, youngs_modulus, linear_expansion_coefficient)
    nu = np.asarray(poisson_ratio, dtype=float)
    if nu.shape != t.shape or not np.all(np.isfinite(nu)) or np.any(nu <= -1) or np.any(nu >= .5):
        raise ValueError("poisson_ratio needs one value per layer in (-1, 0.5)")
    L = _scalar(length, "length")
    if L <= 0:
        raise ValueError("length must be positive")
    c = curvature(thickness=t, youngs_modulus=e, linear_expansion_coefficient=al,
                  temperature_change=temperature_change)
    a, b, dt = c.strain_yy, c.curvature, c.temperature_change
    edges = np.concatenate([[0.], np.cumsum(t)])
    # u_x = -b y^2/2 + theta y + U_i(x), U_i' = eps_xx = -nu_i (a + b x - alpha_i dT) + alpha_i dT,
    # U continuous at the interfaces with U(0) = 0; theta = b L/2 makes u_x(0, L) = 0.
    def U(i, x):
        return -nu[i]*(a*x+b*x*x/2-al[i]*dt*x)+al[i]*dt*x
    shift = np.zeros(len(t))
    for i in range(1, len(t)):
        shift[i] = shift[i-1]+U(i-1, edges[i])-U(i, edges[i])
    x, y = p.T
    i = _locate(x, edges, layer)
    theta = b*L/2
    ux = -b*y*y/2+theta*y+U(i, x)+shift[i]
    uy = (a+b*x)*y-theta*x
    strain = a+b*x
    syy = e[i]*(strain-al[i]*dt)
    stress = np.column_stack([np.zeros(len(p)), syy, np.zeros(len(p))])
    return StripFields(np.column_stack([ux, uy]), stress, strain, i, b)


def end_traction(points, normals, *, thickness, youngs_modulus, poisson_ratio, linear_expansion_coefficient,
                 temperature_change, length):
    """Total traction sigma . n of the exact field: (0, sigma_yy n_y) in Pa (the strip of strip_fields)."""
    n = _points(normals)
    f = strip_fields(points, thickness=thickness, youngs_modulus=youngs_modulus, poisson_ratio=poisson_ratio,
                     linear_expansion_coefficient=linear_expansion_coefficient,
                     temperature_change=temperature_change, length=length)
    return np.column_stack([np.zeros(len(n)), f.stress[:, 1]*n[:, 1]])
