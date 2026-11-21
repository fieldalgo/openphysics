# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of axisymmetric steady and transient heat (2026-11-21).

A1-A8 were pre-registered in the HQ work record (2026-11-21) before the implementation ran:
A1 the motion's numbers equal the ordinary solve on the moved mesh (relative 1e-12);
A2 steady dT/dt with a source, an inward flux and convection equals a Richardson-extrapolated
central difference of moved-mesh solves within 1e-8 of max |dT/dt|; A3 JAX and PyTorch agree
within 1e-12; A4 a rigid translation along z gives dT/dt = 0 within 1e-10 max |T|; A5 the heat
rate through the inner wall of a hollow cylinder, differentiated in its outer radius, converges
to the analytic -2 pi k H (T1 - T2) / (b ln^2(b/a)) at order >= 1.5 and within 1 % on the
finest mesh; A6 the transient history's last temperatures as A2; A7 refusals; A8 the results
without a motion equal main 54485b12 (sha256, measured on one machine; the test checks that
motion=None equals a call without the keyword, which holds on every BLAS build).
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import MeshMotion
from galerkin.thermal import solve_steady_heat
from galerkin.transient_heat import solve_transient_heat

BACKENDS = ["jax", "torch"]


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _jacobian(name, function):
    """d function / dt at t = 0 as NumPy numbers (function maps the live t to a vector)."""
    if name == "jax":
        jax = _jax()
        return np.asarray(jax.jacrev(function)(jax.numpy.asarray(0.0, dtype=jax.numpy.float64)))
    torch = _torch()
    return torch.autograd.functional.jacobian(function, torch.tensor(0.0, dtype=torch.float64)).detach().numpy()


def _moved(mesh, W, h):
    return Mesh(mesh.nodes + h * W, mesh.triangles, mesh.boundary, mesh.boundary_edges, mesh.regions,
                mesh.region_names)


def _richardson(values_at, h):
    """Central difference of values_at(h) extrapolated once (h, h/2)."""
    def central(s):
        return (values_at(s) - values_at(-s)) / (2 * s)
    return (4 * central(h / 2) - central(h)) / 3


# ---------------------------------------------------------------- the r-z section

def _section():
    """r in [0, 1] (the left side is the symmetry axis), z in [0, 0.6], a heated core, an interior bump
    and a stretch that moves the right (flux) and top (convection) sides; W_r = 0 on the axis."""
    m = rectangle_mesh(1.0, 0.6, 10, 6)
    cent = m.nodes[m.triangles].mean(axis=1)
    regions = ((cent[:, 0] < 0.4) & (np.abs(cent[:, 1] - 0.3) < 0.15)).astype(int)
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, regions, ["host", "core"])
    r, z = m.nodes[:, 0], m.nodes[:, 1]
    bump = np.sin(math.pi * r) * np.sin(math.pi * z / 0.6)
    W = np.stack([0.1 * r + 0.05 * bump, 0.08 * z / 0.6 + 0.03 * bump], axis=1)
    return m, W


def _steady(m, W, t):
    bottom = [int(i) for i in m.boundary["bottom"]]
    return solve_steady_heat(m, thermal_conductivity={"host": 1.5, "core": 4.0},
                             heat_source_density={"host": 0.0, "core": 5.0e3},
                             prescribed_temperature={i: 300.0 for i in bottom}, convection={"top": (8.0, 290.0)},
                             inward_heat_flux={"right": 300.0}, coordinate_system="axisymmetric",
                             motion=None if t is None else MeshMotion(design_velocity=W, t=t))


TIMES = np.linspace(0.0, 50.0, 6)


def _transient(m, W, t):
    bottom = [int(i) for i in m.boundary["bottom"]]
    return solve_transient_heat(m, thermal_conductivity={"host": 1.5, "core": 4.0},
                                volumetric_heat_capacity={"host": 2.0e5, "core": 1.0e5}, time=TIMES,
                                initial_temperature=np.full(m.num_nodes, 300.0), prescribed_temperature={i: 300.0 for i in bottom},
                                heat_source_density={"host": 0.0, "core": 5.0e3}, convection={"top": (8.0, 290.0)},
                                inward_heat_flux={"right": 300.0}, coordinate_system="axisymmetric",
                                motion=None if t is None else MeshMotion(design_velocity=W, t=t))


def _numbers(value):
    return np.asarray(value.detach() if hasattr(value, "detach") else value, dtype=float)


# ---------------------------------------------------------------- A1, A2, A3 steady

