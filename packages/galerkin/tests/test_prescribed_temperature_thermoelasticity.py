"""Prescribed-temperature mechanical-stage checks; no thermal solver is invoked."""
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from refsol.thermoelasticity import uniform_free, uniform_constrained, sine_manufactured


def material(plane):
    return dict(young_modulus=2e9, poisson_ratio=.27, plane=plane,
                reference_temperature_k=293.15, thermal_expansion_per_k=1.2e-5)


def solve(mesh, temp, plane_mode, bc, **kw):
    return solve_thermoelasticity(mesh, freeze_temperature(mesh,temp),
                                 dirichlet=bc, **(material(plane_mode)|kw))


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('theta,alpha',[(20,1.2e-5),(-20,1.2e-5),(20,-1.2e-5),(20,0.)])
def test_uniform_free(plane,theta,alpha):
    m=rectangle_mesh(1.,1.,4,4); mat=material(plane)|dict(thermal_expansion_per_k=alpha)
    exact=uniform_free(m.nodes,theta,**mat)
    r=solve(m,exact.temperature_k,plane,{(0,0):0.,(0,1):0.,(4,1):0.},thermal_expansion_per_k=alpha)
    np.testing.assert_allclose(r.displacement,exact.displacement,atol=1e-15)
    np.testing.assert_allclose(r.stress,0.,atol=2e-8)
    np.testing.assert_allclose(r.sigma_zz,exact.sigma_zz[0],atol=2e-8)
    expected=0. if plane=='stress' else .5*mat['young_modulus']*(alpha*theta)**2
    assert abs(r.physical_elastic_energy-expected)<1e-10*max(1.,expected)
    assert np.max(np.abs(r.reaction))<2e-8


@pytest.mark.parametrize('plane',['stress','strain'])
def test_uniform_constrained(plane):
    m=rectangle_mesh(1.,1.,4,4)
    boundary=np.unique(np.concatenate(list(m.boundary.values())))
    r=solve(m,np.full(m.num_nodes,313.15),plane,{(int(i),c):0. for i in boundary for c in (0,1)})
    exact=uniform_constrained(m.nodes,**material(plane))
    np.testing.assert_allclose(r.displacement,0.,atol=1e-16)
    np.testing.assert_allclose(r.stress, np.broadcast_to(exact.stress[0],r.stress.shape),atol=1e-8)
    np.testing.assert_allclose(r.reaction.reshape(-1,2).sum(0),0.,atol=1e-8)
    assert r.physical_elastic_energy==pytest.approx(exact.energy_density[0],rel=1e-12)


def test_snapshot_and_constraints():
    m=rectangle_mesh(1.,1.,2,2); t=np.full(m.num_nodes,300.); s=freeze_temperature(m,t)
    t[:]=0
    assert np.all(s.temperature_k==300)
    with pytest.raises(ValueError):s.temperature_k.flags.writeable=True
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,dirichlet={},**material('stress'))
    m.nodes[1,0]+=.01
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,dirichlet={},**material('stress'))
    for bad in [np.zeros((9,1)),np.full(9,-1.),np.full(9,np.nan)]:
        with pytest.raises(ValueError):freeze_temperature(m,bad)


def quadrature(mesh,order):
    z,w=np.polynomial.legendre.leggauss(order);z=(z+1)/2;w=w/2
    r,s=np.meshgrid(z,z,indexing='ij');wr,ws=np.meshgrid(w,w,indexing='ij')
    b=np.stack([(1-r)*(1-s),r*(1-s),s],axis=-1).reshape(-1,3)
    weight=(2*wr*ws*(1-s)).ravel()
    p=mesh.nodes[mesh.triangles];j=p[:,1:]-p[:,:1]
    area=np.abs(np.linalg.det(j))/2
    return b,weight,area,np.einsum('qi,tij->tqj',b,p)


