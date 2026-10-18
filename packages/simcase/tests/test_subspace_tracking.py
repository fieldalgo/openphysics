# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Algebraic checks of electric-l2-subspace-v1, independent of an eigensolver.

Every expected value comes from a construction with a known answer (exact
mixing matrices, hand-enumerated assignments, analytic rotations), not from the
tracker's own output.
"""

import numpy as np
import pytest

from galerkin import EdgeSpace, eval_edge_field, rectangle_mesh
from simcase.fields import VectorField
from simcase.subspace_tracking import (ElectricMetric, SUBSPACE_METHOD, SubspaceTracker, assign_clusters,
                                       columns, partition, principal_values, projection_sin_max_angle,
                                       subspace_settings, whiten)
from simcase.tracking import ModeTracker, ModeTrackingError, tracking_settings

SETTINGS = dict(method=SUBSPACE_METHOD, cluster_span_max=1e-4, external_gap_min=1e-3)


def _field(mesh, transverse, longitudinal):
    space = EdgeSpace(mesh)
    transverse = np.asarray(transverse, dtype=complex)
    longitudinal = np.asarray(longitudinal, dtype=complex)
    electric = np.empty((mesh.num_triangles, transverse.shape[1], 3), dtype=complex)
    for mode in range(transverse.shape[1]):
        electric[:, mode, :2] = eval_edge_field(space, transverse[:, mode])
    electric[:, :, 2] = longitudinal[mesh.triangles].mean(axis=1)
    return VectorField(space.edges.copy(), transverse, longitudinal, electric)


@pytest.fixture
def mesh():
    return rectangle_mesh(2.0, 1.0, 4, 3)


@pytest.fixture
def basis(mesh):
    """Eight generic, linearly independent complex fields with a fixed seed."""
    rng = np.random.default_rng(20261019)
    edges = EdgeSpace(mesh).num_edges
    transverse = rng.normal(size=(edges, 8)) + 1j * rng.normal(size=(edges, 8))
    longitudinal = rng.normal(size=(mesh.num_nodes, 8)) + 1j * rng.normal(size=(mesh.num_nodes, 8))
    return _field(mesh, transverse, longitudinal)


def _settings(num_modes, **extra):
    return tracking_settings(num_modes, dict(SETTINGS, **extra))


def _gram(metric, field):
    return metric.product(field, field)


# -- settings ----------------------------------------------------------------

def test_default_and_explicit_assignment_method_resolve_identically():
    assert tracking_settings(2) == tracking_settings(2, {"method": "electric-l2-assignment-v1"})
    assert "method" not in tracking_settings(2)


@pytest.mark.parametrize("supplied, message", [
    ({"method": SUBSPACE_METHOD}, "cluster_span_max, external_gap_min"),
    (dict(SETTINGS, degeneracy_tolerance=1e-5), "degeneracy_tolerance belongs"),
    (dict(SETTINGS, external_gap_min=1e-4), "greater than cluster_span_max"),
    (dict(SETTINGS, cluster_span_max=0), "positive"),
    (dict(SETTINGS, cluster_span_max=float("nan")), "finite"),
    (dict(SETTINGS, cluster_span_max=True), "finite"),
    (dict(SETTINGS, search_modes=2), "greater than num_modes"),
    (dict(SETTINGS, min_overlap=1.5), r"\(0, 1\]"),
    (dict(SETTINGS, extra=1), "unknown"),
    ({"method": "electric-l2-subspace-v2"}, "method must be one of"),
])
def test_subspace_settings_reject_invalid_values(supplied, message):
    with pytest.raises(ValueError, match=message):
        tracking_settings(2, supplied)


def test_subspace_settings_defaults():
    settings = subspace_settings(2, SETTINGS)
    assert settings == dict(method=SUBSPACE_METHOD, search_modes=6, cluster_span_max=1e-4,
                            external_gap_min=1e-3, min_overlap=0.8, min_margin=0.1)


# -- partition and metric -----------------------------------------------------

def test_partition_joins_only_close_neighbours_and_keeps_chains_whole():
    neff = np.array([2.0, 2.0 - 5e-5, 1.9, 1.9 - 8e-5, 1.9 - 1.6e-4, 1.5])
    assert partition(neff, 1e-4) == [(0, 2), (2, 5), (5, 6)]
    assert partition(np.array([]), 1e-4) == []


def test_electric_metric_integrates_exact_constant_fields(mesh):
    """Constant Ex, Ey and imaginary Ez have L2 norm squared equal to the area."""
    space = EdgeSpace(mesh)
    delta = mesh.nodes[space.edges[:, 1]] - mesh.nodes[space.edges[:, 0]]
    transverse = np.column_stack((delta, np.zeros(space.num_edges)))
    longitudinal = np.zeros((mesh.num_nodes, 3), dtype=complex)
    longitudinal[:, 2] = 1j
    gram = ElectricMetric(mesh).product(*(2 * [_field(mesh, transverse, longitudinal)]))
    np.testing.assert_allclose(gram, 2.0 * np.eye(3), atol=1e-13)


# -- whitening and rank -------------------------------------------------------

def test_whitening_returns_an_orthonormal_frame(mesh, basis):
    metric = ElectricMetric(mesh)
    inverse_root, diagnostics = whiten(_gram(metric, basis))
    np.testing.assert_allclose(_gram(metric, columns(basis, inverse_root)), np.eye(8), atol=1e-12)
    assert diagnostics["orthonormal_defect"] < 1e-12


def test_whitening_refuses_rank_loss_and_bad_metrics(mesh, basis):
    metric = ElectricMetric(mesh)
    duplicate = columns(basis, np.eye(8)[:, [0, 1, 1]])
    gram = _gram(metric, basis)[:3, :3]
    cases = [(_gram(metric, duplicate), "rank deficient"),
             (np.where(np.eye(3, dtype=bool), np.nan, gram), "non-finite"),
             (gram + np.triu(np.ones((3, 3)), 1), "not Hermitian"),
             (np.zeros((3, 3)), "zero"),
             (np.diag([1.0, -1.0]), "rank deficient")]
    for bad, message in cases:
        with pytest.raises(ValueError, match=message):
            whiten(bad)


def test_whitening_refuses_ill_conditioning_without_a_pseudoinverse():
    with pytest.raises(ValueError, match="ill conditioned"):
        whiten(np.diag([1.0, 1e-9]))
    inverse_root, diagnostics = whiten(np.diag([1.0, 1e-7]))
    assert diagnostics["gram_condition"] == pytest.approx(1e7)


# -- principal values ----------------------------------------------------------

def test_principal_values_are_invariant_under_nonsingular_coordinate_changes(mesh, basis):
    metric = ElectricMetric(mesh)
    first = columns(basis, np.eye(8)[:, :3])
    mixing = np.array([[1.0, 2.0 + 1j, 0.0], [0.5j, -1.0, 3.0], [0.0, 0.25, 1.0 - 2j]])
    second = columns(first, mixing)
    frames = [columns(f, whiten(_gram(metric, f))[0]) for f in (first, second)]
    squared, _, _ = principal_values(metric.product(*frames))
    np.testing.assert_allclose(squared, np.ones(3), atol=1e-12)


def test_worst_direction_rejects_a_lost_direction_despite_high_mean():
    """Rank six sharing five directions: mean 5/6 > 0.8, but one value is zero."""
    cross = np.diag([1, 1, 1, 1, 1, 0]).astype(complex)
    squared, _, _ = principal_values(cross)
    assert squared.mean() == pytest.approx(5 / 6) and squared.mean() > 0.8
    assert squared[-1] == 0


def test_principal_values_refuse_large_excursions_above_one():
    with pytest.raises(ValueError, match="exceeds one"):
        principal_values(np.array([[1.01]]))
    np.testing.assert_array_equal(principal_values(np.array([[1 + 1e-13]]))[0], [1.0])
    # Measured frame defects widen the allowance exactly as the norm bound implies.
    from simcase.subspace_tracking import excursion_bound
    bound = excursion_bound(2, 1e-9, 2e-9)
    assert bound == pytest.approx((1 + 2e-9) * (1 + 4e-9) - 1 + 1e-12)
    principal_values(np.array([[np.sqrt(1 + 0.9 * bound)]]), bound)
    with pytest.raises(ValueError, match="exceeds one"):
        principal_values(np.array([[np.sqrt(1 + 1.1 * bound)]]), bound)


# -- assignment ----------------------------------------------------------------

def test_assignment_matches_hand_enumerated_complete_matchings():
    scores = np.array([[0.90, 0.30, 0.20], [0.40, 0.95, 0.10]])
    allowed = np.ones_like(scores, dtype=bool)
    picked, margins = assign_clusters(scores, allowed)
    assert picked.tolist() == [0, 1]
    # Best total 1.85. Excluding (0,0): best is (0,2)+(1,1)=1.15. Excluding (1,1): (0,0)+(1,0)? not injective;
    # candidates (0,0)+(1,2)=1.00, (0,1)+(1,0)=0.70, (0,2)+(1,0)=0.60 -> 1.00.
    np.testing.assert_allclose(margins, [0.70, 0.85])


def test_assignment_respects_rank_and_reports_unavailable_alternatives():
    scores = np.array([[0.9, 0.99], [0.8, 0.1]])
    allowed = np.array([[True, False], [False, True]])
    picked, margins = assign_clusters(scores, allowed)
    assert picked.tolist() == [0, 1] and margins == [None, None]
    assert assign_clusters(scores, np.array([[True, False], [True, False]])) == (None, None)
    assert assign_clusters(np.ones((2, 1)), np.ones((2, 1), dtype=bool)) == (None, None)


def test_assignment_tie_has_zero_margin():
    picked, margins = assign_clusters(np.full((2, 2), 0.5), np.ones((2, 2), dtype=bool))
    assert margins == [0.0, 0.0]


# -- tracker -------------------------------------------------------------------

def _candidates(basis, transform):
    return columns(basis, transform)


# Candidate spectrum: a rank-2 pair, a rank-1 singleton and a lower guard.
NEFF = np.array([2.00, 2.00 - 2e-5, 1.95, 1.90])


def test_tracker_seed_selects_complete_clusters_and_keeps_raw_fields(mesh, basis):
    tracker = SubspaceTracker(mesh, 3, _settings(3))
    field = columns(basis, np.eye(8)[:, :4])
    neff, raw, transform, offsets, evidence = tracker.step(NEFF, field, "seed")
    np.testing.assert_array_equal(neff, NEFF[:3])
    np.testing.assert_array_equal(raw.transverse, field.transverse[:, :3])
    assert offsets.tolist() == [0, 2, 3]
    assert [c["rank"] for c in evidence["clusters"]] == [2, 1]
    assert evidence["clusters"][1]["lower_guard_rank"] == 4
    assert transform[:2, 2:].any() == False and transform[2:, :2].any() == False   # noqa: E712
    metric = ElectricMetric(mesh)
    frame = columns(raw, transform)
    gram = metric.product(frame, frame)
    np.testing.assert_allclose(gram[:2, :2], np.eye(2), atol=1e-12)     # orthonormal within each cluster;
    np.testing.assert_allclose(gram[2:, 2:], np.eye(1), atol=1e-12)     # clusters are not orthogonalized


def test_tracker_is_invariant_to_mixing_inside_clusters_and_aligns_to_the_previous_frame(mesh, basis):
    tracker = SubspaceTracker(mesh, 3, _settings(3))
    field = columns(basis, np.eye(8)[:, :4])
    _, raw0, t0, _, _ = tracker.step(NEFF, field, "first")
    previous = columns(raw0, t0)
    # Same spans, arbitrary nonsingular mixing within the pair, phase/amplitude on the singleton.
    mixing = np.eye(4, dtype=complex)
    mixing[:2, :2] = [[0.3 + 1j, 2.0], [-1.0, 0.5j]]
    mixing[2, 2] = 4.0 * np.exp(0.7j)
    _, raw1, t1, _, evidence = tracker.step(NEFF, columns(field, mixing), "second")
    np.testing.assert_allclose(columns(raw1, t1).transverse, previous.transverse, atol=1e-10)
    np.testing.assert_allclose(columns(raw1, t1).longitudinal, previous.longitudinal, atol=1e-10)
    for cluster in evidence["clusters"]:
        np.testing.assert_allclose(cluster["principal_squared"], 1.0, atol=1e-12)
    metric = ElectricMetric(mesh)
    cross = metric.product(previous, columns(raw1, t1))
    np.testing.assert_allclose(cross, cross.conj().T, atol=1e-12)
    assert np.linalg.eigvalsh(cross).min() > -1e-12


def test_aligned_rotation_follows_an_analytic_unitary_rotation(mesh, basis):
    """A slowly rotating exact pair: alignment undoes the rotation within the span."""
    metric = ElectricMetric(mesh)
    seed = columns(basis, np.eye(8)[:, :4])
    whitened = columns(seed, np.eye(4))
    pair_root, _ = whiten(metric.product(columns(seed, np.eye(4)[:, :2]), columns(seed, np.eye(4)[:, :2])))
    whitened_pair = np.eye(4, dtype=complex)
    whitened_pair[:2, :2] = pair_root
    orthonormal = columns(whitened, whitened_pair)
    tracker = SubspaceTracker(mesh, 3, _settings(3))
    tracker.step(NEFF, orthonormal, "0")
    for k, angle in enumerate((0.3, 0.6, 0.9)):
        rotation = np.eye(4, dtype=complex)
        rotation[:2, :2] = [[np.cos(angle), -np.exp(0.2j) * np.sin(angle)],
                            [np.exp(-0.2j) * np.sin(angle), np.cos(angle)]]
        _, raw, transform, _, _ = tracker.step(NEFF, columns(orthonormal, rotation), str(k))
        aligned = columns(raw, transform)
        np.testing.assert_allclose(aligned.transverse[:, :2], orthonormal.transverse[:, :2], atol=1e-10)


def test_rank_one_scores_reduce_to_the_assignment_tracker(mesh, basis):
    """For singleton clusters the subspace score is the legacy squared overlap."""
    neff = np.array([2.0, 1.9, 1.8, 1.7])
    field = columns(basis, np.eye(8)[:, :4])
    rotated = columns(basis, np.eye(8)[:, :4] + 0.2 * np.eye(8)[:, 4:8])
    legacy = ModeTracker(mesh, 2, tracking_settings(2))
    legacy.step(neff, field, "a")
    _, _, legacy_evidence = legacy.step(neff, rotated, "b")
    subspace = SubspaceTracker(mesh, 2, _settings(2))
    subspace.step(neff, field, "a")
    _, _, _, _, evidence = subspace.step(neff, rotated, "b")
    np.testing.assert_allclose([c["score"] for c in evidence["clusters"]], legacy_evidence["overlaps"], rtol=1e-12)


@pytest.mark.parametrize("neff, num_modes, extra, message", [
    (NEFF, 1, {}, "cut the observed cluster at candidate ranks 1-2; include all 2 vectors"),
    (np.array([2.0, 2.0 - 6e-5, 2.0 - 1.2e-4, 1.5]), 3, {}, "span .* exceeds cluster_span_max"),
    (np.array([2.0, 2.0 - 2e-5, 2.0 - 5e-4, 1.5]), 2, {}, "lower gap .* not above external_gap_min"),
    (np.array([2.0, 2.0 - 2e-5]), 2, {}, "no lower guided candidate was found"),
    (np.array([2.0, 2.0 - 2e-5, 1.9, 1.9 - 2e-5]), 4, {"search_modes": 5}, "no lower guided candidate"),
    (np.array([2.0]), 2, {}, "found only 1 guided candidates"),
])
def test_tracker_seed_refuses_incomplete_or_ambiguous_clusters(mesh, basis, neff, num_modes, extra, message):
    tracker = SubspaceTracker(mesh, num_modes, _settings(num_modes, **extra))
    with pytest.raises(ModeTrackingError, match=message):
        tracker.step(neff, columns(basis, np.eye(8)[:, :len(neff)]), "seed")
    assert tracker.previous is None


def test_saturated_budget_with_guard_present_is_accepted(mesh, basis):
    neff = np.array([2.0, 2.0 - 2e-5, 1.9, 1.9 - 2e-5])
    tracker = SubspaceTracker(mesh, 2, _settings(2, search_modes=4))
    _, _, _, _, evidence = tracker.step(neff, columns(basis, np.eye(8)[:, :4]), "seed")
    assert evidence["saturated"] and evidence["clusters"][0]["lower_guard_rank"] == 3


def test_merge_split_and_lost_direction_fail_without_advancing_state(mesh, basis):
    field = columns(basis, np.eye(8)[:, :4])
    tracker = SubspaceTracker(mesh, 3, _settings(3))
    tracker.step(NEFF, field, "seed")
    state = tracker.previous
    merged = np.array([2.0, 2.0 - 2e-5, 2.0 - 4e-5, 1.9])          # pair absorbs the singleton
    with pytest.raises(ModeTrackingError, match="no complete equal-rank assignment|no candidate cluster"):
        tracker.step(merged, field, "merge")
    split = np.array([2.0, 1.97, 1.95, 1.90])                         # pair splits into singletons
    with pytest.raises(ModeTrackingError, match="no complete equal-rank assignment"):
        tracker.step(split, field, "split")
    lost = columns(basis, np.eye(8)[:, [0, 5, 2, 3]])                 # one pair direction replaced
    with pytest.raises(ModeTrackingError, match="weakest principal value squared .* direction was lost"):
        tracker.step(NEFF, lost, "lost")
    assert tracker.previous is state


def test_equal_rank_swap_is_followed_and_ambiguity_is_refused(mesh, basis):
    """Two singletons exchange order; a 50/50 mixture of them is ambiguous."""
    neff = np.array([2.0, 1.9, 1.8])
    field = columns(basis, np.eye(8)[:, :3])
    tracker = SubspaceTracker(mesh, 2, _settings(2))
    tracker.step(neff, field, "seed")
    swapped, raw, _, _, evidence = tracker.step(neff, columns(field, np.eye(3)[:, [1, 0, 2]]), "swap")
    np.testing.assert_array_equal(raw.transverse, field.transverse[:, [0, 1]])
    assert evidence["candidate_ranks"] == [2, 1]
    tracker = SubspaceTracker(mesh, 2, _settings(2))
    tracker.step(neff, field, "seed")
    metric = ElectricMetric(mesh)
    orthonormal = columns(field, whiten(metric.product(field, field))[0])
    tracker = SubspaceTracker(mesh, 2, _settings(2, min_overlap=0.4))
    tracker.step(neff, orthonormal, "seed")
    blend = np.eye(3, dtype=complex)
    blend[:2, :2] = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
    with pytest.raises(ModeTrackingError, match="ambiguous assignment margin"):
        tracker.step(neff, columns(orthonormal, blend), "blend")


def test_projection_residual_angle_is_accurate_where_one_minus_cosine_cancels(mesh, basis):
    """A known tiny rotation out of the span: sqrt(1 - sigma^2) loses it, the residual does not."""
    metric = ElectricMetric(mesh)
    orthonormal = columns(basis, whiten(metric.product(basis, basis))[0])
    previous = columns(orthonormal, np.eye(8)[:, :2])
    for angle in (1e-3, 1e-6, 1e-9):
        mix = np.zeros((8, 2))
        mix[0, 0] = mix[1, 1] = 1.0
        mix[0, 0], mix[5, 0] = np.cos(angle), np.sin(angle)
        current = columns(orthonormal, mix)
        cross = metric.product(previous, current)
        assert projection_sin_max_angle(metric, previous, current, cross) == pytest.approx(np.sin(angle), rel=1e-6)
    naive = np.sqrt(max(0.0, 1 - principal_values(cross)[0][-1]))
    assert abs(naive - np.sin(1e-9)) > 1e-9          # the cancelling formula is wrong at this angle
