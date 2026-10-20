# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed-gate independent acceptance of outward flux and Robin heat boundaries."""
import numpy as np
import pytest
from galerkin.mesh import Mesh,rectangle_mesh
from galerkin.thermal import solve_steady_heat,SteadyHeatResult
from thermal_flux_robin_independent_oracle import (
    dirichlet_flux,dirichlet_robin,robin_only,slab_state,smooth_mms,
    independent_system,triangle_geometry,exact_line_moments)

K0=2.7
NORMALS={'left':(-1,0),'right':(1,0),'bottom':(0,-1),'top':(0,1)}
def normal(tag,points):return np.broadcast_to(NORMALS[tag],points.shape)


def audit(mesh,result,bc,source=0.,flux=None,convection=None,k=K0,normals=normal,reference=300.,order=8):
    flux,convection=flux or {},convection or {}
    K,H,f,B,G,shift=independent_system(mesh,k,source,flux,convection,normals,reference,order)
    delta=result.temperature-reference
    expected_conv=H@delta-shift
    expected_residual=K@delta+expected_conv-f+G
    rate=max(np.sum(abs(f))+np.sum(abs(G))+np.sum(abs(expected_conv))+np.sum(abs(result.reaction)),k,1e-30)
    for actual,expected in [(result.load,f),(result.prescribed_outward_load,G),(result.ambient_load,B),(result.system_rhs,f+B-G),(result.convective_outward,expected_conv),(result.residual,expected_residual)]:
        np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-10*rate)
    free=np.setdiff1d(np.arange(mesh.num_nodes),list(bc));fixed=np.array(list(bc),dtype=int)
    np.testing.assert_allclose(result.reaction[free],0,atol=1e-10*rate)
    np.testing.assert_allclose(result.residual[free],0,atol=1e-10*rate)
    np.testing.assert_allclose(result.reaction[fixed],expected_residual[fixed],atol=1e-10*rate,rtol=1e-10)
    assert abs(np.sum(f+result.reaction-G-expected_conv))<=1e-10*rate
    b,w,p,grad=triangle_geometry(mesh.nodes,mesh.triangles,order)
    gradient=np.einsum('tai,ta->ti',grad,delta[mesh.triangles])
    np.testing.assert_allclose(result.heat_flux,-k*gradient,atol=1e-10*max(k,np.max(abs(result.heat_flux))),rtol=1e-10)
    rhs=f+shift-G
    support=delta@result.reaction
    assert abs(delta@((K+H)@delta)-delta@rhs-support)<1e-10*max(rate*np.max(abs(delta)),k)
    return K,H,f,B,G


def solve(m,bc,source=0.,flux=None,convection=None,k=K0):
    return solve_steady_heat(m,conductivity=k,dirichlet=bc,heat_source=source,outward_flux=flux,convection=convection)


@pytest.mark.parametrize('kind',['flux','robin','robin_only','one_robin'])
@pytest.mark.parametrize('source',[0.,6.3,-6.3])
def test_thermal_flux_robin_independent_strip(kind,source):
    m=rectangle_mesh(1.4,.8,6,4);g=2.1;h=7.;ambient=300.;bc={int(i):340. for i in m.boundary['left']};flux={'right':g};conv={}
    if kind=='flux':coef=dirichlet_flux(length=1.4,conductivity=K0,source=source,left_temperature=340.,right_outward=g)
    elif kind=='robin':
        coef=dirichlet_robin(length=1.4,conductivity=K0,source=source,left_temperature=340.,right_h=h,right_ambient=ambient,right_outward=g);conv={'right':(h,ambient)}
    else:
        hleft=0. if kind=='one_robin' else 5.
        coef=robin_only(length=1.4,conductivity=K0,source=source,h_left=hleft,h_right=h,ambient_left=320.,ambient_right=ambient,outward_left=-1.,outward_right=g)
        bc={};flux['left']=-1.;conv={'left':(hleft,320.),'right':(h,ambient)}
    r=solve(m,bc,source,flux,conv);audit(m,r,bc,source,flux,conv)
    if source==0:
        exact,qq=slab_state(m.nodes[:,0],coef,conductivity=K0,source=source)
        np.testing.assert_allclose(r.temperature,exact,atol=1e-10*40,rtol=0)
        np.testing.assert_allclose(r.heat_flux,np.column_stack((np.full(m.num_triangles,qq[0]),np.zeros(m.num_triangles))),atol=1e-10*K0*40)
    # Weak endpoint rates, distinct from integrating raw P1 gradients.
    gtotal=sum(v*.8 for v in flux.values())
    assert abs(np.sum(r.load+r.reaction-r.convective_outward)-gtotal)<1e-10*max(K0,abs(gtotal),np.sum(abs(r.load)))


