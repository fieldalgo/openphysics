# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Self integrals for three static radial-density modes.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).
"""
from functools import lru_cache
import math
import numpy as np
from scipy.special import zeta
from galerkin.laplace_corner import length as _length, power as _power, frozen as _frozen
from galerkin.laplace_corner_harmonic import power_panel_harmonic_gram, power_panel_harmonic_self_log


__all__ = ["power_panel_quadratic_gram", "power_panel_quadratic_self_log"]

def power_panel_quadratic_gram(length, exponent):
    """Immutable physical 3x3 current Gram in inverse metres.

    rho_a(s)=a/h*(s/h)**(a-1); the modes are rho_p,
    sqrt(3)*(rho_2p-rho_p), sqrt(5)*(2*rho_3p-3*rho_2p+rho_p).
    Their masses are [1,0,0]. Require finite positive h and 0.5<p<=1.
    The upper2x2 block is the existing harmonic primitive byte-for-byte.
    No field solve, panel interaction or geometry qualification is implied.
    """
    h,p=_length(length),_power(exponent)
    result=np.empty((3,3));result[:2,:2]=power_panel_harmonic_gram(h,p)
    zero=result[0,0]
    result[0,2]=result[2,0]=zero*(-math.sqrt(5)*(p-1)/((3*p-1)*(4*p-1)))
    result[1,2]=result[2,1]=zero*(math.sqrt(15)*(p-1)*(8*p*p-3*p+1)/((3*p-1)*(4*p-1)*(5*p-1)))
    polynomial=(((72*p-78)*p+35)*p-6)*p+1
    result[2,2]=zero*(5*polynomial/((3*p-1)*(4*p-1)*(5*p-1)*(6*p-1)))
    if not np.isfinite(result).all() or result[2,2]<=0 or (p!=1 and (result[0,2]==0 or result[1,2]==0)):
        raise ValueError('quadratic radial squared-current Gram is not representable')
    return _frozen(result).reshape(3,3)


@lru_cache(maxsize=1)
def _coefficients():
    def moment(i,j,r):
        return (i*j**r*float(zeta(r+1,j+1))+j*i**r*float(zeta(r+1,i+1))-1)/(i+j)
    result=[]
    for r in range(1,65):
        a,b,c,d,e,f=(moment(i,j,r) for i,j in [(1,1),(1,2),(1,3),(2,2),(2,3),(3,3)])
        result.append((math.fsum([a,-3*b,2*c]),
                       math.fsum([-a,4*b,-2*c,-3*d,2*e]),
                       math.fsum([a,-6*b,4*c,9*d,-12*e,4*f])))
    return tuple(result)


def power_panel_quadratic_self_log(length, exponent):
    """Immutable 3x3 self integral of log(|s-t| / 1 metre).

    Use the same physical modes and ordering as power_panel_quadratic_gram.
    Only00 changes with length. The existing upper2x2 block is unchanged.
    New entries use64 Taylor coefficients aboutp=1. On0.5<p<=1 their
    omitted scalar tail is below180*2**-64; roundoff is separate. Exact
    uniform parity makes12 zero; nearby nonzero values are not snapped.
    Interactions and field solving require separate validation.
    """
    h,p=_length(length),_power(exponent);delta=1-p
    result=np.empty((3,3));result[:2,:2]=power_panel_harmonic_self_log(h,p)
    series=[delta*math.fsum(row[k]*delta**r for r,row in enumerate(_coefficients())) for k in range(3)]
    result[0,2]=result[2,0]=math.sqrt(5)*(1/12+series[0])
    result[1,2]=result[2,1]=math.sqrt(15)*series[1]
    result[2,2]=5*(-1/12+series[2])
    if not np.isfinite(result).all() or (p!=1 and result[1,2]==0):
        raise ValueError('quadratic radial self-log block is not representable')
    return _frozen(result).reshape(3,3)
