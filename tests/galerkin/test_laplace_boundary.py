# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
from scipy.constants import epsilon_0
from galerkin.laplace_boundary import solve_grounded_rectangle
from galerkin._laplace_panels import matrix, panels


def solve(polygons, width, height, *, count=32, grading='cubic'):
    # count=1 makes uniform and cubic endpoint grading identical.
    assert grading == 'cubic' or count == 1
    result = solve_grounded_rectangle(polygons, width=width, height=height, panels_per_edge=count)
    return dict(C0=epsilon_0*result.capacitance_per_permittivity,
                parts=result.current_gram, current_integrals=result.current_integrals,
                reciprocity=result.reciprocity_error, matrix_reciprocity=result.reciprocity_error,
                condition=result.condition_bound)



def relative(a,b):return float(np.max(abs(np.asarray(a)-b))/np.max(np.abs(b)))


def polygons(scale=1.):
    return [scale*np.array([[1.05,.2],[1.15,.2],[1.14,.24],[1.06,.24]]),scale*np.array([[1.27,.2],[1.37,.2],[1.36,.25],[1.28,.25]])]


def test_reciprocity_psd_current_scale_and_permutation():
    p=polygons();value=solve(p,2.4,1.,count=16);reverse=solve(p[::-1],2.4,1.,count=16)
    assert value['reciprocity']<1e-10 and value['matrix_reciprocity']<1e-10
    np.testing.assert_allclose(value['C0'],value['C0'].T,rtol=0,atol=0)
    np.testing.assert_allclose(value['current_integrals'],np.vstack((np.eye(2),-np.ones((1,2)))),rtol=0,atol=1e-10)
    for part in value['parts']:assert np.linalg.eigvalsh(part).min()>=-1e-12*np.max(abs(part))
    np.testing.assert_allclose(reverse['C0'],value['C0'][::-1,::-1],rtol=1e-10,atol=1e-25)
    np.testing.assert_allclose(reverse['parts'],value['parts'][[1,0,2],::-1,::-1],rtol=1e-10,atol=1e-12)
    for scale in [.001,1000.]:
        scaled=solve(polygons(scale),2.4*scale,scale,count=16)
        assert relative(scaled['C0'],value['C0'])<1e-10
        assert relative(scaled['parts']*scale,value['parts'])<1e-10


def test_quadrature_and_interpolation_refinement():
    a,b,_=panels(polygons(),16,'cubic')
    first,_=matrix(a,b,2.4,1.,degree=8,order=6);second,_=matrix(a,b,2.4,1.,degree=10,order=8)
    assert relative(first,second)<1e-10


def test_circle_expanding_domain_analytic_limit():
    a,height=.1,.5;b=np.sqrt(height**2-a**2);exact=np.array([2*np.pi*epsilon_0/np.arccosh(height/a),height/(2*np.pi*a*b),1/(2*np.pi*b)])
    theta=np.arange(256)*2*np.pi/256;rows=[]
    for W,H in [(4.,2.),(8.,4.),(16.,8.),(32.,16.),(64.,32.)]:
        polygon=np.column_stack((W/2+a*np.cos(theta),height+a*np.sin(theta)))
        value=solve([polygon],W,H,count=1,grading='uniform');observed=np.r_[value['C0'][0,0],value['parts'][:,0,0]]
        rows.append(dict(W=W,H=H,observed=observed.tolist(),errors=abs(observed/exact-1).tolist(),condition=value['condition'],matrix_reciprocity=value['matrix_reciprocity']))
    errors=np.array([row['errors'] for row in rows]);assert np.all(errors[1:]<errors[:-1]);assert np.all(errors[-1]<.005)

import pytest


@pytest.mark.parametrize('name,value', [
    ('width', True), ('width', '2.4'), ('width', 0), ('width', -1),
    ('width', float('nan')), ('height', float('inf')), ('height', 1j),
    ('panels_per_edge', True), ('panels_per_edge', 1.5), ('panels_per_edge', 0),
    ('panels_per_edge', 257), ('ground_modes', False), ('ground_modes', 63),
    ('ground_modes', 4097), ('ground_modes', 512.),
])
def test_bad_scalar_controls_reject_before_kernel(monkeypatch, name, value):
    import galerkin.laplace_boundary as module
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid input reached numerical assembly')
    monkeypatch.setattr(module.kernel, 'matrix', forbidden)
    kwargs = dict(width=2.4, height=1.)
    kwargs[name] = value
    with pytest.raises(ValueError):
        solve_grounded_rectangle(polygons(), **kwargs)


