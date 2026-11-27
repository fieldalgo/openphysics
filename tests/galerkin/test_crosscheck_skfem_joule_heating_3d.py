# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A partial electrode produces nonuniform Joule heat in a convection-cooled bar."""
import numpy as np

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin import Mesh3D, box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.thermal3d import solve_steady_heat_3d


def test_partial_electrode_and_cooled_end_against_skfem():
    sk = require_tool("scikit-fem")
    from skfem.models.poisson import laplace, mass, unit_load

    grid = box_mesh(0.02, 0.01, 0.01, 8, 4, 4)
    tags = dict(grid.tagged_faces)
    end = tags.pop("x1")
    on_contact = grid.nodes[end].mean(axis=1)[:, 1] < 0.005
    tags.update(contact=end[on_contact], bare=end[~on_contact])
    mesh = Mesh3D(grid.nodes, grid.tets, tagged_faces=tags)
    sigma, k, h, ambient = 2.0, 3.0, 100.0, 300.0
    clock = Stopwatch()
    with clock("openphysics"):
        electric = solve_steady_electric_3d(
            mesh, electrical_conductivity=sigma, prescribed_electric_potential={"x0": 2., "contact": 0.},
        )
        heat = solve_steady_heat_3d(
            mesh, thermal_conductivity=k, prescribed_temperature={},
            convection={"contact": (h, ambient), "bare": (h, ambient)},
            heat_source_density=electric.joule_power_density,
        )

    with clock("reference"):
        refmesh = sk.MeshTet(mesh.nodes.T, mesh.tets.T, sort_t=False)
        basis = sk.Basis(refmesh, sk.ElementTetP1())
        stiffness = sk.asm(laplace, basis)
        left = basis.get_dofs(lambda x: np.isclose(x[0], 0.)).all()
        contact = basis.get_dofs(lambda x: np.isclose(x[0], 0.02) & (x[1] < 0.005)).all()
        values = np.zeros(basis.N)
        values[left] = 2.
        voltage = sk.solve(*sk.condense(sigma * stiffness, np.zeros(basis.N),
                                        x=values, D=np.union1d(left, contact)))
        terminal_power = 2. * (sigma * stiffness @ voltage)[left].sum()
        gradient = basis.interpolate(voltage).grad[:, :, 0]
        source = sigma * np.sum(gradient ** 2, axis=0)

        @sk.LinearForm
        def body_source(v, w):
            return w.source * v

        cooled = refmesh.facets_satisfying(lambda x: np.isclose(x[0], 0.02))
        surface = sk.FacetBasis(refmesh, sk.ElementTetP1(), facets=cooled)
        load = sk.asm(body_source, basis, source=source[:, None])
        rise = sk.solve(k * stiffness + h * sk.asm(mass, surface), load)
        cooling_power = h * sk.asm(unit_load, surface) @ rise

    assert source.max() > 10 * source.min() > 0
    emit(make_record(
        case="steady-joule-heat3d-partial-electrode", physics="3D DC and steady conduction",
        api="galerkin.electric3d and galerkin.thermal3d", discretization="P1 tetrahedra",
        tool="scikit-fem", tool_discretization="ElementTetP1", stopwatch=clock,
        matched=["same SI mesh and materials", "electrodes and cooling face chosen independently",
                 "independent assembly of both fields, electric power, heat loading and cooling"],
        not_matched=[], analytical_acceptance="tests/galerkin/test_joule_heating_3d_coupling.py",
        observables=[observable(name, unit, "global relative difference",
                                relative_difference(actual, reference), 1e-9)
                     for name, unit, actual, reference in [
                         ("potential", "V", electric.electric_potential, voltage),
                         ("local Joule heat", "W/m^3", electric.joule_power_density, source),
                         ("temperature rise", "K", heat.temperature - ambient, rise),
                         ("terminal power", "W", electric.inward_electric_power, terminal_power),
                         ("volumetric heating", "W", heat.generated_heat_rate.sum(), load.sum()),
                         ("convection", "W", heat.outward_convective_heat_rate.sum(), cooling_power),
                     ]],
    ))
