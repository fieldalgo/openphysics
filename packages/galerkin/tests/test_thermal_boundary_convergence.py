# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Predeclared convergence gates with independent 8/10-point field integrals."""
import numpy as np
import pytest
import galerkin.thermal as thermal
from galerkin.mesh import rectangle_mesh
from refsol.thermal_boundary import (dirichlet_robin_slab,robin_only_slab,
    sine_temperature,sine_flux,sine_source)


def norms(m,r,temperature,flux,order):
    x,w=np.polynomial.legendre.leggauss(order);x,w=(x+1)/2,w/2
    a,b=np.meshgrid(x,x,indexing='ij')
    bary=np.stack(((1-a)*(1-b),a,(1-a)*b),axis=-1).reshape(-1,3)
    weights=(2*w[:,None]*w[None,:]*(1-a)).ravel()
    vertices=m.nodes[m.triangles]
    p=np.einsum('qi,tij->tqj',bary,vertices)
    th=np.einsum('qi,ti->tq',bary,r.temperature[m.triangles])
    diff=th-temperature(p)
    qdiff=r.heat_flux[:,None,:]-flux(p)
    # Determinants computed here, independently of mesh.areas/production helpers.
    v=vertices[:,1]-vertices[:,0];u=vertices[:,2]-vertices[:,0]
    area=abs(v[:,0]*u[:,1]-v[:,1]*u[:,0])/2
    return np.sqrt([np.sum(area[:,None]*weights*diff**2),
                    np.sum(area[:,None]*weights*np.sum(qdiff**2,axis=-1))])


def boundary_errors(m,r,temperature,order):
    # Rectangular side coordinates and reference interpolation are independent
    # of boundary tags, edge orientation and the production normal routine.
    x,w=np.polynomial.legendre.leggauss(order);x,w=(x+1)/2,w/2
    total=0.
    for axis,value in ((0,0.),(0,1.),(1,0.),(1,1.)):
        ids=np.where(np.isclose(m.nodes[:,axis],value))[0]
        ids=ids[np.argsort(m.nodes[ids,1-axis])]
        pa,pb=m.nodes[ids[:-1]],m.nodes[ids[1:]]
        p=(1-x[None,:,None])*pa[:,None]+x[None,:,None]*pb[:,None]
        th=(1-x)*r.temperature[ids[:-1],None]+x*r.temperature[ids[1:],None]
        length=np.linalg.norm(pb-pa,axis=1)
        total+=np.sum(length[:,None]*w*(th-temperature(p))**2)
    return np.sqrt(total)


def quality(r,bc):
    scale=max(sum(np.sum(abs(a)) for a in (r.load,r.reaction,r.prescribed_outward_load,r.convective_outward)),1e-300)
    assert abs(np.sum(r.load+r.reaction-r.prescribed_outward_load-r.convective_outward))/scale<=1e-10
    free=np.setdiff1d(np.arange(len(r.temperature)),list(bc))
    assert np.max(abs(r.residual[free]),initial=0)/scale<=1e-10


