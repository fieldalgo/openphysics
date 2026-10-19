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
    for small in (1e-9, 1e-7):                      # 1e7 was accepted before the limit became 1e6
        with pytest.raises(ValueError, match="ill conditioned"):
            whiten(np.diag([1.0, small]))
    inverse_root, diagnostics = whiten(np.diag([1.0, 1e-5]))
    assert diagnostics["gram_condition"] == pytest.approx(1e5)


def _unitary(rank, rng):
    return np.linalg.qr(rng.normal(size=(rank, rank)) + 1j * rng.normal(size=(rank, rank)))[0]


def _conditioned(metric, fields, rank, condition, rng):
    """`rank` fields of the span of `fields` whose Gram matrix has the given condition number."""
    head = columns(fields, np.eye(fields.transverse.shape[1])[:, :rank])
    orthonormal = columns(head, whiten(_gram(metric, head))[0])
    scales = np.logspace(0, -0.5 * np.log10(condition), rank) if rank > 1 else np.ones(1)
    return columns(orthonormal, _unitary(rank, rng) @ np.diag(scales) @ _unitary(rank, rng))


def test_guard_constants_are_consistent_with_the_roundoff_budget():
    """At the condition limit, roundoff alone stays below the defect guard, so that guard signals failures."""
    from simcase.subspace_tracking import (GRAM_CONDITION_MAX, ORTHONORMAL_DEFECT_MAX, SINGULAR_ROUNDOFF,
                                           UNIT_ROUNDOFF, frame_defect_budget)
    assert frame_defect_budget(8, GRAM_CONDITION_MAX, 10 ** 6) < ORTHONORMAL_DEFECT_MAX
    assert frame_defect_budget(8, 1e8, 10 ** 6) > 10 * ORTHONORMAL_DEFECT_MAX      # why 1e8 was inconsistent
    assert 2 * UNIT_ROUNDOFF * (8 + np.sqrt(10 ** 7)) < SINGULAR_ROUNDOFF


@pytest.mark.parametrize("cells", [(4, 3), (40, 20)])
def test_formed_frame_defect_stays_within_the_roundoff_budget(cells):
    """Measured on generic fields over rank, conditioning and mesh size.

    The largest observed ratios were about 2.3 of the 8 in frame_defect_budget and
    0.45 of the 2 in the excursion allowance, under both CI OpenBLAS kernels.
    """
    from simcase.subspace_tracking import UNIT_ROUNDOFF, frame_defect, frame_defect_budget
    mesh = rectangle_mesh(2.0, 1.0, *cells)
    metric = ElectricMetric(mesh)
    rng = np.random.default_rng(7)
    edges = EdgeSpace(mesh).num_edges
    fields = _field(mesh, rng.normal(size=(edges, 8)) + 1j * rng.normal(size=(edges, 8)),
                    rng.normal(size=(mesh.num_nodes, 8)) + 1j * rng.normal(size=(mesh.num_nodes, 8)))
    size = edges + mesh.num_nodes
    for rank in (1, 2, 4, 8):
        for condition in (1.0, 1e2, 1e4, 1e6 * 0.9):
            raw = _conditioned(metric, fields, rank, condition, rng)
            formed = []
            for coordinates in (raw, columns(raw, _unitary(rank, rng))):     # one span, two coordinate sets
                inverse_root, diagnostics = whiten(_gram(metric, coordinates))
                frame = columns(coordinates, inverse_root @ _unitary(rank, rng))
                defect = frame_defect(metric, frame)
                assert defect <= frame_defect_budget(rank, diagnostics["gram_condition"], size)
                formed.append((frame, defect))
            (first, d_first), (second, d_second) = formed
            excursion = np.linalg.svd(metric.product(first, second), compute_uv=False).max() ** 2 - 1
            implied = (1 + rank * d_first) * (1 + rank * d_second) - 1
            assert excursion - implied <= 2 * UNIT_ROUNDOFF * (rank + np.sqrt(size))


