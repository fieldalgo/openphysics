# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import re

import pytest

from gmshio import geo


def _count(pattern, text):
    return len(re.findall(pattern, text))


def test_tiling_resolves_shared_edges_and_t_junction():
    g = geo.Geo()
    g.add_region("a", [(0, 0), (1, 0), (1, 1), (0, 1)])
    g.add_region("b", [(1, 0), (2, 0), (2, 0.5), (1, 0.5)])   # touches a's right edge halfway
    txt = g.render()
    assert _count(r"Point\(\d+\)", txt) == 7                 # (1,0) shared between a and b
    assert _count(r"Line\(\d+\)", txt) == 8                  # a's right edge split into two
    assert _count(r"Plane Surface", txt) == 2
    assert 'Physical Surface("a") = {1};' in txt
    assert 'Physical Surface("b") = {2};' in txt
    # 7 of the 8 lines are on the outer boundary
    m = re.search(r'Physical Curve\("outer"\) = \{([^}]*)\};', txt)
    assert m and len(m.group(1).split(",")) == 7


def test_box_sides_namer():
    namer = geo.box_sides(-1, 1, 0, 2)
    assert namer((-1, 1)) == "left"
    assert namer((1, 0.3)) == "right"
    assert namer((0, 0)) == "bottom"
    assert namer((0.5, 2)) == "top"


def test_geo_numbers_are_plain_floats():
    import numpy as np
    g = geo.Geo()
    g.add_region("a", np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float64))
    txt = g.render()
    assert "np." not in txt


def test_rib_waveguide_regions_and_validation():
    txt = geo.rib_waveguide(slab_thickness=0.0)
    for name in ("core", "box", "clad", "left", "right", "top", "bottom"):
        assert f'"{name}"' in txt
    with pytest.raises(ValueError):
        geo.rib_waveguide(slab_thickness=1.0)


def test_other_builders_validate():
    with pytest.raises(ValueError):
        geo.circular_fiber(2.0, 1.0, 0.1)
    assert "OpenCASCADE" in geo.box_cavity(1, 1, 1, 0.2)
