# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Normalized power-panel integrals for homogeneous two-dimensional Laplace.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).

For arc length s in (0,h), phi(s) = p/h * (s/h)**(p-1) integrates to one.
The singular endpoint is s=0. These explicit numerical primitives do not
alter any constant-panel solver or establish field/mesh convergence.
"""
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import math
import numpy as np
from scipy.special import digamma, xlogy
from scipy.linalg import eigh_tridiagonal

__all__ = ['PowerPanelLogResult', 'power_panel_quadrature',
           'power_panel_gram', 'power_panel_self_log',
           'power_panel_shared_vertex_log', 'power_panel_separated_log',
           'power_panel_constant_log', 'power_panel_linear_gram',
           'power_panel_linear_self_log', 'PowerPanelLinearLogResult',
           'power_panel_linear_far_log', 'power_panel_linear_shared_vertex_log',
           'power_panel_linear_separated_log', 'power_panel_linear_constant_log']


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
    return _cached_power_rule(p, n)


@lru_cache(maxsize=128)
def _cached_power_rule(p, n):
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


def _graded_power_rule(power,order):
    """Cubic-coordinate rule for p*u**(p-1); no weight-sum rescaling."""
    p=_power(power);n=_order(order,128)
    return _cached_graded_rule(p,n)


@lru_cache(maxsize=128)
def _cached_graded_rule(p,n):
    alpha=2.;beta=3*p-1.;s=alpha+beta
    k=np.arange(n,dtype=float);diag=np.empty(n);diag[0]=(beta-alpha)/(s+2)
    diag[1:]=(beta*beta-alpha*alpha)/((2*k[1:]+s)*(2*k[1:]+s+2))
    k=k[1:];off=2/(2*k+s)*np.sqrt(k*(k+alpha)*(k+beta)*(k+s)/((2*k+s-1)*(2*k+s+1)))
    nodes,vectors=eigh_tridiagonal(diag,off,lapack_driver='stev');t=(nodes+1)/2
    denominator=t**3+(1-t)**3
    x=t**3/denominator
    weights=vectors[0]**2*2/((3*p+1)*(3*p+2))/denominator**(p+1)
    return _frozen(x),_frozen(weights)

def _constant_segment_log(z):
    """Mean log|z+t| for a constant unit segment, avoiding far cancellation."""
    z=np.asarray(z,dtype=complex);out=np.empty(z.shape);far=abs(z)>2
    # Integral of log(1+t/z) = sum (-1)^(k+1)/(k*(k+1)*z^k).
    # |1/z| < 1/2: after 48 terms the absolute tail is < 1.5e-18.
    # Complex log1p can lose small real parts before multiplication by z.
    reciprocal=1/z[far]
    series=np.zeros(reciprocal.shape,dtype=complex)
    for k in range(48,0,-1):
        series=reciprocal*(((-1.)**(k+1))/(k*(k+1))+series)
    out[far]=np.log(z[far]).real+series.real
    if np.any(~far):
        u=z[~far].real;h=abs(z[~far].imag)
        def primitive(x):return .5*xlogy(x,x*x+h*h)-x+h*np.arctan2(x,h)
        out[~far]=primitive(u+1)-primitive(u)
    return out

def _require_disjoint_or_endpoint(a,b,o):
    """Exact topology of binary input vectors; no normalized-coordinate snap."""
    a,b,o=[[Fraction(float(x)) for x in v] for v in (a,b,o)]
    def cross(x,y):return x[0]*y[1]-x[1]*y[0]
    determinant=cross(a,b)
    if determinant:
        t,v=cross(o,b)/determinant,cross(o,a)/determinant
        if 0<=t<=1 and 0<=v<=1 and not (t in (0,1) and v in (0,1)):
            raise ValueError('crossing or overlapping panels')
    elif cross(a,o)==0:
        axis=0 if a[0] else 1
        s,t=o[axis]/a[axis],(o[axis]+b[axis])/a[axis]
        if max(0,min(s,t))<min(1,max(s,t)):
            raise ValueError('overlapping panels')

def power_panel_constant_log(a, b, offset, exponent):
    """Double log mean between one power panel and one constant panel.

    The power panel runs from zero to a; the constant panel runs from offset
    to offset+b, in metres. Exponent lies in (0.5,1]. Allow only disjoint
    panels or a common endpoint; refuse overlap and interior intersections.
    The length ratio is at most 1e6. The analytic constant-source mean and a
    cubic target-coordinate rule use fixed orders 64/128, with unchanged
    1e-12 normalized refinement and target-normalization gates. There is no
    adaptive fallback and no field-solve or current-convergence guarantee.
    """
    p = _power(exponent)
    n = 64
    vectors = []
    for value in (a,b,offset):
        raw=np.asarray(value)
        if raw.shape!=(2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():
            raise ValueError('finite planar vectors required')
        vectors.append(np.asarray(raw,dtype=float))
    a,b,o=vectors;la,lb,lo=[math.hypot(*v) for v in vectors]
    if not all(math.isfinite(x) for x in (la,lb,lo)) or min(la,lb)<=0:
        raise ValueError('unrepresentable geometry')
    size=max(la,lb)
    if min(la,lb)/size<1e-6:raise ValueError('length ratio exceeds 1e6')
    if lo/4<size:
        _require_disjoint_or_endpoint(a,b,o)
    scale=max(size,lo);a,b,o=a/scale,b/scale,o/scale
    direction=complex(*b)
    def evaluate(order):
        x,w=_graded_power_rule(p,order)
        if abs(w.sum()-1)>1e-12:raise ValueError('target normalization failed')
        delta=o-x[:,None]*a
        z=(delta[:,0]+1j*delta[:,1])/direction
        if not np.isfinite(z).all():raise ValueError('source coordinates not representable')
        return float(math.log(lb)+w@_constant_segment_log(z))
    coarse,fine=evaluate(n),evaluate(2*n)
    if not math.isfinite(coarse) or not math.isfinite(fine) or abs(fine-coarse)>1e-12*max(1,abs(fine)):
        raise ValueError('power-constant quadrature did not converge')
    return PowerPanelLogResult(fine,coarse,n)


def power_panel_linear_gram(length, exponent):
    """Exact 2x2 squared-current Gram for a hierarchical linear power basis.

    For u=s/h, phi0=p/h*u**(p-1) and
    phi1=sqrt(p*(p+2)) * ((p+1)/h*u**p - phi0).
    Their integrated masses are exactly [1,0]. Rows/columns follow phi0,
    phi1; entries have units 1/metre. Require p in (0.5,1] for finite L2
    current. No existing panel basis or field solver is changed.
    """
    h,p = _length(length),_power(exponent)
    zero = power_panel_gram(h,p)
    scale = math.sqrt(p*(p+2))
    cross = (scale*(p-1)/(2*(2*p-1)))/h
    linear = (p*p*(p+2)/((2*p-1)*(2*p+1)))/h
    if (not all(map(math.isfinite,(zero,cross,linear))) or linear<=0
            or (p!=1 and cross==0)):
        raise ValueError('linear squared-current Gram is not representable')
    return _frozen([[zero,cross],[cross,linear]]).reshape(2,2)


def power_panel_linear_self_log(length, exponent):
    """Exact 2x2 self log-distance integral for the linear power basis.

    Use the same phi0/phi1 as power_panel_linear_gram. The logarithm is
    log(|s-t| / 1 metre); only entry 00 changes under physical scaling,
    since phi1 has zero mass. The closed expressions cancel the shared
    digamma and length terms analytically, not by subtracting estimates.
    This primitive does not supply interactions or a field approximation.
    """
    h,p = _length(length),_power(exponent)
    zero = power_panel_self_log(h,p)
    scale = math.sqrt(p*(p+2))
    cross = scale*(1-p)/(2*p*(p+1))
    linear = -(p+2)/(2*(p+1))
    return _frozen([[zero,cross],[cross,linear]]).reshape(2,2)


@dataclass(frozen=True)
class PowerPanelLinearLogResult:
    """Read-only fine/coarse 2x2 far-log blocks returned by the explicit rule."""
    mean_log_distance: np.ndarray
    coarse_mean_log_distance: np.ndarray
    quadrature_order: int


def power_panel_linear_far_log(first,second,offset,first_exponent,second_exponent,*,quadrature_order=32):
    """Far log-distance block for constant-mass and zero-mass linear modes.

    Use phi0=p/h*u**(p-1) and phi1=sqrt(p*(p+2))*((p+1)/p*u-1)*phi0,
    each singular at its panel origin. Rows belong to the first panel and
    columns to the second, whose origin is offset from the first. All vectors
    are planar metres; length ratio is at most64 and |offset| must be at least
    four times the sum of panel lengths. Exponents lie in (0.5,1].

    The dimensionless logarithm uses one metre as reference. Only entry00
    changes under common geometric scaling. Analytic masses [1,0], centered
    log1p differences and unchanged Gauss-Jacobi weights avoid subtracting
    scale constants in zero-mass modes. Compare n and 2*n (n=4..64) entrywise
    at 1e-12*max(1,abs(fine)); this is a primitive quadrature criterion, not
    a field error bound. Near/touching interactions and field solving are
    outside this explicit far contract. No fallback or weight rescaling.
    """
    p,q=_power(first_exponent),_power(second_exponent);n=_order(quadrature_order,64)
    vectors=[]
    for value in (first,second,offset):
        raw=np.asarray(value)
        if raw.shape!=(2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():
            raise ValueError('vectors must be finite real planar pairs')
        vectors.append(np.asarray(raw,dtype=float))
    a,b,o=vectors;la,lb,lo=[math.hypot(*v) for v in vectors]
    if not all(math.isfinite(x) for x in (la,lb,lo)) or min(la,lb,lo)<=0:
        raise ValueError('panel lengths and offset must be positive and representable')
    if min(la,lb)/max(la,lb)<1/64:raise ValueError('panel length ratio must not exceed 64')
    if la/lo+lb/lo>.25:raise ValueError('offset must be at least four times the sum of panel lengths')
    a,b,o=a/lo,b/lo,o/lo
    def evaluate(order):
        u,w=power_panel_quadrature(p,order);v,z=power_panel_quadrature(q,order)
        ua=u[:,None]*a;vb=v[:,None]*b
        # log|base+delta|-log|base| without subtracting large logarithms.
        def difference(base,delta):
            return .5*np.log1p((2*np.sum(base*delta,axis=-1)+np.sum(delta*delta,axis=-1))/np.sum(base*base,axis=-1))
        L=.5*np.log(np.sum((ua[:,None]-o-vb[None])**2,axis=-1))
        left=difference(-o-vb[None],ua[:,None])
        right=difference(ua[:,None]-o,-vb[None])
        left_zero=difference(-o,ua)[:,None]
        mixed=left-left_zero
        wp=w*math.sqrt(p*(p+2))*((p+1)/p*u-1)
        zq=z*math.sqrt(q*(q+2))*((q+1)/q*v-1)
        def total(x,y,matrix):return math.fsum((x[:,None]*matrix*y[None]).ravel())
        return np.array([[math.log(lo)+total(w,z,L),total(w,zq,right)],
                         [total(wp,z,left),total(wp,zq,mixed)]])
    coarse,fine=evaluate(n),evaluate(2*n)
    if not np.isfinite(coarse).all() or not np.isfinite(fine).all() or np.any(abs(fine-coarse)>1e-12*np.maximum(1,abs(fine))):
        raise ValueError('linear far-panel quadrature did not converge')
    return PowerPanelLinearLogResult(_frozen(fine).reshape(2,2),_frozen(coarse).reshape(2,2),n)


def power_panel_linear_shared_vertex_log(first,second,first_exponent,second_exponent,*,quadrature_order=32):
    """Linear power log block for panels meeting only at their origins.

    Use the same phi0/phi1 and mode ordering as power_panel_linear_far_log.
    Displacements are planar metres with length ratio at most64, nonoverlapping
    rays and exponents in (0.5,1]. A Duffy split integrates the radial log
    analytically; unchanged normalized Gauss-Jacobi rules integrate the angular
    factors. Analytic masses [1,0] add log(scale) only to entry00.

    Retain n/2n entrywise comparisons (n=4..64) at the dimensionless criterion
    1e-12*max(1,abs(fine)). Failure is explicit without retries or fallback.
    Some admitted geometries need a larger explicit order; this is not a
    guarantee that every allowed order resolves every input. The result does
    not establish full current-field or boundary-mesh convergence, and does
    not provide disjoint near-panel interactions or a linear field solver.
    """
    p,q=_power(first_exponent),_power(second_exponent);n=_order(quadrature_order,64)
    vectors=[]
    for value in (first,second):
        raw=np.asarray(value)
        if raw.shape!=(2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():raise ValueError('finite real planar vectors required')
        vectors.append(raw.astype(float))
    a,b=vectors;la,lb=math.hypot(*a),math.hypot(*b)
    if not math.isfinite(max(la,lb)) or min(la,lb)<=0:raise ValueError('positive representable lengths required')
    scale=max(la,lb)
    if min(la,lb)/scale<1/64:raise ValueError('length ratio must not exceed64')
    a,b=a/scale,b/scale;cross=a[0]*b[1]-a[1]*b[0]
    if float(a@b)>=0 and abs(cross)<=128*np.finfo(float).eps*(la/scale)*(lb/scale):raise ValueError('rays must not overlap')
    lp,lq=math.sqrt(p*(p+2)),math.sqrt(q*(q+2))
    left=np.array([[1.,0.],[-lp,lp*(p+1)/p]]);right=np.array([[1.,0.],[-lq,lq*(q+1)/q]])
    def evaluate(k):
        u,w=power_panel_quadrature(p,k);v,z=power_panel_quadrature(q,k)
        loga=np.log(np.hypot(*(a-v[:,None]*b).T));logb=np.log(np.hypot(*(u[:,None]*a-b).T))
        J=np.array([[(p*math.fsum(z*v**s*loga)+q*math.fsum(w*u**r*logb)-p*q/((p+r)*(q+s)))/(p+q+r+s) for s in range(2)] for r in range(2)])
        out=np.array([[math.fsum(left[i,r]*right[j,s]*J[r,s] for r in range(2) for s in range(2)) for j in range(2)] for i in range(2)])
        out[0,0]+=math.log(scale);return out
    coarse,fine=evaluate(n),evaluate(2*n)
    if not np.isfinite(coarse).all() or not np.isfinite(fine).all() or np.any(abs(fine-coarse)>1e-12*np.maximum(1,abs(fine))):raise ValueError('linear vertex quadrature did not converge')
    return PowerPanelLinearLogResult(_frozen(fine).reshape(2,2),_frozen(coarse).reshape(2,2),n)


def power_panel_linear_separated_log(first,second,offset,first_exponent,second_exponent,*,quadrature_order=32):
    """Linear-power log block for two sufficiently separated finite panels.

    The first panel runs from zero to first, the second from offset to
    offset+second, in planar metres. Use the same physical phi0/phi1 modes
    as power_panel_linear_self_log, with analytic masses[1,0]. Require
    exponents in(0.5,1], length ratio<=64 and segment separation at least
    half the longer length. Normalized panel directions must remain
    representable. This separate API does not replace the far primitive.

    Center zero-mass entries using log-distance differences, retain physical
    quadrature weights and add log(scale) only to00. Compare requested
    n/2n rules (n=4..64) entrywise at1e-12*max(1,abs(fine)); unresolved
    inputs are refused without retries. This dimensionless primitive check
    is not a field error bound. Closer/touching panels, assembly and current
    solving need separate contracts and verification.
    """
    p,q=_power(first_exponent),_power(second_exponent);n=_order(quadrature_order,64)
    vectors=[]
    for value in (first,second,offset):
        raw=np.asarray(value)
        if raw.shape!=(2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():
            raise ValueError('vectors must be finite real planar pairs')
        vectors.append(np.asarray(raw,dtype=float))
    a,b,o=vectors;la,lb,lo=[math.hypot(*v) for v in vectors]
    if not all(math.isfinite(x) for x in (la,lb,lo)) or min(la,lb,lo)<=0:
        raise ValueError('panel lengths and offset must be positive and representable')
    size=max(la,lb)
    if min(la,lb)/size<1/64:raise ValueError('panel length ratio must not exceed 64')
    if lo/4<size and _separated_distance(a/size,b/size,o/size)<.5:
        raise ValueError('panel separation must be at least half the longer length')
    scale=max(size,lo);a,b,o=a/scale,b/scale,o/scale
    if not np.any(a) or not np.any(b):raise ValueError('normalized panel direction is not representable')
    def evaluate(order):
        u,w=power_panel_quadrature(p,order);v,z=power_panel_quadrature(q,order)
        ua=u[:,None]*a;vb=v[:,None]*b
        # log|base+delta|-log|base| without subtracting large logarithms.
        def difference(base,delta):
            old=np.hypot(base[...,0],base[...,1]);new=base+delta
            distance=np.hypot(new[...,0],new[...,1])
            change=2*np.sum(base*delta,axis=-1)+np.sum(delta*delta,axis=-1)
            return np.log1p(change/(old*(distance+old)))
        L=.5*np.log(np.sum((ua[:,None]-o-vb[None])**2,axis=-1))
        left=difference(-o-vb[None],ua[:,None])
        right=difference(ua[:,None]-o,-vb[None])
        left_zero=difference(-o,ua)[:,None]
        mixed=left-left_zero
        wp=w*math.sqrt(p*(p+2))*((p+1)/p*u-1)
        zq=z*math.sqrt(q*(q+2))*((q+1)/q*v-1)
        def total(x,y,matrix):return math.fsum((x[:,None]*matrix*y[None]).ravel())
        return np.array([[math.log(scale)+total(w,z,L),total(w,zq,right)],
                         [total(wp,z,left),total(wp,zq,mixed)]])
    coarse,fine=evaluate(n),evaluate(2*n)
    if not np.isfinite(coarse).all() or not np.isfinite(fine).all() or np.any(abs(fine-coarse)>1e-12*np.maximum(1,abs(fine))):
        raise ValueError('linear separated-panel quadrature did not converge')
    return PowerPanelLinearLogResult(_frozen(fine).reshape(2,2),_frozen(coarse).reshape(2,2),n)


def _constant_linear_segment_log(z):
    """Integral of (2t-1)*log|z+t| on[0,1], before sqrt(3)."""
    z=np.asarray(z,dtype=complex);out=np.empty(z.shape);far=abs(z)>2
    reciprocal=1/z[far];series=np.zeros(reciprocal.shape,dtype=complex)
    for k in range(48,0,-1):series=reciprocal*((-1.)**(k+1)/((k+1)*(k+2))+series)
    out[far]=series.real
    near=~far;values=z[near];entry=np.empty(values.shape);zero=values==0;one=values==-1
    entry[zero]=.5;entry[one]=-.5;regular=~(zero|one);x=values[regular]
    entry[regular]=(x+.5-x*(x+1)*(np.log(x+1)-np.log(x))).real
    out[near]=entry;return out

def power_panel_linear_constant_log(a,b,offset,exponent):
    """Two physical linear modes on a power target and a constant source.

    The target runs from zero to a; source from offset to offset+b, in
    planar metres. Use phi0/phi1 of power_panel_linear_self_log, target
    exponent in(0.5,1] and source exponent1. Allow disjoint panels and
    common endpoints, length ratio<=1e6; refuse overlap and interior
    intersections using exact binary-input topology. Normalized directions
    and source coordinates must remain representable.

    Integrate both source polynomial modes analytically and the target
    with fixed cubic-coordinate64/128 rules. Keep physical weights and
    analytic masses[1,0]; center target zero-mass entries before summing.
    Original dimensionless1e-12 target-mass and entrywise refinement checks
    are explicit: unresolved near interactions raise without retries.
    This primitive does not establish field, panel or current convergence.
    """
    p=_power(exponent);n=64;vectors=[]
    for value in (a,b,offset):
        raw=np.asarray(value)
        if raw.shape!=(2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():raise ValueError('finite planar vectors required')
        vectors.append(np.asarray(raw,dtype=float))
    a,b,o=vectors;la,lb,lo=[math.hypot(*v) for v in vectors]
    if not all(math.isfinite(x) for x in (la,lb,lo)) or min(la,lb)<=0:raise ValueError('unrepresentable geometry')
    size=max(la,lb)
    if min(la,lb)/size<1e-6:raise ValueError('length ratio exceeds1e6')
    if lo/4<size:_require_disjoint_or_endpoint(a,b,o)
    scale=max(size,lo);a,b,o=a/scale,b/scale,o/scale;direction=complex(*b)
    if direction==0 or not np.any(a):raise ValueError('unrepresentable normalized direction')
    z0=complex(*o)/direction
    anchor0=float(_constant_segment_log(z0));anchor1=float(_constant_linear_segment_log(z0))
    def evaluate(order):
        u,w=_graded_power_rule(p,order);psi=math.sqrt(p*(p+2))*((p+1)/p*u-1);wp=w*psi
        if max(abs(math.fsum(w)-1),abs(math.fsum(wp)))>1e-12:raise ValueError('target mass unresolved')
        delta=o-u[:,None]*a;z=(delta[:,0]+1j*delta[:,1])/direction
        if not np.isfinite(z).all():raise ValueError('source coordinates unrepresentable')
        k0=_constant_segment_log(z);k1=_constant_linear_segment_log(z)
        return np.array([[math.log(lb)+math.fsum(w*k0),math.sqrt(3)*math.fsum(w*k1)],
                         [math.fsum(wp*(k0-anchor0)),math.sqrt(3)*math.fsum(wp*(k1-anchor1))]])
    coarse,fine=evaluate(n),evaluate(2*n)
    if not np.isfinite(coarse).all() or not np.isfinite(fine).all() or np.any(abs(fine-coarse)>1e-12*np.maximum(1,abs(fine))):raise ValueError('linear power-constant quadrature did not converge')
    return PowerPanelLinearLogResult(_frozen(fine).reshape(2,2),_frozen(coarse).reshape(2,2),n)


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
cached_graded_rule = _cached_graded_rule
cached_power_rule = _cached_power_rule
constant_linear_segment_log = _constant_linear_segment_log
constant_segment_log = _constant_segment_log
frozen = _frozen
graded_power_rule = _graded_power_rule
length = _length
order = _order
power = _power
require_disjoint_or_endpoint = _require_disjoint_or_endpoint
scalar = _scalar
separated_distance = _separated_distance
