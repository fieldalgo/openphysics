# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pytest
from scipy.integrate import quad
from galerkin._laplace_panels import exact_double_log, mean_log_pairs, half_matrix
from scipy.special import xlogy


def _mean_log(targets, a, b):
    # Independent one-dimensional primitive, integrated adaptively over target.
    length = np.linalg.norm(b-a, axis=1)
    direction = (b-a)/length[:, None]
    offset = a[None]-targets[:, None]
    u = np.sum(offset*direction[None], axis=-1)
    h = abs(offset[..., 0]*direction[None, :, 1]-offset[..., 1]*direction[None, :, 0])
    def primitive(x):
        return .5*xlogy(x, x*x+h*h)-x+h*np.arctan2(x, h)
    return (primitive(u+length[None])-primitive(u))/length[None]



CASES=[((0.,.3),(1.,.3),(0.,.3),(1.,.3)),
       ((0.,0.),(1.,0.),(1.,0.),(1.2,0.)),
       ((0.,0.),(1.,0.),(0.,.1),(1.,.1)),
       ((0.,0.),(1.,0.),(1.,0.),(1.,.5)),
       ((.1,.2),(.8,.4),(1.,1.),(.3,1.5)),
       ((-1.,-.2),(0.,-.1),(0.,.8),(1.,.9)),
       ((0.,0.),(1.,0.),(1.,0.),(1.,.0001)),
       ((0.,0.),(1.,0.),(0.,1e-6),(1.,1e-6)),
       ((.4855494335551216,.020833333333333332),(.48655522225623693,.020833333333333332),(.493570697792801,.022291660834453116),(.493570697792801,.022291666666666664)),
       ((.493570697792801,.022291660834453116),(.493570697792801,.022291666666666664),(.4855494335551216,.020833333333333332),(.48655522225623693,.020833333333333332)),
       ((0.,0.),(1.,0.),(1.,0.),(1.,1e-8))]


@pytest.mark.parametrize('case',CASES)
def test_complex_second_primitive_against_independent_adaptive_integral(case):
    a,b,c,d=map(np.array,case)
    if np.linalg.norm(b-a)>np.linalg.norm(d-c):a,b,c,d=c,d,a,b
    expected=quad(lambda u:_mean_log((a+u*(b-a))[None],c[None],d[None])[0,0],0.,1.,epsabs=1e-11,epsrel=1e-11)[0]
    observed=exact_double_log(*(np.asarray(p)[None] for p in case))[0]
    assert abs(observed-expected)<=1e-10*max(1.,abs(expected))


@pytest.mark.parametrize('scale',[.001,1.,1000.])
def test_double_integral_rotation_scale_and_exchange(scale):
    a,b,c,d=map(np.array,CASES[4]);rotation=np.array([[np.cos(.71),-np.sin(.71)],[np.sin(.71),np.cos(.71)]])
    base=exact_double_log(a[None],b[None],c[None],d[None])[0]
    aa,bb,cc,dd=[scale*p@rotation.T for p in [a,b,c,d]]
    value=exact_double_log(aa[None],bb[None],cc[None],dd[None])[0]
    assert value==pytest.approx(base+np.log(scale),rel=1e-10,abs=1e-10)
    swapped=exact_double_log(cc[None],dd[None],aa[None],bb[None])[0]
    assert swapped==pytest.approx(value,rel=1e-10,abs=1e-10)


def test_halfspace_energy_matrix_symmetry_and_positive_definiteness():
    a=np.array([[.1,.2],[.2,.2],[.4,.3],[.5,.3]])
    b=np.array([[.2,.2],[.3,.2],[.5,.3],[.6,.3]])
    G=half_matrix(a,b);assert np.max(abs(G-G.T))/np.max(abs(G))<1e-10
    np.linalg.cholesky((G+G.T)/2)
