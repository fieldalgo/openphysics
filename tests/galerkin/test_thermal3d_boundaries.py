# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact slab fields and power balances on the public 3D heat API."""
import numpy as np
import pytest

from galerkin import box_mesh
from galerkin.kernels import dirichlet_from_faces
from galerkin.thermal3d import solve_steady_heat_3d
from refsol.thermal_boundary import dirichlet_robin_slab, robin_only_slab


@pytest.mark.parametrize("nx", [2, 5, 10])
@pytest.mark.parametrize(("inward", "h"), [(7.0, 0.0), (0.0, 4.0), (7.0, 4.0), (-7.0, 4.0)])
def test_slab_flux_and_robin(nx, inward, h):
    length, k, left, ambient, area = 1.2, 2.5, 310.0, 300.0, 0.8 * 0.6
    mesh = box_mesh(length, 0.8, 0.6, nx, 2, 3)
    result = solve_steady_heat_3d(
        mesh, thermal_conductivity=k,
        prescribed_temperature=dirichlet_from_faces(mesh, {"x0": left}),
        inward_heat_flux={"x1": inward} if inward else None,
        convection={"x1": (h, ambient)} if h else None,
    )
    slope = (inward - h * (left - ambient)) / (k + h * length)
    reference = dirichlet_robin_slab(
        length=length, thermal_conductivity=k, prescribed_temperature=left,
        heat_source_density=0.0, inward_heat_flux=inward,
        heat_transfer_coefficient=h, ambient_temperature=ambient,
    )
    np.testing.assert_allclose(result.temperature, left + slope * mesh.nodes[:, 0], rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.temperature, reference.temperature(mesh.nodes), rtol=0, atol=1e-10)
    flux = reference.heat_flux(mesh.nodes[mesh.tets].mean(axis=1))
    np.testing.assert_allclose(result.heat_flux[:, :2], flux, rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.heat_flux[:, 2], 0.0, rtol=0, atol=1e-10)
    assert result.outward_prescribed_heat_rate.sum() == pytest.approx(-area * inward, abs=1e-11)
    assert result.outward_convective_heat_rate.sum() == pytest.approx(
        area * h * (left + slope * length - ambient), abs=1e-11)
    assert result.reaction_heat_rate.sum() == pytest.approx(-area * reference.outward_heat_flux[0], abs=1e-11)
    assert result.relative_conservation_residual <= 1e-10


def test_distinct_flux_and_robin_faces_anchor_without_dirichlet():
    mesh = box_mesh(1.2, 0.8, 0.6, 4, 2, 3)
    result = solve_steady_heat_3d(
        mesh, thermal_conductivity=2.5, prescribed_temperature={},
        inward_heat_flux={"x0": 7.0}, convection={"x1": (4.0, 300.0)},
    )
    reference = robin_only_slab(
        length=1.2, thermal_conductivity=2.5, heat_transfer_coefficient=(0.0, 4.0),
        ambient_temperature=(300.0, 300.0), heat_source_density=0.0, inward_heat_flux=(7.0, 0.0),
    )
    np.testing.assert_allclose(result.temperature, reference.temperature(mesh.nodes), rtol=0, atol=1e-10)
    assert result.outward_prescribed_heat_rate.sum() == pytest.approx(-7.0 * 0.8 * 0.6)
    assert result.outward_convective_heat_rate.sum() == pytest.approx(7.0 * 0.8 * 0.6)
    assert result.relative_conservation_residual <= 1e-10


def test_element_joule_density_preserves_order_and_total_power():
    mesh = box_mesh(1.2, 0.8, 0.6, 4, 2, 3)
    # Synthetic, varying J·E in mesh.tets order. No electrical solver dependency.
    density = 3.0 + mesh.nodes[mesh.tets].mean(axis=1).sum(axis=1)
    result = solve_steady_heat_3d(
        mesh, thermal_conductivity=2.5, prescribed_temperature={},
        heat_source_density=density, convection={"x1": (4.0, 300.0)},
    )
    np.testing.assert_array_equal(result.heat_source_density, density)
    expected_nodal = np.bincount(mesh.tets.ravel(), weights=np.repeat(density * mesh.volumes() / 4, 4))
    np.testing.assert_allclose(result.generated_heat_rate, expected_nodal, rtol=1e-13, atol=0)
    total = density @ mesh.volumes()
    assert result.generated_heat_rate.sum() == pytest.approx(total, rel=1e-13)
    assert result.outward_convective_heat_rate.sum() == pytest.approx(total, rel=1e-11)
    assert result.relative_conservation_residual <= 1e-10


