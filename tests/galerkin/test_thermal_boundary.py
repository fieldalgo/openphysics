# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Boundary contract and independent physical references (SI, unit depth)."""
import numpy as np
import pytest
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.thermal import PlanarSteadyHeatResult, solve_steady_heat
from refsol.thermal_boundary import dirichlet_robin_slab, robin_only_slab


def bc_left(mesh, value=320.):
    return {int(i): value for i in mesh.boundary['left']}


def balance(r, fixed=()):
    scale=max(sum(np.sum(abs(x)) for x in (r.generated_heat_rate_per_depth,r.reaction_heat_rate_per_depth,r.outward_prescribed_heat_rate_per_depth,r.outward_convective_heat_rate_per_depth)),1e-300)
    assert abs(np.sum(r.generated_heat_rate_per_depth+r.reaction_heat_rate_per_depth-r.outward_prescribed_heat_rate_per_depth-r.outward_convective_heat_rate_per_depth))/scale < 1e-10
    free=np.setdiff1d(np.arange(len(r.temperature)),list(fixed))
    assert np.max(abs(r.residual_heat_rate_per_depth[free]),initial=0)/scale < 1e-10


@pytest.mark.parametrize('mode',['flux','mixed','robin'])
@pytest.mark.parametrize('left_temperature',[320.,280.])
def test_linear_patch_sign_cooling_balance(mode,left_temperature):
    m=rectangle_mesh(1.,.8,6,5);k=2.5;g=.7;h=10.;ambient=300.
    if mode=='robin':
        ref=robin_only_slab(length=1.,thermal_conductivity=k,heat_transfer_coefficient=(8.,h),
                            ambient_temperature=(left_temperature,ambient),heat_source_density=0.,
                            inward_heat_flux=(0.,-g))
        bc={};conv={'left':(8.,left_temperature),'right':(h,ambient)}
    else:
        ref=dirichlet_robin_slab(length=1.,thermal_conductivity=k,prescribed_temperature=left_temperature,
                                 heat_source_density=0.,inward_heat_flux=-g,
                                 heat_transfer_coefficient=h if mode=='mixed' else 0.,ambient_temperature=ambient)
        bc=bc_left(m,left_temperature);conv={'right':(h,ambient)} if mode=='mixed' else None
    r=solve_steady_heat(m,thermal_conductivity=k,prescribed_temperature=bc,inward_heat_flux={'right':-g},convection=conv)
    np.testing.assert_allclose(r.temperature,ref.temperature(m.nodes),rtol=0,atol=1e-10)
    centers=m.nodes[m.triangles].mean(axis=1)
    np.testing.assert_allclose(r.heat_flux,ref.heat_flux(centers),rtol=0,atol=1e-10)
    np.testing.assert_allclose(sum(r.outward_prescribed_heat_rate_per_depth),g*.8,rtol=1e-12)
    if mode!='flux':
        expected=(ref.outward_heat_flux[1]-g)*.8
        np.testing.assert_allclose(sum(r.outward_convective_heat_rate_per_depth[m.boundary['right']]),expected,atol=1e-10)
        if left_temperature>ambient:assert expected>0
        else:assert expected<0
    balance(r,bc)


def test_original_result_constructor_and_default_compatibility():
    a=np.zeros(3);r=PlanarSteadyHeatResult(a,a,a,a,a)
    assert r.outward_prescribed_heat_rate_per_depth is None and r.applied_heat_rate_per_depth is None
    m=rectangle_mesh(1.,1.,2,2);bc=bc_left(m)
    old=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc)
    new=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc,inward_heat_flux={},convection={})
    for name in ('temperature','heat_flux','generated_heat_rate_per_depth','reaction_heat_rate_per_depth',
                 'residual_heat_rate_per_depth'):
        np.testing.assert_array_equal(getattr(old,name),getattr(new,name))
    for name in ('outward_prescribed_heat_rate_per_depth','ambient_convective_heat_rate_per_depth',
                 'outward_convective_heat_rate_per_depth'):
        np.testing.assert_array_equal(getattr(new,name),0.)
    np.testing.assert_array_equal(new.applied_heat_rate_per_depth,new.generated_heat_rate_per_depth)


