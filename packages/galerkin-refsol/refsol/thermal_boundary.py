# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent polynomial boundary references; no FEM/solver imports.

For -k*T''=Q on [0,L], T=a+b*x-Q*x*x/(2*k). Outward fluxes
are k*b at x=0 and Q*L-k*b at x=L. All temperatures are mathematical K.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class BoundarySlab:
    """Closed-form coefficients in SI; flux rates are densities W/m^2."""
    length: float
    conductivity: float
    heat_source: float
    a: float
    b: float

    def temperature(self, points):
        x = np.asarray(points)[..., 0]
        return self.a+self.b*x-self.heat_source*x*x/(2*self.conductivity)

    def heat_flux(self, points):
        x = np.asarray(points)[..., 0]
        return np.stack((-self.conductivity*self.b+self.heat_source*x,
                         np.zeros_like(x)), axis=-1)

    @property
    def outward_fluxes(self):
        return (self.conductivity*self.b,
                self.heat_source*self.length-self.conductivity*self.b)


def _inputs(length, conductivity, heat_source, *values):
    for value in (length, conductivity, heat_source, *values):
        a = np.asarray(value)
        if a.shape != () or a.dtype.kind not in 'iuf' or not np.isfinite(a):
            raise ValueError('reference parameters must be finite real scalars')
    if length <= 0 or conductivity <= 0:
        raise ValueError('length and conductivity must be positive')


def dirichlet_robin_slab(*, length, conductivity, left_temperature,
                         heat_source=0., outward_flux=0., h=0., ambient=300.):
    """Left prescribed T, right outward g+h*(T-ambient); h=0 is flux-only."""
    _inputs(length, conductivity, heat_source, left_temperature, outward_flux, h, ambient)
    if h < 0:
        raise ValueError('h must be nonnegative')
    L, k, Q = length, conductivity, heat_source
    right = ambient+(left_temperature-ambient+Q*L*L/(2*k)-outward_flux*L/k)/(1+h*L/k)
    b = (right-left_temperature+Q*L*L/(2*k))/L
    return BoundarySlab(L, k, Q, left_temperature, b)


def robin_only_slab(*, length, conductivity, left_h, right_h,
                    left_ambient=300., right_ambient=300., heat_source=0.,
                    left_outward=0., right_outward=0.):
    """Both ends Robin/additive flux; at least one strictly positive h.

    Conservation F0+FL=Q*L and the two endpoint temperature jumps determine
    absolute temperature. Pure Neumann remains nonunique even if compatible.
    """
    _inputs(length, conductivity, heat_source, left_h, right_h,
            left_ambient, right_ambient, left_outward, right_outward)
    if left_h < 0 or right_h < 0 or left_h+right_h == 0:
        raise ValueError('nonnegative h and at least one positive Robin boundary required')
    L, k, Q = length, conductivity, heat_source
    if left_h == 0:
        F0 = left_outward
        right = right_ambient+(Q*L-F0-right_outward)/right_h
        a = right-F0*L/k+Q*L*L/(2*k)
    else:
        if right_h == 0:
            F0 = Q*L-right_outward
        else:
            F0 = (right_ambient-left_ambient+(Q*L-right_outward)/right_h
                  +left_outward/left_h+Q*L*L/(2*k))/(L/k+1/left_h+1/right_h)
        a = left_ambient+(F0-left_outward)/left_h
    return BoundarySlab(L, k, Q, a, F0/k)


def sine_temperature(points):
    """T=300+sin(pi*x)sin(pi*y), independently differentiated below."""
    p=np.asarray(points);x,y=p[...,0],p[...,1]
    return 300+np.sin(np.pi*x)*np.sin(np.pi*y)


def sine_flux(points, conductivity=2.5):
    p=np.asarray(points);x,y=p[...,0],p[...,1]
    return -conductivity*np.pi*np.stack((np.cos(np.pi*x)*np.sin(np.pi*y),
                                        np.sin(np.pi*x)*np.cos(np.pi*y)),axis=-1)


def sine_source(points, conductivity=2.5):
    p=np.asarray(points)
    return 2*conductivity*np.pi**2*np.sin(np.pi*p[...,0])*np.sin(np.pi*p[...,1])
