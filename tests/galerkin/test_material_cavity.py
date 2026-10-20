# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Material-loaded PEC cavity: exact rescaling, slab references and fixed gates."""

import numpy as np
import pytest
import scipy.linalg as la

from galerkin import (CavityMaterialRegion as Region, MaterialCavityResult,
                      assemble_curlcurl_3d, assemble_edge_mass_3d, eval_edge_field_3d,
                      solve_cavity_box, solve_material_cavity_box)
from conftest import rate

C0 = 299792458.0
LENGTHS = (1.0, 0.8, 0.6)
SLAB = ((0, 1.0), (0, 0.8), (0, 0.3))


def _wall_edges(result):
    endpoints = result.mesh.nodes[result.space.edges]
    walls = np.zeros(result.space.num_edges, dtype=bool)
    for axis in range(3):
        for position in (0, result.mesh.nodes[:, axis].max()):
            walls |= np.all(endpoints[:, :, axis] == position, axis=1)
    return walls


def _independent_system(result):
    """Assemble per tetrahedron from the returned material arrays, one tet class at a time."""
    space = result.space
    free = np.flatnonzero(~_wall_edges(result))
    eps, mu = result.tet_relative_permittivity, result.tet_relative_permeability
    stiffness = np.zeros((len(free),) * 2, dtype=complex)
    mass = np.zeros((len(free),) * 2, dtype=complex)
    for value in np.unique(eps):
        mask = (eps == value).astype(float)
        mass += value * assemble_edge_mass_3d(space, mask)[free][:, free].toarray()
    for value in np.unique(mu):
        mask = (mu == value).astype(float)
        stiffness += assemble_curlcurl_3d(space, mask)[free][:, free].toarray() / value
    return free, stiffness, mass


def _check_result(result):
    assert isinstance(result, MaterialCavityResult)
    q, space, count = result.edge_coefficients, result.space, result.requested_modes
    assert space.mesh is result.mesh
    assert q.shape == (space.num_edges, count) and q.dtype == complex
    assert result.electric_field.shape == (count, result.mesh.num_tets, 3)
    assert result.time_convention == "exp(+j*omega*t)"
    assert result.search == "near_target"
    assert result.cluster_completeness == "not_certified"
    assert np.all(np.diff(result.resonant_frequencies_hz) >= 0)
    np.testing.assert_allclose(result.frequencies_hz,
                               C0 / (2 * np.pi) * np.sqrt(result.eigenvalues_m2), rtol=1e-12)
    np.testing.assert_array_equal(result.resonant_frequencies_hz, result.frequencies_hz.real)
    if result.lossless:
        assert np.all(result.eigenvalues_m2.imag == 0)
        assert np.all(np.isinf(result.quality_factors))
    else:
        assert np.all(result.frequencies_hz.imag > 0)
        np.testing.assert_allclose(result.quality_factors, result.frequencies_hz.real
                                   / (2 * result.frequencies_hz.imag), rtol=1e-13)
    walls = _wall_edges(result)
    np.testing.assert_array_equal(result.pec_edge_ids, np.flatnonzero(walls))
    assert np.count_nonzero(q[walls]) == 0
    vacuum_mass = assemble_edge_mass_3d(space)
    np.testing.assert_allclose(np.real(np.sum(q.conj() * (vacuum_mass @ q), axis=0)),
                               np.ones(count), rtol=1e-10)
    pivots = q[np.argmax(abs(q), axis=0), np.arange(count)]
    assert np.all(pivots.real > 0) and np.all(abs(pivots.imag) <= 1e-14 * pivots.real)
    free, stiffness, mass = _independent_system(result)
    left, right = stiffness @ q[free], (mass @ q[free]) * result.eigenvalues_m2
    residual = np.linalg.norm(left - right, axis=0) / (
        np.linalg.norm(left, axis=0) + np.linalg.norm(right, axis=0))
    assert residual.max() < 1e-9
    np.testing.assert_allclose(result.relative_residuals, residual, atol=1e-12)
    fields = np.stack([eval_edge_field_3d(space, v) for v in q.T])
    assert np.linalg.norm(fields - result.electric_field) / np.linalg.norm(fields) < 1e-12


def _slab(eps, mu=1.0):
    return [Region(SLAB, eps, mu)]


