# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mode identity and full-field overlap checks independent of an eigensolver."""

import json

import numpy as np
import pytest

from galerkin import EdgeSpace, eval_edge_field, rectangle_mesh
from simcase.fields import VectorField
from simcase.tracking import ModeTracker, ModeTrackingError, tracking_settings


def _field(mesh, transverse, longitudinal):
    """Construct coherent display samples from the actual edge/nodal field."""
    space = EdgeSpace(mesh)
    transverse = np.asarray(transverse, dtype=complex)
    longitudinal = np.asarray(longitudinal, dtype=complex)
    electric = np.empty((mesh.num_triangles, transverse.shape[1], 3), dtype=complex)
    for mode in range(transverse.shape[1]):
        electric[:, mode, :2] = eval_edge_field(space, transverse[:, mode])
    electric[:, :, 2] = longitudinal[mesh.triangles].mean(axis=1)
    return VectorField(space.edges.copy(), transverse, longitudinal, electric)


def _constant_basis(mesh):
    """Exact constant Ex, Ey and imaginary Ez, with equal L2 norms."""
    space = EdgeSpace(mesh)
    delta = mesh.nodes[space.edges[:, 1]] - mesh.nodes[space.edges[:, 0]]
    transverse = np.column_stack((delta, np.zeros(space.num_edges)))
    longitudinal = np.zeros((mesh.num_nodes, 3), dtype=complex)
    longitudinal[:, 2] = 1j
    return _field(mesh, transverse, longitudinal)


def _mix(field, coefficients):
    coefficients = np.asarray(coefficients, dtype=complex)
    return VectorField(field.edges.copy(), field.transverse @ coefficients,
                       field.longitudinal @ coefficients,
                       np.einsum("tmc,mk->tkc", field.electric, coefficients))


def _select(field, indices):
    return _mix(field, np.eye(field.transverse.shape[1])[:, indices])


def _assert_same_fields(actual, expected, scales=None):
    np.testing.assert_array_equal(actual.edges, expected.edges)
    if scales is None:
        scales = np.ones(expected.transverse.shape[1])
    np.testing.assert_allclose(actual.transverse, expected.transverse * scales, atol=1e-13)
    np.testing.assert_allclose(actual.longitudinal, expected.longitudinal * scales, atol=1e-13)
    np.testing.assert_allclose(actual.electric, expected.electric * scales[None, :, None], atol=1e-13)


@pytest.fixture
def mesh():
    return rectangle_mesh(2.0, 1.0, 2, 2)


def test_crossing_keeps_field_identity_when_effective_index_ranks_swap(mesh):
    basis = _constant_basis(mesh)
    tracker = ModeTracker(mesh, 2, tracking_settings(2))
    _, initial, first = tracker.step(np.array([3.2, 2.8, 1.6]), basis, "lambda=1.4")
    assert first["candidate_ranks"] == [1, 2]
    # The same two fields exchange index order between sampled wavelengths.
    # The tracker must follow them instead of relabeling by descending n_eff.
    reordered = _select(basis, [1, 0, 2])
    neff, fields, evidence = tracker.step(np.array([3.1, 2.9, 1.5]), reordered, "lambda=1.5")
    np.testing.assert_array_equal(neff, [2.9, 3.1])
    assert evidence["candidate_ranks"] == [2, 1]
    np.testing.assert_allclose(evidence["overlaps"], [1.0, 1.0])
    _assert_same_fields(fields, initial)
    neff, fields, _ = tracker.step(np.array([3.4, 2.6, 1.4]), reordered, "lambda=1.6")
    np.testing.assert_array_equal(neff, [2.6, 3.4])
    _assert_same_fields(fields, initial)


