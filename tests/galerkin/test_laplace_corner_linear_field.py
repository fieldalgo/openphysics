# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical invariants and numerical refusals of the explicit linear field."""
from functools import lru_cache

import numpy as np
import pytest
from panel_studies import ENABLED as STUDIES, matrix_relative, recorded

from galerkin.laplace_corner_linear_field import solve_two_ground_linear_corner_rectangle_edges as solve
from galerkin import laplace_corner_linear_field as field

GEOMETRIES = [{'case': 'single-rectangle', 'width': 0.008, 'height': 0.002, 'polygons': [[[0.00385, 0.0008], [0.00445, 0.0008], [0.00445, 0.00087], [0.00385, 0.00087]]], 'centered_polygons': [[[-0.00015, 0.0008], [0.00045, 0.0008], [0.00045, 0.00087], [-0.00015, 0.00087]]]}, {'case': 'unequal-pair', 'width': 0.008, 'height': 0.002, 'polygons': [[[0.0035, 0.00065], [0.0038, 0.00065], [0.00377, 0.00069], [0.00353, 0.00069]], [[0.00425, 0.00125], [0.00475, 0.00125], [0.00477, 0.00133], [0.00423, 0.00133]]], 'centered_polygons': [[[-0.0005, 0.00065], [-0.0002, 0.00065], [-0.00023, 0.00069], [-0.00047, 0.00069]], [[0.00025, 0.00125], [0.00075, 0.00125], [0.0007700000000000001, 0.00133], [0.00023, 0.00133]]]}]


def relative(a,b):
    a,b=np.asarray(a),np.asarray(b);difference=abs(a-b);scale=np.maximum(abs(a),abs(b))
    assert np.isfinite(difference).all()
    return float(np.max(np.divide(difference,scale,out=np.zeros_like(difference),where=scale!=0)))


def quantities(result):
    n=len(result.whole.capacitance_per_permittivity);parts=result.whole.current_gram
    return (result.whole.capacitance_per_permittivity,result.edge_current_gram,
            np.concatenate((parts[:n],parts[n:].sum(axis=0)[None])))


def calculated(index,count=64,width=.008,reflect=False):
    # Normalize the cache key: calculated(i) and calculated(i,64) are the same solve.
    return _calculated(index,count,width,reflect)


@lru_cache(maxsize=32)
def _calculated(index,count,width,reflect):
    row=GEOMETRIES[index]
    polygons=[np.asarray(p)+[width/2,0.] for p in row['centered_polygons']]
    if reflect:polygons=[np.column_stack((width-p[:,0],p[:,1])) for p in polygons]
    return solve(polygons,width=width,height=row['height'],panels_per_edge=count,
                 ground_modes={.008:256,.016:512,.032:1024}[width])


if STUDIES:  # dispatch-only convergence study (tests/_support/panel_studies.py)
    @pytest.mark.slow
    @pytest.mark.parametrize('index',range(2))
    def test_panel_refinement_and_two_separate_outer_changes(index,record_property):
        coarse=quantities(calculated(index,32));fine=quantities(calculated(index,64))
        panel=[relative(a,b) for a,b in zip(coarse,fine)]
        assert max(panel)<=.01
        outer=[quantities(calculated(index,width=width)) for width in (.008,.016,.032)]
        changes=[[relative(a,b) for a,b in zip(first,second)] for first,second in zip(outer,outer[1:])]
        assert max(value for row in changes for value in row)<=.01
        record_property('linear_corner_resolution',repr((index,panel,changes)))


@pytest.mark.parametrize('index',range(2))
def test_cheapest_study_resolution_reproduces_the_recorded_values(index):
    """The study above runs only on dispatch (tests/_support/panel_studies.py); the resolution
    the tests below solve (64 panels, 8 mm) must keep the values recorded with it."""
    for value,reference in zip(quantities(calculated(index)),recorded('test_laplace_corner_linear_field',index)):
        assert matrix_relative(value,reference)<=1e-9


def test_active_conductor_basis_permutation():
    row=GEOMETRIES[1];a=calculated(1,32)
    b=solve(row['polygons'][::-1],width=row['width'],height=row['height'],panels_per_edge=32)
    assert relative(b.whole.capacitance_per_permittivity[::-1,::-1],a.whole.capacitance_per_permittivity)<=1e-10
    assert relative(b.whole.current_gram[[1,0,2,3],::-1,::-1],a.whole.current_gram)<=1e-10
    assert relative(b.edge_current_gram[[4,5,6,7,0,1,2,3],::-1,::-1],a.edge_current_gram)<=1e-10


@pytest.mark.parametrize('index',range(2))
def test_exact_face_partition_signed_current_and_positive_gram(index):
    result=calculated(index,32);n=len(GEOMETRIES[index]['polygons'])
    assert result.whole.panel_count==4*n*(32-6)
    assert result.whole.condition_bound<1e10
    for name in ('reciprocity_error','residual_error','current_error','matrix_refinement_error','ground_refinement_error'):
        assert getattr(result.whole,name)<=1e-10
    assert result.partition_error<=1e-10
    for owner in range(n):
        selected=result.edge_owners==owner
        assert relative(result.edge_current_gram[selected].sum(axis=0),result.whole.current_gram[owner])<=1e-10
        np.testing.assert_allclose(result.edge_current_integrals[selected].sum(axis=0),np.eye(n)[owner],rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.whole.current_integrals.sum(axis=0),0,rtol=0,atol=1e-10)
    for part in np.concatenate((result.whole.current_gram,result.edge_current_gram)):
        assert relative(part,part.T)<=1e-10
        assert np.linalg.eigvalsh(part).min()/np.max(abs(part))>=-1e-10