@pytest.mark.parametrize("n", [2, 4])
@pytest.mark.parametrize("eps,mu", [(4 - 0.2j, 1.5 - 0.03j), (2.0, 1.0), (1.0, 3 - 0.3j)])
def test_uniform_filling_is_an_exact_discrete_rescaling(n, eps, mu, refsol):
    vacuum = solve_cavity_box(LENGTHS, (n,) * 3, num_modes=5, target_frequency_hz=150e6)
    filled = solve_material_cavity_box(
        LENGTHS, (n,) * 3, regions=[Region(((0, 1), (0, .8), (0, .6)), eps, mu)], num_modes=5,
        target_frequency_hz=float(150e6 / np.sqrt(abs(eps * mu))))
    expected = [refsol.material_cavity.uniformly_filled_eigenvalue(v, eps, mu)
                for v in vacuum.eigenvalues_m2]
    np.testing.assert_allclose(np.sort_complex(filled.eigenvalues_m2),
                               np.sort_complex(expected), rtol=1e-11)
    exact_q = refsol.material_cavity.quality_factor(
        refsol.material_cavity.complex_frequency_from_eigenvalue(expected[0]))
    np.testing.assert_allclose(filled.quality_factors, exact_q, rtol=1e-9)
    assert filled.lossless == (np.imag(eps) == 0 and np.imag(mu) == 0)
    _check_result(filled)


def test_low_loss_uniform_dielectric_quality_factor_is_inverse_loss_tangent(refsol):
    tan_delta = 1e-3
    result = solve_material_cavity_box(LENGTHS, (4, 4, 4), regions=[
        Region(((0, 1), (0, .8), (0, .6)), 2.2 * (1 - 1j * tan_delta))],
        num_modes=3, target_frequency_hz=120e6)
    exact = refsol.material_cavity.dielectric_loss_quality_factor(tan_delta)
    np.testing.assert_allclose(result.quality_factors, exact, rtol=1e-9)
    assert abs(exact * tan_delta - 1) < 1e-6


def test_empty_regions_reproduce_the_vacuum_solver():
    vacuum = solve_cavity_box(LENGTHS, (4, 4, 4), num_modes=6, target_frequency_hz=240e6)
    result = solve_material_cavity_box(LENGTHS, (4, 4, 4), num_modes=6,
                                       target_frequency_hz=240e6)
    assert result.lossless
    np.testing.assert_allclose(result.eigenvalues_m2.real, vacuum.eigenvalues_m2, rtol=1e-10)
    _check_result(result)


@pytest.mark.parametrize("n,target,count", [(2, 150e6, 4), (4, 150e6, 6), (4, 260e6, 5), (6, 200e6, 6)])
def test_near_target_matches_complete_dense_complex_spectrum(n, target, count):
    result = solve_material_cavity_box(LENGTHS, (n,) * 3, regions=_slab(4 - 0.4j, 1.2 - 0.05j),
                                       num_modes=count, target_frequency_hz=target)
    _, stiffness, mass = _independent_system(result)
    values = la.eigvals(stiffness, mass)
    kernel = abs(values) < 1e-6
    assert np.count_nonzero(kernel) == (n - 1)**3
    physical = values[~kernel]
    sigma = (2 * np.pi * target / C0)**2
    expected = physical[np.argsort(abs(physical - sigma))[:count]]
    expected = expected[np.argsort(expected.real)]
    np.testing.assert_allclose(result.eigenvalues_m2, expected, rtol=1e-9)
    _check_result(result)


def test_lossless_slab_is_real_and_near_reference(refsol):
    reference = refsol.material_cavity.slab_loaded_cavity_modes(
        LENGTHS, 0.3, 300e6, slab_permittivity=4.0)[:4]
    result = solve_material_cavity_box(LENGTHS, (8, 8, 8), regions=_slab(4.0), num_modes=4,
                                       target_frequency_hz=50e6)
    assert result.lossless
    error = abs(result.eigenvalues_m2 - [m.eigenvalue_m2 for m in reference])
    assert np.max(error / abs(result.eigenvalues_m2)) < 0.015
    _check_result(result)


def test_slab_normal_along_x_matches_rotated_reference(refsol):
    """The reference stacks along z; permuting the box exercises other diagonals."""
    eps = 4 - 0.04j
    reference = refsol.material_cavity.slab_loaded_cavity_modes(
        LENGTHS, 0.3, 300e6, slab_permittivity=eps)[:3]
    result = solve_material_cavity_box(
        (0.6, 0.8, 1.0), (8, 8, 8), regions=[Region(((0, .3), (0, .8), (0, 1)), eps)],
        num_modes=3, target_frequency_hz=50e6)
    expected = np.array([m.eigenvalue_m2 for m in reference])
    assert np.max(abs(result.eigenvalues_m2 - expected) / abs(expected)) < 0.015
    np.testing.assert_allclose(result.quality_factors, [m.quality_factor for m in reference],
                               rtol=3e-3)


