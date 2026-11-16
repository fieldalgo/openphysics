# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""physmat's public API against the units convention, and the scan's own checks.

The rule, the module lists and the structural names are shared with galerkin and refsol
in tests/_support/ (api_scan.py and its JSON files). The first part holds physmat's part:
api_units_allowlist.json next to it lists today's violations, and entries may only be
removed. ``physmat.units`` is public but not scanned. The second part checks the shared
rule data, and shows on small synthetic packages that the scan catches each kind of
violation and passes compliant code. docs/development.md describes the scan.
"""
import importlib
import importlib.util
import inspect
import json
import sys
import textwrap
from importlib import resources
from pathlib import Path

import pytest

import api_scan

PACKAGE = "physmat"
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
    assert rules.excluded == {"physmat.units"}


def test_public_modules_export_only_their_own_callables(rules):
    _, foreign = api_scan.package_items(PACKAGE, rules)
    assert not foreign, "\n".join(foreign)


def test_listed_result_classes_exist(rules):
    # Their constructors are outside the scan; their field names are check P3-11's job.
    problems = api_scan.result_class_problems(PACKAGE, rules)
    assert not problems, "\n".join(problems)
    assert ("physmat.material", "Material") not in rules.result_classes      # handled in L1 commit 3
    assert ("physmat.material", "Property") not in rules.result_classes


def test_clean_modules_refuse_strings_and_removed_names(rules):
    problems = api_scan.string_refusal_problems(PACKAGE, ALLOWLIST, rules, STRING_CASES)
    problems += api_scan.removed_name_problems(PACKAGE, ALLOWLIST, rules)
    assert not problems, "\n".join(problems)


def test_public_names_are_not_kernel_names(rules):
    problems = api_scan.kernel_disjointness(PACKAGE, rules)
    if problems is None:
        # Nothing to compare yet: physmat.kernels does not exist until the physmat commit
        # of the first landing creates it. This passes instead of skipping, because the
        # installed-tests job fails on any skip; once the namespace exists it compares.
        assert importlib.util.find_spec("physmat.kernels") is None
        return
    assert not problems, "\n".join(problems)


# ---- the shared rule data ---------------------------------------------------------------------------------------

# The seed list of Appendix A of the phase-3 spec, pre-registered: each name keeps its category.
SEED = {
    "object": "mesh space motion modes incident pml bend field to_mesh",
    "positional data": "points nodes triangles values",
    "index or count": "mode mode_a mode_b incident_mode subdivision_count checkpoint_every time_indices layer",
    "enum": "coordinate_system plane bend_axis pol kind method backend convention",
    "mapping of tags": "regions boundary_tags pec_nodes pec_edges pec_faces conductors ground tags",
    "flag": "strict include_longitudinal live",
    "path or text": "path name label key",
    "mesher, pending": "width height nx ny r_inner r_outer n_r n_theta",
}


def test_structural_list_is_closed_and_keeps_the_seed(rules):
    assert not api_scan.structural_problems(rules)
    for category, names in SEED.items():
        for name in names.split():
            assert rules.structural[name].category == category, name
    assert rules.structural["points"].scope == ("refsol",)
    assert "tol" not in rules.structural and "sigma" not in rules.structural
    assert {e.category for e in rules.structural.values()} == set(api_scan.CATEGORIES)


def test_mesher_names_are_structural_only_in_the_mesh_modules(rules):
    for module in ("galerkin.mesh", "galerkin.mesh3d"):
        assert api_scan.structural_entry("width", module, rules) is not None
    for module in ("galerkin", "galerkin.thermal", "refsol.electrostatics", "galerkin.meshes"):
        assert api_scan.structural_entry("width", module, rules) is None
    for e in rules.structural.values():
        assert (e.category == "mesher, pending") == (e.scope == api_scan.MESHER_SCOPE), e.name


def test_removed_names_file_loads(rules):
    assert all(r.package in rules.packages for r in rules.removed)


def test_unit_tokens_come_from_the_unit_table(rules):
    table = json.loads(resources.files("physmat").joinpath("unit_tables.json").read_text(encoding="utf-8"))
    derived = set()
    for symbol in table["units"]:
        derived |= api_scan.symbol_tokens(symbol)
    assert rules.tokens == derived
    spec_examples = "um m nm m2 um2 k c s hz pa ppm ev db deg mk m3k".split()
    assert set(spec_examples) <= rules.tokens
    for name, token in [("temperature_k", "k"), ("wavelength_um", "um"), ("time_s", "s"), ("pressure_pa", "pa"),
                        ("thermal_expansion_per_k", "k"), ("conductivity_w_mk", "mk"),
                        ("volumetric_heat_capacity_j_m3k", "m3k"), ("frequency_hz", "hz"), ("co2_ppm", "ppm")]:
        assert api_scan.unit_token(name, rules.tokens) == token, name
    for name in ("temperature", "vacuum_wavelength", "mode_b", "um", "k"):
        assert api_scan.unit_token(name, rules.tokens) is None, name
    assert not [n for n in rules.registry if api_scan.unit_token(n, rules.tokens)]


def test_dimensional_defaults(rules):
    assert not api_scan.is_dimensional_default(None, "K")
    assert not api_scan.is_dimensional_default(True, "K")
    assert not api_scan.is_dimensional_default("cartesian", "K")
    assert not api_scan.is_dimensional_default(0.3, "1")
    assert not api_scan.is_dimensional_default(6, "1")
    assert api_scan.is_dimensional_default(0.0, "W/m^3")
    assert api_scan.is_dimensional_default(300, "K")
    assert api_scan.is_dimensional_default((0.0, 0.0), "N/m^3")


# ---- the scan on synthetic packages -----------------------------------------------------------------------------

PLANTED = '''
"""A package with one violation of each kind, and compliant callables beside them."""
__all__ = ["planted", "compliant", "defaulted", "positional", "unplaced", "Thing", "CONSTANT", "helpers"]

from . import helpers

CONSTANT = 1.0


def planted(*, length_um=1.0):
    return length_um


def compliant(mesh, *, length, temperature=None, poisson_ratio=0.3, coordinate_system="cartesian"):
    return length


def defaulted(*, length=1.0):
    return length


def positional(length):
    return length


def unplaced(*, effective_index):
    return effective_index


class Thing:
    def __init__(self, *, temperature_k):
        self.temperature_k = temperature_k

    def at(self, wavelength):
        return wavelength

    def _private(self, anything_um):
        return anything_um
'''

HELPERS = '''
"""Helpers without the internal line."""
'''

CLEAN = '''
"""A compliant package whose one quantity refuses strings."""
__all__ = ["guarded", "lenient"]


def guarded(mesh, *, length):
    if isinstance(length, str):
        raise TypeError("SI numbers only")
    return length


def lenient(*, temperature):
    return temperature
'''

KERNELS = '''
"""Kernels: one shares a public name, one is the public object itself."""
from . import guarded as same_object


def guarded(mesh, length):
    return length
'''


@pytest.fixture
def make_package(tmp_path, monkeypatch):
    """Write a synthetic package under tmp_path and import it fresh; forget it afterwards."""
    made = []

    def make(name, files):
        root = tmp_path / name
        root.mkdir()
        for rel, text in files.items():
            (root / rel).write_text(textwrap.dedent(text), encoding="utf-8")
        monkeypatch.syspath_prepend(str(tmp_path))
        importlib.invalidate_caches()
        made.append(name)
        return root

    yield make
    for key in [k for k in sys.modules if any(k == n or k.startswith(n + ".") for n in made)]:
        del sys.modules[key]


def _rules(rules, package, public, internal=(), removed=(), result_classes=()):
    return api_scan.Rules(packages=(package,), public={package: tuple(public)}, internal={package: tuple(internal)},
                          excluded=frozenset(), structural=rules.structural, removed=tuple(removed),
                          registry=rules.registry, tokens=rules.tokens, result_classes=frozenset(result_classes))


def _allowlist(tmp_path, package, entries):
    path = tmp_path / f"{package}_allowlist.json"
    path.write_text(api_scan.format_allowlist(package, entries), encoding="utf-8")
    return path


EXPECTED = {
    ("apiscan_planted", "planted", "length_um", "unregistered"),
    ("apiscan_planted", "planted", "length_um", "unit-suffix"),
    ("apiscan_planted", "defaulted", "length", "dimensional-default"),
    ("apiscan_planted", "positional", "length", "positional"),
    ("apiscan_planted", "unplaced", "effective_index", "no-api-place"),
    ("apiscan_planted", "Thing", "temperature_k", "unregistered"),
    ("apiscan_planted", "Thing", "temperature_k", "unit-suffix"),
    ("apiscan_planted", "Thing.at", "wavelength", "unregistered"),
}


def test_scan_catches_each_planted_violation_and_passes_compliant_code(rules, tmp_path, make_package):
    assert "api" not in rules.registry["effective_index"][0]       # the no-api-place probe stays valid
    make_package("apiscan_planted", {"__init__.py": PLANTED, "helpers.py": HELPERS})
    synthetic = _rules(rules, "apiscan_planted", ["apiscan_planted"], ["apiscan_planted.helpers"])
    assert api_scan.package_violations("apiscan_planted", synthetic) == EXPECTED

    module = importlib.import_module("apiscan_planted")
    items, foreign = api_scan.public_items(module, ("apiscan_planted",))
    assert not foreign
    names = {i.name for i in items}
    assert {"compliant", "Thing", "Thing.at"} <= names and "Thing._private" not in names
    compliant = next(i for i in items if i.name == "compliant")
    assert not api_scan.violations([compliant], synthetic)


def test_allowlist_must_match_the_violations_exactly(rules, tmp_path, make_package):
    make_package("apiscan_planted", {"__init__.py": PLANTED, "helpers.py": HELPERS})
    synthetic = _rules(rules, "apiscan_planted", ["apiscan_planted"], ["apiscan_planted.helpers"])

    exact = _allowlist(tmp_path, "apiscan_planted", EXPECTED)
    assert api_scan.allowlist_problems("apiscan_planted", exact, synthetic) == []
    assert api_scan.allowlist_format_problems("apiscan_planted", exact, baseline=len(EXPECTED)) == []

    missing = _allowlist(tmp_path, "apiscan_planted", EXPECTED - {("apiscan_planted", "planted", "length_um",
                                                                    "unit-suffix")})
    problems = api_scan.allowlist_problems("apiscan_planted", missing, synthetic)
    assert len(problems) == 1 and problems[0].startswith("new violation") and "length_um" in problems[0]

    stale_entry = ("apiscan_planted", "compliant", "length", "positional")
    stale = _allowlist(tmp_path, "apiscan_planted", EXPECTED | {stale_entry})
    problems = api_scan.allowlist_problems("apiscan_planted", stale, synthetic)
    assert len(problems) == 1 and problems[0].startswith("stale allowlist entry") and "compliant" in problems[0]
    problems = api_scan.allowlist_format_problems("apiscan_planted", stale, baseline=len(EXPECTED))
    assert len(problems) == 1 and "may only be removed" in problems[0]

    unsorted = tmp_path / "unsorted.json"
    text = json.loads(exact.read_text(encoding="utf-8"))
    text["entries"] = list(reversed(text["entries"]))
    unsorted.write_text(json.dumps(text), encoding="utf-8")
    assert "canonical" in api_scan.allowlist_format_problems("apiscan_planted", unsorted, baseline=99)[0]


def test_module_lists_and_internal_docstrings(rules, tmp_path, make_package):
    make_package("apiscan_planted", {"__init__.py": PLANTED, "helpers.py": HELPERS,
                                                         "extra.py": '"""Internal module, consistent units."""\n'})
    synthetic = _rules(rules, "apiscan_planted", ["apiscan_planted", "apiscan_planted.gone"],
                       ["apiscan_planted.helpers"])
    problems = api_scan.module_problems("apiscan_planted", synthetic)
    assert sorted(problems) == sorted([
        "apiscan_planted.extra is on neither the public nor the internal module list",
        "apiscan_planted.gone is listed but does not exist",
        "internal module apiscan_planted.helpers: its docstring does not say 'Internal module, consistent units'",
    ])


def test_clean_module_clauses(rules, tmp_path, make_package):
    make_package("apiscan_clean", {"__init__.py": CLEAN, "kernels.py": KERNELS})
    removed = [api_scan.Removed("apiscan_clean", "parameter", "length", "test"),
               api_scan.Removed("apiscan_clean", "name", "lenient", "test"),
               api_scan.Removed("apiscan_clean", "name", "gone", "test")]
    synthetic = _rules(rules, "apiscan_clean", ["apiscan_clean"], ["apiscan_clean.kernels"], removed)
    assert api_scan.package_violations("apiscan_clean", synthetic) == set()
    empty = _allowlist(tmp_path, "apiscan_clean", [])
    assert api_scan.clean_modules("apiscan_clean", empty, synthetic) == ["apiscan_clean"]

    module = importlib.import_module("apiscan_clean")
    cases = {"apiscan_clean:guarded": lambda: (module.guarded, {"mesh": None, "length": 1.0}),
             "apiscan_clean:lenient": lambda: (module.lenient, {"temperature": 300.0})}
    assert api_scan.string_refusal_problems("apiscan_clean", empty, synthetic, cases) == [
        "apiscan_clean:lenient: a str for temperature was accepted"]
    problems = api_scan.string_refusal_problems("apiscan_clean", empty, synthetic,
                                                {"apiscan_clean:guarded": lambda: (module.guarded, {"length": 1.0})})
    assert problems[0].startswith("apiscan_clean:guarded: the string-refusal case is not a valid call")
    assert problems[1].startswith("apiscan_clean:lenient (public through apiscan_clean")

    assert sorted(api_scan.removed_name_problems("apiscan_clean", empty, synthetic)) == [
        "apiscan_clean.lenient still exists (test)", "apiscan_clean:guarded still takes length (test)"]

    # The clauses wait while the module still has allowlist entries.
    waiting = _allowlist(tmp_path, "apiscan_clean", [("apiscan_clean", "lenient", "temperature", "positional")])
    assert api_scan.clean_modules("apiscan_clean", waiting, synthetic) == []
    assert api_scan.string_refusal_problems("apiscan_clean", waiting, synthetic, {}) == []
    assert api_scan.removed_name_problems("apiscan_clean", waiting, synthetic) == []

    assert sorted(api_scan.kernel_disjointness("apiscan_clean", synthetic)) == [
        "apiscan_clean.guarded has the name of a kernel",
        "apiscan_clean.guarded is the kernel apiscan_clean.kernels.same_object"]


def test_constructors_of_builtin_bases_and_methods_are_handled(rules, tmp_path, make_package):
    make_package("apiscan_classes", {"__init__.py": '''
        """Classes whose constructor or methods come from elsewhere."""
        __all__ = ["Refusal", "Derived", "Plain"]


        class Refusal(ValueError):
            pass


        class Base:
            def shared(self, *, length):
                return length

            @staticmethod
            def static(length_um):
                return length_um

            @classmethod
            def build(cls, *, temperature):
                return cls()


        class Derived(Base):
            def shared(self, *, length):
                return length


        class Plain:
            pass
        '''})
    module = importlib.import_module("apiscan_classes")
    items, _ = api_scan.public_items(module, ("apiscan_classes",))
    by_name = {i.name: i for i in items}
    assert set(by_name) == {"Derived.shared", "Base.static", "Base.build"}
    assert list(by_name["Base.build"].signature.parameters) == ["temperature"]
    assert list(by_name["Base.static"].signature.parameters) == ["length_um"]
    assert inspect.signature(module.Derived.shared).parameters["self"]
    synthetic = _rules(rules, "apiscan_classes", ["apiscan_classes"])
    assert api_scan.package_violations("apiscan_classes", synthetic) == {
        ("apiscan_classes", "Base.static", "length_um", "unregistered"),
        ("apiscan_classes", "Base.static", "length_um", "unit-suffix")}


def test_call_is_scanned_and_result_constructors_are_not(rules, make_package):
    make_package("apiscan_results", {"__init__.py": '''
        """A result class and a callable class."""
        __all__ = ["Result", "Model"]


        class Result:
            def __init__(self, temperature_k):
                self.temperature_k = temperature_k

            def at(self, wavelength_um):
                return wavelength_um


        class Model:
            def __init__(self, *, temperature):
                self.temperature = temperature

            def __call__(self, T=293.15):
                return T
        '''})
    calls = {("apiscan_results", "Model.__call__", "T", "unregistered")}
    result_ctor = {("apiscan_results", "Result", "temperature_k", "unregistered"),
                   ("apiscan_results", "Result", "temperature_k", "unit-suffix")}
    result_method = {("apiscan_results", "Result.at", "wavelength_um", "unregistered"),
                     ("apiscan_results", "Result.at", "wavelength_um", "unit-suffix")}
    plain = _rules(rules, "apiscan_results", ["apiscan_results"])
    assert api_scan.package_violations("apiscan_results", plain) == calls | result_ctor | result_method
    listed = _rules(rules, "apiscan_results", ["apiscan_results"], result_classes=[("apiscan_results", "Result")])
    assert api_scan.package_violations("apiscan_results", listed) == calls | result_method
