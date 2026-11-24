# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Checked density-averaged Laplace Green integrals above a grounded line.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).
"""
from dataclasses import dataclass
import math
import numpy as np
from .laplace_corner import (
    power as _power,
    scalar as _scalar,
    graded_power_rule as _graded_power_rule,
    constant_segment_log as _constant_segment_log,
    require_disjoint_or_endpoint as _require_disjoint_or_endpoint)


@dataclass(frozen=True)
class HalfSpacePanelIntegral:
    """Dimensionless mean log(image distance / real distance), without 1/(2*pi)."""
    green_mean: float
    coarse_green_mean: float
    quadrature_order: int

    @property
    def refinement_error(self):
        return abs(self.green_mean-self.coarse_green_mean)/max(1., abs(self.green_mean))


def power_constant_half_space(first, second, offset, exponent, *, height):
    """Mean bottom-ground Green kernel for a power target and constant source.

    Target: (0, height) + u*first, with normalized density p*u**(p-1).
    Source: (0, height) + offset + v*second, with uniform density on v in [0,1].
    All lengths are metres. Only disjoint segments or endpoint contact are
    admitted. Length ratio <= 1e6; p in (0.5,1]. Every endpoint is above the
    ground. Panel lengths and endpoint heights, divided by the largest
    length, offset/image norm or start height, must be >= 128*binary64 eps.

    An analytic source mean and fixed 64/128 cubic target rules must agree
    to 1e-12*max(1,abs(fine)). The exact constant moment is split analytically;
    quadrature weights are never rescaled. No field accuracy, panel/outer
    convergence or upper/side boundary conditions are supplied by this API.
    """
    p = _power(exponent)
    h = _scalar(height, 'height')
    vectors = []
    for value in (first, second, offset):
        raw = np.asarray(value)
        if raw.shape != (2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():
            raise ValueError('vectors must be finite real planar pairs')
        vectors.append(np.asarray(raw, dtype=float))
    a, b, o = vectors
    la, lb, lo = [math.hypot(*v) for v in vectors]
    if not all(math.isfinite(x) for x in (la,lb,lo)) or min(la,lb) <= 0:
        raise ValueError('panel lengths and offset norm must be representable')
    if min(la,lb)/max(la,lb) < 1e-6:
        raise ValueError('panel length ratio must not exceed 1e6')
    try:
        hs = math.fsum((h,float(o[1])))
        endpoints = [h,math.fsum((h,float(a[1]))),hs,
                     math.fsum((h,float(o[1]),float(b[1])))]
        image = np.array([o[0],math.fsum((-h,-h,-float(o[1])))])
    except OverflowError as exc:
        raise ValueError('endpoint and image heights must be representable') from exc
    if not all(math.isfinite(x) for x in endpoints) or min(endpoints) <= 0:
        raise ValueError('all endpoints must be above ground')
    scale = max(la,lb,lo,math.hypot(*image),h,hs)
    if not math.isfinite(scale) or min(la,lb,*endpoints)/scale < 128*np.finfo(float).eps:
        raise ValueError('panel length or ground clearance is unresolved')
    _require_disjoint_or_endpoint(a,b,o)
    a,b,o,image = [x/scale for x in (a,b,o,image)]
    heights = np.array([h,hs])/scale
    direction = complex(*b)
    image_direction = direction.conjugate()

    def integrand(u):
        u = np.atleast_1d(u)
        real = o-u[:,None]*a
        reflected = image-u[:,None]*a
        z = (real[:,0]+1j*real[:,1])/direction
        zi = (reflected[:,0]+1j*reflected[:,1])/image_direction
        far = (abs(z)>2)&(abs(zi)>2)
        out = np.empty(len(u))
        out[~far] = _constant_segment_log(zi[~far])-_constant_segment_log(z[~far])
        if np.any(far):
            inverse,ii = 1/z[far],1/zi[far]
            power,ip = inverse.copy(),ii.copy()
            series = np.zeros(len(inverse),dtype=complex)
            # Integrate the source log(1+t/z). Each omitted tail is < 1.5e-18.
            for k in range(1,49):
                series += ((-1)**(k+1)/(k*(k+1)))*(ip-power)
                power *= inverse
                ip *= ii
            yt = heights[0]+u[far]*a[1]
            distance = np.sum(real[far]*real[far],axis=1)
            out[far] = .5*np.log1p(4*yt*heights[1]/distance)+series.real
        return out

    anchor = float(integrand([0.])[0])
    estimates = []
    for order in (64,128):
        u,w = _graded_power_rule(p,order)
        if abs(w.sum()-1) > 1e-12:
            raise ValueError('target quadrature normalization failed')
        estimates.append(float(anchor+w@(integrand(u)-anchor)))
    coarse,fine = estimates
    if not all(map(math.isfinite,estimates)) or abs(fine-coarse)>1e-12*max(1,abs(fine)):
        raise ValueError('half-space quadrature did not converge')
    if min(coarse,fine) <= 0:
        raise ValueError('positive half-space Green mean is unresolved')
    return HalfSpacePanelIntegral(fine,coarse,64)


__all__ = ['HalfSpacePanelIntegral','power_constant_half_space']
