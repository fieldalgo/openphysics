# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Producer total-traction API checks, independent analytic reference."""
from dataclasses import fields
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import ThermoelasticResult, freeze_temperature, solve_thermoelasticity
from refsol.thermoelastic_traction import uniform_combined, traction_from_stress


def material(plane):
    return dict(young_modulus=70e9,poisson_ratio=.3,plane=plane,
                thermal_expansion_per_k=12e-6,reference_temperature_k=293.15)


def solve_patch(plane, overlap=False, **kwargs):
    m=rectangle_mesh(1.,1.,3,3);mat=material(plane)|kwargs
    exact=uniform_combined(m.nodes,**mat)
    bc={(int(i),j):exact.displacement[i,j] for i in m.boundary['left'] for j in (0,1)}
    def load(p,n):return traction_from_stress(uniform_combined(p,**mat).stress,n)
    tags=['right','top','bottom']+(['left'] if overlap else [])
    r=solve_thermoelasticity(m,freeze_temperature(m,exact.temperature_k),dirichlet=bc,
                           traction={tag:load for tag in tags},**mat)
    return m,r,exact


@pytest.mark.parametrize('plane',['stress','strain'])
def test_uniform_total_traction_and_overlap(plane):
    m,r,exact=solve_patch(plane);_,over,_=solve_patch(plane,True)
    np.testing.assert_allclose(r.displacement,exact.displacement,atol=1e-14,rtol=0)
    np.testing.assert_allclose(r.stress,exact.stress[0][[0,1,0],[0,1,1]][None,:].repeat(len(m.triangles),0),atol=70e9*max(1e-4,12e-6*20)*1e-10,rtol=0)
    np.testing.assert_allclose(r.sigma_zz,exact.stress[0,2,2],atol=70e9*max(1e-4,12e-6*20)*1e-10,rtol=0)
    assert r.physical_elastic_energy==pytest.approx(exact.energy_density[0],rel=1e-10)
    np.testing.assert_array_equal(r.load_external,r.load_body+r.load_traction)
    np.testing.assert_array_equal(r.load_total,r.load_external+r.load_thermal)
    np.testing.assert_allclose(over.displacement,r.displacement,atol=1e-14,rtol=0)
    np.testing.assert_allclose(over.reaction-r.reaction,-(over.load_traction-r.load_traction),atol=70e9*max(1e-4,12e-6*20)*1e-10,rtol=0)
    np.testing.assert_allclose((r.load_external+r.reaction).sum(0),0,atol=70e9*max(1e-4,12e-6*20)*1e-10)
    assert abs(np.sum(r.displacement*r.reaction))>1


def test_legacy_eighteen_positional_and_none_empty():
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,313.15))
    kw=dict(dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},**material('strain'))
    a=solve_thermoelasticity(m,s,**kw);b=solve_thermoelasticity(m,s,traction={},**kw)
    for f in fields(a):
        if isinstance(getattr(a,f.name),np.ndarray):np.testing.assert_array_equal(getattr(a,f.name),getattr(b,f.name))
    old=ThermoelasticResult(*[getattr(a,f.name) for f in fields(a)[:18]])
    assert old.load_body is None and old.load_traction is None
    np.testing.assert_array_equal(a.load_body,a.load_external)
    assert not a.load_traction.any()


@pytest.mark.parametrize('bad',[True,1.,(1.,2.),{'missing':(1.,0.)},{'right':(True,False)},
    {'right':(np.nan,0.)},{'right':(1j,0.)},{'right':lambda p,n:np.zeros(2)}])
def test_invalid_traction(bad):
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,313.15))
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},traction=bad,**material('stress'))


def test_complete_selection_before_callback_and_current_tags():
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,313.15));calls=[]
    def load(p,n):calls.append(1);return np.zeros_like(p)
    kw=dict(dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},**material('stress'))
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,traction={'right':load,'missing':load},**kw)
    assert not calls
    m.boundary_edges['duplicate']=m.boundary_edges['right'][::-1,::-1]
    with pytest.raises(ValueError,match='duplicate'):solve_thermoelasticity(m,s,traction={'right':load,'duplicate':load},**kw)
    assert not calls
    m.boundary_edges['bad']=np.array([[0,4]])
    with pytest.raises(ValueError,match='exterior'):solve_thermoelasticity(m,s,traction={'bad':load},**kw)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('rotation',[0.,.71])