def norms(m,r,exact,k=K0,order=8):
    b,w,p,grad=triangle_geometry(m.nodes,m.triangles,order)
    th=np.einsum('qa,ta->tq',b,r.temperature[m.triangles])
    temp,flux=exact(p)
    return np.sqrt(np.array([np.sum(w*(th-temp)**2),np.sum(w*np.sum((r.heat_flux[:,None,:]-flux)**2,axis=-1))]))


@pytest.mark.parametrize('kind',['strip_mixed','strip_robin','mms_mixed','mms_robin'])
def test_thermal_flux_robin_independent_convergence(kind):
    history=[];raw_errors=[];weak_errors=[]
    for n in (8,16,32,64):
        m=rectangle_mesh(1,1,n,n)
        if kind.startswith('strip'):
            source=6.3;flux={'right':2.1};conv={'right':(7.,300.)}
            if kind=='strip_mixed':
                bc={int(i):340. for i in m.boundary['left']};coef=dirichlet_robin(length=1,conductivity=K0,source=source,left_temperature=340.,right_h=7.,right_ambient=300.,right_outward=2.1)
            else:
                bc={};flux['left']=-1.;conv['left']=(5.,320.);coef=robin_only(length=1,conductivity=K0,source=source,h_left=5.,h_right=7.,ambient_left=320.,ambient_right=300.,outward_left=-1.,outward_right=2.1)
            def exact(p):
                tt,q=slab_state(p[...,0],coef,conductivity=K0,source=source)
                return tt,np.stack((q,np.zeros_like(q)),axis=-1)
        else:
            source=lambda p:smooth_mms(p,K0)['source'];flux={};conv={}
            bc={int(i):float(smooth_mms(m.nodes[i],K0)['temperature']) for i in m.boundary['left']} if kind=='mms_mixed' else {}
            for tag in NORMALS:
                if tag=='left' and bc:continue
                flux[tag]=lambda p,n:smooth_mms(p,K0)['outward']
                def ambient(p,n):
                    s=smooth_mms(p,K0);return s['temperature']-(np.sum(s['flux']*n,axis=-1)-s['outward'])/s['h']
                conv[tag]=(lambda p,n:smooth_mms(p,K0)['h'],ambient)
            exact=lambda p:(smooth_mms(p,K0)['temperature'],smooth_mms(p,K0)['flux'])
        r=solve(m,bc,source,flux,conv);integrals=audit(m,r,bc,source,flux,conv)
        error=norms(m,r,exact);np.testing.assert_allclose(error,norms(m,r,exact,order=10),rtol=.01)
        high=independent_system(m,K0,source,flux,conv,normal,order=10)
        for low,higher in zip(integrals[2:],high[2:5]):
            assert np.linalg.norm(low-higher,1)<.01*error[1]
        history.append(error)
        if kind.startswith('strip'):
            # Exact right flux is nonzero. Compare raw constitutive boundary gradient.
            edges=m.boundary_edges['right'];target=exact(np.array([[1.,.5]]))[1][0,0]
            owner={tuple(sorted((int(a),int(b)))):i for i,tri in enumerate(m.triangles) for a,b in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0]))}
            raw=sum(np.linalg.norm(m.nodes[e[1]]-m.nodes[e[0]])*r.heat_flux[owner[tuple(sorted(map(int,e)))]][0] for e in edges)
            raw_errors.append(abs(raw-target)/abs(target))
            nodes=m.boundary['right'];weak=np.sum(r.prescribed_outward_load[nodes]+r.convective_outward[nodes])
            weak_errors.append(abs(weak-target)/abs(target))
    rates=np.log2(np.array(history[:-1])/np.array(history[1:]))
    print(kind,'errors',history,'rates',rates,'rawboundary',raw_errors,'weakboundary',weak_errors)
    assert np.all(rates[-2:]>=np.array([1.8,.9]))
    assert np.all(np.diff(history,axis=0)<0)
    if raw_errors:
        assert np.all(np.diff(raw_errors)<0)
        assert np.all(np.log2(np.array(raw_errors[:-1])/np.array(raw_errors[1:]))[-2:]>=.9)
        assert raw_errors[-1]<=.02
        # Roundoff-exact weak rates get an exactness gate, never a fabricated order.
        assert max(weak_errors)<1e-10


