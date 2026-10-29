# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Finite-thickness default mesh: cost and refinement, not an accuracy oracle."""

import numpy as np
import pytest

from sipi import CrossSection, Layer, Trace


def microstrip(thickness):
    return CrossSection(
        [Layer('substrate', 1e-3, 4.3), Layer('air', 20e-3)],
        [Trace('s', 0, 1e-3, 1e-3, thickness)], width=40e-3)


@pytest.mark.parametrize('thickness', [0.0, pytest.param(5e-6, marks=pytest.mark.slow), 35e-6, 105e-6])
def test_default_resolves_thin_and_thick_traces(thickness):
    cs = microstrip(thickness)
    edge, far = cs._sizes(None, None)
    m = cs.mesh()
    p = m.line_parameters()
    fine = cs.analyze(edge_size=edge / 2, far_size=far / 2, grade=0.075)
    # Pre-registered mesh sensitivity bound; external/analytical comparisons
    # are separate. Both material and vacuum solves enter these quantities.
    assert p.z0 == pytest.approx(fine.z0, rel=5e-3)
    assert p.eps_eff == pytest.approx(fine.eps_eff, rel=5e-3)
    if thickness == 35e-6:
        legacy = cs.mesh(edge_size=thickness / 100)
        assert m.mesh.num_nodes < 0.5 * legacy.mesh.num_nodes


def test_thick_coupled_pair_default_matrix_refinement():
    w, gap, h, t = 0.4e-3, 0.1e-3, 0.5e-3, 35e-6
    cs = CrossSection(
        [Layer('lo', h, 4.0), Layer('hi', h, 4.0)],
        [Trace('p', -(w + gap) / 2, w, h - t / 2, t),
         Trace('n', (w + gap) / 2, w, h - t / 2, t)],
        width=6e-3, top='ground')
    edge, far = cs._sizes(None, None)
    p = cs.analyze()
    fine = cs.analyze(edge_size=edge / 2, far_size=far / 2, grade=0.075)
    for name in ('C', 'C0', 'L'):
        np.testing.assert_allclose(getattr(p, name), getattr(fine, name), rtol=5e-3)
    for name in ('z_even', 'z_odd', 'z_diff', 'z_common'):
        assert p.even_odd()[name] == pytest.approx(fine.even_odd()[name], rel=5e-3)


def test_explicit_edge_size_overrides_thickness_default():
    cs = microstrip(35e-6)
    # An explicit resolution remains usable for reproducing earlier studies.
    assert cs._sizes(0.35e-6, 0.5e-3) == (0.35e-6, 0.5e-3)
    assert cs._sizes(20e-6, 0.5e-3) == (20e-6, 0.5e-3)
