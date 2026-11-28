# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded corner-field references, invariants, convergence and refusals."""
from functools import lru_cache
import json
from pathlib import Path
import numpy as np
import pytest
from galerkin.laplace_two_ground import solve_two_ground_corner_rectangle_edges as solve
from galerkin import _laplace_corner_field as field

ROWS = json.loads((Path(__file__).parent/'two_ground/evidence/corner-field-registered.json').read_text())


def relative(a, b):
    a, b = np.asarray(a), np.asarray(b)
    delta, scale = abs(a-b), np.maximum(abs(a), abs(b))
    assert np.isfinite(delta).all()
    return float(np.max(np.divide(delta, scale, out=np.zeros_like(delta), where=scale != 0)))


def quantities(result):
    n = len(result.whole.capacitance_per_permittivity)
    parts = result.whole.current_gram
    return (result.whole.capacitance_per_permittivity, result.edge_current_gram,
            np.concatenate((parts[:n], parts[n:].sum(axis=0)[None])))


def calculated(index, count=512, width=.008, reflect=False):
    # Normalize the cache key: calculated(i) and calculated(i,512) are the same solve.
    return _calculated(index, count, width, reflect)


@lru_cache(maxsize=32)
def _calculated(index, count, width, reflect):
    row = ROWS[index]
    polygons = [np.asarray(p)+[width/2, 0.] for p in row['centered_polygons']]
    if reflect:
        polygons = [np.column_stack((width-p[:, 0], p[:, 1])) for p in polygons]
    return solve(polygons, width=width, height=row['height'], panels_per_edge=count,
                 ground_modes={.008:256, .016:512, .032:1024}[width])


@pytest.mark.parametrize('index', range(2), ids=[r['case'] for r in ROWS])
def test_independent_volume_reference_and_qualified_reference_mesh(index, record_property):
    row = ROWS[index]
    assert row['reference_qualification']['status'] == 'passed'
    c, faces, whole = quantities(calculated(index))
    refs = row['reference_levels']
    for key in ('C0', 'face_parts', 'whole_parts'):
        assert relative(refs[0][key], refs[1][key]) <= .01
    for reference in refs:
        np.testing.assert_allclose(row['vacuum_permittivity_f_per_m']*c, reference['C0'], rtol=.0005, atol=0)
        for extension in reference['face_parts']:
            np.testing.assert_allclose(faces, extension, rtol=.02, atol=0)
        for extension in reference['whole_parts']:
            np.testing.assert_allclose(whole, extension, rtol=.01, atol=0)
    record_property('corner_field_reference', json.dumps(dict(case=row['case'],
        C0=(row['vacuum_permittivity_f_per_m']*c).tolist(), face_parts=faces.tolist(),
        whole_parts=whole.tolist(), independent_solver='stored P3 values; not rerun'), sort_keys=True))


@pytest.mark.parametrize('index', range(2))
def test_panel_and_two_separate_outer_changes(index):
    values = [quantities(calculated(index, count)) for count in (128, 256, 512)]
    # Retain the first change as evidence; the declared gate is 256 -> 512.
    assert all(np.isfinite(relative(a, b)) for a, b in zip(values[0], values[1]))
    assert max(relative(a, b) for a, b in zip(values[1], values[2])) <= .01
    outer = [quantities(calculated(index, width=width)) for width in (.008, .016, .032)]
    for first, second in zip(outer, outer[1:]):
        assert max(relative(a, b) for a, b in zip(first, second)) <= .01


@pytest.mark.parametrize('index', range(2))
def test_horizontal_reflection_without_diagonal_floor(index):
    original, reflected = calculated(index), calculated(index, reflect=True)
    n = len(ROWS[index]['polygons'])
    c, faces, whole = quantities(reflected)
    faces = faces.reshape(n, 4, n, n)[:, [2, 1, 0, 3]].reshape(4*n, n, n)
    assert max(relative(a, b) for a, b in zip(quantities(original), (c, faces, whole))) <= 1e-10


@pytest.mark.parametrize('index', range(2))
@pytest.mark.parametrize('scale', [2.**-20, 2.**20])
def test_physical_scale_and_normalized_current_units(index, scale):
    row = ROWS[index]
    expected = calculated(index, 128)
    result = solve([np.asarray(p)*scale for p in row['polygons']],
        width=row['width']*scale, height=row['height']*scale)
    assert relative(result.whole.capacitance_per_permittivity, expected.whole.capacitance_per_permittivity) <= 1e-10
    assert relative(scale*result.edge_current_gram, expected.edge_current_gram) <= 1e-10
    assert relative(scale*result.whole.current_gram, expected.whole.current_gram) <= 1e-10
    np.testing.assert_allclose(result.whole.current_integrals, expected.whole.current_integrals, rtol=0, atol=1e-10)