def test_result_arrays_and_original_geometry_are_independent_immutable_snapshots():
    polygons=[np.array(p) for p in GEOMETRIES[0]['polygons']];before=[p.copy() for p in polygons]
    result=solve(polygons,width=.008,height=.002,panels_per_edge=16)
    for actual,original in zip(polygons,before):assert np.array_equal(actual,original)
    for value in (result.edge_owners,result.edge_starts,result.edge_ends,result.edge_current_gram,result.edge_current_integrals,result.whole.capacitance_per_permittivity,result.whole.current_gram,result.whole.current_integrals):
        with pytest.raises(ValueError):value.flags.writeable=True
    starts=result.edge_starts.copy();polygons[0][:]=0
    assert np.array_equal(result.edge_starts,starts)


@pytest.mark.parametrize('option,value',[
    ('width',True),('height',0),('width',np.inf),('height',np.nan),
    ('panels_per_edge',15),('panels_per_edge',17),('panels_per_edge',514),
    ('panels_per_edge',True),('panels_per_edge',32.),
    ('ground_modes',63),('ground_modes',65),('ground_modes',4098),('ground_modes',True),
    ('interpolation_degree',20),('interpolation_degree',26),
    ('interpolation_degree',24.),('interpolation_degree',True),
])
def test_invalid_controls_fail_before_assembly(monkeypatch,option,value):
    monkeypatch.setattr(field,'assemble_linear_corner_half_space',lambda *a,**k:pytest.fail('assembly started'))
    kwargs=dict(width=.008,height=.002,panels_per_edge=16);kwargs[option]=value
    with pytest.raises(ValueError):solve(GEOMETRIES[0]['polygons'],**kwargs)


@pytest.mark.parametrize('polygons',[[],GEOMETRIES[0]['polygons']*3,None,
    [[[.001,.001],[.001,.001],[.002,.001]]],
    [[[.001,0],[.002,0],[.002,.001],[.001,.001]]],GEOMETRIES[0]['polygons']*2])
def test_invalid_geometry_and_unsupported_conductor_selection(polygons):
    with pytest.raises(ValueError):solve(polygons,width=.008,height=.002,panels_per_edge=16)


def test_linear_density_budget_precedes_dense_allocation(monkeypatch):
    from galerkin import laplace_corner_linear_assembly as assembly
    angles=np.arange(9)*2*np.pi/9
    polygon=np.column_stack((.004+.0003*np.cos(angles),.001+.0003*np.sin(angles)))
    monkeypatch.setattr(assembly,'_assemble',lambda *a:pytest.fail('dense allocation started'))
    with pytest.raises(ValueError,match='512'):
        solve([polygon],width=.008,height=.002,panels_per_edge=64)


def test_no_implicit_fixed_ground_argument():
    with pytest.raises(TypeError):solve(GEOMETRIES[1]['polygons'],width=.008,height=.002,signals=[0])


@pytest.mark.parametrize('fault',['quadrature','reciprocity','nonfinite'])
def test_smooth_matrix_failure_is_not_hidden_by_symmetry_average(monkeypatch,fault):
    original=field._smooth
    def changed(*args):
        result=original(*args)
        if fault=='quadrature' and args[3].shape[1]==400:result=result+1e-5
        elif fault=='reciprocity':result[0,1]+=1e-5
        elif fault=='nonfinite':result[0,0]=np.nan
        return result
    monkeypatch.setattr(field,'_smooth',changed)
    with pytest.raises(ValueError,match='matrix'):
        solve(GEOMETRIES[0]['polygons'],width=.008,height=.002,panels_per_edge=16)


def test_ground_quadrature_refusal_has_no_fallback(monkeypatch):
    original=field._ground_integrated
    def changed(*args):
        result=original(*args)
        if args[-1]==16:result[:,1:]*=1.01
        return result
    monkeypatch.setattr(field,'_ground_integrated',changed)
    with pytest.raises(ValueError,match='ground'):
        solve(GEOMETRIES[0]['polygons'],width=.008,height=.002,panels_per_edge=16)


def test_circular_limit_against_analytic_grounded_line(record_property):
    # The finite upper plane remains explicit. Geometry refinement approaches
    # the circle; the separate polygon/panel/outer study bounds that bias.
    radius,center_height=.1,.5
    width,height=256.,128.
    b=np.sqrt(center_height**2-radius**2)
    expected=np.array([2*np.pi/np.arccosh(center_height/radius),
        center_height/(2*np.pi*radius*b),1/(2*np.pi*b)])
    errors=[];values=[]
    for vertices in (16,24):
        angle=np.arange(vertices)*2*np.pi/vertices+np.pi/vertices
        circumradius=radius/np.cos(np.pi/vertices)
        polygon=np.column_stack((width/2+circumradius*np.cos(angle),
                                 center_height+circumradius*np.sin(angle)))
        result=solve([polygon],width=width,height=height,panels_per_edge=16,ground_modes=4096)
        actual=np.array([result.whole.capacitance_per_permittivity[0,0],
            result.whole.current_gram[0,0,0],result.whole.current_gram[1:,0,0].sum()])
        values.append(actual.tolist());errors.append(abs(actual-expected)/abs(expected))
    assert np.all(errors[1]<errors[0])
    assert np.max(errors[1])<.005
    record_property('linear_corner_circular_limit',repr((values,[x.tolist() for x in errors])))
