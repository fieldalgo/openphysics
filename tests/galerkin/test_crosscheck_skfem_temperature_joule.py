# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Separate P1 assembly and iteration; no production assembly or solve helpers."""
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.mesh import layered_rectangle_mesh
from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat


@pytest.mark.parametrize('case', ['voltage', 'current'])
def test_temperature_coupling_against_skfem(case):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    mesh = layered_rectangle_mesh([.4, 1.], .3, [4, 6], 3, ['a', 'b'])
    left, right = mesh.boundary['left'], mesh.boundary['right']
    voltage = {int(i): 0. for i in left}
    if case == 'voltage':
        voltage.update({int(i): 1. for i in right})
    models = {name: ConductivityModel(lambda t, s=s: s/(1+.7*(t-300)), (290., 400.))
              for name, s in [('a', 1.), ('b', 2.)]}
    clock = Stopwatch()
    with clock('openphysics'):
        result = solve_temperature_joule_heat(mesh, electrical_conductivity=models,
            thermal_conductivity={'a': 1., 'b': 3.}, electric_dirichlet=voltage,
            thermal_dirichlet={int(i): 300. for i in left}, initial_temperature=300.,
            outward_current={'right': 1.} if case == 'current' else None,
            convection={'right': (2., 300.)}, relaxation=.7,
            relative_tolerance=1e-12, temperature_atol=1e-11, max_iterations=300)
    with clock('reference'):
        m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
        basis = sk.Basis(m, sk.ElementTriP1())
        centers = m.p[:, m.t].mean(axis=1)
        base = np.where(centers[0] < .4, 1., 2.)
        k = np.where(centers[0] < .4, 1., 3.)
        field = lambda a: np.repeat(a[:, None], basis.X.shape[1], axis=1)
        @sk.BilinearForm
        def diffusion(u, v, w):
            return w.coefficient*dot(grad(u), grad(v))
        @sk.LinearForm
        def source(v, w):
            return w.q*v
        @sk.LinearForm
        def boundary(v, w):
            return v
        @sk.BilinearForm
        def robin(u, v, w):
            return 2*u*v
        fb = sk.FacetBasis(m, sk.ElementTriP1(), facets=m.facets_satisfying(lambda p: np.isclose(p[0], 1.)))
        K = diffusion.assemble(basis, coefficient=field(k))+robin.assemble(fb)
        rhs_e = -boundary.assemble(fb) if case == 'current' else np.zeros(basis.N)
        fixed = left if case == 'current' else np.r_[left, right]
        bc = np.zeros(basis.N)
        if case == 'voltage':
            bc[right] = 1.
        rise = np.zeros(basis.N)
        for _ in range(500):
            sigma = base/(1+.7*rise[m.t].mean(axis=0))
            A = diffusion.assemble(basis, coefficient=field(sigma))
            potential = sk.solve(*sk.condense(A, rhs_e, x=bc, D=fixed))
            E = -basis.interpolate(potential).grad[:, :, 0].T
            q = sigma*np.sum(E**2, axis=1)
            load = source.assemble(basis, q=field(q))
            next_rise = sk.solve(*sk.condense(K, load, D=left))
            if np.max(abs(next_rise-rise)) < 1e-13:
                break
            rise = .4*rise+.6*next_rise
        else:
            raise AssertionError('independent iteration did not converge')
        current = sigma[:, None]*E
        power = np.sum(q[:, None]*basis.dx)
    e, h = result.coupled.electrical, result.coupled.thermal
    emit(make_record(case='temperature-joule-'+case, physics='two-way steady 2D electrothermal',
        api='galerkin.temperature_joule_heating.solve_temperature_joule_heat',
        discretization='P1 cell-mean temperature conductivity', tool='scikit-fem',
        tool_discretization='independent P1 and facet forms; independently relaxed iteration',
        matched=['two materials, SI, fixed mesh', 'voltage/current and Robin heat boundary',
                 'cell-mean rho(T), fixed k, Joule heat'], not_matched=[], stopwatch=clock,
        analytical_acceptance='tests/galerkin/test_temperature_joule_heating.py',
        observables=[observable(name, unit, 'max relative difference', relative_difference(a,b), 1e-9)
            for name, unit, a, b in [('potential','V',e.potential,potential),
                ('current','A/m^2',e.current_density,current), ('source','W/m^3',e.joule_heating,q),
                ('temperature rise','K',h.temperature-300,next_rise),
                ('power','W/m',result.coupled.source_power_per_length,power)]]))
