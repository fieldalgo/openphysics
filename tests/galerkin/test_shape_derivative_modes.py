# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of waveguide modes (galerkin.shape, sixth slice).

W1-W8 are the checks pre-registered before the implementation (HQ record,
2026-11-11); their tolerances, and W2's mesh levels, are fixed there and are not
loosened here. W3 compares with values stored from an independent finite-difference
mode solver (modesolverpy 0.4.4, MIT); it was measured before the registration and
records that measurement (HQ record, 2026-11-11).
"""

from __future__ import annotations

import hashlib
import math
import warnings

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import ElementInversion, MeshMotion, admissible_interval, extend_velocity
from galerkin.waveguide import DegenerateModeWarning, solve_modes

BACKENDS = ["jax", "torch"]
LAMBDA, N_CORE, N_CLAD = 1.55, 3.48, 1.444
K0 = 2 * math.pi / LAMBDA


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

def _strip(size, width=0.5, height=0.22):
    """A silicon strip in silica, its width as the design parameter (geometry engine node velocities)."""
    from meshine import generate

    from galerkin.interop import from_mesher
    from simcase.geometry_velocity import design_velocity
    doc = {"openphysics": "0.3",
           "geometry": {"version": 1, "parameters": {"w": {"value": f"{width!r} um"}}, "components": {"xs": {
               "dimension": "2d", "length_unit": "um", "depth": None,
               "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.0, "ymax": 1.0},
               "background": {"material": "clad"},
               "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": -height / 2, "w": "w",
                             "h": height, "material": "core"}]}}}}
    dv = design_velocity(doc, "w")
    domain, namer, _ = dv.complex.to_domain(size)
    tm = generate(domain, namer)
    nv = dv.node_velocity(tm)
    mesh = from_mesher(tm)
    W = extend_velocity(mesh, nv.values, nv.on_curve)
    core = np.array([mesh.region_names[r] == "core" for r in mesh.regions])
    return mesh, W, core


def _eps(core, core_eps=N_CORE ** 2):
    return np.where(core, core_eps, N_CLAD ** 2)


def _field_fraction(et, ez, xp):
    """A gauge-free field quantity: the longitudinal share of the coefficient norm."""
    longitudinal = xp.sum(xp.abs(ez) ** 2)
    return longitudinal / (longitudinal + xp.sum(xp.abs(et) ** 2))


# ---------------------------------------------------------------- W1 discrete consistency

@pytest.fixture(scope="module")
def strip():
    return _strip(0.08)


# a real problem has a real n_eff, so its imaginary part is checked for the lossy core only (the
# installed-wheel run refuses skipped tests, so the combination is not generated at all)
W1_CASES = [(material, functional) for material in ("real", "lossy")
            for functional in ("n_eff_real", "n_eff_imag", "field")
            if not (material == "real" and functional == "n_eff_imag")]


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("mode", [0, 1])
@pytest.mark.parametrize("material, functional", W1_CASES)
def test_w1_matches_moved_mesh_central_difference(strip, name, material, mode, functional):
    xp = _xp(name)
    mesh, W, core = strip
    eps = _eps(core, N_CORE ** 2 if material == "real" else N_CORE ** 2 - 0.05j)

    def pick(result, lib):
        n_eff, _space, et, ez = result
        if functional == "field":
            return _field_fraction(et[mode], ez[mode], lib)
        return lib.real(n_eff[mode]) if functional == "n_eff_real" else lib.imag(n_eff[mode])

    def solve(m, t=None):
        return solve_modes(m, eps, K0, N_CORE, num_modes=2, motion=None if t is None else MeshMotion(W, t))

    value, grad = _gradient(name, lambda t: pick(solve(mesh, t), xp))
    # Deviation from the pre-registered plain central difference (HQ record 2026-11-11): the reference
    # is its Richardson extrapolation from h = 1e-4 and h/2 (fourth order). The plain one at h = 1e-4
    # has truncation error 1.5e-6 for Im n_eff of the lossy mode 0, whose second derivative is large;
    # its h sweep (1e-2 .. 1e-4) converges to the AD value, and the extrapolated one agrees to 6.1e-10.
    # The criterion (1e-6) is unchanged.
    h = 1e-4

    def central(step):
        return (float(pick(solve(_moved(mesh, W, step)), np)) - float(pick(solve(_moved(mesh, W, -step)), np))) / (2 * step)
    fd = (4 * central(h / 2) - central(h)) / 3
    assert value == pytest.approx(float(pick(solve(mesh), np)), rel=1e-10)
    assert rel(grad, fd) <= 1e-6, (grad, fd)


# ---------------------------------------------------------------- W2 hollow PEC guide, TE10

@pytest.mark.parametrize("name", BACKENDS)
def test_w2_hollow_rectangular_guide_width(name):
    xp = _xp(name)
    a, lam = 1.0, 1.5
    k0 = 2 * math.pi / lam
    n_exact = math.sqrt(1 - (lam / (2 * a)) ** 2)
    exact = lam ** 2 / (4 * a ** 3 * n_exact)
    errors, levels = [], (8, 16, 32)                                              # pre-registered nx
    for nx in levels:
        mesh = rectangle_mesh(a, a / 2, nx, nx // 2)
        W = np.stack([mesh.nodes[:, 0] / a, np.zeros(mesh.num_nodes)], axis=1)  # stretch: da = 1

        def n_eff(t):
            return xp.real(solve_modes(mesh, 1.0, k0, n_exact, num_modes=1, motion=MeshMotion(W, t))[0][0])

        _v, grad = _gradient(name, n_eff)
        errors.append(rel(grad, exact))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(2.0) for i in range(2)]
    assert min(orders) >= 1.0, (errors, orders)
    assert errors[-1] <= 1e-2, errors


# ---------------------------------------------------------------- W3 independent mode solver (stored)

# modesolverpy 0.4.4 (MIT), fully vectorial finite differences, area-averaged permittivity,
# grid 0.005 um, central difference of n_eff over w = 0.5 +- 0.01 um (whole cells). Python 3.11,
# NumPy 1.26.4, SciPy 1.10.1 (it needs these; it is not run here). Measured 2026-11-11 (HQ record).
MODESOLVERPY_DNDW = 1.566258637210316


@pytest.mark.parametrize("name", ["jax"])
def test_w3_strip_width_against_modesolverpy(name):
    xp = _xp(name)
    mesh, W, core = _strip(0.02)
    _v, grad = _gradient(name, lambda t: xp.real(
        solve_modes(mesh, _eps(core), K0, N_CORE, num_modes=1, motion=MeshMotion(W, t))[0][0]))
    assert rel(grad, MODESOLVERPY_DNDW) <= 3e-2, grad


# ---------------------------------------------------------------- W4 rigid translation

@pytest.mark.parametrize("name", BACKENDS)
def test_w4_rigid_translation(strip, name):
    xp = _xp(name)
    mesh, _W, core = strip
    W = np.tile([0.7, -0.4], (mesh.num_nodes, 1))
    value, grad = _gradient(name, lambda t: xp.real(
        solve_modes(mesh, _eps(core), K0, N_CORE, num_modes=1, motion=MeshMotion(W, t))[0][0]))
    assert abs(grad) <= 1e-10 * abs(value)


# ---------------------------------------------------------------- W5 uniform scaling

@pytest.mark.parametrize("name", BACKENDS)
def test_w5_uniform_scaling_equals_wavenumber_derivative(strip, name):
    xp = _xp(name)
    mesh, _W, core = strip
    eps = _eps(core)
    W = mesh.nodes.copy()                                                         # X(t) = (1 + t) X0
    _v, d_scale = _gradient(name, lambda t: xp.real(
        solve_modes(mesh, eps, K0, N_CORE, num_modes=1, motion=MeshMotion(W, t))[0][0]))
    _v, d_k0 = _gradient(name, lambda k: xp.real(solve_modes(mesh, eps, k, N_CORE, num_modes=1)[0][0]), K0)
    assert rel(d_scale, K0 * d_k0) <= 1e-8, (d_scale, K0 * d_k0)


# ---------------------------------------------------------------- W6 degenerate modes

def _crisscross(length, cells):
    """[0, L]^2 with every cell split into four triangles at its centre: the square's full symmetry."""
    xs = np.linspace(0.0, length, cells + 1)
    corners = np.array([(x, y) for y in xs for x in xs])
    centres = np.array([((xs[i] + xs[i + 1]) / 2, (xs[j] + xs[j + 1]) / 2) for j in range(cells) for i in range(cells)])
    triangles = []
    for j in range(cells):
        for i in range(cells):
            a, b = j * (cells + 1) + i, j * (cells + 1) + i + 1
            c, d = (j + 1) * (cells + 1) + i + 1, (j + 1) * (cells + 1) + i
            m = (cells + 1) ** 2 + j * cells + i
            triangles += [[a, b, m], [b, c, m], [c, d, m], [d, a, m]]
    nodes = np.vstack([corners, centres])
    wall = np.flatnonzero((np.isclose(nodes, 0.0) | np.isclose(nodes, length)).any(axis=1))
    return Mesh(nodes, np.array(triangles), {"wall": wall})


