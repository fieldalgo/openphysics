# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Original 3D law and analytic fields; no production/refsol helper imports."""
import numpy as np

E, NU, ALPHA, TREF, K = 70e9, .3, 12e-6, 293.15, 10.
MU=E/(2*(1+NU));LAM=E*NU/((1+NU)*(1-2*NU))

def material(plane):
    le=E*NU/(1-NU**2) if plane=='stress' else LAM
    d=np.array([[le+2*MU,le,0],[le,le+2*MU,0],[0,0,MU]])
    return le,d,E*ALPHA/(1-NU if plane=='stress' else 1-2*NU)


def parent(strain,temperature,plane):
    a=ALPHA*(temperature-TREF)
    z=((1+NU)*a-NU*(strain[...,0]+strain[...,1]))/(1-NU) if plane=='stress' else np.zeros_like(a)
    elastic=np.zeros((*a.shape,3,3))
    elastic[...,0,0]=strain[...,0]-a;elastic[...,1,1]=strain[...,1]-a;elastic[...,2,2]=z-a
    elastic[...,0,1]=elastic[...,1,0]=strain[...,2]/2
    trace=np.trace(elastic,axis1=-2,axis2=-1)
    stress=2*MU*elastic+LAM*trace[...,None,None]*np.eye(3)
    energy=MU*np.sum(elastic**2,axis=(-2,-1))+.5*LAM*trace**2
    return stress,energy


def field(p,kind,plane):
    x,y=p[...,0],p[...,1];shape=x.shape
    if kind=='sine':
        sx,sy,cx,cy=np.sin(np.pi*x),np.sin(np.pi*y),np.cos(np.pi*x),np.cos(np.pi*y)
        s=sx*sy;gx=np.pi*cx*sy;gy=np.pi*sx*cy
        temp=TREF+20*s;tg=20*np.stack([gx,gy],axis=-1)
        u=np.stack([1e-4*s,.6e-4*s],axis=-1)
        gu=np.stack([1e-4*gx,1e-4*gy,.6e-4*gx,.6e-4*gy],axis=-1).reshape(*shape,2,2)
    elif kind=='linear':
        temp=TREF+10+20*x;tg=np.broadcast_to([20.,0.],p.shape)
        f=1 if plane=='stress' else 1+NU;a0,p0=ALPHA*10,ALPHA*20
        u=f*np.stack([a0*x+.5*p0*(x*x-y*y),a0*y+p0*x*y],axis=-1)
        gu=f*np.stack([a0+p0*x,-p0*y,p0*y,a0+p0*x],axis=-1).reshape(*shape,2,2)
    else:
        temp=np.full(shape,TREF+20);tg=np.zeros_like(p)
        f=1 if plane=='stress' else 1+NU;u=f*ALPHA*20*p
        gu=np.broadcast_to(f*ALPHA*20*np.eye(2),(*shape,2,2))
    e=np.stack([gu[...,0,0],gu[...,1,1],gu[...,0,1]+gu[...,1,0]],axis=-1)
    return temp,tg,u,gu,e


def body(p,plane):
    x,y=p.T;s=np.sin(np.pi*x)*np.sin(np.pi*y);c=np.cos(np.pi*x)*np.cos(np.pi*y)
    le,d,beta=material(plane)
    result=np.pi**2*np.column_stack([(le+3*MU)*1e-4*s-(le+MU)*.6e-4*c,
                                    (le+3*MU)*.6e-4*s-(le+MU)*1e-4*c])
    result+=beta*20*np.pi*np.column_stack([np.cos(np.pi*x)*np.sin(np.pi*y),np.sin(np.pi*x)*np.cos(np.pi*y)])
    return result


def geometry(mesh,order=8):
    s,w=np.polynomial.legendre.leggauss(order);s,w=(s+1)/2,w/2
    a,b=np.meshgrid(s,s,indexing='ij')
    bary=np.stack([1-a,a*(1-b),a*b],axis=-1).reshape(-1,3)
    weights=(w[:,None]*w[None,:]*a).ravel()
    vertices=mesh.nodes[mesh.triangles]
    det=np.linalg.det(vertices[:,1:]-vertices[:,:1])
    grad=np.linalg.inv(np.concatenate([np.ones((*vertices.shape[:2],1)),vertices],axis=-1))[:,1:,:].swapaxes(1,2)
    return bary,det[:,None]*weights,np.einsum('qn,tnd->tqd',bary,vertices),grad

