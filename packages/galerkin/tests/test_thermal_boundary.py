# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Boundary contract and independent physical references (SI, unit depth)."""
import numpy as np
import pytest
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.thermal import SteadyHeatResult, solve_steady_heat
from refsol.thermal_boundary import dirichlet_robin_slab, robin_only_slab


def bc_left(mesh, value=320.):
    return {int(i): value for i in mesh.boundary['left']}


def balance(r, fixed=()):
    scale=max(sum(np.sum(abs(x)) for x in (r.load,r.reaction,r.prescribed_outward_load,r.convective_outward)),1e-300)
    assert abs(np.sum(r.load+r.reaction-r.prescribed_outward_load-r.convective_outward))/scale < 1e-10
    free=np.setdiff1d(np.arange(len(r.temperature)),list(fixed))
    assert np.max(abs(r.residual[free]),initial=0)/scale < 1e-10


@pytest.mark.parametrize('mode',['flux','mixed','robin'])
@pytest.mark.parametrize('left_temperature',[320.,280.])
def test_linear_patch_sign_cooling_balance(mode,left_temperature):
    m=rectangle_mesh(1.,.8,6,5);k=2.5;g=.7;h=10.;ambient=300.
    if mode=='robin':
        ref=robin_only_slab(length=1.,conductivity=k,left_h=8.,right_h=h,
                            left_ambient=left_temperature,right_ambient=ambient,right_outward=g)
        bc={};conv={'left':(8.,left_temperature),'right':(h,ambient)}
    else:
        ref=dirichlet_robin_slab(length=1.,conductivity=k,left_temperature=left_temperature,
                                 outward_flux=g,h=h if mode=='mixed' else 0.,ambient=ambient)
        bc=bc_left(m,left_temperature);conv={'right':(h,ambient)} if mode=='mixed' else None
    r=solve_steady_heat(m,conductivity=k,dirichlet=bc,outward_flux={'right':g},convection=conv)
    np.testing.assert_allclose(r.temperature,ref.temperature(m.nodes),rtol=0,atol=1e-10)
    centers=m.nodes[m.triangles].mean(axis=1)
    np.testing.assert_allclose(r.heat_flux,ref.heat_flux(centers),rtol=0,atol=1e-10)
    np.testing.assert_allclose(sum(r.prescribed_outward_load),g*.8,rtol=1e-12)
    if mode!='flux':
        expected=(ref.outward_fluxes[1]-g)*.8
        np.testing.assert_allclose(sum(r.convective_outward[m.boundary['right']]),expected,atol=1e-10)
        if left_temperature>ambient:assert expected>0
        else:assert expected<0
    balance(r,bc)


def test_original_result_constructor_and_default_compatibility():
    a=np.zeros(3);r=SteadyHeatResult(a,a,a,a,a)
    assert r.prescribed_outward_load is None and r.system_rhs is None
    m=rectangle_mesh(1.,1.,2,2);bc=bc_left(m)
    old=solve_steady_heat(m,conductivity=2.,dirichlet=bc)
    new=solve_steady_heat(m,conductivity=2.,dirichlet=bc,outward_flux={},convection={})
    for name in ('temperature','heat_flux','load','reaction','residual'):
        np.testing.assert_array_equal(getattr(old,name),getattr(new,name))
    for name in ('prescribed_outward_load','ambient_load','convective_outward'):
        np.testing.assert_array_equal(getattr(new,name),0.)
    np.testing.assert_array_equal(new.system_rhs,new.load)


