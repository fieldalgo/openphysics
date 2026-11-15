# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent binary64 length checks for the planar small-angle lattice."""
from decimal import Decimal, localcontext
import math

import numpy as np
import pytest
from meshine import refine


def decimal_length(vector):
    with localcontext() as context:
        context.prec=80
        x,y=map(lambda x:Decimal.from_float(float(x)),vector)
        return (x*x+y*y).sqrt()


@pytest.mark.parametrize('power',[-400,-40,0,40,400])
@pytest.mark.parametrize('swap',[False,True])
@pytest.mark.parametrize('signs',[(1,1),(1,-1),(-1,1),(-1,-1)])
def test_retained_length_matches_independent_decimal_rounding(power,swap,signs):
    vector=[-3.8000000000000056e-5,-2.5000000000000716e-5]
    if swap:vector.reverse()
    vector=np.array([math.ldexp(sign*x,power) for sign,x in zip(signs,vector)])
    expected=float(decimal_length(vector))
    assert refine._length2(vector).hex()==expected.hex()


def test_treated_apex_and_lattice_lengths_do_not_use_blas_dot(monkeypatch):
    points=np.array([[0.,0.],[-3.8000000000000056e-5,-2.5000000000000716e-5],[-2e-5,-1.5e-5]])
    corners={0:[refine._Corner(0.,.1,1,2,True)],1:[refine._Corner(0.,.1,0,2,True)]}
    def forbidden(*a,**k):pytest.fail('scalar planar lattice reached numpy.linalg.norm')
    monkeypatch.setattr(np.linalg,'norm',forbidden)
    tags,units=refine._treated_apices(points,corners,math.radians(28.))
    assert set(units)=={0,1}
    for vertex,others in [(0,[1,2]),(1,[0,2])]:
        assert units[vertex]==min(float(decimal_length(points[x]-points[vertex])) for x in others)
        for other in others:assert tags[tuple(sorted((vertex,other)))][vertex]==other
    point=refine._lattice_point(points[0],points[1],units[0])
    distance=decimal_length(point-points[0]);length=decimal_length(points[1]-points[0])
    assert length/4<=distance<length/2
    assert point[0]/points[1,0]==point[1]/points[1,1]
