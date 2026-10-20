# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Lossy material and impedance-wall cavities, solved again with scikit-fem.

Both cases use the same mesh, lowest-order Nedelec element, coefficients and
boundary data as galerkin, so the discrete eigenvalues must agree to the 1e-9
same-discretization gate of docs/reference-comparisons.md. The analytical and
convergence acceptance stays in test_material_cavity.py and
test_cavity_wall_loss.py; agreement here is not convergence evidence.
"""

import numpy as np
import pytest
import scipy.linalg as la

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin import CavityMaterialRegion, solve_material_cavity_box

SAME = 1e-9
C0 = 299792458.0
MU0 = 1.25663706212e-6      # the value galerkin.material_cavity uses
ETA0 = MU0 * C0
WALL_AXES = {"x0": (0, 0), "x1": (0, 1), "y0": (1, 0), "y1": (1, 1), "z0": (2, 0), "z1": (2, 1)}


@pytest.fixture(scope="module")
def skfem():
    return require_tool("scikit-fem")


def _forms(skfem):
    from skfem.helpers import curl, dot

    @skfem.BilinearForm
    def curlcurl(u, v, w):
        return dot(curl(u), curl(v))

    @skfem.BilinearForm
    def mass(u, v, w):
        return dot(u, v)

    @skfem.BilinearForm
    def tangential_mass(u, v, w):
        n = w.n
        ut = u - dot(u, n) * n
        vt = v - dot(v, n) * n
        return dot(ut, vt)

    return curlcurl, mass, tangential_mass


def _material_matrices(skfem, mesh, eps, mu):
    """Sum per-material assemblies with complex 1/mu and eps (same tet assignment)."""
    curlcurl, mass, _ = _forms(skfem)
    element = skfem.ElementTetN0()
    full = skfem.Basis(mesh, element)
    stiffness = 0
    mass_matrix = 0
    for value in np.unique(mu):
        basis = skfem.Basis(mesh, element, elements=np.flatnonzero(mu == value))
        stiffness = stiffness + curlcurl.assemble(basis).astype(complex) / value
    for value in np.unique(eps):
        basis = skfem.Basis(mesh, element, elements=np.flatnonzero(eps == value))
        mass_matrix = mass_matrix + mass.assemble(basis).astype(complex) * value
    return full, stiffness.tocsr(), mass_matrix.tocsr()


def _wall_facets(mesh, wall):
    axis, side = WALL_AXES[wall]
    position = mesh.p[axis].max() if side else mesh.p[axis].min()
    return mesh.facets_satisfying(lambda x: np.isclose(x[axis], position, rtol=0, atol=1e-12))


def test_lossy_slab_cavity_same_mesh(skfem):
    lengths, cells = (1.0, 0.8, 0.6), (3, 2, 4)
    slab = CavityMaterialRegion(((0, 1), (0, 0.8), (0, 0.3)), 2.5 - 0.1j, 1.2 - 0.02j)
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_material_cavity_box(lengths, cells, regions=[slab], num_modes=6,
                                         target_frequency_hz=150e6)
    mesh = skfem.MeshTet(ours.mesh.nodes.T.copy(), ours.mesh.tets.T.copy())
    with clock("reference"):
        basis, stiffness, mass = _material_matrices(
            skfem, mesh, ours.tet_relative_permittivity, ours.tet_relative_permeability)
        free = basis.complement_dofs(basis.get_dofs().all())
        values = la.eigvals(stiffness[free][:, free].toarray(), mass[free][:, free].toarray())
    physical = values[np.abs(values) > 1e-6]
    target = (2 * np.pi * 150e6 / C0) ** 2
    nearest = physical[np.argsort(np.abs(physical - target))[:6]]
    reference = nearest[np.argsort(nearest.real)]
    emit(make_record(
        case="cavity-lossy-slab", stopwatch=clock,
        physics="3D PEC box 1 x 0.8 x 0.6 m with a lossy slab z <= 0.3 m "
                "(eps 2.5-0.1j, mu 1.2-0.02j), complex resonances",
        api="galerkin.material_cavity.solve_material_cavity_box",
        discretization="lowest-order Nedelec tetrahedra, complex coefficients per tetrahedron",
        tool="scikit-fem", tool_discretization="ElementTetN0, per-material assembly",
        analytical_acceptance="tests/galerkin/test_material_cavity.py (packages/galerkin/docs/material_cavity.md)",
        matched=["same nodes and tetrahedra (the returned SI mesh, 3 x 2 x 4 cells)",
                 "same per-tetrahedron eps_r and mu_r (galerkin's returned arrays)",
                 "PEC on all six walls", "curl-curl/mu and eps-mass forms",
                 "near-target selection of six modes"],
        not_matched=["eigensolver (galerkin dense or projected shift-invert ARPACK, "
                     "reference dense QZ with a kernel cut-off)"],
        observables=[
            observable("complex eigenvalue k0^2, six near 150 MHz", "m^-2",
                       "max relative difference", relative_difference(ours.eigenvalues_m2, reference),
                       SAME),
            observable("quality factor Re f / (2 Im f)", "1", "max relative difference",
                       relative_difference(ours.quality_factors,
                                           (lambda f: f.real / (2 * f.imag))(
                                               C0 * np.sqrt(reference) / (2 * np.pi))), SAME)]))


def test_impedance_wall_cavity_same_mesh(skfem):
    """Each galerkin mode solves T(k) q = 0 with Zs at its own k: rebuild T in scikit-fem."""
    lengths, cells = (1.0, 0.45, 0.8), (3, 2, 3)
    walls = {"z1": 5.8e7, "x0": 1.0e6}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_material_cavity_box(lengths, cells, num_modes=3, target_frequency_hz=200e6,
                                         wall_conductivity_s_per_m=walls)
    mesh = skfem.MeshTet(ours.mesh.nodes.T.copy(), ours.mesh.tets.T.copy())
    _, _, tangential_mass = _forms(skfem)
    reference = []
    with clock("reference"):
        basis, stiffness, mass = _material_matrices(
            skfem, mesh, ours.tet_relative_permittivity, ours.tet_relative_permeability)
        pec = np.concatenate([_wall_facets(mesh, w) for w in WALL_AXES if w not in walls])
        free = basis.complement_dofs(basis.get_dofs(facets=pec))
        boundary = {w: tangential_mass.assemble(
            skfem.FacetBasis(mesh, skfem.ElementTetN0(), facets=_wall_facets(mesh, w))).tocsr()
            for w in walls}
        for value in ours.eigenvalues_m2:
            k = np.sqrt(value)
            operator = stiffness.copy()
            for wall, sigma in walls.items():
                zs = np.sqrt(1j * k * ETA0 / sigma)          # sqrt(j omega mu0 / sigma)
                operator = operator + (1j * k * ETA0 / zs) * boundary[wall]
            values = la.eigvals(operator[free][:, free].toarray(), mass[free][:, free].toarray())
            reference.append(values[np.argmin(np.abs(values - value))])
    reference = np.array(reference)
    emit(make_record(
        case="cavity-impedance-walls", stopwatch=clock,
        physics="3D vacuum box 1 x 0.45 x 0.8 m, Leontovich walls z1 (5.8e7 S/m) and x0 "
                "(1e6 S/m), other walls PEC; nonlinear in k0",
        api="galerkin.material_cavity.solve_material_cavity_box (wall_conductivity_s_per_m)",
        discretization="lowest-order Nedelec tetrahedra, exact tangential Whitney wall mass",
        tool="scikit-fem", tool_discretization="ElementTetN0 with FacetBasis tangential mass",
        analytical_acceptance="tests/galerkin/test_cavity_wall_loss.py (packages/galerkin/docs/material_cavity.md)",
        matched=["same nodes and tetrahedra (the returned SI mesh, 3 x 2 x 3 cells)",
                 "PEC constraint on the four other walls",
                 "wall term j k0 eta0 / Zs with Zs = sqrt(j omega mu0 / sigma), mu0 = 1.25663706212e-6",
                 "Zs evaluated at each galerkin mode's own k0 (the nonlinear fixed point)"],
        not_matched=["nonlinear solve (galerkin residual inverse iteration; reference checks "
                     "the linear problem frozen at galerkin's k0, dense QZ)",
                     "wall-mass quadrature (galerkin closed form; scikit-fem facet quadrature, "
                     "exact for these quadratic integrands)"],
        observables=[observable("complex eigenvalue k0^2 at the fixed point, three modes", "m^-2",
                                "max relative difference",
                                relative_difference(ours.eigenvalues_m2, reference), SAME)]))
