# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of thermoelasticity (galerkin.shape, fourth slice).

Path 1: solve_thermoelasticity with a temperature snapshot whose nodal values move
with their nodes. Path 2: solve_steady_thermoelasticity, whose heat stage is solved
again on the moving mesh. T1-T8 are the checks pre-registered before the
implementation (HQ record, 2026-11-10); their tolerances, and T3's mesh sizes, are
fixed there and are not loosened here.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from galerkin.elasticity import solve_elasticity
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import ElementInversion, MeshMotion, extend_velocity
from galerkin.thermal_mechanical import solve_steady_thermoelasticity
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity

BACKENDS = ["jax", "torch"]
UNITS = {"length": "m", "temperature": "K"}


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


def _clamped_left(m):
    return {(int(i), c): 0.0 for i in m.boundary["left"] for c in (0, 1)}


# ---------------------------------------------------------------- problems

MATERIALS = dict(young_modulus={"host": 70e9, "core": 200e9}, poisson_ratio={"host": 0.33, "core": 0.28},
                 thermal_expansion_per_k={"host": 2.3e-5, "core": 1.2e-5})


def _plate():
    """A clamped plate with two materials; the right side and an inner core move."""
    m = rectangle_mesh(1.0, 0.4, 12, 6)
    cent = m.nodes[m.triangles].mean(axis=1)
    regions = ((cent[:, 0] - 0.55) ** 2 + (cent[:, 1] - 0.2) ** 2 < 0.02).astype(int)
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, regions, ["host", "core"])
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    bump = np.sin(math.pi * x) * np.sin(math.pi * y / 0.4)
    W = np.stack([0.2 * bump + 0.1 * x * y / 0.4, 0.15 * bump * (x - 0.5) + 0.05 * x * y / 0.4], axis=1)
    return m, W


def _plate_temperature(m):
    x, y = m.nodes[:, 0], m.nodes[:, 1]
    return 300.0 + 80.0 * np.sin(2 * x) * np.cos(3 * y) + 40.0 * x


def _snapshot_solve(m, W, t, plane="stress", temperature=None, tref=290.0):
    T = _plate_temperature(m) if temperature is None else temperature
    return solve_thermoelasticity(m, freeze_temperature(m, T), reference_temperature_k=tref, plane=plane,
                                  dirichlet=_clamped_left(m), body_force=(0.0, -2.7e4),
                                  traction={"right": (1.0e6, -4.0e5)}, motion=None if t is None else MeshMotion(W, t),
                                  **MATERIALS)


def _workflow_solve(m, W, t, plane="stress"):
    hot = {int(i): 400.0 for i in m.boundary["right"]}
    cold = {int(i): 300.0 for i in m.boundary["left"]}
    return solve_steady_thermoelasticity(
        m, units=UNITS, conductivity={"host": 160.0, "core": 20.0}, thermal_dirichlet={**hot, **cold},
        heat_source={"host": 0.0, "core": 5e6}, plane=plane, reference_temperature_k=300.0,
        mechanical_dirichlet=_clamped_left(m), body_force=(0.0, -2.7e4),
        motion=None if t is None else MeshMotion(W, t), **MATERIALS)


def _functionals(m, mech, xp):
    tip = int(np.argmin(np.hypot(m.nodes[:, 0] - 1.0, m.nodes[:, 1] - 0.2)))
    left = np.asarray([int(i) for i in m.boundary["left"]])
    y = m.nodes[left, 1] - 0.2
    return {"tip_uy": lambda: mech.displacement[tip, 1],
            # the clamped side's reaction sum (T1); its x component vanishes by equilibrium in path 2
            "reaction": lambda: xp.sum(mech.reaction[left, 1]),
            "energy": lambda: mech.physical_elastic_energy,
            # extra, not pre-registered: the clamped side's reaction moment, which the thermal load drives
            "moment": lambda: xp.sum(mech.reaction[left, 0] * xp.asarray(y))}


