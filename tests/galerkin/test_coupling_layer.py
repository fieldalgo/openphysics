# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coupling layer: mesh identity, node/element fields, same-mesh transfer, one-way chains."""
import copy

import numpy as np
import pytest

from galerkin.coupling import Field, MeshSignature, OneWayChain, transfer
from galerkin.mesh import rectangle_mesh


def region_mesh():
    mesh = rectangle_mesh(1., 1., 2, 2)
    mesh.regions = np.zeros(mesh.num_triangles, dtype=int)
    mesh.region_names = ["solid"]
    return mesh


def changed(mesh, change):
    other = copy.deepcopy(mesh)
    if change == "coordinates":
        other.nodes *= 2
    elif change == "cell_order":
        other.triangles = other.triangles[::-1].copy()
    elif change == "node_order":
        other.triangles = np.roll(other.triangles, 1, axis=1)
    elif change == "regions":
        other.regions[0] = 1
    elif change == "names":
        other.region_names = ["different"]
    elif change == "no_regions":
        other.regions = None
        other.region_names = None
    return other


def test_signature_matches_equal_copy_and_ignores_boundary_tags():
    mesh = region_mesh()
    signature = MeshSignature(mesh)
    other = copy.deepcopy(mesh)
    other.boundary = {}
    other.boundary_edges = {}
    assert signature.matches(other)
    assert signature.matches(other, regions=False)


@pytest.mark.parametrize("change", ["coordinates", "cell_order", "node_order"])
def test_signature_rejects_geometry_or_ordering(change):
    mesh = region_mesh()
    other = changed(mesh, change)
    assert not MeshSignature(mesh).matches(other)
    assert not MeshSignature(mesh).matches(other, regions=False)


@pytest.mark.parametrize("change", ["regions", "names", "no_regions"])
def test_signature_regions_compared_only_when_asked(change):
    mesh = region_mesh()
    other = changed(mesh, change)
    assert not MeshSignature(mesh).matches(other)
    assert MeshSignature(mesh).matches(other, regions=False)


def test_signature_owns_read_only_copies():
    mesh = region_mesh()
    signature = MeshSignature(mesh)
    mesh.nodes *= 2
    mesh.regions[0] = 1
    assert not signature.matches(mesh, regions=False)
    for value in (signature.nodes, signature.triangles, signature.regions):
        with pytest.raises(ValueError):
            value[0] = 0
    assert signature.region_names == ("solid",)


@pytest.mark.parametrize("location,count", [("node", "num_nodes"), ("element", "num_triangles")])
def test_field_owned_float64_read_only(location, count):
    mesh = region_mesh()
    values = np.arange(getattr(mesh, count))
    field = Field(mesh, values, location=location, unit="K")
    values[:] = 7
    assert field.values.dtype == np.float64
    np.testing.assert_array_equal(field.values, np.arange(getattr(mesh, count)))
    with pytest.raises(ValueError):
        field.values[0] = 1.
    assert (field.location, field.unit) == (location, "K")
    assert field.on_mesh(copy.deepcopy(mesh)) is field.values


@pytest.mark.parametrize("bad", [[1.], [np.nan] * 9, [np.inf] * 9, [1j] * 9,
                                 [True] * 9, ["1"] * 9, np.ones((9, 1))])
def test_field_rejects_invalid_values(bad):
    with pytest.raises(ValueError, match=r"^node field must be finite real shape \(N,\)$"):
        Field(region_mesh(), bad, location="node", unit="K")
    with pytest.raises(ValueError, match=r"^my source must be finite real shape \(M,\)$"):
        Field(region_mesh(), bad[:8] if len(bad) == 9 else bad, location="element", unit="W/m^3",
              name="my source")


