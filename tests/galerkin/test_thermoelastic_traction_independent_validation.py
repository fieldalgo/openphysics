# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent original-3D/edge acceptance; no producer/reference oracle imports."""
from dataclasses import fields,replace,MISSING
import json
from unittest.mock import patch as mockpatch
import numpy as np
import pytest
from galerkin.mesh import Mesh
import galerkin.thermoelasticity as production
from thermoelastic_traction_independent_oracle import (
    E,NU,ALPHA,TREF,C0,TRANSLATION,TARGET,LEVELS,parent,patch,polynomial,
    triangle_rule,square_geometry,ring_geometry,exterior_segments,segment_rule,
    nodal_edge_force,continuum_ledger)

STRAIN=max(C0,ALPHA*20);STRESS=E*STRAIN;ENERGY=E*STRAIN**2
OLD_FIELDS=('displacement','total_strain','thermal_strain','elastic_strain','stress',
 'sigma_zz','epsilon_zz','load_external','load_thermal','reaction','residual',
 'physical_elastic_energy','temperature_snapshot','reference_temperature_k',
 'thermal_expansion_per_k','young_modulus','poisson_ratio','plane')


def mesh_from_raw(p,t,ring=False):
    boundary={};edges={}
    for a,b,c in exterior_segments(p,t):
        mid=(p[a]+p[b])/2
        if ring:tag='inner' if max(abs(mid))<.5 else 'outer'
        else:tag='left' if mid[0]==0 else 'right' if mid[0]==1 else 'bottom' if mid[1]==0 else 'top'
        edges.setdefault(tag,[]).append([a,b])
    for tag,pairs in edges.items():edges[tag]=np.asarray(pairs);boundary[tag]=np.unique(edges[tag])
    return Mesh(p,t,boundary,edges)


def square(n=4):
    x,y=np.meshgrid(np.linspace(0,1,n+1),np.linspace(0,1,n+1),indexing='xy')
    p=np.column_stack((x.ravel(),y.ravel()));cells=[]
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i;cells.extend(((a,a+1,a+n+2),(a,a+n+2,a+n+1)))
    return mesh_from_raw(p,np.asarray(cells))


def solve_case(mesh,field,plane,alpha=ALPHA,tref=TREF,overlap=False):
    values=field(mesh.nodes);snapshot=production.freeze_temperature(mesh,tref+values['theta'])
    if 'left' in mesh.boundary:
        fixed={(int(i),c):float(values['u'][i,c]) for i in mesh.boundary['left'] for c in (0,1)}
    else:fixed={(0,0):float(values['u'][0,0]),(0,1):float(values['u'][0,1]),(1,1):float(values['u'][1,1])}
    traction=lambda p,n:np.einsum('qij,qj->qi',field(p)['state']['stress'][...,:2,:2],n)
    cfg=dict(reference_temperature_k=tref,thermal_expansion_per_k=alpha,young_modulus=E,
             poisson_ratio=NU,plane=plane,dirichlet=fixed,body_force=lambda p:field(p)['body'],
             traction={tag:traction for tag in mesh.boundary_edges if overlap or tag!='left'})
    return snapshot,cfg


def grad(mesh,u):
    _,_,_,g=triangle_rule(mesh.nodes[mesh.triangles],2)
    return np.einsum('tai,taj->tji',g,u[mesh.triangles])


def engineering(gu):return np.stack((gu[...,0,0],gu[...,1,1],gu[...,0,1]+gu[...,1,0]),axis=-1)
def inplane(s):return np.stack((s[...,0,0],s[...,1,1],s[...,0,1]),axis=-1)

def near(name,a,b,scale=1.,tol=1e-10):
    assert np.max(abs(np.asarray(a)-b),initial=0)<=tol*scale,(name,np.max(abs(np.asarray(a)-b)),tol*scale)


def direct_line_load(mesh,mapping):
    owners={(a,b):c for a,b,c in exterior_segments(mesh.nodes,mesh.triangles)}
    result=np.zeros_like(mesh.nodes)
    for tag,fn in mapping.items():
        for a,b in mesh.boundary_edges[tag]:
            c=owners[tuple(sorted((int(a),int(b))))]
            basis,w,p,n=segment_rule(mesh.nodes[a],mesh.nodes[b],mesh.nodes[c],8)
            value=fn(p,n) if callable(fn) else np.broadcast_to(fn,p.shape)
            result[[a,b]]+=np.einsum('qa,q,qi->ai',basis,w,value)
    return result


