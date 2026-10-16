# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reference algebra tests; no product imports and no execution claim."""
import ast
from pathlib import Path
import numpy as np
import pytest
import refsol.transient_heat as reference


def test_exact_consistent_triangle_mass_and_stiffness():
    p=np.array([[0.,0.],[1.,0.],[0.,1.]])
    m,k=reference.p1_matrices(p,np.array([[0,1,2]]),
        conductivity=1.,volumetric_heat_capacity=4.)
    np.testing.assert_allclose(m,(np.ones((3,3))+np.eye(3))/6,rtol=0,atol=1e-10)
    np.testing.assert_allclose(k,[[1.,-.5,-.5],[-.5,.5,0.],[-.5,0.,.5]],rtol=0,atol=1e-10)
    assert np.linalg.eigvalsh(m).min()>0
    np.testing.assert_allclose(k@np.ones(3),0,atol=1e-10)
    assert m[0,1]>0  # the registered mass is not a row-sum diagonal surrogate


def test_dirichlet_mode_pencil_and_unequal_step_product():
    p=np.array([[x,y] for y in (0.,.5,1.) for x in (0.,.5,1.)])
    tri=[]
    for j in range(2):
        for i in range(2):
            a=j*3+i;tri.extend([[a,a+1,a+4],[a,a+4,a+3]])
    m,k=reference.p1_matrices(p,np.array(tri),conductivity=2.5,volumetric_heat_capacity=4.)
    fixed=np.array([i for i in range(9) if i!=4])
    lam,phi=reference.smallest_dirichlet_mode(m,k,fixed)
    assert lam>0 and phi[4]==1 and not phi[fixed].any()
    assert abs((k@phi)[4]-lam*(m@phi)[4])<=1e-10
    times=np.array([0.,.01,.07,.1])
    product=reference.backward_euler_amplitude(lam,times)
    expected=np.array([1.,1/(1+.01*lam),
        1/((1+.01*lam)*(1+.06*lam)),
        1/((1+.01*lam)*(1+.06*lam)*(1+.03*lam))])
    np.testing.assert_allclose(product,expected,rtol=0,atol=1e-10)


def test_exact_affine_and_finite_negative_uniform_fields():
    p=np.array([[0.,0.],[.3,.7],[1.,1.]])
    a=reference.moving_affine(p,.2)
    np.testing.assert_allclose(a.temperature_k,290+5*p[:,0]+.6,atol=1e-10)
    np.testing.assert_allclose(a.heat_flux_w_m2,np.broadcast_to([-12.5,0.],(3,2)),atol=1e-10)
    np.testing.assert_array_equal(a.heat_source_w_m3,np.full(3,12.))
    b=reference.uniform_insulated(p,2.,volumetric_heat_capacity=4.,
        initial_temperature_k=-10.,heat_source=-8.)
    np.testing.assert_array_equal(b.temperature_k,np.full(3,-14.))


@pytest.mark.parametrize('time',[.25,.5,1.])
def test_sine_pde_source_from_time_and_flux_derivatives(time):
    p=np.array([[.2,.3],[.65,.75]])
    f=reference.sine_manufactured(p,time)
    h=1e-3
    divergence=np.zeros(len(p))
    for axis in (0,1):
        d=np.zeros_like(p);d[:,axis]=h
        fm2=reference.sine_manufactured(p-2*d,time).heat_flux_w_m2[:,axis]
        fm1=reference.sine_manufactured(p-d,time).heat_flux_w_m2[:,axis]
        fp1=reference.sine_manufactured(p+d,time).heat_flux_w_m2[:,axis]
        fp2=reference.sine_manufactured(p+2*d,time).heat_flux_w_m2[:,axis]
        divergence+=(fm2-8*fm1+8*fp1-fp2)/(12*h)
    phi=np.sin(np.pi*p[:,0])*np.sin(np.pi*p[:,1])
    derived=4*.7*phi+divergence
    scale=max(1.,np.max(abs(f.heat_source_w_m3)))
    np.testing.assert_allclose(derived,f.heat_source_w_m3,rtol=0,atol=1e-10*scale)


def test_no_engine_or_other_reference_truth_imports():
    tree=ast.parse(Path(reference.__file__).read_text(encoding="utf-8"))
    roots=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):roots.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node,ast.ImportFrom):roots.add(node.module.split('.')[0])
    assert roots=={'numpy','dataclasses'}


@pytest.mark.parametrize('bad',[True,0.,-1.,np.inf,1j])
def test_bad_capacity_rejected(bad):
    with pytest.raises(ValueError):
        reference.uniform_insulated(np.zeros((1,2)),0.,volumetric_heat_capacity=bad)
