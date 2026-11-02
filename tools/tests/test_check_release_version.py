# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tests for tools/check_release_version.py on the checkout and on small synthetic trees."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_release_version", ROOT / "tools" / "check_release_version.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def tree(root, version="0.1.0", core_version=None, sibling='"core>=0.1.0,<0.2"',
         extra_sibling='"core[fast]>=0.1.0,<0.2"', changelog="## [Unreleased]\n"):
    write(root, "packages/core/pyproject.toml",
          f'[project]\nname = "core"\nversion = "{version}"\ndependencies = ["numpy>=1.26"]\n')
    write(root, "packages/core/src/core/__init__.py",
          f'"""Core."""\n\n__version__ = "{core_version or version}"\n')
    write(root, "packages/suite/pyproject.toml",
          f'[project]\nname = "suite"\nversion = "{version}"\ndependencies = [{sibling}]\n'
          f'[project.optional-dependencies]\nfast = [{extra_sibling}]\n')
    write(root, "CHANGELOG.md", "# Changelog\n\n" + changelog)
    return root


def test_checkout_versions_agree():
    version, errors = release.check(ROOT)
    assert errors == []
    assert version


def test_consistent_tree_passes(tmp_path):
    assert release.check(tree(tmp_path)) == ("0.1.0", [])


def test_pyproject_versions_must_match(tmp_path):
    tree(tmp_path)
    write(tmp_path, "packages/suite/pyproject.toml",
          '[project]\nname = "suite"\nversion = "0.1.1"\ndependencies = ["core>=0.1.0,<0.2"]\n')
    _, errors = release.check(tmp_path)
    assert len(errors) == 1 and "versions differ" in errors[0]


def test_source_version_must_match(tmp_path):
    _, errors = release.check(tree(tmp_path, core_version="0.0.1"))
    assert errors == ["packages/core/src/core/__init__.py: __version__ '0.0.1' != '0.1.0'"]


def test_missing_source_version_fails(tmp_path):
    tree(tmp_path)
    write(tmp_path, "packages/core/src/core/__init__.py", "VERSION = '0.1.0'\n")
    _, errors = release.check(tmp_path)
    assert errors == ["packages/core/src/core/__init__.py: no __version__ string"]


def test_sibling_requirement_must_admit_the_version(tmp_path):
    _, errors = release.check(tree(tmp_path, sibling='"core>=0.1.1,<0.2"'))
    assert len(errors) == 1 and "does not admit 0.1.0" in errors[0]


def test_sibling_requirement_needs_an_upper_bound(tmp_path):
    _, errors = release.check(tree(tmp_path, extra_sibling='"core[fast]>=0.1"'))
    assert len(errors) == 1 and "optional-dependencies.fast" in errors[0] and "admits 0.2" in errors[0]


def test_third_party_requirements_are_ignored(tmp_path):
    _, errors = release.check(tree(tmp_path, sibling='"core>=0.1.0,<0.2", "scipy>=1.11.2"'))
    assert errors == []


def test_changelog_needs_unreleased_or_version_section(tmp_path):
    _, errors = release.check(tree(tmp_path, changelog="## [0.0.9] - 2026-01-01\n"))
    assert errors == ["CHANGELOG.md has neither '## [Unreleased]' nor '## [0.1.0]'"]


def test_release_tag_must_name_the_version(tmp_path):
    tree(tmp_path, changelog="## [0.1.0] - 2026-10-21\n")
    assert release.check(tmp_path, "v0.1.0") == ("0.1.0", [])
    _, errors = release.check(tmp_path, "v0.1.1")
    assert errors == ["tag 'v0.1.1' does not name version '0.1.0'; expected v0.1.0"]
    _, errors = release.check(tmp_path, "0.1.0")
    assert len(errors) == 1 and "expected v0.1.0" in errors[0]


def test_release_needs_a_dated_changelog_section(tmp_path):
    _, errors = release.check(tree(tmp_path), "v0.1.0")
    assert errors == ["CHANGELOG.md has no dated '## [0.1.0] - YYYY-MM-DD' section"]
    _, errors = release.check(tree(tmp_path, changelog="## [0.1.0]\n"), "v0.1.0")
    assert len(errors) == 1 and "dated" in errors[0]


def test_command_line_exit_status(tmp_path, capsys):
    assert release.main([]) == 0
    assert "all distributions at" in capsys.readouterr().out
    assert release.main(["--tag", "v999.0.0"]) == 1
    assert "does not name version" in capsys.readouterr().err


def test_compiled_kernel_version_must_match(tmp_path):
    root = tree(tmp_path)
    write(root, "packages/core/Cargo.toml", '[package]\nname = "core-kernel"\nversion = "0.1.0"\n')
    assert release.check(root)[1] == []
    write(root, "packages/core/Cargo.toml", '[package]\nname = "core-kernel"\nversion = "0.0.9"\n')
    assert any("Cargo.toml: package version '0.0.9' != '0.1.0'" in e for e in release.check(root)[1])
