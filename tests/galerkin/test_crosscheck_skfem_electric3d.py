# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent tetrahedral P1 reference with a nonuniform transverse interface."""

import numpy as np

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin import Mesh3D, box_mesh
from galerkin.electric3d import solve_steady_electric_3d


def test_steady_electric_3d_against_skfem():
    sk = require_tool("scikit-fem")
    from skfem.helpers import dot, grad

    box = box_mesh(1., .6, .4, 4, 3, 2)
    cells = box.tets[::-1].copy()
    centers = box.nodes[cells].mean(axis=1)
    high = (centers[:, 0] >= .5) ^ (centers[:, 1] >= .2)
    mesh = Mesh3D(box.nodes, cells, regions=high.astype(int), region_names=["low", "high"],
                  tagged_faces=box.tagged_faces)
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_steady_electric_3d(
            mesh, electrical_conductivity={"low": 2., "high": 9.},
            prescribed_electric_potential={"x0": 5., "x1": 0.},
        )
    with clock("reference"):
        refmesh = sk.MeshTet(box.nodes.T.copy(), cells.T.copy())
        basis = sk.Basis(refmesh, sk.ElementTetP1())
        centers = refmesh.p[:, refmesh.t].mean(axis=1)
        sigma = np.where((centers[0] >= .5) ^ (centers[1] >= .2), 9., 2.)

        @sk.BilinearForm
        def diffusion(u, v, w):
            return w.sigma * dot(grad(u), grad(v))

        matrix = diffusion.assemble(basis, sigma=np.broadcast_to(sigma[:, None], basis.dx.shape))
        left = basis.get_dofs(lambda x: np.isclose(x[0], 0.)).all()
        right = basis.get_dofs(lambda x: np.isclose(x[0], 1.)).all()
        volts = np.zeros(basis.N)
        volts[left] = 5.
        potential = sk.solve(*sk.condense(matrix, np.zeros(basis.N), x=volts, D=np.r_[left, right]))
        electric = -basis.interpolate(potential).grad[:, :, 0].T
        density = sigma[:, None] * electric
        heat = np.sum(density * electric, axis=1)
        power = np.sum(heat[:, None] * basis.dx)
        reaction = matrix @ potential
        current = [reaction[left].sum(), reaction[right].sum()]
        supplied = 5. * current[0]

    # Ensure this case exercises a nonzero transverse field as well as the axial field.
    assert np.max(abs(electric[:, 1:])) > .1
    emit(make_record(
        case="steady-electric3d-checkerboard",
        physics="3D isotropic DC conduction",
        api="galerkin.electric3d.solve_steady_electric_3d",
        discretization="P1 tetrahedra",
        tool="scikit-fem",
        tool_discretization="ElementTetP1",
        matched=["same SI nodes and tetrahedra",
                 "reference conductivity and terminals selected independently from coordinates",
                 "independent weak form, elimination, gradients, reactions and quadrature"],
        not_matched=[], stopwatch=clock,
        analytical_acceptance="tests/galerkin/test_electric_steady3d.py",
        observables=[observable(name, unit, "max relative difference",
                                relative_difference(actual, expected), 1e-10)
                     for name, unit, actual, expected in [
                         ("potential", "V", ours.electric_potential, potential),
                         ("electric field", "V/m", ours.electric_field, electric),
                         ("current density", "A/m^2", ours.current_density, density),
                         ("Joule density", "W/m^3", ours.joule_power_density, heat),
                         ("Joule power", "W", ours.joule_power, power),
                         ("terminal power", "W", ours.inward_electric_power, supplied),
                         ("terminal currents", "A", list(ours.inward_current.values()), current),
                     ]],
    ))
