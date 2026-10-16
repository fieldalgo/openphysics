# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Producer contracts. Written for later authorized execution, not a pass record."""
from dataclasses import fields
import numpy as np
import pytest
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.transient_heat import solve_transient_heat, TransientHeatStepError
from refsol.transient_heat import p1_matrices, moving_affine


def solve(mesh=None, **overrides):
    mesh = rectangle_mesh(1.,1.,2,2) if mesh is None else mesh
    defaults = dict(conductivity=2.5,volumetric_heat_capacity=4.,
                    time_s=[0.,.1,.3],initial_temperature_k=np.full(mesh.num_nodes,300.),
                    dirichlet={},heat_source=0.)
    return solve_transient_heat(mesh, **(defaults|overrides))


def boundary(mesh):
    return np.unique(np.concatenate(list(mesh.boundary.values())))


def audit_original_system(mesh, result, k=2.5, c=4.):
    m,a = p1_matrices(mesh.nodes,mesh.triangles,
                     conductivity=k,volumetric_heat_capacity=c)
    t = result.temperature_k
    rate = np.diff(t,axis=0)/np.diff(result.time_s)[:,None]
    storage = rate@m.T
    residual = storage+t[1:]@a.T-result.source_load_w_per_m[1:]
    # Scales use noncancelling absolute rates and the 1K characteristic change.
    scale = max(1.,np.max(np.sum(abs(storage)+abs(result.source_load_w_per_m[1:])
                                +abs(result.reaction_w_per_m),axis=1)))
    np.testing.assert_allclose(result.storage_rate_w_per_m,storage,rtol=0,atol=1e-10*scale)
    np.testing.assert_allclose(result.residual_w_per_m,residual,rtol=0,atol=1e-10*scale)
    want = np.zeros_like(residual);want[:,result.dirichlet_node_ids] = residual[:,result.dirichlet_node_ids]
    np.testing.assert_allclose(result.reaction_w_per_m,want,rtol=0,atol=1e-10*scale)
    np.testing.assert_allclose(result.heat_content_j_per_m,np.sum(t@m.T,axis=1),rtol=0,atol=4e-10)
    v = .5*np.einsum('ti,ij,tj->t',t,m,t)
    np.testing.assert_allclose(result.quadratic_functional_jk_per_m,v,rtol=0,atol=4e-10)
    outward = -result.reaction_w_per_m.sum(1)
    np.testing.assert_allclose(storage.sum(1),
        result.source_load_w_per_m[1:].sum(1)-outward,rtol=0,atol=1e-10*scale)
    np.testing.assert_allclose(np.diff(result.heat_content_j_per_m)/np.diff(result.time_s),
        result.source_load_w_per_m[1:].sum(1)+result.reaction_w_per_m.sum(1),
        rtol=0,atol=1e-10*scale)
    delta = np.diff(t,axis=0);dt = np.diff(result.time_s)
    lhs = np.diff(v)/dt+.5*np.einsum('ti,ij,tj->t',delta,m,delta)/dt
    lhs += np.einsum('ti,ij,tj->t',t[1:],a,t[1:])
    rhs = np.sum(t[1:]*(result.source_load_w_per_m[1:]+result.reaction_w_per_m),axis=1)
    np.testing.assert_allclose(lhs,rhs,rtol=0,atol=1e-10*scale)


@pytest.mark.parametrize('source',[8.,-8.,0.])
def test_insulated_uniform_signed_source_and_shapes(source):
    mesh=rectangle_mesh(1.,1.,2,2)
    r=solve(mesh,heat_source=source)
    expected=300+source/4*r.time_s
    np.testing.assert_allclose(r.temperature_k,np.broadcast_to(expected[:,None],(3,9)),atol=1e-10,rtol=0)
    np.testing.assert_allclose(r.heat_flux_w_m2,0,atol=2.5e-10,rtol=0)
    assert r.reaction_w_per_m.shape==r.residual_w_per_m.shape==r.storage_rate_w_per_m.shape==(2,9)
    assert r.source_load_w_per_m.shape==(3,9) and r.heat_flux_w_m2.shape==(3,8,2)
    assert r.dirichlet_temperatures_k.shape==(3,0)
    assert not r.reaction_w_per_m.any()
    audit_original_system(mesh,r)


def test_disconnected_unanchored_components():
    a=rectangle_mesh(1.,1.,1,1)
    p=np.concatenate([a.nodes,a.nodes+[3.,0.]])
    t=np.concatenate([a.triangles,a.triangles+a.num_nodes])
    mesh=Mesh(p,t,{})
    initial=np.r_[np.full(4,300.),np.full(4,-10.)]
    r=solve(mesh,initial_temperature_k=initial,heat_source=4.)
    np.testing.assert_allclose(r.temperature_k,initial[None,:]+r.time_s[:,None],atol=1e-10,rtol=0)
    assert not r.reaction_w_per_m.any()
    m,_=p1_matrices(p,t,conductivity=2.5,volumetric_heat_capacity=4.)
    for nodes in (np.arange(4),np.arange(4,8)):
        np.testing.assert_allclose(r.storage_rate_w_per_m[:,nodes].sum(1),4.,atol=4e-10,rtol=0)
        assert np.linalg.eigvalsh(m[np.ix_(nodes,nodes)]).min()>0


