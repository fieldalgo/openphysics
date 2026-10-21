# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The waveguide tutorial runs as written and prints what it shows.

Each ``python`` block runs in one shared namespace, in page order, in a fresh
working folder; the ``text`` block right after it is its exact standard output.
A printed number may differ from the page by one unit in its last printed digit:
mesh generation and BLAS can move a value by a few 1e-6 between machines, which
flips a rounded digit near a boundary; everything else must match exactly.
``python -m simcase`` lines in ``bash`` blocks run as commands. The Korean page
must carry the same blocks, so a number changed in one language is caught.
"""
import contextlib
import io
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGLISH = ROOT / "docs/packages/simcase/waveguide_tutorial.md"
KOREAN = ROOT / "docs/locales/ko/pages/packages/simcase/waveguide_tutorial.md"
FENCE = re.compile(r"^```(\w+)\n(.*?)^```$", re.S | re.M)
NUMBER = re.compile(r"-?\d+\.(\d+)")


def same_output(printed, shown):
    """Equal text; numbers equal within one unit of the page's last digit."""
    if NUMBER.sub("#", printed) != NUMBER.sub("#", shown):
        return False
    for got, want in zip(NUMBER.finditer(printed), NUMBER.finditer(shown)):
        digits = len(want.group(1))
        if len(got.group(1)) != digits or abs(float(got.group(0)) - float(want.group(0))) > 1.01 * 10.0**-digits:
            return False
    return True


def blocks(page):
    return [(m.group(1), m.group(2)) for m in FENCE.finditer(page.read_text(encoding="utf-8"))]


def test_both_languages_show_the_same_code_and_output():
    assert blocks(KOREAN) == blocks(ENGLISH)


@pytest.mark.slow
def test_the_tutorial_runs_and_prints_what_it_shows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    found = blocks(ENGLISH)
    namespace = {"__name__": "tutorial"}
    ran = 0
    for i, (kind, body) in enumerate(found):
        if kind == "bash":
            for line in body.splitlines():
                if line.startswith("python -m simcase "):
                    command, _, target = line[len("python -m "):].partition(" > ")
                    out = subprocess.run([sys.executable, "-m", *command.split()], capture_output=True,
                                         text=True, encoding="utf-8", env=dict(os.environ, MPLBACKEND="Agg"))
                    assert out.returncode == 0, out.stderr
                    if target:
                        Path(target).write_text(out.stdout, encoding="utf-8")
                    ran += 1
        elif kind == "python":
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                exec(compile(body, f"{ENGLISH.name} block {i}", "exec"), namespace)
            ran += 1
            if i + 1 < len(found) and found[i + 1][0] == "text":
                assert same_output(printed.getvalue(), found[i + 1][1]), \
                    f"block {i} printed\n{printed.getvalue()}instead of\n{found[i + 1][1]}"
            else:
                assert printed.getvalue() == "", f"block {i} prints but the page shows no output"
    assert ran >= 10
    assert (tmp_path / "strip_results" / "summary.json").is_file()
