# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""NumPy-only public functions refuse JAX and PyTorch values with a TypeError.

They compute with NumPy, so a live value would lose its derivative or fail
inside NumPy with an unrelated error. One case per guarded input; each skips
when its library is absent. docs/packages/galerkin/differentiation.md lists
these functions under "Refused, not approximated".

The temperature-dependent Joule solve finds its solution by iteration, so it
is checked per input kind, for both methods and for the four kinds of live
value a caller can hold: an eager JAX array, a ``jax.grad`` tracer, a PyTorch
leaf that requires grad and a non-leaf PyTorch tensor. Each must be refused by
the entry guard with a TypeError that names the input, not wrapped in a
JouleConvergenceError or failing inside ``copy.deepcopy``. Callbacks (the
conductivity model and boundary conditions) are seen only when they run, so a
live value they return is pinned as a JouleConvergenceError caused by that
TypeError.
"""
import numpy as np
import pytest

from galerkin import (EdgeSpace3D, assemble_mode_system, assemble_stiffness, box_mesh, eval_edge_field_3d,
                      l2_error, rectangle_mesh, solve_dirichlet, solve_material_cavity_box)
from galerkin.material_cavity import CavityMaterialRegion
from galerkin.mesh import Mesh
from galerkin.mode_coordinates import mode_coordinates, scalar_coordinate_system, solve_scalar_coordinates
from galerkin.temperature_joule_heating import (ConductivityModel, JouleConvergenceError,
                                                solve_temperature_joule_heat)

MESH = rectangle_mesh(2.0, 1.5, 8, 6)
FACTORS = np.ones((MESH.num_triangles, 3))
SIZE = [1.0, 0.7, 0.45]
BOX = {"subdivisions": (2, 2, 2), "num_modes": 2, "target_frequency_hz": 2.2e8}
SLAB = ((0.0, 0.5), (0.0, 0.35), (0.0, 0.45))
SPACE3D = EdgeSpace3D(box_mesh(1.0, 0.7, 0.45, 2, 2, 2))


def _cavity(**kw):
    return solve_material_cavity_box(**{"lengths_m": SIZE, **BOX, **kw})


def _region(**kw):
    return [CavityMaterialRegion(kw.pop("bounds_m", SLAB), **kw)]


CASES = {
    "solve_material_cavity_box lengths_m": lambda v: _cavity(lengths_m=[v(1.0), 0.7, 0.45]),
    "solve_material_cavity_box target_frequency_hz": lambda v: _cavity(target_frequency_hz=v(2.2e8)),
    "solve_material_cavity_box subdivisions": lambda v: _cavity(subdivisions=(v(2), 2, 2)),
    "solve_material_cavity_box num_modes": lambda v: _cavity(num_modes=v(2)),
    "solve_material_cavity_box region bounds": lambda v: _cavity(
        regions=_region(bounds_m=((0.0, v(0.5)), (0.0, 0.35), (0.0, 0.45)))),
    "solve_material_cavity_box region permittivity": lambda v: _cavity(
        regions=_region(relative_permittivity=v(2.0))),
    "solve_material_cavity_box region permeability": lambda v: _cavity(
        regions=_region(relative_permeability=v(2.0))),
    "solve_material_cavity_box wall conductivity": lambda v: _cavity(wall_conductivity_s_per_m=v(5.8e7)),
    "solve_material_cavity_box one wall's conductivity": lambda v: _cavity(
        wall_conductivity_s_per_m={"x0": v(5.8e7)}),
    "mode_coordinates thickness": lambda v: mode_coordinates(MESH, thickness={"left": v(0.4)}),
    "mode_coordinates strength": lambda v: mode_coordinates(MESH, thickness={"left": 0.4}, strength=v(3.0)),
    "mode_coordinates order": lambda v: mode_coordinates(MESH, thickness={"left": 0.4}, order=v(2)),
    "mode_coordinates bend_radius": lambda v: mode_coordinates(MESH, thickness={"left": 0.4},
                                                               bend_radius=v(10.0)),
    "mode_coordinates bend_origin": lambda v: mode_coordinates(MESH, thickness={"left": 0.4},
                                                               bend_radius=10.0, bend_origin=v(0.0)),
    "scalar_coordinate_system eps_r": lambda v: scalar_coordinate_system(MESH, v(2.0), 2 * np.pi, FACTORS),
    "scalar_coordinate_system k0": lambda v: scalar_coordinate_system(MESH, 2.0, v(2 * np.pi), FACTORS),
    "scalar_coordinate_system factors": lambda v: scalar_coordinate_system(MESH, 2.0, 2 * np.pi, v(FACTORS)),
    "solve_scalar_coordinates eps_r": lambda v: solve_scalar_coordinates(MESH, v(2.0), 2 * np.pi, 1.3, FACTORS),
    "solve_scalar_coordinates k0": lambda v: solve_scalar_coordinates(MESH, 2.0, v(2 * np.pi), 1.3, FACTORS),
    "solve_scalar_coordinates n_target": lambda v: solve_scalar_coordinates(MESH, 2.0, 2 * np.pi, v(1.3),
                                                                            FACTORS),
    "solve_scalar_coordinates factors": lambda v: solve_scalar_coordinates(MESH, 2.0, 2 * np.pi, 1.3,
                                                                           v(FACTORS)),
    "solve_scalar_coordinates num_modes": lambda v: solve_scalar_coordinates(MESH, 2.0, 2 * np.pi, 1.3, FACTORS,
                                                                             num_modes=v(2)),
    "solve_scalar_coordinates fixed_nodes": lambda v: solve_scalar_coordinates(
        MESH, 2.0, 2 * np.pi, 1.3, FACTORS, fixed_nodes=v(MESH.boundary["left"])),
    "assemble_mode_system eps_r": lambda v: assemble_mode_system(MESH, v(2.0), 2 * np.pi),
    "assemble_mode_system k0": lambda v: assemble_mode_system(MESH, 2.0, v(2 * np.pi)),
    "assemble_mode_system mu_r": lambda v: assemble_mode_system(MESH, 2.0, 2 * np.pi, v(1.0)),
    "assemble_mode_system coordinate_factors": lambda v: assemble_mode_system(
        MESH, 2.0, 2 * np.pi, coordinate_factors=v(FACTORS)),
    "solve_dirichlet load": lambda v: solve_dirichlet(assemble_stiffness(MESH, 1.0), v(np.ones(MESH.num_nodes)),
                                                      {tuple(MESH.boundary["left"]): 0.0}),
    "solve_dirichlet prescribed value": lambda v: solve_dirichlet(
        assemble_stiffness(MESH, 1.0), np.ones(MESH.num_nodes), {tuple(MESH.boundary["left"]): v(1.0)}),
    "l2_error values": lambda v: l2_error(MESH, v(MESH.nodes[:, 0]), lambda x, y: x),
    "l2_error exact values": lambda v: l2_error(MESH, MESH.nodes[:, 0], lambda x, y: v(x)),
    "eval_edge_field_3d dofs": lambda v: eval_edge_field_3d(SPACE3D, v(np.ones(SPACE3D.num_edges))),
}


def _live(library):
    """Values as arrays of ``library``: integers stay integers, everything else float64."""
    def typed(x):
        a = np.asarray(x)
        return a if a.dtype.kind in "iu" else a.astype(float)
    if library == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        return lambda x: jax.numpy.asarray(typed(x))
    torch = pytest.importorskip("torch")
    return lambda x: torch.as_tensor(typed(x))


@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("library", ["jax", "torch"])
def test_numpy_only_entry_points_refuse_live_values(library, case):
    with pytest.raises(TypeError, match="cut the derivative"):
        CASES[case](_live(library))


# Two regions, so that region tables are a kind of input too.
_STRIP = rectangle_mesh(1.0, 0.25, 8, 2)
JOULE_MESH = Mesh(_STRIP.nodes, _STRIP.triangles, _STRIP.boundary, _STRIP.boundary_edges,
                  (_STRIP.nodes[_STRIP.triangles].mean(axis=1)[:, 0] > 0.5).astype(int), ["a", "b"])
LEFT = [int(i) for i in JOULE_MESH.boundary["left"]]
RIGHT = [int(i) for i in JOULE_MESH.boundary["right"]]


def _joule(v, **kw):
    """The arguments of a small voltage-driven strip, with ``kw`` replacing some of them."""
    args = dict(electrical_conductivity=ConductivityModel(lambda t: 1 / (1 + 0.5 * (t - 300)), (0.0, 5000.0)),
                thermal_conductivity=1.0,
                electric_dirichlet={**{i: 0.0 for i in LEFT}, **{i: 1.0 for i in RIGHT}},
                thermal_dirichlet={i: 300.0 for i in LEFT + RIGHT}, initial_temperature=300.0)
    args.update(kw)
    return args


# Every input that can hold a number, in each container it may come in. ``v``
# turns a number into a live value of the library under test.
JOULE_CASES = {
    "electric_dirichlet": lambda v: _joule(v, electric_dirichlet={**{i: 0.0 for i in LEFT},
                                                                  **{i: v(1.0) for i in RIGHT}}),
    "thermal_conductivity scalar": lambda v: _joule(v, thermal_conductivity=v(1.0)),
    "thermal_conductivity region table": lambda v: _joule(v, thermal_conductivity={"a": 1.0, "b": v(2.0)}),
    "outward_current": lambda v: _joule(v, electric_dirichlet={i: 0.0 for i in LEFT},
                                        outward_current={"right": v(-1.0)}),
    "reference_potential": lambda v: _joule(v, electric_dirichlet={}, reference_potential={LEFT[0]: v(0.0)},
                                            outward_current={"left": -1.0, "right": 1.0}),
    "outward_flux": lambda v: _joule(v, outward_flux={"top": v(1.0)}),
    "convection coefficient": lambda v: _joule(v, convection={"top": (v(2.0), 300.0)}),
    "convection ambient": lambda v: _joule(v, convection={"top": [2.0, v(300.0)]}),
    "thermal_dirichlet": lambda v: _joule(v, thermal_dirichlet={**{i: 300.0 for i in LEFT},
                                                                **{i: v(300.0) for i in RIGHT}}),
    "initial_temperature scalar": lambda v: _joule(v, initial_temperature=v(300.0)),
    "initial_temperature array": lambda v: _joule(v, initial_temperature=v(np.full(JOULE_MESH.num_nodes, 300.0))),
    "initial_temperature list": lambda v: _joule(v, initial_temperature=[v(300.0)] * JOULE_MESH.num_nodes),
    "relaxation": lambda v: _joule(v, relaxation=v(0.5)),
    "temperature_atol": lambda v: _joule(v, temperature_atol=v(1e-8)),
    "relative_tolerance": lambda v: _joule(v, relative_tolerance=v(1e-10)),
    "max_iterations": lambda v: _joule(v, max_iterations=v(100.0)),
}


def _call_with_live(variant, call):
    """``call(v)`` with ``v`` making live values of one of the four kinds."""
    if variant.startswith("jax"):
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        if variant == "jax":
            return call(lambda x: jax.numpy.asarray(np.asarray(x, dtype=float)))

        def objective(p):   # inside jax.grad every value made from p is a tracer
            call(lambda x: p * np.asarray(x, dtype=float))
            return p * 0.0
        jax.grad(objective)(1.0)
        return
    torch = pytest.importorskip("torch")
    if variant == "torch leaf":
        return call(lambda x: torch.tensor(np.asarray(x, dtype=float), requires_grad=True))
    weight = torch.tensor(1.0, dtype=torch.float64, requires_grad=True)
    return call(lambda x: weight * torch.as_tensor(np.asarray(x, dtype=float)))   # not a leaf


@pytest.mark.parametrize("case", sorted(JOULE_CASES))
@pytest.mark.parametrize("method", ["picard", "newton"])
@pytest.mark.parametrize("variant", ["jax", "jax.grad tracer", "torch leaf", "torch non-leaf"])
def test_temperature_joule_heat_refuses_live_inputs_directly(variant, method, case):
    # The prefix pins the entry guard: later checks of some inputs share the
    # "cut the derivative" wording but not the solver's name.
    name = case.split()[0]
    def call(v):
        with pytest.raises(TypeError, match=rf"^solve_temperature_joule_heat {name}: .*cut the derivative"):
            solve_temperature_joule_heat(JOULE_MESH, **JOULE_CASES[case](v), method=method)
    _call_with_live(variant, call)


def _ones(v):
    """A boundary callback(points, normals) returning a live array of ones."""
    return lambda points, normals: v(np.ones(len(points)))


# Each callback with the arguments that use it, and the history rows written
# before it first runs: conductivity ``evaluate`` and every boundary callback
# run in the first evaluation, ``derivative`` in the first Newton step.
JOULE_CALLBACKS = {
    "evaluate": (lambda v: _joule(v, electrical_conductivity=ConductivityModel(
        lambda t: v(1 / (1 + 0.5 * (t - 300))), (0.0, 5000.0))), 0),
    "derivative": (lambda v: _joule(v, electrical_conductivity=ConductivityModel(
        lambda t: 1 / (1 + 0.5 * (t - 300)), (0.0, 5000.0),
        derivative=lambda t: v(-0.5 / (1 + 0.5 * (t - 300)) ** 2))), 1),
    "outward_flux": (lambda v: _joule(v, outward_flux={"top": _ones(v)}), 0),
    "convection coefficient": (lambda v: _joule(v, convection={"top": (_ones(v), 300.0)}), 0),
    "convection ambient": (lambda v: _joule(v, convection={"top": (2.0, _ones(v))}), 0),
    "outward_current": (lambda v: _joule(v, electric_dirichlet={i: 0.0 for i in LEFT},
                                         outward_current={"right": _ones(v)}), 0),
}


@pytest.mark.parametrize("method,callback", [(m, c) for c in sorted(JOULE_CALLBACKS)
                                             for m in ("picard", "newton") if (m, c) != ("picard", "derivative")])
@pytest.mark.parametrize("variant", ["jax", "jax.grad tracer", "torch leaf", "torch non-leaf"])
def test_temperature_joule_heat_callback_live_values_fail_in_the_iteration(variant, method, callback):
    """Callbacks are not inspected in advance; a live result fails where they run."""
    arguments, rows = JOULE_CALLBACKS[callback]
    def call(v):
        with pytest.raises(JouleConvergenceError) as caught:
            solve_temperature_joule_heat(JOULE_MESH, **arguments(v), method=method)
        assert isinstance(caught.value.__cause__, TypeError)
        assert "cut the derivative" in str(caught.value.__cause__)
        assert len(caught.value.history) == rows
    _call_with_live(variant, call)
