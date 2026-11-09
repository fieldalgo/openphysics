# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of steady heat (galerkin.shape, 3h first slice).

S1-S8 are the checks pre-registered before the implementation; their tolerances are
fixed there and are not loosened here.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import ElementInversion, MeshMotion, admissible_interval, extend_velocity
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


def _gradient(name, objective, t0=0.0):
    """d objective / dt at t0, and the objective's number."""
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

def _slab(nx=20, L=1.0, H=0.2, L1=0.4):
    m = rectangle_mesh(L, H, nx, 4)
    cent = m.nodes[m.triangles].mean(axis=1)[:, 0]
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, (cent > L1).astype(int), ["a", "b"])
    x = m.nodes[:, 0]
    W = np.zeros((m.num_nodes, 2))
    W[:, 0] = np.where(x <= L1, x / L1, (L - x) / (L - L1))
    return m, W


def _plate():
    """A unit plate with a heat source, convection on top and an oblique interior motion."""
    m = rectangle_mesh(1.0, 0.6, 12, 8)
    cent = m.nodes[m.triangles].mean(axis=1)
    regions = ((cent[:, 0] - 0.5) ** 2 + (cent[:, 1] - 0.3) ** 2 < 0.04).astype(int)
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, regions, ["host", "core"])
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    bump = np.sin(math.pi * x) * np.sin(math.pi * y / 0.6)
    # an interior bump plus a stretch that moves the top (convection) and right (flux) sides
    W = np.stack([0.3 * bump, 0.2 * bump * (x - 0.5) + 0.1 * x * y / 0.6], axis=1)
    return m, W


def _plate_solve(m, W, t, xp):
    left = [int(i) for i in m.boundary["left"]]
    return solve_steady_heat(m, conductivity={"host": 1.5, "core": 4.0}, heat_source={"host": 0.0, "core": 50.0},
                             dirichlet={i: 300.0 for i in left}, convection={"top": (8.0, 290.0)},
                             outward_flux={"right": -3.0}, motion=None if t is None else MeshMotion(W, t))


def _plate_functionals(m, r, xp):
    probe = int(np.argmin(np.hypot(m.nodes[:, 0] - 0.5, m.nodes[:, 1] - 0.3)))
    left = [int(i) for i in m.boundary["left"]]
    return {"probe": lambda: r.temperature[probe],
            "dirichlet_heat": lambda: xp.sum(r.reaction[np.asarray(left)]),
            "mean": lambda: xp.mean(r.temperature)}


# ---------------------------------------------------------------- S1 discrete consistency

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("functional", ["probe", "dirichlet_heat", "mean"])
def test_s1_matches_moved_mesh_central_difference(name, functional):
    xp = _xp(name)
    m, W = _plate()

    def objective(t):
        r = _plate_solve(m, W, t, xp)
        return _plate_functionals(m, r, xp)[functional]()

    value, grad = _gradient(name, objective)
    h = 1e-4 * 1.0
    up = _plate_solve(_moved(m, W, h), W, None, np)
    down = _plate_solve(_moved(m, W, -h), W, None, np)
    fd = (float(_plate_functionals(m, up, np)[functional]()) - float(_plate_functionals(m, down, np)[functional]())) / (2 * h)
    base = _plate_solve(m, W, None, np)
    assert value == pytest.approx(float(_plate_functionals(m, base, np)[functional]()), rel=1e-12)
    assert rel(grad, fd) <= 1e-6, (grad, fd)


# ---------------------------------------------------------------- S2 slab

@pytest.mark.parametrize("name", BACKENDS)
def test_s2_two_layer_slab(name):
    xp = _xp(name)
    k1, k2, L, H, L1 = 2.0, 5.0, 1.0, 0.2, 0.4
    m, W = _slab(L=L, H=H, L1=L1)
    left, right = ([int(i) for i in m.boundary[s]] for s in ("left", "right"))

    def resistance(t):
        r = solve_steady_heat(m, conductivity={"a": k1, "b": k2}, dirichlet={**{i: 1.0 for i in left},
                              **{i: 0.0 for i in right}}, motion=MeshMotion(W, t))
        return H / xp.sum(r.reaction[np.asarray(left)])

    value, grad = _gradient(name, resistance)
    assert rel(value, L1 / k1 + (L - L1) / k2) <= 1e-10
    assert rel(grad, 1 / k1 - 1 / k2) <= 1e-10


