# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Numerical refusals and result snapshots of the explicit three-active harmonic field,
split from test_laplace_corner_harmonic_field.py.

Each test here makes its own uncached 10- or 16-panel solve, or none; none uses the module's
cached solves, so they run as their own file at no extra solve and the CI test parts
(tools/shards/openphysics_shard.py) can balance them apart from the cached ones.
"""
import numpy as np
import pytest

from test_laplace_corner_harmonic_field import GEOMETRIES, field, solve


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


def test_no_implicit_fixed_ground_argument():
    with pytest.raises(TypeError):solve(GEOMETRIES[0]['polygons'],width=.008,height=.002,signals=[0])


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
