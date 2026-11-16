# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent integrals for two hierarchical panel modes and their units."""
import json
import math
from pathlib import Path
import numpy as np
import pytest
from galerkin.laplace_corner import (power_panel_linear_gram,power_panel_linear_self_log,
    power_panel_gram,power_panel_self_log,power_panel_quadrature)

DATA=json.loads((Path(__file__).parent/'two_ground/evidence/linear-corner-integrals.json').read_text())
FUNCTIONS=(power_panel_linear_gram,power_panel_linear_self_log)

@pytest.mark.parametrize('row',DATA['cases'],ids=lambda r:str(r['exponent']))
@pytest.mark.parametrize('scale',[1e-100,.5,1.,1e100])
def test_independent_direct_integrals_and_mass_scaling(row,scale,record_property):
    p,h=row['exponent'],row['length'];ref=row['reference_values'][-1]
    def matrix(values):
        a,b,c=map(float,values);return np.array([[a,b],[b,c]])
    gram=power_panel_linear_gram(h*scale,p);logs=power_panel_linear_self_log(h*scale,p)
    expected_gram=matrix(ref['gram'])/scale;expected_logs=matrix(ref['self_log']);expected_logs[0,0]+=math.log(scale)
    mask=np.ones((2,2),dtype=bool)
    if p==1.:
        # Orthogonal uniform modes have exactly zero cross terms analytically.
        assert gram[0,1]==0 and logs[0,1]==0
        assert abs(expected_gram[0,1]*(h*scale))<1e-30 and abs(expected_logs[0,1])<1e-30
        mask[0,1]=mask[1,0]=False
    assert np.max(abs((gram-expected_gram)[mask])/abs(expected_gram[mask]))<=1e-12
    assert np.max(abs((logs-expected_logs)[mask])/abs(expected_logs[mask]))<=1e-12
    assert np.array_equal(gram,gram.T) and np.array_equal(logs,logs.T)
    assert np.linalg.eigvalsh(gram/np.max(abs(gram))).min()>0
    assert logs[1,1]<0
    assert gram[0,0]==power_panel_gram(h*scale,p)
    assert logs[0,0]==power_panel_self_log(h*scale,p)
    record_property('linear_corner_reference',json.dumps(dict(p=p,scale=scale,gram=gram.tolist(),self_log=logs.tolist()),sort_keys=True))

@pytest.mark.parametrize('h',[1e-6,.25,1e6])
def test_uniform_legendre_basis_and_exact_subdivision(h):
    gram=power_panel_linear_gram(h,1.);logs=power_panel_linear_self_log(h,1.)
    assert np.array_equal(gram,np.eye(2)/h)
    np.testing.assert_allclose(logs,[[math.log(h)-1.5,0],[0,-.75]],rtol=1e-12,atol=0)
    local=power_panel_linear_gram(h/2,1.);left=np.array([[.5,-math.sqrt(3)/4],[0,.25]]);right=left.copy();right[0,1]*=-1
    np.testing.assert_allclose(left.T@local@left+right.T@local@right,gram,rtol=1e-12,atol=0)

@pytest.mark.parametrize('p',[.5001,.6,2/3,.875,1.])
def test_mode_mass_and_affine_moment_against_quadrature(p):
    u,w=power_panel_quadrature(p,128);linear=((p+1)*u-p)*math.sqrt((p+2)/p)
    assert abs(w.sum()-1)<=1e-12
    assert abs(w@linear)<=1e-12
    assert abs(w@(linear*linear)-1)<=1e-12
    assert abs(w@(u*linear)-math.sqrt(p)/((p+1)*math.sqrt(p+2)))<=1e-12

@pytest.mark.parametrize('function',FUNCTIONS)
@pytest.mark.parametrize('bad',[0.,-1.,np.inf,np.nan,True,'1',[1.],1+0j])
def test_invalid_length(function,bad):
    with pytest.raises(ValueError):function(bad,.75)

@pytest.mark.parametrize('function',FUNCTIONS)
@pytest.mark.parametrize('bad',[.5,0.,1.01,np.inf,np.nan,True,'0.75',[.75],.75+0j])
def test_invalid_power(function,bad):
    with pytest.raises(ValueError):function(.001,bad)

@pytest.mark.parametrize('function',FUNCTIONS)
def test_matrix_immutable(function):
    value=function(.001,.75)
    with pytest.raises(ValueError):value[0,0]=0
    with pytest.raises(ValueError):value.flags.writeable=True


def test_no_snapping_of_near_uniform_basis():
    p=np.nextafter(1.,0.)
    assert power_panel_linear_gram(1.,p)[0,1]<0
    assert power_panel_linear_self_log(1.,p)[0,1]>0

@pytest.mark.parametrize('h,p',[(np.nextafter(0.,1.),.75),(1e308,np.nextafter(1.,0.))])
def test_unrepresentable_current_matrix_is_refused(h,p):
    with pytest.raises(ValueError,match='representable'):power_panel_linear_gram(h,p)
