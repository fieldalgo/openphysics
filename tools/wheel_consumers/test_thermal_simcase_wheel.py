# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Installed headless heat contracts; independent closed forms, not convergence acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import simcase
import simcase.thermal as adapter
import galerkin.thermal as heat
from simcase import Document, DocumentError, ThermalRunResult, run


def model(source=0., unit='mm', fields=True):
    factor = {'m': .001, 'mm': 1., 'um': 1000.}[unit]
    return {'openphysics': '0.3', 'name': 'Installed independent heat consumer',
            'geometry': {'length_unit': unit, 'depth': None,
                         'domain': {'xmin': 0., 'xmax': 30.*factor, 'ymin': 0., 'ymax': 20.*factor}},
            'materials': {}, 'physics': {'heat1': {'type': 'thermal.steady2d',
                'thermal_conductivity': '12.5 W/(m K)', 'heat_source_density': f'{float(source)!r} W/m^3',
                'prescribed_temperature': {'left': '280 K', 'right': '315 K'}}},
            'mesh': {'subdivision_count': [32, 16]}, 'study': {'type': 'single'},
            'results': {'save_fields': fields, 'plots': False}}


def close(actual, expected, scale, atol=1e-10):
    assert np.isfinite(scale) and scale > 0
    np.testing.assert_allclose(np.asarray(actual)/scale, np.asarray(expected)/scale,
                               rtol=1e-10, atol=atol)


def check_physics(result, source):
    """Independent SI rectangle, analytic temperature/flux and heat resultants."""
    L, H, k, delta = .03, .02, 12.5, 35.
    nodes, cells = result.node_coordinates, result.triangles
    assert nodes.shape == (33*17, 2) and cells.shape == (32*16*2, 3)
    x = nodes[:, 0]
    close(nodes.min(axis=0), [0., 0.], L)
    close(nodes.max(axis=0), [L, H], L)
    expected = 280.+delta*x/L+source*x*(L-x)/(2*k)
    # P1 mixed-source fields approximate a quadratic. Bound the error by the
    # analytic source curvature times the squared cell diameter, not summary data.
    h = np.hypot(L/32, H/16)
    error = np.max(np.abs(result.temperature-expected))
    assert error <= abs(source)*h*h/k+1e-10*delta
    xc = nodes[cells].mean(axis=1)[:, 0]
    flux = np.column_stack([-k*delta/L-source*(L/2-xc), np.zeros(len(cells))])
    assert np.max(np.abs(result.heat_flux-flux)) <= abs(source)*h+1e-10*k*delta/L
    left = np.flatnonzero(np.isclose(x, 0., rtol=0., atol=1e-15))
    right = np.flatnonzero(np.isclose(x, L, rtol=0., atol=1e-15))
    # reaction is heat into the body. Outward is its negative; both boundary
    # resultants are nonzero even for the zero-source slab.
    expected_reaction = [-k*delta*H/L-source*L*H/2,
                          k*delta*H/L-source*L*H/2]
    scale = k*delta*H/L+abs(source)*L*H
    close([result.reaction_heat_rate_per_depth[left].sum(), result.reaction_heat_rate_per_depth[right].sum()],
          expected_reaction, scale)
    close(result.generated_heat_rate_per_depth.sum(), source*L*H, scale)
    close(-result.reaction_heat_rate_per_depth.sum(), source*L*H, scale)
    close(result.reaction_heat_rate_per_depth.sum()+result.generated_heat_rate_per_depth.sum(), 0., scale)
    if source == 1e5:
        close(-result.reaction_heat_rate_per_depth.sum(), 60., 60.)


def cli(*args):
    return subprocess.run([sys.executable, '-I', '-m', 'simcase', *map(str, args)],
                          cwd=Path(__file__).resolve().parent,
                          text=True, capture_output=True)


def test_thermal_simcase_module_origins():
    for module in (simcase, adapter, heat):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())


@pytest.mark.parametrize('source', [0., 1e5, -1e5])
def test_api_slab_and_signed_mixed_closed_forms(source):
    result = run(Document.from_dict(model(source)), False)
    assert isinstance(result, ThermalRunResult)
    check_physics(result, source)


@pytest.mark.parametrize('unit', ['m', 'mm', 'um'])
def test_geometry_unit_invariance_against_independent_si(unit):
    result = run(Document.from_dict(model(1e5, unit)), False)
    check_physics(result, 1e5)


