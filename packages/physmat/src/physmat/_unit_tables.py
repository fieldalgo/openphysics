# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Build-time generator of ``unit_tables.json`` from ``quantities.json``.

The run-time converter (``physmat.units``) has no unit grammar: it looks unit
strings up whole. This module holds the small grammar that writes those tables
once, at build time, and checks the hand-written registry while doing so.

Generated sections:

- ``units``: every canonical unit of a quantity or a menu, with its dimension,
  exact rational factor to coherent SI, offset (``degC`` only), angle exponent
  and English name;
- ``spellings``: every accepted spelling -> its canonical unit. Separators are one
  space or ``*``; a denominator is ``/x``, ``/(x y)`` or ``/x/y``; negative powers
  (``W m^-1 K^-1``) and factor orderings are included. Run-together forms
  (``W/mK``) and unparenthesised ``a/b c`` forms are never emitted;
- ``refused``: known-refused spellings with their code and reading: the number
  ``1`` as a unit, foreign units, SI-prefixed symbols that are not on the closed
  symbol list, ``degC`` inside compounds (fix: ``K``), powers without ``^``
  (fix: ``^``), ambiguous run-together or ``a/b c`` forms (also with ``degC``
  for ``K``), case look-alikes of menu compounds (``MW/(m K)`` for ``mW/(m K)``)
  and input-menu compounds with one factor in another common prefix
  (``MW/m^3``, ``mW/(m^2 K)``, ``V/cm``), each with its reading;
- ``names``: every legal quantity name -> its registry base entry;
- ``name_overrides``: the places and rank of a name where they differ from its
  base (a name with an output-only word is an output; ``inward_heat_flux`` is a
  normal component, a scalar);
- ``display_groups``: the members of each display group (``length``: every
  length quantity name).

Everything is sorted, so the output does not depend on hash seeds or dict order.
Standard library only. This module reads only ``quantities.json``, so
``python -m physmat._unit_tables --write`` also repairs an unreadable
``unit_tables.json`` (for example after a merge conflict).
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
from fractions import Fraction
from importlib import resources
from pathlib import Path

FORMAT = "physmat.unit_tables/v1"
SOURCE_FILE = "quantities.json"
TABLES_FILE = "unit_tables.json"
NOTE = ("Generated from quantities.json by physmat.units.generate_tables(); do not edit. "
        "Regenerate with: python -m physmat.units --write (or python -m physmat._unit_tables --write)")
SEPARATORS = (" ", "*")
KINDS = {"ordinary", "absolute", "difference", "fraction", "count"}
RANKS = {"scalar", "vector", "tensor", "matrix"}
PLACES = {"document", "material", "api", "result"}
FAMILIES = {"spectral"}
QUANTITY_FIELDS = {"dimension", "unit", "menu", "kind", "rank", "complex", "domain", "band", "warn_inside",
                   "slot_refusals", "places", "qualifiers", "name_rank", "statistic_definitions", "symbols",
                   "refused_aliases", "status", "hint", "family", "scope", "sign", "description"}
DOMAIN_KEYS = {"min", "min_exclusive", "max", "max_exclusive"}
BAND_KEYS = {"abs_range", "range", "abs_min", "when_unit"}
OUTPUT_PLACES = ("api", "result")
# An exponent is an integer or a half-integer in parentheses (m^(1/2), output-only units).
FACTOR_RE = re.compile(r"(?P<sym>[A-Za-z%]+|[0-9]+)(?:\^(?:(?P<exp>-?[0-9]+)|\((?P<half>-?[0-9]+/2)\)))?")
# Prefixes tried on one factor of an input-menu compound ("c" on the metre only), and the bases left alone.
VARIANT_PREFIXES = ("", "p", "n", "u", "m", "k", "M", "G")
VARIANT_FIXED = ("K", "degC")
LONE_K = re.compile(r"(?<![A-Za-z])K(?![A-Za-z])")
KELVIN_END = re.compile(r"K(?![A-Za-z])")             # K as a whole symbol or glued at the end (W/mK)
DEGC = re.compile(r"(?<![A-Za-z])degC(?![A-Za-z])")
DEGC_NOTE = "degC is not used inside a compound unit; write K (a 1 degC step equals a 1 K step)"
CODES = ("E-UNIT-NOT-ACCEPTED", "E-DEGC-NOT-ABSOLUTE", "E-UNIT-AMBIGUOUS")