@pytest.mark.parametrize('case', [
    [], [np.array([[1., .2], [1.1, .2]])],
    [np.array([[1., .2], [1.1, .2], [1.2, .2]])],
    [np.array([[1., .2], [1.1, .2], [1.1, .3], [1., .2]])],
    [np.array([[1., .2], [1.2, .2], [1.05, .23], [1.2, .3], [1., .3]])],
    [np.array([[1., .2], [1.1, .3], [1.1, .2], [1., .3]])],
    [np.array([[0., .2], [.1, .2], [.1, .3], [0., .3]])],
    [np.array([[1., 0.], [1.1, 0.], [1.1, .1], [1., .1]])],
    [np.array([[1., .2], [1.1, .2], [1.1, float('nan')]])],
    [np.array([['1', '.2'], ['1.1', '.2'], ['1.1', '.3']])],
    [np.array([[1.+0j, .2], [1.1, .2], [1.1, .3]])],
    [polygons()[0], polygons()[0]],
    [polygons()[0], polygons()[0]+[.05, 0]],
    [polygons()[0], np.array([[1.08,.21],[1.12,.21],[1.12,.23],[1.08,.23]])],
    [polygons()[0]]*17,
])
def test_invalid_geometry_rejects_before_assembly(monkeypatch, case):
    import galerkin.laplace_boundary as module
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid geometry reached numerical assembly')
    monkeypatch.setattr(module.kernel, 'matrix', forbidden)
    with pytest.raises(ValueError):
        solve_grounded_rectangle(case, width=2.4, height=1.)


def test_caps_clearance_and_star_polygon_reject():
    with pytest.raises(ValueError, match='2048'):
        solve_grounded_rectangle(polygons()+[polygons()[0]+[.5,0]], width=2.4, height=1., panels_per_edge=256)
    with pytest.raises(ValueError, match='extent'):
        solve_grounded_rectangle([polygons()[0]-[1.,0]], width=2.4, height=1.)
    with pytest.raises(ValueError, match='width/height'):
        solve_grounded_rectangle(polygons(), width=20., height=1.)
    theta=np.arange(5)*2*np.pi/5
    star=np.column_stack((1.2+.1*np.cos(theta), .3+.1*np.sin(theta)))[[0,2,4,1,3]]
    with pytest.raises(ValueError, match='simple and convex'):
        solve_grounded_rectangle([star], width=2.4, height=1.)


def test_reversed_orientation_and_immutable_snapshots():
    original = polygons()
    value = solve_grounded_rectangle(original, width=2.4, height=1., panels_per_edge=16)
    reverse = solve_grounded_rectangle([p[::-1] for p in original], width=2.4, height=1., panels_per_edge=16)
    np.testing.assert_allclose(value.capacitance_per_permittivity, reverse.capacitance_per_permittivity, rtol=1e-10)
    np.testing.assert_allclose(value.current_gram, reverse.current_gram, rtol=1e-10)
    before=value.capacitance_per_permittivity.copy()
    original[0][:]=0
    np.testing.assert_array_equal(before,value.capacitance_per_permittivity)
    for a in [value.capacitance_per_permittivity,value.current_gram,value.current_integrals]:
        with pytest.raises(ValueError):a.flat[0]=0
        with pytest.raises(ValueError):a.setflags(write=True)


# Fixed SI geometries: unequal conductor widths and thicknesses.
THIN_PAIR_CASES = [{'W': 0.024, 'H': 0.0105, 'polygons': [[[0.011244031772371203, 0.0005], [0.011845696747027224, 0.0005], [0.011845696747027224, 0.000535], [0.011244031772371203, 0.000535]], [[0.012255968227628797, 0.0005], [0.012755968227628797, 0.0005], [0.012755968227628797, 0.00055], [0.012255968227628797, 0.00055]]]}, {'W': 0.036, 'H': 0.0155, 'polygons': [[[0.0172440317723712, 0.0005], [0.017845696747027226, 0.0005], [0.017845696747027226, 0.000535], [0.0172440317723712, 0.000535]], [[0.018255968227628795, 0.0005], [0.018755968227628796, 0.0005], [0.018755968227628796, 0.00055], [0.018255968227628795, 0.00055]]]}, {'W': 0.048, 'H': 0.0205, 'polygons': [[[0.0232440317723712, 0.0005], [0.023845696747027224, 0.0005], [0.023845696747027224, 0.000535], [0.0232440317723712, 0.000535]], [[0.024255968227628797, 0.0005], [0.024755968227628797, 0.0005], [0.024755968227628797, 0.00055], [0.024255968227628797, 0.00055]]]}]


@pytest.mark.slow
@pytest.mark.parametrize('case', THIN_PAIR_CASES)
def test_thin_asymmetric_pair_panel_convergence(case):
    rows = [solve_grounded_rectangle(case['polygons'], width=case['W'], height=case['H'],
                                     panels_per_edge=n) for n in [32, 64, 128]]
    changes = []
    for first, second in zip(rows, rows[1:]):
        changes.append([relative(first.capacitance_per_permittivity, second.capacitance_per_permittivity)] +
                       [relative(a, b) for a, b in zip(first.current_gram, second.current_gram)])
    changes = np.asarray(changes)
    assert np.all(changes[-1] < changes[0])
    assert changes[-1, 0] <= .001
    assert np.all(changes[-1, 1:] <= .005)
    for value in rows:
        assert value.current_error <= 1e-10
        assert value.reciprocity_error <= 1e-10
        assert value.residual_error <= 1e-10
        assert value.matrix_refinement_error <= 1e-10
        assert value.ground_refinement_error <= 1e-10
        np.linalg.cholesky(value.capacitance_per_permittivity)
        for part in value.current_gram:
            assert np.linalg.eigvalsh(part).min() >= -1e-12*np.max(abs(part))