def test_moving_affine_both_mass_boundary_terms():
    mesh=rectangle_mesh(1.,1.,3,3);times=np.array([.2,.27,.5,.9])
    initial=moving_affine(mesh.nodes,times[0],initial_time_s=times[0]).temperature_k
    bc={int(i):(lambda time,x=mesh.nodes[i,0]:290+5*x+3*(time-times[0]))
        for i in boundary(mesh)}
    r=solve(mesh,time_s=times,initial_temperature_k=initial,dirichlet=bc,heat_source=12.)
    expected=np.stack([moving_affine(mesh.nodes,t,initial_time_s=times[0]).temperature_k for t in times])
    np.testing.assert_allclose(r.temperature_k,expected,atol=1e-10*5,rtol=0)
    np.testing.assert_allclose(r.heat_flux_w_m2,np.broadcast_to([-12.5,0.],r.heat_flux_w_m2.shape),atol=1.25e-9,rtol=0)
    audit_original_system(mesh,r)


def test_source_sampled_t0_then_right_endpoint_once_and_fixed_bc_once():
    mesh=rectangle_mesh(1.,1.,2,2);times=np.array([0.,.1,.3,.8])
    calls=[];bc_calls=[]
    def source(p,t):
        calls.append(t)
        # Manufactured discrete BE source for T=300+t+t^2, not its PDE derivative.
        i=int(np.flatnonzero(times==t)[0])
        value=4. if i==0 else 4*(1+times[i]+times[i-1])
        return np.full(len(p),value)
    # Isolated run checks source once per time with no boundary influence.
    r=solve(mesh,time_s=times,heat_source=source)
    assert calls==times.tolist()
    expected=300+times+times**2
    np.testing.assert_allclose(r.temperature_k,np.broadcast_to(expected[:,None],r.temperature_k.shape),atol=1e-10,rtol=0)
    def bc(t):bc_calls.append(t);return 300.
    solve(mesh,time_s=times,dirichlet={0:bc})
    assert bc_calls==times.tolist()


def test_t0_source_validation_and_late_chained_failures(monkeypatch):
    mesh=rectangle_mesh(1.,1.,2,2)
    def invalid_initial_source(p,t):
        return np.full(len(p),np.nan) if t==0 else np.zeros(len(p))
    with pytest.raises(TransientHeatStepError) as caught:
        solve(mesh,heat_source=invalid_initial_source)
    assert caught.value.time_index==0 and caught.value.time_s==0.
    assert isinstance(caught.value.__cause__,ValueError)
    marker=RuntimeError('source marker')
    def late(p,t):
        if t==.3:raise marker
        return np.zeros(len(p))
    with pytest.raises(TransientHeatStepError) as caught:solve(mesh,heat_source=late)
    assert caught.value.time_index==2 and caught.value.time_s==.3 and caught.value.__cause__ is marker
    import galerkin.transient_heat as module
    failure=RuntimeError('factorization marker')
    monkeypatch.setattr(module,'splu',lambda *a,**k:(_ for _ in ()).throw(failure))
    with pytest.raises(TransientHeatStepError) as caught:solve(mesh)
    assert caught.value.time_index==1 and caught.value.time_s==.1 and caught.value.__cause__ is failure


def test_late_bc_failure_context():
    def bc(t):
        if t==.3:return float('nan')
        return 300.
    with pytest.raises(TransientHeatStepError) as caught:solve(dirichlet={0:bc})
    assert caught.value.time_index==2 and isinstance(caught.value.__cause__,ValueError)


def test_initial_32eps_agreement_preserved_without_projection():
    mesh=rectangle_mesh(1.,1.,2,2);initial=np.full(9,300.)
    allowed=initial[0]+16*np.finfo(float).eps*300
    r=solve(mesh,initial_temperature_k=initial,dirichlet={0:allowed})
    np.testing.assert_array_equal(r.temperature_k[0],initial)
    assert r.dirichlet_temperatures_k[0,0]==allowed
    rejected=initial[0]+64*np.finfo(float).eps*300
    with pytest.raises(TransientHeatStepError,match='index 0') as caught:
        solve(mesh,initial_temperature_k=initial,dirichlet={0:rejected})
    assert '32 eps' in str(caught.value.__cause__)