def audit(mesh,snapshot,r,cfg,length=1.):
    """Direct independent original-pencil action/RHS/full3D energy audit."""
    tri=mesh.triangles;bary,w,p,g=triangle_rule(mesh.nodes[tri],8)
    u=r.displacement;eps=engineering(grad(mesh,u));plane=cfg['plane'];alpha=cfg['thermal_expansion_per_k'];tref=cfg['reference_temperature_k']
    aq=alpha*(np.einsum('qa,ta->tq',bary,snapshot.temperature_k[tri])-tref)
    full=parent(eps[:,None],aq,plane);cold=parent(eps,0.,plane);thermal=parent(np.zeros((*w.shape,3)),aq,plane)
    scale=max(C0,abs(alpha)*20);s=E*scale;fscale=s*length;escale=E*scale**2*length**2
    body=cfg['body_force'](p.reshape(-1,2)).reshape(p.shape) if callable(cfg['body_force']) else np.broadcast_to(cfg['body_force'],p.shape)
    fbody=np.zeros_like(mesh.nodes);fthermal=fbody.copy();ku=fbody.copy()
    for dest,local in [(fbody,np.einsum('qa,tq,tqi->tai',bary,w,body)),(fthermal,-np.einsum('tq,tqij,taj->tai',w,thermal['stress'][...,:2,:2],g)),(ku,w.sum(1)[:,None,None]*np.einsum('tij,taj->tai',cold['stress'][...,:2,:2],g))]:np.add.at(dest,tri.ravel(),local.reshape(-1,2))
    fline=direct_line_load(mesh,cfg.get('traction') or {})
    near('load_body',r.load_body,fbody,fscale);near('load_traction',r.load_traction,fline,fscale)
    near('load_external',r.load_external,fbody+fline,fscale);near('load_thermal',r.load_thermal,fthermal,fscale)
    near('load_total',r.load_total,fbody+fline+fthermal,fscale)
    residual=ku-fbody-fline-fthermal;fixed=np.zeros_like(u,dtype=bool)
    for key,value in cfg['dirichlet'].items():fixed[key]=True;near('prescribed_component',u[key],value,max(C0*length,abs(value)))
    near('residual',r.residual,residual,fscale,1e-9);near('free_residual',residual[~fixed],0,fscale,1e-9)
    near('reaction',r.reaction,np.where(fixed,residual,0),fscale,1e-9)
    near('physical_force',np.sum(fbody+fline+r.reaction,axis=0),0,fscale,1e-9)
    physical=fbody+fline+r.reaction
    near('physical_moment',np.sum(mesh.nodes[:,0]*physical[:,1]-mesh.nodes[:,1]*physical[:,0]),0,fscale*length,1e-9)
    near('thermal_rigid_force',fthermal.sum(0),0,fscale)
    near('thermal_rigid_moment',np.sum(mesh.nodes[:,0]*fthermal[:,1]-mesh.nodes[:,1]*fthermal[:,0]),0,fscale*length)
    ac=alpha*(snapshot.temperature_k[tri].mean(1)-tref);centroid=parent(eps,ac,plane)
    near('total_strain',r.total_strain,eps,scale)
    near('thermal_strain',r.thermal_strain,np.column_stack((ac,ac,np.zeros_like(ac))),scale)
    near('elastic_strain',r.elastic_strain,eps-r.thermal_strain,scale)
    near('centroid_stress',r.stress,inplane(centroid['stress']),s)
    near('sigma_zz',r.sigma_zz,centroid['stress'][...,2,2],s)
    near('epsilon_zz',r.epsilon_zz,centroid['total'][...,2,2],scale)
    energy=float(np.sum(w*full['energy']));ct=float(np.sum(w*thermal['energy']))
    uku=float(np.sum(u*ku));ug=float(np.sum(u*fthermal));external=float(np.sum(u*(fbody+fline)));support=float(np.sum(u*r.reaction))
    near('physical_energy',r.physical_elastic_energy,energy,escale)
    near('parent_endpoint_energy',energy,.5*uku-ug+ct,escale)
    near('support_work_energy',2*energy,external+support-ug+2*ct,escale)
    near('physical_virtualwork',uku-ug,external+support,escale)
    assert r.temperature_snapshot is snapshot
    return dict(U=energy,support=support,ku=ku,ct=ct,thermal=fthermal,body=fbody,line=fline)


