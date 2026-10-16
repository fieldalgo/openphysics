# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Public steady boundary runtime, serialization and refusal regressions."""
import json

import numpy as np
import pytest

from simcase import Document, ThermalRunResult, run
from simcase.cli import main
from simcase.thermal import _OwnedOutput

ADDED = ('prescribed_outward_load_w_per_m', 'ambient_load_w_per_m',
         'convective_outward_w_per_m', 'system_rhs_w_per_m')


def model(*, robin_only=False, legacy=False, empty=False, fields=True):
    p = dict(type='thermal.steady2d', conductivity_w_mk=2., heat_source_w_m3=0.,
             dirichlet_temperature_k={'left': 300.})
    if not legacy:
        p.update(outward_flux_w_m2={'right': 2.},
                 convection={'right': {'h_w_m2k': 4., 'ambient_temperature_k': 290.}})
    if empty:
        p['outward_flux_w_m2'] = {}
        p.pop('convection', None)
    if robin_only:
        p.update(dirichlet_temperature_k={}, outward_flux_w_m2={},
                 convection={'right': {'h_w_m2k': 4., 'ambient_temperature_k': 290.}})
    return dict(openphysics='0.2', name='Boundary runtime control',
                units={'length': 'm', 'temperature': 'K'},
                geometry={'domain': dict(xmin=0., xmax=1., ymin=0., ymax=1.)},
                materials={}, physics={'heat1': p}, mesh={'subdivisions': [4, 4]},
                study={'type': 'single'}, results={'save_fields': fields, 'plots': False})


def test_additive_exact_linear_public_result():
    result = run(Document.from_dict(model()), verbose=False)
    assert isinstance(result, ThermalRunResult)
    np.testing.assert_allclose((result.temperature_k-(300.-7.*result.mesh_nodes_m[:, 0]))/7.,
                               0., rtol=0., atol=1e-10)
    np.testing.assert_allclose((result.heat_flux_w_m2-[14., 0.])/14.,
                               0., rtol=0., atol=1e-10)
    s = result.summary()
    assert s['result_format'] == 'thermal.steady2d-result-v2'
    assert s['field_layout'] == 'thermal2d-p1-node-cell-boundary-v2'
    np.testing.assert_allclose(
        [s['source_heat_w_per_m'], s['prescribed_outward_heat_w_per_m'],
         s['convective_outward_heat_w_per_m'], s['thermostat_outward_heat_w_per_m'],
         s['outward_heat_w_per_m']], [0., 2., 12., -14., 0.], rtol=0., atol=14e-10)
    np.testing.assert_allclose(result.system_rhs_w_per_m,
        result.load_w_per_m+result.ambient_load_w_per_m-result.prescribed_outward_load_w_per_m,
        rtol=1e-12, atol=1e-12)
    assert 'normalized_free_residual' not in s
    assert s['free_residual_max_w_per_m'] <= 14e-10
    assert not {'wavelength', 'neff', 'normalization'} & s.keys()


@pytest.mark.parametrize('robin_only', [False, True])
@pytest.mark.parametrize('fields', [False, True])
def test_numeric_history_free_npz_and_summary(tmp_path, robin_only, fields):
    r = run(Document.from_dict(model(robin_only=robin_only, fields=fields)), False)
    out = r.save(tmp_path/'result')
    s = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    assert not (out/'.incomplete').exists()
    assert (out/'fields.npz').exists() == fields
    assert len(s['field_shapes']) == 13
    for key in ADDED:
        assert s['field_shapes'][key] == [r.mesh.num_nodes]
        assert s['field_units'][key] == 'W/m'
        assert s['field_locations'][key] == 'nodes'
    if robin_only:
        assert r.dirichlet_node_ids.shape == r.dirichlet_temperature_k.shape == (0,)
        np.testing.assert_allclose(r.temperature_k, 290., rtol=0., atol=1e-10)
        np.testing.assert_array_equal(r.reaction_w_per_m, 0.)
    if fields:
        with np.load(out/'fields.npz', allow_pickle=False) as z:
            assert str(z['result_format']) == s['result_format']
            assert str(z['field_layout']) == s['field_layout']
            assert json.loads(str(z['metadata_json'])) == s
            for key in s['field_shapes']:
                a = z[key]
                assert not a.dtype.hasobject
                np.testing.assert_array_equal(a, r._raw_arrays()[key])
    assert json.loads((out/'model.json').read_text(encoding='utf-8')) == r.doc.data


