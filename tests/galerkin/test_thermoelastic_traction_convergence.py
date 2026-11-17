# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Preregistered mixed-boundary convergence and original-system weak audit."""
import json
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from refsol.thermoelastic_traction import polynomial_manufactured, parent_state, traction_from_stress

E=70e9; A=12e-6; C=1e-4; STRAIN=max(C,A*20); FORCE=E*STRAIN; ENERGY=E*STRAIN**2


def material(plane):
    return dict(youngs_modulus=E,poisson_ratio=.3,plane=plane,
                linear_expansion_coefficient=A,stress_free_temperature=293.15)


def chunks(mesh,order):
    z,w=np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2
    x,y=np.meshgrid(z,z,indexing='ij')
    bary=np.stack([(1-x)*(1-y),x,(1-x)*y],axis=-1).reshape(-1,3)
    weight=(2*w[:,None]*w[None,:]*(1-x)).ravel()
    for start in range(0,len(mesh.triangles),128):
        tri=mesh.triangles[start:start+128];p=mesh.nodes[tri]
        jac=p[:,1:]-p[:,:1];area=np.abs(np.linalg.det(jac))/2
        grad=np.linalg.solve(jac,np.broadcast_to(np.array([[-1.,1.,0.],[-1.,0.,1.]]),(len(tri),2,3)))
        yield start,tri,bary,area[:,None]*weight,np.einsum('qa,tad->tqd',bary,p),grad


def errors(mesh,r,linear,order):
    mat=material(r.plane);sums=np.zeros(7);energy=0.;exactenergy=0.
    for start,tri,bary,w,p,g in chunks(mesh,order):
        sh=p.shape[:2];ex=polynomial_manufactured(p.reshape(-1,2),linear_temperature=linear,**mat)
        u=np.einsum('qa,tad->tqd',bary,r.displacement[tri])
        grad=np.einsum('tij,tjk->tik',r.displacement[tri].transpose(0,2,1),g.transpose(0,2,1))
        strain=np.stack([grad[:,0,0],grad[:,1,1],grad[:,0,1]+grad[:,1,0]],axis=-1)
        st=np.broadcast_to(strain[:,None,:],(*sh,3));t=np.einsum('qa,ta->tq',bary,r.temperature_snapshot.temperature[tri])
        stress,en,total=parent_state(strain=st.reshape(-1,3),temperature=t.ravel(),**mat)
        dg=grad[:,None]-ex.displacement_gradient.reshape((*sh,2,2));du=u-ex.displacement.reshape((*sh,2))
        de=np.stack([dg[...,0,0],dg[...,1,1],dg[...,0,1]+dg[...,1,0]],axis=-1)
        tangent,density,_=parent_state(strain=de.reshape(-1,3),temperature=np.full(np.prod(sh),mat['stress_free_temperature']),**mat)
        ds=stress.reshape((*sh,3,3))-ex.stress.reshape((*sh,3,3))
        dt=t-ex.temperature.reshape(sh)
        tg=np.einsum('tij,tj->ti',g,r.temperature_snapshot.temperature[tri])
        dgt=tg[:,None]-ex.temperature_gradient.reshape((*sh,2))
        vals=[np.sum(du**2,axis=-1),np.sum(dg**2,axis=(-1,-2)),np.sum(ds**2,axis=(-1,-2)),
              2*density.reshape(sh),de[...,0]**2+de[...,1]**2+.5*de[...,2]**2,dt**2,np.sum(dgt**2,axis=-1)]
        sums+=np.array([np.sum(w*v) for v in vals]);energy+=np.sum(w*en.reshape(sh));exactenergy+=np.sum(w*ex.strain_energy_density.reshape(sh))
        sc,_,_=parent_state(strain=strain,temperature=r.temperature_snapshot.temperature[tri].mean(1),**mat)
        sl=slice(start,start+len(tri))
        np.testing.assert_allclose(r.stress[sl],sc[:,[0,1,0],[0,1,1]],atol=FORCE*1e-10,rtol=0)
        np.testing.assert_allclose(r.stress_zz[sl],sc[:,2,2],atol=FORCE*1e-10,rtol=0)
    assert abs(energy-r.strain_energy_per_depth)<=ENERGY*1e-10
    return np.sqrt(sums),exactenergy


