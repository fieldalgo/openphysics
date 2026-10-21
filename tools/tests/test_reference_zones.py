# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reference import boundaries in tracked temporary repositories (P1-P16)."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import check_reference_zones as zones
sys.path.pop(0)


def repo(tmp_path, files, *, listed=('tests/test_probe.py', 'studies/*'), spdx='GPL-3.0-only'):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '.'], check=True)
    inv = json.loads((ROOT / 'tools/third_party_licenses.json').read_text())
    inv['external_tools'] = {'probe': {'spdx': spdx, 'reference': {
        'modules': ['probe'], 'imported_by': list(listed), 'mode': ['stored']}}}
    return inv


@pytest.mark.parametrize('path', ['packages/demo/x.py', 'examples/x.py', 'tools/x.py',
                                 'tests/conftest.py', 'tests/demo/crosscheck.py'])
def test_p1_p5_forbidden_zones(tmp_path, path):
    inv = repo(tmp_path, {path: 'def f():\n import probe\n'}, listed=(path,))
    assert any('non-permissive import' in e for e in zones.check(tmp_path, inv))


@pytest.mark.parametrize('code', ['import probe', 'try:\n import probe\nexcept ImportError:\n pass',
                                 'import pytest\npytest.importorskip("probe")',
                                 'import importlib as il\nil.import_module("probe")',
                                 'class C:\n import probe',
                                 'def f(x=__import__("probe")):\n pass'])
def test_p6_p7_eager_imports(tmp_path, code):
    inv = repo(tmp_path, {'tests/test_probe.py': code})
    assert any('must be lazy' in e for e in zones.check(tmp_path, inv))


@pytest.mark.parametrize('code', ['import probe', 'import importlib\nimportlib.import_module("probe")',
                                 'from importlib import import_module as load\nload("probe")',
                                 'require_tool("probe")', '__import__("probe")'])
def test_p8_p9_unlisted_lazy(tmp_path, code):
    inv = repo(tmp_path, {'tests/test_other.py': 'def f():\n ' + code.replace('\n', '\n ') + '\n'})
    assert any('importer not listed' in e for e in zones.check(tmp_path, inv))


def test_p10_eager_chain_and_p16_main_guard(tmp_path):
    files = {'tests/test_probe.py': 'from studies import generate',
             'studies/generate.py': 'import probe'}
    inv = repo(tmp_path, files)
    assert any('eager import reaches' in e for e in zones.check(tmp_path, inv))
    (tmp_path / 'studies/generate.py').write_text('if __name__ == "__main__":\n import probe\n')
    assert zones.check(tmp_path, inv) == []


def test_p11_unclassified(tmp_path):
    inv = repo(tmp_path, {'surprise.py': 'x = 1'})
    assert any('unclassified' in e for e in zones.check(tmp_path, inv))


@pytest.mark.parametrize('license', ['SSPL-1.0', 'SSPL-1.0+', 'LicenseRef-SSPL'])
def test_p12_forbidden_family(tmp_path, license):
    inv = repo(tmp_path, {'studies/x.py': 'import probe'}, spdx=license)
    assert any('forbidden license' in e for e in zones.check(tmp_path, inv))


@pytest.mark.parametrize('dependency', ['galerkin[crosscheck]', 'bridge[export]'])
def test_p13_transitive_extra(tmp_path, dependency):
    files = {
        'packages/openphysics/pyproject.toml': '[project]\nname="openphysics"\n[project.optional-dependencies]\nstudio=["' + dependency + '"]',
        'packages/bridge/pyproject.toml': '[project]\nname="bridge"\n[project.optional-dependencies]\nexport=["galerkin[crosscheck]"]',
        'packages/galerkin/pyproject.toml': '[project]\nname="galerkin"\n[project.optional-dependencies]\ncrosscheck=["probe"]',
    }
    inv = repo(tmp_path, files)
    assert any('non-test dependency reaches test extra' in e for e in zones.check(tmp_path, inv))
    assert any('reference tool reachable' in e for e in zones.check(tmp_path, inv))


def test_p14_untracked_and_p15_listed_lazy(tmp_path):
    inv = repo(tmp_path, {'tests/test_probe.py': 'def f():\n import probe\n'})
    path = tmp_path / 'tests/venv/gpl.py'
    path.parent.mkdir(parents=True)
    path.write_text('import probe')
    assert zones.check(tmp_path, inv) == []


def test_current_tree():
    assert zones.check() == []


def test_first_party_scan_ignores_untracked_and_sees_tracked(tmp_path, monkeypatch):
    import check_licenses
    inv = repo(tmp_path, {'tests/test_probe.py': 'import probe'})
    (tmp_path / 'tests/untracked.py').write_text('import hidden')
    monkeypatch.setattr(check_licenses, 'ROOT', tmp_path)
    assert check_licenses.first_party_imports({'probe'}) == ['tests/test_probe.py']
    assert check_licenses.first_party_imports({'hidden'}) == []


@pytest.mark.parametrize('row', ['', '| `probe` | live |', '| `probe` | stored |\n| `probe` | stored |'])
def test_mode_missing_wrong_or_duplicate(row):
    import check_licenses
    entry = {'probe': {'reference': {'mode': ['stored']}}}
    text = '| Tool | Mode |\n|---|---|\n' + row
    assert check_licenses.reference_docs_errors(text, entry, 'doc')
    assert check_licenses.reference_docs_errors('| Tool | Mode |\n|---|---|\n| `probe` | stored |', entry, 'doc') == []


def test_reference_mode_docs():
    import check_licenses
    inv = json.loads((ROOT / 'tools/third_party_licenses.json').read_text())
    entries = {**inv['distributions'], **inv['external_tools']}
    for doc in check_licenses.DOCS:
        assert check_licenses.reference_docs_errors(doc.read_text(), entries, str(doc)) == []


def test_local_relative_eager_chain(tmp_path):
    inv = repo(tmp_path, {'tests/test_probe.py': 'from . import helper',
                          'tests/helper.py': 'import probe'}, listed=('tests/helper.py',))
    assert any('eager import reaches' in e for e in zones.check(tmp_path, inv))
