# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The document's unit system: what the numbers in a document mean.

A document declares one unit per SI base dimension it needs. Every numeric field
is then a bare number in that system, and this module is the only place in the
workspace that knows how to move between it and SI:

    factor(dim) = prod over base b of (unit_b_in_SI ** dim_b)
    value_doc   = value_SI / factor(dim)
    value_SI    = value_doc * factor(dim)

A second implementation of that arithmetic would be a defect rather than a
duplication: two of them disagree invisibly at SI, where every factor is 1**k.

Absent keys are SI, with one exception that carries the whole design: inside the
set of dimensions a document's physics actually requires, an absent key is an
error even though the answer would have been 1.0. A bridge in metres therefore
has to say so, and cannot get metres by forgetting.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

BASE_DIMENSIONS = ("length", "mass", "time", "temperature", "current", "amount", "luminous")

#: dimension -> {symbol: size in the SI unit of that dimension}. Closed, case-sensitive.
BASE_UNITS: dict[str, dict[str, float]] = {
    "length": {"m": 1.0, "km": 1e3, "cm": 1e-2, "mm": 1e-3, "um": 1e-6, "µm": 1e-6,
               "nm": 1e-9, "pm": 1e-12, "fm": 1e-15, "Mm": 1e6, "Gm": 1e9},
    "mass": {"kg": 1.0, "g": 1e-3, "mg": 1e-6, "ug": 1e-9, "ng": 1e-12, "pg": 1e-15, "t": 1e3},
    "time": {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12, "fs": 1e-15},
    "temperature": {"K": 1.0},
    "current": {"A": 1.0, "mA": 1e-3, "uA": 1e-6, "nA": 1e-9},
    "amount": {"mol": 1.0, "mmol": 1e-3},
    "luminous": {"cd": 1.0},
}

#: SI symbol of each base dimension, for the escape hatch key ``{"in_m": 1e-10}``.
SI_SYMBOL = {"length": "m", "mass": "kg", "time": "s", "temperature": "K",
             "current": "A", "amount": "mol", "luminous": "cd"}


class UnitError(ValueError):
    """A unit declaration or a unit string that cannot be resolved."""


# ---------------------------------------------------------------------------
# the declared system


@dataclass(frozen=True)
class Scale:
    """A resolved unit system: one SI size per base dimension, plus what was declared.

    Immutable, built once in ``Document.validate`` and passed as an object. It is
    never threaded through call sites as a loose number and never written back
    into the document.
    """
    sizes: tuple[float, ...]                     # in BASE_DIMENSIONS order, SI size of each unit
    declared: frozenset[str]                     # which dimensions the document actually named

    def size(self, dimension: str) -> float:
        return self.sizes[BASE_DIMENSIONS.index(dimension)]

    def factor(self, dim: Mapping[str, Fraction | int]) -> float:
        """The single conversion rule. ``dim`` maps base dimension -> exponent."""
        out = 1.0
        for base, exponent in dim.items():
            if exponent:
                out *= self.size(base) ** float(exponent)
        return out

    def to_si(self, value_doc: float, dim: Mapping[str, Fraction | int]) -> float:
        return value_doc * self.factor(dim)

    def from_si(self, value_si: float, dim: Mapping[str, Fraction | int]) -> float:
        return value_si / self.factor(dim)

    def is_si(self) -> bool:
        return all(s == 1.0 for s in self.sizes)


SI = Scale(tuple(1.0 for _ in BASE_DIMENSIONS), frozenset())


def resolve(block: object) -> Scale:
    """Validate a ``units`` block and resolve it. Absent dimensions are SI."""
    if block is None:
        return SI
    if not isinstance(block, dict):
        raise UnitError("units must be an object mapping base dimensions to unit symbols")
    unknown = [k for k in block if k not in BASE_DIMENSIONS]
    if unknown:
        raise UnitError(f"units has unknown key(s) {sorted(unknown)}; the seven base dimensions are "
                        f"{list(BASE_DIMENSIONS)}")
    sizes, declared = [], set()
    for dimension in BASE_DIMENSIONS:
        if dimension not in block:
            sizes.append(1.0)
            continue
        sizes.append(_resolve_one(dimension, block[dimension]))
        declared.add(dimension)
    return Scale(tuple(sizes), frozenset(declared))


