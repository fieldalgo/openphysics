# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simcase.shape_derivative on axisymmetric heat documents (2026-11-22).

Checks SA1-SA6, pre-registered in the HQ work record (2026-11-22) before the tests ran: SA1 a
two-layer hollow cylinder, the inner layer thickness against the closed-form series rate, order
>= 1.5 and within 1e-3 on the finest mesh; SA2 on a solid cylinder the axis nodes keep W_r = 0
exactly and the solve is accepted; SA3 a same-mesh central difference within 1e-6 there; SA4 the
same for a transient axisymmetric document; SA5 the solve at t = 0 equals run() within 1e-12, on
the same mesh and inputs; SA6 the remaining refusals stand.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.shape_derivative import shape_problem

BACKENDS = ["jax", "torch"]
Q, TB = 1e5, 293.15


def _backend(name):
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
    else:
        pytest.importorskip("torch")


def hollow(d=1.0, k1=5.0, k2=2.0, size=0.2):
    """1 < r < 6 um, 0 < z < 1 um: material A on 1 < r < 1 + d, B beyond; 301 K inside, 300 K outside."""
    comp = {"dimension": "axisymmetric", "length_unit": "um",
            "domain": {"xmin": 1, "xmax": 6, "ymin": 0, "ymax": 1}, "background": {"material": "B"},
            "features": [{"name": "inner", "type": "rect", "x": 1, "y": 0, "w": "d", "h": 1, "material": "A"}]}
    heat = {"type": "thermal.steady2d", "prescribed_temperature": {"left": "301 K", "right": "300 K"}}
    return {"openphysics": "0.3", "name": "hollow",
            "geometry": {"version": 1, "parameters": {"d": {"value": f"{d!r} um"}}, "components": {"xs": comp}},
            "materials": {"A": {"thermal_conductivity": f"{k1!r} W/(m K)"},
                          "B": {"thermal_conductivity": f"{k2!r} W/(m K)"}},
            "physics": {"heat1": heat}, "mesh": {"element_size": f"{size!r} um"}, "study": {"type": "single"},
            "results": {"save_fields": False, "plots": False}}


def solid(a=1.0, size=0.2, transient=False):
    """0 < r < 3 mm, 0 < z < 1 mm: a heated core 0 < r < a (k 2) in a shell (k 0.5), 293.15 K outside."""
    comp = {"dimension": "axisymmetric", "length_unit": "mm",
            "domain": {"xmin": 0, "xmax": 3, "ymin": 0, "ymax": 1}, "background": {"material": "shell"},
            "features": [{"name": "core", "type": "rect", "x": 0, "y": 0, "w": "a", "h": 1, "material": "core"}]}
    heat = {"type": "thermal.steady2d", "heat_source_density": {"core": f"{Q!r} W/m^3"},
            "prescribed_temperature": {"right": f"{TB!r} K"}}
    doc = {"openphysics": "0.3", "name": "solid",
           "geometry": {"version": 1, "parameters": {"a": {"value": f"{a!r} mm"}}, "components": {"rod": comp}},
           "materials": {"core": {"thermal_conductivity": "2.0 W/(m K)"},
                         "shell": {"thermal_conductivity": "0.5 W/(m K)"}},
           "physics": {"heat1": heat}, "mesh": {"element_size": f"{size!r} mm"}, "study": {"type": "single"},
           "results": {"save_fields": False, "plots": False}}
    if transient:
        for m in doc["materials"].values():
            m["volumetric_heat_capacity"] = "1.8e6 J/(m^3 K)"
        heat.update({"type": "thermal.transient2d", "initial_temperature": f"{TB!r} K"})
        doc["study"] = {"type": "transient", "time": {"unit": "s", "values": [0.0, 1.0, 2.0]}}
    return doc


def _rate_in(problem, tag):
    nodes = problem.mesh.boundary[tag]
    return lambda r: r.reaction_heat_rate[nodes].sum()


# ---------------------------------------------------------------- SA1 closed form

@pytest.mark.parametrize("name", BACKENDS)
def test_sa1_two_layer_cylinder_converges_to_the_series_rate(name):
    _backend(name)
    a, b, H, k1, k2, dT = 1e-6, 6e-6, 1e-6, 5.0, 2.0, 1.0
    w = a + 1e-6
    R = math.log(w / a) / k1 + math.log(b / w) / k2
    exact = -2 * math.pi * H * dT * (1 / (k1 * w) - 1 / (k2 * w)) / R ** 2        # dQ/dd, W/m
    sizes, errors = (0.4, 0.2, 0.1), []
    for size in sizes:
        problem = shape_problem(hollow(size=size), "d")
        assert problem.arguments["coordinate_system"] == "axisymmetric"
        _value, slope = problem.derivative(_rate_in(problem, "left"), backend=name)
        errors.append(abs(slope / exact - 1))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(sizes[i] / sizes[i + 1]) for i in range(2)]
    assert min(orders) >= 1.5, (errors, orders)
    assert errors[-1] <= 1e-3, errors


