# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent field integrals and unchanged pre-implementation thermal gates."""
import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.assembly import assemble_stiffness
from galerkin.thermal import solve_steady_heat
from refsol.thermal import slab, sine_manufactured


def all_boundary(mesh, value):
    nodes = np.unique(np.concatenate(list(mesh.boundary.values())))
    return {int(i): value for i in nodes}


def test_linear_slab_flux_reaction_units_and_insulation():
    mesh = rectangle_mesh(2., .7, 8, 5)
    bc = {int(i): 350. for i in mesh.boundary['left']}
    bc.update({int(i): 300. for i in mesh.boundary['right']})
    r = solve_steady_heat(mesh, conductivity=12., dirichlet=bc)
    exact = slab(mesh.nodes, length=2., conductivity=12., left_temperature=350., right_temperature=300.)
    assert np.max(abs(r.temperature-exact.temperature))/350 < 1e-10
    np.testing.assert_allclose(r.heat_flux, np.broadcast_to([300.,0.], r.heat_flux.shape), rtol=0, atol=300e-10)
    np.testing.assert_allclose(sum(r.reaction[mesh.boundary['left']]), 210., rtol=1e-10)
    np.testing.assert_allclose(sum(r.reaction[mesh.boundary['right']]), -210., rtol=1e-10)
    fixed = np.array(sorted(bc))
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    assert not np.any(r.reaction[free])
    scale = sum(abs(r.load))+sum(abs(r.reaction))
    assert abs(sum(r.load+r.reaction))/scale < 1e-10
    original = assemble_stiffness(mesh, 12.)@r.temperature-r.load
    np.testing.assert_allclose(r.residual, original, rtol=0, atol=1e-10*scale)
    assert np.max(abs(r.residual[free]))/scale < 1e-10


def test_callable_load_integrates_shape_function_moments_not_centroid_lumping():
    mesh = Mesh([[0,0],[1,0],[0,1]], [[0,1,2]], {})
    r = solve_steady_heat(mesh, conductivity=2., dirichlet={0:300.,1:300.,2:300.},
                          heat_source=lambda p: p[:,0])
    np.testing.assert_allclose(r.load, [1/24,1/12,1/24], rtol=1e-13)
    np.testing.assert_allclose(r.reaction, -r.load, rtol=1e-13)
    np.testing.assert_array_equal(r.heat_flux, [[0.,0.]])


def test_constant_source_callable_and_scalar_agree_and_balance():
    mesh = rectangle_mesh(1., .8, 6, 5)
    bc = all_boundary(mesh, 300.)
    a = solve_steady_heat(mesh, conductivity=3., dirichlet=bc, heat_source=7.)
    b = solve_steady_heat(mesh, conductivity=3., dirichlet=bc,
                          heat_source=lambda p: np.full(len(p),7.))
    np.testing.assert_allclose(a.temperature,b.temperature,rtol=0,atol=1e-11)
    np.testing.assert_allclose(a.load,b.load,rtol=1e-13)
    np.testing.assert_allclose(sum(a.load), 7*.8, rtol=1e-13)
    assert abs(sum(a.load+a.reaction))/(sum(abs(a.load))+sum(abs(a.reaction))) < 1e-10
    assert np.min(a.temperature)>=300.
    assert -sum(a.reaction)>0  # Outward heat is minus the nodal reaction.


def test_independent_source_quadratic_identity_with_nonzero_boundary_temperature():
    mesh = rectangle_mesh(1.,1.,6,6)
    bc = {int(i):300.+10*mesh.nodes[i,0] for i in np.unique(np.concatenate(list(mesh.boundary.values())))}
    r=solve_steady_heat(mesh,conductivity=4.,dirichlet=bc,heat_source=5.)
    k=assemble_stiffness(mesh,4.)
    lhs=r.temperature@(k@r.temperature)
    rhs=r.temperature@(r.load+r.reaction)
    assert abs(lhs-rhs)/max(abs(lhs),abs(rhs),1.)<1e-10