def errors(mesh,r,field,plane,order=8,alpha=ALPHA):
    tri=mesh.triangles;bary,w,p,g=triangle_rule(mesh.nodes[tri],order);truth=field(p)
    uq=np.einsum('qa,tai->tqi',bary,r.displacement[tri]);gu=grad(mesh,r.displacement)[:,None]
    a=alpha*(np.einsum('qa,ta->tq',bary,r.temperature_snapshot.temperature_k[tri])-TREF)
    de=engineering(gu)-truth['strain'];ds=parent(engineering(gu),a,plane)['stress']-truth['state']['stress']
    norm=lambda value:float(np.sqrt(np.sum(w*value)))
    return dict(u_L2=norm(np.sum((uq-truth['u'])**2,axis=-1)),u_H1=norm(np.sum((gu-truth['gradient'])**2,axis=(-1,-2))),strain=norm(de[...,0]**2+de[...,1]**2+.5*de[...,2]**2),full_stress=norm(np.sum(ds*ds,axis=(-1,-2))),energy_norm=norm(2*parent(de,0.,plane)['energy']))


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('theta,alpha',[(20.,ALPHA),(-20.,ALPHA),(20.,-ALPHA),(20.,0.)])
@pytest.mark.parametrize('overlap',[False,True])
def test_thermoelastic_traction_independent_uniform_combined(plane,theta,alpha,overlap):
    mesh=square();field=lambda p:patch(p,plane,theta=theta,alpha=alpha)
    snapshot,cfg=solve_case(mesh,field,plane,alpha,overlap=overlap);r=production.solve_thermoelasticity(mesh,snapshot,**cfg)
    audit(mesh,snapshot,r,cfg);truth=field(mesh.nodes)
    near('uniform_u',r.displacement,truth['u'],max(C0,abs(alpha)*20))
    ex=field(mesh.nodes[mesh.triangles].mean(1))
    near('uniform_stress',r.stress,inplane(ex['state']['stress']),STRESS)
    near('uniform_energy',r.physical_elastic_energy,ex['state']['energy'][0],ENERGY)
    if overlap:near('uniform_overlap_zero_reaction',r.reaction,0,STRESS)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('linear',[False,True])