# ---- exact arithmetic and dimensions ------------------------------------------------------------

def factor_of(text: str, pi: Fraction) -> Fraction:
    """Exact factor from a rational literal, or ``pi/<n>`` for the angle degree."""
    if text.startswith("pi/"):
        return pi / Fraction(text[3:])
    return Fraction(text)


def dim_add(a: dict, b: dict, times: int = 1) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + times * v
    return {k: v for k, v in out.items() if v}


def dim_sorted(d: dict, order: list[str]) -> dict:
    return {k: d[k] for k in order if d.get(k)}


# ---- canonical form -----------------------------------------------------------------------------

def parse_canonical(text: str, symbols: dict) -> tuple[list, list]:
    """Split a canonical unit into numerator and denominator factors [(token, exponent)]."""
    num_text, slash, den_text = text.partition("/")
    if slash and den_text.startswith("(") and den_text.endswith(")"):
        den_items = den_text[1:-1].split(" ")
    elif slash:
        den_items = [den_text]
    else:
        den_items = []
    num_items = [] if num_text == "1" else num_text.split(" ")
    num, den = [_factor(i, symbols, text) for i in num_items], [_factor(i, symbols, text) for i in den_items]
    if render(num, den) != text:
        raise ValueError(f"menu unit {text!r} is not in canonical form ({render(num, den)!r})")
    return num, den


def _factor(item: str, symbols: dict, text: str) -> tuple[str, int | Fraction]:
    m = FACTOR_RE.fullmatch(item)
    if not m:
        raise ValueError(f"bad factor {item!r} in unit {text!r}")
    sym = m.group("sym")
    if not sym.isdigit() and sym not in symbols:
        raise ValueError(f"unit {text!r} uses {sym!r}, which is not on the closed symbol list")
    if m.group("half"):
        exp = Fraction(m.group("half"))
        if exp < 0 or exp.denominator != 2:
            raise ValueError(f"unit {text!r}: a half-integer exponent is positive, such as ^(1/2) or ^(3/2)")
        return sym, exp
    exp = int(m.group("exp") or 1)
    if exp < 1 or (exp == 1 and m.group("exp")):
        raise ValueError(f"unit {text!r}: write positive exponents >= 2 only")
    return sym, exp


def fmt(f: tuple[str, int | Fraction], sign: int = 1) -> str:
    sym, exp = f
    exp *= sign
    if isinstance(exp, Fraction) and exp.denominator != 1:
        return f"{sym}^({exp})"
    return sym if exp == 1 else f"{sym}^{exp}"


def _power(base: Fraction, exp: int | Fraction) -> Fraction:
    """Exact base**exp; a half-integer power only of a factor of 1 (m^(1/2), not mm^(1/2))."""
    if isinstance(exp, int) or exp.denominator == 1:
        return base ** int(exp)
    if base != 1:
        raise ValueError(f"a half-integer power of the factor {base} is not exact")
    return Fraction(1)


def _json_dim(d: dict) -> dict:
    """Dimension exponents for JSON: integers, or halves written as exact binary floats (-0.5, -1.5)."""
    return {k: int(v) if Fraction(v).denominator == 1 else float(v) for k, v in d.items()}


def render(num: list, den: list, sep: str = " ") -> str:
    head = sep.join(fmt(f) for f in num) or "1"
    if not den:
        return head
    if len(den) == 1:
        return f"{head}/{fmt(den[0])}"
    return f"{head}/({sep.join(fmt(f) for f in den)})"


