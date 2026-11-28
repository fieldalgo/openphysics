# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Conductor order and explicit signal selection of the two-active guard field,
split from test_laplace_corner_harmonic_guard_field.py.

These tests share the module's cached 16-panel solve, calculated(0,16), and no other cached
solve, so they move together and that solve still runs once per CI test part.
"""
import numpy as np
import pytest

from test_laplace_corner_harmonic_guard_field import GEOMETRIES, calculated, relative, solve


@pytest.mark.parametrize('permutation',[(0,1,2),(0,2,1),(1,0,2),(1,2,0),(2,0,1),(2,1,0)])
def test_polygon_order_and_explicit_signal_selection(permutation):
    row=GEOMETRIES[0];perm=np.asarray(permutation);undo=np.argsort(perm);base=calculated(0,16)
    signals=tuple(int(np.flatnonzero(perm==i)[0]) for i in (0,1))
    other=solve([row['polygons'][i] for i in perm],signals=signals,width=.008,height=.002,panels_per_edge=16)
    assert relative(other.whole.capacitance_per_permittivity,base.whole.capacitance_per_permittivity)<=1e-10
    whole=np.concatenate([other.whole.current_gram[:3][undo],other.whole.current_gram[3:]])
    faces=other.edge_current_gram.reshape(3,4,2,2)[undo].reshape(12,2,2)
    assert relative(whole,base.whole.current_gram)<=1e-10
    assert relative(faces,base.edge_current_gram)<=1e-10


def test_prescribed_guard_voltage_and_induced_current_are_not_floating():
    from galerkin.laplace_corner_harmonic_field import solve_two_ground_harmonic_corner_three_active_edges
    row=GEOMETRIES[0];guard=calculated(0,16)
    full=solve_two_ground_harmonic_corner_three_active_edges(row['polygons'],width=.008,height=.002,panels_per_edge=16)
    cap=full.whole.capacitance_per_permittivity;css=cap[:2,:2]
    transform=np.linalg.solve(css,cap[:,:2].T).T
    assert relative(guard.whole.capacitance_per_permittivity,css)<=1e-10
    voltage=np.linalg.solve(cap,guard.whole.current_integrals[:3])
    assert np.max(abs(voltage[2]))<=1e-10
    assert np.max(abs(guard.whole.current_integrals[2]))>1e-6
    expected=np.einsum('ai,pab,bj->pij',transform,full.whole.current_gram,transform)
    assert relative(guard.whole.current_gram,expected)<=1e-10
