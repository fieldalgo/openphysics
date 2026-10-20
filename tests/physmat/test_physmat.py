# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Checks against published values and physical constraints."""

import os
from pathlib import Path

import numpy as np
import pytest

import physmat
from physmat import Constant, DrudeLorentz, OutOfRange, RIIFormula, Sellmeier, Tabulated, fit_drude_lorentz

# An explicit path must fail if broken, not silently skip the database checks.
RII_PATH = os.environ.get("PHYSMAT_RII_PATH") or next(
    (p for p in (Path("/tmp/rii/database"), Path.home() / ".cache/physmat/rii") if p.exists()), None)


# ---- built-in materials vs literature ---------------------------------------

def test_fused_silica_malitson_reference_points():
    sio2 = physmat.get("SiO2")
    assert abs(sio2.n(0.5876) - 1.4585) < 1e-4          # n_d of fused silica (Malitson Table)
    assert abs(sio2.n(1.55) - 1.4440) < 1e-4
    assert abs(sio2.n(0.6328) - 1.4570) < 1e-4          # HeNe
    assert sio2.k(1.0) == 0.0


def test_silicon_reference_points():
    assert abs(physmat.get("Si").n(1.55) - 3.4777) < 2e-4       # Salzberg-Villa
    assert abs(physmat.get("Si").n(3.0) - 3.4320) < 3e-3         # Salzberg-Villa at 3 um
    si_vis = physmat.get("Si_visible")
    assert abs(si_vis.n(0.6328) - 3.88) < 0.02                   # Green 2008 at HeNe
    assert si_vis.k(0.4) > si_vis.k(1.0) > 0                     # absorption drops toward the band gap


def test_silicon_nitride_and_others():
    assert abs(physmat.get("Si3N4").n(1.55) - 1.996) < 2e-3      # Luke 2015
    assert abs(physmat.get("sapphire").n(0.5876) - 1.7681) < 2e-4
    assert abs(physmat.get("MgF2").n(0.5876) - 1.3777) < 2e-4
    assert abs(physmat.get("CaF2").n(0.5876) - 1.4338) < 2e-4
    assert abs(physmat.get("GaAs").n(1.55) - 3.374) < 5e-3
    assert abs(physmat.get("water").n(0.5) - 1.335) < 2e-3       # Hale & Querry
    assert physmat.get("air").n(1.0) == 1.0


def test_gold_johnson_christy_at_800nm():
    au = physmat.get("Au")
    nk = au.index(0.8)
    assert abs(nk.real - 0.15) < 0.02 and abs(nk.imag - 4.9) < 0.1
    eps = au.eps(0.8)
    assert abs(eps.real + 24.1) < 0.5 and 1.2 < eps.imag < 1.8
    assert au.eps(np.linspace(0.5, 1.5, 20)).imag.min() > 0        # passive: Im eps >= 0


def test_aliases_and_lookup_errors():
    assert physmat.get("fused silica") is physmat.get("sio2") is physmat.get("Silica")
    assert physmat.get("aluminium") is physmat.get("Al")
    with pytest.raises(KeyError):
        physmat.get("unobtainium")
    assert "Si" in physmat.names()


def test_validity_range_enforced():
    si = physmat.get("Si")                     # Salzberg-Villa valid 1.357-11.04 um
    with pytest.raises(OutOfRange):
        si.n(0.8)
    assert np.isfinite(si.n(0.8, strict=False))
    assert si.range_um == (1.357, 11.04)


def test_group_index_silicon():
    # Si near 1.55 um: n_g about 3.6 (well known for bulk silicon)
    ng = physmat.get("Si").optical.group_index(1.55)
    assert 3.55 < ng < 3.65


def test_material_properties_slot():
    si = physmat.get("Si")
    assert si.get("thermal_conductivity") == 148.0
    assert si.properties["thermal_conductivity"].unit == "W/(m K)"
    with pytest.raises(KeyError):
        si.get("magic")
    m = physmat.constant(1.5, name="test glass")
    assert m.n(0.5) == 1.5 and m.eps(0.5) == 2.25


# ---- models -------------------------------------------------------------------

def test_sellmeier_and_rii_formula_agree():
    # Malitson coefficients in both parametrisations
    s = Sellmeier([0.6961663, 0.4079426, 0.8974794], [0.0684043 ** 2, 0.1162414 ** 2, 9.896161 ** 2])
    r = RIIFormula(1, [0, 0.6961663, 0.0684043, 0.4079426, 0.1162414, 0.8974794, 9.896161])
    wl = np.linspace(0.3, 3.0, 20)
    assert np.allclose(s.n(wl), r.n(wl), atol=1e-12)


