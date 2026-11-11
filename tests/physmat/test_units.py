# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""physmat.units: quantity registry and exact unit converter.

Pre-registered checks R1..R12 (fixed before the implementation; never weakened):

R1  exactness: every menu unit of every quantity converts sample decimals to
    float(Fraction(text) * exact factor) (+ the degC offset) bit for bit; "200 GPa",
    "200000 MPa" and "2e11 Pa" give the same double; "25 degC" == 298.15.
R2  no quantity menu holds two spellings equal under str.casefold().
R3  the frozen spelling table equals the generator output byte for byte; the generator
    is deterministic.
R4  every entry of the character alias map is covered by a table-driven test.
R5  every known-refused entry yields its code and its reading.
R6  degC only as the whole unit of an absolute temperature: in a compound
    E-DEGC-NOT-ABSOLUTE with a meaning-preserving K fix; for a difference quantity a
    suggestion only, never a fix.
R7  thermal_conductivity "58 MS/m" -> E-UNIT-DIMENSION naming electrical_conductivity.
R8  "1e400 Pa" and "1e-330 m" -> E-DOMAIN.
R9  physmat.units imports only the standard library (works with numpy and scipy blocked).
R10 q() returns an SI float and q_array() an SI list; a bare number only for a
    dimensionless quantity.
R11 registry self-checks: each canonical unit is on its menu; every menu unit has the
    quantity's dimension.
R12 the existing tests/physmat tests pass unchanged.

The test_p2_* tests check the registry additions and converter API of the step-2 specification
(R-1..R-32 of its section 6) that belong to physmat; their expected values are written from that
specification and from the refractiveindex.info records, not read from quantities.json.

The exact factors below are an independent table written from the SI definitions
(exact 2019 SI e, international inch and pound-force, 101325 Pa atmosphere, 40-digit pi),
not read from the registry. Float comparisons are exact on purpose: every expected value
is one correctly rounded division of the same rational number.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import struct
import subprocess
import sys
import unicodedata
from decimal import Decimal
from fractions import Fraction
from importlib import resources
from pathlib import Path

import pytest

from physmat import units
from physmat.units import UnitError, UnitWarning, convert, length_to_pm, q, q_array

F = Fraction
PI_40 = F("3.141592653589793238462643383279502884197")
INCH = F("0.0254")
LBF = F("4.4482216152605")
PSI = LBF / INCH ** 2
EV = F("1.602176634e-19")

D = {"L": "L", "M": "M", "T": "T", "TH": "Theta", "I": "I", "1": "", "Hz": "T-1", "N": "M L T-2", "Pa": "M L-1 T-2",
     "J": "M L2 T-2", "W": "M L2 T-3", "V": "M L2 T-3 I-1", "Ohm": "M L2 T-3 I-2", "S": "M-1 L-2 T3 I2",
     "F": "M-1 L-2 T4 I2", "H": "M L2 T-2 I-2", "C": "I T", "mol": "N", "Tesla": "M T-2 I-1", "Wb": "M L2 T-2 I-1",
     "dB": "dB"}
# symbol: (exact factor to coherent SI, dimension key, angle exponent)
SYMBOLS = {}
for _prefix, _f in (("p", "1e-12"), ("n", "1e-9"), ("u", "1e-6"), ("m", "1e-3"), ("c", "1e-2"), ("", "1"),
                    ("k", "1e3")):
    SYMBOLS[_prefix + "m"] = (F(_f), "L", 0)
SYMBOLS.update({"Angstrom": (F("1e-10"), "L", 0), "in": (INCH, "L", 0), "mil": (INCH / 1000, "L", 0),
                "mg": (F("1e-6"), "M", 0), "g": (F("1e-3"), "M", 0), "kg": (F(1), "M", 0),
                "fs": (F("1e-15"), "T", 0), "ps": (F("1e-12"), "T", 0), "ns": (F("1e-9"), "T", 0),
                "us": (F("1e-6"), "T", 0), "ms": (F("1e-3"), "T", 0), "s": (F(1), "T", 0), "min": (F(60), "T", 0),
                "h": (F(3600), "T", 0), "mK": (F("1e-3"), "TH", 0), "K": (F(1), "TH", 0), "degC": (F(1), "TH", 0),
                "uA": (F("1e-6"), "I", 0), "mA": (F("1e-3"), "I", 0), "A": (F(1), "I", 0), "kA": (F(1000), "I", 0),
                "urad": (F("1e-6"), "1", 1), "mrad": (F("1e-3"), "1", 1), "rad": (F(1), "1", 1),
                "deg": (PI_40 / 180, "1", 1), "Hz": (F(1), "Hz", 0), "kHz": (F(10**3), "Hz", 0),
                "MHz": (F(10**6), "Hz", 0), "GHz": (F(10**9), "Hz", 0), "THz": (F(10**12), "Hz", 0),
                "mN": (F("1e-3"), "N", 0), "N": (F(1), "N", 0), "kN": (F(1000), "N", 0),
                "Pa": (F(1), "Pa", 0), "kPa": (F(10**3), "Pa", 0), "hPa": (F(100), "Pa", 0),
                "MPa": (F(10**6), "Pa", 0), "GPa": (F(10**9), "Pa", 0), "bar": (F(10**5), "Pa", 0),
                "mbar": (F(100), "Pa", 0), "atm": (F(101325), "Pa", 0), "psi": (PSI, "Pa", 0),
                "ksi": (PSI * 1000, "Pa", 0), "barg": (F(10**5), "Pa", 0),
                "psig": (PSI, "Pa", 0), "bara": (F(10**5), "Pa", 0), "psia": (PSI, "Pa", 0),
                "meV": (EV / 1000, "J", 0), "eV": (EV, "J", 0), "mJ": (F("1e-3"), "J", 0), "J": (F(1), "J", 0),
                "kJ": (F(1000), "J", 0), "MJ": (F(10**6), "J", 0), "1": (F(1), "1", 0), "%": (F(1, 100), "1", 0),
                "ppm": (F(1, 10**6), "1", 0), "dB": (F(1), "dB", 0), "mol": (F(1), "mol", 0),
                "mT": (F("1e-3"), "Tesla", 0), "T": (F(1), "Tesla", 0), "Wb": (F(1), "Wb", 0)})
for _base, _key, _prefixes in (("W", "W", "p n u m _ k"), ("V", "V", "u m _ k"), ("Ohm", "Ohm", "n u m _ k"),
                               ("S", "S", "u m _ k M"), ("F", "F", "f p n u _"), ("H", "H", "p n u m _"),
                               ("C", "C", "p n u m _")):
    for _p in _prefixes.split():
        _scale = {"f": "1e-15", "p": "1e-12", "n": "1e-9", "u": "1e-6", "m": "1e-3", "_": "1", "k": "1e3",
                  "M": "1e6"}[_p]
        SYMBOLS[("" if _p == "_" else _p) + _base] = (F(_scale), _key, 0)


def dim_of(key: str) -> dict:
    out = {}
    for item in D[key].split():
        name = item.rstrip("-0123456789")
        out[name] = int(item[len(name):] or 1)
    return out


def parse_unit(text: str) -> list[tuple[str, int | Fraction]]:
    """Independent reading of a canonical unit: [(symbol or integer, signed exponent)]; a
    half-integer exponent is written in parentheses (``1/m^(3/2)``)."""
    num, slash, den = text.partition("/")
    if den.startswith("("):
        den = den[1:-1]
    factors = []
    for sign, part in ((1, num), (-1, den)):
        if sign == 1 and part == "1":
            continue
        for item in part.split():
            sym, _, exp = item.partition("^")
            power = F(exp[1:-1]) if exp.startswith("(") else int(exp or 1)
            factors.append((sym, sign * power))
    return factors


def exact_power(f: Fraction, exp: int | Fraction) -> Fraction:
    """f**exp exactly; a half-integer power occurs only on a factor of 1 (output units in m^(1/2))."""
    if F(exp).denominator == 1:
        return f ** int(exp)
    assert f == 1, (f, exp)
    return F(1)


def expected_unit(text: str) -> tuple[Fraction, dict, int]:
    """Exact factor, dimension and angle exponent of a canonical unit from the independent table."""
    factor, dim, angle = F(1), {}, 0
    for sym, exp in parse_unit(text):
        if sym.isdigit():
            factor *= exact_power(F(int(sym)), exp)
            continue
        f, key, a = SYMBOLS[sym]
        factor *= exact_power(f, exp)
        angle += a * exp
        for k, v in dim_of(key).items():
            dim[k] = dim.get(k, 0) + v * exp
    return factor, {k: v for k, v in dim.items() if v}, angle


def bits(x: float) -> bytes:
    return struct.pack("<d", x)


def registry() -> dict:
    return json.loads(resources.files("physmat").joinpath("quantities.json").read_text(encoding="utf-8"))


def tables() -> dict:
    return json.loads(resources.files("physmat").joinpath("unit_tables.json").read_text(encoding="utf-8"))


BASES = sorted(registry()["quantities"])
# Menu units whose factor equals the canonical one: degC differs by its offset, the rest are
# other spellings of factor 1 (mA/mm = A/m).
SAME_FACTOR = {"degC", "mA/mm", "mJ/mm", "mOhm/mm", "mW/mm"}
SAMPLES = ["0", "1", "0.1", "0.3", "2.5", "-2.5", "12.75", "1e-3", "7e-7", "-3.75e-4", "123456.789", "6.02e23"]


def exact_bound(text: str, canonical: str) -> Fraction:
    number, _, unit = text.partition(" ")
    if not unit:
        return F(number)
    return F(number) * expected_unit(unit)[0] / expected_unit(canonical)[0]


def in_domain(v: Fraction, domain: dict | None, canonical: str) -> bool:
    for key, text in (domain or {}).items():
        b = exact_bound(text, canonical)
        if not {"min": v >= b, "min_exclusive": v > b, "max": v <= b, "max_exclusive": v < b}[key]:
            return False
    return True


# ---- R1 exactness ---------------------------------------------------------------------------------

@pytest.mark.parametrize("base", BASES)
def test_r1_every_menu_unit_converts_exactly(base):
    entry = registry()["quantities"][base]
    canonical = entry["unit"]
    c_factor = expected_unit(canonical)[0]
    for unit in entry["menu"]:
        factor = expected_unit(unit)[0]
        offset = F(27315, 100) if unit == "degC" else F(0)
        if unit not in ("1", canonical):
            # Not vacuous: a unit with the canonical factor is one of these reviewed identities.
            assert factor != c_factor or unit in SAME_FACTOR, unit
        for text in SAMPLES:
            value = Decimal(text) if unit == "1" else f"{text} {unit}"
            got = convert(value, base)
            exact = (F(text) * factor + offset) / c_factor
            integer = "." not in text and "e" not in text
            if entry["kind"] == "count" and not integer or not in_domain(exact, entry["domain"], canonical):
                assert got.error is not None and got.error.code == "E-DOMAIN", (base, value, got)
                continue
            assert got.ok, (base, value, got.error)
            assert bits(got.value) == bits(float(exact)), (base, value, got.value, float(exact))
            assert got.exact == exact


def test_r1_same_value_from_different_units_is_bit_identical():
    a, b, c = q("200 GPa", "youngs_modulus"), q("200000 MPa", "youngs_modulus"), q("2e11 Pa", "youngs_modulus")
    assert bits(a) == bits(b) == bits(c) == bits(2e11)
    assert q("25 degC", "temperature") == 298.15 == float(F(29815, 100))
    assert q("25 degC", "ambient_temperature") == q("298.15 K", "ambient_temperature")
    assert q("12 ppm/K", "linear_expansion_coefficient") == q("1.2e-5 1/K", "linear_expansion_coefficient") \
        == q("12 um/(m K)", "linear_expansion_coefficient")
    assert q("1550 nm", "vacuum_wavelength") == 1.55e-06 == q("1.55 um", "vacuum_wavelength")
    assert q("10 MPa", "gauge_pressure") == 1e7
    assert q("180 deg", "rotation") == math.pi
    assert q("2 dB/(180 deg)", "bend_loss") == 1.0       # rational, never through pi


def test_r1_registry_factors_match_the_independent_table():
    t = tables()
    for unit, rec in t["units"].items():
        factor, dim, angle = expected_unit(unit)
        assert F(rec["factor"]) == factor, unit
        assert rec["dimension"] == dim, unit
        assert rec["angle"] == angle, unit
        assert ("offset" in rec) == (unit == "degC")
    assert F(t["units"]["degC"]["offset"]) == F("273.15")
    assert F(t["units"]["psi"]["factor"]) == F(44482216152605, 6451600000)
    assert set(SYMBOLS) == set(registry()["symbols"])          # the closed symbol list, entry by entry


def test_r1_float_inputs_are_read_as_their_decimal_text():
    # A Python float in a tagged array means its shortest repr, as the JSON text does.
    assert q_array({"unit": "nm", "values": [0.1]}, "length") == [float(F("0.1") * F("1e-9"))]
    assert q_array({"unit": "nm", "values": [Decimal("0.1")]}, "length") == q_array({"unit": "nm", "values": [0.1]},
                                                                                        "length")


# ---- R2 case collisions --------------------------------------------------------------------------

def test_r2_no_menu_holds_two_spellings_equal_under_casefold():
    t = tables()
    by_unit = {}
    for s, u in t["spellings"].items():
        by_unit.setdefault(u, []).append(s)
    for base, entry in registry()["quantities"].items():
        seen = {}
        for unit in entry["menu"]:
            for s in by_unit.get(unit, []):
                assert seen.setdefault(s.casefold(), s) == s, (base, seen[s.casefold()], s)


def test_r2_case_slips_are_named_not_converted():
    err = convert("10 mPa", "youngs_modulus").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "millipascal" in err.message
    assert [s.value for s in err.suggestions][0] == "10 MPa"
    err = convert("10 mS/m", "electrical_conductivity").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "S/m kS/m MS/m S/cm" in err.message
    assert err.suggestions[0].value == "10 MS/m" and err.suggestions[0].si_after == 1e7
    err = convert("2 MW", "heat_rate").error
    assert "megawatt" in err.message and {s.value for s in err.suggestions} == {"2 mW", "2000 kW"}
    assert "MS/m" in units.menu("electrical_conductivity") and "mS/m" not in units.menu("electrical_conductivity")


# ---- R3 frozen tables ----------------------------------------------------------------------------

def test_r3_frozen_tables_equal_the_generator_output_byte_for_byte():
    frozen = resources.files("physmat").joinpath("unit_tables.json").read_bytes()
    assert units.generate_tables().encode("utf-8") == frozen
    assert units.generate_tables() == units.generate_tables()