@pytest.mark.parametrize("name", BACKENDS)
def test_w6_degenerate_modes_get_nan_derivatives(name):
    xp = _xp(name)
    mesh = _crisscross(3.0, 60)
    core = np.all(np.abs(mesh.nodes[mesh.triangles] - 1.5) <= 0.15 + 1e-9, axis=(1, 2))   # 0.3 x 0.3, centred
    eps = _eps(core)
    x = mesh.nodes[:, 0]
    W = np.stack([np.clip(x - 1.5, -0.15, 0.15) / 0.3 * np.clip((1.5 - np.abs(x - 1.5)) / 1.2 + 0.2, 0, 1),
                  np.zeros(mesh.num_nodes)], axis=1)                              # widens the core
    W[np.isclose(x, 0.0) | np.isclose(x, 3.0)] = 0.0
    n_eff = solve_modes(mesh, eps, K0, N_CORE, num_modes=3)[0]
    assert abs(n_eff[0] - n_eff[1]) <= 1e-12 * abs(n_eff[0])                     # the pair, by symmetry
    grads = []
    for mode in range(3):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _v, grad = _gradient(name, lambda t: xp.real(
                solve_modes(mesh, eps, K0, N_CORE, num_modes=3, motion=MeshMotion(W, t))[0][mode]))
        assert any(issubclass(w.category, DegenerateModeWarning) for w in caught)
        grads.append(grad)
    assert math.isnan(grads[0]) and math.isnan(grads[1])
    assert math.isfinite(grads[2])


