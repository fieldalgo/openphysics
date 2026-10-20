# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Rules of tools/check_licenses.py, exercised on synthetic installed environments."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_licenses", ROOT / "tools" / "check_licenses.py")
check_licenses = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_licenses)

INVENTORY = json.loads((ROOT / "tools" / "third_party_licenses.json").read_text(encoding="utf-8"))


def install(site, name, *, version="1.0", expression=None, license=None, classifiers=(),
            requires=(), extras=(), files=(), record=True):
    info = site / f"{name.replace('-', '_')}-{version}.dist-info"
    info.mkdir(parents=True)
    if record:
        # importlib.metadata lists only RECORD entries that exist, so create them (empty).
        for path in files:
            (site / path).parent.mkdir(parents=True, exist_ok=True)
            (site / path).touch()
        listed = [*files, f"{info.name}/METADATA", f"{info.name}/RECORD"]
        (info / "RECORD").write_text("".join(f"{path},,\n" for path in listed), encoding="utf-8")
    lines = ["Metadata-Version: 2.4", f"Name: {name}", f"Version: {version}"]
    if expression:
        lines.append(f"License-Expression: {expression}")
    if license:
        lines.append(f"License: {license}")
    lines += [f"Classifier: {c}" for c in classifiers]
    lines += [f"Provides-Extra: {e}" for e in extras]
    lines += [f"Requires-Dist: {r}" for r in requires]
    (info / "METADATA").write_text("\n".join(lines) + "\n", encoding="utf-8")


def inventory(**entries):
    result = json.loads(json.dumps(INVENTORY))
    result["distributions"] = entries
    return result


def run(site, entries, platform="linux", **first_party):
    for name, kwargs in first_party.items():
        install(site, name.replace("_", "-"), license="Apache-2.0", **kwargs)
    return check_licenses.check([str(site)], inventory(**entries), check_docs=False, platform=platform)


BLAS = "numlib.libs/libblas-1a2b3c4d.so.3.1"
EXTENSIONS = ("numlib/_core.cpython-312-x86_64-linux-gnu.so", "numlib/_fast.cpython-312-darwin.so",
              "numlib/_rust.abi3.so", "numlib/_win.cp312-win_amd64.pyd")


def bundled(glob="numlib.libs/libblas-*.so.*", spdx="BSD-3-Clause", platforms=("linux",), **extra):
    return {"glob": glob, "spdx": spdx, "linkage": "dynamic", "platforms": list(platforms), **extra}


def test_permissive_runtime_dependency_passes(tmp_path):
    install(tmp_path, "numlib", expression="BSD-3-Clause")
    errors, report = run(tmp_path, {"numlib": {"spdx": "BSD-3-Clause"}},
                         galerkin={"requires": ["numlib>=1"]})
    assert errors == []
    assert report["numlib"]["use"] == "runtime"


def test_unreviewed_distribution_fails(tmp_path):
    install(tmp_path, "surprise", expression="MIT")
    errors, _ = run(tmp_path, {})
    assert any("surprise" in e and "no reviewed entry" in e for e in errors)


@pytest.mark.parametrize("spdx", ["GPL-3.0-or-later", "LGPL-2.1-or-later", "MPL-2.0"])
def test_copyleft_runtime_dependency_fails(tmp_path, spdx):
    install(tmp_path, "copylib", expression=spdx)
    errors, _ = run(tmp_path, {"copylib": {"spdx": spdx, "test_only": True}},
                    galerkin={"requires": ["copylib"]})
    assert any("not allowed for runtime use" in e for e in errors)


def test_copyleft_through_optional_extra_fails(tmp_path):
    install(tmp_path, "webstack", expression="MIT", requires=["weakdep"])
    install(tmp_path, "weakdep", expression="LGPL-3.0-or-later")
    errors, report = run(tmp_path, {"webstack": {"spdx": "MIT"},
                                    "weakdep": {"spdx": "LGPL-3.0-or-later", "test_only": True}},
                         simcase={"requires": ['webstack; extra == "studio"'], "extras": ["studio"]})
    assert report["weakdep"]["use"] == "optional"
    assert any("weakdep" in e and "optional use" in e for e in errors)


