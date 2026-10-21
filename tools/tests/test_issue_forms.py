# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The GitHub issue forms named in CONTRIBUTING parse and keep the intake low.

GitHub drops a malformed form silently from the chooser, so this checks the
schema keys it needs. Only the first question of each form is required:
missing evidence must not block a report.
"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FORMS = ROOT / ".github" / "ISSUE_TEMPLATE"
FORM_FILES = sorted(p for p in FORMS.glob("*.yml") if p.name != "config.yml")
INPUT_TYPES = {"input", "textarea", "dropdown", "checkboxes"}


def test_there_are_forms_for_observations_questions_and_proposals():
    names = {yaml.safe_load(p.read_text(encoding="utf-8"))["name"] for p in FORM_FILES}
    assert names == {"Bug or accuracy observation", "Question", "Feature or validation proposal"}


@pytest.mark.parametrize("path", FORM_FILES, ids=lambda p: p.name)
def test_form_schema(path):
    form = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(form["name"], str) and form["name"]
    assert isinstance(form["description"], str) and form["description"]
    body = form["body"]
    fields = [item for item in body if item["type"] in INPUT_TYPES]
    assert fields, "a form needs at least one input"
    ids = [item["id"] for item in fields]
    assert len(ids) == len(set(ids))
    for item in body:
        assert item["type"] in INPUT_TYPES | {"markdown"}
        assert item["attributes"]["label" if item["type"] != "markdown" else "value"]
        if item["type"] == "dropdown":
            assert item["attributes"]["options"]
    required = [item["id"] for item in fields if item.get("validations", {}).get("required")]
    assert required == [fields[0]["id"]]


def test_blank_issues_stay_open_and_vulnerabilities_go_private():
    config = yaml.safe_load((FORMS / "config.yml").read_text(encoding="utf-8"))
    assert config["blank_issues_enabled"] is True
    assert any("security" in link["url"] for link in config["contact_links"])
