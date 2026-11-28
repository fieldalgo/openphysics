# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent facet quadrature for heat transfer across a split-node interface."""
import numpy as np
from scipy.sparse import csr_matrix

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.thermal3d import solve_steady_heat_3d


def _two_solids():
    block = box_mesh(.4, .8, .6, 2, 3, 2)
    n = block.num_nodes
    # Reverse the right body's vertex numbering as well as its tagged face order.
    right_ids = np.arange(2 * n - 1, n - 1, -1)
    right_coordinates = block.nodes.copy()
    right_coordinates[:, 0] = .4 + .65 * right_coordinates[:, 0]
    nodes = np.vstack((block.nodes, right_coordinates[::-1]))
    nodes[:, 0] += .24 * nodes[:, 1] - .18 * nodes[:, 2]
    faces = {f"left_{tag}": triangles for tag, triangles in block.tagged_faces.items()}
    faces.update({f"right_{tag}": right_ids[np.roll(triangles[::-1], 1, axis=1)]
                  for tag, triangles in block.tagged_faces.items()})
    mesh = Mesh3D(nodes, np.vstack((block.tets, right_ids[block.tets])),
                  regions=np.repeat([0, 1], block.num_tets), region_names=["left", "right"],
                  tagged_faces=faces)
    return mesh, block.boundary["x1"], right_ids[block.boundary["x0"]]


def test_nonuniform_jump_against_skfem_facet_quadrature():
    sk = require_tool("scikit-fem")
    from skfem.models.poisson import laplace, mass, unit_load

    mesh, left_trace, right_trace = _two_solids()
    np.testing.assert_array_equal(mesh.nodes[left_trace], mesh.nodes[right_trace])
    k = np.array([2.3, .85])
    source = np.array([4.5, 2.])
    h, inward = 4.9, 7.5
    fixed_temperature = {node: 316. + 110. * (mesh.nodes[node, 1] - .4)
                               - 48. * (mesh.nodes[node, 2] - .3)
                         for node in mesh.boundary["left_x0"]}
    fixed_temperature.update(dict.fromkeys(mesh.boundary["right_x1"], 302.))

    clock = Stopwatch()
    with clock("reference"):
        ref = sk.MeshTet(mesh.nodes.T.copy(), mesh.tets.T.copy(), sort_t=False)
        element = sk.ElementTetP1()
        basis = sk.Basis(ref, element)
        bodies = [basis.with_elements(np.flatnonzero(mesh.regions == i)) for i in range(2)]
        diffusion = sum(coefficient * laplace.assemble(body) for coefficient, body in zip(k, bodies))
        generated = sum(q * unit_load.assemble(body) for q, body in zip(source, bodies))

        def face_basis(nodes):
            facets = np.flatnonzero(np.isin(ref.facets, nodes).all(axis=0))
            return sk.FacetBasis(ref, element, facets=facets, intorder=4)

        outward = -inward * unit_load.assemble(face_basis(mesh.boundary["right_y1"]))
        trace_mass = mass.assemble(face_basis(left_trace))[left_trace][:, left_trace]
        # Rows of J evaluate the coincident nodal trace differences T_left - T_right.
        rows = np.arange(len(left_trace))
        jump = csr_matrix((np.repeat([1., -1.], len(rows)),
                           (np.tile(rows, 2), np.r_[left_trace, right_trace])),
                          shape=(len(rows), basis.N))
        contact = h * jump.T @ trace_mass @ jump
        system = diffusion + contact
        load = generated - outward
        fixed = np.array(sorted(fixed_temperature))
        boundary_values = np.zeros(basis.N)
        boundary_values[fixed] = [fixed_temperature[node] for node in fixed]
        temperature = sk.solve(*sk.condense(system, load, x=boundary_values, D=fixed))
        flux = -k[mesh.regions, None] * basis.interpolate(temperature).grad[:, :, 0].T
        trace_jump = jump @ temperature
        contact_rate = jump.T @ (h * (trace_mass @ trace_jump))
        reaction = np.zeros(basis.N)
        reaction[fixed] = (system @ temperature - load)[fixed]

    # The local flow reverses along this interface. Nodal area weights alone
    # would therefore give a measurably different distribution of heat rates.
    assert trace_jump.min() < 0. < trace_jump.max()
    lumped_rate = h * np.asarray(trace_mass.sum(axis=1)).ravel() * trace_jump
    assert relative_difference(lumped_rate, contact_rate[left_trace]) > .02

    with clock("openphysics"):
        result = solve_steady_heat_3d(
            mesh, thermal_conductivity=dict(zip(mesh.region_names, k)),
            prescribed_temperature=fixed_temperature, heat_source_density=dict(zip(mesh.region_names, source)),
            inward_heat_flux={"right_y1": inward}, thermal_contact_conductance={("left_x1", "right_x0"): h})

    comparisons = [observable(name, unit, "max relative difference", relative_difference(value, ref_value), 1e-9)
                   for name, unit, value, ref_value in (
                       ("temperature relative to cold boundary", "K", result.temperature - 302., temperature - 302.),
                       ("element heat flux", "W/m^2", result.heat_flux, flux),
                       ("signed outward nodal contact rate", "W", result.contact_heat_rate, contact_rate),
                       ("Dirichlet reaction", "W", result.reaction_heat_rate, reaction),
                       ("volume generation", "W", result.generated_heat_rate, generated),
                       ("prescribed outward heat rate", "W", result.outward_prescribed_heat_rate, outward))]
    conduct = diffusion @ result.temperature
    power_scale = np.sum(np.abs(contact_rate))
    external = generated + result.reaction_heat_rate - outward
    nodal_imbalance = conduct + result.contact_heat_rate - external
    pair_imbalance = result.contact_heat_rate[left_trace] + result.contact_heat_rate[right_trace]
    for name, error in (("nodal balance", np.max(np.abs(nodal_imbalance))),
                        ("pairwise contact balance", np.max(np.abs(pair_imbalance))),
                        ("global external balance", abs(external.sum()))):
        comparisons.append(observable(name, "1", "imbalance / total absolute contact rate",
                                      error / power_scale, 1e-10))
    for i, name in enumerate(mesh.region_names):
        nodes = np.unique(mesh.tets[mesh.regions == i])
        imbalance = np.sum(external[nodes] - result.contact_heat_rate[nodes])
        comparisons.append(observable(f"{name} body balance", "1", "imbalance / total absolute contact rate",
                                      abs(imbalance) / power_scale, 1e-10))
    assert 0. <= result.relative_conservation_residual < 1e-10
    emit(make_record(
        case="steady-heat-3d-oblique-contact", physics="3D conduction across a finite-conductance interface",
        api="galerkin.thermal3d.solve_steady_heat_3d", discretization="P1 tetrahedra, matching split faces",
        tool="scikit-fem", tool_discretization="ElementTetP1, degree-four triangular facet quadrature",
        matched=["same skewed two-body mesh, distinct conductivities and sources",
                 "same spatially varying Dirichlet data, side-wall flux, and contact conductance",
                 "matching vertex traces with separate node numbering and opposite outward normals"],
        not_matched=["reference constructs the jump through the known correspondence of the two mesh copies"],
        observables=comparisons, stopwatch=clock,
        analytical_acceptance="tests/galerkin/test_thermal_contact3d.py"))
