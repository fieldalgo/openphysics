# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import numpy as np

from refsol import metallic, scattering


def test_rect_waveguide_cutoffs_1_by_half():
    cut = metallic.rect_waveguide_cutoffs(1.0, 0.5, n_max=3)
    vals = [v for v, _ in cut[:4]]
    assert np.allclose(vals, [np.pi ** 2, 4 * np.pi ** 2, 4 * np.pi ** 2, 5 * np.pi ** 2])
    assert cut[0][1] == "TE10"


def test_cavity_lowest_mode_cube():
    res = metallic.rect_cavity_resonances(1.0, 1.0, 1.0, n_max=2)
    k2, lbl = res[0]
    assert np.isclose(k2, 2 * np.pi ** 2)      # TE101 / TE011 / TM110 degenerate
    assert sum(np.isclose(v, 2 * np.pi ** 2) for v, _ in res) == 3


def test_coax_boundary_values_and_field():
    assert np.isclose(metallic.coax_potential(1.0, 1.0, 3.0), 1.0)
    assert np.isclose(metallic.coax_potential(3.0, 1.0, 3.0), 0.0)
    r = np.array([1.5, 2.0])
    h = 1e-6
    dV = (metallic.coax_potential(r + h, 1, 3) - metallic.coax_potential(r - h, 1, 3)) / (2 * h)
    assert np.allclose(-dV, metallic.coax_field_magnitude(r, 1, 3), rtol=1e-6)


def test_pec_tm_total_field_vanishes_on_cylinder():
    k, a = np.pi, 1.0
    th = np.linspace(0, 2 * np.pi, 13)
    u = scattering.total(a * np.cos(th), a * np.sin(th), k, a, "pec_tm")
    assert np.max(np.abs(u)) < 1e-9


def test_pec_te_normal_derivative_vanishes_on_cylinder():
    k, a = np.pi, 1.0
    th = np.linspace(0, 2 * np.pi, 9)
    h = 1e-6
    u_out = scattering.total((a + h) * np.cos(th), (a + h) * np.sin(th), k, a, "pec_te")
    u_in = scattering.total((a + 2 * h) * np.cos(th), (a + 2 * h) * np.sin(th), k, a, "pec_te")
    assert np.max(np.abs((u_in - u_out) / h)) < 1e-3


def test_dielectric_cylinder_continuity():
    k, a, n = np.pi, 1.0, 1.5
    th = np.linspace(0, 2 * np.pi, 9)
    h = 1e-7
    ro, ri = a + h, a - h
    u_o = scattering.total(ro * np.cos(th), ro * np.sin(th), k, a, "dielectric", n)
    u_i = scattering.total(ri * np.cos(th), ri * np.sin(th), k, a, "dielectric", n)
    assert np.max(np.abs(u_o - u_i)) < 1e-5
    # radial derivative continuity (non-magnetic TM_z)
    u_o2 = scattering.total((ro + h) * np.cos(th), (ro + h) * np.sin(th), k, a, "dielectric", n)
    u_i2 = scattering.total((ri - h) * np.cos(th), (ri - h) * np.sin(th), k, a, "dielectric", n)
    d_o = (u_o2 - u_o) / h
    d_i = (u_i - u_i2) / h
    assert np.max(np.abs(d_o - d_i)) < 1e-2


def test_scattering_width_geometric_optics_limit():
    # Large PEC cylinder: total scattering width -> twice the geometric width (4a)
    a = 1.0
    k = 60.0 / a
    sigma = scattering.scattering_width(k, a, "pec_tm", n_terms=120)
    assert abs(sigma / (4 * a) - 1.0) < 0.1
