# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent acceptance of the public heat-to-mechanics workflow.

No production constitutive/assembly/geometry/refsol helper supplies oracle values.
All three adjacent refinement intervals are mandatory (8,16,32,64).
"""
from dataclasses import replace
import json
from unittest.mock import patch
import numpy as np
import pytest
from galerkin.mesh import Mesh
import galerkin.thermal_mechanical as workflow
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from thermal_mechanical_independent_oracle import (
    E0, NU0, ALPHA0, TREF0, K0, LEVELS, parent_state, inplane,
    tangent_from_parent, triangle_rule, rigid_fit, thermal_dual_density, exact_fields)


def square(n=4):
    """Independent Cartesian topology, not the production mesh generator."""
    x,y=np.meshgrid(np.linspace(0.,1.,n+1),np.linspace(0.,1.,n+1),indexing='xy')
    p=np.column_stack((x.ravel(),y.ravel()));t=[]
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i;t.extend(((a,a+1,a+n+2),(a,a+n+2,a+n+1)))
    boundary=np.flatnonzero((p==0).any(1)|(p==1).any(1))
    return Mesh(p,np.asarray(t),{'exterior':boundary})


def config(mesh,kind,plane,**parameters):
    exact=lambda p:exact_fields(p,kind,plane,**parameters)
    fields=exact(mesh.nodes);p=mesh.nodes
    thermal_nodes=(np.flatnonzero((p[:,0]==0)|(p[:,0]==1)) if kind=='linear'
                   else mesh.boundary['exterior'])
    if kind in ('uniform','linear'):
        fixed={(0,0):0.,(0,1):0.,(int(np.argmax(p[:,0]-2*p[:,1])),1):0.}
    else:fixed={(int(i),c):float(fields['displacement'][i,c]) for i in mesh.boundary['exterior'] for c in (0,1)}
    return dict(units={'length':'m','temperature':'K'},conductivity=K0,
                thermal_dirichlet={int(i):float(fields['temperature'][i]) for i in thermal_nodes},
                heat_source=(lambda p:exact(p)['heat_source']) if kind=='sine' else 0.,
                young_modulus=E0,poisson_ratio=NU0,plane=plane,
                thermal_expansion_per_k=parameters.get('alpha',ALPHA0),
                reference_temperature_k=parameters.get('tref',TREF0),mechanical_dirichlet=fixed,
                body_force=(lambda p:exact(p)['body_force']) if kind=='sine' else (0.,0.))


def gradient(mesh,values):
    _,_,_,g=triangle_rule(mesh.nodes[mesh.triangles],2)
    return np.einsum('tai,ta...->t...i',g,np.asarray(values)[mesh.triangles])


def strains(gu):
    return np.stack((gu[...,0,0],gu[...,1,1],gu[...,0,1]+gu[...,1,0]),axis=-1)


def assert_scaled(a,b,scale,tol=1e-10):
    assert np.max(np.abs(np.asarray(a)-b),initial=0)<=tol*scale


def audit(mesh,result,cfg):
    """Independent integrals, nodal K/H=0/RHS, reactions and parent energy."""
    t=mesh.triangles;n=len(mesh.nodes);u=result.mechanics.displacement
    bary,w,p,g=triangle_rule(mesh.nodes[t],8);area=w.sum(1)
    temp=result.temperature_snapshot.temperature_k;theta=temp-cfg['reference_temperature_k']
    tq=np.einsum('qa,ta->tq',bary,temp[t]);gu=gradient(mesh,u);eps=strains(gu)
    plane=cfg['plane'];alpha=cfg['thermal_expansion_per_k'];tref=cfg['reference_temperature_k']
    d=tangent_from_parent(plane);state=parent_state(eps[:,None],tq,plane,alpha=alpha,tref=tref)
    zero=parent_state(np.zeros(3),tq,plane,alpha=alpha,tref=tref)
    cold=parent_state(eps,TREF0,plane)
    force=cfg['body_force'](p.reshape(-1,2)).reshape(p.shape) if callable(cfg['body_force']) else np.broadcast_to(cfg['body_force'],p.shape)
    q=cfg['heat_source'](p.reshape(-1,2)).reshape(w.shape) if callable(cfg['heat_source']) else np.full_like(w,cfg['heat_source'])
    f_local=np.einsum('qa,tq,tqi->tai',bary,w,force)
    g_local=-np.einsum('tq,tqij,taj->tai',w,zero['stress'][...,:2,:2],g)
    ku_local=area[:,None,None]*np.einsum('tij,taj->tai',cold['stress'][...,:2,:2],g)
    f=np.zeros((n,2));thermal=f.copy();ku=f.copy();fq=np.zeros(n);kt=fq.copy()
    for target,local in [(f,f_local),(thermal,g_local),(ku,ku_local)]:np.add.at(target,t.ravel(),local.reshape(-1,2))
    np.add.at(fq,t.ravel(),np.einsum('qa,tq,tq->ta',bary,w,q).ravel())
    gt=gradient(mesh,theta)
    np.add.at(kt,t.ravel(),(K0*area[:,None]*np.einsum('tai,ti->ta',g,gt)).ravel())
    stress_scale=E0*max(abs(alpha)*max(20.,float(np.max(abs(theta)))),1e-4)
    force_scale=stress_scale;energy_scale=E0*max(abs(alpha)*max(20.,float(np.max(abs(theta)))),1e-4)**2
    heat_scale=max(K0*30.,float(np.sum(w*abs(q))))
    m=result.mechanics;h=result.heat
    assert_scaled(m.total_strain,eps,stress_scale/E0)
    centroid=parent_state(eps,temp[t].mean(1),plane,alpha=alpha,tref=tref)
    assert_scaled(m.stress,inplane(centroid['stress']),stress_scale)
    assert_scaled(m.sigma_zz,centroid['stress'][...,2,2],stress_scale)
    assert_scaled(m.epsilon_zz,centroid['total'][...,2,2],stress_scale/E0)
    assert_scaled(m.thermal_strain,inplane(centroid['thermal'])*[1,1,2],stress_scale/E0)
    assert_scaled(m.elastic_strain,eps-m.thermal_strain,stress_scale/E0)
    assert_scaled(m.load_external,f,force_scale)
    assert_scaled(m.load_thermal,thermal,force_scale)
    r=ku-f-thermal
    assert_scaled(m.residual,r,force_scale,1e-9)
    mask=np.zeros((n,2),bool)
    for key,val in cfg['mechanical_dirichlet'].items():mask[key]=True;assert_scaled(u[key],val,max(abs(val),1e-4))
    assert_scaled(r[~mask],0,force_scale,1e-9)
    assert_scaled(m.reaction,np.where(mask,r,0),force_scale,1e-9)
    assert_scaled(np.sum(f+m.reaction,axis=0),0,force_scale,1e-9)
    physical=f+m.reaction
    assert_scaled(np.sum(mesh.nodes[:,0]*physical[:,1]-mesh.nodes[:,1]*physical[:,0]),0,force_scale,1e-9)
    energy=float(np.sum(w*state['energy']));ct=float(np.sum(w*zero['energy']))
    uku=float(np.sum(u*ku));ug=float(np.sum(u*thermal));external=float(np.sum(u*f));support=float(np.sum(u*m.reaction))
    assert_scaled(m.physical_elastic_energy,energy,energy_scale)
    assert_scaled(energy,.5*uku-ug+ct,energy_scale)
    assert_scaled(2*energy,external+support-ug+2*ct,energy_scale)
    assert_scaled(h.load,fq,heat_scale)
    assert_scaled(h.residual,kt-fq,heat_scale)
    fixed=np.array(sorted(cfg['thermal_dirichlet']));free=np.setdiff1d(np.arange(n),fixed)
    assert_scaled((kt-fq)[free],0,heat_scale)
    hr=np.zeros(n);hr[fixed]=(kt-fq)[fixed]
    assert_scaled(h.reaction,hr,heat_scale)
    assert_scaled(np.sum(fq+hr),0,heat_scale)
    assert_scaled(h.heat_flux,-K0*gt,K0*30)
    assert np.array_equal(temp,h.temperature)
    assert np.array_equal(result.reference_mesh.nodes,mesh.nodes)
    assert np.array_equal(result.reference_mesh.triangles,mesh.triangles)
    assert result.reference_mesh is not mesh
    return dict(energy=energy,support=support,thermal=thermal,external=f,ku=ku,heat_load=fq)


def norms(mesh,u,temperature,kind,plane,order=8,align=False):
    bary,w,p,_=triangle_rule(mesh.nodes[mesh.triangles],order)
    truth=exact_fields(p,kind,plane);uq=np.einsum('qa,tai->tqi',bary,u[mesh.triangles])
    tq=np.einsum('qa,ta->tq',bary,temperature[mesh.triangles]);gu=gradient(mesh,u)[:,None]
    du=uq-truth['displacement'];dg=gu-truth['gradient']
    if align:
        du,coef=rigid_fit(p,w,du);rotation=np.array([[0.,-coef[2]],[coef[2],0.]])
        dg=dg-rotation
    eps=strains(gu);de=strains(dg);d=tangent_from_parent(plane)
    computed=parent_state(eps,tq,plane);ds=computed['stress']-truth['state']['stress']
    gt=gradient(mesh,temperature-TREF0)[:,None]-truth['temperature_gradient']
    integ=lambda a:float(np.sqrt(np.sum(w*a)))
    return dict(T_L2=integ((tq-truth['temperature'])**2),T_H1=integ(np.sum(gt*gt,axis=-1)),
                flux=K0*integ(np.sum(gt*gt,axis=-1)),u_L2=integ(np.sum(du*du,axis=-1)),
                u_H1=integ(np.sum(dg*dg,axis=(-1,-2))),strain=integ(np.sum(de*de,axis=-1)),
                stress=integ(np.sum(ds*ds,axis=(-1,-2))),
                energy_norm=integ(np.einsum('tqi,ij,tqj->tq',de,d,de)))


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('kind',['uniform','constrained_uniform'])
@pytest.mark.parametrize('theta,alpha',[(20.,ALPHA0),(-20.,ALPHA0),(20.,-ALPHA0),(20.,0.)])
def test_thermal_mechanical_independent_uniform(plane,kind,theta,alpha):
    mesh=square();cfg=config(mesh,kind,plane,theta=theta,alpha=alpha)
    r=workflow.solve_steady_thermoelasticity(mesh,**cfg);a=audit(mesh,r,cfg)
    ex=exact_fields(mesh.nodes,kind,plane,theta=theta,alpha=alpha)
    assert_scaled(r.heat.temperature,ex['temperature'],20.)
    assert_scaled(r.mechanics.displacement,ex['displacement'],max(abs(alpha)*20,1e-4))
    assert_scaled(r.mechanics.stress,inplane(exact_fields(mesh.nodes[mesh.triangles].mean(1),kind,plane,theta=theta,alpha=alpha)['state']['stress']),E0*max(abs(alpha)*20,1e-4))
    expected=parent_state(ex['strain'][0],TREF0+theta,plane,alpha=alpha)['energy']
    assert_scaled(a['energy'],expected,E0*max(abs(alpha)*20,1e-4)**2)
    if kind=='constrained_uniform':
        sigma=parent_state(np.zeros(3),TREF0+theta,plane,alpha=alpha)['stress']
        # Side resultants include half of each adjacent corner contribution.
        nodes=mesh.nodes;local=np.zeros_like(nodes);n=4
        for x,normal,coord in [(0.,[-1.,0.],0),(1.,[1.,0.],0),(0.,[0.,-1.],1),(1.,[0.,1.],1)]:
            ids=np.flatnonzero(nodes[:,coord]==x);ids=ids[np.argsort(nodes[ids,1-coord])]
            for a,b in zip(ids[:-1],ids[1:]):local[[a,b]]+=(sigma[:2,:2]@normal)/(2*n)
        assert_scaled(r.mechanics.reaction,local,E0*max(abs(alpha)*20,1e-4),1e-9)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('kind',['linear','sine'])
def test_thermal_mechanical_independent_all_three_intervals(plane,kind):
    collected=[];prescribed=[];energy_errors=[];bounds=[];ledger=[]
    for n in LEVELS:
        mesh=square(n);cfg=config(mesh,kind,plane);r=workflow.solve_steady_thermoelasticity(mesh,**cfg)
        audit(mesh,r,cfg)
        ih=exact_fields(mesh.nodes,kind,plane)['temperature']
        snap=freeze_temperature(mesh,ih)
        m=solve_thermoelasticity(mesh,snap,reference_temperature_k=TREF0,thermal_expansion_per_k=ALPHA0,young_modulus=E0,poisson_ratio=NU0,plane=plane,dirichlet=cfg['mechanical_dirichlet'],body_force=cfg['body_force'])
        error=norms(mesh,r.mechanics.displacement,r.heat.temperature,kind,plane,align=kind=='linear')
        pre=norms(mesh,m.displacement,ih,kind,plane,align=kind=='linear')
        quad10=norms(mesh,r.mechanics.displacement,r.heat.temperature,kind,plane,10,align=kind=='linear')
        keys=['u_L2','u_H1','strain','stress','energy_norm']+(['T_L2','T_H1','flux'] if kind=='sine' else [])
        for key in keys:assert abs(error[key]-quad10[key])<.01*error[key],(n,key,error,quad10)
        bary,w,p,_=triangle_rule(mesh.nodes[mesh.triangles],8)
        delta_u=r.mechanics.displacement-m.displacement;deltaT=r.heat.temperature-ih
        de=strains(gradient(mesh,delta_u));d=tangent_from_parent(plane)
        lhs=float(np.sqrt(np.sum(w.sum(1)*np.einsum('ti,ij,tj->t',de,d,de))))
        dtq=np.einsum('qa,ta->tq',bary,deltaT[mesh.triangles])
        rhs=float(np.sqrt(np.sum(w*thermal_dual_density(dtq,plane))))
        assert lhs<=rhs+1e-10*np.sqrt(E0*(ALPHA0*30)**2),(n,lhs,rhs)
        # Four error objects are vectors; do not claim additive norms.
        tq=np.einsum('qa,ta->tq',bary,r.heat.temperature[mesh.triangles]);iq=np.einsum('qa,ta->tq',bary,ih[mesh.triangles])
        u_actual=np.einsum('qa,tai->tqi',bary,r.mechanics.displacement[mesh.triangles]);u_pre=np.einsum('qa,tai->tqi',bary,m.displacement[mesh.triangles]);truth=exact_fields(p,kind,plane)
        assert_scaled((u_actual-truth['displacement'])-(u_pre-truth['displacement']),u_actual-u_pre,1e-4)
        assert np.array_equal(r.temperature_snapshot.temperature_k,r.heat.temperature)
        integral=lambda x:float(np.sqrt(np.sum(w*np.sum(x*x,axis=-1))))
        ledger.append(dict(n=n,heat_total_L2=error['T_L2'],temperature_interpolation_L2=float(np.sqrt(np.sum(w*(iq-truth['temperature'])**2))),nodal_temperature_error=float(np.max(abs(deltaT))),heat_nodal_correction_L2=float(np.sqrt(np.sum(w*(tq-iq)**2))),transfer_error=0.,prescribed_u_L2=pre['u_L2'],heat_induced_u_L2=integral(u_actual-u_pre),total_u_L2=error['u_L2']))
        if kind=='linear':
            assert_scaled(r.heat.temperature,ih,30.)
            assert_scaled(r.heat.heat_flux,[-K0*20,0.],K0*30)
        else:
            _,wr,pr,_=triangle_rule(np.array([[[0.,0.],[1.,0.],[1.,1.]],[[0.,0.],[1.,1.],[0.,1.]]]),16)
            ref=float(np.sum(wr*exact_fields(pr,kind,plane)['state']['energy']))
            energy_errors.append(abs(r.mechanics.physical_elastic_energy-ref)/ref)
        collected.append(error);prescribed.append(pre);bounds.append([lhs,rhs])
    all_rates={}
    for label,values,keys in [('chain',collected,['u_L2','u_H1','strain','stress','energy_norm']+(['T_L2','T_H1','flux'] if kind=='sine' else [])),('prescribed',prescribed,['u_L2','u_H1','strain','stress','energy_norm'])]:
        for key in keys:
            errors=np.array([v[key] for v in values]);rates=np.log2(errors[:-1]/errors[1:]);gate=1.8 if key.endswith('_L2') else .9
            all_rates[label+'_'+key]=rates.tolist()
            assert np.all(rates>=gate),(plane,kind,label,key,errors,rates,gate)
    if energy_errors:assert np.all(np.diff(energy_errors)<0) and energy_errors[-1]<=.02,energy_errors
    print('WORKFLOW_INDEPENDENT '+json.dumps(dict(plane=plane,kind=kind,levels=LEVELS,rates=all_rates,errors=collected,ledger=ledger,perturbation_bounds=bounds,relative_U_errors=energy_errors)))


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermal_mechanical_independent_support_work_and_shift(plane):
    mesh=square();cfg=config(mesh,'constrained_uniform',plane)
    u=mesh.nodes@np.array([[2e-4,1e-4],[-.5e-4,-1e-4]]).T+[1e-4,-2e-4]
    cfg['mechanical_dirichlet']={(int(i),c):u[i,c] for i in mesh.boundary['exterior'] for c in (0,1)}
    r=workflow.solve_steady_thermoelasticity(mesh,**cfg);a=audit(mesh,r,cfg)
    assert abs(a['support'])>1.;assert_scaled(r.mechanics.displacement,u,1e-4)
    shifted={**cfg,'thermal_dirichlet':{i:v+100. for i,v in cfg['thermal_dirichlet'].items()},'reference_temperature_k':TREF0+100.}
    s=workflow.solve_steady_thermoelasticity(mesh,**shifted);audit(mesh,s,shifted)
    assert_scaled(s.mechanics.displacement,r.mechanics.displacement,1e-4)
    assert_scaled(s.mechanics.stress,r.mechanics.stress,E0*ALPHA0*20)
    assert_scaled(s.mechanics.physical_elastic_energy,r.mechanics.physical_elastic_energy,E0*(ALPHA0*20)**2)


def test_thermal_mechanical_independent_manifest_snapshot_lifetime():
    mesh=square();cfg=config(mesh,'linear','strain');r=workflow.solve_steady_thermoelasticity(mesh,**cfg)
    manifest=r.manifest;encoded=r.manifest_json;snapshot=r.temperature_snapshot
    assert json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False)==encoded
    assert manifest['schema']=='galerkin-steady-thermoelasticity-v1'
    assert manifest['units']=={'length':'m','temperature':'K'}
    assert manifest['origin']=='workflow_owned_heat_call' and manifest['authentication']=='not_certified'
    assert manifest['stages']==dict(heat='completed',transfer='completed',mechanics='completed')
    assert manifest['inputs']['materials']==dict(conductivity_w_mk=K0,young_modulus_pa=E0,poisson_ratio=NU0,thermal_expansion_per_k=ALPHA0,reference_temperature_k=TREF0,plane='strain')
    assert manifest['inputs']['thermal_dirichlet']==[[i,v] for i,v in sorted(cfg['thermal_dirichlet'].items())]
    assert manifest['transfer']['policy']=='same_mesh_exact_nodal_P1_copy'
    for key in ('temperature_hash','snapshot_hash'):assert manifest['transfer'][key]==getattr(snapshot,key)
    assert manifest['mesh']['mesh_hash']==snapshot.mesh_hash
    assert manifest['quantity_units']==dict(heat_load_reaction_residual='W/m',heat_flux='W/m^2',mechanical_load_reaction_residual='N/m',physical_elastic_energy='J/m')
    manifest['units']['length']='mm';assert r.manifest_json==encoded and r.manifest['units']['length']=='m'
    saved=snapshot.temperature_k.copy();nodes=snapshot.nodes.copy();triangles=snapshot.triangles.copy()
    r.heat.temperature[:]=0;mesh.nodes[:]+=10;cfg['thermal_dirichlet'].clear();r.reference_mesh.nodes[:]+=5
    assert np.array_equal(saved,snapshot.temperature_k) and np.array_equal(nodes,snapshot.nodes) and np.array_equal(triangles,snapshot.triangles)
    for a in (snapshot.nodes,snapshot.triangles,snapshot.temperature_k):
        with pytest.raises(ValueError):a.setflags(write=True)
    with pytest.raises(ValueError,match='stale|mismatch'):
        solve_thermoelasticity(r.reference_mesh,snapshot,reference_temperature_k=TREF0,thermal_expansion_per_k=ALPHA0,young_modulus=E0,poisson_ratio=NU0,plane='strain',dirichlet={(0,0):0.,(0,1):0.,(4,1):0.})
    assert r.manifest['post_return_integrity']=='not_certified_mutable_component_results'


def test_thermal_mechanical_independent_callback_capture():
    mesh=square();cfg=config(mesh,'uniform','stress');original=mesh.nodes.copy();bc=cfg['mechanical_dirichlet'].copy()
    def source(p):
        mesh.nodes[:]+=100.;cfg['thermal_dirichlet'].clear();cfg['mechanical_dirichlet'].clear()
        return np.zeros(len(p))
    cfg['heat_source']=source;r=workflow.solve_steady_thermoelasticity(mesh,**cfg)
    assert np.array_equal(r.reference_mesh.nodes,original)
    assert r.manifest['inputs']['heat_source_w_m3']==dict(kind='callable',origin='caller_provided',fingerprinted=False)
    assert r.manifest['inputs']['mechanical_dirichlet']==[[i,c,v] for (i,c),v in sorted(bc.items())]
    assert_scaled(r.mechanics.displacement,ALPHA0*20*original,ALPHA0*20)


@pytest.mark.parametrize('change',[
    {'units':{'length':'mm','temperature':'K'}},{'units':{'length':'m','temperature':'C'}},
    {'units':{'length':'m','temperature':'K','extra':1}}, {'conductivity':0.},
    {'young_modulus':-1.},{'poisson_ratio':.5},{'plane':'plane_stress'},
    {'reference_temperature_k':-1.},{'thermal_expansion_per_k':np.nan},
    {'thermal_dirichlet':{True:300.}},{'mechanical_dirichlet':{(0,2):0.}},
    {'body_force':[0.]},{'heat_source':np.inf}])
def test_thermal_mechanical_independent_input_abort(change):
    mesh=square();cfg={**config(mesh,'uniform','stress'),**change}
    with patch.object(workflow,'solve_steady_heat') as heat,patch.object(workflow,'solve_thermoelasticity') as mech:
        with pytest.raises(workflow.WorkflowStageError) as error:workflow.solve_steady_thermoelasticity(mesh,**cfg)
        assert error.value.stage=='input' and error.value.__cause__ is not None
        heat.assert_not_called();mech.assert_not_called()


@pytest.mark.parametrize('bad',['float_connectivity','clockwise','nonfinite','out_of_range','bad_tag'])
def test_thermal_mechanical_independent_raw_mesh_abort(bad):
    mesh=square();cfg=config(mesh,'uniform','stress')
    if bad=='float_connectivity':mesh.triangles=mesh.triangles.astype(float)+.1
    elif bad=='clockwise':mesh.triangles=mesh.triangles[:,[0,2,1]]
    elif bad=='nonfinite':mesh.nodes[0,0]=np.nan
    elif bad=='out_of_range':mesh.triangles[0,0]=len(mesh.nodes)
    else:mesh.boundary['exterior']=np.array([.1,1.])
    with patch.object(workflow,'solve_steady_heat') as heat:
        with pytest.raises(workflow.WorkflowStageError) as error:workflow.solve_steady_thermoelasticity(mesh,**cfg)
        assert error.value.stage=='input';heat.assert_not_called()


@pytest.mark.parametrize('bad',['shape','nan','infinite','negative','tiny_negative','complex'])
def test_thermal_mechanical_independent_transfer_abort(bad):
    mesh=square();cfg=config(mesh,'uniform','stress');real=workflow.solve_steady_heat
    def modified(*args,**kwargs):
        h=real(*args,**kwargs);t=h.temperature.copy()
        if bad=='shape':t=t[:,None]
        elif bad=='complex':t=t.astype(complex)
        else:t[2]={'nan':np.nan,'infinite':np.inf,'negative':-1.,'tiny_negative':-np.finfo(float).tiny}[bad]
        return replace(h,temperature=t)
    with patch.object(workflow,'solve_steady_heat',modified),patch.object(workflow,'solve_thermoelasticity') as mech:
        with pytest.raises(workflow.WorkflowStageError) as error:workflow.solve_steady_thermoelasticity(mesh,**cfg)
        assert error.value.stage=='transfer' and error.value.__cause__ is not None
        if bad in ('negative','tiny_negative'):assert 'node 2' in str(error.value) and 'minimum' in str(error.value)
        mech.assert_not_called()


@pytest.mark.parametrize('stage',['heat','mechanics','manifest'])
def test_thermal_mechanical_independent_stage_exception_chain(stage):
    mesh=square();cfg=config(mesh,'uniform','stress');cause=RuntimeError('independent stage failure')
    target={'heat':'solve_steady_heat','mechanics':'solve_thermoelasticity'}.get(stage)
    context=patch.object(workflow,target,side_effect=cause) if target else patch.object(workflow.json,'dumps',side_effect=cause)
    with context,patch.object(workflow,'freeze_temperature',wraps=workflow.freeze_temperature) as freeze:
        with pytest.raises(workflow.WorkflowStageError) as error:workflow.solve_steady_thermoelasticity(mesh,**cfg)
        assert error.value.stage==stage and error.value.__cause__ is cause
        if stage=='heat':freeze.assert_not_called()


@pytest.mark.parametrize('kind',['missing_heat_anchor','heat_shape','heat_nonfinite','missing_support','body_shape','body_nonfinite','owned_mutation'])
def test_thermal_mechanical_independent_real_failure_stages(kind):
    mesh=square();cfg=config(mesh,'uniform','stress');expected='heat'
    if kind=='missing_heat_anchor':cfg['thermal_dirichlet']={}
    elif kind=='heat_shape':cfg['heat_source']=lambda p:np.zeros((len(p),1))
    elif kind=='heat_nonfinite':cfg['heat_source']=lambda p:np.full(len(p),np.nan)
    elif kind=='missing_support':cfg['mechanical_dirichlet']={(0,0):0.};expected='mechanics'
    elif kind=='body_shape':cfg['body_force']=lambda p:np.zeros(len(p));expected='mechanics'
    elif kind=='body_nonfinite':cfg['body_force']=lambda p:np.full((len(p),2),np.inf);expected='mechanics'
    real=workflow.solve_steady_heat
    def mutated(m,**kw):
        h=real(m,**kw);m.nodes[0,0]+=.01;return h
    with patch.object(workflow,'solve_steady_heat',mutated if kind=='owned_mutation' else real):
        with pytest.raises(workflow.WorkflowStageError) as error:workflow.solve_steady_thermoelasticity(mesh,**cfg)
        assert error.value.stage==expected and error.value.__cause__ is not None


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermal_mechanical_independent_order_rotation_units(plane):
    mesh=square();cfg=config(mesh,'sine',plane);r=workflow.solve_steady_thermoelasticity(mesh,**cfg)
    rng=np.random.default_rng(319);order=rng.permutation(len(mesh.nodes));inverse=np.argsort(order);elements=rng.permutation(len(mesh.triangles))
    new=Mesh(mesh.nodes[order],inverse[mesh.triangles[elements]][:,[1,2,0]],{'exterior':inverse[mesh.boundary['exterior']]})
    kw={**cfg,'thermal_dirichlet':{int(inverse[i]):v for i,v in cfg['thermal_dirichlet'].items()},'mechanical_dirichlet':{(int(inverse[i]),c):v for (i,c),v in cfg['mechanical_dirichlet'].items()}}
    s=workflow.solve_steady_thermoelasticity(new,**kw);audit(new,s,kw)
    assert_scaled(s.heat.temperature[inverse],r.heat.temperature,20.);assert_scaled(s.mechanics.displacement[inverse],r.mechanics.displacement,1e-4)
    angle=.37;rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    rotated=Mesh(mesh.nodes@rot.T+[.2,-.1],mesh.triangles.copy(),mesh.boundary)
    def unrotate(p):return (p-[.2,-.1])@rot
    kr={**cfg,'heat_source':lambda p:exact_fields(unrotate(p),'sine',plane)['heat_source'],'body_force':lambda p:exact_fields(unrotate(p),'sine',plane)['body_force']@rot.T,'mechanical_dirichlet':{(int(i),c):float((r.mechanics.displacement[i]@rot.T)[c]) for i in mesh.boundary['exterior'] for c in (0,1)}}
    rr=workflow.solve_steady_thermoelasticity(rotated,**kr);audit(rotated,rr,kr)
    assert_scaled(rr.mechanics.displacement@rot,r.mechanics.displacement,1e-4,1e-9)
    assert_scaled(rr.heat.temperature,r.heat.temperature,20.,1e-9)
    assert_scaled(rr.mechanics.physical_elastic_energy,r.mechanics.physical_elastic_energy,E0*(ALPHA0*20)**2,1e-9)
    for scale in (1e-3,1e-6):
        converted=Mesh((mesh.nodes/scale)*scale,mesh.triangles.copy(),mesh.boundary);rc=workflow.solve_steady_thermoelasticity(converted,**cfg)
        assert_scaled(rc.mechanics.displacement,r.mechanics.displacement,1e-4,1e-9);assert_scaled(rc.heat.temperature,r.heat.temperature,20.,1e-9)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermal_mechanical_independent_components(plane):
    one=square(2);n=len(one.nodes);mesh=Mesh(np.concatenate((one.nodes,one.nodes+[2.,0.])),np.concatenate((one.triangles,one.triangles+n)),{'exterior':np.r_[one.boundary['exterior'],one.boundary['exterior']+n]})
    cfg=config(one,'uniform',plane);cfg['thermal_dirichlet']|={i+n:v+10 for i,v in list(cfg['thermal_dirichlet'].items())};cfg['mechanical_dirichlet']|={(i+n,c):v for (i,c),v in list(cfg['mechanical_dirichlet'].items())}
    r=workflow.solve_steady_thermoelasticity(mesh,**cfg);audit(mesh,r,cfg);factor=1 if plane=='stress' else 1+NU0
    assert_scaled(r.mechanics.displacement[:n],factor*ALPHA0*20*one.nodes,ALPHA0*30);assert_scaled(r.mechanics.displacement[n:],factor*ALPHA0*30*one.nodes,ALPHA0*30)
    for stage in ('heat','mechanics'):
        bad={**cfg}
        if stage=='heat':bad['thermal_dirichlet']={i:v for i,v in cfg['thermal_dirichlet'].items() if i<n}
        else:bad['mechanical_dirichlet']={(i,c):v for (i,c),v in cfg['mechanical_dirichlet'].items() if i<n}
        with pytest.raises(workflow.WorkflowStageError) as err:workflow.solve_steady_thermoelasticity(mesh,**bad)
        assert err.value.stage==stage


@pytest.mark.parametrize('wrong',['thermal_sign','three_alpha','naive_PE','absolute_T','zz_omission','PE_residual_energy','centroid_T_squared','support_work_omission'])
def test_thermal_mechanical_independent_actual_wrong_physics(wrong):
    mesh=square();cfg=config(mesh,'linear','strain')
    if wrong=='support_work_omission':
        cfg=config(mesh,'constrained_uniform','strain');cfg['mechanical_dirichlet']={(int(i),c):float((mesh.nodes[i]*[2e-4,-1e-4])[c]) for i in mesh.boundary['exterior'] for c in (0,1)}
    real=workflow.solve_thermoelasticity
    def corrupt(*args,**kw):
        if wrong=='thermal_sign':kw['thermal_expansion_per_k']*=-1
        elif wrong=='three_alpha':kw['thermal_expansion_per_k']*=3
        elif wrong=='naive_PE':kw['thermal_expansion_per_k']/=1+NU0
        elif wrong=='absolute_T':kw['reference_temperature_k']=0.
        m=real(*args,**kw)
        if wrong=='zz_omission':m.sigma_zz[:]=0.
        elif wrong=='PE_residual_energy':
            bary,w,_,_=triangle_rule(mesh.nodes[mesh.triangles],8);a=ALPHA0*(np.einsum('qa,ta->tq',bary,m.temperature_snapshot.temperature_k[mesh.triangles])-TREF0)
            m.physical_elastic_energy-=float(np.sum(w*.5*E0*a*a))
        elif wrong=='centroid_T_squared':
            tc=m.temperature_snapshot.temperature_k[mesh.triangles].mean(1);_,w,_,_=triangle_rule(mesh.nodes[mesh.triangles],2)
            m.physical_elastic_energy=float(np.sum(w.sum(1)*parent_state(m.total_strain,tc,'strain')['energy']))
        elif wrong=='support_work_omission':m.physical_elastic_energy-=.5*float(np.sum(m.displacement*m.reaction))
        return m
    with patch.object(workflow,'solve_thermoelasticity',corrupt):r=workflow.solve_steady_thermoelasticity(mesh,**cfg)
    with pytest.raises(AssertionError):audit(mesh,r,cfg)


@pytest.mark.parametrize('change',['node_order','element_order','scale','schema','unit','temperature_hash'])
def test_thermal_mechanical_independent_snapshot_mismatch(change):
    mesh=square();cfg=config(mesh,'linear','strain');r=workflow.solve_steady_thermoelasticity(mesh,**cfg)
    snapshot=r.temperature_snapshot
    if change=='node_order':mesh.nodes=mesh.nodes[::-1].copy()
    elif change=='element_order':mesh.triangles=mesh.triangles[::-1].copy()
    elif change=='scale':mesh.nodes*=.001
    else:object.__setattr__(snapshot,{'schema':'schema_version','unit':'temperature_unit','temperature_hash':'temperature_hash'}[change],{'schema':2,'unit':'C','temperature_hash':'fnv1a64:0000000000000000'}[change])
    with pytest.raises(ValueError):solve_thermoelasticity(mesh,snapshot,reference_temperature_k=TREF0,thermal_expansion_per_k=ALPHA0,young_modulus=E0,poisson_ratio=NU0,plane='strain',dirichlet=cfg['mechanical_dirichlet'])


@pytest.mark.parametrize('temperature',[-1.,-np.finfo(float).tiny,20.,0.])
def test_thermal_mechanical_independent_actual_heat_K_domain(temperature):
    mesh=square();cfg=config(mesh,'uniform','stress');cfg['thermal_dirichlet']={i:temperature for i in cfg['thermal_dirichlet']}
    if temperature<0:
        with patch.object(workflow,'solve_thermoelasticity') as mech:
            with pytest.raises(workflow.WorkflowStageError) as err:workflow.solve_steady_thermoelasticity(mesh,**cfg)
            assert err.value.stage=='transfer';mech.assert_not_called()
    else:
        r=workflow.solve_steady_thermoelasticity(mesh,**cfg);audit(mesh,r,cfg)
        assert np.all(r.temperature_snapshot.temperature_k==temperature)
        assert r.manifest['authentication']=='not_certified'


def test_thermal_mechanical_independent_actual_body_only_omission():
    # For uniform T the gradient of thermal stress vanishes; dropping the
    # boundary term makes an incorrect body-only implementation return cold u.
    mesh=square();cfg=config(mesh,'uniform','stress');real=workflow.solve_thermoelasticity
    def wrong(m,snapshot,**kw):
        cold=freeze_temperature(m,np.full(len(m.nodes),TREF0))
        return real(m,cold,**kw)
    with patch.object(workflow,'solve_thermoelasticity',wrong):r=workflow.solve_steady_thermoelasticity(mesh,**cfg)
    with pytest.raises(AssertionError):audit(mesh,r,cfg)
