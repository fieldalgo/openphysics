# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest
from galerkin.laplace_two_ground import _ground_coefficients as ground_coefficients, _factors as factors
from galerkin.laplace_two_ground import _point_green as point_green, _solve as solve

@pytest.mark.parametrize('source',[(.35,.4),(.12,.8),(.8,.25)])
def test_point_ground_flux_against_independent_green_normal_difference(source):
    a=np.array([source]);charge=np.ones((1,1));w=1.;height=1.
    coeff=ground_coefficients(a,a,charge,w,height,modes=256,order=12)
    x=np.array([.08,.31,.61,.94]);modes=np.arange(257)
    values=np.cos(x[:,None]*modes*np.pi)@coeff[:,:,0].T
    step=1e-5
    for boundary in (0,1):
        y=0. if boundary==0 else height
        sign=1 if boundary==0 else -1
        at=lambda distance:point_green(np.column_stack((x,np.full(len(x),y+sign*distance))),a,w,height)[:,0]
        flux=-(-3*at(0)+4*at(step)-at(2*step))/(2*step*2*np.pi)
        np.testing.assert_allclose(values[:,boundary],flux,rtol=2e-8,atol=1e-9)
    np.testing.assert_allclose(coeff[:,0,0],[-(1-source[1]),-source[1]],rtol=0,atol=1e-15)

@pytest.mark.parametrize('operation',['scale','mirror-x','mirror-y','permutation'])
def test_integrated_boundary_current_invariants(operation):
    polygons=[np.array([[.00345,.000975],[.00385,.000975],[.00385,.001025],[.00345,.001025]]),np.array([[.00415,.000975],[.00455,.000975],[.00455,.001025],[.00415,.001025]])]
    w=.008;h=.002;before=factors(solve(polygons,width=w,height=h,panels_per_edge=16),w,h)
    if operation=='scale':polygons=[p*2 for p in polygons];w*=2;h*=2
    if operation=='mirror-x':polygons=[np.column_stack((w-p[:,0],p[:,1])) for p in polygons]
    if operation=='mirror-y':polygons=[np.column_stack((p[:,0],h-p[:,1])) for p in polygons]
    if operation=='permutation':polygons=polygons[::-1]
    after=factors(solve(polygons,width=w,height=h,panels_per_edge=16),w,h)
    q=after['parts'];ground=after['ground_parts'];integrated=after['current_integrals']
    if operation=='scale':q=q*2;ground=ground*2
    if operation=='permutation':q=q[[1,0,2],::-1,::-1];ground=ground[:,::-1,::-1];integrated=integrated[[1,0,2],::-1]
    if operation=='mirror-y':ground=ground[::-1]
    np.testing.assert_allclose(q,before['parts'],rtol=1e-10,atol=0)
    np.testing.assert_allclose(ground,before['ground_parts'],rtol=1e-10,atol=0)
    np.testing.assert_allclose(integrated,np.vstack((np.eye(2),-np.ones(2))),rtol=0,atol=1e-10)