def spellings_of(num: list, den: list) -> list[str]:
    """Every accepted spelling of one canonical unit (canonical form first)."""
    out = [render(num, den)]
    if any(sym.isdigit() for sym, _ in num + den):         # dB/(90 deg): only the two separators
        out.append(render(num, den, "*"))
        return _unique(out)
    for sep in SEPARATORS:
        for n in itertools.permutations(num):
            head = sep.join(fmt(f) for f in n) or "1"
            if not den:
                out.append(head)
            elif len(den) == 1:
                out.append(f"{head}/{fmt(den[0])}")
            else:
                for d in itertools.permutations(den):
                    out.append(f"{head}/({sep.join(fmt(f) for f in d)})")
                    out.append(head + "".join("/" + fmt(f) for f in d))
            if den:                                        # negative powers on one line
                for d in itertools.permutations(den):
                    out.append(sep.join([fmt(f) for f in n] + [fmt(f, -1) for f in d]))
    return _unique(out)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def unit_name(num: list, den: list, symbols: dict) -> str:
    def one(f):
        sym, exp = f
        name = sym if sym.isdigit() else symbols[sym]["name"]
        length = not sym.isdigit() and symbols[sym]["dimension"] == {"L": 1}
        if exp == 1:
            return name
        if exp == 2:
            return f"square {name}" if length else f"{name} squared"
        if exp == 3:
            return f"cubic {name}" if length else f"{name} cubed"
        return f"{name} to the power {exp}"
    head = " ".join(one(f) for f in num)
    if not den:
        return head or "one"
    tail = " ".join(one(f) for f in den)
    return f"{head} per {tail}" if head else f"per {tail}"


def unit_record(num: list, den: list, symbols: dict, pi: Fraction, order: list) -> dict:
    dimension, factor, angle = {}, Fraction(1), 0
    for sign, group in ((1, num), (-1, den)):
        for sym, exp in group:
            if sym.isdigit():
                factor *= _power(Fraction(int(sym)), sign * exp)
                continue
            s = symbols[sym]
            dimension = dim_add(dimension, s["dimension"], sign * exp)
            factor *= _power(factor_of(s["factor"], pi), sign * exp)
            angle += sign * exp * s.get("angle", 0)
    if Fraction(angle).denominator != 1:
        raise ValueError(f"unit {render(num, den)!r} has a fractional angle exponent")
    record = {"dimension": _json_dim(dim_sorted(dimension, order)), "factor": str(factor), "angle": int(angle),
              "name": unit_name(num, den, symbols)}
    if not den and len(num) == 1 and num[0][1] == 1:
        for key in ("offset", "reference"):            # degC offset; gauge or absolute pressure mark
            if key in symbols[num[0][0]]:
                record[key] = symbols[num[0][0]][key]
    return record


# ---- splitting run-together text into symbols ------------------------------------------------------

def splits(token: str, symbols: list[str]) -> list[list[tuple[str, int]]]:
    """All ways to read a run-together token as a product of symbols with optional ^n."""
    found = []

    def walk(i, acc):
        if i == len(token):
            found.append(list(acc))
            return
        for sym in symbols:
            if token.startswith(sym, i):
                j = i + len(sym)
                m = re.match(r"\^(-?[0-9]+)", token[j:])
                exp = int(m.group(1)) if m else 1
                walk(j + (m.end() if m else 0), acc + [(sym, exp)])
    walk(0, [])
    return found


def render_signed(factors: list[tuple[str, int]]) -> str:
    """Canonical text of a product with signed exponents."""
    num = [(s, e) for s, e in factors if e > 0]
    den = [(s, -e) for s, e in factors if e < 0]
    return render(num, den)


def name_signed(factors: list[tuple[str, int]], symbols: dict) -> str:
    num = [(s, e) for s, e in factors if e > 0]
    den = [(s, -e) for s, e in factors if e < 0]
    return unit_name(num, den, symbols)


# ---- the generator --------------------------------------------------------------------------------

