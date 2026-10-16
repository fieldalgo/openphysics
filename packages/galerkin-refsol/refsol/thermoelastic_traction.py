# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytic total-traction thermoelastic fields from the original 3D law.

NumPy only; no engine, existing reference or assembly helpers. SI, Kelvin,
engineering strain (exx,eyy,gamma_xy); full stress/strain tensors are (Q,3,3).
The polynomial family uses a fixed 1m square, not a general CAD solution.
"""
from dataclasses import dataclass
import numpy as np


def _real(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in 'iuf' or not np.all(np.isfinite(a)):
        raise ValueError(f'{name} must be finite real')
    return a.astype(float)


def _points(points):
    p = _real(points, 'points')
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError('points must have shape (Q,2)')
    return p


def _material(young_modulus, poisson_ratio, plane, thermal_expansion_per_k,
              reference_temperature_k):
    a = [_real(v,n) for v,n in zip((young_modulus,poisson_ratio,
         thermal_expansion_per_k,reference_temperature_k), ('E','nu','alpha','Tref'))]
    if any(v.shape != () for v in a):
        raise ValueError('material/reference inputs must be scalar')
    e,nu,alpha,tref = map(float,a)
    if e <= 0 or not -1 < nu < .5 or tref < 0 or plane not in ('stress','strain'):
        raise ValueError('require E>0, -1<nu<.5, Tref>=0, plane stress/strain')
    return e,nu,alpha,tref,e/(2*(1+nu)),e*nu/((1+nu)*(1-2*nu))


@dataclass
class TractionState:
    displacement: np.ndarray
    gradient: np.ndarray
    temperature_k: np.ndarray
    temperature_gradient: np.ndarray
    total_strain: np.ndarray
    stress: np.ndarray
    energy_density: np.ndarray
    body_force: np.ndarray


def parent_state(strain, temperature_k, *, young_modulus, poisson_ratio, plane,
                 thermal_expansion_per_k, reference_temperature_k):
    """Return full physical stress, energy density and total 3D strain."""
    e,nu,alpha,tref,mu,lam = _material(young_modulus,poisson_ratio,plane,
                                    thermal_expansion_per_k,reference_temperature_k)
    strain = _real(strain,'strain'); t = _real(temperature_k,'temperature_k')
    if strain.ndim != 2 or strain.shape[1] != 3 or t.shape != (len(strain),) or np.any(t<0):
        raise ValueError('strain (Q,3) and nonnegative temperature_k (Q,) required')
    a = alpha*(t-tref)
    total = np.zeros((len(t),3,3))
    total[:,0,0],total[:,1,1] = strain[:,0],strain[:,1]
    total[:,0,1] = total[:,1,0] = strain[:,2]/2
    if plane == 'stress':
        total[:,2,2] = ((2*mu+3*lam)*a-lam*(strain[:,0]+strain[:,1]))/(2*mu+lam)
    elastic = total-a[:,None,None]*np.eye(3)
    tr = np.trace(elastic,axis1=1,axis2=2)
    stress = 2*mu*elastic+lam*tr[:,None,None]*np.eye(3)
    energy = mu*np.sum(elastic**2,axis=(1,2))+.5*lam*tr**2
    if not np.all(np.isfinite(stress)) or not np.all(np.isfinite(energy)):
        raise ValueError('reference state exceeds finite range')
    return stress,energy,total


def traction_from_stress(stress, normals):
    """TOTAL physical sigma*n, global Cartesian Pa, unit normals."""
    n = _points(normals); s = _real(stress,'stress')
    if s.shape != (len(n),3,3) or not np.allclose(np.linalg.norm(n,axis=1),1,atol=1e-10,rtol=0):
        raise ValueError('stress (Q,3,3) and unit normals (Q,2) required')
    return np.einsum('qij,qj->qi',s[:,:2,:2],n)


def uniform_combined(points, *, theta_k=20., applied_stress=(8e6,-2e6,3e6),
                     translation=(2e-5,-1e-5), **material):
    """Affine combined normal/shear/thermal patch with nonzero support work."""
    p = _points(points)
    e,nu,alpha,tref,mu,lam = _material(**material)
    theta = _real(theta_k,'theta_k'); s = _real(applied_stress,'applied_stress')
    c = _real(translation,'translation')
    if theta.shape != () or s.shape != (3,) or c.shape != (2,):
        raise ValueError('theta scalar, stress (3,), translation (2,) required')
    sx,sy,tau = s
    if material['plane'] == 'stress':
        em = np.array([(sx-nu*sy)/e,(sy-nu*sx)/e,2*(1+nu)*tau/e])
        eta = alpha*theta
    else:
        em = np.array([(1+nu)*((1-nu)*sx-nu*sy)/e,
                       (1+nu)*((1-nu)*sy-nu*sx)/e,2*(1+nu)*tau/e])
        eta = (1+nu)*alpha*theta
    strain = np.broadcast_to(em+eta*np.array([1,1,0]),(len(p),3)).copy()
    gradient = np.tile([[strain[0,0] if len(p) else em[0]+eta,em[2]],
                         [0,em[1]+eta]],(len(p),1,1))
    t = np.full(len(p),tref+float(theta))
    stress,energy,total = parent_state(strain,t,**material)
    u = np.einsum('qij,qj->qi',gradient,p)+c
    return TractionState(u,gradient,t,np.zeros_like(p),total,stress,energy,np.zeros_like(p))


def polynomial_manufactured(points, *, linear_temperature=False, **material):
    """Cubic u, quadratic (or linear control) T; translated mixed-boundary MMS."""
    p = _points(points);x,y = p.T
    e,nu,alpha,tref,mu,lam = _material(**material)
    c = 1e-4
    u = c*np.column_stack([x**3+2*x*y*y+x*y,2*x*x*y+y**3+x*x])+[2e-5,-1e-5]
    gradient = c*np.stack([3*x*x+2*y*y+y,4*x*y+x,4*x*y+2*x,2*x*x+3*y*y],axis=-1).reshape(-1,2,2)
    strain = np.column_stack([gradient[:,0,0],gradient[:,1,1],gradient[:,0,1]+gradient[:,1,0]])
    theta = 12+9*x-4*y
    gt = np.column_stack([np.full(len(p),9.),np.full(len(p),-4.)])
    if not linear_temperature:
        theta += 6*x*y+3*y*y
        gt += np.column_stack([6*y,6*x+6*y])
    t = tref+theta
    stress,energy,total = parent_state(strain,t,**material)
    le = e*nu/(1-nu**2) if material['plane']=='stress' else lam
    beta = e*alpha/(1-nu if material['plane']=='stress' else 1-2*nu)
    body = np.column_stack([-10*c*(le+2*mu)*x+beta*gt[:,0],
        -c*(mu*(10*y+2)+(le+mu)*(10*y+1))+beta*gt[:,1]])
    return TractionState(u,gradient,t,gt,total,stress,energy,body)
