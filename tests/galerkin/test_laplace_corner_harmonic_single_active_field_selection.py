# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Conductor order and explicit signal selection of the single-active guard field,
split from test_laplace_corner_harmonic_single_active_field.py.

These tests share the module's cached 16-panel solve, calculated(0,16), and no other cached
solve, so they move together and that solve still runs once per CI test part.
"""
from functools import lru_cache

import numpy as np
import pytest

from test_laplace_corner_harmonic_single_active_field import GEOMETRIES, calculated, relative, solve


@lru_cache(maxsize=1)
def full_three():
    from galerkin.laplace_corner_harmonic_field import solve_two_ground_harmonic_corner_three_active_edges
    row=GEOMETRIES[0]
    return solve_two_ground_harmonic_corner_three_active_edges(row['polygons'],width=.008,height=.002,panels_per_edge=16)


def test_explicit_active_index_selects_physical_voltage_boundary():
    row=GEOMETRIES[0];full=full_three();observed=[]
    for signal in (0,1,2):
        result=(calculated(0,16) if signal==2 else solve(row['polygons'],signal=signal,width=.008,height=.002,panels_per_edge=16))
        cap=full.whole.capacitance_per_permittivity[signal:signal+1,signal:signal+1]
        assert relative(result.whole.capacitance_per_permittivity,cap)<=1e-10
        guards=[i for i in range(3) if i!=signal]
        voltage=np.linalg.solve(full.whole.capacitance_per_permittivity,result.whole.current_integrals[:3])
        assert np.max(abs(voltage[guards]))<=1e-10
        np.testing.assert_allclose(result.whole.current_integrals[signal],1.,rtol=0,atol=1e-10)
        observed.append(float(cap[0,0]))
    assert len(set(observed))==3


@pytest.mark.parametrize('permutation',[(0,1,2),(0,2,1),(1,0,2),(1,2,0),(2,0,1),(2,1,0)])
def test_polygon_order_and_explicit_signal_selection(permutation):
    row=GEOMETRIES[0];perm=np.asarray(permutation);undo=np.argsort(perm);base=calculated(0,16)
    signal=int(np.flatnonzero(perm==2)[0])
    other=solve([row['polygons'][i] for i in perm],signal=signal,width=.008,height=.002,panels_per_edge=16)
    assert relative(other.whole.capacitance_per_permittivity,base.whole.capacitance_per_permittivity)<=1e-10
    whole=np.concatenate([other.whole.current_gram[:3][undo],other.whole.current_gram[3:]])
    faces=other.edge_current_gram.reshape(3,4,1,1)[undo].reshape(12,1,1)
    assert relative(whole,base.whole.current_gram)<=1e-10
    assert relative(faces,base.edge_current_gram)<=1e-10


def test_prescribed_guard_voltage_and_induced_current_are_not_floating():
    from galerkin.laplace_corner_harmonic_field import solve_two_ground_harmonic_corner_three_active_edges
    row=GEOMETRIES[0];guard=calculated(0,16)
    full=full_three()
    cap=full.whole.capacitance_per_permittivity;css=cap[2:3,2:3]
    transform=np.linalg.solve(css,cap[:,2:3].T).T
    assert relative(guard.whole.capacitance_per_permittivity,css)<=1e-10
    voltage=np.linalg.solve(cap,guard.whole.current_integrals[:3])
    assert np.max(abs(voltage[:2]))<=1e-10
    assert np.max(abs(guard.whole.current_integrals[:2]))>1e-6
    expected=np.einsum('ai,pab,bj->pij',transform,full.whole.current_gram,transform)
    assert relative(guard.whole.current_gram,expected)<=1e-10