def build(src: dict) -> dict:
    """Generate the frozen tables from the parsed registry source."""
    symbols = src["symbols"]
    order = src["dimension_bases"]
    pi = Fraction(src["constants"]["pi_40"])
    quantities = src["quantities"]
    codes = src["diagnostics"]

    # Canonical units: every quantity unit and menu entry, and every closed-list symbol, so that a
    # symbol no menu uses ("5 mg") is still read and refused by dimension, not reported unknown.
    canon = sorted({e["unit"] for e in quantities.values()} | {u for e in quantities.values() for u in e["menu"]}
                   | set(symbols))
    parsed = {u: parse_canonical(u, symbols) for u in canon}
    units = {u: unit_record(*parsed[u], symbols, pi, order) for u in canon}

    spellings: dict[str, str] = {}
    for u in canon:
        if u == "1":
            continue                                       # dimensionless values are bare numbers
        for s in spellings_of(*parsed[u]):
            if spellings.setdefault(s, u) != u:
                raise ValueError(f"spelling {s!r} would mean both {spellings[s]!r} and {u!r}")
    _check_quantities(src, units, spellings, pi)
    _check_names(src, units)

    refused: dict[str, dict] = {}

    def refuse(spelling: str, entry: dict) -> None:
        if spelling not in spellings and spelling not in refused:
            refused[spelling] = entry

    refuse("1", {"code": "E-UNIT-NOT-ACCEPTED", "reading": "the number one: a dimensionless value is a bare number",
                 "dimension": {}, "factor": "1", "angle": 0})
    for sym, e in sorted(src["foreign_units"].items()):
        entry = {"code": "E-UNIT-NOT-ACCEPTED", "reading": e["reading"],
                 "dimension": dim_sorted(e["dimension"], order), "factor": e["factor"], "angle": e.get("angle", 0)}
        if "offset" in e:
            entry["offset"] = e["offset"]
        refuse(sym, entry)
    known = dict(symbols)                                  # accepted symbols and SI-prefixed refusals
    for base in sorted(src["prefixable"]):
        b = symbols[base]
        for p, (pname, pfactor) in sorted(src["prefixes"].items()):
            spelling = p + base
            if spelling in symbols:
                continue
            entry = {"code": "E-UNIT-NOT-ACCEPTED", "reading": pname + b["name"],
                     "dimension": dim_sorted(b["dimension"], order),
                     "factor": str(Fraction(pfactor) * factor_of(b["factor"], pi)), "angle": b.get("angle", 0)}
            refuse(spelling, entry)
            known.setdefault(spelling, {"name": entry["reading"], "dimension": entry["dimension"],
                                        "factor": entry["factor"], "angle": entry["angle"]})
    for s, u in sorted(spellings.items()):                 # degC inside a compound: fix writes K
        if s != "K" and LONE_K.search(s):
            refuse(LONE_K.sub("degC", s), {"code": "E-DEGC-NOT-ABSOLUTE", "fix": u,
                                           "reading": f"{u} written with degC in place of K"})
    for s, u in sorted(spellings.items()):                 # m2 for m^2: fix writes ^
        if "^" in s and "^(" not in s:
            refuse(s.replace("^", ""), {"code": "E-UNIT-NOT-ACCEPTED", "fix": u,
                                        "reading": f"{u} written without ^"})
    for text in sorted(_ambiguous_forms(parsed)):
        refuse(text, _ambiguity(text, symbols, spellings))
    for text in sorted(src["run_together"]):
        refuse(text, _ambiguity(text, symbols, spellings))
    for text, e in sorted(refused.items()):               # W/m degC, J/kgdegC: ambiguous, with the K readings
        if e["code"] == "E-UNIT-AMBIGUOUS" and KELVIN_END.search(text):
            variant = KELVIN_END.sub("degC", text)
            refuse(variant, _degc_ambiguity(variant, symbols, spellings))
    for u in canon:                                        # MW/(m K) beside mW/(m K): case look-alikes
        for text, entry in _case_lookalikes(*parsed[u], known, pi, order):
            refuse(text, entry)
    inputs = sorted({u for e in quantities.values() if {"document", "material"} & set(e["places"]) for u in e["menu"]})
    for u in inputs:                                       # MW/m^3, mW/(m^2 K), V/cm: one factor re-prefixed
        for text, entry in _prefix_variants(*parsed[u], known, src["prefixes"], src["prefixable"], pi, order):
            refuse(text, entry)
    for s, e in refused.items():
        if e["code"] == "E-UNIT-AMBIGUOUS" and not e["readings"]:
            raise ValueError(f"ambiguous spelling {s!r} has no reading")
        if e["code"] not in CODES or e["code"] not in codes:
            raise ValueError(f"refused spelling {s!r} has code {e['code']!r}")

    return {"format": FORMAT, "note": NOTE, "units": units, "spellings": spellings, "refused": refused,
            "names": _names(src), "name_overrides": _name_overrides(src), "display_groups": _display_groups(src)}