# ---------------------------------------------------------------- S3 annulus from the geometry engine

def _annulus(a, b, size):
    """The meshed annulus a < r < b of a v1 geometry document, its design velocity for a, and curve masks."""
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
    outer = nv.on_curve & ~inner
    return mesh, nv, inner, outer


@pytest.mark.parametrize("name", BACKENDS)
def test_s3_annulus_inner_radius(name):
    xp = _xp(name)
    a, b, k = 2.0, 4.0, 3.0
    exact = 2 * math.pi * k / (a * math.log(b / a) ** 2)            # dQ/da for dT = 1, Q = 2 pi k / ln(b/a)
    errors = []
    sizes = (0.8, 0.4, 0.2)
    for size in sizes:
        mesh, nv, inner, outer = _annulus(a, b, size)
        W = extend_velocity(mesh, nv.values, nv.on_curve)
        inner_nodes = np.flatnonzero(inner)
        dirichlet = {**{int(i): 1.0 for i in inner_nodes}, **{int(i): 0.0 for i in np.flatnonzero(outer)}}

        def heat(t):
            r = solve_steady_heat(mesh, conductivity=k, dirichlet=dirichlet, motion=MeshMotion(W, t))
            return xp.sum(r.reaction[inner_nodes])

        _value, grad = _gradient(name, heat)
        errors.append(rel(grad, exact))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(sizes[i] / sizes[i + 1]) for i in range(2)]
    assert min(orders) >= 1.5, (errors, orders)
    assert errors[-1] <= 1e-3, errors


# ---------------------------------------------------------------- S4 extension independence

@pytest.mark.parametrize("name", BACKENDS[:1])
def test_s4_extension_does_not_matter_in_the_limit(name):
    xp = _xp(name)
    a, b, k = 2.0, 4.0, 3.0
    exact = 2 * math.pi * k / (a * math.log(b / a) ** 2)
    gaps, sizes = [], (0.8, 0.4, 0.2)
    for size in sizes:
        mesh, nv, inner, outer = _annulus(a, b, size)
        inner_nodes = np.flatnonzero(inner)
        dirichlet = {**{int(i): 1.0 for i in inner_nodes}, **{int(i): 0.0 for i in np.flatnonzero(outer)}}
        grads = []
        for method in ("harmonic", "stiffened"):
            W = extend_velocity(mesh, nv.values, nv.on_curve, method=method)

            def heat(t):
                r = solve_steady_heat(mesh, conductivity=k, dirichlet=dirichlet, motion=MeshMotion(W, t))
                return xp.sum(r.reaction[inner_nodes])

            grads.append(_gradient(name, heat)[1])
        gaps.append(abs(grads[0] - grads[1]) / exact)
    orders = [math.log(gaps[i] / gaps[i + 1]) / math.log(sizes[i] / sizes[i + 1]) for i in range(2)]
    assert min(orders) >= 1.0, (gaps, orders)
    assert gaps[-1] <= 1e-3, gaps


# ---------------------------------------------------------------- S5 rigid translation

@pytest.mark.parametrize("name", BACKENDS)
def test_s5_rigid_translation(name):
    xp = _xp(name)
    m, _W = _plate()
    W = np.tile([0.7, -0.4], (m.num_nodes, 1))
    left = [int(i) for i in m.boundary["left"]]

    def total(t):
        r = solve_steady_heat(m, conductivity={"host": 1.5, "core": 4.0}, heat_source={"host": 0.0, "core": 50.0},
                              dirichlet={i: 300.0 for i in left}, convection={"top": (8.0, 290.0)},
                              motion=MeshMotion(W, t))
        return xp.sum(r.temperature)

    value, grad = _gradient(name, total)
    assert abs(grad) <= 1e-12 * abs(value)


# ---------------------------------------------------------------- S6 inversion bound

