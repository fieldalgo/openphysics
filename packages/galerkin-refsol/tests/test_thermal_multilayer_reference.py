# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct differential checks of the layered-wall references, no engine imports."""
import ast
from pathlib import Path

import numpy as np
import pytest

from refsol.thermal_multilayer import composite_cylinder, layered_slab

SLAB = dict(interfaces=[.02, .05, .06], conductivities=[15., 0.8, 45.],
            left_temperature=420., right_temperature=300., sources=[2e5, -3e4, 6e5])
CYL = dict(inner_radius=.01, interfaces=[.015, .03, .034], conductivities=[50., .25, 16.],
           inner_temperature=500., outer_temperature=310., sources=[1e6, 0., -2e5])


def _x(x):
    x = np.atleast_1d(x)
    return np.column_stack([x, np.full(len(x), .3)])


def _r(r, angle=.7):
    r = np.atleast_1d(r)
    return np.column_stack([r*np.cos(angle), r*np.sin(angle)])


def test_slab_boundary_temperatures_and_series_resistance_without_source():
    f = layered_slab(_x([0., .06]), **SLAB)
    np.testing.assert_allclose(f.temperature, [420., 300.], rtol=1e-14)
    L = np.diff([0., .02, .05, .06])
    k = np.array([15., .8, 45.])
    plain = layered_slab(_x(np.linspace(0, .06, 7)), **{**SLAB, 'sources': None})
    np.testing.assert_allclose(plain.heat_flux[:, 0], 120./np.sum(L/k), rtol=1e-13)
    np.testing.assert_array_equal(plain.heat_flux[:, 1], 0.)


def test_slab_temperature_and_flux_are_continuous_at_interfaces():
    for x in (.02, .05):
        e = 1e-12
        b = layered_slab(_x([x-e, x+e]), **SLAB)
        slope = np.max(abs(b.heat_flux[:, 0])/np.array(SLAB['conductivities'])[b.layer])
        assert abs(b.temperature[0]-b.temperature[1]) <= 2.01*e*slope+1e-13*b.temperature[0]
        np.testing.assert_allclose(b.heat_flux[0, 0], b.heat_flux[1, 0], rtol=1e-9)
        assert b.layer[0] != b.layer[1]


def test_slab_fourier_law_and_energy_balance_by_finite_differences():
    k, Q = np.array(SLAB['conductivities']), np.array(SLAB['sources'])
    for x in (.007, .013, .031, .044, .057):
        h = 1e-7
        f, plus, minus = (layered_slab(_x(v), **SLAB) for v in (x, x+h, x-h))
        i = f.layer[0]
        np.testing.assert_allclose(-k[i]*(plus.temperature-minus.temperature)/(2*h),
                                   f.heat_flux[:, 0], rtol=1e-6)
        np.testing.assert_allclose((plus.heat_flux[0, 0]-minus.heat_flux[0, 0])/(2*h), Q[i], rtol=1e-6)


def test_cylinder_boundary_values_and_log_resistance_without_source():
    f = composite_cylinder(_r([.01, .034]), **CYL)
    np.testing.assert_allclose(f.temperature, [500., 310.], rtol=1e-14)
    edges = np.array([.01, .015, .03, .034])
    k = np.array(CYL['conductivities'])
    plain = composite_cylinder(_r(np.linspace(.01, .034, 9)), **{**CYL, 'sources': None})
    r = np.hypot(*plain.heat_flux.T)
    rate = 190./np.sum(np.log(edges[1:]/edges[:-1])/k)    # r q_r, W/m per radian
    np.testing.assert_allclose(r*np.linspace(.01, .034, 9), rate, rtol=1e-13)


