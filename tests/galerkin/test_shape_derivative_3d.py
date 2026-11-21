# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of 3D steady heat (galerkin.thermal3d, 2026-11-21).

T1-T10 were pre-registered in the HQ work record (2026-11-21) before the implementation ran:
T1 the motion's temperatures equal the ordinary solve on the moved mesh (relative 1e-12); T2 on
a two-region box with a source, an interior bump plus a face motion, dT/dt equals a Richardson
central difference of moved-mesh solves within 1e-8 of max |dT/dt|; T3 JAX and PyTorch agree
within 1e-12; T4 a rigid translation and an infinitesimal rotation give dT/dt = 0 within 1e-10
max |T|; T5 a two-layer box, dQ/dL1 of the analytic heat rate within 1e-10; T6 a hollow
cylinder, dQ/da against 2 pi k H (T1 - T2) / (a ln^2(b/a)) at order >= 1.5 and within 1e-2 on the
finest mesh; T7 the admissible interval brackets the first inversion within 1e-9 and a step
beyond it is refused; T8 the 3D harmonic extension reproduces linear data within 1e-12; T9
refusals; T10 without a motion, motion=None equals a call without the keyword bit for bit.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.shape import ElementInversion, MeshMotion, admissible_interval, extend_velocity
from galerkin.thermal3d import solve_steady_heat_3d

BACKENDS = ["jax", "torch"]


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _t(name, value=0.0):
    if name == "jax":
        return _jax().numpy.asarray(value, dtype=_jax().numpy.float64)
    torch = pytest.importorskip("torch")
    return torch.tensor(value, dtype=torch.float64)


def _jacobian(name, function):
    """d function / dt at t = 0 as NumPy numbers (function maps the live t to an array or a scalar)."""
    if name == "jax":
        jax = _jax()
        return np.asarray(jax.jacrev(function)(jax.numpy.asarray(0.0, dtype=jax.numpy.float64)))
    torch = pytest.importorskip("torch")
    return torch.autograd.functional.jacobian(function, torch.tensor(0.0, dtype=torch.float64)).detach().numpy()


def _moved(mesh, W, h):
    return Mesh3D(mesh.nodes + h * W, mesh.tets, mesh.boundary, mesh.regions, mesh.region_names)


def _richardson(values_at, h):
    def central(s):
        return (values_at(s) - values_at(-s)) / (2 * s)
    return (4 * central(h / 2) - central(h)) / 3


def _numbers(value):
    return np.asarray(value.detach() if hasattr(value, "detach") else value, dtype=float)


# ---------------------------------------------------------------- the two-region box

def _box():
    """[0, 1] x [0, 0.5] x [0, 0.5], regions split at x = 0.5, Dirichlet on x = 0 and x = 1; W is an
    interior bump plus a stretch that moves the x = 1 face (its Dirichlet values move with it)."""
    m = box_mesh(1.0, 0.5, 0.5, 8, 4, 4)
    cent = m.nodes[m.tets].mean(axis=1)
    m = Mesh3D(m.nodes, m.tets, m.boundary, (cent[:, 0] > 0.5).astype(int), ["a", "b"])
    x, y, z = m.nodes.T
    bump = np.sin(math.pi * x) * np.sin(math.pi * y / 0.5) * np.sin(math.pi * z / 0.5)
    W = np.stack([0.1 * x + 0.05 * bump, 0.03 * bump, -0.02 * bump], axis=1)
    return m, W


def _box_bc():
    """Dirichlet nodes of the reference box (they move with the mesh, keeping their values)."""
    x = box_mesh(1.0, 0.5, 0.5, 8, 4, 4).nodes[:, 0]
    return {**{int(i): 300.0 for i in np.flatnonzero(np.isclose(x, 0))},
            **{int(i): 310.0 for i in np.flatnonzero(np.isclose(x, 1))}}


def _box_solve(m, W, t):
    bc = _box_bc()
    return solve_steady_heat_3d(m, thermal_conductivity={"a": 2.0, "b": 5.0}, prescribed_temperature=bc,
                                heat_source_density={"a": 1.0e3, "b": 0.0},
                                motion=None if t is None else MeshMotion(design_velocity=W, t=t))


@pytest.mark.parametrize("name", BACKENDS)
def test_t1_the_motion_keeps_the_moved_mesh_numbers(name):
    m, W = _box()
    live = _box_solve(m, W, _t(name, 0.01))
    plain = _box_solve(_moved(m, W, 0.01), W, None)
    for field in ("temperature", "reaction_heat_rate", "generated_heat_rate", "heat_flux"):
        a, b = _numbers(getattr(live, field)), np.asarray(getattr(plain, field), dtype=float)
        assert np.max(np.abs(a - b)) <= 1e-12 * max(np.max(np.abs(b)), 1.0), field