def test_thermoelastic_traction_independent_fixed_mesh_gates(plane,linear):
    history=[];energies=[];thermal=[];support=[]
    field=lambda p:polynomial(p,plane,linear_temperature=linear)
    vv,tt=square_geometry();_,wr,pr,_=triangle_rule(vv[tt],16);ref=float(np.sum(wr*field(pr)['state']['energy']))
    _,w12,p12,_=triangle_rule(vv[tt],12);near('reference12_16',np.sum(w12*field(p12)['state']['energy']),ref,ENERGY,1e-8)
    for n in LEVELS:
        mesh=square(n);snapshot,cfg=solve_case(mesh,field,plane);r=production.solve_thermoelasticity(mesh,snapshot,**cfg);a=audit(mesh,snapshot,r,cfg)
        error=errors(mesh,r,field,plane);error10=errors(mesh,r,field,plane,10)
        for key in error:assert abs(error[key]-error10[key])<=.01*error[key],(n,key,error,error10)
        tri=mesh.triangles;bary,w,p,g=triangle_rule(mesh.nodes[tri],8);tn=field(mesh.nodes)['theta']
        tq=np.einsum('qa,ta->tq',bary,tn[tri]);gt=np.einsum('tai,ta->ti',g,tn[tri])[:,None]
        if linear:exactgt=np.broadcast_to([9.,-4.],p.shape)
        else:exactgt=np.stack((9+6*p[...,1],-4+6*p[...,0]+6*p[...,1]),axis=-1)
        terr=[float(np.sqrt(np.sum(w*(tq-field(p)['theta'])**2))),float(np.sqrt(np.sum(w*np.sum((gt-exactgt)**2,axis=-1))))]
        thermal.append(terr);history.append(error);support.append(a['support']);energies.append(abs(a['U']-ref)/ENERGY)
        if linear:near('linear_T_exact',np.array(terr),0,20.)
    rates={key:np.log2(np.array([x[key] for x in history[:-1]])/np.array([x[key] for x in history[1:]])).tolist() for key in history[0]}
    for key,rate in rates.items():assert np.all(np.array(rate[-2:])>=(1.8 if key=='u_L2' else .9)),(plane,linear,key,history,rate)
    trates=None
    if not linear:
        t=np.array(thermal);trates=np.log2(t[:-1]/t[1:]);assert np.all(trates[-2:]>=np.array([1.8,.9])),trates
    assert np.all(np.diff(energies)<0) and energies[-1]<=.02,energies
    print('THERMOELASTIC_TRACTION_INDEPENDENT '+json.dumps(dict(plane=plane,linear_temperature=linear,levels=LEVELS,rates=rates,errors=history,temperature_interpolation=thermal,temperature_rates=None if trates is None else trates.tolist(),normalized_U_errors=energies,support_work=support,reference_U=ref)))


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermoelastic_traction_independent_overlap_and_v2_translation(plane):
    mesh=square(8);field=lambda p:polynomial(p,plane);snapshot,cfg=solve_case(mesh,field,plane)
    r=production.solve_thermoelasticity(mesh,snapshot,**cfg);a=audit(mesh,snapshot,r,cfg)
    traction=lambda p,n:np.einsum('qij,qj->qi',field(p)['state']['stress'][...,:2,:2],n)
    overlap={**cfg,'traction':{**cfg['traction'],'left':traction}}
    added=direct_line_load(mesh,{'left':traction});s=production.solve_thermoelasticity(mesh,snapshot,**overlap);audit(mesh,snapshot,s,overlap)
    near('overlap_same_u',s.displacement,r.displacement,C0)
    near('overlap_reaction',s.reaction-r.reaction,-added,STRESS)
    assert abs(a['support'])>1.
    oldfield=lambda p:polynomial(p,plane,translation=np.zeros(2));oldcfg={**cfg,'dirichlet':{(i,c):float(oldfield(mesh.nodes)['u'][i,c]) for i,c in cfg['dirichlet']}}
    old=production.solve_thermoelasticity(mesh,snapshot,**oldcfg);aa=audit(mesh,snapshot,old,oldcfg)
    near('v2_rigid_translation',r.displacement-old.displacement,np.broadcast_to(TRANSLATION,r.displacement.shape),C0)
    near('v2_same_stress',r.stress,old.stress,STRESS);near('v2_same_energy',a['U'],aa['U'],ENERGY)
    near('v2_support_work_change',a['support']-aa['support'],np.sum(TRANSLATION*old.reaction.sum(0)),ENERGY)
    # Exact zero-work is the original CONTINUUM case, not assumed for FE reactions.
    v,t=square_geometry();near('original_continuum_zero_work',continuum_ledger(v,t,oldfield,plane)['support_work'],0,ENERGY)


def test_thermoelastic_traction_independent_legacy_none_empty_and_shift():
    mesh=square();field=lambda p:patch(p,'strain',target=np.zeros((2,2)));snapshot,cfg=solve_case(mesh,field,'strain')
    cfg['traction']=None;r=production.solve_thermoelasticity(mesh,snapshot,**cfg)
    empty=production.solve_thermoelasticity(mesh,snapshot,**{**cfg,'traction':{}})
    names=[f.name for f in fields(production.ThermoelasticResult)]
    assert names==list(OLD_FIELDS)+['load_body','load_traction']
    assert all(f.default is None for f in fields(production.ThermoelasticResult)[18:])
    manual=production.ThermoelasticResult(*(getattr(r,name) for name in OLD_FIELDS))
    assert manual.load_body is None and manual.load_traction is None
    for name in OLD_FIELDS:
        x,y=getattr(r,name),getattr(empty,name)
        if isinstance(x,np.ndarray):assert np.array_equal(x,y),name
        else:assert x==y,name
        assert getattr(manual,name) is x or np.array_equal(getattr(manual,name),x)
    audit(mesh,snapshot,r,cfg);near('no_traction_array',r.load_traction,0,STRESS)
    shift=production.freeze_temperature(mesh,snapshot.temperature_k+100.)
    shifted=production.solve_thermoelasticity(mesh,shift,**{**cfg,'reference_temperature_k':TREF+100.})
    near('T_Tref_shift',shifted.displacement,r.displacement,C0);near('shift_U',shifted.physical_elastic_energy,r.physical_elastic_energy,ENERGY)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('kind',['uniform','polynomial'])
