"""Prescribed-temperature mechanical-stage checks; no thermal solver is invoked."""
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from refsol.thermoelasticity import uniform_free, uniform_constrained, sine_manufactured


def material(plane):
    return dict(young_modulus=2e9, poisson_ratio=.27, plane=plane,
                reference_temperature_k=293.15, thermal_expansion_per_k=1.2e-5)


def solve(mesh, temp, plane, bc, **kw):
    return solve_thermoelasticity(mesh, freeze_temperature(mesh,temp),
                                 dirichlet=bc, **(material(plane)|kw))


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
    return np.array([np.sqrt(np.sum(area[:,None]*w*v)) for v in vals])


@pytest.mark.parametrize('plane',['stress','strain'])
def test_sine_convergence(plane):
    history=[]
    for n in (8,16,32):
        m=rectangle_mesh(1.,1.,n,n);mat=material(plane)
        exact=sine_manufactured(m.nodes,**mat)
        boundary=np.unique(np.concatenate(list(m.boundary.values())))
        bc={(int(i),c):float(exact.displacement[i,c]) for i in boundary for c in (0,1)}
        r=solve(m,exact.temperature_k,plane,bc,body_force=lambda p:sine_manufactured(p,**mat).body_force)
        e=errors(m,r,plane,8);e10=errors(m,r,plane,10)
        np.testing.assert_allclose(e,e10,rtol=.01)
        history.append(e)
        np.testing.assert_allclose((r.load_external+r.reaction).reshape(-1,2).sum(0),0.,atol=1e-6)
    rates=np.log2(np.array(history[:-1])/np.array(history[1:]))
    print(plane,'errors',np.array(history),'rates',rates)
    assert np.all(rates>=np.array([1.8,.9,.9]))
