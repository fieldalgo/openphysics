# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Public document dispatch for steady boundary data; no runtime/save adapter."""
import copy
import json

import pytest

from simcase.schema import Document, DocumentError
from simcase.steady_boundary_contract import (
    V1, V2, validate_steady_boundary, steady_result_versions,
)


def raw():
    return {
        "name": "Steady boundary schema",
        "units": {"length": "mm", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0, "xmax": 1000, "ymin": 0, "ymax": 1000}},
        "physics": {"heat1": {
            "type": "thermal.steady2d", "conductivity_w_mk": 2.,
            "dirichlet_temperature_k": {"left": 300.},
        }},
        "mesh": {"subdivisions": [2, 2]},
    }


def boundary_document():
    d = raw()
    d["physics"]["heat1"].update(
        outward_flux_w_m2={"right": 2.},
        convection={"right": {"h_w_m2k": 4., "ambient_temperature_k": 290.}})
    return d


@pytest.mark.parametrize("presence", ["flux", "convection", "both"])
def test_empty_mapping_presence_enters_strict_path_without_implicit_keys(presence):
    data = raw()
    p = data["physics"]["heat1"]
    if presence in ("flux", "both"):
        p["outward_flux_w_m2"] = {}
    if presence in ("convection", "both"):
        p["convection"] = {}
    before = copy.deepcopy(data)
    doc = Document.from_dict(data)
    assert data == before
    normalized = doc.sole_physics()[1]
    assert ("outward_flux_w_m2" in normalized) == ("outward_flux_w_m2" in p)
    assert ("convection" in normalized) == ("convection" in p)
    assert steady_result_versions(doc) == V2
    assert doc["openphysics"] == "0.2"
    assert normalized["heat_source_w_m3"] == 0.
    assert doc["study"] == {"type": "single"}
    assert doc["results"] == {"save_fields": True, "plots": False}
    assert doc.scale.to_si(1000, {"length": 1}) == 1.
    assert "thermal.steady2d-result-v2" in doc.summary()


def test_legacy_no_mapping_keeps_defaults_format_and_tuple_policy():
    data = raw()
    data["openphysics"] = .2  # Historical str(format) policy, unchanged.
    data["mesh"]["subdivisions"] = (2, 2)  # Historical Python API policy.
    doc = Document.from_dict(data)
    assert doc["mesh"]["subdivisions"] == (2, 2)
    assert doc["openphysics"] == .2
    assert "outward_flux_w_m2" not in doc.sole_physics()[1]
    assert "convection" not in doc.sole_physics()[1]
    assert "remaining exterior insulated" in doc.summary()
    assert "result-v2" not in doc.summary()
    assert doc.sole_physics()[1]["heat_source_w_m3"] == 0.


@pytest.mark.parametrize("path,value", [
    ("openphysics", .2),
    ("mesh.subdivisions", (2, 2)),
    ("physics.heat1.convection", None),
    ("physics.heat1.outward_flux_w_m2", None),
    ("physics.heat1.convection.right.h_w_m2k", True),
    ("physics.heat1.convection.right.h_w_m2k", -1.),
    ("physics.heat1.convection.right.ambient_temperature_k", -1.),
    ("physics.heat1.convection.right.ambient_temperature_k", float("nan")),
    ("physics.heat1.outward_flux_w_m2.right", float("inf")),
    ("physics.heat1.dirichlet_temperature_k.left", True),
    ("physics.heat1.convection.right.unknown", 0),
    ("physics.heat1.outward_flux_w_m2.unknown", 0),
    ("units.time", "s"),
    ("results.plots", True),
])
def test_from_dict_rejects_invalid_new_contract(path, value):
    d = Document.from_dict(boundary_document())
    d.set_path(path, value)
    data = copy.deepcopy(d.data)
    with pytest.raises(DocumentError):
        Document.from_dict(data)


@pytest.mark.parametrize("key", ["outward_flux_w_m2", "convection"])
def test_even_null_mapping_is_presence_not_legacy_fallback(key):
    data = raw()
    data["physics"]["heat1"][key] = None
    with pytest.raises(DocumentError, match=key):
        Document.from_dict(data)


