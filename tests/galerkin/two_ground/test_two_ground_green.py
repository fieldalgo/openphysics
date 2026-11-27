# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest
from galerkin.laplace_two_ground import _point_green as point_green, kernel


def lateral_series(x,y,sx,sy,w,h):
    low=min(y,sy);high=max(y,sy);n=np.arange(1,513);k=n*np.pi/w
    vertical=np.exp(-k*(high-low))*(-np.expm1(-2*k*low))*(-np.expm1(-2*k*(h-high)))/(2*k*(-np.expm1(-2*k*h)))
    return 2*np.pi*(low*(h-high)/(w*h)+2/w*np.sum(np.cos(k*x)*np.cos(k*sx)*vertical))


@pytest.mark.parametrize('w,h,target,source',[(1.,.4,(.7,.29),(.4,.13)),(.7,1.,(.6,.2),(.2,.7)),(1.,1.,(.1,.2),(.8,.7))])
def test_independent_lateral_eigenseries(w,h,target,source):
    actual=point_green([target],[source],w,h,images=16)[0,0]
    assert actual==pytest.approx(lateral_series(*target,*source,w,h),rel=1e-12,abs=1e-12)


@pytest.mark.parametrize('y',[0.,.4])
def test_both_ground_planes_are_dirichlet(y):
    result=point_green([[.1,y],[.5,y],[.9,y]],[[.4,.13]],1.,.4)
    np.testing.assert_allclose(result,0.,rtol=0,atol=1e-12)


@pytest.mark.parametrize('wall',[0.,1.])
def test_side_neumann_reflection(wall):
    delta=.0001
    values=point_green([[wall-delta,.29],[wall+delta,.29]],[[.4,.13]],1.,.4)
    assert values[0,0]==pytest.approx(values[1,0],rel=1e-12,abs=1e-12)


def test_reciprocity_and_plane_reflection():
    a=np.array([[.2,.1],[.7,.3]]);b=np.array([[.4,.16],[.8,.08]])
    expected=point_green(a,b,1.,.4)
    np.testing.assert_allclose(expected,point_green(b,a,1.,.4).T,rtol=1e-12,atol=1e-12)
    a[:,1]=.4-a[:,1];b[:,1]=.4-b[:,1]
    np.testing.assert_allclose(expected,point_green(a,b,1.,.4),rtol=1e-12,atol=1e-12)


def test_independent_vertical_eigenseries_and_half_space_limit():
    dx=.3;y=.2;sy=.4;h=1.;n=np.arange(1,513)
    reference=2*np.sum(np.sin(n*np.pi*y/h)*np.sin(n*np.pi*sy/h)*np.exp(-n*np.pi*dx/h)/n)
    assert float(kernel._dd(np.array(dx),np.array(y),np.array(sy),h/2))==pytest.approx(reference,rel=1e-12,abs=1e-12)
    half=.5*np.log1p(4*y*sy/(dx*dx+(y-sy)**2))
    errors=[abs(float(kernel._dd(np.array(dx),np.array(y),np.array(sy),height/2))-half) for height in (8.,16.,32.)]
    assert errors[2]<errors[1]<errors[0] and errors[-1]<1e-3


def test_new_admission_keeps_original_dn_contract_unchanged():
    from galerkin.laplace_boundary import _admit
    from galerkin.laplace_two_ground import _admit as _admit_dual_ground
    polygons=[np.array([[.35,.18],[.45,.18],[.45,.22],[.35,.22]]),
              np.array([[.55,.18],[.65,.18],[.65,.22],[.55,.22]])]
    # The one-cluster-extent top clearance is not met: wall-scaled boxes, not a refusal.
    assert _admit(polygons,1.,.4,16)[4] is False
    accepted,unit,w,h=_admit_dual_ground(polygons,1.,.4,16)
    assert len(accepted)==2 and unit==1. and w==1. and h==.4


def full_smooth(targets, sources, width, height, images):
    """The smooth kernel with every image added (the sum before image skipping)."""
    dx = targets[:, None, 0] - sources[None, :, 0]
    yt, ys = targets[:, None, 1], sources[None, :, 1]
    out = kernel.dd_minus_half(dx, yt, ys, height / 2)
    for n in range(-images, images + 1):
        if n:
            out += kernel.dd(dx - 2 * n * width, yt, ys, height / 2)
        out += kernel.dd(targets[:, None, 0] + sources[None, :, 0] - 2 * n * width, yt, ys, height / 2)
    return out


@pytest.mark.parametrize('height', [.05, .4, 1., 4.])
def test_image_bound_is_above_every_sampled_image(height):
    from galerkin.laplace_two_ground import _image_bound
    rng = np.random.default_rng(7)
    for low in (-.3, .02, .2, 1.5, -2.):
        high = low + .25
        dx = rng.uniform(low, high, 400)
        y = rng.uniform(0, height, (2, 400))
        values = abs(kernel.dd(dx, y[0], y[1], height / 2))
        assert np.all(values <= _image_bound(low, high, height))


@pytest.mark.parametrize('width,height,images', [(1., .05, 8), (1., .4, 8), (.25, 1., 20)])
def test_skipped_images_leave_the_smooth_kernel_bit_identical(width, height, images, monkeypatch):
    from galerkin.laplace_two_ground import smooth
    rng = np.random.default_rng(3)
    boxes = [(.1, .2), (.45, .5), (.7, .95)]
    points = [np.column_stack((rng.uniform(*box, 30) * width, rng.uniform(.05, .95, 30) * height)) for box in boxes]
    calls = []
    original = kernel.dd
    monkeypatch.setattr(kernel, 'dd', lambda *args: calls.append(1) or original(*args))
    for targets in points:
        for sources in points:
            assert np.array_equal(smooth(targets, sources, width, height, images),
                                  full_smooth(targets, sources, width, height, images))
    full_calls = 2 * len(points) ** 2 * (2 * images + 1) - len(points) ** 2
    skipped = full_calls - (len(calls) - full_calls)
    # Wide, low rectangles skip the laterally distant images; tall ones keep them.
    assert skipped > (full_calls // 2 if height < .1 else -1)
