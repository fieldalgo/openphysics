# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""galerkin.waveguide.degenerate_branch_derivatives: the branch slopes of degenerate modes.

The meshes are in micrometres and k0 in rad per micrometre (consistent units, as the 2026-11-11
comparison used), so the slopes are per micrometre of the motion's t.

Checks D1-D6, pre-registered in the HQ work record (2026-11-21) before the tests ran:
D1 on a symmetric square core the sorted branch slopes equal one-sided differences of the
sorted effective indices on both sides (Richardson) within 1e-6; D2 their sum equals the
central difference of the smooth sum within 1e-6; D3 a nondegenerate problem has no group;
D4 a degenerate mode without its partner is refused; D5 JAX and PyTorch agree within 1e-12;
D6 the square core of the 2026-11-11 comparison (geometry-engine node velocities, nearly
degenerate on its mesh) against that day's galerkin one-sided differences within 3 % and the
modesolverpy slopes within 5 %.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from galerkin.kernels import solve_modes
from galerkin.waveguide import degenerate_branch_derivatives
from galerkin.mesh import Mesh
from galerkin.shape import MeshMotion, extend_velocity

BACKENDS = ["jax", "torch"]
LAMBDA, N_CORE, N_CLAD = 1.55, 3.48, 1.444
K0 = 2 * math.pi / LAMBDA


def _t(name):
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        return jax.numpy.asarray(0.0, dtype=jax.numpy.float64)
    torch = pytest.importorskip("torch")
    return torch.tensor(0.0, dtype=torch.float64, requires_grad=True)


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


def _square():
    """The W6 problem: a 0.3 x 0.3 core centred in a 3 x 3 PEC box, widened in x by W."""
    mesh = _crisscross(3.0, 60)
    core = np.all(np.abs(mesh.nodes[mesh.triangles] - 1.5) <= 0.15 + 1e-9, axis=(1, 2))
    eps = np.where(core, N_CORE ** 2, N_CLAD ** 2)
    x = mesh.nodes[:, 0]
    W = np.stack([np.clip(x - 1.5, -0.15, 0.15) / 0.3 * np.clip((1.5 - np.abs(x - 1.5)) / 1.2 + 0.2, 0, 1),
                  np.zeros(mesh.num_nodes)], axis=1)
    W[np.isclose(x, 0.0) | np.isclose(x, 3.0)] = 0.0
    return mesh, eps, W


