# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored-index contract, isolation and atomic failure regressions."""
from dataclasses import replace
import gc
import weakref

import numpy as np
import pytest

from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat
import galerkin.transient_thermal_mechanical as workflow


def case():
    mesh = rectangle_mesh(1., 1., 2, 2)
    heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
        time_s=[2., 2.1, 2.7, 3.], initial_temperature_k=np.full(mesh.num_nodes, 300.),
        dirichlet={}, heat_source=8.)
    right = int(mesh.boundary['bottom'][-1])
    kwargs = dict(units={'length': 'm', 'time': 's', 'temperature': 'K'},
        young_modulus=2e9, poisson_ratio=.25, plane='stress',
        thermal_expansion_per_k=1e-5, reference_temperature_k=300.,
        mechanical_dirichlet={(0, 0): 0., (0, 1): 0., (right, 1): 0.})
    return mesh, heat, kwargs


def test_default_and_subset_exact_times_and_snapshot_ownership():
    mesh, heat, kwargs = case()
    before_nodes = mesh.nodes.copy()
    before_temperature = heat.temperature_k.copy()
    result = workflow.solve_transient_thermoelasticity(mesh, heat, **kwargs)
    assert result.time_indices == (0, 1, 2, 3)
    assert result.time_s == tuple(heat.time_s)
    subset = workflow.solve_transient_thermoelasticity(mesh, heat, time_indices=[0, 2], **kwargs)
    assert subset.time_indices == (0, 2)
    assert subset.time_s == (2., 2.7)
    for step in result.steps:
        snapshot = step.temperature_snapshot
        assert snapshot is step.mechanics.temperature_snapshot
        np.testing.assert_array_equal(snapshot.temperature_k, heat.temperature_k[step.time_index])
        for array in (snapshot.nodes, snapshot.triangles, snapshot.temperature_k):
            with pytest.raises(ValueError):
                array.setflags(write=True)
    np.testing.assert_array_equal(mesh.nodes, before_nodes)
    np.testing.assert_array_equal(heat.temperature_k, before_temperature)
    mesh.nodes[:] += 100
    kwargs['mechanical_dirichlet'].clear()
    np.testing.assert_array_equal(result.reference_mesh.nodes, before_nodes)
    np.testing.assert_array_equal(result.steps[0].temperature_snapshot.nodes, before_nodes)
    reference = weakref.ref(heat)
    del heat
    gc.collect()
    assert reference() is None  # Selected result does not retain the heat history.


@pytest.mark.parametrize('indices', [[], [True], [0, True], [0., 1.], [-1], [4],
    [1, 1], [2, 1], [[0]], np.array([[0]]), '0', 1])
def test_bad_selection(indices):
    mesh, heat, kwargs = case()
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, heat, time_indices=indices, **kwargs)
    assert caught.value.stage == 'input'
    assert caught.value.time_index is None
    assert isinstance(caught.value.__cause__, ValueError)


@pytest.mark.parametrize('field,value', [
    ('time_s', np.array([0., 1., 1., 2.])),
    ('time_s', np.array([0., 1., np.nan, 2.])),
    ('time_s', np.array([-1., 0., 1., 2.])),
    ('time_s', np.array([0., 1e308, 1.5e308, 1.6e308])),
    ('time_s', np.array([0.])),
    ('temperature_k', np.zeros((4, 2))),
    ('temperature_k', np.full((4, 9), np.inf)),
])
def test_bad_consumed_history(field, value):
    mesh, heat, kwargs = case()
    if field == 'time_s' and len(value) == 4 and value[1] == 1e308:
        # Nonnegative finite times cannot overflow their positive differences;
        # these extreme but valid times are metadata only and must be preserved.
        result = workflow.solve_transient_thermoelasticity(mesh, replace(heat, **{field: value}), **kwargs)
        assert result.time_s == tuple(value)
        return
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, replace(heat, **{field: value}), **kwargs)
    assert caught.value.stage == 'input'


@pytest.mark.parametrize('change', ['nodes', 'triangles', 'node_order'])
def test_exact_mesh_order_required(change):
    mesh, heat, kwargs = case()
    if change == 'nodes':
        mesh.nodes[4, 0] += .01
    elif change == 'triangles':
        mesh.triangles[:] = mesh.triangles[::-1]
    else:
        permutation = np.arange(mesh.num_nodes)[::-1]
        mesh.nodes[:] = mesh.nodes[permutation]
        mesh.triangles[:] = permutation[mesh.triangles]
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, heat, **kwargs)
    assert caught.value.stage == 'input'


def test_later_negative_transfer_is_atomic_and_unselected_negative_allowed(monkeypatch):
    mesh, heat, kwargs = case()
    temperatures = heat.temperature_k.copy()
    temperatures[2, 0] = -1.
    changed = replace(heat, temperature_k=temperatures)
    workflow.solve_transient_thermoelasticity(mesh, changed, time_indices=[0, 1], **kwargs)
    calls = []
    monkeypatch.setattr(workflow, 'solve_thermoelasticity', lambda *a, **k: calls.append(1))
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, changed, **kwargs)
    assert calls == []
    assert (caught.value.stage, caught.value.time_index, caught.value.time_s) == ('transfer', 2, 2.7)
    assert isinstance(caught.value.__cause__, ValueError)


def test_all_snapshots_frozen_before_mechanics_and_failure_location(monkeypatch):
    mesh, heat, kwargs = case()
    original = workflow.solve_thermoelasticity
    events = []
    freeze = workflow.freeze_temperature
    def record_freeze(*args):
        events.append('freeze')
        return freeze(*args)
    def fail_second(*args, **kw):
        events.append('mechanics')
        if events.count('mechanics') == 2:
            raise RuntimeError('injected second mechanics failure')
        return original(*args, **kw)
    monkeypatch.setattr(workflow, 'freeze_temperature', record_freeze)
    monkeypatch.setattr(workflow, 'solve_thermoelasticity', fail_second)
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, heat, time_indices=[1, 3], **kwargs)
    assert events == ['freeze', 'freeze', 'mechanics', 'mechanics']
    assert (caught.value.stage, caught.value.time_index, caught.value.time_s) == ('mechanics', 3, 3.)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert not hasattr(caught.value, 'partial_result')


@pytest.mark.parametrize('key,value', [
    ('units', {'length': 'mm', 'time': 's', 'temperature': 'K'}),
    ('plane', '3d'), ('young_modulus', 0), ('poisson_ratio', .5),
    ('reference_temperature_k', -1), ('thermal_expansion_per_k', True),
    ('body_force', lambda p: p), ('body_force', [0, True]),
    ('mechanical_dirichlet', {(0, 0): True}),
])
def test_invalid_configuration(key, value):
    mesh, heat, kwargs = case()
    kwargs[key] = value
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, heat, **kwargs)
    assert caught.value.stage == 'input'


def test_insufficient_supports_have_initial_selected_index():
    mesh, heat, kwargs = case()
    kwargs['mechanical_dirichlet'] = {}
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, heat, time_indices=[2], **kwargs)
    assert (caught.value.stage, caught.value.time_index, caught.value.time_s) == ('mechanics', 2, 2.7)
    assert 'rigid modes' in str(caught.value.__cause__)
