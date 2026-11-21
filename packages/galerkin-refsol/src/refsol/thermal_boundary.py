# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent polynomial boundary references; no FEM/solver imports.

For -k*T''=Q on [0,L], T=a+b*x-Q*x*x/(2*k). Outward heat fluxes (positive
leaves the body) are k*b at x=0 and Q*L-k*b at x=L. All temperatures are
mathematical K. Inputs are keyword-only SI registry names; the heat flux a
boundary is given is the inward one (positive enters the body), negated once as
0.0 - x for the outward algebra. A str for a quantity raises TypeError.
"""
from dataclasses import dataclass
import numpy as np

from ._checks import pair, refuse_text

__all__ = ["BoundarySlab", "dirichlet_robin_slab", "robin_only_slab", "sine_temperature",
           "sine_flux", "sine_source"]


@dataclass(frozen=True)
class BoundarySlab:
    """Closed-form coefficients in SI (a in K, b in K/m); flux rates are densities W/m^2."""
    length: float
    thermal_conductivity: float
    heat_source_density: float
    a: float
    b: float

    def temperature(self, points):
        x = np.asarray(points)[..., 0]
        return self.a+self.b*x-self.heat_source_density*x*x/(2*self.thermal_conductivity)

    def heat_flux(self, points):
        x = np.asarray(points)[..., 0]
        return np.stack((-self.thermal_conductivity*self.b+self.heat_source_density*x,
                         np.zeros_like(x)), axis=-1)

    @property
    def outward_heat_flux(self):
        """The outward heat fluxes (x = 0, x = L) in W/m^2, positive leaving the body."""
        return (self.thermal_conductivity*self.b,
                self.heat_source_density*self.length-self.thermal_conductivity*self.b)


def _inputs(length, conductivity, heat_source, *values):
    for value in (length, conductivity, heat_source, *values):
        a = np.asarray(value)
        if a.shape != () or a.dtype.kind not in 'iuf' or not np.isfinite(a):
            raise ValueError('reference parameters must be finite real scalars')
    if length <= 0 or conductivity <= 0:
        raise ValueError('length and thermal_conductivity must be positive')


def dirichlet_robin_slab(*, length, thermal_conductivity, prescribed_temperature, heat_source_density,
                         inward_heat_flux, heat_transfer_coefficient, ambient_temperature):
    """Prescribed temperature at x=0; at x=L the inward heat flux and convection to ambient.

    The heat leaving at x=L is h*(T-ambient) - inward_heat_flux; heat_transfer_coefficient
    h=0 is flux only (ambient_temperature then still enters the arithmetic, so give it).
    """
    refuse_text(length=length, thermal_conductivity=thermal_conductivity,
                prescribed_temperature=prescribed_temperature, heat_source_density=heat_source_density,
                inward_heat_flux=inward_heat_flux, heat_transfer_coefficient=heat_transfer_coefficient,
                ambient_temperature=ambient_temperature)
    h, ambient = heat_transfer_coefficient, ambient_temperature
    _inputs(length, thermal_conductivity, heat_source_density, prescribed_temperature, inward_heat_flux, h, ambient)
    outward_flux = 0.0 - inward_heat_flux
    if h < 0:
        raise ValueError('heat_transfer_coefficient must be nonnegative')
    L, k, Q = length, thermal_conductivity, heat_source_density
    left_temperature = prescribed_temperature
    right = ambient+(left_temperature-ambient+Q*L*L/(2*k)-outward_flux*L/k)/(1+h*L/k)
    b = (right-left_temperature+Q*L*L/(2*k))/L
    return BoundarySlab(L, k, Q, left_temperature, b)


def robin_only_slab(*, length, thermal_conductivity, heat_transfer_coefficient, ambient_temperature,
                    heat_source_density, inward_heat_flux):
    """Both ends Robin with an additive inward heat flux; at least one strictly positive h.

    heat_transfer_coefficient, ambient_temperature and inward_heat_flux are pairs
    (x = 0, x = L). Conservation F0+FL=Q*L and the two endpoint temperature jumps
    determine absolute temperature. Pure Neumann remains nonunique even if compatible.
    """
    refuse_text(length=length, thermal_conductivity=thermal_conductivity,
                heat_transfer_coefficient=heat_transfer_coefficient, ambient_temperature=ambient_temperature,
                heat_source_density=heat_source_density, inward_heat_flux=inward_heat_flux)
    left_h, right_h = pair(heat_transfer_coefficient, "heat_transfer_coefficient")
    left_ambient, right_ambient = pair(ambient_temperature, "ambient_temperature")
    left_inward, right_inward = pair(inward_heat_flux, "inward_heat_flux")
    _inputs(length, thermal_conductivity, heat_source_density, left_h, right_h,
            left_ambient, right_ambient, left_inward, right_inward)
    left_outward, right_outward = 0.0 - left_inward, 0.0 - right_inward
    if left_h < 0 or right_h < 0 or left_h+right_h == 0:
        raise ValueError('nonnegative h and at least one positive Robin boundary required')
    L, k, Q = length, thermal_conductivity, heat_source_density
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


def sine_flux(points, *, thermal_conductivity):
    refuse_text(thermal_conductivity=thermal_conductivity)
    p=np.asarray(points);x,y=p[...,0],p[...,1]
    return -thermal_conductivity*np.pi*np.stack((np.cos(np.pi*x)*np.sin(np.pi*y),
                                                np.sin(np.pi*x)*np.cos(np.pi*y)),axis=-1)


def sine_source(points, *, thermal_conductivity):
    refuse_text(thermal_conductivity=thermal_conductivity)
    p=np.asarray(points)
    return 2*thermal_conductivity*np.pi**2*np.sin(np.pi*p[...,0])*np.sin(np.pi*p[...,1])
