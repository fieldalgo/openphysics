# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Producer preregistered lab738 physics gates, separate from C acceptance."""
import json
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from galerkin.thermal_mechanical import solve_steady_thermoelasticity, WorkflowStageError
from thermal_mechanical_workflow_oracle import E, NU, ALPHA, TREF, K, field, parent, body, material


def options(m,kind,plane):
    boundary=np.unique(np.concatenate(list(m.boundary.values())))
    ids=boundary if kind!='linear' else np.unique(np.concatenate([m.boundary['left'],m.boundary['right']]))
    temperature=field(m.nodes,kind,plane)[0]
    right=int(np.argmin(np.sum((m.nodes-[1,0])**2,axis=1)))
    bc={(int(i),c):0. for i in boundary for c in (0,1)} if kind=='sine' else {(0,0):0.,(0,1):0.,(right,1):0.}
    source=(lambda p:K*20*2*np.pi**2*np.sin(np.pi*p[:,0])*np.sin(np.pi*p[:,1])) if kind=='sine' else 0.
    return dict(units={'length':'m','temperature':'K'},conductivity=K,
        thermal_dirichlet={int(i):temperature[i] for i in ids},heat_source=source,
        young_modulus=E,poisson_ratio=NU,plane=plane,thermal_expansion_per_k=ALPHA,
        reference_temperature_k=TREF,mechanical_dirichlet=bc,
        body_force=(lambda p:body(p,plane)) if kind=='sine' else (0.,0.))


def chunks(m,order):
    s,w=np.polynomial.legendre.leggauss(order);s,w=(s+1)/2,w/2
    a,b=np.meshgrid(s,s,indexing='ij');bary=np.stack([1-a,a*(1-b),a*b],axis=-1).reshape(-1,3)
    weights=(w[:,None]*w[None,:]*a).ravel()
    for start in range(0,m.num_triangles,128):
        tri=m.triangles[start:start+128];v=m.nodes[tri]
        det=np.linalg.det(v[:,1:]-v[:,:1])
        grad=np.linalg.inv(np.concatenate([np.ones((*v.shape[:2],1)),v],axis=-1))[:,1:,:].swapaxes(1,2)
        yield tri,bary,det[:,None]*weights,np.einsum('qn,tnd->tqd',bary,v),grad


def reconstruct(r,tri,bary,grad):
    u=np.einsum('qn,tnd->tqd',bary,r.displacement[tri])
    gu=np.einsum('tni,tnj->tji',grad,r.displacement[tri])
    e=np.stack([gu[:,0,0],gu[:,1,1],gu[:,0,1]+gu[:,1,0]],axis=-1)
    t=np.einsum('qn,tn->tq',bary,r.temperature_snapshot.temperature_k[tri])
    stress,energy=parent(e[:,None],t,r.plane)
    return u,gu,e,t,stress,energy


def metric(m,result,kind,order=8):
    plane=result.plane;fit=np.zeros(3)
    if kind=='linear':
        lhs=np.zeros((3,3));rhs=np.zeros(3)
        for tri,bary,w,p,g in chunks(m,order):
            u,*_=reconstruct(result,tri,bary,g);exact=field(p,kind,plane)[2]
            rigid=np.zeros((*p.shape[:-1],2,3));rigid[...,0,0]=1;rigid[...,1,1]=1
            rigid[...,0,2]=-p[...,1];rigid[...,1,2]=p[...,0]
            lhs+=np.einsum('tq,tqik,tqil->kl',w,rigid,rigid)
            rhs+=np.einsum('tq,tqik,tqi->k',w,rigid,u-exact)
        fit=np.linalg.solve(lhs,rhs)
    sums=np.zeros(7);actual_energy=0.;exact_energy=0.
    for tri,bary,w,p,g in chunks(m,order):
        u,gu,e,t,stress,energy=reconstruct(result,tri,bary,g)
        tex,tg,uex,gex,eex=field(p,kind,plane);sx,exenergy=parent(eex,tex,plane)
        rigid=np.stack([fit[0]-fit[2]*p[...,1],fit[1]+fit[2]*p[...,0]],axis=-1)
        du=u-uex-rigid;dg=gu[:,None]-gex-np.array([[0,-fit[2]],[fit[2],0]])
        de=e[:,None]-eex;ds=stress-sx
        gradt=np.einsum('tni,tn->ti',g,result.temperature_snapshot.temperature_k[tri])
        _,tangent=parent(de,np.full_like(t,TREF),plane)
        quantities=[np.sum(du**2,axis=-1),np.sum(dg**2,axis=(-2,-1)),
            np.sum(ds**2,axis=(-2,-1)),2*tangent,(t-tex)**2,
            np.sum((gradt[:,None]-tg)**2,axis=-1),de[...,0]**2+de[...,1]**2+.5*de[...,2]**2]
        sums+=np.array([np.sum(w*q) for q in quantities])
        actual_energy+=float(np.sum(w*energy));exact_energy+=float(np.sum(w*exenergy))
        # Centroid recovery is checked independently from parent 3D law.
        strain=e;tc=result.temperature_snapshot.temperature_k[tri].mean(1);sc,_=parent(strain,tc,plane)
        index=np.arange(len(tri))+int(np.where((m.triangles==tri[0]).all(1))[0][0])
        np.testing.assert_allclose(result.stress[index],np.column_stack([sc[:,0,0],sc[:,1,1],sc[:,0,1]]),atol=E*ALPHA*30*1e-10,rtol=1e-10)
        np.testing.assert_allclose(result.sigma_zz[index],sc[:,2,2],atol=E*ALPHA*30*1e-10,rtol=1e-10)
    scale=E*(ALPHA*30)**2
    assert abs(actual_energy-result.physical_elastic_energy)<=1e-10*scale
    return np.sqrt(sums),exact_energy