@pytest.mark.slow
@pytest.mark.parametrize('mode',['flux','mixed','robin'])
def test_quadratic_slab_original_convergence_and_boundary_gates(mode):
    errors=[];boundary=[]
    for n in (8,16,32,64):
        m=rectangle_mesh(1.,1.,n,n);bc={int(i):320. for i in m.boundary['left']}
        if mode=='robin':
            bc={};ref=robin_only_slab(length=1.,conductivity=2.5,heat_source=5.,left_h=8.,right_h=12.,left_ambient=300.,right_ambient=310.)
            conv={'left':(8.,300.),'right':(12.,310.)};g=0.
        else:
            h=10. if mode=='mixed' else 0.;g=.7
            ref=dirichlet_robin_slab(length=1.,conductivity=2.5,left_temperature=320.,heat_source=5.,outward_flux=g,h=h,ambient=300.)
            conv={'right':(h,300.)} if h else None
        r=thermal.solve_steady_heat(m,conductivity=2.5,dirichlet=bc,heat_source=5.,outward_flux={'right':g},convection=conv)
        e8=norms(m,r,ref.temperature,ref.heat_flux,8);e10=norms(m,r,ref.temperature,ref.heat_flux,10)
        assert np.all(abs(e8-e10)<.01*e10)
        b8=boundary_errors(m,r,ref.temperature,8);b10=boundary_errors(m,r,ref.temperature,10)
        assert abs(b8-b10)<.01*b10
        errors.append(e10);quality(r,bc)
        if conv:
            exact=ref.outward_fluxes[1]-g
            # Independent line integration of convection (not the reported C).
            ids=m.boundary['right'];line=m.nodes[ids,1]
            numerical=np.sum(np.diff(line)*((r.temperature[ids[:-1]]+r.temperature[ids[1:]])/2-(310. if mode=='robin' else 300.))*(12. if mode=='robin' else 10.))
            assert abs(numerical-exact)/abs(exact)<1e-10
            # An independent one-sided gradient trace has nonzero discretization
            # error; the integrated Robin rate above is already exact at roundoff.
            vertices=m.nodes[m.triangles]
            selected=np.sum(np.isclose(vertices[:,:,0],1.),axis=1)==2
            V=vertices[selected];T=r.temperature[m.triangles[selected]]
            gradients=np.linalg.solve(V[:,1:]-V[:,:1],(T[:,1:]-T[:,:1])[...,None])[...,0]
            lengths=np.max(V[:,:,1],axis=1)-np.min(V[:,:,1],axis=1)
            numerical_trace=np.sum(lengths*(-2.5*gradients[:,0]))
            boundary.append(abs(numerical_trace-ref.outward_fluxes[1])/abs(ref.outward_fluxes[1]))
    orders=np.log2(np.array(errors[:-1])/errors[1:])
    print('quadratic',mode,'errors',np.array(errors).tolist(),'orders',orders.tolist(),'boundary',boundary)
    assert np.all(orders[-2:,0]>=1.8) and np.all(orders[-2:,1]>=.9)
    if boundary:
        assert boundary[-1]<=.02 and np.all(np.diff(boundary)<0)


@pytest.mark.slow
@pytest.mark.parametrize('mixed',[False,True])
def test_sine_all_robin_or_mixed_mms(mixed):
    errors=[]
    # Rectangular normal oracle is explicit, not a production helper.
    normals={'left':np.array([-1.,0.]),'right':np.array([1.,0.]),'bottom':np.array([0.,-1.]),'top':np.array([0.,1.])}
    for n in (8,16,32,64):
        m=rectangle_mesh(1.,1.,n,n);bc={int(i):float(sine_temperature(m.nodes[i])) for i in m.boundary['left']} if mixed else {}
        conv={};g={}
        for tag,normal in normals.items():
            if mixed and tag=='left':continue
            def ambient(p,provided,normal=normal):
                np.testing.assert_allclose(provided,np.broadcast_to(normal,provided.shape),atol=1e-14)
                prescribed=.7+p[:,0]+.2*p[:,1]
                return sine_temperature(p)-(sine_flux(p)@normal-prescribed)/10.
            conv[tag]=(10.,ambient)
            g[tag]=lambda p,n:.7+p[:,0]+.2*p[:,1]
        r=thermal.solve_steady_heat(m,conductivity=2.5,dirichlet=bc,heat_source=sine_source,outward_flux=g,convection=conv)
        e8=norms(m,r,sine_temperature,sine_flux,8);e10=norms(m,r,sine_temperature,sine_flux,10)
        assert np.all(abs(e8-e10)<.01*e10)
        b8=boundary_errors(m,r,sine_temperature,8);b10=boundary_errors(m,r,sine_temperature,10)
        assert abs(b8-b10)<.01*b10
        errors.append(e10);quality(r,bc)
    orders=np.log2(np.array(errors[:-1])/errors[1:])
    print('sine mixed',mixed,'errors',np.array(errors).tolist(),'orders',orders.tolist())
    assert np.all(orders[-2:,0]>=1.8) and np.all(orders[-2:,1]>=.9)


