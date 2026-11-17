# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent original-3D-law oracles for a prescribed Kelvin mechanical stage.

No FEM engine/helper imports. Coordinates/displacement m; T K; alpha 1/K;
stress/E Pa; force density N/m^3; physical energy density J/m^3.
Keyword-only registry names after the leading positional ``points``: youngs_modulus,
poisson_ratio, plane, stress_free_temperature (T_ref) and linear_expansion_coefficient
(alpha); temperature_change is T - T_ref, temperature_difference an amplitude. A str for a
quantity raises TypeError.
"""
from dataclasses import dataclass
import numpy as np

from ._checks import pair, refuse_text

__all__ = ["ThermoelasticState", "state_from_3d", "ThermoelasticField", "uniform_free",
           "uniform_constrained", "linear_temperature", "sine_manufactured"]


def _real(value,name):
    refuse_text(**{name: value})
    a=np.asarray(value)
    if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be finite and real")
    return a.astype(float)


def _parameters(youngs_modulus,poisson_ratio,plane,stress_free_temperature,linear_expansion_coefficient):
    vals=[_real(v,n) for v,n in zip((youngs_modulus,poisson_ratio,stress_free_temperature,linear_expansion_coefficient),
                                   ("youngs_modulus","poisson_ratio","stress_free_temperature",
                                    "linear_expansion_coefficient"))]
    if any(v.shape!=() for v in vals):raise ValueError("material/reference inputs must be scalars")
    e,nu,tref,alpha=map(float,vals)
    if e<=0 or not -1<nu<.5 or tref<0 or plane not in ("stress","strain"):
        raise ValueError("require youngs_modulus>0, -1<poisson_ratio<.5, stress_free_temperature>=0K, "
                         "plane stress/strain")
    return e,nu,tref,alpha,e/(2*(1+nu)),e*nu/((1+nu)*(1-2*nu))


def _points(points):
    p=_real(points,"points")
    if p.ndim!=2 or p.shape[1]!=2:raise ValueError("points must have shape (Q,2)")
    return p


@dataclass
class ThermoelasticState:
    thermal_strain: np.ndarray
    elastic_strain: np.ndarray
    stress: np.ndarray
    stress_zz: np.ndarray
    strain_zz: np.ndarray
    strain_energy_density: np.ndarray


def state_from_3d(*,strain,temperature,youngs_modulus,poisson_ratio,plane,
                  stress_free_temperature,linear_expansion_coefficient):
    """Use physical 3D thermal eigenstrain, imposing total sigma_zz=0 or ezz=0.

    strain: (Q,3) total engineering strain; temperature: (Q,) absolute K.
    """
    e,nu,tref,alpha,mu,lam=_parameters(youngs_modulus,poisson_ratio,plane,stress_free_temperature,
                                       linear_expansion_coefficient)
    eps=_real(strain,"strain");temp=_real(temperature,"temperature")
    if eps.ndim!=2 or eps.shape[1]!=3 or temp.shape!=(len(eps),) or np.any(temp<0):
        raise ValueError("require engineering strain(Q,3), absolute temperature(Q,) >=0K")
    a=alpha*(temp-tref)
    ex,ey,gamma=eps.T
    z=((1+nu)*a-nu*(ex+ey))/(1-nu) if plane=="stress" else np.zeros(len(a))
    trace=ex+ey+z-3*a
    stress=np.column_stack([2*mu*(ex-a)+lam*trace,2*mu*(ey-a)+lam*trace,mu*gamma])
    zz=2*mu*(z-a)+lam*trace
    density=mu*((ex-a)**2+(ey-a)**2+(z-a)**2+.5*gamma**2)+.5*lam*trace**2
    th=np.column_stack([a,a,np.zeros(len(a))])
    return ThermoelasticState(th,eps-th,stress,zz,z,density)


@dataclass
class ThermoelasticField:
    displacement: np.ndarray
    displacement_gradient: np.ndarray
    temperature: np.ndarray
    temperature_gradient: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    stress_zz: np.ndarray
    strain_zz: np.ndarray
    strain_energy_density: np.ndarray
    body_force_density: np.ndarray


def _field(u,gradient,temp,temp_gradient,body,**material):
    strain=np.column_stack([gradient[:,0,0],gradient[:,1,1],gradient[:,0,1]+gradient[:,1,0]])
    state=state_from_3d(strain=strain,temperature=temp,**material)
    return ThermoelasticField(u,gradient,temp,temp_gradient,strain,state.stress,
                              state.stress_zz,state.strain_zz,state.strain_energy_density,body)


def uniform_free(points,*,temperature_change,youngs_modulus,poisson_ratio,plane,
                 stress_free_temperature,linear_expansion_coefficient):
    """Free expansion under the uniform temperature change T - T_ref = temperature_change."""
    p=_points(points)
    e,nu,tref,alpha,_,_=_parameters(youngs_modulus,poisson_ratio,plane,stress_free_temperature,
                                    linear_expansion_coefficient)
    theta=_real(temperature_change,"temperature_change")
    if theta.shape!=():raise ValueError("temperature_change must be scalar")
    factor=1 if plane=="stress" else 1+nu
    gradient=np.tile(factor*alpha*theta*np.eye(2),(len(p),1,1))
    return _field(factor*alpha*theta*p,gradient,np.full(len(p),tref+theta),np.zeros_like(p),np.zeros_like(p),
        youngs_modulus=e,poisson_ratio=nu,plane=plane,stress_free_temperature=tref,linear_expansion_coefficient=alpha)


def uniform_constrained(points,*,temperature_change,youngs_modulus,poisson_ratio,plane,
                        stress_free_temperature,linear_expansion_coefficient):
    """Fully constrained (u = 0) under the uniform temperature change T - T_ref = temperature_change."""
    p=_points(points)
    e,nu,tref,alpha,_,_=_parameters(youngs_modulus,poisson_ratio,plane,stress_free_temperature,
                                    linear_expansion_coefficient)
    theta=_real(temperature_change,"temperature_change")
    if theta.shape!=():raise ValueError("temperature_change must be scalar")
    return _field(np.zeros_like(p),np.zeros((len(p),2,2)),np.full(len(p),tref+theta),np.zeros_like(p),np.zeros_like(p),
        youngs_modulus=e,poisson_ratio=nu,plane=plane,stress_free_temperature=tref,linear_expansion_coefficient=alpha)


def linear_temperature(points,*,temperature_change,temperature_gradient,youngs_modulus,poisson_ratio,
                       plane,stress_free_temperature,linear_expansion_coefficient):
    """Free expansion under T - T_ref = temperature_change + temperature_gradient * x.

    temperature_change is the change at x = 0 (K) and temperature_gradient the scalar
    dT/dx (K/m); the temperature varies along x only.
    """
    p=_points(points)
    e,nu,tref,alpha,_,_=_parameters(youngs_modulus,poisson_ratio,plane,stress_free_temperature,
                                    linear_expansion_coefficient)
    theta0,g=_real(temperature_change,"temperature_change"),_real(temperature_gradient,"temperature_gradient")
    if theta0.shape!=() or g.shape!=():raise ValueError("linear temperature parameters must be scalar")
    x,y=p.T;a0,slope=alpha*theta0,alpha*g
    factor=1 if plane=="stress" else 1+nu
    u=factor*np.column_stack([a0*x+.5*slope*(x*x-y*y),a0*y+slope*x*y])
    gradient=np.empty((len(p),2,2));gradient[:,0,0]=gradient[:,1,1]=factor*(a0+slope*x)
    gradient[:,0,1]=-factor*slope*y;gradient[:,1,0]=factor*slope*y
    return _field(u,gradient,tref+theta0+g*x,np.tile([g,0.],(len(p),1)),np.zeros_like(p),
        youngs_modulus=e,poisson_ratio=nu,plane=plane,stress_free_temperature=tref,linear_expansion_coefficient=alpha)


def sine_manufactured(points,*,youngs_modulus,poisson_ratio,plane,stress_free_temperature,
                       linear_expansion_coefficient,temperature_difference,displacement,length):
    """Manufactured field on the rectangle [0,Lx]x[0,Ly] with sin(pi x/Lx) sin(pi y/Ly) shapes.

    temperature_difference is the amplitude of T - T_ref (K), displacement the pair of
    displacement amplitudes (a, b) in m, and length the pair (Lx, Ly) in m.
    """
    refuse_text(displacement=displacement,length=length)
    p=_points(points)
    e,nu,tref,alpha,mu,lam=_parameters(youngs_modulus,poisson_ratio,plane,stress_free_temperature,
                                       linear_expansion_coefficient)
    lengths=_real(pair(length,"length"),"length");amps=_real(pair(displacement,"displacement"),"displacement")
    theta=_real(temperature_difference,"temperature_difference")
    if lengths.shape!=(2,) or np.any(lengths<=0) or amps.shape!=(2,) or theta.shape!=():
        raise ValueError("require positive length(2,), displacement(2,), scalar temperature_difference")
    kx,ky=np.pi/lengths
    x,y=p[:,0]*kx,p[:,1]*ky
    sx,sy,cx,cy=np.sin(x),np.sin(y),np.cos(x),np.cos(y)
    s,c=sx*sy,cx*cy;a,b=amps
    u=np.column_stack([a*s,b*s]);gradient=np.empty((len(p),2,2))
    gradient[:,0,0]=a*kx*cx*sy;gradient[:,0,1]=a*ky*sx*cy
    gradient[:,1,0]=b*kx*cx*sy;gradient[:,1,1]=b*ky*sx*cy
    tg=theta*np.column_stack([kx*cx*sy,ky*sx*cy])
    le=e*nu/(1-nu*nu) if plane=="stress" else lam
    beta=e*alpha/(1-nu if plane=="stress" else 1-2*nu)
    body=np.column_stack([a*((le+2*mu)*kx*kx+mu*ky*ky)*s-(le+mu)*b*kx*ky*c,
                          b*(mu*kx*kx+(le+2*mu)*ky*ky)*s-(le+mu)*a*kx*ky*c])+beta*tg
    return _field(u,gradient,tref+theta*s,tg,body,youngs_modulus=e,poisson_ratio=nu,plane=plane,
                  stress_free_temperature=tref,linear_expansion_coefficient=alpha)