def test_consistent_affine_h_ambient_and_flux_moments():
    m=rectangle_mesh(1.,1.,1,1)
    r=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature={0:300.},
        inward_heat_flux={'right':lambda p,n:-(3-5*p[:,1])},
        convection={'right':(lambda p,n:2+3*p[:,1],lambda p,n:300+20*p[:,1])})
    edge=m.boundary_edges['right'][0];H=np.array([[11,7],[7,17]])/12
    G=np.array([4,-1])/6
    B=np.array([3*2*300+2*320+5*300+5*320,2*300+2*320+5*300+3*5*320])/12
    np.testing.assert_allclose(r.outward_prescribed_heat_rate_per_depth[edge],G,atol=1e-13)
    np.testing.assert_allclose(r.ambient_convective_heat_rate_per_depth[edge],B,atol=1e-12)
    np.testing.assert_allclose(r.outward_convective_heat_rate_per_depth[edge],H@r.temperature[edge]-B,atol=1e-12)
    assert not np.allclose(B,np.array([3.5*310/2]*2))
    assert not np.allclose(H@r.temperature[edge]-B,H.sum(axis=1)*r.temperature[edge]-B)
    balance(r,{0})


@pytest.mark.parametrize('s',[1e-3,1.,1e3])
@pytest.mark.parametrize('c',[.1,1.,10.])
def test_boundary_si_similarity(s,c):
    def solve(scale,coef):
        m=rectangle_mesh(scale,.8*scale,4,4)
        return solve_steady_heat(m,thermal_conductivity=2.5*coef,prescribed_temperature=bc_left(m),heat_source_density=5*coef/scale**2,
             inward_heat_flux={'right':-(.7*coef/scale)},convection={'right':(10*coef/scale,300.)})
    a=solve(1.,1.);b=solve(s,c)
    np.testing.assert_allclose(b.temperature,a.temperature,rtol=1e-9,atol=1e-9)
    np.testing.assert_allclose(b.heat_flux,a.heat_flux*c/s,rtol=1e-9,atol=1e-9*c/s)
    for name in ('generated_heat_rate_per_depth','reaction_heat_rate_per_depth','outward_prescribed_heat_rate_per_depth',
                 'ambient_convective_heat_rate_per_depth','outward_convective_heat_rate_per_depth',
                 'applied_heat_rate_per_depth'):
        np.testing.assert_allclose(getattr(b,name),getattr(a,name)*c,rtol=1e-9,atol=1e-9*c)


def test_joint_offset_and_h_zero_ambient_invariance():
    m=rectangle_mesh(1.,1.,4,4)
    def solve(offset,h=10.):
        return solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc_left(m,320+offset),heat_source_density=5.,
                                convection={'right':(h,300+offset)})
    a=solve(0);b=solve(1e8)
    np.testing.assert_allclose(b.temperature-1e8,a.temperature,rtol=0,atol=2e-8)
    np.testing.assert_array_equal(a.heat_flux,b.heat_flux)
    np.testing.assert_array_equal(a.outward_convective_heat_rate_per_depth,b.outward_convective_heat_rate_per_depth)
    z=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc_left(m),convection={'right':(0.,-999.)})
    plain=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc_left(m))
    np.testing.assert_array_equal(z.temperature,plain.temperature)
    negative=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature={},convection={'right':(1.,-100.)})
    np.testing.assert_array_equal(negative.temperature,-100.)


@pytest.mark.parametrize('bad',[True,1j,np.nan,np.inf,[1.],lambda p,n:1.,lambda p,n:np.zeros((len(p),1)),lambda p,n:np.ones(len(p),dtype=bool),lambda p,n:np.full(len(p),np.nan)])
@pytest.mark.parametrize('kind',['flux','h','ambient'])
def test_invalid_values_and_callback_shapes(bad,kind):
    m=rectangle_mesh(1.,1.,2,2);kwargs={'inward_heat_flux':{'right':bad}} if kind=='flux' else {'convection':{'right':(bad,300.) if kind=='h' else (0.,bad)}}
    with pytest.raises(ValueError):solve_steady_heat(m,thermal_conductivity=1.,prescribed_temperature=bc_left(m),**kwargs)


@pytest.mark.parametrize('h',[-1.,lambda p,n:-np.ones(len(p))])
def test_negative_h(h):
    with pytest.raises(ValueError):solve_steady_heat(rectangle_mesh(1.,1.,2,2),thermal_conductivity=1.,prescribed_temperature={},convection={'right':(h,300.)})


