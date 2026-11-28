# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical invariants and explicit fixed-potential guard admission.

The tests here share the cached 32-panel solve and its reflection (calculated(index) and
calculated(index,reflect=True)), so each of those solves runs once per CI test part. The
16-panel signal-selection tests, which share calculated(0,16), are in
test_laplace_corner_harmonic_single_active_field_selection.py; the refusals, which share no cached solve, in
test_laplace_corner_harmonic_single_active_field_refusals.py.
"""
from functools import lru_cache

import numpy as np
import pytest
from panel_studies import ENABLED as STUDIES, matrix_relative, recorded

from galerkin import laplace_corner_harmonic_single_active_field as field


def solve(polygons, **kwargs):
    kwargs.setdefault("signal", 2)
    return field.solve_two_ground_harmonic_corner_single_active_edges(polygons, **kwargs)

GEOMETRIES = [{'case': 'three-unequal-tapered', 'width': 0.008, 'height': 0.002, 'polygons': [[[0.003425, 0.0006], [0.003775, 0.0006], [0.00375, 0.00065], [0.00345, 0.00065]], [[0.00425, 0.0011], [0.00465, 0.0011], [0.004675, 0.00116], [0.0042250000000000005, 0.00116]], [[0.0039000000000000003, 0.00155], [0.0041, 0.00155], [0.00409, 0.00159], [0.00391, 0.00159]]], 'centered_polygons': [[[-0.000575, 0.0006], [-0.00022500000000000002, 0.0006], [-0.00025, 0.00065], [-0.00055, 0.00065]], [[0.00025, 0.0011], [0.00065, 0.0011], [0.000675, 0.00116], [0.000225, 0.00116]], [[-0.0001, 0.00155], [0.0001, 0.00155], [9e-05, 0.00159], [-9e-05, 0.00159]]]}]


def relative(a,b):
    a,b=np.asarray(a),np.asarray(b);difference=abs(a-b);scale=np.maximum(abs(a),abs(b))
    assert np.isfinite(difference).all()
    return float(np.max(np.divide(difference,scale,out=np.zeros_like(difference),where=scale!=0)))


def quantities(result):
    n=3;parts=result.whole.current_gram
    return (result.whole.capacitance_per_permittivity,result.edge_current_gram,
            np.concatenate((parts[:n],parts[n:].sum(axis=0)[None])))


def calculated(index,count=32,width=.008,reflect=False):
    # Normalize the cache key: calculated(i) and calculated(i,32) are the same solve.
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
    @pytest.mark.parametrize('index',range(1))
    def test_panel_refinement_and_two_separate_outer_changes(index,record_property):
        coarse=quantities(calculated(index,32));fine=quantities(calculated(index,48))
        panel=[relative(a,b) for a,b in zip(coarse,fine)]
        assert max(panel)<=.01
        outer=[quantities(calculated(index,count=48,width=width)) for width in (.008,.016,.032)]
        changes=[[relative(a,b) for a,b in zip(first,second)] for first,second in zip(outer,outer[1:])]
        assert max(value for row in changes for value in row)<=.01
        record_property('harmonic_single_active_resolution',repr((index,panel,changes)))


@pytest.mark.parametrize('index',range(1))
def test_cheapest_study_resolution_reproduces_the_recorded_values(index):
    """The study above runs only on dispatch (tests/_support/panel_studies.py); the resolution
    the tests below solve (32 panels, 8 mm) must keep the values recorded with it."""
    for value,reference in zip(quantities(calculated(index)),recorded('test_laplace_corner_harmonic_single_active_field',index)):
        assert matrix_relative(value,reference)<=1e-9


@pytest.mark.parametrize('index',range(1))
def test_horizontal_reflection_preserves_each_current_entry_without_floor(index):
    original,reflected=calculated(index),calculated(index,reflect=True)
    n=len(GEOMETRIES[index]['polygons']);cap,faces,whole=quantities(reflected)
    faces=faces.reshape(n,4,1,1)[:,[2,1,0,3]].reshape(4*n,1,1)
    assert max(relative(a,b) for a,b in zip(quantities(original),(cap,faces,whole)))<=1e-10


@pytest.mark.parametrize('index',range(1))
@pytest.mark.parametrize('scale',[2.**-15,2.**15])
def test_physical_scaling_keeps_capacitance_and_inverse_length_current_units(index,scale):
    row=GEOMETRIES[index];expected=calculated(index,32)
    result=solve([np.asarray(p)*scale for p in row['polygons']],
                 width=row['width']*scale,height=row['height']*scale,panels_per_edge=32)
    assert relative(result.whole.capacitance_per_permittivity,expected.whole.capacitance_per_permittivity)<=1e-10
    assert relative(scale*result.whole.current_gram,expected.whole.current_gram)<=1e-10
    assert relative(scale*result.edge_current_gram,expected.edge_current_gram)<=1e-10
    np.testing.assert_allclose(result.whole.current_integrals,expected.whole.current_integrals,rtol=0,atol=1e-10)


@pytest.mark.parametrize('index',range(1))
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
        np.testing.assert_allclose(result.edge_current_integrals[selected].sum(axis=0),result.whole.current_integrals[owner],rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.whole.current_integrals[2:3],np.eye(1),rtol=0,atol=1e-10)
    assert np.min(abs(result.whole.current_integrals[:2]))>1e-6
    np.testing.assert_allclose(result.whole.current_integrals.sum(axis=0),0,rtol=0,atol=1e-10)
    for part in np.concatenate((result.whole.current_gram,result.edge_current_gram)):
        assert relative(part,part.T)<=1e-10
        assert np.linalg.eigvalsh(part).min()/np.max(abs(part))>=-1e-10