def _same_value(m, plain, value, expected):
    """The motion path's value equals the ordinary solve's (a sanity check, not a T criterion).

    Measured against the size of the summed terms: the reaction moment sums reactions that
    largely cancel, and the live correction's rounding (and in path 2 the live heat stage's)
    shows at 1e-12 to 3e-10 of the moment itself."""
    left = np.asarray([int(i) for i in m.boundary["left"]])
    scale = max(abs(float(expected)), float(np.sum(np.abs(plain.reaction[left, 0] * (m.nodes[left, 1] - 0.2)))))
    assert abs(value - float(expected)) <= 1e-12 * scale, (value, float(expected), scale)


# ---------------------------------------------------------------- T1 discrete consistency

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("plane", ["stress", "strain"])
@pytest.mark.parametrize("functional", ["tip_uy", "reaction", "energy", "moment"])
def test_t1_snapshot_matches_moved_mesh_central_difference(name, plane, functional):
    xp = _xp(name)
    m, W = _plate()
    T = _plate_temperature(m)
    value, grad = _gradient(name, lambda t: _functionals(m, _snapshot_solve(m, W, t, plane), xp)[functional]())
    h = 1e-4
    up = _functionals(m, _snapshot_solve(_moved(m, W, h), W, None, plane, T), np)[functional]()
    down = _functionals(m, _snapshot_solve(_moved(m, W, -h), W, None, plane, T), np)[functional]()
    fd = (float(up) - float(down)) / (2 * h)
    plain = _snapshot_solve(m, W, None, plane)
    _same_value(m, plain, value, _functionals(m, plain, np)[functional]())
    assert rel(grad, fd) <= 1e-6, (grad, fd)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("plane", ["stress", "strain"])
