# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Read-only acceptance against predeclared non-sine thermal oracles."""
import copy
import json
from types import SimpleNamespace
import numpy as np
import pytest
from galerkin.mesh import Mesh
from galerkin.thermal import solve_steady_heat
from thermal_independent_oracle import LX,LY,K,T0,AMP,rectangle,field,errors,system_checks,integrate_system


def solve_case(n=6,case='quartic'):
    p,t,tags=rectangle(n);fixed=tags['all'] if case=='quartic' else np.r_[tags['left'],tags['right']]
    bc=dict(zip(fixed,field(p[fixed],case)[0]));source=lambda points:field(points,case)[2]
    result=solve_steady_heat(Mesh(p,t,{}),conductivity=K,dirichlet=bc,heat_source=source)
    return p,t,tags,bc,source,result


@pytest.mark.parametrize('case',['quartic','mixed_quadratic'])
def test_independent_non_sine_convergence_and_original_system(case):
    rows=[]
    for n in (8,16,32,64):
        p,t,tags,bc,source,r=solve_case(n,case)
        e=errors(p,t,r,case,6);e8=errors(p,t,r,case,8)
        np.testing.assert_allclose(e,e8,rtol=1e-10,atol=0)
        checks=system_checks(p,t,r,bc,K,source)
        expected_total=(-K*AMP*(11*LY/(3*LX)+20*LX/(3*LY)) if case=='quartic' else 1e5*LX*LY)
        assert abs(r.load.sum()-expected_total)/abs(expected_total)<1e-10
        rows.append({'n':n,'temperature_L2':e[0],'flux_L2':e[1],**checks})
    e=np.array([[r['temperature_L2'],r['flux_L2']] for r in rows]);rates=np.log(e[:-1]/e[1:])/np.log(2)
    print(json.dumps({'case':case,'rows':rows,'orders':rates.tolist()}))
    assert np.all(np.diff(e,axis=0)<0)
    assert np.all(rates[-2:,0]>=1.8)
    assert np.all(rates[-2:,1]>=.9)


def test_independent_affine_mixed_side_reactions_and_insulation():
    p,t,tags,bc,source,r=solve_case(5,'affine')
    np.testing.assert_allclose((r.temperature-field(p,'affine')[0])/35,0,atol=1e-10,rtol=0)
    expected=np.array([-K*35/LX,0.])
    np.testing.assert_allclose((r.heat_flux-expected)/np.linalg.norm(expected),0,atol=1e-10,rtol=0)
    heat=K*35/LX*LY
    # TL=280 < TR=315: heat enters on the right, exits on the left.
    np.testing.assert_allclose([r.reaction[tags['left']].sum()/heat,r.reaction[tags['right']].sum()/heat],[-1,1],rtol=1e-10,atol=1e-10)
    system_checks(p,t,r,bc,K,source)


@pytest.mark.parametrize('length_scale',[1e-3,1.,1e3])
@pytest.mark.parametrize('c,d',[(.1,.1),(1.,1.),(10.,10.),(.1,10.),(10.,.1)])
def test_independent_length_material_source_similarity(length_scale,c,d):
    p,t,tags,bc,source,r=solve_case(5)
    changed_bc={i:T0+d/c*(value-T0) for i,value in bc.items()}
    changed=solve_steady_heat(Mesh(p*length_scale,t.copy(),{}),conductivity=K*c,
                             dirichlet=changed_bc,heat_source=lambda x:d/length_scale**2*source(x/length_scale))
    assert max(abs(changed.temperature-(T0+d/c*(r.temperature-T0))))/(AMP*max(1,d/c))<=1e-9
    for actual,expected in [(changed.heat_flux,d/length_scale*r.heat_flux),
                            (changed.load,d*r.load),(changed.reaction,d*r.reaction)]:
        assert np.max(abs(actual-expected))/np.max(abs(expected))<=1e-9


