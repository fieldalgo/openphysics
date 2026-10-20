# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct checks of the layered elastic references; no engine imports."""
import ast
from pathlib import Path

import numpy as np
import pytest

from refsol.elasticity_multilayer import composite_cylinder, laminate_axial, series_bar

CYL = dict(inner_radius=.02, interfaces=[.03, .045, .05], young_moduli=[200e9, 3e9, 70e9],
           poisson_ratios=[.3, .38, .33])


def law(e, nu, plane):
    mu = e/(2*(1+nu))
    lam = e*nu/((1+nu)*(1-2*nu)) if plane == 'strain' else e*nu/(1-nu*nu)
    return lam, mu


def stress_from_displacement(field, x, e, nu, plane, alpha=0., dT=lambda p: 0., h=1e-7):
    """Central-difference strain of field(points) at x, then the isotropic law."""
    lam, mu = law(e, nu, plane)
    beta = (3*lam+2*mu)*alpha if plane == 'strain' else e*alpha/(1-nu)
    g = np.zeros((2, 2))
    for j in range(2):
        d = np.zeros(2)
        d[j] = h
        g[:, j] = (field(x+d)-field(x-d))/(2*h)
    exx, eyy, gxy = g[0, 0], g[1, 1], g[0, 1]+g[1, 0]
    th = beta*dT(x)
    return np.array([(lam+2*mu)*exx+lam*eyy-th, lam*exx+(lam+2*mu)*eyy-th, mu*gxy])


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_laminate_is_traction_free_on_faces_and_satisfies_the_law(plane):
    kw = dict(y_interfaces=[.002, .005, .006], young_moduli=[70e9, 3e9, 200e9],
              poisson_ratios=[.33, .4, .29], axial_strain=1e-3, plane=plane)
    for y, i in ((.001, 0), (.0035, 1), (.0058, 2)):
        x = np.array([.13, y])
        f = laminate_axial(x[None], **kw)
        assert f.layer[0] == i
        local = stress_from_displacement(lambda q: laminate_axial(q[None], **kw, layer=np.array([i])).displacement[0],
                                         x, kw['young_moduli'][i], kw['poisson_ratios'][i], plane)
        np.testing.assert_allclose(local, f.stress[0], rtol=1e-6, atol=1e-6*abs(f.stress[0, 0]))
    for y in (.002, .005):   # displacement continuous across interfaces
        a = laminate_axial([[.1, y-1e-13], [.1, y+1e-13]], **kw).displacement
        np.testing.assert_allclose(a[0], a[1], rtol=0, atol=1e-15)
    e, nu = np.array(kw['young_moduli']), np.array(kw['poisson_ratios'])
    resultant = np.sum((e if plane == 'stress' else e/(1-nu**2))*np.diff([0, .002, .005, .006]))*1e-3
    pts = np.column_stack([np.full(3, .1), [.001, .0035, .0058]])
    f = laminate_axial(pts, **kw)
    np.testing.assert_allclose(np.sum(f.stress[:, 0]*np.diff([0, .002, .005, .006])), resultant, rtol=1e-13)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_series_bar_with_matched_lateral_strain_and_rejects_mismatch(plane):
    # Plane stress: eps_yy = -nu s/E equal; plane strain: nu(1+nu)/E equal.
    e = np.array([200e9, 100e9])
    nu = np.array([.3, .15]) if plane == 'stress' else None
    if plane == 'strain':
        target = .3*1.3/200e9
        nu2 = (-1+np.sqrt(1+4*target*100e9))/2
        nu = np.array([.3, nu2])
    kw = dict(x_interfaces=[.04, .1], young_moduli=e, poisson_ratios=nu, axial_stress=5e7, plane=plane)
    for x, i in ((.02, 0), (.07, 1)):
        p = np.array([x, .01])
        f = series_bar(p[None], **kw)
        local = stress_from_displacement(lambda q: series_bar(q[None], **kw, layer=np.array([i])).displacement[0],
                                         p, e[i], nu[i], plane)
        np.testing.assert_allclose(local, f.stress[0], rtol=1e-6, atol=1e-6*5e7)
    a = series_bar([[.04-1e-13, .01], [.04+1e-13, .01]], **kw).displacement
    np.testing.assert_allclose(a[0], a[1], rtol=0, atol=1e-15)
    with pytest.raises(ValueError, match='laterally'):
        series_bar([[.01, 0.]], **{**kw, 'poisson_ratios': [.3, .3]})


