# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Installed CLI/SI/save and failure checks, also run on all three supported OSes."""
import json
import subprocess
import sys

import numpy as np
import pytest


def cli(*args):
    return subprocess.run([sys.executable, '-I', '-m', 'simcase', *map(str,args)],
                          capture_output=True, text=True, encoding='utf-8')


@pytest.mark.parametrize('kind', ['electric_rectangle', 'joule_rectangle', 'joule_temperature'])
def test_installed_cli(kind,tmp_path):
    doc = cli('example',kind)
    assert doc.returncode == 0,doc.stderr
    source = tmp_path/'model.json';source.write_text(doc.stdout,encoding='utf-8')
    out = tmp_path/'result'
    solve = cli('run',source,'-o',out,'-q')
    assert solve.returncode == 0,solve.stderr
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'converged'
    with np.load(out/'fields.npz',allow_pickle=False) as f:
        assert f['nodes_m'].shape == (175,2)
        assert np.isfinite(f['potential_v']).all()
        if kind == 'electric_rectangle':
            np.testing.assert_allclose(f['potential_v'],1-f['nodes_m'][:,0],atol=2e-12)
            assert summary['diagnostics']['joule_power_w_per_m'] == pytest.approx(.4,rel=1e-12)
        else:
            assert 300 < f['temperature_k'].max() < 300.251
    before=(out/'summary.json').read_bytes()
    assert cli('run',source,'-o',out).returncode == 1
    assert (out/'summary.json').read_bytes() == before


def test_installed_failure(tmp_path):
    doc=json.loads(cli('example','joule_temperature').stdout)
    doc['physics']['electric']['iteration'].update(max_iterations=1,relaxation=1e-12)
    source=tmp_path/'failure.json';source.write_text(json.dumps(doc),encoding='utf-8')
    out=tmp_path/'out'
    failed=cli('run',source,'-o',out,'-q')
    assert failed.returncode == 1
    assert not out.exists()
    evidence=json.loads(failed.stderr)
    assert evidence['status']=='failed' and len(evidence['iterations'])==1
