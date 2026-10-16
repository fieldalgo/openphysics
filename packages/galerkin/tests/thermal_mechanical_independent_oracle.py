# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent continuum/polynomial oracle; no production or refsol imports.

Preparation only: no mesh PDE solve, workflow driver or acceptance adapter.
Engineering strain is (exx,eyy,gamma_xy). Tensor shear is gamma_xy/2.
"""
import numpy as np

E0,NU0,ALPHA0,TREF0,K0=70e9,.3,12e-6,293.15,10.
LEVELS=(8,16,32,64)


def parent_state(strain,temperature,plane,*,young=E0,nu=NU0,alpha=ALPHA0,tref=TREF0):
    """Eliminate z directly in the original 3D isotropic law."""
    e=np.asarray(strain,dtype=float);a=alpha*(np.asarray(temperature,dtype=float)-tref)
    shape=np.broadcast_shapes(e.shape[:-1],a.shape)
    e=np.broadcast_to(e,(*shape,3));a=np.broadcast_to(a,shape)
    mu=young/(2*(1+nu));lam=young*nu/((1+nu)*(1-2*nu))
    total=np.zeros((*shape,3,3));total[...,0,0]=e[...,0];total[...,1,1]=e[...,1]
    total[...,0,1]=total[...,1,0]=e[...,2]/2
    if plane=='stress':
        total[...,2,2]=((2*mu+3*lam)*a-lam*(e[...,0]+e[...,1]))/(2*mu+lam)
    elif plane!='strain':raise ValueError('explicit stress/strain plane required')
    thermal=a[...,None,None]*np.eye(3);elastic=total-thermal
    trace=np.trace(elastic,axis1=-2,axis2=-1)
    sigma=2*mu*elastic+lam*trace[...,None,None]*np.eye(3)
    psi=mu*np.sum(elastic*elastic,axis=(-2,-1))+.5*lam*trace*trace
    return dict(total=total,thermal=thermal,elastic=elastic,stress=sigma,energy=psi)


def inplane(tensor):
    return np.stack((tensor[...,0,0],tensor[...,1,1],tensor[...,0,1]),axis=-1)


def tangent_from_parent(plane,*,young=E0,nu=NU0):
    """Unit-strain probes of the parent law, never a copied reduced helper."""
    return inplane(parent_state(np.eye(3),np.full(3,TREF0),plane,young=young,nu=nu)['stress']).T


def exact_fields(points,kind,plane,*,young=E0,nu=NU0,alpha=ALPHA0,tref=TREF0,
                 conductivity=K0,theta=20.,theta0=10.,gradient=20.,lengths=(1.,1.),
                 amplitudes=(1e-4,.6e-4)):
    p=np.asarray(points);x,y=np.moveaxis(p,-1,0);shape=x.shape
    lx,ly=lengths;factor=1. if plane=='stress' else 1+nu
    body=np.zeros((*shape,2));source=np.zeros(shape)
    if kind in ('uniform','constrained_uniform'):
        temperature=np.full(shape,tref+theta);gt=np.zeros_like(p)
        if kind=='uniform':
            u=factor*alpha*theta*p;gu=np.broadcast_to(factor*alpha*theta*np.eye(2),(*shape,2,2))
        else:u=np.zeros_like(p);gu=np.zeros((*shape,2,2))
    elif kind=='linear':
        temperature=tref+theta0+gradient*x;gt=np.broadcast_to([gradient,0.],p.shape)
        a0,b=alpha*theta0,alpha*gradient
        u=factor*np.stack((a0*x+.5*b*(x*x-y*y),a0*y+b*x*y),axis=-1)
        gu=factor*np.stack((a0+b*x,-b*y,b*y,a0+b*x),axis=-1).reshape((*shape,2,2))
    elif kind=='sine':
        kx,ky=np.pi/lx,np.pi/ly;ax,ay=amplitudes
        sx,cx,sy,cy=np.sin(kx*x),np.cos(kx*x),np.sin(ky*y),np.cos(ky*y)
        s,c=sx*sy,cx*cy;dx,dy=kx*cx*sy,ky*sx*cy
        temperature=tref+theta*s;gt=theta*np.stack((dx,dy),axis=-1)
        u=np.stack((ax*s,ay*s),axis=-1)
        gu=np.stack((ax*dx,ax*dy,ay*dx,ay*dy),axis=-1).reshape((*shape,2,2))
        source=conductivity*theta*(kx*kx+ky*ky)*s
        d=tangent_from_parent(plane,young=young,nu=nu)
        thermal_probe=parent_state(np.zeros(3),tref+1.,plane,young=young,nu=nu,alpha=alpha,tref=tref)
        beta=-thermal_probe['stress'][0,0]
        cxx,cxy,shear=d[0,0],d[0,1],d[2,2]
        body=np.stack((ax*(cxx*kx*kx+shear*ky*ky)*s-(cxy+shear)*ay*kx*ky*c+beta*theta*dx,
                       ay*(shear*kx*kx+cxx*ky*ky)*s-(cxy+shear)*ax*kx*ky*c+beta*theta*dy),axis=-1)
    else:raise ValueError(kind)
    strain=np.stack((gu[...,0,0],gu[...,1,1],gu[...,0,1]+gu[...,1,0]),axis=-1)
    state=parent_state(strain,temperature,plane,young=young,nu=nu,alpha=alpha,tref=tref)
    return dict(temperature=temperature,temperature_gradient=gt,heat_source=source,
                heat_flux=-conductivity*gt,displacement=u,gradient=gu,strain=strain,
                body_force=body,state=state)


def triangle_rule(vertices,order=8):
    """Independent polynomial coordinates/Duffy weights; not a mesh solver."""
    vertices=np.asarray(vertices);z,w=np.polynomial.legendre.leggauss(order)
    z,w=(z+1)/2,w/2;a,b=np.meshgrid(z,z,indexing='ij')
    bary=np.stack((1-a,a*(1-b),a*b),axis=-1).reshape(-1,3)
    det=np.abs(np.linalg.det(vertices[...,1:,:]-vertices[...,:1,:]))
    points=np.einsum('qa,...ad->...qd',bary,vertices)
    weights=det[...,None]*(w[:,None]*w[None,:]*a).ravel()
    v=np.concatenate((np.ones((*vertices.shape[:-1],1)),vertices),axis=-1)
    grad=np.linalg.inv(v)[...,1:,:].swapaxes(-1,-2)
    return bary,weights,points,grad


def rigid_fit(points,weights,error):
    """Mass-weighted additive translation/infinitesimal rotation only."""
    p=np.asarray(points).reshape(-1,2);w=np.asarray(weights).reshape(-1)
    du=np.asarray(error).reshape(-1,2);center=np.einsum('q,qi->i',w,p)/w.sum()
    basis=np.zeros((len(p),2,3));basis[:,0,0]=1;basis[:,1,1]=1
    basis[:,0,2]=-(p[:,1]-center[1]);basis[:,1,2]=p[:,0]-center[0]
    mass=np.einsum('q,qik,qil->kl',w,basis,basis)
    rhs=np.einsum('q,qik,qi->k',w,basis,du)
    coefficients=np.linalg.solve(mass,rhs)
    residual=du-np.einsum('qik,k->qi',basis,coefficients)
    return residual.reshape(np.asarray(error).shape),coefficients


def thermal_dual_density(delta_temperature,plane,*,young=E0,nu=NU0,alpha=ALPHA0):
    """Squared D^{-1/2} thermal-stress norm from the original parent law."""
    d=tangent_from_parent(plane,young=young,nu=nu)
    delta=-inplane(parent_state(np.zeros(3),TREF0+np.asarray(delta_temperature),plane,
                                young=young,nu=nu,alpha=alpha)['stress'])
    compliance=np.linalg.solve(d,delta[...,None])[...,0]
    return np.sum(delta*compliance,axis=-1)


def immutable_temperature_witness(values):
    """Mathematical copy/lifetime witness only; not the production snapshot."""
    a=np.asarray(values,dtype='<f8')
    return np.frombuffer(a.tobytes(),dtype='<f8').reshape(a.shape)