def test_presence_empty_preserves_physics_but_not_layout(tmp_path):
    old = run(Document.from_dict(model(legacy=True)), False)
    explicit = run(Document.from_dict(model(empty=True)), False)
    assert old.result_format == 'thermal.steady2d-result-v1'
    assert explicit.result_format == 'thermal.steady2d-result-v2'
    assert len(old._raw_arrays()) == 9 and len(explicit._raw_arrays()) == 13
    for key, values in old._raw_arrays().items():
        np.testing.assert_array_equal(values, explicit._raw_arrays()[key])
    assert 'outward_flux_w_m2' not in old.doc.sole_physics()[1]
    old.save(tmp_path/'legacy')
    with np.load(tmp_path/'legacy'/'fields.npz', allow_pickle=False) as z:
        assert not set(ADDED) & set(z.files)
        assert str(z['field_layout']) == 'thermal2d-p1-node-cell-v1'


@pytest.mark.parametrize('key', ADDED)
@pytest.mark.parametrize('fault', ['nan', 'shape', 'missing'])
@pytest.mark.parametrize('fields', [False, True])
def test_added_raw_invalid_never_completes(tmp_path, key, fault, fields):
    r = run(Document.from_dict(model(fields=fields)), False)
    attr = {'prescribed_outward_load_w_per_m': 'prescribed_outward_load',
            'ambient_load_w_per_m': 'ambient_load', 'convective_outward_w_per_m': 'convective_outward',
            'system_rhs_w_per_m': 'system_rhs'}[key]
    if fault == 'nan':
        getattr(r.solution, attr)[0] = np.nan
    else:
        setattr(r.solution, attr, np.zeros((r.mesh.num_nodes, 1)) if fault == 'shape' else None)
    with pytest.raises(ValueError):
        r.save(tmp_path/'bad')
    assert not (tmp_path/'bad'/'summary.json').exists()
    assert not (tmp_path/'bad').exists()


@pytest.mark.parametrize('kind', ['source', 'flux', 'ambient', 'h', 'domain', 'mesh',
                                  'dirichlet', 'name', 'results'])
def test_valid_document_mutation_is_not_relabelled(tmp_path, kind):
    r = run(Document.from_dict(model()), False)
    p = r.doc.sole_physics()[1]
    if kind == 'source': p['heat_source_w_m3'] = 1.
    elif kind == 'flux': p['outward_flux_w_m2']['right'] = 3.
    elif kind == 'ambient': p['convection']['right']['ambient_temperature_k'] = 291.
    elif kind == 'h': p['convection']['right']['h_w_m2k'] = 5.
    elif kind == 'domain': r.doc.data['geometry']['domain']['xmax'] = 2.
    elif kind == 'mesh': r.doc.data['mesh']['subdivisions'] = [8, 8]
    elif kind == 'dirichlet': p['dirichlet_temperature_k']['left'] = 301.
    elif kind == 'name': r.doc.data['name'] = 'Different run'
    else: r.doc.data['results']['save_fields'] = False
    r.doc.validate()  # Deliberately valid data; invalid-input refusal is separate.
    with pytest.raises(ValueError, match='document changed'):
        r.summary()
    with pytest.raises(ValueError, match='document changed'):
        r.save(tmp_path/'mutated')
    assert not (tmp_path/'mutated').exists()


@pytest.mark.parametrize('kind', ['nodes', 'triangles', 'fixed', 'temperature'])
def test_bound_mesh_and_prescribed_data_mutation(tmp_path, kind):
    r = run(Document.from_dict(model()), False)
    if kind == 'nodes': r.mesh.nodes[0, 0] += .001
    elif kind == 'triangles': r.mesh.triangles[0] = r.mesh.triangles[0][::-1]
    elif kind == 'fixed': r.dirichlet_node_ids[0] = r.dirichlet_node_ids[1]
    else: r.dirichlet_temperature_k[0] += 1.
    with pytest.raises(ValueError, match='mesh or prescribed data changed'):
        r.save(tmp_path/'changed')
    assert not (tmp_path/'changed').exists()


