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


def fourier_gram(a, b, charges, w, h, modes, order):
    """The plane Gram as a cosine (Parseval) sum: the independent reference for the physical-space one."""
    coeff = ground_coefficients(a, b, charges, w, h, modes=modes, order=order)
    return w * (np.einsum('bi,bj->bij', coeff[:, 0], coeff[:, 0]) + .5 * np.einsum('bni,bnj->bij', coeff[:, 1:], coeff[:, 1:]))


@pytest.mark.parametrize('w,h', [(1., 1.), (1., .25), (.5, 1.)])
def test_physical_space_ground_gram_equals_the_cosine_parseval_sum(w, h):
    from galerkin.laplace_two_ground import _ground_gram as ground_gram
    rng = np.random.default_rng(5)
    a = np.column_stack((rng.uniform(.25, .7, 6) * w, rng.uniform(.3, .7, 6) * h))
    b = a + np.column_stack((rng.uniform(.02, .06, 6) * w, rng.uniform(-.05, .05, 6) * h))
    charges = rng.normal(size=(6, 3))
    actual = ground_gram(a, b, charges, w, h, order=16)
    expected = fourier_gram(a, b, charges, w, h, 4096, 16)
    np.testing.assert_allclose(actual, actual.swapaxes(1, 2), rtol=1e-13, atol=0)
    assert np.max(abs(actual - expected)) <= 1e-12 * np.max(abs(expected))


def test_ground_intervals_follow_the_distance_to_the_nearest_singularity():
    from galerkin.laplace_two_ground import _ground_intervals as intervals, GROUND_INTERVAL_FRACTION as fraction
    xs = np.array([.3, .31, .7]); distance = np.array([.02, .05, .01])
    edges = intervals(xs, distance, 1.)
    assert edges[0] == 0 and edges[-1] == 1 and np.all(np.diff(edges) > 0)
    for left, right in zip(edges[:-1], edges[1:]):
        x = np.linspace(left, right, 7)
        r = np.min(np.hypot(x[:, None] - xs, distance), axis=1)
        assert right - left <= fraction / (1 - fraction) * r.min() * (1 + 1e-12)
    # Fine only near the sources: the widest interval is far wider than the narrowest.
    assert np.max(np.diff(edges)) > 10 * np.min(np.diff(edges))
