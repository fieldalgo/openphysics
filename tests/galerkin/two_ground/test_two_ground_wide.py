# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest
from galerkin.laplace_two_ground import _point_green as point_green, _admit as _admit_wide_dual_ground
from galerkin.laplace_boundary import solve_grounded_rectangle as solve

@pytest.mark.parametrize('aspect',[4.,8.,16.])
def test_wide_green_independent_lateral_series(aspect):
    w=aspect;h=1.;x=w/2-.2;y=.3;sx=w/2+.2;sy=.7;n=np.arange(1,8193);k=n*np.pi/w
    vertical=np.exp(-k*abs(y-sy))*(-np.expm1(-2*k*y))*(-np.expm1(-2*k*(h-sy)))/(2*k*(-np.expm1(-2*k*h)))
    expected=2*np.pi*(y*(h-sy)/(w*h)+2/w*np.sum(np.cos(k*x)*np.cos(k*sx)*vertical))
    actual=point_green([[x,y]],[[sx,sy]],w,h)[0,0]
    assert actual==pytest.approx(expected,rel=1e-12,abs=1e-12)
    assert actual==pytest.approx(point_green([[sx,sy]],[[x,y]],w,h)[0,0],rel=1e-12,abs=1e-12)
    np.testing.assert_allclose(point_green([[x,0.],[x,h]],[[sx,sy]],w,h),0.,rtol=0,atol=1e-12)
    for wall in (0.,w):
        values=point_green([[wall-1e-4,y],[wall+1e-4,y]],[[sx,sy]],w,h)
        assert values[0,0]==pytest.approx(values[1,0],rel=1e-12,abs=1e-12)

@pytest.mark.parametrize('aspect',[8.,16.])
def test_original_narrow_contract_is_still_rejected(aspect):
    p=[np.array([[aspect/2-.2,.45],[aspect/2+.2,.45],[aspect/2+.2,.55],[aspect/2-.2,.55]])]
    with pytest.raises(ValueError,match='width/height'):solve(p,width=aspect,height=1.,panels_per_edge=16)
    assert len(_admit_wide_dual_ground(p,aspect,1.,16)[0])==1

@pytest.mark.parametrize('aspect',[.2,16.00001])
def test_new_bound_is_explicit(aspect):
    with pytest.raises(ValueError,match='width/height'):_admit_wide_dual_ground([np.ones((4,2))],aspect,1.,16)