def test_weak_copyleft_allowed_only_when_marked_test_only(tmp_path):
    install(tmp_path, "certs", expression="MPL-2.0")
    first_party = {"simcase": {"requires": ['certs; extra == "test"'], "extras": ["test"]}}
    errors, report = run(tmp_path, {"certs": {"spdx": "MPL-2.0", "test_only": True}}, **first_party)
    assert errors == [] and report["certs"]["use"] == "test"
    other = tmp_path / "unmarked"
    install(other, "certs", expression="MPL-2.0")
    errors, _ = run(other, {"certs": {"spdx": "MPL-2.0"}}, **first_party)
    assert any("not allowed for test use" in e for e in errors)


def test_named_test_extras_are_test_only(tmp_path):
    install(tmp_path, "reftool", expression="MPL-2.0")
    errors, report = run(tmp_path, {"reftool": {"spdx": "MPL-2.0", "test_only": True}},
                         galerkin={"requires": ['reftool; extra == "crosscheck"'], "extras": ["crosscheck"]})
    assert errors == [] and report["reftool"]["use"] == "test"


def test_strictest_path_wins(tmp_path):
    install(tmp_path, "shared", expression="MIT")
    errors, report = run(tmp_path, {"shared": {"spdx": "MIT"}},
                         galerkin={"requires": ["shared"]},
                         simcase={"requires": ['shared; extra == "test"'], "extras": ["test"]})
    assert errors == [] and report["shared"]["use"] == "runtime"


def test_gpl_requires_external_process_entry(tmp_path):
    install(tmp_path, "mesher", license="GPLv2+",
            classifiers=["License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)"])
    errors, _ = run(tmp_path, {"mesher": {"spdx": "GPL-2.0-or-later"}})
    assert any("not allowed for tool use" in e for e in errors)
    external = {"spdx": "GPL-2.0-or-later",
                "external_process": {"executable": "mesher", "forbidden_imports": ["mesher_never_imported"]}}
    errors, report = run(tmp_path, {"mesher": external})
    assert errors == [] and report["mesher"]["use"] == "external-process"


def test_external_process_cannot_be_base_runtime(tmp_path):
    install(tmp_path, "mesher", license="GPLv2+")
    external = {"spdx": "GPL-2.0-or-later",
                "external_process": {"executable": "mesher", "forbidden_imports": ["mesher_never_imported"]}}
    errors, _ = run(tmp_path, {"mesher": external}, gmshio={"requires": ["mesher"]})
    assert any("cannot be a base runtime requirement" in e for e in errors)


def test_first_party_import_of_external_tool_is_detected():
    # numpy is imported by first-party code, so treating it as external must fail.
    assert check_licenses.first_party_imports({"numpy"})
    assert check_licenses.first_party_imports({"gmsh"}) == []
    # Examples and maintainer tools outside packages/ are first-party code too.
    assert "examples/gmshio/hadley_rib_mesh.py" in check_licenses.first_party_imports({"gmshio"})
    assert "tools/build_physmat_tables.py" in check_licenses.first_party_imports({"yaml"})


NEVER = ["AGPL-3.0-or-later", "MIT OR AGPL-3.0-only", "EUPL-1.2", "AGPL-3.0", "AGPL-1.0", "AGPL-3.0+",
         "SSPL-1.0", "OSL-2.1", "RPL-1.5", "CPAL-1.0", "LicenseRef-AGPL-3.0-custom"]


@pytest.mark.parametrize("spdx", NEVER)
def test_agpl_is_never_allowed(tmp_path, spdx):
    install(tmp_path, "netlib", expression=spdx)
    errors, _ = run(tmp_path, {"netlib": {"spdx": spdx, "test_only": True}})
    assert any("never allowed" in e for e in errors)