@pytest.mark.parametrize("functional", ["tip_uy", "reaction", "energy", "mean_temperature", "moment"])
def test_t1_workflow_matches_moved_mesh_central_difference(name, plane, functional):
    xp = _xp(name)
    m, W = _plate()

    def pick(r, lib):
        if functional == "mean_temperature":
            return lib.mean(r.heat.temperature)
        return _functionals(m, r.mechanics, lib)[functional]()

    value, grad = _gradient(name, lambda t: pick(_workflow_solve(m, W, t, plane), xp))
    # Deviation from the pre-registered h = 1e-4 (HQ record 2026-11-10), for the reaction sum and the moment of
    # this path only, in both planes: they sum reactions of about 1e7 N/m to 10 800 N/m and 5400 N, and the
    # ordinary workflow's own rounding moves them by about 2e-6 between t = 0 and t = 1e-12. At h = 1e-4 that
    # is up to 4.2e-6 (sum) and 7.0e-6 (moment) of the difference quotient in plane strain (plane stress:
    # 2.0e-8, 4.5e-7). Measured: central differences approach the derivative as h grows (h = 1e-2: 5e-9 to
    # 4e-8), so they are taken there. Both are also checked exactly by equilibrium (tests below).
    h = 1e-2 if functional in ("reaction", "moment") else 1e-4
    fd = (float(pick(_workflow_solve(_moved(m, W, h), W, None, plane), np))
          - float(pick(_workflow_solve(_moved(m, W, -h), W, None, plane), np))) / (2 * h)
    plain = _workflow_solve(m, W, None, plane)
    _same_value(m, plain.mechanics, value, pick(plain, np))
    assert rel(grad, fd) <= 1e-6, (grad, fd)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_t1_workflow_reaction_sum_by_equilibrium(name, plane):
    """Extra: the clamped side carries the whole body force, so d(sum R_y)/dt = -f_y dA/dt exactly."""
    xp = _xp(name)
    m, W = _plate()
    _v, grad = _gradient(name, lambda t: _functionals(m, _workflow_solve(m, W, t, plane).mechanics, xp)["reaction"]())
    p, w = m.nodes[m.triangles], W[m.triangles]
    e1, e2, d1, d2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], w[:, 1] - w[:, 0], w[:, 2] - w[:, 0]
    sign = np.sign(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    d_area = np.sum(sign * 0.5 * (d1[:, 0] * e2[:, 1] + e1[:, 0] * d2[:, 1] - d1[:, 1] * e2[:, 0] - e1[:, 1] * d2[:, 0]))
    # measured 2026-11-10: 1.2e-10 to 4.5e-10 (the sum cancels reactions about 1e3 times larger); this bound
    # was set after that measurement, as the check itself is not pre-registered
    assert rel(grad, 2.7e4 * d_area) <= 1e-8, (grad, 2.7e4 * d_area)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_t1_workflow_moment_by_equilibrium(name, plane):
    """Extra (review 2026-11-10): the thermal load has no net moment and the clamped side is at x = 0, so the
    reaction moment about y = 0.2 is f_y * sum(area * x_centroid); its derivative is taken by complex step."""
    xp = _xp(name)
    m, W = _plate()
    _v, grad = _gradient(name, lambda t: _functionals(m, _workflow_solve(m, W, t, plane).mechanics, xp)["moment"]())
    h = 1e-30
    p = (m.nodes + 1j * h * W)[m.triangles]
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    sign = np.sign((e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).real)
    first_moment = np.sum(sign * 0.5 * (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) * p[:, :, 0].mean(axis=1))
    exact = -2.7e4 * first_moment.imag / h
    # measured: 1.1e-10 to 4.3e-10 (review); bound set after the measurement, as for the reaction sum
    assert rel(grad, exact) <= 1e-8, (grad, exact)


# ---------------------------------------------------------------- T2 free thermal expansion

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_t2_free_expansion_length(name, plane):
    xp = _xp(name)
    L, H, alpha, nu, dT = 2.0, 0.3, 1.7e-5, 0.3, 120.0
    m = rectangle_mesh(L, H, 10, 3)
    left = [int(i) for i in m.boundary["left"]]
    pin = min(left, key=lambda i: m.nodes[i, 1])
    dirichlet = {**{(i, 0): 0.0 for i in left}, (pin, 1): 0.0}
    W = np.stack([m.nodes[:, 0] / L, np.zeros(m.num_nodes)], axis=1)              # stretch: dL = 1
    tip = np.asarray([int(i) for i in m.boundary["right"]])
    snapshot = freeze_temperature(m, np.full(m.num_nodes, 293.0 + dT))
    strain = alpha * dT * (1.0 if plane == "stress" else 1.0 + nu)

    def delta(t):
        r = solve_thermoelasticity(m, snapshot, reference_temperature_k=293.0, thermal_expansion_per_k=alpha,
                                   young_modulus=80e9, poisson_ratio=nu, plane=plane, dirichlet=dirichlet,
                                   motion=MeshMotion(W, t))
        return xp.mean(r.displacement[tip, 0])

    value, grad = _gradient(name, delta)
    assert rel(value, strain * L) <= 1e-10
    assert rel(grad, strain) <= 1e-10


# ---------------------------------------------------------------- T3 thick cylinder, heat chained

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
    return mesh, nv, nv.on_curve & (r < 0.5 * (a + b)), nv.on_curve & (r > 0.5 * (a + b))


def _thermal_cylinder_force(a, b, E, nu, alpha, Ta, Tb, Tref):
    """Radial force on the clamped inner circle (u(a) = 0, outer face free, plane strain) for the
    steady logarithmic temperature T(r) = Ta + (Tb - Ta) ln(r/a)/ln(b/a); F = -2 pi a sigma_r(a)."""
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    beta = alpha * (1 + nu) / (1 - nu)
    ln = np.log(b / a)
    integral = (Ta - Tref) * (b * b - a * a) / 2 + (Tb - Ta) / ln * (b * b / 2 * ln - b * b / 4 + a * a / 4)
    c1 = 2 * mu * beta * integral / b ** 2 / (2 * (lam + mu) + 2 * mu * a * a / b ** 2)
    sigma_a = c1 * (2 * (lam + mu) + 2 * mu)
    return -2 * math.pi * a * sigma_a


@pytest.mark.parametrize("name", BACKENDS)
def test_t3_thick_cylinder_heat_chained(name):
    xp = _xp(name)
    a, b, E, nu, alpha, Ta, Tb, Tref = 2.0, 4.0, 1.0, 0.3, 1e-3, 400.0, 300.0, 300.0
    exact = _thermal_cylinder_force(complex(a, 1e-30), b, E, nu, alpha, Ta, Tb, Tref).imag / 1e-30
    errors, sizes = [], (0.4, 0.2, 0.1)                                           # pre-registered sizes
    for size in sizes:
        mesh, nv, inner, outer = _annulus(a, b, size)
        W = extend_velocity(mesh, nv.values, nv.on_curve)
        nodes = np.flatnonzero(inner)
        radial = mesh.nodes[nodes] / np.hypot(mesh.nodes[nodes, 0], mesh.nodes[nodes, 1])[:, None]
        heat = {**{int(i): Ta for i in nodes}, **{int(i): Tb for i in np.flatnonzero(outer)}}
        clamp = {(int(i), c): 0.0 for i in nodes for c in (0, 1)}

        def force(t):
            r = solve_steady_thermoelasticity(
                mesh, units=UNITS, conductivity=1.0, thermal_dirichlet=heat, young_modulus=E, poisson_ratio=nu,
                plane="strain", thermal_expansion_per_k=alpha, reference_temperature_k=Tref,
                mechanical_dirichlet=clamp, motion=MeshMotion(W, t))
            return xp.sum(r.mechanics.reaction[nodes] * xp.asarray(radial))

        value, grad = _gradient(name, force)
        errors.append(rel(grad, exact))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(sizes[i] / sizes[i + 1]) for i in range(2)]
    assert min(orders) >= 1.0, (errors, orders)
    assert errors[-1] <= 1e-2, errors