def test_rii_formulas_2_to_9_hand_checked():
    l = 1.0
    assert np.isclose(RIIFormula(2, [0, 1.0, 0.5]).n(l), np.sqrt(1 + 1.0 / (1 - 0.5)))
    assert np.isclose(RIIFormula(3, [2.0, 0.5, -2]).n(l), np.sqrt(2.5))
    assert np.isclose(RIIFormula(4, [2.0, 0.5, 0, 0.5, 1]).n(l), np.sqrt(2.0 + 0.5 / (1 - 0.5)))
    assert np.isclose(RIIFormula(5, [1.5, 0.01, -2]).n(l), 1.51)
    assert np.isclose(RIIFormula(6, [0, 1e-4, 2.0]).n(2.0), 1 + 1e-4 / (2.0 - 0.25))
    q = 1 / (1 - 0.028)
    assert np.isclose(RIIFormula(7, [1.5, 0.1, 0.01, 0, 0, 0]).n(l), 1.5 + 0.1 * q + 0.01 * q ** 2)
    r = 0.3
    assert np.isclose(RIIFormula(8, [0.3, 0, 0, 0]).n(l), np.sqrt((1 + 2 * r) / (1 - r)))
    assert np.isclose(RIIFormula(9, [2.0, 0.5, 0.5, 0, 0, 1]).n(l), np.sqrt(2.0 + 0.5 / 0.5))


def test_tabulated_interpolation_and_range():
    t = Tabulated([0.5, 1.0, 1.5], [1.5, 1.4, 1.3], [0.0, 0.1, 0.2])
    assert t.index(1.0) == 1.4 + 0.1j
    assert np.isclose(t.n(0.75), 1.45) and np.isclose(t.k(1.25), 0.15)
    assert t.range_um == (0.5, 1.5)
    with pytest.raises(OutOfRange):
        t.n(2.0)


def test_drude_lorentz_physics():
    # Drude: eps -> eps_inf at high frequency, negative real part below the plasma frequency
    d = physmat.Drude(1.0, wp_ev=9.0, gamma_ev=0.07)
    assert d.eps_of_energy(100.0).real > 0.99
    assert d.eps_of_energy(1.5).real < -30
    assert d.eps_of_energy(1.5).imag > 0
    # index root chosen with k >= 0
    assert d.k(0.8) > 0
    # exact zero-crossing of Re eps for gamma -> 0 at w = wp
    d0 = physmat.Drude(1.0, wp_ev=9.0, gamma_ev=1e-9)
    assert abs(d0.eps_of_energy(9.0).real) < 1e-6
    # round trip through the flat parameter vector
    m = DrudeLorentz(3.0, 8.0, 0.8, 0.05, [(0.1, 2.5, 0.4), (0.5, 3.5, 1.0)])
    assert np.allclose(DrudeLorentz.from_parameters(m.parameters()).eps(np.array([0.5, 1.0])), m.eps(np.array([0.5, 1.0])))


def test_fit_recovers_synthetic_drude_lorentz():
    truth = DrudeLorentz(2.0, 9.0, 1.0, 0.07, [(0.3, 2.8, 0.6)], label="truth")
    wl = np.linspace(0.4, 1.2, 50)
    res = fit_drude_lorentz(truth, wl, n_lorentz=1)
    assert res.rms_eps < 1e-3
    assert np.allclose(res.model.eps(wl), truth.eps(wl), rtol=1e-3, atol=1e-3)


def test_fit_gold_table_is_usable():
    au = physmat.get("Au").optical
    wl = np.linspace(0.4, 1.0, 60)
    res = fit_drude_lorentz(au, wl, n_lorentz=2)
    assert res.max_rel_index < 0.05                     # within 5 % of Johnson & Christy over 400-1000 nm
    assert res.model.eps(wl).imag.min() > 0             # passive by construction
    assert abs(res.model.eps(0.8).real - au.eps(0.8).real) < 1.0


# ---- refractiveindex.info reader --------------------------------------------

def test_rii_record_parsing_on_fixture(tmp_path):
    (tmp_path / "x.yml").write_text(
        "REFERENCES: |\n    test\nDATA:\n  - type: formula 1\n    wavelength_range: 0.21 6.7\n"
        "    coefficients: 0 0.6961663 0.0684043 0.4079426 0.1162414 0.8974794 9.896161\n"
        "  - type: tabulated k\n    data: |\n        0.5 1e-8\n        1.0 2e-8\n        2.0 4e-8\n")
    rec = physmat.rii.load_record(tmp_path / "x.yml")
    assert isinstance(rec.dispersion, physmat.Composite)
    assert abs(rec.dispersion.n(0.5876) - 1.4585) < 1e-4
    assert np.isclose(rec.dispersion.k(1.5), 3e-8)
    assert rec.dispersion.range_um == (0.21, 6.7)          # validity follows the n model


@pytest.mark.skipif(RII_PATH is None, reason="local refractiveindex.info database not found")
def test_rii_database_matches_builtins():
    db = physmat.rii.Database(RII_PATH)
    assert len(db.entries) > 3000
    wl = np.linspace(0.4, 1.9, 9)
    assert np.allclose(db.load("main/SiO2/Malitson").dispersion.n(wl), physmat.get("SiO2").n(wl))
    assert np.allclose(db.load("main/Au/Johnson").dispersion.index(wl), physmat.get("Au").index(wl))
    assert any(e.book == "Si3N4" for e in db.search("silicon nitride"))
    with pytest.raises(KeyError):
        db.load("main/SiO2/nope")


@pytest.mark.skipif(RII_PATH is None, reason="local refractiveindex.info database not found")
def test_rii_every_record_parses():
    db = physmat.rii.Database(RII_PATH)
    for e in db.entries:
        rec = db.get(e.shelf, e.book, e.page)
        lo, hi = rec.dispersion.range_um
        assert np.isfinite(rec.dispersion.index(0.5 * (lo + hi))).all()
