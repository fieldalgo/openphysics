# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Quantity registry and exact unit converter. Standard library only.

    from physmat.units import q, q_array
    q("200 GPa", "youngs_modulus")                  # 200000000000.0  (Pa)
    q("25 degC", "ambient_temperature")             # 298.15  (K)
    q("12 ppm/K", "linear_expansion_coefficient")   # 1.2e-05  (1/K)
    q("220 \u339a", "length")                        # 2.2e-07  (m); character aliases such as \u339a and \u00b5
    q(0.3, "poisson_ratio")                         # a bare number only for a dimensionless quantity
    q_array({"unit": "nm", "values": [1500, 1550]}, "vacuum_wavelength")   # [1.5e-06, 1.55e-06]
    q("10 mPa", "gauge_pressure")                   # UnitError E-UNIT-NOT-ACCEPTED: "mPa" is millipascal

``convert()`` returns the value with its diagnostics instead of raising (and the number and
unit as written), ``convert_array()`` does the same for every entry of an array,
``convert_complex()`` reads complex values under exp(-i omega t) and refuses gain,
``is_quantity_text()`` tells a quantity string from an expression, ``length_to_pm()`` puts a
geometry length on the integer picometre grid, and ``format()`` writes a value back as a
quantity string. The rules are in docs/packages/physmat/units.md. No other OpenPhysics
package calls this module yet: documents, simcase and galerkin keep their current units
until later steps of the units convention.

How a value is read: the character map and attached forms (``normalize``), then the number
grammar, then a whole-string lookup of the unit in the frozen spelling table and the
known-refused list (no unit grammar runs here), then dimension, kind and menu, then one
exact rational conversion to the canonical unit, rounded once, then the range, domain and
plausibility checks. Each value gets at most one error: the first rule that applies.

Data. The registry ships as two JSON package-data files next to this module:

- ``quantities.json``, the reviewed source: quantities, the closed symbol list with exact
  factors, prefixes, foreign units, the character alias map and the diagnostic codes;
- ``unit_tables.json``, generated from it by ``generate_tables()`` (``python -m
  physmat.units --write``; ``--check`` compares; ``python -m physmat._unit_tables --write``
  also works when the tables do not load): canonical units, every accepted spelling, the
  known-refused list, every legal quantity name with the places and rank of the names that
  differ from their base, and the display groups.

JSON and not generated Python, because the registry is data that readers other than this
module (Studio, documentation tables, CI name scans) are meant to share; JSON loads with
the standard library in any language, diffs one entry per line, and keeping source and
generated tables apart makes the frozen-table check a plain byte comparison.

``format`` and ``names`` are left out of ``__all__`` so that a star import does not hide the
builtin ``format`` or ``physmat.names``; call them as ``units.format`` and ``units.names``.
"""

from __future__ import annotations

import json
import math
import numbers
import operator
import re
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import MAX_EMAX, MIN_EMIN, Context, Decimal
from fractions import Fraction
from importlib import resources
from types import MappingProxyType
from typing import Any, Mapping

__all__ = ["q", "q_array", "convert", "convert_array", "convert_complex", "is_quantity_text", "quantity", "menu",
           "display_groups", "normalize", "length_to_pm", "pm_to_m", "generate_tables", "Quantity", "Conversion",
           "ArrayConversion", "ComplexConversion", "Diagnostic", "Fix", "Suggestion", "GridLength", "UnitError",
           "UnitWarning", "LENGTH_UNITS", "DIAGNOSTIC_CODES"]

SOURCE_FILE = "quantities.json"
TABLES_FILE = "unit_tables.json"


def _read(name: str) -> str:
    return resources.files("physmat").joinpath(name).read_text(encoding="utf-8")


_SRC = json.loads(_read(SOURCE_FILE))
_TAB = json.loads(_read(TABLES_FILE))


def _dimkey(d: Mapping[str, int]) -> tuple:
    return tuple(sorted((k, v) for k, v in d.items() if v))


@dataclass(frozen=True)
class _Unit:
    text: str
    dimension: tuple
    factor: Fraction
    offset: Fraction
    angle: int
    name: str
    reference: str | None           # "gauge" or "absolute" for barg psig bara psia


_UNITS = {u: _Unit(u, _dimkey(e["dimension"]), Fraction(e["factor"]), Fraction(e.get("offset", "0")), e["angle"],
                   e["name"], e.get("reference")) for u, e in _TAB["units"].items()}
_SPELLINGS: dict[str, str] = _TAB["spellings"]
_REFUSED: dict[str, dict] = _TAB["refused"]
_NAMES: dict[str, str] = _TAB["names"]
_OVERRIDES: dict[str, dict] = _TAB["name_overrides"]
_ENTRIES: dict[str, dict] = _SRC["quantities"]
_ALIASES = tuple((a, b) for a, b in _SRC["character_aliases"])
_SUPERSCRIPTS: dict[str, str] = _SRC["superscripts"]
_SPACES = tuple(_SRC["spaces"])
LENGTH_UNITS: tuple[str, ...] = tuple(_SRC["length_units"])
DIAGNOSTIC_CODES = MappingProxyType({k: MappingProxyType(v) for k, v in _SRC["diagnostics"].items()})

_BY_UNIT: dict[str, list[str]] = {}
_FOLDED: dict[str, list[str]] = {}            # casefolded text -> accepted and refused spellings
for _s, _u in _SPELLINGS.items():
    _BY_UNIT.setdefault(_u, []).append(_s)
for _s in sorted(set(_SPELLINGS) | set(_REFUSED)):
    _FOLDED.setdefault(_s.casefold(), []).append(_s)


def _rank(base: str) -> tuple:
    places = _ENTRIES[base]["places"]
    return (0 if "material" in places else 1 if "document" in places else 2, base)


# Quantities named in E-UNIT-DIMENSION messages. "hint": false (model parameters, air_wavelength)
# are never named; "hint": true marks the primary quantity of a dimension, and a "family" (the
# spectral keys) ranks its own members first, so a frequency in vacuum_wavelength names frequency.
_TAKERS: dict[str, list[str]] = {}            # canonical unit -> bases whose menu holds it
_SAME_DIM: dict[tuple, list[str]] = {}        # (dimension, angle exponent) -> bases
for _b, _e in _ENTRIES.items():
    if _e.get("hint") is False:
        continue
    for _u in _e["menu"]:
        _TAKERS.setdefault(_u, []).append(_b)
    _SAME_DIM.setdefault((_dimkey(_e["dimension"]), _TAB["units"][_e["unit"]]["angle"]), []).append(_b)


def _hint_order(bases: list[str], qo: "Quantity") -> list[str]:
    family = _ENTRIES[qo.base].get("family")

    def key(base: str) -> tuple:
        e = _ENTRIES[base]
        return (family is None or e.get("family") != family, not e.get("hint"), "document" not in e["places"], base)
    return sorted(bases, key=key)


def _hinted(base: str, qo: "Quantity") -> bool:
    """A quantity named in "Did you mean": the primary one of its dimension, or of the same family."""
    e, family = _ENTRIES[base], _ENTRIES[qo.base].get("family")
    return bool(e.get("hint")) or (family is not None and e.get("family") == family)


# ---- errors and diagnostics ---------------------------------------------------------------------

@dataclass(frozen=True)
class Fix:
    """A replacement that keeps the SI value; tools may apply it without asking."""
    value: Any

    def patch(self, pointer: str) -> dict:
        """The fix as one JSON Patch operation at a JSON Pointer."""
        return {"op": "replace", "path": pointer, "value": self.value}


@dataclass(frozen=True)
class Suggestion:
    """A replacement that may change the meaning; applied only after a person confirms it.

    ``si_before`` is the value as written, read in the quantity's canonical unit (None when the
    written text has no such reading); ``si_after`` is the value after the replacement."""
    value: Any
    si_before: float | None
    si_after: float | None
    unit: str

    def patch(self, pointer: str) -> dict:
        return {"op": "replace", "path": pointer, "value": self.value}


@dataclass(frozen=True)
class Diagnostic:
    """``{code, severity, path, message, fix, suggestions, acknowledged}``; codes in DIAGNOSTIC_CODES."""
    code: str
    path: str
    message: str
    fix: Fix | None = None
    suggestions: tuple[Suggestion, ...] = ()
    acknowledged: str | None = None

    @property
    def severity(self) -> str:
        return DIAGNOSTIC_CODES[self.code]["severity"]

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "path": self.path, "message": self.message,
                "fix": None if self.fix is None else self.fix.value,
                "suggestions": [{"value": s.value, "si_before": s.si_before, "si_after": s.si_after,
                                 "unit": s.unit} for s in self.suggestions],
                "acknowledged": self.acknowledged}

    def __str__(self) -> str:
        head = f"{self.severity} {self.code}" + (f" at {self.path}" if self.path else "")
        lines = [head] + ["  " + line for line in self.message.splitlines()]
        if self.fix is not None:
            lines.append(f"  Fix (keeps the value): {_shown(self.fix.value)}")
        for s in self.suggestions:
            unit = "" if s.unit == "1" else f" {s.unit}"
            after = "" if s.si_after is None else f"{_num(s.si_after)}{unit}"
            before = "" if s.si_before is None or s.si_before == s.si_after else \
                f"; as written {_num(s.si_before)}{unit}"
            note = f" ({after}{before})" if after else ""
            lines.append(f"  Suggestion (not applied automatically): {_shown(s.value)}{note}")
        return "\n".join(lines)


def _shown(value: Any) -> str:
    return f'"{value}"' if isinstance(value, str) else str(value)


class UnitError(ValueError):
    """A value that cannot be converted; ``.diagnostic`` holds the error."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic

    @property
    def code(self) -> str:
        return self.diagnostic.code


