# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tests for the --shard parts of tools/run_installed_tests.py.

The four installed-test jobs must together run every test file under tests/
once, and each part's result check must require results from its own files
only.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location("run_installed_tests", ROOT / "tools" / "run_installed_tests.py")
installed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installed)


def junit(path, classnames, skipped=()):
    cases = "".join(f'<testcase classname="{name}" name="test_a" time="0.1"/>' for name in classnames)
    cases += "".join(f'<testcase classname="{name}" name="test_s" time="0"><skipped/></testcase>'
                     for name in skipped)
    path.write_text(f'<testsuites><testsuite name="pytest">{cases}</testsuite></testsuites>',
                    encoding="utf-8")
    return path


def test_the_parts_of_the_checkout_cover_every_test_file_once():
    tests = ROOT / "tests"
    every = [p.relative_to(ROOT).as_posix() for p in installed.collected_files(tests)]
    parts = [installed.shard_files(tests, f"{k}/4") for k in range(1, 5)]
    files = [part[0] for part in parts]
    assert sorted(sum(files, [])) == sorted(every)
    assert all(part[2] == every for part in parts)
    estimates = [part[1] for part in parts]
    assert max(estimates) - min(estimates) <= max(installed.load_shards().load_durations().values())


def test_shard_files_names_files_relative_to_the_suite(tmp_path):
    for name in ("tests/a/test_one.py", "tests/test_two.py", "tests/b/three_test.py"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("", encoding="utf-8")
    parts = [installed.shard_files(tmp_path / "tests", f"{k}/3")[0] for k in (1, 2, 3)]
    assert sorted(sum(parts, [])) == ["tests/a/test_one.py", "tests/b/three_test.py", "tests/test_two.py"]
    with pytest.raises(RuntimeError, match="no test files"):
        installed.shard_files(tmp_path / "tests", "4/4")


def test_a_part_needs_results_from_its_own_files_only(tmp_path):
    tests = tmp_path / "tests"
    for name in ("test_one.py", "test_two.py"):
        (tests / name).parent.mkdir(parents=True, exist_ok=True)
        (tests / name).write_text("", encoding="utf-8")
    report = junit(tmp_path / "part.xml", ["tests.test_one"])
    assert installed.check_results(report, tests, ["tests/test_one.py"]) == 1
    with pytest.raises(RuntimeError, match="no results: \\['tests/test_two.py'\\]"):
        installed.check_results(report, tests)
    with pytest.raises(RuntimeError, match="no results: \\['tests/test_two.py'\\]"):
        installed.check_results(report, tests, ["tests/test_one.py", "tests/test_two.py"])
    with pytest.raises(RuntimeError, match="skipped or xfailed"):
        installed.check_results(junit(tmp_path / "skip.xml", ["tests.test_one"], ["tests.test_one"]),
                                tests, ["tests/test_one.py"])


def test_a_bad_shard_is_refused_before_anything_is_built(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "run_installed_tests.py"),
                             "--output", str(tmp_path / "out"), "--shard", "5/4"],
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 2
    assert "--shard" in result.stderr
    assert not (tmp_path / "out").exists()
