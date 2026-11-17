# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent rational partitions and unchanged geometry outside the new private range."""
from fractions import Fraction
import math

import numpy as np
import pytest

from galerkin import _laplace_corner_compact_geometry as compact
from galerkin.laplace_corner_geometry import CornerPanelGeometry, prepare_two_ground_corner_panels
from test_laplace_corner_geometry import W,H,SQUARE,EQUILATERAL,RIGHT

ARRAYS=('normalized_anchors','normalized_local_starts','normalized_directions',
        'exponents','owners','faces','endpoint_ids')


def prepare(poly=SQUARE,count=10):
    return compact._prepare_compact_corner_panels([poly],width=W,height=H,panels_per_edge=count)


@pytest.mark.parametrize('poly,powers',[(SQUARE,[2/3]*4),(EQUILATERAL,[.6]*3),(RIGHT,[2/3,4/7,4/7])])
@pytest.mark.parametrize('count',[10,12,14])
def test_rational_partition_lengths_area_corner_powers_and_endpoint_topology(poly,powers,count,record_property):
    result=prepare(poly,count);indices=[0,*range(4,count-3),count]
    def node(k):return float(Fraction(k**3,k**3+(count-k)**3))
    expected=np.array([[node(a),node(b)] for a,b in zip(indices,indices[1:])])
    area=0.;largest=0.
    for face,(a,b) in enumerate(zip(poly,np.roll(poly,-1,axis=0))):
        selected=np.flatnonzero(result.faces==face);edge=b-a;length=math.hypot(*edge)
        assert len(selected)==count-6
        local=(result.normalized_anchors[selected]*result.length_unit_m-a)+result.normalized_local_starts[selected]*result.length_unit_m
        delta=result.normalized_directions[selected]*result.length_unit_m
        points=np.stack((local,local+delta),axis=1)
        intervals=np.sort(points@edge/(edge@edge),axis=1);intervals=intervals[np.argsort(intervals[:,0])]
        error=float(np.max(abs(intervals-expected)));largest=max(largest,error);assert error<=1e-14
        assert abs(math.fsum(result.lengths_m[selected])/length-1)<=1e-14
        actual=result.exponents[selected]
        assert abs(actual[0]-powers[face])<=1e-14
        assert abs(actual[-1]-powers[(face+1)%len(poly)])<=1e-14
        assert np.array_equal(actual[1:-1],np.ones(count-8))
        starts=result.normalized_starts[selected]*result.length_unit_m
        sign=np.sign(delta@edge)
        area+=float(np.sum(sign*(starts[:,0]*delta[:,1]-starts[:,1]*delta[:,0]))/2)
    expected_area=.5*abs(np.sum(poly[:,0]*np.roll(poly[:,1],-1)-poly[:,1]*np.roll(poly[:,0],-1)))
    assert abs(area/expected_area-1)<=1e-12
    _,incidence=np.unique(result.endpoint_ids,return_counts=True);assert np.all(incidence==2)
    assert np.unique(np.sort(result.endpoint_ids,axis=1),axis=0).shape[0]==result.panel_count
    record_property('compact_rational_geometry',repr((len(poly),count,result.panel_count,largest,area)))


@pytest.mark.parametrize('kind',['quadrilaterals','regular-polygons'])
@pytest.mark.parametrize('count',[16,18,32,48])
def test_old_range_matches_every_public_descriptor_byte_exact(kind,count):
    if kind=='quadrilaterals':
        polygons=[np.array([[x-.02,y],[x+.02,y],[x+.018,y+.01],[x-.018,y+.01]])
                  for x,y in [(.4,.4),(.5,.5),(.6,.6)]]
    else:
        angle=np.arange(21)*2*np.pi/21
        polygons=[np.column_stack((x+.025*np.cos(angle),y+.025*np.sin(angle)))
                  for x,y in [(.4,.4),(.5,.5),(.6,.6)]]
    old=prepare_two_ground_corner_panels(polygons,width=1.,height=1.,panels_per_edge=count)
    new=compact._prepare_compact_corner_panels(polygons,width=1.,height=1.,panels_per_edge=count)
    assert type(new) is type(old) is CornerPanelGeometry
    assert (new.length_unit_m,new.normalized_width,new.normalized_height)==(old.length_unit_m,old.normalized_width,old.normalized_height)
    for key in (*ARRAYS,'normalized_starts','normalized_ends','lengths_m'):
        assert getattr(new,key).tobytes()==getattr(old,key).tobytes()


