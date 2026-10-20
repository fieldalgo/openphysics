# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""HE11 cluster mean-index derivative against the exact vector group index.

Pre-registered before the first run (openphysics issues #17 and #18) on the
symmetric polar fiber fixture (a = 4 um, n1 = 1.45, n2 = 1.44). The analytic
value comes from implicit differentiation of the exact dispersion equation
(refsol.fiber.vector_group_index), not from FEM.

#17: g_bar at 1.55 um within 2e-4 of the exact n_g at mesh scale 2, and
smaller at scale 3. A first attempt that also tracked TE01 and TM01 as
singletons failed at every scale (the mesh resolves their 9.6e-6 splitting
only to about 1e-6); it is recorded in the issue and not encoded here.

#17 item 2: the FEM HE11 eigenvector span approaches the exact HE11 span
(two polarizations, electric L2 by degree-5 quadrature): sin(theta_max) < 0.05
at scale 2, decreasing over scales 1-3 with observed order > 0.8 on the finest
pair; the exact HE21 span is a negative control (sin theta_min > 0.9).

#17 Sellmeier case: dispersive core and cladding (core 1 + 1.1 l^2/(l^2-0.01),
cladding 0.993 x core) re-evaluated per wavelength on the fixed mesh: g_bar
within 2e-4 of the exact dispersive n_g at scale 2 and smaller at scale 3; the
FEM material-dispersion contribution (dispersive minus frozen indices) within
2e-4 of the oracle's.

#18 second family: fiber a = 4 um, n1 = 1.47, n2 = 1.44 (V = 4.79). HE21 x2 and
TM01 (2.2e-5 apart) form an isolated rank-3 cluster of physically distinct
modes; settings span 4e-5, gap 6e-5 were chosen from the analytic gaps. The
pre-registered run failed at scale 2 (FEM TE01-HE21 gap below 4e-5 chains TE01
into the cluster; safe refusal) and is recorded in the issue. A separately
pre-registered run at scales 3 and 4 is encoded: partition [2, 1, 3] with the
EH11 guard, every cluster's g_bar within 2e-4 of its exact reference at scale 3
(rank 3: (2 n_g(HE21) + n_g(TM01)) / 3), largest error smaller at scale 4.

