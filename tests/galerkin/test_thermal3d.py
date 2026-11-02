# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""3D P1 steady heat (docs/packages/galerkin/thermal3d.md) against refsol.thermal3d.

M4  manufactured sine product on an extruded box: L2 order >= 1.8, H1 order >= 0.9
    over sizes 0.2, 0.1, 0.05; layered slab along z exact to <= 1e-10; heat balance
    <= 1e-10 on every solve.
M5  refusals: bad regions, nodes off the boundary, conflicting face temperatures,
    an unanchored component, live inputs.
"""
import sys
import types

import numpy as np
import pytest

from galerkin import Mesh3D, box_mesh, from_mesher
from galerkin.thermal3d import dirichlet_from_faces, solve_steady_heat_3d, source_load_3d

meshine = pytest.importorskip("meshine")
refsol = pytest.importorskip("refsol")
from refsol import thermal3d as exact  # noqa: E402

LENGTHS = (1.0, 0.8, 0.6)


def extruded(h, z=(0.0, LENGTHS[2]), materials=None):
    from meshine import Domain, box_sides, extrude, generate, rectangle
    d = Domain(size=h)
    d.add_region("box", rectangle(0, 0, LENGTHS[0], LENGTHS[1]))
    return from_mesher(extrude(generate(d, box_sides(0, LENGTHS[0], 0, LENGTHS[1])), list(z),
                               materials, size=h))


def _tet_rule():
    """Collapsed 4x4x4 Gauss rule on the reference tetrahedron: barycentric weights summing to 1/6."""
    x, w = np.polynomial.legendre.leggauss(4)
    x, w = 0.5 * (x + 1), 0.5 * w
    u, v, s = np.meshgrid(x, x, x, indexing="ij")
    wu, wv, ws = np.meshgrid(w, w, w, indexing="ij")
    a, b, c = u, v * (1 - u), s * (1 - u) * (1 - v)
    weight = (wu * wv * ws * (1 - u) ** 2 * (1 - v)).ravel()
    lam = np.stack([1 - a - b - c, a, b, c], axis=-1).reshape(-1, 4)
    return lam, weight


def _errors(mesh, result, k):
    lam, wq = _tet_rule()
    p = mesh.nodes[mesh.tets]
    vol6 = 6.0 * mesh.volumes()
    xq = np.einsum("qk,tkd->tqd", lam, p)
    fields = exact.sine_product(xq.reshape(-1, 3), lengths=LENGTHS, conductivity=k)
    u = fields.temperature.reshape(xq.shape[:2])
    gu = -fields.heat_flux.reshape(xq.shape) / k
    uh = np.einsum("qk,tk->tq", lam, result.temperature[mesh.tets])
    guh = -result.heat_flux / k
    e2 = ((uh - u) ** 2 * wq * vol6[:, None]).sum()
    g2 = (((guh[:, None, :] - gu) ** 2).sum(axis=2) * wq * vol6[:, None]).sum()
    return np.sqrt(e2), np.sqrt(g2)


def _manufactured(h, k=2.5):
    mesh = extruded(h)
    source = lambda c: exact.sine_product(c, lengths=LENGTHS, conductivity=k).heat_source
    bc = dirichlet_from_faces(mesh, dict.fromkeys(mesh.tagged_faces, 300.0))
    result = solve_steady_heat_3d(mesh, conductivity=k, dirichlet=bc, heat_source=source)
    assert result.balance_error <= 1e-10
    return mesh, result


@pytest.mark.slow
def test_m4_manufactured_sine_product_converges_at_second_order():
    sizes = (0.2, 0.1, 0.05)
    l2, h1 = zip(*(_errors(*_manufactured(h), 2.5) for h in sizes))
    order_l2 = np.polyfit(np.log(sizes), np.log(l2), 1)[0]
    order_h1 = np.polyfit(np.log(sizes), np.log(h1), 1)[0]
    print(f"M4 L2 {list(l2)} order {order_l2:.3f}; H1 {list(h1)} order {order_h1:.3f}")
    assert order_l2 >= 1.8, (order_l2, l2)
    assert order_h1 >= 0.9, (order_h1, h1)


def test_manufactured_solution_on_a_coarse_mesh_is_close_and_balanced():
    mesh, result = _manufactured(0.2)
    nodal = exact.sine_product(mesh.nodes, lengths=LENGTHS, conductivity=2.5).temperature
    assert np.abs(result.temperature - nodal).max() < 0.2       # amplitude 1 K, h = 0.2 m
    assert np.array_equal(result.dirichlet_nodes, mesh.boundary_nodes())
    assert abs(result.load.sum() + result.reaction.sum()) <= 1e-10 * np.abs(result.load).sum()
    # the source load integrates Q exactly for a constant per tetrahedron
    assert abs(result.load.sum() - (result.heat_source * mesh.volumes()).sum()) <= 1e-12 * abs(result.load).sum()
    assert np.all(result.reaction[np.setdiff1d(np.arange(mesh.num_nodes), result.dirichlet_nodes)] == 0)


def test_m4_layered_slab_is_reproduced_exactly():
    z = (0.0, 0.2, 0.3, 0.6)
    k = {"substrate": 1.0, "die": 0.01, "mold": 0.5}
    mesh = extruded(0.15, z, {"box": ["substrate", "die", "mold"]})
    bc = dirichlet_from_faces(mesh, {"z0": 320.0, "z1": 300.0})
    result = solve_steady_heat_3d(mesh, conductivity=k, dirichlet=bc)
    fields = exact.layered_slab(mesh.nodes, interfaces=z[1:], conductivities=[k[n] for n in
                                ("substrate", "die", "mold")], bottom_temperature=320.0,
                                top_temperature=300.0)
    error = np.abs(result.temperature - fields.temperature).max() / 20.0
    centroids = mesh.nodes[mesh.tets].mean(axis=1)
    flux_error = np.abs(result.heat_flux - exact.layered_slab(
        centroids, interfaces=z[1:], conductivities=[1.0, 0.01, 0.5], bottom_temperature=320.0,
        top_temperature=300.0).heat_flux).max() / abs(fields.heat_flux[0, 2])
    print(f"M4 layered slab temperature error {error:.3e}, flux error {flux_error:.3e}, "
          f"balance {result.balance_error:.3e}")
    assert error <= 1e-10
    assert flux_error <= 1e-9
    assert result.balance_error <= 1e-10
    # reactions: heat enters at the hot face and leaves at the cold one, flux x area
    area = LENGTHS[0] * LENGTHS[1]
    hot = result.reaction[np.unique(mesh.tagged_faces["z0"])].sum()
    assert abs(hot - fields.heat_flux[0, 2] * area) <= 1e-9 * abs(hot)
    assert np.array_equal(result.conductivity, mesh.by_region(k))


def test_region_sources_on_the_box_mesh_balance_and_use_every_region():
    base = box_mesh(*LENGTHS, 4, 3, 3)
    regions = (base.nodes[base.tets].mean(axis=1)[:, 0] > 0.5).astype(int)
    mesh = Mesh3D(base.nodes, base.tets, base.boundary, regions, ["left", "right"],
                  tagged_faces=base.tagged_faces)
    bc = dirichlet_from_faces(mesh, {"x0": 300.0})
    result = solve_steady_heat_3d(mesh, conductivity={"left": 1.0, "right": 10.0}, dirichlet=bc,
                                  heat_source={"left": 0.0, "right": 1e4})
    assert result.balance_error <= 1e-10
    assert abs(result.load.sum() - 1e4 * 0.5 * LENGTHS[1] * LENGTHS[2]) <= 1e-9 * result.load.sum()
    assert np.all(result.temperature >= 300.0 - 1e-9)
    assert np.array_equal(result.heat_source, np.where(regions == 1, 1e4, 0.0))
    assert np.allclose(source_load_3d(mesh, result.heat_source), result.load)


def test_m5_refusals(monkeypatch):
    mesh = extruded(0.3)
    bc = dirichlet_from_faces(mesh, {"z0": 300.0})
    with pytest.raises(ValueError, match="match mesh.region_names"):
        solve_steady_heat_3d(mesh, conductivity={"air": 1.0}, dirichlet=bc)
    with pytest.raises(ValueError, match="> 0"):
        solve_steady_heat_3d(mesh, conductivity=-1.0, dirichlet=bc)
    with pytest.raises(ValueError, match="exterior mesh boundary"):
        interior = int(np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary_nodes())[0])
        solve_steady_heat_3d(mesh, conductivity=1.0, dirichlet={interior: 300.0})
    with pytest.raises(ValueError, match="different temperatures"):
        dirichlet_from_faces(mesh, {"z0": 300.0, "left": 310.0})
    with pytest.raises(ValueError, match="unknown face tag"):
        dirichlet_from_faces(mesh, {"lid": 300.0})
    with pytest.raises(ValueError, match="needs a Dirichlet node"):
        solve_steady_heat_3d(mesh, conductivity=1.0, dirichlet={})
    with pytest.raises(ValueError, match="centroids"):
        solve_steady_heat_3d(mesh, conductivity=1.0, dirichlet=bc, heat_source=lambda c: c)
    with pytest.raises(TypeError, match="Mesh3D"):
        solve_steady_heat_3d({"nodes": mesh.nodes}, conductivity=1.0, dirichlet=bc)

    class Array:
        pass
    monkeypatch.setitem(sys.modules, "jax", types.SimpleNamespace(Array=Array))
    with pytest.raises(TypeError, match="carries no derivative"):
        solve_steady_heat_3d(mesh, conductivity=Array(), dirichlet=bc)
    with pytest.raises(TypeError, match="carries no derivative"):
        solve_steady_heat_3d(mesh, conductivity=1.0, dirichlet={**bc, 0: Array()})
    with pytest.raises(TypeError, match="carries no derivative"):
        solve_steady_heat_3d(mesh, conductivity=1.0, dirichlet=bc, heat_source={"box": Array()})