def test_consistent_affine_h_ambient_and_flux_moments():
    m=rectangle_mesh(1.,1.,1,1)
    r=solve_steady_heat(m,conductivity=2.,dirichlet={0:300.},
        outward_flux={'right':lambda p,n:3-5*p[:,1]},
        convection={'right':(lambda p,n:2+3*p[:,1],lambda p,n:300+20*p[:,1])})
    edge=m.boundary_edges['right'][0];H=np.array([[11,7],[7,17]])/12
    G=np.array([4,-1])/6
    B=np.array([3*2*300+2*320+5*300+5*320,2*300+2*320+5*300+3*5*320])/12
    np.testing.assert_allclose(r.prescribed_outward_load[edge],G,atol=1e-13)
    np.testing.assert_allclose(r.ambient_load[edge],B,atol=1e-12)
    np.testing.assert_allclose(r.convective_outward[edge],H@r.temperature[edge]-B,atol=1e-12)
    assert not np.allclose(B,np.array([3.5*310/2]*2))
    assert not np.allclose(H@r.temperature[edge]-B,H.sum(axis=1)*r.temperature[edge]-B)
    balance(r,{0})


@pytest.mark.parametrize('s',[1e-3,1.,1e3])
@pytest.mark.parametrize('c',[.1,1.,10.])
def test_boundary_si_similarity(s,c):
    def solve(scale,coef):
        m=rectangle_mesh(scale,.8*scale,4,4)
        return solve_steady_heat(m,conductivity=2.5*coef,dirichlet=bc_left(m),heat_source=5*coef/scale**2,
             outward_flux={'right':.7*coef/scale},convection={'right':(10*coef/scale,300.)})
    a=solve(1.,1.);b=solve(s,c)
    np.testing.assert_allclose(b.temperature,a.temperature,rtol=1e-9,atol=1e-9)
    np.testing.assert_allclose(b.heat_flux,a.heat_flux*c/s,rtol=1e-9,atol=1e-9*c/s)
    for name in ('load','reaction','prescribed_outward_load','ambient_load','convective_outward','system_rhs'):
        np.testing.assert_allclose(getattr(b,name),getattr(a,name)*c,rtol=1e-9,atol=1e-9*c)


def test_joint_offset_and_h_zero_ambient_invariance():
    m=rectangle_mesh(1.,1.,4,4)
    def solve(offset,h=10.):
        return solve_steady_heat(m,conductivity=2.,dirichlet=bc_left(m,320+offset),heat_source=5.,
                                convection={'right':(h,300+offset)})
    a=solve(0);b=solve(1e8)
    np.testing.assert_allclose(b.temperature-1e8,a.temperature,rtol=0,atol=2e-8)
    np.testing.assert_array_equal(a.heat_flux,b.heat_flux)
    np.testing.assert_array_equal(a.convective_outward,b.convective_outward)
    z=solve_steady_heat(m,conductivity=2.,dirichlet=bc_left(m),convection={'right':(0.,-999.)})
    plain=solve_steady_heat(m,conductivity=2.,dirichlet=bc_left(m))
    np.testing.assert_array_equal(z.temperature,plain.temperature)
    negative=solve_steady_heat(m,conductivity=2.,dirichlet={},convection={'right':(1.,-100.)})
    np.testing.assert_array_equal(negative.temperature,-100.)


@pytest.mark.parametrize('bad',[True,1j,np.nan,np.inf,[1.],lambda p,n:1.,lambda p,n:np.zeros((len(p),1)),lambda p,n:np.ones(len(p),dtype=bool),lambda p,n:np.full(len(p),np.nan)])
@pytest.mark.parametrize('kind',['flux','h','ambient'])
def test_invalid_values_and_callback_shapes(bad,kind):
    m=rectangle_mesh(1.,1.,2,2);kwargs={'outward_flux':{'right':bad}} if kind=='flux' else {'convection':{'right':(bad,300.) if kind=='h' else (0.,bad)}}
    with pytest.raises(ValueError):solve_steady_heat(m,conductivity=1.,dirichlet=bc_left(m),**kwargs)


@pytest.mark.parametrize('h',[-1.,lambda p,n:-np.ones(len(p))])
def test_negative_h(h):
    with pytest.raises(ValueError):solve_steady_heat(rectangle_mesh(1.,1.,2,2),conductivity=1.,dirichlet={},convection={'right':(h,300.)})


