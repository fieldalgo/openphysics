# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict JSON boundary and independent input construction (format 0.3), not solver acceptance."""
import copy
import decimal
import json
import math
import numpy as np
import pytest

from simcase.schema import Document, DocumentError
from simcase.transient_thermal_contract import (
    PHYSICS, V1_03, transient_result_versions, transient_solver_inputs, is_transient_thermal)
from galerkin.mesh import rectangle_mesh


def model():
    return {
        "openphysics": "0.3", "name": "transient",
        "geometry": {"length_unit": "mm", "depth": None,
                     "domain": {"xmin": 10., "xmax": 40., "ymin": -20., "ymax": 0.}},
        "physics": {"heat1": {
            "type": PHYSICS, "thermal_conductivity": "12.5 W/(m K)",
            "volumetric_heat_capacity": "1000000 J/(m^3 K)", "initial_temperature": "300 K",
            "prescribed_temperature": {"left": {"unit": "K", "values": [300., 301., 305.]}}
        }},
        "mesh": {"subdivision_count": [2, 3]},
        "study": {"type": "transient", "time": {"unit": "s", "values": [0., 1., 3.]}}
    }


def affine(reference, gradient):
    return {"type": "affine", "reference_temperature": reference,
            "temperature_gradient": {"unit": "K/m", "values": gradient}}


def mesh_for(doc):
    mesh = rectangle_mesh(.03, .02, 2, 3)
    mesh.nodes += [.01, -.02]
    return mesh


def set_path(data, path, value):
    node = data
    for key in path.split(".")[:-1]:
        node = node[key]
    node[path.split(".")[-1]] = value


