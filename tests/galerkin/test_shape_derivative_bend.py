# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives of bent waveguide modes (ModalPML + Bend, 2026-11-22); lengths in micrometres.

BD1-BD6 were pre-registered in the HQ work record (2026-11-22) before the implementation ran:
BD1 the motion's n_eff equal the ordinary bend solve on the moved mesh (relative 1e-12); BD2 on
the bent slab of test_pml_modes (radius 2 um), the complex dn_eff/dt of a film-thickness motion
equals a Richardson central difference of moved-mesh public solves within 1e-7; BD3 JAX and
PyTorch agree within 1e-12; BD4 against the Bessel-Hankel pole of the bent film, differentiated
in its thickness: the complex error falls on meshes 0.04, 0.02 and 0.01 and is within 2e-2 on the
finest, the imaginary part within 5e-2; BD5 a velocity on a PML node or normal to an outer face
is refused; BD6 without a motion, motion=None equals no keyword bit for bit.
"""

from __future__ import annotations

import hashlib
import math
import warnings

import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.shape import MeshMotion
from galerkin.waveguide import Bend, ModalPML, solve_waveguide_modes

K0 = 2 * math.pi / 1.55
N_SI, N_OX, RADIUS, FILM = 3.48, 1.444, 2.0, 0.22
BEND = Bend(bend_radius=RADIUS, bend_origin=0.0, bend_axis="x")


def _derivative(name, function):
    """d function / dt at t = 0 for a complex scalar function, as a Python complex."""
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        t = jax.numpy.asarray(0.0, dtype=jax.numpy.float64)
        return complex(float(jax.grad(lambda s: jax.numpy.real(function(s)))(t)),
                       float(jax.grad(lambda s: jax.numpy.imag(function(s)))(t)))
    torch = pytest.importorskip("torch")
    out = []
    for part in (torch.real, torch.imag):
        t = torch.tensor(0.0, dtype=torch.float64, requires_grad=True)
        part(function(t)).backward()
        out.append(float(t.grad))
    return complex(*out)


def _bent_slab(step):
    """test_pml_modes.measure_bend's mesh: the film 0 < x < 0.22 bent about x = -RADIUS... in its own frame
    (bend_origin 0, radius 2), PML on both sides; W moves the film's outer face, not its inner one."""
    inner, thick, outer = min(1.2, RADIUS * .6), min(.6, RADIUS * .3), max(3., RADIUS * 1.2)
    breaks = [-inner - thick, -inner, 0, FILM, FILM + outer, FILM + outer + 1.]
    x = np.concatenate([np.linspace(a, b, int(np.ceil((b - a) / step)) + 1)[:-1]
                        for a, b in zip(breaks[:-1], breaks[1:])] + [[breaks[-1]]])
    m = rectangle_mesh(len(x) - 1, .05, len(x) - 1, max(2, int(np.ceil(.05 / step))))
    m.nodes[:, 0] = x[m.nodes[:, 0].astype(int)]
    cent = m.nodes[m.triangles, 0].mean(axis=1)
    eps = np.where((cent > 0) & (cent < FILM), N_SI ** 2, N_OX ** 2)
    xn = m.nodes[:, 0]
    W = np.zeros((m.num_nodes, 2))
    W[:, 0] = np.where((xn >= 0) & (xn <= FILM), xn / FILM,
                       np.where((xn > FILM) & (xn <= FILM + outer), (FILM + outer - xn) / outer, 0.0))
    pml = ModalPML(pml_thickness={"left": thick, "right": 1.0})
    fixed = np.unique(np.concatenate([m.boundary[s] for s in ("left", "right", "top", "bottom")]))
    return m, eps, W, pml, fixed


def _solve(mesh, eps, pml, fixed, motion=None, bend=BEND):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return solve_waveguide_modes(mesh, relative_permittivity=eps, vacuum_angular_wavenumber=K0,
                                     target_effective_index=3.01, search_mode_count=6, pec_nodes=fixed, pml=pml,
                                     bend=bend, motion=motion)


def _moved(mesh, W, h):
    return Mesh(mesh.nodes + h * W, mesh.triangles, mesh.boundary, mesh.boundary_edges)


def _cylindrical_root(film):
    """The TE Bessel-Hankel pole of test_pml_modes.cylindrical_root with the film film um thick
    (kernel convention exp(+i omega t)), at 40 digits."""
    mp = pytest.importorskip("mpmath")
    with mp.workdps(40):
        def residual(n):
            nu = K0 * RADIUS * n

            def col(kind, index, r):
                f = {'J': mp.besselj, 'Y': mp.bessely, 'H': mp.hankel2}[kind]
                arg = K0 * index * r
                return mp.matrix([f(nu, arg), K0 * index * (f(nu - 1, arg) - f(nu + 1, arg)) / 2])
            inner = col('J', N_OX, RADIUS)
            a, b = col('J', N_SI, RADIUS), col('Y', N_SI, RADIUS)
            coeff = mp.lu_solve(mp.matrix([[a[0], b[0]], [a[1], b[1]]]), inner / inner[0])
            a, b = col('J', N_SI, RADIUS + film), col('Y', N_SI, RADIUS + film)
            state = coeff[0] * a + coeff[1] * b
            outer = col('H', N_OX, RADIUS + film)
            return state[1] - outer[1] / outer[0] * state[0]
        return mp.findroot(residual, (2.99 - .001j, 3.0 - .002j), tol=mp.mpf('1e-30'), maxsteps=50)


