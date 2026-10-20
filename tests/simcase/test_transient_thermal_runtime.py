# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Adapter/history storage controls; no replacement for independent PDE gates."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from simcase.schema import Document, DocumentError
from simcase.transient_thermal import TransientThermalRunResult, run_transient_thermal as run
from simcase.examples import TRANSIENT_THERMAL_UNIFORM
from simcase.transient_thermal import _FIELD_SPEC
import simcase.transient_thermal as adapter
import simcase.thermal as storage


def document():
    data = copy.deepcopy(TRANSIENT_THERMAL_UNIFORM)
    data['mesh']['subdivisions'] = [2, 2]
    return Document.from_dict(data)


def test_uniform_history_and_independent_heat_accounting():
    r = run(document(), verbose=False)
    assert isinstance(r, TransientThermalRunResult)
    t = r.time_s
    np.testing.assert_allclose(r.temperature_k, np.broadcast_to(300+2*t[:, None], (3, 9)),
                               rtol=0, atol=1e-10)
    np.testing.assert_allclose(r.heat_flux_w_m2, 0, rtol=0, atol=1e-10)
    np.testing.assert_allclose(r.source_load_w_per_m.sum(1), 8, rtol=0, atol=1e-10)
    np.testing.assert_allclose(r.storage_rate_w_per_m.sum(1), 8, rtol=0, atol=1e-10)
    assert r.dirichlet_temperatures_k.shape == (3, 0)
    assert r.reaction_w_per_m.shape == r.residual_w_per_m.shape == (2, 9)
    assert not r.reaction_w_per_m.any()
    # Domain area1, c4: analytic H and V, independent of adapter diagnostics.
    np.testing.assert_allclose(r.heat_content_j_per_m, 4*(300+2*t), rtol=0, atol=1e-9)
    np.testing.assert_allclose(r.quadratic_functional_jk_per_m, 2*(300+2*t)**2,
                               rtol=0, atol=1e-8)


def test_sampled_boundary_and_affine_initial_are_not_projected():
    d = document()
    p = d.sole_physics()[1]
    p['dirichlet_temperature_k'] = {side: {'values_k': [300., 300.2, 300.6]}
                                    for side in ('left', 'right')}
    r = run(d, verbose=False)
    np.testing.assert_allclose(r.temperature_k, 300+2*r.time_s[:, None]+np.zeros((3, 9)),
                               rtol=0, atol=1e-10)
    assert len(r.dirichlet_node_ids) == 6
    np.testing.assert_allclose(r.residual_w_per_m, 0, rtol=0, atol=1e-10)
    d = document()
    p = d.sole_physics()[1]
    p.update(initial_temperature_k={'type': 'affine', 'origin_temperature_k': 300.,
                                    'gradient_k_per_m': [10., 0.]}, heat_source_w_m3=0.,
             dirichlet_temperature_k={'left': 300., 'right': 310.})
    r = run(d, verbose=False)
    expected = 300+10*r.nodes_m[:, 0]
    np.testing.assert_allclose(r.temperature_k, np.broadcast_to(expected, (3, 9)), rtol=0, atol=1e-10)
    np.testing.assert_allclose(r.heat_flux_w_m2,
                               np.broadcast_to([-25., 0.], (3, 8, 2)), rtol=0, atol=1e-9)


def test_explicit_si_length_conversion_and_negative_kelvin():
    d = document()
    d.sole_physics()[1].update(initial_temperature_k=-10., heat_source_w_m3=-8.)
    a = run(d, verbose=False)
    converted = d.copy()
    converted.data['units']['length'] = 'mm'
    for key in converted.domain:
        converted.domain[key] *= 1000
    b = run(converted, verbose=False)
    for key in _FIELD_SPEC:
        np.testing.assert_allclose(getattr(a, key), getattr(b, key), rtol=0, atol=1e-9)
    assert a.temperature_k[-1].max() < -10


def test_document_and_input_lifetime_and_no_em_attributes():
    d = document()
    r = run(d, verbose=False)
    d.data['study']['time_s'][1] = 99
    d.domain['xmax'] = 99
    assert r.doc['study']['time_s'][1] == .1
    assert r.doc.domain['xmax'] == 1
    for key in _FIELD_SPEC:
        a = getattr(r, key)
        assert not a.flags.writeable
    for attr in ('neff', 'wavelength', 'group_index'):
        assert not hasattr(r, attr)


def test_public_dispatch_and_stage_refusals():
    from simcase import run as public_run, build_mesh, solve_point
    r = public_run(document(), verbose=False)
    assert isinstance(r, TransientThermalRunResult)
    with pytest.raises(DocumentError, match='thermal.transient2d'):
        build_mesh(r.doc)
    with pytest.raises(DocumentError, match='thermal.transient2d'):
        solve_point(None, r.doc.sole_physics()[1])