class UnitWarning(UserWarning):
    """A converted value with a warning (for example W-MAGNITUDE); ``.diagnostic`` holds it."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic


# ---- the registry ---------------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Quantity:
    """One registry quantity. ``menu`` lists canonical units; ``"1"`` means a bare number.

    ``rank`` and ``places`` are those of the name (``inward_heat_flux`` is a scalar normal
    component, ``evaluation_temperature`` an output); ``sign`` is the sign sentence of the name
    and ``definition`` that of a statistic name ({"en", "ko"} or None); ``scope`` names the model
    a model parameter belongs to ({"quantity", "model"} or None)."""
    name: str
    base: str
    dimension: Mapping[str, int]
    unit: str
    menu: tuple[str, ...]
    kind: str
    rank: tuple[str, ...]
    complex: bool
    domain: Mapping[str, str] | None
    band: Mapping[str, Any] | None
    places: tuple[str, ...]
    description: Mapping[str, str]
    status: str | None = None
    sign: Mapping[str, str] | None = None
    definition: Mapping[str, str] | None = None
    scope: Mapping[str, str] | None = None
    _cache: dict = field(default_factory=dict, repr=False)

    @property
    def bare(self) -> bool:
        """True when a bare number is accepted: only dimensionless quantities and counts."""
        return "1" in self.menu


_QUANTITIES: dict[str, Quantity] = {}


def _frozen(value: Any) -> Any:
    """A read-only copy: dicts become mapping proxies and lists tuples, all the way down."""
    if isinstance(value, dict):
        return MappingProxyType({k: _frozen(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_frozen(v) for v in value)
    return value


_GROUPS = _frozen(_TAB["display_groups"])


def quantity(name: str) -> Quantity:
    """The registry entry of a quantity name (a base name or a generated qualified name)."""
    if not isinstance(name, str):
        raise TypeError("a quantity name is a string, such as 'youngs_modulus'")
    found = _QUANTITIES.get(name)
    if found is not None:
        return found
    base = _NAMES.get(name)
    if base is None:
        raise UnitError(_unknown_quantity(name))
    e, own = _ENTRIES[base], _OVERRIDES.get(name, {})
    found = Quantity(name=name, base=base, dimension=_frozen(e["dimension"]), unit=e["unit"],
                     menu=tuple(e["menu"]), kind=e["kind"], rank=tuple(own.get("rank", e["rank"])),
                     complex=e.get("complex", False), domain=_frozen(e["domain"]), band=_frozen(e["band"]),
                     places=tuple(own.get("places", e["places"])), description=_frozen(e["description"]),
                     status=e.get("status"), sign=_frozen(e.get("sign", {}).get(name)),
                     definition=_frozen(e.get("statistic_definitions", {}).get(name)),
                     scope=_frozen(e.get("scope")))
    _QUANTITIES[name] = found
    return found


def menu(name: str) -> tuple[str, ...]:
    """Accepted units of a quantity, canonical spellings; ``"1"`` stands for a bare number."""
    return quantity(name).menu


def names() -> list[str]:
    """Every legal quantity name, sorted."""
    return sorted(_NAMES)


def display_groups() -> Mapping[str, Mapping[str, Any]]:
    """The display groups of ``display_units``: ``{group: {"quantities", "menu", "shape_numbers"}}``.

    ``length`` holds every length quantity name; ``shape_numbers`` says that the bare shape
    numbers of a geometry belong to the group too. A group's unit is one of its ``menu``."""
    return _GROUPS


def _unknown_quantity(name: str) -> Diagnostic:
    import difflib                                  # only needed for a misspelt name

    hits = [b for b, e in _ENTRIES.items() if name in e.get("symbols", ()) or name in e.get("refused_aliases", ())]
    hits = sorted(hits, key=_rank) or difflib.get_close_matches(name, list(_NAMES), n=3, cutoff=0.75)
    msg = f'Unknown quantity "{name}". Quantity names are full names, never symbols or units.'
    if hits:
        msg += f" Did you mean {_or(hits)}?"
    return Diagnostic("E-KEY-UNKNOWN", "", msg)


def _or(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def _limits(qo: Quantity) -> dict:
    """Exact domain, band and warning bounds of a quantity, parsed once."""
    if not qo._cache:
        e = _ENTRIES[qo.base]
        dom = e["domain"] or {}
        band = e["band"] or {}
        lim = {"domain": {k: _bound(v, qo) for k, v in dom.items()}}
        lim["abs_range"] = [None if v is None else _bound(v, qo) for v in band.get("abs_range", [None, None])]
        lim["range"] = [None if v is None else _bound(v, qo) for v in band.get("range", [None, None])]
        lim["abs_min"] = None if band.get("abs_min") is None else _bound(band["abs_min"], qo)
        lim["when_unit"] = band.get("when_unit")
        w = e.get("warn_inside")
        lim["warn"] = None if w is None else (w["code"], _bound(w["range"][0], qo), _bound(w["range"][1], qo))
        lim["slot"] = dict(e.get("slot_refusals", {}))
        qo._cache.update(lim)
    return qo._cache


def _bound(text: str, qo: Quantity) -> Fraction:
    number, _, unit = text.partition(" ")
    value = Fraction(number)
    if not unit:
        return value
    return _to_canonical(value, _SPELLINGS[unit], qo)


def _to_canonical(n: Fraction, unit: str, qo: Quantity) -> Fraction:
    u, c = _UNITS[unit], _UNITS[qo.unit]
    return (n * u.factor + u.offset - c.offset) / c.factor


# ---- reading text -------------------------------------------------------------------------------

_NUMBER = r"[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
_BARE = re.compile(_NUMBER)
_INTEGER = re.compile(r"[+-]?[0-9]+")
_QTY = re.compile(rf"({_NUMBER}) (\S(?:.*\S)?)")
_GLUED = re.compile(rf"({_NUMBER})([^\s0-9.,+\-].*)")
_ATTACHED = re.compile("\\s*([+\\-\u2212]?[0-9][0-9.eE+\\-\u2212]*)(%|\u00b0C|\u00b0)\\s*")   # % and the degree signs only
_LITERAL = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?)([0-9]+))?")
_DEGC_TOKEN = re.compile(r"(?<![A-Za-z])degC(?![A-Za-z])")
_SUPER_RUN = re.compile("[" + re.escape("".join(_SUPERSCRIPTS)) + "]+")
_SPACE_RUN = re.compile(" {2,}")
_MAX_EXPONENT = 1000        # a decimal exponent beyond this is outside a double for every unit factor
_MAX_BITS = 1100            # an integer or a fraction's size in bits beyond this is outside a double, too
_TINY = Fraction(1, 10 ** 300)
_INT64_MIN, _INT64_MAX = -2 ** 63, 2 ** 63 - 1


def normalize(text: str) -> str:
    """The text the converter reads: attached forms, the character alias map and space rules.

    ``"40%"``, ``"25\u00b0C"`` and ``"8\u00b0"`` get a space before the unit (``"25\u2103"`` does not:
    it is refused with the fix ``"25 degC"``, like any number glued to its unit). Superscript
    digits and minus become ``^`` and ASCII (``m\u207b\u00b3`` -> ``m^-3``), then every alias of the map
    applies (``\u00b5`` -> ``u``, ``\u03a9`` -> ``Ohm``, ``\u339a`` -> ``nm``, ``\u2212`` -> ``-``,
    ``\u00b7`` -> space, ...), no-break and thin spaces become spaces, runs of spaces collapse and the
    ends are stripped.
    No Unicode normalisation (NFC, NFKC) is applied."""
    m = _ATTACHED.fullmatch(text)
    if m:
        text = f"{m.group(1)} {m.group(2)}"
    text = _SUPER_RUN.sub(lambda r: "^" + "".join(_SUPERSCRIPTS[c] for c in r.group(0)), text)
    for a, b in _ALIASES:
        text = text.replace(a, b)
    for s in _SPACES:
        text = text.replace(s, " ")
    return _SPACE_RUN.sub(" ", text).strip()