def test_global_assignment_can_sacrifice_one_rows_best_match(mesh):
    basis = _constant_basis(mesh)
    # Previous fields A=Ex and B=.8 Ex+.6 Ey both prefer candidate X=Ex.
    # Candidate Y=.8 Ex-.6 Ey gives the squared score matrix
    # [[1, .64], [.64, .0784]]. A->Y, B->X is the unique best full assignment.
    previous = _mix(basis, [[1, 0.8], [0, 0.6], [0, 0]])
    current = _mix(basis, [[1, 0.8], [0, -0.6], [0, 0]])
    settings = tracking_settings(2, dict(min_overlap=0.6, min_margin=0.15))
    tracker = ModeTracker(mesh, 2, settings)
    tracker.step(np.array([3.2, 2.8]), previous, "first")
    neff, fields, evidence = tracker.step(np.array([3.1, 2.7]), current, "next")
    np.testing.assert_array_equal(neff, [2.7, 3.1])
    assert evidence["candidate_ranks"] == [2, 1]
    np.testing.assert_allclose(evidence["overlaps"], [0.64, 0.64], atol=1e-13)
    np.testing.assert_allclose(evidence["margins"], [0.2016, 0.2016], atol=1e-13)
    _assert_same_fields(fields, _select(current, [1, 0]))


def test_phase_and_amplitude_do_not_change_matches_or_relative_components(mesh):
    basis = _constant_basis(mesh)
    # Three orthogonal directions with every Cartesian component nonzero.
    directions = np.column_stack((np.array([1, 2, 3]) / np.sqrt(14),
                                  np.array([1, 1, -1]) / np.sqrt(3),
                                  np.array([-5, 4, -1]) / np.sqrt(42)))
    modes = _mix(basis, directions)
    tracker = ModeTracker(mesh, 2, tracking_settings(2))
    _, initial, _ = tracker.step(np.array([3.2, 2.8, 1.6]), modes, "first")
    amplitudes = np.array([2.5, 0.04, 7.0])
    phases = np.exp(1j * np.array([0.7, -1.2, 2.3]))
    candidates = _mix(_select(modes, [1, 0, 2]), np.diag(amplitudes * phases))
    originals = [value.copy() for value in (candidates.transverse, candidates.longitudinal, candidates.electric)]
    neff, aligned, evidence = tracker.step(np.array([3.1, 2.9, 1.5]), candidates, "next")
    np.testing.assert_array_equal(neff, [2.9, 3.1])
    np.testing.assert_allclose(evidence["overlaps"], [1.0, 1.0], atol=1e-13)
    # Alignment removes the arbitrary phase, without changing the amplitude or
    # independently rephasing transverse and longitudinal components.
    _assert_same_fields(aligned, initial, amplitudes[[1, 0]])
    reconstructed = _field(mesh, aligned.transverse, aligned.longitudinal)
    np.testing.assert_allclose(aligned.electric, reconstructed.electric, atol=1e-13)
    for original, after in zip(originals, (candidates.transverse, candidates.longitudinal, candidates.electric)):
        np.testing.assert_array_equal(after, original)


@pytest.mark.parametrize("length_scale", [1e-6, 1.0, 1e3])
def test_product_integrates_raw_edge_and_nodal_fields_not_centroid_samples(length_scale):
    mesh = rectangle_mesh(2 * length_scale, length_scale, 1, 1)
    space = EdgeSpace(mesh)
    endpoints = mesh.nodes[space.edges]
    delta = endpoints[:, 1] - endpoints[:, 0]
    midpoint = endpoints.mean(axis=1) / length_scale
    # Both functions are exactly representable: the Nedelec rotation (-y,x)
    # and nodal P1 Ez=i(x+2y), with x,y measured in the unit rectangle.
    rotation_integrals = -midpoint[:, 1] * delta[:, 0] + midpoint[:, 0] * delta[:, 1]
    transverse = np.column_stack((rotation_integrals, np.zeros(space.num_edges)))
    longitudinal = np.zeros((mesh.num_nodes, 2), dtype=complex)
    longitudinal[:, 1] = 1j * (mesh.nodes[:, 0] + 2 * mesh.nodes[:, 1]) / length_scale
    fields = _field(mesh, transverse, longitudinal)
    tracker = ModeTracker(mesh, 1, tracking_settings(1))
    # Independent polynomial integrals over [0,2] x [0,1]:
    # integral(x^2+y^2)=10/3, integral((x+2y)^2)=28/3.
    expected = np.diag([10 / 3, 28 / 3]) * length_scale**2
    np.testing.assert_allclose(tracker.product(fields, fields), expected, rtol=1e-13, atol=0)
    combined = _mix(fields, [[1], [1]])
    exact_norm = (38 / 3) * length_scale**2
    centroid_norm = np.sum(mesh.areas() * np.sum(abs(combined.electric[:, 0, :])**2, axis=1))
    assert centroid_norm < 0.9 * exact_norm
    factor = 2 * np.exp(0.73j)
    changed = _mix(combined, [[factor]])
    np.testing.assert_allclose(tracker.product(combined, changed), [[factor * exact_norm]], rtol=1e-13)
    np.testing.assert_allclose(tracker.product(changed, combined), [[factor.conjugate() * exact_norm]], rtol=1e-13)