def test_thermoelastic_traction_independent_frame_order_similarity(plane,kind):
    base=square();field=(lambda p:patch(p,plane)) if kind=='uniform' else (lambda p:polynomial(p,plane))
    snapshot,cfg=solve_case(base,field,plane);original=production.solve_thermoelasticity(base,snapshot,**cfg);audit(base,snapshot,original,cfg)
    rng=np.random.default_rng(157);order=rng.permutation(len(base.nodes));inverse=np.argsort(order)
    angle=.41;rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]);offset=np.array([.3,-.2])
    for scale in (.1,10.):
        p=(base.nodes[order]*scale)@rotation.T+offset
        mesh=Mesh(p,inverse[base.triangles[::-1]][:,[2,1,0]],{k:inverse[v] for k,v in base.boundary.items()},{k:inverse[v[:,::-1]] for k,v in reversed(list(base.boundary_edges.items()))})
        def moved(p):
            f=field((p-offset)@rotation/scale);gu=np.einsum('ij,...jk,lk->...il',rotation,f['gradient'],rotation)
            eng=engineering(gu)
            return dict(u=scale*f['u']@rotation.T,gradient=gu,strain=eng,theta=f['theta'],body=f['body']@rotation.T/scale,state=parent(eng,ALPHA*f['theta'],plane))
        sn,kw=solve_case(mesh,moved,plane);r=production.solve_thermoelasticity(mesh,sn,**kw);audit(mesh,sn,r,kw,scale)
        near('frame_u',r.displacement[inverse]@rotation/scale,original.displacement,C0)
        near('frame_U',r.physical_elastic_energy/scale**2,original.physical_elastic_energy,ENERGY)
        for name in ('load_body','load_traction','load_thermal','reaction'):
            near('frame_'+name,getattr(r,name)[inverse]@rotation/scale,getattr(original,name),STRESS)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('pressure',[False,True])
def test_thermoelastic_traction_independent_ring_hole_normals(plane,pressure):
    p,t=ring_geometry();mesh=mesh_from_raw(p,t,ring=True);target=-5e6*np.eye(2) if pressure else TARGET
    field=lambda pp:patch(pp,plane,target=target);snapshot,cfg=solve_case(mesh,field,plane)
    calls=[]
    def observed(pp,nn):
        near('callback_unit_normal',np.linalg.norm(nn,axis=1),1.)
        inner=np.max(abs(pp),axis=1)<.5;dot=np.sum(pp*nn,axis=1)
        assert np.all(dot[inner]<0) and np.all(dot[~inner]>0)
        calls.append(len(pp));return nn@target.T
    cfg['traction']={k:observed for k in mesh.boundary_edges}
    r=production.solve_thermoelasticity(mesh,snapshot,**cfg);audit(mesh,snapshot,r,cfg)
    assert calls;near('ring_exact_u',r.displacement,field(p)['u'],C0)
    expected=float(field(p)['state']['energy'][0])*(4-.8**2)
    near('ring_exact_U',r.physical_elastic_energy,expected,ENERGY)
    near('ring_exact_reaction',r.reaction,0,STRESS)


@pytest.mark.parametrize('degree',range(7))
def test_thermoelastic_traction_independent_direct_edge_moments(degree):
    p=np.array([[-.2,.1],[1.4,.8],[0.,1.5]]);mesh=Mesh(p,np.array([[0,1,2]]),{'all':np.arange(3)},{'segment':np.array([[0,1]])})
    d=p[1]-p[0];length=np.linalg.norm(d);vector=np.array([3e6,-2e6])
    callback=lambda pp,nn:(((pp-p[0])@d/(d@d))**degree)[:,None]*vector
    snapshot=production.freeze_temperature(mesh,np.full(3,TREF+20));cfg=dict(reference_temperature_k=TREF,thermal_expansion_per_k=ALPHA,young_modulus=E,poisson_ratio=NU,plane='strain',dirichlet={(i,c):0. for i in range(3) for c in (0,1)},body_force=(0.,0.),traction={'segment':callback})
    r=production.solve_thermoelasticity(mesh,snapshot,**cfg);audit(mesh,snapshot,r,cfg)
    expected=np.zeros((3,2));expected[:2]=length*np.array([1/((degree+1)*(degree+2)),1/(degree+2)])[:,None]*vector
    near('direct_line_moment',r.load_traction,expected,STRESS)
    cold=production.solve_thermoelasticity(mesh,snapshot,**{**cfg,'traction':None})
    near('retained_fixed_edge_load',r.reaction-cold.reaction,-expected,STRESS)
    mesh.boundary_edges['segment']=mesh.boundary_edges['segment'][:,::-1]
    reverse=production.solve_thermoelasticity(mesh,snapshot,**cfg)
    near('edge_endpoint_order',reverse.load_traction,expected,STRESS)


