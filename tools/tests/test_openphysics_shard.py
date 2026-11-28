# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tests for tools/shards/openphysics_shard.py, the CI source-test shards.

The parts must together run every collected test exactly once, whatever the
order of collection, and a bad --shard must stop the run instead of running
nothing or everything.
"""

import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / "tools" / "shards"
_spec = importlib.util.spec_from_file_location("openphysics_shard", PLUGIN_DIR / "openphysics_shard.py")
shard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shard)


@pytest.mark.parametrize("text, expected", [("1/1", (1, 1)), ("2/4", (2, 4)), ("4/4", (4, 4))])
def test_parse_shard_accepts_k_of_n(text, expected):
    assert shard.parse_shard(text) == expected


@pytest.mark.parametrize("text", ["0/4", "5/4", "1/0", "-1/4", "4", "a/b", "1/2/3", ""])
def test_parse_shard_refuses_other_forms(text):
    with pytest.raises(ValueError, match="--shard"):
        shard.parse_shard(text)


def test_every_file_goes_to_exactly_one_part_whatever_the_order():
    seconds = {f"tests/t{i}.py": float((i * 37) % 23 + 1) for i in range(40)}
    files = list(seconds) + ["tests/new_a.py", "tests/new_b.py"]
    plan = shard.assign(files, seconds, 4)
    assert set(plan) == set(files) and set(plan.values()) == {0, 1, 2, 3}
    for seed in range(5):
        shuffled = files[:]
        random.Random(seed).shuffle(shuffled)
        assert shard.assign(shuffled, seconds, 4) == plan
    assert set(shard.assign(files, seconds, 1).values()) == {0}


def test_a_file_missing_from_the_table_counts_as_the_median():
    seconds = {"a.py": 10.0, "b.py": 2.0, "c.py": 4.0}
    # d is not in the table and counts as the median, 4 s. Largest first, names breaking
    # ties: a (10) to part 0; c (4) to part 1; d (4) to part 1 (4 < 10); b (2) to part 1 (8 < 10).
    assert shard.assign(["a.py", "b.py", "c.py", "d.py"], seconds, 2) == {
        "a.py": 0, "c.py": 1, "d.py": 1, "b.py": 1}
    # With d at 20 s in the table it goes first instead.
    assert shard.assign(["a.py", "b.py", "c.py", "d.py"], dict(seconds, **{"d.py": 20.0}), 2) == {
        "d.py": 0, "a.py": 1, "c.py": 1, "b.py": 1}


@pytest.mark.parametrize("parts", [4, 8])
def test_the_stored_table_balances_the_parts(parts):
    seconds = shard.load_durations()
    plan = shard.assign(list(seconds), seconds, parts)
    load = [sum(seconds[f] for f, i in plan.items() if i == part) for part in range(parts)]
    # Greedy largest-first: no part exceeds the even share by more than the largest file.
    assert max(load) <= sum(load) / parts + max(seconds.values())
    assert all(value > 0 for value in load)


def test_no_file_is_much_longer_than_a_part_of_the_suite():
    # CI runs sixteen parts (.github/workflows/validate.yml) and assigns whole files, so a
    # file far above a sixteenth of the suite would set the run's floor; split such a file instead.
    seconds = shard.load_durations()
    part = sum(seconds.values()) / 16
    assert max(seconds.values()) <= 1.1 * part, max(seconds, key=seconds.get)


def test_the_stored_table_names_existing_test_files():
    data = json.loads((PLUGIN_DIR / "durations.json").read_text(encoding="utf-8"))
    assert data["source"]
    missing = [name for name in data["seconds"] if not (ROOT / name).is_file()]
    # A removed file only wastes its estimate; keep the table current when it grows stale.
    assert len(missing) <= len(data["seconds"]) // 10, missing


def collect(tree, *args):
    env = dict(os.environ, PYTHONPATH=str(PLUGIN_DIR))
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "-p", "openphysics_shard", *args],
        cwd=tree, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)


def node_ids(output):
    ids = []
    for line in output.splitlines():
        if not line.strip():
            break
        if "::" in line:
            ids.append(line)
    return ids


@pytest.fixture
def small_suite(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    for name, count in [("test_one.py", 3), ("test_two.py", 1), ("sub/test_three.py", 2)]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"def test_{i}():\n    pass\n" for i in range(count)), encoding="utf-8")
    return tmp_path


def test_parts_of_a_real_collection_add_up_to_the_whole(small_suite):
    whole = collect(small_suite)
    assert whole.returncode == 0, whole.stdout + whole.stderr
    every = node_ids(whole.stdout)
    assert len(every) == 6
    parts = []
    for k in (1, 2, 3):
        result = collect(small_suite, "--shard", f"{k}/3")
        assert result.returncode in (0, 5), result.stdout + result.stderr
        parts.append(node_ids(result.stdout))
        assert f"shard {k}/3:" in result.stdout
    assert sorted(sum(parts, [])) == sorted(every)
    files = [{node.split("::")[0] for node in part} for part in parts]
    assert sum(len(f) for f in files) == 3


def test_a_bad_shard_stops_the_run(small_suite):
    result = collect(small_suite, "--shard", "4/3")
    assert result.returncode == 4  # pytest's usage error
    assert "--shard" in result.stderr


def junit(path, cases):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f'<testcase classname="{c}" name="t{i}" time="{t}"/>' for i, (c, t) in enumerate(cases))
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>',
                    encoding="utf-8")


def test_slowest_keeps_each_files_longest_run(small_suite, tmp_path_factory):
    # Two runs of the same suite on runners of different speed: per file, the run's sum of
    # its test cases, then the longer of the two runs. A file seen in one run only keeps that time.
    runs = tmp_path_factory.mktemp("runs")
    junit(runs / "a" / "part-1.xml", [("test_one", 1.0), ("test_one", 2.0)])
    junit(runs / "a" / "part-2.xml", [("sub.test_three", 9.0)])
    junit(runs / "b" / "nested" / "part-1.xml", [("test_one", 4.0), ("test_two", 0.5)])
    junit(runs / "b" / "part-2.xml", [("sub.test_three", 5.0)])
    output = tmp_path_factory.mktemp("out") / "durations.json"
    table = shard.update_slowest([runs / "a", runs / "b"], "runs a and b", output, root=small_suite)
    assert table == {"source": "runs a and b", "seconds": {
        "sub/test_three.py": 9.0, "test_one.py": 4.0, "test_two.py": 0.5}}
    assert json.loads(output.read_text(encoding="utf-8")) == table
    # One run's folder alone gives that run's sums, as --update does with its files.
    assert shard.update_slowest([runs / "a"], "a", output, root=small_suite)["seconds"] == \
        shard.update(sorted((runs / "a").glob("*.xml")), "a", output, root=small_suite)["seconds"]


def test_slowest_refuses_a_folder_without_junit(tmp_path):
    with pytest.raises(SystemExit, match="no JUnit XML"):
        shard.update_slowest([tmp_path], "empty", tmp_path / "durations.json", root=tmp_path)
