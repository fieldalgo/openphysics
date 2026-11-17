# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent checks of the bimetal-strip references; no engine imports."""
import ast
from pathlib import Path

import numpy as np
import pytest

from refsol import bimetal

STRIP = dict(thickness=[.4e-3, .7e-3], youngs_modulus=[200e9, 70e9], poisson_ratio=[.3, .33],
             linear_expansion_coefficient=[12e-6, 23e-6], temperature_change=100., length=20e-3)
SCALE = 200e9*1e-5*100*1e-3    # E alpha dT h, N/m


def _gauss(lo, hi, order=8):
    x, w = np.polynomial.legendre.leggauss(order)
    return (lo+hi)/2+(hi-lo)/2*x, (hi-lo)/2*w


def test_three_published_closed_forms_agree_with_the_force_moment_balance():
    rng = np.random.default_rng(20261022)
    for _ in range(50):
        t1, t2 = rng.uniform(.05e-3, 3e-3, 2)
        e1, e2 = rng.uniform(1e9, 400e9, 2)
        a1, a2 = rng.uniform(.5e-6, 80e-6, 2)
        dt = rng.uniform(-150., 250.)
        layers = dict(thickness=[t1, t2], youngs_modulus=[e1, e2], linear_expansion_coefficient=[a1, a2],
                      temperature_change=dt)
        k = bimetal.curvature(**layers).curvature
        np.testing.assert_allclose(bimetal.timoshenko_curvature(**layers), k, rtol=1e-10)
        np.testing.assert_allclose(bimetal.villarceau_curvature(**layers), k, rtol=1e-10)


def test_equal_materials_do_not_bend_and_sign_follows_the_expansion_mismatch():
    # Identical layers expand freely: the curvature is zero up to the roundoff of the
    # 2x2 solve (the free strain is alpha dT = 1.6e-3, so 1e-12 of it is 1e-15 1/m).
    def curvature(t, e, a, dt):
        return bimetal.curvature(thickness=t, youngs_modulus=e, linear_expansion_coefficient=a, temperature_change=dt)
    free = curvature([1e-3, 2e-3], [70e9, 70e9], [2e-5, 2e-5], 80.)
    assert abs(free.curvature) <= 1e-12*abs(free.strain_yy)/3e-3
    np.testing.assert_allclose(free.strain_yy, 2e-5*80., rtol=1e-12)
    assert curvature([1e-3, 1e-3], [70e9, 70e9], [1e-5, 2e-5], 80.).curvature > 0.
    assert curvature([1e-3, 1e-3], [70e9, 70e9], [2e-5, 1e-5], 80.).curvature < 0.
    assert curvature([1e-3, 1e-3], [70e9, 70e9], [1e-5, 2e-5], -80.).curvature < 0.


def test_thin_film_limit_is_the_uniaxial_stoney_relation():
    es, ts, e1 = 70e9, 1e-3, 100e9
    sf = e1*(20e-6-2e-6)*50.
    ratios = []
    for tf in (1e-5, 1e-6, 1e-7):
        k = bimetal.curvature(thickness=[tf, ts], youngs_modulus=[e1, es], linear_expansion_coefficient=[2e-6, 20e-6],
                              temperature_change=50.).curvature
        ratios.append(k/bimetal.stoney_uniaxial_curvature(thickness=(tf, ts), youngs_modulus=es, stress=sf))
    assert abs(ratios[-1]-1) < 1e-3
    assert np.all(np.diff(abs(np.array(ratios)-1)) < 0)    # approaches 1 as t_f/t_s -> 0


def test_strip_section_carries_no_force_and_no_moment():
    t1, t2 = STRIP['thickness']
    force = moment = 0.
    for lo, hi in ((0., t1), (t1, t1+t2)):
        xs, ws = _gauss(lo, hi)
        f = bimetal.strip_fields(np.column_stack([xs, np.full(len(xs), .011)]), **STRIP)
        force += np.sum(ws*f.stress[:, 1])
        moment += np.sum(ws*xs*f.stress[:, 1])
    assert abs(force) <= 1e-12*SCALE and abs(moment) <= 1e-12*SCALE*(t1+t2)
    assert np.all(f.stress[:, [0, 2]] == 0)


def test_displacement_is_continuous_across_the_interface_and_fixed_at_the_supports():
    t1 = STRIP['thickness'][0]
    e = 1e-12
    f = bimetal.strip_fields(np.array([[t1-e, .007], [t1+e, .007]]), **STRIP)
    assert tuple(f.layer) == (0, 1)
    assert np.max(abs(f.displacement[0]-f.displacement[1])) <= 1e-9*np.max(abs(f.displacement))
    g = bimetal.strip_fields(np.array([[0., 0.], [0., STRIP['length']]]), **STRIP)
    assert np.all(g.displacement[0] == 0) and g.displacement[1, 0] == 0