@pytest.mark.parametrize('mode',['variable_line','negative_kelvin','h0','offset'])
def test_thermal_flux_robin_independent_line_offset(mode):
    m=rectangle_mesh(1,1,4,4);bc={int(i):330. for i in m.boundary['left']}
    flux={'right':lambda p,n:3.-8*p[:,1]+2*p[:,1]**2}
    conv={'right':(lambda p,n:2+3*p[:,1]+p[:,1]**2,lambda p,n:300-7*p[:,1]+5*p[:,1]**2)}
    if mode=='negative_kelvin':bc={i:-25. for i in bc};conv={'right':(7.,-40.)}
    if mode=='h0':conv={'right':(0.,-20.)}
    if mode=='offset':conv={'right':(conv['right'][0],300.)}
    r=solve(m,bc,flux=flux,convection=conv);audit(m,r,bc,flux=flux,convection=conv)
    if mode=='variable_line':
        expectedH=np.zeros((m.num_nodes,m.num_nodes));expectedB=np.zeros(m.num_nodes);expectedG=np.zeros(m.num_nodes)
        from numpy.polynomial import polynomial as poly
        for edge in m.boundary_edges['right']:
            start,end=m.nodes[edge,1];y=np.array([start,end-start])
            hp=poly.polyadd(poly.polyadd([2.],3*y),poly.polymul(y,y));ap=poly.polyadd(poly.polyadd([300.],-7*y),5*poly.polymul(y,y));gp=poly.polyadd(poly.polyadd([3.],-8*y),2*poly.polymul(y,y))
            H,B,G=exact_line_moments(abs(end-start),hp,ap,gp)
            expectedH[np.ix_(edge,edge)]+=H;np.add.at(expectedB,edge,B);np.add.at(expectedG,edge,G)
        np.testing.assert_allclose(r.ambient_load,expectedB,rtol=1e-10,atol=1e-10)
        np.testing.assert_allclose(r.prescribed_outward_load,expectedG,rtol=1e-10,atol=1e-10)
        np.testing.assert_allclose(r.convective_outward,expectedH@r.temperature-expectedB,rtol=1e-10,atol=1e-10)
    if mode=='h0':
        bare=solve(m,bc,flux=flux);np.testing.assert_array_equal(r.temperature,bare.temperature)
    if mode=='offset':
        shift=2**30
        shiftedconv={'right':(conv['right'][0],300.+shift)}
        shifted=solve(m,{i:t+shift for i,t in bc.items()},flux=flux,convection=shiftedconv)
        np.testing.assert_allclose(shifted.temperature-shift,r.temperature,rtol=0,atol=2e-6)
        # Stable differences retain flux/rates, independently of large absolute T.
        np.testing.assert_allclose(shifted.heat_flux,r.heat_flux,rtol=1e-9,atol=1e-9)
        np.testing.assert_allclose(shifted.convective_outward,r.convective_outward,rtol=1e-9,atol=1e-9)


@pytest.mark.parametrize('scale',[1e-3,1.,1e3])
@pytest.mark.parametrize('factor',[.1,1.,10.])
def test_thermal_flux_robin_independent_similarity(scale,factor):
    m=rectangle_mesh(1,1,5,5);bc={int(i):340. for i in m.boundary['left']}
    r=solve(m,bc,6.3,{'right':2.1},{'right':(7.,300.)})
    angle=.41;R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    shift=np.array([2.3,-1.7])*scale
    changed=Mesh(scale*m.nodes@R.T+shift,m.triangles[:,[1,2,0]][::-1],m.boundary,{tag:edges[::-1,::-1] for tag,edges in m.boundary_edges.items()})
    rr=solve(changed,bc,factor/scale**2*6.3,{'right':factor/scale*2.1},{'right':(factor/scale*7.,300.)},k=factor*K0)
    expected_norm=lambda tag,p:np.broadcast_to(np.asarray(NORMALS[tag])@R.T,p.shape)
    audit(changed,rr,bc,factor/scale**2*6.3,{'right':factor/scale*2.1},{'right':(factor/scale*7.,300.)},k=factor*K0,normals=expected_norm)
    np.testing.assert_allclose(rr.temperature,r.temperature,rtol=0,atol=1e-9*40)
    np.testing.assert_allclose(rr.heat_flux,factor/scale*r.heat_flux[::-1]@R.T,rtol=1e-9,atol=1e-9*factor/scale*K0*40)
    np.testing.assert_allclose(rr.reaction,factor*r.reaction,rtol=1e-9,atol=1e-9*factor*K0*40)