def _decimal_fraction(text: str) -> Fraction | None:
    """Exact value of a decimal literal; None when it is far outside the range of a double.

    The exponent is checked on the text before any arithmetic, so "1e999999999999999999999"
    is refused instead of overflowing the decimal module."""
    m = _LITERAL.fullmatch(text)
    if m is None:
        raise ValueError(f"not a decimal literal: {text!r}")
    _, whole, frac, esign, edigits = m.groups()
    digits = ((whole or "") + (frac or "")).lstrip("0")
    if not digits:
        return Fraction(0)
    edigits = (edigits or "0").lstrip("0") or "0"
    if len(edigits) > 6:
        return None
    adjusted = int((esign or "") + edigits) - len(frac or "") + len(digits) - 1
    if abs(adjusted) > _MAX_EXPONENT:
        return None
    try:
        return Fraction(Decimal(text))
    except ValueError:                      # more digits than int() converts
        return None


def _bare_number(value: Any) -> tuple[Fraction | None, str]:
    """Exact value and display text of a bare JSON or Python number.

    A float is read through its shortest repr, so 0.1 means the decimal 0.1, as the JSON text
    "0.1" does. numpy scalars work through the numbers ABCs (np.float64 is a float, np.int64 an
    Integral, np.float32 a Real read as its exact double); numpy itself is never imported."""
    if isinstance(value, bool) or isinstance(value, str) or not isinstance(value, (numbers.Real, Decimal)):
        raise TypeError(f"a value is a quantity string or a number, not {type(value).__name__}")
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None, str(value)
        return _decimal_fraction(str(value)), str(value)
    if isinstance(value, numbers.Integral):
        n = operator.index(value)
        if n.bit_length() > _MAX_BITS:
            return None, f"an integer of {n.bit_length()} bits"
        return Fraction(n), str(n)
    if isinstance(value, numbers.Rational):
        f = Fraction(value.numerator, value.denominator)
        size = f.numerator.bit_length() - f.denominator.bit_length()
        if f and abs(size) > _MAX_BITS:
            return None, f"a fraction of about 2^{size}"
        shown = repr(f) if max(f.numerator.bit_length(), f.denominator.bit_length()) < 10000 else \
            f"a fraction of about 2^{size}"
        return f, shown
    x = float(value)
    text = float.__repr__(x)
    if not math.isfinite(x):
        return None, text
    return _decimal_fraction(text), text


