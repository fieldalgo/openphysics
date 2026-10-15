# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Public thermal/traction consumers, run outside source with installed wheels.

Direct closed forms, weak resultants and actual archived examples supplement,
and do not replace, the independent source convergence/acceptance evidence.
"""
import re
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import galerkin.thermal as heat
import galerkin.elasticity as elastic
import refsol.thermal as heat_reference
import refsol.elasticity_traction as traction_reference
from galerkin.mesh import rectangle_mesh


def scaled_close(actual, expected, scale, rtol=1e-10, atol=1e-12):
    assert np.isfinite(scale) and scale > 0
    np.testing.assert_allclose(np.asarray(actual) / scale, np.asarray(expected) / scale,
                               rtol=rtol, atol=atol)


def test_new_submodules_are_installed():
    for module in (heat, elastic, heat_reference, traction_reference):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())


@pytest.mark.parametrize("offset", [0., 1000.])
def test_heat_kelvin_slab_flux_and_outward_sign(offset):
    mesh = rectangle_mesh(2., .7, 8, 5)
    bc = {int(i): 350. + offset for i in mesh.boundary['left']}
    bc.update({int(i): 300. + offset for i in mesh.boundary['right']})
    result = heat.solve_steady_heat(mesh, conductivity=12., dirichlet=bc)
    expected = 350. + offset - 25. * mesh.nodes[:, 0]
    reference = heat_reference.slab(mesh.nodes, length=2., conductivity=12.,
                                    left_temperature=350. + offset, right_temperature=300. + offset)
    scaled_close(result.temperature - (300. + offset), expected - (300. + offset), 50.)
    scaled_close(reference.temperature - (300. + offset), expected - (300. + offset), 50.)
    scaled_close(result.heat_flux, np.tile([300., 0.], (mesh.num_triangles, 1)), 300.)
    scaled_close(reference.heat_flux, np.tile([300., 0.], (mesh.num_nodes, 1)), 300.)
    np.testing.assert_array_equal(result.load, 0.)
    left = result.reaction[mesh.boundary['left']].sum()
    right = result.reaction[mesh.boundary['right']].sum()
    scaled_close([left, right], [210., -210.], 210.)
    assert -left < 0 < -right  # outward heat is minus the fixed-node reaction
    fixed = np.array(sorted(bc))
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    np.testing.assert_array_equal(result.reaction[free], 0.)
    scale = np.abs(result.load).sum() + np.abs(result.reaction).sum()
    assert abs(np.sum(result.load + result.reaction)) / scale <= 1e-10


def heat_closed_form_errors(mesh, result):
    # Independent interior integration of a quadratic mixed-insulation solution.
    x, w = np.polynomial.legendre.leggauss(4)
    x, w = (x + 1) / 2, w / 2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qa,tad->tqd', bary, mesh.nodes[mesh.triangles])
    xx = points[..., 0]
    exact_t = 300. + 48./12. * (2.*xx - xx**2/2.)
    exact_q = np.stack([-48.*(2.-xx), np.zeros_like(xx)], axis=-1)
    actual_t = np.einsum('qa,ta->tq', bary, result.temperature[mesh.triangles])
    area_weights = mesh.areas()[:, None] * weights
    et = np.sqrt(np.sum(area_weights * (actual_t - exact_t)**2))
    eq = np.sqrt(np.sum(area_weights * np.sum((result.heat_flux[:, None] - exact_q)**2, axis=-1)))
    return et, eq


def test_heat_constant_source_mixed_insulation_closed_form():
    # x=0 is at 300 K; x=2, top and bottom are insulated. Q=48 W/m^3.
    # Exact T=300+Q/k*(L*x-x^2/2), q=(-Q*(L-x),0). Use the existing
    # regular-solution P1 orders 1.8/.9 on one small 8->16 consumer interval;
    # this is not the independent full source mesh/quadrature acceptance gate.
    errors = []
    for nx in (8, 16):
        mesh = rectangle_mesh(2., .7, nx, nx // 2)
        bc = {int(i): 300. for i in mesh.boundary['left']}
        constant = heat.solve_steady_heat(mesh, conductivity=12., dirichlet=bc, heat_source=48.)
        callback = heat.solve_steady_heat(mesh, conductivity=12., dirichlet=bc,
                                          heat_source=lambda points: np.full(len(points), 48.))
        scaled_close(callback.temperature - 300., constant.temperature - 300., 8.)
        scaled_close(callback.heat_flux, constant.heat_flux, 96.)
        scaled_close(callback.load, constant.load, 67.2)
        scaled_close(callback.reaction, constant.reaction, 67.2)
        scaled_close(constant.load.sum(), 48.*2.*.7, 67.2)
        scaled_close(constant.reaction.sum(), -48.*2.*.7, 67.2)
        assert -constant.reaction.sum() > 0  # positive generation leaves through x=0
        scale = np.abs(constant.load).sum() + np.abs(constant.reaction).sum()
        assert abs(np.sum(constant.load + constant.reaction)) / scale <= 1e-10
        assert constant.temperature.max() > 300.
        errors.append(heat_closed_form_errors(mesh, constant))
    coarse, fine = np.asarray(errors)
    assert np.all(fine > 0) and np.all(fine < coarse)
    assert np.log2(coarse[0] / fine[0]) >= 1.8
    assert np.log2(coarse[1] / fine[1]) >= .9


def test_heat_rejects_unconstrained_constant_mode():
    mesh = rectangle_mesh(1., 1., 2, 2)
    with pytest.raises(ValueError):
        heat.solve_steady_heat(mesh, conductivity=12., dirichlet={})


@pytest.mark.parametrize('conductivity', [0., -1., np.nan])
def test_heat_rejects_invalid_conductivity(conductivity):
    mesh = rectangle_mesh(1., 1., 2, 2)
    with pytest.raises(ValueError):
        heat.solve_steady_heat(mesh, conductivity=conductivity, dirichlet={0: 300.})


@pytest.mark.parametrize('source', [lambda p: 1., lambda p: np.full(len(p), np.nan)])
def test_heat_rejects_invalid_source_callback(source):
    mesh = rectangle_mesh(1., 1., 2, 2)
    with pytest.raises(ValueError):
        heat.solve_steady_heat(mesh, conductivity=12., dirichlet={0: 300.}, heat_source=source)


def archived_example(name):
    path = Path(__file__).resolve().parents[1] / 'examples' / name
    assert path.is_file(), 'the checker must supply the byte-verified archived example'
    completed = subprocess.run([sys.executable, '-I', str(path)],
                               check=True, capture_output=True, text=True)
    return completed.stdout.splitlines()


def test_archived_heat_example():
    lines = archived_example('thermal_steady2d.py')
    assert len(lines) == 4
    labels = ['Maximum temperature error (K):', 'Mean heat flux (W/m^2):',
              'Left/right heat input (W/m of thickness):', 'Heat imbalance (W/m of thickness):']
    assert all(line.startswith(label) for line, label in zip(lines, labels))
    assert abs(float(lines[0].split(':', 1)[1])) / 50. <= 1e-10
    flux = np.fromstring(lines[1].split(':', 1)[1].strip(' []'), sep=' ')
    sides = np.fromstring(lines[2].split(':', 1)[1], sep=' ')
    scaled_close(flux, [300., 0.], 300.)
    scaled_close(sides, [210., -210.], 210.)
    assert -sides[0] < 0 < -sides[1]
    assert abs(float(lines[3].split(':', 1)[1])) / np.abs(sides).sum() <= 1e-10


def rollers(mesh):
    bc = {(int(i), 0): 0. for i in mesh.boundary['left']}
    bc.update({(int(i), 1): 0. for i in mesh.boundary['bottom']})
    return bc


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_traction_uniaxial_closed_form(plane):
    mesh = rectangle_mesh(1.2, .7, 4, 3)
    e, nu, p = 70000., .3, 123.
    ex, ey = (p/e, -nu*p/e) if plane == 'stress' else ((1-nu**2)*p/e, -nu*(1+nu)*p/e)
    result = elastic.solve_elasticity(mesh, young_modulus=e, poisson_ratio=nu,
                                      plane=plane, dirichlet=rollers(mesh), traction={'right': (p, 0.)})
    exact = traction_reference.uniaxial(mesh.nodes, p, young_modulus=e, poisson_ratio=nu, plane=plane)
    expected_u = mesh.nodes * [ex, ey]
    scaled_close(result.displacement, expected_u, p/e*1.2)
    scaled_close(exact.displacement, expected_u, p/e*1.2)
    scaled_close(result.strain, np.tile([ex, ey, 0.], (mesh.num_triangles, 1)), p/e)
    scaled_close(result.stress, np.tile([p, 0., 0.], (mesh.num_triangles, 1)), p)
    scaled_close(result.load.sum(axis=0), [p*.7, 0.], p*.7)
    scaled_close(result.reaction.sum(axis=0), [-p*.7, 0.], p*.7)
    scale = np.linalg.norm(result.load.sum(axis=0))
    assert np.linalg.norm((result.load + result.reaction).sum(axis=0)) / scale <= 1e-9


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_traction_shear_closed_form(plane):
    mesh = rectangle_mesh(1.2, .7, 4, 3)
    e, nu, tau = 70000., .3, 87.
    mu = e/(2*(1+nu))
    bc = {(int(i), c): 0. for i in mesh.boundary['bottom'] for c in (0, 1)}

    def field(points, normals):
        return tau * normals[:, ::-1]  # sigma=[[0,tau],[tau,0]]

    result = elastic.solve_elasticity(mesh, young_modulus=e, poisson_ratio=nu, plane=plane,
                                      dirichlet=bc, traction={s: field for s in ('left', 'right', 'top')})
    exact = traction_reference.shear(mesh.nodes, tau, young_modulus=e, poisson_ratio=nu, plane=plane)
    expected = np.column_stack([tau/mu * mesh.nodes[:, 1], np.zeros(mesh.num_nodes)])
    scaled_close(result.displacement, expected, tau/mu*.7)
    scaled_close(exact.displacement, expected, tau/mu*.7)
    scaled_close(result.stress, np.tile([0., 0., tau], (mesh.num_triangles, 1)), tau)


def test_traction_consistent_linear_load_and_outward_normal():
    mesh = rectangle_mesh(1., 1., 1, 1)
    bc = {(i, c): 0. for i in range(mesh.num_nodes) for c in (0, 1)}
    right = sorted(mesh.boundary['right'], key=lambda i: mesh.nodes[i, 1])

    def linear(points, normals):
        scaled_close(normals, np.tile([1., 0.], (len(points), 1)), 1.)
        y = points[:, 1]
        return np.column_stack([3. + 2.*y, -4. + y])

    expected = np.zeros((mesh.num_nodes, 2))
    expected[right[0]] = [11./6., -11./6.]
    expected[right[1]] = [13./6., -5./3.]
    outputs = []
    for reverse in (False, True):
        if reverse:
            mesh.boundary_edges['right'] = mesh.boundary_edges['right'][:, ::-1].copy()
        r = elastic.solve_elasticity(mesh, young_modulus=70000., poisson_ratio=.3, plane='stress',
                                     dirichlet=bc, traction={'right': linear})
        scaled_close(r.load, expected, np.linalg.norm([4., -3.5]))
        scaled_close(r.reaction, -expected, np.linalg.norm([4., -3.5]))
        outputs.append(r.load)
    scaled_close(outputs[0], outputs[1], np.linalg.norm([4., -3.5]))


def test_traction_preserves_load_on_prescribed_dofs():
    mesh = rectangle_mesh(1., 1., 1, 1)
    u = mesh.nodes @ np.array([[.002, .0003], [.0001, -.0006]]).T + [.01, -.02]
    bc = {(i, c): u[i, c] for i in range(mesh.num_nodes) for c in (0, 1)}
    args = dict(young_modulus=70000., poisson_ratio=.3, plane='stress', dirichlet=bc)
    base = elastic.solve_elasticity(mesh, **args)
    loaded = elastic.solve_elasticity(mesh, **args, traction={'right': (123., -17.)})
    np.testing.assert_array_equal(loaded.displacement, base.displacement)
    scaled_close(loaded.reaction - base.reaction, -loaded.load, np.linalg.norm([123., -17.]))
    scaled_close(loaded.load.sum(axis=0), [123., -17.], np.linalg.norm([123., -17.]))


@pytest.mark.parametrize('kind', ['duplicate', 'interior'])
def test_traction_rejects_invalid_selected_edges(kind):
    mesh = rectangle_mesh(1., 1., 1, 1)
    if kind == 'duplicate':
        mesh.boundary_edges['alias'] = mesh.boundary_edges['right'].copy()
        traction = {'right': (1., 0.), 'alias': (1., 0.)}
    else:
        owners = {}
        for tri in mesh.triangles:
            for a, b in ((0, 1), (1, 2), (2, 0)):
                edge = tuple(sorted((int(tri[a]), int(tri[b]))))
                owners[edge] = owners.get(edge, 0) + 1
        edge = next(edge for edge, count in owners.items() if count == 2)
        mesh.boundary_edges['interior'] = np.array([edge], dtype=int)
        traction = {'interior': (1., 0.)}
    with pytest.raises(ValueError):
        elastic.solve_elasticity(mesh, young_modulus=70000., poisson_ratio=.3, plane='stress',
                                 dirichlet=rollers(mesh), traction=traction)


def test_traction_none_and_empty_mapping_keep_existing_results():
    mesh = rectangle_mesh(1., 1., 2, 2)
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    args = dict(young_modulus=70000., poisson_ratio=.3, plane='strain', dirichlet=bc, body_force=(0., -1.))
    default = elastic.solve_elasticity(mesh, **args)
    for traction in (None, {}):
        result = elastic.solve_elasticity(mesh, **args, traction=traction)
        for name in ('displacement', 'strain', 'stress', 'load', 'reaction', 'residual'):
            np.testing.assert_array_equal(getattr(result, name), getattr(default, name))


def test_archived_traction_example():
    lines = archived_example('elasticity_traction.py')
    assert len(lines) == 6
    for j, plane in enumerate(('stress', 'strain')):
        first, forces, energies = lines[3*j:3*j+3]
        assert first.startswith(plane + ' max ux (m):')
        assert forces.startswith('load / reaction per thickness (N/m):')
        assert energies.startswith('energy / proportional external work per thickness (J/m):')
        ex = 123./70000. * (1. if plane == 'stress' else 1-.3**2)
        scaled_close(float(first.split(':', 1)[1]), ex*1.2, ex*1.2)
        arrays = [np.fromstring(s, sep=' ') for s in re.findall(r'\[([^\]]+)\]', forces)]
        assert len(arrays) == 2 and all(a.shape == (2,) for a in arrays)
        scaled_close(arrays[0], [86.1, 0.], 86.1, rtol=1e-9)
        scaled_close(arrays[1], [-86.1, 0.], 86.1, rtol=1e-9)
        assert np.linalg.norm(arrays[0] + arrays[1]) / 86.1 <= 1e-9
        energy, work = np.fromstring(energies.split(':', 1)[1], sep=' ')
        expected = .5 * 123. * ex * 1.2 * .7
        scaled_close([energy, work], [expected, expected], expected)
