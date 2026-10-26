# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tests for the offline parts of tools/check_release_install.py.

The install itself needs built wheels and network access; the release workflow
runs it. These tests cover how it picks the local wheels and how it compares
PyPI's files with the build.
"""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_release_install", Path(__file__).resolve().parents[1] / "check_release_install.py")
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)

FILES = {f"{name.replace('-', '_')}-0.1.0{suffix}": f"{index:064x}"
         for index, (name, suffix) in enumerate(
             (name, suffix) for name in install.DISTRIBUTIONS
             for suffix in ("-py3-none-any.whl", ".tar.gz"))}


def wheels(directory, version="0.1.0", names=install.DISTRIBUTIONS):
    directory.mkdir(exist_ok=True)
    for name in names:
        (directory / f"{name.replace('-', '_')}-{version}-py3-none-any.whl").write_bytes(b"")
    return directory


def sums(path, files=FILES):
    path.write_text("".join(f"{digest}  {name}\n" for name, digest in files.items()), encoding="utf-8")
    return path


def test_local_requirements_name_every_wheel_by_url(tmp_path):
    version, requirements = install.local_requirements(wheels(tmp_path / "dist"))
    assert version == "0.1.0"
    assert len(requirements) == 8
    assert all(" @ file:" in r for r in requirements)
    assert [r for r in requirements if r.startswith("openphysics[studio,export,rii,sipi] @ ")]
    assert [r for r in requirements if r.startswith("galerkin-refsol @ ")]


def test_local_requirements_need_all_seven_at_one_version(tmp_path):
    with pytest.raises(SystemExit, match="expected one wheel"):
        install.local_requirements(wheels(tmp_path / "a", names=install.DISTRIBUTIONS[:-1]))
    directory = wheels(tmp_path / "b")
    (directory / "simcase-0.1.0-py3-none-any.whl").unlink()
    (directory / "simcase-0.1.1-py3-none-any.whl").write_bytes(b"")
    with pytest.raises(SystemExit, match="different versions"):
        install.local_requirements(directory)


def fake_pypi(monkeypatch, listed):
    def files(name, version):
        found = {f: d for f, d in listed.items() if f.startswith(name.replace("-", "_") + "-")}
        return found or None
    monkeypatch.setattr(install, "pypi_files", files)


def test_pypi_files_must_equal_the_build(tmp_path, monkeypatch):
    fake_pypi(monkeypatch, FILES)
    assert install.wait_for_pypi("0.1.0", sums(tmp_path / "SHA256SUMS"), 0) == dict(sorted(FILES.items()))


def test_pypi_hash_mismatch_fails(tmp_path, monkeypatch):
    changed = dict(FILES, **{"simcase-0.1.0.tar.gz": "f" * 64})
    fake_pypi(monkeypatch, changed)
    with pytest.raises(SystemExit, match=r"hash mismatch \['simcase-0.1.0.tar.gz'\]"):
        install.wait_for_pypi("0.1.0", sums(tmp_path / "SHA256SUMS"), 0)


def test_pypi_file_not_built_here_fails(tmp_path, monkeypatch):
    fake_pypi(monkeypatch, dict(FILES, **{"simcase-0.1.0-py3-none-win_amd64.whl": "e" * 64}))
    with pytest.raises(SystemExit, match="not built here"):
        install.wait_for_pypi("0.1.0", sums(tmp_path / "SHA256SUMS"), 0)


def test_missing_release_times_out(tmp_path, monkeypatch):
    fake_pypi(monkeypatch, {f: d for f, d in FILES.items() if not f.startswith("openphysics-")})
    with pytest.raises(SystemExit, match=r"PyPI does not list \['openphysics'\]"):
        install.wait_for_pypi("0.1.0", sums(tmp_path / "SHA256SUMS"), -1)
