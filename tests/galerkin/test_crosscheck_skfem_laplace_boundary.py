# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent P2 volume reference; different discretizations, report only."""
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.laplace_boundary import solve_grounded_rectangle
from meshine import Domain, rectangle, generate


@pytest.mark.parametrize('size', [.08, .04, .02])
def test_boundary_against_independent_quadratic_volume(size):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad

    width, height, radius, center = 2.4, 1., .1, np.array([1.2, .35])
    theta = np.arange(64)*2*np.pi/64
    polygon = center + radius*np.column_stack((np.cos(theta), np.sin(theta)))
    domain = Domain(size=size)
    domain.add_region('vacuum', rectangle(0., 0., width, height), holes=[polygon])
    mesh = generate(domain, smooth=0, candidate_order='stable')
    clock = Stopwatch()
    with clock('openphysics'):
        ours = solve_grounded_rectangle([polygon], width=width, height=height, panels_per_edge=2)
    with clock('reference'):
        m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
        element = sk.ElementTriP2()
        basis = sk.Basis(m, element)
        facets = m.boundary_facets()
        midpoints = m.p[:, m.facets[:, facets]].mean(axis=1).T
        signal = facets[np.linalg.norm(midpoints-center, axis=1) < 1.1*radius]
        ground = facets[midpoints[:, 1] == 0.]
        assert len(signal) >= 64 and len(ground) > 0
        groups = [basis.get_dofs(facets=f).all() for f in [signal, ground]]
        fixed = np.unique(np.concatenate(groups))
        @sk.BilinearForm
        def laplace(u, v, w):
            return dot(grad(u), grad(v))
        @sk.BilinearForm
        def boundary_mass(u, v, w):
            return u*v
        stiffness = laplace.assemble(basis)
        voltage = np.zeros(basis.N)
        voltage[groups[0]] = 1.
        voltage = sk.solve(*sk.condense(stiffness, np.zeros(basis.N), x=voltage, D=fixed))
        capacitance = float(voltage @ (stiffness @ voltage))
        reaction = stiffness @ voltage / capacitance
        parts = []
        for facets, nodes in zip([signal, ground], groups):
            fb = sk.FacetBasis(m, element, facets=facets, intorder=4)
            mass = boundary_mass.assemble(fb)[nodes][:, nodes]
            weights = np.asarray(mass.sum(axis=1)).ravel()
            assert np.all(weights > 0)
            parts.append(float(np.sum(reaction[nodes]**2/weights)))
        np.testing.assert_allclose([reaction[g].sum() for g in groups], [1., -1.], atol=1e-10, rtol=0)
    observations = [observable('capacitance / permittivity', '1', 'relative difference',
                               relative_difference(ours.capacitance_per_permittivity, [[capacitance]]))]
    observations += [observable(name, '1/m', 'relative difference', relative_difference(ours.current_gram[i, 0, 0], value))
                     for i, (name, value) in enumerate(zip(['signal current Gram', 'ground current Gram'], parts))]
    emit(make_record(case=f'grounded-rectangle-boundary-p2-{size}', physics='2D homogeneous Laplace boundary',
                     api='galerkin.laplace_boundary.solve_grounded_rectangle', discretization='constant Galerkin boundary panels',
                     tool='scikit-fem', tool_discretization='ElementTriP2, independently assembled volume and boundary mass',
                     matched=['same 64-vertex conductor polygon and rectangle; homogeneous permittivity divided out',
                              'grounded bottom, zero side/top flux, unit signal potential', 'current integral normalization'],
                     not_matched=['boundary panel vs quadratic volume discretization; report-only'],
                     observables=observations, stopwatch=clock,
                     analytical_acceptance='tests/galerkin/test_laplace_boundary.py'))