def test_original_caller_mutation_and_dictionary_order_are_harmless():
    d = Document.from_dict(model())
    r = run(d, False)
    d.data['physics']['heat1']['heat_source_w_m3'] = 10.
    r.doc.data = dict(reversed(list(r.doc.data.items())))
    assert r.summary()['heat_source_w_m3'] == 0.


def test_inputs_are_captured_before_solver_returns(monkeypatch):
    import galerkin.thermal as engine
    original = engine.solve_steady_heat
    def changed(mesh, **kwargs):
        solution = original(mesh, **kwargs)
        mesh.nodes[0, 0] += .001
        return solution
    monkeypatch.setattr(engine, 'solve_steady_heat', changed)
    with pytest.raises(ValueError, match='inputs changed during'):
        run(Document.from_dict(model()), False)


def test_negative_solved_kelvin_is_not_clamped():
    d = model()
    p = d['physics']['heat1']
    p['dirichlet_temperature_k'] = {'left': 1.}
    p['outward_flux_w_m2'] = {'right': 20.}
    p['convection']['right']['ambient_temperature_k'] = 0.
    r = run(Document.from_dict(d), False)
    np.testing.assert_allclose(r.temperature_k, 1.-4.*r.mesh_nodes_m[:, 0],
                               rtol=0., atol=1e-10)
    assert r.temperature_k.min() < 0.
    r.summary()