def test_t2_t3_derivative_against_moved_meshes():
    m, W = _box()
    jac = {name: _jacobian(name, lambda t: _box_solve(m, W, t).temperature) for name in BACKENDS}
    fd = _richardson(lambda h: np.asarray(_box_solve(_moved(m, W, h), W, None).temperature), 2e-3)
    scale = np.max(np.abs(fd))
    assert scale > 0
    assert np.max(np.abs(jac["jax"] - fd)) <= 1e-8 * scale, np.max(np.abs(jac["jax"] - fd)) / scale       # T2
    assert np.max(np.abs(jac["torch"] - jac["jax"])) <= 1e-12 * np.max(np.abs(jac["jax"]))                # T3


@pytest.mark.parametrize("name", BACKENDS)
def test_t4_rigid_motions_do_not_change_the_temperatures(name):
    m, _W = _box()
    temperature = np.asarray(_box_solve(m, _W, None).temperature)
    translation = np.broadcast_to(np.array([1.0, 2.0, 3.0]), m.nodes.shape).copy()
    rotation = np.cross(np.array([0.3, -0.2, 0.5]), m.nodes)
    for W in (translation, rotation):
        derivative = _jacobian(name, lambda t: _box_solve(m, W, t).temperature)
        assert np.max(np.abs(derivative)) <= 1e-10 * np.max(np.abs(temperature))


# ---------------------------------------------------------------- T5 the two-layer box

@pytest.mark.parametrize("name", BACKENDS)
def test_t5_two_layer_box(name):
    L, L1, k1, k2, t_hot, t_cold, side = 1.0, 0.4, 2.0, 5.0, 400.0, 300.0, 0.2
    m = box_mesh(L, side, side, 10, 2, 2)
    cent = m.nodes[m.tets].mean(axis=1)
    m = Mesh3D(m.nodes, m.tets, m.boundary, (cent[:, 0] > L1).astype(int), ["one", "two"])
    x = m.nodes[:, 0]
    hot = np.flatnonzero(np.isclose(x, 0))
    bc = {**{int(i): t_hot for i in hot}, **{int(i): t_cold for i in np.flatnonzero(np.isclose(x, L))}}
    W = np.zeros_like(m.nodes)
    W[:, 0] = np.where(x <= L1, x / L1, (L - x) / (L - L1))          # moves the interface, not the ends

    def heat_in(t):
        r = solve_steady_heat_3d(m, thermal_conductivity={"one": k1, "two": k2}, prescribed_temperature=bc,
                                 motion=MeshMotion(design_velocity=W, t=t))
        return r.reaction_heat_rate[hot].sum()
    resistance = L1 / k1 + (L - L1) / k2
    exact = -side * side * (t_hot - t_cold) * (1 / k1 - 1 / k2) / resistance ** 2
    assert abs(float(_jacobian(name, heat_in)) / exact - 1) <= 1e-10


# ---------------------------------------------------------------- T6 the hollow cylinder

def _hollow_cylinder(a, b, height, nr, ntheta):
    """Structured (r, theta) prisms of one layer in z, each split into three tetrahedra by global
    vertex order (a conforming split); W moves the inner wall r = a outward with unit speed."""
    r = np.linspace(a, b, nr + 1)
    theta = np.linspace(0.0, 2 * math.pi, ntheta, endpoint=False)
    bottom = np.array([(ri * math.cos(q), ri * math.sin(q)) for ri in r for q in theta])
    plane = len(bottom)
    nodes = np.vstack([np.column_stack([bottom, np.zeros(plane)]), np.column_stack([bottom, np.full(plane, height)])])

    def nid(i, j):
        return i * ntheta + j % ntheta
    tets = []
    for i in range(nr):
        for j in range(ntheta):
            for tri in ((nid(i, j), nid(i + 1, j), nid(i + 1, j + 1)), (nid(i, j), nid(i + 1, j + 1), nid(i, j + 1))):
                p, q, s = sorted(tri)
                tets += [[p, q, s, s + plane], [p, q, q + plane, s + plane], [p, p + plane, q + plane, s + plane]]
    mesh = Mesh3D(nodes, np.array(tets))
    radius = np.hypot(nodes[:, 0], nodes[:, 1])
    W = np.zeros_like(nodes)
    W[:, :2] = ((b - radius) / (b - a))[:, None] * nodes[:, :2] / radius[:, None]
    return mesh, W, radius


def _inner_rate_slope(name, nr, ntheta):
    a, b, height, k, t1, t2 = 1.0, 2.0, 0.5, 3.0, 400.0, 300.0
    mesh, W, radius = _hollow_cylinder(a, b, height, nr, ntheta)
    inner = np.flatnonzero(np.isclose(radius, a))
    bc = {**{int(i): t1 for i in inner}, **{int(i): t2 for i in np.flatnonzero(np.isclose(radius, b))}}

    def heat_in(t):
        r = solve_steady_heat_3d(mesh, thermal_conductivity=k, prescribed_temperature=bc,
                                 motion=MeshMotion(design_velocity=W, t=t))
        return r.reaction_heat_rate[inner].sum()
    exact = 2 * math.pi * k * height * (t1 - t2) / (a * math.log(b / a) ** 2)
    return float(_jacobian(name, heat_in)), exact


