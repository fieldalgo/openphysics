# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Public document dispatch for steady boundary data (format 0.3); no runtime/save adapter."""
import copy
import json

import pytest

from simcase.schema import Document, DocumentError
from simcase.steady_boundary_contract import (
    V1_03 as V1, V2_03 as V2, validate_steady_boundary, steady_result_versions,
)


def raw():
    # name, materials, study and results take their structural defaults
    return {
        "openphysics": "0.3",
        "geometry": {"length_unit": "mm", "depth": None, "domain": {"xmin": 0, "xmax": 1000, "ymin": 0, "ymax": 1000}},
        "physics": {"heat1": {
            "type": "thermal.steady2d", "thermal_conductivity": "2 W/(m K)",
            "prescribed_temperature": {"left": "300 K"},
        }},
        "mesh": {"subdivision_count": [2, 2]},
    }


def boundary_document():
    d = raw()
    d["physics"]["heat1"].update(
        inward_heat_flux={"right": "-2 W/m^2"},
        convection={"right": {"heat_transfer_coefficient": "4 W/(m^2 K)", "ambient_temperature": "290 K"}})
    return d


def set_path(data, path, value):
    node = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


@pytest.mark.parametrize("presence", ["flux", "convection", "both"])
def test_empty_mapping_presence_enters_strict_path_without_implicit_keys(presence):
    data = raw()
    p = data["physics"]["heat1"]
    if presence in ("flux", "both"):
        p["inward_heat_flux"] = {}
    if presence in ("convection", "both"):
        p["convection"] = {}
    before = copy.deepcopy(data)
    doc = Document.from_dict(data)
    assert data == before
    normalized = doc.sole_physics()[1]
    assert ("inward_heat_flux" in normalized) == ("inward_heat_flux" in p)
    assert ("convection" in normalized) == ("convection" in p)
    assert steady_result_versions(doc) == V2
    assert doc["openphysics"] == "0.3"
    # no value is written back: the absent source and the structural defaults are echoed
    assert "heat_source_density" not in normalized and "heat_source_density" not in doc.si["physics"]["heat1"]
    assert sorted(d["path"] for d in doc.defaults_applied) == [
        "materials", "name", "physics.heat1.heat_source_density", "results", "study"]
    assert doc.si["study"] == {"type": "single"}
    assert doc.si["results"] == {"save_fields": True, "plots": False}
    assert doc.si["geometry"]["domain"]["xmax"] == 1.
    assert V2[0] in doc.summary()


def test_legacy_no_mapping_keeps_defaults_and_refuses_the_numeric_format():
    data = raw()
    data["mesh"]["subdivision_count"] = (2, 2)  # a tuple reads as the JSON list it writes
    doc = Document.from_dict(data)
    assert doc.si["mesh"]["subdivision_count"] == [2, 2]
    assert "inward_heat_flux" not in doc.sole_physics()[1]
    assert "convection" not in doc.sole_physics()[1]
    assert "remaining exterior insulated" in doc.summary()
    assert V2[0] not in doc.summary() and V1[0] in doc.summary()
    assert "heat_source_density" not in doc.si["physics"]["heat1"]
    data["openphysics"] = .3  # the format is the JSON string "0.3", not a number
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics] == [("E-FORMAT", "openphysics")]


@pytest.mark.parametrize("path,value", [
    ("openphysics", .2),
    ("openphysics", "0.2"),
    ("physics.heat1.convection", None),
    ("physics.heat1.inward_heat_flux", None),
    ("physics.heat1.convection.right.heat_transfer_coefficient", True),
    ("physics.heat1.convection.right.heat_transfer_coefficient", "-1 W/(m^2 K)"),
    ("physics.heat1.convection.right.ambient_temperature", "-1 K"),
    ("physics.heat1.convection.right.ambient_temperature", float("nan")),
    ("physics.heat1.inward_heat_flux.right", float("inf")),
    ("physics.heat1.prescribed_temperature.left", True),
    ("physics.heat1.convection.right.unknown", 0),
    ("physics.heat1.inward_heat_flux.unknown", "0 W/m^2"),
    ("units.time", "s"),
    ("results.plots", True),
])
def test_from_dict_rejects_invalid_new_contract(path, value):
    data = boundary_document()
    Document.from_dict(copy.deepcopy(data))
    set_path(data, path, value)
    with pytest.raises(DocumentError):
        Document.from_dict(data)


@pytest.mark.parametrize("key", ["inward_heat_flux", "convection"])
def test_even_null_mapping_is_presence_not_legacy_fallback(key):
    data = raw()
    data["physics"]["heat1"][key] = None
    with pytest.raises(DocumentError, match=key):
        Document.from_dict(data)