def audit_loads(m,result,kind):
    # Direct weak functional, not production assembly or returned residual as truth.
    external=np.zeros_like(result.load_external);thermal=np.zeros_like(external);internal=np.zeros_like(external)
    uku=ct=0.;le,d,beta=material(result.plane)
    for tri,bary,w,p,g in chunks(m,8):
        _,gu,e,t,stress,energy=reconstruct(result,tri,bary,g)
        zero,zero_energy=parent(np.zeros_like(e[:,None]),t,result.plane)
        loc_internal=np.einsum('tq,tqij,tnj->tni',w,stress[...,:2,:2],g)
        loc_thermal=-np.einsum('tq,tqij,tnj->tni',w,zero[...,:2,:2],g)
        force=body(p.reshape(-1,2),result.plane).reshape(p.shape) if kind=='sine' else np.zeros_like(p)
        loc_external=np.einsum('tq,qn,tqd->tnd',w,bary,force)
        for dest,local in [(external,loc_external),(thermal,loc_thermal),(internal,loc_internal)]:
            np.add.at(dest,tri.ravel(),local.reshape(-1,2))
        uku+=float(np.sum(w.sum(1)*np.einsum('ti,ij,tj->t',e,d,e)))
        ct+=float(np.sum(w*zero_energy))
    scale=E*ALPHA*30
    np.testing.assert_allclose(result.load_external,external,atol=scale*1e-10,rtol=1e-10)
    np.testing.assert_allclose(result.load_thermal,thermal,atol=scale*1e-10,rtol=1e-10)
    np.testing.assert_allclose(result.residual,internal-external,atol=scale*1e-10,rtol=1e-10)
    for forces in [thermal,external+result.reaction]:
        assert np.linalg.norm(forces.sum(0),np.inf)<=scale*1e-9
        assert abs(np.sum(m.nodes[:,0]*forces[:,1]-m.nodes[:,1]*forces[:,0]))<=scale*1e-9
    u=result.displacement;f=result.load_external;g=result.load_thermal;r=result.reaction
    workscale=E*(ALPHA*30)**2
    assert abs(uku-np.sum(u*(f+g+r)))<=workscale*1e-10
    assert abs(2*result.physical_elastic_energy-(np.sum(u*(f+r-g))+2*ct))<=workscale*1e-10


def audit_heat(m,heat,kind,bc):
    load=np.zeros(m.num_nodes);internal=np.zeros(m.num_nodes)
    for tri,bary,w,p,g in chunks(m,8):
        source=K*20*2*np.pi**2*np.sin(np.pi*p[...,0])*np.sin(np.pi*p[...,1]) if kind=='sine' else np.zeros(p.shape[:-1])
        gradient=np.einsum('tni,tn->ti',g,(heat.temperature-TREF)[tri])
        local_load=np.einsum('tq,qn,tq->tn',w,bary,source)
        local_internal=K*w.sum(1)[:,None]*np.einsum('tni,ti->tn',g,gradient)
        np.add.at(load,tri.ravel(),local_load.ravel());np.add.at(internal,tri.ravel(),local_internal.ravel())
    scale=max(K*30,abs(load.sum()))
    np.testing.assert_allclose(heat.load,load,atol=scale*1e-10,rtol=1e-10)
    np.testing.assert_allclose(heat.residual,internal-load,atol=scale*1e-10,rtol=1e-10)
    reaction=np.zeros_like(load);ids=list(bc);reaction[ids]=(internal-load)[ids]
    np.testing.assert_allclose(heat.reaction,reaction,atol=scale*1e-10,rtol=1e-10)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('kind',['linear','sine'])