def errors(mesh,result,plane,order):
    b,w,area,p=quadrature(mesh,order);tri=mesh.triangles
    exact=sine_manufactured(p.reshape(-1,2),**material(plane))
    uh=np.einsum('qi,tij->tqj',b,result.displacement[tri])
    grad=np.linalg.solve(mesh.nodes[tri][:,1:]-mesh.nodes[tri][:,:1],
                         result.displacement[tri][:,1:]-result.displacement[tri][:,:1]).swapaxes(1,2)
    du=uh-exact.displacement.reshape(uh.shape)
    dg=grad[:,None]-exact.gradient.reshape((*p.shape[:2],2,2))
    tq=np.einsum('qi,ti->tq',b,result.temperature_snapshot.temperature_k[tri])
    tc=result.temperature_snapshot.temperature_k[tri].mean(1)
    mat=material(plane);coef=mat['young_modulus']*mat['thermal_expansion_per_k']/(1-mat['poisson_ratio'] if plane=='stress' else 1-2*mat['poisson_ratio'])
    sh=result.stress[:,None,:]-coef*(tq-tc[:,None])[:,:,None]*np.array([1,1,0])
    ds=sh-exact.stress.reshape(sh.shape)
    sz=result.sigma_zz[:,None]-(coef*(tq-tc[:,None]) if plane=='strain' else 0)
    dz=sz-exact.sigma_zz.reshape(tq.shape)
    vals=[np.sum(du**2,axis=-1),np.sum(dg**2,axis=(-1,-2)),ds[:,:,0]**2+ds[:,:,1]**2+2*ds[:,:,2]**2+dz**2]
    # Independent reduced tangent energy norm and temperature interpolation norms.
    de=np.stack([dg[:,:,0,0],dg[:,:,1,1],dg[:,:,0,1]+dg[:,:,1,0]],axis=-1)
    from refsol.thermoelasticity import state_from_3d
    tangent=state_from_3d(de.reshape(-1,3),np.full(de.shape[0]*de.shape[1],mat['reference_temperature_k']),**mat).stress.reshape(de.shape)
    vals.append(np.sum(de*tangent,axis=-1))
    dt=tq-exact.temperature_k.reshape(tq.shape)
    gt=np.linalg.solve(mesh.nodes[tri][:,1:]-mesh.nodes[tri][:,:1],(result.temperature_snapshot.temperature_k[tri][:,1:]-result.temperature_snapshot.temperature_k[tri][:,:1])[...,None])[...,0]
    dgt=gt[:,None]-exact.temperature_gradient.reshape((*p.shape[:2],2))
    vals.extend([dt*dt,np.sum(dgt*dgt,axis=-1)])
    return np.array([np.sqrt(np.sum(area[:,None]*w*v)) for v in vals])


