# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Keep introductory document code and independent physical controls reproducible."""
from pathlib import Path
import json
import re
import runpy
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGES = [
    *[f'packages/galerkin/{name}_tutorial.md' for name in
      ('thermal', 'joule', 'thermoelastic', 'transient', 'temperature_joule')],
    'packages/simcase/layered_wall_tutorial.md',
    'modeling/boundaries-units.md', 'results/saved-results.md',
    'validation/convergence.md', 'guide/troubleshooting.md',
    'modeling/materials.md', 'guide/execution-paths.md', 'results/waveguide-modes.md',
    'validation/slab-tutorial.md', 'results/thermoelastic-controls.md', 'results/run-records.md',
]


@pytest.mark.parametrize('page', PAGES)
def test_bilingual_worked_code_and_outputs_match(page):
    def blocks(path):
        return re.findall(r'^```(?:python|sh|bash|text|json)\n(.*?)^```',
                          path.read_text(encoding='utf-8'), re.M | re.S)
    assert blocks(ROOT / 'docs' / page) == blocks(ROOT / 'docs/locales/ko/pages' / page)


def test_first_heat_examples_match_independent_uniform_references():
    heat = runpy.run_path(str(ROOT / 'examples/galerkin/thermal_steady2d.py'))
    x = heat['mesh'].nodes[:, 0]
    np.testing.assert_allclose(heat['result'].temperature, 350. - 25. * x, rtol=0, atol=1e-10)
    np.testing.assert_allclose(heat['result'].heat_flux[:, 0], 300., rtol=0, atol=1e-8)
    joule = runpy.run_path(str(ROOT / 'examples/galerkin/joule_heating.py'))['result']
    assert joule.thermal.temperature.max() == pytest.approx(300.3, abs=1e-8, rel=0)
    assert joule.source_power_per_length == pytest.approx(6., abs=1e-8, rel=0)
    transient = runpy.run_path(str(ROOT / 'examples/galerkin/transient_heat_uniform.py'))['result']
    expected = np.broadcast_to(300. + 2. * transient.time_s[:, None], transient.temperature_k.shape)
    np.testing.assert_allclose(transient.temperature_k, expected, rtol=0, atol=1e-10)
    np.testing.assert_allclose(transient.heat_content_j_per_m - transient.heat_content_j_per_m[0],
                               8. * transient.time_s, rtol=0, atol=1e-10)


@pytest.mark.parametrize('size', [4., 2.])
def test_layered_wall_saved_fields_match_series_resistance(tmp_path, monkeypatch, size):
    output = tmp_path / 'wall'
    script = ROOT / 'examples/simcase/layered_wall.py'
    monkeypatch.setattr(sys, 'argv', [str(script), str(output), '--mesh-size-mm', str(size)])
    runpy.run_path(str(script), run_name='__main__')
    q = 50. / (.01 / 10. + .03 / 1. + 1. / 50.)
    with np.load(output / 'fields.npz', allow_pickle=False) as fields:
        x = fields['nodes_m'][:, 0]
        expected = 350. - q * (np.minimum(x, .01) / 10. + np.maximum(x - .01, 0.))
        np.testing.assert_allclose(fields['temperature_k'], expected, rtol=0, atol=1e-9)
        np.testing.assert_allclose(fields['heat_flux_w_m2'][:, 0], q, rtol=1e-9, atol=1e-8)
        np.testing.assert_allclose(fields['heat_flux_w_m2'][:, 1], 0., rtol=0, atol=1e-8)
        assert fields['reaction_w_per_m'].sum() == pytest.approx(q * .01, rel=1e-9)
        assert fields['convective_outward_w_per_m'].sum() == pytest.approx(q * .01, rel=1e-9)
    summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
    assert summary['regions']['left_layer']['material'] == 'high_k'
    assert summary['regions']['background']['material'] == 'low_k'


def test_saved_result_document_blocks_preserve_exported_fields(tmp_path, monkeypatch):
    meshio = pytest.importorskip('meshio')
    script = ROOT / 'examples/simcase/layered_wall.py'
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', [str(script), 'out/wall-base', '--export'])
    runpy.run_path(str(script), run_name='__main__')
    text = (ROOT / 'docs/results/saved-results.md').read_text(encoding='utf-8')
    namespace = {}
    for code in re.findall(r'^```python\n(.*?)^```', text, re.M | re.S):
        exec(compile(code, 'docs/results/saved-results.md', 'exec'), namespace)
    folder = tmp_path / 'out/wall-base'
    with np.load(folder / 'fields.npz', allow_pickle=False) as fields:
        for name in ('view.vtu', 'second-view.vtu'):
            viewed = meshio.read(folder / name)
            np.testing.assert_array_equal(viewed.points[:, :2], fields['nodes_m'])
            np.testing.assert_array_equal(viewed.point_data['temperature_k'], fields['temperature_k'])
            np.testing.assert_array_equal(viewed.cell_data['triangle_regions'][0], fields['triangle_regions'])
            np.testing.assert_array_equal(viewed.cell_data['heat_flux_w_m2'][0][:, :2], fields['heat_flux_w_m2'])