def test_finite_difference_strains_match_the_beam_kinematics_and_plane_stress_law():
    h = 1e-7
    for p in (np.array([.0002, .013]), np.array([.0009, .004])):
        pts = np.array([p, p+[h, 0], p-[h, 0], p+[0, h], p-[0, h]])
        f = bimetal.strip_fields(pts, **STRIP)
        u, i = f.displacement, f.layer[0]
        exx = (u[1, 0]-u[2, 0])/(2*h)
        eyy = (u[3, 1]-u[4, 1])/(2*h)
        gxy = (u[3, 0]-u[4, 0])/(2*h)+(u[1, 1]-u[2, 1])/(2*h)
        nu, al, dt = STRIP['poisson_ratio'][i], STRIP['linear_expansion_coefficient'][i], STRIP['temperature_change']
        np.testing.assert_allclose(eyy, f.strain_yy[0], rtol=1e-6)
        np.testing.assert_allclose(exx, -nu*(f.strain_yy[0]-al*dt)+al*dt, rtol=1e-6)
        assert abs(gxy) <= 1e-9
        np.testing.assert_allclose(f.stress[0, 1], STRIP['youngs_modulus'][i]*(f.strain_yy[0]-al*dt), rtol=1e-12)


def test_curvature_of_the_x0_face_is_the_closed_form():
    y = np.linspace(0., STRIP['length'], 7)
    f = bimetal.strip_fields(np.column_stack([0*y, y]), **STRIP)
    c = np.polyfit(y, f.displacement[:, 0], 2)
    np.testing.assert_allclose(-2*c[0], f.curvature, rtol=1e-9)
    np.testing.assert_allclose(f.curvature, bimetal.curvature(
        thickness=STRIP['thickness'], youngs_modulus=STRIP['youngs_modulus'],
        linear_expansion_coefficient=STRIP['linear_expansion_coefficient'], temperature_change=100.).curvature)


def test_end_traction_is_sigma_n_of_the_field():
    pts = np.array([[.0001, 0.], [.0009, 0.], [.0001, .02]])
    normals = np.array([[0., -1.], [0., -1.], [0., 1.]])
    t = bimetal.end_traction(pts, normals, **STRIP)
    s = bimetal.strip_fields(pts, **STRIP).stress[:, 1]
    np.testing.assert_allclose(t, np.column_stack([0*s, s*normals[:, 1]]), rtol=0, atol=0)


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        bimetal.curvature(thickness=[1e-3], youngs_modulus=[70e9], linear_expansion_coefficient=[1e-5],
                          temperature_change=10.)
    with pytest.raises(ValueError):
        bimetal.curvature(thickness=[1e-3, -1e-3], youngs_modulus=[70e9, 70e9],
                          linear_expansion_coefficient=[1e-5, 2e-5], temperature_change=10.)
    with pytest.raises(ValueError):
        bimetal.timoshenko_curvature(thickness=(1e-3, 1e-3), youngs_modulus=(0., 70e9),
                                     linear_expansion_coefficient=(1e-5, 2e-5), temperature_change=10.)
    with pytest.raises(ValueError):
        bimetal.strip_fields([[0., 0.]], **{**STRIP, 'poisson_ratio': [.3, .6]})
    with pytest.raises(ValueError):
        bimetal.strip_fields([[2e-3, 0.]], **STRIP)
    with pytest.raises(ValueError):
        bimetal.strip_fields([[0., 0.]], layer=np.array([5]), **STRIP)


def test_module_imports_no_engine():
    source = Path(bimetal.__file__).read_text(encoding='utf-8')
    names = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            names |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level:             # refsol's own modules, by name
            names |= {'.' + n.module} if n.module else {'.' + a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names.add(n.module.split('.')[0])
    assert names <= {'dataclasses', 'numpy', '._checks'}      # ._checks: refsol's text refusal (L2 commit 8)


def test_text_is_refused_and_the_neutral_axis_is_a_position():
    with pytest.raises(TypeError, match='temperature_change: SI numbers only'):
        bimetal.curvature(thickness=[1e-3, 1e-3], youngs_modulus=[70e9, 70e9],
                          linear_expansion_coefficient=[1e-5, 2e-5], temperature_change='80 K')
    c = bimetal.curvature(thickness=[1e-3, 1e-3], youngs_modulus=[70e9, 70e9],
                          linear_expansion_coefficient=[1e-5, 2e-5], temperature_change=80.)
    assert c.position == -c.strain_yy/c.curvature
    np.testing.assert_array_equal(c.strain_yy_at([[c.position, 0.], [0., 1.]]), [c.strain_yy+c.curvature*c.position,
                                                                                c.strain_yy])