@pytest.mark.parametrize('mutation',['flux_sign','negative_H','omit_ambient','omit_offset','lumped_mass','separate_means','reversed_normal'])
def test_actual_runtime_negative_controls(monkeypatch,mutation):
    original=thermal._boundary_system
    samples_original=thermal._boundary_samples
    def oracle():
        m=rectangle_mesh(1.,1.,3,3)
        # Varying ambient/h ensures product/lumping errors are observable.
        r=thermal.solve_steady_heat(m,conductivity=2.5,dirichlet={0:320.},heat_source=5.,
             outward_flux={'right':lambda p,n:.7*n[:,0]},
             convection={'right':(lambda p,n:2+3*p[:,1],lambda p,n:300+20*p[:,1])})
        # Independent exact polynomial edge moments give a production-independent gate.
        expectedG=np.zeros(len(m.nodes));expectedB=np.zeros(len(m.nodes));expectedC=np.zeros(len(m.nodes))
        nodes=m.boundary['right'];y=m.nodes[nodes,1]
        for a,b,ya,yb in zip(nodes[:-1],nodes[1:],y[:-1],y[1:]):
            length=yb-ya;h0,h1=2+3*ya,2+3*yb;t0,t1=300+20*ya,300+20*yb
            H=length/12*np.array([[3*h0+h1,h0+h1],[h0+h1,h0+3*h1]])
            B=length/12*np.array([3*h0*t0+h0*t1+h1*t0+h1*t1,h0*t0+h0*t1+h1*t0+3*h1*t1])
            expectedG[[a,b]]+=.7*length/2
            expectedB[[a,b]]+=B
            expectedC[[a,b]]+=H@r.temperature[[a,b]]-B
        np.testing.assert_allclose(r.prescribed_outward_load,expectedG,atol=1e-11)
        np.testing.assert_allclose(r.ambient_load,expectedB,atol=1e-11)
        np.testing.assert_allclose(r.convective_outward,expectedC,atol=1e-11)
        # Independently check the same PDE using its weak work identity;
        # gradients computed directly from triangle coordinate differences.
        Kwork=0.;volumeWork=0.
        for tri in m.triangles:
            p=m.nodes[tri];J=p[1:]-p[0];area=abs(np.linalg.det(J))/2
            grad=np.linalg.solve(J,r.temperature[tri[1:]]-r.temperature[tri[0]])
            Kwork+=2.5*area*(grad@grad)
            volumeWork+=5*area*np.mean(r.temperature[tri])
        # Shift the test function by its prescribed value, so no unknown reaction work.
        v=r.temperature-320
        # Integral grad(v).grad(T) is Kwork; compute volume/boundary work directly.
        rhs=volumeWork-320*sum(r.load)-v@expectedG-v@expectedC
        assert abs(Kwork-rhs)<1e-9*max(abs(rhs),1.)
    oracle()
    def mutated(samples,n,labels,anchors,constrained):
        if mutation=='separate_means':
            samples=[(kind,e,N,w,(v[0],np.repeat(v[1].mean(axis=1)[:,None],v[1].shape[1],axis=1))) if kind=='convection' else (kind,e,N,w,v) for kind,e,N,w,v in samples]
        H,G,B,S=original(samples,n,labels,anchors,constrained)
        if mutation=='flux_sign':G=-G
        if mutation=='negative_H':H=-H
        if mutation=='omit_ambient':B=np.zeros_like(B);S=np.zeros_like(S)
        if mutation=='omit_offset':S=B.copy()
        if mutation=='lumped_mass':
            from scipy.sparse import diags
            H=diags(np.asarray(H.sum(axis=1)).ravel()).tocsr()
        return H,G,B,S
    if mutation=='reversed_normal':
        def samples_wrong(mesh,p,t,prescribed,outward_flux,convection):
            wrong={tag:(lambda p,n,fn=fn:fn(p,-n)) for tag,fn in outward_flux.items()}
            return samples_original(mesh,p,t,prescribed,wrong,convection)
        monkeypatch.setattr(thermal,'_boundary_samples',samples_wrong)
    else:monkeypatch.setattr(thermal,'_boundary_system',mutated)
    with pytest.raises((AssertionError,ValueError)):
        oracle()