def test_regions_assign_centroids_and_later_regions_override():
    regions = [Region(((0, .5), (0, .8), (0, .6)), 3.0),
               Region(((.25, .5), (.2, .6), (.15, .45)), 2 - 0.1j, 1.5)]
    result = solve_material_cavity_box(LENGTHS, (4, 4, 4), regions=regions, num_modes=2,
                                       target_frequency_hz=150e6)
    centroids = result.mesh.nodes[result.mesh.tets].mean(axis=1)
    inner = np.all((centroids > [.25, .2, .15]) & (centroids < [.5, .6, .45]), axis=1)
    outer = (centroids[:, 0] < .5) & ~inner
    np.testing.assert_array_equal(result.tet_relative_permittivity[inner], 2 - 0.1j)
    np.testing.assert_array_equal(result.tet_relative_permeability[inner], 1.5)
    np.testing.assert_array_equal(result.tet_relative_permittivity[outer], 3.0)
    np.testing.assert_array_equal(result.tet_relative_permittivity[~inner & ~outer], 1.0)
    assert np.count_nonzero(inner) == 6 * 1 * 2 * 2
    assert not result.lossless
    _check_result(result)


@pytest.mark.parametrize("regions,match", [
    ([Region(((0, .3), (0, .8), (0, .6)), 2.0)], "grid plane"),
    ([Region(((0, .5), (0, .8), (0, .6)), 2 + 0.1j)], "passive"),
    ([Region(((0, .5), (0, .8), (0, .6)), 2.0, -1.0)], "positive real part"),
    ([Region(((.5, .25), (0, .8), (0, .6)), 2.0)], "low < high"),
    ([Region(((0, 1.25), (0, .8), (0, .6)), 2.0)], "low < high"),
    ([Region(((0, .5), (0, .8)), 2.0)], "three"),
    ([Region(((0, .5), (0, .8), (0, np.nan)), 2.0)], "finite"),
    ([Region(((0, .5), (0, .8), (0, .6)), True)], "complex"),
    (Region(((0, .5), (0, .8), (0, .6)), 2.0), "sequence"),
    ([((0, .5), (0, .8), (0, .6))], "CavityMaterialRegion"),
])
def test_invalid_regions(regions, match):
    with pytest.raises(ValueError, match=match):
        solve_material_cavity_box(LENGTHS, (4, 4, 4), regions=regions, num_modes=1,
                                  target_frequency_hz=150e6)


def test_shared_arguments_are_validated_like_the_vacuum_solver():
    with pytest.raises(ValueError, match="target_frequency_hz"):
        solve_material_cavity_box(LENGTHS, (2, 2, 2), target_frequency_hz=-1.0)
    with pytest.raises(ValueError, match="subdivisions"):
        solve_material_cavity_box(LENGTHS, (2, 0, 2), target_frequency_hz=1e8)
    with pytest.raises(RuntimeError, match="physical degrees of freedom"):
        solve_material_cavity_box(LENGTHS, (1, 1, 1), num_modes=2, target_frequency_hz=1e8)


CONVERGENCE_CASES = {
    "dielectric": (4 - 0.04j, 1.0),
    "dielectric_magnetic": (2.5 - 0.1j, 1.2 - 0.02j),
}


@pytest.mark.slow
@pytest.mark.parametrize("case", sorted(CONVERGENCE_CASES))
def test_slab_loaded_mesh_convergence(case, refsol):
    """Fixed sequence n=4,8,16; reference from the independent TE/TM-to-z roots.

    The six lowest modes are compared in ascending real order. The three lowest
    (TM11, TE10, TE01) are rate-gated; all six have fixed n=16 accuracy gates.
    """
    eps, mu = CONVERGENCE_CASES[case]
    reference = refsol.material_cavity.slab_loaded_cavity_modes(
        LENGTHS, 0.3, 400e6, slab_permittivity=eps, slab_permeability=mu)[:6]
    assert [(m.family, m.indices) for m in reference[:3]] == [
        ("TM_z", (1, 1)), ("TE_z", (1, 0)), ("TE_z", (0, 1))]
    exact = np.array([m.eigenvalue_m2 for m in reference])
    exact_q = np.array([m.quality_factor for m in reference])
    errors, q_errors = [], []
    for n in (4, 8, 16):
        result = solve_material_cavity_box(LENGTHS, (n,) * 3, regions=_slab(eps, mu),
                                           num_modes=6, target_frequency_hz=50e6)
        assert np.all(result.relative_residuals < 1e-8)
        errors.append(abs(result.eigenvalues_m2 - exact) / abs(exact))
        q_errors.append(abs(result.quality_factors - exact_q) / exact_q)
    errors, q_errors = np.array(errors), np.array(q_errors)
    assert np.all(np.diff(errors[:, :3], axis=0) < 0)
    orders = np.array([rate(errors[:, j]) for j in range(3)])
    assert np.all(orders[:, -1] > 1.8), orders
    assert np.all(errors[2] < 4e-3), errors[2]
    assert np.all(q_errors[2] < 1.5e-3), q_errors[2]
    assert np.all(q_errors[2] < q_errors[1]), q_errors
