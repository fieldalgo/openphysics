# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent contract controls; shared schema dispatch is connected separately."""
import copy

import numpy as np
import pytest

from simcase.schema import Document, DocumentError
from simcase.steady_boundary_contract import (
    V1, V2, validate_steady_boundary, steady_result_versions, steady_boundary_inputs,
)
from galerkin import rectangle_mesh
from galerkin.thermal import solve_steady_heat


def document():
    # Direct construction intentionally avoids the not-yet-connected public reader.
    return Document({
        "openphysics": "0.2", "name": "Boundary slab",
        "units": {"length": "m", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0., "xmax": 1., "ymin": 0., "ymax": 1.}},
        "materials": {}, "physics": {"heat1": {
            "type": "thermal.steady2d", "conductivity_w_mk": 2.,
            "heat_source_w_m3": 0., "dirichlet_temperature_k": {"left": 300.},
            "outward_flux_w_m2": {"right": 2.},
            "convection": {"right": {"h_w_m2k": 4., "ambient_temperature_k": 290.}}}},
        "mesh": {"subdivisions": [2, 2]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False},
    })


def physics(d):
    return d.data["physics"]["heat1"]


def set_value(d, path, value):
    d.set_path(path, value)


def test_five_kwargs_and_independent_additive_linear_patch():
    d = document()
    mesh = rectangle_mesh(1., 1., 2, 2)
    kw = steady_boundary_inputs(d, mesh)
    assert set(kw) == {"conductivity", "dirichlet", "heat_source", "outward_flux", "convection"}
    assert kw["outward_flux"] == {"right": 2.}
    assert kw["convection"] == {"right": (4., 290.)}
    result = solve_steady_heat(mesh, **kw)
    # Direct q=-k gradT and right 2+4*(293-290)=14, independent of production summary.
    np.testing.assert_allclose(result.temperature, 300-7*mesh.nodes[:, 0], rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.heat_flux, np.tile([14., 0.], (mesh.num_triangles, 1)),
                               rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.prescribed_outward_load.sum(), 2., rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.convective_outward.sum(), 12., rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.reaction.sum(), 14., rtol=0, atol=1e-10)


@pytest.mark.parametrize("presence", ["neither", "flux", "robin", "both"])
def test_presence_not_truth_selects_version_without_mutating(presence):
    d = document()
    p = physics(d)
    p.pop("outward_flux_w_m2")
    p.pop("convection")
    if presence in ("flux", "both"):
        p["outward_flux_w_m2"] = {}
    if presence in ("robin", "both"):
        p["convection"] = {}
    before, old_scale, old_notes = copy.deepcopy(d.data), d.scale, d.notes
    validate_steady_boundary(d)
    assert steady_result_versions(d) == (V1 if presence == "neither" else V2)
    steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 2))
    assert d.data == before and d.scale is old_scale and d.notes is old_notes


@pytest.mark.parametrize("unit,factor", [("m", 1.), ("mm", 1000.), ("um", 1e6)])
def test_nonzero_origin_units_and_data_lifetime(unit, factor):
    d = document()
    d.data["units"]["length"] = unit
    d.data["geometry"]["domain"] = dict(xmin=2*factor, xmax=3*factor,
                                        ymin=-3*factor, ymax=-2*factor)
    mesh = rectangle_mesh(1, 1, 2, 2)
    mesh.nodes += [2., -3.]
    before = copy.deepcopy(d.data)
    nodes, cells = mesh.nodes.copy(), mesh.triangles.copy()
    kw = steady_boundary_inputs(d, mesh)
    assert d.data == before
    np.testing.assert_array_equal(mesh.nodes, nodes)
    np.testing.assert_array_equal(mesh.triangles, cells)
    physics(d)["convection"]["right"]["h_w_m2k"] = 99.
    physics(d)["dirichlet_temperature_k"]["left"] = 999.
    assert kw["convection"]["right"] == (4., 290.)
    assert all(v == 300 for v in kw["dirichlet"].values())


def test_reordered_nodes_and_reversed_edges_are_valid_single_identities():
    d = document()
    mesh = rectangle_mesh(1, 1, 2, 2)
    order = np.arange(mesh.num_nodes)[::-1]
    inverse = np.argsort(order)
    mesh.nodes = mesh.nodes[order].copy()
    mesh.triangles = inverse[mesh.triangles]
    mesh.boundary = {k: inverse[v] for k, v in mesh.boundary.items()}
    mesh.boundary_edges = {k: inverse[v][:, ::-1] for k, v in mesh.boundary_edges.items()}
    kw = steady_boundary_inputs(d, mesh)
    assert list(kw["dirichlet"]) == sorted(kw["dirichlet"])
    result = solve_steady_heat(mesh, **kw)
    np.testing.assert_allclose(result.temperature, 300-7*mesh.nodes[:, 0], rtol=0, atol=1e-10)