def test_cylinder_flux_is_radial_continuous_and_satisfies_the_ode():
    k, Q = np.array(CYL['conductivities']), np.array(CYL['sources'])
    for angle in (0., 1.1, 2.9):
        f = composite_cylinder(_r(.02, angle), **CYL)
        direction = np.array([np.cos(angle), np.sin(angle)])
        assert abs(direction[0]*f.heat_flux[0, 1]-direction[1]*f.heat_flux[0, 0]) < 1e-12*np.linalg.norm(f.heat_flux)
    for r in (.015, .03):
        e = 1e-12
        f = composite_cylinder(_r([r-e, r+e]), **CYL)
        slope = np.max(np.hypot(*f.heat_flux.T)/k[f.layer])
        assert abs(f.temperature[0]-f.temperature[1]) <= 2.01*e*slope+1e-13*f.temperature[0]
        np.testing.assert_allclose(f.heat_flux[0], f.heat_flux[1], rtol=1e-8)
    for r in (.012, .02, .028, .032):
        h = 1e-8
        f, plus, minus = (composite_cylinder(_r(v), **CYL) for v in (r, r+h, r-h))
        i = f.layer[0]
        qr = lambda g, s: np.hypot(*g.heat_flux[0])*np.sign(g.heat_flux[0]@_r(s)[0])
        np.testing.assert_allclose(-k[i]*(plus.temperature-minus.temperature)/(2*h), qr(f, r), rtol=1e-6)
        div = ((r+h)*qr(plus, r+h)-(r-h)*qr(minus, r-h))/(2*h)/r
        np.testing.assert_allclose(div, Q[i], rtol=1e-5, atol=1e-6*abs(Q).max())


def test_single_layer_matches_textbook_formulas():
    s = layered_slab(_x([.25]), interfaces=[1.], conductivities=[2.],
                     left_temperature=350., right_temperature=300., sources=[8.])
    np.testing.assert_allclose(s.temperature, 350.-50*.25+8*.25*.75/(2*2.), rtol=1e-14)
    a, b = .1, .3
    c = composite_cylinder(_r([.2]), inner_radius=a, interfaces=[b], conductivities=[3.],
                           inner_temperature=400., outer_temperature=300.)
    np.testing.assert_allclose(c.temperature, 400.-100*np.log(.2/a)/np.log(b/a), rtol=1e-14)


@pytest.mark.parametrize('change', [dict(interfaces=[]), dict(interfaces=[.05, .02, .06]),
                                    dict(conductivities=[1., 0., 1.]), dict(conductivities=[1., 2.]),
                                    dict(sources=[1., np.nan, 1.]), dict(left_temperature=1j)])
def test_slab_rejects_invalid_layers(change):
    with pytest.raises(ValueError):
        layered_slab(_x(.01), **{**SLAB, **change})


def test_points_outside_the_layers_are_rejected():
    with pytest.raises(ValueError):
        layered_slab(_x(.07), **SLAB)
    with pytest.raises(ValueError):
        composite_cylinder(_r(.005), **CYL)
    with pytest.raises(ValueError):
        composite_cylinder(_r(.02), **{**CYL, 'inner_radius': 0.})


def test_explicit_layer_continues_the_layer_formula_past_its_interface():
    r = np.array([.0099, .0151])
    explicit = composite_cylinder(_r(r), **CYL, layer=np.array([0, 0]))
    inside = composite_cylinder(_r([.012, .014]), **CYL)
    assert np.all(inside.layer == 0)
    # Same closed form: T(r) = A - B ln r - Q r^2/(4k) on layer 0.
    rr = np.r_[r, .012, .014]
    T = np.r_[explicit.temperature, inside.temperature]
    k0, Q0 = CYL['conductivities'][0], CYL['sources'][0]
    coef = np.linalg.lstsq(np.column_stack([np.ones(4), np.log(rr)]), T+Q0*rr**2/(4*k0), rcond=None)
    np.testing.assert_allclose(coef[1], 0., atol=1e-10*np.max(abs(T)))
    with pytest.raises(ValueError):
        composite_cylinder(_r(r), **CYL, layer=np.array([0, 3]))
    with pytest.raises(ValueError):
        layered_slab(_x(.01), **SLAB, layer=np.array([0.]))


def test_reference_has_no_engine_solver_or_assembly_imports():
    import refsol.thermal_multilayer as module
    for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
            assert all(n.split('.')[0] in ('numpy', 'dataclasses') for n in names)
