# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical density integrals, exact old subspace and representation contracts."""
import math
import numpy as np
import pytest
from scipy.integrate import quad
from galerkin.laplace_corner_harmonic import power_panel_harmonic_gram,power_panel_harmonic_self_log
from galerkin.laplace_corner_quadratic import power_panel_quadratic_gram as gram,power_panel_quadratic_self_log as self_log

POWERS=[.500001,.55,.6,2/3,.8,.95,1-2**-20,1-2**-40,1.]


@pytest.mark.parametrize('p',POWERS)
@pytest.mark.parametrize('h',[2**-20,1.,2**20])
def test_old_subspace_physical_scale_and_immutable_positive_gram(p,h):
    g,k=gram(h,p),self_log(h,p)
    assert g[:2,:2].tobytes()==power_panel_harmonic_gram(h,p).tobytes()
    assert k[:2,:2].tobytes()==power_panel_harmonic_self_log(h,p).tobytes()
    for a in (g,k):
        np.testing.assert_array_equal(a,a.T)
        assert a.shape==(3,3) and not a.flags.writeable
        with pytest.raises(ValueError):a[0,0]=0
        with pytest.raises(ValueError):a.setflags(write=True)
    assert np.linalg.eigvalsh(g).min()>0
    np.testing.assert_array_equal(g*h,gram(1.,p))
    expected=self_log(1.,p).copy();expected[0,0]+=math.log(h)
    np.testing.assert_allclose(k,expected,rtol=0,atol=4e-15)
    if p!=1:assert g[0,2]!=0 and g[1,2]!=0 and k[1,2]!=0


@pytest.mark.parametrize('h',[2**-20,1.,2**20])
def test_uniform_shifted_legendre_exact_mass_and_self_log(h):
    g,k=gram(h,1.),self_log(h,1.)
    np.testing.assert_array_equal(g,np.eye(3)/h)
    expected=np.array([[-1.5+math.log(h),0.,math.sqrt(5)/12],
                       [0.,-.75,0.],[math.sqrt(5)/12,0.,-5/12]])
    np.testing.assert_allclose(k,expected,rtol=0,atol=4e-15)
    assert k[0,1]==k[1,2]==0


@pytest.mark.parametrize('p',[.6,2/3,.8,1.])
def test_direct_physical_density_gram_and_masses(p):
    # Flatten rho_p ds with v=(s/h)^p. The Gram uses a separate
    # endpoint-removing coordinate t=(s/h)^(2p-1), not product rational forms.
    def mode(k,v):return (1.,math.sqrt(3)*(2*v-1),math.sqrt(5)*(6*v*v-6*v+1))[k]
    masses=[quad(lambda v:mode(k,v),0,1,epsabs=1e-13,epsrel=1e-13)[0] for k in range(3)]
    np.testing.assert_allclose(masses,[1,0,0],rtol=0,atol=2e-14)
    exponent=p/(2*p-1)
    expected=np.array([[p*p/(2*p-1)*quad(lambda t:mode(i,t**exponent)*mode(j,t**exponent),0,1,epsabs=1e-12,epsrel=1e-12)[0] for j in range(3)] for i in range(3)])
    np.testing.assert_allclose(gram(1.,p),expected,rtol=1e-12,atol=1e-13)


@pytest.mark.parametrize('function',[gram,self_log])
@pytest.mark.parametrize('length',[0.,-1.,math.inf,math.nan,True,1+1j])
def test_invalid_lengths(function,length):
    with pytest.raises((ValueError,TypeError)):function(length,2/3)


@pytest.mark.parametrize('function',[gram,self_log])
@pytest.mark.parametrize('power',[.5,0.,1.01,math.inf,math.nan,True,1+1j])
def test_invalid_powers(function,power):
    with pytest.raises((ValueError,TypeError)):function(1.,power)


def test_extreme_current_gram_refuses_unrepresentable_scale():
    with pytest.raises(ValueError):gram(np.nextafter(0.,1.),2/3)


def test_module_does_not_expose_a_field_or_interaction():
    import galerkin.laplace_corner_quadratic as module
    assert module.__all__==['power_panel_quadratic_gram','power_panel_quadratic_self_log']
