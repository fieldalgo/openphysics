# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent original-3D-law oracles for a prescribed Kelvin mechanical stage.

No FEM engine/helper imports. Coordinates/displacement m; T K; alpha 1/K;
stress/E Pa; force density N/m^3; physical energy density J/m^3.
"""
from dataclasses import dataclass
import numpy as np


def _real(value,name):
    a=np.asarray(value)
    if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be finite and real")
    return a.astype(float)


def _parameters(young_modulus,poisson_ratio,plane,reference_temperature_k,thermal_expansion_per_k):
    vals=[_real(v,n) for v,n in zip((young_modulus,poisson_ratio,reference_temperature_k,thermal_expansion_per_k),
                                   ("E","nu","Tref","alpha"))]
    if any(v.shape!=() for v in vals):raise ValueError("material/reference inputs must be scalars")
    e,nu,tref,alpha=map(float,vals)
    if e<=0 or not -1<nu<.5 or tref<0 or plane not in ("stress","strain"):
        raise ValueError("require E>0, -1<nu<.5, Tref>=0K, plane stress/strain")
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
    sigma_zz: np.ndarray
    epsilon_zz: np.ndarray
    energy_density: np.ndarray


def state_from_3d(total_strain,temperature_k,*,young_modulus,poisson_ratio,plane,
                  reference_temperature_k,thermal_expansion_per_k):
    """Use physical 3D thermal eigenstrain, imposing total sigma_zz=0 or ezz=0."""
    e,nu,tref,alpha,mu,lam=_parameters(young_modulus,poisson_ratio,plane,reference_temperature_k,thermal_expansion_per_k)
    eps=_real(total_strain,"total_strain");temp=_real(temperature_k,"temperature_k")
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
    gradient: np.ndarray
    temperature_k: np.ndarray
    temperature_gradient: np.ndarray
    total_strain: np.ndarray
    stress: np.ndarray
    sigma_zz: np.ndarray
    epsilon_zz: np.ndarray
    energy_density: np.ndarray
    body_force: np.ndarray


def _field(u,gradient,temp,temp_gradient,body,**material):
    strain=np.column_stack([gradient[:,0,0],gradient[:,1,1],gradient[:,0,1]+gradient[:,1,0]])
    state=state_from_3d(strain,temp,**material)
    return ThermoelasticField(u,gradient,temp,temp_gradient,strain,state.stress,
                              state.sigma_zz,state.epsilon_zz,state.energy_density,body)


def uniform_free(points,temperature_difference_k=20.,*,young_modulus,poisson_ratio,plane,
                 reference_temperature_k,thermal_expansion_per_k):
    p=_points(points)
    e,nu,tref,alpha,_,_=_parameters(young_modulus,poisson_ratio,plane,reference_temperature_k,thermal_expansion_per_k)
    theta=_real(temperature_difference_k,"temperature difference")
    if theta.shape!=():raise ValueError("temperature difference must be scalar")
    factor=1 if plane=="stress" else 1+nu
    gradient=np.tile(factor*alpha*theta*np.eye(2),(len(p),1,1))
    return _field(factor*alpha*theta*p,gradient,np.full(len(p),tref+theta),np.zeros_like(p),np.zeros_like(p),
        young_modulus=e,poisson_ratio=nu,plane=plane,reference_temperature_k=tref,thermal_expansion_per_k=alpha)


def uniform_constrained(points,temperature_difference_k=20.,*,young_modulus,poisson_ratio,plane,
                        reference_temperature_k,thermal_expansion_per_k):
    p=_points(points)
    e,nu,tref,alpha,_,_=_parameters(young_modulus,poisson_ratio,plane,reference_temperature_k,thermal_expansion_per_k)
    theta=_real(temperature_difference_k,"temperature difference")
    if theta.shape!=():raise ValueError("temperature difference must be scalar")
    return _field(np.zeros_like(p),np.zeros((len(p),2,2)),np.full(len(p),tref+theta),np.zeros_like(p),np.zeros_like(p),
        young_modulus=e,poisson_ratio=nu,plane=plane,reference_temperature_k=tref,thermal_expansion_per_k=alpha)


def linear_temperature(points,offset_k=10.,gradient_k_per_m=20.,*,young_modulus,poisson_ratio,
                       plane,reference_temperature_k,thermal_expansion_per_k):
    p=_points(points)
    e,nu,tref,alpha,_,_=_parameters(young_modulus,poisson_ratio,plane,reference_temperature_k,thermal_expansion_per_k)
    theta0,g=_real(offset_k,"offset_k"),_real(gradient_k_per_m,"gradient_k_per_m")
    if theta0.shape!=() or g.shape!=():raise ValueError("linear temperature parameters must be scalar")
    x,y=p.T;a0,slope=alpha*theta0,alpha*g
    factor=1 if plane=="stress" else 1+nu
    u=factor*np.column_stack([a0*x+.5*slope*(x*x-y*y),a0*y+slope*x*y])
    gradient=np.empty((len(p),2,2));gradient[:,0,0]=gradient[:,1,1]=factor*(a0+slope*x)
    gradient[:,0,1]=-factor*slope*y;gradient[:,1,0]=factor*slope*y
    return _field(u,gradient,tref+theta0+g*x,np.tile([g,0.],(len(p),1)),np.zeros_like(p),
        young_modulus=e,poisson_ratio=nu,plane=plane,reference_temperature_k=tref,thermal_expansion_per_k=alpha)


def sine_manufactured(points,*,young_modulus,poisson_ratio,plane,reference_temperature_k,
                       thermal_expansion_per_k,temperature_amplitude_k=20.,
                       displacement_amplitudes_m=(1e-4,.6e-4),lengths_m=(1.,1.)):
    p=_points(points)
    e,nu,tref,alpha,mu,lam=_parameters(young_modulus,poisson_ratio,plane,reference_temperature_k,thermal_expansion_per_k)
    lengths=_real(lengths_m,"lengths_m");amps=_real(displacement_amplitudes_m,"displacement amplitudes")
    theta=_real(temperature_amplitude_k,"temperature amplitude")
    if lengths.shape!=(2,) or np.any(lengths<=0) or amps.shape!=(2,) or theta.shape!=():
        raise ValueError("require positive lengths(2,), amplitudes(2,), scalar temperature amplitude")
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
    return _field(u,gradient,tref+theta*s,tg,body,young_modulus=e,poisson_ratio=nu,plane=plane,
                  reference_temperature_k=tref,thermal_expansion_per_k=alpha)
