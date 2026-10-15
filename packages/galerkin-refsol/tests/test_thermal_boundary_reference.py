# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct differentiation and boundary equations, without importing an engine."""
import ast
from pathlib import Path
import numpy as np
import pytest
from refsol.thermal_boundary import (dirichlet_robin_slab,robin_only_slab,
                                    sine_temperature,sine_source,sine_flux)


@pytest.mark.parametrize('h0,h1',[(8.,12.),(0.,12.),(8.,0.)])
def test_constant_Q_equations_and_flux_balance(h0,h1):
    L,k,Q=1.3,2.5,5.;g0,g1=.7,-.2;ta0,ta1=300.,310.
    ref=robin_only_slab(length=L,conductivity=k,heat_source=Q,left_h=h0,right_h=h1,
        left_ambient=ta0,right_ambient=ta1,left_outward=g0,right_outward=g1)
    points=np.array([[0.,0.],[L,0.]])
    t=ref.temperature(points);F0,F1=ref.outward_fluxes
    np.testing.assert_allclose([F0,F1],[g0+h0*(t[0]-ta0),g1+h1*(t[1]-ta1)],rtol=1e-12,atol=1e-12)
    assert abs(F0+F1-Q*L)<1e-12
    x=.4;eps=1e-3
    temps=ref.temperature(np.array([[x-eps,0.],[x,0.],[x+eps,0.]]))
    assert abs(-k*(temps[0]-2*temps[1]+temps[2])/eps**2-Q)<1e-6


@pytest.mark.parametrize('h',[0.,10.])
def test_dirichlet_flux_or_robin_equations(h):
    ref=dirichlet_robin_slab(length=1.,conductivity=2.5,left_temperature=320.,heat_source=5.,outward_flux=.7,h=h,ambient=300.)
    t=ref.temperature(np.array([[0.,0.],[1.,0.]]))
    assert t[0]==320.
    np.testing.assert_allclose(ref.outward_fluxes[1],.7+h*(t[1]-300.),atol=1e-12)


def test_mms_differentiation_and_source_sign():
    p=np.array([[.23,.37],[.51,.69]]);eps=1e-4;k=2.5
    gradient=[];laplace=np.zeros(2)
    for axis in range(2):
        d=np.zeros(2);d[axis]=eps
        gradient.append((sine_temperature(p+d)-sine_temperature(p-d))/(2*eps))
        laplace+=(sine_temperature(p+d)-2*sine_temperature(p)+sine_temperature(p-d))/eps**2
    np.testing.assert_allclose(sine_flux(p),-k*np.array(gradient).T,rtol=1e-6)
    np.testing.assert_allclose(sine_source(p),-k*laplace,rtol=1e-6)
    assert np.all(sine_source(p)>0)


@pytest.mark.parametrize('kwargs',[{'left_h':0.,'right_h':0.},{'left_h':-1.,'right_h':1.},
                                  {'left_h':True,'right_h':1.},{'left_h':np.nan,'right_h':1.}])
def test_reference_rejects_invalid_or_unanchored(kwargs):
    with pytest.raises(ValueError):robin_only_slab(length=1.,conductivity=1.,**kwargs)


def test_reference_has_no_solver_or_assembly_imports():
    import refsol.thermal_boundary as module
    tree=ast.parse(Path(module.__file__).read_text())
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
    assert all(not any(word in name for word in ('galerkin','scipy','solver','assembly')) for name in imports)
