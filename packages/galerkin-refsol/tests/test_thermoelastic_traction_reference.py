# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import ast
from pathlib import Path
import numpy as np
import pytest
import refsol.thermoelastic_traction as reference


def mat(plane):
    return dict(young_modulus=70e9,poisson_ratio=.3,plane=plane,
                thermal_expansion_per_k=12e-6,reference_temperature_k=293.15)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('linear',[False,True])
def test_polynomial_direct_derivatives(plane,linear):
    p=np.array([[.2,.3],[.7,.8],[0.,.4],[1.,1.]])
    def field(p):return reference.polynomial_manufactured(p,linear_temperature=linear,**mat(plane))
    f=field(p);div=np.zeros_like(p)
    for j in (0,1):
        dp=np.zeros_like(p);dp[:,j]=1e-5
        plus,minus=field(p+dp),field(p-dp)
        np.testing.assert_allclose((plus.displacement-minus.displacement)/2e-5,f.gradient[:,:,j],rtol=0,atol=2e-14)
        div+=(plus.stress[:,:2,j]-minus.stress[:,:2,j])/2e-5
    np.testing.assert_allclose(div,-f.body_force,rtol=1e-9,atol=.002)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('theta,alpha',[ (20.,12e-6),(-20.,12e-6),(20.,-12e-6),(20.,0.)])
def test_uniform_original_law(plane,theta,alpha):
    m=mat(plane)|{'thermal_expansion_per_k':alpha}
    f=reference.uniform_combined(np.array([[0.,0.],[.2,.3]]),theta_k=theta,**m)
    s=np.array([[8e6,3e6],[3e6,-2e6]])
    np.testing.assert_allclose(f.stress[:,:2,:2],np.broadcast_to(s,(2,2,2)),atol=.001,rtol=0)
    zz=0 if plane=='stress' else .3*6e6-70e9*alpha*theta
    np.testing.assert_allclose(f.stress[:,2,2],zz,atol=.001,rtol=0)
    eta=alpha*theta*(1 if plane=='stress' else 1.3)
    em=f.total_strain[0,:2,:2]-eta*np.eye(2)
    expected=.5*np.sum(s*em)+(0 if plane=='stress' else .5*70e9*(alpha*theta)**2)
    np.testing.assert_allclose(f.energy_density,expected,atol=1e-7,rtol=0)


def test_reference_no_engine_or_other_reference_imports():
    tree=ast.parse(Path(reference.__file__).read_text())
    roots=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):roots.update(a.name.split('.')[0] for a in n.names)
        elif isinstance(n,ast.ImportFrom):roots.add(n.module.split('.')[0])
    assert roots=={'numpy','dataclasses'}


def test_traction_contract():
    s=np.array([[[8.,3.,0.],[3.,-2.,0.],[0.,0.,5.]]])
    np.testing.assert_array_equal(reference.traction_from_stress(s,np.array([[0.,-1.]])),[[-3.,2.]])
    for n in ([[0.,2.]],[[True,False]],[[float('nan'),0.]]):
        with pytest.raises(ValueError):reference.traction_from_stress(s,n)


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('linear',[False,True])
def test_original_zero_support_work_and_translated_negative_control(plane,linear):
    z,w=np.polynomial.legendre.leggauss(8);y=(z+1)/2;w=w/2
    p=np.column_stack([np.zeros_like(y),y]);f=reference.polynomial_manufactured(p,linear_temperature=linear,**mat(plane))
    traction=-f.stress[:,:2,0]
    original=np.sum(w*np.sum((f.displacement-[2e-5,-1e-5])*traction,axis=1))
    translated=np.sum(w*np.sum(f.displacement*traction,axis=1))
    scale=70e9*max(1e-4,12e-6*20)**2
    assert abs(original)<=scale*1e-10
    assert abs(translated)>scale*1e-8