def test_robin_only_anchor_and_empty_fixed_set():
    d = document()
    physics(d)["dirichlet_temperature_k"] = {}
    physics(d)["outward_flux_w_m2"] = {}
    result = solve_steady_heat(rectangle_mesh(1, 1, 2, 2),
                               **steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 2)))
    np.testing.assert_allclose(result.temperature, 290., rtol=0, atol=1e-10)
    assert not result.reaction.any()


@pytest.mark.parametrize("balanced", [False, True])
def test_pure_neumann_rejects_compatible_and_incompatible(balanced):
    d = document()
    p = physics(d)
    p["dirichlet_temperature_k"] = {}
    p["convection"] = {}
    p["heat_source_w_m3"] = 2. if balanced else 3.
    with pytest.raises(DocumentError, match="anchor"):
        validate_steady_boundary(d)


def test_zero_h_not_anchor_but_zero_h_with_other_anchor_valid():
    d = document()
    physics(d)["convection"]["right"]["h_w_m2k"] = 0.
    validate_steady_boundary(d)
    physics(d)["dirichlet_temperature_k"] = {}
    with pytest.raises(DocumentError, match="anchor"):
        validate_steady_boundary(d)


def test_partial_corner_load_is_not_deleted():
    d = document()
    p = physics(d)
    p["outward_flux_w_m2"] = {"top": 6.}
    p["convection"] = {}
    mesh = rectangle_mesh(1, 1, 2, 2)
    kw = steady_boundary_inputs(d, mesh)
    result = solve_steady_heat(mesh, **kw)
    corner = np.intersect1d(mesh.boundary["left"], mesh.boundary["top"])[0]
    # First top edge length .5, endpoint moment g*ell/2=1.5 W/m, even at fixed corner.
    np.testing.assert_allclose(result.prescribed_outward_load[corner], 1.5, rtol=0, atol=1e-12)
    np.testing.assert_allclose(result.prescribed_outward_load.sum(), 6., rtol=0, atol=1e-12)


@pytest.mark.parametrize("kind", ["flux", "robin"])
def test_fully_fixed_actual_edge_despite_disjoint_side_names(kind):
    d = document()
    p = physics(d)
    p["dirichlet_temperature_k"] = {"top": 300., "bottom": 300.}
    p["outward_flux_w_m2"] = {"left": 0.} if kind == "flux" else {}
    p["convection"] = {"left": {"h_w_m2k": 0., "ambient_temperature_k": 0.}} if kind == "robin" else {}
    validate_steady_boundary(d)  # Shape-level side names alone cannot decide.
    with pytest.raises(DocumentError, match="fully Dirichlet"):
        steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 1))


@pytest.mark.parametrize("path", [
    "physics.heat1.conductivity_w_mk", "physics.heat1.heat_source_w_m3",
    "physics.heat1.outward_flux_w_m2.right", "physics.heat1.dirichlet_temperature_k.left",
    "physics.heat1.convection.right.h_w_m2k", "physics.heat1.convection.right.ambient_temperature_k",
])
@pytest.mark.parametrize("value", [True, None, "2", float("nan"), float("inf"), 1+0j, 10**1000])
def test_strict_numeric_rejections(path, value):
    d = document()
    set_value(d, path, value)
    with pytest.raises(DocumentError):
        validate_steady_boundary(d)


@pytest.mark.parametrize("path,value", [
    ("physics.heat1.conductivity_w_mk", 0),
    ("physics.heat1.convection.right.h_w_m2k", -1),
    ("physics.heat1.convection.right.ambient_temperature_k", -1),
    ("physics.heat1.dirichlet_temperature_k.left", -1),
    ("physics.heat1.convection.right", [1, 300]),
    ("physics.heat1.convection.right", {"h_w_m2k": 1}),
    ("physics.heat1.convection.right", {"h_w_m2k": 1, "ambient_temperature_k": 300, "extra": 0}),
    ("physics.heat1.outward_flux_w_m2", None),
    ("physics.heat1.outward_flux_w_m2", {"outer": 0}),
    ("physics.heat1.outward_flux_w_m2.right", [2]),
    ("physics.heat1.unknown", 0),
    ("geometry.shapes", []),
    ("units.time", "s"),
    ("units.temperature", "C"),
    ("mesh.subdivisions", [True, 2]),
    ("mesh.subdivisions", [2., 2]),
    ("mesh.subdivisions", [0, 2]),
    ("study.type", "transient"),
    ("results.plots", True),
    ("geometry.domain.xmax", 0),
])
def test_invalid_shapes_unknown_units_and_ranges(path, value):
    d = document()
    set_value(d, path, value)
    with pytest.raises(DocumentError):
        validate_steady_boundary(d)


