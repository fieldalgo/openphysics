# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent checks of the convective-rectangle series; no engine imports."""
import ast
from pathlib import Path

import numpy as np
import pytest

from refsol import _published, thermal_convection as tc

P = tc.nafems_t4()                  # SI, from the published degC literals at run time
TARGET = tc.nafems_t4_target()
CELSIUS = 273.15                    # K at 0 degC: the SI series compared with the published degC numbers


def celsius_problem(bottom, ambient):
    """NAFEMS T4's rectangle with its temperatures given as the numbers ``bottom`` and ``ambient``."""
    return tc.ConvectionRectangle(length=(.6, 1.), thermal_conductivity=52., heat_transfer_coefficient=750.,
                                  prescribed_temperature=bottom, ambient_temperature=ambient)


def test_published_statement_is_recorded():
    s = _published.NAFEMS_T4
    assert (s.width, s.height, s.conductivity, s.convection) == (.6, 1., 52., 750.)
    assert (s.bottom_temperature, s.ambient) == (100., 0.) and s.unit == 'degC'
    t = _published.NAFEMS_T4_TARGET
    assert t.point == (.6, .2) and t.value == 18.3 and t.quoted_precision == .1 and t.unit == 'degC'
    assert 'NAFEMS' in t.source


def test_accessors_return_si_by_the_decimal_rule():
    # K = float(Fraction(repr(degC)) + 273.15): the doubles nearest 373.15, 273.15 and 291.45
    assert P.length == (.6, 1.) and (P.thermal_conductivity, P.heat_transfer_coefficient) == (52., 750.)
    assert (P.prescribed_temperature, P.ambient_temperature) == (373.15, 273.15)
    assert TARGET.position == (.6, .2) and TARGET.temperature == 291.45 and TARGET.temperature_tolerance == .1
    assert TARGET.source == _published.NAFEMS_T4_TARGET.source
    with pytest.raises(TypeError):
        celsius_problem('100 degC', 0.)


def test_eigenvalues_solve_the_robin_condition_in_order():
    lam = tc.eigenvalues(P, 40)
    assert np.all(np.diff(lam) > 0)
    width = P.length[0]
    np.testing.assert_allclose(lam*np.tan(lam*width), P.heat_transfer_coefficient/P.thermal_conductivity, rtol=1e-10)
    n = np.arange(40)
    assert np.all(lam > n*np.pi/width) and np.all(lam < (n+.5)*np.pi/width)


def test_series_satisfies_laplace_by_finite_differences():
    h = 1e-4
    for c in (np.array([.3, .5]), np.array([.1, .9]), np.array([.5, .3])):
        pts = np.array([c, c+[h, 0], c-[h, 0], c+[0, h], c-[0, h]])
        t = tc.series(pts, P, terms=200).temperature
        assert abs(t[1]+t[2]+t[3]+t[4]-4*t[0])/h**2 <= 1e-6*abs(t[0])/h**2*1e-4+1e-3


def test_flux_is_minus_k_grad_t_by_finite_differences():
    h = 1e-6
    for c in (np.array([.3, .5]), np.array([.55, .15])):
        pts = np.array([c, c+[h, 0], c-[h, 0], c+[0, h], c-[0, h]])
        f = tc.series(pts, P, terms=200)
        grad = np.array([(f.temperature[1]-f.temperature[2]), (f.temperature[3]-f.temperature[4])])/(2*h)
        np.testing.assert_allclose(f.heat_flux[0], -P.thermal_conductivity*grad, rtol=1e-6)


def test_boundary_conditions_hold():
    f = tc.series(np.array([[.6, .5], [.3, 1.], [.6, 1.], [0., .5], [0., .05]]), P, terms=200)
    h, ta = P.heat_transfer_coefficient, P.ambient_temperature
    np.testing.assert_allclose(f.heat_flux[0, 0], h*(f.temperature[0]-ta), rtol=1e-12)   # x = W, n = +x
    np.testing.assert_allclose(f.heat_flux[1, 1], h*(f.temperature[1]-ta), rtol=1e-12)   # y = H, n = +y
    np.testing.assert_allclose(f.heat_flux[2], h*(f.temperature[2]-ta), rtol=1e-12)      # corner, both
    assert np.all(f.heat_flux[3:, 0] == 0)                                                # insulated x = 0


def test_hot_edge_is_approached_like_a_fourier_series():
    x = np.array([0., .15, .3, .45])
    errors = [np.max(abs(tc.series(np.column_stack([x, 0*x]), P, terms=n).temperature-P.prescribed_temperature))
              for n in (100, 400, 1600)]
    assert errors[-1] < 1e-4 and np.all(np.diff(errors) < 0)


def test_interior_values_converge_geometrically_and_the_target_value():
    pts = np.array([[.6, .2], [.2, .05]])
    t10, t20, t40, t80, t160 = (tc.series(pts, P, terms=n).temperature for n in (10, 20, 40, 80, 160))
    assert np.max(abs(t80-t160)) < 1e-5 and np.max(abs(t40-t160)) < 1e-3 and np.max(abs(t20-t160)) < 1e-1
    assert np.max(abs(t10-t160)) < 1.      # geometric: each doubling of the terms gains >= 2 digits
    value = t160[0]
    assert abs((value-CELSIUS)-18.2538) < 1e-4  # exact value of the stated problem at (0.6, 0.2), in degC
    assert abs(value-TARGET.temperature) <= TARGET.temperature_tolerance
    assert P.ambient_temperature < value < P.prescribed_temperature


def test_temperature_offset_and_scaling_are_linear():
    base = tc.series(np.array([[.4, .3]]), celsius_problem(100., 0.), terms=60).temperature[0]
    shifted = tc.series(np.array([[.4, .3]]), celsius_problem(373.15, 273.15), terms=60)
    np.testing.assert_allclose(shifted.temperature[0], base+273.15, rtol=1e-13)
    doubled = tc.series(np.array([[.4, .3]]), celsius_problem(200., 0.), terms=60)
    np.testing.assert_allclose(doubled.temperature[0], 2*base, rtol=1e-13)
    si = tc.series(np.array([[.4, .3]]), P, terms=60).temperature[0]       # the accessor's 373.15 K, 273.15 K
    np.testing.assert_allclose(si, base+273.15, rtol=1e-13)


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        tc.series(np.array([[.7, .2]]), P)
    with pytest.raises(ValueError):
        tc.series(np.array([[.1, .2]]), tc.ConvectionRectangle(length=(.6, 1.), thermal_conductivity=52.,
                                                               heat_transfer_coefficient=0., prescribed_temperature=100.,
                                                               ambient_temperature=0.))
    with pytest.raises(ValueError):
        tc.eigenvalues(P, 0)
    with pytest.raises(ValueError):
        tc.series([[.1]], P)


def test_module_imports_no_engine():
    source = Path(tc.__file__).read_text(encoding='utf-8')
    names = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            names |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names.add('.' if n.level else n.module.split('.')[0])     # '.': refsol's private modules
    assert names <= {'dataclasses', 'fractions', 'numpy', 'scipy', '.'}