@pytest.fixture(scope="module")
def steady_jacobians():
    m, W = _section()
    out = {name: _jacobian(name, lambda t: _steady(m, W, t).temperature) for name in BACKENDS}
    fd = _richardson(lambda h: _steady(_moved(m, W, h), W, None).temperature, 2e-3)
    return m, W, out, fd


@pytest.mark.parametrize("name", BACKENDS)
def test_a1_the_motion_keeps_the_moved_mesh_numbers(name):
    m, W = _section()
    t = _jax().numpy.asarray(0.01) if name == "jax" else _torch().tensor(0.01, dtype=_torch().float64)
    live = _steady(m, W, t)
    plain = _steady(_moved(m, W, 0.01), W, None)
    assert live.coordinate_system == "axisymmetric"
    for field in ("temperature", "reaction_heat_rate", "generated_heat_rate", "outward_prescribed_heat_rate",
                  "outward_convective_heat_rate"):
        a, b = _numbers(getattr(live, field)), np.asarray(getattr(plain, field), dtype=float)
        assert np.max(np.abs(a - b)) <= 1e-12 * max(np.max(np.abs(b)), 1.0), field


def test_a2_a3_steady_derivative_against_moved_meshes(steady_jacobians):
    _m, _W, jac, fd = steady_jacobians
    scale = np.max(np.abs(fd))
    assert scale > 0
    assert np.max(np.abs(jac["jax"] - fd)) <= 1e-8 * scale, np.max(np.abs(jac["jax"] - fd)) / scale        # A2
    assert np.max(np.abs(jac["torch"] - jac["jax"])) <= 1e-12 * np.max(np.abs(jac["jax"]))                 # A3


# ---------------------------------------------------------------- A4 rigid translation along z

@pytest.mark.parametrize("name", BACKENDS)
def test_a4_rigid_translation_along_the_axis(name):
    m, _W = _section()
    W = np.zeros((m.num_nodes, 2))
    W[:, 1] = 1.0
    derivative = _jacobian(name, lambda t: _steady(m, W, t).temperature)
    temperature = np.asarray(_steady(m, W, None).temperature)
    assert np.max(np.abs(derivative)) <= 1e-10 * np.max(np.abs(temperature))


# ---------------------------------------------------------------- A5 the hollow cylinder

def _hollow(a, b, height, nr, nz):
    m = rectangle_mesh(b - a, height, nr, nz)
    m = Mesh(m.nodes + np.array([a, 0.0]), m.triangles, m.boundary, m.boundary_edges)
    W = np.zeros((m.num_nodes, 2))
    W[:, 0] = (m.nodes[:, 0] - a) / (b - a)          # moves the outer wall r = b with unit speed
    return m, W


def _inner_heat_rate(name, a, b, height, k, t1, t2, nr):
    m, W = _hollow(a, b, height, nr, 2)
    inner = np.asarray(m.boundary["left"], dtype=int)
    dirichlet = {**{int(i): t1 for i in inner}, **{int(i): t2 for i in m.boundary["right"]}}

    def rate(t):
        r = solve_steady_heat(m, thermal_conductivity=k, prescribed_temperature=dirichlet,
                              coordinate_system="axisymmetric", motion=MeshMotion(design_velocity=W, t=t))
        return r.reaction_heat_rate[inner].sum()
    return float(_jacobian(name, rate))


@pytest.mark.parametrize("name", BACKENDS)
def test_a5_hollow_cylinder_outer_radius_converges_to_the_analytic_rate(name):
    a, b, height, k, t1, t2 = 1.0, 2.0, 0.5, 3.0, 400.0, 300.0
    exact = -2 * math.pi * k * height * (t1 - t2) / (b * math.log(b / a) ** 2)
    errors = [abs(_inner_heat_rate(name, a, b, height, k, t1, t2, nr) / exact - 1) for nr in (8, 16, 32)]
    orders = [math.log2(errors[i] / errors[i + 1]) for i in range(2)]
    assert min(orders) >= 1.5, (errors, orders)
    assert errors[-1] <= 1e-2, errors


# ---------------------------------------------------------------- A6 transient

def test_a6_transient_history_against_moved_meshes():
    m, W = _section()
    last = {name: _jacobian(name, lambda t: _transient(m, W, t).temperature[-1]) for name in BACKENDS}
    fd = _richardson(lambda h: np.asarray(_transient(_moved(m, W, h), W, None).temperature[-1]), 2e-3)
    scale = np.max(np.abs(fd))
    assert scale > 0
    assert np.max(np.abs(last["jax"] - fd)) <= 1e-8 * scale, np.max(np.abs(last["jax"] - fd)) / scale
    assert np.max(np.abs(last["torch"] - last["jax"])) <= 1e-12 * np.max(np.abs(last["jax"]))
    t = _jax().numpy.asarray(0.0)
    assert _transient(m, W, t).coordinate_system == "axisymmetric"


