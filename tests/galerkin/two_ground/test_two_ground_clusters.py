# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Plane-scaled interpolation boxes after a failed one-box matrix check."""
import numpy as np
import pytest
import galerkin.laplace_two_ground as module
from galerkin import _laplace_panels as kernel
from galerkin.laplace_two_ground import solve_two_ground_rectangle as solve

H = 5e-4  # plane spacing


def rectangle(x0, width, y0, thickness):
    return np.array([[x0, y0], [x0 + width, y0], [x0 + width, y0 + thickness], [x0, y0 + thickness]])


def coupled():
    """Two 0.2 mm traces, 0.2 mm apart, centred between the planes (coupled stripline)."""
    y0 = (H - 17.5e-6) / 2
    return [rectangle(2.7e-3, 2e-4, y0, 17.5e-6), rectangle(3.1e-3, 2e-4, y0, 17.5e-6)], 6e-3


def near_plane():
    """A 0.3 mm trace 0.05 mm below the top plane (a layered stripline trace)."""
    return [rectangle(2.85e-3, 3e-4, H - 5e-5 - 35e-6, 35e-6)], 6e-3


def single(width=2e-4):
    y0 = (H - 17.5e-6) / 2
    return [rectangle(3e-3 - width / 2, width, y0, 17.5e-6)], 6e-3


def normalized(polygons, width, count):
    polygons, unit, w, h = module._admit(polygons, width, H, count)
    a, b, owners = kernel.panels(polygons, count, 'cubic')
    images = max(8, int(np.ceil(h / w * np.log(1e14) / np.pi)) + 1)
    return a, b, owners, w, h, images


@pytest.mark.parametrize('geometry', [coupled, near_plane], ids=['coupled', 'near-plane'])
def test_failed_one_box_check_is_repeated_on_plane_scaled_boxes(geometry):
    polygons, width = geometry()
    result = solve(polygons, width=width, height=H, panels_per_edge=64, ground_modes=512, interpolation_degree=14)
    assert result.single_box_matrix_error > 1e-10 and result.smooth_interpolation_boxes > 1
    assert result.matrix_refinement_error <= 1e-10
    a, b, owners, w, h, images = normalized(polygons, width, 64)
    labels = module._clusters(a, b, owners, w, h)
    mids = (a + b) / 2
    for label in np.unique(labels):
        group = labels == label
        owner = np.unique(owners[group])
        assert len(owner) == 1
        points = np.concatenate((a[owners == owner[0]], b[owners == owner[0]]))
        gap = min(points[:, 1].min(), h - points[:, 1].max())
        assert np.ptp(mids[group, 0]) <= gap
    # Panel refinement (64 -> 128) and a finer interpolation reference stay well
    # inside the stored-reference allowances used elsewhere (5e-4 C0, 1% Q).
    finer = solve(polygons, width=width, height=H, panels_per_edge=128, ground_modes=512, interpolation_degree=16)
    c, q = result.capacitance_per_permittivity, result.current_gram
    assert np.max(abs(finer.capacitance_per_permittivity - c)) / np.max(abs(c)) < 1e-5
    assert np.max(abs(finer.current_gram - q)) / np.max(abs(q)) < 5e-3
    reference = module._matrix(a, b, w, h, degree=16, order=8, images=images + 4, labels=labels)[0]
    used = module._matrix(a, b, w, h, degree=14, order=8, images=images + 2, labels=labels)[0]
    assert np.max(abs(used - reference)) / np.max(abs(reference)) < 1e-12


def test_plane_scaled_boxes_reproduce_one_box_where_both_converge():
    a, b, owners, w, h, images = normalized(*single(5e-4), 64)
    labels = module._clusters(a, b, owners, w, h)
    assert labels.max() > 0
    one = module._matrix(a, b, w, h, degree=16, order=8, images=images + 2)[0]
    split = module._matrix(a, b, w, h, degree=16, order=8, images=images + 2, labels=labels)[0]
    assert np.max(abs(one - split)) / np.max(abs(one)) < 1e-11


def test_passing_one_box_check_never_builds_plane_scaled_boxes(monkeypatch):
    monkeypatch.setattr(module, '_clusters', lambda *a, **k: pytest.fail('plane-scaled boxes built'))
    polygons, width = single()
    result = solve(polygons, width=width, height=H, panels_per_edge=64, interpolation_degree=14)
    assert result.smooth_interpolation_boxes == 1 and result.single_box_matrix_error is None