def test_independent_offset_and_geometry_covariance():
    p,t,tags,bc,source,r=solve_case(5)
    shifted=solve_steady_heat(Mesh(p,t,{}),conductivity=K,dirichlet={i:v+11 for i,v in bc.items()},heat_source=source)
    assert max(abs(shifted.temperature-r.temperature-11))/AMP<=1e-9
    assert np.max(abs(shifted.heat_flux-r.heat_flux))/np.max(abs(r.heat_flux))<=1e-9
    assert max(abs(shifted.reaction-r.reaction))/max(abs(r.reaction))<=1e-9
    angle=.37;rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    trans=np.array([.25,-.1]);rng=np.random.default_rng(15)
    perm=rng.permutation(len(p));inverse=np.argsort(perm);cells=rng.permutation(len(t))
    moved=solve_steady_heat(Mesh((p@rot.T+trans)[perm],inverse[t[cells]],{}),conductivity=K,
                           dirichlet={int(inverse[i]):v for i,v in bc.items()},
                           heat_source=lambda x:source((x-trans)@rot))
    assert max(abs(moved.temperature[inverse]-r.temperature))/AMP<=1e-9
    assert np.max(abs(moved.heat_flux[np.argsort(cells)]-r.heat_flux@rot.T))/np.max(abs(r.heat_flux))<=1e-9
    assert max(abs(moved.reaction[inverse]-r.reaction))/max(abs(r.reaction))<=1e-9


def test_independent_all_constrained_and_componentwise_anchors():
    p,t,tags=rectangle(1);bc=dict(enumerate([281.,299.,302.,317.]))
    source=lambda x:np.full(len(x),350.)
    r=solve_steady_heat(Mesh(p,t,{}),conductivity=K,dirichlet=bc,heat_source=350.)
    np.testing.assert_array_equal(r.temperature,list(bc.values()))
    system_checks(p,t,r,bc,K,source)
    nodes=np.r_[p,p+[1.,0.]];tris=np.r_[t,t+len(p)]
    r=solve_steady_heat(Mesh(nodes,tris,{}),conductivity=K,dirichlet={0:300.,len(p):2e6})
    np.testing.assert_allclose(r.temperature[:len(p)],300.,rtol=0,atol=1e-10)
    np.testing.assert_allclose(r.temperature[len(p):],2e6,rtol=0,atol=1e-10)
    np.testing.assert_allclose(r.heat_flux,0.,rtol=0,atol=1e-10)
    with pytest.raises(ValueError,match='component'):
        solve_steady_heat(Mesh(nodes,tris,{}),conductivity=K,dirichlet={0:300.})


def test_independent_fixed_source_inverse_conductivity_with_constant_trace():
    p,t,tags=rectangle(6);bc={int(i):T0 for i in tags['all']}
    r=solve_steady_heat(Mesh(p,t,{}),conductivity=K,dirichlet=bc,heat_source=1e5)
    for c in (.1,10.):
        changed=solve_steady_heat(Mesh(p,t,{}),conductivity=c*K,dirichlet=bc,heat_source=1e5)
        assert max(abs(changed.temperature-(T0+(r.temperature-T0)/c)))/AMP<=1e-9
        assert np.max(abs(changed.heat_flux-r.heat_flux))/np.max(abs(r.heat_flux))<=1e-9
        assert max(abs(changed.reaction-r.reaction))/max(abs(r.reaction))<=1e-9


def test_independent_reflected_diagonal_and_constructor_orientation():
    p,t,tags,bc,source,r=solve_case(5)
    mirrored=p.copy();mirrored[:,0]=LX-p[:,0]
    # Reflection reverses triangle orientation; Mesh's documented constructor
    # restores CCW. The solver itself still rejects mutated clockwise data.
    changed=solve_steady_heat(Mesh(mirrored,t.copy(),{}),conductivity=K,dirichlet=bc,
        heat_source=lambda x:source(np.column_stack((LX-x[:,0],x[:,1]))))
    assert max(abs(changed.temperature-r.temperature))/AMP<=1e-9
    assert np.max(abs(changed.heat_flux-r.heat_flux*[-1,1]))/np.max(abs(r.heat_flux))<=1e-9
    assert max(abs(changed.reaction-r.reaction))/max(abs(r.reaction))<=1e-9


