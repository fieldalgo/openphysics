# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent Fourier circle charges, analytical self terms and ground multipoles."""
from functools import lru_cache
import json
import numpy as np
from harmonic_circle_reference import solve as reference
from galerkin.laplace_corner_harmonic_field import solve_two_ground_harmonic_corner_three_active_edges as solve

CENTERS=np.array([[-1.,.5],[0.,.7],[1.,.6]])
RADII=np.array([.1,.08,.12])


def relative(a,b):
    a,b=np.asarray(a),np.asarray(b);d=abs(a-b);s=abs(b)
    assert np.isfinite(d).all()
    return float(np.max(np.divide(d,s,out=np.where(d==0,0.,np.inf),where=s!=0)))


@lru_cache(maxsize=1)
def full_reference():return reference(CENTERS,RADII,order=16,quadrature=256)


def test_single_circle_reference_matches_closed_capacitance_and_surface_currents():
    row=reference([[0.,.5]],[.1],order=16);b=np.sqrt(.5**2-.1**2)
    expected=np.array([2*np.pi/np.arccosh(5),.5/(2*np.pi*.1*b),1/(2*np.pi*b)])
    actual=np.array([row['capacitance'][0,0],row['whole'][0,0,0],row['ground'][0,0]])
    assert relative(actual,expected)<=1e-12
    assert row['numerical']['pointwise']<=1e-10


def test_three_circle_reference_has_independent_order_rule_and_boundary_convergence(record_property):
    fine=full_reference();errors=[]
    for order,rule in [(12,256),(16,128)]:
        other=reference(CENTERS,RADII,order=order,quadrature=rule)
        errors.append({key:relative(other[key],fine[key]) for key in ['capacitance','whole','ground']})
        assert max(errors[-1].values())<=1e-12
        assert other['numerical']['pointwise']<=1e-10
    assert fine['numerical']['pointwise']<=1e-10
    record_property('independent_three_circle_reference',json.dumps(errors,sort_keys=True))


def test_finite_polygon_fields_against_three_circle_fourier_reference(record_property):
    # Separate registered polygon/panel/outer studies bound each approximation.
    # This final finite-box comparison is not an exact circular-domain solve.
    vertices,width,height=21,256.,128.;angle=(np.arange(vertices)+.5)*2*np.pi/vertices
    polygons=[np.column_stack((c[0]+width/2+r/np.cos(np.pi/vertices)*np.cos(angle),
                               c[1]+r/np.cos(np.pi/vertices)*np.sin(angle))) for c,r in zip(CENTERS,RADII)]
    result=solve(polygons,width=width,height=height,panels_per_edge=14,ground_modes=4096)
    actual=dict(capacitance=result.whole.capacitance_per_permittivity,
                whole=result.whole.current_gram[:3],ground=result.whole.current_gram[3:].sum(axis=0))
    expected=full_reference();errors={key:relative(value,expected[key]) for key,value in actual.items()}
    assert result.whole.panel_count==504
    assert max(errors.values())<=.01
    assert max(getattr(result.whole,name) for name in ['reciprocity_error','residual_error',
        'current_error','matrix_refinement_error','ground_refinement_error'])<=1e-10
    record_property('harmonic_three_circle_comparison',json.dumps(dict(errors=errors,
        values={key:value.tolist() for key,value in actual.items()}),sort_keys=True))