def _ambiguous_forms(parsed: dict) -> set[str]:
    """Run-together groups (W/mK, Ohmm) and unparenthesised a/b c forms (W/m K)."""
    out = set()
    for num, den in parsed.values():
        if any(s.isdigit() for s, _ in num + den):
            continue
        den_text = render([], den)[2:] if den else ""
        if len(num) >= 2:
            for n in itertools.permutations(num):
                glued = "".join(fmt(f) for f in n)
                out.add(glued + (f"/{den_text}" if den else ""))
        if len(den) >= 2:
            head = render(num, [])
            for d in itertools.permutations(den):
                glued = "".join(fmt(f) for f in d)
                out.add(f"{head}/{glued}")
                out.add(f"{head}/({glued})")
                for sep in SEPARATORS:
                    out.add(f"{head}/{sep.join(fmt(f) for f in d)}")
    return out


def _ambiguity(text: str, symbols: dict, spellings: dict) -> dict:
    """Readings of an ambiguous spelling: each symbol split, a/b c groupings and case twins."""
    names = sorted(symbols, key=lambda s: (-len(s), s))
    readings = {}
    head, slash, tail = text.partition("/")
    groups = []
    if slash and not tail.startswith("("):
        for sep in SEPARATORS:
            if sep in tail:
                first, rest = tail.split(sep, 1)
                groups.append((head, first, rest.split(sep)))   # W/m K: (W K)/m
        if groups:
            h, first, rest = groups[0]
            whole = f"{h}/({' '.join([first] + rest)})"
            mixed = f"{' '.join([h] + rest)}/{first}"
            for t in (whole, mixed):
                readings[t] = None
    if not readings:
        inner = tail[1:-1] if tail.startswith("(") else tail
        heads = splits(head, names) if head != "1" else [[]]
        tails = splits(inner, names) if slash else [[]]
        for h in heads:
            for t in tails:
                factors = h + [(s, -e) for s, e in t]
                readings[render_signed(factors)] = factors
    for s, u in spellings.items():                          # Nm and nm differ by case only
        if s.casefold() == text.casefold() and s != text:
            readings[u] = None
    out = []
    for t, factors in readings.items():
        u = spellings.get(t)
        if u is not None:
            out.append({"unit": u, "name": _canonical_name(u, symbols)})
        elif factors is not None:
            out.append({"unit": t, "name": name_signed(factors, symbols)})
        else:
            out.append({"unit": t, "name": _text_name(t, symbols)})
    out.sort(key=lambda r: (r["unit"] not in spellings.values(), r["unit"]))
    return {"code": "E-UNIT-AMBIGUOUS", "readings": out}


def _degc_ambiguity(text: str, symbols: dict, spellings: dict) -> dict:
    """Readings of an ambiguous spelling with degC for K, given as the K units they would be."""
    readings, seen = [], set()
    for r in _ambiguity(text, symbols, spellings)["readings"]:
        if not DEGC.search(r["unit"]):
            continue                                       # keep the readings where degC stood for K
        k_text = DEGC.sub("K", r["unit"])
        unit = spellings.get(k_text, k_text)
        if unit in seen:
            continue
        seen.add(unit)
        readings.append({"unit": unit, "name": _text_name(unit, symbols)})
    return {"code": "E-UNIT-AMBIGUOUS", "readings": readings, "note": DEGC_NOTE}


def _case_lookalikes(num: list, den: list, known: dict, pi: Fraction, order: list) -> list[tuple[str, dict]]:
    """A compound with one factor's milli/mega prefix in the other case (MW/(m K) for mW/(m K))."""
    factors = num + den
    if len(factors) < 2 or any(sym.isdigit() for sym, _ in factors):
        return []
    out = []
    for i, (sym, exp) in enumerate(factors):
        if len(sym) < 2 or sym[0] not in "mM":
            continue
        other = sym[0].swapcase() + sym[1:]
        if other not in known:
            continue
        out.append(_substituted(num, den, i, other, known, pi, order))
    return out


