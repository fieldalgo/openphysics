# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin's public API against the units convention: the API units scan.

The rule, the module lists and the structural names are shared with refsol and physmat
in tests/_support/ (api_scan.py and its JSON files). This file holds galerkin's part:
api_units_allowlist.json next to it lists today's violations, and entries may only be
removed. docs/development.md describes the scan.
"""
import importlib.util
from pathlib import Path

import pytest

import api_scan

PACKAGE = "galerkin"
ALLOWLIST = Path(__file__).with_name("api_units_allowlist.json")

# Valid calls for the TypeError clause, keyed "module:callable": each returns the callable
# and keyword arguments that make a valid call. A module needs them once it has no
# allowlist entries and takes a quantity.
STRING_CASES = {}


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


def test_public_parameters_match_the_allowlist(rules):
    problems = api_scan.allowlist_problems(PACKAGE, ALLOWLIST, rules)
    assert not problems, "\n".join(problems)


def test_allowlist_is_canonical_and_never_grows():
    problems = api_scan.allowlist_format_problems(PACKAGE, ALLOWLIST)
    assert not problems, "\n".join(problems)


def test_every_module_is_public_or_internal(rules):
    problems = api_scan.module_problems(PACKAGE, rules)
    assert not problems, "\n".join(problems)


def test_public_modules_export_only_their_own_callables(rules):
    _, foreign = api_scan.package_items(PACKAGE, rules)
    assert not foreign, "\n".join(foreign)


def test_listed_result_classes_exist(rules):
    # Their constructors are outside the scan; their field names are check P3-11's job.
    problems = api_scan.result_class_problems(PACKAGE, rules)
    assert not problems, "\n".join(problems)


def test_clean_modules_refuse_strings_and_removed_names(rules):
    problems = api_scan.string_refusal_problems(PACKAGE, ALLOWLIST, rules, STRING_CASES)
    problems += api_scan.removed_name_problems(PACKAGE, ALLOWLIST, rules)
    assert not problems, "\n".join(problems)


def test_public_names_are_not_kernel_names(rules):
    problems = api_scan.kernel_disjointness(PACKAGE, rules)
    if problems is None:
        # Nothing to compare yet: galerkin.kernels does not exist until it is created in
        # the non-em landing. This passes instead of skipping, because the installed-tests
        # job fails on any skip; once the namespace exists the comparison runs.
        assert importlib.util.find_spec("galerkin.kernels") is None
        return
    assert not problems, "\n".join(problems)


def test_star_import_keeps_todays_names():
    namespace = {}
    exec("from galerkin import *", namespace)
    names = set(namespace) - {"__builtins__"}
    assert len(names) == 78 and {"Mesh", "solve_modes", "scalar_effective_area", "core", "waveguide"} <= names
