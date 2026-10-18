# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""HE11 cluster mean-index derivative against the exact vector group index.

Pre-registered before the first run (openphysics issue #17): on the symmetric
polar fiber fixture (a = 4 um, n1 = 1.45, n2 = 1.44, radius 6a) with
wavelengths 1.53..1.57 um, the HE11 rank-2 cluster's g_bar at 1.55 um must be
within 2e-4 of the analytic n_g at scale 2, and the error must decrease from
scale 2 to scale 3. The analytic value comes from implicit differentiation of
the exact dispersion equation (refsol.fiber.vector_group_index), not from FEM.

A first pre-registered attempt that also tracked TE01 and TM01 as singletons
failed at every scale: this mesh resolves their 9.6e-6 splitting only to
about 1e-6. That attempt is recorded in the issue and not encoded here.
"""

import numpy as np
import pytest

from galerkin import disk_mesh, eval_edge_field, solve_modes
from refsol import fiber
from simcase.fields import VectorField
from simcase.subspace_tracking import SubspaceTracker
from simcase.tracking import tracking_settings

A, N1, N2 = 4.0, 1.45, 1.44
WAVELENGTHS = (1.53, 1.54, 1.55, 1.56, 1.57)
SETTINGS = dict(method="electric-l2-subspace-v1", cluster_span_max=1e-6, external_gap_min=1e-3)


def he11_mean_group_index(scale):
    mesh = disk_mesh((A, 2 * A, 6 * A), (4 * scale, 4 * scale, 16 * scale), 32 * scale)
    eps = mesh.by_region([N1 ** 2, N2 ** 2, N2 ** 2])
    settings = tracking_settings(2, SETTINGS)
    tracker = SubspaceTracker(mesh, 2, settings)
    means = []
    for wl in WAVELENGTHS:
        n_eff, space, et, ez = solve_modes(mesh, eps, 2 * np.pi / wl, n_target=N1, num_modes=10)
        keep = np.flatnonzero((n_eff > N2) & (n_eff < N1))[:settings["search_modes"]]
        electric = np.zeros((mesh.num_triangles, len(keep), 3), dtype=complex)
        for j, i in enumerate(keep):
            electric[:, j, :2] = eval_edge_field(space, et[i])
            electric[:, j, 2] = 1j * ez[i][mesh.triangles].mean(axis=1)
        field = VectorField(space.edges.copy(), et[keep].T, 1j * ez[keep].T, electric)
        neff, _, _, offsets, evidence = tracker.step(n_eff[keep], field, f"{wl} um")
        assert offsets.tolist() == [0, 2]
        assert evidence["clusters"][0]["lower_guard_rank"] == 3
        means.append(neff.mean())
    wl = np.array(WAVELENGTHS)
    means = np.array(means)
    return (means - wl * np.gradient(means, wl, edge_order=2))[2]


@pytest.fixture(scope="module")
def exact():
    return fiber.vector_group_index(A, N1, N2, 1.55, "HE11")[1]


@pytest.fixture(scope="module")
def scale2_error(exact):
    return abs(he11_mean_group_index(2) - exact)


def test_he11_cluster_mean_group_index_meets_the_preregistered_budget(scale2_error):
    assert scale2_error < 2e-4


@pytest.mark.slow
def test_he11_cluster_mean_group_index_error_decreases_with_refinement(scale2_error, exact):
    assert abs(he11_mean_group_index(3) - exact) < scale2_error