@pytest.mark.parametrize('change',['none','reverse','rotate','order'])
def test_thermal_flux_robin_independent_hole_normals(change):
    outer=np.array([[-2.,-2.],[2.,-2.],[2.,2.],[-2.,2.]])
    nodes=np.concatenate((outer,outer/2));cells=[];edges=[]
    for i in range(4):
        j=(i+1)%4;cells.extend([[i,j,j+4],[i,j+4,i+4]]);edges.extend([[i,j],[i+4,j+4]])
    cells,edges=np.array(cells),np.array(edges);R=np.eye(2);shift=np.zeros(2);perm=np.arange(8)
    if change=='reverse':edges=edges[::-1,::-1];cells=cells[:,::-1]
    if change=='rotate':R=np.array([[.6,-.8],[.8,.6]]);shift=np.array([1.7,-2.1]);nodes=nodes@R.T+shift
    if change=='order':
        perm=perm[::-1];inverse=np.argsort(perm);nodes=nodes[perm];cells=inverse[cells[::-1]];edges=inverse[edges]
    m=Mesh(nodes,cells,{'all':np.arange(8)},{'all':edges})
    def truth(p):return 300+(p-shift)@R@np.array([2.,-3.])
    def exact_normal(tag,p):
        local=(p-shift)@R;limit=np.max(abs(local),axis=1)
        axis=np.argmax(abs(local),axis=1);n=np.zeros_like(local);n[np.arange(len(p)),axis]=np.sign(local[np.arange(len(p)),axis])
        n[limit<1.5]*=-1
        return n@R.T
    def outward(p,n):
        np.testing.assert_allclose(n,exact_normal('all',p),atol=1e-12)
        return n@(-K0*np.array([2.,-3.])@R.T)-5*(truth(p)-300)
    flux={'all':outward};conv={'all':(5.,300.)}
    r=solve(m,{},flux=flux,convection=conv);audit(m,r,{},flux=flux,convection=conv,normals=exact_normal)
    np.testing.assert_allclose(r.temperature,truth(m.nodes),atol=1e-10*10)


@pytest.mark.parametrize('kind',['duplicate','reversed_duplicate','interior','unknown','empty','float_index','self_edge','negative_index','full_dirichlet','flux_shape','ambient_shape','h_scalar_callback','h_negative','h_nan','ambient_inf_h0','complex_flux','bool_h','neumann_compatible','neumann_incompatible'])
def test_thermal_flux_robin_independent_rejection(kind):
    m=rectangle_mesh(1,1,2,2);bc={int(i):300. for i in m.boundary['left']};flux={'right':1.};conv={};source=0.
    if kind=='duplicate':m.boundary_edges['extra']=m.boundary_edges['right'].copy();flux['extra']=2.
    elif kind=='reversed_duplicate':m.boundary_edges['right']=np.concatenate((m.boundary_edges['right'],m.boundary_edges['right'][:1,::-1]))
    elif kind=='interior':m.boundary_edges['right']=np.array([[0,4]])
    elif kind=='unknown':flux={'missing':1.}
    elif kind=='empty':m.boundary_edges['right']=np.empty((0,2),dtype=int)
    elif kind=='float_index':m.boundary_edges['right']=m.boundary_edges['right'].astype(float)
    elif kind=='self_edge':m.boundary_edges['right']=np.array([[2,2]])
    elif kind=='negative_index':m.boundary_edges['right']=np.array([[-1,2]])
    elif kind=='full_dirichlet':flux={'left':0.}
    elif kind=='flux_shape':flux={'right':lambda p,n:np.ones((len(p),1))}
    elif kind=='ambient_shape':conv={'right':(1.,lambda p,n:np.ones((2,len(p))))}
    elif kind=='h_scalar_callback':conv={'right':(lambda p,n:1.,300.)}
    elif kind=='h_negative':conv={'right':(-1.,300.)}
    elif kind=='h_nan':conv={'right':(np.nan,300.)}
    elif kind=='ambient_inf_h0':conv={'right':(0.,np.inf)}
    elif kind=='complex_flux':flux={'right':1+1j}
    elif kind=='bool_h':conv={'right':(True,300.)}
    elif kind=='neumann_compatible':bc={};flux={'left':-1.,'right':1.};conv={'top':(0.,300.)}
    else:bc={};flux={'right':1.}
    with pytest.raises(ValueError):solve(m,bc,source,flux,conv)


