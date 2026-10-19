# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct checks of the layered transient eigenfunction series; no engine imports."""
import ast
from pathlib import Path

import numpy as np
import pytest

from refsol.transient_heat_multilayer import LayeredWall

WALL = dict(interfaces=[.01, .03], conductivities=[45., .5], capacities=[3.6e6, 1.2e6])
STATE = dict(left_temperature=400., right_temperature=300., amplitudes=[60., -25., 10.])


def test_single_layer_eigenvalues_match_the_sine_series():
    wall = LayeredWall([.2], [2.], [5e5])
    m = np.arange(1, 7)
    np.testing.assert_allclose(wall.eigenvalues(6), (m*np.pi/.2)**2*2./5e5, rtol=1e-12)
    x = np.linspace(0, .2, 9)
    X, _ = wall.mode(1, x, np.zeros(9, int))
    np.testing.assert_allclose(abs(X), abs(np.sin(2*np.pi*x/.2)), atol=1e-4)  # dense max grid


def test_two_layer_eigenvalues_solve_the_characteristic_equation():
    wall = LayeredWall(**WALL)
    lam = wall.eigenvalues(12)
    assert np.all(np.diff(lam) > 0)
    k1, k2 = WALL['conductivities']
    c1, c2 = WALL['capacities']
    a, b = .01, .02
    for l in lam:   # k1 w1 cos(w1 a) sin(w2 b) + k2 w2 sin(w1 a) cos(w2 b) = 0
        w1, w2 = np.sqrt(l*c1/k1), np.sqrt(l*c2/k2)
        f = k1*w1*np.cos(w1*a)*np.sin(w2*b)+k2*w2*np.sin(w1*a)*np.cos(w2*b)
        assert abs(f) < 1e-9*(k1*w1+k2*w2)
    # No root is skipped: the Sturm count from a much finer scan agrees.
    s = np.linspace(1e-9, np.sqrt(lam[-1])*1.0001, 400000)
    values = np.array([wall._end_value(v) for v in s])
    assert np.count_nonzero(np.sign(values[1:]) != np.sign(values[:-1])) == 12


def test_modes_are_c_weighted_orthogonal_and_satisfy_the_interface_conditions():
    wall = LayeredWall(**WALL)
    g, w = np.polynomial.legendre.leggauss(40)
    xs, ws, layer = [], [], []
    for i, (lo, hi) in enumerate(zip(wall.edges[:-1], wall.edges[1:])):
        for p in range(32):
            a, b = lo+(hi-lo)*p/32, lo+(hi-lo)*(p+1)/32
            xs.append(a+(b-a)*(g+1)/2)
            ws.append(w*(b-a)/2)
            layer.append(np.full(len(g), i))
    x, wq, layer = np.concatenate(xs), np.concatenate(ws), np.concatenate(layer)
    modes = [wall.mode(m, x, layer)[0] for m in range(5)]
    gram = np.array([[np.sum(wq*wall.c[layer]*a*b) for b in modes] for a in modes])
    off = gram-np.diag(np.diag(gram))
    assert np.max(abs(off)) < 1e-10*np.max(np.diag(gram))
    for m in range(5):
        X, F = wall.mode(m, np.array([.01-1e-13, .01+1e-13]), np.array([0, 1]))
        np.testing.assert_allclose(X[0], X[1], atol=1e-9)
        np.testing.assert_allclose(F[0], F[1], rtol=1e-8, atol=1e-8*abs(F).max())
        ends, _ = wall.mode(m, np.array([0., .03]), np.array([0, 1]))
        np.testing.assert_allclose(ends, 0., atol=1e-12)


def test_series_satisfies_the_pde_boundaries_and_initial_state():
    wall = LayeredWall(**WALL)
    k, c = np.array(WALL['conductivities']), np.array(WALL['capacities'])
    pts = lambda x: np.column_stack([np.atleast_1d(x), np.zeros(np.size(x))])
    f0 = wall.fields(pts([0., .03]), 37., **STATE)
    np.testing.assert_allclose(f0.temperature, [400., 300.], atol=1e-10)
    for x, i in ((.004, 0), (.008, 0), (.015, 1), (.026, 1)):
        h, dt, t = 1e-6, 1e-3, 20.
        f = wall.fields(pts(x), t, **STATE)
        dTdt = (wall.fields(pts(x), t+dt, **STATE).temperature-wall.fields(pts(x), t-dt, **STATE).temperature)/(2*dt)
        dqdx = (wall.fields(pts(x+h), t, **STATE).heat_flux[0, 0]-wall.fields(pts(x-h), t, **STATE).heat_flux[0, 0])/(2*h)
        np.testing.assert_allclose(c[i]*dTdt, -dqdx, rtol=1e-4, atol=1e-6*abs(c[i]*dTdt).max())
        dTdx = (wall.fields(pts(x+h), t, **STATE).temperature-wall.fields(pts(x-h), t, **STATE).temperature)/(2*h)
        np.testing.assert_allclose(-k[i]*dTdx, f.heat_flux[0, 0], rtol=1e-6)
    # At long time the steady series wall remains.
    late = wall.fields(pts(.01), 1e6, **STATE)
    q0 = 100./(.01/45.+.02/.5)
    np.testing.assert_allclose(late.temperature, 400.-q0*.01/45., rtol=1e-12)


@pytest.mark.parametrize('bad', [dict(interfaces=[.03, .01]), dict(conductivities=[1., 0.]),
                                 dict(capacities=[1.]), dict(interfaces=[])])
def test_invalid_walls(bad):
    with pytest.raises(ValueError):
        LayeredWall(**{**WALL, **bad})


def test_invalid_evaluations():
    wall = LayeredWall(**WALL)
    with pytest.raises(ValueError):
        wall.fields([[.04, 0.]], 1., **STATE)
    with pytest.raises(ValueError):
        wall.fields([[.01, 0.]], -1., **STATE)
    with pytest.raises(ValueError):
        wall.eigenvalues(0)


def test_reference_has_no_engine_solver_or_assembly_imports():
    import refsol.transient_heat_multilayer as module
    for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
            assert all(n.split('.')[0] in ('numpy', 'dataclasses') for n in names)
