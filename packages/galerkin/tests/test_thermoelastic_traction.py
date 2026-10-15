# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Producer total-traction API checks, independent analytic reference."""
from dataclasses import fields
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import ThermoelasticResult, freeze_temperature, solve_thermoelasticity
from refsol.thermoelastic_traction import uniform_combined, traction_from_stress


def material(plane):
    return dict(young_modulus=70e9,poisson_ratio=.3,plane=plane,
                thermal_expansion_per_k=12e-6,reference_temperature_k=293.15)


def solve_patch(plane, overlap=False, **kwargs):
    m=rectangle_mesh(1.,1.,3,3);mat=material(plane)|kwargs
    exact=uniform_combined(m.nodes,**mat)
    bc={(int(i),j):exact.displacement[i,j] for i in m.boundary['left'] for j in (0,1)}
    def load(p,n):return traction_from_stress(uniform_combined(p,**mat).stress,n)
    tags=['right','top','bottom']+(['left'] if overlap else [])
    r=solve_thermoelasticity(m,freeze_temperature(m,exact.temperature_k),dirichlet=bc,
                           traction={tag:load for tag in tags},**mat)
    return m,r,exact


@pytest.mark.parametrize('plane',['stress','strain'])
def test_uniform_total_traction_and_overlap(plane):
    m,r,exact=solve_patch(plane);_,over,_=solve_patch(plane,True)
    np.testing.assert_allclose(r.displacement,exact.displacement,atol=1e-14,rtol=0)
    np.testing.assert_allclose(r.stress,exact.stress[0][[0,1,0],[0,1,1]][None,:].repeat(len(m.triangles),0),atol=70e9*max(1e-4,12e-6*20)*1e-10,rtol=0)
    np.testing.assert_allclose(r.sigma_zz,exact.stress[0,2,2],atol=70e9*max(1e-4,12e-6*20)*1e-10,rtol=0)
    assert r.physical_elastic_energy==pytest.approx(exact.energy_density[0],rel=1e-10)
    np.testing.assert_array_equal(r.load_external,r.load_body+r.load_traction)
    np.testing.assert_array_equal(r.load_total,r.load_external+r.load_thermal)
    np.testing.assert_allclose(over.displacement,r.displacement,atol=1e-14,rtol=0)
    np.testing.assert_allclose(over.reaction-r.reaction,-(over.load_traction-r.load_traction),atol=70e9*max(1e-4,12e-6*20)*1e-10,rtol=0)
    np.testing.assert_allclose((r.load_external+r.reaction).sum(0),0,atol=70e9*max(1e-4,12e-6*20)*1e-10)
    assert abs(np.sum(r.displacement*r.reaction))>1


def test_legacy_eighteen_positional_and_none_empty():
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,313.15))
    kw=dict(dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},**material('strain'))
    a=solve_thermoelasticity(m,s,**kw);b=solve_thermoelasticity(m,s,traction={},**kw)
    for f in fields(a):
        if isinstance(getattr(a,f.name),np.ndarray):np.testing.assert_array_equal(getattr(a,f.name),getattr(b,f.name))
    old=ThermoelasticResult(*[getattr(a,f.name) for f in fields(a)[:18]])
    assert old.load_body is None and old.load_traction is None
    np.testing.assert_array_equal(a.load_body,a.load_external)
    assert not a.load_traction.any()


@pytest.mark.parametrize('bad',[True,1.,(1.,2.),{'missing':(1.,0.)},{'right':(True,False)},
    {'right':(np.nan,0.)},{'right':(1j,0.)},{'right':lambda p,n:np.zeros(2)}])
def test_invalid_traction(bad):
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,313.15))
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},traction=bad,**material('stress'))


def test_complete_selection_before_callback_and_current_tags():
    m=rectangle_mesh(1.,1.,2,2);s=freeze_temperature(m,np.full(m.num_nodes,313.15));calls=[]
    def load(p,n):calls.append(1);return np.zeros_like(p)
    kw=dict(dirichlet={(0,0):0.,(0,1):0.,(2,1):0.},**material('stress'))
    with pytest.raises(ValueError):solve_thermoelasticity(m,s,traction={'right':load,'missing':load},**kw)
    assert not calls
    m.boundary_edges['duplicate']=m.boundary_edges['right'][::-1,::-1]
    with pytest.raises(ValueError,match='duplicate'):solve_thermoelasticity(m,s,traction={'right':load,'duplicate':load},**kw)
    assert not calls
    m.boundary_edges['bad']=np.array([[0,4]])
    with pytest.raises(ValueError,match='exterior'):solve_thermoelasticity(m,s,traction={'bad':load},**kw)