def test_robin_only_and_zero_h_anchor_policy():
    data = boundary_document()
    p = data["physics"]["heat1"]
    p["dirichlet_temperature_k"] = {}
    doc = Document.from_dict(data)
    assert doc.sole_physics()[1]["dirichlet_temperature_k"] == {}
    assert "q.n = g_out + h*(T-T_ambient)" in doc.summary()
    p["convection"]["right"]["h_w_m2k"] = 0
    with pytest.raises(DocumentError, match="anchor"):
        Document.from_dict(data)


def test_legacy_empty_constraints_still_reject():
    data = raw()
    data["physics"]["heat1"]["dirichlet_temperature_k"] = {}
    with pytest.raises(DocumentError, match="at least one"):
        Document.from_dict(data)


@pytest.mark.parametrize("entry", ["validate", "summary"])
@pytest.mark.parametrize("path,value", [
    ("physics.heat1.convection.right.h_w_m2k", -1),
    ("physics.heat1.convection.right.ambient_temperature_k", True),
    ("physics.heat1.outward_flux_w_m2.right", float("nan")),
    ("physics.heat1.dirichlet_temperature_k.bottom", 301),
])
def test_direct_document_mutation_checked_at_validation_and_summary(entry, path, value):
    doc = Document.from_dict(boundary_document())
    doc.set_path(path, value)
    with pytest.raises(DocumentError):
        getattr(doc, entry)()


def test_summary_uses_new_boundary_meaning_and_never_legacy_insulation_claim():
    doc = Document.from_dict(boundary_document())
    summary = doc.summary()
    assert "convection" in summary and "outward flux" in summary
    assert "unselected natural sides insulated" in summary
    assert "remaining exterior insulated" not in summary
    assert V2[0] in summary and V2[1] in summary
    assert "nodal heat W/m of depth" in summary


def test_utf8_load_save_roundtrip_and_invalid_load(tmp_path):
    data = boundary_document()
    data["name"] = "Boundary \u0394T"
    path = tmp_path/"boundary.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    doc = Document.load(path)
    doc.save(tmp_path/"saved.json")
    other = Document.load(tmp_path/"saved.json")
    assert other.data == doc.data
    assert other.summary() == doc.summary()
    data["physics"]["heat1"]["convection"]["right"]["h_w_m2k"] = -1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DocumentError):
        Document.load(path)


def test_validator_stays_non_mutating_and_schema_sets_only_normalization():
    doc = Document.from_dict(boundary_document())
    p = doc.sole_physics()[1]
    del p["heat_source_w_m3"]
    before = copy.deepcopy(doc.data)
    scale, notes = doc.scale, doc.notes
    validate_steady_boundary(doc)
    assert doc.data == before and doc.scale is scale and doc.notes is notes
    doc.validate()
    assert p["heat_source_w_m3"] == 0.
    assert doc.notes == []


def test_legacy_list_document_remains_v1():
    doc = Document.from_dict(raw())
    assert steady_result_versions(doc) == V1
    assert "outward_flux_w_m2" not in doc.sole_physics()[1]


def test_p1_transient_dispatch_and_temperature_policy_remain_unchanged():
    from simcase.examples import TRANSIENT_THERMAL_UNIFORM
    data = copy.deepcopy(TRANSIENT_THERMAL_UNIFORM)
    data["physics"]["heat1"]["initial_temperature_k"] = -10.
    doc = Document.from_dict(data)
    assert doc.sole_physics()[1]["type"] == "thermal.transient2d"
    assert "explicit times in s" in doc.summary()
    data["physics"]["heat1"]["convection"] = {}
    with pytest.raises(DocumentError):
        Document.from_dict(data)


def test_em_scalar_dispatch_unchanged():
    from simcase.examples import SOI_STRIP
    doc = Document.from_dict(copy.deepcopy(SOI_STRIP))
    assert doc.sole_physics()[1]["type"] == "em.modes2d"
    assert "em.modes2d" in doc.summary()
