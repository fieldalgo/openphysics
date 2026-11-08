# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Interior Dirichlet nodes in the 2D heat solvers (G6-1, G6-3, G6-4; HQ decision 2026-11-08).

A prescribed temperature on an internal line is an ordinary constraint: the solution is the
piecewise-linear one P1 reproduces exactly, and the reactions on the fixed interior nodes are
the heat that line injects, which the balance identity counts like any thermostat.
"""
import numpy as np
import pytest

from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.transient_heat import solve_transient_heat

K, T_LEFT, T_MID, T_RIGHT = 2.0, 0.0, 30.0, 100.0


def _plate(nx=16, ny=8):
    mesh = rectangle_mesh(1.0, 1.0, nx, ny)           # nodes at x = 0.5 exist for even nx
    mid = np.flatnonzero(np.abs(mesh.nodes[:, 0] - 0.5) < 1e-12)
    assert len(mid) == ny + 1
    exterior = set(np.concatenate(list(mesh.boundary.values())).tolist())
    assert any(int(i) not in exterior for i in mid)   # the line's inner nodes are interior
    dirichlet = {int(i): T_LEFT for i in mesh.boundary["left"]}
    dirichlet.update({int(i): T_RIGHT for i in mesh.boundary["right"]})
    dirichlet.update({int(i): T_MID for i in mid})
    return mesh, mid, dirichlet


def _exact(x):
    return np.where(x < 0.5, T_LEFT + (T_MID - T_LEFT) * x / 0.5, T_MID + (T_RIGHT - T_MID) * (x - 0.5) / 0.5)


def test_g6_1_a_fixed_interior_line_gives_the_exact_piecewise_linear_profile_and_its_injected_heat():
    mesh, mid, dirichlet = _plate()
    result = solve_steady_heat(mesh, conductivity=K, dirichlet=dirichlet)
    assert np.max(np.abs(result.temperature - _exact(mesh.nodes[:, 0]))) <= 1e-10 * T_RIGHT
    # heat enters through both sides (gradients 60 and 140 K/m) and the line removes it:
    # its outward rate is k (140 - 60) per metre of height; reaction is the inward contribution
    injected = K * ((T_RIGHT - T_MID) / 0.5 - (T_MID - T_LEFT) / 0.5) * 1.0
    assert abs(-float(result.reaction[mid].sum()) - injected) <= 1e-10 * injected
    balance = float(result.load.sum() + result.reaction.sum() - result.prescribed_outward_load.sum()
                    - result.convective_outward.sum())
    assert abs(balance) <= 1e-12 * injected


def test_g6_3_the_transient_solver_fixes_the_line_and_reaches_the_steady_profile():
    mesh, mid, dirichlet = _plate()
    initial = np.full(mesh.num_nodes, T_MID)
    for node, value in dirichlet.items():
        initial[node] = value
    times = np.array([0.0, 1.0, 2.0, 4.0, 8.0, 16.0])          # c / k = 1 s/m^2: 16 s is many diffusion times
    result = solve_transient_heat(mesh, conductivity=K, volumetric_heat_capacity=K, time_s=times,
                                  initial_temperature_k=initial, dirichlet=dirichlet)
    final = np.asarray(result.temperature_k)[-1]
    assert np.max(np.abs(final - _exact(mesh.nodes[:, 0]))) <= 1e-6 * T_RIGHT


def test_g6_4_a_node_outside_the_mesh_is_refused_and_the_other_solvers_keep_their_rule():
    mesh, _mid, dirichlet = _plate()
    with pytest.raises(ValueError, match="outside the mesh"):
        solve_steady_heat(mesh, conductivity=K, dirichlet={**dirichlet, mesh.num_nodes: 1.0})
    with pytest.raises(ValueError, match="inside the mesh"):
        solve_transient_heat(mesh, conductivity=K, volumetric_heat_capacity=K, time_s=np.array([0.0, 1.0]),
                             initial_temperature_k=np.zeros(mesh.num_nodes), dirichlet={mesh.num_nodes: 0.0})
    from galerkin.electric import solve_steady_electric
    interior = next(int(i) for i in _plate()[1] if int(i) not in
                    set(np.concatenate(list(mesh.boundary.values())).tolist()))
    with pytest.raises(ValueError, match="exterior mesh boundary"):
        solve_steady_electric(mesh, conductivity=1.0, dirichlet={interior: 1.0, int(mesh.boundary["left"][0]): 0.0})