def test_weak_overlap_fails_without_advancing_the_previous_field(mesh):
    basis = _constant_basis(mesh)
    tracker = ModeTracker(mesh, 1, tracking_settings(1))
    tracker.step(np.array([3.0]), _select(basis, [0]), "first")
    previous = tracker.previous
    candidates = _mix(basis, [[np.sqrt(0.79), 0], [np.sqrt(0.21), 0], [0, 1]])
    with pytest.raises(ModeTrackingError, match=r"lambda=1.6: mode 1 has weak overlap 0.79"):
        tracker.step(np.array([2.9, 2.0]), candidates, "lambda=1.6")
    assert tracker.previous is previous


def test_equal_complete_assignments_are_rejected_as_ambiguous(mesh):
    basis = _constant_basis(mesh)
    tracker = ModeTracker(mesh, 1, tracking_settings(1))
    tracker.step(np.array([3.0]), _select(basis, [0]), "first")
    candidates = _mix(basis, [[np.sqrt(0.9), np.sqrt(0.9)],
                              [np.sqrt(0.1), -np.sqrt(0.1)], [0, 0]])
    with pytest.raises(ModeTrackingError, match="ambiguous assignment margin"):
        tracker.step(np.array([2.9, 2.0]), candidates, "next")


@pytest.mark.parametrize("after_initial_step", [False, True])
def test_unselected_near_degenerate_partner_is_not_ignored(mesh, after_initial_step):
    basis = _select(_constant_basis(mesh), [0, 1])
    tracker = ModeTracker(mesh, 1, tracking_settings(1))
    if after_initial_step:
        tracker.step(np.array([3.0, 2.0]), basis, "first")
    with pytest.raises(ModeTrackingError, match="mode 1 is near-degenerate"):
        tracker.step(np.array([2.500005, 2.5]), basis, "degenerate point")


@pytest.mark.parametrize("after_initial_step", [False, True])
def test_missing_requested_mode_fails_instead_of_reusing_or_padding(mesh, after_initial_step):
    basis = _constant_basis(mesh)
    tracker = ModeTracker(mesh, 2, tracking_settings(2))
    if after_initial_step:
        tracker.step(np.array([3.0, 2.0]), _select(basis, [0, 1]), "first")
    previous = tracker.previous
    with pytest.raises(ModeTrackingError, match="requested 2 modes, found only 1 guided candidates"):
        tracker.step(np.array([2.9]), _select(basis, [0]), "cutoff")
    assert tracker.previous is previous


@pytest.mark.parametrize("saturated", [False, True])
def test_selected_last_candidate_requires_an_unsaturated_search(mesh, saturated):
    basis = _constant_basis(mesh)
    settings = tracking_settings(1, dict(search_modes=3 if saturated else 4))
    tracker = ModeTracker(mesh, 1, settings)
    _, initial, _ = tracker.step(np.array([3.2, 2.8, 2.4]), basis, "first")
    candidates = _select(basis, [1, 2, 0])
    if saturated:
        with pytest.raises(ModeTrackingError, match="candidate search boundary"):
            tracker.step(np.array([3.1, 2.6, 2.2]), candidates, "next")
    else:
        neff, fields, evidence = tracker.step(np.array([3.1, 2.6, 2.2]), candidates, "next")
        np.testing.assert_array_equal(neff, [2.2])
        assert evidence["candidate_ranks"] == [3]
        _assert_same_fields(fields, initial)


def test_only_possible_assignment_has_json_null_margin(mesh):
    field = _select(_constant_basis(mesh), [0])
    tracker = ModeTracker(mesh, 1, tracking_settings(1))
    tracker.step(np.array([3.0]), field, "first")
    _, _, evidence = tracker.step(np.array([2.9]), _mix(field, [[-2j]]), "next")
    assert evidence["margins"] == [None]
    assert json.loads(json.dumps(evidence, allow_nan=False))["margins"] == [None]