@pytest.mark.parametrize('case',['empty','unknown','interior','orphan','degenerate','duplicate','cross_tag','fractional','shape','index','full_dir'])
@pytest.mark.parametrize('kind',['inward_heat_flux','convection'])
def test_invalid_selected_edges(case,kind):
    m=rectangle_mesh(1.,1.,2,2);bc={0:300.};tag='right';value=0. if kind=='inward_heat_flux' else (0.,300.)
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
    with pytest.raises(ValueError):solve_steady_heat(m,thermal_conductivity=1.,prescribed_temperature=bc,**{kind:data})


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
    a=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature={0:300.},inward_heat_flux={'hole':lambda p,n:-condition(p,n)})
    m.boundary_edges['hole']=hole[::-1,::-1]
    b=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature={0:300.},inward_heat_flux={'hole':lambda p,n:-condition(p,n)})
    np.testing.assert_allclose(a.temperature,b.temperature,atol=1e-12)
    # A single fixed endpoint on an otherwise natural edge is valid.
    r=solve_steady_heat(rectangle_mesh(1.,1.,1,1),thermal_conductivity=1.,prescribed_temperature={0:300.},inward_heat_flux={'bottom':-1.})
    balance(r,{0})


@pytest.mark.parametrize('compatible',[True,False])
def test_pure_neumann_compatibility_is_not_uniqueness(compatible):
    m=rectangle_mesh(1.,1.,2,2)
    with pytest.raises(ValueError,match='connected component'):
        solve_steady_heat(m,thermal_conductivity=1.,prescribed_temperature={},heat_source_density=1.,inward_heat_flux={'right':-(1. if compatible else 2.)},convection={'top':(0.,300.)})


def test_disconnected_dirichlet_or_robin_per_component():
    a=rectangle_mesh(1.,1.,2,2);n=len(a.nodes)
    m=Mesh(np.vstack([a.nodes,a.nodes+[2,0]]),np.vstack([a.triangles,a.triangles+n]),{}, {'second':a.boundary_edges['right']+n})
    with pytest.raises(ValueError,match='connected component'):
        solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature={0:300.})
    r=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature={0:300.},convection={'second':(1.,350.)})
    np.testing.assert_array_equal(r.temperature,np.r_[np.full(n,300.),np.full(n,350.)])


@pytest.mark.parametrize('data',[[],True,1.])
@pytest.mark.parametrize('kind',['inward_heat_flux','convection'])
def test_condition_maps_required(data,kind):
    with pytest.raises(ValueError):
        solve_steady_heat(rectangle_mesh(1.,1.,1,1),thermal_conductivity=1.,prescribed_temperature={0:300.},**{kind:data})


@pytest.mark.parametrize('pair',[1.,(),(1.,),(1.,300.,0.),np.array([1.,300.])])
def test_convection_pair_required(pair):
    with pytest.raises(ValueError):
        solve_steady_heat(rectangle_mesh(1.,1.,1,1),thermal_conductivity=1.,prescribed_temperature={0:300.},convection={'right':pair})


def test_small_positive_robin_and_dirichlet_limits():
    m=rectangle_mesh(1.,1.,3,3)
    # Positive support is not discarded by an arbitrary unitful threshold.
    tiny=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature={},convection={'right':(1e-8,300.)})
    np.testing.assert_array_equal(tiny.temperature,300.)
    ref=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc_left(m),inward_heat_flux={'right':-.7})
    small=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc_left(m),inward_heat_flux={'right':-.7},convection={'right':(1e-8,300.)})
    np.testing.assert_allclose(small.temperature,ref.temperature,rtol=0,atol=1e-7)
    large=solve_steady_heat(m,thermal_conductivity=2.,prescribed_temperature=bc_left(m),convection={'right':(1e6,300.)})
    assert np.max(abs(large.temperature[m.boundary['right']]-300.))<5e-5
    quality_scale=sum(abs(large.reaction_heat_rate_per_depth))+sum(abs(large.outward_convective_heat_rate_per_depth))
    assert abs(sum(large.reaction_heat_rate_per_depth-large.outward_convective_heat_rate_per_depth))/quality_scale<1e-10
