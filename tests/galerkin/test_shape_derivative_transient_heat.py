# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of transient heat (galerkin.shape, fifth slice).

H1-H8 are the checks pre-registered before the implementation (HQ record,
2026-11-10); their tolerances, and H3's mesh and step counts, are fixed there and
are not loosened here.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import ElementInversion, MeshMotion, admissible_interval
from galerkin.thermal import solve_steady_heat
from galerkin.transient_heat import solve_transient_heat

BACKENDS = ["jax", "torch"]


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _xp(name):
    return _jax().numpy if name == "jax" else _torch()


def _gradient(name, objective, t0=0.0):
    if name == "jax":
        jax = _jax()
        value, grad = jax.value_and_grad(objective)(jax.numpy.asarray(t0, dtype=jax.numpy.float64))
        return float(value), float(grad)
    torch = _torch()
    leaf = torch.tensor(t0, dtype=torch.float64, requires_grad=True)
    value = objective(leaf)
    value.backward()
    return float(value.detach()), float(leaf.grad)


def _moved(mesh, W, h):
    return Mesh(mesh.nodes + h * W, mesh.triangles, mesh.boundary, mesh.boundary_edges, mesh.regions,
                mesh.region_names)


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


# ---------------------------------------------------------------- problem

def _plate():
    """Two materials, a heated core, a time-dependent Dirichlet side, flux and convection on moving sides."""
    m = rectangle_mesh(1.0, 0.4, 12, 6)
    cent = m.nodes[m.triangles].mean(axis=1)
    regions = ((cent[:, 0] - 0.55) ** 2 + (cent[:, 1] - 0.2) ** 2 < 0.02).astype(int)
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, regions, ["host", "core"])
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    bump = np.sin(math.pi * x) * np.sin(math.pi * y / 0.4)
    W = np.stack([0.2 * bump + 0.1 * x * y / 0.4, 0.15 * bump * (x - 0.5) + 0.05 * x * y / 0.4], axis=1)
    return m, W


def _plate_inputs(m):
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    left = [int(i) for i in m.boundary["left"]]
    T0 = 300.0 + 20.0 * np.sin(3 * x) * np.cos(2 * y)
    T0[left] = 300.0
    return dict(conductivity={"host": 1.5, "core": 0.3}, volumetric_heat_capacity={"host": 2e3, "core": 4e3},
                time_s=np.linspace(0.0, 200.0, 11), initial_temperature_k=T0,
                dirichlet={i: (lambda time: 300.0 + 0.05 * time) for i in left},
                heat_source={"host": 0.0, "core": 800.0},
                outward_flux={"top": (lambda time: -30.0 - 0.1 * time)}, convection={"right": (12.0, 290.0)})


def _plate_solve(m, W, t, inputs_mesh=None):
    """``inputs_mesh``: the mesh whose nodes define the initial field (nodal values move with the nodes)."""
    return solve_transient_heat(m, motion=None if t is None else MeshMotion(W, t),
                                **_plate_inputs(m if inputs_mesh is None else inputs_mesh))


def _functionals(m, r, xp):
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    probe = int(np.argmin((x - 0.7) ** 2 + (y - 0.25) ** 2))
    weights = xp.asarray(np.linspace(0.1, 1.0, 11))[:, None]
    return {"probe": lambda: r.temperature_k[-1, probe],
            "reaction": lambda: xp.sum(r.reaction_w_per_m[-1]),
            "content": lambda: r.heat_content_j_per_m[-1],
            "history": lambda: xp.sum(r.temperature_k * weights)}


# ---------------------------------------------------------------- H1 discrete consistency

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("functional", ["probe", "reaction", "content", "history"])
def test_h1_matches_moved_mesh_central_difference(name, functional):
    xp = _xp(name)
    m, W = _plate()
    value, grad = _gradient(name, lambda t: _functionals(m, _plate_solve(m, W, t), xp)[functional]())
    h = 1e-4
    fd = (float(_functionals(m, _plate_solve(_moved(m, W, h), W, None, m), np)[functional]())
          - float(_functionals(m, _plate_solve(_moved(m, W, -h), W, None, m), np)[functional]())) / (2 * h)
    assert value == pytest.approx(float(_functionals(m, _plate_solve(m, W, None), np)[functional]()), rel=1e-12)
    assert rel(grad, fd) <= 1e-6, (grad, fd)


# ---------------------------------------------------------------- H2 uniform solution