@pytest.mark.parametrize("spdx", ["AGPL-3.0-only", "AGPL-3.0", "SSPL-1.0"])
def test_network_copyleft_is_rejected_as_external_process(tmp_path, spdx):
    install(tmp_path, "nettool", expression=spdx)
    external = {"spdx": spdx, "external_process": {"executable": "nettool", "forbidden_imports": ["nettool_x"]}}
    errors, _ = run(tmp_path, {"nettool": external})
    assert any("never allowed" in e for e in errors)


@pytest.mark.parametrize("classifier", ["GNU Affero General Public License v3",
                                        "GNU Affero General Public License v3 or later (AGPLv3+)",
                                        "European Union Public Licence 1.2 (EUPL 1.2)"])
def test_network_copyleft_in_installed_metadata_is_rejected(tmp_path, classifier):
    # The inventory records GPL, but the installed metadata names a network-copyleft license.
    install(tmp_path, "nettool", classifiers=[f"License :: OSI Approved :: {classifier}"])
    external = {"spdx": "GPL-2.0-or-later",
                "external_process": {"executable": "nettool", "forbidden_imports": ["nettool_x"]}}
    errors, _ = run(tmp_path, {"nettool": external})
    assert any("metadata names a never-allowed license" in e for e in errors)


@pytest.mark.parametrize("spdx", ["MIT", "GPL-2.0-or-later", "LGPL-2.1-only", "OLDAP-2.8", "MPL-2.0"])
def test_never_families_do_not_match_other_licenses(spdx):
    never = check_licenses.never_pattern(INVENTORY["policy"]["never_families"])
    assert check_licenses.never_ids({spdx}, never) == []


def test_metadata_change_must_be_reviewed(tmp_path):
    install(tmp_path, "drift", expression="MIT AND LGPL-2.1-only")
    errors, _ = run(tmp_path, {"drift": {"spdx": "MIT"}})
    assert any("metadata declares" in e for e in errors)
    assert any("mentions a copyleft license" in e for e in errors)


def test_undeclared_copyleft_classifier_needs_review(tmp_path):
    install(tmp_path, "mixed", classifiers=["License :: OSI Approved :: GNU General Public License (GPL)"])
    errors, _ = run(tmp_path, {"mixed": {"spdx": "BSD-2-Clause"}})
    assert any("mentions a copyleft license" in e for e in errors)
    reviewed = tmp_path / "reviewed"
    install(reviewed, "mixed", classifiers=["License :: OSI Approved :: GNU General Public License (GPL)"])
    errors, _ = run(reviewed, {"mixed": {"spdx": "BSD-2-Clause", "metadata_review": "files outside the wheel"}})
    assert errors == []


def test_first_party_must_declare_apache(tmp_path):
    install(tmp_path, "meshine", license="MIT")
    errors, _ = check_licenses.check([str(tmp_path)], inventory(), check_docs=False)
    assert any("first-party metadata must declare Apache-2.0" in e for e in errors)


@pytest.mark.parametrize("expression, allowed, expected", [
    ("Apache-2.0 OR BSD-3-Clause", {"BSD-3-Clause"}, True),
    ("MIT AND (Zlib OR GPL-3.0-only)", {"MIT", "Zlib"}, True),
    ("MIT AND (Zlib OR GPL-3.0-only)", {"MIT"}, False),
    ("GPL-3.0-or-later WITH GCC-exception-3.1", {"MIT"}, False),
])
def test_spdx_expression_evaluation(expression, allowed, expected):
    assert check_licenses.satisfies(check_licenses.parse_expression(expression), allowed) is expected


def test_recorded_bundled_library_passes_and_is_reported(tmp_path):
    install(tmp_path, "numlib", expression="MIT", files=["numlib/__init__.py", BLAS, *EXTENSIONS])
    errors, report = run(tmp_path, {"numlib": {"spdx": "MIT", "bundled_files": [bundled()]}})
    assert errors == []
    assert report["numlib"]["bundled_files"] == [
        {"file": BLAS, "glob": "numlib.libs/libblas-*.so.*", "spdx": "BSD-3-Clause"}]


@pytest.mark.parametrize("library", [BLAS, "numlib/.dylibs/libgcc_s.1.1.dylib", "numlib.libs/msvcp140-0f1e.dll",
                                     "../../libtool.so.1"])
