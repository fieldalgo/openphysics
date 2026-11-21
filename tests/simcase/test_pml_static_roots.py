# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""PML vector search whose roots all belong to the static beta^2 = 0 family.

With a small n_target every root nearest the shift is static; galerkin returns
none of them, and the selection refuses with diagnostics, as before, instead of
failing while building fields. Kernel lengths in micrometres; the slab of
tests/galerkin/test_pml_modes.py.
"""
import pytest

from simcase.physics_pml_modes import ModeSelectionError, solve
from test_pml_modes import slab_mesh


def test_all_static_search_is_refused_with_diagnostics():
    mesh, eps = slab_mesh(.05)
    walls = dict(left='pec', right='pec', top='pec', bottom='pec')
    pml = dict(thickness=dict(left=1., right=1.))
    reference = solve(mesh, eps, 1.55, walls, 1, 'vector', 2.85, pml, None)
    assert len(reference['neff']) == 1
    with pytest.raises(ModeSelectionError, match='accepted 0 of 1') as refusal:
        solve(mesh, eps, 1.55, walls, 1, 'vector', 0.05, pml, None)
    diagnostics = refusal.value.diagnostics
    assert diagnostics['candidates'] == [] and diagnostics['returned_modes'] == 0
