# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simcase.shape_derivative beyond steady heat: electric, elasticity, thermoelastic, transient heat.

Checks P1-P6, pre-registered in the HQ work record (2026-11-21) before the tests ran. P3 and P4
had analytic references in the plan that P1 does not reproduce, so they use the references
below; the test docstrings say why.
"""

from __future__ import annotations

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.shape_derivative import shape_problem

BACKENDS = ["jax", "torch"]
L1, L, H = 0.8e-3, 2.0e-3, 1.0e-3                        # the strip, metres


def _backend(name):
    if name == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        return jax.numpy
    return pytest.importorskip("torch")


def _zero(name):
    xp = _backend(name)
    return xp.asarray(0.0, dtype=xp.float64) if name == "jax" else xp.tensor(0.0, dtype=xp.float64)


def q(value, unit):
    return f"{float(value)!r} {unit}"


def strip(physics, materials, *, size=0.25, study=None):
    """Material A on 0 < x < L1 and B on L1 < x < L (mm), height H; the parameter is L1."""
    comp = {"dimension": "2d", "length_unit": "mm", "depth": None,
            "domain": {"xmin": 0, "xmax": L * 1e3, "ymin": 0, "ymax": H * 1e3},
            "background": {"material": "B"},
            "features": [{"name": "first", "type": "rect", "x": 0, "y": 0, "w": "L1", "h": H * 1e3, "material": "A"}]}
    return {"openphysics": "0.3", "name": "strip",
            "geometry": {"version": 1, "parameters": {"L1": {"value": q(L1 * 1e3, "mm")}}, "components": {"xs": comp}},
            "materials": materials, "physics": {"p": physics}, "mesh": {"element_size": q(size, "mm")},
            "study": study or {"type": "single"}, "results": {"save_fields": False, "plots": False}}


def solid(E):
    return {"youngs_modulus": q(E, "Pa"), "poisson_ratio": 0.0, "linear_expansion_coefficient": q(1e-5, "1/K"),
            "thermal_conductivity": q(10.0 if E > 1e11 else 4.0, "W/(m K)")}


def electric_doc():
    return strip({"type": "electric.steady2d", "prescribed_electric_potential": {"left": "1 V", "right": "0 V"}},
                 {"A": {"electrical_conductivity": "5 S/m"}, "B": {"electrical_conductivity": "2 S/m"}})


def elasticity_doc():
    return strip({"type": "mechanics.elasticity2d", "plane": "stress",
                  "prescribed_displacement": {"left": {"x": "0.0 m", "y": "0.0 m"}},
                  "traction": {"right": ["1000000.0 Pa", "0.0 Pa"]}}, {"A": solid(200e9), "B": solid(70e9)})


def thermoelastic_doc(**extra):
    return strip({"type": "mechanics.thermoelastic2d", "plane": "stress", "stress_free_temperature": "300.0 K",
                  "prescribed_displacement": {"left": {"x": "0.0 m"}, "bottom": {"y": "0.0 m"}},
                  "prescribed_temperature": {"left": "400 K", "right": "300 K"}, **extra},
                 {"A": solid(200e9), "B": solid(70e9)})


HEAT_MATERIALS = {"A": {"thermal_conductivity": "5 W/(m K)", "volumetric_heat_capacity": "2e6 J/(m^3 K)"},
                  "B": {"thermal_conductivity": "2 W/(m K)", "volumetric_heat_capacity": "2e6 J/(m^3 K)"}}
HEAT = {"prescribed_temperature": {"left": "300 K", "right": "300 K"}, "heat_source_density": {"first": "1e7 W/m^3"}}
TIMES = [0.0, 1.0, 10.0, 100.0, 1000.0]                 # the diffusion time is about 4 s


def transient_doc():
    return strip({"type": "thermal.transient2d", "initial_temperature": "300 K", **HEAT}, HEAT_MATERIALS,
                 study={"type": "transient", "time": {"unit": "s", "values": TIMES}})


def steady_twin():
    return strip({"type": "thermal.steady2d", **HEAT},
                 {k: {"thermal_conductivity": m["thermal_conductivity"]} for k, m in HEAT_MATERIALS.items()})


def _moved(mesh, W, h):
    from galerkin.mesh import Mesh
    return Mesh(mesh.nodes + h * W, mesh.triangles, boundary=mesh.boundary, boundary_edges=mesh.boundary_edges,
                regions=mesh.regions, region_names=mesh.region_names)


def _rel(a, b):
    return abs(a / b - 1)


# ---------------------------------------------------------------- P1 electric, exact

@pytest.mark.parametrize("name", BACKENDS)
def test_p1_electric_series_strip_is_exact(name):
    _backend(name)
    R = L1 / 5.0 + (L - L1) / 2.0
    current, exact = H / R, -(H / R) / R * (1 / 5.0 - 1 / 2.0)    # per depth, dV = 1 V
    problem = shape_problem(electric_doc(), "L1")
    left = problem.mesh.boundary["left"]
    value, slope = problem.derivative(lambda r: r.reaction_current_per_depth[left].sum(), backend=name)
    assert _rel(value, current) <= 1e-9 and _rel(slope, exact) <= 1e-9, (value, current, slope, exact)


# ---------------------------------------------------------------- P2 elasticity, exact

@pytest.mark.parametrize("name", BACKENDS)
def test_p2_elastic_series_bar_is_exact(name):
    """nu = 0, plane stress: uniaxial stress, u = sigma x / E piecewise, which P1 represents."""
    _backend(name)
    sigma, E1, E2 = 1e6, 200e9, 70e9
    problem = shape_problem(elasticity_doc(), "L1")
    right = problem.mesh.boundary["right"]
    value, slope = problem.derivative(lambda r: r.displacement[right, 0].mean(), backend=name)
    assert _rel(value, sigma * (L1 / E1 + (L - L1) / E2)) <= 1e-9, value
    assert _rel(slope, sigma * (1 / E1 - 1 / E2)) <= 1e-9, slope


# ---------------------------------------------------------------- P3 thermoelastic (path 2)

@pytest.mark.parametrize("name", BACKENDS)
def test_p3_thermoelastic_moves_the_temperature_and_matches_a_central_difference(name):
    """The plan's reference, u_end = integral of alpha (T - T_ref), is not the P1 solution: a
    temperature linear in x gives a quadratic displacement, and a jump of alpha or of T' at the
    interface makes the thermal strain incompatible. So P3 checks (a) that the heat stage is the
    steady heat problem's, derivative included, within 1e-12, and (b) a same-mesh central
    difference of the end displacement within 1e-6."""
    _backend(name)
    from galerkin.thermal_mechanical import solve_steady_thermoelasticity
    problem = shape_problem(thermoelastic_doc(), "L1")
    m, W = problem.mesh, problem.design_velocity
    right, left = m.boundary["right"], m.boundary["left"]
    heat_twin = shape_problem(strip({"type": "thermal.steady2d",
                                     "prescribed_temperature": {"left": "400 K", "right": "300 K"}},
                                    {"A": {"thermal_conductivity": "10.0 W/(m K)"},
                                     "B": {"thermal_conductivity": "4.0 W/(m K)"}}), "L1")
    assert np.array_equal(heat_twin.mesh.nodes, m.nodes)
    _v, d_heat = problem.derivative(lambda r: r.heat.reaction_heat_rate_per_depth[left].sum(), backend=name)
    _v, d_twin = heat_twin.derivative(lambda r: r.reaction_heat_rate_per_depth[left].sum(), backend=name)
    assert _rel(d_heat, d_twin) <= 1e-12, (d_heat, d_twin)

    def end(h):
        r = solve_steady_thermoelasticity(_moved(m, W, h), **problem.arguments)
        return float(np.mean(np.asarray(r.mechanics.displacement)[right, 0]))
    h = 1e-4 * L1
    fd = (end(h) - end(-h)) / (2 * h)
    _v, slope = problem.derivative(lambda r: r.mechanics.displacement[right, 0].mean(), backend=name)
    assert _rel(slope, fd) <= 1e-6, (slope, fd)


def test_p3_thermoelastic_refuses_flux_convection_and_traction_by_name():
    with pytest.raises(DocumentError, match="has traction; the shape derivative of mechanics.thermoelastic2d"):
        shape_problem(thermoelastic_doc(traction={"right": ["1000000.0 Pa", "0.0 Pa"]}), "L1")
    held = {"top": {"heat_transfer_coefficient": "10 W/(m^2 K)", "ambient_temperature": "300 K"}}
    with pytest.raises(DocumentError, match="has convection; "):
        shape_problem(thermoelastic_doc(convection=held), "L1")


# ---------------------------------------------------------------- P4 transient heat

@pytest.mark.parametrize("name", BACKENDS)
def test_p4_transient_heat_reaches_the_steady_derivative(name):
    """Region transient documents take no inward flux and the analytic strip with a source is not
    the P1 solution in 2D, so the reference is the steady problem of the same document on the same
    mesh: at 1000 s (250 diffusion times) the derivative of the heat out at the left equals it
    within 1e-6, and a same-mesh central difference at that time within 1e-6."""
    _backend(name)
    from galerkin.transient_heat import solve_transient_heat
    problem = shape_problem(transient_doc(), "L1")
    steady = shape_problem(steady_twin(), "L1")
    assert np.array_equal(steady.mesh.nodes, problem.mesh.nodes)
    m, W = problem.mesh, problem.design_velocity
    left = m.boundary["left"]
    _v, slope = problem.derivative(lambda r: r.reaction_heat_rate_per_depth[-1][left].sum(), backend=name)
    _v, reference = steady.derivative(lambda r: r.reaction_heat_rate_per_depth[left].sum(), backend=name)
    assert _rel(slope, reference) <= 1e-6, (slope, reference)

    def out(h):
        r = solve_transient_heat(_moved(m, W, h), **problem.arguments)
        return float(np.asarray(r.reaction_heat_rate_per_depth)[-1][left].sum())
    h = 1e-4 * L1
    assert _rel(slope, (out(h) - out(-h)) / (2 * h)) <= 1e-6


# ---------------------------------------------------------------- P5 equal to run()

def _close(got, want, scale=None):
    from galerkin.core.backend import to_numpy
    got, want = np.asarray(to_numpy(got)), np.asarray(want)
    scale = np.max(np.abs(want)) if scale is None else scale
    return np.max(np.abs(got - want)) <= 1e-12 * scale


@pytest.mark.parametrize("which", ["electric", "elasticity", "thermoelastic", "transient"])
def test_p5_mesh_inputs_and_solve_at_zero_equal_run(which):
    doc = {"electric": electric_doc, "elasticity": elasticity_doc, "thermoelastic": thermoelastic_doc,
           "transient": transient_doc}[which]()
    ran = run(Document.from_dict(doc), verbose=False)
    problem = shape_problem(doc, "L1")
    r = problem.solve(_zero("jax"))
    if which == "transient":
        nodes, T0 = np.asarray(ran.solution.node_coordinates), np.asarray(ran.solution.temperature)
        assert np.array_equal(problem.mesh.nodes, nodes)
        assert _close(r.temperature, T0, np.ptp(T0))
        assert _close(r.reaction_heat_rate_per_depth, ran.solution.reaction_heat_rate_per_depth)
        return
    fields = ran.fields
    assert np.array_equal(problem.mesh.nodes, fields["node_coordinates"])
    assert np.array_equal(problem.mesh.triangles, fields["triangles"])
    if which == "electric":
        assert _close(r.electric_potential, fields["electric_potential"])
        assert _close(r.reaction_current_per_depth, fields["reaction_current_per_depth"])
    elif which == "elasticity":
        assert _close(r.displacement, fields["displacement"])
        assert _close(r.reaction_force_per_depth, fields["reaction_force_per_depth"])
    else:
        T0 = fields["temperature"]
        assert _close(r.heat.temperature, T0, np.ptp(T0))
        assert _close(r.heat.reaction_heat_rate_per_depth, fields["reaction_heat_rate_per_depth"])
        assert _close(r.mechanics.displacement, fields["displacement"])
        assert _close(r.mechanics.reaction_force_per_depth, fields["reaction_force_per_depth"])


# ---------------------------------------------------------------- P6 refusals

@pytest.mark.parametrize("example, kind", [("soi_strip", "em.modes2d"),
                                           ("joule_temperature_regions", "joule.temperature2d")])
def test_p6_other_physics_are_refused_by_name(example, kind):
    import copy
    from simcase.examples import EXAMPLES
    with pytest.raises(DocumentError, match=f"is {kind!r}; the shape derivative of a document covers "
                                            "thermal.steady2d, thermal.transient2d, electric.steady2d"):
        shape_problem(copy.deepcopy(EXAMPLES[example]), "x")
