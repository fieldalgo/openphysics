# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded binary64 residuals with exact-product expansions.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).
"""
import math
import numpy as np

__all__ = ['bounded_dense_residual']


def bounded_dense_residual(matrix,solution,rhs):
    """Return a fresh float64 ``rhs - matrix @ solution`` using product splits.

    Real inputs are converted to float64. Require compatible two-dimensional
    arrays, 1..8192 matrix rows/columns, and 1..16 right-hand columns. Nonzero
    matrix/solution magnitudes must be in [2**-400, 2**400]; right-side
    magnitudes must not exceed 2**900. These explicit bounds keep the Dekker
    splitting and product expansion intermediates normal and finite.
    Sum both product components and the right side with ``math.fsum``.
    No extended floating-point type, solver, tolerance adjustment or input
    mutation is used. Invalid shapes, complex/nonfinite values and out-of-
    range magnitudes raise ValueError. A small residual is not a condition
    number, forward-error estimate or field convergence certificate.
    """
    values=[]
    for x in (matrix,solution,rhs):
        if np.iscomplexobj(x):raise ValueError('real arrays required')
        value=np.asarray(x,dtype=np.float64)
        if not np.isfinite(value).all():raise ValueError('finite arrays required')
        values.append(value)
    a,x,b=values
    if a.ndim!=2 or x.ndim!=2 or b.ndim!=2 or not 1<=a.shape[0]<=8192 or not 1<=a.shape[1]<=8192 or not 1<=x.shape[1]<=16 or x.shape[0]!=a.shape[1] or b.shape!=(a.shape[0],x.shape[1]):raise ValueError('bounded compatible matrices required')
    for v in (a,x):
        nonzero=abs(v[v!=0])
        if np.any((nonzero<2.**-400)|(nonzero>2.**400)):raise ValueError('product inputs outside 2^-400..2^400')
    if np.any(abs(b)>2.**900):raise ValueError('right side exceeds 2^900')
    def split(v):
        t=(2.**27+1)*v;hi=t-(t-v);return hi,v-hi
    xh,xl=split(x);result=np.empty_like(b)
    for first in range(0,len(a),32):
        last=min(first+32,len(a));aa=a[first:last];ah,al=split(aa)
        product=aa[:,:,None]*x[None]
        error=al[:,:,None]*xl[None]-(((product-ah[:,:,None]*xh[None])-al[:,:,None]*xh[None])-ah[:,:,None]*xl[None])
        for row in range(last-first):
            for j in range(x.shape[1]):
                result[first+row,j]=math.fsum(np.concatenate(([b[first+row,j]],-product[row,:,j],-error[row,:,j])))
    return result
