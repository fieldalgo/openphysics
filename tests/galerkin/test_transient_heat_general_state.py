# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""General-state original-BE controls for numerical stabilization candidates.

Small dense references are assembled here from P1 integrals, without producer
assembly/refsol imports. Existing convergence gates and cases are not replaced.
"""
import numpy as np
import pytest

from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.transient_heat import solve_transient_heat

TIMES = np.array([.2, .23, .41, .9])
K = 2.5
C = 4.


def _skewed(width, height, nx, ny):
    mesh = rectangle_mesh(width, height, nx, ny)
    exterior = np.unique(np.concatenate(list(mesh.boundary.values())))
    interior = np.setdiff1d(np.arange(mesh.num_nodes), exterior)
    mesh.nodes[interior] += [.013*width, -.009*height]
    return mesh


def _operators(mesh):
    cells = mesh.triangles
    points = mesh.nodes[cells]
    size = mesh.num_nodes
    mass, stiffness = np.zeros((size, size)), np.zeros((size, size))
    gradients, areas, local_k = [], [], []
    for ids, p in zip(cells, points):
        jacobian = np.column_stack((p[1]-p[0], p[2]-p[0]))
        area = np.linalg.det(jacobian)/2
        assert area > 0
        grad = np.array([[-1., -1.], [1., 0.], [0., 1.]])@np.linalg.inv(jacobian)
        me = C*area*(np.ones((3, 3))+np.eye(3))/12
        ke = K*area*(grad@grad.T)
        mass[np.ix_(ids, ids)] += me
        stiffness[np.ix_(ids, ids)] += ke
        gradients.append(grad); areas.append(area); local_k.append(ke)
    return mass, stiffness, np.array(gradients), np.array(areas), np.array(local_k)


def _q(points, now):
    return 1.4+.3*points[:, 0]-.2*points[:, 1]+.5*now


def _load(mesh, area, now):
    # Q is affine in coordinates, so N_i Q integrates exactly by the P1 mass.
    nodal_q = _q(mesh.nodes, now)[mesh.triangles]
    local = area[:, None]*(nodal_q+nodal_q.sum(axis=1)[:, None])/12
    load = np.zeros(mesh.num_nodes)
    np.add.at(load, mesh.triangles.ravel(), local.ravel())
    return load


def _bc(initial, nodes, fixed):
    return {int(i): (lambda now, i=int(i): initial[i]
                    +(.3+.07*nodes[i, 0]-.02*nodes[i, 1])*(now-TIMES[0])
                    +.11*(now-TIMES[0])**2) for i in fixed}


def _dense_be(mesh, initial, boundary, mass, stiffness, area, omit_old_fixed=False):
    fixed = np.array(sorted(boundary), dtype=int)
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    states = [initial.copy()]
    for now, h in zip(TIMES[1:], np.diff(TIMES)):
        system = mass/h+stiffness
        old = states[-1].copy()
        if omit_old_fixed:
            old[fixed] = 0.
        rhs = _load(mesh, area, now)+mass@old/h
        state = np.empty(mesh.num_nodes)
        state[fixed] = [boundary[int(i)](now) for i in fixed]
        if len(free):
            state[free] = np.linalg.solve(system[np.ix_(free, free)],
                rhs[free]-system[np.ix_(free, fixed)]@state[fixed])
        states.append(state)
    return np.array(states)


def _audit(mesh, initial, boundary):
    mass, stiffness, gradients, area, local_k = _operators(mesh)
    expected = _dense_be(mesh, initial, boundary, mass, stiffness, area)
    result = solve_transient_heat(mesh, conductivity=K, volumetric_heat_capacity=C,
        time_s=TIMES, initial_temperature_k=initial, dirichlet=boundary, heat_source=_q)
    np.testing.assert_array_equal(result.temperature_k[0], initial)
    np.testing.assert_array_equal(result.time_s, TIMES)
    np.testing.assert_allclose(result.temperature_k, expected, rtol=0, atol=1e-10)
    cells = mesh.triangles
    # Independent local differences remove only a constant in the gradient/K action.
    local_t = expected[:, cells]-expected[:, cells[:, :1]]
    flux = -K*np.einsum('tei,eid->ted', local_t, gradients)
    storage = np.diff(expected, axis=0)@mass.T/np.diff(TIMES)[:, None]
    loads = np.array([_load(mesh, area, now) for now in TIMES])
    spatial = np.zeros_like(storage)
    for frame in range(len(TIMES)-1):
        local = np.einsum('eij,ej->ei', local_k, local_t[frame+1])
        np.add.at(spatial[frame], cells.ravel(), local.ravel())
    residual = storage+spatial-loads[1:]
    fixed = np.array(sorted(boundary), dtype=int)
    reaction = np.zeros_like(residual); reaction[:, fixed] = residual[:, fixed]
    scale = max(1., float(np.max(np.sum(abs(storage)+abs(loads[1:])+abs(reaction), axis=1))))
    for actual, truth in ((result.source_load_w_per_m, loads),
                          (result.storage_rate_w_per_m, storage),
                          (result.residual_w_per_m, residual),
                          (result.reaction_w_per_m, reaction)):
        np.testing.assert_allclose(actual, truth, rtol=0, atol=1e-10*scale)
    np.testing.assert_allclose(result.heat_flux_w_m2, flux, rtol=0, atol=1e-10*max(1., float(np.max(abs(flux)))))
    heat = expected@mass.sum(axis=1)
    quadratic = .5*np.einsum('ti,ij,tj->t', expected, mass, expected)
    np.testing.assert_allclose(result.heat_content_j_per_m, heat, rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.quadratic_functional_jk_per_m, quadratic, rtol=0, atol=1e-10)
    np.testing.assert_array_equal(result.dirichlet_node_ids, fixed)
    np.testing.assert_allclose(result.dirichlet_temperatures_k, expected[:, fixed], rtol=0, atol=1e-10)
    return result, expected, (mass, stiffness, area)


def test_nonuniform_partial_moving_dirichlet_preserves_both_mass_terms():
    mesh = _skewed(.7, .4, 3, 2)
    x, y = mesh.nodes.T
    initial = 17.+.4*x/.7+.2*y/.4+.1*np.sin(np.pi*x/.7)*np.sin(np.pi*y/.4)
    boundary = _bc(initial, mesh.nodes, mesh.boundary['left'])
    _, expected, (mass, stiffness, area) = _audit(mesh, initial, boundary)
    wrong = _dense_be(mesh, initial, boundary, mass, stiffness, area, omit_old_fixed=True)
    # Verify this fixture distinguishes dropping the old M_FC term.
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(wrong, expected, rtol=0, atol=1e-10)


def test_all_fixed_nonuniform_history_has_original_reactions():
    mesh = rectangle_mesh(.7, .4, 1, 1)
    initial = np.array([17., 17.4, 16.8, 17.1])
    boundary = _bc(initial, mesh.nodes, np.arange(mesh.num_nodes))
    _audit(mesh, initial, boundary)


@pytest.mark.parametrize('anchoring', ['none', 'first', 'both'])
@pytest.mark.parametrize('reorder', [False, True])
def test_disconnected_nonuniform_components_with_mixed_anchors(anchoring, reorder):
    first = _skewed(.7, .4, 3, 2)
    second = _skewed(.2, .5, 2, 3)
    second.nodes += [1., 0.]
    offset = first.num_nodes
    nodes = np.concatenate((first.nodes, second.nodes))
    cells = np.concatenate((first.triangles, second.triangles+offset))
    fixed = []
    if anchoring in ('first', 'both'):
        fixed.extend(first.boundary['left'])
    if anchoring == 'both':
        fixed.extend(second.boundary['left']+offset)
    fixed = np.asarray(fixed, dtype=int)
    initial = np.where(np.arange(len(nodes)) < offset, 17., -37.) + .4*nodes[:, 0]-.2*nodes[:, 1]
    initial += .13*np.sin(3*nodes[:, 0]+nodes[:, 1])
    if reorder:
        permutation = np.arange(len(nodes))[::-1]
        reverse = np.argsort(permutation)
        nodes, initial = nodes[permutation], initial[permutation]
        cells, fixed = reverse[cells], reverse[fixed]
    mesh = Mesh(nodes, cells, {})
    boundary = _bc(initial, mesh.nodes, fixed)
    _audit(mesh, initial, boundary)