def _integer_literal(value: Any) -> bool:
    """True for a number written as an integer literal: an int (or numpy integer), or a
    Decimal with exponent 0 (the JSON reader's integers)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, Decimal):
        return value.is_finite() and value.as_tuple().exponent == 0
    return isinstance(value, numbers.Integral)


@dataclass(frozen=True)
class _Read:
    number: Fraction | None
    number_text: str
    unit: str | None            # canonical unit on the menu, None for a bare number
    shown: str                  # the value as written, for messages
    text: str | None            # normalised quantity text with the canonical spelling
    integer: bool               # written as an integer literal (counts)
    unit_text: str | None = None    # the unit as written, after the character map


def _parse(raw: str, qo: Quantity, path: str, shown: str | None = None) -> _Read | Diagnostic:
    """Rules 4-9: grammar, lookup, ambiguity, dimension, degC kind, refused spellings, menu."""
    text = normalize(raw)
    shown = shown or f'"{raw}"'
    if _BARE.fullmatch(text):
        if not qo.bare:                                  # a number without its unit: rule 3 in _finish
            return _Read(_decimal_fraction(text), text, None, text, None, bool(_INTEGER.fullmatch(text)))
        return _number_string(text, qo, path, shown)
    m = _QTY.fullmatch(text)
    if m:
        number_text, unit_text = m.groups()
        unit = _resolve(unit_text, qo, number_text, shown, path)
        if isinstance(unit, Diagnostic):
            return unit
        return _Read(_decimal_fraction(number_text), number_text, unit, shown, f"{number_text} {unit}",
                     bool(_INTEGER.fullmatch(number_text)), unit_text)
    m = _GLUED.fullmatch(text)
    if m:
        spaced = f"{m.group(1)} {m.group(2)}"
        inner = _parse(spaced, qo, path, shown)
        if isinstance(inner, Diagnostic):
            note = "\nA space is also needed between the number and the unit."
            return Diagnostic(inner.code, path, inner.message + note, inner.fix, inner.suggestions)
        return Diagnostic("E-UNIT-UNKNOWN", path,
                          f"{shown} needs one space between the number and the unit.", Fix(inner.text))
    return Diagnostic("E-UNIT-UNKNOWN", path, f"{shown} is not a quantity: {_why_not(text)}. "
                      f'Write a number, one space and a unit, for example "{_example(qo)}".')


def _number_string(text: str, qo: Quantity, path: str, shown: str) -> Diagnostic:
    """A string that holds only a number, for a dimensionless quantity or a count: the value is a
    bare JSON number, so the fix writes that number (and keeps the value)."""
    n = _decimal_fraction(text)
    if qo.kind == "count":
        msg = f"{shown} is a string; {qo.name} is a count, written as a bare JSON integer"
        if n is not None and n.denominator == 1:
            return Diagnostic("E-UNIT-UNKNOWN", path, msg + f": {int(n)}.", Fix(int(n)))
        return Diagnostic("E-UNIT-UNKNOWN", path, msg + ", and this number is not one.")
    msg = f"{shown} is a string; {qo.name} is dimensionless, so its value is a bare JSON number"
    if n is None or _range_problem(n):
        return Diagnostic("E-UNIT-UNKNOWN", path, msg + " (this one is outside the range of a double).")
    return Diagnostic("E-UNIT-UNKNOWN", path, msg + f": {text}.", Fix(_bare_value(text)))


def _why_not(text: str) -> str:
    if not text:
        return "it is empty"
    if re.match(r"[+-]?\.[0-9]", text):
        return "a number needs a leading digit (0.5, not .5)"
    if re.match(r"[+-]?[0-9]+,[0-9]", text):
        return "a number has no decimal comma or thousands separator (1.5 or 1500)"
    if re.match(r"[+-]?[0-9]+\.(?![0-9])", text):
        return "a decimal point needs digits after it (5 or 5.0, not 5.)"
    if not re.match(r"[+-]?[0-9]", text):
        return "it does not start with a number"
    return "it is not a number followed by one space and a unit"


def _example(qo: Quantity) -> str:
    unit = next((u for u in qo.menu if u != "1"), None)
    return "1" if unit is None else f"1 {unit}"


def _menu_text(qo: Quantity) -> str:
    return " ".join("a bare number" if u == "1" else u for u in qo.menu)


def _resolve(unit_text: str, qo: Quantity, number_text: str | None, shown: str, path: str) -> str | Diagnostic:
    """Canonical unit of an accepted, on-menu spelling, or the one diagnostic that refuses it.

    With ``number_text`` None (the unit of a tagged array) fixes and suggestions replace the
    unit text alone."""
    canonical = _SPELLINGS.get(unit_text)
    refused = None if canonical is not None else _REFUSED.get(unit_text)
    n = None if number_text is None else _decimal_fraction(number_text)

    def value_text(unit: str) -> Any:
        if number_text is None:
            return unit
        return _bare_value(number_text) if unit == "1" else f"{number_text} {unit}"

    def si(unit: str, number: Fraction | None = n) -> float | None:
        return None if number is None else _float_or_none(_to_canonical(number, unit, qo))

    def case_suggestions(before: float | None) -> tuple[Suggestion, ...]:
        return tuple(Suggestion(value_text(u), before, si(u), qo.unit) for u in _case_twins(unit_text, qo))

    if canonical is None and refused is None:                                    # rule 4
        msg = f'{shown}: "{unit_text}" is not a unit spelling of the registry. {qo.name} takes: {_menu_text(qo)}.'
        msg += _case_readings(unit_text, qo, n)
        if _DEGC_TOKEN.search(unit_text):
            msg += " degC is never used inside a compound unit: temperature steps are written in K."
        return Diagnostic("E-UNIT-UNKNOWN", path, msg, suggestions=case_suggestions(None))
    if refused is not None and refused["code"] == "E-UNIT-AMBIGUOUS":            # rule 5
        readings = refused["readings"]
        listed = "; or ".join(f'{r["unit"]} ({r["name"]})' for r in readings)
        if len(readings) == 1:
            msg = (f'{shown}: "{unit_text}" runs symbols together; it reads as {listed}. '
                   "Separate the factors with a space.")
        else:
            msg = f'{shown}: "{unit_text}" can be read more than one way: {listed}. Write the reading you mean.'
        if "note" in refused:
            msg += f" {refused['note']}."
        return Diagnostic("E-UNIT-AMBIGUOUS", path, msg)
    if canonical is not None:
        u = _UNITS[canonical]
        dim, factor, offset, angle, reading = u.dimension, u.factor, u.offset, u.angle, u.name
    elif "fix" in refused:
        u = _UNITS[refused["fix"]]
        dim, factor, offset, angle, reading = u.dimension, u.factor, u.offset, u.angle, refused["reading"]
    else:
        dim, angle, reading = _dimkey(refused["dimension"]), refused["angle"], refused["reading"]
        factor = None if refused["factor"] is None else Fraction(refused["factor"])
        offset = Fraction(refused.get("offset", "0"))
    before = _as_written(n, factor, offset, angle, qo)

    if dim != _dimkey(qo.dimension):                                             # rule 6
        msg = f'{shown}: "{unit_text}" is {reading}'
        takers = _hint_order(_TAKERS.get(canonical, []), qo) if canonical is not None else []
        if takers:                                       # an accepted spelling: name the quantities taking it
            msg += f", a unit of {_or(takers[:4])}; {qo.name} needs {qo.unit}."
            if _hinted(takers[0], qo):
                msg += f" Did you mean {takers[0]}?"
        else:                                            # refused, or on no menu: name the dimension only
            group = _hint_order(_SAME_DIM.get((dim, angle), []), qo)
            msg += f", which has the dimension of {_or(group[:3])}" if group else ", which no registry quantity takes"
            msg += f"; {qo.name} needs {qo.unit}."
        return Diagnostic("E-UNIT-DIMENSION", path, msg)
    if canonical == "degC" and qo.kind != "absolute":                            # rule 7
        msg = (f"{shown} is ambiguous: {qo.name} is a temperature difference, and degC is a point on the "
               "Celsius scale. A 1 degC step equals a 1 K step, so the same number in K is suggested; it is "
               "not applied automatically, because an absolute temperature may have been meant.")
        as_point = None if n is None else _float_or_none(n + _UNITS["degC"].offset)
        return Diagnostic("E-DEGC-NOT-ABSOLUTE", path, msg,
                          suggestions=(Suggestion(value_text("K"), as_point, si("K"), qo.unit),))
    if refused is not None and refused["code"] == "E-DEGC-NOT-ABSOLUTE":
        fixed = refused["fix"]
        msg = (f'{shown}: "{unit_text}" is {refused["reading"]}. degC is a point on the Celsius scale and is not '
               f"used inside a compound unit; a 1 degC step equals a 1 K step, so the unit is {fixed}.")
        if fixed in qo.menu:
            return Diagnostic("E-DEGC-NOT-ABSOLUTE", path, msg, Fix(value_text(fixed)))
        return Diagnostic("E-DEGC-NOT-ABSOLUTE", path, msg + f" {qo.name} takes: {_menu_text(qo)}.")
    if refused is not None:                                                      # rule 8
        if "fix" in refused:
            fixed = refused["fix"]
            msg = f'{shown}: "{unit_text}" is {refused["reading"]}; powers are written with ^, as in "{fixed}".'
            if fixed in qo.menu:
                return Diagnostic("E-UNIT-NOT-ACCEPTED", path, msg, Fix(value_text(fixed)))
            return Diagnostic("E-UNIT-NOT-ACCEPTED", path, msg + f" {qo.name} takes: {_menu_text(qo)}.")
        if unit_text == "1":
            msg = f'{shown}: "1" is {reading}, so the unit "1" is never written.'
        else:
            msg = f'{shown}: "{unit_text}" is {reading}.'
            msg += "" if before is None else f" As written it is {_num(before)}{_unit_suffix(qo)}."
            msg += f" It is not accepted for {qo.name}. Accepted: {_menu_text(qo)}."
        sugg = case_suggestions(before) + _reexpress(n, factor, offset, angle, qo, number_text is None)
        return Diagnostic("E-UNIT-NOT-ACCEPTED", path, msg, suggestions=_unique(sugg))
    slot = _limits(qo)["slot"].get(canonical)
    if slot is not None:
        msg = (f"{shown} is an absolute pressure ({reading}); {qo.name} is a load relative to ambient. "
               "Mechanical loads are gauge pressures: the ambient pressure cancels on a closed body. "
               "Write the pressure above ambient.")
        return Diagnostic(slot, path, msg)
    if canonical not in qo.menu:                                                 # rule 9
        msg = f'{shown}: "{unit_text}" is {reading}'
        msg += "" if before is None else f" ({_num(before)}{_unit_suffix(qo)})"
        msg += f", which is not on the {qo.name} menu. Accepted: {_menu_text(qo)}."
        takers = _hint_order(_TAKERS.get(canonical, []), qo)
        if takers:
            msg += f" {canonical} is a unit of {_or(takers[:4])}."
        if u.reference is not None:                      # barg psig bara psia: no unit change keeps the meaning
            msg += (f" {canonical} marks a {u.reference} pressure (absolute = gauge + ambient), so it is not "
                    "re-expressed in another unit.")
            return Diagnostic("E-UNIT-NOT-ACCEPTED", path, msg)
        sugg = case_suggestions(before) + _reexpress(n, factor, offset, angle, qo, number_text is None)
        return Diagnostic("E-UNIT-NOT-ACCEPTED", path, msg, suggestions=_unique(sugg))
    return canonical


def _as_written(n: Fraction | None, factor: Fraction | None, offset: Fraction, angle: int,
                qo: Quantity) -> float | None:
    """The written value read in the canonical unit; None when the angle content differs (1/cm vs rad/m)."""
    c = _UNITS[qo.unit]
    if n is None or factor is None or angle != c.angle:
        return None
    return _float_or_none((n * factor + (offset if qo.kind == "absolute" else 0) - c.offset) / c.factor)


def _case_readings(unit_text: str, qo: Quantity, n: Fraction | None) -> str:
    """The spellings of the tables equal to ``unit_text`` under case folding, each with its reading,
    when any of them is off the menu ("ms/m": MS/m on the menu, and mS/m, 1e9 times smaller)."""
    twins = [t for t in _FOLDED.get(unit_text.casefold(), []) if t != unit_text]
    if all(_SPELLINGS.get(t) in qo.menu for t in twins):
        return ""
    found = []
    for t in twins:
        refused = _REFUSED.get(t)
        if t in _SPELLINGS:
            u = _UNITS[_SPELLINGS[t]]
            factor, offset, angle, dim, reading = u.factor, u.offset, u.angle, u.dimension, u.name
            status = "on the menu" if u.text in qo.menu else f"not on the {qo.name} menu"
        elif refused["code"] == "E-UNIT-AMBIGUOUS":
            found.append(f"{t} (ambiguous)")
            continue
        else:
            u = _UNITS[refused["fix"]] if "fix" in refused else None
            if u is not None:
                factor, offset, angle, dim = u.factor, u.offset, u.angle, u.dimension
            else:
                factor = None if refused["factor"] is None else Fraction(refused["factor"])
                offset, angle = Fraction(refused.get("offset", "0")), refused["angle"]
                dim = _dimkey(refused["dimension"])
            reading, status = refused["reading"], "refused"
        value = _as_written(n, factor, offset, angle, qo) if dim == _dimkey(qo.dimension) else None
        shown = "" if value is None else f", {_num(value)}{_unit_suffix(qo)}"
        found.append(f"{t} ({reading}{shown}, {status})")
    return f' Equal to "{unit_text}" under case folding: ' + "; ".join(found) + "."


def _unique(suggestions: tuple[Suggestion, ...]) -> tuple[Suggestion, ...]:
    return tuple(dict.fromkeys(suggestions))


def _case_twins(unit_text: str, qo: Quantity) -> list[str]:
    """Menu units with a spelling equal to ``unit_text`` under case folding (at most one per menu)."""
    folded = unit_text.casefold()
    return [u for u in qo.menu if u != "1" and any(s.casefold() == folded and s != unit_text for s in _BY_UNIT[u])]


def _reexpress(n: Fraction | None, factor: Fraction | None, offset: Fraction, angle: int, qo: Quantity,
               unit_only: bool) -> tuple[Suggestion, ...]:
    """The written value in the menu unit that gives the plainest number (same SI value)."""
    if n is None or factor is None or unit_only:
        return ()
    c = _UNITS[qo.unit]
    si_exact = n * factor + (offset if qo.kind == "absolute" else 0)
    best = None
    for i, unit in enumerate(qo.menu):
        u = _UNITS[unit]
        if u.angle != angle or (u.offset and qo.kind != "absolute") or not _power_of_ten(u.factor / c.factor):
            continue
        v = (si_exact - u.offset) / u.factor
        try:
            lg = math.log10(abs(float(v))) if v else 0.0
        except (OverflowError, ValueError):
            continue
        distance = -lg if lg < 0 else (lg - 3 + 1e-9 if lg >= 3 else 0.0)   # plainest: 1 <= |v| < 1000
        score = (distance, unit != qo.unit, i)
        if best is None or score < best[0]:
            best = (score, unit, v)
    if best is None:
        return ()
    _, unit, v = best
    canonical = _float_or_none((si_exact - c.offset) / c.factor)
    if canonical is None:
        return ()
    # The exact decimal when it is short, else the shortest text that converts back to the same double.
    text = _decimal_text(v, exact_only=True) or _shortest_text(v, unit, qo, canonical)
    value = _bare_value(text) if unit == "1" else f"{text} {unit}"
    return (Suggestion(value, canonical, canonical, qo.unit),)


def _power_of_ten(r: Fraction) -> bool:
    def p10(k: int) -> bool:
        while k % 10 == 0:
            k //= 10
        return k == 1
    return r > 0 and p10(r.numerator) and p10(r.denominator)


def _bare_value(text: str) -> int | float:
    return int(text) if _INTEGER.fullmatch(text) else float(text)


def _float_or_none(v: Fraction) -> float | None:
    try:
        x = float(v)
    except OverflowError:
        return None
    return x if math.isfinite(x) else None


# ---- numbers in messages ------------------------------------------------------------------------

def _pretty(d: Decimal) -> str:
    """Exact decimal text: fixed for 1e-3 <= |d| < 1e6, else exponent form (2e11, 1.2e-5).

    Built from the digits, so the caller's decimal context (precision, traps) never applies."""
    sign, digits, exp = d.as_tuple()
    text = "".join(map(str, digits)).lstrip("0")
    if not text:
        return "0"
    stripped = text.rstrip("0")
    exp += len(text) - len(stripped)
    text = stripped
    adjusted = exp + len(text) - 1
    if -3 <= adjusted < 6:
        if exp >= 0:
            body = text + "0" * exp
        elif len(text) + exp > 0:
            body = text[:len(text) + exp] + "." + text[len(text) + exp:]
        else:
            body = "0." + "0" * -(len(text) + exp) + text
    else:
        body = text[0] + ("." + text[1:] if len(text) > 1 else "") + f"e{adjusted}"
    return ("-" if sign else "") + body