def test_ring_outward_normals_ordering_and_rotation(plane,rotation):
    from galerkin.mesh import Mesh
    base=rectangle_mesh(1.,1.,4,4)
    centers=base.nodes[base.triangles].mean(1)
    tri=base.triangles[~((centers[:,0]>.25)&(centers[:,0]<.75)&(centers[:,1]>.25)&(centers[:,1]<.75))]
    used=np.unique(tri);mapping=np.full(base.num_nodes,-1);mapping[used]=np.arange(len(used))
    nodes=base.nodes[used];tri=mapping[tri]
    owners={}
    for a,b,c in tri:
        for i,j in ((a,b),(b,c),(c,a)):owners[tuple(sorted((i,j)))]=owners.get(tuple(sorted((i,j))),0)+1
    edges=np.array([e for e,count in owners.items() if count==1],dtype=int)
    left=np.flatnonzero(nodes[:,0]==0.)
    rotation_matrix=np.array([[np.cos(rotation),-np.sin(rotation)],[np.sin(rotation),np.cos(rotation)]])
    p=nodes@rotation_matrix.T+[2.,-3.]
    m=Mesh(p,tri.copy(),boundary={'left':left},boundary_edges={'all':edges})
    exact=uniform_combined(nodes,**material(plane));target=exact.displacement@rotation_matrix.T
    s=rotation_matrix@exact.stress[0,:2,:2]@rotation_matrix.T
    normals=[]
    def traction(points,n):
        local=(points-[2.,-3.])@rotation_matrix
        ln=n@rotation_matrix;inner=(np.max(np.abs(local-.5),axis=1)<.251)
        assert np.all(np.sum(ln[inner]*(.5-local[inner]),axis=1)>0)
        normals.append(n.copy());return n@s.T
    def run(mesh,displacement):
        return solve_thermoelasticity(mesh,freeze_temperature(mesh,np.full(mesh.num_nodes,313.15)),
            dirichlet={(int(i),j):displacement[i,j] for i in mesh.boundary['left'] for j in (0,1)},
            traction={'all':traction},**material(plane))
    r=run(m,target)
    np.testing.assert_allclose(r.displacement,target,atol=1e-14,rtol=0)
    assert normals and abs(r.physical_elastic_energy-.75*exact.energy_density[0])<70e9*(12e-6*20)**2*1e-10
    # New exact snapshot for reordered nodes/cells/local endpoints; no stale transplant.
    perm=np.arange(m.num_nodes)[::-1];inv=np.argsort(perm)
    altered=Mesh(m.nodes[perm],inv[m.triangles[::-1,::-1]],boundary={'left':inv[left]},
                 boundary_edges={'all':inv[edges[::-1,::-1]]})
    rr=run(altered,target[perm])
    np.testing.assert_allclose(rr.displacement[inv],r.displacement,atol=1e-14,rtol=0)
    np.testing.assert_allclose(rr.load_traction[inv],r.load_traction,atol=.00168,rtol=0)


def test_linear_segment_consistent_and_dirichlet_overlap():
    m=rectangle_mesh(1.,1.,1,1);s=freeze_temperature(m,np.full(m.num_nodes,293.15))
    t0=np.array([2e6,-3e6]);t1=np.array([5e6,7e6])
    def load(p,n):return (1-p[:,1,None])*t0+p[:,1,None]*t1
    r=solve_thermoelasticity(m,s,dirichlet={(i,j):0. for i in range(m.num_nodes) for j in (0,1)},
                           traction={'right':load},**material('stress'))
    bottom=int(np.flatnonzero((m.nodes[:,0]==1)&(m.nodes[:,1]==0))[0]);top=int(np.flatnonzero((m.nodes[:,0]==1)&(m.nodes[:,1]==1))[0])
    np.testing.assert_allclose(r.load_traction[bottom],(2*t0+t1)/6,atol=.00168,rtol=0)
    np.testing.assert_allclose(r.load_traction[top],(t0+2*t1)/6,atol=.00168,rtol=0)
    np.testing.assert_array_equal(r.reaction,-r.load_traction)
    assert np.linalg.norm(r.load_traction[bottom]-t0/2)>1e5