def test_robin_only_and_zero_h_anchor_policy():
    data = boundary_document()
    p = data["physics"]["heat1"]
    p["prescribed_temperature"] = {}
    doc = Document.from_dict(data)
    assert doc.sole_physics()[1]["prescribed_temperature"] == {}
    assert "q.n = -inward_heat_flux + h (T - ambient_temperature)" in doc.summary()
    p["convection"]["right"]["heat_transfer_coefficient"] = "0 W/(m^2 K)"
    with pytest.raises(DocumentError, match="anchor"):
        Document.from_dict(data)


def test_legacy_empty_constraints_still_reject():
    data = raw()
    data["physics"]["heat1"]["prescribed_temperature"] = {}
    with pytest.raises(DocumentError, match="at least one"):
        Document.from_dict(data)


@pytest.mark.parametrize("entry", ["validate", "summary"])
@pytest.mark.parametrize("path,value", [
    ("physics.heat1.convection.right.heat_transfer_coefficient", "-1 W/(m^2 K)"),
    ("physics.heat1.convection.right.ambient_temperature", True),
    ("physics.heat1.inward_heat_flux.right", float("nan")),
    ("physics.heat1.prescribed_temperature.bottom", "301 K"),
])
def test_direct_document_mutation_checked_at_validation_and_summary(entry, path, value):
    doc = Document.from_dict(boundary_document())
    set_path(doc.data, path, value)       # a caller changing the authored tree after reading
    with pytest.raises(DocumentError):
        getattr(doc, entry)()


def test_summary_uses_new_boundary_meaning_and_never_legacy_insulation_claim():
    doc = Document.from_dict(boundary_document())
    summary = doc.summary()
    assert "convection" in summary and "inward_heat_flux" in summary
    assert "unselected natural sides insulated" in summary
    assert "remaining exterior insulated" not in summary
    assert V2[0] in summary and V2[1] in summary
    assert "nodal heat rates W/m of depth" in summary


def test_utf8_load_save_roundtrip_and_invalid_load(tmp_path):
    data = boundary_document()
    data["name"] = "Boundary \u0394T"
    path = tmp_path/"boundary.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    doc = Document.load(path)
    doc.save(tmp_path/"saved.json")
    assert (tmp_path/"saved.json").read_bytes() == path.read_bytes()    # the authored bytes
    other = Document.load(tmp_path/"saved.json")
    assert other.data == doc.data
    assert other.summary() == doc.summary()
    data["physics"]["heat1"]["convection"]["right"]["heat_transfer_coefficient"] = "-1 W/(m^2 K)"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DocumentError):
        Document.load(path)


def test_validator_stays_non_mutating_and_schema_writes_no_default():
    doc = Document.from_dict(boundary_document())
    before = copy.deepcopy(doc.data)
    scale, notes = doc.scale, doc.notes
    validate_steady_boundary(doc)
    assert doc.data == before and doc.scale is scale and doc.notes is notes
    doc.validate()
    assert doc.data == before and "heat_source_density" not in doc.sole_physics()[1]
    assert not doc.diagnostics.errors


def test_legacy_list_document_remains_v1():
    doc = Document.from_dict(raw())
    assert steady_result_versions(doc) == V1
    assert "inward_heat_flux" not in doc.sole_physics()[1]


def test_p1_transient_dispatch_and_temperature_policy():
    from simcase.examples import TRANSIENT_THERMAL_UNIFORM
    data = copy.deepcopy(TRANSIENT_THERMAL_UNIFORM)
    doc = Document.from_dict(data)
    assert doc.sole_physics()[1]["type"] == "thermal.transient2d"
    assert "explicit times" in doc.summary()
    # absolute temperatures are above 0 K since the units batch: a negative initial is refused
    data["physics"]["heat1"]["initial_temperature"] = "-10 K"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [
        ("E-DOMAIN", "physics.heat1.initial_temperature")]
    # The transient contract reads the same boundary keys with its own layout pair.
    from simcase.transient_thermal_contract import V2_03, transient_result_versions
    data["physics"]["heat1"]["initial_temperature"] = "300 K"
    data["physics"]["heat1"]["convection"] = {}
    doc = Document.from_dict(data)
    assert transient_result_versions(doc) == V2_03
    data["physics"]["heat1"]["convection"] = {"right": {"heat_transfer_coefficient": "1 W/(m^2 K)",
                                                        "ambient_temperature": "-1 K"}}
    with pytest.raises(DocumentError, match="ambient_temperature"):
        Document.from_dict(data)


def test_em_scalar_dispatch_unchanged():
    from simcase.examples import SOI_STRIP
    doc = Document.from_dict(copy.deepcopy(SOI_STRIP))
    assert doc.sole_physics()[1]["type"] == "em.modes2d"
    assert "em.modes2d" in doc.summary()