def test_thermoelastic_traction_independent_tags_not_snapshot_hash_and_lifetime():
    mesh=square();field=lambda p:patch(p,'strain');snapshot,cfg=solve_case(mesh,field,'strain');hashes=(snapshot.mesh_hash,snapshot.temperature_hash,snapshot.snapshot_hash)
    mesh.boundary_edges['editable']=mesh.boundary_edges['right'].copy()
    kw={**cfg,'traction':{'editable':np.array([2e6,-1e6])}}
    first=production.solve_thermoelasticity(mesh,snapshot,**kw);audit(mesh,snapshot,first,kw)
    mesh.boundary_edges['editable']=mesh.boundary_edges['top'].copy()
    second=production.solve_thermoelasticity(mesh,snapshot,**kw);audit(mesh,snapshot,second,kw)
    assert not np.array_equal(first.load_traction,second.load_traction)
    assert hashes==(snapshot.mesh_hash,snapshot.temperature_hash,snapshot.snapshot_hash)
    initial=np.full(len(mesh.nodes),TREF+20);sn=production.freeze_temperature(mesh,initial);saved=sn.temperature_k.copy();initial[:]=0
    assert np.array_equal(sn.temperature_k,saved)
    for a in (sn.nodes,sn.triangles,sn.temperature_k):
        with pytest.raises(ValueError):a.setflags(write=True)
    # Geometry binding remains separate from the current mutable tag maps.
    mesh.boundary_edges['editable']=np.array([[0,6]])
    with pytest.raises(ValueError):production.solve_thermoelasticity(mesh,snapshot,**kw)


@pytest.mark.parametrize('bad',['node_order','cell_order','scale','schema','unit','temperature','mutable','collision'])
def test_thermoelastic_traction_independent_snapshot_refusal(bad):
    mesh=square();field=lambda p:patch(p,'strain');snapshot,cfg=solve_case(mesh,field,'strain')
    if bad=='node_order':
        mesh.nodes=mesh.nodes[::-1].copy();mesh.triangles=len(mesh.nodes)-1-mesh.triangles
        mesh.boundary={k:len(mesh.nodes)-1-v for k,v in mesh.boundary.items()};mesh.boundary_edges={k:len(mesh.nodes)-1-v for k,v in mesh.boundary_edges.items()}
    elif bad=='cell_order':mesh.triangles=mesh.triangles[::-1].copy()
    elif bad in ('scale','collision'):mesh.nodes*=1.001
    elif bad=='schema':object.__setattr__(snapshot,'schema_version',2)
    elif bad=='unit':object.__setattr__(snapshot,'temperature_unit','C')
    elif bad=='temperature':object.__setattr__(snapshot,'temperature_k',np.frombuffer((snapshot.temperature_k+1.).tobytes(),dtype='<f8'))
    else:object.__setattr__(snapshot,'temperature_k',snapshot.temperature_k.copy())
    if bad=='collision':
        expected=(snapshot.mesh_hash,snapshot.temperature_hash,snapshot.snapshot_hash)
        with mockpatch.object(production,'_hashes',return_value=expected),mockpatch.object(production,'_fingerprint',return_value=snapshot.mesh_hash):
            with pytest.raises(ValueError,match='stale|mismatch'):production.solve_thermoelasticity(mesh,snapshot,**cfg)
    else:
        with pytest.raises(ValueError):production.solve_thermoelasticity(mesh,snapshot,**cfg)