def test_r3_generator_is_deterministic_across_hash_seeds(tmp_path):
    src = str(Path(units.__file__).resolve().parents[1])
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import physmat.units as u; "
            "sys.stdout.buffer.write(u.generate_tables().encode('utf-8'))")
    outputs = []
    for seed in ("0", "1", "4242"):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED", "PYTHONSTARTUP")}
        env["PYTHONHASHSEED"] = seed
        run = subprocess.run([sys.executable, "-B", "-c", code, src], cwd=tmp_path, env=env, capture_output=True,
                             timeout=300, check=True)
        outputs.append(run.stdout)
    frozen = resources.files("physmat").joinpath("unit_tables.json").read_bytes()
    assert outputs[0] == outputs[1] == outputs[2] == frozen


def test_r3_spelling_grammar():
    s = tables()["spellings"]
    for text in ("W/(m K)", "W/(m*K)", "W/m/K", "W m^-1 K^-1", "W/(K m)", "W*m^-1*K^-1"):
        assert s[text] == "W/(m K)", text
    for text in ("W/mK", "W/m K", "W/m^2 K", "Nm", "Ohmm", "J/kgK", "kWh"):
        assert text not in s and tables()["refused"][text]["code"] == "E-UNIT-AMBIGUOUS", text
    assert "1" not in s                                      # dimensionless values are bare numbers
    readings = {r["unit"] for r in tables()["refused"]["W/mK"]["readings"]}
    assert readings == {"W/(m K)", "W/mK"}                   # metre kelvin, or per millikelvin


# ---- R4 character aliases -------------------------------------------------------------------------

ALIASES = [  # (characters, replacement, sample, quantity, ASCII equivalent)
    ("\u00b5", "u", "3 \u00b5m", "length", "3 um"),
    ("\u03bc", "u", "3 \u03bcm", "length", "3 um"),
    ("\u03a9", "Ohm", "5 k\u03a9", "resistance", "5 kOhm"),
    ("\u2126", "Ohm", "5 k\u2126", "resistance", "5 kOhm"),
    ("\u00c5", "Angstrom", "5 \u00c5", "length", "5 Angstrom"),
    ("\u212b", "Angstrom", "5 \u212b", "length", "5 Angstrom"),
    ("\u212a", "K", "300 \u212a", "temperature", "300 K"),
    ("\u00b0C", "degC", "25 \u00b0C", "temperature", "25 degC"),
    ("\u2103", "degC", "25 \u2103", "temperature", "25 degC"),
    ("\u00b0", "deg", "8 \u00b0", "incidence_angle", "8 deg"),
    ("\u339a", "nm", "220 \u339a", "length", "220 nm"),
    ("\u339b", "um", "3 \u339b", "length", "3 um"),
    ("\u339c", "mm", "3 \u339c", "length", "3 mm"),
    ("\u339d", "cm", "3 \u339d", "length", "3 cm"),
    ("\u339e", "km", "3 \u339e", "length", "3 km"),
    ("\u339f", "mm^2", "4 \u339f", "area", "4 mm^2"),
    ("\u33a0", "cm^2", "4 \u33a0", "area", "4 cm^2"),
    ("\u33a1", "m^2", "4 \u33a1", "area", "4 m^2"),
    ("\u2212", "-", "\u22125 MPa", "traction", "-5 MPa"),
    ("\u00b7", " ", "148 W/(m\u00b7K)", "thermal_conductivity", "148 W/(m K)"),
    ("\u22c5", " ", "148 W/(m\u22c5K)", "thermal_conductivity", "148 W/(m K)"),
]
SUPERSCRIPTS = {"\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2074": "4", "\u2075": "5",
                "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9", "\u207b": "-"}
SPACES = ["\u00a0", "\u2007", "\u2009", "\u200a", "\u202f"]


def test_r4_the_alias_map_is_exactly_the_tested_table():
    reg = registry()
    assert [tuple(p) for p in reg["character_aliases"]] == [(a, b) for a, b, *_ in ALIASES]
    assert reg["superscripts"] == SUPERSCRIPTS
    assert reg["spaces"] == SPACES
    assert [unicodedata.name(c) for c in "\u339a\u33a1"] == ["SQUARE NM", "SQUARE M SQUARED"]


@pytest.mark.parametrize("chars, replacement, sample, name, ascii_text", ALIASES)
def test_r4_each_character_alias(chars, replacement, sample, name, ascii_text):
    assert units.normalize(sample) == ascii_text
    assert bits(q(sample, name)) == bits(q(ascii_text, name))


@pytest.mark.parametrize("char", sorted(SUPERSCRIPTS))
def test_r4_each_superscript(char):
    assert units.normalize(f"1 m{char}") == f"1 m^{SUPERSCRIPTS[char]}"


def test_r4_superscript_units_convert():
    assert q("2 m\u00b2", "area") == 2.0 and q("1 mm\u00b3", "volume") == 1e-9
    assert q("10 W m\u207b\u00b2 K\u207b\u00b9", "heat_transfer_coefficient") == 10.0
    assert units.normalize("1 m\u00b9\u2070") == "1 m^10"
    assert q("1e\u22123 m", "length") == 1e-3                    # U+2212 in an exponent


@pytest.mark.parametrize("space", SPACES)
def test_r4_each_space(space):
    assert units.normalize(f"5{space}mm") == "5 mm"
    assert q(f"148{space}W/(m{space}K)", "thermal_conductivity") == 148.0


def test_r4_no_unicode_normalisation_and_attached_forms():
    assert units.normalize("4 m\u00b2") == "4 m^2"              # NFKC would give "m2", which is refused
    assert convert("4 m2", "area").error.code == "E-UNIT-NOT-ACCEPTED"
    assert convert("\uff15 mm", "length").error.code == "E-UNIT-UNKNOWN"   # fullwidth digit is not mapped
    assert units.normalize("5   mm") == "5 mm" and units.normalize(" 5 mm ") == "5 mm"
    for attached, spaced in (("40%", "40 %"), ("25\u00b0C", "25 degC"), ("8\u00b0", "8 deg"), ("\u22125\u00b0C", "-5 degC")):
        assert units.normalize(attached) == spaced
    assert q("40%", "relative_humidity") == 0.4 and q("25\u00b0C", "temperature") == 298.15
    assert q("25 \u2103", "temperature") == 298.15 and q("220 \u339a", "length") == 2.2e-07
    # Only the three attached forms of 3.1: "25\u2103" is a glued unit, refused with a fix that keeps the value.
    assert units.normalize("25\u2103") == "25degC"
    err = convert("25\u2103", "temperature").error
    assert err.code == "E-UNIT-UNKNOWN" and err.fix.value == "25 degC" and q(err.fix.value, "temperature") == 298.15


# ---- R5 known-refused list -------------------------------------------------------------------------

def test_r5_every_known_refused_entry_yields_its_code_and_reading():
    t, reg = tables(), registry()
    dims = {base: {k: v for k, v in e["dimension"].items() if v} for base, e in reg["quantities"].items()}
    orphans = []
    for spelling, entry in sorted(t["refused"].items()):
        text = f"1 {spelling}"
        if entry["code"] == "E-UNIT-AMBIGUOUS":
            err = convert(text, "length").error
            assert err.code == "E-UNIT-AMBIGUOUS", spelling
            assert entry["readings"] and all(r["unit"] in err.message for r in entry["readings"]), spelling
            assert err.fix is None
            continue
        dim = t["units"][entry["fix"]]["dimension"] if "fix" in entry else entry["dimension"]
        taker = next((b for b in sorted(dims) if dims[b] == dim), None)
        if taker is None:                                       # no quantity of this dimension: rule 6 first
            err = convert(text, "temperature" if dim != {"Theta": 1} else "length").error
            assert err.code == "E-UNIT-DIMENSION", spelling
            orphans.append(spelling)
        else:
            err = convert(text, taker).error
            assert err.code == entry["code"], (spelling, taker, err)
        assert entry["reading"] in err.message, (spelling, err.message)
    # Only symbols of dimensions no registry quantity has yet are orphans: mass, amount, tesla, weber,
    # henry and siemens (whole dimension vectors, exponents included).
    allowed = [{"M": 1}, {"N": 1}, {"M": 1, "T": -2, "I": -1}, {"M": 1, "L": 2, "T": -2, "I": -1},
               {"M": 1, "L": 2, "T": -2, "I": -2}, {"M": -1, "L": -2, "T": 3, "I": 2}]
    assert orphans and all(t["refused"][s]["dimension"] in allowed for s in orphans), orphans


# Every spelling 3.2 names in the known-refused list, pinned to the design (not read from the tables):
# (text, quantity, code, words of the reading, fix or None).
DESIGN_REFUSED = [
    ("10 mPa", "youngs_modulus", "E-UNIT-NOT-ACCEPTED", "millipascal", None),
    ("1 Mm", "length", "E-UNIT-NOT-ACCEPTED", "megametre", None),
    ("1 MW", "heat_rate", "E-UNIT-NOT-ACCEPTED", "megawatt", None),
    ("1 MV", "electric_potential", "E-UNIT-NOT-ACCEPTED", "megavolt", None),
    ("1 MA", "current", "E-UNIT-NOT-ACCEPTED", "megaampere", None),
    ("1 MOhm", "resistance", "E-UNIT-NOT-ACCEPTED", "megaohm", None),
    ("1 dam", "length", "E-UNIT-NOT-ACCEPTED", "decametre", None),
    ("1 Tm", "length", "E-UNIT-NOT-ACCEPTED", "terametre", None),
    ("1 W/(m degC)", "thermal_conductivity", "E-DEGC-NOT-ABSOLUTE", "W/(m K) written with degC", "1 W/(m K)"),
    ("1 ppm/degC", "linear_expansion_coefficient", "E-DEGC-NOT-ABSOLUTE", "ppm/K written with degC", "1 ppm/K"),
    ("1 1/degC", "thermo_optic_coefficient", "E-DEGC-NOT-ABSOLUTE", "1/K written with degC", "1 1/K"),
    ("1 J/(kg degC)", "specific_heat_capacity", "E-DEGC-NOT-ABSOLUTE", "J/(kg K) written with degC", "1 J/(kg K)"),
    ("1 W/(m^2 degC)", "heat_transfer_coefficient", "E-DEGC-NOT-ABSOLUTE", "W/(m^2 K) written with degC",
     "1 W/(m^2 K)"),
    ("77 degF", "temperature", "E-UNIT-NOT-ACCEPTED", "Fahrenheit", None),
    ("30 Mpsi", "youngs_modulus", "E-UNIT-NOT-ACCEPTED", "megapound-force", None),
    ("1 R", "temperature", "E-UNIT-NOT-ACCEPTED", "Rankine", None),
    ("1 Np", "bend_loss", "E-UNIT-NOT-ACCEPTED", "neper", None),
    ("1 Np/m", "propagation_loss", "E-UNIT-NOT-ACCEPTED", "8.686 dB/m", None),
    ("1 Btu", "photon_energy", "E-UNIT-NOT-ACCEPTED", "British thermal unit", None),
    ("1 kgf/mm^2", "youngs_modulus", "E-UNIT-NOT-ACCEPTED", "kilogram-force per square millimetre", None),
    ("1 oz", "length", "E-UNIT-DIMENSION", "ounce", None),                 # no mass quantity yet: rule 6
    ("4 m2", "area", "E-UNIT-NOT-ACCEPTED", "m^2 written without ^", "4 m^2"),
    ("4 m3", "volume", "E-UNIT-NOT-ACCEPTED", "m^3 written without ^", "4 m^3"),
    ("4 um2", "area", "E-UNIT-NOT-ACCEPTED", "um^2 written without ^", "4 um^2"),
    ("5 W/m K", "thermal_conductivity", "E-UNIT-AMBIGUOUS", "W/(m K)", None),
    ("5 W/m^2 K", "heat_transfer_coefficient", "E-UNIT-AMBIGUOUS", "W/(m^2 K)", None),
    ("5 W/mK", "thermal_conductivity", "E-UNIT-AMBIGUOUS", "per millikelvin", None),
    ("5 J/kgK", "specific_heat_capacity", "E-UNIT-AMBIGUOUS", "J/(kg K)", None),
    ("5 Nm", "length", "E-UNIT-AMBIGUOUS", "newton metre", None),
    ("5 Ohmm", "electrical_resistivity", "E-UNIT-AMBIGUOUS", "ohm metre", None),
    ("5 kWh", "stored_energy", "E-UNIT-AMBIGUOUS", "kilowatt hour", None),
    # degC inside an a/b c or run-together form: ambiguous first (rule 5), with the K readings and a degC note
    ("4186 J/kg degC", "specific_heat_capacity", "E-UNIT-AMBIGUOUS", "J/(kg K)", None),
    ("4186 J/kg\u00b0C", "specific_heat_capacity", "E-UNIT-AMBIGUOUS", "J/(kg K)", None),
    ("4186 J/kg\u00b7\u00b0C", "specific_heat_capacity", "E-UNIT-AMBIGUOUS", "J/(kg K)", None),
    ("398 W/m\u00b0C", "thermal_conductivity", "E-UNIT-AMBIGUOUS", "W/(m K)", None),
    ("398 W/mdegC", "thermal_conductivity", "E-UNIT-AMBIGUOUS", "W/(m K)", None),
    ("10 W/m^2\u00b0C", "heat_transfer_coefficient", "E-UNIT-AMBIGUOUS", "W/(m^2 K)", None),
    ("2 bara", "gauge_pressure", "E-ABSOLUTE-AS-LOAD", "bar absolute", None),
    ("2 psia", "gauge_pressure", "E-ABSOLUTE-AS-LOAD", "pound-force per square inch absolute", None),
    # case look-alikes of menu compounds are refused by name too
    ("1 MW/(m K)", "thermal_conductivity", "E-UNIT-NOT-ACCEPTED", "megawatt per metre kelvin", None),
    ("1 MOhm/mm", "resistance_per_length", "E-UNIT-NOT-ACCEPTED", "megaohm per millimetre", None),
]


@pytest.mark.parametrize("text, name, code, reading, fixed", DESIGN_REFUSED)
def test_r5_spellings_named_by_the_design(text, name, code, reading, fixed):
    err = convert(text, name).error
    assert err is not None and err.code == code, (text, err)
    assert reading in err.message, (text, err.message)
    assert (err.fix and err.fix.value) == fixed, (text, err.fix)
    if code == "E-UNIT-AMBIGUOUS" and ("degC" in text or "\u00b0" in text):
        assert "degC is not used inside a compound unit; write K" in err.message


def test_r5_unknown_spellings_with_degc_say_so():
    err = convert("5 kW/(m degC)", "thermal_conductivity").error             # in neither list: rule 4
    assert err.code == "E-UNIT-UNKNOWN" and "degC is never used inside a compound unit" in err.message