def side_wall():
    """A 0.4 mm trace 0.05 mm from the left wall, centred between the planes."""
    y0 = (H - 17.5e-6) / 2
    return [rectangle(5e-5, 4e-4, y0, 17.5e-6)], 3e-3


def test_cluster_near_a_side_wall_uses_wall_scaled_boxes_without_a_one_box_attempt():
    polygons, width = side_wall()
    result = solve(polygons, width=width, height=H, panels_per_edge=64, ground_modes=512, interpolation_degree=14)
    assert result.smooth_interpolation_boxes > 1 and result.single_box_matrix_error is None
    assert result.matrix_refinement_error <= 1e-10
    finer = solve(polygons, width=width, height=H, panels_per_edge=128, ground_modes=512, interpolation_degree=16)
    c = result.capacitance_per_permittivity
    assert np.max(abs(finer.capacitance_per_permittivity - c)) / np.max(abs(c)) < 1e-5


def test_zero_extent_box_is_refused_not_interpolated():
    a, b, owners, w, h, images = normalized(*single(5e-4), 16)
    labels = np.arange(len(a))  # one panel per box: straight panels have zero extent across
    with pytest.raises(ValueError, match='zero extent'):
        module._matrix(a, b, w, h, degree=12, order=8, images=images, labels=labels)


def test_unresolved_plane_scaled_check_still_refuses(monkeypatch):
    polygons, width = coupled()
    original = module._matrix

    def noisy(*args, labels=None, **kwargs):
        matrix, reciprocity = original(*args, labels=labels, **kwargs)
        if labels is not None and kwargs['degree'] == 12:
            matrix = matrix * (1 + 1e-9)
        return matrix, reciprocity
    monkeypatch.setattr(module, '_matrix', noisy)
    with pytest.raises(ValueError, match='matrix quadrature/interpolation failed'):
        solve(polygons, width=width, height=H, panels_per_edge=64, interpolation_degree=14)


def test_layered_coupled_coplanar_section_passes_the_ground_check_with_margin():
    """SIPI coupled_layered_coplanar_stripline: 0.3 mm pair, 0.2 mm gaps, 1 mm grounds, 35 um copper
    at 0.1 mm in a 0.2 mm plane spacing. Its top-plane ground-to-ground Gram entry is about 3e-6 of
    its Cauchy-Schwarz bound; as a cosine sum it was left by cancellation, and the entrywise ground
    check (1.1e-10) failed by rounding. The physical-space Gram keeps its relative accuracy."""
    y0, t = 1e-4, 35e-6
    polygons = [rectangle(1.6e-3, 3e-4, y0, t), rectangle(2.1e-3, 3e-4, y0, t),
                rectangle(4e-4, 1e-3, y0, t), rectangle(2.6e-3, 1e-3, y0, t)]
    result = solve(polygons, width=4e-3, height=2e-4, panels_per_edge=64, ground_modes=512,
                   interpolation_degree=14)
    assert result.smooth_interpolation_boxes == 42
    assert result.ground_refinement_error < 1e-12


def test_smooth_kernel_is_reciprocal():
    """Plane-scaled blocks j > i + 1 are filled by transposition: the smooth kernel is reciprocal."""
    rng = np.random.default_rng(3)
    w, h = 1., .1
    targets = np.column_stack((rng.uniform(.2, .5, 40), rng.uniform(.01, .09, 40)))
    sources = np.column_stack((rng.uniform(.4, .8, 30), rng.uniform(.01, .09, 30)))
    forward = module._smooth(targets, sources, w, h, 10)
    backward = module._smooth(sources, targets, w, h, 10)
    assert np.max(abs(forward - backward.T)) <= 1e-14 * np.max(abs(forward))


def layered_coupled(count):
    """The layered coupled coplanar section below, normalized: many plane-scaled boxes."""
    y0, t = 1e-4, 35e-6
    polygons = [rectangle(1.6e-3, 3e-4, y0, t), rectangle(2.1e-3, 3e-4, y0, t),
                rectangle(4e-4, 1e-3, y0, t), rectangle(2.6e-3, 1e-3, y0, t)]
    polygons, unit, w, h = module._admit(polygons, 4e-3, 2e-4, count, side_walls=False, max_aspect=64)
    a, b, owners = kernel.panels(polygons, count, 'cubic')
    images = max(8, int(np.ceil(h / w * np.log(1e14) / np.pi)) + 1)
    return a, b, owners, w, h, images