def _interior_errors(mesh, result):
    # Independent 8x8 interior norm quadrature, not nodal or centroid error.
    x,w=np.polynomial.legendre.leggauss(8);x,w=(x+1)/2,w/2
    a,b=np.meshgrid(x,x,indexing='ij')
    bary=np.stack([(1-a)*(1-b),a,(1-a)*b],axis=-1).reshape(-1,3)
    weights=(2*w[:,None]*w[None,:]*(1-a)).ravel()
    p=mesh.nodes[mesh.triangles]
    points=np.einsum('qi,tij->tqj',bary,p)
    exact=sine_manufactured(points.reshape(-1,2),conductivity=2.5)
    th=np.einsum('qi,ti->tq',bary,result.temperature[mesh.triangles])
    diff=th-exact.temperature.reshape(th.shape)
    qdiff=result.heat_flux[:,None,:]-exact.heat_flux.reshape(points.shape)
    return (np.sqrt(np.sum(mesh.areas()[:,None]*weights*diff**2)),
            np.sqrt(np.sum(mesh.areas()[:,None]*weights*np.sum(qdiff**2,axis=2))))


@pytest.mark.slow
def test_sine_internal_l2_and_flux_convergence_original_gates():
    errors=[]
    for n in [8,16,32,64]:
        mesh=rectangle_mesh(1.,1.,n,n)
        r=solve_steady_heat(mesh,conductivity=2.5,dirichlet=all_boundary(mesh,300.),
                            heat_source=lambda p:sine_manufactured(p,conductivity=2.5).heat_source)
        errors.append(_interior_errors(mesh,r))
        scale=sum(abs(r.load))+sum(abs(r.reaction))
        assert abs(sum(r.load+r.reaction))/scale<1e-10
        fixed=np.array(sorted(all_boundary(mesh,300.)))
        free=np.setdiff1d(np.arange(mesh.num_nodes),fixed)
        assert np.max(abs(r.residual[free]))/scale<1e-10
    orders=np.log2(np.array(errors[:-1])/errors[1:])
    print('thermal n8/16/32/64 interior errors:',errors,'orders:',orders.tolist())
    assert np.all(orders[-2:,0]>=1.8)
    assert np.all(orders[-2:,1]>=.9)


@pytest.mark.parametrize('length_scale',[1e-3,1.,1e3])
@pytest.mark.parametrize('k_scale',[.1,1.,10.])
@pytest.mark.parametrize('q_scale',[.1,1.,10.])
def test_si_length_conductivity_source_similarity(length_scale,k_scale,q_scale):
    mesh=rectangle_mesh(1.,.8,4,4)
    def source(p):return sine_manufactured(p,lengths=(1.,.8),conductivity=2.).heat_source
    base=solve_steady_heat(mesh,conductivity=2.,dirichlet=all_boundary(mesh,300.),heat_source=source)
    scaled=rectangle_mesh(length_scale,.8*length_scale,4,4)
    result=solve_steady_heat(scaled,conductivity=2*k_scale,dirichlet=all_boundary(scaled,300.),
                             heat_source=lambda p:q_scale/length_scale**2*source(p/length_scale))
    expected=300.+q_scale/k_scale*(base.temperature-300.)
    assert np.max(abs(result.temperature-expected))/max(np.max(abs(expected)),1.)<1e-9
    np.testing.assert_allclose(result.heat_flux,q_scale/length_scale*base.heat_flux,rtol=1e-9,atol=1e-9*q_scale/length_scale)
    np.testing.assert_allclose(result.load,q_scale*base.load,rtol=1e-9,atol=1e-11*q_scale)
    np.testing.assert_allclose(result.reaction,q_scale*base.reaction,rtol=1e-9,atol=1e-10*q_scale)


