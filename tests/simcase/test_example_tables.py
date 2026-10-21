# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The supported-documents tables name every shipped example under its physics type.

`python -m simcase example <name>` prints the documents in ``examples.EXAMPLES``;
the package README and its English and Korean documentation pages list them in a
table so a reader can find them. Field-layout IDs are internal and not checked.
The installed-package run has no ``packages/`` tree; there the README is read
from the installed distribution's long description, which carries the same table.
"""
from importlib import metadata
import json
import re
from pathlib import Path

import pytest

from simcase import examples

ROOT = Path(__file__).resolve().parents[2]
PAGES = [
    "packages/simcase/README.md",
    "docs/packages/simcase/overview.md",
    "docs/locales/ko/pages/packages/simcase/overview.md",
]
HEADERS = ("| Physics type |", "| 물리 유형 |")
CODE = re.compile(r"`([^`]+)`")


def physics_type(doc):
    (entry,) = doc["physics"].values()
    return entry["type"]


def page_text(page):
    path = ROOT / page
    if path.exists() or page != PAGES[0]:
        return path.read_text(encoding="utf-8")
    return metadata.metadata("simcase").get_payload()


def table_rows(page):
    lines = page_text(page).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(HEADERS))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append((CODE.findall(cells[0])[0], CODE.findall(cells[2])))
    return rows


@pytest.mark.parametrize("page", PAGES)
def test_every_example_is_listed_once_under_its_physics_type(page):
    listed = {}
    for kind, names in table_rows(page):
        for name in names:
            assert name not in listed, f"{page}: {name} listed twice"
            listed[name] = kind
    assert set(listed) == set(examples.EXAMPLES), page
    for name, kind in listed.items():
        assert physics_type(examples.EXAMPLES[name]) == kind, f"{page}: {name}"


@pytest.mark.parametrize("name", sorted(examples.EXAMPLES))
def test_example_file_matches_the_printed_example(name):
    path = ROOT / "examples" / "simcase" / f"{name}.json"
    assert json.loads(path.read_text(encoding="utf-8")) == examples.EXAMPLES[name]
