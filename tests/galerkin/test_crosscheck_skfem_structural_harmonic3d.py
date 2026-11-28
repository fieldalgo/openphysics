# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare complex forced response with a full modal expansion on a skewed solid."""
import numpy as np
from scipy.linalg import eigh

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.structural_harmonic3d import solve_structural_harmonic_3d


def test_two_material_rayleigh_response_against_skfem():
    sk = require_tool("scikit-fem")
    from skfem.helpers import dot, sym_grad
    from skfem.models.elasticity import lame_parameters, linear_elasticity, linear_stress

    block = box_mesh(1., .45, .28, 4, 2, 2)
    nodes = block.nodes.copy()
    nodes[:, 1] += .16 * nodes[:, 0]
    nodes[:, 2] += .07 * nodes[:, 0] - .13 * nodes[:, 1]
    region = (nodes[block.tets, 0].mean(axis=1) > .5).astype(int)
    mesh = Mesh3D(nodes, block.tets, regions=region, region_names=["base", "tip"],
                  tagged_faces=block.tagged_faces)
    young = np.array([150e6, 65e6])
    poisson = np.array([.24, .32])
    density = np.array([1200., 2800.])
    body = (1.3 - .7j, -.4 + .9j, .8 + .3j)
    traction = {"x1": (.5 + .3j, 1.1 - .6j, -.9 + 1.2j),
                "x0": (-.3 + .8j, .4 + .1j, .6 - .2j)}
    alpha, beta = 1.5, 8e-5

    clock = Stopwatch()
    with clock("reference"):
        ref = sk.MeshTet(nodes.T.copy(), mesh.tets.T.copy(), sort_t=False)
        element = sk.ElementVector(sk.ElementTetP1())
        basis = sk.Basis(ref, element)
        lam, mu = lame_parameters(young[region, None], poisson[region, None])
        stiffness = linear_elasticity(lam, mu).assemble(basis)

        @sk.BilinearForm
        def vector_mass(u, v, w):
            return density[region, None] * dot(u, v)

        mass = vector_mass.assemble(basis)

        def assemble_load(domain, force):
            @sk.LinearForm(dtype=complex)
            def vector_load(v, w):
                return dot(np.asarray(force)[:, None, None], v)

            return vector_load.assemble(domain)

        root = ref.facets_satisfying(lambda x: np.isclose(x[0], 0.))
        tip = ref.facets_satisfying(lambda x: np.isclose(x[0], 1.))
        load = (assemble_load(basis, body)
                + assemble_load(sk.FacetBasis(ref, element, facets=tip), traction["x1"])
                + assemble_load(sk.FacetBasis(ref, element, facets=root), traction["x0"]))
        fixed = basis.get_dofs(facets=root).all()
        free = np.setdiff1d(np.arange(basis.N), fixed)
        eigenvalues, modes = eigh(stiffness[free][:, free].toarray(), mass[free][:, free].toarray())
        modal_load = modes.T @ load[free]
        fundamental = np.sqrt(eigenvalues[0]) / (2 * np.pi)
        frequency = fundamental * np.array([1.006, 0., .37, 1.5])
    with clock("openphysics"):
        result = solve_structural_harmonic_3d(
            mesh, youngs_modulus=dict(zip(mesh.region_names, young)),
            poisson_ratio=dict(zip(mesh.region_names, poisson)),
            mass_density=dict(zip(mesh.region_names, density)), frequency=frequency,
            prescribed_displacement={(n, a): 0. for n in mesh.boundary["x0"] for a in range(3)},
            body_force_density=body, traction=traction, mass_proportional_damping_coefficient=alpha,
            stiffness_proportional_damping_coefficient=beta)

    np.testing.assert_array_equal(result.frequency, frequency)
    comparisons = []
    for i, omega in enumerate(2 * np.pi * frequency):
        with clock("reference"):
            # Rayleigh damping is diagonal in the mass-normalized elastic modes.
            denominator = eigenvalues - omega**2 - 1j * omega * (alpha + beta * eigenvalues)
            displacement = np.zeros(basis.N, dtype=complex)
            displacement[free] = modes @ (modal_load / denominator)
            strain = sym_grad(basis.interpolate(displacement))
            stress = linear_stress(lam, mu)(strain)[:, :, :, 0].transpose(2, 0, 1)

            dynamic = stiffness - omega**2 * mass - 1j * omega * (alpha * mass + beta * stiffness)
            reaction = np.zeros_like(load)
            reaction[fixed] = (dynamic @ displacement - load)[fixed]
        computed = np.empty_like(displacement)
        computed[basis.nodal_dofs] = result.displacement[i].T
        imbalance = (dynamic @ computed - load)[free]
        for name, unit, ours, reference in (
                ("complex nodal displacement", "m", result.displacement[i], displacement[basis.nodal_dofs].T),
                ("complex elastic stress", "Pa", result.stress[i], stress),
                ("complex nodal reaction", "N", result.reaction_force[i], reaction[basis.nodal_dofs].T)):
            comparisons.append(observable(f"{name} at {frequency[i]:.5g} Hz", unit,
                                          "max relative difference", relative_difference(ours, reference), 1e-9))
        comparisons.append(observable(f"free equilibrium at {frequency[i]:.5g} Hz", "1",
                                      "free force imbalance norm / load norm",
                                      np.linalg.norm(imbalance) / np.linalg.norm(load[free]), 1e-10))
        assert 0. <= result.relative_residual[i] < 1e-10

    emit(make_record(
        case="structural-harmonic-3d-two-material-cantilever",
        physics="Damped 3D elastic forced response of a two-material skewed cantilever",
        api="galerkin.structural_harmonic3d.solve_structural_harmonic_3d",
        discretization="P1 tetrahedra, consistent vector mass, Rayleigh damping",
        tool="scikit-fem", tool_discretization="ElementVector(ElementTetP1), volume and facet quadrature",
        matched=["same 96 tetrahedra, two isotropic materials and densities, and clamped root",
                 "complex volume force and tractions on the free tip and constrained root",
                 "mass- and stiffness-proportional damping, exp(-i omega t) convention",
                 "static, subresonant, near-resonant and above-first-resonance frequencies"],
        not_matched=["direct dynamic solve compared with a full mass-normalized modal expansion"],
        analytical_acceptance="tests/galerkin/test_structural_harmonic3d.py", stopwatch=clock,
        observables=comparisons))
