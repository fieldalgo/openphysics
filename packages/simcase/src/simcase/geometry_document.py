# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Geometry document version 1: parse, validate and quantize (stage 1).

This module reads the ``geometry`` block defined in
``docs/packages/simcase/geometry_document.md``. It checks names, ids, kinds and
reserved keywords, evaluates parameter expressions in exact rational arithmetic,
and moves every defining value onto the fixed 1 pm integer grid, rounding at most
once per value and reporting each rounding.

Stage 1 does not resolve booleans itself: the exact 2D engine (``simcase.geometry_engine``)
does. ``to_flat`` compiles a 2D component (or a box-only 3D component) to the flat
``geometry`` block of format 0.3, which the reader keeps for the kinds that read flat blocks
(``Document.geometry_flat``); ``from_flat`` writes a flat block as version 1. ``layer_stack``
compiles a ``layers`` feature to the levels and material table that ``meshine.extrude`` takes.

The block is read in format 0.3 (``"openphysics": "0.3"``). Each component declares its own
``length_unit`` (and ``depth`` when it is ``2d``); its bare shape numbers and the literals of
its expressions are read in that unit. Geometry parameters stay outside every component and
carry their unit (``"value": "0.5 um"``); their values are exact picometres (length) or exact
rationals (ratio). Element sizes are quantity strings (``"element_size": "0.25 um"``), never
expressions. Refusals carry a diagnostic code and a JSON path (``GeometryError.code``,
``.path``).

Only the standard library is imported here, apart from ``physmat.units``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from decimal import Decimal
from typing import Any

from physmat import units as qty
from physmat.units import Diagnostic

from .diagnostics import CodedError

#: Grid points per metre: the grid step is 1 pm.
PM_PER_M = 10 ** 12
#: Coordinates must satisfy |k| < GRID_LIMIT pm.
GRID_LIMIT = 2 ** 63
#: The relative snapping tolerance of meshine (``meshine.geometry.SNAP_EPS``).
#: A feature smaller than this fraction of its component's bounding-box diagonal is
#: refused at the hand-off instead of disappearing inside the mesher.
MESHER_RELATIVE_TOLERANCE = 3e-8

ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
PART_RE = re.compile(r"^[A-Za-z0-9_-]+$")
PARAM_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVED_IDS = frozenset(
    ["background", "domain", "exterior", "outer", "void", "axis", "left", "right", "bottom", "top"]
    + [f"{a}{b}" for a in "xyz" for b in "01"]
    + [f"{a}{b}" for a in "xyz" for b in ("min", "max")])

_COMMON = {"id", "name", "region", "type", "material", "element_size"}
_FIELDS_2D = {
    "rect": ({"x", "y", "w", "h"}, set()),
    "circle": ({"cx", "cy", "r"}, set()),
    "polygon": ({"points"}, {"edges"}),
    "trapezoid": ({"cx", "y", "w", "h"}, {"w_top"}),
    "segment": ({"points"}, set()),
    "path": ({"start", "segments"}, set()),
}
_FIELDS_3D = {
    "box": ({"xmin", "xmax", "ymin", "ymax", "zmin", "zmax"}, set()),
    "cylinder": ({"cx", "cy", "r", "zmin", "zmax"}, {"axis"}),
    "sphere": ({"cx", "cy", "cz", "r"}, set()),
    "extrude": ({"profile", "zmin", "zmax"}, {"axis"}),
    "layers": ({"z0", "layers"}, set()),
}
_RESERVED_TYPES = {"ellipse"}
_RESERVED_FEATURE_KEYS = {"rotation", "offset", "surface"}
_SELECTOR_KEYS = {"feature", "provenance", "material", "between", "of", "any"}
_RESERVED_SELECTOR_KEYS = {"inside", "kind", "all", "except", "covered_by"}
_DOMAIN_KEYS = {"2d": ("xmin", "xmax", "ymin", "ymax"),
                "axisymmetric": ("xmin", "xmax", "ymin", "ymax"),
                "3d": ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")}

_MISSING = object()


class GeometryError(CodedError):
    """A geometry document that version 1 does not accept. The message names the path.

    ``GeometryError(message, *, path=None, code="E-CONTRACT", diagnostics=())``: a format 0.3
    refusal carries its diagnostic code and path; ``str()`` is the message."""


@dataclass(frozen=True)
class Rounding:
    """One value moved onto the 1 pm grid: where, what was written, and by how much."""

    path: str
    written: str
    displacement_pm: Fraction


@dataclass
class Feature:
    id: str
    name: str
    region: str
    type: str
    material: Any                     # a name, None for void, or _MISSING
    mesh_size: int | None             # pm
    data: dict                        # quantized fields (pm integers, point lists, layers)


@dataclass
class Component:
    name: str
    dimension: str
    domain: dict                      # pm integers
    background: dict                  # {"material": ...} (may be absent), "mesh_size": pm
    features: list[Feature]
    finalize: str
    selections: dict
    boundary_tags: list
    #: the unit its bare numbers are written in (its ``length_unit`` symbol), and grid points
    #: per that unit, exactly
    length_unit: Any = None
    pm_per_unit: Fraction | None = None
    #: format 0.3: the ``depth`` of a 2d component in metres (None: per metre of depth), as written
    depth: float | None = None
    depth_written: Any = None

    def to_unit(self, k) -> float:
        """An integer pm count in this component's length unit, rounded once to a double."""
        return float(Fraction(k) / self.pm_per_unit)

    @property
    def region_names(self) -> list[str]:
        names = []
        for f in self.features:
            if f.type not in ("segment", "layers") and f.region not in names:
                names.append(f.region)
        return names


@dataclass
class GeometryModel:
    """A parsed version 1 geometry block, with all lengths in integer pm.

    Each component has its own length unit (``Component.length_unit``, ``.pm_per_unit``);
    parameter values are exact pm (length) or exact rationals (ratio). The model keeps the pm
    count of every shape number by JSON path (``pm_values``) and the rounding diagnostics
    (``diagnostics``)."""

    parameters: dict                  # name -> (value: exact pm for a length, kind)
    components: dict
    roundings: list[Rounding] = field(default_factory=list)
    format: str = "0.3"
    pm_values: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)

    def to_um(self, k: int) -> float:
        """An integer pm count in micrometres, rounded once (the meshine hand-off)."""
        return float(Fraction(k, 10 ** 6))


# --------------------------------------------------------------------------- units

def pm_per_length_unit(unit, path: str) -> tuple[str, Fraction]:
    """``(symbol, grid points per unit)`` of a format 0.3 ``length_unit``; raises ``GeometryError``."""
    if isinstance(unit, dict):
        raise GeometryError(f"{path}: a length_unit is one of {' '.join(qty.LENGTH_UNITS)}; a numeric unit "
                            "such as {\"in_m\": ...} is not read", path=path, code="E-VALUE-FORM")
    if not isinstance(unit, str):
        raise GeometryError(f"{path}: a length_unit is one of {' '.join(qty.LENGTH_UNITS)}", path=path,
                            code="E-VALUE-FORM")
    grid = qty.length_to_pm(1, unit, path=path)
    if grid.error is not None:
        raise GeometryError(f"{path}: {grid.error.message}", path=path, code=grid.error.code)
    return grid.unit, Fraction(grid.picometres)