def test_fixed_four_mesh_chain_gates(plane,kind):
    history=[];prescribed_history=[];energy_errors=[];heat_induced=[]
    for n in (8,16,32,64):
        m=rectangle_mesh(1,1,n,n);kw=options(m,kind,plane)
        aggregate=solve_steady_thermoelasticity(m,**kw);r=aggregate.mechanics
        np.testing.assert_array_equal(aggregate.temperature_snapshot.temperature_k,aggregate.heat.temperature)
        errors,exact=metric(m,r,kind,8);errors10,_=metric(m,r,kind,10)
        indices=[0,1,2,3,6] if kind=='linear' else list(range(7))
        np.testing.assert_allclose(errors[indices],errors10[indices],rtol=.01)
        _,e12=metric(m,r,kind,12);_,e16=metric(m,r,kind,16)
        scale=E*(ALPHA*30)**2
        assert abs(e12-e16)<=1e-8*scale
        energy_errors.append(abs(r.physical_elastic_energy-exact)/max(exact,scale))
        history.append(errors);audit_loads(m,r,kind)
        heat=aggregate.heat;audit_heat(m,heat,kind,kw['thermal_dirichlet']);hscale=max(K*30,abs(heat.load.sum()))
        assert abs(heat.reaction.sum()+heat.load.sum())<=1e-10*hscale
        # Independent integrated volumetric heat: sine integral is1600W/m.
        assert abs(heat.load.sum()-(1600 if kind=='sine' else 0))<=1e-10*hscale
        if kind=='linear':assert max(errors[4:6])<=1e-10
        ti=field(m.nodes,kind,plane)[0]
        prescribed=solve_thermoelasticity(m,freeze_temperature(m,ti),reference_temperature_k=TREF,
            thermal_expansion_per_k=ALPHA,young_modulus=E,poisson_ratio=NU,plane=plane,
            dirichlet=kw['mechanical_dirichlet'],body_force=kw['body_force'])
        prescribed_errors,_=metric(m,prescribed,kind,8);prescribed_history.append(prescribed_errors)
        # Exact vector decomposition and fixed-operator thermal perturbation bound.
        np.testing.assert_allclose((r.displacement-prescribed.displacement)+prescribed.displacement,r.displacement,atol=1e-20)
        le,d,beta=material(plane);lhs=rhs=0.
        for tri,bary,w,p,g in chunks(m,8):
            delta=r.displacement[tri]-prescribed.displacement[tri]
            gu=np.einsum('tni,tnj->tji',g,delta)
            de=np.stack([gu[:,0,0],gu[:,1,1],gu[:,0,1]+gu[:,1,0]],axis=-1)
            dt=np.einsum('qn,tn->tq',bary,(heat.temperature-ti)[tri])
            lhs+=float(np.sum(w.sum(1)*np.einsum('ti,ij,tj->t',de,d,de)))
            rhs+=float(np.sum(w*(beta*dt)**2))*float(np.array([1,1,0])@np.linalg.solve(d,np.array([1,1,0])))
        assert np.sqrt(lhs)<=np.sqrt(rhs)+1e-10*np.sqrt(scale)
        heat_induced.append([np.sqrt(lhs),np.sqrt(rhs)])
    rates=np.log2(np.array(history[:-1])[:,indices]/np.array(history[1:])[:,indices])
    gates=np.array([1.8,.9,.9,.9,1.8,.9,.9])
    assert np.all(rates>=gates[indices])
    prescribed_rates=np.log2(np.array(prescribed_history[:-1])[:,indices]/np.array(prescribed_history[1:])[:,indices])
    assert np.all(prescribed_rates>=gates[indices])
    assert np.all(np.diff(energy_errors)<0) and energy_errors[-1]<=.02
    print(json.dumps({'plane':plane,'kind':kind,'errors':np.array(history).tolist(),
        'orders':rates.tolist(),'prescribed_temperature_errors':np.array(prescribed_history).tolist(),'prescribed_orders':prescribed_rates.tolist(),'energy_errors':energy_errors,'thermal_perturbation':heat_induced}))


