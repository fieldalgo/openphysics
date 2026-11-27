# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""three.js 0.186.1, vendored unmodified and served by Studio (check W16, Python part).

The recorded SHA-256 values below were taken from the npm registry tarball
``three-0.186.1.tgz`` (its sha512 integrity matched the registry's) and agree with the
values recorded in the 3D view design. The browser part of W16 (a page that loads
``three.module.js`` makes no request to another origin) is
tools/studio_browser/studio_vendor_three_browser.mjs.
"""
import hashlib
import json
import re
import tomllib
from pathlib import Path

import pytest

import simcase

ROOT = Path(__file__).resolve().parents[2]
VENDOR = Path(simcase.__file__).parent / "studio" / "static" / "vendor" / "three-0.186.1"
ROUTE = "/vendor/three-0.186.1/"
# name in the vendor folder -> (path in the npm package, size in bytes, SHA-256)
RECORDED = {
    "three.core.js": ("build/three.core.js", 1458113,
                      "9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6"),
    "three.module.js": ("build/three.module.js", 662772,
                        "9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea"),
    "LICENSE": ("LICENSE", 1081,
                "8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc"),
}
MEDIA = {"three.core.js": "text/javascript", "three.module.js": "text/javascript", "LICENSE": "text/plain"}


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi", reason="the studio extra is not installed")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


def test_w16_vendored_files_are_exactly_the_recorded_bytes():
    assert sorted(p.name for p in VENDOR.iterdir()) == sorted(RECORDED)
    for name, (_, size, digest) in RECORDED.items():
        data = (VENDOR / name).read_bytes()
        assert len(data) == size, name
        assert hashlib.sha256(data).hexdigest() == digest, name


def test_w16_served_bytes_and_headers_match_the_record(client):
    for name, (_, _, digest) in RECORDED.items():
        response = client.get(ROUTE + name)
        assert response.status_code == 200, name
        assert hashlib.sha256(response.content).hexdigest() == digest, name
        assert response.headers["content-type"].split(";")[0] == MEDIA[name]
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        policy = response.headers["content-security-policy"]
        script = next(d for d in policy.split("; ") if d.startswith("script-src "))
        assert script.split()[1] == "'self'" and not any(t.startswith(("http", "*")) for t in script.split()[1:])
    assert "MIT License" in client.get(ROUTE + "LICENSE").text


@pytest.mark.parametrize("name", ["three.js", "three.cjs", "OrbitControls.js", "../index.html",
                                  "%2e%2e/index.html", "build/three.core.js", "three.core.js.map"])
def test_w16_only_the_recorded_files_are_served(client, name):
    assert client.get(ROUTE + name).status_code == 404


def test_w16_the_module_imports_only_its_core_by_a_relative_path():
    text = (VENDOR / "three.module.js").read_text(encoding="utf-8")
    specifiers = set(re.findall(r"""\b(?:from|import)\s*['"]([^'"]+)['"]""", text))
    specifiers |= set(re.findall(r"""\bimport\s*\(\s*['"]([^'"]+)['"]""", text))
    assert specifiers == {"./three.core.js"}
    core = (VENDOR / "three.core.js").read_text(encoding="utf-8")
    assert not re.search(r"""^\s*import\b[^(]""", core, re.M)
    assert not re.findall(r"""\bimport\s*\(\s*['"]""", core)


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