# ---------------------------------------------------------------- W7 unchanged without motion

def _digest(result):
    n_eff, _space, et, ez = result
    return hashlib.sha256(b"".join(np.ascontiguousarray(a).tobytes() for a in (n_eff, et, ez))).hexdigest()


def test_w7_unchanged_without_motion(strip):
    # main e6c5826 and this branch give the same sha256 for these problems (measured 2026-11-11; HQ record)
    mesh, _W, core = strip
    for eps in (_eps(core), _eps(core, N_CORE ** 2 - 0.05j)):
        assert _digest(solve_modes(mesh, eps, K0, N_CORE, num_modes=2)) == _digest(
            solve_modes(mesh, eps, K0, N_CORE, num_modes=2, motion=None))


# ---------------------------------------------------------------- W8 refusals

def test_w8_refusals(strip):
    xp = _xp("jax")
    mesh, W, core = strip
    t = xp.asarray(0.0)
    eps = _eps(core)
    with pytest.raises(TypeError, match="NumPy does not differentiate"):
        solve_modes(mesh, eps, K0, N_CORE, motion=MeshMotion(W, 0.0))
    with pytest.raises(TypeError, match="eps_r is live"):
        solve_modes(mesh, xp.asarray(eps), K0, N_CORE, motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="mu_r is live"):
        solve_modes(mesh, eps, K0, N_CORE, mu_r=xp.asarray(1.0), motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="k0 is live"):
        solve_modes(mesh, eps, xp.asarray(K0), N_CORE, motion=MeshMotion(W, t))
    with pytest.raises(TypeError, match="eps_r must be a number or a per-element array"):
        solve_modes(mesh, lambda p: 1.0, K0, N_CORE, motion=MeshMotion(W, t))
    with pytest.raises(ValueError, match="coordinate_factors .* refused with a motion"):
        solve_modes(mesh, eps, K0, N_CORE, coordinate_factors=np.ones((mesh.num_triangles, 3)),
                    motion=MeshMotion(W, t))
    _lo, hi = admissible_interval(mesh, W)
    with pytest.raises(ElementInversion):
        solve_modes(mesh, eps, K0, N_CORE, motion=MeshMotion(W, xp.asarray(hi * 1.01)))


def test_w8_jax_without_x64_is_named(strip):
    jax = _jax()
    mesh, W, core = strip
    jax.config.update("jax_enable_x64", False)
    try:
        with pytest.raises(ValueError, match="galerkin needs float64"):
            solve_modes(mesh, _eps(core), K0, N_CORE, motion=MeshMotion(W, jax.numpy.asarray(0.0)))
    finally:
        jax.config.update("jax_enable_x64", True)
