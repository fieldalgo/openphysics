# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Ciddor (1996) moist air against independent published values and physical limits.

References used below
---------------------
* NIST Engineering Metrology Toolbox, "Refractive Index of Air Calculator",
  documentation Table 1 (J. A. Stone and J. H. Zimmerman), https://emtoolbox.nist.gov/Wavelength/Documentation.asp:
  n at 633, 300 and 1700 nm for several (t, p, RH) at 450 umol/mol CO2, computed by NIST's
  implementation of the Ciddor equation and of the modified Edlen equation (Birch & Downs 1994
  with NIST's 292.75/T water-vapour factor), tabulated to 1e-9. NIST uses the IAPWS saturation
  vapour pressure where Ciddor uses Davis (1992); the two differ by 0.4 Pa at 20 C.
* K. P. Birch and J. A. Downs, "Correction to the updated Edlen equation for the refractive index
  of air", Metrologia 31, 315-316 (1994): the modified Edlen equation, implemented here as an
  independent model of dry and moist air.
* P. E. Ciddor, Appl. Opt. 35, 1566 (1996), Appendix A: Z_a = 0.9995922115 for standard dry air and
  rho_ws = 0.00985938 kg/m^3 for water vapour at 20 C, 1333 Pa are published constants that the
  density equations must reproduce.
"""

import numpy as np
import pytest

import physmat
from physmat import OutOfRange, air

# (t [C], RH [%], p [kPa], wavelength [nm], n Ciddor, n modified Edlen): NIST Table 1, 450 umol/mol CO2
NIST_TABLE_1 = [
    (20, 0, 101.325, 633, 1.000271800, 1.000271799),
    (20, 0, 60, 633, 1.000160924, 1.000160920),
    (20, 0, 120, 633, 1.000321916, 1.000321918),
    (50, 0, 100, 633, 1.000243285, 1.000243270),
    (5, 0, 100, 633, 1.000282756, 1.000282750),
    (-40, 0, 100, 633, 1.000337580, 1.000337471),
    (50, 100, 120, 633, 1.000287924, 1.000287864),
    (40, 75, 120, 633, 1.000299418, 1.000299406),
    (20, 100, 100, 633, 1.000267394, 1.000267394),
    (40, 100, 110, 1700, 1.000270247, 1.000270237),
    (20, 0, 101.325, 1700, 1.000268479, 1.000268483),
    (40, 100, 110, 300, 1.000289000, 1.000288922),
    (20, 0, 101.325, 300, 1.000286581, 1.000286579),
    (-40, 0, 120, 300, 1.000427233, 1.000427072),
]


def birch_downs_1994(wavelength_um, temperature_c, pressure_pa, humidity):
    """Modified Edlen equation of Birch & Downs (1994) for 450 ppm CO2, NIST form of the water term.

    (n_s - 1) 1e8 = 8342.54 + 2406147 / (130 - s^2) + 15998 / (38.9 - s^2)
    (n_tp - 1) = (n_s - 1) p [1 + 1e-8 (0.601 - 0.00972 t) p] / [96095.43 (1 + 0.003661 t)]
    n_tpf = n_tp - 1e-10 (292.75 / T) (3.7345 - 0.0401 s^2) p_v
    The 292.75 / T factor is NIST's temperature correction of the water term; it is 1 at 19.6 C
    and does not act on the dry points.
    """
    s2 = 1.0 / wavelength_um ** 2
    ns1 = 1e-8 * (8342.54 + 2406147 / (130 - s2) + 15998 / (38.9 - s2))
    t = temperature_c
    ntp1 = pressure_pa * ns1 * (1 + 1e-8 * (0.601 - 0.00972 * t) * pressure_pa) / (96095.43 * (1 + 0.003661 * t))
    pv = humidity * air.saturation_vapour_pressure(t)
    return 1 + ntp1 - 1e-10 * (292.75 / (t + 273.15)) * (3.7345 - 0.0401 * s2) * pv


# ---- published values ------------------------------------------------------------

@pytest.mark.parametrize("t, rh, p_kpa, wl_nm, n_ciddor, n_edlen", NIST_TABLE_1)
def test_ciddor_matches_nist_toolbox_table(t, rh, p_kpa, wl_nm, n_ciddor, n_edlen):
    # NIST tabulates to 1e-9; the Davis/IAPWS vapour-pressure difference adds < 1e-9 at 100 % RH.
    # Measured |difference| over the 14 rows: max 0.75e-9 (Ciddor), 0.61e-9 (Edlen check), 2026-11-02.
    n = air.refractive_index(wl_nm * 1e-3, t, p_kpa * 1e3, humidity=rh / 100, strict=False)
    assert abs(n - n_ciddor) < 1.5e-9
    # the independent Edlen implementation of this test reproduces NIST's Edlen column as well
    assert abs(birch_downs_1994(wl_nm * 1e-3, t, p_kpa * 1e3, rh / 100) - n_edlen) < 1.5e-9


def test_ciddor_and_birch_downs_agree_at_ambient_conditions():
    # Birch & Downs claim 3e-8 (3 sigma) for 350-650 nm at ambient conditions; NIST Table 1 reports
    # Ciddor - Edlen differences of 0.1-1.5e-8 there. Dry air at 20 C, 101325 Pa, 633 nm: both 2.718e-4.
    # Measured here (2026-11-02): 0.9e-9 at the standard point, at most 5.7e-9 over the eight points.
    for wl, t, p, h in ((0.633, 20, 101325, 0.0), (0.633, 20, 60e3, 0.0), (0.633, 20, 120e3, 0.0),
                        (0.633, 5, 100e3, 0.0), (0.633, 20, 100e3, 1.0), (0.5, 25, 101325, 0.4),
                        (0.35, 15, 101325, 0.0), (0.65, 30, 90e3, 0.6)):
        n = air.refractive_index(wl, t, p, humidity=h, strict=False)       # 60 kPa is outside Ciddor's range
        assert abs(n - birch_downs_1994(wl, t, p, h)) < 1.5e-8
    assert abs(air.refractive_index(0.633, 20, 101325) - 1 - 2.71800e-4) < 1e-9


def test_published_constants_reproduced_by_the_density_equations():
    # Ciddor App. A: Z_a of standard dry air (15 C, 101325 Pa) and rho_ws of water vapour (20 C, 1333 Pa)
    assert abs(air.compressibility(15.0, 101325.0, 0.0) - 0.9995922115) < 1e-10
    rho_ws = 1333.0 * 0.018015 / (air.compressibility(20.0, 1333.0, 1.0) * 8.314510 * 293.15)
    assert abs(rho_ws - 0.00985938) < 5e-9
    # saturation vapour pressure vs NIST Table 2 (IAPWS, rounded to 1 Pa): 20 C 2339, 40 C 7384, 50 C 12351
    svp = air.saturation_vapour_pressure(np.array([20.0, 40.0, 50.0]))
    assert np.all(np.abs(svp - [2339, 7384, 12351]) < 1.5)
    # dry air density at 20 C, 101325 Pa, 400 ppm CO2: 1.2041 kg/m^3 (CIPM-81/91; handbook 1.204)
    assert abs(air.density(20.0, 101325.0, co2_ppm=400.0) - 1.2041) < 5e-4


# ---- limiting behaviour -------------------------------------------------------------

def test_limits_in_pressure_temperature_humidity_and_co2():
    p = np.array([1.0, 1e3, 20e3, 60e3, 80e3, 101325.0, 120e3, 140e3])
    r = air.refractivity(0.633, 20.0, p, strict=False)
    assert r[0] < 3e-9 and np.all(np.diff(r) > 0)                       # n -> 1 as p -> 0, monotonic in p
    assert abs(air.refractive_index(0.633, 20.0, 1e-6, strict=False) - 1) < 1e-14
    t = np.linspace(-40, 100, 15)
    assert np.all(np.diff(air.refractivity(0.633, t, 101325.0)) < 0)   # n falls with T at fixed p
    # adding water vapour at fixed p lowers n in the visible (Edlen's negative humidity term)
    assert air.refractivity(0.633, 20, 101325, humidity=1.0) < air.refractivity(0.633, 20, 101325, humidity=0.0)
    # more CO2 raises n (Eq. 12), with 0.534e-6 per ppm of n - 1 at the same density
    assert air.refractivity(0.633, co2_ppm=2000) > air.refractivity(0.633, co2_ppm=0)
    # normal dispersion: n decreases with wavelength
    wl = np.linspace(0.3, 1.69, 50)
    assert np.all(np.diff(air.refractivity(wl)) < 0)
    # the partial-pressure route equals the relative-humidity route
    pv = 0.5 * air.saturation_vapour_pressure(20.0)
    assert np.isclose(air.refractive_index(0.633, 20, 101325, vapour_pressure_pa=pv),
                      air.refractive_index(0.633, 20, 101325, humidity=0.5), rtol=0, atol=1e-15)


# ---- physmat API ----------------------------------------------------------------------

def test_standard_air_material_and_registry():
    std = physmat.get("standard air")
    assert std is physmat.get("standard_air") is physmat.get("Ciddor air")
    assert physmat.get("air").n(1.0) == 1.0                              # the vacuum alias is unchanged
    assert "Ciddor" in std.source and std.range_um == (0.3, 1.69)
    assert np.isclose(std.n(0.633), air.refractive_index(0.633), rtol=0, atol=1e-15)
    assert std.k(0.633) == 0.0 and np.isclose(std.eps(0.633).real, std.n(0.633) ** 2)
    assert "standard_air" in physmat.names()
    m = physmat.standard_air(20.0, 101325.0, humidity=0.5, co2_ppm=400.0)
    assert np.isclose(m.n(0.633), air.refractive_index(0.633, 20.0, 101325.0, 0.5, 400.0), rtol=0, atol=1e-15)
    assert np.isclose(m.optical.at(humidity=0.0).n(0.633), air.refractive_index(0.633, 20.0, 101325.0), atol=1e-15)
    assert 0.011 < m.optical.water_mole_fraction < 0.012                # 0.5 * 2339 Pa * f / 101325 Pa
    # the density Property follows the package convention (kelvin) at the material's p, RH and CO2
    assert np.isclose(m.get("density", 293.15), air.density(20.0, 101325.0, 0.5, 400.0))
    assert m.properties["density"].unit == "kg/m^3"
    assert 1.19 < m.get("density") < 1.21
    assert m.optical.group_index(0.633) > m.n(0.633)                     # normal dispersion


def test_validity_checks():
    std = physmat.get("standard_air")
    with pytest.raises(OutOfRange):
        std.n(2.0)
    assert np.isfinite(std.n(2.0, strict=False))
    for bad in ({"temperature_c": 120.0}, {"pressure_pa": 50e3}, {"humidity": 1.2}, {"co2_ppm": 3000.0}):
        with pytest.raises(OutOfRange):
            physmat.standard_air(**bad)
        physmat.standard_air(strict=False, **bad)                       # extrapolation on request
    with pytest.raises(OutOfRange):
        physmat.standard_air(20.0, vapour_pressure_pa=5000.0)           # above saturation at 20 C
    with pytest.raises(ValueError):
        physmat.standard_air(20.0, humidity=-0.1)
    with pytest.raises(ValueError):
        physmat.standard_air(20.0, humidity=0.5, vapour_pressure_pa=1000.0)
    with pytest.raises(ValueError):
        physmat.standard_air(20.0, 1000.0, vapour_pressure_pa=2000.0, strict=False)   # p_v > p
    with pytest.raises(ValueError):
        air.refractive_index(0.633, pressure_pa=0.0, strict=False)