@pytest.mark.parametrize("name", BACKENDS)
def test_h2_uniform_heat_content(name):
    xp = _xp(name)
    m, W = _plate()
    c, Q, T0 = 2.5e3, 400.0, 310.0
    times = np.linspace(0.0, 50.0, 6)

    def content(t, index):
        r = solve_transient_heat(m, conductivity=1.2, volumetric_heat_capacity=c, time_s=times,
                                 initial_temperature_k=np.full(m.num_nodes, T0), dirichlet={}, heat_source=Q,
                                 motion=MeshMotion(W, t))
        return r.heat_content_j_per_m[index]

    p, w = m.nodes[m.triangles], W[m.triangles]
    e1, e2, d1, d2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], w[:, 1] - w[:, 0], w[:, 2] - w[:, 0]
    d_area = 0.5 * np.sum(d1[:, 0] * e2[:, 1] + e1[:, 0] * d2[:, 1] - d1[:, 1] * e2[:, 0] - e1[:, 1] * d2[:, 0])
    for index in (0, 3, 5):
        _v, grad = _gradient(name, lambda t: content(t, index))
        assert rel(grad, (c * T0 + Q * times[index]) * d_area) <= 1e-10, (index, grad)


# ---------------------------------------------------------------- H3 decaying sine, bar length

@pytest.mark.parametrize("name", BACKENDS)
def test_h3_decaying_sine_bar_length(name):
    xp = _xp(name)
    L, H, kappa, tf = 1.0, 0.1, 1.0, 0.05
    exact = 1.0 * H * (2 / math.pi) * math.exp(-kappa * math.pi ** 2 * tf / L ** 2) \
        * (1 + 2 * kappa * math.pi ** 2 * tf / L ** 2)
    errors, levels = [], ((10, 10), (20, 40), (40, 160))                          # pre-registered (nx, steps)
    for nx, steps in levels:
        m = rectangle_mesh(L, H, nx, 2)
        x = m.nodes[:, 0]
        ends = [int(i) for side in ("left", "right") for i in m.boundary[side]]
        W = np.stack([x / L, np.zeros(m.num_nodes)], axis=1)
        T0 = np.sin(math.pi * x / L)
        T0[ends] = 0.0

        def content(t):
            r = solve_transient_heat(m, conductivity=kappa, volumetric_heat_capacity=1.0,
                                     time_s=np.linspace(0.0, tf, steps + 1), initial_temperature_k=T0,
                                     dirichlet={i: 0.0 for i in ends}, motion=MeshMotion(W, t))
            return r.heat_content_j_per_m[-1]

        _v, grad = _gradient(name, content)
        errors.append(rel(grad, exact))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(2.0) for i in range(2)]
    assert min(orders) >= 1.0, (errors, orders)
    assert errors[-1] <= 1e-2, errors


# ---------------------------------------------------------------- H4 steady limit

@pytest.mark.parametrize("name", BACKENDS)
def test_h4_steady_limit(name):
    xp = _xp(name)
    m, W = _plate()
    left = [int(i) for i in m.boundary["left"]]
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    probe = int(np.argmin((x - 0.7) ** 2 + (y - 0.25) ** 2))
    common = dict(conductivity={"host": 1.5, "core": 0.3}, dirichlet={i: 300.0 for i in left},
                  heat_source={"host": 0.0, "core": 800.0}, outward_flux={"top": -30.0},
                  convection={"right": (12.0, 290.0)})

    def transient(t):
        r = solve_transient_heat(m, volumetric_heat_capacity={"host": 2e3, "core": 4e3},
                                 time_s=np.array([0.0, 1e9, 2e9, 3e9]),
                                 initial_temperature_k=np.full(m.num_nodes, 300.0), motion=MeshMotion(W, t),
                                 **common)
        return r.temperature_k[-1, probe]

    def steady(t):
        return solve_steady_heat(m, motion=MeshMotion(W, t), **common).temperature[probe]

    _v, d_transient = _gradient(name, transient)
    _v, d_steady = _gradient(name, steady)
    assert rel(d_transient, d_steady) <= 1e-8, (d_transient, d_steady)


# ---------------------------------------------------------------- H5 rigid translation

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("functional", ["content", "temperature_sum"])
def test_h5_rigid_translation(name, functional):
    xp = _xp(name)
    m, _W = _plate()
    W = np.tile([0.7, -0.4], (m.num_nodes, 1))

    def objective(t):
        r = _plate_solve(m, W, t)
        return r.heat_content_j_per_m[-1] if functional == "content" else xp.sum(r.temperature_k)

    value, grad = _gradient(name, objective)
    assert abs(grad) <= 1e-12 * abs(value)


# ---------------------------------------------------------------- H6 heat balance