# ---------------------------------------------------------------- T4 clamped two-material bar

@pytest.mark.parametrize("name", BACKENDS)
def test_t4_clamped_series_bar_interface(name):
    xp = _xp(name)
    L, H, L1, E1, E2, a1, a2, dT = 2.0, 0.3, 0.8, 50e9, 120e9, 2.3e-5, 1.1e-5, 80.0
    m = rectangle_mesh(L, H, 10, 3)
    cent = m.nodes[m.triangles].mean(axis=1)[:, 0]
    m = Mesh(m.nodes, m.triangles, m.boundary, m.boundary_edges, (cent > L1).astype(int), ["a", "b"])
    ends = [int(i) for side in ("left", "right") for i in m.boundary[side]]
    rollers = [int(i) for side in ("top", "bottom") for i in m.boundary[side]]
    dirichlet = {**{(i, 0): 0.0 for i in ends}, **{(i, 1): 0.0 for i in rollers}}
    x = m.nodes[:, 0]
    W = np.stack([np.where(x <= L1, x / L1, (L - x) / (L - L1)), np.zeros(m.num_nodes)], axis=1)
    snapshot = freeze_temperature(m, np.full(m.num_nodes, 300.0 + dT))

    def sigma(t):
        r = solve_thermoelasticity(m, snapshot, reference_temperature_k=300.0,
                                   thermal_expansion_per_k={"a": a1, "b": a2}, young_modulus={"a": E1, "b": E2},
                                   poisson_ratio=0.0, plane="stress", dirichlet=dirichlet, motion=MeshMotion(W, t))
        return r.stress[0, 0]

    def exact(L1):
        return -dT * (a1 * L1 + a2 * (L - L1)) / (L1 / E1 + (L - L1) / E2)

    value, grad = _gradient(name, sigma)
    assert rel(value, exact(L1)) <= 1e-10
    assert rel(grad, exact(complex(L1, 1e-30)).imag / 1e-30) <= 1e-10


# ---------------------------------------------------------------- T5 rigid translation

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("path", ["snapshot", "workflow"])
@pytest.mark.parametrize("functional", ["energy", "displacement_sum"])
def test_t5_rigid_translation(name, path, functional):
    xp = _xp(name)
    m, _W = _plate()
    W = np.tile([0.7, -0.4], (m.num_nodes, 1))

    def objective(t):
        r = _snapshot_solve(m, W, t) if path == "snapshot" else _workflow_solve(m, W, t).mechanics
        return r.physical_elastic_energy if functional == "energy" else xp.sum(r.displacement)

    value, grad = _gradient(name, objective)
    assert abs(grad) <= 1e-12 * abs(value)


# ---------------------------------------------------------------- T6 no temperature change

