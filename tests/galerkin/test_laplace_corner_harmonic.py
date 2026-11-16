# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent exact density-product integrals, units and admitted boundaries."""
from fractions import Fraction
import json
import math
import numpy as np
import pytest
from galerkin.laplace_corner_harmonic import (
    power_panel_harmonic_gram, power_panel_harmonic_self_log)
from galerkin.laplace_corner import (
    power_panel_gram, power_panel_self_log, power_panel_linear_gram,
    power_panel_linear_self_log)

FUNCTIONS = (power_panel_harmonic_gram, power_panel_harmonic_self_log)
POWERS = sorted(set([*np.linspace(.5001, 1., 65), np.nextafter(.5, 1.),
                    np.nextafter(1., 0.), 1-2.**-20, 1-2.**-40, 2/3, .55, .8]))


@pytest.mark.parametrize('p', POWERS)
def test_exact_rational_density_products(p, record_property):
    h = .0007
    fp, fh = Fraction(float(p)), Fraction(h)
    powers = (fp, 2*fp)
    raw = [[a*b / (fh*(a+b-1)) for b in powers] for a in powers]
    zero = float(raw[0][0])
    cross = math.sqrt(3)*float(raw[0][1]-raw[0][0])
    diagonal = float(3*(raw[1][1]-2*raw[0][1]+raw[0][0]))
    expected = np.array([[zero, cross], [cross, diagonal]])
    gram = power_panel_harmonic_gram(h, p)
    mask = expected != 0
    assert np.max(abs(gram[mask]-expected[mask])/abs(expected[mask])) <= 1e-12
    assert np.array_equal(gram[~mask], expected[~mask])
    assert np.linalg.eigvalsh(gram/np.max(abs(gram))).min() > 0
    assert np.array_equal(gram, gram.T)
    assert gram[0,0] == power_panel_gram(h, p)
    for scale in (2.**-15, 2.**15):
        np.testing.assert_array_equal(power_panel_harmonic_gram(h*scale, p)*scale, gram)
    record_property('harmonic_gram', json.dumps(dict(p=float(p), gram=gram.tolist()), sort_keys=True))


@pytest.mark.parametrize('p', [.5001, 2/3, .8, np.nextafter(1.,0.), 1.])
@pytest.mark.parametrize('h', [1e-100, .0007, 1., 1e100])
def test_physical_log_scaling_and_nonzero_cross(p,h,record_property):
    value=power_panel_harmonic_self_log(h,p)
    assert value[0,0] == power_panel_self_log(h,p)
    assert np.array_equal(value,value.T)
    assert value[1,1] < 0
    if p==1:assert value[0,1]==0
    else:assert value[0,1]>0
    for scale in (2.**-15,2.**15):
        scaled=power_panel_harmonic_self_log(h*scale,p)
        assert abs((scaled[0,0]-value[0,0])-math.log(scale))<=1e-12
        np.testing.assert_array_equal(scaled.ravel()[1:],value.ravel()[1:])
    record_property('harmonic_self_scaling',json.dumps(dict(p=float(p),h=h,value=value.tolist()),sort_keys=True))


@pytest.mark.parametrize('h', [1e-6,.25,1e6])
def test_uniform_branch_is_existing_linear_mode(h):
    np.testing.assert_array_equal(power_panel_harmonic_gram(h,1),power_panel_linear_gram(h,1))
    np.testing.assert_array_equal(power_panel_harmonic_self_log(h,1),power_panel_linear_self_log(h,1))


@pytest.mark.parametrize('function',FUNCTIONS)
@pytest.mark.parametrize('bad',[0.,-1.,np.inf,np.nan,True,'1',[1.],1+0j])
def test_invalid_length(function,bad):
    with pytest.raises(ValueError):function(bad,.75)


@pytest.mark.parametrize('function',FUNCTIONS)
@pytest.mark.parametrize('bad',[.5,0.,1.01,np.inf,np.nan,True,'0.75',[.75],.75+0j])
def test_invalid_power(function,bad):
    with pytest.raises(ValueError):function(.001,bad)


@pytest.mark.parametrize('function',FUNCTIONS)
def test_immutable_storage(function):
    result=function(.001,.75)
    with pytest.raises(ValueError):result[0,0]=0
    with pytest.raises(ValueError):result.flags.writeable=True
    with pytest.raises(ValueError):result.base.flags.writeable=True


@pytest.mark.parametrize('h,p',[(np.nextafter(0.,1.),.75),(1e308,np.nextafter(1.,0.))])
def test_unrepresentable_current_matrix_is_refused(h,p):
    with pytest.raises(ValueError,match='representable'):power_panel_harmonic_gram(h,p)
