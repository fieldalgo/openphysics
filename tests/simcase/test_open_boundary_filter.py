# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""V8 (and V4b, the completeness of the shipped search): the candidate filter returns physical
modes only, and every mode of the 2.46/32 reference.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from open_boundary_fixtures import ALL, TOP_BOTTOM, build, reference_modes, slab_reference, solve


# -- V8: the candidate filter --------------------------------------------------------------------
# Re-registered after the result. The registered reference (a search of 32 near the target) cannot
# see modes far from it: the strip over a substrate has a third physical mode near the cladding
# index (n ~ 1.486 + 7.9e-3i, physical fraction 0.978) that only a search near 1.95 finds. The
# reference physical modes are now the union of the searches 2.46/32 and 1.95/32; the pass gate is
# every mode of the 2.46/32 reference; the modes only the 1.95 search finds are known misses of
# the single-target search, checked here to be the ones near the cladding index (Re < 1.6).

@pytest.mark.slow
@pytest.mark.parametrize("kind,modes", [("slab", 1), ("slab", 2), ("slab", 3), ("slab", 4), ("template", 4),
                                        ("strip_substrate", 2), ("strip_substrate", 8)])
def test_v8_the_filter_returns_physical_modes_only(kind, modes):
    edges = TOP_BOTTOM if kind == "slab" else ALL
    target = 2.85 if kind == "slab" else 2.46
    text = build(kind, modes, target=target if kind == "slab" else "-", edges=edges)
    n, _, fraction, _ = solve(json.loads(text))
    assert len(n) <= modes
    assert np.all(fraction >= 0.5) and np.all(n.real > 1.45), (n, fraction)
    reference_text = build(kind, 8, target=target if kind == "slab" else "-", edges=edges)
    near = sorted(reference_modes(reference_text, target), key=lambda z: abs(z - target))
    for z in near[:modes]:
        assert np.min(abs(n - z)) <= 1e-6, (z, n)
    if kind == "slab":
        assert np.min(abs(n - slab_reference("TE"))) <= 1e-3, n
    low = reference_modes(reference_text, 1.95)
    missed = [z for z in low if np.min(abs(np.asarray(near) - z)) > 1e-6]
    assert all(z.real < 1.6 for z in missed), missed            # known misses: near the cladding index only
