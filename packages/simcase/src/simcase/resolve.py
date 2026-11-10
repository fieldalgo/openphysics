# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Resolve a format 0.3 document: walk the slot table, convert every value once, check.

    result = resolve_text(raw_bytes)          # or resolve_tree(python_object)
    result.diagnostics                        # the append-only list, in document order
    doc = result.document()                   # the Document, or None when an error exists

The steps (phase-2 spec section 3.2): the envelope (``"openphysics": "0.3"``, else
``E-FORMAT`` and stop); the kind (a kind without slots refuses with ``E-CONTRACT``); the slot
walk, where every authored path matches exactly one slot and the first applicable rule gives
its one error (a refused key, an unknown key with "did you mean", the value form, the value
itself through ``physmat.units``); the requirements and the closed list of defaults, each
echoed in ``defaults_applied``; the geometry (shape numbers on the 1 pm grid, a version 1
block through ``geometry_document``), the material references and the study values; then the
kind's validation on the resolved SI tree, and the cross-checks of ``simcase.checks``.

The resolved SI tree (``si``) has the keys of the authored tree, without ``accept``: a
quantity string becomes its SI float, a tagged array or a short list a list of floats, a
component object a dict, a complex value a ``complex``, a count an ``int``, a shape number
metres (``pm_to_m``), an annotated value its value. The authored tree is never changed.
"""

from __future__ import annotations

import copy
import difflib
import json
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from importlib import resources
from typing import Any

from physmat import units
from physmat.units import Diagnostic

from . import _old_keys, reader, slots
from .diagnostics import DiagnosticList, acknowledge, from_exception
from .reader import display_path

__all__ = ["Resolution", "resolve_text", "resolve_tree", "FORMAT"]

FORMAT = "0.3"
_MISSING = object()
_FORMAT_HELP = ('format 0.2 documents are not read: units now travel with each value ("200 GPa", "300 K") and each '
                'geometry component declares its length_unit. Write "openphysics": "0.3"')


@lru_cache(maxsize=1)
def _registry_words() -> dict[str, set[str]]:
    """Each quantity's symbols and refused aliases, from physmat's shipped registry data."""
    data = json.loads(resources.files("physmat").joinpath("quantities.json").read_text(encoding="utf-8"))
    return {name: set(e.get("symbols", ())) | set(e.get("refused_aliases", ()))
            for name, e in data["quantities"].items()}


def _number(value) -> bool:
    return isinstance(value, (int, Decimal, float)) and not isinstance(value, bool)


class Resolution:
    """Everything the reader found about one document, complete or not."""

    def __init__(self, source_bytes: bytes | None = None):
        self.source_bytes = source_bytes
        self.tree: Any = None
        self.kind = None
        self.table = None
        self.diagnostics = DiagnosticList()
        self.si: Any = None
        self.exact: dict[str, Fraction] = {}
        self.pm: dict[str, int] = {}
        self.authored: dict[str, Any] = {}
        self.conversions: dict[str, Any] = {}
        self.inputs: dict[str, dict] = {}
        self.defaults_applied: list[dict] = []
        self.spelling_fixes: list[dict] = []
        self.refs: dict[str, tuple] = {}
        self.accepts: dict[str, dict] = {}
        self.geometry_model = None
        self.geometry_flat = None
        self.extent: list[str] = []
        self.estimates: dict[str, float] = {}
        self._document = None

    @property
    def ok(self) -> bool:
        return not self.diagnostics.errors

    def document(self):
        """The resolved ``Document``, or None when any error was found."""
        return self._document if self.ok else None


# -- entry points ---------------------------------------------------------------------------------

def resolve_text(raw) -> Resolution:
    """Read and resolve a document text (bytes or str)."""
    if isinstance(raw, str):
        source = raw.encode("utf-8")
    else:
        source = bytes(raw)
    result = Resolution(source)
    tree, found = reader.parse(raw)
    if found:
        result.diagnostics.extend(found)
        return result
    return _resolve(tree, result)


def resolve_tree(obj, *, from_python: bool = True) -> Resolution:
    """Resolve a Python object (``Document.from_dict``): floats are read through their ``repr``."""
    result = Resolution()
    tree, found = reader.read_with_diagnostics(obj) if from_python else (obj, [])
    if found:
        result.diagnostics.extend(found)
        return result
    return _resolve(tree, result)


def _resolve(tree, result: Resolution) -> Resolution:
    from .registry import kind_of
    result.tree = tree
    diags = result.diagnostics
    if not isinstance(tree, dict):
        diags.append(Diagnostic("E-VALUE-FORM", "", "a document is a JSON object"))
        return result
    if "openphysics" not in tree:
        diags.append(Diagnostic("E-FORMAT", "openphysics", f"the document has no format key; {_FORMAT_HELP}"))
        return result
    fmt = tree["openphysics"]
    if fmt != FORMAT or not isinstance(fmt, str):
        shown = f'the number {fmt}' if _number(fmt) else json.dumps(fmt, default=str)
        hint = (' The format is the JSON string "0.3", not a number.' if _number(fmt) and str(fmt) == "0.3"
                else f" {_FORMAT_HELP}.")
        diags.append(Diagnostic("E-FORMAT", "openphysics", f"openphysics is {shown}; this reader reads the format "
                                                           f'"0.3".{hint}'))
        return result
    kind = kind_of(tree)
    result.kind = kind
    if kind.slots is None:
        diags.append(_unread_kind(tree, kind))
        return result
    form = slots.geometry_form(tree.get("geometry"))
    if kind.forms_03 is not None and form is not None and form not in kind.forms_03:
        diags.append(_unread_form(tree, kind, form))
        return result
    result.table = slots.table_for(kind)
    walker = _Walker(result)
    result.si = walker.walk()
    walker.finish()
    _build(result)
    return result


def _unread_kind(tree, kind) -> Diagnostic:
    physics = tree.get("physics")
    if isinstance(physics, dict):
        for name, entry in physics.items():
            if isinstance(entry, dict) and entry.get("type") in kind.types:
                path = display_path(["physics", name, "type"])
                return Diagnostic("E-CONTRACT", path, f"{path}: {entry['type']!r} documents are not read in format "
                                                      f"0.3 yet; this release reads them in format 0.2")
    return Diagnostic("E-CONTRACT", "physics", "physics: no entry has a type this release reads in format 0.3")


_FORM_WORDS = {"rect": "a flat rectangle", "regions": "flat regions (background and shapes)",
               "v1": "a version 1 geometry block"}


def _unread_form(tree, kind, form) -> Diagnostic:
    """A kind that reads format 0.3 for some geometry forms only (during the units batch)."""
    read = " or ".join(_FORM_WORDS[f] for f in sorted(kind.forms_03))
    for name, entry in tree["physics"].items():
        if isinstance(entry, dict) and entry.get("type") in kind.types:
            path = display_path(["physics", name, "type"])
            return Diagnostic("E-CONTRACT", "geometry", f"geometry: {entry['type']!r} documents on {_FORM_WORDS[form]} "
                                                        f"are not read in format 0.3 yet; this release reads them in "
                                                        f"format 0.2, and reads {read} in format 0.3 ({path})")
    return Diagnostic("E-CONTRACT", "geometry", f"geometry: {_FORM_WORDS[form]} is not read in format 0.3 yet")


# -- the walk -------------------------------------------------------------------------------------

class _Walker:
    def __init__(self, result: Resolution):
        self.r = result
        self.tree = result.tree
        self.table = result.table
        self.form = slots.geometry_form(self.tree.get("geometry"))
        geometry = self.tree.get("geometry")
        unit = geometry.get("length_unit") if isinstance(geometry, dict) and self.form != "v1" else None
        grid = units.length_to_pm(1, unit) if isinstance(unit, str) else None
        self.flat_unit = grid.unit if grid is not None and grid.error is None else None
        self.refs: list[tuple[list, Any]] = []
        self.v1_shapes: set[str] = set()
        self.v1_parameters: list[list] = []
        self.geometry_errors = False
        self.recording = True

    # diagnostics
    def add(self, d: Diagnostic, path=None) -> None:
        self.r.diagnostics.append(d)
        if d.severity == "error" and (path or [None])[0] == "geometry":
            self.geometry_errors = True

    def error(self, code: str, path, message: str, **extra) -> None:
        where = display_path(path)
        if code == "E-CONTRACT" and where:
            message = f"{where}: {message}"
        self.add(Diagnostic(code, where, message, **extra), path)

    def extend(self, found, path, accept=None) -> None:
        for d in found:
            if accept and d.code in accept and d.severity != "error":
                d = acknowledge(d, accept[d.code])
            self.add(d, path)

    # walking
    def walk(self):
        return self.obj(None, self.tree, [])

    def node(self, value, path):
        found = self.table.match(path, self.tree)
        if not found:
            self.unknown(path)
            return _MISSING
        if len(found) > 1:
            raise AssertionError(f"slot table: {display_path(path)} matches {[e['pattern'] for e in found]}")
        return self.slot(found[0], value, path)

    def slot(self, slot, value, path):
        kind = slot["kind"]
        if kind == "refused":
            self.error(slot["code"], path, slot["message"])
            return _MISSING
        if kind == "structural":
            if "LIST" in slot["forms"]:
                if not isinstance(value, list):
                    self.error("E-VALUE-FORM", path, "expected a list")
                    return None
                return [self.node(v, path + [i]) for i, v in enumerate(value)]
            return self.obj(slot, value, path)
        handler = getattr(self, f"leaf_{kind}")
        return handler(slot, value, path)

    def obj(self, slot, value, path):
        if not isinstance(value, dict):
            self.error("E-VALUE-FORM", path, "expected an object")
            return None
        out = {}
        keys = slot.get("keys") if slot else None
        for k, v in value.items():
            child = path + [k]
            if keys == "material":
                from .materials import check_local_name
                problem = check_local_name(k, display_path(child))
                if problem is not None:
                    self.add(problem, child)
            result = self.node(v, child)
            if result is not _MISSING and not (k == "accept" and result is None):
                out[k] = result
        self.requirements(path, value)
        self.defaults(path, value, out)
        return out

    def requirements(self, path, value) -> None:
        for e in self.table.children(path, self.tree):
            name = slots.compile_pattern(e["pattern"])[-1].name
            if e.get("required") and name not in value and "default" not in e:
                self.error("E-KEY-MISSING", path + [name], f"{display_path(path) or 'the document'} needs "
                                                           f"{name}")

    def defaults(self, path, value, out) -> None:
        for e in self.table.children(path, self.tree):
            name = slots.compile_pattern(e["pattern"])[-1].name
            if "default" not in e or name in value:
                continue
            condition = e.get("default_if")
            if condition is not None and condition not in value:
                continue
            default = copy.deepcopy(e["default"])
            where = path + [name]
            self.r.defaults_applied.append({"path": display_path(where), "value": default,
                                            "reason": e.get("default_reason", "default")})
            if default is None:
                continue                  # an absence (no source, no body force): nothing to resolve
            saved, self.recording = self.recording, False      # a default is no authored input
            try:
                resolved = self.slot(e, reader.read(default), where)
            finally:
                self.recording = saved
            if resolved is not _MISSING:
                out[name] = resolved

    def unknown(self, path) -> None:
        key, parent = path[-1], path[:-1]
        where = display_path(parent) or "the document"
        if isinstance(key, int):
            self.error("E-VALUE-FORM", parent, f"{where} is not a list")
            return
        siblings = self.table.sibling_names(parent, self.tree)
        hints = difflib.get_close_matches(key, siblings, n=3, cutoff=0.7)
        words = _registry_words()
        for e in self.table.children(parent, self.tree):
            q = e.get("quantity")
            name = slots.compile_pattern(e["pattern"])[-1].name
            if q and key in words.get(units.quantity(q).base, ()) and name not in hints:
                hints.append(name)
        message = f'unknown key "{key}" in {where}.'
        old = _old_keys.suggest(key, display_path(parent))
        if old is not None and old[0] not in hints:
            new, note = old
            message += f' "{key}" is the format 0.2 name; write {new}' + (f" ({note})" if note else "") + "."
        if hints:
            message += " Did you mean " + " or ".join(hints) + "?"
        elif siblings and old is None:
            message += " Keys here: " + ", ".join(siblings) + "."
        self.error("E-KEY-UNKNOWN", path, message)

    # leaves
    def leaf_format(self, slot, value, path):
        return value

    def leaf_string(self, slot, value, path):
        if not isinstance(value, str):
            self.error("E-VALUE-FORM", path, "expected a string")
            return None
        return value

    def leaf_id(self, slot, value, path):
        if not isinstance(value, str) or not value:
            self.error("E-VALUE-FORM", path, "expected a non-empty name")
            return None
        return value

    def leaf_bool(self, slot, value, path):
        if not isinstance(value, bool):
            self.error("E-VALUE-FORM", path, "expected true or false")
            return None
        return value

    def leaf_selector(self, slot, value, path):
        if not isinstance(value, (str, dict)):
            self.error("E-VALUE-FORM", path, "a selection is a name or a selector object")
            return None
        return copy.deepcopy(value)

    def leaf_path(self, slot, value, path):
        if not isinstance(value, str):
            self.error("E-VALUE-FORM", path, "expected a dotted path such as physics.em1.vacuum_wavelength")
            return None
        return value

    def leaf_study_values(self, slot, value, path):
        return value                      # read after the walk, against study.parameter

    def leaf_enum(self, slot, value, path):
        refused = slot.get("refused_values", {})
        if isinstance(value, str) and value in refused:
            self.error("E-CONTRACT", path, refused[value])
            return None
        allowed = slot["values"]
        if isinstance(value, dict) and slot.get("object_message"):
            self.error("E-CONTRACT", path, slot["object_message"])
            return None
        if value in allowed and type(value) is type(allowed[allowed.index(value)]):
            return value
        text = ", ".join(json.dumps(v) for v in allowed)
        message = f"{json.dumps(value, default=str)} is not one of {text}."
        if isinstance(value, str):
            close = difflib.get_close_matches(value, [v for v in allowed if isinstance(v, str)], n=1, cutoff=0.6)
            if close:
                message += f' Did you mean "{close[0]}"?'
        self.error("E-VALUE-FORM", path, message)
        return None

    def leaf_ref(self, slot, value, path):
        if value is None and slot.get("nullable"):
            return None
        if isinstance(value, dict) and "OBJECT" in slot.get("forms", ()):
            return self.obj(slot, value, path)
        if not isinstance(value, str) or not value:
            self.error("E-VALUE-FORM", path, 'a material reference is a local name or "physmat:<Name>"'
                       + (", or null for void" if slot.get("nullable") else ""))
            return None
        self.refs.append((path, value))
        return value

    def leaf_accept(self, slot, value, path):
        if not isinstance(value, dict) or not value:
            self.error("E-VALUE-FORM", path, 'accept is an object {"<W-CODE>": "<reason>"}')
            return None
        good = {}
        for code, reason in value.items():
            if code not in units.DIAGNOSTIC_CODES:
                self.error("E-KEY-UNKNOWN", path + [code], f'"{code}" is not a diagnostic code')
            elif units.DIAGNOSTIC_CODES[code]["severity"] == "error":
                self.error("E-VALUE-FORM", path + [code], f"{code} is an error; errors cannot be acknowledged")
            elif not isinstance(reason, str) or not reason.strip():
                self.error("E-VALUE-FORM", path + [code], "an acknowledgement gives its reason as a string")
            else:
                good[code] = reason
        self.r.accepts[display_path(path[:-1])] = good
        return None

    def leaf_display_unit(self, slot, value, path):
        name = path[-1]
        groups = units.display_groups()
        if name in groups:
            menu = groups[name]["menu"]
            grid = units.length_to_pm(1, value) if isinstance(value, str) and name == "length" else None
            if grid is None or grid.error is not None or grid.unit not in menu:
                self.error("E-UNIT-NOT-ACCEPTED", path, f"{json.dumps(value, default=str)} is not on the {name} "
                                                        f"display menu: {' '.join(menu)}")
                return None
            return grid.unit
        if name not in units.names():
            close = list(dict.fromkeys(difflib.get_close_matches(name, list(groups) + units.names(), n=3,
                                                                 cutoff=0.75)))[:2]
            self.error("E-KEY-UNKNOWN", path, f'display_units takes a quantity name or a display group '
                                              f'({", ".join(groups)}), not "{name}".'
                                              + (" Did you mean " + " or ".join(close) + "?" if close else ""))
            return None
        if not isinstance(value, str):
            self.error("E-VALUE-FORM", path, "a display unit is a unit string")
            return None
        c = units.convert(f"1 {value}", name, path=display_path(path))
        if c.error is not None:
            self.add(Diagnostic(c.error.code, c.error.path, f'display unit "{value}" for {name}: {c.error.message}'),
                     path)
            return None
        return c.text.split(" ", 1)[1]

    def leaf_length_unit(self, slot, value, path):
        if not isinstance(value, str):
            self.error("E-VALUE-FORM", path, f"a length_unit is one of {' '.join(units.LENGTH_UNITS)}"
                       + ('; a numeric unit such as {"in_m": ...} is not read' if isinstance(value, dict) else ""))
            return None
        grid = units.length_to_pm(1, value, path=display_path(path))
        if grid.error is not None:
            self.add(grid.error, path)
            return None
        if grid.unit != value:
            self.spelling_fix(path, value, grid.unit)
        return grid.unit

    def leaf_depth(self, slot, value, path):
        if value is None:
            self.record(path, None, {"authored": None, "value": None, "unit": "m"})
            return None
        return self.leaf_quantity({**slot, "quantity": "depth", "forms": ["QS", "AV"]}, value, path)

    def leaf_count_list(self, slot, value, path):
        if not isinstance(value, list) or not 2 <= len(value) <= 3:
            self.error("E-VALUE-FORM", path, "subdivision_count is a list of 2 or 3 integer counts")
            return None
        c = units.convert_array(value, slot["quantity"], path=display_path(path))
        self.extend(c.diagnostics, path)
        if not c.ok:
            return None
        out = [int(e.exact) for e in c.entries]
        self.record(path, None, {"authored": copy.deepcopy(value), "value": out, "unit": "1"})
        return out

    def leaf_parameter(self, slot, value, path):
        ok = isinstance(value, str) or _number(value)
        if path[-1] == "range":
            ok = isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) or _number(v) for v in value)
            if not ok:
                self.error("E-VALUE-FORM", path, "a parameter range is [lo, hi]")
                return None
        elif not ok:
            self.error("E-VALUE-FORM", path, "a parameter value is a quantity string, a number or an expression")
            return None
        self.v1_parameters.append(path)
        return copy.deepcopy(value)

    def leaf_shape(self, slot, value, path):
        where = display_path(path)
        if self.form == "v1":
            if not (isinstance(value, str) or _number(value)):
                self.error("E-VALUE-FORM", path, "a shape number is a bare number in the component's length_unit "
                                                 "or an expression")
                return None
            self.v1_shapes.add(where)
            return copy.deepcopy(value)
        if not _number(value):
            self.error("E-VALUE-FORM", path, "a shape number is a bare number, read in geometry.length_unit")
            return None
        if self.flat_unit is None:
            return None                   # the length_unit refusal is reported at its own path
        grid = units.length_to_pm(value, self.flat_unit, path=where)
        self.extend(grid.diagnostics, path)
        if grid.error is not None:
            return None
        self.r.pm[where] = grid.picometres
        metres = units.pm_to_m(grid.picometres)
        self.record(path, Fraction(grid.picometres, 10 ** 12),
                    {"authored": value, "value": metres, "unit": "m", "length_unit": self.flat_unit})
        return metres

    # quantities
    def leaf_material_property(self, slot, value, path):
        return self.leaf_quantity(slot, value, path)

    def leaf_quantity(self, slot, value, path, *, record: bool = True):
        forms = set(slot.get("forms", ()))
        name = slot["quantity"]
        qo = units.quantity(name)
        accept = None
        authored = value
        if isinstance(value, dict) and "AV" in forms and "accept" in value:
            extra = sorted(set(value) - {"value", "accept"})
            if extra:
                self.error("E-KEY-UNKNOWN", path + [extra[0]], 'an annotated value holds "value" and "accept"')
                return None
            if "value" not in value:
                self.error("E-KEY-MISSING", path + ["value"], 'an annotated value needs "value"')
                return None
            self.leaf_accept(slot, value["accept"], path + ["accept"])
            accept = self.r.accepts.get(display_path(path), {})
            value, path = value["value"], path + ["value"]
            forms = forms - {"AV", "MODEL", "CO"}
        where = display_path(path)
        if value is None:
            if "NULL" in forms:
                return None
            self.error("E-VALUE-FORM", path, f"{name} takes a value here, not null")
            return None
        if qo.complex and forms & {"CX", "NK"} and not (isinstance(value, dict) and "model" in value):
            if isinstance(value, bool) or not isinstance(value, (str, int, Decimal, dict, list)):
                self.error("E-VALUE-FORM", path, f"{name} takes a number or {self._complex_form(qo)}")
                return None
            c = units.convert_complex(value, name, path=where)
            self.extend(c.diagnostics, path, accept)
            if not c.ok:
                return None
            self.spelling_check(path, value, c)
            out = c.value
            self.record(path, c.exact, {"authored": copy.deepcopy(authored), "value": {"re": out.real,
                                                                                        "im": out.imag},
                                        "unit": qo.unit}, record)
            return out
        if isinstance(value, bool):
            self.error("E-VALUE-FORM", path, f"{name} takes {self._forms_text(forms, qo)}, not true or false")
            return None
        if isinstance(value, (str, int, Decimal)):
            if not forms & {"QS", "BD", "BC"}:
                self.error("E-VALUE-FORM", path, f"{name} takes {self._forms_text(forms, qo)} here")
                return None
            c = units.convert(value, name, path=where)
            self.extend(c.diagnostics, path, accept)
            if not c.ok:
                return None
            if isinstance(value, str) and units.normalize(value) != value:
                self.spelling_fix(path, value, units.normalize(value))
            limit = slot.get("maximum")
            if limit is not None and c.exact > units.convert(limit, name).exact:
                self.error("E-DOMAIN", path, f"{value} is above {limit}, the largest {name} this reader takes")
                return None
            self.r.conversions[where] = c
            out = int(c.exact) if qo.kind == "count" else c.value
            self.record(path, c.exact, {"authored": copy.deepcopy(authored), "value": out, "unit": qo.unit}, record)
            return out
        if isinstance(value, list):
            if "SL" not in forms:
                self.error("E-VALUE-FORM", path, f"{name} takes {self._forms_text(forms, qo)} here, not a list")
                return None
            if slot.get("range"):
                return self.range(slot, value, path, record)
            return self.array(name, value, path, authored, accept, record)
        if isinstance(value, dict):
            if "model" in value and "MODEL" in forms:
                out = self.obj(slot, value, path)
                from .materials import check_record_model
                self.extend(check_record_model(value, where), path)
                return out
            if "values" in value and "TA" in forms:
                return self.array(name, value, path, authored, accept, record)
            if "CO" in forms:
                return self.components(slot, value, path, accept, record)
            if "OBJECT" in forms:
                return self.obj(slot, value, path)          # a typed object whose keys are slots
            self.error("E-VALUE-FORM", path, f"{name} takes {self._forms_text(forms, qo)} here, not this object")
            return None
        self.error("E-VALUE-FORM", path, f"{name} takes {self._forms_text(forms, qo)} here")
        return None

    def array(self, name, value, path, authored, accept, record=True):
        c = units.convert_array(value, name, path=display_path(path))
        self.extend(c.diagnostics, path, accept)
        if not c.ok:
            return None
        unit = value.get("unit") if isinstance(value, dict) else None
        if isinstance(unit, str) and units.normalize(unit) != unit:
            self.spelling_fix(path + ["unit"], unit, units.normalize(unit))
        if isinstance(value, list):
            for i, v in enumerate(value):
                if isinstance(v, str) and units.normalize(v) != v:
                    self.spelling_fix(path + [i], v, units.normalize(v))
        exact = [e.exact for e in c.entries]
        qo = units.quantity(name)
        out = [int(e) for e in exact] if qo.kind == "count" else list(c.values)
        self.record(path, exact, {"authored": copy.deepcopy(authored), "value": out, "unit": qo.unit}, record)
        return out

    def range(self, slot, value, path, record=True):
        name = slot["quantity"]
        if len(value) != 2:
            self.error("E-VALUE-FORM", path, f"a range is [lo, hi]: two quantity strings, lo may be null")
            return None
        lo_raw, hi_raw = value
        out, exact = [], []
        for i, v in enumerate(value):
            if v is None and i == 0:
                out.append(None)
                exact.append(None)
                continue
            if not isinstance(v, str):
                self.error("E-VALUE-FORM", path + [i], f"a range bound is a quantity string such as \"1.2 um\"")
                return None
            c = units.convert(v, name, path=display_path(path + [i]))
            self.extend(c.diagnostics, path + [i])
            if not c.ok:
                return None
            out.append(c.value)
            exact.append(c.exact)
        if exact[0] is not None and not exact[0] < exact[1]:
            self.error("E-DOMAIN", path, f"the range [{lo_raw}, {hi_raw}] needs lo < hi")
            return None
        self.record(path, exact, {"authored": copy.deepcopy(value), "value": out, "unit": units.quantity(name).unit},
                    record)
        return out

    def components(self, slot, value, path, accept, record=True):
        allowed = slot.get("components", ["x", "y", "z"])
        out = {}
        for k, v in value.items():
            if k not in allowed:
                self.error("E-KEY-UNKNOWN", path + [k], f'a component object takes {", ".join(allowed)}')
                continue
            if not isinstance(v, str) and not _number(v):
                self.error("E-VALUE-FORM", path + [k], "a component is a quantity string")
                continue
            got = self.leaf_quantity({"quantity": slot["quantity"], "forms": ["QS"]}, v, path + [k], record=record)
            if got is not None:
                out[k] = got
        return out

    @staticmethod
    def _complex_form(qo) -> str:
        return '{"n": .., "k": ..}' if qo.base == "refractive_index" else '{"re": .., "im": ..}'

    @staticmethod
    def _forms_text(forms, qo) -> str:
        words = {"QS": "a quantity string", "TA": "a tagged array", "SL": "a list of at most 3 quantity strings",
                 "CO": "a component object", "BD": "a number", "BC": "an integer", "NULL": "null",
                 "MODEL": "a model object", "CX": '{"re": .., "im": ..}', "NK": '{"n": .., "k": ..}',
                 "OBJECT": "an object"}
        listed = [words[f] for f in ("QS", "BD", "BC", "TA", "SL", "CO", "CX", "NK", "MODEL", "OBJECT", "NULL")
                  if f in forms]
        if "QS" in forms and qo.bare and "BD" not in forms:
            listed[0] = "a number"
        return " or ".join(listed) or "no value"

    # records
    def record(self, path, exact, entry, record=True) -> None:
        where = display_path(path)
        if exact is not None:
            self.r.exact[where] = exact
        if record and self.recording:
            self.r.authored[where] = entry.get("authored")
            self.r.inputs[where] = entry

    def spelling_fix(self, path, written, fixed) -> None:
        self.r.spelling_fixes.append({"path": display_path(path), "written": written, "fix": fixed})

    def spelling_check(self, path, value, conversion) -> None:
        if isinstance(value, str) and units.normalize(value) != value:
            self.spelling_fix(path, value, units.normalize(value))

    # after the walk
    def finish(self) -> None:
        self.depth_rules()
        if self.form == "v1" and not self.geometry_errors and isinstance(self.r.si, dict):
            self.version_1()
        self.materials()
        self.study_values()
        self.controls()

    def depth_rules(self) -> None:
        g = self.tree.get("geometry")
        if self.form not in ("rect", "regions") or not isinstance(g, dict):
            return
        dom = g.get("domain")
        three_d = isinstance(dom, dict) and ("zmin" in dom or "zmax" in dom)
        if three_d and "depth" in g:
            self.error("E-KEY-UNKNOWN", ["geometry", "depth"], "a 3D geometry block has no depth")
        elif not three_d and "depth" not in g:
            self.error("E-KEY-MISSING", ["geometry", "depth"], "a planar geometry block gives its depth: a length "
                                                               "such as \"40 mm\", or null for per metre of depth")

    def version_1(self) -> None:
        from .geometry_document import GeometryError, _pick, parse, to_v02
        try:
            model = parse(self.tree)
        except GeometryError as exc:
            self.extend(from_exception(exc), ["geometry"])
            return
        self.r.geometry_model = model
        self.extend([d for d in model.diagnostics if d.code in ("I-PM-ROUNDING", "W-PM-ROUNDING")], ["geometry"])
        units_of = {}
        for cname, comp in model.components.items():
            units_of[f"geometry.components.{cname}"] = comp.length_unit
        for where, k in model.pm_values.items():
            if where not in self.v1_shapes:
                continue
            component = ".".join(where.split(".")[:3])
            self.r.pm[where] = k
            self.r.exact[where] = Fraction(k, 10 ** 12)
            self.r.authored[where] = _lookup(self.tree, reader.split_path(where))
            self.r.inputs[where] = {"authored": copy.deepcopy(self.r.authored[where]), "value": units.pm_to_m(k),
                                    "unit": "m", "length_unit": units_of.get(component)}
            _assign(self.r.si, reader.split_path(where), units.pm_to_m(k))
        for path in self.v1_parameters:
            name = path[2]
            value, kind = model.parameters[name]
            where = display_path(path)
            if path[-1] == "range":
                bounds = [units.convert(v, "length").value if isinstance(v, str) and units.is_quantity_text(v)
                          else float(v) if _number(v) else v for v in _lookup(self.tree, path)]
                _assign(self.r.si, path, bounds)
                continue
            si = float(Fraction(value) / 10 ** 12) if kind == "length" else float(value)
            self.r.exact[where] = Fraction(value) / 10 ** 12 if kind == "length" else Fraction(value)
            self.r.authored[where] = copy.deepcopy(_lookup(self.tree, path))
            self.r.inputs[where] = {"authored": self.r.authored[where], "value": si,
                                    "unit": "m" if kind == "length" else "1"}
            _assign(self.r.si, path, si)
        if len(model.components) == 1:
            comp = _pick(model, None)
            homogeneous = not comp.features and "material" not in comp.background
            if comp.dimension == "3d" or homogeneous:
                try:
                    self.r.geometry_flat = to_v02(model, validation=True)
                except GeometryError as exc:
                    self.extend(from_exception(exc), ["geometry"])

    def materials(self) -> None:
        from .materials import datum_diagnostic, resolve_reference
        policy = self.table.policy()
        local = self.tree.get("materials") if isinstance(self.tree.get("materials"), dict) else {}
        for path, value in self.refs:
            where = display_path(path)
            target, found = resolve_reference(value, local, where, policy.get("library", "none"))
            self.extend(found, path)
            if target is None:
                continue
            self.r.refs[where] = target
            if target[0] == "library":
                datum = datum_diagnostic(target[1], where)
                if datum is not None:
                    self.add(datum, path)
        reads = policy.get("reads")
        if reads is None:
            return
        physics = self.tree.get("physics") if isinstance(self.tree.get("physics"), dict) else {}
        types = {p.get("type") for p in physics.values() if isinstance(p, dict)}
        wanted = set().union(*(set(reads.get(t, ())) for t in types)) if types else set()
        for mname, record in local.items():
            if not isinstance(record, dict):
                continue
            for key in record:
                if key in slots.MATERIAL_PROPERTIES and key not in wanted:
                    path = ["materials", mname, key]
                    self.add(Diagnostic("I-UNUSED-PROPERTY", display_path(path),
                                        f"no physics of this run reads {key}; it is checked and not used"), path)

    def study_values(self) -> None:
        study = self.tree.get("study")
        if not isinstance(study, dict) or "values" not in study:
            return
        where = ["study", "values"]
        parameter = study.get("parameter")
        if not isinstance(parameter, str):
            self.error("E-KEY-MISSING", ["study", "parameter"], "study.values needs study.parameter, the dotted path "
                                                                 "of the swept value")
            return
        segments = parameter.split(".")
        slot = None
        if segments[0] == "physics" and _lookup(self.tree, segments) is not _MISSING:
            found = self.table.match(segments, self.tree)
            slot = found[0] if len(found) == 1 else None
        if slot is None:
            self.error("E-CONTRACT", ["study", "parameter"], f"{parameter!r} names no value under physics. of this "
                                                             "document; only a physics value can be swept")
            return
        values = study["values"]
        if slot["kind"] == "enum":
            if not isinstance(values, list) or not all(v in slot["values"] for v in values):
                self.error("E-VALUE-FORM", where, f"study.values of {parameter} are a list of {slot['values']}")
                return
            _assign(self.r.si, where, list(values))
            return
        if slot["kind"] not in ("quantity", "material_property"):
            self.error("E-CONTRACT", ["study", "parameter"], f"{parameter!r} is not a value that can be swept")
            return
        qo = units.quantity(slot["quantity"])
        if not qo.bare and (isinstance(values, list) or (isinstance(values, dict) and "unit" not in values)):
            self.error("E-UNIT-MISSING", where, f"study.values of {parameter} ({qo.name}) carry their unit: write a "
                                                f'tagged array such as {{"unit": "{qo.menu[0]}", "values": [...]}}')
            return
        if not isinstance(values, (list, dict)):
            self.error("E-VALUE-FORM", where, "study.values is a tagged array or a list")
            return
        data = values if isinstance(values, dict) else {"values": values}
        if isinstance(values, list) and len(values) > 0 and not all(_number(v) for v in values):
            self.error("E-VALUE-FORM", where, "study.values is a list of numbers here")
            return
        c = units.convert_array(data, qo.name, path=display_path(where))
        self.extend(c.diagnostics, where)
        if not c.ok:
            return
        if not c.entries:
            self.error("E-VALUE-FORM", where, "study.values needs at least one value")
            return
        out = [int(e.exact) if qo.kind == "count" else e.value for e in c.entries]
        raw = values["values"] if isinstance(values, dict) else values
        for i, e in enumerate(c.entries):
            point = display_path(where + [i])
            self.r.exact[point] = e.exact
            self.r.inputs[point] = {"authored": copy.deepcopy(raw[i]), "value": out[i], "unit": qo.unit}
        _assign(self.r.si, where, out)

    def controls(self) -> None:
        mesh = self.tree.get("mesh")
        controls = mesh.get("controls") if isinstance(mesh, dict) else None
        if not isinstance(controls, list) or not controls:
            return
        if self.form != "v1":
            self.error("E-CONTRACT", ["mesh", "controls"], "mesh.controls needs a version 1 geometry block with a 2D "
                                                           "region component; a flat geometry block has no selections "
                                                           "to control")
            return
        grading = {"near", "far", "refinement_distance"}
        for i, entry in enumerate(controls):
            if not isinstance(entry, dict):
                continue
            keys = set(entry) - {"select"}
            path = ["mesh", "controls", i]
            if keys & grading and keys != grading:
                self.error("E-CONTRACT", path, f"a distance grading needs near, far and refinement_distance together, "
                                               f"got {sorted(keys)}")
            elif not keys & grading and (len(keys) != 1 or not keys <= {"circle_segment_count", "element_size"}):
                self.error("E-CONTRACT", path, f"expected circle_segment_count, element_size, or near+far+"
                                               f"refinement_distance, got {sorted(keys)}")
            n = entry.get("circle_segment_count")
            if isinstance(n, int) and not isinstance(n, bool) and n < 8:
                self.error("E-DOMAIN", path + ["circle_segment_count"], f"{n} is below 8, meshine's floor")


def _lookup(tree, segments):
    node = tree
    for s in segments:
        if isinstance(node, dict) and isinstance(s, str) and s in node:
            node = node[s]
        elif isinstance(node, list) and isinstance(s, int) and 0 <= s < len(node):
            node = node[s]
        else:
            return _MISSING
    return node


def _assign(tree, segments, value) -> None:
    node = tree
    for s in segments[:-1]:
        if isinstance(node, dict) and s in node and node[s] is not None:
            node = node[s]
        elif isinstance(node, list) and isinstance(s, int) and s < len(node) and node[s] is not None:
            node = node[s]
        else:
            return
    if isinstance(node, (dict, list)):
        try:
            node[segments[-1]] = value
        except (IndexError, TypeError):
            pass


# -- the document ---------------------------------------------------------------------------------

def _build(result: Resolution) -> None:
    """Build the Document, run the kind's validation and the cross-checks."""
    from .checks import cross_checks
    from .diagnostics import CodedError
    from .schema import Document
    errors_before = bool(result.diagnostics.errors)
    doc = Document._from_resolution(result)
    result._document = doc
    if errors_before:
        return
    try:
        result.kind.validate(doc)
    except CodedError as exc:
        result.diagnostics.extend(from_exception(exc))
    cross_checks(result, doc)
