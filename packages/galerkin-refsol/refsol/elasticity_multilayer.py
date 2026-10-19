# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact small-strain states of layered isotropic solids; no engine imports.

Plane stress or plane strain (eps_zz = 0), SI units: m, Pa, 1/K, K.
Perfect bonding: displacement and traction continuous at every interface.

laminate_axial       layers stacked in y, uniform axial strain eps0 along x,
                     free top/bottom faces. u_x = eps0 x, sigma_yy = 0,
                     u_y = -eps0 * integral of c(y), c = nu (stress) or
                     nu/(1-nu) (strain). sigma_xx = E' eps0 (Voigt laminate).
series_bar           layers in series along x under uniform sigma_xx = s.
                     Exact only when every layer has the same lateral strain;
                     other data are rejected, because the true solution then
                     has interface singularities.
composite_cylinder   concentric shells under inner/outer pressure and an
                     optional per-layer temperature change
                     dT_i(r) = a_i + b_i ln(r/r_0) (uniform mismatch: b_i = 0;
                     steady conduction without source gives exactly this form).
                     In each shell u_r = kappa I(r)/r + A r + B/r with
                     I = integral of s dT ds and kappa = beta/(lambda+2 mu);
                     A_i, B_i follow from the 2n boundary/interface equations.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class LayeredElasticFields:
    displacement: np.ndarray        # (Q,2) m
    stress: np.ndarray              # (Q,3) Pa, [sxx, syy, sxy]
    layer: np.ndarray               # (Q,) layer index
    out_of_plane_stress: np.ndarray  # (Q,) Pa; zero in plane stress


@dataclass
class CylinderFields(LayeredElasticFields):
    radial_displacement: np.ndarray
    radial_stress: np.ndarray
    hoop_stress: np.ndarray
    coefficients: np.ndarray        # (n,2) A_i (1), B_i (m^2)


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


def _per_layer(values, n, name, default=None):
    if values is None and default is not None:
        return np.full(n, float(default))
    a = np.asarray(values)
    if a.shape != (n,) or a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must give one finite real value per layer")
    return a.astype(float)


def _layers(start, interfaces, young, poisson, plane):
    edges = np.asarray(interfaces)
    if (edges.ndim != 1 or not len(edges) or edges.dtype.kind not in "iuf"
            or not np.all(np.isfinite(edges))):
        raise ValueError("interfaces must be a nonempty finite 1D sequence")
    edges = np.concatenate([[start], edges.astype(float)])
    if np.any(np.diff(edges) <= 0):
        raise ValueError("interfaces must increase strictly from the first face")
    n = len(edges)-1
    e = _per_layer(young, n, "young_moduli")
    nu = _per_layer(poisson, n, "poisson_ratios")
    if np.any(e <= 0) or np.any(nu <= -1) or np.any(nu >= .5):
        raise ValueError("each layer needs E > 0 and -1 < nu < 0.5")
    if plane not in ("stress", "strain"):
        raise ValueError("plane must be 'stress' or 'strain'")
    mu = e/(2*(1+nu))
    lam = e*nu/((1+nu)*(1-2*nu)) if plane == "strain" else e*nu/(1-nu*nu)
    return edges, e, nu, lam, mu


def _locate(s, edges, label, layer):
    if layer is not None:
        i = np.asarray(layer)
        if i.shape != s.shape or i.dtype.kind not in "iu" or np.any(i < 0) or np.any(i >= len(edges)-1):
            raise ValueError("layer must give one valid layer index per point")
        return i.astype(int)
    span = edges[-1]-edges[0]
    if np.any(s < edges[0]-1e-9*span) or np.any(s > edges[-1]+1e-9*span):
        raise ValueError(f"points lie outside the layered {label}")
    return np.clip(np.searchsorted(edges, s, side="right")-1, 0, len(edges)-2)


def laminate_axial(points, *, y_interfaces, young_moduli, poisson_ratios,
                   axial_strain, plane, layer=None):
    """Parallel laminate on 0 <= y <= y_n stretched by eps0 along x."""
    p = _points(points)
    edges, e, nu, lam, mu = _layers(0., y_interfaces, young_moduli, poisson_ratios, plane)
    eps0 = _scalar(axial_strain, "axial_strain")
    c = lam/(lam+2*mu)                          # -eps_yy/eps_xx with sigma_yy = 0
    stiff = lam+2*mu-lam*c                      # E (stress) or E/(1-nu^2) (strain)
    drop = np.concatenate([[0.], np.cumsum(c*np.diff(edges))])[:-1]
    i = _locate(p[:, 1], edges, "laminate", layer)
    uy = -eps0*(drop[i]+c[i]*(p[:, 1]-edges[i]))
    sxx = stiff[i]*eps0
    szz = nu[i]*sxx if plane == "strain" else np.zeros(len(p))
    return LayeredElasticFields(np.column_stack([eps0*p[:, 0], uy]),
                                np.column_stack([sxx, np.zeros((len(p), 2))]), i, szz)