def errors(caught):
    return [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"]


def test_versions_defaults_summary_and_copy(tmp_path):
    raw = model()
    doc = Document.from_dict(raw)
    assert raw == model()  # defaults never mutate caller dictionaries
    assert doc.si["results"] == {"save_fields": True, "plots": False}
    assert doc.si["materials"] == {}
    # an absent source is echoed, never written into the document (hazard H9)
    assert "heat_source_density" not in doc.si["physics"]["heat1"]
    assert "physics.heat1.heat_source_density" in [d["path"] for d in doc.defaults_applied]
    assert PHYSICS in doc.summary() and "3 explicit times" in doc.summary()
    assert V1_03 == ("thermal.transient2d-result-v3", "thermal2d-transient-p1-node-cell-v2")
    assert transient_result_versions(doc) == V1_03
    target = tmp_path/"unicode-温度.json"
    doc.save(target)
    loaded = Document.load(target)
    assert loaded.data == doc.data
    assert loaded.copy().data == doc.data


@pytest.mark.parametrize("initial", ["-200 K", "0 K", "300 K"])
def test_finite_negative_kelvin_and_empty_constraints(initial):
    # absolute temperatures are above 0 K since the units batch (registry domain)
    raw = model()
    raw["physics"]["heat1"].update(initial_temperature=initial, prescribed_temperature={},
                                  heat_source_density="-2 W/m^3")
    if initial != "300 K":
        with pytest.raises(DocumentError) as caught:
            Document.from_dict(raw)
        assert errors(caught) == [("E-DOMAIN", "physics.heat1.initial_temperature")]
        return
    doc = Document.from_dict(raw)
    kw = transient_solver_inputs(doc, mesh_for(doc))
    np.testing.assert_array_equal(kw["initial_temperature_k"], 300.)
    assert kw["dirichlet"] == {} and kw["heat_source"] == -2.
    assert set(kw) == {"conductivity", "volumetric_heat_capacity", "time_s",
                       "initial_temperature_k", "dirichlet", "heat_source"}


def test_nonzero_start_and_exact_sample_lookup_lifetime():
    raw = model()
    raw["study"]["time"]["values"] = [2., 2.5, 5.]
    doc = Document.from_dict(raw)
    mesh = mesh_for(doc)
    kw = transient_solver_inputs(doc, mesh)
    fixed = sorted(kw["dirichlet"])
    callback = kw["dirichlet"][fixed[0]]
    assert [callback(t) for t in [2., 2.5, 5.]] == [300., 301., 305.]
    with pytest.raises(ValueError, match="no interpolation"):
        callback(3.)
    with pytest.raises(ValueError):
        callback(True)
    doc.si["study"]["time"][0] = 42.
    doc.data["physics"]["heat1"]["prescribed_temperature"]["left"]["values"][1] = -1.
    mesh.nodes[:] = 999.
    kw["time_s"][0] = -99.
    assert callback(2.5) == 301.
    np.testing.assert_array_equal(kw["initial_temperature_k"], 300.)


@pytest.mark.parametrize("unit,factor", [("m", .001), ("mm", 1.), ("um", 1000.)])
def test_affine_initial_si_units_and_reordered_nodes(unit, factor):
    raw = model()
    raw["geometry"]["length_unit"] = unit
    raw["geometry"]["domain"] = {k: v*factor for k, v in raw["geometry"]["domain"].items()}
    raw["physics"]["heat1"].update(
        initial_temperature=affine("300 K", [200., 0.]),
        prescribed_temperature={"left": "300 K", "right": "306 K"})
    doc = Document.from_dict(raw)
    mesh = mesh_for(doc)
    permutation = np.arange(mesh.num_nodes)[::-1]
    reverse = np.argsort(permutation)
    mesh.nodes = mesh.nodes[permutation]
    mesh.triangles = reverse[mesh.triangles]
    mesh.boundary = {tag: reverse[ids] for tag, ids in mesh.boundary.items()}
    kw = transient_solver_inputs(doc, mesh)
    expected = 300.+200.*(mesh.nodes[:, 0]-.01)
    np.testing.assert_allclose(kw["initial_temperature_k"], expected, rtol=0, atol=1e-13)
    # The helper must not project even roundoff-sized differences at boundaries.
    assert len(kw["dirichlet"]) == 2*4


@pytest.mark.parametrize("ulps,accepted", [(16, True), (64, False)])
def test_t0_tolerance_preserves_actual_initial(ulps, accepted):
    # 0 K is outside the registry domain, so the t0 bound is tested at 300 K. The bound,
    # 32 eps max(1, |a|, |b|), is about 37 ulp there; the initial is the exact decimal of the double.
    value = 300.
    for _ in range(ulps):
        value = float(np.nextafter(value, math.inf))
    raw = model()
    raw["physics"]["heat1"].update(initial_temperature=f"{decimal.Decimal(value)} K",
                                  prescribed_temperature={"left": "300 K"})
    if not accepted:
        with pytest.raises(DocumentError, match="t0 mismatch") as caught:
            Document.from_dict(raw)
        assert [d.code for d in caught.value.diagnostics] == ["E-CONTRACT"]
        return
    doc = Document.from_dict(raw)
    kw = transient_solver_inputs(doc, mesh_for(doc))
    np.testing.assert_array_equal(kw["initial_temperature_k"], value)
    assert all(v == 300. for v in kw["dirichlet"].values())


def test_adjacent_side_samples_deduplicate_without_projection():
    raw = model()
    raw["physics"]["heat1"]["prescribed_temperature"]["bottom"] = {"unit": "K", "values": [300, 301, 305]}
    doc = Document.from_dict(raw)
    kw = transient_solver_inputs(doc, mesh_for(doc))
    assert len(kw["dirichlet"]) == 4+3-1
    assert list(kw["dirichlet"]) == sorted(kw["dirichlet"])
    raw["physics"]["heat1"]["prescribed_temperature"]["bottom"]["values"][-1] = 306.
    with pytest.raises(DocumentError, match="conflicting corner"):
        Document.from_dict(raw)


def samples(*values, **extra):
    return {"unit": "K", "values": list(values), **extra}


@pytest.mark.parametrize("path,value", [
    ("openphysics", .3), ("openphysics", True), ("openphysics", "0.2"),
    ("name", 123),
    ("geometry.length_unit", True), ("geometry.length_unit", "s"),
    ("geometry.depth", "-1 m"),
    ("geometry.domain.xmin", float("nan")),
    ("geometry.domain.xmax", 10.),
    ("geometry.domain.xmax", float("inf")),
    ("mesh.subdivision_count", [2., 3]), ("mesh.subdivision_count", [True, 3]),
    ("mesh.subdivision_count", [0, 3]), ("mesh.subdivision_count", [2]),
    ("study.type", "sweep"),
    ("study.time", {"unit": "s", "values": []}), ("study.time", {"unit": "s", "values": [0]}),
    ("study.time", {"unit": "s", "values": [-1., 0.]}),
    ("study.time", {"unit": "s", "values": [0., 0.]}), ("study.time", {"unit": "s", "values": [1., 0.]}),
    ("study.time", {"unit": "s", "values": [0., True]}),
    ("study.time", {"unit": "s", "values": [0., float("nan")]}),
    ("study.time", {"unit": "s", "values": [0., float("inf")]}), ("study.time", "0 1"),
    ("study.time", [0., 1., 3.]), ("study.time", {"unit": "m", "values": [0., 1., 3.]}),
    ("physics.heat1.thermal_conductivity", "0 W/(m K)"),
    ("physics.heat1.thermal_conductivity", True),
    ("physics.heat1.thermal_conductivity", 12.5),
    ("physics.heat1.volumetric_heat_capacity", "-1 J/(m^3 K)"),
    ("physics.heat1.volumetric_heat_capacity", float("nan")),
    ("physics.heat1.heat_source_density", True),
    ("physics.heat1.heat_source_density", {"values": [0, 1, 2]}),
    ("physics.heat1.initial_temperature", {"unit": "K", "values": [300.]*12}),
    ("physics.heat1.initial_temperature", True),
    ("physics.heat1.initial_temperature", float("inf")),
    ("physics.heat1.initial_temperature", {"type": "expression", "value": "x"}),
    ("physics.heat1.initial_temperature", affine("300 K", [0., True])),
    ("physics.heat1.initial_temperature", affine("300 K", [0.])),
    ("physics.heat1.prescribed_temperature", {"unknown": "300 K"}),
    ("physics.heat1.prescribed_temperature", {"left": [300., 301., 305.]}),
    ("physics.heat1.prescribed_temperature", {"left": samples(300., 301.)}),
    ("physics.heat1.prescribed_temperature", {"left": samples(300., True, 305.)}),
    ("physics.heat1.prescribed_temperature", {"left": samples(300., float("nan"), 305.)}),
    ("physics.heat1.prescribed_temperature", {"left": samples(300., 301., 305., interpolation="linear")}),
    ("physics.heat1.prescribed_temperature", {"left": "299 K"}),
    ("results", {"save_fields": 1, "plots": False}),
    ("results", {"save_fields": True, "plots": True}),
    ("materials", {"solid": {}})
])
def test_strict_invalid_values(path, value):
    raw = model()
    set_path(raw, path, value)
    with pytest.raises(DocumentError):
        Document.from_dict(raw)


@pytest.mark.parametrize("container,key", [
    ("", "unknown"), ("", "units"), ("geometry", "shapes"),
    ("geometry.domain", "zmin"), ("mesh", "size"), ("study", "parameter"),
    ("results", "renderer"), ("physics.heat1", "outward_flux_w_m2"),
    ("physics.heat1", "conductivity_w_mk"),
    ("physics.heat1", "convection"), ("physics.heat1", "wavelength"),
])
def test_unknown_keys_rejected(container, key):
    raw = model()
    node = raw
    if container:
        for part in container.split("."):
            node = node.setdefault(part, {})
    node[key] = 0
    with pytest.raises(DocumentError):
        Document.from_dict(raw)


@pytest.mark.parametrize("path", [
    "geometry.length_unit", "geometry.domain", "mesh.subdivision_count", "study.time",
    "physics.heat1.initial_temperature", "physics.heat1.thermal_conductivity",
    "physics.heat1.volumetric_heat_capacity", "physics.heat1.prescribed_temperature"
])
def test_required_fields(path):
    raw = model()
    node = raw
    parts = path.split(".")
    for key in parts[:-1]:
        node = node[key]
    del node[parts[-1]]
    with pytest.raises(DocumentError):
        Document.from_dict(raw)


def test_affine_tangent_conflict_and_nonfinite_field():
    raw = model()
    raw["physics"]["heat1"]["initial_temperature"] = affine("300 K", [0., 1.])
    with pytest.raises(DocumentError, match="t0 mismatch"):
        Document.from_dict(raw)
    raw["physics"]["heat1"]["prescribed_temperature"] = {}
    raw["physics"]["heat1"]["initial_temperature"] = affine("300 K", [1e308, 1e308])
    raw["geometry"]["domain"] = {"xmin": 0., "xmax": 1e6, "ymin": 0., "ymax": 1e6}
    with pytest.raises(DocumentError, match="finite"):
        Document.from_dict(raw)


def test_mixed_physics_rejected_and_detection_is_narrow():
    raw = model()
    raw["physics"]["heat2"] = copy.deepcopy(raw["physics"]["heat1"])
    with pytest.raises(DocumentError, match="more than one"):
        Document.from_dict(raw)
    del raw["physics"]["heat2"]
    raw["physics"]["em1"] = {"type": "em.modes2d"}     # not a kind of format 0.3 yet
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(raw)
    assert errors(caught) == [("E-KEY-UNKNOWN", "physics.em1.type")]
    assert is_transient_thermal(raw)
    for value in [None, [], {"physics": []}, {"physics": {"heat": {"type": "thermal.steady2d"}}}]:
        assert not is_transient_thermal(value)


@pytest.mark.parametrize("damage", ["nodes_nonfinite", "outside", "missing_tag",
                                    "duplicate", "bad_index", "wrong_side", "partial_side"])
def test_runtime_mesh_boundary_rejections(damage):
    doc = Document.from_dict(model())
    mesh = mesh_for(doc)
    if damage == "nodes_nonfinite": mesh.nodes[0, 0] = math.nan
    elif damage == "outside": mesh.nodes[0, 0] = 999.
    elif damage == "missing_tag": del mesh.boundary["left"]
    elif damage == "duplicate": mesh.boundary["left"] = np.array([0, 0])
    elif damage == "bad_index": mesh.boundary["left"] = np.array([mesh.num_nodes])
    elif damage == "wrong_side": mesh.boundary["left"] = mesh.boundary["right"]
    else: mesh.boundary["left"] = mesh.boundary["left"][:-1]
    with pytest.raises(DocumentError):
        transient_solver_inputs(doc, mesh)


def test_kwargs_execute_existing_engine_with_linear_time_exact_field():
    from galerkin.transient_heat import solve_transient_heat
    raw = model()
    raw['physics']['heat1'].update(
        heat_source_density="2000000 W/m^3",
        prescribed_temperature={side: samples(300., 302., 306.)
                                for side in ['left', 'right', 'bottom', 'top']})
    doc = Document.from_dict(raw)
    mesh = mesh_for(doc)
    result = solve_transient_heat(mesh, **transient_solver_inputs(doc, mesh))
    np.testing.assert_allclose(result.temperature_k,
        np.broadcast_to((300.+2*result.time_s)[:, None], result.temperature_k.shape),
        rtol=0, atol=1e-12)
    assert result.reaction_w_per_m.shape == (2, mesh.num_nodes)
    np.testing.assert_array_equal(result.temperature_k[0], 300.)


def test_steady_and_optical_schema_dispatch_unchanged():
    raw = model()
    raw['study'] = {'type': 'single'}
    raw['physics']['heat1'] = {'type': 'thermal.steady2d',
        'thermal_conductivity': '12.5 W/(m K)', 'prescribed_temperature': {'left': '300 K'}}
    steady = Document.from_dict(raw)
    assert 'single steady heat' in steady.summary()
    raw['physics']['heat1']['prescribed_temperature']['left'] = '-1 K'
    with pytest.raises(DocumentError): Document.from_dict(raw)
    # a minimal format 0.2 document is completed with the default em.modes2d entry, which reads
    # format 0.3 only since the units batch: refused by name, as every 0.2 document of a 0.3 kind
    with pytest.raises(DocumentError) as caught:
        Document.from_dict({'units': {'length': 'um'},
                            'geometry': {'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}}})
    assert [(d.code, d.path) for d in caught.value.diagnostics] == [('E-FORMAT', 'openphysics')]
    assert 'format 0.2 em.modes2d documents are not read' in str(caught.value)


def test_helper_refuses_missing_mesh_without_incidental_attribute_error():
    with pytest.raises(DocumentError, match='mesh.nodes'):
        transient_solver_inputs(Document.from_dict(model()), None)