def _number(value, path: str) -> Fraction:
    """A JSON number, read as the shortest decimal that round-trips its double (a ``Decimal``
    of the exact reader, exactly)."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise GeometryError(f"{path}: {value} is not finite", path=path, code="E-JSON")
        return Fraction(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GeometryError(f"{path}: expected a number, got {value!r}", path=path, code="E-VALUE-FORM")
    if isinstance(value, int):
        return Fraction(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise GeometryError(f"{path}: {value!r} is not finite", path=path, code="E-JSON")
    return Fraction(repr(value))


def is_unit_symbol(name: str) -> bool:
    """True for a name that is an accepted or known-refused unit spelling (``nm``, ``m``, ``bar``)."""
    return qty.is_quantity_text(f"1 {name}")


# --------------------------------------------------------------------------- expressions

_TOKEN = re.compile(r"\s*(?:(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<op>[-+*/()]))")

#: A decimal literal in an expression has no kind of its own: in + and - it takes the
#: other operand's kind, and in * and / it is a ratio.
_LITERAL = "literal"


def _tokens(text: str, path: str):
    pos, out = 0, []
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise GeometryError(f"{path}: cannot read {text[pos:].strip()!r} in expression {text!r}; "
                                "allowed are decimal numbers, parameter names, + - * / and parentheses")
        pos = m.end()
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
    return out


class _Evaluator:
    """Evaluates parameter expressions exactly.

    Length values are exact picometres. A length parameter's value is a quantity string (on the
    pm grid) or an expression of other parameters; a literal that is added to a length is read
    in the component's length unit (``ppu``, grid points per unit), and has no unit at geometry
    level, outside every component."""

    def __init__(self, parameters: dict):
        self.raw = parameters
        self.values: dict[str, tuple[Fraction, str]] = {}
        self.active: list[str] = []
        self.ppu = None
        self.diagnostics: list = []

    def parameter(self, name: str, path: str) -> tuple[Fraction, str]:
        if name in self.values:
            return self.values[name]
        if name not in self.raw:
            if is_unit_symbol(name):
                raise _unit_in_expression(path, name)
            raise GeometryError(f"{path}: unknown parameter {name!r}", path=path, code="E-KEY-UNKNOWN")
        if name in self.active:
            cycle = " -> ".join(self.active[self.active.index(name):] + [name])
            raise GeometryError(f"geometry.parameters.{name}: cycle {cycle}", path=f"geometry.parameters.{name}")
        self.active.append(name)
        spec = self.raw[name]
        kind = spec.get("kind", "length")
        saved, self.ppu = self.ppu, None                 # parameters are read outside every component
        try:
            value, vkind = self.parameter_value(spec["value"], f"geometry.parameters.{name}.value", kind)
            if vkind not in (_LITERAL, kind):
                raise GeometryError(f"geometry.parameters.{name}: value is a {vkind}, the parameter is a {kind}",
                                    path=f"geometry.parameters.{name}.value", code="E-EXPRESSION-KIND")
            lo_hi = spec.get("range")
            if lo_hi is not None:
                lo, hi = (self.parameter_value(v, f"geometry.parameters.{name}.range[{i}]", kind)[0]
                          for i, v in enumerate(lo_hi))
                if not lo <= value <= hi:
                    shown = (lambda x: float(x) / 10 ** 12) if kind == "length" else float
                    unit = " m" if kind == "length" else ""
                    raise GeometryError(f"geometry.parameters.{name}: value {shown(value)}{unit} is outside its "
                                        f"range [{shown(lo)}, {shown(hi)}]{unit}",
                                        path=f"geometry.parameters.{name}.value", code="E-DOMAIN")
        finally:
            self.ppu = saved
        self.active.pop()
        self.values[name] = (value, kind)
        return self.values[name]

    def parameter_value(self, raw, path: str, kind: str):
        """A parameter's value or range bound: a length takes a quantity string."""
        if isinstance(raw, str) and qty.is_quantity_text(raw):
            if kind != "length":
                raise GeometryError(f"{path}: a {kind} parameter is a bare number or an expression, not "
                                    f"{raw!r}", path=path, code="E-VALUE-FORM")
            grid = qty.length_to_pm(raw, path=path)
            if grid.error is not None:
                raise GeometryError(f"{path}: {grid.error.message}", path=path, code=grid.error.code)
            self.diagnostics.extend(grid.diagnostics)
            return Fraction(grid.picometres), "length"
        value, vkind = self.value(raw, path)
        if kind == "length" and vkind == _LITERAL:
            raise GeometryError(f"{path}: a length parameter carries its unit, such as \"0.5 um\"; "
                                f"{_shown(raw)} has none", path=path, code="E-UNIT-MISSING")
        return value, vkind

    def value(self, raw, path: str) -> tuple[Fraction, str]:
        if isinstance(raw, str):
            if qty.is_quantity_text(raw):
                raise GeometryError(f"{path}: {raw!r}: a shape number is bare, read in its component's "
                                    "length_unit; give a tagged length to a parameter and use its name",
                                    path=path, code="E-VALUE-FORM")
            return self.expression(raw, path)
        return _number(raw, path), _LITERAL

    def expression(self, text: str, path: str) -> tuple[Fraction, str]:
        toks = _tokens(text, path)
        if not toks:
            raise GeometryError(f"{path}: empty expression")
        for kind, tok in toks:
            if kind == "name" and tok not in self.raw and is_unit_symbol(tok):
                raise _unit_in_expression(path, tok)
        self._toks, self._i, self._path, self._text = toks, 0, path, text
        result = self._sum()
        if self._i != len(toks):
            raise GeometryError(f"{path}: unexpected {toks[self._i][1]!r} in expression {text!r}")
        return result

    def _peek(self):
        return self._toks[self._i] if self._i < len(self._toks) else (None, None)

    def _sum(self):
        left = self._product()
        while self._peek()[1] in ("+", "-"):
            op = self._toks[self._i][1]
            self._i += 1
            right = self._product()
            kind = _add_kind(left[1], right[1], self._path, op)
            if kind == "length" and _LITERAL in (left[1], right[1]):
                left, right = (self._scaled(x) for x in (left, right))
            left = (left[0] + right[0] if op == "+" else left[0] - right[0], kind)
        return left

    def _scaled(self, operand):
        """A literal added to a length, read in the component's unit."""
        value, kind = operand
        if kind != _LITERAL:
            return operand
        if self.ppu is None:
            raise GeometryError(f"{self._path}: a bare number added to a length has no unit outside a component; "
                                "write it as a parameter with its unit", path=self._path, code="E-UNIT-MISSING")
        return value * self.ppu, "length"

    def _product(self):
        left = self._unary()
        while self._peek()[1] in ("*", "/"):
            op = self._toks[self._i][1]
            self._i += 1
            right = self._unary()
            if op == "*":
                left = (left[0] * right[0], _mul_kind(left[1], right[1], self._path))
            else:
                if right[0] == 0:
                    raise GeometryError(f"{self._path}: division by zero in {self._text!r}")
                left = (left[0] / right[0], _div_kind(left[1], right[1], self._path))
        return left

    def _unary(self):
        if self._peek()[1] == "-":
            self._i += 1
            value, kind = self._unary()
            return -value, kind
        if self._peek()[1] == "+":
            self._i += 1
            return self._unary()
        return self._atom()

    def _atom(self):
        kind, tok = self._peek()
        if kind is None:
            raise GeometryError(f"{self._path}: expression {self._text!r} ends early")
        self._i += 1
        if kind == "num":
            return Fraction(tok), _LITERAL
        if kind == "name":
            saved = (self._toks, self._i, self._path, self._text)
            value = self.parameter(tok, self._path)
            self._toks, self._i, self._path, self._text = saved
            return value
        if tok == "(":
            value = self._sum()
            if self._peek()[1] != ")":
                raise GeometryError(f"{self._path}: missing ')' in {self._text!r}")
            self._i += 1
            return value
        raise GeometryError(f"{self._path}: unexpected {tok!r} in expression {self._text!r}")