@pytest.mark.parametrize('count',[10,12,14])
@pytest.mark.parametrize('scale',[2.**-15,2.**15])
def test_exact_binary_length_units_preserve_normalized_descriptors(count,scale):
    base=prepare(count=count)
    changed=compact._prepare_compact_corner_panels([SQUARE*scale],width=W*scale,height=H*scale,panels_per_edge=count)
    for key in ARRAYS:assert np.array_equal(getattr(base,key),getattr(changed,key))
    assert changed.length_unit_m==scale*base.length_unit_m
    assert np.array_equal(changed.lengths_m,scale*base.lengths_m)


@pytest.mark.parametrize('poly',[SQUARE,EQUILATERAL,RIGHT])
@pytest.mark.parametrize('count',[10,12,14])
def test_reflection_and_clockwise_admission_keep_local_geometry(poly,count):
    base=prepare(poly,count);reflected=prepare(np.column_stack((W-poly[:,0],poly[:,1])),count)
    n=count-6;order=np.concatenate([((len(poly)-2-face)%len(poly))*n+np.arange(n-1,-1,-1) for face in range(len(poly))])
    for key in ('normalized_local_starts','normalized_directions'):
        np.testing.assert_allclose(getattr(reflected,key)[order],getattr(base,key)*[-1,1],rtol=1e-12,atol=0)
    np.testing.assert_allclose(reflected.exponents[order],base.exponents,rtol=1e-14,atol=0)
    clockwise=prepare(poly[::-1],count)
    for key in ARRAYS:assert np.array_equal(getattr(clockwise,key),getattr(base,key))


@pytest.mark.parametrize('count',[10,12,14])
def test_geometry_is_private_and_result_storage_cannot_be_modified(count):
    assert compact.__all__==[]
    poly=SQUARE.copy();saved=poly.copy();result=prepare(poly,count)
    assert np.array_equal(poly,saved);starts=result.normalized_starts.copy();poly[:]=0
    assert np.array_equal(result.normalized_starts,starts)
    for key in (*ARRAYS,'normalized_starts','normalized_ends','lengths_m'):
        value=getattr(result,key)
        with pytest.raises(ValueError):value.flags.writeable=True
        with pytest.raises(ValueError):value.flat[0]=0


@pytest.mark.parametrize('count',[8,9,11,True,10.,513,514,np.nan])
def test_unsupported_compact_subdivisions_are_refused(count):
    with pytest.raises((TypeError,ValueError)):prepare(count=count)


INVALID=[[],[SQUARE,SQUARE],[SQUARE[[0,2,1,3]]],[np.vstack((SQUARE,SQUARE[0]))],
         [[[0,0],[1,0]]],[np.full((3,2),np.nan)],[SQUARE+[-.0036,0]]]
@pytest.mark.parametrize('polygons',INVALID)
def test_original_geometry_admission_is_preserved(polygons):
    with pytest.raises(ValueError):
        compact._prepare_compact_corner_panels(polygons,width=W,height=H,panels_per_edge=10)


@pytest.mark.parametrize('dimension,value',[('width',0.),('height',-1.),('width',True),('height',np.inf)])
def test_invalid_rectangle_is_refused(dimension,value):
    kwargs=dict(width=W,height=H);kwargs[dimension]=value
    with pytest.raises(ValueError):compact._prepare_compact_corner_panels([SQUARE],**kwargs)


def test_total_geometry_budget_precedes_partition_construction(monkeypatch):
    polygons=[SQUARE+[.004+(i-2)*.0006,0] for i in range(5)]
    monkeypatch.setattr(compact,'_compact_basis',lambda *a:pytest.fail('partition constructed'))
    with pytest.raises(ValueError,match='8192'):
        compact._prepare_compact_corner_panels(polygons,width=.016,height=H,panels_per_edge=512)


def test_unresolved_panel_lengths_are_still_refused():
    small=(SQUARE-[.004,.001])*1e-8+[.004,.001]
    with pytest.raises(ValueError,match='panel length'):prepare(small,512)
