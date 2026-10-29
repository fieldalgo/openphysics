# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""NumPy-only public functions refuse JAX and PyTorch values with a TypeError.

They compute with NumPy, so a live value would lose its derivative or fail
inside NumPy with an unrelated error. One case per guarded input; each skips
when its library is absent. docs/packages/galerkin/differentiation.md lists
these functions under "Refused, not approximated".
"""
import numpy as np
import pytest

from galerkin import (EdgeSpace3D, assemble_mode_system, assemble_stiffness, box_mesh, eval_edge_field_3d,
                      l2_error, rectangle_mesh, solve_dirichlet, solve_material_cavity_box)
from galerkin.material_cavity import CavityMaterialRegion
from galerkin.mode_coordinates import mode_coordinates, scalar_coordinate_system, solve_scalar_coordinates

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
