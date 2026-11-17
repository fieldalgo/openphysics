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
    heat = solve_transient_heat(mesh, thermal_conductivity=2., volumetric_heat_capacity=4.,
        time=[2., 2.1, 2.7, 3.], initial_temperature=np.full(mesh.num_nodes, 300.),
        prescribed_temperature={}, heat_source_density=8.)
    right = int(mesh.boundary['bottom'][-1])
    kwargs = dict(youngs_modulus=2e9, poisson_ratio=.25, plane='stress',
        linear_expansion_coefficient=1e-5, stress_free_temperature=300.,
        prescribed_displacement={(0, 0): 0., (0, 1): 0., (right, 1): 0.})
    return mesh, heat, kwargs


def test_default_and_subset_exact_times_and_snapshot_ownership():
    mesh, heat, kwargs = case()
    before_nodes = mesh.nodes.copy()
    before_temperature = heat.temperature.copy()
    result = workflow.solve_transient_thermoelasticity(mesh, heat, **kwargs)
    assert result.time_indices == (0, 1, 2, 3)
    assert result.time == tuple(heat.time)
    subset = workflow.solve_transient_thermoelasticity(mesh, heat, time_indices=[0, 2], **kwargs)
    assert subset.time_indices == (0, 2)
    assert subset.time == (2., 2.7)
    for step in result.steps:
        snapshot = step.temperature_snapshot
        assert snapshot is step.mechanics.temperature_snapshot
        np.testing.assert_array_equal(snapshot.temperature, heat.temperature[step.time_index])
        for array in (snapshot.nodes, snapshot.triangles, snapshot.temperature):
            with pytest.raises(ValueError):
                array.setflags(write=True)
    np.testing.assert_array_equal(mesh.nodes, before_nodes)
    np.testing.assert_array_equal(heat.temperature, before_temperature)
    mesh.nodes[:] += 100
    kwargs['prescribed_displacement'].clear()
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
    ('time', np.array([0., 1., 1., 2.])),
    ('time', np.array([0., 1., np.nan, 2.])),
    ('time', np.array([-1., 0., 1., 2.])),
    ('time', np.array([0., 1e308, 1.5e308, 1.6e308])),
    ('time', np.array([0.])),
    ('temperature', np.zeros((4, 2))),
    ('temperature', np.full((4, 9), np.inf)),
])
def test_bad_consumed_history(field, value):
    mesh, heat, kwargs = case()
    if field == 'time' and len(value) == 4 and value[1] == 1e308:
        # Nonnegative finite times cannot overflow their positive differences;
        # these extreme but valid times are metadata only and must be preserved.
        result = workflow.solve_transient_thermoelasticity(mesh, replace(heat, **{field: value}), **kwargs)
        assert result.time == tuple(value)
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
    temperatures = heat.temperature.copy()
    temperatures[2, 0] = -1.
    changed = replace(heat, temperature=temperatures)
    workflow.solve_transient_thermoelasticity(mesh, changed, time_indices=[0, 1], **kwargs)
    calls = []
    monkeypatch.setattr(workflow, 'solve_thermoelasticity', lambda *a, **k: calls.append(1))
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, changed, **kwargs)
    assert calls == []
    assert (caught.value.stage, caught.value.time_index, caught.value.time) == ('transfer', 2, 2.7)
    assert isinstance(caught.value.__cause__, ValueError)


def test_all_snapshots_frozen_before_mechanics_and_failure_location(monkeypatch):
    mesh, heat, kwargs = case()
    original = workflow.solve_thermoelasticity
    events = []
    freeze = workflow.freeze_temperature
    def record_freeze(*args, **kw):
        events.append('freeze')
        return freeze(*args, **kw)
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
    assert (caught.value.stage, caught.value.time_index, caught.value.time) == ('mechanics', 3, 3.)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert not hasattr(caught.value, 'partial_result')


@pytest.mark.parametrize('key,value', [
    ('plane', '3d'), ('youngs_modulus', 0), ('poisson_ratio', .5),
    ('stress_free_temperature', -1), ('linear_expansion_coefficient', True),
    ('body_force_density', lambda p: p), ('body_force_density', [0, True]),
    ('prescribed_displacement', {(0, 0): True}),
])
def test_invalid_configuration(key, value):
    mesh, heat, kwargs = case()
    kwargs[key] = value
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, heat, **kwargs)
    assert caught.value.stage == 'input'


def test_insufficient_supports_have_initial_selected_index():
    mesh, heat, kwargs = case()
    kwargs['prescribed_displacement'] = {}
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(mesh, heat, time_indices=[2], **kwargs)
    assert (caught.value.stage, caught.value.time_index, caught.value.time) == ('mechanics', 2, 2.7)
    assert 'rigid modes' in str(caught.value.__cause__)