@pytest.mark.parametrize('kind',['kzero','knegative','kboolean','ktensor','knan','kcomplex',
    'source_nan','source_shape','source_complex','source_scalar_callback','bc_empty','bc_interior',
    'bc_nan','bc_bool_index','bc_float_index','bc_outside','clockwise','fractional_connectivity',
    'duplicate_triangle','unused_node','degenerate','nonfinite_node'])
def test_independent_invalid_contract(kind):
    p,t,tags=rectangle(2);mesh=Mesh(p,t,{});kw=dict(conductivity=K,dirichlet={int(i):300. for i in tags['all']})
    badk={'kzero':0.,'knegative':-1.,'kboolean':True,'ktensor':np.eye(2),'knan':np.nan,'kcomplex':1+0j}
    if kind in badk:kw['conductivity']=badk[kind]
    elif kind=='source_nan':kw['heat_source']=lambda x:np.full(len(x),np.nan)
    elif kind=='source_shape':kw['heat_source']=lambda x:np.ones((len(x),1))
    elif kind=='source_complex':kw['heat_source']=lambda x:np.ones(len(x),complex)
    elif kind=='source_scalar_callback':kw['heat_source']=lambda x:1.
    elif kind=='bc_empty':kw['dirichlet']={}
    elif kind=='bc_interior':kw['dirichlet']={4:300.}
    elif kind=='bc_nan':kw['dirichlet']={0:np.nan}
    elif kind=='bc_bool_index':kw['dirichlet']={True:300.}
    elif kind=='bc_float_index':kw['dirichlet']={0.:300.}
    elif kind=='bc_outside':kw['dirichlet']={len(p):300.}
    elif kind=='clockwise':mesh.triangles=mesh.triangles[:,::-1].copy()
    elif kind=='fractional_connectivity':mesh.triangles=mesh.triangles.astype(float)+.1
    elif kind=='duplicate_triangle':mesh.triangles=np.r_[mesh.triangles,mesh.triangles[:1]]
    elif kind=='unused_node':mesh.nodes=np.r_[mesh.nodes,[[2.,2.]]]
    elif kind=='degenerate':mesh.nodes[1]=mesh.nodes[0]
    elif kind=='nonfinite_node':mesh.nodes[0,0]=np.nan
    with pytest.raises(ValueError):solve_steady_heat(mesh,**kw)


def test_independent_negative_controls_are_detected():
    p,t,tags,bc,source,r=solve_case(6)
    # Wrong physical inputs produce different valid PDEs: the oracle must reject
    # them even though each solve can satisfy its own tiny algebraic residual.
    wrong_source=solve_steady_heat(Mesh(p,t,{}),conductivity=K,dirichlet=bc,heat_source=lambda x:-source(x))
    wrong_k=solve_steady_heat(Mesh(p,t,{}),conductivity=2*K,dirichlet=bc,heat_source=source)
    for bad in (wrong_source,wrong_k):
        with pytest.raises(AssertionError):system_checks(p,t,bad,bc,K,source)
    flipped=copy.deepcopy(r);flipped.heat_flux*=-1
    assert errors(p,t,flipped,'quartic')[1]>10*errors(p,t,r,'quartic')[1]
    damaged=copy.deepcopy(r);damaged.temperature[10]+=.05
    with pytest.raises(AssertionError):system_checks(p,t,damaged,bc,K,source)
    print('NEGATIVE CONTROLS: wrong source, wrong k, flipped flux, damaged temperature rejected')
