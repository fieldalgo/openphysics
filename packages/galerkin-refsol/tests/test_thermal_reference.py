# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct differential checks of analytic heat fields, without engine imports."""
import ast
from pathlib import Path
import numpy as np
import pytest
from refsol.thermal import slab,sine_manufactured


def test_slab_closed_form_and_cooling_sign():
    r=slab([[0.,0.],[1.,.3],[2.,.7]],length=2.,conductivity=12.,left_temperature=350.,right_temperature=300.)
    np.testing.assert_allclose(r.temperature,[350.,325.,300.])
    np.testing.assert_allclose(r.heat_flux,[[300.,0.]]*3)
    np.testing.assert_array_equal(r.heat_source,0.)


def test_sine_heat_source_is_flux_divergence_and_flux_is_negative_gradient():
    p=np.array([[.21,.37],[.52,.43],[.79,.64]])
    h=1e-5;params=dict(lengths=(1.,.8),conductivity=3.,amplitude=2.)
    r=sine_manufactured(p,**params);div=np.zeros(len(p))
    for j in range(2):
        d=np.zeros(2);d[j]=h
        plus,minus=sine_manufactured(p+d,**params),sine_manufactured(p-d,**params)
        np.testing.assert_allclose(-3*(plus.temperature-minus.temperature)/(2*h),r.heat_flux[:,j],rtol=1e-7)
        div+=(plus.heat_flux[:,j]-minus.heat_flux[:,j])/(2*h)
    np.testing.assert_allclose(div,r.heat_source,rtol=1e-7)


@pytest.mark.parametrize('p',[[1.,2.],[[np.nan,0.]],[[1j,0.]],[[True,False]]])
def test_reference_rejects_points(p):
    with pytest.raises(ValueError):sine_manufactured(p)


@pytest.mark.parametrize('parameters',[dict(conductivity=0.),dict(conductivity=1j),dict(lengths=(0.,1.)),
                                     dict(lengths=(1.,)),dict(amplitude=np.nan),dict(reference_temperature=np.inf)])
def test_reference_rejects_parameters(parameters):
    with pytest.raises(ValueError):sine_manufactured([[.1,.2]],**parameters)


def test_reference_has_no_engine_solver_or_assembly_imports():
    import refsol.thermal
    tree=ast.parse(Path(refsol.thermal.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or '']
            assert all(name.split('.')[0] in ('numpy','dataclasses') for name in names)
