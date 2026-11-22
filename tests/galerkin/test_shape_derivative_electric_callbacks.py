# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Current-density callbacks of steady electric conduction with a motion (3h follow-up e4).

EE1-EE7 were pre-registered on 2026-11-22 before the implementation; their tolerances
are fixed there and are not loosened here. An inward current density
callback(position, outward_normal) is called again at the live points and normals of
the ordinary 4-point Gauss edge rule.
"""

from __future__ import annotations

import numpy as np
import pytest

from galerkin.electric import solve_steady_electric
from galerkin.mesh import rectangle_mesh
from galerkin.shape import MeshMotion

from test_shape_derivative_callbacks import BACKENDS, _gradient, _leaf, _moved, _numpy, _xp  # noqa: F401

FIELDS = ("electric_potential", "electric_field", "current_density", "joule_power_density",
          "generated_heat_rate_per_depth", "joule_power_per_depth", "reaction_current_per_depth",
          "outward_prescribed_current_per_depth", "residual_current_per_depth", "inward_electric_power_per_depth")


def _current(p, n):
    return 2.0e3 * (1.0 + 2.0 * p[:, 1] - 0.5 * n[:, 0] * p[:, 0])


def _case():
    m = rectangle_mesh(1.0, 0.5, 12, 6)
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    W = np.stack([0.2 * x + 0.05 * np.sin(np.pi * x) * np.sin(np.pi * y / 0.5), 0.1 * y * x], axis=1)
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(electrical_conductivity=5.0e3, prescribed_electric_potential={i: 0.0 for i in left},
              inward_current_density={"right": _current})
    return m, W, kw


def _power(xp, m, W, kw):
    def f(t):
        return solve_steady_electric(m, **kw, motion=MeshMotion(design_velocity=W, t=t)).joule_power_per_depth
    return f


def _richardson(g):
    d = lambda h: (g(h) - g(-h)) / (2 * h)                                   # noqa: E731
    return (4 * d(1e-3) - d(2e-3)) / 3


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("t0", [0.0, 0.1])
def test_ee1_numbers_equal_the_moved_mesh_solve(name, t0):
    m, W, kw = _case()
    plain = solve_steady_electric(_moved(m, W, t0), **kw)
    r = solve_steady_electric(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name, t0)))
    for field in FIELDS:
        got, want = _numpy(getattr(r, field)), np.asarray(getattr(plain, field))
        scale = np.ptp(want) if field == "electric_potential" else max(np.max(np.abs(want)), np.finfo(float).tiny)
        assert np.max(np.abs(got - want)) <= 1e-12 * scale, field


@pytest.mark.parametrize("name", BACKENDS)
def test_ee2_power_derivative_matches_richardson(name):
    m, W, kw = _case()
    _value, slope = _gradient(name, _power(_xp(name), m, W, kw))
    fd = _richardson(lambda h: float(solve_steady_electric(_moved(m, W, h), **kw).joule_power_per_depth))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


def test_ee3_jax_and_torch_agree():
    m, W, kw = _case()
    a = _gradient("jax", _power(_xp("jax"), m, W, kw))
    b = _gradient("torch", _power(_xp("torch"), m, W, kw))
    for x, y in zip(a, b):
        assert abs(x - y) <= 1e-12 * max(abs(x), abs(y)), (a, b)


J0, L, H = 3.0e3, 1.3, 0.5


@pytest.mark.parametrize("name", BACKENDS)
def test_ee4_analytic_reaction_of_a_fixed_current_on_a_growing_side(name):
    m = rectangle_mesh(L, H, 10, 4)
    W = np.zeros_like(m.nodes)
    W[:, 1] = m.nodes[:, 1] / H
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(electrical_conductivity=5.0e3, prescribed_electric_potential={i: 0.0 for i in left},
              inward_current_density={"right": lambda p, n: J0 * p[:, 1]})
    xp = _xp(name)

    def f(t):
        r = solve_steady_electric(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_current_per_depth)
    value, slope = _gradient(name, f)
    assert abs(value + J0 * H * H / 2) <= 1e-10 * J0 * H * H / 2, value
    assert abs(slope + J0 * H) <= 1e-10 * J0 * H, slope


@pytest.mark.parametrize("name", BACKENDS)
def test_ee5_normal_dependent_current_on_a_tilting_side(name):
    m = rectangle_mesh(1.0, 0.5, 12, 6)
    W = np.zeros_like(m.nodes)
    W[:, 0] = m.nodes[:, 0] * m.nodes[:, 1]                 # the right side tilts
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(electrical_conductivity=5.0e3, prescribed_electric_potential={i: 0.0 for i in left},
              inward_current_density={"right": lambda p, n: 2.0e3 * (1.0 + n[:, 1] + p[:, 1])})
    _value, slope = _gradient(name, _power(_xp(name), m, W, kw))
    fd = _richardson(lambda h: float(solve_steady_electric(_moved(m, W, h), **kw).joule_power_per_depth))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


@pytest.mark.parametrize("name", BACKENDS)
def test_ee6_numpy_only_callback_is_refused_by_name(name):
    m, W, kw = _case()
    kw = {**kw, "inward_current_density": {"right": lambda p, n: np.full(len(p), 1.0e3)}}
    with pytest.raises(TypeError, match="the callback of the current density on 'right'") as caught:
        solve_steady_electric(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name)))
    assert "JAX or PyTorch" in str(caught.value)


def test_ee6_callback_current_without_prescribed_volts_is_refused():
    m = rectangle_mesh(1.0, 0.5, 6, 3)
    W = np.zeros_like(m.nodes)
    W[:, 1] = 0.1 * m.nodes[:, 1]
    kw = dict(electrical_conductivity=5.0e3, prescribed_electric_potential={},
              reference_electric_potential={0: 0.0},
              inward_current_density={"right": lambda p, n: 1.0e3 + 0.0 * p[:, 0],
                                      "left": lambda p, n: -1.0e3 + 0.0 * p[:, 0]})
    with pytest.raises(TypeError, match="is a callback on component 0, which has no prescribed_electric_potential"):
        solve_steady_electric(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf("jax")))


def test_ee7_without_a_motion_nothing_changes():
    m, _W, kw = _case()
    a = solve_steady_electric(m, **kw)
    b = solve_steady_electric(m, **kw, motion=None)
    for field in FIELDS:
        assert np.array_equal(np.asarray(getattr(a, field)), np.asarray(getattr(b, field))), field
