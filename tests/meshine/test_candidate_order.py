# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Equal-radius conflicts must not depend on NumPy's platform-specific quicksort."""

import numpy as np
import pytest

from meshine.refine import _separate


@pytest.mark.parametrize("factor", [0.4, 0.7, 1.0])
def test_radius_priority_and_input_order_against_pairwise_filter(factor):
    # Many ties, with neighboring candidates competing for acceptance. Python's
    # tuple order is an independent specification of radius, then original index.
    radii = np.tile([1.0, 2.0, 1.0, 3.0], 16)
    candidates = np.column_stack((np.arange(len(radii)) * 0.4, np.zeros(len(radii))))
    kept = []
    for i in sorted(range(len(radii)), key=lambda i: (-radii[i], i)):
        if all(np.linalg.norm(candidates[i] - candidates[j]) > factor * radii[i] for j in kept):
            kept.append(i)
    expected = np.zeros(len(radii), dtype=bool)
    expected[kept] = True
    np.testing.assert_array_equal(_separate(candidates, radii, factor), expected)


def test_larger_radius_wins_and_ties_keep_first_candidate():
    candidates = np.array([[0.0, 0.0], [0.1, 0.0], [10.0, 0.0], [10.1, 0.0]])
    radii = np.array([1.0, 2.0, 3.0, 3.0])
    np.testing.assert_array_equal(_separate(candidates, radii), [False, True, True, False])
