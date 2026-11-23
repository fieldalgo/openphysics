# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import numpy as np
import pytest
import galerkin.laplace_two_ground as module
from galerkin.laplace_two_ground import solve_two_ground_rectangle as solve


def polygons():
    return [np.array([[.00345,.000975],[.00385,.000975],[.00385,.001025],[.00345,.001025]]),
            np.array([[.00415,.000975],[.00455,.000975],[.00455,.001025],[.00415,.001025]])]


@pytest.fixture(scope="module")
def result():
    return solve(polygons(), width=.008, height=.002, panels_per_edge=16)


@pytest.mark.parametrize("field", ["width", "height"])
@pytest.mark.parametrize("value", [True, "1", 0., -1., np.nan, np.inf, 1j])
def test_dimensions_rejected_before_field_solve(monkeypatch, field, value):
    monkeypatch.setattr(module.kernel, "panels", lambda *a,**k: pytest.fail("field solve reached"))
    args=dict(width=.008,height=.002); args[field]=value
    with pytest.raises(ValueError): solve(polygons(), **args)


@pytest.mark.parametrize("field,value", [
    ("panels_per_edge",True),("panels_per_edge",0),("panels_per_edge",257),
    ("panels_per_edge",1.5),("ground_modes",True),("ground_modes",63),
    ("ground_modes",4097),("ground_modes",64.),("interpolation_degree",True),
    ("interpolation_degree",9),("interpolation_degree",11),("interpolation_degree",18)])
def test_controls_rejected_before_field_solve(monkeypatch, field, value):
    monkeypatch.setattr(module.kernel, "panels", lambda *a,**k: pytest.fail("field solve reached"))
    with pytest.raises(ValueError): solve(polygons(), width=.008,height=.002,**{field:value})


@pytest.mark.parametrize("case", ["empty","bool","nan","duplicate","overlap","touch","concave","outside","side","cap"])
def test_geometry_rejected_before_field_solve(monkeypatch,case):
    p=polygons(); count=16
    if case=="empty":p=[]
    if case=="bool":p=[np.ones((4,2),dtype=bool)]
    if case=="nan":p[0][0,0]=np.nan
    if case=="duplicate":p[0]=np.vstack((p[0],p[0][0]))
    if case=="overlap":p=[p[0],p[0].copy()]
    if case=="touch":p[1][:,0]-=.0003
    if case=="concave":p[0][1]=p[0].mean(axis=0)
    if case=="outside":p[0][:,1]-=.001
    if case=="side":p=[p[0]-[.00345-1e-7,0]]  # closer than the wall-scaled box limit allows
    if case=="cap":p=p+[p[0]+[.0015,0]];count=256
    monkeypatch.setattr(module.kernel, "panels", lambda *a,**k: pytest.fail("field solve reached"))
    with pytest.raises(ValueError):solve(p,width=.008,height=.002,panels_per_edge=count)


def test_immutable_surface_order_and_conservation(result):
    assert result.panel_count==128
    assert result.current_gram.shape==(4,2,2)
    np.testing.assert_allclose(result.current_integrals[:2],np.eye(2),rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.current_integrals[2:],-.5,rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.current_gram[2],result.current_gram[3],rtol=1e-10,atol=0)
    assert result.condition_bound<1e10
    assert max(result.reciprocity_error,result.residual_error,result.current_error,
               result.matrix_refinement_error,result.ground_refinement_error)<=1e-10
    assert result.minimum_scaled_eigenvalue>=-1e-10
    for name in ("capacitance_per_permittivity","current_gram","current_integrals"):
        a=getattr(result,name)
        with pytest.raises(ValueError):a.setflags(write=True)
        with pytest.raises(ValueError):a.flat[0]=0
    with pytest.raises(dataclasses.FrozenInstanceError):result.panel_count=0


@pytest.mark.parametrize("operation", ["scale","mirror-y","permutation","clockwise"])
def test_public_surface_transform(result,operation):
    p=polygons();w=.008;h=.002
    if operation=="scale":p=[x*2 for x in p];w*=2;h*=2
    if operation=="mirror-y":p=[x*[1,-1]+[0,h] for x in p]
    if operation=="permutation":p=p[::-1]
    if operation=="clockwise":p=[x[::-1] for x in p]
    after=solve(p,width=w,height=h,panels_per_edge=16)
    q=after.current_gram;c=after.capacitance_per_permittivity;j=after.current_integrals
    if operation=="scale":q=q*2
    if operation=="mirror-y":q=q[[0,1,3,2]];j=j[[0,1,3,2]]
    if operation=="permutation":q=q[[1,0,2,3],::-1,::-1];j=j[[1,0,2,3],::-1];c=c[::-1,::-1]
    np.testing.assert_allclose(q,result.current_gram,rtol=1e-10,atol=0)
    np.testing.assert_allclose(c,result.capacitance_per_permittivity,rtol=1e-10,atol=0)
    np.testing.assert_allclose(j,result.current_integrals,rtol=0,atol=1e-10)


def test_ground_refinement_failure_does_not_fallback(monkeypatch):
    original=module._factors; calls=[]
    def changed(*args,**kwargs):
        calls.append(kwargs["modes"]); value=original(*args,**kwargs)
        if kwargs["modes"]==256:value["ground_parts"]*=1.001
        return value
    monkeypatch.setattr(module,"_factors",changed)
    with pytest.raises(ValueError,match="ground Fourier"):
        solve(polygons(),width=.008,height=.002,panels_per_edge=16)
    assert calls==[128,256]


def test_ground_gate_preserves_small_entry_relative_scale(monkeypatch):
    original=module._factors
    def changed(*args,**kwargs):
        value=original(*args,**kwargs)
        value["ground_parts"]=np.array([[[1.,1e-12],[1e-12,1.]],[[1.,1e-12],[1e-12,1.]]])
        if kwargs["modes"]==256:
            value["ground_parts"][0,0,1]*=1.001
            value["ground_parts"][0,1,0]*=1.001
        return value
    monkeypatch.setattr(module,"_factors",changed)
    with pytest.raises(ValueError,match="ground Fourier"):
        solve(polygons(),width=.008,height=.002,panels_per_edge=16)