def lame_single(r, a, b, p_in, p_out):
    srr = (p_in*a*a-p_out*b*b)/(b*b-a*a)-(p_in-p_out)*a*a*b*b/((b*b-a*a)*r*r)
    stt = (p_in*a*a-p_out*b*b)/(b*b-a*a)+(p_in-p_out)*a*a*b*b/((b*b-a*a)*r*r)
    return srr, stt


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_single_shell_matches_textbook_lame(plane):
    r = np.linspace(.02, .05, 7)
    f = composite_cylinder(np.column_stack([r, 0*r]), inner_radius=.02, interfaces=[.05],
                           young_moduli=[200e9], poisson_ratios=[.3], plane=plane,
                           inner_pressure=3e7, outer_pressure=1e6)
    srr, stt = lame_single(r, .02, .05, 3e7, 1e6)
    np.testing.assert_allclose(f.radial_stress, srr, rtol=1e-12, atol=1e-6)
    np.testing.assert_allclose(f.hoop_stress, stt, rtol=1e-12)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_single_shell_log_temperature_matches_timoshenko_thermal_stresses(plane):
    # Timoshenko & Goodier, thick cylinder with radial temperature, free surfaces.
    a, b, e, nu, alpha = .02, .05, 200e9, .3, 1.2e-5
    c0, c1 = 80., -35.
    T = lambda s: c0+c1*np.log(s/a)
    x, w = np.polynomial.legendre.leggauss(40)
    def integral(lo, hi):
        s = lo+(hi-lo)*(x+1)/2
        return np.sum(w*T(s)*s)*(hi-lo)/2
    scale = alpha*e/(1-nu) if plane == 'strain' else alpha*e
    r = np.array([.021, .03, .041, .049])
    total = integral(a, b)
    srr = np.array([scale/ri**2*((ri**2-a**2)/(b**2-a**2)*total-integral(a, ri)) for ri in r])
    stt = np.array([scale/ri**2*((ri**2+a**2)/(b**2-a**2)*total+integral(a, ri)-T(ri)*ri**2) for ri in r])
    f = composite_cylinder(np.column_stack([r, 0*r]), inner_radius=a, interfaces=[b],
                           young_moduli=[e], poisson_ratios=[nu], plane=plane,
                           thermal_expansions=[alpha], temperature_change=[[c0, c1]])
    np.testing.assert_allclose(f.radial_stress, srr, rtol=1e-10, atol=1e-8*abs(stt).max())
    np.testing.assert_allclose(f.hoop_stress, stt, rtol=1e-10, atol=1e-8*abs(stt).max())


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_uniform_heating_of_one_material_is_stress_free_in_plane(plane):
    f = composite_cylinder([[.025, 0.], [0., .045]], **{**CYL, 'young_moduli': [70e9]*3,
                           'poisson_ratios': [.33]*3}, plane=plane,
                           thermal_expansions=[2.3e-5]*3, temperature_change=[[100., 0.]]*3)
    assert np.max(abs(f.stress)) < 1e-6
    expected = 2.3e-5*100*(1+.33 if plane == 'strain' else 1.)
    np.testing.assert_allclose(f.radial_displacement/np.array([.025, .045]), expected, rtol=1e-12)
    if plane == 'strain':
        np.testing.assert_allclose(f.out_of_plane_stress, -70e9*2.3e-5*100, rtol=1e-12)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('load', ['pressure', 'mismatch', 'gradient'])
def test_composite_cylinder_equilibrium_interfaces_and_boundaries(plane, load):
    kw = dict(CYL, plane=plane)
    if load == 'pressure':
        kw.update(inner_pressure=4e7, outer_pressure=5e6)
    else:
        kw.update(thermal_expansions=[1.2e-5, 7e-5, 2.3e-5],
                  temperature_change=[[120., 0.]]*3 if load == 'mismatch'
                  else [[150., -20.], [140., -60.], [110., -5.]])
    edges = [.02, .03, .045, .05]
    f = composite_cylinder([[.02, 0.], [0., .05]], **kw)
    np.testing.assert_allclose(f.radial_stress, [-kw.get('inner_pressure', 0.), -kw.get('outer_pressure', 0.)],
                               atol=1e-6*np.max(abs(f.hoop_stress)))
    for r in edges[1:-1]:
        g = composite_cylinder([[r-1e-13, 0.], [r+1e-13, 0.]], **kw)
        assert g.layer[0] != g.layer[1]
        np.testing.assert_allclose(g.radial_displacement[0], g.radial_displacement[1], rtol=1e-9)
        np.testing.assert_allclose(g.radial_stress[0], g.radial_stress[1], rtol=1e-8,
                                   atol=1e-9*np.max(abs(g.hoop_stress)))
    alpha = kw.get('thermal_expansions', [0.]*3)
    dt = np.asarray(kw.get('temperature_change', [[0., 0.]]*3))
    for i, r in enumerate((.025, .037, .048)):
        angle = .4+i
        x = r*np.array([np.cos(angle), np.sin(angle)])
        sel = np.array([i])
        field = lambda q: composite_cylinder(q[None], **kw, layer=sel).displacement[0]
        local = stress_from_displacement(field, x, CYL['young_moduli'][i], CYL['poisson_ratios'][i], plane,
                                         alpha[i], lambda q: dt[i, 0]+dt[i, 1]*np.log(np.hypot(*q)/.02))
        here = composite_cylinder(x[None], **kw).stress[0]
        np.testing.assert_allclose(local, here, rtol=1e-5, atol=1e-5*np.max(abs(here)))
        # Cartesian equilibrium div(sigma) = 0 by central differences of the stress.
        h = 1e-6
        div = np.zeros(2)
        for j in range(2):
            d = np.zeros(2)
            d[j] = h
            sp, sm = (composite_cylinder((x+s*d)[None], **kw, layer=sel).stress[0] for s in (1, -1))
            ds = (sp-sm)/(2*h)
            div += [ds[0], ds[2]] if j == 0 else [ds[2], ds[1]]
        assert np.max(abs(div)) < 1e-5*np.max(abs(here))/r


@pytest.mark.parametrize('change', [dict(young_moduli=[1., 0., 1.]), dict(poisson_ratios=[.3, .5, .3]),
                                    dict(interfaces=[.03, .03, .05]), dict(plane='auto'),
                                    dict(temperature_change=[[1., 0.]]), dict(thermal_expansions=[1., np.nan, 1.])])
def test_cylinder_rejects_invalid_layers(change):
    with pytest.raises(ValueError):
        composite_cylinder([[.03, 0.]], **{**CYL, 'plane': 'stress', **change})


def test_reference_has_no_engine_solver_or_assembly_imports():
    import refsol.elasticity_multilayer as module
    for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
            assert all(n.split('.')[0] in ('numpy', 'dataclasses') for n in names)
