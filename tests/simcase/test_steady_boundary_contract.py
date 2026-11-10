# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent contract controls; shared schema dispatch is connected separately.

The documents are format 0.3 (the format 0.2 reader of this contract is gone since units
batch C7). Origins beyond the int64 picometre grid (about 9.2e6 m) are refused by the reader,
so the mesh-side precision controls at 1e9 to 1e15 m drive ``boundary_kwargs`` with the grid
and heat inputs a document at that origin would hand it."""
import copy

import numpy as np
import pytest

from simcase import views
from simcase.schema import Document, DocumentError
from simcase.steady_boundary_contract import (
    V1_03, V2_03, boundary_kwargs, validate_steady_boundary, steady_result_versions, steady_boundary_inputs,
)
from galerkin import rectangle_mesh
from galerkin.thermal import solve_steady_heat


def data():
    return {
        "openphysics": "0.3", "name": "Boundary slab",
        "geometry": {"length_unit": "m", "depth": None, "domain": {"xmin": 0., "xmax": 1., "ymin": 0., "ymax": 1.}},
        "materials": {}, "physics": {"heat1": {
            "type": "thermal.steady2d", "thermal_conductivity": "2 W/(m K)",
            "heat_source_density": "0 W/m^3", "prescribed_temperature": {"left": "300 K"},
            "inward_heat_flux": {"right": "-2 W/m^2"},
            "convection": {"right": {"heat_transfer_coefficient": "4 W/(m^2 K)", "ambient_temperature": "290 K"}}}},
        "mesh": {"subdivision_count": [2, 2]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False},
    }


def document(raw=None):
    return Document.from_dict(copy.deepcopy(data() if raw is None else raw))


def physics(raw):
    return raw["physics"]["heat1"]


def set_value(raw, path, value):
    node, keys = raw, path.split(".")
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = value


def far_inputs(origin, *, full=False, subdivisions=(2, 2)):
    """The grid and heat inputs ``steady_boundary_inputs`` would hand ``boundary_kwargs`` for the
    1 m slab with its lower corner at ``origin``: the conditions of ``data()`` when ``full``,
    else its convection only (no prescribed temperature and no flux)."""
    grid = views.RectangleMesh((origin, origin), (origin + 1., origin + 1.), (1., 1.), tuple(subdivisions),
                               "difference")
    heat = views.HeatInputs(conductivity=2., heat_source=0., dirichlet={"left": 300.} if full else {},
                            outward_flux={"right": 2.} if full else {}, convection={"right": (4., 290.)},
                            boundary_layout=True)
    return grid, heat


def test_five_kwargs_and_independent_additive_linear_patch():
    d = document()
    mesh = rectangle_mesh(1., 1., 2, 2)
    kw = steady_boundary_inputs(d, mesh)
    assert set(kw) == {"conductivity", "dirichlet", "heat_source", "outward_flux", "convection"}
    assert kw["outward_flux"] == {"right": 2.}                 # outward = 0.0 - inward (hazard H1)
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
    raw = data()
    p = physics(raw)
    p.pop("inward_heat_flux")
    p.pop("convection")
    if presence in ("flux", "both"):
        p["inward_heat_flux"] = {}
    if presence in ("robin", "both"):
        p["convection"] = {}
    d = document(raw)
    before, si = copy.deepcopy(d.data), copy.deepcopy(d.si)
    validate_steady_boundary(d)
    assert steady_result_versions(d) == (V1_03 if presence == "neither" else V2_03)
    steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 2))
    assert d.data == before and d.si == si


@pytest.mark.parametrize("unit,factor", [("m", 1.), ("mm", 1000.), ("um", 1e6)])
def test_nonzero_origin_units_and_data_lifetime(unit, factor):
    raw = data()
    raw["geometry"]["length_unit"] = unit
    raw["geometry"]["domain"] = dict(xmin=2*factor, xmax=3*factor, ymin=-3*factor, ymax=-2*factor)
    d = document(raw)
    mesh = rectangle_mesh(1, 1, 2, 2)
    mesh.nodes += [2., -3.]
    before = copy.deepcopy(d.data)
    nodes, cells = mesh.nodes.copy(), mesh.triangles.copy()
    kw = steady_boundary_inputs(d, mesh)
    assert d.data == before
    np.testing.assert_array_equal(mesh.nodes, nodes)
    np.testing.assert_array_equal(mesh.triangles, cells)
    physics(d.data)["convection"]["right"]["heat_transfer_coefficient"] = "99 W/(m^2 K)"
    physics(d.data)["prescribed_temperature"]["left"] = "999 K"
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
    raw = data()
    physics(raw)["prescribed_temperature"] = {}
    physics(raw)["inward_heat_flux"] = {}
    d = document(raw)
    result = solve_steady_heat(rectangle_mesh(1, 1, 2, 2),
                               **steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 2)))
    np.testing.assert_allclose(result.temperature, 290., rtol=0, atol=1e-10)
    assert not result.reaction.any()


@pytest.mark.parametrize("balanced", [False, True])
def test_pure_neumann_rejects_compatible_and_incompatible(balanced):
    raw = data()
    p = physics(raw)
    p["prescribed_temperature"] = {}
    p["convection"] = {}
    p["heat_source_density"] = "2 W/m^3" if balanced else "3 W/m^3"
    with pytest.raises(DocumentError, match="anchor"):
        validate_steady_boundary(document(raw))


def test_zero_h_not_anchor_but_zero_h_with_other_anchor_valid():
    raw = data()
    physics(raw)["convection"]["right"]["heat_transfer_coefficient"] = "0 W/(m^2 K)"
    validate_steady_boundary(document(raw))
    physics(raw)["prescribed_temperature"] = {}
    with pytest.raises(DocumentError, match="anchor"):
        validate_steady_boundary(document(raw))


def test_partial_corner_load_is_not_deleted():
    raw = data()
    p = physics(raw)
    p["inward_heat_flux"] = {"top": "-6 W/m^2"}
    p["convection"] = {}
    mesh = rectangle_mesh(1, 1, 2, 2)
    kw = steady_boundary_inputs(document(raw), mesh)
    result = solve_steady_heat(mesh, **kw)
    corner = np.intersect1d(mesh.boundary["left"], mesh.boundary["top"])[0]
    # First top edge length .5, endpoint moment g*ell/2=1.5 W/m, even at fixed corner.
    np.testing.assert_allclose(result.prescribed_outward_load[corner], 1.5, rtol=0, atol=1e-12)
    np.testing.assert_allclose(result.prescribed_outward_load.sum(), 6., rtol=0, atol=1e-12)


@pytest.mark.parametrize("kind", ["flux", "robin"])
def test_fully_fixed_actual_edge_despite_disjoint_side_names(kind):
    raw = data()
    p = physics(raw)
    p["prescribed_temperature"] = {"top": "300 K", "bottom": "300 K"}
    p["inward_heat_flux"] = {"left": "0 W/m^2"} if kind == "flux" else {}
    # an ambient temperature is above 0 K in format 0.3 (it was 0 K here before units batch C7)
    p["convection"] = ({"left": {"heat_transfer_coefficient": "0 W/(m^2 K)", "ambient_temperature": "1 K"}}
                       if kind == "robin" else {})
    d = document(raw)
    validate_steady_boundary(d)  # Shape-level side names alone cannot decide.
    with pytest.raises(DocumentError, match="fully Dirichlet"):
        steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 1))


H = "physics.heat1."


@pytest.mark.parametrize("path", [
    H+"thermal_conductivity", H+"heat_source_density", H+"inward_heat_flux.right", H+"prescribed_temperature.left",
    H+"convection.right.heat_transfer_coefficient", H+"convection.right.ambient_temperature",
])
@pytest.mark.parametrize("value", [True, None, "2", float("nan"), float("inf"), 1+0j, 10**1000])
def test_strict_numeric_rejections(path, value):
    raw = data()
    set_value(raw, path, value)
    with pytest.raises(DocumentError):
        validate_steady_boundary(document(raw))


@pytest.mark.parametrize("path,value", [
    (H+"thermal_conductivity", "0 W/(m K)"),
    (H+"convection.right.heat_transfer_coefficient", "-1 W/(m^2 K)"),
    (H+"convection.right.ambient_temperature", "-1 K"),
    (H+"prescribed_temperature.left", "-1 K"),
    (H+"convection.right", ["1 W/(m^2 K)", "300 K"]),
    (H+"convection.right", {"heat_transfer_coefficient": "1 W/(m^2 K)"}),
    (H+"convection.right", {"heat_transfer_coefficient": "1 W/(m^2 K)", "ambient_temperature": "300 K", "extra": 0}),
    (H+"inward_heat_flux", None),
    (H+"inward_heat_flux", {"outer": "0 W/m^2"}),
    (H+"inward_heat_flux.right", ["2 W/m^2"]),
    (H+"unknown", 0),
    ("geometry.shapes", []),
    ("units", {"time": "s"}),
    ("geometry.length_unit", "C"),
    ("mesh.subdivision_count", [True, 2]),
    ("mesh.subdivision_count", [2., 2]),
    ("mesh.subdivision_count", [0, 2]),
    ("study.type", "transient"),
    ("results.plots", True),
    ("geometry.domain.xmax", 0),
])
def test_invalid_shapes_unknown_units_and_ranges(path, value):
    raw = data()
    set_value(raw, path, value)
    with pytest.raises(DocumentError):
        validate_steady_boundary(document(raw))


@pytest.mark.parametrize("tag", ["bottom", "top"])
def test_equal_corner_dedup_conflict_and_full_side_overlap(tag):
    raw = data()
    p = physics(raw)
    p["prescribed_temperature"][tag] = "300 K"
    kw = steady_boundary_inputs(document(raw), rectangle_mesh(1, 1, 2, 2))
    assert len(kw["dirichlet"]) == 5
    p["prescribed_temperature"][tag] = "301 K"
    with pytest.raises(DocumentError, match="corner"):
        validate_steady_boundary(document(raw))
    p["prescribed_temperature"] = {"right": "300 K"}
    with pytest.raises(DocumentError, match="overlaps"):
        validate_steady_boundary(document(raw))


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
    # The unclamped negative solution is test_signed_flux_and_unclamped_negative_solution_format_03
    # (0 K is outside the registry domain since format 0.3); here: a negative source and a heat
    # input through the right side are valid inputs
    raw = data()
    p = physics(raw)
    p["inward_heat_flux"] = {"right": "10 W/m^2"}
    p["heat_source_density"] = "-1 W/m^3"
    validate_steady_boundary(document(raw))


def test_signed_flux_and_unclamped_negative_solution_format_03():
    # Format 0.3 twin: 0 K is outside the registry domain, so the left side is at 1 K and the
    # right side loses 10 W/m^2 (inward_heat_flux -10 W/m^2). The solution minimum is -4 K
    # (measured; -5 K with 0 K): the solver still does not clamp a negative temperature.
    d = Document.from_dict({
        "openphysics": "0.3", "name": "Boundary slab",
        "geometry": {"length_unit": "m", "depth": None, "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
        "materials": {}, "physics": {"heat1": {
            "type": "thermal.steady2d", "thermal_conductivity": "2 W/(m K)", "heat_source_density": "0 W/m^3",
            "prescribed_temperature": {"left": "1 K"}, "inward_heat_flux": {"right": "-10 W/m^2"},
            "convection": {}}},
        "mesh": {"subdivision_count": [2, 2]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False}})
    kw = steady_boundary_inputs(d, rectangle_mesh(1, 1, 2, 2))
    assert kw["outward_flux"] == {"right": 10.}            # outward = 0.0 - inward (hazard H1)
    result = solve_steady_heat(rectangle_mesh(1, 1, 2, 2), **kw)
    assert result.temperature.min() < 0
    np.testing.assert_allclose(result.temperature.min(), -4., rtol=0, atol=1e-12)
    d.data["physics"]["heat1"]["prescribed_temperature"] = {"left": "0 K"}
    with pytest.raises(DocumentError) as caught:
        d.validate()
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [
        ("E-DOMAIN", "physics.heat1.prescribed_temperature.left")]


def test_a_format_0_2_document_is_refused_by_name():
    old = Document({"openphysics": "0.2", "name": "Boundary slab", "units": {"length": "m", "temperature": "K"},
                    "geometry": {"domain": {"xmin": 0., "xmax": 1., "ymin": 0., "ymax": 1.}}, "materials": {},
                    "physics": {"heat1": {"type": "thermal.steady2d", "conductivity_w_mk": 2.,
                                          "dirichlet_temperature_k": {"left": 300.}}},
                    "mesh": {"subdivisions": [2, 2]}, "study": {"type": "single"},
                    "results": {"save_fields": True, "plots": False}})
    for call in (validate_steady_boundary, steady_result_versions):
        with pytest.raises(DocumentError, match="format 0.2 rectangle heat documents are not read"):
            call(old)


def test_invalid_mesh_does_not_change_document():
    d = document()
    before = copy.deepcopy(d.data)
    for bad in (None, object()):
        with pytest.raises(DocumentError, match="mesh"):
            steady_boundary_inputs(d, bad)
    assert d.data == before


@pytest.mark.parametrize("origin", [1e7, 1e9, 1e15])
def test_an_origin_beyond_the_picometre_grid_is_refused_by_the_reader(origin):
    raw = data()
    raw["geometry"]["domain"] = {"xmin": origin, "xmax": origin+1., "ymin": origin, "ymax": origin+1.}
    with pytest.raises(DocumentError) as caught:
        document(raw)
    assert {(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"} == {
        ("E-DOMAIN", "geometry.domain." + key) for key in ("xmin", "xmax", "ymin", "ymax")}


@pytest.mark.parametrize("origin", [1e9, 1e15])
@pytest.mark.parametrize("tag", ["normal", "wrong_side", "all_exterior"])
def test_large_origin_side_precision_and_tampered_robin_tag(origin, tag):
    grid, heat = far_inputs(origin)
    mesh = rectangle_mesh(1., 1., 2, 2)
    mesh.nodes += origin
    if tag == "wrong_side":
        mesh.boundary_edges["right"] = mesh.boundary_edges["left"].copy()
    elif tag == "all_exterior":
        mesh.boundary_edges["right"] = np.vstack(
            [mesh.boundary_edges[side] for side in ("left", "right", "bottom", "top")])
    if origin == 1e15:
        # Even correct tags must fail clearly when the unchanged 64-eps
        # coordinate budget can cover opposite sides. No wrong tag is accepted.
        with pytest.raises(DocumentError, match="insufficient coordinate precision"):
            boundary_kwargs(grid, heat, mesh)
    elif tag != "normal":
        with pytest.raises(DocumentError, match="complete SI side"):
            boundary_kwargs(grid, heat, mesh)
    else:
        kw = boundary_kwargs(grid, heat, mesh)
        assert kw["dirichlet"] == {}
        assert kw["convection"] == {"right": (4., 290.)}


def test_large_origin_wrong_dirichlet_node_side_is_rejected():
    grid, heat = far_inputs(1e9, full=True)
    mesh = rectangle_mesh(1., 1., 2, 2)
    mesh.nodes += 1e9
    mesh.boundary["left"] = mesh.boundary["right"].copy()
    with pytest.raises(DocumentError, match="complete unique SI side"):
        boundary_kwargs(grid, heat, mesh)


@pytest.mark.parametrize("tamper", [False, True])
def test_large_origin_adjacent_side_edge_ambiguity_rejects_even_normal_tags(tamper):
    origin = 1e13
    grid, heat = far_inputs(origin, subdivisions=(8, 8))
    mesh = rectangle_mesh(1., 1., 8, 8)
    mesh.nodes += origin
    if tamper:
        # The last top edge is adjacent to right and shorter than the retained
        # coordinate budget. It must never be admitted as another right edge.
        mesh.boundary_edges["right"] = np.vstack(
            [mesh.boundary_edges["right"], mesh.boundary_edges["top"][-1]])
    with pytest.raises(DocumentError, match="ambiguous rectangle side edge classification"):
        boundary_kwargs(grid, heat, mesh)


def test_near_side_interior_node_cannot_become_dirichlet_by_coordinate_mask():
    origin = 1e13
    grid, heat = far_inputs(origin, full=True, subdivisions=(8, 8))
    mesh = rectangle_mesh(1., 1., 8, 8)
    mesh.nodes += origin
    # This malformed selection includes the nearby interior column. Geometry's
    # ambiguous edge classification must reject before accepting any such nodes.
    mesh.boundary["left"] = np.flatnonzero(mesh.nodes[:, 0] <= origin+.125)
    with pytest.raises(DocumentError, match="ambiguous rectangle side edge classification"):
        boundary_kwargs(grid, heat, mesh)


@pytest.mark.parametrize("include_interior", [False, True])
def test_dirichlet_identity_uses_exterior_endpoints_not_nearby_interior(include_interior):
    # Fixture geometry validity is intentionally checked by the real helper;
    # this direct branch coverage must not mock or bypass galerkin.core.triangles.triangle_geometry.
    origin = 1e12
    grid, heat = far_inputs(origin, full=True)
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
            boundary_kwargs(grid, heat, mesh)
    else:
        kw = boundary_kwargs(grid, heat, mesh)
        assert list(kw["dirichlet"]) == sorted(map(int, normal_left))
        assert center not in kw["dirichlet"]