def test_unrecorded_bundled_library_fails(tmp_path, library):
    # A data file outside site-packages (as gmsh installs libgmsh) appears in RECORD as ../../name.
    site = tmp_path / "prefix" / "lib" / "python3.12" / "site-packages"
    install(site, "numlib", expression="MIT", files=["numlib/__init__.py", library])
    errors, _ = run(site, {"numlib": {"spdx": "MIT", "bundled_files": [bundled(glob="numlib.libs/other-*.so")]}})
    assert any(f"unrecorded bundled native library {library}" in e for e in errors)


def test_extension_modules_are_not_bundled_libraries(tmp_path):
    install(tmp_path, "numlib", expression="MIT", files=["numlib/__init__.py", *EXTENSIONS])
    errors, report = run(tmp_path, {"numlib": {"spdx": "MIT"}})
    assert errors == [] and "bundled_files" not in report["numlib"]


def test_copyleft_bundled_library_needs_review(tmp_path):
    install(tmp_path, "numlib", expression="MIT", files=[BLAS])
    unreviewed = {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx="LGPL-2.1-or-later")]}}
    errors, _ = run(tmp_path, unreviewed)
    assert any("copyleft 'LGPL-2.1-or-later' needs a review" in e for e in errors)
    reviewed = {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx="LGPL-2.1-or-later", review="dynamic")]}}
    errors, _ = run(tmp_path, reviewed)
    assert errors == []


@pytest.mark.parametrize("spdx", ["AGPL-3.0+", "AGPL-3.0-only", "MIT AND LicenseRef-SSPL"])
def test_never_allowed_bundled_record_fails(tmp_path, spdx):
    install(tmp_path, "numlib", expression="MIT", files=[BLAS])
    errors, _ = run(tmp_path, {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx=spdx, review="no")]}})
    assert any("never allowed, also when bundled" in e for e in errors)


@pytest.mark.parametrize("spdx", ["GPL-3.0-only", "GPL-2.0-or-later", "MIT AND GPL-3.0-or-later", "GPL-2.0+",
                                  "GPL-3.0-only WITH Autoconf-exception-3.0", "LicenseRef-GPL-custom"])
def test_plain_gpl_bundled_in_process_fails(tmp_path, spdx):
    # numlib is a runtime dependency, so its bundled library loads into the OpenPhysics process.
    install(tmp_path, "numlib", expression="MIT", files=[BLAS])
    entries = {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx=spdx, review="looks fine")]}}
    errors, _ = run(tmp_path, entries, galerkin={"requires": ["numlib"]})
    assert any("only an external_process entry may bundle it" in e for e in errors)


@pytest.mark.parametrize("spdx", ["FTL OR GPL-2.0-or-later", "GPL-3.0-or-later WITH GCC-exception-3.1",
                                  "LGPL-2.1-or-later", "BSD-3-Clause AND GPL-3.0-or-later WITH GCC-exception-3.1"])
def test_gpl_with_exception_or_other_option_bundled_in_process_passes(tmp_path, spdx):
    install(tmp_path, "numlib", expression="MIT", files=[BLAS])
    entries = {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx=spdx, review="reviewed")]}}
    errors, _ = run(tmp_path, entries, galerkin={"requires": ["numlib"]})
    assert errors == []


def test_external_process_entry_may_bundle_gpl_library(tmp_path):
    library = "../../lib/libmesher.so.4.15"
    site = tmp_path / "prefix" / "lib" / "python3.12" / "site-packages"
    install(site, "mesher", license="GPLv2+", files=["mesher/__init__.py", library])
    external = {"spdx": "GPL-2.0-or-later",
                "external_process": {"executable": "mesher", "forbidden_imports": ["mesher_never_imported"]},
                "bundled_files": [bundled(glob="*/libmesher.so.*", spdx="GPL-2.0-or-later", review="own library")]}
    errors, report = run(site, {"mesher": external}, gmshio={"requires": ['mesher; extra == "mesh"'],
                                                             "extras": ["mesh"]})
    assert errors == [] and report["mesher"]["bundled_files"][0]["file"] == library


