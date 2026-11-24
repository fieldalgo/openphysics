# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Normalized corner-density Green matrices above one grounded line.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).
"""
from dataclasses import dataclass
from .laplace_corner_geometry import (
    CornerPanelGeometry,
    prepare_two_ground_corner_panels,
    immutable as _immutable)

import math
import numpy as np
from numpy.polynomial.legendre import leggauss
from galerkin import _laplace_panels as kernel
from galerkin.laplace_corner import (power_panel_self_log,power_panel_shared_vertex_log,
    power_panel_separated_log,power_panel_constant_log)

def _offsets(g,ii,jj,image=False):
    ii,jj=np.atleast_1d(ii),np.atleast_1d(jj);ii,jj=np.broadcast_arrays(ii,jj)
    sign=np.array([1.,-1.]) if image else np.ones(2)
    values=np.array([[math.fsum((float(sign[k]*g['anchor'][j,k]),-float(g['anchor'][i,k]),float(sign[k]*g['local'][j,k]),-float(g['local'][i,k]))) for k in range(2)] for i,j in zip(ii,jj)])
    if not image:
        ai,bi=g['starts'][ii],g['ends'][ii];aj,bj=g['starts'][jj],g['ends'][jj]
        values[ai==aj]=0.
        mask=bi==aj;values[mask]=g['direction'][ii[mask]]
        mask=ai==bj;values[mask]=-g['direction'][jj[mask]]
        mask=bi==bj;values[mask]=g['direction'][ii[mask]]-g['direction'][jj[mask]]
    return values

def _relative_displacements(g,sl):
    # Neumaier compensation keeps the four binary coordinate components.
    # No platform-specific extended floating-point type is required.
    anchor,local=g['anchor'],g['local']
    total=np.zeros((len(anchor[sl]),len(anchor),2));correction=np.zeros_like(total)
    for value in (anchor[None],-anchor[sl,None],local[None],-local[sl,None]):
        updated=total+value
        correction+=np.where(abs(total)>=abs(value),(total-updated)+value,(value-updated)+total)
        total=updated
    return total+correction

def _constant_half(a,g,order):
    v=g['direction'];length=np.linalg.norm(v,axis=1);mid=a+.5*v;image_mid=mid*[1.,-1.]
    limit=8*np.maximum(length[:,None],length[None])
    near=(np.linalg.norm(mid[:,None]-mid[None],axis=-1)<=limit)|(np.linalg.norm(mid[:,None]-image_mid[None],axis=-1)<=limit)
    value=np.zeros((len(a),len(a)));nodes,weights=leggauss(order)
    # Form compensated relative displacements before quadrature motion.
    # Binary input coordinates are retained without snapping.
    for first in range(0,len(a),128):
        last=min(first+128,len(a));sl=slice(first,last)
        relative=_relative_displacements(g,sl)
        block=value[sl]
        for u,wu in zip((nodes+1)/2,weights/2):
            target_y=a[sl,1]+u*v[sl,1]
            for t,wt in zip((nodes+1)/2,weights/2):
                source_y=a[:,1]+t*v[:,1]
                dx=relative[:,:,0]+t*v[None,:,0]-u*v[sl,None,0]
                dy=relative[:,:,1]+t*v[None,:,1]-u*v[sl,None,1]
                distance=np.where(near[sl],1.,dx*dx+dy*dy)
                block+=wu*wt*.5*np.log1p(4*target_y[:,None]*source_y[None,:]/distance)
    i,j=np.nonzero(near);origin=np.zeros((len(i),2));real=_offsets(g,i,j);image=_offsets(g,i,j,True)
    value[i,j]=kernel.mean_log_pairs(origin,v[i],image,image+v[j]*[1.,-1.],order=order)-kernel.mean_log_pairs(origin,v[i],real,real+v[j],order=order)
    return value

def _weighted_pair(g,i,j,p,q,image=False):
    a=g['direction'][i];b=g['direction'][j].copy();o=_offsets(g,i,j,image)[0]
    if image:b*=np.array([1.,-1.])
    if q==1:
        if not image and g['ends'][j] in (g['starts'][i],g['ends'][i]):
            b=-b;o=np.zeros(2) if g['ends'][j]==g['starts'][i] else a.copy()
        result=power_panel_constant_log(a,b,o,p)
    elif not image and i==j:
        x=power_panel_self_log(math.hypot(*a),p);return x,x
    elif not image and g['starts'][i]==g['starts'][j]:result=power_panel_shared_vertex_log(a,b,p,q)
    else:result=power_panel_separated_log(a,b,o,p,q)
    return result.coarse_mean_log_distance,result.mean_log_distance

def _half(a,b,p,g):
    coarse,fine=_constant_half(a,g,6),_constant_half(a,g,8)
    selected=set(map(int,np.flatnonzero(p<1)))
    for i in sorted(selected):
        for j in range(len(a)):
            try:real=_weighted_pair(g,i,j,p[i],p[j]);image=_weighted_pair(g,i,j,p[i],p[j],True)
            except ValueError as exc:raise ValueError(f'parametric pair {i}/{j}: {exc}') from exc
            coarse[i,j]=image[0]-real[0];fine[i,j]=image[1]-real[1]
            if j not in selected:coarse[j,i]=coarse[i,j];fine[j,i]=fine[i,j]
    return coarse,fine


@dataclass(frozen=True)
class CornerHalfSpaceMatrix:
    """Raw source/target averaged, dimensionless half-space Green matrices.

    The rectangle bounds admit and normalize the geometry; this primitive
    contains the y=0 image only, not upper-plane or side-wall corrections.
    Raw reciprocity is checked before any caller's symmetry averaging.
    """
    geometry: CornerPanelGeometry
    coarse_matrix: np.ndarray
    matrix: np.ndarray
    quadrature_error: float
    reciprocity_error: float

    def __post_init__(self):
        for name in ('coarse_matrix','matrix'):
            object.__setattr__(self,name,_immutable(getattr(self,name)))


def assemble_corner_half_space(polygons, *, width, height, panels_per_edge=32):
    """Assemble normalized power/constant panels above a grounded line.

    Reuse the explicit convex two-ground geometry admission and its 8192
    panel budget. The upper plane and side walls are not in this matrix.
    Integrate each source and target density, using local compensated
    relative coordinates for constant far pairs. Fixed 6/8 Gauss rules and
    the power primitives' independent refinement rules produce coarse/fine
    matrices. Both normalized refinement and raw reciprocity must be at
    most 1e-10; otherwise raise ValueError, without a numerical fallback.
    These checks are not panel, outer-domain or field accuracy estimates.
    """
    geometry=prepare_two_ground_corner_panels(polygons,width=width,height=height,
        panels_per_edge=panels_per_edge)
    a,b=geometry.normalized_starts,geometry.normalized_ends
    g=dict(anchor=geometry.normalized_anchors,local=geometry.normalized_local_starts,
        direction=geometry.normalized_directions,starts=geometry.endpoint_ids[:,0],
        ends=geometry.endpoint_ids[:,1])
    coarse,fine=_half(a,b,geometry.exponents,g)
    if not np.isfinite(coarse).all() or not np.isfinite(fine).all():
        raise ValueError('corner half-space matrix must be finite')
    scale=float(np.max(abs(fine)))
    if not scale>0:raise ValueError('corner half-space matrix scale must be positive')
    error=float(np.max(abs(fine-coarse))/scale)
    reciprocity=max(float(np.max(abs(m-m.T))/np.max(abs(m))) for m in (coarse,fine))
    if max(error,reciprocity)>1e-10:
        raise ValueError('corner half-space quadrature or reciprocity failed')
    return CornerHalfSpaceMatrix(geometry,coarse,fine,error,reciprocity)


__all__=['CornerHalfSpaceMatrix','assemble_corner_half_space']


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
constant_half = _constant_half
offsets = _offsets
weighted_pair = _weighted_pair
