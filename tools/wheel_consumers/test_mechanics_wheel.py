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
    assert summary['result_format'] == 'mechanics.elasticity2d-result-v1'
    assert summary['field_layout'] == 'mechanics2d-p1-v1' and summary['mesh_length_unit'] == 'm'
    assert not (out/'.incomplete').exists()
    with np.load(out/'fields.npz', allow_pickle=False) as f:
        nodes, u, stress = f['nodes_m'], f['displacement_m'], f['stress_pa']
        assert nodes.shape == (105, 2) and u.shape == (105, 2) and stress.shape == (160, 3)
        assert abs(nodes[:, 0].max()-.1) < 1e-15 and abs(nodes[:, 1].max()-.02) < 1e-15  # mm -> m
        # Uniaxial plane stress: u = (P/E x, -nu P/E y), sigma = (P, 0, 0), P = 1 MPa.
        np.testing.assert_allclose(u[:, 0], 1e6/200e9*nodes[:, 0], rtol=0, atol=1e-10*u.max())
        np.testing.assert_allclose(u[:, 1], -.3e6/200e9*nodes[:, 1], rtol=0, atol=1e-10*u.max())
        np.testing.assert_allclose(stress[:, 0], 1e6, rtol=1e-10, atol=0)
        np.testing.assert_allclose(stress[:, 1:], 0., rtol=0, atol=1e-10*1e6)
        assert json.loads(str(f['metadata_json'])) == summary
    assert summary['diagnostics']['applied_load_n_per_m'] == pytest.approx([1e6*.02, 0.], abs=1e-9)
    before = (out/'summary.json').read_bytes()
    assert cli('run', source, '-o', out).returncode == 1
    assert (out/'summary.json').read_bytes() == before


def test_installed_refuses_a_hinged_plate(tmp_path):
    doc = json.loads(cli('example', 'elastic_plate').stdout)
    doc['physics']['plate']['displacement_m'] = {'bottom': {'x': 0.}, 'left': {'y': 0.}}
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
    mesh = meshio.read(export_fields(out/'fields.npz', tmp_path/'plate.vtu'))
    assert set(mesh.point_data) == {'displacement_m', 'load_n_per_m', 'reaction_n_per_m', 'residual_n_per_m'}
    assert set(mesh.cell_data) == {'exx', 'eyy', 'gxy', 'sxx_pa', 'syy_pa', 'sxy_pa'}
    np.testing.assert_allclose(mesh.cell_data['sxx_pa'][0], 1e6, rtol=1e-10)