def test_r5_examples():
    err = convert("10 mPa", "youngs_modulus").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "millipascal" in err.message
    err = convert("3 MOhm", "resistance").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "megaohm" in err.message
    assert "megametre" in convert("1 Mm", "length").error.message
    err = convert("77 degF", "temperature").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "Fahrenheit" in err.message
    assert err.suggestions[0].value == "298.15 K" and err.suggestions[0].si_after == 298.15
    err = convert("1 Np/m", "propagation_loss").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "8.686 dB" in err.message
    err = convert("4 m2", "area").error
    assert err.fix.value == "4 m^2"
    err = convert("5 W/m K", "heat_transfer_coefficient").error
    assert err.code == "E-UNIT-AMBIGUOUS" and "W K/m" in err.message and err.fix is None
    assert "nanometre" in convert("5 Nm", "length").error.message


# ---- R6 degC kind -----------------------------------------------------------------------------------

def _k_compounds():
    reg = registry()
    for base, e in reg["quantities"].items():
        for unit in e["menu"]:
            if unit != "K" and "K" in [s for s, _ in parse_unit(unit)]:
                yield base, unit


def test_r6_degc_inside_any_compound_is_refused_with_a_meaning_preserving_fix():
    seen = 0
    for base, unit in _k_compounds():
        written = re.sub(r"(?<![A-Za-z])K(?![A-Za-z])", "degC", unit)
        assert "degC" in written and written != unit
        err = convert(f"12 {written}", base).error
        assert err.code == "E-DEGC-NOT-ABSOLUTE", (base, written)
        assert err.fix is not None and err.fix.value == f"12 {unit}", (base, written)
        assert err.suggestions == ()
        fixed = convert(err.fix.value, base)                    # the fix keeps the number and the meaning
        assert fixed.ok and fixed.exact == 12 * expected_unit(unit)[0] / expected_unit(e_unit(base))[0]
        seen += 1
    assert seen >= 15
    assert convert("12 ppm/\u00b0C", "linear_expansion_coefficient").error.fix.value == "12 ppm/K"
    assert convert("148 W/(m\u00b7\u00b0C)", "thermal_conductivity").error.fix.value == "148 W/(m K)"
    assert convert("5 degC/m", "temperature_gradient").error.fix.value == "5 K/m"


def e_unit(base: str) -> str:
    return registry()["quantities"][base]["unit"]


def test_r6_degc_for_a_difference_is_a_suggestion_never_a_fix():
    reg = registry()
    differences = [b for b, e in reg["quantities"].items()
                   if e["kind"] == "difference" and e["dimension"] == {"Theta": 1}]
    assert set(differences) >= {"temperature_difference", "temperature_rise", "temperature_change",
                                "temperature_tolerance"}
    for base in differences:
        err = convert("0.001 degC", base).error
        assert err.code == "E-DEGC-NOT-ABSOLUTE" and err.fix is None, base
        (s,) = err.suggestions
        assert s.value == "0.001 K" and s.si_after == 0.001 and s.si_before == float(F("0.001") + F("273.15"))
    with pytest.raises(UnitError) as info:
        q_array({"unit": "degC", "values": [1, 2]}, "temperature_rise")
    assert info.value.code == "E-DEGC-NOT-ABSOLUTE" and info.value.diagnostic.fix is None
    assert info.value.diagnostic.suggestions[0].value == "K"


def test_r6_degc_is_the_whole_unit_of_every_absolute_temperature():
    absolute = [n for n in units.names() if units.quantity(n).kind == "absolute"]
    assert {"temperature", "ambient_temperature", "reference_temperature", "initial_temperature",
            "stress_free_temperature"} <= set(absolute)
    for name in absolute:
        assert q("25 degC", name) == 298.15
    assert q_array({"unit": "degC", "values": [0, 25]}, "temperature") == [273.15, 298.15]


# ---- R7 dimension ------------------------------------------------------------------------------------

def test_r7_dimension_mismatch_names_the_quantity_that_takes_the_unit():
    err = convert("58 MS/m", "thermal_conductivity").error
    assert err.code == "E-UNIT-DIMENSION" and "electrical_conductivity" in err.message
    assert "Did you mean electrical_conductivity?" in err.message
    err = convert("398 W/(m K)", "electrical_conductivity").error
    assert err.code == "E-UNIT-DIMENSION" and "Did you mean thermal_conductivity?" in err.message
    # 3.8: a frequency in vacuum_wavelength hints frequency; the spectral keys hint each other.
    for text, name, hint in (("1550 THz", "vacuum_wavelength", "frequency"), ("1550 nm", "frequency", "vacuum_wavelength"),
                             ("2 eV", "vacuum_wavelength", "photon_energy"), ("5 mm", "temperature", "length"),
                             ("193 THz", "photon_energy", "frequency"), ("6451.6 1/cm", "frequency", "vacuum_wavenumber"),
                             ("25 degC", "length", "temperature"), ("10 mV", "current", "electric_potential")):
        err = convert(text, name).error
        assert err.code == "E-UNIT-DIMENSION" and err.message.endswith(f"Did you mean {hint}?"), (text, err.message)


def test_r7_hints_never_name_model_parameters_or_quantities_that_refuse_the_unit():
    never = ("lower_corner_frequency", "upper_corner_frequency", "reference_frequency", "plasma_energy",
             "damping_energy", "resonance_energy", "air_wavelength", "reference_conductivity", "reference_resistivity")
    for text, name in (("1550 THz", "vacuum_wavelength"), ("2 eV", "length"), ("1550 nm", "frequency"),
                       ("58 MS/m", "length"), ("1 Ohm m", "length")):
        msg = convert(text, name).error.message
        assert not any(n in msg for n in never), (text, msg)
    # A refused spelling is never "a unit of" anything, and no hint is offered for it.
    for text, name, dimension_of in (("5 MW", "thermal_conductivity", "heat_rate"), ("1 Np/m", "length",
                                                                                   "propagation_loss")):
        msg = convert(text, name).error.message
        assert f"which has the dimension of {dimension_of}" in msg and "a unit of" not in msg and "Did you mean" \
            not in msg, msg
    # Angles count: dB and Np are not bend_loss units (bend_loss is a loss per angle), and no quantity takes them.
    for text, name in (("3 dB", "propagation_loss"), ("3 Np", "propagation_loss"), ("3 dB", "poisson_ratio")):
        msg = convert(text, name).error.message
        assert "bend_loss" not in msg and "which no registry quantity takes" in msg, msg


# ---- R8 range ------------------------------------------------------------------------------------------

def test_r8_out_of_range_values_are_refused():
    for text, name in (("1e400 Pa", "youngs_modulus"), ("-1e400 Pa", "traction"), ("1e-330 m", "length"),
                       ("1e-330 m", "depth"), ("1e999999999 Pa", "traction"), ("1e-999999999 m", "length"),
                       ("1e999999999999999999999 Pa", "gauge_pressure"), ("-1e-999999999999999999999 Pa", "traction")):
        err = convert(text, name).error
        assert err is not None and err.code == "E-DOMAIN", (text, name)
    assert q("0e999999999999999999999 Pa", "traction") == 0.0          # zero is zero, whatever its exponent
    for value in (Decimal("1e999999999999999999"), Decimal("1e-999999999999999999"), 10 ** 5000, F(10 ** 5000),
                  F(1, 10 ** 5000)):
        assert convert(value, "poisson_ratio").error.code == "E-DOMAIN"
    assert length_to_pm("1e999999999999999999999", "mm").error.code == "E-DOMAIN"
    assert length_to_pm(10 ** 5000, "mm").error.code == "E-DOMAIN"
    with pytest.raises(UnitError) as info:
        q_array({"unit": "nm", "values": [10 ** 5000]}, "length")
    assert info.value.code == "E-DOMAIN"
    for value in (Decimal("1e400"), Decimal("1e-320"), float("inf"), float("nan"), Decimal("NaN"), 10 ** 400):
        assert convert(value, "relative_permittivity").error.code == "E-DOMAIN", value
    assert q("1.7e308 Pa", "traction") == 1.7e308 and q("1e-300 m", "length") == 1e-300
    assert q("0 m", "length") == 0.0
    assert length_to_pm("1e7 m").error.code == "E-DOMAIN" and length_to_pm("9e6 m").picometres == 9 * 10 ** 18
    # The int64 grid holds -2^63 .. 2^63 - 1 pm.
    assert length_to_pm(-(2 ** 63), "pm").picometres == -(2 ** 63)
    assert length_to_pm("-9223372.036854775808 m").picometres == -(2 ** 63)
    assert length_to_pm(2 ** 63 - 1, "pm").picometres == 2 ** 63 - 1
    assert length_to_pm(2 ** 63, "pm").error.code == "E-DOMAIN" and length_to_pm(-(2 ** 63) - 1, "pm").error


# ---- R9 standard library only --------------------------------------------------------------------------

