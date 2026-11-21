# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""M3 of the external-mesh cavity gates: the dielectric slab refinement study.

A dielectric slab as an extruded layer region through ``solve_material_cavity``
against ``solve_material_cavity_box`` with the same slab as a region, at sizes
0.15, 0.1 and 0.05 m: the finest relative frequency difference is at most 5e-3
and smaller than the coarsest (docs/packages/galerkin/material_cavity.md,
"External meshes"). The meshes and solves are those of test_cavity_mesh.py; this
study takes about nine tenths of that file's time, so it has its own file and CI,
which assigns whole files to its parallel parts, can run it beside the rest.
"""
import numpy as np
import pytest

from test_cavity_mesh import _slab_pair


@pytest.mark.slow
def test_m3_dielectric_slab_layer_matches_the_box_solver_on_refinement():
    differences = []
    for h in (0.15, 0.1, 0.05):          # 0.3 m must be a grid plane of the box route
        box, through = _slab_pair(h)
        differences.append(np.max(np.abs(through.resonant_frequency - box.resonant_frequency)
                                  / np.abs(box.resonant_frequency)))
    print(f"M3 slab differences {differences}")
    assert differences[-1] <= 5e-3
    assert differences[0] > differences[-1]