def _shown(raw) -> str:
    return repr(raw) if isinstance(raw, str) else str(raw)


def _unit_in_expression(path: str, name: str) -> GeometryError:
    return GeometryError(f"{path}: {name!r} is a unit; an expression holds bare numbers in the component's "
                         "length_unit and parameter names: declare a parameter with the tagged value",
                         path=path, code="E-EXPRESSION-KIND")


def _add_kind(a: str, b: str, path: str, op: str) -> str:
    if a == _LITERAL:
        return b
    if b == _LITERAL or a == b:
        return a
    raise GeometryError(f"{path}: {a} {op} {b} mixes kinds")


def _mul_kind(a: str, b: str, path: str) -> str:
    kinds = {a, b} - {_LITERAL, "ratio"}
    if a == b == "length":
        raise GeometryError(f"{path}: length * length is not a length")
    return "length" if kinds else ("ratio" if "ratio" in (a, b) else _LITERAL)


def _div_kind(a: str, b: str, path: str) -> str:
    if b == "length":
        if a == "length":
            return "ratio"
        raise GeometryError(f"{path}: dividing by a length gives an inverse length")
    if a == "length":
        return "length"
    return "ratio" if "ratio" in (a, b) else _LITERAL


# --------------------------------------------------------------------------- parsing

class _Reader:
    """Reads lengths of one format 0.3 document; ``evaluator`` evaluates its parameters (the
    design velocity pass, ``simcase.geometry_velocity``, passes one that also carries
    derivatives). ``ppu`` is set per component as each is read."""

    def __init__(self, doc: dict, evaluator=None):
        g = doc.get("geometry")
        if not isinstance(g, dict):
            raise GeometryError("geometry: expected an object", path="geometry", code="E-VALUE-FORM")
        if g.get("version") != 1:
            raise GeometryError("geometry.version: this reader takes version 1; a block without "
                                "version is the flat form (see from_flat)", path="geometry.version")
        self.pm_values: dict[str, int] = {}
        self.diagnostics: list = []
        for key in ("length_unit", "depth"):
            if key in g:
                raise GeometryError(f"geometry.{key}: a version 1 block gives {key} on each component "
                                    f"(geometry.components.<c>.{key})", path=f"geometry.{key}",
                                    code="E-KEY-UNKNOWN")
        _keys(g, {"version", "components"}, {"parameters"}, "geometry")
        self.ppu, self.unit = None, None
        params = g.get("parameters", {})
        if not isinstance(params, dict):
            raise GeometryError("geometry.parameters: expected an object", path="geometry.parameters",
                                code="E-VALUE-FORM")
        for name, spec in params.items():
            path = f"geometry.parameters.{name}"
            if not PARAM_RE.match(name):
                raise GeometryError(f"{path}: a parameter name matches [A-Za-z_][A-Za-z0-9_]*", path=path,
                                    code="E-ID-CLASH")
            if is_unit_symbol(name):
                raise GeometryError(f"{path}: {name!r} is a unit symbol; a parameter name that reads as a unit "
                                    "would make expressions ambiguous, so rename it", path=path, code="E-ID-CLASH")
            if not isinstance(spec, dict):
                raise GeometryError(f"{path}: expected {{\"value\": ..., \"kind\": ..., \"range\": ...}}")
            _keys(spec, {"value"}, {"kind", "range"}, path)
            kind = spec.get("kind", "length")
            if kind in ("angle", "count"):
                raise GeometryError(f"{path}.kind: {kind!r} is reserved for a later version")
            if kind not in ("length", "ratio"):
                raise GeometryError(f"{path}.kind: expected 'length' or 'ratio'")
            if "range" in spec and (not isinstance(spec["range"], list) or len(spec["range"]) != 2):
                raise GeometryError(f"{path}.range: expected [lo, hi]")
        self.ev = (evaluator or _Evaluator)(params)
        for name in params:
            self.ev.parameter(name, f"geometry.parameters.{name}")
        self.roundings: list[Rounding] = []

    def set_component(self, unit, ppu) -> None:
        """Read the next component's numbers in ``unit`` (``ppu`` grid points each)."""
        self.unit, self.ppu = unit, ppu
        self.ev.ppu = ppu

    def exact_pm(self, value, kind: str, path: str):
        """The exact pm value of an evaluated length field."""
        if kind == "ratio":
            raise GeometryError(f"{path}: expected a length, the expression is a ratio", path=path,
                                code="E-EXPRESSION-KIND")
        if kind == "length":
            return value                       # parameters and their expressions are pm already
        return value * self.ppu

    def length(self, raw, path: str) -> int:
        """A length field as an integer pm count, rounded at most once with a report."""
        value, kind = self.ev.value(raw, path)
        exact = self.exact_pm(value, kind, path)
        return self.on_grid(exact, raw, path)

    def on_grid(self, exact, raw, path: str) -> int:
        k = round(exact)                       # Fraction rounds half to even
        if k != exact:
            self.roundings.append(Rounding(path, raw if isinstance(raw, str) else repr(raw), Fraction(k) - exact))
            self.diagnostics.append(_rounding(path, raw, self.unit, exact, k))
        if abs(k) >= GRID_LIMIT:
            raise GeometryError(f"{path}: {raw!r} is outside the grid range |k| < 2^63 pm", path=path,
                                code="E-DOMAIN")
        self.pm_values[path] = k
        return k

    def element_size(self, raw, path: str) -> int:
        """An element size, a quantity string (or an annotated one), on the pm grid."""
        accept = {}
        if isinstance(raw, dict) and "value" in raw:
            accept = raw.get("accept") or {}
            path, raw = f"{path}.value", raw["value"]
        if not isinstance(raw, (str, int, float, Decimal)) or isinstance(raw, bool):
            raise GeometryError(f"{path}: an element size is a quantity string such as \"0.5 um\"", path=path,
                                code="E-VALUE-FORM")
        c = qty.convert(raw, "element_size", path=path)
        if c.error is not None:
            raise GeometryError(f"{path}: {c.error.message}", path=path, code=c.error.code)
        for d in c.diagnostics:
            self.diagnostics.append(d if d.code not in accept else
                                    Diagnostic(d.code, d.path, d.message, d.fix, d.suggestions, str(accept[d.code])))
        grid = qty.length_to_pm(raw, path=path)
        self.diagnostics.extend(grid.diagnostics)
        if abs(grid.picometres) >= GRID_LIMIT:
            raise GeometryError(f"{path}: {raw!r} is outside the grid range |k| < 2^63 pm", path=path,
                                code="E-DOMAIN")
        self.pm_values[path] = grid.picometres
        return grid.picometres

    def point(self, raw, path: str) -> tuple[int, int]:
        if not isinstance(raw, list) or len(raw) != 2:
            raise GeometryError(f"{path}: expected [x, y]", path=path, code="E-VALUE-FORM")
        return self.length(raw[0], f"{path}[0]"), self.length(raw[1], f"{path}[1]")


