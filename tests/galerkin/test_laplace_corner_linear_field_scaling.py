# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical scaling of the explicit linear field, split from test_laplace_corner_linear_field.py.

Each scale needs its own solve; together with the rest of that module they exceed an eighth of
the CI suite (tools/tests/test_openphysics_shard.py), so they run as their own file.
"""
import numpy as np
import pytest

from test_laplace_corner_linear_field import GEOMETRIES, calculated, relative, solve


@pytest.mark.parametrize('index',range(2))
@pytest.mark.parametrize('scale',[2.**-15,2.**15])
def test_physical_scaling_keeps_capacitance_and_inverse_length_current_units(index,scale):
    row=GEOMETRIES[index];expected=calculated(index,32)
    result=solve([np.asarray(p)*scale for p in row['polygons']],
                 width=row['width']*scale,height=row['height']*scale,panels_per_edge=32)
    assert relative(result.whole.capacitance_per_permittivity,expected.whole.capacitance_per_permittivity)<=1e-10
    assert relative(scale*result.whole.current_gram,expected.whole.current_gram)<=1e-10
    assert relative(scale*result.edge_current_gram,expected.edge_current_gram)<=1e-10
    np.testing.assert_allclose(result.whole.current_integrals,expected.whole.current_integrals,rtol=0,atol=1e-10)