def test_s6_admissible_interval_exact():
    # one triangle (0,0), (1,0), (0,1); the apex moves down by t: area (1 - t)/2 -> t_hi = 1
    m = Mesh(np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]), np.array([[0, 1, 2]]), {})
    W = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, -1.0]])
    assert admissible_interval(m, W) == (-math.inf, 1.0)
    # the right corner moves left and up: 2A = (1 - t)(1) - (t)(0) ... with a quadratic term
    W2 = np.array([[0.0, 0.0], [-1.0, 1.0], [1.0, 0.0]])
    # 2A(t) = (1 - t)(1) - (t)(t) = 1 - t - t^2 -> roots (-1 +- sqrt 5)/2
    lo, hi = admissible_interval(m, W2)
    assert hi == pytest.approx((-1 + math.sqrt(5)) / 2, rel=1e-15)
    assert lo == pytest.approx((-1 - math.sqrt(5)) / 2, rel=1e-15)
    slab, Ws = _slab()
    assert admissible_interval(slab, Ws) == pytest.approx((-0.4, 0.6), rel=1e-12)


@pytest.mark.parametrize("name", BACKENDS[:1])
def test_s6_step_beyond_the_bound_is_refused(name):
    xp = _xp(name)
    m, W = _slab()
    left, right = ([int(i) for i in m.boundary[s]] for s in ("left", "right"))
    with pytest.raises(ElementInversion, match=r"admissible interval \(-0.4, 0.6\)"):
        solve_steady_heat(m, conductivity={"a": 2.0, "b": 5.0}, dirichlet={**{i: 1.0 for i in left},
                          **{i: 0.0 for i in right}}, motion=MeshMotion(W, xp.asarray(0.61)))
    # inside the interval the step solves the moved mesh
    r = solve_steady_heat(m, conductivity={"a": 2.0, "b": 5.0}, dirichlet={**{i: 1.0 for i in left},
                          **{i: 0.0 for i in right}}, motion=MeshMotion(W, xp.asarray(0.3)))
    Q = float(np.sum(np.asarray(r.reaction)[left]))
    assert rel(0.2 / Q, 0.7 / 2.0 + 0.3 / 5.0) <= 1e-10


# ---------------------------------------------------------------- S7 unchanged without motion

def test_s7_unchanged_without_motion():
    # motion=None takes the unchanged path: the arrays equal those of a call without the keyword
    # (main and this branch give the same sha256 for this problem, measured 2026-11-09; the HQ record)
    m, _W = _plate()
    left = [int(i) for i in m.boundary["left"]]
    kw = dict(conductivity={"host": 1.5, "core": 4.0}, heat_source={"host": 0.0, "core": 50.0},
              dirichlet={i: 300.0 for i in left}, convection={"top": (8.0, 290.0)}, outward_flux={"right": -3.0})
    r1 = solve_steady_heat(m, **kw)
    r2 = solve_steady_heat(m, **kw, motion=None)

    def digest(r):
        return hashlib.sha256(b"".join(np.ascontiguousarray(getattr(r, f), dtype=float).tobytes()
                                       for f in ("temperature", "heat_flux", "load", "reaction", "residual")))

    assert digest(r1).hexdigest() == digest(r2).hexdigest()
    assert isinstance(r1.temperature, np.ndarray)


# ---------------------------------------------------------------- S8 refusals

def test_s8_refusals():
    xp = _xp("jax")
    m, W = _slab()
    left = [int(i) for i in m.boundary["left"]]
    common = dict(conductivity={"a": 2.0, "b": 5.0}, dirichlet={i: 1.0 for i in left})
    t = xp.asarray(0.0)
    with pytest.raises(TypeError, match="NumPy does not differentiate"):
        solve_steady_heat(m, **common, motion=MeshMotion(W, 0.0))
    with pytest.raises(TypeError, match="heat_source is a callback"):
        solve_steady_heat(m, **common, heat_source=lambda p: np.ones(len(p)), motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match=r"outward_flux\['right'\] is a callback"):
        solve_steady_heat(m, **common, outward_flux={"right": lambda p, n: np.ones(len(p))}, motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="conductivity is live"):
        solve_steady_heat(m, conductivity={"a": xp.asarray(2.0), "b": 5.0}, dirichlet={i: 1.0 for i in left},
                          motion=MeshMotion(W, t))
    with pytest.raises(ValueError, match=r"velocity must have shape"):
        solve_steady_heat(m, **common, motion=MeshMotion(W[:-1], t))
    bad = W.copy()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError, match="velocity must be finite"):
        solve_steady_heat(m, **common, motion=MeshMotion(bad, t))
    with pytest.raises(ValueError, match="axisymmetric is refused"):
        solve_steady_heat(m, **common, coordinate_system="axisymmetric", motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="only t is live"):
        solve_steady_heat(m, **common, motion=MeshMotion(xp.asarray(W), t))


