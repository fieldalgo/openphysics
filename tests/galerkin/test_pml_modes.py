# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Outgoing slab poles, convergence and PML stability; lengths in micrometres."""
import pytest
import numpy as np
from scipy.optimize import root
from galerkin.mesh import rectangle_mesh
from galerkin.waveguide import solve_modes
from galerkin.mode_coordinates import mode_coordinates, solve_scalar_coordinates

K0 = 2*np.pi/1.55


def outgoing_root(pol='TE'):
    eps = np.array([1.444**2, 3.48**2, 1.444**2, 3.48**2])
    def residual(z):
        n = complex(*z)
        q = np.sqrt((K0**2*(eps-n*n)).astype(complex))
        # Evanescent left exterior decays; propagating substrate is outgoing.
        if q[0].imag > 0:
            q[0] = -q[0]
        if q[-1].real < 0:
            q[-1] = -q[-1]
        weight = eps if pol == 'TM' else np.ones(4)
        state = np.array([1., 1j*q[0]/weight[0]])
        for j, d in [(1, .22), (2, .25)]:
            c, s = np.cos(q[j]*d), np.sin(q[j]*d)
            state = np.array([[c, weight[j]*s/q[j]], [-q[j]*s/weight[j], c]])@state
        r = state[1]+1j*q[-1]/weight[-1]*state[0]
        return [r.real, r.imag]
    r = root(residual, [2.85 if pol == 'TE' else 2.0, -.01], tol=1e-11)
    if not r.success or np.linalg.norm(residual(r.x)) > 1e-8:
        raise RuntimeError(str(r))
    return complex(*r.x)


def slab_mesh(step, thickness=1., pad=1.):
    breaks = [-pad-thickness, -pad, 0, .22, .47, .47+pad, .47+pad+thickness]
    x = np.concatenate([np.linspace(a,b,int(np.ceil((b-a)/step))+1)[:-1] for a,b in zip(breaks[:-1],breaks[1:])]+[[breaks[-1]]])
    mesh = rectangle_mesh(len(x)-1, .1, len(x)-1, max(2, int(np.ceil(.1/step))))
    mesh.nodes[:,0] = x[mesh.nodes[:,0].astype(int)]
    centers = mesh.nodes[mesh.triangles,0].mean(axis=1)
    eps = np.where(((centers>0)&(centers<.22))|(centers>.47), 3.48**2, 1.444**2)
    return mesh, eps


def measure(step, pol='TE', vector=False, thickness=1., strength=3., pad=1.):
    mesh, eps = slab_mesh(step, thickness, pad)
    coords = mode_coordinates(mesh, thickness=dict(left=thickness,right=thickness),strength=strength)
    expected = outgoing_root(pol)
    if vector:
        sides = ['left','right','top','bottom'] if pol=='TE' else ['left','right']
        fixed = np.unique(np.concatenate([mesh.boundary[s] for s in sides]))
        n, *_ = solve_modes(mesh, eps, K0, expected.real, num_modes=6, pec_nodes=fixed, coordinate_factors=coords.factors)
    else:
        fixed = np.r_[mesh.boundary['left'],mesh.boundary['right']]
        n, _ = solve_scalar_coordinates(mesh,eps,K0,expected.real,coords.factors,fixed_nodes=fixed)
    candidate = n[np.argmin(abs(n-expected))]
    return dict(step=step,pol=pol,vector=vector,thickness=thickness,strength=strength,pad=pad,
                nodes=mesh.num_nodes,expected=[expected.real,expected.imag],neff=[candidate.real,candidate.imag],error=abs(candidate-expected),imag_relative_error=abs((candidate.imag-expected.imag)/expected.imag))



@pytest.mark.parametrize('pol,vector',[('TE',False),('TE',True),('TM',True)])
def test_outgoing_slab_convergence(pol,vector):
    results=[measure(h,pol,vector) for h in (.04,.02,.01)]
    errors=[r['error'] for r in results]
    assert errors[0]>errors[1]>errors[2]
    assert errors[-1]<2e-3
    assert np.log2(errors[-2]/errors[-1])>1.5
    assert results[-1]['imag_relative_error']<.02


@pytest.mark.parametrize('pol,vector',[('TE',False),('TE',True),('TM',True)])
def test_pml_strength_thickness_and_window_stability(pol,vector):
    base=complex(*measure(.02,pol,vector)['neff'])
    for settings in [dict(thickness=.75),dict(thickness=1.5),dict(strength=2.),dict(strength=6.),dict(pad=2.)]:
        value=complex(*measure(.02,pol,vector,**settings)['neff'])
        assert abs(value-base)<5e-4
        assert abs((value.imag-base.imag)/base.imag)<.02


def test_identity_transform_preserves_vector_pencil():
    from galerkin.waveguide import assemble_mode_system
    mesh=rectangle_mesh(2.,1.,8,4)
    eps=np.full(mesh.num_triangles,2.25)
    a,b,_=assemble_mode_system(mesh,eps,K0)
    aa,bb,_=assemble_mode_system(mesh,eps,K0,coordinate_factors=np.ones((mesh.num_triangles,3)))
    np.testing.assert_allclose(aa.toarray(),a.toarray(),rtol=1e-14,atol=1e-13)
    np.testing.assert_allclose(bb.toarray(),b.toarray(),rtol=1e-14,atol=1e-13)

