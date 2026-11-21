# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Finite-conductivity (Leontovich) cavity walls: references, consistency and gates.

The public solver's complex values follow exp(-i omega t) (a decaying mode has Im f < 0), as
refsol's wall-loss references do since the galerkin step (L3 commit 12), so their complex frequency is
compared as it is. The independent rebuild of the impedance operator is written in exp(+j omega t): it
conjugates the public values once (D8).
"""

import numpy as np
import pytest

from galerkin import CavityMaterialRegion, solve_cavity_box, solve_material_cavity_box
from galerkin.kernels import assemble_curlcurl_3d, assemble_edge_mass_3d
from galerkin.material_cavity import WALLS, _wall_faces, _wall_mass
from conftest import rate

C0 = 299792458.0
COPPER = 5.8e7
BOX = (1.0, 0.45, 0.8)          # no accidental degeneracy among the lowest modes


def Region(bounds, relative_permittivity=1.0, relative_permeability=1.0):
    """A material box from its (low, high) bounds per axis in m."""
    return CavityMaterialRegion(lower_corner_position=tuple(low for low, _ in bounds),
                                upper_corner_position=tuple(high for _, high in bounds),
                                relative_permittivity=relative_permittivity,
                                relative_permeability=relative_permeability)


def _edges_on(result, axis, position):
    endpoints = result.mesh.nodes[result.space.edges]
    return np.all(endpoints[:, :, axis] == position, axis=1)


def _check(result):
    count = result.mode_count
    assert not result.lossless
    assert np.all(result.resonant_frequency.imag < 0)
    assert np.all(result.iteration_count >= 1)
    assert np.all(result.relative_residual <= 1e-8)
    np.testing.assert_allclose(result.quality_factor, result.resonant_frequency.real
                               / (-2 * result.resonant_frequency.imag), rtol=1e-13)
    q = result.mass_normalized_electric_field_line_integral
    assert np.count_nonzero(q[result.pec_edges]) == 0
    # Edges of every finite-conductivity wall that are not on a PEC wall are free.
    lengths = result.mesh.nodes.max(axis=0)
    pec_mask = np.zeros(result.space.num_edges, dtype=bool)
    lossy_mask = np.zeros(result.space.num_edges, dtype=bool)
    for index, wall in enumerate(WALLS):
        on = _edges_on(result, index // 2, 0.0 if index % 2 == 0 else lengths[index // 2])
        (pec_mask if result.electrical_conductivity[wall] is None else lossy_mask)[on] = True
    np.testing.assert_array_equal(np.sort(result.pec_edges), np.flatnonzero(pec_mask))
    assert np.any(q[lossy_mask & ~pec_mask] != 0)
    vacuum_mass = assemble_edge_mass_3d(result.space)
    np.testing.assert_allclose(np.real(np.sum(q.conj() * (vacuum_mass @ q), axis=0)),
                               np.ones(count), rtol=1e-10)


def _independent_nonlinear_residual(result):
    """Rebuild T(k) on the SI mesh from public assemblies and the wall mass, under exp(+j omega t): the
    public eigenvalue and edge coefficients are conjugated once into that frame."""
    space = result.space
    free = np.setdiff1d(np.arange(space.num_edges), result.pec_edges)
    stiffness = assemble_curlcurl_3d(space)[free][:, free]
    mass = assemble_edge_mass_3d(space)[free][:, free]
    faces = _wall_faces(result.mesh, result.mesh.nodes.max(axis=0))
    eta0 = 4e-7 * np.pi * 1.00000000055 * C0
    out = []
    for j in range(result.mode_count):
        eigenvalue = np.conj(result.wavenumber_squared[j])
        k = np.sqrt(eigenvalue)
        operator = stiffness.astype(complex)
        for wall, sigma in result.electrical_conductivity.items():
            if sigma is not None:
                zs = np.sqrt(1j * k * eta0 / sigma)            # sqrt(j omega mu0 / sigma)
                operator = operator + (1j * k * eta0 / zs) * _wall_mass(space, faces[wall])[
                    free][:, free]
        x = np.conj(result.mass_normalized_electric_field_line_integral[free, j])
        left, right = operator @ x, eigenvalue * (mass @ x)
        out.append(np.linalg.norm(left - right) / (np.linalg.norm(left) + np.linalg.norm(right)))
    return np.array(out)


def test_te101_matches_pozar_and_satisfies_the_si_impedance_equation(refsol):
    a, b, d = BOX
    result = solve_material_cavity_box(box_size=BOX, subdivision_count=(8, 8, 8), mode_count=2,
                                       target_frequency=200e6, electrical_conductivity=COPPER)
    _check(result)
    pozar = refsol.wall_loss.pozar_te101_quality_factor(box_size=(a, b, d), electrical_conductivity=COPPER)
    assert abs(result.quality_factor[0] / pozar - 1) < 0.015
    # Independent rebuild uses the SI form j k eta0 / Zs, not the solver's sqrt(j k eta0 sigma).
    assert _independent_nonlinear_residual(result).max() < 1e-7


def test_wall_tangential_mass_integrates_constant_fields_exactly():
    """Edge circulations of a uniform field u give int_wall |u_t|^2 dS exactly."""
    result = solve_cavity_box(box_size=(1.0, 0.8, 0.6), subdivision_count=(3, 2, 4), mode_count=1,
                              target_frequency=3e8)
    space, nodes = result.space, result.mesh.nodes
    faces = _wall_faces(result.mesh, nodes.max(axis=0))
    u = np.array([0.3, -1.1, 0.7])
    q = (nodes[space.edges[:, 1]] - nodes[space.edges[:, 0]]) @ u
    areas = {"x": 0.8 * 0.6, "y": 1.0 * 0.6, "z": 1.0 * 0.8}
    for index, wall in enumerate(WALLS):
        axis = index // 2
        tangential = np.delete(u, axis)
        expected = areas["xyz"[axis]] * tangential @ tangential
        assert q @ (_wall_mass(space, faces[wall]) @ q) == pytest.approx(expected, rel=1e-12)


def test_wall_losses_add_and_single_walls_match_reference(refsol):
    total = solve_material_cavity_box(box_size=BOX, subdivision_count=(8, 8, 8), mode_count=3,
                                      target_frequency=200e6, electrical_conductivity=COPPER)
    inverse = np.zeros(3)
    for wall in WALLS:
        single = solve_material_cavity_box(box_size=BOX, subdivision_count=(8, 8, 8), mode_count=3,
                                           target_frequency=200e6,
                                           electrical_conductivity={wall: COPPER})
        _check(single)
        inverse += 1 / single.quality_factor
        reference = refsol.wall_loss.wall_loss_modes(box_size=BOX, frequency_limit=400e6,
                                                     electrical_conductivity={wall: COPPER})[:3]
        np.testing.assert_allclose(single.quality_factor,
                                   [m.quality_factor for m in reference], rtol=0.1)
    # First-order additivity: second-order terms are O(1/Q) relative.
    np.testing.assert_allclose(inverse, 1 / total.quality_factor, rtol=1e-3)


def test_highly_conducting_walls_approach_pec():
    pec = solve_cavity_box(box_size=BOX, subdivision_count=(4, 4, 4), mode_count=3, target_frequency=200e6)
    walls = solve_material_cavity_box(box_size=BOX, subdivision_count=(4, 4, 4), mode_count=3,
                                      target_frequency=200e6, electrical_conductivity=1e18)
    np.testing.assert_allclose(walls.resonant_frequency.real, pec.resonant_frequency, rtol=1e-9)
    assert np.all(walls.quality_factor > 1e8)


def test_dielectric_and_wall_losses_combine(refsol):
    eps, tan_delta = 2.2, 1e-4
    fill = ((0, BOX[0]), (0, BOX[1]), (0, BOX[2]))
    args = dict(mode_count=2, target_frequency=150e6)
    both = solve_material_cavity_box(box_size=BOX, subdivision_count=(8, 8, 8),
                                     regions=[Region(fill, eps * (1 + 1j * tan_delta))],
                                     electrical_conductivity=COPPER, **args)
    walls = solve_material_cavity_box(box_size=BOX, subdivision_count=(8, 8, 8), regions=[Region(fill, eps)],
                                      electrical_conductivity=COPPER, **args)
    dielectric = refsol.material_cavity.dielectric_loss_quality_factor(loss_tangent=tan_delta)
    np.testing.assert_allclose(1 / both.quality_factor,
                               1 / walls.quality_factor + 1 / dielectric, rtol=1e-4)
    reference = refsol.wall_loss.wall_loss_modes(box_size=BOX, frequency_limit=300e6, electrical_conductivity=COPPER,
                                                 relative_permittivity=eps)[:2]
    np.testing.assert_allclose(walls.quality_factor, [m.quality_factor for m in reference],
                               rtol=0.04)


def test_cube_degenerate_triplet_keeps_three_independent_modes(refsol):
    result = solve_material_cavity_box(box_size=(1, 1, 1), subdivision_count=(4, 4, 4), mode_count=3,
                                       target_frequency=200e6,
                                       electrical_conductivity=COPPER)
    _check(result)
    np.testing.assert_allclose(result.wavenumber_squared, result.wavenumber_squared[0], rtol=1e-8)
    reference = refsol.wall_loss.wall_loss_modes(box_size=(1, 1, 1), frequency_limit=250e6,
                                                 electrical_conductivity=COPPER)[0].quality_factor
    np.testing.assert_allclose(result.quality_factor, reference, rtol=0.06)


def test_dense_path_with_walls():
    result = solve_material_cavity_box(box_size=(1, .8, .6), subdivision_count=(2, 2, 2), mode_count=2,
                                       target_frequency=200e6,
                                       electrical_conductivity={"z0": 1e6, "x1": 3e6})
    _check(result)
    assert result.electrical_conductivity["y0"] is None


@pytest.mark.parametrize("value,match", [
    (0.0, "positive"), (-1.0, "positive"), (True, "positive"), (np.inf, "positive"),
    ({"top": 1.0}, "unknown walls"), ({"x0": -1.0}, "positive"),
])
def test_invalid_wall_conductivity(value, match):
    with pytest.raises(ValueError, match=match):
        solve_material_cavity_box(box_size=BOX, subdivision_count=(2, 2, 2), mode_count=1,
                                  target_frequency=2e8, electrical_conductivity=value)


@pytest.mark.slow
def test_wall_loss_mesh_convergence(refsol):
    """Fixed n=4,8,16, copper walls; four lowest non-degenerate modes against Q_c."""
    reference = refsol.wall_loss.wall_loss_modes(box_size=BOX, frequency_limit=400e6,
                                                 electrical_conductivity=COPPER)[:4]
    assert [m.indices for m in reference] == [(1, 0, 1), (2, 0, 1), (1, 1, 0), (0, 1, 1)]
    exact_q = np.array([m.quality_factor for m in reference])
    exact_f = np.array([m.resonant_frequency for m in reference])
    q_errors, f_errors = [], []
    for n in (4, 8, 16):
        result = solve_material_cavity_box(box_size=BOX, subdivision_count=(n,) * 3, mode_count=4,
                                           target_frequency=150e6,
                                           electrical_conductivity=COPPER)
        assert np.all(result.relative_residual <= 1e-8)
        q_errors.append(np.abs(result.quality_factor - exact_q) / exact_q)
        f_errors.append(np.abs(result.resonant_frequency - exact_f) / np.abs(exact_f))
    q_errors, f_errors = np.array(q_errors), np.array(f_errors)
    assert np.all(np.diff(q_errors, axis=0) < 0), q_errors
    orders = np.array([rate(q_errors[:, j]) for j in range(4)])
    assert np.all(orders[:, -1] > 1.8), orders
    assert np.all(q_errors[-1] < 8e-3), q_errors[-1]
    assert np.all(f_errors[-1] < 4e-3), f_errors[-1]