#18 (scale 2): domain radius 8a changes g_bar by < 1e-6; a nonuniform grid is
within 5e-6 of the uniform one and its reversal agrees to 1e-12; a larger
candidate budget keeps ranks/guards and g_bar within 1e-9; random unitary
rotations of the solver's degenerate bases change g_bar and sigma^2 by
< 1e-10; coordinates and wavelengths written in nm or m give g_bar within
1e-9 of the um run.
"""

import numpy as np
import pytest

from refsol import fiber
from subspace_fiber_fixture import (A, N1, N2, centred, cluster_sweep, field_space_sin_angles, he11_sweep,
                                    sellmeier)


@pytest.fixture(scope="module")
def exact():
    return fiber.vector_group_index(A, N1, N2, 1.55, "HE11")[1]


@pytest.fixture(scope="module")
def base():
    return he11_sweep(centred(0.01))


def test_he11_cluster_mean_group_index_meets_the_preregistered_budget(base, exact):
    assert base["ranks"] == [2] and base["guards"] == [3] * 5
    assert abs(base["g"][2] - exact) < 2e-4


@pytest.mark.slow
def test_he11_cluster_mean_group_index_error_decreases_with_refinement(base, exact):
    assert abs(he11_sweep(centred(0.01), scale=3)["g"][2] - exact) < abs(base["g"][2] - exact)


@pytest.mark.slow
def test_domain_truncation_is_negligible(base):
    assert abs(he11_sweep(centred(0.01), radius=8.0)["g"][2] - base["g"][2]) < 1e-6


@pytest.mark.slow
def test_nonuniform_and_reversed_wavelengths(base):
    grid = [1.53, 1.535, 1.55, 1.56, 1.57]
    forward = he11_sweep(grid)
    backward = he11_sweep(grid[::-1])
    assert abs(forward["g"][2] - base["g"][2]) < 5e-6
    np.testing.assert_allclose(backward["g"][::-1], forward["g"], atol=1e-12, rtol=0)


@pytest.mark.slow
def test_candidate_budget_and_solver_orientation_do_not_change_the_result(base):
    larger = he11_sweep(centred(0.01), search_modes=8)
    assert larger["ranks"] == base["ranks"] and larger["guards"] == base["guards"]
    np.testing.assert_allclose(larger["g"], base["g"], atol=1e-9, rtol=0)
    rotated = he11_sweep(centred(0.01), rotate_seed=20261019)
    np.testing.assert_allclose(rotated["g"], base["g"], atol=1e-10, rtol=0)
    for a, b in zip(rotated["sigma2"][1:], base["sigma2"][1:]):
        np.testing.assert_allclose(a, b, atol=1e-10, rtol=0)


def test_fem_he11_span_matches_the_exact_field_span():
    assert field_space_sin_angles(2).max() < 0.05


@pytest.mark.slow
def test_fem_he11_span_converges_to_the_exact_span_at_first_order():
    errors = [field_space_sin_angles(scale).max() for scale in (1, 2, 3)]
    assert errors[0] > errors[1] > errors[2]
    assert np.log(errors[1] / errors[2]) / np.log(1.5) > 0.8


@pytest.mark.slow
def test_field_space_negative_control():
    assert field_space_sin_angles(2, label="HE21").min() > 0.9


@pytest.fixture(scope="module")
def sellmeier_case():
    n1, n2, dn1, dn2 = sellmeier(1.55)
    exact = fiber.vector_group_index(A, n1, n2, 1.55, "HE11", dn1, dn2)[1]
    frozen = fiber.vector_group_index(A, n1, n2, 1.55, "HE11")[1]
    dispersive = he11_sweep(centred(0.01), materials=lambda wl: sellmeier(wl)[:2])["g"][2]
    fem_frozen = he11_sweep(centred(0.01), materials=lambda wl: (n1, n2))["g"][2]
    return dict(exact=exact, frozen=frozen, dispersive=dispersive, fem_frozen=fem_frozen)


def test_dispersive_he11_cluster_group_index_meets_the_preregistered_budget(sellmeier_case):
    c = sellmeier_case
    assert abs(c["dispersive"] - c["exact"]) < 2e-4
    assert abs((c["dispersive"] - c["fem_frozen"]) - (c["exact"] - c["frozen"])) < 2e-4


@pytest.mark.slow
def test_dispersive_he11_error_decreases_with_refinement(sellmeier_case):
    fine = he11_sweep(centred(0.01), scale=3, materials=lambda wl: sellmeier(wl)[:2])["g"][2]
    assert abs(fine - sellmeier_case["exact"]) < abs(sellmeier_case["dispersive"] - sellmeier_case["exact"])


@pytest.mark.slow
def test_rank_three_accidental_cluster_mean_group_index():
    a, n1, n2 = 4.0, 1.47, 1.44
    ng = {label: fiber.vector_group_index(a, n1, n2, 1.55, label)[1] for label in ("HE11", "TE01", "HE21", "TM01")}
    reference = np.array([ng["HE11"], ng["TE01"], (2 * ng["HE21"] + ng["TM01"]) / 3])
    settings = dict(method="electric-l2-subspace-v1", cluster_span_max=4e-5, external_gap_min=6e-5)
    errors = []
    for scale in (3, 4):
        r = cluster_sweep(centred(0.01), 6, settings, scale=scale, materials=lambda wl: (n1, n2), core_radius=a)
        assert r["ranks"] == [2, 1, 3] and r["guards"] == [7] * 5
        errors.append(np.abs(r["g"][2] - reference))
    assert errors[0].max() < 2e-4
    assert errors[1].max() < errors[0].max()


@pytest.mark.slow
@pytest.mark.parametrize("unit, ratio", [("nm", 1e3), ("m", 1e-6)])
def test_scaled_coordinates_give_the_same_cluster_statistics(base, unit, ratio):
    """Writing coordinates and wavelengths in nm or m instead of um leaves g_bar unchanged.

    The metre case was pre-registered with the nanometre threshold (ranks and
    guards identical, g_bar within 1e-9); it was observed at about 1e-13.
    """
    scaled = cluster_sweep([ratio * w for w in centred(0.01)], 2,
                           dict(method="electric-l2-subspace-v1", cluster_span_max=1e-6, external_gap_min=1e-3),
                           core_radius=ratio * A)
    assert scaled["ranks"] == base["ranks"] and scaled["guards"] == base["guards"]
    np.testing.assert_allclose(scaled["g"][:, 0], base["g"], atol=1e-9, rtol=0)