@pytest.mark.parametrize('bad',['missing_tag','interior','not_edge','duplicate_in_tag','duplicate_across','empty','float','bool','zero','negative_index','range','shape'])
def test_thermoelastic_traction_independent_complete_selection_before_callback(bad):
    mesh=square();field=lambda p:patch(p,'strain');snapshot,cfg=solve_case(mesh,field,'strain');calls=[]
    def observed(p,n):calls.append(1);return np.zeros_like(p)
    mesh.boundary_edges['bad']=mesh.boundary_edges['right'].copy()
    mapping={'top':observed,'bad':observed}
    if bad=='missing_tag':mapping['missing']=observed
    elif bad=='interior':mesh.boundary_edges['bad']=np.array([[0,6]])
    elif bad=='not_edge':mesh.boundary_edges['bad']=np.array([[0,4]])
    elif bad=='duplicate_in_tag':mesh.boundary_edges['bad']=np.repeat(mesh.boundary_edges['right'][:1],2,axis=0)
    elif bad=='duplicate_across':mapping['right']=observed
    elif bad=='empty':mesh.boundary_edges['bad']=np.empty((0,2),int)
    elif bad=='float':mesh.boundary_edges['bad']=mesh.boundary_edges['right'].astype(float)
    elif bad=='bool':mesh.boundary_edges['bad']=np.array([[True,False]])
    elif bad=='zero':mesh.boundary_edges['bad']=np.array([[0,0]])
    elif bad=='negative_index':mesh.boundary_edges['bad']=np.array([[-1,0]])
    elif bad=='range':mesh.boundary_edges['bad']=np.array([[0,len(mesh.nodes)]])
    else:mesh.boundary_edges['bad']=np.array([0,1])
    with pytest.raises(ValueError):production.solve_thermoelasticity(mesh,snapshot,**{**cfg,'traction':mapping})
    assert not calls


@pytest.mark.parametrize('bad',['scalar','vector3','complex','bool','nan','infinity','callback_vector','callback_column','callback_complex','callback_bool','callback_nan','overflow'])
def test_thermoelastic_traction_independent_traction_field_refusal(bad):
    mesh=square();field=lambda p:patch(p,'strain');snapshot,cfg=solve_case(mesh,field,'strain')
    values={'scalar':1.,'vector3':[1.,2.,3.],'complex':[1+1j,2.],'bool':[True,False],'nan':[np.nan,1.],'infinity':[np.inf,1.],
      'callback_vector':lambda p,n:np.array([1.,2.]),'callback_column':lambda p,n:np.ones((len(p),1)),
      'callback_complex':lambda p,n:np.ones(p.shape,complex),'callback_bool':lambda p,n:np.ones(p.shape,bool),'callback_nan':lambda p,n:np.full(p.shape,np.nan),'overflow':[np.finfo(float).max,np.finfo(float).max]}
    if bad=='overflow':mesh.nodes*=10.;snapshot=production.freeze_temperature(mesh,np.full(len(mesh.nodes),TREF+20))
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(ValueError):production.solve_thermoelasticity(mesh,snapshot,**{**cfg,'traction':{'right':values[bad]}})


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermoelastic_traction_independent_components_and_rigid_rank(plane):
    base=square(2);n=len(base.nodes);p=np.r_[base.nodes,base.nodes+[2.,0.]];t=np.r_[base.triangles,base.triangles+n]
    mesh=Mesh(p,t,{'all':np.r_[np.unique(np.concatenate(list(base.boundary.values()))),np.unique(np.concatenate(list(base.boundary.values())))+n]},
              {'all':np.r_[np.concatenate(list(base.boundary_edges.values())),np.concatenate(list(base.boundary_edges.values()))+n]})
    field=lambda pp:patch(pp,plane);snapshot=production.freeze_temperature(mesh,TREF+field(p)['theta']);values=field(p)['u']
    fixed={(i,c):values[i,c] for i,c in [(0,0),(0,1),(2,1),(n,0),(n,1),(n+2,1)]}
    traction=lambda pp,nn:nn@TARGET.T
    cfg=dict(reference_temperature_k=TREF,thermal_expansion_per_k=ALPHA,young_modulus=E,poisson_ratio=NU,plane=plane,dirichlet=fixed,body_force=(0.,0.),traction={'all':traction})
    r=production.solve_thermoelasticity(mesh,snapshot,**cfg);audit(mesh,snapshot,r,cfg)
    near('components_exact_patch',r.displacement,values,C0)
    for keys in [[],[(0,0),(0,1),(2,1)],[(0,0),(0,1),(2,0),(n,0),(n,1),(n+2,1)]]:
        with pytest.raises(ValueError):production.solve_thermoelasticity(mesh,snapshot,**{**cfg,'dirichlet':{k:fixed.get(k,0.) for k in keys}})


