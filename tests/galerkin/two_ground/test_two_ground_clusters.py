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
