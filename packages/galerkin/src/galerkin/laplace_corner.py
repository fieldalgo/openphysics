# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Normalized power-panel integrals for homogeneous two-dimensional Laplace.

For arc length s in (0,h), phi(s) = p/h * (s/h)**(p-1) integrates to one.
The singular endpoint is s=0. These explicit numerical primitives do not
alter any constant-panel solver or establish field/mesh convergence.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.special import digamma
from scipy.linalg import eigh_tridiagonal

__all__ = ['PowerPanelLogResult', 'power_panel_quadrature',
           'power_panel_gram', 'power_panel_self_log',
           'power_panel_shared_vertex_log', 'power_panel_separated_log']


def _scalar(value, name):
    raw = np.asarray(value)
    if raw.ndim != 0 or raw.dtype.kind not in 'fiu':
        raise ValueError(name + ' must be a finite real scalar')
    result = float(raw)
    if not math.isfinite(result):
        raise ValueError(name + ' must be a finite real scalar')
    return result


def _power(value):
    value = _scalar(value, 'exponent')
    if not .5 < value <= 1.:
        raise ValueError('exponent must lie in (0.5, 1] for finite squared current')
    return value


def _length(value):
    value = _scalar(value, 'length')
    if value <= 0:
        raise ValueError('length must be positive')
    return value


def _order(value, maximum):
    value = _scalar(value, 'quadrature_order')
    if not value.is_integer() or not 4 <= value <= maximum:
        raise ValueError(f'quadrature_order must be an integer in [4, {maximum}]')
    return int(value)


def _frozen(value):
    return np.frombuffer(np.asarray(value, dtype=float).tobytes(), dtype=float)


def power_panel_quadrature(exponent, order=32):
    """Immutable nodes/weights for integral_0^1 p*u**(p-1)*f(u) du.

    Positive Gauss-Jacobi weights are analytically normalized, without
    dividing by their computed sum. Orders 4..128 are explicit.
    """
    p = _power(exponent)
    n = _order(order, 128)
    # Golub-Welsch for the already normalized Jacobi measure. Avoid a
    # derivative-based weight formula and any computed-sum normalization.
    beta = p-1.
    index = np.arange(n, dtype=float)
    diagonal = np.empty(n)
    diagonal[0] = beta/(beta+2.)
    diagonal[1:] = beta*beta/((2*index[1:]+beta)*(2*index[1:]+beta+2.))
    k = index[1:]
    off_diagonal = (2./(2*k+beta) * np.sqrt(
        k*k*(k+beta)*(k+beta)/((2*k+beta-1.)*(2*k+beta+1.))))
    nodes, vectors = eigh_tridiagonal(diagonal, off_diagonal, lapack_driver='stev')
    return _frozen((nodes+1.)/2.), _frozen(vectors[0]**2)


def power_panel_gram(length, exponent):
    """Exact integral phi(s)**2 ds, in inverse metres; p must exceed 1/2."""
    h, p = _length(length), _power(exponent)
    result = (p*p/(2.*p-1.))/h
    if not math.isfinite(result):
        raise ValueError('squared-current integral is not representable')
    return result


def power_panel_self_log(length, exponent):
    """Exact double mean log(|s-t| / 1 metre) on the same power panel."""
    h, p = _length(length), _power(exponent)
    return float(math.log(h)-1./(2.*p)-digamma(p+1.)-np.euler_gamma)


@dataclass(frozen=True)
class PowerPanelLogResult:
    """Mean logarithmic distance and the retained quadrature comparison."""
    mean_log_distance: float
    coarse_mean_log_distance: float
    quadrature_order: int

    @property
    def refinement_error(self):
        return abs(self.mean_log_distance-self.coarse_mean_log_distance) / max(
            1., abs(self.mean_log_distance))


