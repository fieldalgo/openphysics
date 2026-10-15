# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent quartic/mixed heat oracles and P1 integration; no engine helpers."""
import numpy as np
from scipy.sparse import coo_matrix

LX, LY, K, T0, AMP = .03, .02, 12.5, 293.15, 7.


def rectangle(n, scale=1.):
    x,y=np.meshgrid(np.linspace(0,LX*scale,n+1),np.linspace(0,LY*scale,n+1),indexing='ij')
    nodes=np.column_stack((x.ravel(),y.ravel()))
    a=np.arange((n+1)**2).reshape(n+1,n+1)
    v=[q.ravel() for q in (a[:-1,:-1],a[1:,:-1],a[1:,1:],a[:-1,1:])]
    tris=np.concatenate((np.stack((v[0],v[1],v[2]),axis=1),np.stack((v[0],v[2],v[3]),axis=1)))
    boundary=np.unique(np.r_[a[0],a[-1],a[:,0],a[:,-1]])
    return nodes,tris,{'all':boundary,'left':a[0],'right':a[-1]}


def field(points, case='quartic'):
    x,y=np.asarray(points).T
    if case=='quartic':
        u,v=x/LX,y/LY
        T=T0+AMP*(u**3-u+2*v**3+v+u*u*v*v)
        gradient=AMP*np.column_stack(((3*u*u-1+2*u*v*v)/LX,(6*v*v+1+2*u*u*v)/LY))
        Q=-K*AMP*((6*u+2*v*v)/LX**2+(12*v+2*u*u)/LY**2)
    else:
        source=0. if case=='affine' else 1e5
        T=280.+35*x/LX+source*x*(LX-x)/(2*K)
        gradient=np.column_stack((35/LX+source*(LX-2*x)/(2*K),np.zeros_like(x)))
        Q=np.full(len(x),source)
    return T,-K*gradient,Q


def geometry(nodes,tris):
    p=nodes[tris]
    det=(p[:,1,0]-p[:,0,0])*(p[:,2,1]-p[:,0,1])-(p[:,2,0]-p[:,0,0])*(p[:,1,1]-p[:,0,1])
    dy=p[:,[1,2,0],1]-p[:,[2,0,1],1]
    dx=p[:,[1,2,0],0]-p[:,[2,0,1],0]
    gradients=np.stack((dy,-dx),axis=-1)/det[:,None,None]
    np.testing.assert_allclose(np.einsum('tic,tid->tcd',p,gradients),np.broadcast_to(np.eye(2),(len(p),2,2)),atol=1e-11)
    return gradients,abs(det)


def quadrature(order):
    s,w=np.polynomial.legendre.leggauss(order);s,w=(s+1)/2,w/2
    u,v=np.meshgrid(s,s,indexing='ij')
    bary=np.stack((1-u,u*v,u*(1-v)),axis=-1).reshape(-1,3)
    return bary,(w[:,None]*w[None,:]*u).ravel()


def integrate_system(nodes,tris,k,source,order=8):
    grads,det=geometry(nodes,tris)
    local=k*det[:,None,None]/2*np.einsum('tid,tjd->tij',grads,grads)
    rows=np.repeat(tris,3,axis=1).ravel();cols=np.tile(tris,(1,3)).ravel()
    matrix=coo_matrix((local.ravel(),(rows,cols)),shape=(len(nodes),len(nodes))).tocsr()
    bary,w=quadrature(order)
    pts=np.einsum('qi,tic->tqc',bary,nodes[tris])
    Q=np.asarray(source(pts.reshape(-1,2))).reshape(pts.shape[:2])
    loads=np.einsum('qi,tq,q,t->ti',bary,Q,w,det)
    rhs=np.zeros(len(nodes));np.add.at(rhs,tris.ravel(),loads.ravel())
    return matrix,rhs


def errors(nodes,tris,result,case,order=6):
    bary,w=quadrature(order);_,det=geometry(nodes,tris)
    pts=np.einsum('qi,tic->tqc',bary,nodes[tris])
    exact,flux,_=field(pts.reshape(-1,2),case)
    exact=exact.reshape(pts.shape[:2]);flux=flux.reshape(pts.shape)
    measured=np.einsum('qi,ti->tq',bary,result.temperature[tris])
    measure=det[:,None]*w
    return (float(np.sqrt(np.sum(measure*(measured-exact)**2))),
            float(np.sqrt(np.sum(measure[...,None]*(result.heat_flux[:,None]-flux)**2))))


def system_checks(nodes,tris,result,bc,k,source,reference=T0):
    matrix,load=integrate_system(nodes,tris,k,source)
    fixed=np.array(sorted(bc));free=np.setdiff1d(np.arange(len(nodes)),fixed)
    theta=result.temperature-reference
    residual=matrix@theta-load
    # Norm of physical fluctuation terms, not the absolute Kelvin offset.
    scale=max(float(np.linalg.norm(abs(matrix)@abs(theta)+abs(load),np.inf)),np.finfo(float).tiny)
    np.testing.assert_allclose(result.load,load,rtol=1e-10,atol=1e-10*max(abs(load).max(),np.finfo(float).tiny))
    assert np.max(abs(result.residual-residual))/scale<=1e-10
    assert (np.max(abs(residual[free]))/scale if len(free) else 0)<=1e-10
    np.testing.assert_array_equal(result.reaction[free],0.)
    assert np.max(abs(result.reaction[fixed]-residual[fixed]))/scale<=1e-10
    assert max(abs(result.temperature[i]-v) for i,v in bc.items())/AMP<=1e-10
    balance=abs(np.sum(result.reaction)+np.sum(load))/max(np.sum(abs(result.reaction))+np.sum(abs(load)),np.finfo(float).tiny)
    assert balance<=1e-10
    left=float(theta@(matrix@theta));right=float(theta@load+theta[fixed]@result.reaction[fixed])
    assert abs(left-right)/max(abs(left)+abs(right),np.finfo(float).tiny)<=1e-10
    return {'balance':float(balance),'functional_left':left,'functional_right':right,
            'original_free_residual':float(np.max(abs(residual[free]))/scale if len(free) else 0)}
