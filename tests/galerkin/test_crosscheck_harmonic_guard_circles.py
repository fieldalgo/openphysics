# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent fixed-voltage Fourier-circle fields and induced guard current."""
from functools import lru_cache
import json
import numpy as np
from harmonic_circle_reference import solve as reference,ground_gram
from galerkin.laplace_corner_harmonic_guard_field import solve_two_ground_harmonic_corner_guard_edges as solve

CENTERS=np.array([[-1.,.5],[0.,.7],[1.,.6]])
RADII=np.array([.1,.08,.12])


def relative(a,b):
    a,b=np.asarray(a),np.asarray(b);delta=abs(a-b);scale=abs(b)
    assert np.isfinite(delta).all()
    return float(np.max(np.divide(delta,scale,out=np.where(delta==0,0.,np.inf),where=scale!=0)))


@lru_cache(maxsize=3)
def guard_reference(order=16,quadrature=256):
    full=reference(CENTERS,RADII,order=order,quadrature=quadrature)
    cap=full['capacitance'];active=np.array([0,2]);css=cap[np.ix_(active,active)]
    transform=np.linalg.solve(css,cap[:,active].T).T
    coefficients=full['current_coefficients']@transform
    whole=np.array([a.T@a/(2*np.pi*r) for a,r in zip(coefficients,RADII)])
    ground=ground_gram(CENTERS,RADII,coefficients)
    assert relative(whole,np.einsum('ai,pab,bj->pij',transform,full['whole'],transform))<=1e-12
    assert relative(ground,transform.T@full['ground']@transform)<=1e-12
    assert np.max(abs(np.linalg.solve(cap,transform)[1]))<=1e-12
    assert np.max(abs(coefficients[active,0]-np.eye(2)))<=1e-12
    assert np.max(abs(coefficients[1,0]))>1e-6
    assert full['numerical']['pointwise']<=1e-10
    return dict(capacitance=css,whole=whole,ground=ground,current_coefficients=coefficients)


def test_fixed_guard_fourier_reference_converges_in_order_and_rule(record_property):
    fine=guard_reference();errors=[]
    for order,rule in [(12,256),(16,128)]:
        other=guard_reference(order,rule)
        errors.append({key:relative(other[key],fine[key]) for key in ['capacitance','whole','ground']})
        assert max(errors[-1].values())<=1e-12
    record_property('independent_guard_circle_reference',json.dumps(errors,sort_keys=True))


def test_fixed_guard_ground_multipoles_match_multiprecision():
    import mpmath as mp
    with mp.workdps(mp.mp.dps):
        row=guard_reference();a=ground_gram(CENTERS,RADII,row['current_coefficients'],precision=60)
        b=ground_gram(CENTERS,RADII,row['current_coefficients'],precision=80)
        assert max(abs(a[i][j]/b[i][j]-1) for i in range(2) for j in range(2))<=mp.mpf('1e-40')
        assert relative(row['ground'],np.asarray(b,dtype=float))<=1e-12



def test_finite_polygon_fixed_guard_against_independent_fourier_circles(record_property):
    vertices,width,height=21,256.,128.;angle=(np.arange(vertices)+.5)*2*np.pi/vertices
    polygons=[np.column_stack((c[0]+width/2+r/np.cos(np.pi/vertices)*np.cos(angle),c[1]+r/np.cos(np.pi/vertices)*np.sin(angle))) for c,r in zip(CENTERS,RADII)]
    result=solve(polygons,signals=(0,2),width=width,height=height,panels_per_edge=14,ground_modes=4096)
    actual=dict(capacitance=result.whole.capacitance_per_permittivity,whole=result.whole.current_gram[:3],ground=result.whole.current_gram[3:].sum(axis=0))
    expected=guard_reference();errors={key:relative(value,expected[key]) for key,value in actual.items()}
    assert result.whole.panel_count==504 and max(errors.values())<=.01
    assert max(getattr(result.whole,key) for key in ['reciprocity_error','residual_error','current_error','matrix_refinement_error','ground_refinement_error'])<=1e-10
    assert np.max(abs(result.whole.current_integrals[1]))>1e-6
    record_property('harmonic_guard_circle_comparison',json.dumps(dict(errors=errors,values={k:v.tolist() for k,v in actual.items()}),sort_keys=True))
