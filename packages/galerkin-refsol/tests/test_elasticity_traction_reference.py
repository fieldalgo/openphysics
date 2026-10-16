# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Verify traction oracles directly, without invoking an elasticity solver."""
import ast
from pathlib import Path
import numpy as np
import pytest
from numpy.testing import assert_allclose
from refsol import elasticity_traction as ref


def test_traction_reference_does_not_import_fem_or_solver():
    tree=ast.parse(Path(ref.__file__).read_text())
    imports=[n.module or "" for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
    assert not any(x.startswith(("galerkin","simcase")) for x in imports)


@pytest.mark.parametrize("plane", ["stress","strain"])
def test_traction_polynomial_kinematics_and_negative_stress_divergence(plane):
    p=np.array([[.17,.31],[.41,.72],[.63,.24]])
    args=dict(young_modulus=70000,poisson_ratio=.3,plane=plane)
    h=1e-5
    xp,xm=ref.polynomial_manufactured(p+[h,0],**args),ref.polynomial_manufactured(p-[h,0],**args)
    yp,ym=ref.polynomial_manufactured(p+[0,h],**args),ref.polynomial_manufactured(p-[0,h],**args)
    dx,dy=(xp.displacement-xm.displacement)/(2*h),(yp.displacement-ym.displacement)/(2*h)
    f=ref.polynomial_manufactured(p,**args)
    assert_allclose(f.strain,np.column_stack([dx[:,0],dy[:,1],dy[:,0]+dx[:,1]]),rtol=1e-8,atol=1e-12)
    sx,sy=(xp.stress-xm.stress)/(2*h),(yp.stress-ym.stress)/(2*h)
    assert_allclose(f.body_force,-np.column_stack([sx[:,0]+sy[:,2],sx[:,2]+sy[:,1]]),rtol=1e-8,atol=1e-8)


def test_traction_known_tensor_normal_and_plane_answers():
    assert_allclose(ref.traction_from_stress([[11,-5,3],[11,-5,3]],[[1,0],[0,-1]]),[[11,3],[-3,5]])
    args=dict(young_modulus=200,poisson_ratio=.25)
    s=ref.uniaxial([[1,1]],2,plane="stress",**args)
    e=ref.uniaxial([[1,1]],2,plane="strain",**args)
    assert_allclose(s.displacement,[[.01,-.0025]])
    assert_allclose(e.displacement,[[.009375,-.003125]])
    assert_allclose(ref.shear([[0,1]],2,plane="strain",**args).displacement,[[.025,0]])


@pytest.mark.parametrize("normal", [[[0,0]],[[2,0]],[[np.nan,0]],[[1,0,0]]])
def test_traction_reference_rejects_bad_normals(normal):
    with pytest.raises(ValueError): ref.traction_from_stress([[1,2,3]],normal)