def test_each_disconnected_component_needs_one_dirichlet_node():
    a=rectangle_mesh(1.,1.,2,2);b=rectangle_mesh(1.,1.,2,2)
    mesh=Mesh(np.vstack([a.nodes,b.nodes+[2.,0.]]),np.vstack([a.triangles,b.triangles+len(a.nodes)]),{})
    with pytest.raises(ValueError,match='connected component'):
        solve_steady_heat(mesh,conductivity=1.,dirichlet={0:300.})
    r=solve_steady_heat(mesh,conductivity=1.,dirichlet={0:300.,len(a.nodes):350.})
    np.testing.assert_array_equal(r.temperature,np.r_[np.full(len(a.nodes),300.),np.full(len(b.nodes),350.)])
    np.testing.assert_array_equal(r.heat_flux,0.)


@pytest.mark.parametrize('k',[0.,-1.,np.inf,np.nan,1j,True,[1.,2.]])
def test_invalid_conductivity(k):
    with pytest.raises(ValueError):solve_steady_heat(rectangle_mesh(1.,1.,1,1),conductivity=k,dirichlet={0:300.})


@pytest.mark.parametrize('bc',[{}, {True:300.}, {1.5:300.}, {-1:300.}, {999:300.},
                               {4:300.}, {0:np.nan}, {0:1j}, {0:[300.]}, []])
def test_invalid_dirichlet_and_nullspace(bc):
    with pytest.raises(ValueError):solve_steady_heat(rectangle_mesh(1.,1.,2,2),conductivity=1.,dirichlet=bc)


@pytest.mark.parametrize('source',[np.nan,np.inf,1j,[1.,2.],True,
                                  lambda p:1.,lambda p:np.zeros((len(p),1)),
                                  lambda p:np.full(len(p),np.nan),lambda p:np.ones(len(p),dtype=complex)])
def test_invalid_source_or_callback_shape(source):
    with pytest.raises(ValueError):solve_steady_heat(rectangle_mesh(1.,1.,1,1),conductivity=1.,dirichlet={0:300.},heat_source=source)


@pytest.mark.parametrize('kind',['nan','shape','fractional','index','clockwise','degenerate','duplicate','unused','coincident'])
def test_invalid_mesh_data(kind):
    mesh=rectangle_mesh(1.,1.,1,1)
    if kind=='nan':mesh.nodes[0,0]=np.nan
    if kind=='shape':mesh.nodes=mesh.nodes[:,0]
    if kind=='fractional':mesh.triangles=mesh.triangles.astype(float)
    if kind=='index':mesh.triangles[0,0]=99
    if kind=='clockwise':mesh.triangles[0]=mesh.triangles[0,::-1]
    if kind=='degenerate':mesh.nodes[:,1]=0
    if kind=='duplicate':mesh.triangles=np.vstack([mesh.triangles,mesh.triangles[0]])
    if kind=='unused':mesh.nodes=np.vstack([mesh.nodes,[2.,2.]])
    if kind=='coincident':mesh.nodes[1]=mesh.nodes[0]
    with pytest.raises(ValueError):solve_steady_heat(mesh,conductivity=1.,dirichlet={0:300.})


@pytest.mark.parametrize('nodes,triangles',[
    ([[0,0],[1,0],[0,1],[.2,.2],[1.2,.2],[.2,1.2]],[[0,1,2],[3,4,5]]),
    ([[0,0],[1,0],[0,1],[-1,0],[0,-1]],[[0,1,2],[0,3,4]]),
    ([[0,0],[1,0],[0,1],[1,1],[.5,0],[.5,-1]],[[0,1,2],[1,3,2],[0,5,4]]),
])
def test_overlapping_hinge_and_nonconforming_mesh_rejected(nodes,triangles):
    with pytest.raises(ValueError):solve_steady_heat(Mesh(nodes,triangles,{}),conductivity=1.,dirichlet={0:300.})
