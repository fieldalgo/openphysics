# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transient contact on an oblique split mesh, compared with a full modal recurrence."""
import numpy as np
from scipy.linalg import eigh

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.transient_heat3d import solve_transient_heat_3d
from test_crosscheck_skfem_thermal_contact3d import _two_solids


def test_nonuniform_transient_contact_against_skfem():
    sk = require_tool("scikit-fem")
    from skfem.models.poisson import laplace, mass, unit_load

    mesh, left_trace, right_trace = _two_solids()
    mesh.nodes *= .02
    k, capacity = (2.3, .85), (1.3e6, 2.4e6)
    h, cooling, ambient = 350., 25., 300.
    time = np.array([0., .6, 2., 4.5, 9., 16., 28., 53., 99.])
    start, stop = 2., 16.
    centres = mesh.nodes[mesh.tets].mean(axis=1)
    heater = (mesh.regions == 0) & (centres[:, 1] > .006)
    power_density = 9e6
    right = np.unique(mesh.tets[mesh.regions == 1])
    y, z = mesh.nodes[:, 1] / .016, mesh.nodes[:, 2] / .012
    initial = ambient - 12. + 24. * y - 8. * z
    initial[right] = ambient + 3. + 4. * z[right]
    fixed = mesh.boundary["right_x1"]
    initial[fixed] = ambient

    clock = Stopwatch()
    with clock("reference"):
        ref = sk.MeshTet(mesh.nodes.T.copy(), mesh.tets.T.copy(), sort_t=False)
        element = sk.ElementTetP1()
        basis = sk.Basis(ref, element)
        bodies = [basis.with_elements(np.flatnonzero(mesh.regions == i)) for i in range(2)]
        bulk = sum(value * laplace.assemble(body) for value, body in zip(k, bodies)).toarray()
        capacity_matrix = sum(value * mass.assemble(body) for value, body in zip(capacity, bodies)).toarray()

        def face_mass(nodes):
            facets = np.flatnonzero(np.isin(ref.facets, nodes).all(axis=0))
            face = sk.FacetBasis(ref, element, facets=facets, intorder=4)
            return mass.assemble(face).toarray()

        jump = np.zeros((len(left_trace), basis.N))
        rows = np.arange(len(left_trace))
        jump[rows, left_trace] = 1.
        jump[rows, right_trace] = -1.
        surface = face_mass(left_trace)[np.ix_(left_trace, left_trace)]
        contact = h * jump.T @ surface @ jump
        robin = cooling * face_mass(mesh.boundary["left_z1"])
        conductance = bulk + contact + robin
        free = np.setdiff1d(np.arange(basis.N), fixed)
        free_block = np.ix_(free, free)
        decay, modes = eigh(conductance[free_block], capacity_matrix[free_block])
        pulse = power_density * unit_load.assemble(basis.with_elements(np.flatnonzero(heater)))
        active = (time[:-1] >= start) & (time[1:] <= stop)
        generated = active[:, None] * pulse

        # Advance every capacity-normalized mode with the same backward Euler rule.
        dt = np.diff(time)
        rise = np.zeros((len(time), basis.N))
        rise[0] = initial - ambient
        amplitudes = modes.T @ capacity_matrix[free_block] @ rise[0, free]
        for i, step in enumerate(dt):
            amplitudes = (amplitudes + step * (modes.T @ generated[i, free])) / (1. + step * decay)
            rise[i + 1, free] = modes @ amplitudes
        storage = (np.diff(rise, axis=0) @ capacity_matrix) / dt[:, None]
        contact_rate = h * ((rise[1:] @ jump.T) @ surface) @ jump
        convective = rise[1:] @ robin
        reaction = np.zeros_like(storage)
        reaction[:, fixed] = (storage + rise[1:] @ conductance - generated)[:, fixed]
        energy_weights = capacity_matrix.sum(axis=0)
        energy = (ambient + rise) @ energy_weights

    # Both the local sign of the initial jump and the net transfer across time vary.
    initial_jump = jump @ rise[0]
    net_transfer = contact_rate[:, left_trace].sum(axis=1)
    assert initial_jump.min() < 0. < initial_jump.max()
    assert net_transfer.min() < 0. < net_transfer.max()

    with clock("openphysics"):
        result = solve_transient_heat_3d(
            mesh, time=time, initial_temperature=initial, prescribed_temperature=dict.fromkeys(fixed, ambient),
            thermal_conductivity=dict(zip(mesh.region_names, k)),
            volumetric_heat_capacity=dict(zip(mesh.region_names, capacity)),
            thermal_contact_conductance={("left_x1", "right_x0"): h}, convection={"left_z1": (cooling, ambient)},
            heat_source_density=lambda t: power_density * heater if start <= t < stop else 0.)

    np.testing.assert_array_equal(result.time, time)
    np.testing.assert_allclose(result.stored_heat[0], energy[0], rtol=2e-14, atol=0.)
    comparisons = [observable(name, unit, "max relative difference", relative_difference(value, expected), 1e-9)
                   for name, unit, value, expected in (
                       ("temperature relative to ambient", "K", result.temperature - ambient, rise),
                       ("interval-end outward contact rate", "W", result.contact_heat_rate, contact_rate),
                       ("nodal storage rate", "W", result.heat_storage_rate, storage),
                       ("Dirichlet reaction", "W", result.reaction_heat_rate, reaction),
                       ("convection rate", "W", result.outward_convective_heat_rate, convective),
                       ("switched volume load", "W", result.generated_heat_rate, generated),
                       ("change in stored heat", "J", result.stored_heat - energy[0], energy - energy[0]))]

    supplied = result.generated_heat_rate + result.reaction_heat_rate - result.outward_convective_heat_rate
    comparisons.append(observable("paired nodal contact rates", "W", "max relative difference",
                                  relative_difference(result.contact_heat_rate[:, left_trace],
                                                      -result.contact_heat_rate[:, right_trace]), 1e-10))
    for i, name in enumerate(mesh.region_names):
        nodes = np.unique(mesh.tets[mesh.regions == i])
        stored_change = np.diff((result.temperature[:, nodes] - ambient) @ energy_weights[nodes])
        net_energy = dt * (supplied[:, nodes] - result.contact_heat_rate[:, nodes]).sum(axis=1)
        comparisons.append(observable(f"{name} body interval energy balance", "J", "max relative difference",
                                      relative_difference(stored_change, net_energy), 1e-10))
    comparisons.append(observable("global interval energy balance", "J", "max relative difference",
                                  relative_difference(np.diff(result.stored_heat), dt * supplied.sum(axis=1)), 1e-10))
    emit(make_record(
        case="transient-heat-3d-oblique-contact", physics="Pulsed heating and cooling with finite thermal contact",
        api="galerkin.transient_heat3d.solve_transient_heat_3d", discretization="P1 tetrahedra, backward Euler",
        tool="scikit-fem", tool_discretization="ElementTetP1, consistent capacity and degree-four facet quadrature",
        matched=["same split mesh, material properties, contact and exterior convection coefficients",
                 "same nonuniform initial temperature, fixed temperature and localized pulse",
                 "same eight unequal backward Euler steps with the switch times on the grid"],
        not_matched=["reference independently assembles the spatial operators and advances all modes separately"],
        analytical_acceptance="tests/galerkin/test_transient_thermal_contact3d.py", stopwatch=clock,
        observables=comparisons))