@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_t6_reduces_to_elasticity_without_temperature_change(name, plane):
    xp = _xp(name)
    m, W = _plate()
    tip = int(np.argmin(np.hypot(m.nodes[:, 0] - 1.0, m.nodes[:, 1] - 0.2)))
    left = np.asarray([int(i) for i in m.boundary["left"]])
    uniform = np.full(m.num_nodes, 290.0)
    elastic = dict(young_modulus=MATERIALS["young_modulus"], poisson_ratio=MATERIALS["poisson_ratio"], plane=plane,
                   dirichlet=_clamped_left(m), body_force=(0.0, -2.7e4), traction={"right": (1.0e6, -4.0e5)})
    for pick in (lambda r: r.displacement[tip, 1], lambda r: xp.sum(r.reaction[left, 0])):
        _v, d_thermo = _gradient(name, lambda t: pick(_snapshot_solve(m, W, t, plane, uniform, tref=290.0)))
        _v, d_elastic = _gradient(name, lambda t: pick(solve_elasticity(m, motion=MeshMotion(W, t), **elastic)))
        assert rel(d_thermo, d_elastic) <= 1e-12, (d_thermo, d_elastic)


# ---------------------------------------------------------------- T7 unchanged without motion

def _digest(r):
    fields = ("displacement", "total_strain", "thermal_strain", "elastic_strain", "stress", "sigma_zz", "epsilon_zz",
              "load_external", "load_thermal", "reaction", "residual")
    parts = [np.ascontiguousarray(getattr(r, f), dtype=float).tobytes() for f in fields]
    parts.append(np.float64(r.physical_elastic_energy).tobytes())
    return hashlib.sha256(b"".join(parts)).hexdigest()


def test_t7_unchanged_without_motion():
    # main e9bb438 and this branch give the same sha256 for these problems (measured 2026-11-10; HQ record)
    m, W = _plate()
    assert _digest(_snapshot_solve(m, W, None)) == _digest(solve_thermoelasticity(
        m, freeze_temperature(m, _plate_temperature(m)), reference_temperature_k=290.0, plane="stress",
        dirichlet=_clamped_left(m), body_force=(0.0, -2.7e4), traction={"right": (1.0e6, -4.0e5)}, **MATERIALS))
    hot = {int(i): 400.0 for i in m.boundary["right"]}
    cold = {int(i): 300.0 for i in m.boundary["left"]}
    plain = solve_steady_thermoelasticity(
        m, units=UNITS, conductivity={"host": 160.0, "core": 20.0}, thermal_dirichlet={**hot, **cold},
        heat_source={"host": 0.0, "core": 5e6}, plane="stress", reference_temperature_k=300.0,
        mechanical_dirichlet=_clamped_left(m), body_force=(0.0, -2.7e4), **MATERIALS)
    with_none = _workflow_solve(m, W, None)
    assert _digest(plain.mechanics) == _digest(with_none.mechanics)
    assert plain.manifest_json == with_none.manifest_json


# ---------------------------------------------------------------- T8 refusals

