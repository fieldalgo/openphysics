# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent rational polynomial and closed Fourier physical moments."""
from fractions import Fraction as F
import math

import numpy as np
import pytest

import galerkin._laplace_corner_harmonic_moments as field

POWERS=np.array([.5001,.6,2/3,.875,1.])
STARTS=np.array([[.25,.125],[.5,.25],[.125,.5],[.625,.5],[.375,.25]])
DIRECTIONS=np.array([[.0625,.03125],[-.03125,.0625],[.0625,-.03125],[-.0625,-.03125],[.03125,.0625]])


def moments(r,s):
    expected=[]
    for start,direction,power in zip(STARTS,DIRECTIONS,POWERS):
        coefficient=[F(0)]*(r+s+1)
        for i in range(r+1):
            for j in range(s+1):
                coefficient[i+j]+=math.comb(r,i)*math.comb(s,j)*F(float(start[0]))**(r-i)*F(float(direction[0]))**i*F(float(start[1]))**(s-j)*F(float(direction[1]))**j
        p=F(float(power))
        constant=sum(c*p/(p+k) for k,c in enumerate(coefficient))
        linear=sum(c*p*k/((p+k)*(2*p+k)) for k,c in enumerate(coefficient))
        expected.extend([float(constant),math.sqrt(3)*float(linear)])
    return np.array(expected)


@pytest.mark.parametrize('degree',[8,20,24])
@pytest.mark.parametrize('r,s',[(r,s) for r in range(4) for s in range(4-r)])
def test_exact_rational_monomials_with_physical_zero_mass_mode(degree,r,s):
    grid,projection=field._projection(STARTS,DIRECTIONS,POWERS,degree)
    actual=projection@(grid[:,0]**r*grid[:,1]**s);expected=moments(r,s)
    assert np.all(abs(actual-expected)<=1e-12*np.maximum(1,abs(expected)))
    if r+s==0:
        np.testing.assert_allclose(actual[::2],1,rtol=1e-12,atol=0)
        np.testing.assert_allclose(actual[1::2],0,rtol=0,atol=1e-12)


@pytest.mark.parametrize('degree',[20,24])
@pytest.mark.parametrize('kind',['constant','affine','quadratic','mixed'])
def test_centered_smooth_bilinear_kernel_uses_analytic_masses(degree,kind):
    grid,projection=field._projection(STARTS,DIRECTIONS,POWERS,degree)
    before=projection.tobytes()
    def features(x):
        return np.column_stack((np.ones(len(x)),x[:,0],x[:,1],x[:,0]**2,x[:,0]*x[:,1],x[:,1]**2))
    center=np.array([.4,.45]);values=features(grid);at_center=features(center[None])[0]
    coefficients=np.zeros((6,6));coefficients[0,0]=2
    if kind=='affine':coefficients[1,0],coefficients[0,2]=.25,-.125
    if kind=='quadratic':coefficients+=np.diag([0.,.5,-.25,.125,.0625,-.03125])
    if kind=='mixed':coefficients[1,4],coefficients[3,2],coefficients[5,3]=.5,-.25,.125
    result=field._centered_projection(projection,values@coefficients@values.T,
        values@coefficients@at_center,at_center@coefficients@values.T,
        float(at_center@coefficients@at_center))
    exact=np.column_stack([moments(r,s) for r,s in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))])
    expected=exact@coefficients@exact.T
    assert np.all(abs(result-expected)<=1e-12*np.maximum(1,abs(expected)))
    if kind=='constant':assert np.array_equal(result,expected)
    assert projection.tobytes()==before


@pytest.mark.parametrize('order',[16,32])
def test_horizontal_uniform_panel_matches_closed_cosine_moments(order):
    starts=np.array([[.25,.125]]);directions=np.array([[.125,0.]])
    width,height,modes=1.,.5,8;k=np.arange(1,modes+1)*np.pi/width
    span=k*directions[0,0];center=k*(starts[0,0]+directions[0,0]/2)
    constant=np.cos(center)*np.sinc(span/(2*np.pi))
    linear=2*math.sqrt(3)*np.sin(center)*(np.cos(span/2)/span-2*np.sin(span/2)/span**2)
    y=starts[0,1]
    amplitudes=np.array([2/width*np.exp(-k*y)*(1-np.exp(-2*k*(height-y)))/(1-np.exp(-2*k*height)),
        2/width*np.exp(-k*(height-y))*(1-np.exp(-2*k*y))/(1-np.exp(-2*k*height))])
    expected=amplitudes[:,:,None]*np.stack((constant,linear),axis=-1)[None]
    actual=field._ground_integrated(starts,directions,np.ones(1),width,height,modes,order)
    np.testing.assert_allclose(actual[:,1:],expected,rtol=0,atol=1e-12)
    np.testing.assert_array_equal(actual[:,0,1],np.zeros(2))


@pytest.mark.parametrize('order',[16,32])
def test_total_plane_charge_uses_exact_physical_mass_for_every_power(order):
    value=field._ground_integrated(STARTS,DIRECTIONS,POWERS,1.,1.,8,order)
    np.testing.assert_allclose(value[:,0,:].sum(axis=0),np.tile([1.,0.],len(POWERS)),rtol=0,atol=1e-12)
    assert np.any(value[0,0,1::2]!=0)
    np.testing.assert_array_equal(value[0,0,1::2],-value[1,0,1::2])


@pytest.mark.parametrize('fault',['mass','nonfinite'])
def test_projection_refuses_broken_physical_measure(monkeypatch,fault):
    original=field._harmonic_rule
    def changed(p,degree):
        x,w=original(p,degree);return x,w*(1.000001 if fault=='mass' else np.nan)
    monkeypatch.setattr(field,'_harmonic_rule',changed)
    with pytest.raises(ValueError,match='mass'):field._projection(STARTS,DIRECTIONS,POWERS,24)


def test_nonfinite_centered_kernel_is_not_returned():
    with pytest.raises(ValueError,match='nonfinite'):
        field._centered_projection(np.eye(2),np.full((2,2),np.nan),np.ones(2),np.ones(2),1.)


@pytest.mark.parametrize('order',[16,32])
@pytest.mark.parametrize('case',['near-bottom','near-top','thin-height'])
def test_small_exponential_arguments_match_closed_hyperbolic_moments(order,case,record_property):
    import json
    from scipy.special import spherical_jn
    width=1.;height=2.**-20 if case=='thin-height' else .5
    y=height*.375 if case=='thin-height' else 2.**-40 if case=='near-bottom' else height-2.**-40
    starts=np.array([[.234375,y]]);directions=np.array([[.078125,0.]])
    modes=8;k=np.arange(1,modes+1)*np.pi/width
    half_span=k*directions[0,0]/2;center=k*(starts[0,0]+directions[0,0]/2)
    spatial=np.stack((np.cos(center)*np.sinc(half_span/np.pi),
                      -np.sqrt(3)*np.sin(center)*spherical_jn(1,half_span)),axis=-1)
    amplitude=np.array([2/width*np.sinh(k*(height-y))/np.sinh(k*height),
                        2/width*np.sinh(k*y)/np.sinh(k*height)])
    expected=amplitude[:,:,None]*spatial[None]
    actual=field._ground_integrated(starts,directions,np.ones(1),width,height,modes,order)[:,1:]
    assert np.all(expected!=0)
    np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=0)
    record_property('near_plane_harmonic_moments',json.dumps(dict(case=case,order=order,
        actual=actual.tolist(),closed=expected.tolist(),maximum_relative=float(np.max(abs(actual-expected)/abs(expected)))),sort_keys=True))