def audit(mesh,r,linear):
    mat=material(r.plane);body=np.zeros_like(r.applied_body_force_per_depth);thermal=np.zeros_like(body);internal=np.zeros_like(body);ct=uku=0.
    for start,tri,bary,w,p,g in chunks(mesh,8):
        sh=p.shape[:2];ex=polynomial_manufactured(p.reshape(-1,2),linear_temperature=linear,**mat)
        tq=np.einsum('qa,ta->tq',bary,r.temperature_snapshot.temperature[tri]);strain=r.strain[start:start+len(tri)]
        ss,en,_=parent_state(strain=np.repeat(strain,len(bary),axis=0),temperature=tq.ravel(),**mat)
        zero,ez,_=parent_state(strain=np.zeros((tq.size,3)),temperature=tq.ravel(),**mat)
        tan,_,_=parent_state(strain=strain,temperature=np.full(len(tri),mat['stress_free_temperature']),**mat)
        locb=np.einsum('tq,qa,tqd->tad',w,bary,ex.body_force_density.reshape((*sh,2)))
        loct=-np.einsum('tq,tqij,tja->tai',w,zero.reshape((*sh,3,3))[...,:2,:2],g)
        loci=np.einsum('tq,tqij,tja->tai',w,ss.reshape((*sh,3,3))[...,:2,:2],g)
        for target,local in [(body,locb),(thermal,loct),(internal,loci)]:np.add.at(target,tri.ravel(),local.reshape(-1,2))
        ct+=np.sum(w*ez.reshape(sh));uku+=np.sum(w.sum(1)*np.sum(strain*tan[:,[0,1,0],[0,1,1]],axis=1))
    # Independent 8-point segment integrals, including endpoint P1 test functions.
    line=np.zeros_like(body);z,w=np.polynomial.legendre.leggauss(8);s=(z+1)/2;w=w/2
    for tag in ('right','top','bottom'):
        n={'right':[1.,0.],'top':[0.,1.],'bottom':[0.,-1.]}[tag]
        for edge in mesh.boundary_edges[tag]:
            points=(1-s[:,None])*mesh.nodes[edge[0]]+s[:,None]*mesh.nodes[edge[1]]
            st=polynomial_manufactured(points,linear_temperature=linear,**mat).stress
            traction=np.einsum('qij,j->qi',st[:,:2,:2],n);length=np.linalg.norm(mesh.nodes[edge[1]]-mesh.nodes[edge[0]])
            line[edge[0]]+=length*np.sum((w*(1-s))[:,None]*traction,axis=0)
            line[edge[1]]+=length*np.sum((w*s)[:,None]*traction,axis=0)
    for actual,expected in [(r.applied_body_force_per_depth,body),(r.applied_traction_force_per_depth,line),(r.thermal_equivalent_force_per_depth,thermal),
                            (r.residual_force_per_depth,internal-body-line)]:
        np.testing.assert_allclose(actual,expected,atol=FORCE*1e-10,rtol=0)
    u=r.displacement;f=r.applied_force_per_depth;gload=r.thermal_equivalent_force_per_depth;reaction=r.reaction_force_per_depth
    support=float(np.sum(u*reaction));ug=np.sum(u*gload)
    assert abs(uku-np.sum(u*(f+gload+reaction)))<=ENERGY*1e-10
    assert abs(r.strain_energy_per_depth-(.5*uku-ug+ct))<=ENERGY*1e-10
    assert abs(2*r.strain_energy_per_depth-(np.sum(u*f)+support-ug+2*ct))<=ENERGY*1e-10
    assert abs(support)>ENERGY*1e-8  # translated v2 detects the omitted-work variant
    assert abs(r.strain_energy_per_depth-.5*uku)>ENERGY*1e-8
    for force in (f+reaction,gload):
        assert np.linalg.norm(force.sum(0),np.inf)<=FORCE*1e-9
        assert abs(np.sum(mesh.nodes[:,0]*force[:,1]-mesh.nodes[:,1]*force[:,0]))<=FORCE*1e-9
    fixed=np.array([2*int(i)+j for i in mesh.boundary['left'] for j in (0,1)])
    free=np.setdiff1d(np.arange(2*mesh.num_nodes),fixed)
    assert np.max(np.abs(r.residual_force_per_depth.ravel()[free]))<=FORCE*1e-9


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('linear',[False,True])
def test_fixed_four_mesh_mixed_mms(plane,linear):
    mat=material(plane);history=[];energy_errors=[]
    for n in (8,16,32,64):
        mesh=rectangle_mesh(1.,1.,n,n);exact=polynomial_manufactured(mesh.nodes,linear_temperature=linear,**mat)
        bc={(int(i),j):exact.displacement[i,j] for i in mesh.boundary['left'] for j in (0,1)}
        def field(p):return polynomial_manufactured(p,linear_temperature=linear,**mat)
        def traction(p,normals):return traction_from_stress(normals,stress=field(p).stress)
        r=solve_thermoelasticity(mesh,freeze_temperature(mesh,temperature=exact.temperature),prescribed_displacement=bc,
            body_force_density=lambda p:field(p).body_force_density,traction={t:traction for t in ('right','top','bottom')},**mat)
        e8,_=errors(mesh,r,linear,8);e10,_=errors(mesh,r,linear,10)
        indices=list(range(5)) if linear else list(range(7))
        np.testing.assert_allclose(e8[indices],e10[indices],atol=0,rtol=.01)
        _,en12=errors(mesh,r,linear,12);_,en16=errors(mesh,r,linear,16)
        assert abs(en12-en16)<=ENERGY*1e-8
        history.append(e8);energy_errors.append(abs(r.strain_energy_per_depth-en16)/ENERGY)
        audit(mesh,r,linear)
    rates=np.log2(np.array(history[:-1])[:,indices]/np.array(history[1:])[:,indices])
    gates=np.array([1.8,.9,.9,.9,.9,1.8,.9])[indices]
    assert np.all(rates[-2:]>=gates)
    assert np.all(np.diff(energy_errors)<0) and energy_errors[-1]<=.02
    print(json.dumps({'plane':plane,'linear_temperature':linear,'n':[8,16,32,64],
                     'errors':np.array(history).tolist(),'orders':rates.tolist(),'physical_energy_errors':energy_errors}))
