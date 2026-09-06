# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pytest

from refsol import fiber


def params_for_v(V, n1=1.45, n2=1.44, lam=1.55):
    a = V * lam / (2 * np.pi * np.sqrt(n1 ** 2 - n2 ** 2))
    return a, n1, n2, lam


@pytest.mark.parametrize("V", [0.8, 1.5, 2.6, 4.0, 6.0, 9.0])
def test_lp_mode_count_matches_cutoffs(V):
    a, n1, n2, lam = params_for_v(V)
    found = fiber.lp_modes(a, n1, n2, lam)
    assert len(found) == fiber.num_lp_modes(V)
    assert all(n2 < md.neff < n1 for md in found)
    assert [md.neff for md in found] == sorted((md.neff for md in found), reverse=True)


def test_lp11_cutoff_at_first_zero_of_j0():
    for V, expect in [(2.39, False), (2.42, True)]:
        found = fiber.lp_modes(*params_for_v(V))
        assert ("LP11" in [md.label for md in found]) is expect
    assert abs(fiber.lp_cutoff_v(1, 1) - 2.404825557695773) < 1e-12


def test_lp01_normalized_propagation_constant_rudolph_neumann():
    # Rudolph-Neumann approximation b ~ (1.1428 - 0.996/V)^2, ~0.1% accurate for 1.5 < V < 2.5
    V = 2.4
    lp01 = fiber.lp_modes(*params_for_v(V))[0]
    assert lp01.label == "LP01"
    assert abs(lp01.b - (1.1428 - 0.996 / V) ** 2) < 0.01


def test_he11_matches_lp01_in_weak_guidance():
    a, n1, n2, lam = params_for_v(2.2, n1=1.45, n2=1.449)
    lp01 = fiber.lp_modes(a, n1, n2, lam)[0]
    he11 = fiber.fundamental_neff(a, n1, n2, lam)
    assert abs(he11 - lp01.neff) < 5e-6


def test_te01_tm01_cutoff_and_count():
    for V, expect in [(2.39, 0), (2.5, 1), (5.6, 2)]:
        modes = fiber.vector_modes(*params_for_v(V), l_max=0)
        assert sum(md.label.startswith("TE") for md in modes) == expect
        assert sum(md.label.startswith("TM") for md in modes) == expect


def test_weak_guidance_degeneracy_lp11_group():
    # LP11 ~ {TE01, TM01, HE21} become degenerate as n1 -> n2
    a, n1, n2, lam = params_for_v(3.0, n1=1.45, n2=1.4495)
    lp11 = [md for md in fiber.lp_modes(a, n1, n2, lam) if md.label == "LP11"][0]
    vec = {md.label: md.neff for md in fiber.vector_modes(a, n1, n2, lam, l_max=2)}
    for lbl in ("TE01", "TM01", "HE21"):
        assert lbl in vec
        assert abs(vec[lbl] - lp11.neff) < 1e-5


def test_he11_has_no_cutoff():
    modes = fiber.vector_modes(*params_for_v(0.6), l_max=1)
    assert [md.label for md in modes] == ["HE11"]


def test_strongly_guiding_vector_modes_differ_from_scalar():
    # Silica core / air cladding: exact HE11 must differ visibly from LP01
    a, n1, n2, lam = 0.5, 1.45, 1.0, 1.55
    lp01 = fiber.lp_modes(a, n1, n2, lam)[0].neff
    he11 = fiber.fundamental_neff(a, n1, n2, lam)
    assert n2 < he11 < n1
    assert abs(he11 - lp01) > 1e-4