@pytest.mark.parametrize('plane',['stress','strain'])
def test_sine_convergence(plane):
    history=[]; energy_errors=[]
    for n in (8,16,32):
        m=rectangle_mesh(1.,1.,n,n);mat=material(plane)
        exact=sine_manufactured(m.nodes,**mat)
        boundary=np.unique(np.concatenate(list(m.boundary.values())))
        bc={(int(i),c):float(exact.displacement[i,c]) for i in boundary for c in (0,1)}
        r=solve(m,exact.temperature_k,plane,bc,body_force=lambda p:sine_manufactured(p,**mat).body_force)
        e=errors(m,r,plane,8);e10=errors(m,r,plane,10)
        np.testing.assert_allclose(e,e10,rtol=.01)
        history.append(e)
        b,w,area,p=quadrature(m,12)
        ue=np.sum(area[:,None]*w*sine_manufactured(p.reshape(-1,2),**mat).energy_density.reshape(p.shape[:2]))
        b16,w16,a16,p16=quadrature(m,16)
        ue16=np.sum(a16[:,None]*w16*sine_manufactured(p16.reshape(-1,2),**mat).energy_density.reshape(p16.shape[:2]))
        assert abs(ue-ue16)<1e-8*max(1.,ue)
        energy_errors.append(abs(r.physical_elastic_energy-ue)/max(ue,mat['young_modulus']*(mat['thermal_expansion_per_k']*20)**2))
        np.testing.assert_allclose((r.load_external+r.reaction).reshape(-1,2).sum(0),0.,atol=1e-6)
    rates=np.log2(np.array(history[:-1])/np.array(history[1:]))
    print(plane,'errors',np.array(history),'rates',rates)
    assert np.all(rates>=np.array([1.8,.9,.9,.9,1.8,.9]))
    assert np.all(np.diff(energy_errors)<0)
    assert energy_errors[-1]<=.02
    print('physical energy normalized errors',energy_errors)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_energy_work_force_moment_and_shift(plane):
    from refsol.thermoelasticity import state_from_3d
    m=rectangle_mesh(1.,1.,5,5);mat=material(plane)
    temp=303.15+20*m.nodes[:,0]
    boundary=np.unique(np.concatenate(list(m.boundary.values())))
    bc={(int(i),c):float(1e-4*m.nodes[i,c]) for i in boundary for c in (0,1)}
    r=solve(m,temp,plane,bc,body_force=(100.,-40.))
    b,w,area,p=quadrature(m,8);tri=m.triangles
    tq=np.einsum('qi,ti->tq',b,temp[tri]);strain=np.repeat(r.total_strain[:,None,:],len(w),axis=1)
    exact=state_from_3d(strain.reshape(-1,3),tq.ravel(),**mat)
    integrated=np.sum(area[:,None]*w*exact.energy_density.reshape(tq.shape))
    assert r.physical_elastic_energy==pytest.approx(integrated,rel=1e-12)
    # Three-dimensional elastic energy, reduced thermal constant and endpoint work.
    E,nu=mat['young_modulus'],mat['poisson_ratio'];alpha=mat['thermal_expansion_per_k']
    a=alpha*(tq-mat['reference_temperature_k'])
    ct=np.sum(area[:,None]*w*a*a)*E/(1-nu) if plane=='stress' else np.sum(area[:,None]*w*a*a)*1.5*E/(1-2*nu)
    u=r.displacement.ravel();f=r.load_external.ravel();g=r.load_thermal.ravel();reaction=r.reaction.ravel()
    tangent=state_from_3d(r.total_strain,np.full(len(tri),mat['reference_temperature_k']),**mat).stress
    uku=np.sum(area*np.sum(r.total_strain*tangent,axis=1))
    scale=max(1.,integrated,abs(uku),ct)
    assert abs(uku-u@(f+g+reaction))<1e-10*scale
    assert abs(integrated-(.5*uku-u@g+ct))<1e-10*scale
    assert abs(2*integrated-(u@f+u@reaction-u@g+2*ct))<1e-10*scale
    internal_work=np.sum(area*np.sum(r.total_strain*r.stress,axis=1))
    assert abs(internal_work-u@(f+reaction))<1e-10*scale
    for forces in (r.load_external+r.reaction,r.load_thermal):
        forces=forces.reshape(-1,2)
        np.testing.assert_allclose(forces.sum(0),0.,atol=1e-6)
        moment=np.sum(m.nodes[:,0]*forces[:,1]-m.nodes[:,1]*forces[:,0])
        assert abs(moment)<1e-6
    shifted=solve(m,temp+100,plane,bc,reference_temperature_k=393.15,body_force=(100.,-40.))
    np.testing.assert_allclose(shifted.displacement,r.displacement,atol=1e-16)
    assert shifted.physical_elastic_energy==pytest.approx(integrated,rel=1e-12)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_linear_temperature_compatible_convergence(plane):
    from refsol.thermoelasticity import linear_temperature
    history=[];energies=[]
    for n in (8,16,32):
        m=rectangle_mesh(1.,1.,n,n);mat=material(plane)
        field=linear_temperature(m.nodes,**mat)
        bc={(0,0):0.,(0,1):0.,(n,1):0.}
        r=solve(m,field.temperature_k,plane,bc)
        b,w,area,p=quadrature(m,8);t=m.triangles
        exact=linear_temperature(p.reshape(-1,2),**mat)
        uh=np.einsum('qi,tij->tqj',b,r.displacement[t])
        du=exact.displacement.reshape(uh.shape)-uh
        # Consistent-mass best rigid fit, never strain/scale/shear alignment.
        basis=np.zeros((*p.shape[:2],2,3));basis[:,:,0,0]=1;basis[:,:,1,1]=1
        basis[:,:,0,2]=-p[:,:,1];basis[:,:,1,2]=p[:,:,0]
        aw=area[:,None]*w
        mass=np.einsum('tq,tqik,tqil->kl',aw,basis,basis)
        rhs=np.einsum('tq,tqik,tqi->k',aw,basis,du)
        rigid=np.linalg.solve(mass,rhs)
        du-=np.einsum('tqik,k->tqi',basis,rigid)
        grad=np.linalg.solve(m.nodes[t][:,1:]-m.nodes[t][:,:1],r.displacement[t][:,1:]-r.displacement[t][:,:1]).swapaxes(1,2)
        grad+=np.array([[0,-rigid[2]],[rigid[2],0]])
        dg=exact.gradient.reshape((*p.shape[:2],2,2))-grad[:,None]
        # Temperature interpolation is exact for this affine temperature field.
        tq=np.einsum('qi,ti->tq',b,field.temperature_k[t])
        np.testing.assert_allclose(tq,exact.temperature_k.reshape(tq.shape),atol=1e-12)
        de=np.stack([dg[:,:,0,0],dg[:,:,1,1],dg[:,:,0,1]+dg[:,:,1,0]],axis=-1)
        from refsol.thermoelasticity import state_from_3d
        ds=state_from_3d(de.reshape(-1,3),np.full(de.shape[0]*de.shape[1],mat['reference_temperature_k']),**mat).stress.reshape(de.shape)
        history.append([np.sqrt(np.sum(aw*np.sum(du*du,axis=-1))),np.sqrt(np.sum(aw*np.sum(dg*dg,axis=(-1,-2)))),np.sqrt(np.sum(aw*(ds[:,:,0]**2+ds[:,:,1]**2+2*ds[:,:,2]**2))),np.sqrt(np.sum(aw*np.sum(de*de,axis=-1)))])
        expected=.5*mat['young_modulus']*mat['thermal_expansion_per_k']**2*(100+200+400/3) if plane=='strain' else 0.
        energies.append(abs(r.physical_elastic_energy-expected))
    rates=np.log2(np.array(history[:-1])/np.array(history[1:]))
    print('compatible',plane,'errors',history,'rates',rates,'energy errors',energies)
    assert np.all(rates>=np.array([1.8,.9,.9,.9]))
    assert np.all(np.diff(energies)<0)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_alpha_zero_matches_elasticity(plane):
    from galerkin.elasticity import solve_elasticity
    m=rectangle_mesh(1.,1.,3,3);bc={(0,0):0.,(0,1):0.,(3,1):0.}
    mat=material(plane)
    r=solve(m,np.linspace(100,400,m.num_nodes),plane,bc,thermal_expansion_per_k=0.,body_force=(100.,50.))
    e=solve_elasticity(m,young_modulus=mat['young_modulus'],poisson_ratio=mat['poisson_ratio'],plane=plane,dirichlet=bc,body_force=(100.,50.))
    np.testing.assert_allclose(r.displacement,e.displacement,rtol=1e-13)
    np.testing.assert_allclose(r.stress,e.stress,rtol=1e-13)
    assert np.all(r.load_thermal==0)


