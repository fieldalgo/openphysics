# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent vector P1 assembly for a clamped body under volume and surface loads."""
import numpy as np

from crosscheck import require_tool
from galerkin.elasticity3d import solve_elasticity_3d
from galerkin.mesh3d import box_mesh


def test_elasticity_3d_against_skfem():
    sk = require_tool("scikit-fem")
    from skfem.helpers import dot
    from skfem.models.elasticity import linear_elasticity

    mesh = box_mesh(1., .6, .4, 4, 3, 2)
    body = (1., -2., 3.)
    surface = (2., 1., -1.)
    held = {(n, a): 0. for n in mesh.boundary["x0"] for a in range(3)}
    ours = solve_elasticity_3d(mesh, youngs_modulus=100., poisson_ratio=.25,
                               prescribed_displacement=held, body_force_density=body,
                               traction={"x1": surface})
    reference_mesh = sk.MeshTet(mesh.nodes.T.copy(), mesh.tets.T.copy(), sort_t=False)
    element = sk.ElementVector(sk.ElementTetP1())
    basis = sk.Basis(reference_mesh, element)
    facets = reference_mesh.facets_satisfying(lambda x: np.isclose(x[0], 1.))
    face_basis = sk.FacetBasis(reference_mesh, element, facets=facets)

    @sk.LinearForm
    def body_load(v, w):
        return dot(np.asarray(body)[:, None, None], v)

    @sk.LinearForm
    def surface_load(v, w):
        return dot(np.asarray(surface)[:, None, None], v)

    matrix = linear_elasticity(40., 40.).assemble(basis)
    load = body_load.assemble(basis) + surface_load.assemble(face_basis)
    fixed_dofs = basis.nodal_dofs[:, mesh.boundary["x0"]].ravel()
    displacement = sk.solve(*sk.condense(matrix, load, D=fixed_dofs))
    gradient = basis.interpolate(displacement).grad[:, :, :, 0].transpose(2, 0, 1)
    strain = (gradient + gradient.swapaxes(1, 2)) / 2
    stress = 80 * strain + 40 * np.trace(strain, axis1=1, axis2=2)[:, None, None] * np.eye(3)
    residual = matrix @ displacement - load
    reaction = np.zeros_like(residual)
    reaction[fixed_dofs] = residual[fixed_dofs]
    np.testing.assert_allclose(ours.displacement, displacement[basis.nodal_dofs].T, atol=1e-13)
    np.testing.assert_allclose(ours.stress, stress, atol=1e-11)
    np.testing.assert_allclose(ours.reaction_force, reaction[basis.nodal_dofs].T, atol=1e-12)
