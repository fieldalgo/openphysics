# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed tiny-domain producer regression and diagnostic, not a new oracle gate.

Diagnostic replay never changes the engine or catches a failing solve as success.
Use pytest -s on this file in an authorized Actions preflight to retain JSON.
"""
import json

import numpy as np
import pytest
from scipy.sparse.linalg import splu

from galerkin import rectangle_mesh
from galerkin.assembly import assemble_mass, assemble_stiffness
from galerkin.core.loads import source_load
from galerkin.transient_heat import solve_transient_heat

TIMES = np.array([2., 2.03, 2.1, 2.4, 3.])


def _case(scenario):
    n = 1 if scenario == 'support' else 8
    mesh = rectangle_mesh(.002, .001, n, n)
    ramp = scenario in ('ramp', 'support')
    initial = 290. if ramp else 300.
    q = {'heating': 8., 'cooling': -1600., 'ramp': 12., 'support': 2.}[scenario]
    ids = np.unique(np.concatenate(list(mesh.boundary.values()))) if ramp else np.array([], dtype=int)
    return mesh, initial, q, ids, ramp


def _diagnostic(scenario, mesh, initial, q, fixed, ramp):
    # Reconstruct the existing fixed-offset step solely to expose its arithmetic.
    # No guard is removed from the real solver invoked by the test below.
    m = assemble_mass(mesh, 4.)
    k = assemble_stiffness(mesh, 2.5)
    n = mesh.num_nodes
    ones = np.ones(n)
    w = m@ones
    f = source_load(mesh, mesh.nodes, mesh.triangles, mesh.areas(), q)
    free = np.setdiff1d(np.arange(n), fixed)
    previous = np.zeros(n)
    header = {
        'scenario': scenario, 'nodes': n, 'area_m2': float(mesh.areas().sum()),
        'total_mass_j_mk': float(w.sum()),
        'k_ones_inf': float(np.max(abs(k@ones))),
        'k_ones_sum': float(np.sum(k@ones)),
        'constant_source_vs_mass_inf': float(np.max(abs(f-(q/4.)*w))),
        'steps': [],
    }
    for index, h in enumerate(np.diff(TIMES), start=1):
        system = m/h+k
        rhs = f+(m@previous)/h
        current = np.empty(n)
        current[fixed] = 3.*(TIMES[index]-TIMES[0]) if ramp else 0.
        rhs_free = rhs[free]-system[free][:, fixed]@current[fixed]
        if len(free):
            current[free] = splu(system[free][:, free].tocsc()).solve(rhs_free)
        rate = (current-previous)/h
        stored = m@rate
        raw_spatial = k@current
        centered_spatial = k@(current-current[0])
        raw_residual = stored+raw_spatial-f
        centered_residual = stored+centered_spatial-f
        raw_reaction = np.zeros(n)
        centered_reaction = np.zeros(n)
        raw_reaction[fixed] = raw_residual[fixed]
        centered_reaction[fixed] = centered_residual[fixed]
        raw_balance = float(np.sum(stored-f-raw_reaction))
        centered_balance = float(np.sum(stored-f-centered_reaction))
        scale = max(float(np.sum(abs(stored)+abs(f)+abs(raw_reaction))), np.finfo(float).tiny)
        expected = (3. if ramp else q/4.)*(TIMES[index]-TIMES[0])
        matrix_error = system@current-rhs
        reduced = system[free][:, free].toarray() if len(free) else np.empty((0, 0))
        eig = np.linalg.eigvalsh(reduced) if len(free) else np.array([])
        header['steps'].append({
            'index': index, 'time_s': float(TIMES[index]), 'dt_s': float(h),
            'constant_mass_rayleigh': float(w.sum()/(n*h)),
            'reduced_eigen_min': float(eig[0]) if eig.size else None,
            'reduced_eigen_max': float(eig[-1]) if eig.size else None,
            'reduced_spectral_ratio': float(eig[-1]/eig[0]) if eig.size and eig[0] > 0 else None,
            'linear_free_residual_inf': float(np.max(abs(matrix_error[free]))) if len(free) else 0.,
            'physical_free_residual_inf': float(np.max(abs(raw_residual[free]))) if len(free) else 0.,
            'centered_free_residual_inf': float(np.max(abs(centered_residual[free]))) if len(free) else 0.,
            'physical_balance': raw_balance, 'centered_balance': centered_balance,
            'physical_balance_scale': scale,
            'physical_balance_ratio': abs(raw_balance)/scale,
            'centered_balance_same_scale_ratio': abs(centered_balance)/scale,
            'mass_mean_increment_error': float((w@current)/w.sum()-expected),
            'max_increment_error': float(np.max(abs(current-expected))),
            'spurious_spatial_range': float(np.ptp(current)),
            'raw_minus_centered_spatial_inf': float(np.max(abs(raw_spatial-centered_spatial))),
            'predicted_k_constant_leak_inf': float(np.max(abs((k@ones)*current[0]))),
        })
        previous = current.copy()
    print('TRANSIENT_TINY_DOMAIN_DIAGNOSTIC '+json.dumps(header, allow_nan=False), flush=True)


@pytest.mark.parametrize('scenario', ['heating', 'cooling', 'ramp', 'support'])
def test_tiny_domain_original_heat_balance_and_zero_flux(scenario):
    mesh, initial, q, fixed, ramp = _case(scenario)
    _diagnostic(scenario, mesh, initial, q, fixed, ramp)
    bc = {int(i): (lambda now: 290.+3.*(now-TIMES[0])) for i in fixed}
    # Original guard failures remain failures, with the complete chained cause.
    result = solve_transient_heat(
        mesh, conductivity=2.5, volumetric_heat_capacity=4., time_s=TIMES,
        initial_temperature_k=np.full(mesh.num_nodes, initial),
        dirichlet=bc, heat_source=q)
    rate = 3. if ramp else q/4.
    expected = initial+rate*(TIMES-TIMES[0])
    np.testing.assert_allclose(result.temperature_k,
        np.broadcast_to(expected[:, None], result.temperature_k.shape),
        rtol=0, atol=1e-10*max(1., float(np.max(abs(expected)))))
    np.testing.assert_allclose(result.heat_flux_w_m2, 0., rtol=0, atol=1e-10)
    area = .002*.001
    source = np.full(len(TIMES), q*area)
    storage = np.full(len(TIMES)-1, 4.*rate*area)
    reaction = storage-source[1:]
    scale = max(abs(q)*area, abs(4.*rate)*area, float(np.max(abs(reaction))), 1e-30)
    np.testing.assert_allclose(result.source_load_w_per_m.sum(1), source, rtol=0, atol=1e-10*scale)
    np.testing.assert_allclose(result.storage_rate_w_per_m.sum(1), storage, rtol=0, atol=1e-10*scale)
    np.testing.assert_allclose(result.reaction_w_per_m.sum(1), reaction, rtol=0, atol=1e-10*scale)