def _num(x: float) -> str:
    """Shortest text that reads back as the double ``x``."""
    for k in range(1, 18):
        t = f"{x:.{k}g}"
        if float(t) == x:
            return _pretty(Decimal(t))
    return repr(x)


def _decimal_text(v: Fraction, exact_only: bool = False) -> str | None:
    """Exact decimal text of a terminating fraction (at most 17 digits), else the shortest double
    text (None with ``exact_only``). A denominator over 2000 bits is never expanded."""
    den = v.denominator
    if den.bit_length() <= 2000 and v.numerator.bit_length() <= 4000:
        twos = (den & -den).bit_length() - 1             # factors of 2 in one step
        den >>= twos
        fives = 0
        while den % 5 == 0:
            den //= 5
            fives += 1
        if den == 1:
            k = max(twos, fives)
            d = Decimal(f"{v.numerator * 10 ** k // v.denominator}E-{k}")
            if len(str(abs(v.numerator * 10 ** k // v.denominator)).strip("0") or "0") <= 17:
                return _pretty(d)
    if exact_only:
        return None
    x = _float_or_none(v)
    return "inf" if x is None else _num(x)


def _shortest_text(target: Fraction, unit: str, qo: Quantity, x: float) -> str:
    """Shortest decimal text d (fewest significant digits) with float(d in ``unit``) == x, where
    ``target`` is the exact value in ``unit`` of the double x. Uses a private decimal context.

    17 digits are enough without an offset; near the degC offset a tiny x needs more (about 17 plus
    the decimal exponent gap, at most a few hundred for subnormal doubles)."""
    num, den = Decimal(target.numerator), Decimal(target.denominator)
    for digits in range(1, 1200):
        d = Context(prec=digits, Emax=MAX_EMAX, Emin=MIN_EMIN, traps=[]).divide(num, den)
        try:
            if float(_to_canonical(Fraction(d), unit, qo)) == x:
                return _pretty(d)
        except OverflowError:                           # rounded up past the largest double
            continue
    raise ValueError(f"no decimal text of {x!r} in {unit} converts back")


# ---- conversion ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Conversion:
    """Result of ``convert``: the SI value (None on error), its exact rational value, the canonical
    unit, the normalised text (number as written, canonical unit spelling) and the diagnostics.

    ``number_text`` is the number as written (a bare number: its decimal text) and ``unit_text``
    the unit as written after the character map (None for a bare number), so that a caller can
    hand on the authored number when the unit is the one it needs (``"30 deg"`` -> 30)."""
    quantity: str
    value: float | None
    exact: Fraction | None
    unit: str
    text: str | None
    diagnostics: tuple[Diagnostic, ...] = ()
    number_text: str | None = None
    unit_text: str | None = None

    @property
    def error(self) -> Diagnostic | None:
        return next((d for d in self.diagnostics if d.severity == "error"), None)

    @property
    def ok(self) -> bool:
        return self.error is None


def convert(value: Any, quantity_name: str, *, path: str = "") -> Conversion:
    """Convert a quantity string or a bare number to the canonical unit, with diagnostics.

    Never raises for a bad value; raises UnitError only for an unknown quantity name and
    TypeError for a value that is neither a string nor a number (int, float, Decimal, Fraction
    and numpy scalars are numbers)."""
    qo = quantity(quantity_name)
    if isinstance(value, str):
        read = _parse(value, qo, path)
    else:
        number, text = _bare_number(value)
        read = _Read(number, text, None, text, None, _integer_literal(value))
    if isinstance(read, Diagnostic):
        return Conversion(qo.name, None, None, qo.unit, None, (read,))
    return _finish(read, qo, path)


def _fail(qo: Quantity, *diagnostics: Diagnostic, read: _Read | None = None) -> Conversion:
    texts = (None, None) if read is None else (read.number_text, read.unit_text)
    return Conversion(qo.name, None, None, qo.unit, None, tuple(diagnostics), *texts)


def _finish(read: _Read, qo: Quantity, path: str) -> Conversion:
    """Rules 3 and 10-12: unit required, exact conversion and range, domain, band."""
    if read.unit is None and not qo.bare:                                        # rule 3
        msg = (f"{read.shown} has no unit. {qo.name} takes {_menu_text(qo)} (canonical {qo.unit}). "
               "Write the unit with the number, as on a datasheet.")
        return _fail(qo, Diagnostic("E-UNIT-MISSING", path, msg), read=read)
    unit = read.unit or "1"
    if read.number is None:                                                      # rule 10
        msg = f"{read.shown} is far outside the range of a double; no value can be stored."
        return _fail(qo, Diagnostic("E-DOMAIN", path, msg), read=read)
    exact = _to_canonical(read.number, unit, qo)
    problem = _range_problem(exact)
    if problem:
        return _fail(qo, Diagnostic("E-DOMAIN", path, f"{read.shown} is {problem}."), read=read)
    value = float(exact)
    if qo.kind == "count" and not (read.integer and exact.denominator == 1):
        if exact.denominator == 1:                       # 2.0, 2e1, Fraction(2): the right value, written otherwise
            msg = (f"{read.shown} is not written as an integer literal; {qo.name} is a count, written as "
                   f"a JSON integer: {int(exact)}.")
            return _fail(qo, Diagnostic("E-DOMAIN", path, msg, Fix(int(exact))), read=read)
        msg = f"{read.shown} is not a whole number; {qo.name} is a count, written as an integer."
        return _fail(qo, Diagnostic("E-DOMAIN", path, msg), read=read)
    lim = _limits(qo)
    bad = _domain_problem(exact, lim["domain"], qo)                              # rule 11
    if bad:
        msg = f"{read.shown} is {_num(value)}{_unit_suffix(qo)}; {qo.name} must be {bad}."
        sugg = ()
        if qo.kind == "fraction" and read.unit is None and exact > 1 and "%" in qo.menu:
            msg += f' A fraction is written as a number up to 1 or in %: did you mean "{read.number_text} %"?'
            percent = _to_canonical(read.number, "%", qo)
            sugg = (Suggestion(f"{read.number_text} %", value, float(percent), qo.unit),) if percent <= 1 else ()
        return _fail(qo, Diagnostic("E-DOMAIN", path, msg, suggestions=sugg), read=read)
    found = _band(read, exact, value, unit, qo, lim, path)                       # rule 12
    return Conversion(qo.name, value, exact, qo.unit, read.text, tuple(found), read.number_text,
                      read.unit_text)


def _unit_suffix(qo: Quantity) -> str:
    return "" if qo.unit == "1" else f" {qo.unit}"


def _range_problem(v: Fraction) -> str | None:
    if v == 0:
        return None
    if abs(v) < _TINY:
        return "below 1e-300 in magnitude after conversion, where a double is subnormal or 0"
    if _float_or_none(v) is None:
        return "beyond the largest double (about 1.8e308) after conversion"
    return None


_OPS = {"min": (lambda v, b: v >= b, ">="), "min_exclusive": (lambda v, b: v > b, ">"),
        "max": (lambda v, b: v <= b, "<="), "max_exclusive": (lambda v, b: v < b, "<")}


def _domain_problem(v: Fraction, domain: dict, qo: Quantity) -> str | None:
    if all(_OPS[k][0](v, b) for k, b in domain.items()):
        return None
    spec = _ENTRIES[qo.base]["domain"]
    parts = [f"{_OPS[k][1]} {_bound_text(spec[k], qo)}" for k in ("min", "min_exclusive", "max", "max_exclusive")
             if k in spec]
    return " and ".join(parts)


def _bound_text(text: str, qo: Quantity) -> str:
    return text if " " in text else text + _unit_suffix(qo)


def _band(read: _Read, exact: Fraction, value: float, unit: str, qo: Quantity, lim: dict,
          path: str) -> list[Diagnostic]:
    """W-MAGNITUDE outside the plausibility band, and a quantity's own in-range warning."""
    found = []
    if lim["warn"] is not None:
        code, lo, hi = lim["warn"]
        if lo <= exact <= hi:
            msg = (f"{read.shown} is {_num(value)} {qo.unit}, close to atmospheric pressure (101325 Pa). "
                   f"{qo.name} is the pressure above ambient; an ambient absolute pressure written as a load "
                   "is a common slip. If the load is meant, acknowledge it on the value with a reason.")
            found.append(Diagnostic(code, path, msg))
    if lim["when_unit"] is not None and lim["when_unit"] != unit:
        return found
    a = abs(exact)
    lo_abs, hi_abs = lim["abs_range"]
    lo, hi = lim["range"]
    low = (exact != 0 and ((lo_abs is not None and a < lo_abs) or (lim["abs_min"] is not None and a < lim["abs_min"])))
    high = hi_abs is not None and a > hi_abs
    signed_low = lo is not None and exact < lo
    signed_high = hi is not None and exact > hi
    if not (low or high or signed_low or signed_high):
        return found
    spec = _ENTRIES[qo.base]["band"]
    msg = (f"{read.shown} is {_num(value)}{_unit_suffix(qo)}, outside the usual range of {qo.name} "
           f"({_band_text(spec, qo)}).")
    too_small = low or (signed_low and exact >= 0) or (signed_high and exact < 0)
    if low and _UNITS[unit].factor < _UNITS[qo.unit].factor:
        msg += f" It looks like a number in {qo.unit if qo.unit != '1' else 'the bare form'} written with {unit}."
    msg += (" If the value is right, acknowledge it on the value with a reason: "
            '{"value": ..., "accept": {"W-MAGNITUDE": "<reason>"}}.')
    sugg = _slips(read, unit, qo, lim, upward=too_small)
    found.append(Diagnostic("W-MAGNITUDE", path, msg, suggestions=sugg))
    return found


def _band_text(spec: dict, qo: Quantity) -> str:
    parts = []
    if "abs_range" in spec:
        lo, hi = spec["abs_range"]
        if lo is not None and hi is not None:
            parts.append(f"|value| {_bound_text(lo, qo)} to {_bound_text(hi, qo)}")
        elif hi is not None:
            parts.append(f"|value| <= {_bound_text(hi, qo)}")
        else:
            parts.append(f"|value| >= {_bound_text(lo, qo)}")
    if "range" in spec:
        lo, hi = spec["range"]
        if lo is not None and hi is not None:
            parts.append(f"{_bound_text(lo, qo)} to {_bound_text(hi, qo)}")
        elif hi is not None:
            parts.append(f"<= {_bound_text(hi, qo)}")
        else:
            parts.append(f">= {_bound_text(lo, qo)}")
    if "abs_min" in spec:
        parts.append(f"|value| >= {_bound_text(spec['abs_min'], qo)} unless exactly 0")
    if "when_unit" in spec:
        parts.append(f"when written in {spec['when_unit']}")
    return "; ".join(parts)


def _in_band(v: Fraction, lim: dict, unit: str) -> bool:
    if lim["when_unit"] is not None and lim["when_unit"] != unit:
        return True
    a = abs(v)
    lo_abs, hi_abs = lim["abs_range"]
    lo, hi = lim["range"]
    if v != 0 and ((lo_abs is not None and a < lo_abs) or (lim["abs_min"] is not None and a < lim["abs_min"])):
        return False
    return not ((hi_abs is not None and a > hi_abs) or (lo is not None and v < lo) or (hi is not None and v > hi))


def _slips(read: _Read, unit: str, qo: Quantity, lim: dict, upward: bool) -> tuple[Suggestion, ...]:
    """Likely prefix slips: the same number with another menu unit that lands inside the band."""
    here = _UNITS[unit]
    found = []
    for other in qo.menu:
        u = _UNITS[other]
        if other == unit or u.angle != here.angle or u.offset or here.offset:
            continue
        ratio = u.factor / here.factor
        if not _power_of_ten(ratio) or (ratio > 1) != upward:
            continue
        v = _to_canonical(read.number, other, qo)
        if _in_band(v, lim, other) and _range_problem(v) is None:
            value = _bare_value(read.number_text) if other == "1" else f"{read.number_text} {other}"
            found.append((abs(math.log10(ratio.numerator) - math.log10(ratio.denominator)), other, value, v))
    found.sort(key=lambda t: (t[0], t[1]))
    before = float(_to_canonical(read.number, unit, qo))
    distinct = list({v: (value, v) for _, _, value, v in reversed(found)}.values())[::-1]   # first per SI value
    return tuple(Suggestion(value, before, float(v), qo.unit) for value, v in distinct[:2])


# ---- public conversions -------------------------------------------------------------------------

def q(value: Any, quantity_name: str) -> float:
    """SI float of a quantity string or a bare number; raises UnitError, warns UnitWarning.

    ``q("1550 nm", "vacuum_wavelength") == 1.55e-06`` and ``q("10 MPa", "gauge_pressure") == 1e7``;
    ``q("10 mPa", "gauge_pressure")`` raises. A bare number is accepted only for a
    dimensionless quantity or a count."""
    c = convert(value, quantity_name)
    if c.error is not None:
        raise UnitError(c.error)
    for d in c.diagnostics:
        warnings.warn(UnitWarning(d), stacklevel=2)
    return c.value


def q_array(values: Any, quantity_name: str, *, path: str = "") -> list:
    """SI list of a tagged array ``{"unit": "nm", "values": [...]}`` (nested lists keep their
    shape), a dimensionless ``{"values": [...]}``, or a short vector of at most 3 quantity
    strings (``["0 MPa", "-5 MPa"]``). "values" may be any sequence or an array with
    ``tolist()`` (a numpy array); numpy is never imported.

    Raises TypeError for a value of the wrong form, UnitError for the first error and warns
    each warning; ``convert_array`` returns every diagnostic instead."""
    c = convert_array(values, quantity_name, path=path)
    form = next((d for d in c.diagnostics if d.code == "E-VALUE-FORM"), None)
    if form is not None:
        raise TypeError(form.message)
    if c.error is not None:
        raise UnitError(c.error)
    for d in c.diagnostics:
        warnings.warn(UnitWarning(d), stacklevel=2)
    return c.values


@dataclass(frozen=True)
class ArrayConversion:
    """Result of ``convert_array``: the SI values in the shape written (None for an entry that
    failed; ``values`` is None when the array itself is refused), one ``Conversion`` per entry in
    order (``entries``), the unit as written after the character map, and every diagnostic: the
    array's own first, then each entry's, in order."""
    quantity: str
    values: list | None
    unit: str
    unit_text: str | None
    entries: tuple[Conversion, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def error(self) -> Diagnostic | None:
        return next((d for d in self.diagnostics if d.severity == "error"), None)

    @property
    def ok(self) -> bool:
        return self.error is None


def convert_array(values: Any, quantity_name: str, *, path: str = "") -> ArrayConversion:
    """Convert a tagged array, a dimensionless ``{"values": [...]}`` or a short vector of at most
    3 quantity strings, with every diagnostic, as ``convert`` does for one value.

    Never raises for a bad value: a value of the wrong form (a string in a tagged array, a list
    of more than 3 strings, an object that is no array) is ``E-VALUE-FORM`` at its path. Raises
    UnitError only for an unknown quantity name."""
    qo = quantity(quantity_name)

    def refused(diagnostic: Diagnostic, unit_text: str | None = None) -> ArrayConversion:
        return ArrayConversion(qo.name, None, qo.unit, unit_text, (), (diagnostic,))

    entries: list[Conversion] = []
    unit_text = None
    if isinstance(values, Mapping):
        extra = sorted(set(values) - {"unit", "values"})
        if extra:
            return refused(Diagnostic("E-KEY-UNKNOWN", _join(path, extra[0]),
                                      f'Unknown key "{extra[0]}" in a tagged array, which holds "unit" and "values".'))
        if "values" not in values:
            return refused(Diagnostic("E-KEY-MISSING", _join(path, "values"), 'A tagged array needs "values".'))
        unit = values.get("unit")
        data = _as_list(values["values"])
        if data is None:
            return refused(Diagnostic("E-VALUE-FORM", _join(path, "values"),
                                      'the "values" of a tagged array are a list (or an array with tolist())'))
        if unit is None:
            def one(v: Any, p: str) -> Conversion:
                return _form(qo, p, _NUMBERS_ONLY) if not _is_number(v) else convert(v, qo.name, path=p)
        else:
            if not isinstance(unit, str):
                return refused(Diagnostic("E-VALUE-FORM", _join(path, "unit"), "a tagged array's unit is a string"))
            unit_text = normalize(unit)
            canonical = _resolve(unit_text, qo, None, f'"unit": "{unit}"', _join(path, "unit"))
            if isinstance(canonical, Diagnostic):
                return refused(canonical, unit_text)

            def one(v: Any, p: str) -> Conversion:
                if not _is_number(v):
                    return _form(qo, p, _NUMBERS_ONLY)
                number, text = _bare_number(v)
                read = _Read(number, text, canonical, f'"{text} {unit}"', f"{text} {canonical}", _integer_literal(v),
                             unit_text)
                return _finish(read, qo, p)
        out = _walk(data, _join(path, "values"), one, entries)
    elif _as_list(values) is not None:
        vector = _as_list(values)
        if len(vector) > 3 or any(_as_list(v) is not None for v in vector):
            return refused(Diagnostic("E-VALUE-FORM", path,
                                      "a list of quantity strings is a short vector of at most 3 components; write a "
                                      "tagged array {'unit': 'nm', 'values': [...]} for longer or nested lists"))

        def one(v: Any, p: str) -> Conversion:
            if isinstance(v, str) or _is_number(v):
                return convert(v, qo.name, path=p)
            return _form(qo, p, f"a vector component is a quantity string or a number, not {type(v).__name__}")
        out = [_walk(v, f"{path}[{i}]", one, entries) for i, v in enumerate(vector)]
    else:
        return refused(Diagnostic("E-VALUE-FORM", path, "an array is a tagged array {'unit': ..., 'values': [...]} "
                                  "or a list"))
    found = tuple(d for c in entries for d in c.diagnostics)
    return ArrayConversion(qo.name, out, qo.unit, unit_text, tuple(entries), found)


_NUMBERS_ONLY = "the values of a tagged array are bare numbers"


def _is_number(v: Any) -> bool:
    return not isinstance(v, bool) and isinstance(v, (numbers.Real, Decimal))


def _form(qo: Quantity, path: str, message: str) -> Conversion:
    return Conversion(qo.name, None, None, qo.unit, None, (Diagnostic("E-VALUE-FORM", path, message),))


def is_quantity_text(text: Any) -> bool:
    """True for a quantity string: a number, one space and a unit that the spelling table accepts
    or the known-refused list names (``"0.5 um"``, ``"10 mPa"``; attached ``"40%"`` too).

    False for an expression (``"w/2"``, ``"220 nm + gap"``), a bare number and anything that is
    not a string. A document reader uses it to tell a tagged value from an expression."""
    if not isinstance(text, str):
        return False
    m = _QTY.fullmatch(normalize(text))
    return m is not None and (m.group(2) in _SPELLINGS or m.group(2) in _REFUSED)


# ---- complex values -----------------------------------------------------------------------------

@dataclass(frozen=True)
class ComplexConversion:
    """Result of ``convert_complex``: the complex SI value under exp(-i omega t) (None on error),
    its exact real and imaginary parts, the canonical unit, the form read (``"real"``, ``"re_im"``
    or ``"n_k"``) and the diagnostics."""
    quantity: str
    value: complex | None
    exact: tuple[Fraction, Fraction] | None
    unit: str
    form: str | None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def error(self) -> Diagnostic | None:
        return next((d for d in self.diagnostics if d.severity == "error"), None)

    @property
    def ok(self) -> bool:
        return self.error is None


_TIME_CONVENTION = "exp(-i omega t)"


def convert_complex(value: Any, quantity_name: str, *, path: str = "", allow_gain: bool = False) -> ComplexConversion:
    """Convert a value of a complex quantity under exp(-i omega t), with its diagnostics.

    Forms: a real value as ``convert`` takes it (``4.0``, a quantity string); ``{"re": .., "im": ..}``
    for a dimensionless complex quantity other than ``refractive_index``; ``{"n": .., "k": ..}``
    for ``refractive_index``. The real part (``re``, ``n``) is checked against the quantity's domain
    and band; the imaginary part is a bare number. For a passive material quantity
    (``refractive_index``, ``relative_permittivity``, ``relative_permeability``) a negative
    imaginary part or ``k`` is ``E-GAIN`` with the exp(+j omega t) hint, unless ``allow_gain``.
    A ``[re, im]`` pair is ``E-VALUE-FORM``. Never raises for a bad value; raises UnitError only
    for an unknown quantity name."""
    qo = quantity(quantity_name)
    nk = qo.base == "refractive_index"
    keys = ("n", "k") if nk else ("re", "im")

    def failed(*diagnostics: Diagnostic, form: str | None = None) -> ComplexConversion:
        return ComplexConversion(qo.name, None, None, qo.unit, form, tuple(diagnostics))

    if isinstance(value, Mapping):
        form = "n_k" if nk else "re_im"
        given = set(value)
        if not qo.complex:
            return failed(Diagnostic("E-VALUE-FORM", path, f"{qo.name} is real: write one value, not an object."))
        if nk and given & {"re", "im"} and not given & {"n", "k"}:
            return failed(Diagnostic("E-VALUE-FORM", path, 'refractive_index is written {"n": .., "k": ..} '
                                     f"under {_TIME_CONVENTION}, with k >= 0 for loss; " + '{"re", "im"} is for '
                                     "relative_permittivity and relative_permeability."), form=form)
        if not nk and given & {"n", "k"} and not given & {"re", "im"}:
            return failed(Diagnostic("E-VALUE-FORM", path, '"n" and "k" are written only inside refractive_index; '
                                     f'write {{"re": .., "im": ..}} under {_TIME_CONVENTION}.'), form=form)
        if qo.unit != "1":
            return failed(Diagnostic("E-VALUE-FORM", path, f'{qo.name} has the unit {qo.unit}; '
                                     '{"re": .., "im": ..} is only for a dimensionless quantity.'), form=form)
        extra = sorted(str(k) for k in given - set(keys))
        if extra:
            return failed(Diagnostic("E-KEY-UNKNOWN", _join(path, extra[0]), f'Unknown key "{extra[0]}" in a '
                                     f'complex value, which holds "{keys[0]}" and "{keys[1]}".'), form=form)
        missing = [k for k in keys if k not in value]
        if missing:
            note = f" Write {keys[0]} alone as a number for a lossless value." if missing == [keys[1]] else ""
            return failed(Diagnostic("E-KEY-MISSING", _join(path, missing[0]), f'A complex value needs "{keys[0]}" '
                                     f'and "{keys[1]}".{note}'), form=form)
        real = convert(value[keys[0]], qo.name, path=_join(path, keys[0])) if _readable(value[keys[0]]) else \
            _form(qo, _join(path, keys[0]), f'"{keys[0]}" is a bare number')
        imag = _imaginary(value[keys[1]], qo, _join(path, keys[1]))
        found = real.diagnostics + imag.diagnostics
        if real.error is not None or imag.error is not None:
            return failed(*found, form=form)
        if imag.exact < 0 and not allow_gain and qo.complex and "material" in qo.places:
            found += (_gain(imag, qo, _join(path, keys[1]), nk),)
            return failed(*found, form=form)
        return ComplexConversion(qo.name, complex(real.value, imag.value), (real.exact, imag.exact), qo.unit, form,
                                 found)
    if _as_list(value) is not None:
        want = '{"n": .., "k": ..}' if nk else '{"re": .., "im": ..}'
        return failed(Diagnostic("E-VALUE-FORM", path, f"a [re, im] pair is not read: write {want} under "
                                 f"{_TIME_CONVENTION} (a source using exp(+j omega t) has the opposite imaginary "
                                 "sign)."))
    if not _readable(value):
        objects = '{"n": .., "k": ..}' if nk else '{"re": .., "im": ..}'
        return failed(Diagnostic("E-VALUE-FORM", path, f"{qo.name} takes a number, a quantity string or "
                                 f"{objects}, not {type(value).__name__}."))
    c = convert(value, qo.name, path=path)
    if c.error is not None:
        return failed(*c.diagnostics, form="real")
    return ComplexConversion(qo.name, complex(c.value, 0.0), (c.exact, Fraction(0)), qo.unit, "real", c.diagnostics)


def _readable(v: Any) -> bool:
    """A value ``convert`` reads: a string or a number (not a bool)."""
    return isinstance(v, str) or _is_number(v)


def _imaginary(v: Any, qo: Quantity, path: str) -> Conversion:
    """The imaginary part (or k): a bare number, checked for range only."""
    if isinstance(v, str):
        text = normalize(v)
        msg = f'"{v}" is a string; the imaginary part is a bare JSON number'
        n = _decimal_fraction(text) if _BARE.fullmatch(text) else None
        if n is not None and not _range_problem(n):
            return Conversion(qo.name, None, None, qo.unit, None,
                              (Diagnostic("E-UNIT-UNKNOWN", path, msg + f": {text}.", Fix(_bare_value(text))),))
        return Conversion(qo.name, None, None, qo.unit, None, (Diagnostic("E-UNIT-UNKNOWN", path, msg + "."),))
    if not _is_number(v):
        return _form(qo, path, f"the imaginary part is a bare number, not {type(v).__name__}")
    number, text = _bare_number(v)
    if number is None:
        return Conversion(qo.name, None, None, qo.unit, None,
                          (Diagnostic("E-DOMAIN", path, f"{text} is far outside the range of a double."),))
    problem = _range_problem(number)
    if problem:
        return Conversion(qo.name, None, None, qo.unit, None, (Diagnostic("E-DOMAIN", path, f"{text} is {problem}."),))
    return Conversion(qo.name, float(number), number, qo.unit, text, (), text, None)


def _gain(imag: Conversion, qo: Quantity, path: str, nk: bool) -> Diagnostic:
    """E-GAIN for a negative imaginary part; the negated number is a suggestion (it changes the meaning)."""
    part = "k" if nk else f"Im {qo.name}"
    msg = (f"{part} = {imag.number_text} is gain under {_TIME_CONVENTION}: a passive material has "
           f"{'k' if nk else 'an imaginary part'} >= 0, which is loss. If your source uses exp(+j omega t), "
           f"negate the imaginary part.")
    flipped = _bare_value(_decimal_text(-imag.exact))
    return Diagnostic("E-GAIN", path, msg, suggestions=(Suggestion(flipped, imag.value, -imag.value, "1"),))


def _as_list(data: Any) -> list | None:
    """A list for a sequence or an array (``tolist()``), None for anything else (str, numbers)."""
    if isinstance(data, (str, bytes, Mapping)):
        return None
    if not isinstance(data, Sequence) and callable(getattr(data, "tolist", None)):
        data = data.tolist()
    return list(data) if isinstance(data, Sequence) and not isinstance(data, (str, bytes)) else None


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _walk(data: Any, path: str, fn, results: list) -> Any:
    items = _as_list(data)
    if items is not None:
        return [_walk(x, f"{path}[{i}]", fn, results) for i, x in enumerate(items)]
    c = fn(data, path)
    results.append(c)
    return c.value


def format(value: float, quantity_name: str, unit: str | None = None) -> str:
    """Quantity string of an SI value in a menu unit, with the shortest number that converts back
    to exactly ``value`` (``format(2e11, "youngs_modulus", "GPa") == "200 GPa"``)."""
    qo = quantity(quantity_name)
    if unit is None:
        unit = qo.unit
    canonical = "1" if unit == "1" else _SPELLINGS.get(normalize(unit))
    if canonical not in qo.menu:
        raise UnitError(Diagnostic("E-UNIT-NOT-ACCEPTED", "", f'"{unit}" is not on the {qo.name} menu. '
                                   f"Accepted: {_menu_text(qo)}."))
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("format takes a finite value")
    u, c = _UNITS[canonical], _UNITS[qo.unit]
    target = (Fraction(x) * c.factor + c.offset - u.offset) / u.factor
    text = _shortest_text(target, canonical, qo, x)
    return text if canonical == "1" else f"{text} {canonical}"


# ---- geometry grid ------------------------------------------------------------------------------

@dataclass(frozen=True)
class GridLength:
    """A length on the integer picometre grid: ``picometres`` (None on error), the exact value in pm
    before rounding, the unit it was read in and the diagnostics (rounding is reported)."""
    picometres: int | None
    exact: Fraction | None
    unit: str | None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def error(self) -> Diagnostic | None:
        return next((d for d in self.diagnostics if d.severity == "error"), None)

    @property
    def metres(self) -> float | None:
        return None if self.picometres is None else pm_to_m(self.picometres)


def length_to_pm(value: Any, length_unit: str | None = None, *, path: str = "") -> GridLength:
    """Put a geometry length on the signed int64 picometre grid, rounding half to even once.

    A bare number (or bare number text) is read in ``length_unit``, which must be one of
    LENGTH_UNITS; a quantity string with its own length unit ("0.5 nm") is read in that unit.
    A value that moves is reported: I-PM-ROUNDING below 1e-3 pm, else W-PM-ROUNDING."""
    qo = quantity("length")
    if isinstance(value, str) and not _BARE.fullmatch(normalize(value)):
        read = _parse(value, qo, path)
        if isinstance(read, Diagnostic):
            return GridLength(None, None, None, (read,))
        number, unit, shown = read.number, read.unit, read.shown
    else:
        if length_unit is None:
            msg = "A bare shape number is read in its component's length_unit, and none was given."
            return GridLength(None, None, None, (Diagnostic("E-UNIT-MISSING", path, msg),))
        unit = _SPELLINGS.get(normalize(length_unit)) if isinstance(length_unit, str) else None
        if unit not in LENGTH_UNITS:
            msg = f'length_unit "{length_unit}" is not one of: {" ".join(LENGTH_UNITS)}.'
            return GridLength(None, None, None, (Diagnostic("E-UNIT-NOT-ACCEPTED", path, msg),))
        if isinstance(value, str):
            number, text = _decimal_fraction(normalize(value)), normalize(value)
        else:
            number, text = _bare_number(value)
        shown = f"{text} ({length_unit})"
    if number is None:
        return GridLength(None, None, unit, (Diagnostic("E-DOMAIN", path, f"{shown} is far outside the pm grid."),))
    exact = number * _UNITS[unit].factor * 10 ** 12
    k = round(exact)                                   # Fraction rounds half to even
    if not _INT64_MIN <= k <= _INT64_MAX:
        msg = f"{shown} is outside the int64 picometre grid (about +-9.2e6 m)."
        return GridLength(None, None, unit, (Diagnostic("E-DOMAIN", path, msg),))
    found = ()
    shift = k - exact
    if shift:
        code = "I-PM-ROUNDING" if abs(shift) < Fraction(1, 1000) else "W-PM-ROUNDING"
        msg = (f"{shown} is {_decimal_text(exact)} pm; it is stored as {k} pm, "
               f"a shift of {_decimal_text(shift)} pm.")
        found = (Diagnostic(code, path, msg),)
    return GridLength(k, exact, unit, found)


def pm_to_m(picometres: int) -> float:
    """Metres of a grid value, rounded once: ``pm_to_m(100_000_000_000) == 0.1``.

    Takes an integer only (an int or a numpy integer); a float, a string or a bool is a TypeError."""
    if isinstance(picometres, bool):
        raise TypeError("a grid value is an integer number of picometres, not a bool")
    try:
        k = operator.index(picometres)
    except TypeError:
        raise TypeError(f"a grid value is an integer number of picometres, not {type(picometres).__name__}") \
            from None
    return float(Fraction(k, 10 ** 12))


# ---- generator entry point ----------------------------------------------------------------------

def generate_tables() -> str:
    """Text of unit_tables.json generated from the shipped quantities.json (deterministic)."""
    from . import _unit_tables
    return _unit_tables.generate(_read(SOURCE_FILE))


def _main(argv: list[str] | None = None) -> int:
    """``python -m physmat.units [--check] [--write] [names]``. --check and --write run
    ``physmat._unit_tables``, which also works when unit_tables.json does not load."""
    import argparse

    from . import _unit_tables

    parser = argparse.ArgumentParser(prog="python -m physmat.units",
                                     description="Describe quantities, or check or regenerate unit_tables.json.")
    parser.add_argument("--check", action="store_true", help="exit 1 if unit_tables.json is not the generator output")
    parser.add_argument("--write", action="store_true", help="regenerate unit_tables.json next to this module")
    parser.add_argument("names", nargs="*", help="quantity names to describe")
    args = parser.parse_args(argv)
    flags = [flag for flag, on in (("--check", args.check), ("--write", args.write)) if on]
    status = _unit_tables.main(flags) if flags else 0
    for name in args.names:
        qo = quantity(name)
        print(f"{qo.name}: {qo.description['en']}")
        print(f"  unit {qo.unit}; menu {_menu_text(qo)}; kind {qo.kind}; domain {dict(qo.domain or {})}; "
              f"band {dict(qo.band or {})}")
    return status


if __name__ == "__main__":
    raise SystemExit(_main())
