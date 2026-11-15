# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Replay registered face studies; the independent P2 solver is not rerun here."""
import json
from pathlib import Path
import numpy as np
import pytest
from galerkin.laplace_two_ground import solve_two_ground_rectangle_edges
ROWS=json.loads((Path(__file__).parent/'evidence/edges-registered.json').read_text())


def change(a,b):
    a,b=np.asarray(a),np.asarray(b);d=abs(a-b);scale=np.maximum(abs(a),abs(b))
    return np.divide(d,scale,out=np.zeros_like(d),where=scale!=0)


@pytest.mark.parametrize('row',ROWS,ids=[x['case'] for x in ROWS])
def test_registered_edges_against_independent_volume_reference(row,record_property):
    epsilon_0=row['vacuum_permittivity_f_per_m']
    results=[]
    for count in (64,128,256):
        result=solve_two_ground_rectangle_edges(row['polygons'],width=row['width'],height=row['height'],
            panels_per_edge=count,interpolation_degree=row['degree'])
        expected=row['panel_levels'][str(count)]
        np.testing.assert_allclose(epsilon_0*result.whole.capacitance_per_permittivity,expected['C0'],rtol=1e-10,atol=0)
        np.testing.assert_allclose(result.edge_current_gram,expected['edge_parts'],rtol=1e-10,atol=0)
        np.testing.assert_allclose(result.edge_current_integrals,expected['edge_current_integrals'],rtol=0,atol=1e-10)
        results.append(result)
    assert np.max(change(results[1].edge_current_gram,results[2].edge_current_gram))<=.01
    for level in ('coarse','medium'):
        ref=row['reference_levels'][level]
        np.testing.assert_allclose(epsilon_0*results[-1].whole.capacitance_per_permittivity,ref['C0'],rtol=5e-4,atol=0)
        for extension in ref['face_parts']:
            np.testing.assert_allclose(results[-1].edge_current_gram,extension,rtol=.02,atol=0)
    assert np.max(change(row['reference_levels']['coarse']['face_parts'],row['reference_levels']['medium']['face_parts']))<=.01
    record_property('edge_reference',json.dumps(dict(case=row['case'],C0=(epsilon_0*results[-1].whole.capacitance_per_permittivity).tolist(),edge_parts=results[-1].edge_current_gram.tolist(),source='stored independent P2 volume reference; not rerun'),sort_keys=True))


@pytest.mark.parametrize('row',ROWS,ids=[x['case'] for x in ROWS])
def test_registered_edge_finite_outer_changes(row):
    epsilon_0=row['vacuum_permittivity_f_per_m']
    results=[]
    for width_mm in (8,16,32):
        width=width_mm*.001;p=[np.asarray(x)+[(width-row['width'])/2,0.] for x in row['polygons']]
        result=solve_two_ground_rectangle_edges(p,width=width,height=row['height'],panels_per_edge=256,
            ground_modes=256,interpolation_degree=row['degree'])
        expected=row['finite_outer'][str(width_mm)]
        np.testing.assert_allclose(epsilon_0*result.whole.capacitance_per_permittivity,expected['C0'],rtol=1e-10,atol=0)
        np.testing.assert_allclose(result.edge_current_gram,expected['edge_parts'],rtol=1e-10,atol=0)
        results.append(result)
    for a,b in zip(results,results[1:]):assert np.max(change(a.edge_current_gram,b.edge_current_gram))<=.01
