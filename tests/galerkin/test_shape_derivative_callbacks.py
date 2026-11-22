# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coordinate callbacks of steady 2D heat with a motion (3h follow-up (e), first slice).

E1-E7 were pre-registered on 2026-11-22 before the implementation; their tolerances are
fixed there and are not loosened here. A heat source callback(points), an inward heat flux
callback(points, normals) and convection h/ambient callbacks(points, normals) are called
again with the live points and normals of the same quadrature rules, so the derivative
includes the callbacks' own variation along the motion.
"""

from __future__ import annotations

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import MeshMotion
from galerkin.thermal import solve_steady_heat

BACKENDS = ["jax", "torch"]


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _xp(name):
    return _jax().numpy if name == "jax" else _torch()


def _leaf(name, t0=0.0):
    if name == "jax":
        return _jax().numpy.asarray(t0, dtype=_jax().numpy.float64)
    return _torch().tensor(t0, dtype=_torch().float64, requires_grad=True)


def _gradient(name, objective, t0=0.0):
    if name == "jax":
        jax = _jax()
        value, grad = jax.value_and_grad(objective)(_leaf("jax", t0))
        return float(value), float(grad)
    leaf = _leaf("torch", t0)
    value = objective(leaf)
    value.backward()
    return float(value.detach()), float(leaf.grad)


def _numpy(a):
    from galerkin.core.backend import to_numpy
    return np.asarray(to_numpy(a))


def _moved(mesh, W, h):
    return Mesh(mesh.nodes + h * W, mesh.triangles, mesh.boundary, mesh.boundary_edges, mesh.regions,
                mesh.region_names)


# callbacks written with array operations only, so they run on NumPy, JAX and PyTorch points alike

def _source(p):
    return 40.0 + 30.0 * p[:, 0] * p[:, 0] + 10.0 * p[:, 1]


def _flux(p, n):
    return 5.0 + 3.0 * p[:, 1] - 2.0 * n[:, 0] * p[:, 0]


def _h(p, n):
    return 4.0 + 2.0 * p[:, 0]


def _ambient(p, n):
    return 290.0 + 5.0 * p[:, 0] * p[:, 1]


def _plate():
    m = rectangle_mesh(1.0, 0.6, 12, 8)
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    W = np.zeros_like(m.nodes)
    W[:, 0] = 0.2 * x + 0.05 * np.sin(np.pi * x) * np.sin(np.pi * y / 0.6)
    W[:, 1] = 0.1 * y
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(thermal_conductivity=3.0, prescribed_temperature={i: 300.0 for i in left},
              heat_source_density=_source, inward_heat_flux={"right": _flux},
              convection={"top": (_h, _ambient)})
    return m, W, kw, left


def _objective(xp, m, W, kw, nodes):
    def f(t):
        r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_heat_rate_per_depth[np.asarray(nodes)]) + xp.sum(r.temperature) / len(nodes)
    return f


def _plain_objective(m, kw, nodes):
    r = solve_steady_heat(m, **kw)
    return float(np.sum(r.reaction_heat_rate_per_depth[np.asarray(nodes)]) + np.sum(r.temperature) / len(nodes))


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("t0", [0.0, 0.1])
def test_e1_numbers_equal_the_moved_mesh_solve(name, t0):
    m, W, kw, _left = _plate()
    plain = solve_steady_heat(_moved(m, W, t0), **kw)
    r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name, t0)))
    for field in ("temperature", "reaction_heat_rate_per_depth", "outward_convective_heat_rate_per_depth",
                  "heat_flux"):
        got, want = _numpy(getattr(r, field)), np.asarray(getattr(plain, field))
        scale = np.ptp(want) if field == "temperature" else np.max(np.abs(want))
        assert np.max(np.abs(got - want)) <= 1e-12 * scale, field


@pytest.mark.parametrize("name", BACKENDS)
def test_e2_derivative_matches_richardson_differences(name):
    m, W, kw, left = _plate()
    _value, slope = _gradient(name, _objective(_xp(name), m, W, kw, left))
    f = lambda h: _plain_objective(_moved(m, W, h), kw, left)              # noqa: E731
    d = lambda h: (f(h) - f(-h)) / (2 * h)                                   # noqa: E731
    fd = (4 * d(1e-3) - d(2e-3)) / 3
    assert abs(slope - fd) <= 1e-8 * max(abs(fd), 1e-300), (slope, fd)
    # and the callbacks' own variation matters: freezing them at the t = 0 points changes the slope
    assert abs(slope) > 0


def test_e3_jax_and_torch_agree():
    m, W, kw, left = _plate()
    a = _gradient("jax", _objective(_xp("jax"), m, W, kw, left))
    b = _gradient("torch", _objective(_xp("torch"), m, W, kw, left))
    for x, y in zip(a, b):
        assert abs(x - y) <= 1e-12 * max(abs(x), abs(y)), (a, b)


@pytest.mark.parametrize("name", BACKENDS)
def test_e4_analytic_heat_rate_of_a_fixed_linear_source(name):
    """1D strip 0 < x < L, insulated in y, q = Q0 x fixed in space, T(0) = T(L) = 0.

    T = Q0 (L^2 x - x^3) / (6k); the heat leaving at x = 0 is k T'(0) H = Q0 L^2 H / 6,
    so the reaction there (the heat the boundary injects) is -Q0 L^2 H / 6 and its
    derivative in L is -Q0 L H / 3. Stretching the strip, x -> x (1 + t / L), moves the
    right end at unit speed, so d/dt = d/dL.
    """
    Q0, L, H, k = 7.0, 1.3, 0.4, 2.5
    m = rectangle_mesh(L, H, 10, 3)
    W = np.zeros_like(m.nodes)
    W[:, 0] = m.nodes[:, 0] / L
    left = [int(i) for i in m.boundary["left"]]
    right = [int(i) for i in m.boundary["right"]]
    kw = dict(thermal_conductivity=k, heat_source_density=lambda p: Q0 * p[:, 0],
              prescribed_temperature={**{i: 0.0 for i in left}, **{i: 0.0 for i in right}})
    xp = _xp(name)

    def f(t):
        r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_heat_rate_per_depth[np.asarray(left)])
    value, slope = _gradient(name, f)
    assert abs(value - (-Q0 * L * L * H / 6)) <= 1e-10 * Q0 * L * L * H / 6, value
    assert abs(slope - (-Q0 * L * H / 3)) <= 1e-10 * Q0 * L * H / 3, slope


@pytest.mark.parametrize("name", BACKENDS)
def test_e5_flux_callback_on_a_moving_side(name):
    """Only a flux callback g(y) on the right side, which moves along its normal."""
    m = rectangle_mesh(1.0, 0.6, 12, 8)
    W = np.zeros_like(m.nodes)
    W[:, 0] = m.nodes[:, 0] ** 2
    W[:, 1] = 0.3 * m.nodes[:, 1] * m.nodes[:, 0]
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(thermal_conductivity=3.0, prescribed_temperature={i: 300.0 for i in left},
              inward_heat_flux={"right": lambda p, n: 20.0 + 15.0 * p[:, 1] * p[:, 1]})
    xp = _xp(name)

    def f(t):
        r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_heat_rate_per_depth[np.asarray(left)])
    _value, slope = _gradient(name, f)
    g = lambda h: float(np.sum(solve_steady_heat(_moved(m, W, h), **kw)                # noqa: E731
                               .reaction_heat_rate_per_depth[np.asarray(left)]))
    d = lambda h: (g(h) - g(-h)) / (2 * h)                                               # noqa: E731
    fd = (4 * d(1e-3) - d(2e-3)) / 3
    assert abs(slope - fd) <= 1e-8 * max(abs(fd), 1e-300), (slope, fd)


NUMPY_ONLY = [
    ("heat_source_density", dict(heat_source_density=lambda p: np.asarray(p)[:, 0] + 1.0)),
    ("inward_heat_flux", dict(inward_heat_flux={"right": lambda p, n: np.ones(len(p))})),
    ("convection h", dict(convection={"top": (lambda p, n: np.full(len(p), 3.0), 290.0)})),
    ("convection ambient", dict(convection={"top": (3.0, lambda p, n: 290.0 + 0.0 * np.asarray(p)[:, 0])})),
]


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("label,over", NUMPY_ONLY, ids=[c[0] for c in NUMPY_ONLY])
def test_e6_numpy_only_callbacks_are_refused_by_name(name, label, over):
    m, W, kw, _left = _plate()
    kw = {**kw, "heat_source_density": None, "inward_heat_flux": None, "convection": None, **over}
    kw = {k: v for k, v in kw.items() if v is not None}
    word = {"inward_heat_flux": "the heat flux on 'right'"}.get(label, label.split()[0])
    with pytest.raises(TypeError, match=rf"the callback of {word}") as caught:
        solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name)))
    assert "JAX or PyTorch" in str(caught.value)


def test_e6_callbacks_with_an_axisymmetric_motion_stay_refused():
    m, W, kw, _left = _plate()
    W = W.copy()
    W[np.isclose(m.nodes[:, 0], 0), 0] = 0.0
    with pytest.raises(TypeError, match="coordinate callbacks with an axisymmetric motion"):
        solve_steady_heat(m, **kw, coordinate_system="axisymmetric",
                          motion=MeshMotion(design_velocity=W, t=_leaf("jax")))


def test_e7_without_a_motion_nothing_changes():
    m, _W, kw, _left = _plate()
    a = solve_steady_heat(m, **kw)
    b = solve_steady_heat(m, **kw, motion=None)
    for field in ("temperature", "reaction_heat_rate_per_depth", "outward_convective_heat_rate_per_depth",
                  "heat_flux"):
        assert np.array_equal(np.asarray(getattr(a, field)), np.asarray(getattr(b, field))), field
