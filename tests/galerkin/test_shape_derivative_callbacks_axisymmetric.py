# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coordinate callbacks of axisymmetric steady heat with a motion (3h follow-up e2).

EA1-EA7 were pre-registered on 2026-11-22 before the implementation; their tolerances
are fixed there and are not loosened here. The callbacks are sampled at the live points
of the ordinary rules with the 2 pi r measure of the axisymmetric solve.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import MeshMotion
from galerkin.thermal import solve_steady_heat

from test_shape_derivative_callbacks import BACKENDS, _gradient, _leaf, _moved, _numpy, _xp  # noqa: F401

AXI = dict(coordinate_system="axisymmetric")


def _annulus(r0, r1, L, nr, nz):
    """A hollow cylinder r0 < r < r1, 0 < z < L as a (r, z) rectangle mesh."""
    m = rectangle_mesh(r1 - r0, L, nr, nz)
    nodes = m.nodes + np.array([r0, 0.0])
    return Mesh(nodes, m.triangles, m.boundary, m.boundary_edges, m.regions, m.region_names)


def _source(p):
    return 40.0 + 30.0 * p[:, 0] * p[:, 1] + 10.0 * p[:, 1]


def _flux(p, n):
    return 5.0 + 3.0 * p[:, 1] - 2.0 * n[:, 0] * p[:, 0]


def _h(p, n):
    return 4.0 + 2.0 * p[:, 0]


def _ambient(p, n):
    return 290.0 + 5.0 * p[:, 0] * p[:, 1]


def _case():
    m = _annulus(0.2, 1.0, 0.6, 12, 8)
    r, z = m.nodes[:, 0], m.nodes[:, 1]
    W = np.zeros_like(m.nodes)
    W[:, 0] = 0.2 * (r - 0.2) + 0.05 * np.sin(np.pi * (r - 0.2) / 0.8) * np.sin(np.pi * z / 0.6)
    W[:, 1] = 0.1 * z
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(thermal_conductivity=3.0, prescribed_temperature={i: 300.0 for i in left},
              heat_source_density=_source, inward_heat_flux={"right": _flux},
              convection={"top": (_h, _ambient)}, **AXI)
    return m, W, kw, left


def _objective(xp, m, W, kw, nodes):
    def f(t):
        r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_heat_rate[np.asarray(nodes)]) + xp.sum(r.temperature) / len(nodes)
    return f


def _plain(m, kw, nodes):
    r = solve_steady_heat(m, **kw)
    return float(np.sum(r.reaction_heat_rate[np.asarray(nodes)]) + np.sum(r.temperature) / len(nodes))


def _richardson(g):
    d = lambda h: (g(h) - g(-h)) / (2 * h)                                   # noqa: E731
    return (4 * d(1e-3) - d(2e-3)) / 3


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("t0", [0.0, 0.1])
def test_ea1_numbers_equal_the_moved_mesh_solve(name, t0):
    m, W, kw, _left = _case()
    plain = solve_steady_heat(_moved(m, W, t0), **kw)
    r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name, t0)))
    for field in ("temperature", "reaction_heat_rate", "outward_convective_heat_rate", "heat_flux"):
        got, want = _numpy(getattr(r, field)), np.asarray(getattr(plain, field))
        scale = np.ptp(want) if field == "temperature" else np.max(np.abs(want))
        assert np.max(np.abs(got - want)) <= 1e-12 * scale, field


@pytest.mark.parametrize("name", BACKENDS)
def test_ea2_derivative_matches_richardson_differences(name):
    m, W, kw, left = _case()
    _value, slope = _gradient(name, _objective(_xp(name), m, W, kw, left))
    fd = _richardson(lambda h: _plain(_moved(m, W, h), kw, left))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


def test_ea3_jax_and_torch_agree():
    m, W, kw, left = _case()
    a = _gradient("jax", _objective(_xp("jax"), m, W, kw, left))
    b = _gradient("torch", _objective(_xp("torch"), m, W, kw, left))
    for x, y in zip(a, b):
        assert abs(x - y) <= 1e-12 * max(abs(x), abs(y)), (a, b)


Q0, R0, R1, L = 7.0, 0.3, 1.1, 1.3