def _resolve_one(dimension: str, spec: object) -> float:
    table = BASE_UNITS[dimension]
    if isinstance(spec, str):
        if spec in table:
            return table[spec]
        for other, other_table in BASE_UNITS.items():
            if spec in other_table:
                raise UnitError(f"units.{dimension}: {spec!r} is a unit of {other}, not {dimension}")
        raise UnitError(f"units.{dimension}: unknown unit {spec!r}; expected one of "
                        f"{sorted(table)} or the escape hatch {{'in_{SI_SYMBOL[dimension]}': <number>}}")
    if isinstance(spec, dict):
        key = f"in_{SI_SYMBOL[dimension]}"
        if set(spec) != {key}:
            raise UnitError(f"units.{dimension}: the escape hatch takes exactly {{{key!r}: <number>}}, "
                            f"got {sorted(spec)}")
        value = spec[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise UnitError(f"units.{dimension}.{key} must be a number")
        value = float(value)
        if not (value > 0.0 and value < float("inf")):
            raise UnitError(f"units.{dimension}.{key} must be finite and positive, got {value!r}")
        return value
    raise UnitError(f"units.{dimension} must be a unit symbol or {{'in_{SI_SYMBOL[dimension]}': <number>}}")


# ---------------------------------------------------------------------------
# unit strings, as material databases and constants write them

def _dim(**kw) -> dict[str, Fraction]:
    return {k: Fraction(v) for k, v in kw.items() if v}


#: symbol -> (dimension vector, size in SI). Derived units carry their full vector:
#: a watt hides an m^2, so counting "m" tokens in ``W/(m K)`` gets the sign wrong.
_UNITS: dict[str, tuple[dict[str, Fraction], float]] = {
    "m": (_dim(length=1), 1.0),
    "g": (_dim(mass=1), 1e-3),
    "t": (_dim(mass=1), 1e3),
    "s": (_dim(time=1), 1.0),
    "K": (_dim(temperature=1), 1.0),
    "A": (_dim(current=1), 1.0),
    "mol": (_dim(amount=1), 1.0),
    "cd": (_dim(luminous=1), 1.0),
    "Hz": (_dim(time=-1), 1.0),
    "N": (_dim(length=1, mass=1, time=-2), 1.0),
    "Pa": (_dim(length=-1, mass=1, time=-2), 1.0),
    "J": (_dim(length=2, mass=1, time=-2), 1.0),
    "W": (_dim(length=2, mass=1, time=-3), 1.0),
    "C": (_dim(time=1, current=1), 1.0),
    "V": (_dim(length=2, mass=1, time=-3, current=-1), 1.0),
    "F": (_dim(length=-2, mass=-1, time=4, current=2), 1.0),
    "S": (_dim(length=-2, mass=-1, time=3, current=2), 1.0),
    "H": (_dim(length=2, mass=1, time=-2, current=-2), 1.0),
    "T": (_dim(mass=1, time=-2, current=-1), 1.0),
    "Ohm": (_dim(length=2, mass=1, time=-3, current=-2), 1.0),
    "eV": (_dim(length=2, mass=1, time=-2), 1.602176634e-19),
}
_NO_PREFIX = {"t"}
_PREFIXES = {"Y": 1e24, "Z": 1e21, "E": 1e18, "P": 1e15, "T": 1e12, "G": 1e9, "M": 1e6,
             "k": 1e3, "h": 1e2, "da": 1e1, "d": 1e-1, "c": 1e-2, "m": 1e-3, "u": 1e-6,
             "µ": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15, "a": 1e-18, "z": 1e-21, "y": 1e-24}


def _symbol(token: str) -> tuple[dict[str, Fraction], float]:
    if token in _UNITS:
        return _UNITS[token]
    for prefix, scale in _PREFIXES.items():
        rest = token[len(prefix):]
        if token.startswith(prefix) and rest in _UNITS and rest not in _NO_PREFIX:
            dim, size = _UNITS[rest]
            return dim, size * scale
    raise UnitError(f"unknown unit symbol {token!r}")


def parse_unit_string(text: str) -> tuple[dict[str, Fraction], float]:
    """``"W/(m K)"`` -> (dimension vector, size in SI).

    Symbols are tokenized before any operator is applied, so a fractional
    exponent (``MPa*m^1/2``) does not collide with division.
    """
    if not isinstance(text, str):
        raise UnitError(f"unit must be a string, got {type(text).__name__}")
    s = text.strip()
    if s in ("", "-", "1"):
        return {}, 1.0
    tokens, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            tokens.append("*"); i += 1
        elif c in "*/^()":
            tokens.append(c); i += 1
        elif c.isdigit() or (c == "-" and tokens and tokens[-1] == "^"):
            j = i + 1
            while j < len(s) and s[j].isdigit():
                j += 1
            tokens.append(s[i:j]); i = j
        elif c.isalpha() or c == "µ":
            j = i
            while j < len(s) and (s[j].isalpha() or s[j] == "µ"):
                j += 1
            tokens.append(s[i:j]); i = j
        else:
            raise UnitError(f"unit {text!r}: unexpected character {c!r}")
    while tokens and tokens[0] == "*":
        tokens.pop(0)
    depth = 0
    for token in tokens:
        depth += (token == "(") - (token == ")")
        if depth < 0:
            raise UnitError(f"unit {text!r}: unbalanced parentheses")
    if depth:
        raise UnitError(f"unit {text!r}: unbalanced parentheses")
    return _parse_expression(tokens, text)


def _parse_expression(tokens: list[str], text: str) -> tuple[dict[str, Fraction], float]:
    dim: dict[str, Fraction] = {}
    factor = 1.0
    sign = 1
    pending = False
    while tokens:
        token = tokens.pop(0)
        if token == "*":
            sign, pending = 1, True; continue
        if token == "/":
            sign, pending = -1, True; continue
        if token == ")":
            pending = False
            break
        if token == "(":
            sub_dim, sub_factor = _parse_expression(tokens, text)   # consumes through ")"
        elif token.isdigit():
            if token != "1":
                raise UnitError(f"unit {text!r}: only the numeral 1 may appear, got {token!r}")
            sub_dim, sub_factor = {}, 1.0
        else:
            sub_dim, sub_factor = _symbol(token)
        exponent = Fraction(1)
        if tokens and tokens[0] == "^":
            tokens.pop(0)
            exponent = _parse_exponent(tokens, text)
        exponent *= sign
        for base, value in sub_dim.items():
            dim[base] = dim.get(base, Fraction(0)) + value * exponent
        factor *= sub_factor ** float(exponent)
        sign, pending = 1, False
    if pending:
        raise UnitError(f"unit {text!r}: trailing operator with nothing after it")
    return {k: v for k, v in dim.items() if v}, factor


def _parse_exponent(tokens: list[str], text: str) -> Fraction:
    if not tokens:
        raise UnitError(f"unit {text!r}: '^' with no exponent")
    head = tokens.pop(0)
    try:
        value = Fraction(int(head))
    except ValueError:
        raise UnitError(f"unit {text!r}: bad exponent {head!r}") from None
    if len(tokens) >= 2 and tokens[0] == "/" and tokens[1].lstrip("-").isdigit():
        tokens.pop(0)
        value = Fraction(value, int(tokens.pop(0)))
    return value


#: physmat's optical database is micrometre-native and stays that way: that is a
#: property of a material database, not of a document. This is the one boundary.
UM_IN_SI = 1e-6


def to_micrometres(value_doc: float, scale: Scale) -> float:
    """A document length, in micrometres, for physmat."""
    return scale.to_si(value_doc, {"length": 1}) / UM_IN_SI


# ---------------------------------------------------------------------------
# magnitude plausibility

#: quantity -> (low, high) in SI. Heuristic bands, so these warn and never reject.
PLAUSIBLE_SI = {
    "wavelength": (1e-9, 1e-3),          # m
    "refractive index": (1.0, 5.0),      # dimensionless
    "Young's modulus": (1e6, 1e12),      # Pa
    "density": (1e-2, 1e5),              # kg/m^3
    "temperature": (1.0, 5000.0),        # K
}


def implausible(quantity: str, value_si: float) -> str | None:
    """A message when a converted value is outside its band, else None.

    This is the only check in the stack that can catch a scale error. A unit
    declaration says what the numbers mean; it cannot say whether they are the
    numbers you meant, and no dimension checker anywhere catches a bridge
    authored in millimetres and declared in metres. The bands are rules of thumb,
    so this warns and names the converted SI value rather than rejecting.
    """
    band = PLAUSIBLE_SI.get(quantity)
    if band is None:
        return None
    low, high = band
    if low <= abs(value_si) <= high or value_si == 0.0:
        return None
    return f"{quantity} is {value_si:g} in SI, outside the usual {low:g} to {high:g}; check the units block"
