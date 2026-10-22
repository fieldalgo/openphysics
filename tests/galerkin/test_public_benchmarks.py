# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Public-reference benchmarks: Timoshenko bimetal strip and NAFEMS T4.

References: refsol.bimetal (beam-theory closed form that is also the exact
plane-stress field under its own end traction) and refsol.thermal_convection
(separation-of-variables series for the NAFEMS T4 rectangle, plus the published
target). Gates were preregistered from the convergence runs recorded in
docs/packages/galerkin/public_benchmarks.md.
"""
import numpy as np
import pytest

from galerkin.mesh import layered_rectangle_mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from refsol import bimetal
from refsol import thermal_convection as tc

# Bimetal strip: 0.5 mm steel-like layer bonded to 0.5 mm aluminium-like layer,
# 20 mm long, heated uniformly by 100 K. Handbook-type constants, example inputs.
T1 = T2 = .5e-3
LENGTH = 20e-3
E, NU, ALPHA = [200e9, 70e9], [.3, .33], [12e-6, 23e-6]
DT, TREF = 100., 293.15
STRIP = dict(thicknesses=[T1, T2], young_moduli=E, poisson_ratios=NU, expansions=ALPHA,
             temperature_change=DT, length=LENGTH)
KAPPA = bimetal.curvature([T1, T2], E, ALPHA, DT).curvature
FORCE_SCALE = E[0]*ALPHA[1]*DT*(T1+T2)     # N/m of thickness
KELVIN = 273.15


def _duffy(mesh, order=6):
    x, w = np.polynomial.legendre.leggauss(order)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qi,tij->tqj', bary, mesh.nodes[mesh.triangles])
    return bary, points, mesh.areas()[:, None]*weights[None, :]


def fit_curvature(mesh, displacement, y_min, y_max):
    """-d2 u_x/dy2 of a parabola fitted to the x = 0 face nodes in [y_min, y_max]."""
    ids = mesh.boundary['left']
    y = mesh.nodes[ids, 1]
    sel = (y >= y_min-1e-12) & (y <= y_max+1e-12)
    return -2*np.polyfit(y[sel], displacement[ids[sel], 0], 2)[0]


def solve_strip(n, free_ends):
    """2n elements across the thickness, 40n along the strip (square cells)."""
    mesh = layered_rectangle_mesh([T1, T1+T2], LENGTH, [n, n], 40*n, ['layer1', 'layer2'])
    top_left = 40*n*(2*n+1)                       # node (0, LENGTH)
    snapshot = freeze_temperature(mesh, np.full(len(mesh.nodes), TREF+DT))
    supports = {(0, 0): 0., (0, 1): 0., (top_left, 0): 0.}   # statically determinate
    traction = None
    if not free_ends:
        end = lambda p, normals: bimetal.end_traction(p, normals, **STRIP)
        traction = {'top': end, 'bottom': end}
    result = solve_thermoelasticity(
        mesh, snapshot, reference_temperature_k=TREF, plane='stress', dirichlet=supports,
        thermal_expansion_per_k={'layer1': ALPHA[0], 'layer2': ALPHA[1]},
        young_modulus={'layer1': E[0], 'layer2': E[1]},
        poisson_ratio={'layer1': NU[0], 'layer2': NU[1]}, traction=traction)
    return mesh, result


def strip_errors(mesh, result):
    """Relative L2 errors of displacement and stress against the exact field."""
    bary, points, weight = _duffy(mesh)
    layer = np.repeat(mesh.regions, bary.shape[0])
    exact = bimetal.strip_fields(points.reshape(-1, 2), layer=layer, **STRIP)
    uh = np.einsum('qi,tid->tqd', bary, result.displacement[mesh.triangles])
    ue = exact.displacement.reshape(uh.shape)
    se = exact.stress.reshape(*uh.shape[:2], 3)
    du, ds = uh-ue, result.stress[:, None, :]-se
    norm = lambda a: np.sqrt(np.sum(weight[..., None]*a**2))
    return norm(du)/norm(ue), norm(ds)/norm(se)


def _orders(errors):
    e = np.asarray(errors)
    return np.log2(e[:-1]/e[1:])


def test_bimetal_closed_form_and_quick_mesh():
    """n = 4: 2560 triangles; preregistered from the convergence table (6.1e-2)."""
    assert abs(KAPPA-bimetal.timoshenko_curvature(T1, T2, E[0], E[1], ALPHA[0], ALPHA[1], DT)) <= 1e-10*KAPPA
    for free in (False, True):
        mesh, r = solve_strip(4, free)
        assert np.max(abs(r.reaction)) <= 1e-9*FORCE_SCALE
        assert abs(fit_curvature(mesh, r.displacement, LENGTH/4, 3*LENGTH/4)/KAPPA-1) <= 8e-2


@pytest.mark.slow
def test_bimetal_strip_converges_to_the_timoshenko_field():
    """Exact end traction: the closed form is the exact plane-stress solution."""
    errors, curvatures = [], []
    for n in (1, 2, 4, 8):
        mesh, r = solve_strip(n, free_ends=False)
        assert np.max(abs(r.reaction)) <= 1e-9*FORCE_SCALE
        errors.append(strip_errors(mesh, r))
        curvatures.append(fit_curvature(mesh, r.displacement, 0., LENGTH))
    errors = np.array(errors)
    kerr = np.array(curvatures)/KAPPA-1
    print('bimetal exact-traction errors (u, stress)', errors.tolist(), 'curvature', kerr.tolist(),
          _orders(errors[:, 0]), _orders(errors[:, 1]), _orders(abs(kerr)))
    assert np.all(_orders(errors[:, 0])[-2:] >= 1.6)
    assert np.all(_orders(errors[:, 1])[-2:] >= .8)
    assert np.all(_orders(abs(kerr))[-2:] >= 1.6)
    assert abs(kerr[-1]) <= 2.5e-2 and errors[-1, 0] <= 2.5e-2


@pytest.mark.slow
def test_free_ended_strip_has_the_timoshenko_curvature_away_from_the_ends():
    """Traction-free ends: Saint-Venant; the central half matches the exact-traction case."""
    for n in (4, 8):
        mesh_f, free = solve_strip(n, free_ends=True)
        mesh_e, exact = solve_strip(n, free_ends=False)
        k_free = fit_curvature(mesh_f, free.displacement, LENGTH/4, 3*LENGTH/4)
        k_exact = fit_curvature(mesh_e, exact.displacement, LENGTH/4, 3*LENGTH/4)
        print('free-end curvature', n, k_free/KAPPA-1, k_exact/KAPPA-1)
        assert abs(k_free/k_exact-1) <= 1e-4        # end effect on the central half
        assert abs(k_free/KAPPA-1) <= 2.5e-2*(8/n)**2*1.5


# NAFEMS T4
P = tc.NAFEMS_T4
TARGET = tc.NAFEMS_T4_TARGET


def solve_t4(n):
    mesh = rectangle_mesh(P.width, P.height, 6*n, 10*n)
    hot = {int(i): P.bottom_temperature+KELVIN for i in mesh.boundary['bottom']}
    ambient = P.ambient+KELVIN
    r = solve_steady_heat(mesh, conductivity=P.conductivity, dirichlet=hot,
                          convection={'right': (P.convection, ambient), 'top': (P.convection, ambient)})
    celsius = r.temperature-KELVIN
    node = np.flatnonzero(np.isclose(mesh.nodes[:, 0], TARGET.point[0]) & np.isclose(mesh.nodes[:, 1], TARGET.point[1]))
    assert len(node) == 1
    return mesh, celsius, float(celsius[node[0]])


def t4_errors(mesh, celsius, terms=300):
    bary, points, weight = _duffy(mesh, 4)
    exact = tc.series(points.reshape(-1, 2), P, terms=terms).temperature.reshape(points.shape[:2])
    th = np.einsum('qi,ti->tq', bary, celsius[mesh.triangles])
    sq = weight*(th-exact)**2
    norm = np.sqrt(np.sum(weight*exact**2))
    far = points[..., 1] >= .1
    return np.sqrt(np.sum(sq))/norm, np.sqrt(np.sum(sq[far]))/norm


def test_nafems_t4_quick_mesh_matches_the_series_and_the_published_target():
    """n = 8: 7680 triangles; preregistered point error 1.5e-2 C."""
    exact = tc.series(np.array([TARGET.point]), P, terms=160).temperature[0]
    _, _, value = solve_t4(8)
    assert abs(value-exact) <= 2.5e-2
    assert abs(value-TARGET.value) <= TARGET.quoted_precision


@pytest.mark.slow
def test_nafems_t4_converges_at_second_order_away_from_the_hot_corner():
    exact = tc.series(np.array([TARGET.point]), P, terms=300).temperature[0]
    l2, far, point = [], [], []
    for n in (2, 4, 8, 16):
        mesh, celsius, value = solve_t4(n)
        a, b = t4_errors(mesh, celsius)
        l2.append(a); far.append(b); point.append(abs(value-exact))
    print('T4 errors L2, L2(y>=0.1), point', l2, far, point, _orders(l2), _orders(far), _orders(point))
    assert np.all(_orders(far)[-2:] >= 1.8)
    assert np.all(_orders(point)[-2:] >= 1.8)
    assert np.all(_orders(l2)[-2:] >= 1.5)        # Dirichlet/Robin corner limits the global rate
    assert point[-1] <= 1e-2 and far[-1] <= 1e-4


def test_figure_script_quick_run_writes_consistent_numbers(tmp_path):
    import importlib.util
    import json
    from pathlib import Path
    pytest.importorskip('matplotlib')
    script = Path(__file__).resolve().parents[2]/'examples'/'galerkin'/'public_benchmarks.py'
    spec = importlib.util.spec_from_file_location('openphysics_public_benchmarks', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = module.main([str(tmp_path), '--quick'])
    assert json.loads((tmp_path/'public_benchmarks.json').read_text(encoding='utf-8')) == values
    assert (tmp_path/'public_benchmarks.png').stat().st_size > 0
    assert abs(values['bimetal']['closed_form_curvature_per_m']-KAPPA) <= 1e-12*KAPPA
    assert values['nafems_t4']['published_c'] == TARGET.value
    assert abs(values['nafems_t4']['rows'][-1]['temperature_c']-18.1936) < 1e-3     # n = 4 row of the table