# ---------------------------------------------------------------- A7 refusals

def test_a7_refusals():
    jnp = _jax().numpy
    m, W = _section()
    off_axis = W.copy()
    off_axis[m.nodes[:, 0] == 0, 0] = 0.1
    with pytest.raises(ValueError, match="symmetry axis off it"):
        _steady(m, off_axis, jnp.asarray(0.0))
    with pytest.raises(ValueError, match="symmetry axis off it"):
        _transient(m, off_axis, jnp.asarray(0.0))
    bottom = [int(i) for i in m.boundary["bottom"]]
    with pytest.raises(TypeError, match="live"):
        solve_steady_heat(m, thermal_conductivity=jnp.asarray(2.0), prescribed_temperature={i: 300.0 for i in bottom},
                          coordinate_system="axisymmetric", motion=MeshMotion(design_velocity=W, t=jnp.asarray(0.0)))
    with pytest.raises(ValueError, match="coordinate_system must be"):
        solve_steady_heat(m, thermal_conductivity=2.0, prescribed_temperature={i: 300.0 for i in bottom},
                          coordinate_system="polar", motion=MeshMotion(design_velocity=W, t=jnp.asarray(0.0)))


def test_review_the_axis_is_taken_at_the_step_t():
    """Independent review 2026-11-21: the axis test uses X0 + t W, not X0."""
    jnp = _jax().numpy
    m = rectangle_mesh(1.0, 0.5, 8, 4)
    W = np.zeros((m.num_nodes, 2))
    W[:, 0] = 1.0
    hot = [int(i) for i in m.boundary["right"]]
    kw = dict(thermal_conductivity=2.0, prescribed_temperature={i: 300.0 for i in hot},
              convection={"left": (5.0, 290.0)}, coordinate_system="axisymmetric")
    # a ring r in [0.1, 1.1] at t = 0.1: nothing lies on the axis there
    ring = solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=jnp.asarray(0.1)))
    assert ring.coordinate_system == "axisymmetric"
    # r in [-0.1, 0.9] reaches the axis exactly at t = 0.1 and moves off it
    shifted = Mesh(m.nodes - np.array([0.1, 0.0]), m.triangles, m.boundary, m.boundary_edges)
    with pytest.raises(ValueError, match="symmetry axis off it"):
        solve_steady_heat(shifted, **{**kw, "convection": None},
                          motion=MeshMotion(design_velocity=W, t=jnp.asarray(0.1)))


# ---------------------------------------------------------------- A8 unchanged without a motion

def _digest(result, fields):
    h = hashlib.sha256()
    for field in fields:
        h.update(np.ascontiguousarray(np.asarray(getattr(result, field), dtype=float)).tobytes())
    return h.hexdigest()


def test_a8_unchanged_without_motion():
    # A8 as measured on 2026-11-21: on one machine, these problems without a motion give the same
    # sha256 on main 54485b12 and on this branch (steady 93f3a3d1..., transient b2cb8a7a...). A hash
    # is not portable across BLAS builds, so the test checks what holds everywhere: motion=None takes
    # the unchanged path, bit for bit equal to a call without the keyword.
    from galerkin.thermal import solve_steady_heat as steady
    from galerkin.transient_heat import solve_transient_heat as transient
    m, W = _section()
    with_none = (_steady(m, W, None), _transient(m, W, None))
    bottom = [int(i) for i in m.boundary["bottom"]]
    common = dict(thermal_conductivity={"host": 1.5, "core": 4.0}, heat_source_density={"host": 0.0, "core": 5.0e3},
                  prescribed_temperature={i: 300.0 for i in bottom}, convection={"top": (8.0, 290.0)},
                  inward_heat_flux={"right": 300.0}, coordinate_system="axisymmetric")
    without = (steady(m, **common),
               transient(m, **common, volumetric_heat_capacity={"host": 2.0e5, "core": 1.0e5}, time=TIMES,
                         initial_temperature=np.full(m.num_nodes, 300.0)))
    fields = (("temperature", "heat_flux", "reaction_heat_rate", "outward_convective_heat_rate"),
              ("temperature", "heat_flux", "reaction_heat_rate", "stored_heat"))
    for a, b, names in zip(with_none, without, fields):
        assert _digest(a, names) == _digest(b, names)
        assert isinstance(a.temperature, np.ndarray)