@pytest.mark.parametrize('case',['empty','unknown','interior','orphan','degenerate','duplicate','cross_tag','fractional','shape','index','full_dir'])
@pytest.mark.parametrize('kind',['outward_flux','convection'])
def test_invalid_selected_edges(case,kind):
    m=rectangle_mesh(1.,1.,2,2);bc={0:300.};tag='right';value=0. if kind=='outward_flux' else (0.,300.)
    if case=='unknown':tag='absent'
    elif case=='empty':m.boundary_edges[tag]=np.empty((0,2),int)
    elif case=='interior':m.boundary_edges[tag]=np.array([[0,4]])
    elif case=='orphan':m.boundary_edges[tag]=np.array([[0,8]])
    elif case=='degenerate':m.boundary_edges[tag]=np.array([[2,2]])
    elif case=='duplicate':m.boundary_edges[tag]=np.vstack([m.boundary_edges[tag],m.boundary_edges[tag][0,::-1]])
    elif case=='fractional':m.boundary_edges[tag]=np.array([[2.,5.]])
    elif case=='shape':m.boundary_edges[tag]=np.array([2,5])
    elif case=='index':m.boundary_edges[tag]=np.array([[2,999]])
    elif case=='full_dir':bc.update({int(i):300. for i in m.boundary['right']})
    data={tag:value}
    if case=='cross_tag':m.boundary_edges['alias']=m.boundary_edges['right'][::-1,::-1];data['alias']=value
    with pytest.raises(ValueError):solve_steady_heat(m,conductivity=1.,dirichlet=bc,**{kind:data})


def test_normals_tag_reversal_mixed_corner_and_hole():
    # A central removed square has outward normals pointing into its hole.
    m=rectangle_mesh(3.,3.,3,3)
    centers=m.nodes[m.triangles].mean(axis=1)
    t=m.triangles[~((centers[:,0]>1)&(centers[:,0]<2)&(centers[:,1]>1)&(centers[:,1]<2))]
    hole=np.array([[5,6],[6,10],[10,9],[9,5]])
    m=Mesh(m.nodes,t,m.boundary,{**m.boundary_edges,'hole':hole})
    def condition(p,n):
        assert np.allclose(np.linalg.norm(n,axis=1),1)
        assert np.all(np.sum(n*(np.array([1.5,1.5])-p),axis=1)>0)
        return n[:,0]*2+n[:,1]*3
    a=solve_steady_heat(m,conductivity=2.,dirichlet={0:300.},outward_flux={'hole':condition})
    m.boundary_edges['hole']=hole[::-1,::-1]
    b=solve_steady_heat(m,conductivity=2.,dirichlet={0:300.},outward_flux={'hole':condition})
    np.testing.assert_allclose(a.temperature,b.temperature,atol=1e-12)
    # A single fixed endpoint on an otherwise natural edge is valid.
    r=solve_steady_heat(rectangle_mesh(1.,1.,1,1),conductivity=1.,dirichlet={0:300.},outward_flux={'bottom':1.})
    balance(r,{0})


@pytest.mark.parametrize('compatible',[True,False])
def test_pure_neumann_compatibility_is_not_uniqueness(compatible):
    m=rectangle_mesh(1.,1.,2,2)
    with pytest.raises(ValueError,match='connected component'):
        solve_steady_heat(m,conductivity=1.,dirichlet={},heat_source=1.,outward_flux={'right':1. if compatible else 2.},convection={'top':(0.,300.)})


def test_disconnected_dirichlet_or_robin_per_component():
    a=rectangle_mesh(1.,1.,2,2);n=len(a.nodes)
    m=Mesh(np.vstack([a.nodes,a.nodes+[2,0]]),np.vstack([a.triangles,a.triangles+n]),{}, {'second':a.boundary_edges['right']+n})
    with pytest.raises(ValueError,match='connected component'):
        solve_steady_heat(m,conductivity=2.,dirichlet={0:300.})
    r=solve_steady_heat(m,conductivity=2.,dirichlet={0:300.},convection={'second':(1.,350.)})
    np.testing.assert_array_equal(r.temperature,np.r_[np.full(n,300.),np.full(n,350.)])
