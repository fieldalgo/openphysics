# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent acceptance of the prescribed-temperature mechanical stage.

Continuum truth comes from the original 3D law, never production/refsol helpers.
Gates were registered in lab commit 34241af before reading the candidate API.
"""
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh, Mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from thermoelasticity_independent_oracle import (
    original_3d, nonlinear_fields, compatible, triangle_rule, E0, NU0, ALPHA0, TREF0)


def solve(m, theta, plane, bc, **kw):
    args = dict(reference_temperature_k=TREF0, thermal_expansion_per_k=ALPHA0,
                young_modulus=E0, poisson_ratio=NU0, plane=plane, dirichlet=bc)
    args.update(kw)
    return solve_thermoelasticity(m, freeze_temperature(m, TREF0+theta), **args)


def exterior(m, u):
    return {(int(i), c): float(u[i,c]) for i in np.unique(np.concatenate(list(m.boundary.values()))) for c in (0,1)}


def geometry(m, order=8):
    b, w = triangle_rule(order)
    vertices = m.nodes[m.triangles]
    det = np.abs(np.linalg.det(vertices[:,1:]-vertices[:,:1]))
    inv = np.linalg.inv(np.concatenate((np.ones((*vertices.shape[:2],1)),vertices),axis=2))
    grad = inv[:,1:,:].swapaxes(1,2)
    return b, det[:,None]*w, np.einsum('qa,tad->tqd',b,vertices), grad


def reconstruction(m, r, plane, order=8):
    b,w,p,g = geometry(m,order)
    gu = np.einsum('tai,taj->tji',g,r.displacement[m.triangles])
    e = np.stack((gu[:,0,0],gu[:,1,1],gu[:,0,1]+gu[:,1,0]),axis=-1)
    theta = b @ (r.temperature_snapshot.temperature_k[m.triangles]-r.reference_temperature_k).T
    state = original_3d(e[:,None,:],theta.T,plane,alpha=r.thermal_expansion_per_k)
    return b,w,p,g,gu,e,theta.T,state


def audit(m,r,plane,body=(0.,0.)):
    b,w,p,g,gu,e,theta,state = reconstruction(m,r,plane)
    scale = E0*max(np.max(np.abs(e)), np.max(np.abs(theta*r.thermal_expansion_per_k)),1e-12)
    np.testing.assert_allclose(e,r.total_strain,atol=1e-10*scale/E0,rtol=1e-10)
    center=original_3d(e,(r.temperature_snapshot.temperature_k[m.triangles].mean(1)-r.reference_temperature_k),plane,alpha=r.thermal_expansion_per_k)
    for actual,expected in [(r.stress,np.stack((center['sigma'][:,0,0],center['sigma'][:,1,1],center['sigma'][:,0,1]),axis=-1)),(r.sigma_zz,center['sigma'][:,2,2])]:
        np.testing.assert_allclose(actual,expected,atol=scale*1e-10,rtol=1e-10)
    np.testing.assert_allclose(r.epsilon_zz,center['total'][:,2,2],atol=scale/E0*1e-10)
    np.testing.assert_allclose(r.thermal_strain, np.stack((center['thermal'][:,0,0],center['thermal'][:,1,1],2*center['thermal'][:,0,1]),axis=-1),atol=1e-10*scale/E0)
    np.testing.assert_allclose(r.elastic_strain,r.total_strain-r.thermal_strain,atol=1e-10*scale/E0)
    energy=np.sum(w*state['energy']); escale=max(E0*(scale/E0)**2,abs(energy),1e-20)
    assert abs(energy-r.physical_elastic_energy)<=1e-10*escale
    # Integrate initial stress from the parent 3D law, without a reduced D/RHS.
    zero=original_3d(np.zeros_like(e[:,None,:]),theta,plane,alpha=r.thermal_expansion_per_k)
    local=-np.einsum('tq,tqij,taj->tai',w,zero['sigma'][...,:2,:2],g)
    thermal=np.zeros_like(r.load_thermal)
    np.add.at(thermal,m.triangles.ravel(),local.reshape(-1,2))
    np.testing.assert_allclose(r.load_thermal,thermal,atol=scale*1e-10,rtol=1e-10)
    local_internal=np.einsum('tq,tqij,taj->tai',w,state['sigma'][...,:2,:2],g)
    internal=np.zeros_like(r.reaction)
    np.add.at(internal,m.triangles.ravel(),local_internal.reshape(-1,2))
    np.testing.assert_allclose(r.residual,internal-r.load_external,atol=1e-10*scale,rtol=1e-10)
    np.testing.assert_allclose(r.residual,r.reaction,atol=1e-9*scale,rtol=1e-9)
    force=body(p.reshape(-1,2)).reshape(p.shape) if callable(body) else np.broadcast_to(body,p.shape)
    local_external=np.einsum('tq,qa,tqi->tai',w,b,force)
    external=np.zeros_like(r.load_external)
    np.add.at(external,m.triangles.ravel(),local_external.reshape(-1,2))
    np.testing.assert_allclose(r.load_external,external,atol=1e-10*scale,rtol=1e-10)
    tangent=original_3d(e,np.zeros(len(e)),plane)['sigma']
    uku=np.sum(w.sum(1)*np.einsum('tij,tji->t',tangent[:,:2,:2],gu))
    u=r.displacement.ravel();f=r.load_external.ravel();th=r.load_thermal.ravel();reaction=r.reaction.ravel()
    ct=np.sum(w*zero['energy'])
    for error in [uku-u@(f+th+reaction),energy-(.5*uku-u@th+ct),2*energy-(u@f+u@reaction-u@th+2*ct),np.sum(w*np.einsum('tqij,tji->tq',state['sigma'][...,:2,:2],gu))-u@(f+reaction)]:
        assert abs(error)<=1e-10*max(escale,abs(uku),ct)
    for forces in [r.load_external+r.reaction,r.load_thermal]:
        assert np.linalg.norm(forces.sum(0),np.inf)<1e-9*scale
        assert abs(np.sum(m.nodes[:,0]*forces[:,1]-m.nodes[:,1]*forces[:,0]))<1e-9*scale
    return energy


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('theta,alpha',[(20.,ALPHA0),(-20.,ALPHA0),(20.,-ALPHA0),(20.,0.)])
def test_thermoelasticity_independent_uniform(plane,theta,alpha):
    m=rectangle_mesh(1,1,4,4);a=theta*alpha
    factor=1 if plane=='stress' else 1+NU0
    r=solve(m,np.full(m.num_nodes,theta),plane,{(0,0):0.,(0,1):0.,(4,1):0.},thermal_expansion_per_k=alpha)
    np.testing.assert_allclose(r.displacement,factor*a*m.nodes,atol=1e-10*max(abs(a),ALPHA0))
    np.testing.assert_allclose(r.stress,0,atol=1e-10*E0*max(abs(a),ALPHA0))
    np.testing.assert_allclose(r.sigma_zz,0 if plane=='stress' else -E0*a,atol=1e-10*E0*max(abs(a),ALPHA0))
    audit(m,r,plane)
    expected=0 if plane=='stress' else .5*E0*a*a
    assert abs(r.physical_elastic_energy-expected)<1e-10*E0*max(a*a,ALPHA0**2)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('theta',[20.,-20.])
def test_thermoelasticity_independent_constrained(plane,theta):
    m=rectangle_mesh(1,1,4,4)
    r=solve(m,np.full(m.num_nodes,theta),plane,exterior(m,np.zeros_like(m.nodes)))
    audit(m,r,plane)
    np.testing.assert_allclose(r.displacement,0,atol=1e-14)
    stress=original_3d(np.zeros(3),theta,plane)['sigma']
    expected=np.zeros_like(m.nodes)
    for tag,normal in [('left',[-1,0]),('right',[1,0]),('bottom',[0,-1]),('top',[0,1])]:
        for edge in m.boundary_edges[tag]:
            value=stress[:2,:2]@normal*np.linalg.norm(np.diff(m.nodes[edge],axis=0))/2
            expected[edge]+=value
    np.testing.assert_allclose(r.reaction,expected,atol=1e-10*E0*ALPHA0*abs(theta))


def error_metrics(m,r,plane,kind,order):
    b,w,p,g,gu,e,theta,state=reconstruction(m,r,plane,order)
    if kind=='linear':
        exact_u,exact_e,exact_t=compatible(p,plane)
        exact=original_3d(exact_e,exact_t,plane)
        dt=theta-exact_t
        dgt=(np.einsum('tai,ta->ti',g,r.temperature_snapshot.temperature_k[m.triangles])-np.array([20,0]))[:,None,:]
    else:
        field=nonlinear_fields(p,plane,polynomial=kind=='polynomial')
        exact_u,exact_e,exact_t,exact=field['displacement'],field['strain'],field['theta'],field['state']
        dt=theta-exact_t
        dgt=np.einsum('tai,ta->ti',g,r.temperature_snapshot.temperature_k[m.triangles])[:,None,:]-field['grad_theta']
    uh=np.einsum('qa,tad->tqd',b,r.displacement[m.triangles]);du=uh-exact_u
    if kind=='linear':
        rigid=np.zeros((*p.shape[:-1],2,3));rigid[...,0,0]=1;rigid[...,1,1]=1;rigid[...,0,2]=-p[...,1];rigid[...,1,2]=p[...,0]
        coeff=np.linalg.solve(np.einsum('tq,tqik,tqil->kl',w,rigid,rigid),np.einsum('tq,tqik,tqi->k',w,rigid,du))
        du-=np.einsum('tqik,k->tqi',rigid,coeff)
    de=e[:,None,:]-exact_e
    x,y=p[...,0],p[...,1]
    if kind=='linear':
        factor=1 if plane=='stress' else 1+NU0
        gradient=factor*ALPHA0*np.stack((10+20*x,-20*y,20*y,10+20*x),axis=-1).reshape((*x.shape,2,2))
        gu=gu-np.array([[0,-coeff[2]],[coeff[2],0]])
    elif kind=='polynomial':
        gradient=1e-4*np.stack((2*x*y+y*y+x*x,x*x+2*x*y, y*y-4*x*y,2*x*y-2*x*x+.75*y*y),axis=-1).reshape((*x.shape,2,2))
    else:
        dx=np.pi*np.cos(np.pi*x)*np.sin(np.pi*y);dy=np.pi*np.sin(np.pi*x)*np.cos(np.pi*y)
        gradient=np.stack((1e-4*dx,1e-4*dy,.6e-4*dx,.6e-4*dy),axis=-1).reshape((*x.shape,2,2))
    dg=gu[:,None]-gradient
    ds=state['sigma']-exact['sigma']
    tangent=original_3d(de,np.zeros_like(theta),plane)
    values=[np.sum(du*du,axis=-1),np.sum(dg*dg,axis=(-2,-1)),np.sum(ds*ds,axis=(-2,-1)),2*tangent['energy'],dt**2,np.sum(dgt*dgt,axis=-1)]
    norms=np.array([np.sqrt(np.sum(w*v)) for v in values])
    return norms,np.sum(w*exact['energy'])


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('kind',['linear','sine','polynomial'])
def test_thermoelasticity_independent_convergence(plane,kind):
    history=[];energy_errors=[]
    for n in (8,16,32):
        m=rectangle_mesh(1,1,n,n)
        if kind=='linear':
            u,e,t=compatible(m.nodes,plane);bc={(0,0):0.,(0,1):0.,(n,1):0.};body=(0.,0.)
        else:
            f=nonlinear_fields(m.nodes,plane,polynomial=kind=='polynomial');u,t=f['displacement'],f['theta'];bc=exterior(m,u)
            body=lambda p:nonlinear_fields(p,plane,polynomial=kind=='polynomial')['body']
        r=solve(m,t,plane,bc,body_force=body);audit(m,r,plane,body)
        errors,energy=error_metrics(m,r,plane,kind,8)
        errors10,_=error_metrics(m,r,plane,kind,10)
        np.testing.assert_allclose(errors[:4],errors10[:4],rtol=.01)
        _,e12=error_metrics(m,r,plane,kind,12);_,e16=error_metrics(m,r,plane,kind,16)
        assert abs(e12-e16)<1e-8*max(e16,E0*(20*ALPHA0)**2)
        if kind=='linear':assert max(errors[4:])<1e-10
        history.append(errors);energy_errors.append(abs(r.physical_elastic_energy-energy)/max(energy,E0*(20*ALPHA0)**2))
    count=4 if kind=='linear' else 6
    rates=np.log2(np.array(history[:-1])[:,:count]/np.array(history[1:])[:,:count])
    print(plane,kind,'errors',np.array(history),'rates',rates,'energy',energy_errors)
    assert np.all(rates>=np.array([1.8,.9,.9,.9,1.8,.9])[:count])
    assert np.all(np.diff(energy_errors)<0)
    assert energy_errors[-1]<=.02


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermoelasticity_independent_support_work_shift(plane):
    m=rectangle_mesh(1,1,5,5);u=1e-4*np.column_stack((m.nodes[:,0]+m.nodes[:,1],2*m.nodes[:,1]))
    t=10+20*m.nodes[:,0];bc=exterior(m,u)
    r=solve(m,t,plane,bc,body_force=(100.,-40.));audit(m,r,plane,(100.,-40.))
    assert abs(np.sum(r.displacement*r.reaction))>1
    shifted=solve(m,t+100,plane,bc,body_force=(100.,-40.),reference_temperature_k=TREF0+100)
    np.testing.assert_allclose(shifted.displacement,r.displacement,atol=1e-14)
    assert shifted.physical_elastic_energy==pytest.approx(r.physical_elastic_energy,rel=1e-10)


@pytest.mark.parametrize('change',['coordinate','node_order','cell_order','units','metadata','temperature','shape'])
def test_thermoelasticity_independent_snapshot_reject(change):
    m=rectangle_mesh(1,1,3,3);s=freeze_temperature(m,np.full(m.num_nodes,300.))
    if change=='coordinate':m.nodes[5,0]+=.01
    elif change=='node_order':m.nodes[[5,6]]=m.nodes[[6,5]]
    elif change=='cell_order':m.triangles[[0,1]]=m.triangles[[1,0]]
    elif change=='units':object.__setattr__(s,'temperature_unit','C')
    elif change=='metadata':object.__setattr__(s,'mesh_hash','fnv1a64:0000000000000000')
    elif change=='temperature':object.__setattr__(s,'temperature_k',np.full(m.num_nodes,301.))
    else:object.__setattr__(s,'temperature_k',np.full((m.num_nodes,1),300.))
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,reference_temperature_k=TREF0,thermal_expansion_per_k=ALPHA0,young_modulus=E0,poisson_ratio=NU0,plane='strain',dirichlet={(0,0):0.,(0,1):0.,(3,1):0.})


def test_thermoelasticity_independent_snapshot_copy():
    m=rectangle_mesh(1,1,2,2);t=np.full(m.num_nodes,300.);s=freeze_temperature(m,t);ident=s.snapshot_hash
    t[:]=301.;m.nodes[4,0]+=.01
    assert np.all(s.temperature_k==300.) and s.nodes[4,0]==.5
    for a in (s.nodes,s.triangles,s.temperature_k):
        with pytest.raises(ValueError):a.flags.writeable=True
    fresh=freeze_temperature(rectangle_mesh(1,1,2,2),np.full(9,300.))
    assert fresh.snapshot_hash==ident
    for bad in (np.full(9,np.nan),np.full(9,-1.),np.full((9,1),300.),np.full(9,np.inf)):
        with pytest.raises(ValueError):freeze_temperature(rectangle_mesh(1,1,2,2),bad)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('transform',['rotation','order'])
def test_thermoelasticity_independent_mesh_invariance(plane,transform):
    m=rectangle_mesh(1,1,3,3);t=10+20*m.nodes[:,0]
    affine=np.array([[1e-4,2e-5],[-3e-5,1.5e-4]])
    u=m.nodes@affine.T
    r=solve(m,t,plane,exterior(m,u));audit(m,r,plane)
    if transform=='rotation':
        q=np.array([[.6,-.8],[.8,.6]])
        new=Mesh(m.nodes@q.T+np.array([2.,-1.]),m.triangles.copy(),m.boundary,m.boundary_edges)
        expected=u@q.T;perm=np.arange(m.num_nodes)
    else:
        perm=np.arange(m.num_nodes)[::-1];inverse=np.argsort(perm);q=np.eye(2)
        new=Mesh(m.nodes[perm],inverse[m.triangles[::-1, [1,2,0]]],{k:inverse[v] for k,v in m.boundary.items()},{k:inverse[v[::-1,::-1]] for k,v in m.boundary_edges.items()})
        expected=u[perm]
    actual=solve(new,t[perm],plane,exterior(new,expected));audit(new,actual,plane)
    np.testing.assert_allclose(actual.displacement,r.displacement[perm]@q.T,atol=1e-14)
    np.testing.assert_allclose(actual.reaction,r.reaction[perm]@q.T,atol=E0*ALPHA0*20*1e-10)
    assert actual.physical_elastic_energy==pytest.approx(r.physical_elastic_energy,rel=1e-10)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermoelasticity_independent_disconnected_components(plane):
    m=rectangle_mesh(1,1,2,2);count=m.num_nodes
    nodes=np.concatenate((m.nodes,m.nodes+[2.,0.]));tri=np.concatenate((m.triangles,m.triangles+count))
    boundary={k:np.concatenate((v,v+count)) for k,v in m.boundary.items()}
    combined=Mesh(nodes,tri,boundary)
    theta=np.concatenate((np.full(count,20.),np.full(count,-10.)))
    factor=1 if plane=='stress' else 1+NU0
    exact=np.concatenate((factor*ALPHA0*20*m.nodes,factor*ALPHA0*(-10)*m.nodes))
    bc={(offset+i,c):0. for offset in (0,count) for i,c in ((0,0),(0,1),(2,1))}
    r=solve(combined,theta,plane,bc);audit(combined,r,plane)
    np.testing.assert_allclose(r.displacement,exact,atol=1e-14)
    del bc[(count+2,1)]
    with pytest.raises(ValueError):solve(combined,theta,plane,bc)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_thermoelasticity_independent_zero_alpha_mechanical(plane):
    m=rectangle_mesh(1,1,4,4);matrix=np.array([[1e-4,2e-5],[-3e-5,2e-4]])
    u=m.nodes@matrix.T
    r=solve(m,10+5*m.nodes[:,0]**2,plane,exterior(m,u),thermal_expansion_per_k=0.)
    audit(m,r,plane)
    np.testing.assert_allclose(r.displacement,u,atol=1e-14)
    np.testing.assert_array_equal(r.load_thermal,0.)


def test_thermoelasticity_independent_collision_does_not_bind(monkeypatch):
    import galerkin.thermoelasticity as production
    monkeypatch.setattr(production,'_fingerprint',lambda *args:'fnv1a64:0000000000000000')
    m=rectangle_mesh(1,1,2,2);s=freeze_temperature(m,np.full(m.num_nodes,300.));m.nodes[4,0]+=.01
    with pytest.raises(ValueError,match='stale or mismatched'):
        solve_thermoelasticity(m,s,reference_temperature_k=TREF0,thermal_expansion_per_k=ALPHA0,young_modulus=E0,poisson_ratio=NU0,plane='stress',dirichlet={(0,0):0.,(0,1):0.,(2,1):0.})
