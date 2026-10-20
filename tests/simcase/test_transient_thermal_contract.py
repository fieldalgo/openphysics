# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict JSON boundary and independent input construction, not solver acceptance."""
import copy
import json
import math
import numpy as np
import pytest

from simcase.schema import Document, DocumentError
from simcase.transient_thermal_contract import (
    PHYSICS, RESULT_FORMAT, FIELD_LAYOUT, transient_solver_inputs, is_transient_thermal)
from galerkin.mesh import rectangle_mesh


def model():
    return {
        "openphysics": "0.2", "name": "transient",
        "units": {"length": "mm", "temperature": "K", "time": "s"},
        "geometry": {"domain": {"xmin": 10., "xmax": 40., "ymin": -20., "ymax": 0.}},
        "physics": {"heat1": {
            "type": PHYSICS, "conductivity_w_mk": 12.5,
            "volumetric_heat_capacity_j_m3k": 1e6, "initial_temperature_k": 300.,
            "dirichlet_temperature_k": {"left": {"values_k": [300., 301., 305.]}}
        }},
        "mesh": {"subdivisions": [2, 3]},
        "study": {"type": "transient", "time_s": [0., 1., 3.]}
    }


def mesh_for(doc):
    mesh = rectangle_mesh(.03, .02, 2, 3)
    mesh.nodes += [.01, -.02]
    return mesh


def set_path(data, path, value):
    node = data
    for key in path.split(".")[:-1]:
        node = node[key]
    node[path.split(".")[-1]] = value


def test_versions_defaults_summary_and_copy(tmp_path):
    raw = model()
    doc = Document.from_dict(raw)
    assert raw == model()  # defaults never mutate caller dictionaries
    assert doc["results"] == {"save_fields": True, "plots": False}
    assert doc["materials"] == {}
    assert doc["physics"]["heat1"]["heat_source_w_m3"] == 0.
    assert PHYSICS in doc.summary() and "3 explicit times in s" in doc.summary()
    assert RESULT_FORMAT == "thermal.transient2d-result-v1"
    assert FIELD_LAYOUT == "thermal2d-transient-p1-node-cell-v1"
    target = tmp_path/"unicode-温度.json"
    doc.save(target)
    loaded = Document.load(target)
    assert loaded.data == doc.data
    assert loaded.copy().data == doc.data


@pytest.mark.parametrize("initial", [-200., 0., 300.])
def test_finite_negative_kelvin_and_empty_constraints(initial):
    raw = model()
    raw["physics"]["heat1"].update(initial_temperature_k=initial, dirichlet_temperature_k={},
                                  heat_source_w_m3=-2.)
    doc = Document.from_dict(raw)
    kw = transient_solver_inputs(doc, mesh_for(doc))
    np.testing.assert_array_equal(kw["initial_temperature_k"], initial)
    assert kw["dirichlet"] == {} and kw["heat_source"] == -2.
    assert set(kw) == {"conductivity", "volumetric_heat_capacity", "time_s",
                       "initial_temperature_k", "dirichlet", "heat_source"}


def test_nonzero_start_and_exact_sample_lookup_lifetime():
    raw = model()
    raw["study"]["time_s"] = [2., 2.5, 5.]
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
    doc["study"]["time_s"][0] = 42.
    doc["physics"]["heat1"]["dirichlet_temperature_k"]["left"]["values_k"][1] = -1.
    mesh.nodes[:] = 999.
    kw["time_s"][0] = -99.
    assert callback(2.5) == 301.
    np.testing.assert_array_equal(kw["initial_temperature_k"], 300.)


@pytest.mark.parametrize("unit,factor", [("m", .001), ("mm", 1.), ("um", 1000.)])
def test_affine_initial_si_units_and_reordered_nodes(unit, factor):
    raw = model()
    raw["units"]["length"] = unit
    raw["geometry"]["domain"] = {k: v*factor for k, v in raw["geometry"]["domain"].items()}
    raw["physics"]["heat1"].update(
        initial_temperature_k={"type": "affine", "origin_temperature_k": 300.,
                               "gradient_k_per_m": [200., 0.]},
        dirichlet_temperature_k={"left": 300., "right": 306.})
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


@pytest.mark.parametrize("eps,accepted", [(16, True), (64, False)])
def test_t0_tolerance_preserves_actual_initial(eps, accepted):
    raw = model()
    value = eps*np.finfo(float).eps
    raw["physics"]["heat1"].update(initial_temperature_k=value,
                                  dirichlet_temperature_k={"left": 0.})
    if not accepted:
        with pytest.raises(DocumentError, match="t0 mismatch"):
            Document.from_dict(raw)
        return
    doc = Document.from_dict(raw)
    kw = transient_solver_inputs(doc, mesh_for(doc))
    np.testing.assert_array_equal(kw["initial_temperature_k"], value)
    assert all(v == 0. for v in kw["dirichlet"].values())


def test_adjacent_side_samples_deduplicate_without_projection():
    raw = model()
    raw["physics"]["heat1"]["dirichlet_temperature_k"]["bottom"] = {"values_k": [300, 301, 305]}
    doc = Document.from_dict(raw)
    kw = transient_solver_inputs(doc, mesh_for(doc))
    assert len(kw["dirichlet"]) == 4+3-1
    assert list(kw["dirichlet"]) == sorted(kw["dirichlet"])
    raw["physics"]["heat1"]["dirichlet_temperature_k"]["bottom"]["values_k"][-1] = 306.
    with pytest.raises(DocumentError, match="conflicting corner"):
        Document.from_dict(raw)


