# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest
from galerkin.laplace_two_ground import _point_green as point_green, _admit as _admit_wide_dual_ground
from galerkin.laplace_boundary import solve_grounded_rectangle as solve

@pytest.mark.parametrize('aspect',[4.,8.,16.,32.,64.])
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


@pytest.mark.parametrize('aspect',[.2,64.00001])
def test_two_ground_solver_bound_is_explicit(aspect):
    # The solver admits up to 64 (its ground-series and matrix checks still apply);
    # the shared admission default stays 16 for the corner solvers that reuse it.
    with pytest.raises(ValueError,match=r'width/height must lie in \[0.25, 64\]'):
        _admit_wide_dual_ground([np.ones((4,2))],aspect,1.,16,max_aspect=64)


def test_wide_strip_matches_the_narrow_box_and_widest_series_refusal_still_closes():
    from galerkin.laplace_two_ground import solve_two_ground_rectangle as solve2
    h=5e-4;y0=(h-1.75e-5)/2
    p=[np.array([[0.,y0],[2e-4,y0],[2e-4,y0+1.75e-5],[0.,y0+1.75e-5]])]
    c=[]
    for aspect in (16,32,64):
        w=aspect*h;shifted=[q+[w/2-1e-4,0] for q in p]
        c.append(solve2(shifted,width=w,height=h,panels_per_edge=64,ground_modes=512,interpolation_degree=14).capacitance_per_permittivity)
    np.testing.assert_allclose(c[1],c[0],rtol=1e-12,atol=0);np.testing.assert_allclose(c[2],c[0],rtol=1e-12,atol=0)
