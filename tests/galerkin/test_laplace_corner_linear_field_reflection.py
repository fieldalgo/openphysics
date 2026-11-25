# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Horizontal reflection of the explicit linear field, split from test_laplace_corner_linear_field.py.

Each case needs its own reflected solve; together with the rest of that module they exceed
the share of one CI test part (tools/tests/test_openphysics_shard.py), so they run as their own file.
"""
import pytest

from test_laplace_corner_linear_field import GEOMETRIES, calculated, quantities, relative


@pytest.mark.parametrize('index',range(2))
def test_horizontal_reflection_preserves_each_current_entry_without_floor(index):
    original,reflected=calculated(index),calculated(index,reflect=True)
    n=len(GEOMETRIES[index]['polygons']);cap,faces,whole=quantities(reflected)
    faces=faces.reshape(n,4,n,n)[:,[2,1,0,3]].reshape(4*n,n,n)
    assert max(relative(a,b) for a,b in zip(quantities(original),(cap,faces,whole)))<=1e-10
