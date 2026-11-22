# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Body force and traction callbacks of linear elasticity with a motion (3h follow-up e5).

EL1-EL7 were pre-registered on 2026-11-22 before the implementation; their tolerances
are fixed there and are not loosened here. A body force callback(points) -> (Q, 2) and a
traction callback(points, outward_normals) -> (Q, 2) are called again at the live
points of the ordinary rules (6 x 6 Duffy, 4-point Gauss on edges).
"""

from __future__ import annotations

import numpy as np
import pytest
from array_api_compat import array_namespace

from galerkin.elasticity import solve_elasticity
from galerkin.mesh import rectangle_mesh
from galerkin.shape import MeshMotion

from test_shape_derivative_callbacks import BACKENDS, _gradient, _leaf, _moved, _numpy, _xp  # noqa: F401

FIELDS = ("displacement", "strain", "stress", "applied_force_per_depth", "reaction_force_per_depth",
          "residual_force_per_depth")
COMMON = dict(youngs_modulus=70e9, poisson_ratio=0.33, plane="stress")


def _clamped_left(m):
    return {(int(i), c): 0.0 for i in m.boundary["left"] for c in (0, 1)}


# callbacks written with array API operations, so they run on NumPy, JAX and PyTorch points alike

def _vector(p, a, b):
    xp = array_namespace(p)
    return xp.stack([a, b], axis=1)


def _body(p):
    x, y = p[:, 0], p[:, 1]
    return _vector(p, 1e6 * x * y + 2e5 * y, 1e6 * x * y + 2e5 * x)


def _traction(p, n):
    return -3e6 * (1.0 + p[:, 1:]) * n + 1e6 * p[:, :1]


def _case():
    m = rectangle_mesh(1.0, 0.4, 12, 5)
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    W = np.stack([0.2 * x + 0.05 * np.sin(np.pi * x) * np.sin(np.pi * y / 0.4), 0.1 * y * x], axis=1)
    kw = dict(COMMON, prescribed_displacement=_clamped_left(m), body_force_density=_body,
              traction={"right": _traction, "top": _traction})
    return m, W, kw


def _probe(m):
    return int(np.argmin((m.nodes[:, 0] - 1.0) ** 2 + (m.nodes[:, 1] - 0.4) ** 2))


def _objective(xp, m, W, kw):
    probe = _probe(m)

    def f(t):
        r = solve_elasticity(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return 1e3 * r.displacement[probe, 1] + 1e-6 * xp.sum(r.reaction_force_per_depth[:, 0])
    return f


def _plain(m, kw):
    r = solve_elasticity(m, **kw)
    return float(1e3 * r.displacement[_probe(m), 1] + 1e-6 * np.sum(r.reaction_force_per_depth[:, 0]))


def _richardson(g):
    d = lambda h: (g(h) - g(-h)) / (2 * h)                                   # noqa: E731
    return (4 * d(1e-3) - d(2e-3)) / 3


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("t0", [0.0, 0.1])
def test_el1_numbers_equal_the_moved_mesh_solve(name, t0):
    m, W, kw = _case()
    plain = solve_elasticity(_moved(m, W, t0), **kw)
    r = solve_elasticity(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name, t0)))
    for field in FIELDS:
        got, want = _numpy(getattr(r, field)), np.asarray(getattr(plain, field))
        assert np.max(np.abs(got - want)) <= 1e-12 * np.max(np.abs(want)), field


@pytest.mark.parametrize("name", BACKENDS)
def test_el2_derivative_matches_richardson_differences(name):
    m, W, kw = _case()
    _value, slope = _gradient(name, _objective(_xp(name), m, W, kw))
    fd = _richardson(lambda h: _plain(_moved(m, W, h), kw))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


def test_el3_jax_and_torch_agree():
    m, W, kw = _case()
    a = _gradient("jax", _objective(_xp("jax"), m, W, kw))
    b = _gradient("torch", _objective(_xp("torch"), m, W, kw))
    for x, y in zip(a, b):
        assert abs(x - y) <= 1e-12 * max(abs(x), abs(y)), (a, b)


F0, T0, L, H = 2e6, 3e6, 1.3, 0.5


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("kind", ["body", "traction"])
def test_el4_analytic_applied_force(name, kind):
    m = rectangle_mesh(L, H, 10, 4)
    W = np.zeros_like(m.nodes)
    kw = dict(COMMON, prescribed_displacement=_clamped_left(m))
    if kind == "body":
        W[:, 0] = m.nodes[:, 0] / L
        kw["body_force_density"] = lambda p: _vector(p, F0 * p[:, 0], 0.0 * p[:, 0])
        component, value, slope = 0, F0 * L * L * H / 2, F0 * L * H
    else:
        W[:, 1] = m.nodes[:, 1] / H
        kw["traction"] = {"right": lambda p, n: _vector(p, 0.0 * p[:, 1], T0 * p[:, 1])}
        component, value, slope = 1, T0 * H * H / 2, T0 * H
    xp = _xp(name)

    def f(t):
        r = solve_elasticity(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.applied_force_per_depth[:, component])
    got, d = _gradient(name, f)
    assert abs(got - value) <= 1e-10 * value, (got, value)
    assert abs(d - slope) <= 1e-10 * slope, (d, slope)


@pytest.mark.parametrize("name", BACKENDS)
def test_el5_pressure_on_a_tilting_side(name):
    m = rectangle_mesh(1.0, 0.4, 12, 5)
    W = np.zeros_like(m.nodes)
    W[:, 0] = m.nodes[:, 0] * m.nodes[:, 1]                 # the right side tilts
    kw = dict(COMMON, prescribed_displacement=_clamped_left(m),
              traction={"right": lambda p, n: -4e6 * (1.0 + 2.0 * p[:, 1:]) * n})
    _value, slope = _gradient(name, _objective(_xp(name), m, W, kw))
    fd = _richardson(lambda h: _plain(_moved(m, W, h), kw))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


NUMPY_ONLY = [
    ("body_force_density", dict(body_force_density=lambda p: np.ones((len(p), 2)))),
    (r"traction\['right'\]", dict(traction={"right": lambda p, n: np.asarray(n) * 1e6})),
]


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("label,over", NUMPY_ONLY, ids=["body", "traction"])
def test_el6_numpy_only_callbacks_are_refused_by_name(name, label, over):
    m, W, _kw = _case()
    kw = dict(COMMON, prescribed_displacement=_clamped_left(m), **over)
    with pytest.raises(TypeError, match=f"the callback of {label}") as caught:
        solve_elasticity(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name)))
    assert "JAX or PyTorch" in str(caught.value)


def test_el7_without_a_motion_nothing_changes():
    m, _W, kw = _case()
    a = solve_elasticity(m, **kw)
    b = solve_elasticity(m, **kw, motion=None)
    for field in FIELDS:
        assert np.array_equal(np.asarray(getattr(a, field)), np.asarray(getattr(b, field))), field
