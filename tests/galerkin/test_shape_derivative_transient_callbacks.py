# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Coordinate callbacks of transient heat with a motion (3h follow-up e3).

ET1-ET7 were pre-registered on 2026-11-22 before the implementation; their tolerances
are fixed there and are not loosened here. The source callback(position, time) and the
field boundary callbacks(position, outward_normal, time) are called again at the end of
every step at the live points of the same rules; static callbacks(position,
outward_normal) once.
"""

from __future__ import annotations

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import MeshMotion
from galerkin.transient_heat import solve_transient_heat

from test_shape_derivative_callbacks import BACKENDS, _gradient, _leaf, _moved, _numpy, _xp  # noqa: F401

TIME = np.linspace(0.0, 200.0, 6)


def _source(p, time):
    return 400.0 + 300.0 * p[:, 0] * p[:, 1] + 2.0 * time * p[:, 0]


def _flux(p, n):
    return 30.0 + 20.0 * p[:, 1] - 10.0 * n[:, 0] * p[:, 0]


def _h(p, n, time):
    return 8.0 + 4.0 * p[:, 0] + 0.01 * time


def _ambient(p, n, time):
    return 290.0 + 5.0 * p[:, 0] * p[:, 1] + 0.02 * time


def _mesh(axisymmetric):
    m = rectangle_mesh(1.0, 0.4, 12, 6)
    if axisymmetric:                          # a hollow cylinder 0.2 < r < 1.2
        m = Mesh(m.nodes + np.array([0.2, 0.0]), m.triangles, m.boundary, m.boundary_edges, m.regions,
                 m.region_names)
    return m


def _case(axisymmetric=False):
    m = _mesh(axisymmetric)
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    s = x - x.min()
    W = np.stack([0.2 * s + 0.05 * np.sin(np.pi * s) * np.sin(np.pi * y / 0.4), 0.1 * y], axis=1)
    left = [int(i) for i in m.boundary["left"]]
    T0 = 300.0 + 20.0 * np.sin(3 * x) * np.cos(2 * y)
    T0[left] = 300.0
    kw = dict(thermal_conductivity=1.5, volumetric_heat_capacity=2e3, time=TIME, initial_temperature=T0,
              prescribed_temperature={i: 300.0 for i in left}, heat_source_density=_source,
              inward_heat_flux={"top": _flux}, convection={"right": (_h, _ambient)})
    if axisymmetric:
        kw["coordinate_system"] = "axisymmetric"
    return m, W, kw, left


def _rates(r):
    """The result's rate fields under their planar or axisymmetric names."""
    suffix = "" if r.coordinate_system == "axisymmetric" else "_per_depth"
    names = ("reaction_heat_rate", "heat_storage_rate", "generated_heat_rate", "outward_prescribed_heat_rate",
             "outward_convective_heat_rate", "stored_heat")
    return {name: getattr(r, name + suffix) for name in names}


def _objective(xp, m, W, kw, left):
    def f(t):
        r = solve_transient_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
        rates = _rates(r)
        return (xp.sum(rates["reaction_heat_rate"][-1][np.asarray(left)]) + xp.sum(r.temperature[-1]) / len(left)
                + rates["stored_heat"][-1] * 1e-6)
    return f


def _plain(m, kw, left):
    r = solve_transient_heat(m, **kw)
    rates = _rates(r)
    return float(np.sum(rates["reaction_heat_rate"][-1][np.asarray(left)]) + np.sum(r.temperature[-1]) / len(left)
                 + rates["stored_heat"][-1] * 1e-6)


def _richardson(g):
    d = lambda h: (g(h) - g(-h)) / (2 * h)                                   # noqa: E731
    return (4 * d(1e-3) - d(2e-3)) / 3


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("t0,axisymmetric", [(0.0, False), (0.1, False), (0.1, True)])
def test_et1_histories_equal_the_moved_mesh_solve(name, t0, axisymmetric):
    m, W, kw, _left = _case(axisymmetric)
    plain = solve_transient_heat(_moved(m, W, t0), **kw)
    r = solve_transient_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name, t0)))
    got_rates, want_rates = _rates(r), _rates(plain)
    pairs = [("temperature", r.temperature, plain.temperature)] + \
        [(k, got_rates[k], want_rates[k]) for k in want_rates]
    for field, got, want in pairs:
        got, want = _numpy(got), np.asarray(want)
        scale = np.ptp(want) if field == "temperature" else np.max(np.abs(want))
        assert np.max(np.abs(got - want)) <= 1e-12 * scale, field