def test_conductor_basis_permutation():
    row = ROWS[1]
    a = calculated(1, 128)
    b = solve(row['polygons'][::-1], width=row['width'], height=row['height'])
    np.testing.assert_allclose(b.whole.capacitance_per_permittivity[::-1, ::-1], a.whole.capacitance_per_permittivity, rtol=1e-10, atol=0)
    assert relative(b.whole.current_gram[[1, 0, 2, 3], ::-1, ::-1], a.whole.current_gram) <= 1e-10
    assert relative(b.edge_current_gram[[4, 5, 6, 7, 0, 1, 2, 3], ::-1, ::-1], a.edge_current_gram) <= 1e-10


@pytest.mark.parametrize('index', range(2))
def test_face_partition_signed_current_and_psd(index):
    r = calculated(index, 128)
    n = len(ROWS[index]['polygons'])
    assert r.whole.panel_count == 4*n*(128-6)
    assert r.whole.condition_bound < 1e10
    for name in ('reciprocity_error', 'residual_error', 'current_error',
                 'matrix_refinement_error', 'ground_refinement_error'):
        assert getattr(r.whole, name) <= 1e-10
    assert r.partition_error <= 1e-10
    for owner in range(n):
        selected = r.edge_owners == owner
        assert relative(r.edge_current_gram[selected].sum(axis=0), r.whole.current_gram[owner]) <= 1e-10
        np.testing.assert_allclose(r.edge_current_integrals[selected].sum(axis=0), np.eye(n)[owner], rtol=0, atol=1e-10)
    np.testing.assert_allclose(r.whole.current_integrals.sum(axis=0), 0, rtol=0, atol=1e-10)
    for part in np.concatenate((r.whole.current_gram, r.edge_current_gram)):
        assert relative(part, part.T) <= 1e-10
        assert np.linalg.eigvalsh(part).min()/np.max(abs(part)) >= -1e-10


def test_immutable_result_and_input_independence():
    polygons = [np.array(p) for p in ROWS[0]['polygons']]
    before = [p.copy() for p in polygons]
    r = solve(polygons, width=.008, height=.002, panels_per_edge=16)
    for a, b in zip(polygons, before):
        assert np.array_equal(a, b)
    arrays = (r.edge_owners, r.edge_starts, r.edge_ends, r.edge_current_gram,
              r.edge_current_integrals, r.whole.capacitance_per_permittivity,
              r.whole.current_gram, r.whole.current_integrals)
    for a in arrays:
        with pytest.raises(ValueError):
            a.flags.writeable = True
    starts = r.edge_starts.copy()
    polygons[0][:] = 0
    assert np.array_equal(r.edge_starts, starts)


@pytest.mark.parametrize('option,value', [
    ('width', True), ('height', 0), ('width', np.inf), ('height', np.nan),
    ('panels_per_edge', 15), ('panels_per_edge', 17), ('panels_per_edge', 514),
    ('panels_per_edge', True), ('panels_per_edge', 32.),
    ('ground_modes', 63), ('ground_modes', 65), ('ground_modes', 4098),
    ('ground_modes', True), ('interpolation_degree', 20), ('interpolation_degree', 26),
    ('interpolation_degree', 24.), ('interpolation_degree', True)])
def test_invalid_resolution_or_dimensions(option, value):
    kwargs = dict(width=.008, height=.002, panels_per_edge=16)
    kwargs[option] = value
    with pytest.raises(ValueError):
        solve(ROWS[0]['polygons'], **kwargs)


@pytest.mark.parametrize('polygons', [[], ROWS[0]['polygons']*3, None,
    [[[.001, .001], [.001, .001], [.002, .001]]],
    [[[.001, 0], [.002, 0], [.002, .001], [.001, .001]]],
    ROWS[0]['polygons']*2])
def test_invalid_geometry_or_unsupported_conductor_count(polygons):
    with pytest.raises(ValueError):
        solve(polygons, width=.008, height=.002, panels_per_edge=16)


def test_explicit_panel_budget_before_dense_assembly(monkeypatch):
    theta = np.arange(9)*2*np.pi/9
    polygon = np.column_stack((.004+.0003*np.cos(theta), .001+.0003*np.sin(theta)))
    monkeypatch.setattr(field, '_half', lambda *args: pytest.fail('dense allocation before budget refusal'))
    with pytest.raises(ValueError, match='4096'):
        solve([polygon], width=.008, height=.002, panels_per_edge=512)