def test_numeric_npz_versions_units_shapes_and_physical_sign(tmp_path):
    result = run(Document.from_dict(model(1e5)), False)
    result.save(tmp_path/'fresh')
    check_physics(result, 1e5)
    with np.load(tmp_path/'fresh/fields.npz', allow_pickle=False) as arrays:
        assert all(not arrays[name].dtype.hasobject for name in arrays.files)
        assert str(arrays['result_format']) == 'thermal.steady2d-result-v3'
        assert str(arrays['field_layout']) == 'thermal2d-p1-node-cell-v2'
        assert 'mesh_length_unit' not in arrays.files      # coordinates are SI; field_units carries m
        shapes = {'node_coordinates': (561, 2), 'triangles': (1024, 3),
                  'temperature': (561,), 'heat_flux': (1024, 2),
                  'generated_heat_rate_per_depth': (561,), 'reaction_heat_rate_per_depth': (561,),
                  'residual_heat_rate_per_depth': (561,), 'prescribed_node_ids': (34,),
                  'prescribed_temperature': (34,)}
        for name, shape in shapes.items():
            assert arrays[name].shape == shape
            assert arrays[name].dtype.kind in 'iuf'
            assert np.all(np.isfinite(arrays[name]))
        assert arrays['triangles'].dtype.kind in 'iu'
        fixed = arrays['prescribed_node_ids']
        assert fixed.dtype.kind in 'iu' and np.all(np.diff(fixed) > 0)
        close(-arrays['reaction_heat_rate_per_depth'][fixed].sum(), 60., 60.)
        close(arrays['generated_heat_rate_per_depth'].sum(), 60., 60.)
        x = arrays['node_coordinates'][:, 0]
        analytic = 280.+35*x/.03+1e5*x*(.03-x)/(2*12.5)
        assert np.max(abs(arrays['temperature']-analytic)) < 1e5*np.hypot(.03/32,.02/16)**2/12.5
        metadata = json.loads(str(arrays['metadata_json']))
        assert metadata['field_units'] == {'node_coordinates': 'm', 'prescribed_temperature': 'K',
            'temperature': 'K', 'heat_flux': 'W/m^2', 'generated_heat_rate_per_depth': 'W/m',
            'reaction_heat_rate_per_depth': 'W/m', 'residual_heat_rate_per_depth': 'W/m'}
        for name in ('temperature', 'heat_flux', 'generated_heat_rate_per_depth', 'reaction_heat_rate_per_depth', 'residual_heat_rate_per_depth'):
            assert metadata['field_shapes'][name] == list(shapes[name])
        assert metadata['field_locations']['temperature'] == 'nodes'
        assert metadata['field_locations']['heat_flux'] == 'triangle_centroids'
    assert not (tmp_path/'fresh/.incomplete').exists()


@pytest.mark.parametrize('reverse', [False, True])
def test_equal_corner_is_unique_and_conflict_is_rejected(reverse):
    data = model()
    data['mesh']['subdivision_count'] = [4, 3]
    pairs = [('left', 300.), ('top', 300.)]
    if reverse:
        pairs.reverse()
    data['physics']['heat1']['prescribed_temperature'] = {side: f'{v!r} K' for side, v in pairs}
    r = run(Document.from_dict(data), False)
    assert len(r.prescribed_node_ids) == 4+5-1
    assert len(np.unique(r.prescribed_node_ids)) == 8
    close(r.temperature, 300., 300.)
    data['physics']['heat1']['prescribed_temperature']['top'] = '301 K'
    with pytest.raises(DocumentError, match='corner'):
        Document.from_dict(data)


def test_fields_disabled_retains_finite_summary(tmp_path):
    r = run(Document.from_dict(model(1e5, fields=False)), False)
    r.save(tmp_path/'fresh')
    assert not (tmp_path/'fresh/fields.npz').exists()
    summary = json.loads((tmp_path/'fresh/summary.json').read_text(),
                         parse_constant=lambda s: pytest.fail(f'nonfinite JSON {s}'))
    assert summary['result_format'] == 'thermal.steady2d-result-v3'
    close(summary['outward_heat_rate_per_depth']['value'], 60., 60.)
    close(summary['generated_heat_rate_per_depth']['value'], 60., 60.)


@pytest.mark.parametrize('kind', ['directory', 'file', 'dangling_symlink'])
def test_api_and_cli_preserve_existing_target(tmp_path, kind):
    target = tmp_path/'existing'
    if kind == 'directory':
        target.mkdir()
        (target/'sentinel').write_bytes(b'keep')
    elif kind == 'file':
        target.write_bytes(b'keep')
    else:
        target.symlink_to(tmp_path/'absent')
        original_link_text = os.readlink(target)
    r = run(Document.from_dict(model()), False)
    with pytest.raises(FileExistsError):
        r.save(target)
    path = tmp_path/'model.json'
    path.write_text(json.dumps(model()))
    completed = cli('run', path, '-o', target, '-q')
    assert completed.returncode == 1, completed.stderr
    if kind == 'directory':
        assert list(target.iterdir()) == [target/'sentinel']
        assert (target/'sentinel').read_bytes() == b'keep'
    elif kind == 'file':
        assert target.read_bytes() == b'keep'
    else:
        assert target.is_symlink() and os.readlink(target) == original_link_text
        assert not (tmp_path/'absent').exists()


def test_cli_success_and_invalid_plots_exit_codes(tmp_path):
    path = tmp_path/'model.json'
    path.write_text(json.dumps(model(1e5)))
    assert cli('validate', path).returncode == 0
    completed = cli('run', path, '-o', tmp_path/'fresh', '-q')
    assert completed.returncode == 0, completed.stderr
    with np.load(tmp_path/'fresh/fields.npz', allow_pickle=False) as arrays:
        close(-arrays['reaction_heat_rate_per_depth'].sum(), 60., 60.)
    invalid = model()
    invalid['results']['plots'] = True
    with pytest.raises(DocumentError, match='plots'):
        Document.from_dict(invalid)
    path.write_text(json.dumps(invalid))
    for command in ('validate', 'run'):
        completed = cli(command, path)
        assert completed.returncode == 2, completed.stderr


@pytest.mark.parametrize('filename,source', [('thermal_slab.json', 0.), ('thermal_mixed.json', 1e5)])
def test_example_json_api_and_cli(tmp_path, filename, source):
    path = Path(__file__).resolve().parents[1]/'examples'/filename
    doc = Document.load(path)
    assert doc['geometry']['length_unit'] == 'mm'
    check_physics(run(doc, False), source)
    completed = cli('run', path, '-o', tmp_path/'fresh', '-q')
    assert completed.returncode == 0, completed.stderr
    with np.load(tmp_path/'fresh/fields.npz', allow_pickle=False) as arrays:
        scale = 12.5*35*.02/.03+abs(source)*.03*.02
        close(-arrays['reaction_heat_rate_per_depth'].sum(), source*.03*.02, scale)