def _balance_case(kind):
    m = _annulus(R0, R1, L, 8, 10)
    r, z = m.nodes[:, 0], m.nodes[:, 1]
    W = np.zeros_like(m.nodes)
    bottom = [int(i) for i in m.boundary["bottom"]]
    if kind == "z":
        W[:, 1] = z / L
        source = lambda p: Q0 * p[:, 1]                                       # noqa: E731
        value = -Q0 * L * L * math.pi * (R1 * R1 - R0 * R0) / 2
        slope = -Q0 * L * math.pi * (R1 * R1 - R0 * R0)
    else:
        W[:, 0] = (r - R0) / (R1 - R0)
        source = lambda p: Q0 * p[:, 0]                                       # noqa: E731
        value = -2 * math.pi * Q0 * L * (R1 ** 3 - R0 ** 3) / 3
        slope = -2 * math.pi * Q0 * L * R1 * R1
    kw = dict(thermal_conductivity=2.5, heat_source_density=source,
              prescribed_temperature={i: 0.0 for i in bottom}, **AXI)
    return m, W, kw, bottom, value, slope


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("kind", ["z", "r"])
def test_ea4_analytic_heat_rate_of_a_fixed_source(name, kind):
    """Insulated except z = 0, so the reaction there is minus the total source (heat balance)."""
    m, W, kw, bottom, value, slope = _balance_case(kind)
    xp = _xp(name)

    def f(t):
        r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_heat_rate[np.asarray(bottom)])
    got, d = _gradient(name, f)
    assert abs(got - value) <= 1e-10 * abs(value), (got, value)
    assert abs(d - slope) <= 1e-10 * abs(slope), (d, slope)


@pytest.mark.parametrize("name", BACKENDS)
def test_ea5_flux_callback_on_the_moving_outer_radius(name):
    m = _annulus(0.2, 1.0, 0.6, 12, 8)
    W = np.zeros_like(m.nodes)
    W[:, 0] = (m.nodes[:, 0] - 0.2) ** 2
    W[:, 1] = 0.3 * m.nodes[:, 1] * (m.nodes[:, 0] - 0.2)
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(thermal_conductivity=3.0, prescribed_temperature={i: 300.0 for i in left},
              inward_heat_flux={"right": lambda p, n: 20.0 + 15.0 * p[:, 1] * p[:, 1]}, **AXI)
    xp = _xp(name)

    def f(t):
        r = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        return xp.sum(r.reaction_heat_rate[np.asarray(left)])
    _value, slope = _gradient(name, f)
    fd = _richardson(lambda h: float(np.sum(solve_steady_heat(_moved(m, W, h), **kw)
                                            .reaction_heat_rate[np.asarray(left)])))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


@pytest.mark.parametrize("name", BACKENDS)
def test_ea6_numpy_only_callbacks_are_refused_by_name(name):
    m, W, kw, _left = _case()
    kw = {**kw, "heat_source_density": lambda p: np.asarray(p)[:, 0] + 1.0}
    # JAX values come back as NumPy numbers; a PyTorch leaf refuses .numpy() and the callback raises
    with pytest.raises(TypeError, match="the callback of heat_source_density") as caught:
        solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name)))
    assert "JAX or PyTorch" in str(caught.value)


def test_ea6_flux_on_the_axis_keeps_the_solver_refusal():
    m = rectangle_mesh(1.0, 0.6, 6, 4)                     # the left side is the axis r = 0
    W = np.zeros_like(m.nodes)
    W[:, 1] = 0.1 * m.nodes[:, 1]
    right = [int(i) for i in m.boundary["right"]]
    with pytest.raises(ValueError, match="on the symmetry axis is not permitted"):
        solve_steady_heat(m, thermal_conductivity=3.0, prescribed_temperature={i: 300.0 for i in right},
                          inward_heat_flux={"left": lambda p, n: 1.0 + 0.0 * p[:, 0]}, **AXI,
                          motion=MeshMotion(design_velocity=W, t=_leaf("jax")))


def test_ea7_without_a_motion_nothing_changes():
    m, _W, kw, _left = _case()
    a = solve_steady_heat(m, **kw)
    b = solve_steady_heat(m, **kw, motion=None)
    for field in ("temperature", "reaction_heat_rate", "outward_convective_heat_rate", "heat_flux"):
        assert np.array_equal(np.asarray(getattr(a, field)), np.asarray(getattr(b, field))), field