def test_r9_imports_only_the_standard_library():
    for module in ("units.py", "_unit_tables.py"):
        tree = ast.parse(Path(units.__file__).with_name(module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                roots = [] if node.level else [node.module.split(".")[0]]
            else:
                continue
            assert all(r in sys.stdlib_module_names or r == "__future__" for r in roots), (module, roots)


def test_r9_units_work_with_numpy_and_scipy_blocked(tmp_path):
    src = str(Path(units.__file__).resolve().parents[1])
    code = r"""
import sys
sys.path.insert(0, sys.argv[1])
class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("numpy", "scipy"):
            raise ImportError("blocked: " + name)
sys.meta_path.insert(0, Block())
import physmat.units as u
assert u.q("200 GPa", "youngs_modulus") == 2e11
assert u.q_array({"unit": "nm", "values": [1550]}, "vacuum_wavelength") == [1.55e-06]
assert u.generate_tables() == u._read(u.TABLES_FILE)
loaded = sorted(m for m in sys.modules if m.split(".")[0] in ("numpy", "scipy"))
first_party = sorted(m for m in sys.modules if m.split(".")[0] == "physmat")
assert not loaded, loaded
assert first_party == ["physmat", "physmat._unit_tables", "physmat.units"], first_party
print("ok")
"""
    run = subprocess.run([sys.executable, "-I", "-B", "-c", code, src], cwd=tmp_path, capture_output=True, text=True,
                         timeout=300)
    assert run.returncode == 0 and run.stdout.strip() == "ok", run.stderr


# ---- R10 q and q_array -----------------------------------------------------------------------------------

def test_r10_q_returns_an_si_float_and_q_array_an_si_list():
    value = q("200 GPa", "youngs_modulus")
    assert type(value) is float and value == 2e11
    out = q_array({"unit": "nm", "values": [1500, 1525, 1550]}, "vacuum_wavelength")
    assert type(out) is list and all(type(x) is float for x in out) and out == [1.5e-06, 1.525e-06, 1.55e-06]
    assert q_array({"values": [3.48, 3.47]}, "refractive_index") == [3.48, 3.47]
    assert q_array(["0 MPa", "-5 MPa"], "traction") == [0.0, -5e6]
    assert q_array({"unit": "GPa", "values": [[200, 80], [80, 200]]}, "elasticity_tensor") == [[2e11, 8e10],
                                                                                                [8e10, 2e11]]
    assert q_array({"unit": "%", "values": [40, 50]}, "relative_humidity") == [0.4, 0.5]
    assert type(q(3, "mode_count")) is float and q(3, "mode_count") == 3.0


def test_r10_bare_numbers_only_for_dimensionless_quantities():
    for name in units.names():
        qo = units.quantity(name)
        got = convert(1, name)
        if "1" in qo.menu:                                      # accepted as a value; its domain may still refuse 1
            assert dict(qo.dimension) == {}, name
            assert got.value == 1.0 if got.ok else got.error.code == "E-DOMAIN", name
        else:
            assert got.error.code == "E-UNIT-MISSING", name
    assert q(0.3, "poisson_ratio") == 0.3
    # A bare number is a JSON number: a string holding only a number is refused, with the number as the fix.
    for text, name, fixed in (("0.3", "poisson_ratio", 0.3), ("40", "relative_humidity", 40), ("2", "mode_count", 2),
                              ("2e1", "mode_count", 20), (" 5 ", "pml_order", 5)):
        err = convert(text, name).error
        assert err.code == "E-UNIT-UNKNOWN" and err.fix.value == fixed and type(err.fix.value) is type(fixed), text
        assert convert(err.fix.value, name).exact == convert(Decimal(text.strip()), name).exact or name == "mode_count"
    for text, name in (("2.5", "mode_count"), ("1e400", "poisson_ratio"), ("1e-330", "poisson_ratio")):
        err = convert(text, name).error
        assert err.code == "E-UNIT-UNKNOWN" and err.fix is None, text
    for value, name in ((200000, "youngs_modulus"), ("200000", "youngs_modulus"), (0, "electric_potential"),
                        (5, "rotation"), (Decimal("1.5"), "vacuum_wavelength")):
        with pytest.raises(UnitError) as info:
            q(value, name)
        assert info.value.code == "E-UNIT-MISSING"
    with pytest.raises(UnitError) as info:
        q_array({"values": [1, 2]}, "length")
    assert info.value.code == "E-UNIT-MISSING" and info.value.diagnostic.path == "values[0]"
    with pytest.raises(TypeError):
        q(True, "poisson_ratio")
    with pytest.raises(TypeError):
        q_array({"unit": "nm", "values": ["1500"]}, "length")


def test_r10_counts_are_integers():
    assert q(2, "mode_count") == 2.0 and q(Decimal("2"), "mode_count") == 2.0
    for value in (2.5, Decimal("2.5"), -1):
        err = convert(value, "mode_count").error
        assert err.code == "E-DOMAIN" and err.fix is None, value
    # The right whole number written as something other than an integer literal: E-DOMAIN with the integer as fix.
    for value, fixed in ((2.0, 2), (Decimal("2.0"), 2), (Decimal("5E+1"), 50), (F(5), 5)):
        err = convert(value, "mode_count").error
        assert err.code == "E-DOMAIN" and err.fix.value == fixed and type(err.fix.value) is int, value
        assert "not written as an integer literal" in err.message and "not a whole number" not in err.message
        assert q(err.fix.value, "mode_count") == float(fixed)
    assert convert("2", "mode_count").error.fix.value == 2
    assert convert(0, "pml_order").error.code == "E-DOMAIN"


# ---- R11 registry self-checks ------------------------------------------------------------------------------

def test_r11_canonical_unit_on_menu_and_menu_units_have_the_quantity_dimension():
    for base, e in registry()["quantities"].items():
        assert e["unit"] in e["menu"], base
        want = {k: v for k, v in e["dimension"].items() if v}
        for unit in e["menu"]:
            assert expected_unit(unit)[1] == want, (base, unit)
        assert expected_unit(e["unit"])[0] == 1 or e["unit"] in ("dB/(90 deg)",), base   # coherent SI


def test_r11_registry_vocabularies_and_names():
    reg = registry()
    for base, e in reg["quantities"].items():
        assert e["kind"] in {"ordinary", "absolute", "difference", "fraction", "count"}
        assert set(e["rank"]) <= {"scalar", "vector", "tensor", "matrix"}
        assert set(e["places"]) <= {"document", "material", "api", "result"}
        assert e["description"]["en"] and e["description"]["ko"], base
        if e["kind"] in ("fraction", "count"):
            assert e["dimension"] == {} and "1" in e["menu"]
        if e["kind"] == "fraction":
            assert e["domain"] in ({"min": "0", "max": "1"}, {"min_exclusive": "0", "max": "1"})
    names = set(units.names())
    assert set(reg["quantities"]) <= names
    for name in ("ambient_temperature", "stress_free_temperature", "maximum_temperature", "inward_heat_flux",
                 "outward_heat_rate_per_depth", "generated_heat_rate", "inward_current_per_depth",
                 "maximum_von_mises_stress", "stress_xy", "displacement_x", "strain_hoop", "reference_conductivity"):
        assert name in names, name
    for name in ("conductivity", "young_modulus", "temperature_maximum", "ambient_maximum_temperature", "E", "k0"):
        assert name not in names, name
    assert units.quantity("ambient_temperature").kind == "absolute"
    assert units.quantity("inward_heat_flux").unit == "W/m^2"
    for name in ("thermal_conductivity", "electrical_conductivity", "youngs_modulus", "linear_expansion_coefficient",
                 "thermo_optic_coefficient", "vacuum_wavelength", "gauge_pressure", "absolute_pressure"):
        assert name in reg["quantities"]
    for e in reg["quantities"].values():                        # every 1/K quantity has a lower |value| bound
        if e["unit"] == "1/K":
            assert e["band"] and ("abs_min" in e["band"] or e["band"].get("abs_range", [None])[0]), e


def test_r11_menus_from_the_starter_registry():
    assert units.menu("youngs_modulus") == ("Pa", "kPa", "MPa", "GPa", "psi", "ksi")
    assert units.menu("gauge_pressure") == ("Pa", "kPa", "MPa", "GPa", "bar", "mbar", "psi", "ksi", "barg", "psig")
    assert units.menu("absolute_pressure") == ("Pa", "kPa", "hPa", "bar", "mbar", "atm", "bara", "psia")
    assert units.menu("temperature") == ("K", "mK", "degC")
    assert units.menu("temperature_difference") == ("K", "mK")
    assert units.menu("electrical_conductivity") == ("S/m", "kS/m", "MS/m", "S/cm")
    assert units.menu("thermal_conductivity") == ("W/(m K)", "mW/(m K)", "W/(cm K)")
    assert units.menu("linear_expansion_coefficient") == ("1/K", "ppm/K", "um/(m K)")
    assert units.menu("vacuum_wavenumber") == ("1/cm", "1/m")
    assert units.menu("vacuum_angular_wavenumber") == ("rad/m", "rad/um")
    assert units.menu("relative_humidity") == ("1", "%")
    assert units.LENGTH_UNITS == ("pm", "nm", "Angstrom", "um", "mm", "cm", "m", "in", "mil")
    assert "hPa" in units.menu("vapor_pressure") and "atm" not in units.menu("gauge_pressure")
    err = convert("6451.6 1/cm", "vacuum_angular_wavenumber").error     # disjoint wavenumber menus
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "vacuum_wavenumber" in err.message and err.suggestions == ()
    assert q("6451.6 1/cm", "vacuum_wavenumber") == 645160.0


# ---- R12 existing physmat tests ------------------------------------------------------------------------------

PUBLIC = ["get", "names", "constant", "standard_air", "CiddorAir", "Material", "Property", "Dispersion", "Constant",
          "Sellmeier", "Tabulated", "Composite", "Drude", "DrudeLorentz", "RIIFormula", "OutOfRange", "ev_to_um",
          "um_to_ev", "fit_drude_lorentz", "FitResult", "HustLankford", "air", "dispersion", "fit", "library", "rii",
          "thermal", "__version__"]


def test_r12_public_physmat_api_is_unchanged():
    import importlib

    import physmat
    assert set(PUBLIC) <= set(physmat.__all__) and set(physmat.__all__) - set(PUBLIC) == {"units"}
    modules = {"CiddorAir": "air", "Material": "material", "Property": "material", "HustLankford": "thermal",
               "fit_drude_lorentz": "fit", "FitResult": "fit", "get": "library", "names": "library",
               "constant": "library", "standard_air": "library"}
    for name in PUBLIC:
        value = getattr(physmat, name)
        assert name in dir(physmat)
        if name in modules:
            assert value is getattr(importlib.import_module(f"physmat.{modules[name]}"), name)
    assert physmat.material.Material is physmat.Material
    assert physmat.get("Si").n(1.55) == pytest.approx(3.4777, abs=2e-4)
    with pytest.raises(AttributeError):
        physmat.no_such_name


def test_r12_existing_physmat_tests_pass_unchanged():
    here = Path(__file__).resolve().parent
    files = [str(here / f) for f in ("test_air.py", "test_conductivity_temperature.py", "test_physmat.py")]
    command = [sys.executable, "-B"] + (["-I"] if sys.flags.isolated else []) + ["-m", "pytest", "-q", "-p",
                                                                                "no:cacheprovider", *files]
    run = subprocess.run(command, cwd=here.parents[1], capture_output=True, text=True, timeout=900)
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-4000:]
    assert " passed" in run.stdout and " failed" not in run.stdout


# ---- precedence: one test per rule ------------------------------------------------------------------------------

def test_precedence_rule_3_unit_missing_before_domain():
    assert convert(-5, "mass_density").error.code == "E-UNIT-MISSING"
    assert convert(Decimal("1e400"), "length").error.code == "E-UNIT-MISSING"


def test_precedence_rule_4_unknown_spelling_with_case_suggestion():
    err = convert("10 Mpa", "youngs_modulus").error
    assert err.code == "E-UNIT-UNKNOWN" and err.fix is None
    assert [s.value for s in err.suggestions] == ["10 MPa"] and err.suggestions[0].si_before is None
    assert convert("5 furlong", "length").error.code == "E-UNIT-UNKNOWN"


def test_precedence_rule_5_ambiguity_before_dimension():
    assert convert("5 W/mK", "youngs_modulus").error.code == "E-UNIT-AMBIGUOUS"


def test_precedence_rule_6_dimension_before_degc_and_refusals():
    assert convert("12 ppm/degC", "youngs_modulus").error.code == "E-UNIT-DIMENSION"
    assert convert("5 degC", "length").error.code == "E-UNIT-DIMENSION"
    assert convert("5 MW", "thermal_conductivity").error.code == "E-UNIT-DIMENSION"


def test_precedence_rule_7_degc_before_menu():
    assert convert("5 degC", "temperature_difference").error.code == "E-DEGC-NOT-ABSOLUTE"
    assert convert("5 degC^-1", "thermo_optic_coefficient").error.code == "E-DEGC-NOT-ABSOLUTE"


def test_precedence_rule_8_known_refused_before_menu():
    err = convert("10 mPa", "gauge_pressure").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "millipascal" in err.message
    err = convert("2 bara", "gauge_pressure").error
    assert err.code == "E-ABSOLUTE-AS-LOAD" and err.fix is None
    assert convert("2 psia", "gauge_pressure").error.code == "E-ABSOLUTE-AS-LOAD"
    assert q("1.2 bara", "absolute_pressure") == 1.2e5


def test_precedence_rule_9_accepted_spelling_off_the_menu():
    err = convert("1 atm", "gauge_pressure").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "Pa kPa MPa GPa bar mbar psi ksi barg psig" in err.message
    assert convert("5 hPa", "youngs_modulus").error.code == "E-UNIT-NOT-ACCEPTED"


def test_precedence_rule_10_range_before_domain():
    err = convert("1e-330 m", "depth").error                   # > 0 holds exactly, the double does not
    assert err.code == "E-DOMAIN" and "1e-300" in err.message


def test_precedence_rule_11_domain_before_band():
    assert convert("-5 GPa", "youngs_modulus").error.code == "E-DOMAIN"
    assert convert(0.5, "poisson_ratio").error.code == "E-DOMAIN"
    assert convert("-300 degC", "temperature").error.code == "E-DOMAIN"
    assert convert("36 deg", "minimum_angle").error.code == "E-DOMAIN" and q("35 deg", "minimum_angle") > 0
    err = convert(40, "relative_humidity").error
    assert err.code == "E-DOMAIN" and err.suggestions[0].value == "40 %" and err.suggestions[0].si_after == 0.4


def test_precedence_rule_12_band_warns_and_keeps_the_value():
    c = convert("210000 Pa", "youngs_modulus")
    assert c.ok and c.value == 210000.0 and [d.code for d in c.diagnostics] == ["W-MAGNITUDE"]
    assert "210000 MPa" in [s.value for s in c.diagnostics[0].suggestions]
    with pytest.warns(UnitWarning, match="W-MAGNITUDE"):
        assert q("210000 Pa", "youngs_modulus") == 210000.0


def test_each_path_gets_exactly_one_error():
    for text, name in (("10 mpa", "youngs_modulus"), ("1e400 mPa", "gauge_pressure"), ("12 ppm/degC", "length"),
                       ("2eV", "photon_energy"), ("10mPa", "gauge_pressure")):
        c = convert(text, name)
        assert [d.severity for d in c.diagnostics] == ["error"], text


# ---- diagnostics: codes, fixes, suggestions, messages --------------------------------------------------------------

def test_diagnostic_codes_are_the_closed_list_with_en_and_ko_text():
    codes = units.DIAGNOSTIC_CODES
    # 58 codes of the design, plus the 8 of the document reader (R-1): E-FORMAT, E-JSON, E-VALUE-FORM,
    # E-MATERIAL-UNKNOWN, E-CONTRACT, W-SHAPE-DROPPED, W-PIECE-DROPPED, I-MESH-CONTROL-RAISED.
    assert len(codes) == 66
    assert sum(1 for c in codes.values() if c["severity"] == "error") == 37
    assert sum(1 for c in codes.values() if c["severity"] == "warning") == 18
    assert sum(1 for c in codes.values() if c["severity"] == "info") == 11
    for code, c in codes.items():
        assert code.startswith({"error": "E-", "warning": "W-", "info": "I-"}[c["severity"]])
        assert c["en"] and c["ko"]
    raised = {code for code, c in codes.items() if "physmat.units" in c.get("raised_by", ())}
    assert raised == {"E-KEY-UNKNOWN", "E-KEY-MISSING", "E-UNIT-MISSING", "E-UNIT-UNKNOWN", "E-UNIT-AMBIGUOUS",
                      "E-UNIT-DIMENSION", "E-UNIT-NOT-ACCEPTED", "E-DEGC-NOT-ABSOLUTE", "E-ABSOLUTE-AS-LOAD",
                      "E-DOMAIN", "W-MAGNITUDE", "W-GAUGE-ATMOSPHERIC", "W-PM-ROUNDING", "I-PM-ROUNDING",
                      "E-VALUE-FORM", "E-GAIN"}


def test_every_code_the_converter_raises_has_a_trigger():
    triggers = {
        "E-KEY-UNKNOWN": lambda: _raised(lambda: units.quantity("E")),
        "E-KEY-MISSING": lambda: _raised(lambda: q_array({"unit": "nm"}, "length")),
        "E-UNIT-MISSING": lambda: convert(5, "length").error,
        "E-UNIT-UNKNOWN": lambda: convert("5 furlong", "length").error,
        "E-UNIT-AMBIGUOUS": lambda: convert("5 Ohmm", "electrical_resistivity").error,
        "E-UNIT-DIMENSION": lambda: convert("5 V", "length").error,
        "E-UNIT-NOT-ACCEPTED": lambda: convert("5 Mm", "length").error,
        "E-DEGC-NOT-ABSOLUTE": lambda: convert("5 1/degC", "thermo_optic_coefficient").error,
        "E-ABSOLUTE-AS-LOAD": lambda: convert("2 bara", "gauge_pressure").error,
        "E-DOMAIN": lambda: convert("-1 K", "temperature").error,
        "W-MAGNITUDE": lambda: convert("12 1/K", "linear_expansion_coefficient").diagnostics[0],
        "W-GAUGE-ATMOSPHERIC": lambda: convert("1 bar", "gauge_pressure").diagnostics[0],
        "W-PM-ROUNDING": lambda: length_to_pm("0.0005 nm").diagnostics[0],
        "I-PM-ROUNDING": lambda: length_to_pm("0.30000000000000004 nm").diagnostics[0],
        "E-VALUE-FORM": lambda: units.convert_complex([4.0, 0.04], "relative_permittivity").error,
        "E-GAIN": lambda: units.convert_complex({"re": 4.0, "im": -0.04}, "relative_permittivity").error,
    }
    for code, trigger in triggers.items():
        assert trigger().code == code, code


def _raised(fn):
    with pytest.raises(UnitError) as info:
        fn()
    return info.value.diagnostic


def test_fixes_keep_the_value_and_suggestions_show_both_values():
    for text, name, fixed in (("2eV", "photon_energy", "2 eV"), ("25K", "temperature", "25 K"),
                              ("5 W/m2", "heat_flux", "5 W/m^2"), ("12 ppm/degC", "linear_expansion_coefficient",
                                                                   "12 ppm/K"), ("10mm", "length", "10 mm"),
                              ("3 W m-1 K-1", "thermal_conductivity", "3 W/(m K)")):
        err = convert(text, name).error
        assert err.fix is not None and err.fix.value == fixed and err.suggestions == (), text
        assert convert(fixed, name).ok
        assert err.fix.patch("/a/b") == {"op": "replace", "path": "/a/b", "value": fixed}
    err = convert("10mPa", "gauge_pressure").error             # glued and refused: the refusal wins
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "space" in err.message and err.suggestions[0].value == "10 MPa"
    s = convert("10 mPa", "gauge_pressure").error.suggestions[0]
    assert (s.value, s.si_before, s.si_after, s.unit) == ("10 MPa", 0.01, 1e7, "Pa")
    for text, name in (("10 mPa", "youngs_modulus"), ("0.001 degC", "temperature_tolerance"),
                       ("5 W/mK", "thermal_conductivity"), ("10 mS/m", "electrical_conductivity")):
        assert convert(text, name).error.fix is None, text      # meaning may change: never a fix


def test_message_style():
    err = convert("10 mPa", "gauge_pressure", path="physics.solid.conditions.bore.gauge_pressure").error
    text = str(err)
    assert text.splitlines()[0] == "error E-UNIT-NOT-ACCEPTED at physics.solid.conditions.bore.gauge_pressure"
    assert '"10 mPa"' in text and "millipascal" in text and "Pa kPa MPa GPa bar mbar psi ksi barg psig" in text
    assert 'Suggestion (not applied automatically): "10 MPa" (1e7 Pa; as written 0.01 Pa)' in text
    d = err.as_dict()
    assert set(d) == {"code", "severity", "path", "message", "fix", "suggestions", "acknowledged"}
    assert d["severity"] == "error" and d["acknowledged"] is None
    assert str(convert("12 ppm/degC", "linear_expansion_coefficient").error).endswith(
        'Fix (keeps the value): "12 ppm/K"')
    err = convert("200000", "youngs_modulus", path="materials.steel.youngs_modulus").error
    assert str(err).startswith("error E-UNIT-MISSING at materials.steel.youngs_modulus\n  200000 has no unit.")


def test_number_grammar():
    for text in (".5 mm", "5. mm", "1,5 mm", "1 000 mm", "mm", "", "five mm", "5 mm extra"):
        assert convert(text, "length").error.code == "E-UNIT-UNKNOWN", text
    assert "leading digit" in convert(".5 mm", "length").error.message
    assert q("+5 mm", "length") == 0.005 and q("1E3 mm", "length") == 1.0 and q("-0 mm", "length") == 0.0


def test_quantity_lookup():
    with pytest.raises(UnitError) as info:
        units.quantity("E")
    assert info.value.code == "E-KEY-UNKNOWN" and "youngs_modulus" in str(info.value)
    msg = _raised(lambda: units.quantity("conductivity")).message
    assert "thermal_conductivity" in msg and "electrical_conductivity" in msg
    assert "vapor_pressure" in _raised(lambda: units.quantity("vapour_pressure")).message
    assert "youngs_modulus" in _raised(lambda: units.quantity("young_modulus")).message
    qo = units.quantity("youngs_modulus")
    assert (qo.unit, qo.kind, dict(qo.dimension), qo.bare) == ("Pa", "ordinary", {"M": 1, "L": -1, "T": -2}, False)
    assert units.quantity("poisson_ratio").bare and units.quantity("stress_xy").base == "stress"
    with pytest.raises(TypeError):
        units.quantity(None)


def test_bands():
    def codes(text, name):
        return [d.code for d in convert(text, name).diagnostics]
    assert codes("1.2e-5 ppm/K", "linear_expansion_coefficient") == ["W-MAGNITUDE"]     # double conversion
    assert codes("0.00393 ppm/K", "resistivity_temperature_coefficient") == ["W-MAGNITUDE"]
    assert codes("1.8e-4 ppm/K", "thermo_optic_coefficient") == ["W-MAGNITUDE"]
    assert codes("12 1/K", "linear_expansion_coefficient") == ["W-MAGNITUDE"]
    assert codes("0 1/K", "linear_expansion_coefficient") == []                         # exact zero is exempt
    assert codes("12 ppm/K", "linear_expansion_coefficient") == []
    assert codes("0.4 %", "relative_humidity") == ["W-MAGNITUDE"] and codes("0 %", "relative_humidity") == []
    assert codes(0.004, "relative_humidity") == [] and codes("40 %", "relative_humidity") == []
    assert codes(-0.1, "poisson_ratio") == ["W-MAGNITUDE"]
    assert codes("0 S/m", "electrical_conductivity") == []
    err = convert("1.2e-5 ppm/K", "linear_expansion_coefficient").diagnostics[0]
    assert "1/K written with ppm/K" in err.message and err.suggestions[0].value == "1.2e-5 1/K"
    assert convert("0.4 %", "relative_humidity").diagnostics[0].suggestions[0].value == 0.4


def test_gauge_pressure_near_atmospheric_warns():
    for text in ("1 bar", "100 kPa", "0.1 MPa", "14.5 psi", "101325 Pa", "14.7 psi"):
        assert [d.code for d in convert(text, "gauge_pressure").diagnostics] == ["W-GAUGE-ATMOSPHERIC"], text
    assert convert("10 MPa", "gauge_pressure").diagnostics == ()
    assert convert("1 bar", "absolute_pressure").diagnostics == ()


def test_q_array_forms_and_errors():
    with pytest.raises(UnitError) as info:
        q_array({"unit": "nm", "values": [1], "scale": 2}, "length")
    assert info.value.code == "E-KEY-UNKNOWN"
    with pytest.raises(UnitError) as info:
        q_array({"unit": "1", "values": [0.3]}, "poisson_ratio")
    assert info.value.code == "E-UNIT-NOT-ACCEPTED"
    with pytest.raises(UnitError) as info:
        q_array({"unit": "mPa", "values": [1, 2]}, "gauge_pressure")
    assert info.value.code == "E-UNIT-NOT-ACCEPTED" and info.value.diagnostic.path == "unit"
    assert info.value.diagnostic.suggestions[0].value == "MPa"
    with pytest.raises(UnitError) as info:
        q_array({"unit": "GPa", "values": [200, -1]}, "youngs_modulus", path="materials.x.youngs_modulus")
    assert info.value.code == "E-DOMAIN" and info.value.diagnostic.path == "materials.x.youngs_modulus.values[1]"
    assert q_array({"unit": "\u00b5m", "values": [1]}, "length") == [1e-06]
    with pytest.warns(UnitWarning):
        assert q_array({"unit": "Pa", "values": [210000]}, "youngs_modulus") == [210000.0]


def test_length_to_pm_grid():
    g = length_to_pm(100, "mm")
    assert g.picometres == 100 * 10 ** 9 and g.diagnostics == () and g.metres == 0.1 == float("0.1")
    assert length_to_pm("100", "mm").picometres == g.picometres
    assert length_to_pm(220, "nm").picometres == length_to_pm("0.22 um").picometres == 220_000
    assert length_to_pm(1, "in").picometres == 25_400_000_000 and length_to_pm(1, "mil").picometres == 25_400_000
    assert length_to_pm(1, "Angstrom").picometres == 100 and length_to_pm("1 km").picometres == 10 ** 15
    assert length_to_pm("0.0005 nm").picometres == 0 and length_to_pm("0.0015 nm").picometres == 2   # half to even
    assert length_to_pm("0.0025 nm").picometres == 2 and length_to_pm("-0.0015 nm").picometres == -2
    w = length_to_pm("0.0015 nm").diagnostics[0]
    assert w.code == "W-PM-ROUNDING" and "1.5 pm" in w.message and "2 pm" in w.message and "0.5 pm" in w.message
    i = length_to_pm(0.30000000000000004, "nm").diagnostics[0]
    assert i.code == "I-PM-ROUNDING" and length_to_pm(0.30000000000000004, "nm").picometres == 300
    assert length_to_pm(5, "km").error.code == "E-UNIT-NOT-ACCEPTED"       # km is not a length_unit
    assert length_to_pm(5).error.code == "E-UNIT-MISSING"
    assert length_to_pm("5 GPa").error.code == "E-UNIT-DIMENSION"
    assert units.pm_to_m(100_000_000_000) == 0.1 and units.pm_to_m(-1) == -1e-12


def test_format_round_trips():
    assert units.format(2e11, "youngs_modulus", "GPa") == "200 GPa"
    assert units.format(298.15, "temperature", "degC") == "25 degC"
    assert units.format(1.55e-06, "vacuum_wavelength", "nm") == "1550 nm"
    assert units.format(0.3, "poisson_ratio") == "0.3" and units.format(0.4, "relative_humidity", "%") == "40 %"
    for value, name, unit in ((0.1 + 0.2, "length", "mm"), (1 / 3, "length", "in"), (math.pi / 7, "rotation", "deg"),
                              (2.7e-5, "linear_expansion_coefficient", "ppm/K"), (310.0, "temperature", "degC")):
        assert q(units.format(value, name, unit), name) == value, (value, unit)
    with pytest.raises(UnitError):
        units.format(1.0, "youngs_modulus", "mPa")


def test_registry_files_are_package_data():
    for name in ("quantities.json", "unit_tables.json"):
        data = resources.files("physmat").joinpath(name).read_bytes()
        assert data.endswith(b"\n") and b"\r\n" not in data
    assert tables()["format"] == "physmat.unit_tables/v1" and registry()["format"] == "physmat.quantities/v1"


def test_main_check_entry_point(capsys):
    assert units._main(["--check", "youngs_modulus"]) == 0
    assert "youngs_modulus" in capsys.readouterr().out


# ---- review follow-ups: menus pinned to the design, forms, numbers, formatting ------------------------------------

L_MENU = ("pm", "nm", "Angstrom", "um", "mm", "cm", "m", "km", "in", "mil")
TIME = ("fs", "ps", "ns", "us", "ms", "s", "min", "h")
HZ = ("Hz", "kHz", "MHz", "GHz", "THz")
MODULUS = ("Pa", "kPa", "MPa", "GPa", "psi", "ksi")   # no Mpsi: founder decision 2026-11-09
STRESS = ("Pa", "kPa", "MPa", "GPa", "psi", "ksi")
PER_K = ("1/K", "ppm/K")
ENERGY_EV = ("meV", "eV")
W_M3 = ("W/m^3", "W/cm^3", "W/mm^3", "W/um^3", "mW/um^3")
W_M = ("W/m", "W/mm", "mW/mm", "mW/um")
POWER = ("nW", "uW", "mW", "W", "kW")
SIGMA = ("S/m", "kS/m", "MS/m", "S/cm")
RHO = ("Ohm m", "Ohm cm", "mOhm cm", "uOhm cm", "nOhm m")
BARE = ("1",)


def _menus(names: str, menu: tuple) -> dict:
    return {n: menu for n in names.split()}


# The starter registry of design 4.8, written from its tables (not read from quantities.json).
DESIGN_MENUS = {
    **_menus("length position depth sheet_thickness element_size refinement_distance expected_extent perimeter "
             "line_length beam_waist_radius mode_field_diameter bend_radius pml_thickness", L_MENU),
    **_menus("element_growth_rate circle_segment_count subdivision_count layer_division_count emissivity "
             "relative_permittivity loss_tangent relative_permeability huray_surface_ratio poisson_ratio "
             "refractive_index effective_index group_index target_effective_index high_frequency_relative_permittivity "
             "drude_strength overlap_threshold mode_tracking_threshold degeneracy_tolerance pml_strength pml_order "
             "pml_minimum_physical_fraction residual_resistivity_ratio relative_tolerance relaxation_factor "
             "coverage_factor mode_count iteration_limit iteration_count element_count_limit mode_index sweep_index",
             BARE),
    "minimum_angle": ("deg", "rad"), **_menus("rotation incidence_angle", ("deg", "rad", "mrad", "urad")),
    **_menus("area meridional_area", ("nm^2", "um^2", "mm^2", "cm^2", "m^2")),
    "volume": ("um^3", "mm^3", "cm^3", "m^3"),
    "temperature": ("K", "mK", "degC"),
    **_menus("temperature_difference temperature_rise temperature_change temperature_tolerance", ("K", "mK")),
    "temperature_gradient": ("K/m", "K/mm", "K/um"),
    "thermal_conductivity": ("W/(m K)", "mW/(m K)", "W/(cm K)"),
    "mass_density": ("kg/m^3", "g/cm^3"),
    "specific_heat_capacity": ("J/(kg K)", "kJ/(kg K)", "J/(g K)"),
    "volumetric_heat_capacity": ("J/(m^3 K)", "MJ/(m^3 K)", "J/(cm^3 K)"),
    **_menus("heat_source_density joule_power_density", W_M3),
    **_menus("heat_rate joule_power", POWER),
    **_menus("heat_rate_per_depth joule_power_per_depth heat_rate_per_depth_tolerance", W_M),
    "heat_flux": ("W/m^2", "kW/m^2", "W/cm^2", "W/mm^2", "mW/mm^2"),
    "heat_transfer_coefficient": ("W/(m^2 K)", "kW/(m^2 K)", "W/(cm^2 K)"),
    **_menus("time time_step duration output_times", TIME),
    "electric_potential": ("uV", "mV", "V", "kV"), "electric_potential_tolerance": ("uV", "mV", "V"),
    **_menus("electrical_conductivity reference_conductivity", SIGMA),
    **_menus("electrical_resistivity reference_resistivity", RHO),
    **_menus("resistivity_temperature_coefficient conductivity_temperature_coefficient volumetric_expansion_coefficient "
             "thermo_optic_coefficient", PER_K),
    **_menus("current axial_current", ("uA", "mA", "A", "kA")),
    "current_per_depth": ("A/m", "A/mm", "mA/mm"), "sheet_current_density": ("A/m", "A/mm"),
    "current_density": ("A/m^2", "A/mm^2", "A/cm^2", "A/um^2", "mA/um^2"),
    "electric_field": ("V/m", "V/mm", "V/um", "kV/mm", "kV/cm"),
    "resistance": ("nOhm", "uOhm", "mOhm", "Ohm", "kOhm"),
    **_menus("characteristic_impedance reference_impedance reactance", ("mOhm", "Ohm", "kOhm")),
    "free_charge_density": ("C/m^3", "C/cm^3"),
    "capacitance_per_length": ("pF/m", "nF/m", "pF/cm", "pF/mm"),
    "inductance_per_length": ("nH/m", "uH/m", "nH/mm", "nH/cm"),
    "resistance_per_length": ("Ohm/m", "mOhm/mm", "Ohm/mm", "Ohm/cm"),
    "conductance_per_length": ("S/m", "mS/m", "uS/m"),
    **_menus("frequency target_frequency reference_frequency lower_corner_frequency upper_corner_frequency", HZ),
    **_menus("huray_sphere_radius rms_roughness", ("nm", "um")),
    **_menus("youngs_modulus shear_modulus bulk_modulus", MODULUS),
    "elasticity_tensor": ("GPa", "MPa", "Pa"),
    **_menus("linear_expansion_coefficient mean_linear_expansion_coefficient", ("1/K", "ppm/K", "um/(m K)")),
    "displacement": ("pm", "nm", "um", "mm", "m", "in", "mil"),
    "gauge_pressure": ("Pa", "kPa", "MPa", "GPa", "bar", "mbar", "psi", "ksi", "barg", "psig"),
    **_menus("traction stress von_mises_stress", STRESS),
    "body_force_density": ("N/m^3", "kN/m^3", "N/mm^3"), "gravitational_acceleration": ("m/s^2",),
    **_menus("strain elastic_strain thermal_strain engineering_shear_strain_xy", ("1", "ppm")),
    **_menus("force reaction_force", ("mN", "N", "kN")),
    **_menus("force_per_depth reaction_force_per_depth", ("N/m", "N/mm", "kN/m")),
    "strain_energy": ("mJ", "J", "kJ"), "strain_energy_per_depth": ("J/m", "mJ/mm"),
    "vacuum_wavelength": ("nm", "um", "m"), "air_wavelength": ("nm", "um"),
    **_menus("photon_energy plasma_energy damping_energy resonance_energy", ENERGY_EV),
    "vacuum_wavenumber": ("1/cm", "1/m"), "vacuum_angular_wavenumber": ("rad/m", "rad/um"),
    "propagation_loss": ("dB/m", "dB/cm", "dB/mm"), "bend_loss": ("dB/(90 deg)", "dB/(180 deg)"),
    "phase_shift": ("rad", "deg", "mrad"),
    **_menus("confinement_factor overlap coupling_efficiency relative_humidity", ("1", "%")),
    "co2_mole_fraction": ("1", "ppm", "%"),
    "absolute_pressure": ("Pa", "kPa", "hPa", "bar", "mbar", "atm", "bara", "psia"),
    "vapor_pressure": ("Pa", "kPa", "hPa"),
}
# Reviewed additions: the canonical unit, put on the menus where 4.8 leaves it out, so that R11
# (each canonical unit is on its menu) holds. Recorded in docs/packages/physmat/units.md.
CANONICAL_ADDED = {"capacitance_per_length": "F/m", "inductance_per_length": "H/m", "huray_sphere_radius": "m",
                   "rms_roughness": "m", "air_wavelength": "m", "photon_energy": "J", "plasma_energy": "J",
                   "damping_energy": "J", "resonance_energy": "J"}
# Output rows of 4.8 with no menu ("—"): the canonical unit only.
OUTPUT_ONLY = {"node_coordinates": "m", "stored_heat": "J", "stored_heat_per_depth": "J/m", "heat_storage_rate": "W",
               "heat_storage_rate_per_depth": "W/m", "thermal_energy_functional": "J K",
               "thermal_energy_functional_per_depth": "J K/m", "thermal_diffusivity": "m^2/s",
               "conductance_per_depth": "S/m", "permittivity": "F/m", "charge": "C", "charge_per_depth": "C/m",
               "capacitance": "F", "capacitance_per_depth": "F/m", "stored_energy": "J", "stored_energy_per_depth": "J/m",
               "scattering_parameter": "1", "skin_depth": "m", "phase_shift_per_depth": "rad/m",
               "pi_phase_shift_power": "W", "mode_power": "W", "effective_area": "m^2", "magnetic_field": "A/m",
               "resonant_frequency": "Hz", "quality_factor": "1", "wavenumber_squared": "1/m^2",
               "relative_residual": "1", "relative_conservation_residual": "1", "transferred_power": "W",
               "transferred_power_per_depth": "W/m", "wall_time": "s",
               **{f"{w}_heat_rate{d}": "W" + d.replace("_per_depth", "/m")
                  for w in ("applied", "reaction", "residual", "convective", "prescribed") for d in ("", "_per_depth")}}


# Phase-2 registry additions (spec section 6, R-7..R-22), written from the spec's table, not read
# from quantities.json: inputs with their menus, and output-only entries with their canonical unit.
PHASE2_MENUS = {
    "constant": BARE, "strength": BARE, "resonance_wavelength": ("nm", "um", "m"),
    "resonance_wavelength_squared": ("nm^2", "um^2", "m^2"), "effective_index_threshold": BARE,
    "bend_origin": L_MENU, "search_mode_count": BARE, "mode_tracking_margin_threshold": BARE,
    "cluster_span_tolerance": BARE, "cluster_gap_threshold": BARE,
}
PHASE2_OUTPUT_ONLY = {
    **{f"{base}{d}": unit + d.replace("_per_depth", "/m")
       for base, unit in (("heat_rate_imbalance", "W"), ("current_imbalance", "A"), ("electric_power_imbalance", "W"),
                          ("force_imbalance", "N"), ("reaction_current", "A"), ("prescribed_current", "A"),
                          ("residual_current", "A"), ("electric_power", "W"), ("applied_force", "N"),
                          ("applied_body_force", "N"), ("applied_traction_force", "N"),
                          ("thermal_equivalent_force", "N"), ("residual_force", "N"),
                          ("stiffness_energy_functional", "J"))
       for d in ("", "_per_depth")},
    "relative_electrical_conductivity_change": "1", "triangle_angle": "rad", "returned_mode_count": "1",
    "relative_residual_threshold": "1", "physical_l2_fraction": "1", "pml_l2_fraction": "1",
    "engineering_shear_elastic_strain_xy": "1", "engineering_shear_thermal_strain_xy": "1",
    "mode_field": "1", "electric_field_line_integral": "V", "mode_field_square_integral": "m^2",
    "field_overlap": "m^2", "unnormalized_electric_field": "1", "unnormalized_electric_field_line_integral": "m",
    "mass_normalized_electric_field": "1/m^(3/2)", "mass_normalized_electric_field_line_integral": "1/m^(1/2)",
}


def test_r11_every_menu_equals_the_design_table():
    tables = (DESIGN_MENUS, OUTPUT_ONLY, PHASE2_MENUS, PHASE2_OUTPUT_ONLY)
    assert set().union(*tables) == set(BASES) and sum(len(t) for t in tables) == len(BASES)
    for base, menu in {**DESIGN_MENUS, **PHASE2_MENUS}.items():
        want = menu + ((CANONICAL_ADDED[base],) if base in CANONICAL_ADDED else ())
        assert units.menu(base) == want, (base, units.menu(base), want)
    for base, unit in CANONICAL_ADDED.items():
        assert units.quantity(base).unit == unit and unit not in DESIGN_MENUS[base], base
    for base, unit in {**OUTPUT_ONLY, **PHASE2_OUTPUT_ONLY}.items():
        assert units.menu(base) == (unit,) and units.quantity(base).places == ("result",) or base in (
            "conductance_per_depth",), base


def test_r11_statistic_names_of_results():
    for name in ("minimum_overlap", "maximum_overlap", "mean_overlap", "maximum_temperature"):
        assert name in units.names() and units.quantity(name).base == name.split("_", 1)[1]
    assert "minimum_overlap_threshold" not in units.names()           # a threshold takes no statistic (4.2)


def test_q_array_string_lists_are_short_vectors():
    assert q_array(["1 m", "2 m", "3 m"], "position") == [1.0, 2.0, 3.0]
    for bad in (["1 m"] * 4, [["1 m"], ["2 m"]], ["1 m"] * 10):
        with pytest.raises(TypeError, match="at most 3 components"):
            q_array(bad, "position")
    assert q_array({"unit": "m", "values": [1] * 10}, "position") == [1.0] * 10


def test_gauge_and_absolute_marked_pressures_are_not_reexpressed():
    for text in ("2 barg", "2 psig"):
        err = convert(text, "absolute_pressure").error
        assert err.code == "E-UNIT-NOT-ACCEPTED" and err.suggestions == () and "gauge pressure" in err.message, text
    assert convert("2 bara", "youngs_modulus").error.suggestions == ()
    assert q("2 barg", "gauge_pressure") == 2e5 and q("1.2 bara", "absolute_pressure") == 1.2e5


def test_numpy_scalars_and_arrays():
    np = pytest.importorskip("numpy")
    assert q(np.float64(0.3), "poisson_ratio") == 0.3 and type(q(np.float64(0.3), "poisson_ratio")) is float
    assert q(np.float32(0.25), "poisson_ratio") == 0.25                 # read as its exact double
    assert q(np.float32(0.3), "poisson_ratio") == float(np.float32(0.3))
    assert q(np.int64(2), "mode_count") == 2.0
    assert convert(np.float64(1550.0), "length").error.code == "E-UNIT-MISSING"
    assert convert(np.float64(2.0), "mode_count").error.fix.value == 2
    data = np.array([1500.0, 1550.0])
    for values in (data, list(data), data.reshape(1, 2)):
        out = q_array({"unit": "nm", "values": values}, "vacuum_wavelength")
        assert out in ([1.5e-06, 1.55e-06], [[1.5e-06, 1.55e-06]])
    assert length_to_pm(np.float64(0.1), "mm").picometres == 100_000_000
    assert units.pm_to_m(np.int64(100_000_000_000)) == 0.1
    with pytest.raises(TypeError):
        q(np.bool_(True), "poisson_ratio")


def test_pm_to_m_takes_integers_only():
    assert units.pm_to_m(-1) == -1e-12 and units.pm_to_m(2 ** 63 - 1) == float(F(2 ** 63 - 1, 10 ** 12))
    for bad in (2.9, 0.5, "12", True, F(3), Decimal(3)):
        with pytest.raises(TypeError):
            units.pm_to_m(bad)


def _suggestion_corpus():
    numbers = ("1", "0.001", "123456.789", "7", "2.5e-4", "3e5")
    t = tables()
    by_dim = {}                                  # only spellings of the quantity's dimension get suggestions
    for spelling, entry in t["refused"].items():
        if entry["code"] != "E-UNIT-AMBIGUOUS":
            dim = t["units"][entry["fix"]]["dimension"] if "fix" in entry else entry["dimension"]
            by_dim.setdefault(json.dumps(dim, sort_keys=True), []).append(spelling)
    for spelling, unit in t["spellings"].items():
        if spelling == unit or spelling.casefold() != spelling:
            by_dim.setdefault(json.dumps(t["units"][unit]["dimension"], sort_keys=True), []).append(spelling)
    for base in BASES:
        qo = units.quantity(base)
        dim = json.dumps({k: v for k, v in qo.dimension.items() if v}, sort_keys=True)
        texts = [f"{n} {s}" for s in by_dim.get(dim, []) for n in numbers]
        texts += [f"{n} {s.swapcase()}" for s in by_dim.get(dim, []) for n in numbers[:2]]   # case slips
        for text in texts:
            err = convert(text, base).error
            for d in (err,) if err else convert(text, base).diagnostics:
                yield from ((qo, s) for s in d.suggestions if s.si_after is not None)


def test_every_suggestion_converts_to_its_si_after():
    checked = 0
    for qo, s in _suggestion_corpus():
        read = units._parse(s.value, qo, "") if isinstance(s.value, str) else None
        if read is None:
            got = float(units._bare_number(s.value)[0])
        else:
            assert not isinstance(read, units.Diagnostic), (qo.name, s)
            got = float(units._to_canonical(read.number, read.unit or "1", qo))
        assert bits(got) == bits(s.si_after), (qo.name, s)
        checked += 1
    assert checked > 5000


def test_formatting_ignores_the_callers_decimal_context():
    import decimal
    with decimal.localcontext() as ctx:
        ctx.prec = 5
        ctx.traps[decimal.Inexact] = True
        ctx.traps[decimal.Rounded] = True
        assert units.format(0.30000000000000004, "poisson_ratio") == "0.30000000000000004"
        assert units.format(1.2345678912345e-6, "vacuum_wavelength", "nm") == "1234.5678912345 nm"
        s = convert("123456.789 mPa", "youngs_modulus").error.suggestions
        assert [x.value for x in s] == ["123456.789 MPa", "123.456789 Pa"]
        w = length_to_pm("300000000.0000000000004 pm").diagnostics[0]
        assert "300000000.0000000000004 pm" in w.message and "-4e-13 pm" in w.message


def test_format_round_trips_on_every_menu_unit():
    values = (1.0, 0.1 + 0.2, 1 / 3, 2.0 ** -40, 6.02214076e23, 1.5e308, 1.7976931348623157e308, 1e-300, 298.15,
              1.0336557535322433e-22)
    for base in BASES:
        qo = units.quantity(base)
        for unit in qo.menu:
            for x in values:
                text = units.format(x, base, unit)
                number = text if unit == "1" else text.rsplit(" " + unit, 1)[0]
                assert units.normalize(text) == text and (unit == "1" or text.endswith(" " + unit))
                got = float(units._to_canonical(F(Decimal(number)), unit, qo))
                assert bits(got) == bits(x), (base, unit, x, text)
    assert units.format(1.0336557535322433e-22, "temperature", "degC").startswith("-273.149999999999999999999")


def test_long_numbers_are_converted_quickly():
    import time
    start = time.perf_counter()
    err = convert("1." + "3" * 100000 + " mPa", "youngs_modulus").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and time.perf_counter() - start < 10    # 14 s before the fix


def test_quantity_objects_are_read_only():
    qo = units.quantity("shear_modulus")
    with pytest.raises(TypeError):
        qo.band["abs_range"][0] = "1e12"
    with pytest.raises(TypeError):
        qo.band["abs_range"] = ["1e12", None]
    with pytest.raises(TypeError):
        qo.domain["min_exclusive"] = "-1"
    assert convert("200 GPa", "shear_modulus").diagnostics == ()


def test_case_look_alikes_name_every_reading():
    err = convert("1 ms/m", "electrical_conductivity").error
    assert err.code == "E-UNIT-UNKNOWN" and [s.value for s in err.suggestions] == ["1 MS/m"]
    assert "MS/m (megasiemens per metre, 1e6 S/m, on the menu)" in err.message
    assert "mS/m (millisiemens per metre, 0.001 S/m, not on the electrical_conductivity menu)" in err.message
    err = convert("1 mpa", "youngs_modulus").error
    assert "MPa (megapascal, 1e6 Pa, on the menu)" in err.message and "mPa (millipascal, 0.001 Pa, refused)" in \
        err.message
    err = convert("1 MW/(m K)", "thermal_conductivity").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and "megawatt per metre kelvin" in err.message
    assert [(s.value, s.si_before, s.si_after) for s in err.suggestions][0] == ("1 mW/(m K)", 1e6, 1e-3)
    assert "Equal to" not in convert("1 Mm", "length").error.message      # a refused spelling: its own reading


def test_regeneration_repairs_a_broken_table(tmp_path):
    src = Path(units.__file__).resolve().parent
    copy = tmp_path / "physmat"
    copy.mkdir()
    for name in ("__init__.py", "_unit_tables.py", "units.py", "quantities.json"):
        (copy / name).write_bytes((src / name).read_bytes())
    (copy / "unit_tables.json").write_bytes(b"<<<<<<< HEAD\n" + (src / "unit_tables.json").read_bytes())
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONSTARTUP")}
    env["PYTHONPATH"] = str(tmp_path)
    command = [sys.executable, "-B", "-m", "physmat._unit_tables"]
    assert subprocess.run(command + ["--check"], cwd=tmp_path, env=env, capture_output=True, timeout=300).returncode == 1
    subprocess.run(command + ["--write"], cwd=tmp_path, env=env, capture_output=True, timeout=300, check=True)
    assert (copy / "unit_tables.json").read_bytes() == (src / "unit_tables.json").read_bytes()
    run = subprocess.run([sys.executable, "-B", "-m", "physmat.units", "--check"], cwd=tmp_path, env=env,
                         capture_output=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr


def test_star_import_keeps_builtins_and_physmat_names():
    assert "format" not in units.__all__ and "names" not in units.__all__
    namespace = {}
    exec("from physmat.units import *", namespace)
    assert "format" not in namespace and "names" not in namespace and "q" in namespace


# ---- phase-2 registry additions and converter API (units and naming, step 2; spec section 6) ----------------------
# Expected values below are written from the spec's R-items, not read from quantities.json.

def test_p2_r1_reader_diagnostic_codes():
    want = {"E-FORMAT": "error", "E-JSON": "error", "E-VALUE-FORM": "error", "E-MATERIAL-UNKNOWN": "error",
            "E-CONTRACT": "error", "W-SHAPE-DROPPED": "warning", "W-PIECE-DROPPED": "warning",
            "I-MESH-CONTROL-RAISED": "info"}
    for code, severity in want.items():
        c = units.DIAGNOSTIC_CODES[code]
        assert c["severity"] == severity and c["en"] and c["ko"], code
        assert units.Diagnostic(code, "a.b", "text").as_dict()["severity"] == severity


def _names(text: str) -> list[str]:
    return text.split()


P2_NAMES = {  # name: (canonical unit, places) for every name R-2..R-22 makes legal
    **{n: ("K", ("document", "material", "api", "result")) for n in _names("prescribed_temperature")},
    "prescribed_electric_potential": ("V", ("document", "api", "result")),
    "prescribed_displacement": ("m", ("document", "api", "result")),
    "evaluation_temperature": ("K", ("api", "result")),
    **{f"{w}_{b}{d}": ("W/m" if d else "W", ("result",))
       for w, b in (("outward", "prescribed_heat_rate"), ("outward", "convective_heat_rate"),
                    ("outward", "reaction_heat_rate"), ("ambient", "convective_heat_rate"),
                    ("maximum", "residual_heat_rate"), ("inward", "electric_power"))
       for d in ("", "_per_depth")},
    **{f"{b}{d}": (u + ("/m" if d else ""), ("result",))
       for b, u in (("heat_rate_imbalance", "W"), ("current_imbalance", "A"), ("electric_power_imbalance", "W"),
                    ("force_imbalance", "N"), ("reaction_current", "A"), ("outward_prescribed_current", "A"),
                    ("residual_current", "A"), ("maximum_residual_current", "A"), ("applied_force", "N"),
                    ("applied_body_force", "N"), ("applied_traction_force", "N"), ("thermal_equivalent_force", "N"),
                    ("residual_force", "N"), ("maximum_residual_force", "N"), ("stiffness_energy_functional", "J"))
       for d in ("", "_per_depth")},
    "relative_electrical_conductivity_change": ("1", ("result",)),
    **{n: ("1", ("material",)) for n in _names("strength constant")},
    "resonance_wavelength": ("m", ("material",)), "resonance_wavelength_squared": ("m^2", ("material",)),
    "effective_index_threshold": ("1", ("document", "api", "result")),
    "bend_origin": ("m", ("document", "api")),
    "minimum_triangle_angle": ("rad", ("result",)),
    "search_mode_count": ("1", ("document", "api", "result")), "returned_mode_count": ("1", ("result",)),
    **{n: ("1", ("document", "api", "result"))
       for n in _names("mode_tracking_margin_threshold cluster_span_tolerance cluster_gap_threshold")},
    **{n: ("1", ("result",)) for n in _names("relative_residual_threshold physical_l2_fraction pml_l2_fraction "
                                             "mean_effective_index mean_group_index "
                                             "engineering_shear_elastic_strain_xy "
                                             "engineering_shear_thermal_strain_xy")},
    "maximum_displacement": ("m", ("document", "api", "result")),
    "unnormalized_mode_field": ("1", ("result",)), "unnormalized_electric_field": ("1", ("result",)),
    "unnormalized_electric_field_z": ("1", ("result",)),
    "unnormalized_electric_field_line_integral": ("m", ("result",)), "unnormalized_mode_power": ("W", ("result",)),
    "unnormalized_mode_field_square_integral": ("m^2", ("result",)), "unnormalized_field_overlap": ("m^2", ("result",)),
    "mass_normalized_electric_field": ("1/m^(3/2)", ("result",)),
    "mass_normalized_electric_field_line_integral": ("1/m^(1/2)", ("result",)),
}


def test_p2_names_are_legal_with_their_unit_and_places():
    names = set(units.names())
    for name, (unit, places) in P2_NAMES.items():
        assert name in names, name
        qo = units.quantity(name)
        assert (qo.unit, qo.places) == (unit, places), (name, qo.unit, qo.places)
    for name in ("unnormalized_electric_field_x", "evaluation_heat_rate", "prescribed_current_per_depth_x",
                 "maximum_maximum_displacement", "outward_ambient_convective_heat_rate", "node_count", "element_count",
                 "joule_heat_rate_per_depth", "minimum_principal_squared", "near_element_size"):
        assert name not in names, name                      # spec section 6, "not added"
    assert len(units._ENTRIES) == 242 and len(names) == 367


def test_p2_r2_r5_temperatures_and_potentials():
    for name in ("prescribed_temperature", "evaluation_temperature"):
        qo = units.quantity(name)
        assert qo.kind == "absolute" and q("25 degC", name) == 298.15
        assert convert("0 K", name).error.code == "E-DOMAIN"
    assert q("1 mV", "prescribed_electric_potential") == 1e-3
    assert q("0 mm", "prescribed_displacement_x") == 0.0
    reg = registry()
    assert reg["output_only_words"] == ["evaluation", "unnormalized", "mass_normalized"]
    assert set(reg["output_only_words"]) <= set(reg["qualifier_words"]["role"])


def test_p2_r11_sellmeier_parameters():
    for name in ("constant", "strength", "resonance_wavelength", "resonance_wavelength_squared"):
        qo = units.quantity(name)
        assert dict(qo.scope) == {"quantity": "refractive_index", "model": "sellmeier"} and qo.places == ("material",)
    assert units.menu("resonance_wavelength") == ("nm", "um", "m")
    assert units.menu("resonance_wavelength_squared") == ("nm^2", "um^2", "m^2")
    assert convert(-0.1, "strength").error.code == "E-DOMAIN" and q(0, "strength") == 0.0
    assert [d.code for d in convert(0.5, "constant").diagnostics] == ["W-MAGNITUDE"]
    assert ">= 1" in convert(0.5, "constant").diagnostics[0].message
    assert convert(1, "constant").diagnostics == () and convert(2.1, "constant").diagnostics == ()
    # C in um^2 and lambda in um give the same exact SI values as the micrometre coefficients physmat uses.
    c = convert("0.0684043 um^2", "resonance_wavelength_squared")
    assert c.exact == F("0.0684043") / 10 ** 12 and bits(c.value) == bits(float(F("0.0684043e-12")))
    assert q("68.4043 nm", "resonance_wavelength") == float(F("68.4043e-9"))
    err = convert("0.0684043 um2", "resonance_wavelength_squared").error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and err.fix.value == "0.0684043 um^2"
    # Model parameters are never named in a dimension hint.
    for text, name in (("1550 nm", "frequency"), ("5 mm", "temperature"), ("1 um^2", "length")):
        msg = convert(text, name).error.message
        assert "resonance_wavelength" not in msg and "strength" not in msg, msg


def test_p2_r12_to_r17_inputs_and_domains():
    assert convert(0, "effective_index_threshold").error.code == "E-DOMAIN" and q(1.45, "effective_index_threshold")
    assert q("-5 um", "bend_origin") == -5e-6 and q("0 mm", "bend_origin") == 0.0
    assert units.menu("bend_origin") == L_MENU
    assert units.quantity("minimum_triangle_angle").unit == "rad"
    assert convert(0, "mode_tracking_margin_threshold").error.code == "E-DOMAIN"
    assert q(1, "mode_tracking_margin_threshold") == 1.0 and convert(1.5, "mode_tracking_margin_threshold").error
    for name in ("cluster_span_tolerance", "cluster_gap_threshold", "relative_residual_threshold"):
        assert convert(0, name).error.code == "E-DOMAIN" and q(1e-8, name) == 1e-8
    assert q(6, "search_mode_count") == 6.0 and convert(0, "search_mode_count").error.code == "E-DOMAIN"
    assert convert(2.0, "returned_mode_count").error.fix.value == 2
    assert convert("0 Hz", "target_frequency").error.code == "E-DOMAIN" and q("250 MHz", "target_frequency") == 2.5e8
    assert units.quantity("subdivision_count").rank == ("vector",)


def test_p2_r20_r21_statistic_definitions_and_ranks():
    d = units.quantity("maximum_displacement")
    assert "Euclidean norm" in d.definition["en"] and d.definition["ko"] and d.rank == ("scalar",)
    s = units.quantity("maximum_stress")
    assert "largest absolute in-plane cartesian" in s.definition["en"].lower() and s.rank == ("scalar",)
    assert units.quantity("maximum_residual_force_per_depth").rank == ("scalar",)
    assert units.quantity("displacement").rank == ("vector",) and units.quantity("displacement").definition is None
    assert units.quantity("maximum_temperature").definition is None


def test_p2_r22_half_power_output_units_are_exact():
    for unit, exponent in (("1/m^(1/2)", -0.5), ("1/m^(3/2)", -1.5)):
        rec = tables()["units"][unit]
        assert rec["dimension"] == {"L": exponent} and rec["factor"] == "1" and rec["angle"] == 0
    name = "mass_normalized_electric_field_line_integral"
    for text in ("2.5 1/m^(1/2)", "2.5 m^(-1/2)"):
        c = convert(text, name)
        assert c.ok and c.exact == F(5, 2) and c.text == "2.5 1/m^(1/2)", text
    assert convert("2.5 1/m(1/2)", name).error.code == "E-UNIT-UNKNOWN"     # no "written without ^" entry
    assert units.format(0.1, "mass_normalized_electric_field", "1/m^(3/2)") == "0.1 1/m^(3/2)"
    inputs = {u for e in registry()["quantities"].values() if {"document", "material"} & set(e["places"])
              for u in e["menu"]}
    assert not {"1/m^(1/2)", "1/m^(3/2)"} & inputs                       # on no input menu
    assert units.quantity("mode_power").base == "mode_power" == units.quantity("unnormalized_mode_power").base


def test_p2_r24_display_group_length():
    groups = units.display_groups()
    g = groups["length"]
    assert tuple(g["menu"]) == units.LENGTH_UNITS and g["shape_numbers"] is True
    want = sorted(n for n in units.names() if dict(units.quantity(n).dimension) == {"L": 1})
    assert list(g["quantities"]) == want
    assert {"length", "depth", "element_size", "vacuum_wavelength", "displacement", "node_coordinates",
            "bend_origin", "pml_thickness", "position"} <= set(want) and "area" not in want
    with pytest.raises(TypeError):
        groups["length"]["menu"] = ("m",)


def test_p2_r25_number_and_unit_text():
    cases = [("30 deg", "minimum_angle", "30", "deg"), ("28.5 °", "minimum_angle", "28.5", "deg"),
             ("148 W·m⁻¹·K⁻¹", "thermal_conductivity", "148", "W m^-1 K^-1"),
             ("25°C", "temperature", "25", "degC"), ("1 µm", "length", "1", "um")]
    for text, name, number, unit in cases:
        c = convert(text, name)
        assert c.ok and (c.number_text, c.unit_text) == (number, unit), (text, c)
    for value, number in ((0.3, "0.3"), (Decimal("0.30"), "0.30"), (2, "2")):
        c = convert(value, "poisson_ratio" if value != 2 else "mode_count")
        assert (c.number_text, c.unit_text) == (number, None)
    assert (convert("1e400 Pa", "traction").number_text, convert("1e400 Pa", "traction").unit_text) == ("1e400", "Pa")
    assert convert("5 furlong", "length").number_text is None                  # refused before the number is read
    # H3: the authored degree number goes to the mesher, not degrees(radians): 30 and 28.5 do not round-trip.
    for text in ("30 deg", "28.5 deg"):
        c = convert(text, "minimum_angle")
        assert float(F(c.number_text)) == float(text.split()[0]) and math.degrees(c.value) != float(c.number_text)


def test_p2_r25_convert_array_reports_every_entry():
    a = units.convert_array({"unit": "nm", "values": [1500, -1, "x", True, [1550, 10 ** 5000]]}, "vacuum_wavelength",
                            path="study.values")
    assert a.values == [1.5e-06, None, None, None, [1.55e-06, None]] and a.unit == "m" and a.unit_text == "nm"
    assert [(d.code, d.path) for d in a.diagnostics] == [
        ("E-DOMAIN", "study.values.values[1]"), ("E-VALUE-FORM", "study.values.values[2]"),
        ("E-VALUE-FORM", "study.values.values[3]"), ("E-DOMAIN", "study.values.values[4][1]")]
    assert len(a.entries) == 6 and a.error.code == "E-DOMAIN" and not a.ok
    w = units.convert_array({"unit": "Pa", "values": [210000, 2e11]}, "youngs_modulus")
    assert w.ok and w.values == [210000.0, 2e11] and [d.code for d in w.diagnostics] == ["W-MAGNITUDE"]
    assert units.convert_array({"unit": "µm", "values": [1]}, "length").unit_text == "um"
    assert units.convert_array({"unit": "µm", "values": [1]}, "length").entries[0].unit_text == "um"
    for values, code, path in (({"unit": "Mm", "values": [1]}, "E-UNIT-NOT-ACCEPTED", "unit"),
                               ({"unit": "nm"}, "E-KEY-MISSING", "values"),
                               ({"unit": "nm", "values": [1], "x": 1}, "E-KEY-UNKNOWN", "x"),
                               ({"unit": 5, "values": [1]}, "E-VALUE-FORM", "unit"),
                               ({"unit": "nm", "values": 5}, "E-VALUE-FORM", "values"),
                               (["1 m"] * 4, "E-VALUE-FORM", ""), (5, "E-VALUE-FORM", ""),
                               ([True], "E-VALUE-FORM", "[0]"), ({"values": ["1"]}, "E-VALUE-FORM", "values[0]")):
        a = units.convert_array(values, "position")
        assert a.error.code == code and a.error.path == path, (values, a.diagnostics)
    with pytest.raises(UnitError):
        units.convert_array([1], "no_such_quantity")


def test_p2_r25_q_array_keeps_its_contract():
    # q_array is convert_array that raises: TypeError for a value form, UnitError for the first error.
    for values, name in (({"unit": "nm", "values": [1500, 1550]}, "vacuum_wavelength"),
                         (["0 MPa", "-5 MPa"], "traction"), ({"values": [3.48, 3.47]}, "refractive_index"),
                         ({"unit": "GPa", "values": [[200, 80]]}, "elasticity_tensor")):
        assert q_array(values, name) == units.convert_array(values, name).values
    with pytest.raises(TypeError, match="bare numbers"):
        q_array({"unit": "nm", "values": [10 ** 5000, "1"]}, "length")      # a form error wins, as before
    with pytest.raises(TypeError, match="not bool"):
        q_array([True], "position")
    with pytest.raises(UnitError) as info:
        q_array({"unit": "nm", "values": [-1, 10 ** 5000]}, "vacuum_wavelength")
    assert info.value.diagnostic.path == "values[0]"


def test_p2_r25_is_quantity_text():
    for text, want in (("0.5 um", True), ("10 mPa", True), ("25 degC", True), ("40%", True), ("220 ㎚", True),
                       ("5 W/mK", True), ("1 MW/m^3", True), ("w/2", False), ("220 nm + gap", False), ("0.5", False),
                       ("0.5um", False), ("2 furlong", False), ("", False), (0.5, False), (None, False)):
        assert units.is_quantity_text(text) is want, text


P2_COMPOUNDS = [  # (text, quantity, reading, SI value as written)
    ("5 MW/m^3", "heat_source_density", "megawatt per cubic metre", 5e6),
    ("10 mW/(m^2 K)", "heat_transfer_coefficient", "milliwatt per square metre kelvin", 0.01),
    ("2 V/cm", "electric_field", "volt per centimetre", 200.0),
    ("3 kW/m^3", "heat_source_density", "kilowatt per cubic metre", 3000.0),
    ("1 MV/m", "electric_field", "megavolt per metre", 1e6),
    ("1 mS/cm", "electrical_conductivity", "millisiemens per centimetre", 0.1),
    ("2 kA/m^2", "current_density", "kiloampere per square metre", 2000.0),
    ("1 W/(mm K)", "thermal_conductivity", "watt per millimetre kelvin", 1000.0),
    ("4 g/m^3", "mass_density", "gram per cubic metre", 0.004),
    ("3 km^2", "area", "square kilometre", 3e6),
    ("5 1/mm", "vacuum_wavenumber", "per millimetre", 5000.0),
]


@pytest.mark.parametrize("text, name, reading, si", P2_COMPOUNDS)
def test_p2_r25_compound_refusals_name_their_reading(text, name, reading, si):
    err = convert(text, name).error
    assert err.code == "E-UNIT-NOT-ACCEPTED" and reading in err.message, err
    assert f"As written it is {units._num(si)}" in err.message, err.message
    for s in err.suggestions:                                    # re-expressions keep the value
        assert s.si_after == si or s.si_before == si, s


def _render(factors: list) -> str:
    num = [(s, e) for s, e in factors if e > 0]
    den = [(s, -e) for s, e in factors if e < 0]

    def one(s, e):
        return s if e == 1 else f"{s}^{e}"
    head = " ".join(one(*f) for f in num) or "1"
    if not den:
        return head
    return f"{head}/{one(*den[0])}" if len(den) == 1 else f"{head}/({' '.join(one(*f) for f in den)})"


def test_p2_r25_every_re_prefixed_input_compound_is_read():
    """One factor of an input-menu compound in another common prefix is accepted or refused by name, never
    E-UNIT-UNKNOWN (kelvin and degC factors excepted; "c" only on the metre)."""
    reg = registry()
    prefixable, prefixes = set(reg["prefixable"]), sorted(reg["prefixes"], key=len, reverse=True)

    def split(sym):
        for p in prefixes:
            if sym.startswith(p) and sym[len(p):] in prefixable:
                return p, sym[len(p):]
        return "", sym
    checked = 0
    for name, e in reg["quantities"].items():
        if not {"document", "material"} & set(e["places"]):
            continue
        for unit in e["menu"]:
            factors = parse_unit(unit)
            if not factors or any(s.isdigit() for s, _ in factors) or (len(factors) == 1 and factors[0][1] == 1):
                continue                                    # a bare symbol: its prefixes are refused as symbols
            for i, (sym, exp) in enumerate(factors):
                base = split(sym)[1]
                if base in ("K", "degC"):
                    continue
                for p in ("", "p", "n", "u", "m", "k", "M", "G") + (("c",) if base == "m" else ()):
                    other = p + base
                    if other == sym or split(other) != (p, base) or (other not in SYMBOLS and base not in prefixable):
                        continue
                    text = _render([(other, x) if j == i else (s, x) for j, (s, x) in enumerate(factors)])
                    got = convert(f"1 {text}", name)
                    assert got.ok or got.error.code == "E-UNIT-NOT-ACCEPTED", (name, text, got.error)
                    checked += 1
    assert checked > 1000


def test_p2_r26_sign_sentences():
    listed = _names("inward_heat_flux inward_current_density outward_heat_rate outward_heat_rate_per_depth "
                    "outward_current outward_current_per_depth heat_flux gauge_pressure traction refractive_index "
                    "relative_permittivity effective_index resonant_frequency propagation_loss bend_loss")
    listed += [f"{b}{d}" for b in ("reaction_heat_rate", "reaction_current", "reaction_force",
                                   "outward_prescribed_heat_rate", "outward_convective_heat_rate",
                                   "ambient_convective_heat_rate", "generated_heat_rate", "applied_heat_rate",
                                   "applied_force", "inward_electric_power") for d in ("", "_per_depth")]
    for name in listed:
        sign = units.quantity(name).sign
        assert sign is not None and sign["en"] and sign["ko"], name
    # Every name with a direction word carries its sentence, which says which way is positive.
    for name in units.names():
        word = name.split("_", 1)[0]
        if word in ("inward", "outward"):
            sign = units.quantity(name).sign
            assert sign is not None, name
            assert ("enters the body" if word == "inward" else "leaves the body") in sign["en"], name
    assert "k >= 0 is loss" in units.quantity("refractive_index").sign["en"]
    assert "Im >= 0 is loss" in units.quantity("relative_permittivity").sign["en"]
    assert "Im >= 0 is loss" in units.quantity("effective_index").sign["en"]
    assert "Im < 0 decays" in units.quantity("resonant_frequency").sign["en"]
    assert "pushes into the body" in units.quantity("gauge_pressure").sign["en"]
    assert "enters the body" in units.quantity("ambient_convective_heat_rate").sign["en"]    # Q7 (b)
    assert units.quantity("temperature").sign is None


def test_p2_r27_r28_descriptions_and_normal_components():
    assert "Re eps_r |E|^2" in units.quantity("confinement_factor").description["en"]
    for name in ("inward_heat_flux", "outward_heat_flux", "inward_current_density"):
        assert units.quantity(name).rank == ("scalar",), name
    assert units.quantity("heat_flux").rank == ("vector",) and units.quantity("current_density").rank == ("vector",)


def test_p2_r31_echoed_inputs_are_results():
    for name in _names("heat_transfer_coefficient heat_source_density stress_free_temperature body_force_density "
                       "traction gauge_pressure prescribed_displacement vacuum_wavelength target_frequency mode_count "
                       "pml_thickness pml_strength pml_order pml_minimum_physical_fraction mode_tracking_threshold "
                       "mode_tracking_margin_threshold degeneracy_tolerance cluster_span_tolerance "
                       "cluster_gap_threshold search_mode_count effective_index_threshold beam_waist_radius position "
                       "thermal_conductivity volumetric_heat_capacity electrical_conductivity youngs_modulus "
                       "poisson_ratio linear_expansion_coefficient relative_permittivity relative_permeability"):
        assert "result" in units.quantity(name).places, name


def test_p2_r32_did_you_mean_hints():
    for key, names in (("n_eff", ("effective_index", "target_effective_index")), ("neff", ("effective_index",)),
                       ("alpha", ("linear_expansion_coefficient",)), ("E", ("youngs_modulus",)),
                       ("k0", ("vacuum_angular_wavenumber",)), ("lambda0", ("vacuum_wavelength",)),
                       ("wl", ("vacuum_wavelength",)), ("eps_r", ("relative_permittivity",)),
                       ("sigma", ("electrical_conductivity",))):
        msg = _raised(lambda: units.quantity(key)).message
        assert all(n in msg for n in names), (key, msg)


def test_p2_r30_convert_complex_forms():
    cc = units.convert_complex
    c = cc({"re": 4.0, "im": 0.04}, "relative_permittivity", path="materials.slab.relative_permittivity")
    assert c.ok and c.value == complex(4.0, 0.04) and c.exact == (F(4), F("0.04")) and c.form == "re_im"
    c = cc({"n": Decimal("3.48"), "k": Decimal("0.01")}, "refractive_index")
    assert c.ok and c.value == complex(3.48, 0.01) and c.form == "n_k"
    for value, name, want in ((1.45, "refractive_index", complex(1.45, 0)), (4, "relative_permittivity", 4 + 0j),
                              (Decimal("1"), "relative_permeability", 1 + 0j), ({"re": -20.0, "im": 1.2},
                                                                                 "relative_permittivity", -20 + 1.2j)):
        c = cc(value, name)
        assert c.ok and c.value == want and type(c.value) is complex, (value, c)
    assert cc(1.45, "refractive_index").form == "real" and cc(1.45, "refractive_index").exact == (F("1.45"), F(0))
    # A dimensional complex quantity takes a quantity string; a real quantity takes the real forms only.
    assert cc("50 Ohm", "characteristic_impedance").value == 50 + 0j
    assert cc(0.3, "poisson_ratio").value == 0.3 + 0j


def test_p2_r30_gain_and_refusals():
    cc = units.convert_complex
    err = cc({"re": 4.0, "im": -0.04}, "relative_permittivity", path="m.eps").error
    assert err.code == "E-GAIN" and err.path == "m.eps.im" and "exp(+j omega t)" in err.message and err.fix is None
    assert err.suggestions[0].value == 0.04 and err.suggestions[0].si_after == 0.04
    err = cc({"n": 3.48, "k": -0.002}, "refractive_index", path="m.n").error
    assert err.code == "E-GAIN" and err.path == "m.n.k" and "k = -0.002" in err.message
    assert cc({"re": 1.0, "im": -0.5}, "relative_permeability").error.code == "E-GAIN"
    ok = cc({"re": 4.0, "im": -0.04}, "relative_permittivity", allow_gain=True)
    assert ok.ok and ok.value == complex(4.0, -0.04)
    assert cc({"re": 4.0, "im": -0.0}, "relative_permittivity").ok          # -0 is zero, not gain
    for value, name, code, path in (
            ([4.0, -0.04], "relative_permittivity", "E-VALUE-FORM", ""),
            ((3.48, 0.01), "refractive_index", "E-VALUE-FORM", ""),
            ({"re": 3.48, "im": 0.01}, "refractive_index", "E-VALUE-FORM", ""),
            ({"n": 2.0, "k": 0.0}, "relative_permittivity", "E-VALUE-FORM", ""),
            ({"re": 50, "im": 1}, "characteristic_impedance", "E-VALUE-FORM", ""),
            ({"re": 1, "im": 0}, "poisson_ratio", "E-VALUE-FORM", ""),
            (True, "relative_permittivity", "E-VALUE-FORM", ""), (None, "refractive_index", "E-VALUE-FORM", ""),
            ({"re": 4.0}, "relative_permittivity", "E-KEY-MISSING", "im"),
            ({"n": 3.48}, "refractive_index", "E-KEY-MISSING", "k"),
            ({"re": 4.0, "im": 0.0, "allow_gain": True}, "relative_permittivity", "E-KEY-UNKNOWN", "allow_gain"),
            ({"n": 0, "k": 0}, "refractive_index", "E-DOMAIN", "n"),
            ({"re": "4", "im": 0}, "relative_permittivity", "E-UNIT-UNKNOWN", "re"),
            ({"re": 4, "im": "0.04"}, "relative_permittivity", "E-UNIT-UNKNOWN", "im"),
            ({"re": 4, "im": [0.04]}, "relative_permittivity", "E-VALUE-FORM", "im"),
            ({"re": 4, "im": 1e400}, "relative_permittivity", "E-DOMAIN", "im"),
            ("4 1", "relative_permittivity", "E-UNIT-NOT-ACCEPTED", "")):
        err = cc(value, name).error
        assert err is not None and (err.code, err.path) == (code, path), (value, name, err)
    assert cc({"re": 4, "im": "0.04"}, "relative_permittivity").error.fix.value == 0.04
    assert [d.code for d in cc({"n": 200, "k": 0}, "refractive_index").diagnostics] == ["W-MAGNITUDE"]
    with pytest.raises(UnitError):
        cc(1.0, "no_such_quantity")


# Library datum (R-29): the temperature each refractiveindex.info record states (pinned revision of
# tools/rii-revision.txt, read 2026-11-09), or "assumed" where it says "room temperature" or nothing.
LIBRARY_DATUM = {"standard_air": 288.15, "SiO2": 293.15, "Si": 299.15, "Si_visible": 300.0, "GaAs": 295.15,
                 "Ge": 295.0, "Al2O3": 293.15, "MgF2": 292.15, "CaF2": 297.15, "LiNbO3": 294.15, "H2O": 298.15,
                 "Si3N4": None, "InP": None, "TiO2": None, "Au": None, "Ag": None, "Cu": None, "Al": None}


def test_p2_r29_library_datum():
    pytest.importorskip("numpy")
    import physmat
    assert set(physmat.names()) == set(LIBRARY_DATUM) | {"vacuum"}
    for name, datum in LIBRARY_DATUM.items():
        m = physmat.get(name)
        assert m.datum_temperature == datum and m.datum_assumed is (datum is None), name
    vacuum = physmat.get("vacuum")                                   # exact at every temperature: nothing assumed
    assert vacuum.datum_temperature is None and vacuum.datum_assumed is False
    assert physmat.standard_air(temperature_c=25).datum_temperature == 298.15
    assert physmat.standard_air().datum_temperature == 288.15
    assert physmat.constant(1.5).datum_temperature is None and not physmat.constant(1.5).datum_assumed


def test_p2_generator_refuses_broken_name_fields():
    from physmat import _unit_tables

    def broken(edit):
        src = registry()
        edit(src)
        with pytest.raises(ValueError):
            _unit_tables.build(src)
    broken(lambda s: s["quantities"]["heat_flux"]["sign"].update({"outward_heat_rate": {"en": "x", "ko": "x"}}))
    broken(lambda s: s["quantities"]["heat_flux"]["sign"].update({"inward_heat_flux": {"en": "x"}}))
    broken(lambda s: s["quantities"]["stress"]["statistic_definitions"].update({"stress_xx": {"en": "x", "ko": "x"}}))
    broken(lambda s: s["quantities"]["heat_flux"]["name_rank"].update({"inward_heat_flux": ["field"]}))
    broken(lambda s: s["quantities"]["constant"].update({"hint": True}))
    broken(lambda s: s["quantities"]["constant"].update({"scope": {"quantity": "no_such", "model": "sellmeier"}}))
    broken(lambda s: s["quantities"]["unnormalized_electric_field"].update({"places": ["document", "result"]}))
    broken(lambda s: s["quantities"]["mode_field_square_integral"].update({"unit": "mm^(1/2)", "menu": ["mm^(1/2)"]}))
    broken(lambda s: s["display_groups"]["length"].update({"menu": ["m", "s"]}))
    broken(lambda s: s["output_only_words"].append("sideways"))
