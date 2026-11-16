# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Checks against published values and physical constraints.

The built-in materials are evaluated through the public SI API (vacuum wavelengths in m;
the literature points are the same decimal values as before, now written in metres, and
physmat converts each back to the same micrometre double, decision D31). The model
classes and the fitter are the internal kernels (physmat.kernels, micrometres), tested
as they are.
"""

import os
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

import physmat
from physmat import OutOfRange, kernels
from physmat.kernels import Constant, DrudeLorentz, RIIFormula, Sellmeier, Tabulated, fit_drude_lorentz

# An explicit path must fail if broken, not silently skip the database checks.
RII_PATH = os.environ.get("PHYSMAT_RII_PATH") or next(
    (p for p in (Path("/tmp/rii/database"), Path.home() / ".cache/physmat/rii") if p.exists()), None)


# ---- built-in materials vs literature ---------------------------------------

def n(material, vacuum_wavelength):
    """The real refractive index n of a built-in material (name) or a Material at a vacuum wavelength in m."""
    m = physmat.material(material) if isinstance(material, str) else material
    return m.refractive_index(vacuum_wavelength=vacuum_wavelength).real


def k(material, vacuum_wavelength):
    """The extinction coefficient k of a built-in material (name) or a Material at a vacuum wavelength in m."""
    m = physmat.material(material) if isinstance(material, str) else material
    return m.refractive_index(vacuum_wavelength=vacuum_wavelength).imag


def test_fused_silica_malitson_reference_points():
    sio2 = physmat.material("SiO2")
    assert abs(n(sio2, 5.876e-7) - 1.4585) < 1e-4          # n_d of fused silica (Malitson Table)
    assert abs(n(sio2, 1.55e-6) - 1.4440) < 1e-4
    assert abs(n(sio2, 6.328e-7) - 1.4570) < 1e-4          # HeNe
    assert k(sio2, 1.0e-6) == 0.0


def test_silicon_reference_points():
    assert abs(n("Si", 1.55e-6) - 3.4777) < 2e-4       # Salzberg-Villa
    assert abs(n("Si", 3.0e-6) - 3.4320) < 3e-3         # Salzberg-Villa at 3 um
    si_vis = physmat.material("Si_visible")
    assert abs(n(si_vis, 6.328e-7) - 3.88) < 0.02                   # Green 2008 at HeNe
    assert k(si_vis, 4e-7) > k(si_vis, 1.0e-6) > 0                     # absorption drops toward the band gap


def test_silicon_nitride_and_others():
    assert abs(n("Si3N4", 1.55e-6) - 1.996) < 2e-3      # Luke 2015
    assert abs(n("Al2O3", 5.876e-7) - 1.7681) < 2e-4    # sapphire
    assert abs(n("MgF2", 5.876e-7) - 1.3777) < 2e-4
    assert abs(n("CaF2", 5.876e-7) - 1.4338) < 2e-4
    assert abs(n("GaAs", 1.55e-6) - 3.374) < 5e-3
    assert abs(n("H2O", 5e-7) - 1.335) < 2e-3       # Hale & Querry (water)
    assert n("vacuum", 1.0e-6) == 1.0


def test_gold_johnson_christy_at_800nm():
    au = physmat.material("Au")
    nk = au.refractive_index(vacuum_wavelength=8e-7)
    assert abs(nk.real - 0.15) < 0.02 and abs(nk.imag - 4.9) < 0.1
    eps = au.relative_permittivity(vacuum_wavelength=8e-7)
    assert abs(eps.real + 24.1) < 0.5 and 1.2 < eps.imag < 1.8
    assert au.relative_permittivity(vacuum_wavelength=np.linspace(5e-7, 1.5e-6, 20)).imag.min() > 0   # passive


def test_lookup_is_exact_without_aliases():
    # physmat.material matches names exactly (D34): case folding and aliases are gone; the aliases stay as data
    assert physmat.material("SiO2") is physmat.material("SiO2")
    for wrong in ("fused silica", "sio2", "Silica", "aluminium", "air", "si", "unobtainium"):
        with pytest.raises(KeyError, match="names are exact"):
            physmat.material(wrong)
    assert "silica" in physmat.material("SiO2").aliases and "aluminium" in physmat.material("Al").aliases
    with pytest.raises(TypeError):
        physmat.material(None)
    assert "Si" in physmat.names() and len(physmat.names()) == 19


def test_validity_range_enforced():
    si = physmat.material("Si")                     # Salzberg-Villa valid 1.357-11.04 um
    with pytest.raises(OutOfRange, match=r"valid range \[1.357e-06, 1.104e-05\] m"):
        si.refractive_index(vacuum_wavelength=8e-7)
    assert np.isfinite(si.optical.n(0.8, strict=False))         # the kernel extrapolates on request (micrometres)
    assert si.optical.range_um == (1.357, 11.04)
    assert si.valid_vacuum_wavelength == (1.357e-06, 1.104e-05)  # the same bounds in m (decimal rule)


def test_group_index_silicon():
    # Si near 1.55 um: n_g about 3.6 (well known for bulk silicon); group_index is a kernel method (micrometres)
    ng = physmat.material("Si").optical.group_index(1.55)
    assert 3.55 < ng < 3.65


def test_material_properties_slot():
    si = physmat.material("Si")
    assert si.property("thermal_conductivity", temperature=293.15) == 148.0
    assert si.properties["thermal_conductivity"].unit == "W/(m K)"
    with pytest.raises(KeyError):
        si.property("magic", temperature=293.15)
    with pytest.raises(TypeError):
        si.property("thermal_conductivity")                     # the temperature is required (D35)
    m = physmat.Material("test glass", physmat.constant_model(refractive_index=1.5), "user-defined")
    assert n(m, 5e-7) == 1.5 and m.relative_permittivity(vacuum_wavelength=5e-7) == 2.25


def test_the_public_api_takes_si_numbers_only():
    si = physmat.material("Si")
    for call in (lambda: si.refractive_index(vacuum_wavelength="1.55 um"),
                 lambda: si.relative_permittivity(vacuum_wavelength=["1.55e-6"]),
                 lambda: si.property("thermal_conductivity", temperature="300 K"),
                 lambda: physmat.constant_model(refractive_index="1.5"),
                 lambda: physmat.metal_thermal_conductivity("Cu", temperature=np.array(["300"]),
                                                            residual_resistivity_ratio=100.0)):
        with pytest.raises(TypeError, match="SI numbers only"):
            call()
    with pytest.raises(TypeError):
        si.refractive_index(1.55e-6)                            # keyword-only
    with pytest.raises(TypeError, match=r"physmat.units.q\('1550 nm', 'vacuum_wavelength'\)"):
        si.refractive_index(vacuum_wavelength="1550 nm")


def test_vacuum_wavelength_in_metres_gives_the_kernels_micrometre_double():
    # D31: float(Fraction(repr(x)) * 10**6) per element; x * 1e6 would miss 0.8, 1.45, 1.6 and 1.65 um
    si, sio2 = physmat.material("Si"), physmat.material("SiO2")
    for um, m in ((0.8, 8e-7), (1.45, 1.45e-6), (1.55, 1.55e-6), (1.6, 1.6e-6), (1.65, 1.65e-6), (0.5876, 5.876e-7)):
        assert sio2.refractive_index(vacuum_wavelength=m) == sio2.optical.index(um)
        if um > 1.357:
            assert si.relative_permittivity(vacuum_wavelength=m) == si.optical.eps(um)
    assert 1.45e-6 * 1e6 != 1.45                                 # the float product misses
    wl = np.array([[1.5e-6, 1.55e-6], [1.6e-6, 1.65e-6]])
    assert sio2.refractive_index(vacuum_wavelength=wl).shape == (2, 2)
    assert np.array_equal(sio2.refractive_index(vacuum_wavelength=wl), sio2.optical.index([[1.5, 1.55], [1.6, 1.65]]))


def test_model_constructors_build_the_kernels():
    c = physmat.constant_model(refractive_index=complex(1.5, -0.0))
    assert isinstance(c, kernels.Constant) and c.n0 == 1.5 and np.signbit(c.k0)     # the signed zero is kept
    assert physmat.Material("c", c).refractive_index(vacuum_wavelength=1e-6).tobytes() == \
        kernels.Constant(1.5, -0.0).index(1.0).tobytes()                              # evaluated as n0 + 1j*k0
    # Malitson's fused silica as sellmeier_model: C in m^2 or the resonance wavelength in m give the kernel's um^2
    b = [0.6961663, 0.4079426, 0.8974794]
    s1 = physmat.sellmeier_model(strength=b, resonance_wavelength=[6.84043e-8, 1.162414e-7, 9.896161e-6],
                                 valid_vacuum_wavelength=(2.1e-7, 6.7e-6))
    s2 = physmat.sellmeier_model(strength=b, resonance_wavelength_squared=[4.67914825849e-15, 1.351206307396e-14,
                                                                           9.7934002537921e-11])
    assert isinstance(s1, kernels.Sellmeier) and s1.range_um == (0.21, 6.7) and s2.range_um == (0.0, np.inf)
    assert s1.C == [float(Fraction(r) ** 2) for r in ("0.0684043", "0.1162414", "9.896161")]   # exact square, rounded once
    assert s2.C == [0.00467914825849, 0.01351206307396, 97.934002537921] and s2.A == 1.0
    wl = np.linspace(2.1e-7, 6.7e-6, 50)
    ref = physmat.material("SiO2").refractive_index(vacuum_wavelength=wl)
    assert np.allclose(physmat.Material("s1", s1).refractive_index(vacuum_wavelength=wl), ref, rtol=1e-14, atol=0)
    assert physmat.sellmeier_model(strength=[1.0], resonance_wavelength=[1e-7],
                                   valid_vacuum_wavelength=(None, 2e-6)).range_um == (0.0, 2.0)
    for bad in (dict(strength=b), dict(strength=b, resonance_wavelength=[1e-7], resonance_wavelength_squared=[1e-14]),
                dict(strength=b, resonance_wavelength=[1e-7]), dict(strength=[], resonance_wavelength=[])):
        with pytest.raises(ValueError):
            physmat.sellmeier_model(**bad)


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
    d = kernels.Drude(1.0, wp_ev=9.0, gamma_ev=0.07)
    assert d.eps_of_energy(100.0).real > 0.99
    assert d.eps_of_energy(1.5).real < -30
    assert d.eps_of_energy(1.5).imag > 0
    # index root chosen with k >= 0
    assert d.k(0.8) > 0
    # exact zero-crossing of Re eps for gamma -> 0 at w = wp
    d0 = kernels.Drude(1.0, wp_ev=9.0, gamma_ev=1e-9)
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
    au = physmat.material("Au").optical
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
    assert isinstance(rec.dispersion, kernels.Composite)
    assert abs(rec.dispersion.n(0.5876) - 1.4585) < 1e-4
    assert np.isclose(rec.dispersion.k(1.5), 3e-8)
    assert rec.dispersion.range_um == (0.21, 6.7)          # validity follows the n model


@pytest.mark.skipif(RII_PATH is None, reason="local refractiveindex.info database not found")
def test_rii_database_matches_builtins():
    db = physmat.rii.Database(RII_PATH)
    assert len(db.entries) > 3000
    wl = np.linspace(0.4, 1.9, 9)
    assert np.allclose(db.load("main/SiO2/Malitson").dispersion.n(wl), physmat.material("SiO2").optical.n(wl))
    assert np.allclose(db.load("main/Au/Johnson").dispersion.index(wl), physmat.material("Au").optical.index(wl))
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
