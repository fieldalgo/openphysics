# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of steady electric conduction (galerkin.shape, second slice).

E1-E8 are the checks pre-registered before the implementation (HQ record,
2026-11-10); their tolerances are fixed there and are not loosened here.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from galerkin.electric import ElementConductivity, solve_steady_electric
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import MeshMotion, extend_velocity

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


# ---------------------------------------------------------------- problems

def _plate():
    """A plate with two conductivities, a terminal on the left, current injected on the moving right side."""
    m = rectangle_mesh(1.0, 0.6, 12, 8)
    cent = m.nodes[m.triangles].mean(axis=1)
    regions = ((cent[:, 0] - 0.5) ** 2 + (cent[:, 1] - 0.3) ** 2 < 0.04).astype(int)
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, regions, ["host", "core"])
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    bump = np.sin(math.pi * x) * np.sin(math.pi * y / 0.6)
    W = np.stack([0.3 * bump + 0.1 * x * y / 0.6, 0.2 * bump * (x - 0.5) + 0.1 * x * y / 0.6], axis=1)
    return m, W


def _plate_solve(m, W, t):
    left = [int(i) for i in m.boundary["left"]]
    return solve_steady_electric(m, conductivity={"host": 2.0e3, "core": 5.0e4}, dirichlet={i: 0.0 for i in left},
                                 outward_current={"right": -1.5e3}, motion=None if t is None else MeshMotion(W, t))


def _functionals(m, r, xp):
    probe = int(np.argmin(np.hypot(m.nodes[:, 0] - 0.7, m.nodes[:, 1] - 0.3)))
    left = np.asarray([int(i) for i in m.boundary["left"]])
    return {"probe": lambda: r.potential[probe],
            "terminal_current": lambda: xp.sum(r.reaction[left]),
            "joule_power": lambda: r.joule_power_per_length}


# ---------------------------------------------------------------- E1 discrete consistency

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("functional", ["probe", "terminal_current", "joule_power"])
def test_e1_matches_moved_mesh_central_difference(name, functional):
    xp = _xp(name)
    m, W = _plate()
    value, grad = _gradient(name, lambda t: _functionals(m, _plate_solve(m, W, t), xp)[functional]())
    h = 1e-4
    up = _functionals(m, _plate_solve(_moved(m, W, h), W, None), np)[functional]()
    down = _functionals(m, _plate_solve(_moved(m, W, -h), W, None), np)[functional]()
    fd = (float(up) - float(down)) / (2 * h)
    assert value == pytest.approx(float(_functionals(m, _plate_solve(m, W, None), np)[functional]()), rel=1e-12)
    assert rel(grad, fd) <= 1e-6, (grad, fd)


# ---------------------------------------------------------------- E2 series resistor

@pytest.mark.parametrize("name", BACKENDS)
def test_e2_two_layer_resistor(name):
    xp = _xp(name)
    s1, s2, L, H, L1 = 3.0e3, 8.0e3, 1.0, 0.2, 0.4
    m = rectangle_mesh(L, H, 20, 4)
    cent = m.nodes[m.triangles].mean(axis=1)[:, 0]
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, (cent > L1).astype(int), ["a", "b"])
    x = m.nodes[:, 0]
    W = np.zeros((m.num_nodes, 2))
    W[:, 0] = np.where(x <= L1, x / L1, (L - x) / (L - L1))
    left, right = ([int(i) for i in m.boundary[s]] for s in ("left", "right"))

    def resistance(t):
        r = solve_steady_electric(m, conductivity={"a": s1, "b": s2},
                                  dirichlet={**{i: 1.0 for i in left}, **{i: 0.0 for i in right}},
                                  motion=MeshMotion(W, t))
        return 1.0 / xp.sum(r.reaction[np.asarray(left)])

    value, grad = _gradient(name, resistance)
    assert rel(value, (L1 / s1 + (L - L1) / s2) / H) <= 1e-10
    assert rel(grad, (1 / s1 - 1 / s2) / H) <= 1e-10


# ---------------------------------------------------------------- E3 coaxial conductor

