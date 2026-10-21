# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent electrical and thermal weak forms, joined by reference P1 Q."""
import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.electric import solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.mesh import layered_rectangle_mesh


@pytest.mark.parametrize('case', ['voltage', 'current'])
def test_actual_joule_pipeline_against_independent_skfem(case):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    mesh = layered_rectangle_mesh([.01, .03], .01, [4, 8], 4, ['a', 'b'])
    sigma, k = {'a': 2., 'b': 8.}, {'a': 3., 'b': 7.}
    left, right = mesh.boundary['left'], mesh.boundary['right']
    bc = {int(i): 1.+2000*mesh.nodes[i, 1]**2 for i in left}
    if case == 'voltage':
        bc.update({int(i): 0. for i in right})
    clock = Stopwatch()
    with clock('openphysics'):
        electric = solve_steady_electric(mesh, conductivity=sigma, dirichlet=bc,
                                         outward_current={'right': 100.} if case == 'current' else None)
        ours = solve_steady_joule_heat(mesh, electrical_result=electric, conductivity=k,
                                       dirichlet={int(i): 300. for i in left},
                                       outward_flux={'top': 20.}, convection={'right': (100., 300.)})
    with clock('reference'):
        m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
        basis = sk.Basis(m, sk.ElementTriP1())
        centers = m.p[:, m.t].mean(axis=1)
        sig = np.where(centers[0] < .01, 2., 8.)
        thermal_k = np.where(centers[0] < .01, 3., 7.)
        def field(values):
            return np.repeat(values[:, None], basis.X.shape[1], axis=1)
        @sk.BilinearForm
        def diffusion(u, v, w):
            return w.coefficient*dot(grad(u), grad(v))
        @sk.LinearForm
        def source(v, w):
            return w.q*v
        @sk.LinearForm
        def unit_boundary(v, w):
            return v
        @sk.BilinearForm
        def robin(u, v, w):
            return 100.*u*v
        right_basis = sk.FacetBasis(m, sk.ElementTriP1(),
                                    facets=m.facets_satisfying(lambda p: np.isclose(p[0], .03)))
        top_basis = sk.FacetBasis(m, sk.ElementTriP1(),
                                  facets=m.facets_satisfying(lambda p: np.isclose(p[1], .01)))
        A = diffusion.assemble(basis, coefficient=field(sig))
        electric_rhs = -100.*unit_boundary.assemble(right_basis) if case == 'current' else np.zeros(basis.N)
        fixed = left if case == 'current' else np.concatenate([left, right])
        prescribed = np.zeros(basis.N); prescribed[left] = 1.+2000*m.p[1, left]**2
        potential = sk.solve(*sk.condense(A, electric_rhs, x=prescribed, D=fixed))
        E = -basis.interpolate(potential).grad[:, :, 0].T
        Q = sig*np.sum(E*E, axis=1)
        load = source.assemble(basis, q=field(Q))
        K = diffusion.assemble(basis, coefficient=field(thermal_k))
        H = robin.assemble(right_basis)
        outward = 20.*unit_boundary.assemble(top_basis)
        rise = sk.solve(*sk.condense(K+H, load-outward, D=left))
        flux = -thermal_k[:, None]*basis.interpolate(rise).grad[:, :, 0].T
        reference_power = float(np.sum(Q[:, None]*basis.dx))
    emit(make_record(case='steady-joule-'+case, physics='one-way 2D DC electric to steady heat',
                     api='galerkin.joule_heating.solve_steady_joule_heat', discretization='P1 triangles',
                     tool='scikit-fem', tool_discretization='ElementTriP1 and facet forms',
                     matched=['SI coordinates and cell order, two material regions',
                              'independently assembled electrical field and element Joule source',
                              'fixed left temperature, right convection, top outward heat flux',
                              'same voltage/current data, no implicit thickness'],
                     not_matched=[], stopwatch=clock,
                     analytical_acceptance='tests/galerkin/test_joule_heating.py',
                     observables=[observable(name, unit, 'max relative difference', relative_difference(a, b), 1e-9)
                                  for name, unit, a, b in [
                                      ('Joule source', 'W/m^3', electric.joule_heating, Q),
                                      ('nodal heat load', 'W/m', ours.thermal.load, load),
                                      ('temperature rise', 'K', ours.thermal.temperature-300., rise),
                                      ('heat flux', 'W/m^2', ours.thermal.heat_flux, flux),
                                      ('power', 'W/m', ours.source_power_per_length, reference_power)]]))