@pytest.mark.parametrize("name", BACKENDS)
def test_h6_heat_balance_along_the_motion(name):
    xp = _xp(name)
    m, W = _plate()

    def reaction(t):
        return xp.sum(_plate_solve(m, W, t).reaction_w_per_m[-1])

    def balance(t):
        r = _plate_solve(m, W, t)
        return xp.sum(r.storage_rate_w_per_m[-1] - r.source_load_w_per_m[-1] + r.prescribed_outward_load_w_per_m[-1]
                      + r.convective_outward_w_per_m[-1])

    _v, d_reaction = _gradient(name, reaction)
    _v, d_balance = _gradient(name, balance)
    assert rel(d_reaction, d_balance) <= 1e-10, (d_reaction, d_balance)


# ---------------------------------------------------------------- H7 unchanged without motion

def _digest(r):
    fields = ("temperature_k", "heat_flux_w_m2", "source_load_w_per_m", "reaction_w_per_m", "residual_w_per_m",
              "storage_rate_w_per_m", "heat_content_j_per_m", "quadratic_functional_jk_per_m",
              "prescribed_outward_load_w_per_m", "convective_outward_w_per_m")
    return hashlib.sha256(b"".join(np.ascontiguousarray(getattr(r, f), dtype=float).tobytes()
                                   for f in fields)).hexdigest()


def test_h7_unchanged_without_motion():
    # main 3afaaa6 and this branch give the same sha256 for this problem (measured 2026-11-10; HQ record)
    m, W = _plate()
    assert _digest(_plate_solve(m, W, None)) == _digest(solve_transient_heat(m, **_plate_inputs(m)))


# ---------------------------------------------------------------- H8 refusals

def test_h8_refusals():
    xp = _xp("jax")
    m, W = _plate()
    t = xp.asarray(0.0)
    base = _plate_inputs(m)

    def call(**over):
        kw = {**base, **over}
        return solve_transient_heat(m, motion=MeshMotion(W, kw.pop("t", t)), **kw)

    with pytest.raises(TypeError, match="NumPy does not differentiate"):
        call(t=0.0)
    with pytest.raises(TypeError, match="heat_source is a callback; with a moving mesh its sample points move"):
        call(heat_source=lambda points, time: np.zeros(len(points)))
    with pytest.raises(TypeError, match=r"outward_flux\['top'\] is a callback of coordinates"):
        call(outward_flux={"top": lambda points, normals: np.zeros(len(points))})
    with pytest.raises(TypeError, match=r"convection\['right'\] is a callback of coordinates"):
        call(convection={"right": (lambda points, normals, time: np.ones(len(points)), 290.0)})
    with pytest.raises(TypeError, match="Dirichlet temperature is a callback of coordinates"):
        call(dirichlet={0: lambda a, b: 300.0})
    with pytest.raises(TypeError, match="conductivity is live"):
        call(conductivity=xp.asarray(1.5))
    with pytest.raises(TypeError, match="volumetric_heat_capacity is live"):
        call(volumetric_heat_capacity={"host": xp.asarray(2e3), "core": 4e3})
    with pytest.raises(TypeError, match="initial_temperature_k is live"):
        call(initial_temperature_k=xp.asarray(base["initial_temperature_k"]))
    with pytest.raises(TypeError, match="Dirichlet temperature is live"):
        call(dirichlet={0: xp.asarray(300.0)})
    with pytest.raises(TypeError, match=r"convection\['right'\] is live"):
        call(convection={"right": (xp.asarray(12.0), 290.0)})
    with pytest.raises(TypeError, match="callbacks of time must return NumPy numbers"):
        call(dirichlet={int(m.boundary["left"][0]): (lambda time: xp.asarray(300.0))})
    with pytest.raises(ValueError, match="axisymmetric is refused"):
        call(coordinate_system="axisymmetric")
    with pytest.raises(ValueError, match="checkpoint_every is not supported with a motion"):
        call(checkpoint_every=2)
    with pytest.raises(ValueError, match="conductivity is a callback; with a motion it must be"):
        call(conductivity=lambda: 1.5)
    _lo, hi = admissible_interval(m, W)
    with pytest.raises(ElementInversion):
        call(t=xp.asarray(hi * 1.01))


def test_h8_jax_without_x64_is_named():
    jax = _jax()
    m, W = _plate()
    jax.config.update("jax_enable_x64", False)
    try:
        with pytest.raises(ValueError, match="galerkin needs float64"):
            _plate_solve(m, W, jax.numpy.asarray(0.0))
    finally:
        jax.config.update("jax_enable_x64", True)
