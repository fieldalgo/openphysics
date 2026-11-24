# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical invariants and explicit fixed-potential guard admission."""
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


@lru_cache(maxsize=32)
def calculated(index,count=32,width=.008,reflect=False):
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


@lru_cache(maxsize=1)
def full_three():
    from galerkin.laplace_corner_harmonic_field import solve_two_ground_harmonic_corner_three_active_edges
    row=GEOMETRIES[0]
    return solve_two_ground_harmonic_corner_three_active_edges(row['polygons'],width=.008,height=.002,panels_per_edge=16)


def test_explicit_active_index_selects_physical_voltage_boundary():
    row=GEOMETRIES[0];full=full_three();observed=[]
    for signal in (0,1,2):
        result=(calculated(0,16) if signal==2 else solve(row['polygons'],signal=signal,width=.008,height=.002,panels_per_edge=16))
        cap=full.whole.capacitance_per_permittivity[signal:signal+1,signal:signal+1]
        assert relative(result.whole.capacitance_per_permittivity,cap)<=1e-10
        guards=[i for i in range(3) if i!=signal]
        voltage=np.linalg.solve(full.whole.capacitance_per_permittivity,result.whole.current_integrals[:3])
        assert np.max(abs(voltage[guards]))<=1e-10
        np.testing.assert_allclose(result.whole.current_integrals[signal],1.,rtol=0,atol=1e-10)
        observed.append(float(cap[0,0]))
    assert len(set(observed))==3


@pytest.mark.parametrize('permutation',[(0,1,2),(0,2,1),(1,0,2),(1,2,0),(2,0,1),(2,1,0)])
def test_polygon_order_and_explicit_signal_selection(permutation):
    row=GEOMETRIES[0];perm=np.asarray(permutation);undo=np.argsort(perm);base=calculated(0,16)
    signal=int(np.flatnonzero(perm==2)[0])
    other=solve([row['polygons'][i] for i in perm],signal=signal,width=.008,height=.002,panels_per_edge=16)
    assert relative(other.whole.capacitance_per_permittivity,base.whole.capacitance_per_permittivity)<=1e-10
    whole=np.concatenate([other.whole.current_gram[:3][undo],other.whole.current_gram[3:]])
    faces=other.edge_current_gram.reshape(3,4,1,1)[undo].reshape(12,1,1)
    assert relative(whole,base.whole.current_gram)<=1e-10
    assert relative(faces,base.edge_current_gram)<=1e-10


def test_prescribed_guard_voltage_and_induced_current_are_not_floating():
    from galerkin.laplace_corner_harmonic_field import solve_two_ground_harmonic_corner_three_active_edges
    row=GEOMETRIES[0];guard=calculated(0,16)
    full=full_three()
    cap=full.whole.capacitance_per_permittivity;css=cap[2:3,2:3]
    transform=np.linalg.solve(css,cap[:,2:3].T).T
    assert relative(guard.whole.capacitance_per_permittivity,css)<=1e-10
    voltage=np.linalg.solve(cap,guard.whole.current_integrals[:3])
    assert np.max(abs(voltage[:2]))<=1e-10
    assert np.max(abs(guard.whole.current_integrals[:2]))>1e-6
    expected=np.einsum('ai,pab,bj->pij',transform,full.whole.current_gram,transform)
    assert relative(guard.whole.current_gram,expected)<=1e-10


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
    ('panels_per_edge',8),('panels_per_edge',17),('panels_per_edge',514),
    ('panels_per_edge',True),('panels_per_edge',32.),
    ('ground_modes',63),('ground_modes',65),('ground_modes',4098),('ground_modes',True),
    ('interpolation_degree',20),('interpolation_degree',26),
    ('interpolation_degree',24.),('interpolation_degree',True),
])
def test_invalid_controls_fail_before_assembly(monkeypatch,option,value):
    monkeypatch.setattr(field,'assemble_harmonic_half_space',lambda *a,**k:pytest.fail('assembly started'))
    kwargs=dict(width=.008,height=.002,panels_per_edge=10);kwargs[option]=value
    with pytest.raises(ValueError):solve(GEOMETRIES[0]['polygons'],**kwargs)


@pytest.mark.parametrize('polygons',[[],GEOMETRIES[0]['polygons'][:1],None,
    [[[.001,.001],[.001,.001],[.002,.001]]],
    [[[.001,0],[.002,0],[.002,.001],[.001,.001]]],GEOMETRIES[0]['polygons']*2])
def test_invalid_geometry_and_unsupported_conductor_selection(polygons):
    with pytest.raises(ValueError):solve(polygons,width=.008,height=.002,panels_per_edge=10)


def test_harmonic_density_budget_precedes_dense_allocation(monkeypatch):
    from galerkin import _laplace_corner_compact_harmonic_assembly as assembly
    angles=np.arange(9)*2*np.pi/9
    polygons=[np.column_stack((x+.0001*np.cos(angles),y+.0001*np.sin(angles))) for x,y in [(.0035,.0007),(.004,.001),(.0045,.0013)]]
    monkeypatch.setattr(assembly,'_assemble',lambda *a:pytest.fail('dense allocation started'))
    with pytest.raises(ValueError,match='512'):
        solve(polygons,width=.008,height=.002,panels_per_edge=32)


@pytest.mark.parametrize('signal',[None,[],[0],-1,3,False,True,0.,'0',np.array(0)])
def test_invalid_signal_selection_precedes_assembly(monkeypatch,signal):
    monkeypatch.setattr(field,'assemble_harmonic_half_space',lambda *a,**k:pytest.fail('assembly started'))
    with pytest.raises(ValueError):solve(GEOMETRIES[0]['polygons'],width=.008,height=.002,signal=signal)


def test_signal_selection_is_required_on_public_api():
    with pytest.raises(TypeError):field.solve_two_ground_harmonic_corner_single_active_edges(GEOMETRIES[0]['polygons'],width=.008,height=.002)


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
