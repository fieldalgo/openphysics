# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytic polygon geometry and stable small-panel displacement checks."""
import math
import numpy as np
import pytest
from galerkin.laplace_corner_geometry import prepare_two_ground_corner_panels

W,H=.008,.002
SQUARE=np.array([[.0038,.0008],[.0042,.0008],[.0042,.0012],[.0038,.0012]])
EQUILATERAL=np.array([[.0038,.0008],[.0042,.0008],[.004,.0008+math.sqrt(3)*.0002]])
RIGHT=np.array([[.0038,.0008],[.0042,.0008],[.0038,.0012]])


def prepare(poly=SQUARE,count=32):
    return prepare_two_ground_corner_panels([poly],width=W,height=H,panels_per_edge=count)


@pytest.mark.parametrize('poly,expected', [(SQUARE,[2/3]*4),(EQUILATERAL,[.6]*3),(RIGHT,[2/3,4/7,4/7])])
@pytest.mark.parametrize('count',[16,32,128,512])
def test_analytic_corner_exponents_and_closed_polygon_coverage(poly,expected,count,record_property):
    result=prepare(poly,count);n=count-6
    assert result.panel_count==len(poly)*n
    edges=np.roll(poly,-1,axis=0)-poly;lengths=np.hypot(*edges.T)
    reconstructed_area=0.
    for face in range(len(poly)):
        chosen=result.faces==face
        assert np.count_nonzero(chosen)==n
        powers=result.exponents[chosen]
        assert abs(powers[0]-expected[face])<=1e-14
        assert abs(powers[-1]-expected[(face+1)%len(poly)])<=1e-14
        assert np.array_equal(powers[1:-1],np.ones(n-2))
        assert abs(result.lengths_m[chosen].sum()-lengths[face])<=1e-14*lengths[face]
        start=result.normalized_starts[chosen]*result.length_unit_m
        direction=result.normalized_directions[chosen]*result.length_unit_m
        orientation=np.sign(direction@edges[face])
        reconstructed_area+=np.sum(orientation*(start[:,0]*direction[:,1]-start[:,1]*direction[:,0]))/2
    area=.5*abs(np.sum(poly[:,0]*np.roll(poly[:,1],-1)-poly[:,1]*np.roll(poly[:,0],-1)))
    assert abs(reconstructed_area-area)<=1e-12*area
    _,incidence=np.unique(result.endpoint_ids,return_counts=True)
    assert np.all(incidence==2)
    assert np.unique(np.sort(result.endpoint_ids,axis=1),axis=0).shape[0]==result.panel_count
    record_property('analytic_geometry',f'{len(poly)}:{count}:{result.panel_count}:{reconstructed_area:.17g}')


@pytest.mark.parametrize('poly',[SQUARE,EQUILATERAL,RIGHT])
@pytest.mark.parametrize('count',[16,128,512])
def test_reflection_preserves_local_displacements(poly,count):
    base=prepare(poly,count)
    reflected=prepare(np.column_stack((W-poly[:,0],poly[:,1])),count)
    n=count-6;indices=np.concatenate([((len(poly)-2-face)%len(poly))*n+np.arange(n-1,-1,-1) for face in range(len(poly))])
    for key in ('normalized_local_starts','normalized_directions'):
        np.testing.assert_allclose(getattr(reflected,key)[indices],getattr(base,key)*[-1,1],rtol=1e-12,atol=0)
    np.testing.assert_allclose(reflected.exponents[indices],base.exponents,rtol=1e-14,atol=0)
    np.testing.assert_allclose(reflected.lengths_m[indices],base.lengths_m,rtol=1e-12,atol=0)


@pytest.mark.parametrize('scale',[1e-6,2.,1e6])
@pytest.mark.parametrize('count',[16,128,512])
def test_physical_length_scaling(scale,count):
    base=prepare(count=count)
    changed=prepare_two_ground_corner_panels([scale*SQUARE],width=scale*W,height=scale*H,panels_per_edge=count)
    for key in ('normalized_anchors','normalized_local_starts','normalized_directions','exponents'):
        np.testing.assert_allclose(getattr(changed,key),getattr(base,key),rtol=1e-12,atol=0)
    np.testing.assert_allclose(changed.lengths_m,scale*base.lengths_m,rtol=1e-12,atol=0)


def test_inputs_and_all_output_arrays_are_isolated_and_immutable():
    poly=SQUARE.copy();result=prepare(poly);expected=result.normalized_starts.copy();poly[:]=0
    assert np.array_equal(result.normalized_starts,expected)
    for key in ('normalized_anchors','normalized_local_starts','normalized_directions','exponents','owners','faces','endpoint_ids','normalized_starts','normalized_ends','lengths_m'):
        array=getattr(result,key)
        with pytest.raises(ValueError):array.flat[0]=0
        with pytest.raises(ValueError):array.flags.writeable=True


def test_multiple_owners_and_clockwise_inputs():
    left=SQUARE+[-.0005,0];right=SQUARE+[.0005,0]
    result=prepare_two_ground_corner_panels([left[::-1],right],width=W,height=H)
    assert np.array_equal(np.bincount(result.owners),[104,104])
    assert np.array_equal(np.unique(result.faces),np.arange(8))
    assert set(result.endpoint_ids[:104].ravel()).isdisjoint(result.endpoint_ids[104:].ravel())


@pytest.mark.parametrize('count',[True,15,17,513,514,32.0,np.nan])
def test_unsupported_subdivision_refused(count):
    with pytest.raises(ValueError):prepare(count=count)


@pytest.mark.parametrize('polys', [[],[SQUARE,SQUARE], [SQUARE[[0,2,1,3]]],
    [np.vstack((SQUARE,SQUARE[0]))], [[[0,0],[1,0]]], [np.full((3,2),np.nan)]])
def test_invalid_boundaries_refused(polys):
    with pytest.raises(ValueError):prepare_two_ground_corner_panels(polys,width=W,height=H)


@pytest.mark.parametrize('dimension,value',[('width',0.),('height',-1.),('width',True),('height',np.inf)])
def test_invalid_rectangle_refused(dimension,value):
    kwargs=dict(width=W,height=H);kwargs[dimension]=value
    with pytest.raises(ValueError):prepare_two_ground_corner_panels([SQUARE],**kwargs)


def test_total_panel_budget_is_checked_before_construction():
    polygons=[SQUARE+[.004+(i-2)*.0006,0] for i in range(5)]
    with pytest.raises(ValueError,match='8192'):
        prepare_two_ground_corner_panels(polygons,width=.016,height=H,panels_per_edge=512)


def test_unresolved_tiny_corner_panels_are_refused():
    small=(SQUARE-[.004,.001])*1e-8+[.004,.001]
    with pytest.raises(ValueError,match='panel length'):
        prepare(small,512)
