# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare every temperature on unequal time steps with independent P1 assembly."""
import numpy as np
from scipy.sparse.linalg import spsolve

from crosscheck import require_tool
from galerkin import Mesh3D, box_mesh
from galerkin.transient_heat3d import solve_transient_heat_3d


def test_two_material_pulse_with_convection_against_scikit_fem():
    sk = require_tool("scikit-fem")
    from skfem.models.poisson import laplace, mass, unit_load

    grid = box_mesh(0.02, 0.012, 0.01, 4, 3, 2)
    centres = grid.nodes[grid.tets].mean(axis=1)
    other = centres[:, 0] >= 0.01
    mesh = Mesh3D(grid.nodes, grid.tets, regions=other.astype(int),
                  region_names=("core", "end"), tagged_faces=grid.tagged_faces)
    time = np.array([0, 0.25, 0.7, 2, 2.5, 5])
    switch = 2.0
    ambient = 300.0
    fixed = mesh.boundary["x0"]
    # A partial heater on the top of the first material gives a fully 3D field.
    heater = ~other & (centres[:, 1] > 0.006) & (centres[:, 2] > 0.005)
    source = 2e8 * heater
    heat = solve_transient_heat_3d(
        mesh, time=time, initial_temperature=np.full(mesh.num_nodes, ambient),
        thermal_conductivity={"core": 6.0, "end": 14.0},
        volumetric_heat_capacity={"core": 1.2e6, "end": 2.5e6},
        prescribed_temperature={int(i): ambient for i in fixed},
        convection={"x1": (1500.0, ambient)},
        heat_source_density=lambda t: source if t < switch else 0.0,
    )

    refmesh = sk.MeshTet(mesh.nodes.T.copy(), mesh.tets.T.copy(), sort_t=False)
    basis = sk.Basis(refmesh, sk.ElementTetP1())
    core = basis.with_elements(np.flatnonzero(~other))
    end = basis.with_elements(np.flatnonzero(other))
    right = refmesh.facets_satisfying(lambda p: np.isclose(p[0], 0.02))
    face = sk.FacetBasis(refmesh, sk.ElementTetP1(), facets=right)
    capacity = 1.2e6 * mass.assemble(core) + 2.5e6 * mass.assemble(end)
    stiffness = 6 * laplace.assemble(core) + 14 * laplace.assemble(end) + 1500 * mass.assemble(face)
    heater_load = 2e8 * unit_load.assemble(basis.with_elements(np.flatnonzero(heater)))
    free = basis.complement_dofs(basis.get_dofs(lambda p: np.isclose(p[0], 0.0)))
    rise = np.zeros((len(time), basis.N))
    for i, dt in enumerate(np.diff(time), start=1):
        system = capacity + dt * stiffness
        load = capacity @ rise[i-1]
        if time[i] <= switch:
            load += dt * heater_load
        rise[i, free] = spsolve(system[free][:, free], load[free])
    assert rise[3].max() > rise[-1].max() > 0
    np.testing.assert_allclose(heat.temperature - ambient, rise, rtol=2e-10, atol=1e-10)