def test_material_selection_document_checks_source_and_range():
    import physmat
    namespace = _execute_document_python('modeling/materials.md')
    si = namespace['si']
    assert namespace['k_w_mk'] == 148.0
    assert si.properties['thermal_conductivity'].source
    assert si.source
    assert si.get('thermal_conductivity', T=400.0) == namespace['k_w_mk']
    with pytest.raises(physmat.OutOfRange):
        si.index(0.5)


def test_waveguide_interpretation_document_has_passive_loss():
    namespace = _execute_document_python('results/waveguide-modes.md')
    assert np.all(np.isfinite(namespace['neff']))
    assert np.all(namespace['neff'].imag < 0)
    assert np.all(np.asarray(namespace['loss_db_cm']) > 0)


def _execute_document_python(page):
    text = (ROOT / 'docs' / page).read_text(encoding='utf-8')
    namespace = {}
    for code in re.findall(r'^```python\n(.*?)^```', text, re.M | re.S):
        exec(compile(code, page, 'exec'), namespace)
    return namespace


def test_slab_tutorial_separates_mesh_and_window_errors():
    example = runpy.run_path(str(ROOT / 'examples/galerkin/slab_convergence.py'))
    reference, rows = example['main']()
    assert reference == pytest.approx(2.851738987, abs=5e-10)
    mesh_errors = [row[4] for row in rows if row[0] == 'mesh']
    assert all(3.5 < a / b < 4.5 for a, b in zip(mesh_errors, mesh_errors[1:]))
    window_errors = [row[4] for row in rows if row[0] == 'window']
    assert window_errors[0] > 100 * window_errors[-1]
    assert window_errors[-1] < 1e-4


def test_thermoelastic_controls_match_uniform_3d_reductions():
    example = runpy.run_path(str(ROOT / 'examples/galerkin/thermoelastic_controls.py'))
    mesh, results = example['main']()
    a, young, nu = 12e-6 * 20, 70e9, .3
    for name, factor, inplane, zz, energy in (
        ('free_plane_stress', a, 0., 0., 0.),
        ('free_plane_strain', (1 + nu) * a, 0., -young * a, .5 * young * a*a),
        ('blocked_plane_strain', 0., -young*a/(1-2*nu),
         -young*a/(1-2*nu), 1.5*young*a*a/(1-2*nu)),
    ):
        r = results[name]
        np.testing.assert_allclose(r.displacement, factor * mesh.nodes, atol=1e-14, rtol=0)
        np.testing.assert_allclose(r.stress[:, :2], inplane, atol=1e-5, rtol=0)
        np.testing.assert_allclose(r.stress[:, 2], 0., atol=1e-5, rtol=0)
        np.testing.assert_allclose(r.sigma_zz, zz, atol=1e-5, rtol=0)
        assert r.physical_elastic_energy == pytest.approx(energy, abs=1e-8, rel=1e-12)
        np.testing.assert_allclose(r.reaction.sum(axis=0), 0., atol=1e-5, rtol=0)
        moment = np.sum(mesh.nodes[:, 0]*r.reaction[:, 1] - mesh.nodes[:, 1]*r.reaction[:, 0])
        assert abs(moment) < 1e-5
    assert np.linalg.norm(results['blocked_plane_strain'].reaction) > 1e6


def test_run_record_preserves_inputs_and_detects_changed_output(tmp_path, monkeypatch):
    script = ROOT / 'examples/simcase/record_wall_run.py'
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', [str(script), 'out/wall-recorded'])
    runpy.run_path(str(script), run_name='__main__')
    folder = tmp_path / 'out/wall-recorded'
    assert (folder / 'input.json').read_bytes() == (script.parent / 'layered_wall.json').read_bytes()
    record = json.loads((folder / 'run-record.json').read_text())
    assert record['convergence'] == 'not_checked'
    assert record['package_versions']['simcase']
    assert 'run-record.json' not in record['sha256']
    _execute_document_python('results/run-records.md')
    with (folder / 'summary.json').open('a') as stream:
        stream.write('\n')
    with pytest.raises(ValueError, match='Changed result file: summary.json'):
        _execute_document_python('results/run-records.md')