def test_t8_snapshot_refusals():
    xp = _xp("jax")
    m, W = _plate()
    t = xp.asarray(0.0)
    snap = freeze_temperature(m, _plate_temperature(m))
    common = dict(reference_temperature_k=290.0, plane="stress", dirichlet=_clamped_left(m), **MATERIALS)

    def call(**over):
        kw = {**common, **over}
        snapshot = kw.pop("snapshot", snap)
        return solve_thermoelasticity(m, snapshot, motion=MeshMotion(W, kw.pop("t", t)), **kw)

    with pytest.raises(TypeError, match="NumPy does not differentiate"):
        call(t=0.0)
    with pytest.raises(TypeError, match="reference_temperature_k is live"):
        call(reference_temperature_k=xp.asarray(290.0))
    with pytest.raises(ValueError, match="reference_temperature_k is a callback; with a motion it must be a finite nonnegative"):
        call(reference_temperature_k=lambda: 290.0)
    with pytest.raises(TypeError, match="thermal_expansion_per_k is live"):
        call(thermal_expansion_per_k={"host": xp.asarray(2.3e-5), "core": 1.2e-5})
    with pytest.raises(ValueError, match="thermal_expansion_per_k is a callback; with a motion it must be a finite real scalar"):
        call(thermal_expansion_per_k=lambda p: 1e-5)
    with pytest.raises(TypeError, match="young_modulus is live"):
        call(young_modulus=xp.asarray(70e9))
    with pytest.raises(TypeError, match="poisson_ratio is live"):
        call(poisson_ratio=xp.asarray(0.3))
    with pytest.raises(TypeError, match="body_force is live"):
        call(body_force=(0.0, xp.asarray(-1.0)))
    with pytest.raises(TypeError, match="body_force is a callback"):
        call(body_force=lambda p: np.zeros((len(p), 2)))
    with pytest.raises(TypeError, match=r"traction\['right'\] is live"):
        call(traction={"right": (xp.asarray(1.0), 0.0)})
    with pytest.raises(TypeError, match=r"traction\['right'\] is a callback"):
        call(traction={"right": lambda p, n: np.zeros((len(p), 2))})
    with pytest.raises(TypeError, match="Dirichlet displacement is live"):
        call(dirichlet={**_clamped_left(m), (int(m.boundary["right"][0]), 0): xp.asarray(1e-3)})
    with pytest.raises(TypeError, match="Dirichlet displacement is a callback; with a motion this slice takes"):
        call(dirichlet={**_clamped_left(m), (int(m.boundary["right"][0]), 0): lambda: 1e-3})
    with pytest.raises(TypeError, match="thermal_expansion_per_k is a callback; with a motion this slice takes"):
        call(thermal_expansion_per_k={"host": lambda: 2.3e-5, "core": 1.2e-5})
    with pytest.raises(ValueError, match="young_modulus is a callback; with a motion it must be"):
        call(young_modulus=lambda: 70e9)
    with pytest.raises(ValueError, match="stale or mismatched mesh"):
        call(snapshot=freeze_temperature(_moved(m, W, 0.01), _plate_temperature(m)))
    lo, hi = __import__("galerkin.shape", fromlist=["admissible_interval"]).admissible_interval(m, W)
    with pytest.raises(ElementInversion):
        call(t=xp.asarray(hi * 1.01))


def test_t8_workflow_refusals():
    xp = _xp("jax")
    m, W = _plate()
    t = xp.asarray(0.0)
    hot = {int(i): 400.0 for i in m.boundary["right"]}
    cold = {int(i): 300.0 for i in m.boundary["left"]}
    common = dict(units=UNITS, conductivity=160.0, thermal_dirichlet={**hot, **cold}, plane="stress",
                  reference_temperature_k=300.0, mechanical_dirichlet=_clamped_left(m), **MATERIALS)

    def call(**over):
        kw = {**common, **over}
        return solve_steady_thermoelasticity(m, motion=MeshMotion(W, kw.pop("t", t)), **kw)

    with pytest.raises(TypeError, match="NumPy does not differentiate"):
        call(t=0.0)
    with pytest.raises(TypeError, match="heat_source is a callback"):
        call(heat_source=lambda p: np.zeros(len(p)))
    with pytest.raises(TypeError, match="heat_source is live"):
        call(heat_source=xp.asarray(1e5))
    with pytest.raises(TypeError, match="conductivity is live"):
        call(conductivity=xp.asarray(160.0))
    with pytest.raises(TypeError, match="Dirichlet temperature is live"):
        call(thermal_dirichlet={**hot, **cold, int(m.boundary["top"][3]): xp.asarray(350.0)})
    with pytest.raises(ValueError, match="thermal_dirichlet must map"):
        call(thermal_dirichlet=[(0, 300.0)])
    with pytest.raises(TypeError, match="body_force is a callback"):
        call(body_force=lambda p: np.zeros((len(p), 2)))
    with pytest.raises(TypeError, match="reference_temperature_k is live"):
        call(reference_temperature_k=xp.asarray(300.0))
    with pytest.raises(TypeError, match="young_modulus is live"):
        call(young_modulus=xp.asarray(70e9))


def test_t8_jax_without_x64_is_named():
    jax = _jax()
    m, W = _plate()
    jax.config.update("jax_enable_x64", False)
    try:
        with pytest.raises(ValueError, match="galerkin needs float64"):
            _snapshot_solve(m, W, jax.numpy.asarray(0.0))
    finally:
        jax.config.update("jax_enable_x64", True)
