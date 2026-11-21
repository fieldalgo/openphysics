# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of waveguide modes with a modal PML (2026-11-21); lengths in micrometres.

P1-P7 were pre-registered in the HQ work record (2026-11-21) before the implementation ran:
P1 the motion's n_eff equal the ordinary PML solve on the moved mesh (relative 1e-12); P2 on a
strip in a PML window, dn_eff/dt (complex) of a core-width motion equals a Richardson central
difference of moved-mesh solves within 1e-7; P3 JAX and PyTorch agree within 1e-12; P4 a design
velocity on a node of a PML element, and a motion with a bend, are refused by name; P5 without a
motion the PML solve is unchanged (motion=None equals no keyword, bit for bit); P6 the outgoing
(leaky) slab pole of test_pml_modes, differentiated in the first core thickness, against the
derivative of the analytic root: the complex error falls on meshes 0.04, 0.02, 0.01 and is within
2e-2 on the finest, its imaginary part within 5e-2; P7 the same derivative on mesh 0.02 changes by
at most 1e-2 for PML thicknesses 0.75 and 1.5 and strengths 2 and 6.
"""

from __future__ import annotations

import hashlib
import math
import warnings

import numpy as np
import pytest
from scipy.optimize import root

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import MeshMotion
from galerkin.waveguide import Bend, ModalPML, solve_waveguide_modes

BACKENDS = ["jax", "torch"]
K0 = 2 * math.pi / 1.55
N_SI, N_OX = 3.48, 1.444


def _t(name, value=0.0):
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        return jax.numpy.asarray(value, dtype=jax.numpy.float64)
    torch = pytest.importorskip("torch")
    return torch.tensor(value, dtype=torch.float64, requires_grad=True)


def _derivative(name, function):
    """d function / dt at t = 0 for a complex scalar function, as a Python complex."""
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        t = jax.numpy.asarray(0.0, dtype=jax.numpy.float64)
        re = jax.grad(lambda s: jax.numpy.real(function(s)))(t)
        im = jax.grad(lambda s: jax.numpy.imag(function(s)))(t)
        return complex(float(re), float(im))
    torch = pytest.importorskip("torch")
    out = []
    for part in (torch.real, torch.imag):
        t = torch.tensor(0.0, dtype=torch.float64, requires_grad=True)
        part(function(t)).backward()
        out.append(float(t.grad))
    return complex(*out)


def _moved(mesh, W, h):
    return Mesh(mesh.nodes + h * W, mesh.triangles, mesh.boundary, mesh.boundary_edges)


def _quiet(call):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return call()


# ---------------------------------------------------------------- P1-P5 a strip in a PML window

PML = ModalPML(pml_thickness={"left": 0.5, "right": 0.5, "bottom": 0.5, "top": 0.5})


def _strip():
    """A 0.6 x 0.2 um Si strip in SiO2, a 3 x 2 um window, PML 0.5 um on every side; W widens the core
    and vanishes outside the physical window [0.5, 2.5] x [0.5, 1.5]."""
    mesh = rectangle_mesh(3.0, 2.0, 30, 20)
    cent = mesh.nodes[mesh.triangles].mean(axis=1)
    core = (np.abs(cent[:, 0] - 1.5) < 0.3) & (np.abs(cent[:, 1] - 1.0) < 0.1)
    eps = np.where(core, N_SI ** 2, N_OX ** 2)
    x, y = mesh.nodes[:, 0] - 1.5, mesh.nodes[:, 1] - 1.0
    wx = np.where(np.abs(x) <= 0.3, x / 0.3, np.sign(x) * np.clip((1.0 - np.abs(x)) / 0.7, 0, 1))
    wy = np.where(np.abs(y) <= 0.1, 1.0, np.clip((0.5 - np.abs(y)) / 0.4, 0, 1))
    W = np.stack([wx * wy, np.zeros(mesh.num_nodes)], axis=1)
    return mesh, eps, W


def _fundamental(mesh, eps, motion=None, pml=PML):
    modes = _quiet(lambda: solve_waveguide_modes(mesh, relative_permittivity=eps, vacuum_angular_wavenumber=K0,
                                                 target_effective_index=2.6, search_mode_count=4, pml=pml,
                                                 motion=motion))
    return modes


def _index_of(modes):
    n = modes.effective_index
    values = np.real(np.asarray(n.detach() if hasattr(n, "detach") else n))
    return int(np.argmax(values))


@pytest.fixture(scope="module")
def strip():
    mesh, eps, W = _strip()
    mode = _index_of(_fundamental(mesh, eps))

    def n_at(h):
        return complex(np.asarray(_fundamental(_moved(mesh, W, h), eps).effective_index)[mode])

    def central(s):
        return (n_at(s) - n_at(-s)) / (2 * s)
    h = 2e-3
    fd = (4 * central(h / 2) - central(h)) / 3
    return mesh, eps, W, mode, fd


@pytest.mark.parametrize("name", BACKENDS)
def test_p1_the_motion_keeps_the_moved_mesh_numbers(strip, name):
    mesh, eps, W, mode, _fd = strip
    live = _fundamental(mesh, eps, MeshMotion(design_velocity=W, t=_t(name, 0.01)))
    n = live.effective_index
    n = np.asarray(n.detach() if hasattr(n, "detach") else n)
    plain = np.asarray(_fundamental(_moved(mesh, W, 0.01), eps).effective_index)
    assert np.max(np.abs(n - plain)) <= 1e-12 * np.max(np.abs(plain))


def test_p2_p3_derivative_against_moved_meshes(strip):
    mesh, eps, W, mode, fd = strip
    slopes = {name: _derivative(name, lambda t: _fundamental(mesh, eps, MeshMotion(design_velocity=W, t=t))
                                .effective_index[mode]) for name in BACKENDS}
    assert abs(fd.imag) > 0
    assert abs(slopes["jax"] - fd) <= 1e-7 * abs(fd), (slopes["jax"], fd)                       # P2
    assert abs(slopes["torch"] - slopes["jax"]) <= 1e-12 * abs(slopes["jax"])                   # P3


def test_p4_refusals(strip):
    mesh, eps, W, _mode, _fd = strip
    t = _t("jax")
    into_layer = W.copy()
    into_layer[np.argmin(mesh.nodes[:, 0] + mesh.nodes[:, 1]), 0] = 0.1          # the corner (0, 0) lies in the PML
    with pytest.raises(ValueError, match=r"moves 1 node\(s\) of PML or bend elements"):
        _fundamental(mesh, eps, MeshMotion(design_velocity=into_layer, t=t))
    shifted = Mesh(mesh.nodes + np.array([4.0, 0.0]), mesh.triangles, mesh.boundary, mesh.boundary_edges)
    with pytest.raises(ValueError, match="a motion is refused with a bend"):
        _quiet(lambda: solve_waveguide_modes(shifted, relative_permittivity=eps, vacuum_angular_wavenumber=K0,
                                             target_effective_index=2.6, search_mode_count=4, pml=PML,
                                             bend=Bend(bend_radius=20.0, bend_origin=0.0), motion=MeshMotion(design_velocity=W, t=t)))


def test_p5_unchanged_without_motion(strip):
    mesh, eps, _W, _mode, _fd = strip

    def digest(modes):
        return hashlib.sha256(b"".join(np.ascontiguousarray(np.asarray(a)).tobytes() for a in (
            modes.effective_index, modes.unnormalized_electric_field_line_integral,
            modes.unnormalized_electric_field_z))).hexdigest()
    without = _quiet(lambda: solve_waveguide_modes(mesh, relative_permittivity=eps, vacuum_angular_wavenumber=K0,
                                                   target_effective_index=2.6, search_mode_count=4, pml=PML))
    assert digest(_fundamental(mesh, eps)) == digest(without)


# ---------------------------------------------------------------- P6, P7 the outgoing slab pole

def _outgoing_root(d1):
    """The TE outgoing pole of test_pml_modes with the first core d1 thick and the substrate still at
    x = 0.47 (the gap is 0.47 - d1), the geometry the motion below makes."""
    eps = np.array([N_OX ** 2, N_SI ** 2, N_OX ** 2, N_SI ** 2])

    def residual(z):
        n = complex(*z)
        q = np.sqrt((K0 ** 2 * (eps - n * n)).astype(complex))
        if q[0].imag > 0:
            q[0] = -q[0]
        if q[-1].real < 0:
            q[-1] = -q[-1]
        state = np.array([1., 1j * q[0]])
        for j, d in [(1, d1), (2, .47 - d1)]:
            c, s = np.cos(q[j] * d), np.sin(q[j] * d)
            state = np.array([[c, s / q[j]], [-q[j] * s, c]]) @ state
        r = state[1] + 1j * q[-1] * state[0]
        return [r.real, r.imag]
    r = root(residual, [2.85, -.01], tol=1e-13)
    assert r.success and np.linalg.norm(residual(r.x)) <= 1e-9
    return complex(*r.x)


def _analytic_slope():
    h = 1e-4
    return (_outgoing_root(0.22 + h) - _outgoing_root(0.22 - h)) / (2 * h)


def _slab(step, thickness=1.0):
    """test_pml_modes.slab_mesh: Si 0 < x < 0.22 and x > 0.47 (the substrate leaks), SiO2 between and left."""
    pad = 1.0
    breaks = [-pad - thickness, -pad, 0, .22, .47, .47 + pad, .47 + pad + thickness]
    x = np.concatenate([np.linspace(a, b, int(np.ceil((b - a) / step)) + 1)[:-1]
                        for a, b in zip(breaks[:-1], breaks[1:])] + [[breaks[-1]]])
    mesh = rectangle_mesh(len(x) - 1, .1, len(x) - 1, max(2, int(np.ceil(.1 / step))))
    mesh.nodes[:, 0] = x[mesh.nodes[:, 0].astype(int)]
    centers = mesh.nodes[mesh.triangles, 0].mean(axis=1)
    eps = np.where(((centers > 0) & (centers < .22)) | (centers > .47), N_SI ** 2, N_OX ** 2)
    xn = mesh.nodes[:, 0]
    W = np.zeros((mesh.num_nodes, 2))
    W[:, 0] = np.where((xn >= 0) & (xn <= .22), xn / .22, np.where((xn > .22) & (xn <= .47), (.47 - xn) / .25, 0))
    return mesh, eps, W


def _slab_slope(name, step, thickness=1.0, strength=3.0):
    mesh, eps, W = _slab(step, thickness)
    pml = ModalPML(pml_thickness={"left": thickness, "right": thickness}, pml_strength=strength)
    fixed = np.unique(np.concatenate([mesh.boundary[s] for s in ("left", "right", "top", "bottom")]))
    expected = _outgoing_root(0.22)

    def solve(motion=None):
        return _quiet(lambda: solve_waveguide_modes(
            mesh, relative_permittivity=eps, vacuum_angular_wavenumber=K0, target_effective_index=expected.real,
            search_mode_count=6, pec_nodes=fixed, pml=pml, motion=motion))
    # the public index follows exp(-i omega t), the analytic root exp(+i omega t): conjugate
    n = np.conj(np.asarray(solve().effective_index))
    mode = int(np.argmin(np.abs(n - expected)))
    return np.conj(_derivative(name, lambda t: solve(MeshMotion(design_velocity=W, t=t)).effective_index[mode]))


def test_p6_leaky_slab_against_the_analytic_root():
    exact = _analytic_slope()
    slopes = [_slab_slope("jax", step) for step in (.04, .02, .01)]
    errors = [abs(s - exact) / abs(exact) for s in slopes]
    assert errors[0] > errors[1] > errors[2], (errors, slopes, exact)
    assert errors[-1] <= 2e-2, (errors, slopes, exact)
    assert abs(slopes[-1].imag - exact.imag) <= 5e-2 * abs(exact.imag), (slopes[-1], exact)


def test_p7_the_slope_does_not_depend_on_the_layer():
    base = _slab_slope("jax", .02)
    for settings in (dict(thickness=.75), dict(thickness=1.5), dict(strength=2.0), dict(strength=6.0)):
        value = _slab_slope("jax", .02, **settings)
        assert abs(value - base) <= 1e-2 * abs(base), (settings, value, base)