def power_panel_shared_vertex_log(first, second, first_exponent,
                                  second_exponent, *, quadrature_order=32):
    """Double weighted log distance for panels meeting only at their origins.

    first and second are two finite planar displacement vectors in metres.
    Their length ratio is at most 64; coincident/overlapping rays are rejected.
    A Duffy split integrates the radial logarithm analytically and uses
    Gauss-Jacobi only for its smooth angular integrals. Compare order n with
    2*n at 1e-12 * max(1, abs(fine)); failure is explicit, without fallback.
    This checks quadrature, not current-field or boundary-mesh convergence.
    """
    p, q = _power(first_exponent), _power(second_exponent)
    n = _order(quadrature_order, 64)
    vectors = []
    for value in (first, second):
        raw = np.asarray(value)
        if raw.shape != (2,) or raw.dtype.kind not in 'fiu':
            raise ValueError('panel vectors must be finite real planar pairs')
        vector = np.asarray(raw, dtype=float)
        if not np.isfinite(vector).all():
            raise ValueError('panel vectors must be finite real planar pairs')
        vectors.append(vector)
    a, b = vectors
    la, lb = math.hypot(*a), math.hypot(*b)
    if not math.isfinite(max(la, lb)) or min(la, lb) <= 0:
        raise ValueError('panel vectors must have finite positive lengths')
    scale = max(la, lb)
    if min(la, lb)/scale < 1./64.:
        raise ValueError('panel length ratio must not exceed 64')
    a, b = a/scale, b/scale
    cross = a[0]*b[1]-a[1]*b[0]
    if (float(a@b) >= 0 and
            abs(cross) <= 128*np.finfo(float).eps*(la/scale)*(lb/scale)):
        raise ValueError('panel rays must not overlap')

    def integrate(order):
        u, wu = power_panel_quadrature(q, order)
        v, wv = power_panel_quadrature(p, order)
        first_log = np.log(np.hypot(*(a[None]-u[:, None]*b).T))
        second_log = np.log(np.hypot(*(v[:, None]*a-b[None]).T))
        return float(math.log(scale)-1./(p+q) +
                     (p*(wu@first_log)+q*(wv@second_log))/(p+q))

    coarse, fine = integrate(n), integrate(2*n)
    if (not math.isfinite(coarse) or not math.isfinite(fine) or
            abs(fine-coarse) > 1e-12*max(1., abs(fine))):
        raise ValueError('power-panel quadrature did not converge')
    return PowerPanelLogResult(fine, coarse, n)


def _separated_distance(a,b,offset):
    """Minimum segment distance after bounded coordinate normalization."""
    def cross(x,y):return x[0]*y[1]-x[1]*y[0]
    def distance(point,start,direction):
        t=np.clip((point-start)@direction/(direction@direction),0.,1.)
        return math.hypot(*(point-start-t*direction))
    if cross(a,b)!=0:
        c,d=cross(a,offset),cross(a,offset+b)
        e,f=cross(b,-offset),cross(b,a-offset)
        if ((c<=0<=d or d<=0<=c) and (e<=0<=f or f<=0<=e)):
            return 0.
    return min(distance(np.zeros(2),offset,b),distance(a,offset,b),
               distance(offset,np.zeros(2),a),distance(offset+b,np.zeros(2),a))

def power_panel_separated_log(first,second,offset,first_exponent,second_exponent,*,quadrature_order=32):
    """Weighted double log distance between explicitly separated power panels.

    First panel starts at zero with displacement first. Second starts at
    offset with displacement second. All vectors are in metres; each power
    density is singular at its specified start. Length ratio is at most 64;
    minimum segment distance must be at least half the longer panel length.
    Positive tensor Gauss-Jacobi compares n and 2*n with the unchanged 1e-12
    normalized log gate. No proximity fallback or field solve is performed.
    """
    p,q=_power(first_exponent),_power(second_exponent);n=_order(quadrature_order,64)
    vectors=[]
    for value in (first,second,offset):
        raw=np.asarray(value)
        if raw.shape!=(2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():
            raise ValueError('vectors must be finite real planar pairs')
        vectors.append(np.asarray(raw,dtype=float))
    a,b,o=vectors;la,lb,lo=[math.hypot(*v) for v in vectors]
    if not all(math.isfinite(x) for x in (la,lb,lo)) or min(la,lb)<=0:
        raise ValueError('panel lengths and offset norm must be representable')
    size=max(la,lb)
    if min(la,lb)/size<1/64:raise ValueError('panel length ratio must not exceed 64')
    if lo/4<size and _separated_distance(a/size,b/size,o/size)<.5:
        raise ValueError('panel separation must be at least half the longer length')
    scale=max(size,lo);a,b,o=a/scale,b/scale,o/scale
    def evaluate(order):
        u,w=power_panel_quadrature(p,order);v,z=power_panel_quadrature(q,order)
        delta=u[:,None,None]*a-o-v[None,:,None]*b
        distance=np.hypot(delta[:,:,0],delta[:,:,1])
        if not np.isfinite(distance).all() or np.any(distance<=0):
            raise ValueError('panel distance is not representable')
        return float(math.log(scale)+w@np.log(distance)@z)
    coarse,fine=evaluate(n),evaluate(2*n)
    if not math.isfinite(coarse) or not math.isfinite(fine) or abs(fine-coarse)>1e-12*max(1,abs(fine)):
        raise ValueError('power-panel quadrature did not converge')
    return PowerPanelLogResult(fine,coarse,n)