def _annulus(a, b, size):
    from meshine import generate

    from galerkin.interop import from_mesher
    from simcase.geometry_velocity import design_velocity
    doc = {"openphysics": "0.2", "units": {"length": "um"},
           "geometry": {"version": 1, "parameters": {"a": {"value": a}}, "components": {"xs": {
               "dimension": "2d", "domain": {"xmin": -6, "xmax": 6, "ymin": -6, "ymax": 6},
               "background": {"material": None},
               "features": [{"name": "ring", "type": "circle", "cx": 0, "cy": 0, "r": b, "material": "k"},
                            {"name": "hole", "type": "circle", "cx": 0, "cy": 0, "r": "a", "material": None}]}}}}
    dv = design_velocity(doc, "a")
    domain, namer, _ = dv.complex.to_domain(size)
    tm = generate(domain, namer)
    nv = dv.node_velocity(tm)
    mesh = from_mesher(tm)
    r = np.hypot(mesh.nodes[:, 0], mesh.nodes[:, 1])
    inner = nv.on_curve & (r < 0.5 * (a + b))
    return mesh, nv, inner, nv.on_curve & ~inner


@pytest.mark.parametrize("name", BACKENDS)
def test_e3_coaxial_inner_radius(name):
    xp = _xp(name)
    a, b, sigma = 2.0, 4.0, 6.0e3
    exact = 2 * math.pi * sigma / (a * math.log(b / a) ** 2)             # dI/da for dV = 1
    errors, sizes = [], (0.8, 0.4, 0.2)
    for size in sizes:
        mesh, nv, inner, outer = _annulus(a, b, size)
        W = extend_velocity(mesh, nv.values, nv.on_curve)
        inner_nodes = np.flatnonzero(inner)
        dirichlet = {**{int(i): 1.0 for i in inner_nodes}, **{int(i): 0.0 for i in np.flatnonzero(outer)}}

        def current(t):
            r = solve_steady_electric(mesh, conductivity=sigma, dirichlet=dirichlet, motion=MeshMotion(W, t))
            return xp.sum(r.reaction[inner_nodes])

        errors.append(rel(_gradient(name, current)[1], exact))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(sizes[i] / sizes[i + 1]) for i in range(2)]
    assert min(orders) >= 1.5, (errors, orders)
    assert errors[-1] <= 1e-3, errors


# ---------------------------------------------------------------- E4 rigid translation

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("functional", ["joule_power", "potential_sum"])
def test_e4_rigid_translation(name, functional):
    xp = _xp(name)
    m, _W = _plate()
    W = np.tile([0.7, -0.4], (m.num_nodes, 1))

    def objective(t):
        r = _plate_solve(m, W, t)
        return r.joule_power_per_length if functional == "joule_power" else xp.sum(r.potential)

    value, grad = _gradient(name, objective)
    assert abs(grad) <= 1e-12 * abs(value)


# ---------------------------------------------------------------- E5 power identity

@pytest.mark.parametrize("name", BACKENDS)
def test_e5_power_identity_holds_along_the_motion(name):
    m, W = _plate()
    _p, d_power = _gradient(name, lambda t: _plate_solve(m, W, t).joule_power_per_length)
    _s, d_supplied = _gradient(name, lambda t: _plate_solve(m, W, t).supplied_power_per_length)
    assert rel(d_power, d_supplied) <= 1e-10


# ---------------------------------------------------------------- E6 unchanged without motion

def test_e6_unchanged_without_motion():
    # main and this branch give the same sha256 for this problem (measured 2026-11-10; HQ record)
    m, _W = _plate()
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(conductivity={"host": 2.0e3, "core": 5.0e4}, dirichlet={i: 0.0 for i in left},
              outward_current={"right": -1.5e3})

    def digest(r):
        return hashlib.sha256(b"".join(np.ascontiguousarray(getattr(r, f), dtype=float).tobytes() for f in
                                       ("potential", "electric_field", "current_density", "joule_heating",
                                        "joule_load", "reaction", "residual"))).hexdigest()

    assert digest(solve_steady_electric(m, **kw)) == digest(solve_steady_electric(m, **kw, motion=None))


# ---------------------------------------------------------------- E7 gauge component

@pytest.mark.parametrize("name", BACKENDS)
def test_e7_neumann_component_with_a_gauge(name):
    m, W = _plate()
    gauge = int(m.boundary["left"][0])

    def solve(mesh, t):
        return solve_steady_electric(mesh, conductivity={"host": 2.0e3, "core": 5.0e4}, dirichlet={},
                                     outward_current={"right": -1.5e3, "left": 1.5e3},
                                     reference_potential={gauge: 0.0},
                                     motion=None if t is None else MeshMotion(W, t))

    # left (height 0.6) and right (moves) carry currents that must balance; keep the right side
    # length fixed by a motion tangential to it, and the left side fixed
    x = m.nodes[:, 0]
    W = W * (x[:, None] * (1 - x[:, None])) * 4.0
    probe = int(np.argmin(np.hypot(m.nodes[:, 0] - 0.7, m.nodes[:, 1] - 0.3)))
    _value, grad = _gradient(name, lambda t: solve(m, t).potential[probe])
    h = 1e-4
    fd = (float(solve(_moved(m, W, h), None).potential[probe])
          - float(solve(_moved(m, W, -h), None).potential[probe])) / (2 * h)
    assert rel(grad, fd) <= 1e-6, (grad, fd)


