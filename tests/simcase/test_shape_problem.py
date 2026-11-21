# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simcase.shape_derivative: one call from a document parameter to its shape derivative.

Checks C1-C6, pre-registered in the HQ work record (2026-11-21) before the tests ran:
C1 the annulus inner radius against 2 pi k dT / (a ln^2(b/a)), order >= 1.5 and <= 1e-3 at
the finest mesh; C2 a two-material series strip, exact for P1, within 1e-9; C3 the
problem's mesh and solver inputs are run()'s, and its solve at t = 0 agrees within 1e-12; C4 a same-mesh central difference within
1e-6; C5 refusals by name (the pre-registered sweep refusal is the validation's own: steady heat
takes only a single study); C6 run() is unchanged (the region heat tests).
"""

from __future__ import annotations

import math

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


def annulus(a=2.0, b=4.0, k=3.0, size=0.4):
    """The ring a < r < b (um) of conductivity k, inner circle at 301 K, ring circle at 300 K.

    The background outside the ring is the same material and only touches the ring circle, so
    it sits at 300 K and the annulus has the closed-form solution."""
    comp = {"dimension": "2d", "length_unit": "um", "depth": None,
            "domain": {"xmin": -6, "xmax": 6, "ymin": -6, "ymax": 6},
            "background": {"material": "k"},
            "features": [{"name": "ring", "type": "circle", "cx": 0, "cy": 0, "r": b, "material": "k"},
                         {"name": "hole", "type": "circle", "cx": 0, "cy": 0, "r": "a", "material": None}],
            "selections": {"inner": {"boundary": {"feature": "hole"}}, "rim": {"boundary": {"feature": "ring"}}}}
    heat = {"type": "thermal.steady2d", "prescribed_temperature": {"inner": "301 K", "rim": "300 K"}}
    return {"openphysics": "0.3", "name": "annulus",
            "geometry": {"version": 1, "parameters": {"a": {"value": f"{a!r} um"}}, "components": {"xs": comp}},
            "materials": {"k": {"thermal_conductivity": f"{k!r} W/(m K)"}},
            "physics": {"heat1": heat}, "mesh": {"element_size": f"{size!r} um"}, "study": {"type": "single"},
            "results": {"save_fields": False, "plots": False}}


def strip(L1=0.8, L=2.0, H=1.0, k1=5.0, k2=2.0, size=0.25):
    """Material A on 0 < x < L1 and B on L1 < x < L (mm), height H, 400 K left and 300 K right."""
    comp = {"dimension": "2d", "length_unit": "mm", "depth": None,
            "domain": {"xmin": 0, "xmax": L, "ymin": 0, "ymax": H},
            "background": {"material": "B"},
            "features": [{"name": "first", "type": "rect", "x": 0, "y": 0, "w": "L1", "h": H, "material": "A"}]}
    heat = {"type": "thermal.steady2d", "prescribed_temperature": {"left": "400 K", "right": "300 K"}}
    return {"openphysics": "0.3", "name": "strip",
            "geometry": {"version": 1, "parameters": {"L1": {"value": f"{L1!r} mm"}}, "components": {"xs": comp}},
            "materials": {"A": {"thermal_conductivity": f"{k1!r} W/(m K)"},
                          "B": {"thermal_conductivity": f"{k2!r} W/(m K)"}},
            "physics": {"heat1": heat}, "mesh": {"element_size": f"{size!r} mm"}, "study": {"type": "single"},
            "results": {"save_fields": False, "plots": False}}


def _heat_in(problem, tag):
    nodes = problem.mesh.boundary[tag]
    return lambda r: r.reaction_heat_rate_per_depth[nodes].sum()


# ---------------------------------------------------------------- C1 annulus, closed form

@pytest.mark.parametrize("name", BACKENDS)
def test_c1_annulus_inner_radius_converges_to_the_closed_form(name):
    _backend(name)
    a, b, k = 2e-6, 4e-6, 3.0
    exact = 2 * math.pi * k / (a * math.log(b / a) ** 2)          # dQ/da per depth, W/m^2, dT = 1 K
    sizes, errors = (0.8, 0.4, 0.2), []
    for size in sizes:
        problem = shape_problem(annulus(size=size), "a")
        _value, slope = problem.derivative(_heat_in(problem, "inner"), backend=name)
        errors.append(abs(slope / exact - 1))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(sizes[i] / sizes[i + 1]) for i in range(2)]
    assert min(orders) >= 1.5, (errors, orders)
    assert errors[-1] <= 1e-3, errors


# ---------------------------------------------------------------- C2 series strip, exact

@pytest.mark.parametrize("name", BACKENDS)
def test_c2_series_strip_interface_is_exact(name):
    _backend(name)
    L1, L, H, k1, k2, dT = 0.8e-3, 2.0e-3, 1.0e-3, 5.0, 2.0, 100.0
    resistance = L1 / k1 + (L - L1) / k2
    Q = dT * H / resistance
    exact = -Q / resistance * (1 / k1 - 1 / k2)                 # dQ/dL1, W/m^2 per depth
    problem = shape_problem(strip(), "L1")
    value, slope = problem.derivative(_heat_in(problem, "left"), backend=name)
    assert abs(value / Q - 1) <= 1e-9, (value, Q)
    assert abs(slope / exact - 1) <= 1e-9, (slope, exact)


# ---------------------------------------------------------------- C3 equal to run()

def test_c3_mesh_and_solve_at_zero_equal_run():
    _backend("jax")
    import jax.numpy as jnp
    from galerkin.core.backend import to_numpy
    from galerkin.thermal import solve_steady_heat
    data = annulus()
    ran = run(Document.from_dict(data), verbose=False)
    problem = shape_problem(data, "a")
    # the same mesh and the same solver inputs: the plain solve is run()'s, bit for bit
    assert np.array_equal(problem.mesh.nodes, ran.mesh.nodes)
    assert np.array_equal(problem.mesh.triangles, ran.mesh.triangles)
    assert {k: list(v) for k, v in problem.mesh.boundary.items()} == {k: list(v) for k, v in ran.mesh.boundary.items()}
    plain = solve_steady_heat(problem.mesh, **problem.arguments)
    assert np.array_equal(plain.temperature, ran.solution.temperature)
    assert np.array_equal(plain.reaction_heat_rate_per_depth, ran.solution.reaction_heat_rate_per_depth)
    # with the motion at t = 0 the live correction step adds rounding
    r = problem.solve(jnp.asarray(0.0, dtype=jnp.float64))
    T, T0 = to_numpy(r.temperature), ran.solution.temperature
    assert np.max(np.abs(T - T0)) <= 1e-12 * np.max(np.abs(T0))
    # The pre-registered 1e-12 failed at first (2.0e-12, 2026-11-21): the motion path computed
    # with absolute temperatures near 300 K. Since it subtracts each component's offset, as the
    # plain solve does (follow-up 3), the reactions agree to 5.5e-15 and the bound is 1e-12 again.
    q, q0 = to_numpy(r.reaction_heat_rate_per_depth), ran.solution.reaction_heat_rate_per_depth
    assert np.max(np.abs(q - q0)) <= 1e-12 * np.max(np.abs(q0))
    assert problem.on_curve.any() and not problem.on_curve.all()


# ---------------------------------------------------------------- C4 same-mesh central difference

@pytest.mark.parametrize("name", BACKENDS)
def test_c4_matches_a_central_difference_on_the_same_mesh(name):
    _backend(name)
    from galerkin.mesh import Mesh
    from galerkin.thermal import solve_steady_heat
    problem = shape_problem(annulus(), "a")
    m, W = problem.mesh, problem.design_velocity
    inner = m.boundary["inner"]

    def moved(h):
        mm = Mesh(m.nodes + h * W, m.triangles, boundary=m.boundary, boundary_edges=m.boundary_edges,
                  regions=m.regions, region_names=m.region_names)
        return float(solve_steady_heat(mm, **problem.arguments).reaction_heat_rate_per_depth[inner].sum())

    h = 1e-4 * 2e-6
    fd = (moved(h) - moved(-h)) / (2 * h)
    _value, slope = problem.derivative(_heat_in(problem, "inner"), backend=name)
    assert abs(slope / fd - 1) <= 1e-6, (slope, fd)


# ---------------------------------------------------------------- C5 refusals

def test_c5_refusals_name_the_reason():
    flat = strip()
    comp = flat["geometry"]["components"]["xs"]
    flat["geometry"] = {"length_unit": "mm", "depth": None, "domain": comp["domain"], "background": comp["background"],
                        "shapes": [{"name": "first", "type": "rect", "x": 0., "y": 0., "w": 0.8, "h": 1.0,
                                    "material": "A"}]}
    with pytest.raises(DocumentError, match="not a version 1 block"):
        shape_problem(flat, "L1")
    axi = strip()
    axi["geometry"]["components"]["xs"]["dimension"] = "axisymmetric"
    axi["geometry"]["components"]["xs"].pop("depth")
    with pytest.raises(DocumentError, match="axisymmetric"):
        shape_problem(axi, "L1")
    # another physics: test_shape_problem_physics.py (P6), now that electric and mechanics are covered
    with pytest.raises(DocumentError, match="unknown parameter 'nope'"):
        shape_problem(strip(), "nope")
    ratio = strip()
    ratio["geometry"]["parameters"]["f"] = {"value": 0.4, "kind": "ratio"}
    ratio["geometry"]["components"]["xs"]["features"][0]["w"] = "f * 2"
    with pytest.raises(DocumentError, match="is a ratio"):
        shape_problem(ratio, "f")
    derived = strip()
    derived["geometry"]["parameters"]["half"] = {"value": "L1 / 2"}
    with pytest.raises(DocumentError, match="derived from other parameters"):
        shape_problem(derived, "half")
    with pytest.raises(ValueError, match="backend must be 'jax' or 'torch'"):
        shape_problem(strip(), "L1").derivative(lambda r: r.temperature.sum(), backend="numpy")