@pytest.mark.parametrize('wrong',['thermal_sign','omit_g','add_qn','subtract_qn','three_alpha','naive_PE','PE_as_PS','zz_omission','PE_residual_U','centroid_T_squared','support_work_omission','line_weight','endpoint_lumping','drop_fixed_line','flipped_hole','thermal_as_external','swap_body_line'])
def test_thermoelastic_traction_independent_wrong_runtime(wrong):
    mesh=square();field=lambda p:polynomial(p,'strain')
    if wrong in ('add_qn','subtract_qn'):field=lambda p:patch(p,'strain')
    if wrong=='flipped_hole':
        p,t=ring_geometry();mesh=mesh_from_raw(p,t,True);field=lambda p:patch(p,'strain')
    snapshot,cfg=solve_case(mesh,field,'strain',overlap=wrong=='drop_fixed_line')
    thermal_real,line_real=production._thermal_load,production._traction_load
    expected='physical_energy';altered={**cfg}
    if wrong in ('three_alpha','naive_PE','PE_as_PS'):
        if wrong=='three_alpha':altered['thermal_expansion_per_k']*=3
        elif wrong=='naive_PE':altered['thermal_expansion_per_k']/=1+NU
        else:altered['plane']='stress'
        expected='load_thermal'
    def badthermal(*args,**kw):
        result=thermal_real(*args,**kw)
        return -result if wrong=='thermal_sign' else np.zeros_like(result) if wrong=='omit_g' else result
    def badline(m,p,t,mapping):
        if wrong=='endpoint_lumping':
            owners={(a,b):c for a,b,c in exterior_segments(p,t)};load=np.zeros_like(p)
            for tag,fn in mapping.items():
                for a,b in m.boundary_edges[tag]:
                    c=owners[tuple(sorted((int(a),int(b))))];_,_,_,normals=segment_rule(p[a],p[b],p[c],1)
                    values=fn(p[[a,b]],np.broadcast_to(normals[0],(2,2)))
                    load[[a,b]]+=np.linalg.norm(p[b]-p[a])*values/2
            return load.ravel()
        if wrong=='flipped_hole':mapping={tag:(lambda pp,nn,fn=fn:-fn(pp,nn)) if tag=='inner' else fn for tag,fn in mapping.items()}
        load=line_real(m,p,t,mapping)
        if wrong=='line_weight':load=1.1*load
        elif wrong=='drop_fixed_line':
            load=load.copy()
            for i,c in cfg['dirichlet']:load[2*i+c]=0.
        elif wrong in ('add_qn','subtract_qn'):
            extra=direct_line_load(m,{tag:(lambda pp,nn:-(parent(np.zeros(3),ALPHA*20,'strain')['stress'][:2,:2]@nn.T).T) for tag in mapping})
            load=load+(1 if wrong=='add_qn' else -1)*extra.ravel()
        return load
    if wrong in ('thermal_sign','omit_g'):expected='load_thermal'
    if wrong in ('add_qn','subtract_qn','line_weight','endpoint_lumping','drop_fixed_line','flipped_hole'):expected='load_traction'
    with mockpatch.object(production,'_thermal_load',badthermal),mockpatch.object(production,'_traction_load',badline):r=production.solve_thermoelasticity(mesh,snapshot,**altered)
    if wrong=='zz_omission':r.sigma_zz=np.zeros_like(r.sigma_zz);expected='sigma_zz'
    elif wrong=='PE_residual_U':
        b,w,_,_=triangle_rule(mesh.nodes[mesh.triangles],8);a=ALPHA*(np.einsum('qa,ta->tq',b,snapshot.temperature_k[mesh.triangles])-TREF)
        r.physical_elastic_energy-=float(np.sum(w*.5*E*a*a))
    elif wrong=='centroid_T_squared':
        _,w,_,_=triangle_rule(mesh.nodes[mesh.triangles],2);a=ALPHA*(snapshot.temperature_k[mesh.triangles].mean(1)-TREF)
        r.physical_elastic_energy=float(np.sum(w.sum(1)*parent(r.total_strain,a,'strain')['energy']))
    elif wrong=='support_work_omission':r.physical_elastic_energy-=.5*float(np.sum(r.displacement*r.reaction))
    elif wrong=='thermal_as_external':r.load_external=r.load_external+r.load_thermal;expected='load_external'
    elif wrong=='swap_body_line':r.load_body,r.load_traction=r.load_traction,r.load_body;expected='load_body'
    with pytest.raises(AssertionError,match=expected):audit(mesh,snapshot,r,cfg)
