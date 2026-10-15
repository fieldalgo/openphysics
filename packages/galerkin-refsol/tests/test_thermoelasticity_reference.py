"""Direct three-dimensional-law checks independent of the FEM engine."""
import ast
from pathlib import Path
import numpy as np
import pytest
import refsol.thermoelasticity as oracle


@pytest.mark.parametrize('plane',['stress','strain'])
@pytest.mark.parametrize('nu',[.3,-.2])
def test_uniform_original_3d(plane,nu):
    mat=dict(young_modulus=70e9,poisson_ratio=nu,plane=plane,reference_temperature_k=293.15,thermal_expansion_per_k=12e-6)
    a=12e-6*20;E=70e9
    f=oracle.uniform_free(np.array([[0.,0.],[1.,1.]]),**mat)
    np.testing.assert_allclose(f.stress,0.,atol=1e-7)
    np.testing.assert_allclose(f.sigma_zz,0. if plane=='stress' else -E*a,atol=1e-7)
    np.testing.assert_allclose(f.energy_density,0. if plane=='stress' else .5*E*a*a,atol=1e-10)
    c=oracle.uniform_constrained(np.array([[.2,.3]]),**mat)
    expected=-E*a/(1-nu if plane=='stress' else 1-2*nu)
    np.testing.assert_allclose(c.stress[0],[expected,expected,0.],atol=1e-7)


@pytest.mark.parametrize('plane',['stress','strain'])
def test_mms_negative_stress_divergence(plane):
    mat=dict(young_modulus=70e9,poisson_ratio=.3,plane=plane,reference_temperature_k=293.15,thermal_expansion_per_k=12e-6)
    p=np.array([[.21,.34],[.58,.72],[.83,.19]]);h=1e-5
    derivatives=[]
    for axis in (0,1):
        offset=np.eye(2)[axis]*h
        derivatives.append((oracle.sine_manufactured(p+offset,**mat).stress-oracle.sine_manufactured(p-offset,**mat).stress)/(2*h))
    body=-np.column_stack([derivatives[0][:,0]+derivatives[1][:,2],derivatives[0][:,2]+derivatives[1][:,1]])
    np.testing.assert_allclose(body,oracle.sine_manufactured(p,**mat).body_force,rtol=2e-8)


def test_no_engine_imports():
    tree=ast.parse(Path(oracle.__file__).read_text())
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
    assert set(imports)<= {'numpy','dataclasses'}