@pytest.mark.parametrize('unit,factor', [('m', 1.), ('mm', 1000.), ('um', 1e6)])
def test_same_physical_si_fields(unit, factor):
    d = model()
    d['units']['length'] = unit
    d['geometry']['domain'] = {k: v*factor for k, v in d['geometry']['domain'].items()}
    r = run(Document.from_dict(d), False)
    baseline = run(Document.from_dict(model()), False)
    for key, values in baseline._raw_arrays().items():
        np.testing.assert_allclose(r._raw_arrays()[key], values, rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize('fields', [False, True])
def test_nonfinite_json_diagnostics_refuses_publication(tmp_path, fields):
    r = run(Document.from_dict(model(fields=fields)), False)
    r.diagnostics['overflow'] = float('inf')
    with pytest.raises(ValueError):
        r.save(tmp_path/'overflow')
    assert not (tmp_path/'overflow').exists()


@pytest.mark.parametrize('target', ['file', 'empty', 'nonempty', 'dangling'])
def test_existing_output_is_preserved(tmp_path, target):
    out = tmp_path/'existing'
    if target == 'file': out.write_bytes(b'keep')
    elif target == 'dangling':
        out.symlink_to(tmp_path/'missing', target_is_directory=True)
    else:
        out.mkdir()
        if target == 'nonempty': (out/'foreign').write_bytes(b'keep')
    r = run(Document.from_dict(model()), False)
    with pytest.raises(FileExistsError):
        r.save(out)
    if target == 'file': assert out.read_bytes() == b'keep'
    elif target == 'dangling': assert out.is_symlink() and not out.exists()
    elif target == 'empty': assert list(out.iterdir()) == []
    else: assert (out/'foreign').read_bytes() == b'keep'


@pytest.mark.parametrize('failure', ['npz', 'summary', 'unexpected'])
def test_save_failure_owned_cleanup(tmp_path, monkeypatch, failure):
    r = run(Document.from_dict(model()), False)
    original = _OwnedOutput.write
    out = tmp_path/'out'
    def broken(owned, name, writer):
        if failure == 'summary' and name == 'summary.json':
            raise OSError('injected before summary')
        result = original(owned, name, writer)
        if name == 'fields.npz' and failure in ('npz', 'unexpected'):
            if failure == 'unexpected': (out/'foreign').write_bytes(b'keep')
            raise OSError('injected after NPZ')
        return result
    monkeypatch.setattr(_OwnedOutput, 'write', broken)
    with pytest.raises(OSError, match='injected'):
        r.save(out)
    assert not (out/'summary.json').exists()
    if failure == 'unexpected':
        assert (out/'foreign').read_bytes() == b'keep'
        assert (out/'.incomplete').exists()
    else: assert not out.exists()


def test_concurrent_writer_loser_cannot_cleanup_winner(tmp_path):
    out = tmp_path/'exclusive'
    owner = _OwnedOutput(out)
    try:
        owner.write('.incomplete', lambda f: f.write(b'pending'))
        owner.write('winner', lambda f: f.write(b'keep'))
        r = run(Document.from_dict(model()), False)
        with pytest.raises(FileExistsError):
            r.save(out)
        assert (out/'winner').read_bytes() == b'keep'
    finally:
        owner.cleanup()
        owner.close()


def test_public_cli_exit_and_fresh_preflight(tmp_path, capsys):
    path = tmp_path/'model.json'
    path.write_text(json.dumps(model()), encoding='utf-8')
    assert main(['validate', str(path)]) == 0
    out = tmp_path/'run'
    assert main(['run', str(path), '-q', '-o', str(out)]) == 0
    assert main(['run', str(path), '-q', '-o', str(out)]) == 1
    s = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    assert s['result_format'] == 'thermal.steady2d-result-v2'
    invalid = model()
    invalid['physics']['heat1']['convection']['right']['h_w_m2k'] = -1.
    path.write_text(json.dumps(invalid), encoding='utf-8')
    assert main(['run', str(path), '-o', str(tmp_path/'invalid')]) == 2
    assert not (tmp_path/'invalid').exists()


@pytest.mark.parametrize('stage', ['solver', 'save'])
def test_public_cli_solver_and_save_errors_exit_one(tmp_path, monkeypatch, stage):
    path = tmp_path/'model.json'
    path.write_text(json.dumps(model()), encoding='utf-8')
    if stage == 'solver':
        import galerkin.thermal as engine
        def broken(*args, **kwargs):
            raise ValueError('injected solver failure')
        monkeypatch.setattr(engine, 'solve_steady_heat', broken)
    else:
        def broken(*args, **kwargs):
            raise OSError('injected save failure')
        monkeypatch.setattr(np, 'savez_compressed', broken)
    out = tmp_path/'failed'
    assert main(['run', str(path), '-q', '-o', str(out)]) == 1
    assert not out.exists()


@pytest.mark.parametrize('unit,factor', [('mm', 1000.), ('um', 1e6)])
@pytest.mark.parametrize('legacy', [False, True])
def test_result_scale_is_ready_at_return_and_caller_is_preserved(unit, factor, legacy):
    data = model(legacy=legacy)
    data['units']['length'] = unit
    data['geometry']['domain'] = {k: v*factor for k, v in data['geometry']['domain'].items()}
    doc = Document.from_dict(data)
    before = json.loads(json.dumps(doc.data))
    caller_scale = doc.scale.to_si(1., {'length': 1})
    result = run(doc, False)
    # Check before explicitly calling result.summary() or result.save().
    assert result.doc.scale.to_si(1., {'length': 1}) == caller_scale == 1./factor
    assert result.doc.data == before
    assert doc.data == before
    assert doc.scale.to_si(1., {'length': 1}) == caller_scale
    # Direct public construction isolates __post_init__ from run's final summary validation.
    clone = ThermalRunResult(doc, result.mesh, result.solution, result.dirichlet_node_ids,
                             result.dirichlet_temperature_k, result.diagnostics,
                             result.timings, result.log)
    assert clone.doc.scale.to_si(1., {'length': 1}) == caller_scale
    assert clone.doc.data == before


def test_removed_default_is_detected_before_validation_can_restore_it(tmp_path):
    result = run(Document.from_dict(model()), False)
    del result.doc.sole_physics()[1]['heat_source_w_m3']
    with pytest.raises(ValueError, match='document changed'):
        result.summary()
    assert 'heat_source_w_m3' not in result.doc.sole_physics()[1]
    with pytest.raises(ValueError, match='document changed'):
        result.save(tmp_path/'removed')
    assert not (tmp_path/'removed').exists()
