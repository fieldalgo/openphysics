# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pytest

from refsol import slab


@pytest.mark.parametrize("n_f,n_s,d,lam", [
    (1.5, 1.0, 1.0, 1.55), (3.5, 1.45, 0.22, 1.55), (1.46, 1.44, 8.0, 1.3),
    (2.0, 1.5, 3.0, 0.633), (1.5, 1.0, 5.0, 1.0),
])
def test_symmetric_mode_count_matches_cutoff_formula(n_f, n_s, d, lam):
    for pol in ("TE", "TM"):
        found = slab.modes(n_f, n_s, n_s, d, lam, pol=pol)
        assert len(found) == slab.num_modes_symmetric(n_f, n_s, d, lam)


def test_effective_indices_are_bracketed_and_sorted():
    ne = slab.modes(1.5, 1.0, 1.0, 5.0, 1.0, "TE")
    assert all(1.0 < n < 1.5 for n in ne)
    assert ne == sorted(ne, reverse=True)


def test_te_more_confined_than_tm_in_symmetric_slab():
    te = slab.modes(3.5, 1.45, 1.45, 0.3, 1.55, "TE")[0]
    tm = slab.modes(3.5, 1.45, 1.45, 0.3, 1.55, "TM")[0]
    assert te > tm


def test_even_mode_equation_symmetric_te0():
    # TE0 of a symmetric slab also satisfies tan(kappa d/2) = gamma/kappa
    n_f, n_s, d, lam = 1.5, 1.0, 1.0, 1.55
    neff = slab.modes(n_f, n_s, n_s, d, lam, "TE")[0]
    k0 = 2 * np.pi / lam
    kappa = k0 * np.sqrt(n_f ** 2 - neff ** 2)
    gamma = k0 * np.sqrt(neff ** 2 - n_s ** 2)
    assert abs(np.tan(kappa * d / 2) - gamma / kappa) < 1e-9


def test_thick_film_limit_approaches_film_index():
    neff = slab.modes(1.5, 1.0, 1.0, 200.0, 1.0, "TE")[0]
    assert 1.5 - neff < 1e-4


def test_asymmetric_field_is_smooth_across_interfaces():
    n_f, n_s, n_c, d, lam = 2.0, 1.5, 1.0, 1.0, 1.0
    neff = slab.modes(n_f, n_s, n_c, d, lam, "TE")[0]
    h = 1e-6
    for xi in (d / 2, -d / 2):
        left = slab.field_te(np.array([xi - h]), neff, n_f, n_s, n_c, d, lam)[0]
        right = slab.field_te(np.array([xi + h]), neff, n_f, n_s, n_c, d, lam)[0]
        assert abs(left - right) < 1e-4                      # continuity of E_y
        dl = (slab.field_te(np.array([xi - h]), neff, n_f, n_s, n_c, d, lam)[0]
              - slab.field_te(np.array([xi - 2 * h]), neff, n_f, n_s, n_c, d, lam)[0]) / h
        dr = (slab.field_te(np.array([xi + 2 * h]), neff, n_f, n_s, n_c, d, lam)[0]
              - slab.field_te(np.array([xi + h]), neff, n_f, n_s, n_c, d, lam)[0]) / h
        assert abs(dl - dr) < 1e-2 * max(abs(dl), 1.0)      # continuity of dE_y/dx