def _branches(mesh, eps, W, name, num_modes=3, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return degenerate_branch_derivatives(mesh, relative_permittivity=eps, vacuum_angular_wavenumber=K0,
                                             target_effective_index=N_CORE, search_mode_count=num_modes,
                                             motion=MeshMotion(design_velocity=W, t=_t(name)), **kw)


def _sorted_pair(mesh, eps, W, h):
    moved = Mesh(mesh.nodes + h * W, mesh.triangles, mesh.boundary)
    return np.sort(np.real(solve_modes(moved, eps, K0, N_CORE, num_modes=3)[0][:2]))[::-1]


@pytest.fixture(scope="module")
def square():
    return _square()


# ---------------------------------------------------------------- D1, D2, D5 on the symmetric square

def test_d1_d2_d5_branch_slopes_on_the_symmetric_square(square):
    mesh, eps, W = square
    jax_groups, torch_groups = _branches(mesh, eps, W, "jax"), _branches(mesh, eps, W, "torch")
    assert len(jax_groups) == 1 and jax_groups[0].mode_index == (0, 1)
    slopes = jax_groups[0].effective_index_derivative
    assert np.max(np.abs(torch_groups[0].effective_index_derivative - slopes)) <= 1e-12 * np.max(np.abs(slopes))      # D5
    n0 = _sorted_pair(mesh, eps, W, 0.0)

    def one_sided(h):                       # two Richardson levels of (n(h) - n0) / h
        d = {s: (_sorted_pair(mesh, eps, W, s) - n0) / s for s in (h, h / 2, h / 4)}
        r1, r2 = 2 * d[h / 2] - d[h], 2 * d[h / 4] - d[h / 2]
        return (4 * r2 - r1) / 3
    h = 5e-4
    plus, minus = one_sided(h), one_sided(-h)
    # sorted from above: for t > 0 the upper mode follows the steeper branch, for t < 0 the gentler one
    assert np.max(np.abs(plus / slopes - 1)) <= 1e-6, (plus, slopes)                               # D1
    assert np.max(np.abs(minus[::-1] / slopes - 1)) <= 1e-6, (minus, slopes)
    # the sum is smooth; a plain central difference at h = 5e-4 is 2.2e-6 off by truncation (measured),
    # so it is extrapolated once (Richardson on h and h / 2)
    def central(s):
        return (np.sum(_sorted_pair(mesh, eps, W, s)) - np.sum(_sorted_pair(mesh, eps, W, -s))) / (2 * s)
    total = (4 * central(h / 2) - central(h)) / 3
    assert abs(np.sum(slopes) / total - 1) <= 1e-6, (np.sum(slopes), total)                        # D2
    combos = jax_groups[0].mode_combination
    assert combos.shape == (2, 2) and abs(np.linalg.det(combos)) > 1e-6


# ---------------------------------------------------------------- D3, D4

def test_d3_a_nondegenerate_problem_has_no_group():
    mesh = _crisscross(3.0, 30)
    core = np.all((np.abs(mesh.nodes[mesh.triangles][..., 0] - 1.5) <= 0.25 + 1e-9)
                  & (np.abs(mesh.nodes[mesh.triangles][..., 1] - 1.5) <= 0.1 + 1e-9), axis=1)    # 0.5 x 0.2
    eps = np.where(core, N_CORE ** 2, N_CLAD ** 2)
    _m, _e, W = _square()
    W = np.zeros((mesh.num_nodes, 2))
    W[:, 0] = np.clip(mesh.nodes[:, 0] - 1.5, -0.25, 0.25) * 0.1
    assert _branches(mesh, eps, W, "jax", num_modes=2) == []


def test_d4_a_partner_that_was_not_returned_is_refused(square):
    mesh, eps, W = square
    with pytest.raises(ValueError, match="degenerate with a mode that was not returned; ask for more modes"):
        _branches(mesh, eps, W, "jax", num_modes=1)
    with pytest.raises(ValueError, match="relative_tolerance must lie in"):
        _branches(mesh, eps, W, "jax", relative_tolerance=0.0)


# ---------------------------------------------------------------- D6 the 2026-11-11 comparison

def test_d6_the_measured_branch_slopes_of_2026_11_11():
    """0.3 x 0.3 um Si in SiO2, 3 x 3 um PEC box, 1.55 um, mesh 0.02 um, width w = h moved by the
    geometry engine's node velocities. Its mesh splits the pair by 3.1e-5 (measured 2026-11-11),
    so the group takes tolerance 1e-4. That day's one-sided differences (Delta w 0.02 and 0.01
    um): galerkin 5.70-5.82 and 2.276-2.283 per um, modesolverpy 5.53-5.63 and 2.251-2.254."""
    pytest.importorskip("jax")
    from meshine import generate

    from galerkin.interop import from_mesher
    from simcase.geometry_velocity import design_velocity
    doc = {"openphysics": "0.3", "geometry": {"version": 1, "parameters": {"w": {"value": "0.3 um"}}, "components": {
        "xs": {"dimension": "2d", "length_unit": "um", "depth": None,
               "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.5, "ymax": 1.5}, "background": {"material": "clad"},
               "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": -0.15, "w": "w", "h": 0.3,
                             "material": "core"}]}}}}
    dv = design_velocity(doc, "w")
    domain, namer, _ = dv.complex.to_domain(0.02)
    tm = generate(domain, namer)
    nv = dv.node_velocity(tm)
    mesh = from_mesher(tm)
    W = extend_velocity(mesh, nv.values, nv.on_curve)
    eps = np.array([N_CORE ** 2 if mesh.region_names[r] == "core" else N_CLAD ** 2 for r in mesh.regions])
    (group,) = _branches(mesh, eps, W, "jax", num_modes=2, relative_tolerance=1e-4)
    steep, gentle = group.effective_index_derivative
    assert 5.70 * 0.97 <= steep <= 5.82 * 1.03 and 2.276 * 0.97 <= gentle <= 2.283 * 1.03, (steep, gentle)
    assert 5.53 * 0.95 <= steep <= 5.63 * 1.05 and 2.251 * 0.95 <= gentle <= 2.254 * 1.05, (steep, gentle)
