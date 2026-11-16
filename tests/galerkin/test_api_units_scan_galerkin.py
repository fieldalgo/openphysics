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
    # galerkin.kernels exists since L2 commit 4: the public names and objects are disjoint from its own (D7).
    problems = api_scan.kernel_disjointness(PACKAGE, rules)
    assert problems is not None and importlib.util.find_spec("galerkin.kernels") is not None
    assert not problems, "\n".join(problems)


# L2 commit 4 (Appendix D, D21): the top-level assembly and solve kernels and the physics modules' helpers left
# the public API for the internal galerkin.kernels, which re-exports them unchanged from their modules.
MOVED_TOP_LEVEL = {"assembly": ["assemble_stiffness", "assemble_mass", "assemble_boundary_mass", "assemble_load"],
                   "assembly3d": ["tet_gradients", "assemble_stiffness_3d", "assemble_mass_3d"],
                   "solver": ["solve_dirichlet"]}
MOVED_HELPERS = {"elasticity": ["lame", "constitutive", "element_materials", "element_constitutive",
                                "stiffness_and_stress", "stress_of", "body_load", "check_solution", "displacement",
                                "at_fixed", "vector_stiffness"],
                 "thermoelasticity": ["verify_snapshot", "thermal_coefficient", "physical_energy"],
                 "thermal": ["scalar_boundary_system"], "thermal3d": ["source_load_3d", "dirichlet_from_faces"],
                 "materials": ["region_property"],
                 "shape": ["solve_steady_heat_moving", "solve_transient_heat_moving", "solve_steady_electric_moving",
                           "solve_elasticity_moving", "solve_thermoelasticity_moving",
                           "solve_steady_thermoelasticity_moving"]}


def test_kernels_reexport_the_moved_names_unchanged(rules):
    import galerkin
    import galerkin.kernels as kernels
    moved = {**MOVED_TOP_LEVEL, **MOVED_HELPERS}
    assert sorted(kernels.__all__) == sorted(n for names in moved.values() for n in names)
    for module, names in moved.items():
        defining = importlib.import_module(f"galerkin.{module}")
        for name in names:
            assert getattr(kernels, name) is getattr(defining, name), name
    for name in (n for names in MOVED_TOP_LEVEL.values() for n in names):
        assert name not in galerkin.__all__ and not hasattr(galerkin, name), name
    public = {n for m in rules.public[PACKAGE] for n in api_scan.public_names(importlib.import_module(m))}
    assert not public & set(kernels.__all__)
    removed = {r.name for r in rules.removed if r.package == PACKAGE}
    assert removed == set(kernels.__all__) - {"region_property"}      # galerkin.materials was never public
    assert "galerkin.kernels" in rules.internal[PACKAGE]


def test_star_import_gives_the_public_names():
    namespace = {}
    exec("from galerkin import *", namespace)
    names = set(namespace) - {"__builtins__"}
    # 78 before L2 commit 4: its 8 kernels left, and so did the submodules assembly3d and solver, which the
    # top-level imports no longer bind.
    assert len(names) == 68 and {"Mesh", "solve_modes", "scalar_effective_area", "core", "waveguide"} <= names
    assert not names & {"assemble_stiffness", "solve_dirichlet", "tet_gradients", "assembly3d", "solver", "kernels"}
