# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent scikit-fem forms/assembly/solve, matched mesh and boundary data."""
import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.electric import solve_steady_electric
from galerkin.mesh import layered_rectangle_mesh


@pytest.mark.parametrize('case', ['voltage', 'mixed', 'neumann'])
def test_electric_same_mesh_independent_forms(case):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad

    mesh = layered_rectangle_mesh([.4, 1.], 1., [4, 6], 8, ['a', 'b'])
    pure = case == 'neumann'
    sigma = 3. if pure else {'a': 2., 'b': 7.}
    bc = {} if pure else {int(i): 1.+mesh.nodes[i, 1]**2 for i in mesh.boundary['left']}
    if case == 'voltage':
        bc |= {int(i): 0. for i in mesh.boundary['right']}
    def normal_current(p, normals):
        # harmonic V=x²-y², J=(-6x,6y); all-edge Neumann quadrature is exact.
        return -6*p[:, 0]*normals[:, 0]+6*p[:, 1]*normals[:, 1]
    imposed = ({tag: normal_current for tag in mesh.boundary_edges} if pure else
               {'right': lambda p, n: 1.+p[:, 1]} if case == 'mixed' else None)
    clock = Stopwatch()
    with clock('openphysics'):
        ours = solve_steady_electric(mesh, conductivity=sigma, dirichlet=bc,
                                     outward_current=imposed,
                                     reference_potential={0: 0.} if pure else None)
    with clock('reference'):
        m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
        basis = sk.Basis(m, sk.ElementTriP1())
        centers = m.p[:, m.t].mean(axis=1)
        sig = np.full(mesh.num_triangles, 3.) if pure else np.where(centers[0] < .4, 2., 7.)
        @sk.BilinearForm
        def stiffness(u, v, w):
            return w.sigma*dot(grad(u), grad(v))
        K = stiffness.assemble(basis, sigma=np.repeat(sig[:, None], basis.X.shape[1], axis=1))
        G = np.zeros(basis.N)
        if case != 'voltage':
            facets = m.boundary_facets() if pure else m.facets_satisfying(lambda x: np.isclose(x[0], 1.))
            facet_basis = sk.FacetBasis(m, sk.ElementTriP1(), facets=facets, intorder=7)
            @sk.LinearForm
            def current(v, w):
                g = (-6*w.x[0]*w.n[0]+6*w.x[1]*w.n[1]) if pure else 1.+w.x[1]
                return g*v
            G = current.assemble(facet_basis)
        fixed = np.array([0]) if pure else np.where(np.isclose(m.p[0], 0.) |
                      ((case == 'voltage') & np.isclose(m.p[0], 1.)))[0]
        values = np.zeros(basis.N)
        if not pure:
            left = np.where(np.isclose(m.p[0], 0.))[0]
            values[left] = 1.+m.p[1, left]**2
        potential = sk.solve(*sk.condense(K, -G, x=values, D=fixed))
        E = -basis.interpolate(potential).grad[:, :, 0].T
        J = sig[:, None]*E
        Q = np.sum(J*E, axis=1)
        @sk.LinearForm
        def heating(v, w):
            return w.q*v
        heat_load = heating.assemble(basis, q=np.repeat(Q[:, None], basis.X.shape[1], axis=1))
        reaction = np.zeros(basis.N)
        if not pure:
            reaction[fixed] = (K@potential+G)[fixed]
        power = float(np.sum(basis.dx*Q[:, None]))
    obs = [observable(name, unit, 'max relative difference', relative_difference(a, b), 1e-10)
           for name, unit, a, b in [('potential', 'V', ours.potential, potential),
                                    ('electric field', 'V/m', ours.electric_field, E),
                                    ('current density', 'A/m^2', ours.current_density, J),
                                    ('Joule heating', 'W/m^3', ours.joule_heating, Q),
                                    ('heat load', 'W/m', ours.joule_load, heat_load),
                                    ('power', 'W/m', ours.joule_power_per_length, power)]]
    if not pure:
        obs.append(observable('electrode reaction', 'A/m', 'max relative difference',
                              relative_difference(ours.reaction, reaction), 1e-10))
    emit(make_record(case='electric-p1-'+case, physics='2D steady electric conduction',
                     api='galerkin.electric.solve_steady_electric', discretization='P1 triangles',
                     tool='scikit-fem', tool_discretization='ElementTriP1, FacetBasis order 7',
                     matched=['same mesh coordinates/connectivity; independent forms and boundary assembly',
                              'SI units, region conductivities, voltage/current functions, gauge',
                              'elementwise Joule heating and consistent load'],
                     not_matched=[], observables=obs, stopwatch=clock,
                     analytical_acceptance='tests/galerkin/test_electric_steady2d.py'))
