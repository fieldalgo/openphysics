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
