# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simcase.shape_derivative for vector waveguide modes (em.modes2d).

Checks Q1-Q5, pre-registered in the HQ work record (2026-11-21) before the tests ran: Q1 the
derivative of the effective index with respect to the core width against a same-mesh
Richardson difference within 1e-6; Q2 the effective index at t = 0 equals run()'s within
1e-12; Q3 the same document in micrometres and in nanometres gives the same mesh and the same
derivative per metre; Q4 refusals by name; Q5 the other shape_problem tests are unchanged.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.shape_derivative import shape_problem

BACKENDS = ["jax", "torch"]


def _backend(name):
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
    else:
        pytest.importorskip("torch")


def strip(scale=1.0, unit="um", w=0.5, **physics):
    """A 0.22 um silicon strip of width w in oxide, PEC box, 1.55 um, one vector mode."""
    s = scale
    comp = {"dimension": "2d", "length_unit": unit, "depth": None,
            "domain": {"xmin": -1.5 * s, "xmax": 1.5 * s, "ymin": -1.2 * s, "ymax": 1.2 * s},
            "background": {"material": "oxide"},
            "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": -0.11 * s, "w": "w", "h": 0.22 * s,
                          "material": "si"}]}
    p = {"type": "em.modes2d", "formulation": "vector", "vacuum_wavelength": "1.55 um", "mode_count": 1,
         "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"},
         "effective_index_threshold": 1.444, **physics}
    return {"openphysics": "0.3", "name": "strip",
            "geometry": {"version": 1, "parameters": {"w": {"value": f"{w * s!r} {unit}"}}, "components": {"xs": comp}},
            "materials": {"si": {"refractive_index": 3.48}, "oxide": {"refractive_index": 1.444}},
            "physics": {"em1": p}, "mesh": {"element_size": f"{0.1 * s!r} {unit}"}, "study": {"type": "single"},
            "results": {"save_fields": False, "plots": False}}


def _index(r):
    return r["effective_index"][0].real


def _plain(problem, h):
    """The runner's vector solve on the micrometre mesh moved by h metres of the parameter."""
    from galerkin.mesh import Mesh

    from simcase.physics_em_modes2d import solve
    a = problem.arguments
    m, p = a["mesh"], a["inputs"]
    moved = Mesh(m.nodes + 1e6 * h * problem.design_velocity, m.triangles, boundary=m.boundary,
                 boundary_edges=m.boundary_edges)
    return float(solve(moved, a["eps"], p.wavelength, p.boundary, p.num_modes, "vector", p.n_cladding)["neff"][0].real)


@pytest.mark.parametrize("name", BACKENDS)
def test_q1_width_derivative_matches_a_richardson_difference(name):
    _backend(name)
    problem = shape_problem(strip(), "w")
    _value, slope = problem.derivative(_index, backend=name)
    h = 2e-9                                              # metres of width (0.4 % of w)
    d1 = (_plain(problem, h) - _plain(problem, -h)) / (2 * h)
    d2 = (_plain(problem, h / 2) - _plain(problem, -h / 2)) / h
    reference = (4 * d2 - d1) / 3
    assert abs(slope / reference - 1) <= 1e-6, (slope, reference, d1, d2)
    assert slope > 0                                      # a wider core confines more


def test_q2_effective_index_at_zero_equals_run():
    _backend("jax")
    import jax.numpy as jnp
    doc = strip()
    ran = run(Document.from_dict(doc), verbose=False)
    r = shape_problem(doc, "w").solve(jnp.asarray(0.0, dtype=jnp.float64))
    got, want = np.asarray(r["effective_index"]), np.asarray(ran.effective_index).ravel()
    assert got.shape == want.shape
    assert np.max(np.abs(got - want)) <= 1e-12 * np.max(np.abs(want)), (got, want)


def test_q3_the_document_unit_does_not_change_mesh_or_derivative():
    _backend("jax")
    um, nm = shape_problem(strip(), "w"), shape_problem(strip(1000.0, "nm"), "w")
    assert np.array_equal(um.mesh.nodes, nm.mesh.nodes)
    a, b = um.derivative(_index)[1], nm.derivative(_index)[1]
    assert abs(a / b - 1) <= 1e-12, (a, b)


def test_q4_refusals_name_the_reason():
    scalar = strip(formulation="scalar")
    scalar["physics"]["em1"].pop("effective_index_threshold")      # the scalar formulation reads none
    with pytest.raises(DocumentError, match="formulation is 'scalar'; .*vector formulation"):
        shape_problem(scalar, "w")
    with pytest.raises(DocumentError, match="has a PML or a bend"):
        shape_problem(strip(pml={"pml_thickness": {"top": "0.3 um", "bottom": "0.3 um"}}, target_effective_index=2.4), "w")
    sweep = strip()
    sweep["study"] = {"type": "sweep", "parameter": "physics.em1.vacuum_wavelength",
                      "values": {"unit": "um", "values": [1.5, 1.55, 1.6]}}
    with pytest.raises(DocumentError, match="taken at one point"):
        shape_problem(sweep, "w")
    flat = copy.deepcopy(strip())
    comp = flat["geometry"]["components"]["xs"]
    flat["geometry"] = {"length_unit": "um", "depth": None, "domain": comp["domain"], "background": comp["background"],
                        "shapes": [{"name": "core", "type": "rect", "x": -0.25, "y": -0.11, "w": 0.5, "h": 0.22,
                                    "material": "si"}]}
    with pytest.raises(DocumentError, match="not a version 1 block"):
        shape_problem(flat, "w")