@pytest.mark.parametrize("tag", ["bottom", "top"])
def test_equal_corner_dedup_conflict_and_full_side_overlap(tag):
    d = document()
    p = physics(d)
    p["dirichlet_temperature_k"][tag] = 300.
    kw = steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 2))
    assert len(kw["dirichlet"]) == 5
    p["dirichlet_temperature_k"][tag] = 301.
    with pytest.raises(DocumentError, match="corner"):
        validate_steady_boundary(d)
    p["dirichlet_temperature_k"] = {"right": 300.}
    with pytest.raises(DocumentError, match="overlaps"):
        validate_steady_boundary(d)


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "interior", "partial", "bool", "wrong_side", "out_of_range"])
def test_invalid_actual_natural_edge_tag(mutation):
    mesh = rectangle_mesh(1, 1, 2, 2)
    edges = mesh.boundary_edges["right"].copy()
    if mutation == "empty":
        edges = np.empty((0, 2), dtype=int)
    elif mutation == "duplicate":
        edges = np.vstack((edges, edges[0, ::-1]))
    elif mutation == "interior":
        edges[0] = mesh.triangles[0, [0, 2]]
    elif mutation == "partial":
        edges = edges[:1]
    elif mutation == "bool":
        edges = edges.astype(bool)
    elif mutation == "wrong_side":
        edges = mesh.boundary_edges["top"]
    else:
        edges[0, 0] = mesh.num_nodes
    mesh.boundary_edges["right"] = edges
    with pytest.raises(DocumentError):
        steady_boundary_inputs(document(), mesh)


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "wrong_side", "bool"])
def test_invalid_actual_node_tag(mutation):
    mesh = rectangle_mesh(1, 1, 2, 2)
    ids = mesh.boundary["left"].copy()
    if mutation == "empty":
        ids = ids[:0]
    elif mutation == "duplicate":
        ids[-1] = ids[0]
    elif mutation == "wrong_side":
        ids = mesh.boundary["right"]
    else:
        ids = ids.astype(bool)
    mesh.boundary["left"] = ids
    with pytest.raises(DocumentError):
        steady_boundary_inputs(document(), mesh)


def test_signed_flux_source_and_unclamped_negative_solution():
    d = document()
    p = physics(d)
    p["dirichlet_temperature_k"] = {"left": 0.}
    p["outward_flux_w_m2"] = {"right": 10.}
    p["convection"] = {}
    result = solve_steady_heat(rectangle_mesh(1, 1, 2, 2),
                               **steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 2)))
    assert result.temperature.min() < 0
    p["outward_flux_w_m2"] = {"right": -10.}
    p["heat_source_w_m3"] = -1.
    validate_steady_boundary(d)


def test_invalid_mesh_does_not_change_document():
    d = document()
    before = copy.deepcopy(d.data)
    for bad in (None, object()):
        with pytest.raises(DocumentError, match="mesh"):
            steady_boundary_inputs(d, bad)
    assert d.data == before


@pytest.mark.parametrize("origin", [1e9, 1e15])
@pytest.mark.parametrize("tag", ["normal", "wrong_side", "all_exterior"])
def test_large_origin_side_precision_and_tampered_robin_tag(origin, tag):
    d = document()
    p = physics(d)
    p["dirichlet_temperature_k"] = {}
    p["outward_flux_w_m2"] = {}
    d.data["geometry"]["domain"] = {
        "xmin": origin, "xmax": origin+1.,
        "ymin": origin, "ymax": origin+1.,
    }
    mesh = rectangle_mesh(1., 1., 2, 2)
    mesh.nodes += origin
    if tag == "wrong_side":
        mesh.boundary_edges["right"] = mesh.boundary_edges["left"].copy()
    elif tag == "all_exterior":
        mesh.boundary_edges["right"] = np.vstack(
            [mesh.boundary_edges[side] for side in ("left", "right", "bottom", "top")])
    before = copy.deepcopy(d.data)
    validate_steady_boundary(d)  # Finite JSON bounds alone are not a mesh precision guarantee.
    if origin == 1e15:
        # Even correct tags must fail clearly when the unchanged 64-eps
        # coordinate budget can cover opposite sides. No wrong tag is accepted.
        with pytest.raises(DocumentError, match="insufficient coordinate precision"):
            steady_boundary_inputs(d, mesh)
    elif tag != "normal":
        with pytest.raises(DocumentError, match="complete SI side"):
            steady_boundary_inputs(d, mesh)
    else:
        kw = steady_boundary_inputs(d, mesh)
        assert kw["dirichlet"] == {}
        assert kw["convection"] == {"right": (4., 290.)}
    assert d.data == before


