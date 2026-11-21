# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Installed mechanics.elasticity2d CLI/SI/save, refusal and export checks, run on all three supported OSes."""
import json
import subprocess
import sys

import numpy as np
import pytest


def cli(*args):
    return subprocess.run([sys.executable, '-I', '-m', 'simcase', *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8')


def test_installed_uniaxial_plate_cli(tmp_path):
    doc = cli('example', 'elastic_plate')
    assert doc.returncode == 0, doc.stderr
    source = tmp_path/'model.json'
    source.write_text(doc.stdout, encoding='utf-8')
    assert cli('validate', source).returncode == 0
    out = tmp_path/'result'
    solve = cli('run', source, '-o', out, '-q')
    assert solve.returncode == 0, solve.stderr
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'solved'
    assert summary['result_format'] == 'mechanics.elasticity2d-result-v2'
    assert summary['field_layout'] == 'mechanics2d-p1-v2' and 'mesh_length_unit' not in summary
    assert not (out/'.incomplete').exists()
    with np.load(out/'fields.npz', allow_pickle=False) as f:
        nodes, u, stress = f['node_coordinates'], f['displacement'], f['stress']
        assert nodes.shape == (105, 2) and u.shape == (105, 2) and stress.shape == (160, 3)
        assert abs(nodes[:, 0].max()-.1) < 1e-15 and abs(nodes[:, 1].max()-.02) < 1e-15  # mm -> m
        # Uniaxial plane stress: u = (P/E x, -nu P/E y), sigma = (P, 0, 0), P = 1 MPa.
        np.testing.assert_allclose(u[:, 0], 1e6/200e9*nodes[:, 0], rtol=0, atol=1e-10*u.max())
        np.testing.assert_allclose(u[:, 1], -.3e6/200e9*nodes[:, 1], rtol=0, atol=1e-10*u.max())
        np.testing.assert_allclose(stress[:, 0], 1e6, rtol=1e-10, atol=0)
        np.testing.assert_allclose(stress[:, 1:], 0., rtol=0, atol=1e-10*1e6)
        assert json.loads(str(f['metadata_json'])) == summary
    assert summary['balance']['applied_force_per_depth'] == {'unit': 'N/m', 'values': pytest.approx([1e6*.02, 0.],
                                                                                                    abs=1e-9)}
    before = (out/'summary.json').read_bytes()
    assert cli('run', source, '-o', out).returncode == 1
    assert (out/'summary.json').read_bytes() == before


def test_installed_refuses_a_hinged_plate(tmp_path):
    doc = json.loads(cli('example', 'elastic_plate').stdout)
    doc['physics']['plate']['prescribed_displacement'] = {'bottom': {'x': '0 mm'}, 'left': {'y': '0 mm'}}
    source = tmp_path/'hinge.json'
    source.write_text(json.dumps(doc), encoding='utf-8')
    out = tmp_path/'out'
    refused = cli('run', source, '-o', out, '-q')
    assert refused.returncode == 2 and 'rigid-body' in refused.stderr
    assert not out.exists()


def test_installed_export_to_vtu(tmp_path):
    meshio = pytest.importorskip('meshio', reason="install simcase[export]")
    from simcase.export import export_fields
    doc = cli('example', 'elastic_plate')
    source = tmp_path/'model.json'
    source.write_text(doc.stdout, encoding='utf-8')
    out = tmp_path/'result'
    assert cli('run', source, '-o', out, '-q').returncode == 0
    from simcase.export import read_field_data
    vtu = export_fields(out/'fields.npz', tmp_path/'plate.vtu')
    mesh = meshio.read(vtu)
    assert set(mesh.point_data) == {'displacement', 'applied_force_per_depth', 'reaction_force_per_depth',
                                    'residual_force_per_depth'}
    assert set(mesh.cell_data) == {'strain_xx', 'strain_yy', 'engineering_shear_strain_xy',
                                   'stress_xx', 'stress_yy', 'stress_xy'}
    np.testing.assert_allclose(mesh.cell_data['stress_xx'][0], 1e6, rtol=1e-10)
    units = read_field_data(vtu)['units']
    assert units['displacement'] == 'm' and units['stress_xx'] == 'Pa' and units['strain_xx'] == '1'


def test_installed_thermoelastic_bar_cli(tmp_path):
    doc = cli('example', 'thermoelastic_bar')
    assert doc.returncode == 0, doc.stderr
    source = tmp_path/'bar.json'
    source.write_text(doc.stdout, encoding='utf-8')
    out = tmp_path/'result'
    solve = cli('run', source, '-o', out, '-q')
    assert solve.returncode == 0, solve.stderr
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'solved'
    assert summary['result_format'] == 'mechanics.thermoelastic2d-result-v2'
    assert summary['field_layout'] == 'thermoelastic2d-p1-v2'
    with np.load(out/'fields.npz', allow_pickle=False) as f:
        x = f['node_coordinates'][:, 0]
        # The P1 heat solve reproduces the linear temperature 293.15 K + 600 K/m x exactly.
        np.testing.assert_allclose(f['temperature'], 293.15+600.*x, rtol=0, atol=1e-9)
        # Confined bar: u_x = (1+nu) alpha (G x^2/2) with G = 600 K/m, within P1 discretization error.
        exact = 1.33*23e-6*300.*x*x
        assert np.max(abs(f['displacement'][:, 0]-exact)) < 5e-3*exact.max()
        assert f['stress'].shape == (160, 3) and f['stress_zz'].shape == (160,)
    assert abs(summary['balance']['heat_rate_imbalance_per_depth']['value']) < 1e-8
    assert cli('run', source, '-o', out).returncode == 1
