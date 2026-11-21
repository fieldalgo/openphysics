# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tests for tools/changelog.py on the checkout and on small synthetic trees."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("changelog", ROOT / "tools" / "changelog.py")
changelog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changelog)

KO = "docs/locales/ko/pages/changelog.md"
EN_LOG = ("# Changelog\n\n## [Unreleased]\n\n- Old bullet.\n\nA paragraph.\n\n"
          "### Added\n\n- Old added.\n\n### Changed\n\n- Old changed.\n\n## [0.0.1] - 2026-01-01\n\n- Past.\n")
KO_LOG = ("# 변경 기록\n\n## [Unreleased]\n\n- 이전 항목.\n\n### Added\n\n- 이전 추가.\n\n"
          "### Changed\n\n- 이전 변경.\n")


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fragment(category, en, ko):
    return f"# {category}\n\n## English\n\n{en}\n\n## 한국어\n\n{ko}\n"


def tree(root):
    write(root, "CHANGELOG.md", EN_LOG)
    write(root, KO, KO_LOG)
    write(root, "docs/guide.md", "# Guide\n\n## Limits\n")
    write(root, "docs/locales/ko/pages/guide.md", "# 안내\n")
    return root


def test_checkout_fragments_are_valid():
    _, errors = changelog.check(ROOT)
    assert errors == []


def test_valid_fragment_passes(tmp_path):
    tree(tmp_path)
    write(tmp_path, "changelog.d/new-thing.md", fragment(
        "Added", "- New thing. [Guide](docs/guide.md#limits).\n  Second line.",
        "- 새 기능. [안내](guide.md)."))
    parsed, errors = changelog.check(tmp_path)
    assert errors == []
    assert [(p.name, c) for p, c, _ in parsed] == [("new-thing.md", "Added")]
    assert parsed[0][2]["English"].endswith("Second line.")


def test_malformed_fragments_are_reported(tmp_path):
    tree(tmp_path)
    write(tmp_path, "changelog.d/Bad_Name.md", fragment("Added", "- a", "- b"))
    write(tmp_path, "changelog.d/unknown.md", fragment("Improved", "- a", "- b"))
    write(tmp_path, "changelog.d/no-korean.md", "# Fixed\n\n## English\n\n- a\n")
    write(tmp_path, "changelog.d/no-bullet.md", fragment("Fixed", "Plain text.", "- b"))
    write(tmp_path, "changelog.d/extra-heading.md", fragment("Fixed", "- a\n\n### Sub", "- b"))
    write(tmp_path, "changelog.d/other-language.md", fragment("Fixed", "- a", "- b") + "\n## Deutsch\n\n- c\n")
    _, errors = changelog.check(tmp_path)
    text = "\n".join(errors)
    assert "Bad_Name.md: name must be" in text
    assert "'Improved' is not one of" in text
    assert "no-korean.md: no '## 한국어' bullets" in text
    assert "no-bullet.md: '## English' must start with a '- ' bullet" in text
    assert "extra-heading.md: no other headings" in text
    assert "other-language.md: section 'Deutsch'" in text
    assert len(errors) == 6


def test_links_resolve_from_each_changelog(tmp_path):
    tree(tmp_path)
    # the Korean bullet links as if from the English changelog, and an anchor is wrong
    write(tmp_path, "changelog.d/links.md", fragment(
        "Changed", "- [Guide](docs/guide.md#nope) [web](https://example.com/x.md)",
        "- [안내](docs/guide.md)"))
    _, errors = changelog.check(tmp_path)
    assert len(errors) == 2
    assert "(English): docs/guide.md#nope (missing anchor)" in errors[0]
    assert f"(한국어): docs/guide.md (missing file, relative to {KO})" in errors[1]


def test_assemble_inserts_under_categories_and_deletes(tmp_path):
    tree(tmp_path)
    write(tmp_path, "changelog.d/b-second.md", fragment("Added", "- B added.", "- B 추가."))
    write(tmp_path, "changelog.d/a-first.md", fragment("Added", "- A added.\n  More.", "- A 추가."))
    write(tmp_path, "changelog.d/fix.md", fragment("Fixed", "- A fix.", "- 수정."))
    write(tmp_path, "changelog.d/sec.md", fragment("Security", "- A guard.", "- 보안."))
    assert changelog.assemble(tmp_path) == []
    assert not list((tmp_path / "changelog.d").iterdir())
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == (
        "# Changelog\n\n## [Unreleased]\n\n- Old bullet.\n\nA paragraph.\n\n"
        "### Added\n\n- A added.\n  More.\n- B added.\n- Old added.\n\n"
        "### Changed\n\n- Old changed.\n\n### Fixed\n\n- A fix.\n\n### Security\n\n- A guard.\n\n"
        "## [0.0.1] - 2026-01-01\n\n- Past.\n")
    assert (tmp_path / KO).read_text(encoding="utf-8") == (
        "# 변경 기록\n\n## [Unreleased]\n\n- 이전 항목.\n\n"
        "### Added\n\n- A 추가.\n- B 추가.\n- 이전 추가.\n\n"
        "### Changed\n\n- 이전 변경.\n\n### Fixed\n\n- 수정.\n\n### Security\n\n- 보안.\n")