def cylindrical_root(radius=2., pol='TE'):
    # Special functions evaluate the independent analytic matching equation.
    import os
    if os.environ.get('OPENPHYSICS_REQUIRE_CROSSCHECK') == '1':
        import mpmath as mp
    else:
        mp = pytest.importorskip('mpmath')
    with mp.workdps(40):
        def residual(n):
            nu = K0*radius*n
            def col(kind, index, r):
                f = {'J':mp.besselj,'Y':mp.bessely,'H':mp.hankel2}[kind]
                arg = K0*index*r
                v = f(nu,arg)
                dv = K0*index*(f(nu-1,arg)-f(nu+1,arg))/2
                return mp.matrix([v,dv/(index**2 if pol=='TM' else 1)])
            inner=col('J',1.444,radius)
            a,b=col('J',3.48,radius),col('Y',3.48,radius)
            coeff=mp.lu_solve(mp.matrix([[a[0],b[0]],[a[1],b[1]]]),inner/inner[0])
            a,b=col('J',3.48,radius+.22),col('Y',3.48,radius+.22)
            state=coeff[0]*a+coeff[1]*b
            outer=col('H',1.444,radius+.22)
            return state[1]-outer[1]/outer[0]*state[0]
        n=mp.findroot(residual,(2.99-.001j,3.0-.002j) if pol=='TE' else (2.15-.01j,2.16-.02j),tol=mp.mpf('1e-30'),maxsteps=50)
        return complex(n)


def measure_bend(step, pol='TE', vector=False, radius=2.):
    # Preserve a positive inner radius; PML starts outside the evanescent tail
    # on the inner side and beyond the outer radiation turning point.
    inner=min(1.2,radius*.6); thick=min(.6,radius*.3)
    outer=max(3.,radius*1.2)
    breaks=[-inner-thick,-inner,0,.22,.22+outer,.22+outer+1.]
    x=np.concatenate([np.linspace(a,b,int(np.ceil((b-a)/step))+1)[:-1] for a,b in zip(breaks[:-1],breaks[1:])]+[[breaks[-1]]])
    mesh=rectangle_mesh(len(x)-1,.05,len(x)-1,max(2,int(np.ceil(.05/step))))
    mesh.nodes[:,0]=x[mesh.nodes[:,0].astype(int)]
    cent=mesh.nodes[mesh.triangles,0].mean(axis=1)
    eps=np.where((cent>0)&(cent<.22),3.48**2,1.444**2)
    c=mode_coordinates(mesh,thickness=dict(left=thick,right=1.),bend_radius=radius)
    expected=cylindrical_root(radius,pol)
    sides=['left','right','top','bottom'] if vector and pol=='TE' else ['left','right']
    fixed=np.unique(np.concatenate([mesh.boundary[s] for s in sides]))
    if vector:
        n,*_=solve_modes(mesh,eps,K0,expected.real,num_modes=6,pec_nodes=fixed,coordinate_factors=c.factors)
    else:
        n,_=solve_scalar_coordinates(mesh,eps,K0,expected.real,c.factors,fixed_nodes=fixed)
    value=n[np.argmin(abs(n-expected))]
    return dict(step=step,radius=radius,pol=pol,vector=vector,expected=[expected.real,expected.imag],neff=[value.real,value.imag],error=abs(value-expected),imag_relative_error=abs((value.imag-expected.imag)/expected.imag))



@pytest.mark.parametrize('pol,vector',[('TE',False),('TE',True),('TM',True)])
def test_cylindrical_bend_converges_to_bessel_hankel_pole(pol,vector):
    results=[measure_bend(h,pol,vector) for h in (.04,.02,.01)]
    errors=[r['error'] for r in results]
    assert errors[0]>errors[1]>errors[2]
    assert np.log2(errors[-2]/errors[-1])>1.5
    assert errors[-1]<2e-3
    assert results[-1]['imag_relative_error']<.03


@pytest.mark.parametrize('vector',[False,True])
def test_bound_mode_closed_window_and_large_radius_limits(vector):
    mesh,eps=slab_mesh(.02)
    x=mesh.nodes[mesh.triangles,0].mean(axis=1)
    eps=np.where((x>0)&(x<.22),3.48**2,1.444**2)
    target=2.85
    fixed=np.unique(np.concatenate(list(mesh.boundary.values()))) if vector else np.r_[mesh.boundary['left'],mesh.boundary['right']]
    values=[]
    for radius in (None,1e6):
        c=mode_coordinates(mesh,thickness=dict(left=1.,right=1.),bend_radius=radius)
        if vector:
            n,*_=solve_modes(mesh,eps,K0,target,6,pec_nodes=fixed,coordinate_factors=c.factors)
        else:
            n,_=solve_scalar_coordinates(mesh,eps,K0,target,c.factors,fixed_nodes=fixed)
        values.append(n[np.argmin(abs(n-target))])
    if vector:
        n,*_=solve_modes(mesh,eps,K0,target,6,pec_nodes=fixed)
    else:
        n,_=solve_scalar_coordinates(mesh,eps,K0,target,np.ones((mesh.num_triangles,3)),fixed_nodes=fixed)
    closed=n[np.argmin(abs(n-target))]
    assert abs(values[0]-closed)<2e-4
    assert abs(values[1]-values[0])<2e-4
    assert abs(values[0].imag)<1e-9
