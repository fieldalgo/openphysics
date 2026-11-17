# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pytest

from refsol import metallic, scattering


def test_rect_waveguide_cutoffs_1_by_half():
    cut = metallic.rect_waveguide_cutoffs(box_size=(1.0, 0.5), n_max=3)     # 1 m x 0.5 m: k_c^2 in 1/m^2
    vals = [v for v, _ in cut[:4]]
    assert np.allclose(vals, [np.pi ** 2, 4 * np.pi ** 2, 4 * np.pi ** 2, 5 * np.pi ** 2])
    assert cut[0][1] == "TE10"


def test_cavity_lowest_mode_cube():
    res = metallic.rect_cavity_resonances(box_size=(1.0, 1.0, 1.0), n_max=2)      # a 1 m cube: k^2 in 1/m^2
    k2, lbl = res[0]
    assert np.isclose(k2, 2 * np.pi ** 2)      # TE101 / TE011 / TM110 degenerate
    assert sum(np.isclose(v, 2 * np.pi ** 2) for v, _ in res) == 3


@pytest.mark.parametrize("box_size", [(1.0, 1.0), (1.0, 0.0, 1.0), (1.0, np.nan, 1.0), (1.0, 1.0, 1.0j), 1.0, None])
def test_cavity_resonances_refuse_a_box_that_is_not_three_positive_lengths(box_size):
    # L3 commit 12: box_size (a, b, d) in m; a str is a TypeError (the units scan's string rule)
    with pytest.raises(ValueError, match="box_size"):
        metallic.rect_cavity_resonances(box_size=box_size)
    with pytest.raises(TypeError, match="box_size"):
        metallic.rect_cavity_resonances(box_size=(1.0, "1", 1.0))
    with pytest.raises(ValueError, match="n_max"):
        metallic.rect_cavity_resonances(box_size=(1.0, 1.0, 1.0), n_max=-1)


#: radii (1, 3) and the potentials (1 V, 0 V) the coax functions took by default before the galerkin step
COAX = dict(position=(1.0, 3.0), prescribed_electric_potential=(1.0, 0.0))


def _on_axis(r):
    """Points (r, 0): their hypot is r exactly, the radius these checks passed before."""
    r = np.atleast_1d(np.asarray(r, dtype=float))
    return np.column_stack([r, np.zeros_like(r)])


def test_coax_boundary_values_and_field():
    assert np.isclose(metallic.coax_potential(_on_axis(1.0), **COAX), 1.0)
    assert np.isclose(metallic.coax_potential(_on_axis(3.0), **COAX), 0.0)
    r = np.array([1.5, 2.0])
    h = 1e-6
    dV = (metallic.coax_potential(_on_axis(r + h), **COAX) - metallic.coax_potential(_on_axis(r - h), **COAX)) / (2 * h)
    assert np.allclose(-dV, metallic.coax_field_magnitude(_on_axis(r), **COAX), rtol=1e-6)


def _cylinder(k, a, **kwargs):
    """The cylinder's keyword arguments; k in rad/m and a in m (only k a and k r enter)."""
    return dict(vacuum_angular_wavenumber=k, radius=a, **kwargs)


def _at(r, th):
    """Points (r cos th, r sin th): the coordinates these checks passed as x and y before."""
    return np.stack([r * np.cos(th), r * np.sin(th)], axis=-1)


def test_pec_tm_total_field_vanishes_on_cylinder():
    k, a = np.pi, 1.0
    th = np.linspace(0, 2 * np.pi, 13)
    u = scattering.total(_at(a, th), **_cylinder(k, a, kind="pec_tm"))
    assert np.max(np.abs(u)) < 1e-9


def test_pec_te_normal_derivative_vanishes_on_cylinder():
    k, a = np.pi, 1.0
    th = np.linspace(0, 2 * np.pi, 9)
    h = 1e-6
    u_out = scattering.total(_at(a + h, th), **_cylinder(k, a, kind="pec_te"))
    u_in = scattering.total(_at(a + 2 * h, th), **_cylinder(k, a, kind="pec_te"))
    assert np.max(np.abs((u_in - u_out) / h)) < 1e-3


def test_dielectric_cylinder_continuity():
    k, a, n = np.pi, 1.0, 1.5
    th = np.linspace(0, 2 * np.pi, 9)
    h = 1e-7
    ro, ri = a + h, a - h
    dielectric = _cylinder(k, a, kind="dielectric", refractive_index=n)
    u_o = scattering.total(_at(ro, th), **dielectric)
    u_i = scattering.total(_at(ri, th), **dielectric)
    assert np.max(np.abs(u_o - u_i)) < 1e-5
    # radial derivative continuity (non-magnetic TM_z)
    u_o2 = scattering.total(_at(ro + h, th), **dielectric)
    u_i2 = scattering.total(_at(ri - h, th), **dielectric)
    d_o = (u_o2 - u_o) / h
    d_i = (u_i - u_i2) / h
    assert np.max(np.abs(d_o - d_i)) < 1e-2


def test_scattering_width_geometric_optics_limit():
    # Large PEC cylinder: total scattering width -> twice the geometric width (4a)
    a = 1.0
    k = 60.0 / a
    sigma = scattering.scattering_width(**_cylinder(k, a, kind="pec_tm", terms=120))
    assert abs(sigma / (4 * a) - 1.0) < 0.1
