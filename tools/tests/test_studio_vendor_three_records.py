# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check W16, repository records of the vendored three.js 0.186.1: the license inventory, the
third-party docs, both NOTICE files and the packaging rules.

They read files of the checkout that the installed-wheel run does not copy, so they live here;
the bytes on disk and as served are checked in tests/simcase/test_studio_vendor_three.py, also
against the installed wheel. RECORDED is that file's record, imported, so both agree.
"""
import importlib.util
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("vendor_three", ROOT / "tests" / "simcase" / "test_studio_vendor_three.py")
_vendor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vendor)
RECORDED = _vendor.RECORDED
VENDOR = ROOT / "packages" / "simcase" / "src" / "simcase" / "studio" / "static" / "vendor" / "three-0.186.1"


def test_w16_inventory_records_the_served_files():
    inventory = json.loads((ROOT / "tools" / "third_party_licenses.json").read_text(encoding="utf-8"))
    entry = inventory["browser_served"]["three"]
    assert (entry["version"], entry["spdx"], entry["modified"]) == ("0.186.1", "MIT", False)
    assert entry["source"] == "https://registry.npmjs.org/three/-/three-0.186.1.tgz"
    assert entry["directory"] == VENDOR.relative_to(ROOT).as_posix()
    assert entry["files"] == {name: {"from": source, "bytes": size, "sha256": digest}
                              for name, (source, size, digest) in RECORDED.items()}


def test_w16_licence_records_name_the_files_and_hashes():
    for doc in (ROOT / "docs" / "third-party.md", ROOT / "docs" / "locales" / "ko" / "pages" / "third-party.md"):
        text = doc.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith("| `three`"))
        assert "0.186.1" in row and "MIT" in row
        for name, (_, _, digest) in RECORDED.items():
            assert f"`{name}`" in row and digest in row, (doc, name)
    for notice in (ROOT / "NOTICE", ROOT / "packages" / "simcase" / "NOTICE"):
        text = notice.read_text(encoding="utf-8")
        assert "three.js" in text and "0.186.1" in text and "Copyright © 2010-2026 three.js authors" in text
        assert "Permission is hereby granted, free of charge" in text


def test_w16_wheel_and_sdist_rules_include_the_vendor_folder():
    project = tomllib.loads((ROOT / "packages" / "simcase" / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = project["tool"]["setuptools"]["package-data"]["simcase.studio"]
    assert "static/vendor/three-0.186.1/*" in patterns
    # Git must store and check out the bytes as they are, on every OS.
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "packages/simcase/src/simcase/studio/static/vendor/** -text" in attributes
