# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``meshloom.generate3d`` on the synthetic small-angle surfaces, each triangle a facet.

These are the minimal synthetic repros of the small-angle rules (C10, C13). The surfaces
come from ``small_angle_cases.py``: a closed body with one feature at the stated strength.

- An in-plane fan at 1 degree, and a needle triangle at 1 degree.
- A vertex 1e-8 or 1e-6 of the diagonal from a non-incident edge. A segment then lies
  almost in a neighbouring facet's plane.
- A wedge at 3 degrees, and a fold at 0.001 degrees from flat.

Before the rules, the fan, needle and close cases inserted points without end. Small
subfacets inside a small angle were split for quality, and segments across a tiny angle
encroached each other. Facet points and segment points nearly in one plane split each
other in turn. Each mesh must now pass V1-V4 (``test_adversarial.check``: positive
tetrahedra, consistent faces, the facets tiled, the exact volume). ``max_points`` bounds a
regressed run instead of a clock: the rules need at most about 3000 points here.
"""

import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import test_adversarial as A
from small_angle_cases import surface
from test_repair import volume

CASES = [
    ("fan", 1, 0.25),
    ("needle", 1, 0.25),
    ("close", 1e-8, 0.25),
    ("close", 1e-6, 0.1),
    ("wedge", 3, 0.25),
    ("fold", 0.001, 0.25),
]


@pytest.mark.parametrize("family, strength, h", CASES)
def test_small_angle_surface_meshes_validly(family, strength, h):
    pts, tri = surface(family, strength)
    facets = [[[int(v) for v in t]] for t in tri]
    m = meshloom.generate3d(points=pts, facets=facets, h=h, max_points=5000)
    by_tag = {k: facets[int(k)] for k in m["boundary_faces"]}
    A.check(m, pts, by_tag, [volume(pts, facets)], False, euler=True, inner_cover=False)