@pytest.mark.parametrize('fields', [True, False])
def test_npz_no_pickle_and_json_shape_unit_time_metadata(tmp_path, fields):
    d = document()
    d.data['results']['save_fields'] = fields
    r = run(d, verbose=False)
    out = r.save(tmp_path/'fresh')
    meta = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    assert not (out/'.incomplete').exists()
    assert meta['result_format'] == 'thermal.transient2d-result-v1'
    assert meta['field_layout'] == 'thermal2d-transient-p1-node-cell-v1'
    assert meta['field_shapes']['reaction_w_per_m'] == [2, 9]
    assert meta['field_time_axes']['reaction_w_per_m'] == 'time_s[1:]'
    assert meta['field_time_axes']['temperature_k'] == 'time_s'
    assert meta['field_units']['heat_content_j_per_m'] == 'J/m'
    assert meta['field_units']['quadratic_functional_jk_per_m'] == 'J K/m'
    assert meta['rate_time_s'] == [.1, .3]
    assert (out/'fields.npz').exists() == fields
    if fields:
        with np.load(out/'fields.npz', allow_pickle=False) as archive:
            for key in _FIELD_SPEC:
                np.testing.assert_array_equal(archive[key], getattr(r, key))
                assert not archive[key].dtype.hasobject
                assert list(archive[key].shape) == meta['field_shapes'][key]
            assert json.loads(str(archive['metadata_json'])) == meta


@pytest.mark.parametrize('key', list(_FIELD_SPEC))
def test_nonfinite_public_result_is_refused_without_complete_output(tmp_path, key):
    d = document()
    d.sole_physics()[1]['dirichlet_temperature_k'] = {'left': 300.}
    r = run(d, verbose=False)
    bad = getattr(r.solution, key).astype(float).copy()
    bad.flat[0] = np.nan
    object.__setattr__(r.solution, key, bad)
    with pytest.raises(ValueError, match='finite'):
        r.save(tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


@pytest.mark.parametrize('key', list(_FIELD_SPEC))
def test_wrong_shape_is_refused_even_without_fields(tmp_path, key):
    d = document()
    d.data['results']['save_fields'] = False
    r = run(d, verbose=False)
    object.__setattr__(r.solution, key, np.zeros((1, 1, 1)))
    with pytest.raises(ValueError):
        r.save(tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


@pytest.mark.parametrize('kind', ['file', 'empty', 'nonempty', 'symlink'])
def test_existing_targets_unchanged(tmp_path, kind):
    out = tmp_path/'target'
    if kind == 'file':
        out.write_bytes(b'foreign')
    elif kind == 'symlink':
        out.symlink_to(tmp_path/'missing')
    else:
        out.mkdir()
        if kind == 'nonempty':
            (out/'foreign.txt').write_bytes(b'foreign')
    before = out.lstat()
    with pytest.raises(FileExistsError):
        run(document(), verbose=False).save(out)
    after = out.lstat()
    assert (before.st_dev, before.st_ino, before.st_mode) == (after.st_dev, after.st_ino, after.st_mode)
    if kind == 'file':
        assert out.read_bytes() == b'foreign'
    elif kind == 'nonempty':
        assert (out/'foreign.txt').read_bytes() == b'foreign'
    elif kind == 'symlink':
        assert out.readlink() == tmp_path/'missing'


@pytest.mark.parametrize('mutation', ['plain', 'foreign', 'replacement', 'removed_required'])
def test_partial_failure_and_required_owned_artifacts(tmp_path, monkeypatch, mutation):
    out = tmp_path/'target'
    original = storage._OwnedOutput.write
    reached = []
    def inject(self, name, writer):
        original(self, name, writer)
        if name != 'fields.npz':
            return
        reached.append(name)
        if mutation == 'foreign':
            (out/'foreign.txt').write_bytes(b'foreign')
        elif mutation == 'replacement':
            # Close destination path handles exactly as a caller would: helper
            # pins are independent; on Windows actual replacement must succeed.
            replacement = tmp_path/'replacement'
            replacement.write_bytes(b'replacement')
            replacement.replace(out/'model.json')
        elif mutation == 'removed_required':
            (out/'model.json').unlink()
            return  # finish must detect missing required artifact itself
        raise OSError('injected after transient NPZ')
    monkeypatch.setattr(storage._OwnedOutput, 'write', inject)
    expected = 'unexpected or replaced' if mutation == 'removed_required' else 'injected after transient NPZ'
    with pytest.raises(OSError, match=expected):
        run(document(), verbose=False).save(out)
    assert reached == ['fields.npz']
    if mutation == 'foreign':
        assert (out/'foreign.txt').read_bytes() == b'foreign'
        assert (out/'.incomplete').exists()
    elif mutation == 'replacement':
        assert (out/'model.json').read_bytes() == b'replacement'
        assert (out/'.incomplete').exists()
    else:
        assert not out.exists()


def test_two_writers_one_fresh_target(tmp_path):
    r = run(document(), verbose=False)
    out = tmp_path/'shared'
    def save():
        try:
            r.save(out)
            return 'success'
        except FileExistsError:
            return 'loser'
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: save(), range(2)))
    assert sorted(statuses) == ['loser', 'success']
    assert (out/'summary.json').exists() and (out/'fields.npz').exists()
    assert not (out/'.incomplete').exists()


