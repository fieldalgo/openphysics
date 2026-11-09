# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit interpolation refinement at fixed conductor and outer geometry."""
import numpy as np
import pytest
import galerkin.laplace_boundary as module
from galerkin.laplace_boundary import solve_grounded_rectangle


def geometry():
    theta = np.arange(64)*2*np.pi/64
    return [np.column_stack((2+x+r*np.cos(theta), .5+r*np.sin(theta)))
            for x,r in [(-.4,.08),(0.,.1),(.4,.1)]]


@pytest.mark.parametrize('value',[True,10.,8,11,13,17,18])
def test_invalid_interpolation_degree_rejects_before_assembly(monkeypatch,value):
    def forbidden(*args,**kwargs):
        raise AssertionError('invalid degree reached matrix assembly')
    monkeypatch.setattr(module.kernel,'matrix',forbidden)
    with pytest.raises(ValueError,match='interpolation_degree'):
        solve_grounded_rectangle(geometry(),width=4.,height=2.,panels_per_edge=2,
                                  interpolation_degree=value)


def test_fixed_geometry_refinement_preserves_default_refusal():
    with pytest.raises(ValueError,match='quadrature/interpolation'):
        solve_grounded_rectangle(geometry(),width=4.,height=2.,panels_per_edge=2)
    rows=[solve_grounded_rectangle(geometry(),width=4.,height=2.,panels_per_edge=2,
                                    interpolation_degree=n) for n in [12,14,16]]
    for row in rows:
        assert row.matrix_refinement_error<=1e-10 and row.reciprocity_error<=1e-10
        assert row.current_error<=1e-10 and row.ground_refinement_error<=1e-10
        np.linalg.cholesky(row.capacitance_per_permittivity)
        for part in row.current_gram:
            assert np.linalg.eigvalsh(part).min()>=-1e-12*abs(part).max()
    for a,b in zip(rows,rows[1:]):
        for first,second in [(a.capacitance_per_permittivity,b.capacitance_per_permittivity),
                             *zip(a.current_gram,b.current_gram)]:
            assert abs(first-second).max()/abs(second).max()<=1e-10


def test_explicit_default_matches_implicit_default_exactly():
    polygon=np.array([[1.05,.2],[1.15,.2],[1.14,.24],[1.06,.24]])
    a=solve_grounded_rectangle([polygon],width=2.4,height=1.,panels_per_edge=16)
    b=solve_grounded_rectangle([polygon],width=2.4,height=1.,panels_per_edge=16,interpolation_degree=10)
    for name in ['capacitance_per_permittivity','current_gram','current_integrals']:
        np.testing.assert_array_equal(getattr(a,name),getattr(b,name))
    assert a.matrix_refinement_error==b.matrix_refinement_error
