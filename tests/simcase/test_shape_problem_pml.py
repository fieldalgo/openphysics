# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simcase.shape_derivative on mode documents with a modal PML (2026-11-22).

Checks PM1-PM6, pre-registered in the HQ work record (2026-11-22) before the tests ran (PM1
corrected before running: the outer faces hold the normal component only): PM1 the problem is
built and W is exactly zero on every node of a stretched element and in the normal component on
the outer faces; PM2 the live n_eff at t = 0 equals run()'s within 1e-12; PM3 dn_eff/dd matches a
same-mesh central difference within 1e-6; PM4 JAX and PyTorch agree within 1e-12; PM5 the
outgoing TE pole of galerkin's leaky-slab check (gap 0.47 - d) gives dn/dd within 1e-2 on the
document's mesh; PM6 a bend and a design moving a point of the layer or an outer face are refused.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import root

from simcase import Document, DocumentError, run
from simcase.shape_derivative import shape_problem

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "simcase"
K0 = 2 * math.pi / 1.55          # rad/um
N_SI, N_OX = 3.48, 1.444


def _backend(name):
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
    else:
        pytest.importorskip("torch")


def leaky_slab(parameter="d"):
    """examples/simcase/pml_leaky_slab.json as a version 1 block: the film thickness d (or the
    height of a marker block inside the bottom PML) is a parameter; PML on the bottom and top, PEC
    all round."""
    raw = json.loads((EXAMPLES / "pml_leaky_slab.json").read_text())
    g = raw["geometry"]
    film, substrate = dict(g["shapes"][0]), dict(g["shapes"][1])
    params, features = {}, [film, substrate]
    if parameter == "d":
        film["h"], params["d"] = "d", {"value": "0.22 um"}
    else:      # a marker block wholly inside the bottom PML, its height the parameter
        features.append({"name": "marker", "type": "rect", "x": -0.03, "y": -1.8, "w": 0.06, "h": "marker_height",
                         "material": "film"})
        params["marker_height"] = {"value": "0.3 um"}
    comp = {"dimension": "2d", "length_unit": "um", "depth": None, "domain": g["domain"],
            "background": g["background"], "features": features}
    raw["geometry"] = {"version": 1, "parameters": params, "components": {"xs": comp}}
    return raw


def _complex_slope(problem, name):
    """d n_eff / dd (complex, per metre) of the first kept mode, under exp(-i omega t)."""
    if name == "jax":
        import jax.numpy as xp
    else:
        import torch as xp
    _v, re = problem.derivative(lambda r: xp.real(r["effective_index"][0]), backend=name)
    _v, im = problem.derivative(lambda r: xp.imag(r["effective_index"][0]), backend=name)
    return complex(re, im)


@pytest.fixture(scope="module")
def problem():
    _backend("jax")
    return shape_problem(leaky_slab(), "d")


# ---------------------------------------------------------------- PM1, PM2

def test_pm1_the_layer_and_the_window_edges_stay_in_place(problem):
    from simcase.physics_pml_modes import coordinates
    mesh = problem.arguments["mesh"]
    c = coordinates(mesh, problem.arguments["inputs"].pml)
    stretched = np.unique(mesh.triangles[np.any(c.factors != 1, axis=1)])
    W = problem.design_velocity
    assert len(stretched) and np.all(W[stretched] == 0.0)
    for axis, faces in ((0, ("left", "right")), (1, ("bottom", "top"))):
        for face in faces:
            assert np.all(W[mesh.boundary[face], axis] == 0.0), face
    assert np.any(W != 0.0)


def test_pm2_the_live_index_at_zero_is_runs(problem):
    import jax.numpy as jnp
    ran = run(Document.from_dict(leaky_slab()), verbose=False)
    live = complex(np.asarray(problem.solve(jnp.asarray(0.0, dtype=jnp.float64))["effective_index"])[0])
    plain = complex(np.asarray(ran.effective_index).ravel()[0])
    assert abs(live - plain) <= 1e-12 * abs(plain), (live, plain)


# ---------------------------------------------------------------- PM3, PM4

def _plain_index(problem, h):
    """The kept mode's public index on the solver mesh moved by h (metres of d), with no motion."""
    from galerkin.mesh import Mesh
    from simcase.physics_em_modes2d import solve
    from simcase.runner import _to_public
    m, p = problem.arguments["mesh"], problem.arguments["inputs"]
    moved = Mesh(m.nodes + 1e6 * h * problem.design_velocity, m.triangles, m.boundary, m.boundary_edges)
    result = solve(moved, problem.arguments["eps"], p.wavelength, p.boundary, p.num_modes, p.formulation,
                   p.n_cladding, n_target=p.n_target, pml=p.pml)
    return complex(np.asarray(_to_public(None, None, result, point=True)["effective_index"])[0])


def test_pm3_pm4_derivative_against_a_same_mesh_central_difference(problem):
    h = 1e-4 * 0.22e-6
    fd = (_plain_index(problem, h) - _plain_index(problem, -h)) / (2 * h)
    slopes = {}
    for name in ("jax", "torch"):
        _backend(name)
        slopes[name] = _complex_slope(problem, name)
    assert abs(slopes["jax"] - fd) <= 1e-6 * abs(fd), (slopes["jax"], fd)                       # PM3
    assert abs(slopes["torch"] - slopes["jax"]) <= 1e-12 * abs(slopes["jax"])                   # PM4


# ---------------------------------------------------------------- PM5 the analytic pole

def _outgoing_root(d1):
    """galerkin's leaky-slab TE pole (exp(+i omega t)): film d1 thick, substrate from 0.47 um."""
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
    assert r.success
    return complex(*r.x)


def test_pm5_the_slope_of_the_leaky_pole(problem):
    h = 1e-4
    exact = np.conj((_outgoing_root(0.22 + h) - _outgoing_root(0.22 - h)) / (2 * h)) * 1e6   # public, per metre
    slope = _complex_slope(problem, "jax")
    assert abs(slope - exact) <= 1e-2 * abs(exact), (slope, exact)


# ---------------------------------------------------------------- PM6 refusals

def test_pm6_refusals():
    _backend("jax")
    bent = json.loads((EXAMPLES / "pml_bent_slab.json").read_text())
    g = bent["geometry"]
    film = dict(g["shapes"][0], h="d")
    bent["geometry"] = {"version": 1, "parameters": {"d": {"value": "0.22 um"}}, "components": {"xs": {
        "dimension": "2d", "length_unit": "um", "depth": None, "domain": g["domain"], "background": g["background"],
        "features": [film]}}}
    with pytest.raises(DocumentError, match="has a bend"):
        shape_problem(bent, "d")
    with pytest.raises(DocumentError, match="inside the PML or across an outer face"):
        shape_problem(leaky_slab("marker_height"), "marker_height")