def test_same_span_in_ill_conditioned_coordinates_is_not_refused(mesh, basis):
    """Identical spans near the condition limit must match.

    Defects measured against the Gram matrix the whitening came from miss its
    roundoff amplified by the condition number; principal values of identical
    spans then exceeded the derived bound and were refused as non-orthonormal.
    """
    from simcase.subspace_tracking import frame_defect
    rng = np.random.default_rng(11)
    neff = np.array([2.0, 2.0 - 2e-5, 2.0 - 4e-5, 1.9])
    for trial in range(40):
        rank = 2 + trial % 2
        values = np.concatenate([neff[:rank], neff[3:]])
        condition = (1e5, 3e5, 9e5)[trial % 3]
        tracker = SubspaceTracker(mesh, rank, _settings(rank))
        cluster = _conditioned(ElectricMetric(mesh), basis, rank, condition, rng)
        guard = columns(basis, np.eye(8)[:, [7]])
        for location in ("seed", "same span"):
            mixed = columns(cluster, _unitary(rank, rng))
            stacked = VectorField(mixed.edges, np.column_stack([mixed.transverse, guard.transverse]),
                                  np.column_stack([mixed.longitudinal, guard.longitudinal]),
                                  np.concatenate([mixed.electric, guard.electric], axis=1))
            _, _, _, _, evidence = tracker.step(values, stacked, location)
        (record,) = evidence["clusters"]
        assert record["min_principal_squared"] == pytest.approx(1.0, abs=1e-6)
        assert record["orthonormal_defect"] == pytest.approx(frame_defect(tracker.metric, tracker.previous[0]),
                                                             rel=1e-6, abs=1e-15)


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
    # The cancelling formula is wrong at this angle: depending on BLAS roundoff it
    # returns 0 (sigma^2 rounds to one) or about sqrt(eps) ~ 1e-8, never ~1e-9.
    assert abs(naive - np.sin(1e-9)) > 0.5 * np.sin(1e-9)


def test_unwhitenable_candidate_of_a_tracked_rank_fails_instead_of_being_dropped(mesh, basis):
    neff = np.array([2.0, 2.0 - 2e-5, 1.9, 1.8])
    tracker = SubspaceTracker(mesh, 2, _settings(2))
    tracker.step(neff, columns(basis, np.eye(8)[:, :4]), "seed")
    state = tracker.previous
    degenerate = columns(basis, np.eye(8)[:, [0, 0, 2, 3]])         # the pair collapses to one direction
    with pytest.raises(ModeTrackingError, match="candidate cluster at ranks 1-2: .*rank deficient"):
        tracker.step(neff, degenerate, "collapsed")
    assert tracker.previous is state


def test_coarse_samples_cannot_see_an_excursion_between_them(mesh, basis):
    """Documented non-guarantee: equal endpoint spans pass even if the span leaves in between.

    The tracked direction rotates fully into an orthogonal one and back between two
    samples. Sampling only the endpoints reports a perfect match; refining the
    sampling exposes the excursion and the tracker refuses.
    """
    metric = ElectricMetric(mesh)
    orthonormal = columns(basis, whiten(metric.product(basis, basis))[0])
    neff = np.array([2.0, 1.9])

    def sample(t):
        angle = 0.5 * np.pi * np.sin(np.pi * t)      # 0 at t = 0 and 1, pi/2 at t = 0.5
        mix = np.zeros((8, 2))
        mix[0, 0], mix[5, 0] = np.cos(angle), np.sin(angle)
        mix[1, 1] = 1.0
        return columns(orthonormal, mix)

    coarse = SubspaceTracker(mesh, 1, _settings(1))
    coarse.step(neff, sample(0.0), "t=0")
    _, _, _, _, evidence = coarse.step(neff, sample(1.0), "t=1")
    assert evidence["clusters"][0]["min_principal_squared"] == pytest.approx(1.0)
    fine = SubspaceTracker(mesh, 1, _settings(1))
    with pytest.raises(ModeTrackingError, match="weakest principal value squared"):
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            fine.step(neff, sample(t), f"t={t}")


def test_avoided_crossing_identity_depends_on_sampling(mesh, basis):
    """H(t) = [[t, d], [d, -t]]: coarse samples follow field character, fine ones the eigenvector.

    Identity is field continuity at the samples, so the reported branch is the
    diabatic one for a coarse step and the adiabatic one for a fine step. Both
    are refined-step questions; the tracker does not choose a physical meaning.
    """
    metric = ElectricMetric(mesh)
    orthonormal = columns(basis, whiten(metric.product(basis, basis))[0])
    delta = 0.1

    def sample(t):
        values, vectors = np.linalg.eigh(np.array([[t, delta], [delta, -t]]))
        order = np.argsort(-values)
        mix = np.zeros((8, 3))
        mix[:2, :2] = vectors[:, order]
        mix[2, 2] = 1.0                                          # guard candidate
        neff = np.concatenate([2.0 + 0.01 * values[order], [1.9]])
        return neff, columns(orthonormal, mix)

    coarse = SubspaceTracker(mesh, 1, _settings(1))
    coarse.step(*sample(-1.0), "t=-1")
    _, _, _, _, evidence = coarse.step(*sample(1.0), "t=+1")
    assert evidence["candidate_ranks"] == [2]                   # followed the field character (diabatic)
    fine = SubspaceTracker(mesh, 1, _settings(1))
    for t in np.linspace(-1.0, 1.0, 81):
        _, _, _, _, evidence = fine.step(*sample(t), f"t={t:.3f}")
        assert evidence["candidate_ranks"] == [1]               # followed the upper eigenvector (adiabatic)