def test_thermal_flux_robin_independent_components_corner_defaults():
    m=rectangle_mesh(1,1,2,2);n=m.num_nodes
    nodes=np.concatenate((m.nodes,m.nodes+[2,0]));tri=np.concatenate((m.triangles,m.triangles+n))
    boundary={tag:np.concatenate((v,v+n)) for tag,v in m.boundary.items()}
    edges={'first':m.boundary_edges['right'],'second':m.boundary_edges['right']+n}
    combined=Mesh(nodes,tri,boundary,edges)
    bc={0:300.};conv={'second':(3.,310.)}
    r=solve(combined,bc,convection=conv)
    audit(combined,r,bc,convection=conv,normals=lambda tag,p:np.broadcast_to([1.,0.],p.shape))
    np.testing.assert_allclose(r.temperature[:n],300.,atol=1e-10)
    np.testing.assert_allclose(r.temperature[n:],310.,atol=1e-10)
    with pytest.raises(ValueError):solve(combined,bc,convection={'second':(0.,310.)})
    # One fixed endpoint of a selected edge is an allowed mixed corner.
    affine=300+2*m.nodes[:,0];corner={int(i):float(affine[i]) for i in m.boundary['left']}
    flux={'right':-2*K0,'top':0.,'bottom':0.}
    r=solve(m,corner,flux=flux);audit(m,r,corner,flux=flux)
    np.testing.assert_allclose(r.temperature,affine,atol=1e-10)
    baseline=solve(m,corner);empty=solve(m,corner,flux={},convection={})
    for field in baseline.__dataclass_fields__:np.testing.assert_array_equal(getattr(baseline,field),getattr(empty,field))
    five=SteadyHeatResult(*(np.zeros(1) for _ in range(5)))
    assert five.system_rhs is None and five.ambient_load is None


def test_thermal_flux_robin_independent_assembled_operator(monkeypatch):
    import galerkin.thermal as production
    observed=[];original=production.solve_dirichlet
    def observe(matrix,rhs,bc):
        observed.append((matrix.copy(),rhs.copy()))
        return original(matrix,rhs,bc)
    monkeypatch.setattr(production,'solve_dirichlet',observe)
    m=rectangle_mesh(1,1,3,3);bc={int(i):330. for i in m.boundary['left']}
    source=lambda p:6.+2*p[:,0]-3*p[:,1]**2
    flux={'right':lambda p,n:3.-8*p[:,1]+2*p[:,1]**2}
    conv={'right':(lambda p,n:2+3*p[:,1]+p[:,1]**2,lambda p,n:300-7*p[:,1]+5*p[:,1]**2)}
    r=solve(m,bc,source,flux,conv)
    K,H,f,B,G=audit(m,r,bc,source,flux,conv)
    matrix,rhs=observed[0];difference=(matrix-K-H).toarray()
    assert np.max(abs(difference))<=1e-10*max(np.max(abs((K+H).data)),1.)
    _,_,_,_,_,shifted=independent_system(m,K0,source,flux,conv,normal,reference=330.)
    np.testing.assert_allclose(rhs,f+shifted-G,rtol=1e-10,atol=1e-10*K0*40)


def test_thermal_flux_robin_independent_tiny_positive_anchor():
    m=rectangle_mesh(1,1,2,2)
    r=solve(m,{},convection={'right':(1e-12,300.)})
    np.testing.assert_array_equal(r.temperature,np.full(m.num_nodes,300.))
    np.testing.assert_array_equal(r.heat_flux,0.)
