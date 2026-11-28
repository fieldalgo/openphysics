# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical scaling, conductor permutation and face partition of the explicit linear field
at 32 panels, split from test_laplace_corner_linear_field.py.

These tests share the cached 32-panel solves calculated(0,32) and calculated(1,32) and no
other cached solve, so they run together and each of those solves runs once per CI test part;
each scale and the permutation add their own solve.
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


def test_active_conductor_basis_permutation():
    row=GEOMETRIES[1];a=calculated(1,32)
    b=solve(row['polygons'][::-1],width=row['width'],height=row['height'],panels_per_edge=32)
    assert relative(b.whole.capacitance_per_permittivity[::-1,::-1],a.whole.capacitance_per_permittivity)<=1e-10
    assert relative(b.whole.current_gram[[1,0,2,3],::-1,::-1],a.whole.current_gram)<=1e-10
    assert relative(b.edge_current_gram[[4,5,6,7,0,1,2,3],::-1,::-1],a.edge_current_gram)<=1e-10


@pytest.mark.parametrize('index',range(2))
def test_exact_face_partition_signed_current_and_positive_gram(index):
    result=calculated(index,32);n=len(GEOMETRIES[index]['polygons'])
    assert result.whole.panel_count==4*n*(32-6)
    assert result.whole.condition_bound<1e10
    for name in ('reciprocity_error','residual_error','current_error','matrix_refinement_error','ground_refinement_error'):
        assert getattr(result.whole,name)<=1e-10
    assert result.partition_error<=1e-10
    for owner in range(n):
        selected=result.edge_owners==owner
        assert relative(result.edge_current_gram[selected].sum(axis=0),result.whole.current_gram[owner])<=1e-10
        np.testing.assert_allclose(result.edge_current_integrals[selected].sum(axis=0),np.eye(n)[owner],rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.whole.current_integrals.sum(axis=0),0,rtol=0,atol=1e-10)
    for part in np.concatenate((result.whole.current_gram,result.edge_current_gram)):
        assert relative(part,part.T)<=1e-10
        assert np.linalg.eigvalsh(part).min()/np.max(abs(part))>=-1e-10
