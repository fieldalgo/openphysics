# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Element source transfer conserves total power and preserves mesh identity."""
import copy

import numpy as np
import pytest

from galerkin.mesh import rectangle_mesh
from galerkin.thermal import ElementHeatSource, solve_steady_heat


def solve(mesh, source):
    fixed = np.unique(np.concatenate(list(mesh.boundary.values())))
    return solve_steady_heat(mesh, conductivity=3., dirichlet={int(i): 300. for i in fixed},
                             heat_source=source)


def test_element_source_exact_local_load_and_power_not_region_average():
    mesh = rectangle_mesh(2., 1., 1, 1)
    source = ElementHeatSource(mesh, [3., 9.])
    result = solve(mesh, source)
    expected = np.zeros(mesh.num_nodes)
    for tri, value in zip(mesh.triangles, [3., 9.]):
        expected[tri] += value/3  # both triangle areas independently equal 1 m²
    np.testing.assert_allclose(result.load, expected, atol=1e-14, rtol=0)
    assert np.sum(result.load) == pytest.approx(12.)
    assert -np.sum(result.reaction) == pytest.approx(12.)
    assert not np.allclose(result.load, solve(mesh, 6.).load)


@pytest.mark.parametrize("change", ["coordinates", "cell_order", "node_order", "regions", "names"])
def test_same_size_different_mesh_rejected(change):
    mesh = rectangle_mesh(1., 1., 2, 2)
    mesh.regions = np.zeros(mesh.num_triangles, dtype=int)
    mesh.region_names = ["solid"]
    source = ElementHeatSource(mesh, np.arange(mesh.num_triangles))
    other = copy.deepcopy(mesh)
    if change == "coordinates":
        other.nodes *= 2
    elif change == "cell_order":
        other.triangles = other.triangles[::-1].copy()
    elif change == "node_order":
        other.triangles = np.roll(other.triangles, 1, axis=1)
    elif change == "regions":
        other.regions[0] = 1
    else:
        other.region_names = ["different"]
    with pytest.raises(ValueError, match="do not match"):
        solve(other, source)


def test_owned_snapshot_and_equivalent_copy():
    mesh = rectangle_mesh(1., 1., 2, 2)
    values = np.arange(mesh.num_triangles, dtype=float)
    source = ElementHeatSource(mesh, values)
    values[:] = 999
    np.testing.assert_array_equal(source.values, np.arange(mesh.num_triangles))
    np.testing.assert_array_equal(solve(mesh, source).load, solve(copy.deepcopy(mesh), source).load)
    with pytest.raises(ValueError):
        source.values[0] = 123
    mesh.nodes *= 2
    with pytest.raises(ValueError, match="do not match"):
        solve(mesh, source)


@pytest.mark.parametrize("bad", [[1.], [[1., 2.]], [np.nan, 1.], [np.inf, 1.],
                                  [1j, 2j], [True, False], ["1", "2"]])
def test_invalid_element_values(bad):
    with pytest.raises(ValueError, match="finite real shape"):
        ElementHeatSource(rectangle_mesh(1., 1., 1, 1), bad)


def test_signed_cooling_and_zero_are_valid_thermal_sources():
    mesh = rectangle_mesh(1., 1., 2, 2)
    for value in [-2., 0., 3.]:
        element = solve(mesh, ElementHeatSource(mesh, np.full(mesh.num_triangles, value)))
        scalar = solve(mesh, value)
        np.testing.assert_array_equal(element.load, scalar.load)
        np.testing.assert_array_equal(element.temperature, scalar.temperature)


def test_source_is_an_element_field_in_w_per_m3():
    from galerkin.coupling import Field
    mesh = rectangle_mesh(1., 1., 2, 2)
    source = ElementHeatSource(mesh, np.arange(mesh.num_triangles))
    assert isinstance(source.field, Field)
    assert (source.field.location, source.field.unit) == ("element", "W/m^3")
    assert source.values is source.field.values
    assert source.field.signature.matches(mesh)