def _analytic_slope():
    mp = pytest.importorskip("mpmath")
    with mp.workdps(40):
        h = mp.mpf('1e-8')
        film = mp.mpf(FILM)
        return complex(np.conj(complex((_cylindrical_root(film + h) - _cylindrical_root(film - h)) / (2 * h))))


def _mode(modes, expected):
    n = np.asarray(modes.effective_index)
    return int(np.argmin(np.abs(n - expected)))


# ---------------------------------------------------------------- BD1-BD3

@pytest.fixture(scope="module")
def slab():
    m, eps, W, pml, fixed = _bent_slab(.02)
    expected = complex(np.conj(complex(_cylindrical_root(FILM))))
    mode = _mode(_solve(m, eps, pml, fixed), expected)

    def n_at(h):
        return complex(np.asarray(_solve(_moved(m, W, h), eps, pml, fixed).effective_index)[mode])

    def central(s):
        return (n_at(s) - n_at(-s)) / (2 * s)
    fd = (4 * central(1e-3) - central(2e-3)) / 3
    return m, eps, W, pml, fixed, mode, fd


@pytest.mark.parametrize("name", ["jax", "torch"])
def test_bd1_the_motion_keeps_the_moved_mesh_numbers(slab, name):
    m, eps, W, pml, fixed, mode, _fd = slab
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        t = jax.numpy.asarray(0.01)
    else:
        torch = pytest.importorskip("torch")
        t = torch.tensor(0.01, dtype=torch.float64)
    n = _solve(m, eps, pml, fixed, MeshMotion(design_velocity=W, t=t)).effective_index
    n = np.asarray(n.detach() if hasattr(n, "detach") else n)
    # The reference is the ordinary bend solve on the moved mesh, polished by the motion path's own
    # bordered Newton step (the same solve with a zero velocity): residual <= 2e-13 (measured 1.2e-13;
    # the eigensolver's raw numbers reach 3.2e-13, and on PML candidates differ from the polished ones
    # by up to 1.85e-12, the first BD1 measurement, kept in the HQ record).
    zero = np.zeros_like(W)
    moved = _moved(m, W, 0.01)
    reference = _solve(moved, eps, pml, fixed, MeshMotion(design_velocity=zero, t=t * 0)).effective_index
    reference = np.asarray(reference.detach() if hasattr(reference, "detach") else reference)
    assert np.max(np.abs(n - reference)) <= 1e-12 * np.max(np.abs(reference))


def test_bd2_bd3_derivative_against_moved_meshes(slab):
    m, eps, W, pml, fixed, mode, fd = slab
    slopes = {name: _derivative(name, lambda t: _solve(m, eps, pml, fixed, MeshMotion(design_velocity=W, t=t))
                                .effective_index[mode]) for name in ("jax", "torch")}
    assert abs(slopes["jax"] - fd) <= 1e-7 * abs(fd), (slopes["jax"], fd)                       # BD2
    assert abs(slopes["torch"] - slopes["jax"]) <= 1e-12 * abs(slopes["jax"])                   # BD3


# ---------------------------------------------------------------- BD4 the Bessel-Hankel pole

def test_bd4_bent_film_against_the_bessel_hankel_pole():
    exact = _analytic_slope()
    expected = complex(np.conj(complex(_cylindrical_root(FILM))))
    slopes = []
    for step in (.04, .02, .01):
        m, eps, W, pml, fixed = _bent_slab(step)
        mode = _mode(_solve(m, eps, pml, fixed), expected)
        slopes.append(_derivative("jax", lambda t: _solve(m, eps, pml, fixed, MeshMotion(design_velocity=W, t=t))
                                  .effective_index[mode]))
    errors = [abs(s - exact) / abs(exact) for s in slopes]
    assert errors[0] > errors[1] > errors[2], (errors, slopes, exact)
    assert errors[-1] <= 2e-2, (errors, slopes, exact)
    assert abs(slopes[-1].imag - exact.imag) <= 5e-2 * abs(exact.imag), (slopes[-1], exact)


# ---------------------------------------------------------------- BD5, BD6

def test_bd5_refusals(slab):
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    m, eps, W, pml, fixed, _mode_index, _fd = slab
    t = jax.numpy.asarray(0.0)
    in_layer = W.copy()
    node = int(np.argmin(np.abs(m.nodes[:, 0] - (m.nodes[:, 0].min() + 0.1))))       # inside the left PML
    in_layer[node, 0] = 0.1
    with pytest.raises(ValueError, match="PML or bend elements"):
        _solve(m, eps, pml, fixed, MeshMotion(design_velocity=in_layer, t=t))
    across = W.copy()
    top = np.asarray(m.boundary["top"], dtype=int)
    film_top = top[(m.nodes[top, 0] > 0.05) & (m.nodes[top, 0] < 0.2)]
    across[film_top, 1] = 0.1
    with pytest.raises(ValueError, match="of the top face along its normal"):
        _solve(m, eps, pml, fixed, MeshMotion(design_velocity=across, t=t))


def test_bd6_unchanged_without_motion(slab):
    m, eps, _W, pml, fixed, _mode_index, _fd = slab

    def digest(modes):
        return hashlib.sha256(b"".join(np.ascontiguousarray(np.asarray(a)).tobytes() for a in (
            modes.effective_index, modes.unnormalized_electric_field_line_integral,
            modes.unnormalized_electric_field_z))).hexdigest()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        without = solve_waveguide_modes(m, relative_permittivity=eps, vacuum_angular_wavenumber=K0,
                                        target_effective_index=3.01, search_mode_count=6, pec_nodes=fixed, pml=pml,
                                        bend=BEND)
    assert digest(_solve(m, eps, pml, fixed)) == digest(without)