@pytest.mark.parametrize('theta,alpha',[(20.,12e-6),(-20.,12e-6),(20.,-12e-6),(20.,0.)])
@pytest.mark.parametrize('plane',['stress','strain'])
def test_uniform_signed_alpha_cooling_and_reference_shift(plane,theta,alpha):
    mat=material(plane)|{'thermal_expansion_per_k':alpha}
    m=rectangle_mesh(1.,1.,2,2)
    ex=uniform_combined(m.nodes,theta_k=theta,**mat)
    def load(p,n):return traction_from_stress(uniform_combined(p,theta_k=theta,**mat).stress,n)
    kw={'dirichlet':{(int(i),j):ex.displacement[i,j] for i in m.boundary['left'] for j in (0,1)},
        'traction':{tag:load for tag in ('right','top','bottom')}}
    r=solve_thermoelasticity(m,freeze_temperature(m,ex.temperature_k),**mat,**kw)
    shifted=solve_thermoelasticity(m,freeze_temperature(m,ex.temperature_k+100),**(mat|{'reference_temperature_k':393.15}),**kw)
    np.testing.assert_allclose(r.displacement,ex.displacement,atol=1e-14,rtol=0)
    np.testing.assert_allclose(shifted.displacement,r.displacement,atol=1e-14,rtol=0)
    assert shifted.physical_elastic_energy==pytest.approx(r.physical_elastic_energy,rel=1e-10)


def test_traction_does_not_authorize_stale_snapshot_or_free_component():
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,313.15))
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,dirichlet={},traction={'right':(1.,0.)},**material('stress'))
    m.nodes[1,0]+=.01
    with pytest.raises(ValueError,match='stale|mismatched'):solve_thermoelasticity(m,s,dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},traction={'right':(1.,0.)},**material('stress'))


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('variant',['add_thermal_boundary','subtract_thermal_boundary','omit_thermal_rhs','wrong_thermal_sign'])
def test_actual_helper_mutation_is_detected(monkeypatch,plane,variant):
    import galerkin.thermoelasticity as engine
    original_line=engine.traction_load;original_thermal=engine._thermal_load
    if 'boundary' in variant:
        sign=1 if variant.startswith('add') else -1
        q=70e9*12e-6*20/(1-.3 if plane=='stress' else 1-2*.3)
        def wrong_line(mesh,p,t,traction,**kw):
            extra=original_line(mesh,p,t,{tag:lambda points,n:sign*q*n for tag in traction},**kw)
            return original_line(mesh,p,t,traction,**kw)+extra
        monkeypatch.setattr(engine,'traction_load',wrong_line)
    else:
        factor=0 if variant=='omit_thermal_rhs' else -1
        monkeypatch.setattr(engine,'_thermal_load',lambda *args:factor*original_thermal(*args))
    # Actual solver mutation must violate the exact physical displacement assertion.
    m,r,exact=solve_patch(plane)
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(r.displacement,exact.displacement,atol=1e-14,rtol=0)


@pytest.mark.parametrize('edges',[np.array([[0.,1.]]),np.array([[0,0]]),np.array([[0,99]]),
    np.array([[0,1],[1,0]]),np.array([],dtype=int),np.array([[0,4]])])
def test_malformed_selected_edges(edges):
    m=rectangle_mesh(1.,1.,2,2);m.boundary_edges['bad']=edges
    with pytest.raises(ValueError):solve_thermoelasticity(m,freeze_temperature(m,np.full(m.num_nodes,313.15)),
        dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},traction={'bad':(1.,0.)},**material('stress'))