def _substituted(num: list, den: list, i: int, other: str, known: dict, pi: Fraction,
                 order: list) -> tuple[str, dict]:
    """Text and refusal entry of a compound with factor ``i`` written as the symbol ``other``."""
    swapped = [(other, e) if j == i else (s, e) for j, (s, e) in enumerate(num + den)]
    n, d = swapped[:len(num)], swapped[len(num):]
    dimension, factor, angle = {}, Fraction(1), 0
    for sign, group in ((1, n), (-1, d)):
        for s, e in group:
            k = known[s]
            dimension = dim_add(dimension, k["dimension"], sign * e)
            factor *= factor_of(k["factor"], pi) ** (sign * e)
            angle += sign * e * k.get("angle", 0)
    return render(n, d), {"code": "E-UNIT-NOT-ACCEPTED", "reading": unit_name(n, d, known),
                          "dimension": dim_sorted(dimension, order), "factor": str(factor), "angle": angle}


def _prefix_variants(num: list, den: list, known: dict, prefixes: dict, prefixable: list, pi: Fraction,
                     order: list) -> list[tuple[str, dict]]:
    """An input-menu compound with one factor in another common prefix (MW/m^3 for W/m^3,
    mW/(m^2 K) for W/(m^2 K), V/cm for V/m), so that it is refused naming its reading."""
    factors = num + den
    if (not den and len(num) == 1 and num[0][1] == 1) or any(
            sym.isdigit() or not isinstance(e, int) for sym, e in factors):
        return []                                          # a bare symbol: its prefixes are refused above

    def split(sym: str) -> tuple[str, str]:                # (prefix, base) of a prefixed symbol
        for p in sorted(prefixes, key=lambda x: (-len(x), x)):
            if sym.startswith(p) and sym[len(p):] in prefixable:
                return p, sym[len(p):]
        return "", sym

    out = []
    for i, (sym, _) in enumerate(factors):
        base = split(sym)[1]
        if base in VARIANT_FIXED:
            continue
        allowed = VARIANT_PREFIXES + (("c",) if base == "m" else ())
        for p in allowed:
            other = p + base
            if other != sym and other in known and split(other) == (p, base):
                out.append(_substituted(num, den, i, other, known, pi, order))
    return out


def _canonical_name(u: str, symbols: dict) -> str:
    return unit_name(*parse_canonical(u, symbols), symbols)


def _text_name(t: str, symbols: dict) -> str:
    try:
        return _canonical_name(t, symbols)
    except ValueError:
        return t


def _qualified(src: dict) -> dict[str, tuple[str, str | None, str | None]]:
    """Every legal quantity name -> (base, kind of its front word, front word): base names, and at
    most one direction, role or statistic word in front, optionally with one component word behind."""
    words = src["qualifier_words"]
    names: dict[str, tuple[str, str | None, str | None]] = {}
    for base, e in sorted(src["quantities"].items()):
        q = e.get("qualifiers", {})
        for key, allowed in q.items():
            bad = set(allowed) - set(words[key])
            if bad:
                raise ValueError(f"{base}: qualifier words {sorted(bad)} are not in qualifier_words.{key}")
        fronts = [(None, "")] + [(key, w) for key in ("direction", "role", "statistic") for w in q.get(key, [])]
        backs = [""] + q.get("component", [])
        for key, front in fronts:
            for back in backs:
                name = "_".join(p for p in (front, base, back) if p)
                found = names.setdefault(name, (base, key, front or None))
                if found[0] != base:
                    raise ValueError(f"quantity name {name!r} comes from both {found[0]!r} and {base!r}")
    return names


def _names(src: dict) -> dict:
    """Every legal quantity name -> its registry base entry."""
    return {name: base for name, (base, _, _) in _qualified(src).items()}


def _name_overrides(src: dict) -> dict:
    """Places and rank of a name where they differ from its base: a name with an output-only word
    keeps only the output places, and ``name_rank`` sets the rank of a name (inward_heat_flux)."""
    quantities, output_words = src["quantities"], set(src["output_only_words"])
    found: dict[str, dict] = {}
    for name, (base, _, word) in sorted(_qualified(src).items()):
        e = quantities[base]
        places = [p for p in e["places"] if p in OUTPUT_PLACES] if word in output_words else e["places"]
        rank = e.get("name_rank", {}).get(name, e["rank"])
        own = {}
        if places != e["places"]:
            own["places"] = places
        if rank != e["rank"]:
            own["rank"] = rank
        if own:
            found[name] = own
    return found