def test_field_rejects_overflow_location_unit_and_mesh():
    mesh = region_mesh()
    huge = np.longdouble("1e400")
    if np.isfinite(huge):
        with pytest.warns(RuntimeWarning), pytest.raises(ValueError, match="^node field exceeds floating-point range$"):
            Field(mesh, np.full(mesh.num_nodes, huge), location="node", unit="K")
    with pytest.raises(ValueError, match="location"):
        Field(mesh, np.ones(mesh.num_nodes), location="edge", unit="K")
    for unit in ("", None, 1):
        with pytest.raises(ValueError, match="unit"):
            Field(mesh, np.ones(mesh.num_nodes), location="node", unit=unit)
    with pytest.raises(ValueError, match="galerkin.mesh.Mesh"):
        Field(object(), [1., 2., 3.], location="node", unit="K")


@pytest.mark.parametrize("library", ["jax", "torch"])
def test_field_refuses_live_values(library):
    module = pytest.importorskip(library)
    mesh = region_mesh()
    if library == "jax":
        values = module.numpy.ones(mesh.num_nodes)
    else:
        values = module.ones(mesh.num_nodes, dtype=module.float64)
    with pytest.raises(TypeError, match="^temperature: .*NumPy"):
        Field(mesh, values, location="node", unit="K", name="temperature")


def test_on_mesh_uses_caller_message():
    mesh = region_mesh()
    field = Field(mesh, np.ones(mesh.num_triangles), location="element", unit="W/m^3")
    with pytest.raises(ValueError, match="^source mesh differs$"):
        field.on_mesh(changed(mesh, "names"), message="source mesh differs")
    np.testing.assert_array_equal(field.on_mesh(changed(mesh, "names"), regions=False),
                                  np.ones(mesh.num_triangles))


def test_transfer_is_identity_on_same_mesh():
    mesh = region_mesh()
    field = Field(mesh, np.linspace(300., 310., mesh.num_nodes), location="node", unit="K")
    target = copy.deepcopy(mesh)
    moved = transfer(field, target)
    assert moved.values.tobytes() == field.values.tobytes()
    assert (moved.location, moved.unit) == ("node", "K")
    assert moved.signature.matches(target)


def test_transfer_without_regions_binds_to_target_regions():
    mesh = region_mesh()
    field = Field(mesh, np.ones(mesh.num_nodes), location="node", unit="K")
    target = changed(mesh, "regions")
    moved = transfer(field, target, regions=False)
    assert moved.signature.matches(target)
    assert not moved.signature.matches(mesh)


@pytest.mark.parametrize("change", ["coordinates", "cell_order", "node_order", "regions", "names"])
def test_transfer_refuses_different_mesh(change):
    mesh = region_mesh()
    field = Field(mesh, np.ones(mesh.num_triangles), location="element", unit="W/m^3")
    with pytest.raises(ValueError, match="does not match"):
        transfer(field, changed(mesh, change))
    with pytest.raises(ValueError, match="Field"):
        transfer(np.ones(mesh.num_triangles), mesh)


class StageError(ValueError):
    def __init__(self, stage, exc, **context):
        self.stage = stage
        self.context = context
        super().__init__(f"[{stage}] {exc}")


def test_chain_records_completed_stages_in_order():
    chain = OneWayChain(StageError)
    with chain.stage("heat"):
        pass
    with chain.stage("mechanics", time_index=3):
        pass
    assert chain.completed == ("heat", "mechanics")


def test_chain_failure_carries_stage_context_and_cause():
    chain = OneWayChain(StageError)
    with chain.stage("heat"):
        pass
    cause = KeyError("node 4")
    with pytest.raises(StageError, match=r"^\[transfer\] 'node 4'$") as caught:
        with chain.stage("transfer", time_index=2, time_s=.5):
            raise cause
    assert caught.value.stage == "transfer"
    assert caught.value.context == {"time_index": 2, "time_s": .5}
    assert caught.value.__cause__ is cause
    assert chain.completed == ("heat",)


def test_chain_requires_error_factory():
    with pytest.raises(ValueError, match="error"):
        OneWayChain(None)