def test_plane_scaled_matrix_equals_every_box_pair_computed():
    a, b, owners, w, h, images = layered_coupled(16)
    labels = module._clusters(a, b, owners, w, h)
    groups = [np.flatnonzero(labels == label) for label in np.unique(labels)]
    assert len(groups) > 10
    boxes = box_grids(a, b, labels, 12)
    expected = kernel.half_matrix(a, b, order=8)
    for i, rows in enumerate(groups):
        for j, columns in enumerate(groups):
            expected[np.ix_(rows, columns)] += boxes[i][1] @ module._smooth(boxes[i][0], boxes[j][0], w, h, images) @ boxes[j][1].T
    actual, reciprocity = module._matrix(a, b, w, h, degree=12, order=8, images=images, labels=labels)
    assert np.max(abs(actual - (expected + expected.T) / 2)) <= 1e-14 * np.max(abs(expected))
    assert reciprocity <= 1e-10


def box_grids(a, b, labels, degree):
    return [module._box(a[g], b[g], degree) for g in (np.flatnonzero(labels == label) for label in np.unique(labels))]


@pytest.mark.parametrize('pair', [(1, 1), (1, 2), (2, 1)], ids=['diagonal', 'neighbour', 'neighbour-reversed'])
def test_raw_reciprocity_still_compares_independent_blocks(monkeypatch, pair):
    """Diagonal blocks and both orders of neighbouring boxes are computed, not transposed:
    an error in only one of them is still caught by the raw reciprocity check."""
    a, b, owners, w, h, images = layered_coupled(16)
    labels = module._clusters(a, b, owners, w, h)
    grids = box_grids(a, b, labels, 12)
    original = module._smooth

    def skewed(targets, sources, *args):
        out = original(targets, sources, *args)
        if np.array_equal(targets, grids[pair[0]][0]) and np.array_equal(sources, grids[pair[1]][0]):
            out = out + 1e-6 * np.max(abs(out)) * np.triu(np.ones_like(out), 1)
        return out
    monkeypatch.setattr(module, '_smooth', skewed)
    with pytest.raises(ValueError, match='raw matrix reciprocity failed'):
        module._matrix(a, b, w, h, degree=12, order=8, images=images, labels=labels)


def test_boxes_with_fewer_panels_than_the_degree_are_integrated_directly(monkeypatch):
    """A box of n < degree panels uses n x degree panel Gauss points, fewer than the degree**2 grid."""
    a, b, owners, w, h, images = layered_coupled(64)
    labels = module._clusters(a, b, owners, w, h)
    counts = np.bincount(labels)
    used = {'direct': [], 'grid': []}
    direct, projection = module._direct, module._projection
    monkeypatch.setattr(module, '_direct', lambda a, b, d: used['direct'].append(len(a)) or direct(a, b, d))
    monkeypatch.setattr(module, '_projection', lambda a, b, lo, hi, d: used['grid'].append(len(a)) or projection(a, b, lo, hi, d))
    module._matrix(a, b, w, h, degree=14, order=8, images=images, labels=labels)
    assert sorted(used['direct']) == sorted(counts[counts < 14].tolist()) and used['direct']
    assert sorted(used['grid']) == sorted(counts[counts >= 14].tolist()) and used['grid']


def test_direct_box_integral_matches_the_interpolated_one():
    """Both integrate the same smooth kernel over the same panels; they differ only by interpolation error."""
    a, b, owners, w, h, images = layered_coupled(64)
    labels = module._clusters(a, b, owners, w, h)
    counts = np.bincount(labels)
    small = [np.flatnonzero(labels == label) for label in np.flatnonzero((counts >= 4) & (counts < 14))[:3]]
    for rows in small:
        for columns in small:
            boxes = []
            for g in (rows, columns):
                points = np.concatenate((a[g], b[g]))
                boxes.append((module._direct(a[g], b[g], 14),
                              module._projection(a[g], b[g], points.min(axis=0), points.max(axis=0), 16)))
            direct = boxes[0][0][1] @ module._smooth(boxes[0][0][0], boxes[1][0][0], w, h, images) @ boxes[1][0][1].T
            grid = boxes[0][1][1] @ module._smooth(boxes[0][1][0], boxes[1][1][0], w, h, images) @ boxes[1][1][1].T
            assert np.max(abs(direct - grid)) <= 1e-13 * np.max(abs(grid))