def _rounding(path: str, raw, unit, exact, k) -> Diagnostic:
    """I-PM-ROUNDING (below 1e-3 pm) or W-PM-ROUNDING for a format 0.3 shape number."""
    shift = Fraction(k) - Fraction(exact)
    code = "I-PM-ROUNDING" if abs(shift) < Fraction(1, 1000) else "W-PM-ROUNDING"
    written = raw if isinstance(raw, str) else str(raw)
    return Diagnostic(code, path, f"{written} ({unit}) is {float(exact):.17g} pm; it is stored as {k} pm, a shift of "
                                  f"{float(shift):.3g} pm.")


def _keys(obj: dict, required: set, optional: set, path: str, reserved: set = frozenset()) -> None:
    missing = required - set(obj)
    if missing:
        first = sorted(missing)[0]
        raise GeometryError(f"{path}: missing {sorted(missing)}", path=f"{path}.{first}", code="E-KEY-MISSING")
    for k in obj:
        if k in reserved:
            raise GeometryError(f"{path}.{k}: reserved for a later version", path=f"{path}.{k}")
        if k not in required and k not in optional:
            raise GeometryError(f"{path}: unknown key {k!r}", path=f"{path}.{k}", code="E-KEY-UNKNOWN")


def parse(doc: dict) -> GeometryModel:
    """Read the version 1 ``geometry`` block of a format 0.3 document. A document of another
    format is refused by name (``E-FORMAT`` at ``openphysics``, as ``Document.from_dict`` refuses
    it; units batch C11a)."""
    from .resolve import format_refusal
    refusal = format_refusal(doc) if isinstance(doc, dict) else None
    if refusal is not None:
        raise GeometryError(refusal.message, path=refusal.path, code=refusal.code)
    return _parse(_Reader(doc), doc)


def _parse(r: _Reader, doc: dict) -> GeometryModel:
    comps = doc["geometry"]["components"]
    if not isinstance(comps, dict) or not comps:
        raise GeometryError("geometry.components: expected a non-empty object", path="geometry.components",
                            code="E-VALUE-FORM")
    components = {}
    for cname, c in comps.items():
        components[cname] = _component(r, cname, c)
    for cname, comp in components.items():
        for f in comp.features:
            if f.type == "layers":
                _check_footprints(cname, f, comp, components)
    return GeometryModel(dict(r.ev.values), components, r.roundings, "0.3", dict(r.pm_values),
                         list(r.ev.diagnostics) + list(r.diagnostics))