@pytest.mark.parametrize("name", BACKENDS)
def test_et2_derivative_matches_richardson_differences(name):
    m, W, kw, left = _case()
    _value, slope = _gradient(name, _objective(_xp(name), m, W, kw, left))
    fd = _richardson(lambda h: _plain(_moved(m, W, h), kw, left))
    assert abs(slope - fd) <= 1e-8 * abs(fd), (slope, fd)


def test_et3_jax_and_torch_agree():
    m, W, kw, left = _case()
    a = _gradient("jax", _objective(_xp("jax"), m, W, kw, left))
    b = _gradient("torch", _objective(_xp("torch"), m, W, kw, left))
    for x, y in zip(a, b):
        assert abs(x - y) <= 1e-12 * max(abs(x), abs(y)), (a, b)


Q0, G0, L, H = 7.0, 3.0, 1.3, 0.5


def _strip():
    m = rectangle_mesh(L, H, 10, 4)
    left = [int(i) for i in m.boundary["left"]]
    common = dict(thermal_conductivity=2.5, volumetric_heat_capacity=1e3, time=TIME,
                  initial_temperature=np.zeros(m.num_nodes), prescribed_temperature={i: 0.0 for i in left})
    return m, common


@pytest.mark.parametrize("name", BACKENDS)
def test_et4_analytic_load_of_a_fixed_time_dependent_source(name):
    m, common = _strip()
    W = np.zeros_like(m.nodes)
    W[:, 0] = m.nodes[:, 0] / L
    kw = dict(common, heat_source_density=lambda p, time: Q0 * p[:, 0] * (1.0 + time / 100.0))
    xp = _xp(name)
    for index, tau in enumerate(TIME):
        def f(t):
            r = solve_transient_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
            return xp.sum(r.generated_heat_rate_per_depth[index])
        value, slope = _gradient(name, f)
        scale = 1.0 + tau / 100.0
        assert abs(value - Q0 * L * L * H / 2 * scale) <= 1e-10 * Q0 * L * L * H / 2 * scale, (index, value)
        assert abs(slope - Q0 * L * H * scale) <= 1e-10 * Q0 * L * H * scale, (index, slope)


@pytest.mark.parametrize("name", BACKENDS)
def test_et5_analytic_rate_of_a_field_flux_on_a_growing_side(name):
    m, common = _strip()
    W = np.zeros_like(m.nodes)
    W[:, 1] = m.nodes[:, 1] / H
    kw = dict(common, inward_heat_flux={"right": lambda p, n, time: G0 * p[:, 1] * (1.0 + time / 100.0)})
    xp = _xp(name)
    for index, tau in enumerate(TIME[1:]):
        def f(t):
            r = solve_transient_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=t))
            return xp.sum(r.outward_prescribed_heat_rate_per_depth[index])
        value, slope = _gradient(name, f)
        scale = 1.0 + tau / 100.0
        assert abs(value + G0 * H * H / 2 * scale) <= 1e-10 * G0 * H * H / 2 * scale, (index, value)
        assert abs(slope + G0 * H * scale) <= 1e-10 * G0 * H * scale, (index, slope)


NUMPY_ONLY = [
    ("heat_source_density", dict(heat_source_density=lambda p, time: np.asarray(p)[:, 0] + time)),
    ("the heat flux on 'top'", dict(inward_heat_flux={"top": lambda p, n: np.ones(len(p))})),
    ("convection['right']", dict(convection={"right": (lambda p, n, time: np.full(len(p), 3.0), 290.0)})),
]


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("label,over", NUMPY_ONLY, ids=[c[0] for c in NUMPY_ONLY])
def test_et6_numpy_only_callbacks_are_refused_by_name(name, label, over):
    m, W, kw, _left = _case()
    kw = {**{k: v for k, v in kw.items() if k not in ("heat_source_density", "inward_heat_flux", "convection")},
          **over}
    with pytest.raises(TypeError, match=f"the callback of {label}".replace("[", r"\[").replace("]", r"\]")) as caught:
        solve_transient_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf(name)))
    assert "JAX or PyTorch" in str(caught.value)


def test_et6_coordinate_dirichlet_callbacks_stay_refused():
    m, W, kw, left = _case()
    kw = {**kw, "prescribed_temperature": {left[0]: lambda p, n: 300.0, **{i: 300.0 for i in left[1:]}}}
    with pytest.raises(TypeError, match="prescribed_temperature is a callback of coordinates"):
        solve_transient_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_leaf("jax")))


def test_et7_without_a_motion_nothing_changes():
    m, _W, kw, _left = _case()
    a = solve_transient_heat(m, **kw)
    b = solve_transient_heat(m, **kw, motion=None)
    assert np.array_equal(a.temperature, b.temperature)
    for k, v in _rates(a).items():
        assert np.array_equal(np.asarray(v), np.asarray(_rates(b)[k])), k