@pytest.mark.parametrize('name,value',[('reference_temperature_k',-1.),('reference_temperature_k',np.nan),('thermal_expansion_per_k',np.inf),('young_modulus',0.),('poisson_ratio',.5),('plane','plane_stress')])
def test_bad_material(name,value):
    m=rectangle_mesh(1.,1.,2,2)
    with pytest.raises(ValueError):solve(m,np.full(m.num_nodes,300.),'stress',{(0,0):0.,(0,1):0.,(2,1):0.},**{name:value})


def test_negative_controls(monkeypatch):
    import galerkin.thermoelasticity as engine
    m=rectangle_mesh(1.,1.,3,3);bc={(0,0):0.,(0,1):0.,(3,1):0.}
    correct=uniform_free(m.nodes,**material('strain'))
    original=engine._thermal_load
    for multiplier in (-1.,0.,3.,1/1.3):
        monkeypatch.setattr(engine,'_thermal_load',lambda *args,multiplier=multiplier:multiplier*original(*args))
        wrong=solve(m,correct.temperature_k,'strain',bc)
        with pytest.raises(AssertionError):
            np.testing.assert_allclose(wrong.displacement,correct.displacement,rtol=1e-10,atol=1e-14)
    monkeypatch.setattr(engine,'_thermal_load',original)
    good=solve(m,correct.temperature_k,'strain',bc)
    for wrong_z in (np.zeros_like(good.sigma_zz),good.sigma_zz+2e9*1.2e-5*20/(1-2*.27)):
        with pytest.raises(AssertionError):np.testing.assert_allclose(wrong_z,correct.sigma_zz[0],rtol=1e-10)
    # Centroid T squared underintegrates the physical energy for affine T.
    m=rectangle_mesh(1.,1.,1,1);temp=303.15+20*m.nodes[:,0]
    r=solve(m,temp,'strain',{(i,c):0. for i in range(4) for c in (0,1)})
    from refsol.thermoelasticity import state_from_3d
    b,w,area,p=quadrature(m,8);tq=np.einsum('qi,ti->tq',b,temp[m.triangles])
    exact=state_from_3d(np.zeros((tq.size,3)),tq.ravel(),**material('strain'))
    energy=np.sum(area[:,None]*w*exact.energy_density.reshape(tq.shape))
    centroid=state_from_3d(np.zeros((2,3)),temp[m.triangles].mean(1),**material('strain'))
    wrong=area@centroid.energy_density
    assert r.physical_elastic_energy==pytest.approx(energy,rel=1e-12)
    with pytest.raises(AssertionError):assert wrong==pytest.approx(energy,rel=1e-10)