def test_no_fixed_ground_selection_parameter():
    with pytest.raises(TypeError):
        solve(ROWS[1]['polygons'], width=.008, height=.002, signals=[0])


@pytest.mark.parametrize('fault', ['quadrature', 'reciprocity', 'nonfinite'])
def test_matrix_failure_is_not_hidden_by_symmetrization(monkeypatch, fault):
    original = field._smooth
    def bad(*args):
        out = original(*args)
        if fault == 'quadrature' and args[3].shape[1] == 400:
            out = out+1e-5
        elif fault == 'reciprocity':
            out[0, 1] += 1e-5
        elif fault == 'nonfinite':
            out[0, 0] = np.nan
        return out
    monkeypatch.setattr(field, '_smooth', bad)
    with pytest.raises(ValueError, match='matrix'):
        solve(ROWS[0]['polygons'], width=.008, height=.002, panels_per_edge=16)


def test_ground_refinement_failure_has_no_fallback(monkeypatch):
    original = field._ground
    def bad(*args):
        out = original(*args)
        if args[-2] == 16:
            out[:, 1:] *= 1.01
        return out
    monkeypatch.setattr(field, '_ground', bad)
    with pytest.raises(ValueError, match='ground refinement'):
        solve(ROWS[0]['polygons'], width=.008, height=.002, panels_per_edge=16)


HALF_REFERENCES = json.loads((Path(__file__).parent/'two_ground/evidence/power-half-space-integrals.json').read_text())['cases']


@pytest.mark.parametrize('row', HALF_REFERENCES, ids=lambda r:r['name'])
@pytest.mark.parametrize('scale,sign', [(1., 1.), (.5, -1.), (2., 1.)])
def test_batched_half_integrals_against_independent_2d_reference(row, scale, sign):
    a, b, offset = (np.array(row[k])*[sign, 1.]*scale for k in ('a', 'b', 'offset'))
    h = row['height']*scale
    image = np.array([offset[0], -2*h-offset[1]])
    heights = np.array([h, h+offset[1]])
    coarse, fine = field._power_constant_means(a[None], b[None], offset[None], image[None], heights[None], row['p'])
    expected = float(row['reference_values'][-1])
    np.testing.assert_allclose(coarse, [expected], rtol=1e-12, atol=0)
    np.testing.assert_allclose(fine, [expected], rtol=1e-12, atol=0)


@pytest.mark.parametrize('degree', [20, 24])
@pytest.mark.parametrize('kind', ['constant', 'affine', 'quadratic', 'mixed'])
def test_smooth_projection_exact_polynomial_moments_without_rescaling(degree, kind):
    from fractions import Fraction as F
    a = np.array([[.2, .3], [.3, .5], [.5, .35], [.6, .6]])
    direction = np.array([[.04, .01], [-.02, .04], [.05, -.02], [-.01, -.03]])
    p = np.array([.6, 2/3, .875, 1.])
    grid, projection = field._projection(a, a+direction, p, degree, direction)
    before = projection.tobytes()
    def features(x):
        return np.column_stack((np.ones(len(x)), x[:,0], x[:,1], x[:,0]**2, x[:,0]*x[:,1], x[:,1]**2))
    center = np.array([.4, .45]);f = features(grid);fc = features(center[None])[0]
    matrix = np.zeros((6,6));matrix[0,0] = 2.
    if kind == 'affine':matrix[1,0], matrix[0,2] = .25, -.125
    if kind == 'quadratic':matrix += np.diag([0., .5, -.25, .125, .0625, -.03125])
    if kind == 'mixed':matrix[1,4], matrix[3,2], matrix[5,3] = .5, -.25, .125
    out = field._centered_projection(projection, f@matrix@f.T, f@matrix@fc, fc@matrix@f.T, float(fc@matrix@fc))
    moments = []
    for start, v, exponent in zip(a, direction, p):
        x,y,dx,dy,power = map(lambda z:F(float(z)), [*start,*v,exponent])
        m1,m2 = power/(power+1),power/(power+2)
        moments.append([F(1),x+dx*m1,y+dy*m1,x*x+2*x*dx*m1+dx*dx*m2,
            x*y+(x*dy+y*dx)*m1+dx*dy*m2,y*y+2*y*dy*m1+dy*dy*m2])
    expected = np.array([[float(sum(u[k]*F(float(matrix[k,l]))*v[l] for k in range(6) for l in range(6))) for v in moments] for u in moments])
    np.testing.assert_allclose(out, expected, rtol=1e-12, atol=0)
    if kind == 'constant':assert np.array_equal(out, expected)
    assert projection.tobytes() == before