# ---------------------------------------------------------------- E8 refusals

def test_e8_refusals():
    xp = _xp("jax")
    m, W = _plate()
    left = [int(i) for i in m.boundary["left"]]
    common = dict(dirichlet={i: 0.0 for i in left})
    t = xp.asarray(0.0)
    with pytest.raises(TypeError, match="NumPy does not differentiate"):
        solve_steady_electric(m, conductivity=2.0e3, **common, motion=MeshMotion(W, 0.0))
    with pytest.raises(TypeError, match=r"outward_current\['right'\] is a callback"):
        solve_steady_electric(m, conductivity=2.0e3, **common, outward_current={"right": lambda p, n: np.ones(len(p))},
                              motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="conductivity is live"):
        solve_steady_electric(m, conductivity={"host": xp.asarray(2.0e3), "core": 5.0e4}, **common,
                              motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="dirichlet is live"):
        solve_steady_electric(m, conductivity=2.0e3, dirichlet={left[0]: xp.asarray(1.0)}, motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="ElementConductivity"):
        solve_steady_electric(m, conductivity=ElementConductivity(m, np.full(m.num_triangles, 2.0e3)), **common,
                              motion=MeshMotion(W, t))


# ---------------------------------------------------------------- independent review regressions (2026-11-10)

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("common", [0.0, 1.0e3, 1.0e6, 1.0e9])
def test_review_large_common_mode_voltage(name, common):
    # A terminal pair at V+1 and V: the supplied power and its derivative do not depend on V.
    # Before the fix the motion path used absolute volts: at 1e6 V it returned 598.33 instead of 600.
    m = rectangle_mesh(1.0, 0.6, 10, 6)
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    W = np.stack([0.1 * x * y, 0.05 * np.sin(3 * x)], axis=1)
    left, right = ([int(i) for i in m.boundary[s]] for s in ("left", "right"))
    kw = dict(conductivity=1.0e3, dirichlet={**{i: common + 1.0 for i in left}, **{i: common for i in right}})
    base = solve_steady_electric(m, **kw)
    supplied, d_supplied = _gradient(name, lambda t: solve_steady_electric(m, **kw, motion=MeshMotion(W, t))
                                     .supplied_power_per_length)
    power, d_power = _gradient(name, lambda t: solve_steady_electric(m, **kw, motion=MeshMotion(W, t))
                               .joule_power_per_length)
    assert rel(supplied, base.supplied_power_per_length) <= 1e-9
    assert rel(power, base.joule_power_per_length) <= 1e-12
    assert rel(d_supplied, d_power) <= 1e-10                         # E5's criterion


def test_review_motion_that_changes_a_current_only_balance_is_refused():
    xp = _xp("jax")
    m = rectangle_mesh(1.0, 0.6, 10, 6)
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    W = np.stack([np.zeros_like(x), x * y], axis=1)                 # the right side grows, the left does not
    gauge = int(m.boundary["left"][0])
    with pytest.raises(ValueError, match="changes its net imposed current"):
        solve_steady_electric(m, conductivity=1.0e3, dirichlet={}, outward_current={"left": 100.0, "right": -100.0},
                              reference_potential={gauge: 0.0}, motion=MeshMotion(W, xp.asarray(0.0)))


def test_review_messages():
    xp = _xp("jax")
    m, W = _plate()
    left = [int(i) for i in m.boundary["left"]]
    with pytest.raises(ValueError, match="outward_current must map boundary edge tags"):
        solve_steady_electric(m, conductivity=2.0e3, dirichlet={i: 0.0 for i in left},
                              outward_current=[("right", 1.0)], motion=MeshMotion(W, xp.asarray(0.0)))
    with pytest.raises(ValueError, match="conductivity must be a finite real scalar"):
        solve_steady_electric(m, conductivity=lambda p: np.ones(len(p)), dirichlet={i: 0.0 for i in left},
                              motion=MeshMotion(W, xp.asarray(0.0)))