@pytest.mark.parametrize('value',[-300.,-1.,0.])
def test_finite_negative_kelvin_not_clamped(value):
    r=solve(initial_temperature_k=np.full(9,value),heat_source=-4.)
    np.testing.assert_allclose(r.temperature_k,value-r.time_s[:,None]+np.zeros((3,9)),atol=1e-10,rtol=0)
    assert r.temperature_k[-1].min()<0


@pytest.mark.parametrize('times',[[0.],[0.,0.],[1.,0.],[-1.,0.],[0.,np.inf],
    [0.,np.nan],[[0.,1.]],np.array([False,True]),[False,1.]])
def test_invalid_times(times):
    with pytest.raises(ValueError):solve(time_s=times)


@pytest.mark.parametrize('keyword',['conductivity','volumetric_heat_capacity'])
@pytest.mark.parametrize('bad',[0.,-1.,True,1j,np.nan,np.inf,[1.]])
def test_invalid_positive_material(keyword,bad):
    with pytest.raises(ValueError):solve(**{keyword:bad})


@pytest.mark.parametrize('bad',[True,np.full(9,np.nan),np.ones((9,1)),np.full(9,1j),
                               [True]+[300.]*8])
def test_invalid_initial(bad):
    with pytest.raises(ValueError):solve(initial_temperature_k=bad)


@pytest.mark.parametrize('data',[None,{True:300.},{1.0:300.},{4:300.},{99:300.},
                                  {0:True},{0:[300.]},{0:1j}])
def test_invalid_dirichlet(data):
    with pytest.raises(ValueError):solve(dirichlet=data)


@pytest.mark.parametrize('callback',[lambda p,t:0.,lambda p,t:np.ones((len(p),1)),
    lambda p,t:np.full(len(p),True),lambda p,t:np.full(len(p),1j),
    lambda p,t:[True]+[0.]*(len(p)-1)])
def test_invalid_source_callback(callback):
    with pytest.raises(TransientHeatStepError) as caught:solve(heat_source=callback)
    assert caught.value.time_index==0 and isinstance(caught.value.__cause__,ValueError)


def test_result_owns_readonly_copies_and_explicit_si_conversion():
    mesh=rectangle_mesh(1.,1.,2,2);times=np.array([0.,.1,.3]);initial=np.full(9,300.)
    r=solve(mesh,time_s=times,initial_temperature_k=initial,heat_source=4.)
    saved=r.temperature_k.copy();p=r.nodes_m.copy();tri=r.triangles.copy()
    mesh.nodes[:]=99;mesh.triangles[:]=0;times[:]=99;initial[:]=-99
    np.testing.assert_array_equal(r.temperature_k,saved)
    np.testing.assert_array_equal(r.nodes_m,p);np.testing.assert_array_equal(r.triangles,tri)
    for f in fields(r):
        value=getattr(r,f.name)
        if isinstance(value,np.ndarray):assert not value.flags.writeable
    with pytest.raises(ValueError):r.temperature_k[0,0]=0
    # Explicit conversion returns the same physical metre mesh; no unit inference.
    converted=Mesh((p*1000)*1e-3,tri.copy(),{})
    rr=solve(converted,heat_source=4.)
    np.testing.assert_allclose(rr.temperature_k,r.temperature_k,atol=1e-9,rtol=0)
    np.testing.assert_allclose(rr.heat_flux_w_m2,r.heat_flux_w_m2,atol=2.5e-9,rtol=0)


def test_common_constant_shift_invariants():
    mesh=rectangle_mesh(1.,1.,2,2)
    a=solve(mesh,heat_source=4.)
    b=solve(mesh,initial_temperature_k=np.full(9,400.),heat_source=4.)
    for name in ('heat_flux_w_m2','storage_rate_w_per_m','reaction_w_per_m'):
        np.testing.assert_allclose(getattr(a,name),getattr(b,name),atol=4e-10,rtol=0)
    np.testing.assert_allclose(b.heat_content_j_per_m-a.heat_content_j_per_m,400.,atol=4e-10,rtol=0)
    assert not np.array_equal(a.quadratic_functional_jk_per_m,b.quadratic_functional_jk_per_m)


def test_invalid_mesh_not_repaired_by_capture():
    mesh=rectangle_mesh(1.,1.,2,2);mesh.triangles=mesh.triangles[:,::-1]
    with pytest.raises(ValueError,match='counter-clockwise'):solve(mesh)
    mesh=rectangle_mesh(1.,1.,2,2);mesh.triangles=mesh.triangles.astype(float)
    with pytest.raises(ValueError,match='integer'):solve(mesh)


def test_negative_fixed_kelvin_and_no_top_level_export():
    r=solve(initial_temperature_k=np.full(9,-10.),dirichlet={0:-10.})
    np.testing.assert_allclose(r.temperature_k,-10.,atol=1e-10,rtol=0)
    import galerkin
    assert not hasattr(galerkin,'solve_transient_heat')