# ---------------------------------------------------------------- SA2, SA3 solid cylinder with its axis

def _moved_solve(problem, h, solver):
    from galerkin.mesh import Mesh
    m, W = problem.mesh, problem.design_velocity
    moved = Mesh(m.nodes + h * W, m.triangles, boundary=m.boundary, boundary_edges=m.boundary_edges,
                 regions=m.regions, region_names=m.region_names)
    return solver(moved, **problem.arguments)


def test_sa2_axis_nodes_keep_a_zero_radial_velocity():
    _backend("jax")
    import jax.numpy as jnp
    problem = shape_problem(solid(), "a")
    axis = problem.mesh.nodes[:, 0] == 0
    assert axis.sum() >= 3
    assert np.all(problem.design_velocity[axis, 0] == 0.0)
    assert np.any(problem.design_velocity[~axis, 0] != 0.0)
    problem.solve(jnp.asarray(0.0, dtype=jnp.float64))           # galerkin accepts the motion


@pytest.mark.parametrize("name", BACKENDS)
def test_sa3_solid_cylinder_matches_a_central_difference_on_the_same_mesh(name):
    _backend(name)
    from galerkin.thermal import solve_steady_heat
    problem = shape_problem(solid(), "a")
    probe = int(np.argmin(np.hypot(problem.mesh.nodes[:, 0], problem.mesh.nodes[:, 1] - 0.5e-3)))
    h = 1e-4 * 1e-3
    fd = (_moved_solve(problem, h, solve_steady_heat).temperature[probe]
          - _moved_solve(problem, -h, solve_steady_heat).temperature[probe]) / (2 * h)
    _value, slope = problem.derivative(lambda r: r.temperature[probe], backend=name)
    assert abs(slope / fd - 1) <= 1e-6, (slope, fd)


# ---------------------------------------------------------------- SA4 transient

@pytest.mark.parametrize("name", BACKENDS)
def test_sa4_transient_solid_cylinder_matches_a_central_difference(name):
    _backend(name)
    from galerkin.transient_heat import solve_transient_heat
    problem = shape_problem(solid(transient=True), "a")
    assert problem.arguments["coordinate_system"] == "axisymmetric"
    probe = int(np.argmin(np.hypot(problem.mesh.nodes[:, 0], problem.mesh.nodes[:, 1] - 0.5e-3)))
    h = 1e-4 * 1e-3
    fd = (_moved_solve(problem, h, solve_transient_heat).temperature[-1][probe]
          - _moved_solve(problem, -h, solve_transient_heat).temperature[-1][probe]) / (2 * h)
    _value, slope = problem.derivative(lambda r: r.temperature[-1][probe], backend=name)
    assert abs(slope / fd - 1) <= 1e-6, (slope, fd)


# ---------------------------------------------------------------- SA5 the solve at t = 0 is run()'s

def test_sa5_mesh_and_solve_at_zero_equal_run():
    _backend("jax")
    import jax.numpy as jnp
    from galerkin.core.backend import to_numpy
    from galerkin.thermal import solve_steady_heat
    data = solid()
    ran = run(Document.from_dict(data), verbose=False)
    problem = shape_problem(data, "a")
    assert np.array_equal(problem.mesh.nodes, ran.mesh.nodes)
    assert np.array_equal(problem.mesh.triangles, ran.mesh.triangles)
    plain = solve_steady_heat(problem.mesh, **problem.arguments)
    assert np.array_equal(plain.temperature, ran.solution.temperature)
    r = problem.solve(jnp.asarray(0.0, dtype=jnp.float64))
    T, T0 = to_numpy(r.temperature), ran.solution.temperature
    assert np.max(np.abs(T - T0)) <= 1e-12 * np.max(np.abs(T0))


# ---------------------------------------------------------------- SA6 refusals

def test_sa6_refusals_stand():
    from simcase.shape_derivative import _axis_kept
    from galerkin.mesh import rectangle_mesh
    # a point of the axis that the design moves radially is refused by name
    m = rectangle_mesh(1.0, 1.0, 2, 2)
    values = np.zeros((m.num_nodes, 2))
    on = np.zeros(m.num_nodes, dtype=bool)
    axis_node = int(np.flatnonzero(m.nodes[:, 0] == 0)[0])
    on[axis_node], values[axis_node, 0] = True, 0.1
    with pytest.raises(DocumentError, match="on the symmetry axis off it"):
        _axis_kept(m, values, values, on, None)
    # an axisymmetric document of another physics stays refused (electric conduction is refused by its
    # own document validation: galerkin.electric has no axisymmetric measure)
    electric = solid()
    electric["materials"] = {"core": {"electrical_conductivity": "1e6 S/m"}, "shell": {"electrical_conductivity": "1e3 S/m"}}
    electric["physics"] = {"e1": {"type": "electric.steady2d", "prescribed_electric_potential": {"right": "0 V", "top": "1 V"}}}
    with pytest.raises(DocumentError, match="axisymmetric component is not supported for electric conduction"):
        shape_problem(electric, "a")