def _display_groups(src: dict) -> dict:
    """Members of each display group: every legal name whose base has the group's dimension."""
    order, quantities, qualified = src["dimension_bases"], src["quantities"], _qualified(src)
    out = {}
    for group, g in sorted(src["display_groups"].items()):
        dim = dim_sorted(g["dimension"], order)
        members = sorted(n for n, (base, _, _) in qualified.items()
                         if dim_sorted(quantities[base]["dimension"], order) == dim)
        out[group] = {"quantities": members, "shape_numbers": bool(g.get("shape_numbers")), "menu": g["menu"]}
    return out


def _check_names(src: dict, units: dict) -> None:
    """Refuse name-keyed fields that name no name of their base, and malformed group or scope data."""
    qualified, quantities = _qualified(src), src["quantities"]
    words = src["qualifier_words"]
    output_words = set(src["output_only_words"])
    if not output_words <= {w for key in ("direction", "role", "statistic") for w in words[key]}:
        raise ValueError("output_only_words must be qualifier words")
    for base, e in quantities.items():                     # unnormalized_electric_field and the like are outputs
        if any(base.startswith(w + "_") for w in output_words) and set(e["places"]) - set(OUTPUT_PLACES):
            raise ValueError(f"{base}: a base that starts with an output-only word is an output")
    for base, e in quantities.items():
        own = {n for n, (b, _, _) in qualified.items() if b == base}
        for field in ("sign", "statistic_definitions", "name_rank"):
            for name, value in e.get(field, {}).items():
                if name not in own:
                    raise ValueError(f"{base}: {field} names {name!r}, which is not a name of this base")
                if field == "statistic_definitions" and qualified[name][1] != "statistic":
                    raise ValueError(f"{base}: statistic_definitions names {name!r}, which has no statistic word")
                if field == "name_rank" and not set(value) <= RANKS:
                    raise ValueError(f"{base}: name_rank of {name!r} is outside the closed rank list")
                if field != "name_rank" and not (value.get("en") and value.get("ko")):
                    raise ValueError(f"{base}: {field} of {name!r} needs en and ko")
        scope = e.get("scope")
        if scope is not None and (scope.get("quantity") not in quantities or not scope.get("model")
                                  or e.get("hint") is not False):
            raise ValueError(f"{base}: a scope names a registry quantity and its model, and a model parameter "
                             "has hint false")
    order = src["dimension_bases"]
    for group, g in src["display_groups"].items():
        dim = dim_sorted(g["dimension"], order)
        if not g["menu"] or any(u not in units or units[u]["dimension"] != dim for u in g["menu"]):
            raise ValueError(f"display group {group!r}: menu units need the group's dimension")
        if not (g["description"].get("en") and g["description"].get("ko")):
            raise ValueError(f"display group {group!r} needs an en and a ko description")


