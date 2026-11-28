# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare frequencies, mode shapes and equilibrium with independent vector P1 forms."""
import numpy as np
from scipy.linalg import eigh

from crosscheck import require_tool
from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.structural_modes3d import solve_structural_modes_3d


def test_clamped_two_material_modes_against_skfem():
    sk = require_tool("scikit-fem")
    from skfem.helpers import dot
    from skfem.models.elasticity import linear_elasticity

    block = box_mesh(1., .4, .25, 5, 3, 2)
    region = (block.nodes[block.tets, 0].mean(axis=1) > .4).astype(int)
    mesh = Mesh3D(block.nodes, block.tets, regions=region, region_names=["base", "tip"],
                  tagged_faces=block.tagged_faces)
    young, poisson, density = (120., 50.), (.24, .31), (3., 8.)
    fixed = {(n, a): 0. for n in mesh.boundary["x0"] for a in range(3)}
    ours = solve_structural_modes_3d(mesh, youngs_modulus=dict(zip(mesh.region_names, young)),
                                     poisson_ratio=dict(zip(mesh.region_names, poisson)),
                                     mass_density=dict(zip(mesh.region_names, density)),
                                     prescribed_displacement=fixed, mode_count=5)
    ref = sk.MeshTet(mesh.nodes.T.copy(), mesh.tets.T.copy(), sort_t=False)
    basis = sk.Basis(ref, sk.ElementVector(sk.ElementTetP1()))

    @sk.BilinearForm
    def vector_mass(u, v, w):
        return dot(u, v)

    stiffness_parts, mass_parts = [], []
    for i, (e, nu, rho) in enumerate(zip(young, poisson, density)):
        sub = basis.with_elements(np.flatnonzero(region == i))
        mu = e / (2 * (1 + nu))
        lam = e * nu / ((1 + nu) * (1 - 2*nu))
        stiffness_parts.append(linear_elasticity(lam, mu).assemble(sub))
        mass_parts.append(rho * vector_mass.assemble(sub))
    free = np.setdiff1d(np.arange(basis.N), basis.nodal_dofs[:, mesh.boundary["x0"]])
    k = sum(stiffness_parts)[free][:, free].toarray()
    m = sum(mass_parts)[free][:, free].toarray()
    values, reference = eigh(k, m, subset_by_index=(0, 4))
    modes = np.empty((basis.N, 5))
    modes[basis.nodal_dofs.T] = ours.mass_normalized_displacement.transpose(1, 2, 0)
    modes = modes[free]
    np.testing.assert_allclose(ours.frequency, np.sqrt(values)/(2*np.pi), rtol=1e-9)
    np.testing.assert_allclose(modes.T @ m @ modes, np.eye(5), atol=1e-10)
    np.testing.assert_allclose(np.abs(reference.T @ m @ modes), np.eye(5), atol=1e-8)
    elastic = k @ modes
    inertia = (m @ modes) * (2*np.pi*ours.frequency)**2
    assert np.all(np.linalg.norm(elastic-inertia, axis=0) / np.linalg.norm(inertia, axis=0) < 1e-8)
