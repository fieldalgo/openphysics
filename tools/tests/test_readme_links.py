# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tests for the packages' setup.py, which makes README links absolute for PyPI."""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = sorted(p.parent for p in (ROOT / "packages").glob("*/setup.py"))
REF = "0123456789abcdef0123456789abcdef01234567"


def load(path):
    spec = importlib.util.spec_from_file_location(f"setup_{path.parent.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # setup() runs only under __main__
    return module


hook = load(ROOT / "packages" / "galerkin" / "setup.py")


def test_every_package_has_the_same_hook():
    names = {p.name for p in PACKAGES}
    assert names == {"galerkin", "galerkin-refsol", "meshine", "gmshio", "physmat", "simcase", "sipi", "openphysics"}
    reference = (ROOT / "packages" / "galerkin" / "setup.py").read_bytes()
    for package in PACKAGES:
        assert (package / "setup.py").read_bytes() == reference, package.name
        pyproject = (package / "pyproject.toml").read_text(encoding="utf-8")
        assert 'dynamic = ["readme"]' in pyproject and "readme =" not in pyproject, package.name


def test_rewrites_links_images_and_anchors():
    text = "\n".join([
        "[guide](docs/guide.md) [part](docs/guide.md#units \"Units\")",
        "![figure](docs/figure.png) [top](#install) [up](../../README.md)",
        "[web](https://example.com/x.md) [mail](mailto:a@example.com)",
        "[page](../../docs/packages/demo/guide.md) [run](../../examples/demo/run.py)",
        "```", "[code](docs/not-a-link.md)", "```",
    ])
    out = hook.absolute_links(text, REF, "packages/demo/")
    blob = f"https://github.com/fieldalgo/openphysics/blob/{REF}/"
    raw = f"https://raw.githubusercontent.com/fieldalgo/openphysics/{REF}/"
    assert f"[guide]({blob}packages/demo/docs/guide.md)" in out
    assert f"[part]({blob}packages/demo/docs/guide.md#units \"Units\")" in out
    assert f"![figure]({raw}packages/demo/docs/figure.png)" in out
    assert f"[top]({blob}packages/demo/README.md#install)" in out
    assert f"[up]({blob}README.md)" in out
    assert f"[page]({blob}docs/packages/demo/guide.md)" in out
    assert f"[run]({blob}examples/demo/run.py)" in out
    assert "[web](https://example.com/x.md)" in out and "[mail](mailto:a@example.com)" in out
    assert "[code](docs/not-a-link.md)" in out


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_no_relative_link_is_left_in_a_readme(package):
    text = (package / "README.md").read_text(encoding="utf-8")
    out = hook.absolute_links(text, REF, f"packages/{package.name}/")
    outside_code = re.sub(r"```.*?```", "", out, flags=re.S)
    targets = re.findall(r"\]\(\s*<?([^)\s>]+)", outside_code)
    assert targets, package.name
    relative = [t for t in targets if not re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", t)]
    assert relative == [], (package.name, relative)


def test_wheel_from_sdist_reuses_the_sdist_description(tmp_path):
    (tmp_path / "PKG-INFO").write_text(
        "Metadata-Version: 2.4\nName: demo\nVersion: 1\n\nStored description\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[guide](docs/guide.md)\n", encoding="utf-8")
    copy = tmp_path / "setup.py"
    copy.write_bytes((ROOT / "packages" / "galerkin" / "setup.py").read_bytes())
    assert load(copy).description().strip() == "Stored description"