@pytest.mark.parametrize("name", BACKENDS)
def test_t6_hollow_cylinder_inner_radius(name):
    results = [_inner_rate_slope(name, nr, nt) for nr, nt in ((4, 16), (8, 32), (16, 64))]
    errors = [abs(value / exact - 1) for value, exact in results]
    orders = [math.log2(errors[i] / errors[i + 1]) for i in range(2)]
    assert min(orders) >= 1.5, (errors, orders)
    assert errors[-1] <= 1e-2, errors


# ---------------------------------------------------------------- T7 inversion interval, T8 extension

def _volumes(nodes, tets):
    p = nodes[tets]
    return np.einsum("td,td->t", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0])) / 6.0


def test_t7_admissible_interval_brackets_the_first_inversion():
    m = box_mesh(1.0, 1.0, 1.0, 3, 3, 3)
    W = np.random.default_rng(7).standard_normal(m.nodes.shape)
    lo, hi = admissible_interval(m, design_velocity=W)
    assert -math.inf < lo < 0 < hi < math.inf
    for end in (lo, hi):
        assert np.all(_volumes(m.nodes + end * (1 - 1e-9) * W, m.tets) > 0)
        assert np.any(_volumes(m.nodes + end * (1 + 1e-9) * W, m.tets) <= 0)
    x = m.nodes[:, 0]
    bc = {int(i): 300.0 for i in np.flatnonzero(np.isclose(x, 0))}
    with pytest.raises(ElementInversion):
        solve_steady_heat_3d(m, thermal_conductivity=1.0, prescribed_temperature=bc,
                             motion=MeshMotion(design_velocity=W, t=_t("jax", hi * 1.01)))


@pytest.mark.parametrize("method", ["harmonic", "stiffened"])
def test_t8_extension_reproduces_linear_data(method):
    m = box_mesh(1.0, 0.7, 0.4, 5, 4, 3)
    A = np.array([[0.2, -0.1, 0.3], [0.05, 0.4, -0.2], [0.1, 0.0, 0.25]])
    linear = m.nodes @ A.T + np.array([0.1, -0.2, 0.3])
    known = np.zeros(m.num_nodes, dtype=bool)
    known[m.boundary_nodes()] = True
    out = extend_velocity(m, np.where(known[:, None], linear, np.nan), known, method=method)
    assert np.max(np.abs(out - linear)) <= 1e-12 * np.max(np.abs(linear))


# ---------------------------------------------------------------- T9 refusals, T10 unchanged

def test_t9_refusals():
    jnp = _jax().numpy
    m, W = _box()
    x = m.nodes[:, 0]
    bc = {int(i): 300.0 for i in np.flatnonzero(np.isclose(x, 0))}
    t = jnp.asarray(0.0)
    with pytest.raises(ValueError, match=r"velocity must have shape \(\d+, 3\)"):
        solve_steady_heat_3d(m, thermal_conductivity=1.0, prescribed_temperature=bc,
                             motion=MeshMotion(design_velocity=W[:, :2], t=t))
    with pytest.raises(TypeError, match="live"):
        solve_steady_heat_3d(m, thermal_conductivity=jnp.asarray(2.0), prescribed_temperature=bc,
                             motion=MeshMotion(design_velocity=W, t=t))
    with pytest.raises(TypeError, match="live"):
        solve_steady_heat_3d(m, thermal_conductivity=2.0, prescribed_temperature={0: jnp.asarray(300.0)},
                             motion=MeshMotion(design_velocity=W, t=t))
    with pytest.raises(TypeError, match="heat_source_density is a callback"):
        solve_steady_heat_3d(m, thermal_conductivity=2.0, prescribed_temperature=bc,
                             heat_source_density=lambda c: np.ones(len(c)), motion=MeshMotion(design_velocity=W, t=t))
    with pytest.raises(TypeError, match="NumPy does not differentiate"):
        solve_steady_heat_3d(m, thermal_conductivity=2.0, prescribed_temperature=bc,
                             motion=MeshMotion(design_velocity=W, t=0.0))


def test_t10_unchanged_without_motion():
    m, W = _box()

    def digest(r):
        return hashlib.sha256(b"".join(np.ascontiguousarray(np.asarray(getattr(r, f), dtype=float)).tobytes()
                                       for f in ("temperature", "heat_flux", "reaction_heat_rate"))).hexdigest()
    bc = _box_bc()
    without = solve_steady_heat_3d(m, thermal_conductivity={"a": 2.0, "b": 5.0}, prescribed_temperature=bc,
                                   heat_source_density={"a": 1.0e3, "b": 0.0})
    assert digest(_box_solve(m, W, None)) == digest(without)
    assert isinstance(without.temperature, np.ndarray)