@pytest.mark.parametrize('plane',['stress','strain'])
def test_uniform_constrained_side_reactions(plane):
    m=rectangle_mesh(1,1,4,4);kw=options(m,'uniform',plane)
    ids=np.unique(np.concatenate(list(m.boundary.values())));kw['mechanical_dirichlet']={(int(i),c):0. for i in ids for c in (0,1)}
    r=solve_steady_thermoelasticity(m,**kw).mechanics
    np.testing.assert_allclose(r.displacement,0,atol=1e-14)
    exact,_=parent(np.zeros(3),np.array(TREF+20),plane);reaction=np.zeros_like(m.nodes)
    for tag,normal in [('left',[-1,0]),('right',[1,0]),('bottom',[0,-1]),('top',[0,1])]:
        for edge in m.boundary_edges[tag]:reaction[edge]+=exact[:2,:2]@normal*np.linalg.norm(m.nodes[edge[1]]-m.nodes[edge[0]])/2
    np.testing.assert_allclose(r.reaction,reaction,atol=E*ALPHA*20*1e-10)
    audit_loads(m,r,'uniform')


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('theta,alpha', [(-20.,ALPHA),(20.,-ALPHA),(20.,0.)])
def test_cooling_signed_alpha_and_zero(plane,theta,alpha):
    m=rectangle_mesh(1,1,4,4);kw=options(m,'uniform',plane)
    kw['thermal_dirichlet']={int(i):TREF+theta for i in m.boundary['left']};kw['thermal_expansion_per_k']=alpha
    r=solve_steady_thermoelasticity(m,**kw).mechanics;a=theta*alpha
    factor=1 if plane=='stress' else 1+NU
    np.testing.assert_allclose(r.displacement,factor*a*m.nodes,atol=1e-10*ALPHA*20)
    np.testing.assert_allclose(r.sigma_zz,0 if plane=='stress' else -E*a,atol=E*ALPHA*20*1e-10)


def test_nonzero_support_work_and_reference_shift():
    m=rectangle_mesh(1,1,4,4);kw=options(m,'linear','strain')
    ids=np.unique(np.concatenate(list(m.boundary.values())))
    u=1e-4*np.column_stack([m.nodes[:,0]+m.nodes[:,1],2*m.nodes[:,1]])
    kw['mechanical_dirichlet']={(int(i),c):u[i,c] for i in ids for c in (0,1)}
    r=solve_steady_thermoelasticity(m,**kw).mechanics;audit_loads(m,r,'linear')
    assert abs(np.sum(r.displacement*r.reaction))>1
    kw['thermal_dirichlet']={i:v+100 for i,v in kw['thermal_dirichlet'].items()};kw['reference_temperature_k']+=100
    shifted=solve_steady_thermoelasticity(m,**kw).mechanics
    np.testing.assert_allclose(shifted.displacement,r.displacement,atol=1e-14)
    assert shifted.physical_elastic_energy==pytest.approx(r.physical_elastic_energy,rel=1e-10)


@pytest.mark.parametrize('factor',[1e-3,1e3])
def test_explicit_length_conversion_is_physical_invariance(factor):
    m=rectangle_mesh(1,1,4,4);kw=options(m,'linear','strain');r=solve_steady_thermoelasticity(m,**kw)
    described=rectangle_mesh(1/factor,1/factor,4,4);described.nodes*=factor
    converted=solve_steady_thermoelasticity(described,**kw)
    for x,y,scale in [(r.heat.temperature,converted.heat.temperature,30),
                      (r.heat.heat_flux,converted.heat.heat_flux,K*30),
                      (r.mechanics.displacement,converted.mechanics.displacement,ALPHA*30),
                      (r.mechanics.stress,converted.mechanics.stress,E*ALPHA*30),
                      (r.mechanics.reaction,converted.mechanics.reaction,E*ALPHA*30)]:
        assert np.max(abs(x-y))/scale<=1e-9


def test_direct_math_negative_controls():
    a=ALPHA*20;d=material('strain')[1];right,_=parent(np.zeros(3),np.array(TREF+20),'strain')
    wrong=d@(-a*np.array([1,1,0]))
    correct=np.array([right[0,0],right[1,1],right[0,1]])
    assert np.linalg.norm(wrong-correct)/np.linalg.norm(correct)>.2
    bary=np.array([[2/3,1/6,1/6],[1/6,2/3,1/6],[1/6,1/6,2/3]])
    values=TREF+bary@np.array([0.,20.,40.]);_,density=parent(np.zeros((3,3)),values,'strain')
    _,centroid=parent(np.zeros(3),np.array(TREF+20),'strain')
    assert abs(centroid-density.mean())/density.mean()>.1
