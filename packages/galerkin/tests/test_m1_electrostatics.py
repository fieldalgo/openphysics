"""M1: electrostatics of a coaxial cable, graded against refsol.metallic."""

import numpy as np
import pytest

from galerkin import (annulus_mesh, assemble_stiffness, assemble_load,
                      solve_dirichlet, l2_error, element_gradient)
from conftest import assert_second_order

A, B = 1.0, 3.0


def solve(n_r, n_theta):
    mesh = annulus_mesh(A, B, n_r, n_theta)
    K = assemble_stiffness(mesh, eps=1.0)
    f = assemble_load(mesh, rho=0.0)
    V = solve_dirichlet(K, f, {tuple(mesh.boundary["inner"]): 1.0,
                               tuple(mesh.boundary["outer"]): 0.0})
    return mesh, V


def test_potential_converges_at_second_order(refsol):
    exact = lambda x, y: refsol.metallic.coax_potential(
        np.sqrt(x ** 2 + y ** 2), A, B)
    errors = []
    for n_r in (4, 8, 16, 32):
        mesh, V = solve(n_r, 6 * n_r)
        errors.append(l2_error(mesh, V, exact))
    assert_second_order(errors, name="coax potential")


def test_field_is_radial_with_the_right_magnitude(refsol):
    mesh, V = solve(32, 192)
    E = -element_gradient(mesh, V)
    centroid = mesh.nodes[mesh.triangles].mean(axis=1)
    r = np.linalg.norm(centroid, axis=1)
    rhat = centroid / r[:, None]

    radial = np.einsum("td,td->t", E, rhat) / np.linalg.norm(E, axis=1)
    assert radial.min() > 0.999, "field is not radial"

    exact = refsol.metallic.coax_field_magnitude(r, A, B)
    rel = np.abs(np.linalg.norm(E, axis=1) - exact) / exact
    assert rel.mean() < 0.01, f"mean |E| error {rel.mean():.3%}"