def test_large_origin_wrong_dirichlet_node_side_is_rejected():
    d = document()
    d.data["geometry"]["domain"] = {
        "xmin": 1e9, "xmax": 1e9+1., "ymin": 1e9, "ymax": 1e9+1.,
    }
    mesh = rectangle_mesh(1., 1., 2, 2)
    mesh.nodes += 1e9
    mesh.boundary["left"] = mesh.boundary["right"].copy()
    with pytest.raises(DocumentError, match="complete unique SI side"):
        steady_boundary_inputs(d, mesh)


@pytest.mark.parametrize("tamper", [False, True])
def test_large_origin_adjacent_side_edge_ambiguity_rejects_even_normal_tags(tamper):
    d = document()
    p = physics(d)
    p["dirichlet_temperature_k"] = {}
    p["outward_flux_w_m2"] = {}
    d.data["mesh"]["subdivisions"] = [8, 8]
    origin = 1e13
    d.data["geometry"]["domain"] = {
        "xmin": origin, "xmax": origin+1.,
        "ymin": origin, "ymax": origin+1.,
    }
    mesh = rectangle_mesh(1., 1., 8, 8)
    mesh.nodes += origin
    if tamper:
        # The last top edge is adjacent to right and shorter than the retained
        # coordinate budget. It must never be admitted as another right edge.
        mesh.boundary_edges["right"] = np.vstack(
            [mesh.boundary_edges["right"], mesh.boundary_edges["top"][-1]])
    validate_steady_boundary(d)
    with pytest.raises(DocumentError, match="ambiguous rectangle side edge classification"):
        steady_boundary_inputs(d, mesh)


def test_near_side_interior_node_cannot_become_dirichlet_by_coordinate_mask():
    d = document()
    d.data["mesh"]["subdivisions"] = [8, 8]
    origin = 1e13
    d.data["geometry"]["domain"] = {
        "xmin": origin, "xmax": origin+1.,
        "ymin": origin, "ymax": origin+1.,
    }
    mesh = rectangle_mesh(1., 1., 8, 8)
    mesh.nodes += origin
    # This malformed selection includes the nearby interior column. Geometry's
    # ambiguous edge classification must reject before accepting any such nodes.
    mesh.boundary["left"] = np.flatnonzero(mesh.nodes[:, 0] <= origin+.125)
    with pytest.raises(DocumentError, match="ambiguous rectangle side edge classification"):
        steady_boundary_inputs(d, mesh)


@pytest.mark.parametrize("include_interior", [False, True])
def test_dirichlet_identity_uses_exterior_endpoints_not_nearby_interior(include_interior):
    # Fixture geometry validity is intentionally checked by the real helper;
    # this direct branch coverage must not mock or bypass _mesh_geometry.
    d = document()
    origin = 1e12
    d.data["geometry"]["domain"] = {
        "xmin": origin, "xmax": origin+1.,
        "ymin": origin, "ymax": origin+1.,
    }
    mesh = rectangle_mesh(1., 1., 2, 2)
    exterior_nodes = np.unique(np.concatenate(list(mesh.boundary.values())))
    interior = np.setdiff1d(np.arange(mesh.num_nodes), exterior_nodes)
    assert len(interior) == 1
    center = int(interior[0])
    mesh.nodes[center] = [.0078125, .5]
    mesh.nodes += origin
    normal_left = mesh.boundary["left"].copy()
    assert len(normal_left) == 3 and center not in normal_left
    if include_interior:
        mesh.boundary["left"] = np.append(normal_left, center)
        with pytest.raises(DocumentError, match="complete unique SI side"):
            steady_boundary_inputs(d, mesh)
    else:
        kw = steady_boundary_inputs(d, mesh)
        assert list(kw["dirichlet"]) == sorted(map(int, normal_left))
        assert center not in kw["dirichlet"]