def _check_quantities(src: dict, units: dict, spellings: dict, pi: Fraction) -> None:
    """Refuse a registry whose entries break the closed vocabularies or the menu rules."""
    order = src["dimension_bases"]
    by_unit: dict[str, list[str]] = {}
    for s, u in spellings.items():
        by_unit.setdefault(u, []).append(s)
    for name, e in src["quantities"].items():
        extra = set(e) - QUANTITY_FIELDS
        if extra:
            raise ValueError(f"{name}: unknown fields {sorted(extra)}")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError(f"{name}: names are lower_snake_case")
        if e["kind"] not in KINDS or not set(e["rank"]) <= RANKS or not set(e["places"]) <= PLACES:
            raise ValueError(f"{name}: kind, rank or places outside the closed lists")
        if e["unit"] not in e["menu"]:
            raise ValueError(f"{name}: canonical unit {e['unit']!r} is not on its menu")
        if not isinstance(e.get("hint", False), bool) or e.get("family", "spectral") not in FAMILIES:
            raise ValueError(f"{name}: hint is true or false, family is one of {sorted(FAMILIES)}")
        dim = dim_sorted(e["dimension"], order)
        if set(e["dimension"]) - set(order):
            raise ValueError(f"{name}: unknown dimension base")
        for u in e["menu"]:
            if units[u]["dimension"] != dim:
                raise ValueError(f"{name}: menu unit {u!r} has dimension {units[u]['dimension']}, not {dim}")
        if e["kind"] in ("count", "fraction") and dim:
            raise ValueError(f"{name}: counts and fractions are dimensionless")
        if "1" in e["menu"] and dim:
            raise ValueError(f"{name}: a bare number is only for a dimensionless quantity")
        if e["kind"] == "count" and e["menu"] != ["1"]:
            raise ValueError(f"{name}: a count is a bare integer")
        folded = {}
        for u in e["menu"]:
            for s in by_unit.get(u, []):
                twin = folded.setdefault(s.casefold(), s)
                if twin != s:
                    raise ValueError(f"{name}: menu holds {twin!r} and {s!r}, equal under case folding")
        for key in ("domain", "band"):
            spec = e.get(key)
            if spec is None:
                continue
            allowed = DOMAIN_KEYS if key == "domain" else BAND_KEYS
            if set(spec) - allowed:
                raise ValueError(f"{name}: unknown {key} keys {sorted(set(spec) - allowed)}")
            values = [v for k, v in spec.items() if k != "when_unit"]
            for v in [x for v in values for x in (v if isinstance(v, list) else [v])]:
                if v is not None:
                    bound(v, e, units, spellings, pi)
            if key == "band" and spec.get("when_unit") is not None and spec["when_unit"] not in e["menu"]:
                raise ValueError(f"{name}: band.when_unit is not on the menu")
        for unit, code in e.get("slot_refusals", {}).items():
            if unit not in spellings or code not in src["diagnostics"] or unit in e["menu"]:
                raise ValueError(f"{name}: bad slot refusal {unit!r}")
        if "warn_inside" in e:
            w = e["warn_inside"]
            if w["code"] not in src["diagnostics"] or src["diagnostics"][w["code"]]["severity"] != "warning":
                raise ValueError(f"{name}: warn_inside needs a warning code")
            for v in w["range"]:
                bound(v, e, units, spellings, pi)


def bound(text: str, entry: dict, units: dict, spellings: dict, pi: Fraction) -> Fraction:
    """Exact value of a registry bound in the entry's canonical unit ("0", "35 deg", "90 kPa")."""
    number, _, unit = text.partition(" ")
    value = Fraction(number)
    if not unit:
        return value
    if unit not in spellings or spellings[unit] not in entry["menu"]:
        raise ValueError(f"bound {text!r} uses a unit off the menu")
    u, c = units[spellings[unit]], units[entry["unit"]]
    si = value * Fraction(u["factor"]) + Fraction(u.get("offset", "0"))
    return (si - Fraction(c.get("offset", "0"))) / Fraction(c["factor"])


def dumps(tables: dict) -> str:
    """Deterministic text: sorted keys, one entry per line, ASCII escapes, LF line ends."""
    lines = ["{"]
    keys = list(tables)
    for i, key in enumerate(keys):
        value = tables[key]
        comma = "," if i < len(keys) - 1 else ""
        if isinstance(value, dict):
            lines.append(f" {json.dumps(key)}: {{")
            items = sorted(value.items())
            for j, (k, v) in enumerate(items):
                tail = "," if j < len(items) - 1 else ""
                lines.append(f"  {json.dumps(k)}: {json.dumps(v, sort_keys=True)}{tail}")
            lines.append(f" }}{comma}")
        else:
            lines.append(f" {json.dumps(key)}: {json.dumps(value, sort_keys=True)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def generate(source_text: str) -> str:
    """Text of unit_tables.json for the registry source text."""
    return dumps(build(json.loads(source_text)))


def main(argv: list[str] | None = None) -> int:
    """Check or regenerate unit_tables.json from quantities.json; the tables are never read first."""
    parser = argparse.ArgumentParser(prog="python -m physmat._unit_tables",
                                     description="Check or regenerate physmat/unit_tables.json.")
    parser.add_argument("--check", action="store_true", help="exit 1 if unit_tables.json is not the generator output")
    parser.add_argument("--write", action="store_true", help="regenerate unit_tables.json next to this module")
    args = parser.parse_args(argv)
    package = resources.files(__package__ or "physmat")
    text = generate(package.joinpath(SOURCE_FILE).read_text(encoding="utf-8")).encode("utf-8")
    status = 0
    if args.write:
        Path(__file__).with_name(TABLES_FILE).write_bytes(text)
    if args.check and package.joinpath(TABLES_FILE).read_bytes() != text:
        print("unit_tables.json differs from the generator output; run: python -m physmat.units --write")
        status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