def _component(r: _Reader, cname: str, c: dict) -> Component:
    path = f"geometry.components.{cname}"
    if not ID_RE.match(cname):
        raise GeometryError(f"{path}: a component name matches [A-Za-z_][A-Za-z0-9_-]{{0,63}}", path=path,
                            code="E-ID-CLASH")
    if not isinstance(c, dict):
        raise GeometryError(f"{path}: expected an object", path=path, code="E-VALUE-FORM")
    _keys(c, {"dimension", "domain", "length_unit"}, {"background", "features", "finalize", "selections",
                                                      "boundary_tags", "depth", "accept"}, path,
          reserved={"periodic"})
    dim = c["dimension"]
    if dim not in _DOMAIN_KEYS:
        raise GeometryError(f"{path}.dimension: expected '2d', 'axisymmetric' or '3d'", path=f"{path}.dimension",
                            code="E-VALUE-FORM")
    depth = depth_written = None
    r.set_component(*pm_per_length_unit(c["length_unit"], f"{path}.length_unit"))
    if dim == "2d" and "depth" not in c:
        raise GeometryError(f"{path}.depth: a 2d component gives its depth, a length or null (per metre of "
                            "depth)", path=f"{path}.depth", code="E-KEY-MISSING")
    if dim != "2d" and "depth" in c:
        raise GeometryError(f"{path}.depth: an {dim} component has no depth", path=f"{path}.depth",
                            code="E-KEY-UNKNOWN")
    if dim == "2d":
        depth_written = c["depth"]
        depth = _depth(depth_written, f"{path}.depth")
    dkeys = _DOMAIN_KEYS[dim]
    if not isinstance(c["domain"], dict):
        raise GeometryError(f"{path}.domain: expected an object")
    _keys(c["domain"], set(dkeys), set(), f"{path}.domain")
    domain = {k: r.length(c["domain"][k], f"{path}.domain.{k}") for k in dkeys}
    for a in "xyz"[: len(dkeys) // 2]:
        if not domain[f"{a}min"] < domain[f"{a}max"]:
            raise GeometryError(f"{path}.domain: {a}min must be below {a}max")
    if dim == "axisymmetric" and domain["xmin"] < 0:
        raise GeometryError(f"{path}.domain.xmin: an axisymmetric component needs r = x >= 0")
    finalize = c.get("finalize", "later_wins")
    if finalize not in ("later_wins", "imprint"):
        raise GeometryError(f"{path}.finalize: expected 'later_wins' or 'imprint'")
    if finalize == "imprint" and dim == "3d":
        raise GeometryError(f"{path}.finalize: 3D imprint is reserved for a later version")
    bg_raw = c.get("background", {})
    if not isinstance(bg_raw, dict):
        raise GeometryError(f"{path}.background: expected an object", path=f"{path}.background",
                            code="E-VALUE-FORM")
    _keys(bg_raw, set(), {"material", "element_size"}, f"{path}.background")
    background = {}
    if "material" in bg_raw:
        _material(bg_raw["material"], f"{path}.background.material")
        background["material"] = bg_raw["material"]
    if "element_size" in bg_raw:
        background["mesh_size"] = _positive(r.element_size(bg_raw["element_size"], f"{path}.background.element_size"),
                                            f"{path}.background.element_size")
    raw_features = c.get("features", [])
    if not isinstance(raw_features, list):
        raise GeometryError(f"{path}.features: expected a list")
    if raw_features and "material" not in background:
        raise GeometryError(f"{path}.background: a component with features needs a background material "
                            "(a name, or null for void)")
    features = [_feature(r, dim, f, f"{path}.features[{i}]", i) for i, f in enumerate(raw_features)]
    _check_names(features, path)
    comp = Component(cname, dim, domain, background, features, finalize, {}, [], r.unit, r.ppu, depth, depth_written)
    comp.selections = _selections(c.get("selections", {}), comp, f"{path}.selections")
    comp.boundary_tags = _boundary_tags(c.get("boundary_tags", []), comp, f"{path}.boundary_tags")
    for name in set(comp.selections) & {e["tag"] for e in comp.boundary_tags}:
        raise GeometryError(f"{path}.selections.{name}: a selection may not share a mesh tag's name")
    _check_small_features(comp, path)
    return comp


def _depth(raw, path: str):
    """Format 0.3: a 2d component's depth in metres, or None (per metre of depth)."""
    if raw is None:
        return None
    if isinstance(raw, dict) and "value" in raw:
        raw, path = raw["value"], f"{path}.value"
    if not isinstance(raw, (str, int, float, Decimal)) or isinstance(raw, bool):
        raise GeometryError(f"{path}: a depth is a quantity string such as \"40 mm\", or null", path=path,
                            code="E-VALUE-FORM")
    c = qty.convert(raw, "depth", path=path)
    if c.error is not None:
        raise GeometryError(f"{path}: {c.error.message}", path=path, code=c.error.code)
    return c.value


def _material(value, path: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise GeometryError(f"{path}: expected a material name or null", path=path, code="E-VALUE-FORM")


def _positive(k: int, path: str) -> int:
    if k <= 0:
        raise GeometryError(f"{path}: must be positive", path=path, code="E-DOMAIN")
    return k


def _feature(r: _Reader, dim: str, f: dict, path: str, index: int) -> Feature:
    if not isinstance(f, dict):
        raise GeometryError(f"{path}: expected an object")
    t = f.get("type")
    if t in _RESERVED_TYPES:
        raise GeometryError(f"{path}.type: {t!r} is reserved for a later version")
    table = _FIELDS_3D if dim == "3d" else _FIELDS_2D
    if t not in table:
        raise GeometryError(f"{path}.type: {t!r} is not a {dim} feature; expected one of {sorted(table)}")
    required, optional = table[t]
    common = _COMMON - ({"material"} if t in ("segment", "layers") else set())
    _keys(f, required | {"name", "type"}, optional | common, path, reserved=_RESERVED_FEATURE_KEYS)
    if f.get("axis", "z") != "z":
        raise GeometryError(f"{path}.axis: only 'z' is defined; other axes are reserved")
    name = f["name"]
    if not isinstance(name, str) or not name:
        raise GeometryError(f"{path}.name: expected a non-empty string")
    if name == "background":
        raise GeometryError(f"{path}.name: 'background' is reserved")
    fid = f.get("id")
    if fid is None:
        if not ID_RE.match(name) or name.lower() in RESERVED_IDS:
            raise GeometryError(f"{path}: name {name!r} cannot serve as an id; give the feature an 'id'")
        fid = name
    elif not isinstance(fid, str) or not ID_RE.match(fid):
        raise GeometryError(f"{path}.id: an id matches [A-Za-z_][A-Za-z0-9_-]{{0,63}}")
    elif fid.lower() in RESERVED_IDS:
        raise GeometryError(f"{path}.id: {fid!r} is reserved")
    region = f.get("region", name)
    if not isinstance(region, str) or not region or region == "background":
        raise GeometryError(f"{path}.region: expected a region name other than 'background'")
    material = f.get("material", _MISSING)
    if t not in ("segment", "layers"):
        if material is _MISSING:
            raise GeometryError(f"{path}: needs 'material' (a name, or null for void)")
        _material(material, f"{path}.material")
    mesh_size = None
    if "element_size" in f:
        mesh_size = _positive(r.element_size(f["element_size"], f"{path}.element_size"), f"{path}.element_size")
    data = _feature_data(r, t, f, path)
    return Feature(fid, name, region, t, material, mesh_size, data)


def _feature_data(r: _Reader, t: str, f: dict, path: str) -> dict:
    L = lambda k: r.length(f[k], f"{path}.{k}")          # noqa: E731
    if t == "rect":
        d = {k: L(k) for k in ("x", "y", "w", "h")}
        _positive(d["w"], f"{path}.w"), _positive(d["h"], f"{path}.h")
        return d
    if t == "circle":
        d = {k: L(k) for k in ("cx", "cy", "r")}
        _positive(d["r"], f"{path}.r")
        return d
    if t == "trapezoid":
        d = {k: L(k) for k in ("cx", "y", "w", "h")}
        d["w_top"] = r.length(f["w_top"], f"{path}.w_top") if "w_top" in f else d["w"]
        for k in ("w", "h", "w_top"):
            _positive(d[k], f"{path}.{k}")
        return d
    if t in ("polygon", "segment"):
        pts = f["points"]
        need = 3 if t == "polygon" else 2
        if not isinstance(pts, list) or len(pts) < need:
            raise GeometryError(f"{path}.points: a {t} needs at least {need} points")
        points = [r.point(p, f"{path}.points[{i}]") for i, p in enumerate(pts)]
        if t == "polygon":
            _check_simple(points, f"{path}.points")
            edges = f.get("edges")
            if edges is not None:
                if (not isinstance(edges, list) or len(edges) != len(points)
                        or not all(isinstance(e, str) and PART_RE.match(e) for e in edges)
                        or len(set(edges)) != len(edges)):
                    raise GeometryError(f"{path}.edges: one distinct part name [A-Za-z0-9_-]+ per edge")
            return {"points": points, "edges": edges or [f"e{i + 1}" for i in range(len(points))]}
        return {"points": points}
    if t == "path":
        start = r.point(f["start"], f"{path}.start")
        segs = f["segments"]
        if not isinstance(segs, list) or not segs:
            raise GeometryError(f"{path}.segments: expected a non-empty list")
        out = []
        for i, s in enumerate(segs):
            sp = f"{path}.segments[{i}]"
            if not isinstance(s, dict):
                raise GeometryError(f"{sp}: expected {{\"line\": ...}} or {{\"arc\": ...}}")
            _keys(s, set(), {"line", "arc", "name"}, sp)
            if ("line" in s) == ("arc" in s):
                raise GeometryError(f"{sp}: give exactly one of 'line' and 'arc'")
            if "line" in s:
                out.append({"line": r.point(s["line"], f"{sp}.line"), "name": s.get("name")})
            else:
                a = s["arc"]
                if not isinstance(a, dict):
                    raise GeometryError(f"{sp}.arc: expected an object")
                _keys(a, {"center", "to", "ccw"}, set(), f"{sp}.arc")
                if not isinstance(a["ccw"], bool):
                    raise GeometryError(f"{sp}.arc.ccw: expected true or false")
                out.append({"arc": {"center": r.point(a["center"], f"{sp}.arc.center"),
                                    "to": r.point(a["to"], f"{sp}.arc.to"), "ccw": a["ccw"]},
                            "name": s.get("name")})
        return {"start": start, "segments": out}
    if t == "box":
        d = {k: L(k) for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")}
        for a in "xyz":
            if not d[f"{a}min"] < d[f"{a}max"]:
                raise GeometryError(f"{path}: {a}min must be below {a}max")
        return d
    if t == "cylinder":
        d = {k: L(k) for k in ("cx", "cy", "r", "zmin", "zmax")}
        _positive(d["r"], f"{path}.r")
        if not d["zmin"] < d["zmax"]:
            raise GeometryError(f"{path}: zmin must be below zmax")
        return d
    if t == "sphere":
        d = {k: L(k) for k in ("cx", "cy", "cz", "r")}
        _positive(d["r"], f"{path}.r")
        return d
    if t == "extrude":
        prof = f["profile"]
        if not isinstance(prof, dict) or prof.get("type") not in ("rect", "circle", "polygon", "trapezoid"):
            raise GeometryError(f"{path}.profile: expected one inline rect, circle, polygon or trapezoid")
        req, opt = _FIELDS_2D[prof["type"]]
        _keys(prof, req | {"type"}, opt, f"{path}.profile")
        d = {"profile": {"type": prof["type"], **_feature_data(r, prof["type"], prof, f"{path}.profile")},
             "zmin": L("zmin"), "zmax": L("zmax")}
        if not d["zmin"] < d["zmax"]:
            raise GeometryError(f"{path}: zmin must be below zmax")
        return d
    if t == "layers":
        layers = f["layers"]
        if not isinstance(layers, list) or not layers:
            raise GeometryError(f"{path}.layers: expected a non-empty list")
        out, seen = [], set()
        for i, lay in enumerate(layers):
            lp = f"{path}.layers[{i}]"
            if not isinstance(lay, dict):
                raise GeometryError(f"{lp}: expected an object")
            _keys(lay, {"name", "thickness"}, {"material", "footprint", "map", "region"}, lp,
                  reserved={"below", "above"})
            if not isinstance(lay["name"], str) or not PART_RE.match(lay["name"]) or lay["name"] in seen:
                raise GeometryError(f"{lp}.name: a distinct layer name [A-Za-z0-9_-]+")
            seen.add(lay["name"])
            if ("material" in lay) == ("footprint" in lay):
                raise GeometryError(f"{lp}: give exactly one of 'material' (a slab) and 'footprint'")
            if "map" in lay and "footprint" not in lay:
                raise GeometryError(f"{lp}.map: only a footprint layer has a map")
            entry = {"name": lay["name"], "thickness": _positive(r.length(lay["thickness"], f"{lp}.thickness"),
                                                                    f"{lp}.thickness")}
            if "material" in lay:
                _material(lay["material"], f"{lp}.material")
                entry["material"] = lay["material"]
                entry["region"] = lay.get("region")
            else:
                entry["footprint"] = lay["footprint"]
                entry["map"] = _layer_map(lay.get("map"), f"{lp}.map")
            out.append(entry)
        return {"z0": L("z0"), "layers": out}
    raise AssertionError(t)


def _layer_map(raw, path: str):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise GeometryError(f"{path}: expected an object of footprint region -> material")
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            _keys(v, {"material"}, {"region"}, f"{path}.{k}")
            _material(v["material"], f"{path}.{k}.material")
            out[k] = (v["material"], v.get("region"))
        else:
            _material(v, f"{path}.{k}")
            out[k] = (v, None)
    return out


def _check_names(features: list[Feature], path: str) -> None:
    ids, names, region_material, name_of = set(), set(), {}, {}
    for f in features:
        if f.id.lower() in ids:
            raise GeometryError(f"{path}: id {f.id!r} is used twice (ids compare case-insensitively)")
        ids.add(f.id.lower())
        if f.name in names:
            raise GeometryError(f"{path}: feature name {f.name!r} is used twice")
        names.add(f.name)
        name_of[f.name] = f
    for f in features:
        if f.type in ("segment", "layers"):
            continue
        if f.region in region_material and region_material[f.region] != f.material:
            raise GeometryError(f"{path}: region {f.region!r} merges features with different materials")
        region_material[f.region] = f.material
        other = name_of.get(f.region)
        if other is not None and other.region != f.region:
            raise GeometryError(f"{path}: region {f.region!r} equals the name of feature {other.name!r}, "
                                "which is not in that region")


def _orient(a, b, c) -> int:
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (v > 0) - (v < 0)


def _on_segment(a, b, p) -> bool:
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _segments_meet(p, q, r, s) -> bool:
    d1, d2, d3, d4 = _orient(r, s, p), _orient(r, s, q), _orient(p, q, r), _orient(p, q, s)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True
    return ((d1 == 0 and _on_segment(r, s, p)) or (d2 == 0 and _on_segment(r, s, q))
            or (d3 == 0 and _on_segment(p, q, r)) or (d4 == 0 and _on_segment(p, q, s)))


def _check_simple(points: list, path: str) -> None:
    """Refuse repeated points, zero area and self-intersections, exactly on the grid."""
    n = len(points)
    if len(set(points)) != n:
        raise GeometryError(f"{path}: repeated point")
    area2 = sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1] for i in range(n))
    if area2 == 0:
        raise GeometryError(f"{path}: the polygon has zero area")
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue
            if _segments_meet(a, b, points[j], points[(j + 1) % n]):
                raise GeometryError(f"{path}: edges {i + 1} and {j + 1} intersect; a polygon must be simple")


def _expr_keys(expr, path: str):
    """Validate a selector expression's syntax and return the string names it mentions."""
    if isinstance(expr, str):
        return [expr]
    if not isinstance(expr, dict) or len(expr) != 1:
        raise GeometryError(f"{path}: a selector expression is a string or an object with one key")
    (k, v), = expr.items()
    if k in _RESERVED_SELECTOR_KEYS:
        raise GeometryError(f"{path}.{k}: reserved for a later version")
    if k not in _SELECTOR_KEYS:
        raise GeometryError(f"{path}: unknown selector key {k!r}")
    if k in ("feature", "provenance", "material"):
        if not isinstance(v, str):
            raise GeometryError(f"{path}.{k}: expected a string")
        return []
    if k == "between":
        if not isinstance(v, list) or len(v) != 2:
            raise GeometryError(f"{path}.between: expected [A, B]")
        return [n for i, e in enumerate(v) if e != "exterior" for n in _expr_keys(e, f"{path}.between[{i}]")]
    if k == "of":
        return _expr_keys(v, f"{path}.of")
    if not isinstance(v, list) or not v:
        raise GeometryError(f"{path}.any: expected a non-empty list")
    return [n for i, e in enumerate(v) for n in _expr_keys(e, f"{path}.any[{i}]")]


def _selector(raw, path: str) -> dict:
    if not isinstance(raw, dict):
        raise GeometryError(f"{path}: expected {{\"region\": ...}} or {{\"boundary\": ...}}")
    _keys(raw, set(), {"region", "boundary", "optional"}, path)
    if ("region" in raw) == ("boundary" in raw):
        raise GeometryError(f"{path}: give exactly one of 'region' and 'boundary'")
    if "optional" in raw and not isinstance(raw["optional"], bool):
        raise GeometryError(f"{path}.optional: expected true or false")
    kind = "region" if "region" in raw else "boundary"
    if kind == "region":
        expr = raw["region"]
        if isinstance(expr, dict) and len(expr) == 1 and next(iter(expr)) in ("between", "of"):
            raise GeometryError(f"{path}.region: 'between' and 'of' select boundaries")
    _expr_keys(raw[kind], f"{path}.{kind}")
    return raw


def _selections(raw, comp: Component, path: str) -> dict:
    if not isinstance(raw, dict):
        raise GeometryError(f"{path}: expected an object")
    regions = set(comp.region_names)
    for name, sel in raw.items():
        if not ID_RE.match(name) or name.lower() in RESERVED_IDS:
            raise GeometryError(f"{path}.{name}: a selection name follows the id grammar and is not reserved")
        if name in regions:
            raise GeometryError(f"{path}.{name}: a selection may not share a region's name")
        _selector(sel, f"{path}.{name}")
    return dict(raw)


def _boundary_tags(raw, comp: Component, path: str) -> list:
    if not isinstance(raw, list):
        raise GeometryError(f"{path}: expected a list")
    regions = set(comp.region_names)
    for i, entry in enumerate(raw):
        ep = f"{path}[{i}]"
        if not isinstance(entry, dict):
            raise GeometryError(f"{ep}: expected {{\"tag\": ..., \"select\": ...}}")
        _keys(entry, {"tag", "select"}, set(), ep)
        tag = entry["tag"]
        if not isinstance(tag, str) or not tag or '"' in tag or "\n" in tag:
            raise GeometryError(f"{ep}.tag: a non-empty name without quotes or newlines")
        if tag in regions:
            raise GeometryError(f"{ep}.tag: {tag!r} is also a region name")
        sel = entry["select"]
        if isinstance(sel, dict) and "region" in sel:
            raise GeometryError(f"{ep}.select: a boundary tag needs a boundary selector")
        _selector(sel, f"{ep}.select")
    return list(raw)


def _feature_extent(f: Feature):
    """The smallest side of a feature's bounding box, in pm, or None if it has no area."""
    d = f.data
    if f.type == "rect":
        return min(d["w"], d["h"])
    if f.type == "circle":
        return 2 * d["r"]
    if f.type == "trapezoid":
        return min(d["h"], d["w"], d["w_top"])
    if f.type == "polygon":
        xs, ys = [p[0] for p in d["points"]], [p[1] for p in d["points"]]
        return min(max(xs) - min(xs), max(ys) - min(ys))
    if f.type == "layers":
        return min(lay["thickness"] for lay in d["layers"])
    if f.type == "box":
        return min(d[f"{a}max"] - d[f"{a}min"] for a in "xyz")
    return None


def _check_small_features(comp: Component, path: str) -> None:
    dom = comp.domain
    diag2 = sum((dom[f"{a}max"] - dom[f"{a}min"]) ** 2 for a in "xyz" if f"{a}min" in dom)
    for f in comp.features:
        size = _feature_extent(f)
        if size is None:
            continue
        ratio = size / diag2 ** 0.5
        if ratio < MESHER_RELATIVE_TOLERANCE:
            raise GeometryError(f"{path}: feature {f.name!r} is {size} pm across, {ratio:.2e} of the component's "
                                f"diagonal, below the mesher tolerance {MESHER_RELATIVE_TOLERANCE:g}; it would "
                                "vanish in the mesh. Meshing such multi-scale geometry is not supported yet.")


def _check_footprints(cname: str, f: Feature, comp: Component, components: dict) -> None:
    for i, lay in enumerate(f.data["layers"]):
        if "footprint" not in lay:
            continue
        lp = f"geometry.components.{cname}.features[{comp.features.index(f)}].layers[{i}]"
        fp = components.get(lay["footprint"])
        if fp is None or fp.dimension != "2d":
            raise GeometryError(f"{lp}.footprint: {lay['footprint']!r} is not a 2d component")
        if any(fp.domain[k] != comp.domain[k] for k in ("xmin", "xmax", "ymin", "ymax")):
            raise GeometryError(f"{lp}.footprint: the footprint's x-y domain must equal this component's")
        regions = set(fp.region_names) | ({"background"} if fp.background.get("material", _MISSING) is not None
                                          else set())
        for k in (lay["map"] or {}):
            if k not in regions:
                raise GeometryError(f"{lp}.map.{k}: not a region of footprint {lay['footprint']!r}")


# --------------------------------------------------------------------------- flat blocks

def from_flat(geometry: dict) -> dict:
    """The version 1 block that expresses a flat ``geometry`` block exactly.

    Numbers are copied unchanged, and so are the block's ``length_unit`` and ``depth``. A shape
    name that cannot be an id gets the id ``s<i>`` (its list position). A flat block without a
    background is a rectangle document: a component without features whose background has no
    material key.
    """
    if not isinstance(geometry, dict) or "version" in geometry:
        raise GeometryError("geometry: expected a flat block (no 'version')")
    dom = geometry["domain"]
    dim = "3d" if "zmin" in dom else "2d"
    comp: dict = {"dimension": dim, "domain": dict(dom)}
    for key in ("length_unit", "depth"):                 # the flat block's own declarations
        if key in geometry:
            comp[key] = geometry[key]
    if "background" in geometry:
        comp["background"] = dict(geometry["background"])
    features = []
    for i, s in enumerate(geometry.get("shapes", []) or []):
        f = dict(s)
        name = s.get("name")
        if not isinstance(name, str) or not ID_RE.match(name) or name.lower() in RESERVED_IDS:
            f["id"] = f"s{i}"
        features.append(f)
    if features or "background" in geometry:
        comp["features"] = features
    comp["finalize"] = "later_wins"
    return {"version": 1, "components": {"main": comp}}


def to_flat(model: GeometryModel, component: str | None = None, *, validation: bool = False) -> dict:
    """Compile a 2D component, or a box-only 3D component, to a flat ``geometry`` block.

    Values come back in the component's length unit, each rounded once from its pm count,
    beside the component's ``length_unit`` and ``depth``; a trapezoid becomes the polygon of
    its exact corners. Features a flat block cannot express (merged regions, segments, paths,
    2.5D and curved 3D features) are refused with their names.

    With ``validation`` the result is the form the document validators read and the
    results record (``Document.geometry_flat``) while the exact engine (stage 2) does the
    meshing: ``finalize: "imprint"`` is accepted (the shapes are the same, the engine keeps
    the covered boundaries) and ``segment`` features are left out (they have no area and no
    material; the engine imprints them). Without it the result is what the flat block's
    shapely builder meshes, which would drop both silently, so both are refused by name.
    """
    comp = _pick(model, component)
    u = comp.to_unit
    if comp.finalize == "imprint" and not validation:
        raise GeometryError(f"component {comp.name!r}: finalize 'imprint' needs the stage 2 engine; the flat "
                            "block's builder would remove the covered boundaries")
    if comp.dimension == "axisymmetric":
        raise GeometryError(f"component {comp.name!r}: a flat block has no axisymmetric form")
    out: dict = {"length_unit": comp.length_unit, **({"depth": comp.depth} if comp.dimension == "2d" else {}),
                 "domain": {k: u(v) for k, v in comp.domain.items()}}
    if comp.background.get("material", "") is None or any(f.material is None for f in comp.features):
        raise GeometryError(f"component {comp.name!r}: void (material null) needs the stage 2 engine; the flat "
                            "block's builder meshes every region")
    if "material" in comp.background:
        out["background"] = {"material": comp.background["material"]}
        if "mesh_size" in comp.background:
            raise GeometryError(f"component {comp.name!r}: a flat block compiled from a component has no background "
                                "element_size")
    elif not comp.features:
        return out
    shapes = []
    for i, f in enumerate(comp.features):
        if f.type == "segment" and validation:
            continue
        if f.region != f.name:
            raise GeometryError(f"feature {f.name!r}: merged regions need the stage 2 hand-off")
        allowed = ("box",) if comp.dimension == "3d" else ("rect", "circle", "polygon", "trapezoid")
        if f.type not in allowed and comp.dimension == "3d" and validation:
            # the reader's flat compile of a 3d component (em.cavity3d reads boxes only)
            where = f"geometry.components.{comp.name}.features[{i}].type"
            raise GeometryError(f"{where}: a 3d component is read as boxes only; feature {f.name!r} is a {f.type}",
                                path=where)
        if f.type not in allowed:
            raise GeometryError(f"feature {f.name!r}: a {f.type} has no flat-block form")
        s: dict = {"name": f.name, "type": f.type, "material": f.material}
        d = f.data
        if f.type in ("rect", "circle", "box"):
            s.update({k: u(v) for k, v in d.items()})
        elif f.type == "polygon":
            s["points"] = [[u(x), u(y)] for x, y in d["points"]]
        else:                                                      # trapezoid: exact corners, one rounding each
            cx, y, w, h, wt = (Fraction(d[k]) for k in ("cx", "y", "w", "h", "w_top"))
            corners = [(cx - w / 2, y), (cx + w / 2, y), (cx + wt / 2, y + h), (cx - wt / 2, y + h)]
            s["type"] = "polygon"
            s["points"] = [[float(px / comp.pm_per_unit), float(py / comp.pm_per_unit)] for px, py in corners]
        if f.mesh_size is not None:
            s["mesh_size"] = u(f.mesh_size)
        shapes.append(s)
    out["shapes"] = shapes
    return out


def _pick(model: GeometryModel, component: str | None) -> Component:
    if component is None:
        if len(model.components) != 1:
            raise GeometryError(f"name a component: {sorted(model.components)}")
        component = next(iter(model.components))
    if component not in model.components:
        raise GeometryError(f"no component {component!r}")
    return model.components[component]


# --------------------------------------------------------------------------- 2.5D

@dataclass
class LayerStack:
    """What ``meshine.extrude`` takes for one ``layers`` feature.

    ``levels`` are the z levels in pm (exact cumulative sums), ``table`` maps each
    footprint region to the cell name of every layer (or None for void), and
    ``materials`` maps each cell name to its material.
    """

    footprint: str | None
    levels: list[int]
    table: dict
    materials: dict

    def table_for(self, region_names) -> dict:
        """The ``extrude`` table for a footprint mesh with these region names.

        A stack of slabs only has one row (key None) that every region takes.
        """
        if None in self.table:
            return {r: list(self.table[None]) for r in region_names}
        missing = [r for r in region_names if r not in self.table]
        if missing:
            raise GeometryError(f"footprint mesh regions {missing} are not regions of {self.footprint!r}")
        return {r: list(self.table[r]) for r in region_names}


def layer_stack(model: GeometryModel, component: str | None = None) -> LayerStack:
    """Compile the one ``layers`` feature of a 3D component.

    A layer cell is named by its explicit ``region``, otherwise by its material, as
    ``meshine.extrude`` names cells. All footprint layers must share one footprint;
    slab layers cover every footprint region.
    """
    comp = _pick(model, component)
    stacks = [f for f in comp.features if f.type == "layers"]
    if comp.dimension != "3d" or len(stacks) != 1 or len(comp.features) != 1:
        raise GeometryError(f"component {comp.name!r}: stage 1 compiles a 3d component holding one layers feature")
    f = stacks[0]
    layers = f.data["layers"]
    footprints = {lay["footprint"] for lay in layers if "footprint" in lay}
    if len(footprints) > 1:
        raise GeometryError(f"feature {f.name!r}: one extrusion takes one footprint; layers name {sorted(footprints)}")
    fp_name = next(iter(footprints), None)
    if fp_name is not None:
        fp = model.components[fp_name]
        regions = list(fp.region_names)
        if fp.background.get("material", _MISSING) is not None:
            regions.append("background")
        own = {r: next((x.material for x in fp.features if x.region == r), fp.background.get("material"))
               for r in regions}
    else:
        regions, own = [None], {None: None}
    levels = [f.data["z0"]]
    for lay in layers:
        levels.append(levels[-1] + lay["thickness"])
    table = {r: [] for r in regions}
    materials: dict = {}

    def cell(material, region):
        if material is None:
            return None
        name = region or material
        if materials.setdefault(name, material) != material:
            raise GeometryError(f"feature {f.name!r}: cell name {name!r} is given two materials")
        return name

    for lay in layers:
        for r in regions:
            if "material" in lay:
                table[r].append(cell(lay["material"], lay.get("region")))
            else:
                mapped = (lay["map"] or {}).get(r, (own[r], None))
                table[r].append(cell(*mapped))
    return LayerStack(fp_name, levels, table, materials)
