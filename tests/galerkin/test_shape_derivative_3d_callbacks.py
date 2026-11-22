# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The heat source callback of 3D steady heat with a motion (3h follow-up e6).

E3D1-E3D6 were pre-registered on 2026-11-22 before the implementation; their tolerances
are fixed there and are not loosened here. The callback of the (T, 3) tetrahedron
centroids is called again at the live centroids (the ordinary solve's centroid rule).
"""

from __future__ import annotations

import numpy as np
import pytest

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.shape import MeshMotion
from galerkin.thermal3d import solve_steady_heat_3d

from test_shape_derivative_callbacks import BACKENDS, _gradient, _leaf, _numpy, _xp  # noqa: F401

FIELDS = ("temperature", "heat_flux", "generated_heat_rate", "reaction_heat_rate", "residual_heat_rate",
          "heat_source_density")


def _moved(mesh, W, h):
    return Mesh3D(mesh.nodes + h * W, mesh.tets.copy(), mesh.tagged_faces, mesh.regions.copy(), mesh.region_names)


def _source(c):
    return 1e4 * (1.0 + c[:, 0] * c[:, 1] + 2.0 * c[:, 2] * c[:, 2])


def _x0(m):
    return [int(i) for i in np.flatnonzero(np.isclose(m.nodes[:, 0], 0))]


def _case():
    m = box_mesh(1.0, 0.5, 0.4, 6, 3, 3)
    x, y, z = m.nodes.T
    W = np.stack([0.2 * x + 0.05 * np.sin(np.pi * x) * np.sin(2 * np.pi * y) * np.sin(2.5 * np.pi * z),
                  0.1 * y * x, 0.05 * z], axis=1)
    kw = dict(thermal_conductivity=2.0, prescribed_temperature={i: 300.0 for i in _x0(m)},
              heat_source_density=_source)
    return m, W, kw


def _objective(xp, m, W, kw):
    def f(t):
        r = solve_steady_heat_3d(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_heat_rate) + xp.sum(r.temperature) / m.num_nodes
    return f


def _plain(m, kw):
    r = solve_steady_heat_3d(m, **kw)
    return float(np.sum(r.reaction_heat_rate) + np.sum(r.temperature) / m.num_nodes)


def _richardson(g):
    d = lambda h: (g(h) - g(-h)) / (2 * h)                                   # noqa: E731
    return (4 * d(1e-3) - d(2e-3)) / 3


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("t0", [0.0, 0.1])
def test_e3d1_numbers_equal_the_moved_mesh_solve(name, t0):
    m, W, kw = _case()
    plain = solve_steady_heat_3d(_moved(m, W, t0), **kw)
    r = solve_steady_heat_3d(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name, t0)))
    for field in FIELDS:
        got, want = _numpy(getattr(r, field)), np.asarray(getattr(plain, field))
        scale = np.ptp(want) if field == "temperature" else np.max(np.abs(want))
        assert np.max(np.abs(got - want)) <= 1e-12 * scale, field


@pytest.mark.parametrize("name", BACKENDS)
def test_e3d2_derivative_matches_richardson_differences(name):
    m, W, kw = _case()
    _value, slope = _gradient(name, _objective(_xp(name), m, W, kw))
    fd = _richardson(lambda h: _plain(_moved(m, W, h), kw))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


def test_e3d3_jax_and_torch_agree():
    m, W, kw = _case()
    a = _gradient("jax", _objective(_xp("jax"), m, W, kw))
    b = _gradient("torch", _objective(_xp("torch"), m, W, kw))
    for x, y in zip(a, b):
        assert abs(x - y) <= 1e-12 * max(abs(x), abs(y)), (a, b)


Q0, L, B, C = 7e3, 1.3, 0.5, 0.4


@pytest.mark.parametrize("name", BACKENDS)
def test_e3d4_analytic_heat_rate_of_a_fixed_linear_source(name):
    m = box_mesh(L, B, C, 5, 2, 2)
    W = np.zeros_like(m.nodes)
    W[:, 0] = m.nodes[:, 0] / L
    kw = dict(thermal_conductivity=2.0, prescribed_temperature={i: 0.0 for i in _x0(m)},
              heat_source_density=lambda c: Q0 * c[:, 0])
    xp = _xp(name)
    for field, sign in (("generated_heat_rate", 1.0), ("reaction_heat_rate", -1.0)):
        def f(t):
            return xp.sum(getattr(solve_steady_heat_3d(m, **kw, motion=MeshMotion(design_velocity=W, t=t)), field))
        value, slope = _gradient(name, f)
        assert abs(value - sign * Q0 * L * L * B * C / 2) <= 1e-10 * Q0 * L * L * B * C / 2, (field, value)
        assert abs(slope - sign * Q0 * L * B * C) <= 1e-10 * Q0 * L * B * C, (field, slope)


@pytest.mark.parametrize("name", BACKENDS)
def test_e3d5_numpy_only_callback_is_refused_by_name(name):
    m, W, kw = _case()
    kw = {**kw, "heat_source_density": lambda c: np.asarray(c)[:, 0] + 1.0}
    with pytest.raises(TypeError, match="the callback of heat_source_density") as caught:
        solve_steady_heat_3d(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name)))
    assert "JAX or PyTorch" in str(caught.value)


def test_e3d6_without_a_motion_nothing_changes():
    m, _W, kw = _case()
    a = solve_steady_heat_3d(m, **kw)
    b = solve_steady_heat_3d(m, **kw, motion=None)
    for field in FIELDS:
        assert np.array_equal(np.asarray(getattr(a, field)), np.asarray(getattr(b, field))), field