@pytest.mark.parametrize("spdx", ["LicenseRef-Proprietary", "LicenseRef-MSVC-Redistributable", "Qhull", "FTL",
                                  "MIT AND LicenseRef-Vendor"])
def test_non_permissive_bundled_library_needs_review(tmp_path, spdx):
    install(tmp_path, "numlib", expression="MIT", files=[BLAS])
    errors, _ = run(tmp_path, {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx=spdx)]}})
    assert any(f"{spdx!r} is not on the permissive lists and needs a review" in e for e in errors)
    errors, _ = run(tmp_path, {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx=spdx, review="terms read")]}})
    assert errors == []


@pytest.mark.parametrize("spdx", ["BSD-3-Clause AND BSD-3-Clause-Open-MPI", "IJG AND Zlib", "X11", "0BSD",
                                  "MIT OR LicenseRef-Vendor"])
def test_permissive_bundled_library_needs_no_review(tmp_path, spdx):
    install(tmp_path, "numlib", expression="MIT", files=[BLAS])
    errors, _ = run(tmp_path, {"numlib": {"spdx": "MIT", "bundled_files": [bundled(spdx=spdx)]}})
    assert errors == []


def test_bundled_library_must_be_recorded_for_this_platform(tmp_path):
    install(tmp_path, "numlib", expression="MIT", files=[BLAS])
    errors, _ = run(tmp_path, {"numlib": {"spdx": "MIT", "bundled_files": [bundled()]}}, platform="windows")
    assert any("recorded for ['linux'], but is installed on windows" in e for e in errors)


def test_bundled_files_records_are_validated(tmp_path):
    entries = {"numlib": {"spdx": "MIT", "bundled_files": [
        {"glob": "a/*.so"},
        bundled(glob="b/*.so", linkage="static"),
        bundled(glob="c/*.so", platforms=("solaris",)),
        bundled(glob="d/*.so", spdx="AGPL-3.0-only", review="no"),
        bundled(glob="e/*.so"), bundled(glob="e/*.so")]}}
    errors, _ = run(tmp_path, entries)
    for expected in ("missing ['linkage', 'platforms', 'spdx']", "separate library files are dynamic",
                     "platforms must be a non-empty subset", "never allowed, also when bundled", "duplicate glob"):
        assert any(expected in e for e in errors), expected


def test_missing_record_cannot_be_checked(tmp_path):
    install(tmp_path, "numlib", expression="MIT", record=False)
    errors, _ = run(tmp_path, {"numlib": {"spdx": "MIT"}})
    assert any("no RECORD file list" in e for e in errors)


@pytest.mark.parametrize("native", ["galerkin/_assemble.cpython-312-x86_64-linux-gnu.so", "galerkin/_kernel.pyd",
                                    "galerkin.libs/libhelper-1234.so.1"])
def test_first_party_distribution_must_not_contain_native_files(tmp_path, native):
    errors, _ = run(tmp_path, {}, galerkin={"files": ["galerkin/__init__.py", native]})
    assert any("first-party distribution contains native files" in e and native in e for e in errors)


def test_inventory_entries_are_valid_and_documented():
    policy = INVENTORY["policy"]
    known = set(policy["permissive"]) | set(policy["weak_copyleft"]) | {"GPL-2.0-or-later"}
    for name, entry in INVENTORY["distributions"].items():
        assert check_licenses.bundled_entry_errors(name, entry, policy) == []
        ids = check_licenses.identifiers(check_licenses.parse_expression(entry["spdx"]))
        assert ids <= known, (name, ids)
        assert entry["url"].startswith("https://"), name
        if ids & set(policy["weak_copyleft"]):
            assert entry.get("test_only") and entry.get("review"), name
        if "GPL-2.0-or-later" in ids:
            assert "external_process" in entry, name
    for doc in check_licenses.DOCS:
        text = doc.read_text(encoding="utf-8")
        for name in INVENTORY["distributions"]:
            assert f"`{name}`" in text, (doc.name, name)