def test_finite_json_failure_and_cli_exit_codes(tmp_path, monkeypatch, capsys):
    from simcase.cli import main
    model = tmp_path/'model.json'
    model.write_text(json.dumps(document().data), encoding='utf-8')
    assert main(['validate', str(model)]) == 0
    assert main(['run', str(model), '-o', str(tmp_path/'ok'), '-q']) == 0
    # Preflight must stop before solving on reuse.
    monkeypatch.setattr('simcase.cli.run', lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not solve')))
    assert main(['run', str(model), '-o', str(tmp_path/'ok'), '-q']) == 1
    r = run(document(), verbose=False)
    r.timings['bad'] = float('nan')
    monkeypatch.setattr('simcase.cli.run', lambda *a, **k: r)
    assert main(['run', str(model), '-o', str(tmp_path/'bad'), '-q']) == 1
    assert not (tmp_path/'bad').exists()
    data = document().data
    data['study']['time_s'] = [0, 0]
    model.write_text(json.dumps(data), encoding='utf-8')
    assert main(['run', str(model), '-o', str(tmp_path/'invalid'), '-q']) == 2
    assert not (tmp_path/'invalid').exists()
    assert 'error:' in capsys.readouterr().err


@pytest.mark.parametrize('path,value', [
    ('name', 'Relabelled result'),
    ('units.length', 'mm'),
    ('geometry.domain.xmax', 2.),
    ('mesh.subdivisions', [3, 2]),
    ('physics.heat1.initial_temperature_k', 301.),
    ('physics.heat1.dirichlet_temperature_k', {'left': {'values_k': [300., 301., 302.]}}),
    ('physics.heat1.heat_source_w_m3', 9.),
    ('study.time_s', [0., .2, .4]),
    ('results.save_fields', False),
])
def test_result_document_changes_cannot_relabel_old_histories(tmp_path, path, value):
    r = run(document(), verbose=False)
    r.doc.set_path(path, copy.deepcopy(value))
    # These are valid standalone new models; validation alone is insufficient.
    r.doc.validate()
    with pytest.raises(ValueError, match='document changed after run'):
        r.summary()
    with pytest.raises(ValueError, match='document changed after run'):
        r.save(tmp_path/'changed')
    assert not (tmp_path/'changed').exists()


def test_original_input_mutation_and_mapping_order_are_not_result_mutation(tmp_path):
    d = document()
    r = run(d, verbose=False)
    d.sole_physics()[1]['heat_source_w_m3'] = 9.
    d.data['name'] = 'New caller model'
    # JSON mapping order is irrelevant, while its captured values stay fixed.
    r.doc.data = dict(reversed(list(r.doc.data.items())))
    out = r.save(tmp_path/'original')
    saved = json.loads((out/'model.json').read_text(encoding='utf-8'))
    assert saved['physics']['heat1']['heat_source_w_m3'] == 8.
    assert saved['name'] == TRANSIENT_THERMAL_UNIFORM['name']
    with np.load(out/'fields.npz', allow_pickle=False) as arrays:
        np.testing.assert_allclose(arrays['source_load_w_per_m'].sum(1), 8.,
                                   rtol=0, atol=1e-10)


@pytest.mark.parametrize('save_fields', [False, True])
def test_derived_json_overflow_leaves_no_completed_output(tmp_path, save_fields):
    d = document()
    d.data['results']['save_fields'] = save_fields
    r = run(d, verbose=False)
    # Each raw entry is finite but its nodal sum overflows.
    huge = np.full_like(r.solution.source_load_w_per_m, np.finfo(float).max)
    object.__setattr__(r.solution, 'source_load_w_per_m', huge)
    with np.errstate(over='ignore', invalid='ignore'):
        with pytest.raises(ValueError):
            r.save(tmp_path/'overflow')
    assert not (tmp_path/'overflow').exists()