@pytest.mark.parametrize('mutation',['scale','order','connectivity','element_order','unit','temperature','checksum','writeable'])
def test_snapshot_rejects_tampering(mutation):
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,300.))
    if mutation=='scale':m.nodes*=.001
    elif mutation=='order':m.nodes[[0,1]]=m.nodes[[1,0]]
    elif mutation=='connectivity':m.triangles[0]=m.triangles[-1]
    elif mutation=='element_order':m.triangles[:]=m.triangles[::-1]
    elif mutation=='unit':object.__setattr__(s,'temperature_unit','C')
    elif mutation=='temperature':object.__setattr__(s,'temperature_k',np.frombuffer(np.full(m.num_nodes,310.).tobytes(),dtype=float))
    elif mutation=='checksum':object.__setattr__(s,'snapshot_hash','invalid')
    else:object.__setattr__(s,'temperature_k',s.temperature_k.copy())
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},**material('stress'))


def test_disconnected_and_bad_mesh():
    from galerkin.mesh import Mesh
    m=rectangle_mesh(1.,1.,1,1)
    separated=Mesh(np.concatenate([m.nodes,m.nodes+[2.,0.]]),np.concatenate([m.triangles,m.triangles+4]),{})
    with pytest.raises(ValueError):solve(separated,np.full(8,300.),'stress',{(0,0):0.,(0,1):0.,(1,1):0.})
    for mutation in ('nonfinite','index','duplicate'):
        m=rectangle_mesh(1.,1.,1,1)
        if mutation=='nonfinite':m.nodes[0,0]=np.nan
        elif mutation=='index':m.triangles[0,0]=999
        else:m.triangles[0,1]=m.triangles[0,0]
        with pytest.raises(ValueError):freeze_temperature(m,np.full(4,300.))


@pytest.mark.parametrize('plane',['stress','strain'])
def test_traction_reactions_and_superposition(plane):
    m=rectangle_mesh(1.,1.,4,4);mat=material(plane)
    boundary=np.unique(np.concatenate(list(m.boundary.values())))
    bc={(int(i),c):0. for i in boundary for c in (0,1)}
    r=solve(m,np.full(m.num_nodes,313.15),plane,bc)
    expected=np.zeros((m.num_nodes,2));sigma=uniform_constrained(m.nodes,**mat).stress[0]
    normals={'left':(-1,0),'right':(1,0),'bottom':(0,-1),'top':(0,1)}
    for tag,normal in normals.items():
        nodes=m.boundary[tag];traction=np.array([[sigma[0],sigma[2]],[sigma[2],sigma[1]]])@normal
        axis=1 if tag in ('left','right') else 0
        ordered=nodes[np.argsort(m.nodes[nodes,axis])]
        for i,j in zip(ordered[:-1],ordered[1:]):
            force=traction*np.linalg.norm(m.nodes[i]-m.nodes[j])/2
            expected[i]+=force;expected[j]+=force
    np.testing.assert_allclose(r.reaction.reshape(-1,2),expected,atol=2e-8)
    t0=np.full(m.num_nodes,293.15);t1=t0+10*m.nodes[:,0];t2=t0+5*m.nodes[:,1]
    results=[solve(m,t,plane,bc,body_force=(100.,-50.)) for t in (t0,t1,t2,t1+t2-t0)]
    np.testing.assert_allclose(results[3].displacement,results[1].displacement+results[2].displacement-results[0].displacement,atol=1e-16)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_preregistered_primary_material_convergence(plane,monkeypatch):
    original=material
    monkeypatch.setitem(globals(),'material',lambda mode:original(mode)|dict(young_modulus=70e9,poisson_ratio=.3))
    test_sine_convergence(plane)
    test_linear_temperature_compatible_convergence(plane)
