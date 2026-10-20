# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tests for tools/check_markdown_links.py on small synthetic trees."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_markdown_links", Path(__file__).resolve().parents[1] / "check_markdown_links.py")
links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(links)


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def broken(root):
    return links.check(root)[1]


def test_valid_links_pass(tmp_path):
    write(tmp_path, "docs/guide.md",
          "# Guide\n\n## Current limits\n\n## Setup `pip`\n\n## Setup `pip`\n\n"
          "## 현재 한계\n\n<a id=\"custom\"></a>\n")
    write(tmp_path, "img/figure.png", "")
    write(tmp_path, "README.md", "\n".join([
        "[guide](docs/guide.md)",
        "[limits](docs/guide.md#current-limits)",
        "[setup](docs/guide.md#setup-pip) [again](docs/guide.md#setup-pip-1)",
        "[korean](docs/guide.md#현재-한계)",
        "[custom](docs/guide.md#custom)",
        "![figure](img/figure.png)",
        "[folder](docs)",
        "[titled](docs/guide.md \"Guide\")",
        "[web](https://example.com/missing.md) [mail](mailto:a@example.com)",
        "[self](#readme-anchor)",
        "",
        "## README anchor",
    ]))
    assert broken(tmp_path) == []
    count, _ = links.check(tmp_path)
    assert count == 10


def test_missing_file_and_anchor_are_reported(tmp_path):
    write(tmp_path, "docs/guide.md", "# Guide\n")
    write(tmp_path, "README.md",
          "[gone](docs/missing.md)\n[bad anchor](docs/guide.md#nope)\n[self](#nowhere)\n")
    found = broken(tmp_path)
    assert len(found) == 3
    assert "README.md:1: docs/missing.md (missing file)" in found[0]
    assert "(missing anchor)" in found[1] and "(missing anchor)" in found[2]


def test_links_in_code_are_ignored(tmp_path):
    write(tmp_path, "README.md",
          "```\n[gone](missing.md)\n```\n\n~~~md\n[gone](missing.md)\n~~~\n\n"
          "Inline `[gone](missing.md)` code.\n")
    assert broken(tmp_path) == []


def test_relative_paths_resolve_from_each_file(tmp_path):
    write(tmp_path, "a/b/page.md", "[up](../../top.md)\n[wrong](top.md)\n")
    write(tmp_path, "top.md", "# Top\n")
    found = broken(tmp_path)
    assert found == ["a/b/page.md:2: top.md (missing file)"]


def test_main_exit_code(tmp_path, capsys):
    write(tmp_path, "README.md", "[ok](README.md)\n")
    assert links.main(["--root", str(tmp_path)]) == 0
    write(tmp_path, "README.md", "[gone](missing.md)\n")
    assert links.main(["--root", str(tmp_path)]) == 1
    assert "1 broken" in capsys.readouterr().out