@pytest.mark.parametrize(("options", "message"), [
    ({"inward_heat_flux": {"typo": 1}}, "exterior face tag"),
    ({"inward_heat_flux": {"x0": 1}}, "fully prescribed"),
    ({"inward_heat_flux": {"x1": np.inf}}, "finite"),
    ({"convection": {"x1": (1,)}}, "pair"),
    ({"convection": {"x1": (-1, 300)}}, "coefficient"),
    ({"convection": {"x1": (1, np.nan)}}, "finite"),
    ({"convection": [1, 300]}, "must map"),
    ({"heat_source_density": [1, 2]}, "one finite value"),
])
def test_invalid_data(options, message):
    mesh = box_mesh(1, 1, 1, 2, 2, 2)
    with pytest.raises(ValueError, match=message):
        solve_steady_heat_3d(mesh, thermal_conductivity=1,
                             prescribed_temperature=dirichlet_from_faces(mesh, {"x0": 300}), **options)


def test_interior_and_duplicate_faces_rejected():
    mesh = box_mesh(1, 1, 1, 2, 2, 2)
    faces, counts = mesh.faces()
    mesh.tagged_faces["interior"] = faces[counts == 2][:1]
    mesh.tagged_faces["duplicate"] = mesh.tagged_faces["x1"][:, ::-1]
    for tags, message in [({"interior": 1}, "non-exterior"), ({"x1": 1, "duplicate": 1}, "duplicate face")]:
        with pytest.raises(ValueError, match=message):
            solve_steady_heat_3d(
                mesh, thermal_conductivity=1,
                prescribed_temperature=dirichlet_from_faces(mesh, {"x0": 300}), inward_heat_flux=tags,
            )


def test_neumann_and_zero_h_do_not_anchor():
    mesh = box_mesh(1, 1, 1, 2, 2, 2)
    with pytest.raises(ValueError, match="positive convection"):
        solve_steady_heat_3d(mesh, thermal_conductivity=1, prescribed_temperature={},
                             inward_heat_flux={"x0": 1}, convection={"x1": (0, 300)})


def test_heated_robin_slab_converges_against_independent_collocation():
    from scipy.integrate import solve_bvp

    length, k, source, h, ambient, left, inward = 1.2, 2.5, 5.0, 4.0, 300.0, 310.0, 7.0

    def ode(x, y):
        return np.vstack((y[1], np.full_like(x, -source / k)))

    def boundary_conditions(a, b):
        return np.array((a[0] - left, -k * b[1] - h * (b[0] - ambient) + inward))

    x = np.linspace(0, length, 8)
    reference = solve_bvp(ode, boundary_conditions, x,
                          np.vstack((np.full_like(x, left), np.zeros_like(x))), tol=1e-10)
    assert reference.success, reference.message
    exact = dirichlet_robin_slab(
        length=length, thermal_conductivity=k, prescribed_temperature=left,
        heat_source_density=source, inward_heat_flux=inward,
        heat_transfer_coefficient=h, ambient_temperature=ambient,
    )
    np.testing.assert_allclose(reference.sol(x)[0], exact.temperature(x[:, None]), rtol=0, atol=1e-10)

    sizes, errors = (3, 6, 12), []
    for n in sizes:
        mesh = box_mesh(length, 0.8, 0.6, n, n, n)
        result = solve_steady_heat_3d(
            mesh, thermal_conductivity=k,
            prescribed_temperature=dirichlet_from_faces(mesh, {"x0": left}),
            heat_source_density=np.full(mesh.num_tets, source),
            inward_heat_flux={"x1": inward}, convection={"x1": (h, ambient)},
        )
        expected_temperature = reference.sol(mesh.nodes[:, 0])[0]
        expected_flux = -k * reference.sol(mesh.nodes[mesh.tets, 0].mean(axis=1))[1]
        errors.append((np.sqrt(np.mean((result.temperature - expected_temperature)**2)),
                       np.sqrt(np.average((result.heat_flux[:, 0] - expected_flux)**2, weights=mesh.volumes()))))
        assert result.relative_conservation_residual <= 1e-10
    order_temperature, order_flux = np.polyfit(-np.log(sizes), np.log(errors), 1)[0]
    assert order_temperature >= 1.8, (order_temperature, errors)
    assert order_flux >= 0.9, (order_flux, errors)