def series_bar(points, *, x_interfaces, young_moduli, poisson_ratios, axial_stress,
               plane, layer=None):
    """Layers in series along x, uniform sigma_xx; u(0, 0) = 0."""
    p = _points(points)
    edges, e, nu, lam, mu = _layers(0., x_interfaces, young_moduli, poisson_ratios, plane)
    s = _scalar(axial_stress, "axial_stress")
    # Invert the 2x2 in-plane law for sigma = (s, 0).
    det = (lam+2*mu)**2-lam**2
    exx, eyy = s*(lam+2*mu)/det, -s*lam/det
    if np.ptp(eyy) > 1e-12*np.max(abs(eyy), initial=0.)+1e-300:
        raise ValueError("layers contract laterally by different amounts; "
                         "the uniform-stress state is not an exact solution")
    shift = np.concatenate([[0.], np.cumsum(exx*np.diff(edges))])[:-1]
    i = _locate(p[:, 0], edges, "bar", layer)
    ux = shift[i]+exx[i]*(p[:, 0]-edges[i])
    szz = nu[i]*s if plane == "strain" else np.zeros(len(p))
    stress = np.column_stack([np.full(len(p), s), np.zeros((len(p), 2))])
    return LayeredElasticFields(np.column_stack([ux, eyy[i]*p[:, 1]]), stress, i, szz)


def composite_cylinder(points, *, inner_radius, interfaces, young_moduli, poisson_ratios,
                       plane, inner_pressure=0., outer_pressure=0.,
                       thermal_expansions=None, temperature_change=None, layer=None):
    """Lamé composite cylinder; temperature_change is (n,2) rows (a_i, b_i) in K."""
    p = _points(points)
    r0 = _scalar(inner_radius, "inner_radius")
    if r0 <= 0:
        raise ValueError("inner_radius must be > 0")
    edges, e, nu, lam, mu = _layers(r0, interfaces, young_moduli, poisson_ratios, plane)
    n = len(e)
    p_in, p_out = _scalar(inner_pressure, "inner_pressure"), _scalar(outer_pressure, "outer_pressure")
    alpha = _per_layer(thermal_expansions, n, "thermal_expansions", default=0.)
    if temperature_change is None:
        dt = np.zeros((n, 2))
    else:
        dt = np.asarray(temperature_change)
        if dt.shape != (n, 2) or dt.dtype.kind not in "iuf" or not np.all(np.isfinite(dt)):
            raise ValueError("temperature_change must be (n,2) finite rows (a_i, b_i)")
        dt = dt.astype(float)
    # beta: thermal stress per kelvin; plane strain keeps eps_zz = 0 of the 3D law.
    beta = (3*lam+2*mu)*alpha if plane == "strain" else e*alpha/(1-nu)
    kappa = beta/(lam+2*mu)

    def integral(i, r):   # I(r) = integral_{r0}^{r} s dT_i(s) ds (constant absorbed in B)
        a, b = dt[i, 0], dt[i, 1]
        return a*r**2/2+b*(r**2*np.log(r/r0)/2-r**2/4)

    def change(i, r):
        return dt[i, 0]+dt[i, 1]*np.log(r/r0)

    def radial(i, r):     # [u, sigma_rr] = rows . [A, B] + particular
        g = kappa[i]*integral(i, r)/r
        return (np.array([[r, 1/r], [2*(lam[i]+mu[i]), -2*mu[i]/r**2]]),
                np.array([g, -2*mu[i]*kappa[i]*integral(i, r)/r**2]))

    M, rhs = np.zeros((2*n, 2*n)), np.zeros(2*n)
    rows, part = radial(0, edges[0])
    M[0, :2], rhs[0] = rows[1], -p_in-part[1]
    for j in range(n-1):
        r = edges[j+1]
        left, lp = radial(j, r)
        right, rp = radial(j+1, r)
        M[1+2*j:3+2*j, 2*j:2*j+2] = left
        M[1+2*j:3+2*j, 2*j+2:2*j+4] = -right
        rhs[1+2*j:3+2*j] = rp-lp
    rows, part = radial(n-1, edges[-1])
    M[-1, -2:], rhs[-1] = rows[1], -p_out-part[1]
    coef = np.linalg.solve(M, rhs).reshape(n, 2)
    r = np.hypot(p[:, 0], p[:, 1])
    i = _locate(r, edges, "cylinder", layer)
    A, B = coef[i, 0], coef[i, 1]
    I = integral(i, r)
    u = kappa[i]*I/r+A*r+B/r
    srr = -2*mu[i]*kappa[i]*I/r**2+2*(lam[i]+mu[i])*A-2*mu[i]*B/r**2
    stt = (-2*mu[i]*kappa[i]*change(i, r)+2*mu[i]*kappa[i]*I/r**2
           + 2*(lam[i]+mu[i])*A+2*mu[i]*B/r**2)
    c, s = p[:, 0]/r, p[:, 1]/r
    stress = np.column_stack([srr*c*c+stt*s*s, srr*s*s+stt*c*c, (srr-stt)*c*s])
    szz = (nu[i]*(srr+stt)-e[i]*alpha[i]*change(i, r) if plane == "strain"
           else np.zeros(len(p)))
    return CylinderFields(u[:, None]*np.column_stack([c, s]), stress, i, szz,
                          u, srr, stt, coef)