@pytest.mark.parametrize("path,value", [
    ("openphysics", .2), ("openphysics", True),
    ("name", 123),
    ("units.time", "ms"), ("units.temperature", "C"),
    ("units.length", True), ("units.length", {"in_m": float("inf")}),
    ("units.length", {"in_m": 10**1000}),
    ("geometry.domain.xmin", float("nan")),
    ("geometry.domain.xmax", 10.),
    ("geometry.domain.xmax", float("inf")),
    ("mesh.subdivisions", [2., 3]), ("mesh.subdivisions", [True, 3]),
    ("mesh.subdivisions", [0, 3]), ("mesh.subdivisions", [2]),
    ("study.type", "sweep"),
    ("study.time_s", []), ("study.time_s", [0]), ("study.time_s", [-1., 0.]),
    ("study.time_s", [0., 0.]), ("study.time_s", [1., 0.]),
    ("study.time_s", [0., True]), ("study.time_s", [0., float("nan")]),
    ("study.time_s", [0., float("inf")]), ("study.time_s", "0 1"),
    ("physics.heat1.conductivity_w_mk", 0),
    ("physics.heat1.conductivity_w_mk", True),
    ("physics.heat1.volumetric_heat_capacity_j_m3k", -1),
    ("physics.heat1.volumetric_heat_capacity_j_m3k", float("nan")),
    ("physics.heat1.heat_source_w_m3", True),
    ("physics.heat1.heat_source_w_m3", {"values": [0, 1, 2]}),
    ("physics.heat1.initial_temperature_k", [300.]*12),
    ("physics.heat1.initial_temperature_k", True),
    ("physics.heat1.initial_temperature_k", float("inf")),
    ("physics.heat1.initial_temperature_k", {"type": "expression", "value": "x"}),
    ("physics.heat1.initial_temperature_k", {"type": "affine", "origin_temperature_k": 300.,
                                          "gradient_k_per_m": [0., True]}),
    ("physics.heat1.initial_temperature_k", {"type": "affine", "origin_temperature_k": 300.,
                                          "gradient_k_per_m": [0.]}),
    ("physics.heat1.dirichlet_temperature_k", {"unknown": 300.}),
    ("physics.heat1.dirichlet_temperature_k", {"left": [300., 301., 305.]}),
    ("physics.heat1.dirichlet_temperature_k", {"left": {"values_k": [300., 301.]}}),
    ("physics.heat1.dirichlet_temperature_k", {"left": {"values_k": [300., True, 305.]}}),
    ("physics.heat1.dirichlet_temperature_k", {"left": {"values_k": [300., float("nan"), 305.]}}),
    ("physics.heat1.dirichlet_temperature_k", {"left": {"values_k": [300., 301., 305.],
                                                     "interpolation": "linear"}}),
    ("physics.heat1.dirichlet_temperature_k", {"left": 299.}),
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
    ("", "unknown"), ("units", "mass"), ("geometry", "shapes"),
    ("geometry.domain", "zmin"), ("mesh", "size"), ("study", "parameter"),
    ("results", "renderer"), ("physics.heat1", "outward_flux"),
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
    "units", "geometry.domain", "mesh.subdivisions", "study.time_s",
    "physics.heat1.initial_temperature_k", "physics.heat1.conductivity_w_mk",
    "physics.heat1.volumetric_heat_capacity_j_m3k", "physics.heat1.dirichlet_temperature_k"
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
    raw["physics"]["heat1"]["initial_temperature_k"] = {
        "type": "affine", "origin_temperature_k": 300., "gradient_k_per_m": [0., 1.]}
    with pytest.raises(DocumentError, match="t0 mismatch"):
        Document.from_dict(raw)
    raw["physics"]["heat1"]["dirichlet_temperature_k"] = {}
    raw["physics"]["heat1"]["initial_temperature_k"]["gradient_k_per_m"] = [1e308, 1e308]
    raw["geometry"]["domain"] = {"xmin": 0., "xmax": 1e6, "ymin": 0., "ymax": 1e6}
    with pytest.raises(DocumentError, match="finite"):
        Document.from_dict(raw)


def test_mixed_physics_rejected_and_detection_is_narrow():
    raw = model()
    raw["physics"]["em1"] = {"type": "em.modes2d"}
    with pytest.raises(DocumentError, match="exactly one"):
        Document.from_dict(raw)
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
        heat_source_w_m3=2e6,
        dirichlet_temperature_k={side: {'values_k': [300., 302., 306.]}
                                 for side in ['left', 'right', 'bottom', 'top']})
    doc = Document.from_dict(raw)
    mesh = mesh_for(doc)
    result = solve_transient_heat(mesh, **transient_solver_inputs(doc, mesh))
    np.testing.assert_allclose(result.temperature_k,
        np.broadcast_to((300.+2*result.time_s)[:, None], result.temperature_k.shape),
        rtol=0, atol=1e-12)
    assert result.reaction_w_per_m.shape == (2, mesh.num_nodes)
    np.testing.assert_array_equal(result.temperature_k[0], 300.)


def test_legacy_steady_and_optical_schema_dispatch_unchanged():
    raw = model()
    raw['units'].pop('time')
    raw['study'] = {'type': 'single'}
    raw['physics']['heat1'] = {'type': 'thermal.steady2d',
        'conductivity_w_mk': 12.5, 'dirichlet_temperature_k': {'left': 300.}}
    steady = Document.from_dict(raw)
    assert 'single steady heat' in steady.summary()
    raw['physics']['heat1']['dirichlet_temperature_k']['left'] = -1.
    with pytest.raises(DocumentError): Document.from_dict(raw)
    optical = Document.from_dict({'units': {'length': 'um'},
        'geometry': {'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}}})
    assert optical['physics']['em1']['type'] == 'em.modes2d'


def test_helper_refuses_missing_mesh_without_incidental_attribute_error():
    with pytest.raises(DocumentError, match='mesh.nodes'):
        transient_solver_inputs(Document.from_dict(model()), None)