def test_assemble_places_a_missing_category_in_order(tmp_path):
    write(tmp_path, "CHANGELOG.md", "## [Unreleased]\n\n### Changed\n\n- Old.\n")
    write(tmp_path, KO, "## [Unreleased]\n\n### Fixed\n\n### Security\n\n- 이전.\n")
    write(tmp_path, "changelog.d/x.md", fragment("Added", "- New.", "- 새."))
    write(tmp_path, "changelog.d/y.md", fragment("Fixed", "- Fix.", "- 수정."))
    assert changelog.assemble(tmp_path) == []
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == (
        "## [Unreleased]\n\n### Added\n\n- New.\n\n### Changed\n\n- Old.\n\n### Fixed\n\n- Fix.\n")
    assert (tmp_path / KO).read_text(encoding="utf-8") == (
        "## [Unreleased]\n\n### Added\n\n- 새.\n\n### Fixed\n\n- 수정.\n\n### Security\n\n- 이전.\n")


def test_assemble_refuses_invalid_fragments_and_changes_nothing(tmp_path):
    tree(tmp_path)
    write(tmp_path, "changelog.d/good.md", fragment("Added", "- Good.", "- 좋음."))
    write(tmp_path, "changelog.d/bad.md", fragment("Added", "- Bad.", "Plain."))
    errors = changelog.assemble(tmp_path)
    assert len(errors) == 1 and "bad.md" in errors[0]
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == EN_LOG
    assert len(list((tmp_path / "changelog.d").iterdir())) == 2


def test_assemble_needs_an_unreleased_section(tmp_path):
    write(tmp_path, "CHANGELOG.md", "# Changelog\n\n## [0.0.1] - 2026-01-01\n")
    write(tmp_path, KO, KO_LOG)
    write(tmp_path, "changelog.d/x.md", fragment("Added", "- New.", "- 새."))
    errors = changelog.assemble(tmp_path)
    assert errors == ["CHANGELOG.md has no '## [Unreleased]' section"]
    assert (tmp_path / KO).read_text(encoding="utf-8") == KO_LOG
    assert (tmp_path / "changelog.d/x.md").is_file()


def test_no_fragments_is_a_no_op(tmp_path):
    tree(tmp_path)
    assert changelog.check(tmp_path) == ([], [])
    assert changelog.assemble(tmp_path) == []
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == EN_LOG


def test_fences_bom_and_paragraphs(tmp_path):
    write(tmp_path, "CHANGELOG.md", "## [Unreleased]\n\n```text\n## not a section\n### Fixed\n```\n\n"
          "### Fixed\n\nA paragraph first.\n\n- Old.\n")
    write(tmp_path, KO, "## [Unreleased]\n\n### Fixed\n\n- 이전.\n")
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d/fenced.md").write_text(
        "﻿" + fragment("Fixed", "- New:\n\n  ```sh\n  # a comment\n  ## English\n  ```", "- 새."),
        encoding="utf-8")
    parsed, errors = changelog.check(tmp_path)
    assert errors == []
    assert "# a comment" in parsed[0][2]["English"]
    assert changelog.assemble(tmp_path) == []
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == (
        "## [Unreleased]\n\n```text\n## not a section\n### Fixed\n```\n\n### Fixed\n\n"
        "- New:\n\n  ```sh\n  # a comment\n  ## English\n  ```\n\nA paragraph first.\n\n- Old.\n")


def test_markdown_link_check_skips_fragments(tmp_path):
    write(tmp_path, "changelog.d/x.md", fragment("Added", "- [gone](nowhere.md)", "- [없음](nowhere.md)"))
    write(tmp_path, "README.md", "[ok](README.md)\n")
    assert changelog.links.check(tmp_path) == (1, [])


def test_command_line_exit_status(capsys, monkeypatch, tmp_path):
    assert changelog.main(["--check"]) == 0
    assert "changelog fragments checked" in capsys.readouterr().out
    tree(tmp_path)
    write(tmp_path, "changelog.d/bad.md", "# Nope\n")
    monkeypatch.setattr(changelog, "ROOT", tmp_path)
    assert changelog.main(["--assemble"]) == 1
    assert "error: changelog.d/bad.md" in capsys.readouterr().err
