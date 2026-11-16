# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact rational checks for bounded binary64 product residuals."""
from fractions import Fraction
import numpy as np
import pytest
from galerkin.dense_residual import bounded_dense_residual as residual


def exact(a,x,b):
    return np.array([[float(Fraction(float(b[i,j]))-sum(
        (Fraction(float(a[i,k]))*Fraction(float(x[k,j])) for k in range(a.shape[1])),
        Fraction(0))) for j in range(x.shape[1])] for i in range(a.shape[0])])


@pytest.mark.parametrize('a,x,answer', [([[1.,1.,1.]],[[2.**53],[1.],[-2.**53]],-1.),
    ([[1+2.**-27,-1.]],[[1-2.**-27],[1.]],2.**-54)])
def test_lost_sum_and_product_bits_are_recovered(a,x,answer,record_property):
    a,x=np.array(a),np.array(x);b=np.zeros((1,1))
    assert (b-a@x)[0,0]==0.
    assert residual(a,x,b)[0,0]==answer
    assert np.array_equal(residual(a,x,b),exact(a,x,b))
    record_property('exact_cancellation',f'{answer:.17g}')


@pytest.mark.parametrize('mode',['moderate','wide','cancellation'])
@pytest.mark.parametrize('seed',range(8))
def test_exact_binary_products_and_column_permutations(mode,seed):
    rng=np.random.default_rng(20261116+seed)
    def data(shape):
        exponents=rng.integers(-399,400,shape) if mode=='wide' else rng.integers(-10,11,shape)
        return np.ldexp(rng.uniform(.5,1,shape)*rng.choice([-1.,1.],shape),exponents)
    a,x,b=data((7,31)),data((31,3)),data((7,3))
    if mode=='cancellation':a[:,:15]=a[:,15:30];x[:15]=-x[15:30]
    wanted=exact(a,x,b);assert np.array_equal(residual(a,x,b),wanted)
    permutation=rng.permutation(a.shape[1]);assert np.array_equal(residual(a[:,permutation],x[permutation],b),wanted)


@pytest.mark.parametrize('a,x,b', [
    (1.,[[1.]],[[0.]]),([1.],[[1.]],[[0.]]),
    (np.empty((0,1)),[[1.]],np.empty((0,1))),
    (np.empty((1,0)),np.empty((0,1)),[[0.]]),
    ([[1.]],[1.],[[0.]]),([[1.]],[[[1.]]],[[0.]]),
    ([[1.]],np.empty((1,0)),np.empty((1,0))),
    ([[1.]],np.zeros((1,17)),np.zeros((1,17))),
    ([[1.]],[[1.],[2.]],[[0.]]),([[1.]],[[1.]],[0.]),
    (np.zeros((8193,1)),[[1.]],np.zeros((8193,1))),
    (np.zeros((1,8193)),np.zeros((8193,1)),[[0.]]),
])
def test_incompatible_or_unbounded_shapes_are_refused(a,x,b):
    with pytest.raises(ValueError):residual(a,x,b)


@pytest.mark.parametrize('position',range(3))
@pytest.mark.parametrize('value',[np.inf,np.nan,1j])
def test_nonfinite_and_complex_inputs_are_refused(position,value):
    values=[[[1.]],[[1.]],[[0.]]];values[position]=[[value]]
    with pytest.raises(ValueError):residual(*values)


@pytest.mark.parametrize('position',[0,1])
@pytest.mark.parametrize('value',[2.**-401,2.**401,np.nextafter(2.**-400,0),np.nextafter(2.**400,np.inf)])
def test_product_magnitude_bounds_are_strict(position,value):
    values=[[[1.]],[[1.]],[[0.]]];values[position]=[[value]]
    with pytest.raises(ValueError):residual(*values)


def test_inclusive_magnitude_and_rhs_bounds_match_exact_products():
    a=np.array([[2.**-400,2.**400],[-2.**-400,-2.**400]])
    x=np.array([[2.**-400,2.**400],[2.**400,-2.**-400]])
    b=np.array([[2.**900,-2.**900],[0.,np.nextafter(0.,1.)]])
    assert np.array_equal(residual(a,x,b),exact(a,x,b))
    with pytest.raises(ValueError):residual([[1.]],[[1.]],[[np.nextafter(2.**900,np.inf)]])


def test_maximum_columns_and_right_sides_and_input_nonmutation():
    a=np.zeros((1,8192));a[0,[0,4095,8191]]=[1.,1.,1.]
    x=np.zeros((8192,16));x[[0,4095,8191]]=[[2.**53]*16,[1.]*16,[-2.**53]*16]
    b=np.zeros((1,16));before=[v.copy() for v in (a,x,b)]
    answer=residual(a,x,b);assert np.array_equal(answer,-np.ones((1,16)))
    for v,old in zip((a,x,b),before):assert np.array_equal(v,old)
    answer[:]=0;assert np.array_equal(residual(a,x,b),-np.ones((1,16)))
