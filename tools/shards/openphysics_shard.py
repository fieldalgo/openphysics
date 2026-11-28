# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Run one time-balanced part of the pytest suite, for the CI shards.

As a pytest plugin (the Linux source-test jobs of validate.yml)::

    PYTHONPATH=tools/shards python -m pytest -p openphysics_shard --shard 2/4

pytest collects the whole suite as usual; this plugin then keeps the test files
of part 2 and deselects the rest. Files are assigned whole, largest first, each
to the part with the least time so far (ties go to the lower part), using the
per-file seconds in ``durations.json`` beside this file; a file missing from the
table counts as the median of the files listed. Every part computes the same
assignment from the same collected files, so the parts together run every
collected test exactly once. Without ``--shard`` the plugin does nothing.

As a script, rebuild the table from the JUnit XML of a complete run (all parts)::

    python tools/shards/openphysics_shard.py --update source-tests-*.xml --source "<run>"

or, with ``--slowest``, from several complete runs, one folder of JUnit XML per run,
keeping each file's longest time: a part runs on one runner, so balancing the parts by
the slowest times seen bounds the longest part when it lands on a slow runner::

    python tools/shards/openphysics_shard.py --slowest run-a run-b --source "<runs>"

Run it from the repository root: test cases are mapped to files by their
dotted class names.
"""
import argparse
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DURATIONS = Path(__file__).with_name("durations.json")


def parse_shard(text):
    """Return (part, parts) from "k/n", with 1 <= k <= n."""
    try:
        part, parts = (int(value) for value in str(text).split("/"))
    except ValueError:
        raise ValueError(f"--shard must be k/n with whole numbers, not {text!r}") from None
    if parts < 1 or not 1 <= part <= parts:
        raise ValueError(f"--shard {text!r}: need 1 <= k <= n")
    return part, parts


def load_durations(path=DURATIONS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    seconds = data["seconds"]
    if not all(isinstance(v, (int, float)) and v >= 0 for v in seconds.values()):
        raise ValueError(f"{path}: every duration must be a number >= 0")
    return seconds


def weights(files, seconds):
    """Seconds per file; a file missing from the table counts as the median of those listed."""
    known = [seconds[f] for f in set(files) if f in seconds]
    default = statistics.median(known) if known else 1.0
    return {f: seconds.get(f, default) for f in set(files)}


def assign(files, seconds, parts):
    """Map each file to a part index in range(parts); the result depends only on the set of files."""
    weight = weights(files, seconds)
    load = [0.0] * parts
    result = {}
    for f in sorted(weight, key=lambda name: (-weight[name], name)):
        index = min(range(parts), key=lambda i: (load[i], i))
        result[f] = index
        load[index] += weight[f]
    return result


def pytest_addoption(parser):
    group = parser.getgroup("openphysics shard")
    group.addoption("--shard", default=None, metavar="K/N",
                    help="run only part K of N time-balanced parts of the collected test files")


def pytest_configure(config):
    text = config.getoption("--shard")
    if text is None:
        return
    import pytest
    try:
        config._openphysics_shard = parse_shard(text)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None


def _file(item, root):
    path = Path(item.path)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def pytest_collection_modifyitems(session, config, items):
    shard = getattr(config, "_openphysics_shard", None)
    if shard is None:
        return
    part, parts = shard
    root = Path(config.rootpath)
    seconds = load_durations()
    files = {_file(item, root) for item in items}
    plan = assign(files, seconds, parts)
    keep, drop = [], []
    for item in items:
        (keep if plan[_file(item, root)] == part - 1 else drop).append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep
    mine = sorted(f for f, index in plan.items() if index == part - 1)
    weight = weights(files, seconds)
    config._openphysics_shard_summary = (
        f"shard {part}/{parts}: {len(mine)} of {len(files)} test files, {len(keep)} of "
        f"{len(keep) + len(drop)} tests, about {sum(weight[f] for f in mine) / 60:.1f} min "
        f"by {DURATIONS.name} ({len(files - set(seconds))} files not in it)")


def pytest_terminal_summary(terminalreporter, config):
    summary = getattr(config, "_openphysics_shard_summary", None)
    if summary:
        terminalreporter.write_line(summary)


def _case_file(classname, root):
    parts = classname.split(".")
    for n in range(len(parts), 0, -1):
        path = root.joinpath(*parts[:n]).with_suffix(".py")
        if path.is_file():
            return path.relative_to(root).as_posix()
    return None


def file_seconds(xml_paths, root=Path(".")):
    """Sum the JUnit test-case times per test file."""
    seconds = {}
    for xml_path in xml_paths:
        for case in ET.parse(xml_path).getroot().iter("testcase"):
            name = _case_file(case.get("classname", ""), root)
            if name is None:
                raise SystemExit(f"{xml_path}: no test file for class {case.get('classname')!r}; "
                                 "run from the repository root")
            seconds[name] = seconds.get(name, 0.0) + float(case.get("time", 0) or 0)
    return seconds


def _write(seconds, source, output):
    table = {"source": source, "seconds": {k: round(v, 1) for k, v in sorted(seconds.items())}}
    Path(output).write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    return table


def update(xml_paths, source, output=DURATIONS, root=Path(".")):
    """Sum the JUnit test-case times per test file and write the table."""
    return _write(file_seconds(xml_paths, root), source, output)


def update_slowest(run_dirs, source, output=DURATIONS, root=Path(".")):
    """Write the table from several runs (one folder of JUnit XML each), keeping per test
    file the longest of the runs' sums."""
    seconds = {}
    for run_dir in run_dirs:
        xml_paths = sorted(Path(run_dir).rglob("*.xml"))
        if not xml_paths:
            raise SystemExit(f"{run_dir}: no JUnit XML files")
        for name, value in file_seconds(xml_paths, root).items():
            seconds[name] = max(seconds.get(name, 0.0), value)
    return _write(seconds, source, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--update", nargs="+", metavar="JUNIT_XML",
                      help="JUnit XML files of one complete run")
    mode.add_argument("--slowest", nargs="+", metavar="RUN_DIR",
                      help="one folder of JUnit XML per complete run; each file's longest time is kept")
    parser.add_argument("--source", required=True, help="where the times come from (run, commit)")
    parser.add_argument("--output", default=str(DURATIONS))
    args = parser.parse_args(argv)
    if args.slowest:
        table = update_slowest(args.slowest, args.source, args.output)
    else:
        table = update(args.update, args.source, args.output)
    total = sum(table["seconds"].values())
    print(f"{len(table['seconds'])} test files, {total / 60:.1f} min, written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