# ---------------------------------------------------------------- independent review regressions (2026-11-09)

def test_review_live_or_callable_values_inside_a_convection_pair_are_refused():
    torch = _torch()
    m, W = _slab()
    left = [int(i) for i in m.boundary["left"]]
    common = dict(conductivity={"a": 2.0, "b": 5.0}, dirichlet={i: 1.0 for i in left})
    t = torch.tensor(0.0, dtype=torch.float64, requires_grad=True)
    h = torch.tensor(8.0, dtype=torch.float64, requires_grad=True)
    # a list pair with a live h once ran and returned dJ/dh = 0 (the correction removed it)
    with pytest.raises(TypeError, match=r"convection\['right'\] is live"):
        solve_steady_heat(m, **common, convection={"right": [h, 280.0]}, motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match=r"convection\['right'\] is a callback"):
        solve_steady_heat(m, **common, convection={"right": (lambda p, n: np.ones(len(p)), 280.0)},
                          motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match=r"convection\['right'\] is a callback"):
        solve_steady_heat(m, **common, convection={"right": [8.0, lambda p, n: np.ones(len(p))]},
                          motion=MeshMotion(W, t))


def test_review_small_motion_keeps_its_inversion_bound():
    m = Mesh(np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]), np.array([[0, 1, 2]]), {})
    for s in (1e-6, 1e-7, 1e-9):
        W = s * np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0]])          # 2A = 1 - s^2 t^2
        lo, hi = admissible_interval(m, W)
        assert hi == pytest.approx(1 / s, rel=1e-12) and lo == pytest.approx(-1 / s, rel=1e-12)


def test_review_extension_refuses_a_component_without_known_nodes():
    a = rectangle_mesh(1.0, 1.0, 2, 2)
    nodes = np.vstack([a.nodes, a.nodes + [3.0, 0.0]])
    tris = np.vstack([a.triangles, a.triangles + a.num_nodes])
    m = Mesh(nodes, tris, {})
    known = np.zeros(m.num_nodes, dtype=bool)
    known[: a.num_nodes] = True
    with pytest.raises(ValueError, match="1 connected component"):
        extend_velocity(m, np.zeros((m.num_nodes, 2)), known)


def test_review_messages_name_the_input():
    xp = _xp("jax")
    m, W = _slab()
    with pytest.raises(ValueError, match="t must be finite"):
        solve_steady_heat(m, conductivity={"a": 2.0, "b": 5.0}, dirichlet={0: 1.0}, motion=MeshMotion(W, xp.asarray(np.nan)))
    with pytest.raises(ValueError, match="dirichlet must map node indices"):
        solve_steady_heat(m, conductivity={"a": 2.0, "b": 5.0}, dirichlet=[(0, 1.0)], motion=MeshMotion(W, xp.asarray(0.0)))


def test_review_torch_second_derivative_is_refused():
    torch = _torch()
    m = rectangle_mesh(1.0, 0.5, 6, 3)
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    W = np.stack([0.1 * x * y, 0.05 * x], axis=1)
    left = [int(i) for i in m.boundary["left"]]
    t = torch.tensor(0.0, dtype=torch.float64, requires_grad=True)
    J = torch.sum(solve_steady_heat(m, conductivity=2.0, dirichlet={i: 300.0 for i in left}, heat_source=3.0,
                                    motion=MeshMotion(W, t)).temperature)
    with pytest.raises(RuntimeError, match="second derivatives"):
        torch.autograd.grad(J, t, create_graph=True)
