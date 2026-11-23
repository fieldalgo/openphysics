# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Conductors closer to the side/top walls than their extent: wall-scaled boxes."""
import numpy as np
import pytest
from crosscheck import require_tool
import galerkin.laplace_boundary as module
from galerkin import _laplace_panels as kernel
from galerkin.laplace_boundary import solve_grounded_rectangle as solve
from meshine import Domain, rectangle, generate

WIDTH, HEIGHT = 2.4, 1.


def strip(x0, x1, y0=.3, y1=.34):
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def near_wall():
    """A 1.2-wide strip 0.15 from the right wall (clearance/extent 0.125)."""
    return [strip(1.05, 2.25)]


def test_near_wall_cluster_uses_wall_scaled_boxes():
    result = solve(near_wall(), width=WIDTH, height=HEIGHT, panels_per_edge=32, interpolation_degree=14)
    assert result.smooth_interpolation_boxes > 1 and result.matrix_refinement_error <= 1e-10
    polygons, unit, w, h, clear = module._admit(near_wall(), WIDTH, HEIGHT, 32)
    assert not clear
    a, b, owners = kernel.panels(polygons, 32, 'cubic')
    labels = kernel.wall_labels(a, b, owners, w, h, bottom=False)
    assert labels.max() + 1 == result.smooth_interpolation_boxes
    mids = (a + b) / 2
    for label in np.unique(labels):
        group = labels == label
        points = np.concatenate((a[owners == owners[group][0]], b[owners == owners[group][0]]))
        lower, upper = points.min(axis=0), points.max(axis=0)
        assert np.ptp(mids[group, 0]) <= kernel.wall_distance(lower, upper, w, h, bottom=False)
    finer = solve(near_wall(), width=WIDTH, height=HEIGHT, panels_per_edge=64, interpolation_degree=16)
    c = result.capacitance_per_permittivity
    assert abs(finer.capacitance_per_permittivity[0, 0] / c[0, 0] - 1) < 1e-5


def test_near_wall_capacitance_against_independent_quadratic_volume():
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    ours = solve(near_wall(), width=WIDTH, height=HEIGHT, panels_per_edge=64,
                 interpolation_degree=14).capacitance_per_permittivity[0, 0]
    polygon = near_wall()[0]
    errors = []
    for size in (.04, .02, .01):
        domain = Domain(size=size)
        domain.add_region('vacuum', rectangle(0., 0., WIDTH, HEIGHT), holes=[polygon])
        mesh = generate(domain, smooth=0, candidate_order='stable')
        m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
        basis = sk.Basis(m, sk.ElementTriP2())
        facets = m.boundary_facets()
        mid = m.p[:, m.facets[:, facets]].mean(axis=1).T
        inside = ((mid[:, 0] > polygon[0, 0] - 1e-9) & (mid[:, 0] < polygon[1, 0] + 1e-9)
                  & (mid[:, 1] > polygon[0, 1] - 1e-9) & (mid[:, 1] < polygon[2, 1] + 1e-9))
        signal, ground = facets[inside], facets[mid[:, 1] == 0.]
        dofs = [basis.get_dofs(facets=f).all() for f in (signal, ground)]

        @sk.BilinearForm
        def laplace(u, v, w):
            return dot(grad(u), grad(v))
        K = laplace.assemble(basis)
        x = np.zeros(basis.N)
        x[dofs[0]] = 1.
        x = sk.solve(*sk.condense(K, np.zeros(basis.N), x=x, D=np.unique(np.concatenate(dofs))))
        errors.append(abs(float(x @ (K @ x)) / ours - 1))
    assert errors[-1] < errors[0] and errors[-1] < 1e-3, errors


def test_clear_cluster_never_builds_wall_boxes(monkeypatch):
    monkeypatch.setattr(kernel, 'wall_labels', lambda *a, **k: pytest.fail('wall boxes built'))
    result = solve([strip(1.0, 1.4)], width=WIDTH, height=HEIGHT, panels_per_edge=16)
    assert result.smooth_interpolation_boxes == 1


def test_conductor_too_close_for_the_box_limit_is_refused_before_field_solve(monkeypatch):
    monkeypatch.setattr(module.kernel, 'panels', lambda *a, **k: pytest.fail('field solve reached'))
    with pytest.raises(ValueError, match='too close to the side/top walls'):
        solve([strip(1.0, WIDTH - 1e-3)], width=WIDTH, height=HEIGHT, panels_per_edge=16)
