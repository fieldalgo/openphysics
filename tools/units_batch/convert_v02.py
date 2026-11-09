# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Convert an ``"openphysics": "0.2"`` document to the ``"0.3"`` format of the units batch.

    python tools/units_batch/convert_v02.py old.json [-o new.json] [--check]

A closed rule table: every key a 0.2 validator accepts is renamed, given its unit, or refused
here by name; an unknown key is an error, never copied. The rules:

- ``"openphysics": "0.3"``; ``units`` goes. ``units.length`` becomes ``geometry.length_unit``
  (flat blocks) or ``geometry.components.<c>.length_unit`` (version 1), and every planar
  component gets ``depth: null`` (per metre of depth, today's meaning);
- a value that carried its unit in the key name (``_k``, ``_w_mk``, ``_pa``, ...) is written as
  ``"<repr digits> <canonical unit>"``; a document length (mesh sizes, wavelengths, PML,
  bend, Gaussian and Sellmeier lengths, ``study.values`` of a wavelength sweep, length
  parameters) keeps its number in the old ``units.length`` when that unit is on the quantity's
  menu, else the same exact value in a menu unit. Shape numbers stay bare;
- the two ``outward_`` inputs become ``inward_heat_flux`` and ``inward_current_density`` with
  the value ``0.0 - x``; cavity ``[re, im]`` becomes ``{"re": re, "im": 0.0 - im}``
  (exp(-i omega t)); Sellmeier ``C`` becomes ``resonance_wavelength_squared`` in the length unit
  squared and ``range: [0, hi]`` becomes ``valid.vacuum_wavelength: [null, hi]``;
- defaults that carried a dimension are written: the em wavelength (1.55 document units), the
  em mesh size (0.2), the em background (``physmat:vacuum``), ``bend.bend_origin`` (0) and the
  Joule ``iteration.temperature_tolerance`` (1e-8 K);
- library material names (em only) are written ``physmat:<Name>``; local names equal to a
  library name are renamed (``SiO2`` -> ``oxide``, ``Si`` -> ``silicon``);
- a value outside the registry's plausibility band (``W-MAGNITUDE``) is written as an
  annotated value with an ``accept`` reason.

``--check`` converts every written quantity back through ``physmat.units`` and requires its
exact value to equal the old value (SI keys: the same double; lengths: the old number times
the old unit, exactly), and every count to be an integer. Covered: all nine kinds in every
form the shipped examples and the harness fixtures use (flat rectangle, flat regions,
version 1 2d and axisymmetric components, the cavity box). The reader of the 0.3 format does
not exist yet: whether a converted document resolves to the old SI tree (P2-2) is checked by
each kind's commit.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path

FORMAT = "0.3"
LENGTH_UNITS = ("pm", "nm", "Angstrom", "um", "mm", "cm", "m", "in", "mil")
D24_RENAMES = {"SiO2": "oxide", "Si": "silicon"}
ACCEPT_REASON = "value carried over from the 0.2 document"


class ConversionError(ValueError):
    """A 0.2 document, or one of its keys, that this closed table does not convert."""


def _units():
    """physmat.units of this checkout (the registry the converted documents are read with)."""
    source = Path(__file__).resolve().parents[2] / "packages" / "physmat" / "src"
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    import physmat.units as units
    return units


def _library():
    source = Path(__file__).resolve().parents[2] / "packages" / "physmat" / "src"
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    import physmat
    return physmat


# -- numbers and quantity strings ---------------------------------------------------------------

def _digits(x) -> str:
    """The shortest decimal of a JSON number that reads back as the same double (repr digits)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ConversionError(f"expected a number, found {x!r}")
    if isinstance(x, int):
        return str(x)
    if not math.isfinite(x):
        raise ConversionError(f"{x!r} is not finite")
    text = repr(float(x))
    return text[:-2] if text.endswith(".0") else text


def _exact(x) -> Fraction:
    return Fraction(_digits(x))


def _decimal(value: Fraction) -> str | None:
    """A terminating decimal text of ``value``, or None."""
    d = value.denominator
    twos = fives = 0
    while d % 2 == 0:
        d //= 2
        twos += 1
    while d % 5 == 0:
        d //= 5
        fives += 1
    if d != 1:
        return None
    scale = max(twos, fives)
    n = value * 10 ** scale
    sign = "-" if n < 0 else ""
    digits = str(abs(int(n))).rjust(scale + 1, "0")
    text = digits if scale == 0 else f"{digits[:-scale]}.{digits[-scale:]}".rstrip("0").rstrip(".")
    if len(text) > 12 and "." not in text:
        stripped = text.rstrip("0")
        text = f"{stripped}e{len(text) - len(stripped)}"
    elif text.startswith("0.") and len(text) > 10:
        mantissa = text[2:].lstrip("0")
        exponent = len(text) - 2 - len(mantissa) + 1
        text = f"{mantissa[0]}{'.' + mantissa[1:] if len(mantissa) > 1 else ''}e-{exponent}"
    return sign + text


class Writer:
    """Writes quantity strings and records what each must resolve to, for ``--check``."""

    def __init__(self, length_unit: str):
        self.length_unit = length_unit
        self.expected: list = []          # (path, text or value, quantity, expected exact or float)
        self.notes: list[str] = []

    def si(self, value, unit: str, quantity: str, path: str, *, negate: bool = False):
        """A value whose 0.2 key carried its SI unit."""
        number = (0.0 - float(value)) if negate else value
        text = f"{_digits(number)} {unit}"
        self.expected.append((path, text, quantity, ("double", float(number))))
        return text

    def length(self, value, quantity: str, path: str, power: int = 1):
        """A document length, read today in ``units.length`` (to the power ``power``)."""
        exact = _exact(value) * _length_factor(self.length_unit) ** power
        text = _spell(exact, self.length_unit, quantity, power)
        self.expected.append((path, text, quantity, ("exact", exact)))
        return text

    def lengths(self, values, quantity: str, path: str) -> dict:
        """A tagged array of document lengths, in one unit."""
        exacts = [_exact(v) * _length_factor(self.length_unit) for v in values]
        unit = _common_unit(exacts, self.length_unit, quantity)
        factor = _length_factor(unit)
        out = {"unit": unit, "values": [_number_of(e / factor) for e in exacts]}
        for i, e in enumerate(exacts):
            self.expected.append((f"{path}.values[{i}]", f"{_decimal(e / factor)} {unit}", quantity, ("exact", e)))
        return out


def _length_factor(unit: str) -> Fraction:
    exact = _units().convert(f"1 {unit}", "length").exact
    if exact is None:
        raise ConversionError(f"length unit {unit!r} is not known")
    return exact


def _accepted(text: str, quantity: str) -> bool:
    c = _units().convert(text, quantity)
    return c.ok and not any(d.code.startswith("E-") for d in c.diagnostics)


def _spell(exact: Fraction, preferred: str, quantity: str, power: int = 1) -> str:
    """``exact`` (SI) in the preferred length unit when its menu takes it, else in a menu unit
    in which it is a terminating decimal."""
    candidates = [preferred] + [u for u in LENGTH_UNITS if u != preferred]
    for unit in candidates:
        factor = _length_factor(unit) ** power
        text = _decimal(exact / factor)
        if text is None:
            continue
        spelled = f"{text} {unit}" + (f"^{power}" if power != 1 else "")
        if _accepted(spelled, quantity):
            return spelled
    raise ConversionError(f"no unit on the menu of {quantity} writes {exact} m^{power} exactly")


def _common_unit(exacts, preferred: str, quantity: str) -> str:
    for unit in [preferred] + [u for u in LENGTH_UNITS if u != preferred]:
        factor = _length_factor(unit)
        if all(_decimal(e / factor) is not None for e in exacts) and \
                all(_accepted(f"{_decimal(e / factor)} {unit}", quantity) for e in exacts):
            return unit
    raise ConversionError(f"no single unit on the menu of {quantity} writes {exacts} exactly")


def _number_of(value: Fraction):
    """The JSON number of an exact decimal: an int when whole, else the float of its text."""
    return int(value) if value.denominator == 1 else float(_decimal(value))


def _count(value, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise ConversionError(f"{path}: {value!r} is not a whole count")
    return int(value)


def _closed(obj: dict, allowed, path: str):
    if not isinstance(obj, dict):
        raise ConversionError(f"{path}: expected an object")
    extra = sorted(set(obj) - set(allowed))
    if extra:
        raise ConversionError(f"{path}: keys {extra} are not in the conversion table")


# -- kinds --------------------------------------------------------------------------------------

HEAT = {"thermal.steady2d", "thermal.transient2d"}
ELECTRIC = {"electric.steady2d", "joule.steady2d", "joule.temperature2d"}
MECHANICS = {"mechanics.elasticity2d", "mechanics.thermoelastic2d"}
EM = {"em.modes2d"}
CAVITY = {"em.cavity3d"}


def _kind(doc: dict) -> str:
    types = {p.get("type") for p in (doc.get("physics") or {}).values() if isinstance(p, dict)}
    if len(types) != 1:
        raise ConversionError(f"expected one physics type, found {sorted(map(str, types))}")
    (kind,) = types
    if kind not in HEAT | ELECTRIC | MECHANICS | EM | CAVITY:
        raise ConversionError(f"physics type {kind!r} is not in the conversion table")
    return kind


# -- geometry -------------------------------------------------------------------------------------

def _material_ref(name, local: dict, kind: str, path: str):
    """A material reference: a local name (D-24 renames applied) or, in em kinds, a library name."""
    if name is None:
        return None
    if not isinstance(name, str):
        raise ConversionError(f"{path}: expected a material name")
    if name in local:
        return D24_RENAMES.get(name, name) if kind in EM else name
    if kind in EM:
        try:
            return "physmat:" + _library().get(name).name
        except KeyError:
            raise ConversionError(f"{path}: {name!r} is neither local nor a library material") from None
    if kind in CAVITY and name == "vacuum":
        return "physmat:vacuum"
    raise ConversionError(f"{path}: material {name!r} has no local record")


def _selector(select, local, kind, path):
    """Selections keep their structure; a material selector names a reference as written."""
    if isinstance(select, dict):
        return {k: (_material_ref(v, local, kind, f"{path}.{k}") if k == "material" else _selector(v, local, kind,
                                                                                                    f"{path}.{k}"))
                for k, v in select.items()}
    if isinstance(select, list):
        return [_selector(v, local, kind, f"{path}[{i}]") for i, v in enumerate(select)]
    return select


SHAPE_KEYS = {"name", "type", "material", "x", "y", "w", "h", "cx", "cy", "r", "points", "xmin", "xmax", "ymin",
              "ymax", "zmin", "zmax"}


def _flat_geometry(g: dict, w: Writer, local: dict, kind: str) -> dict:
    three_d = kind in CAVITY
    _closed(g, {"domain", "background", "shapes"}, "geometry")
    out = {"length_unit": w.length_unit}
    if not three_d:
        out["depth"] = None
    out["domain"] = dict(g["domain"])
    if "background" in g:
        bg = g["background"]
        _closed(bg, {"material", "mesh_size"}, "geometry.background")
        out["background"] = {}
        for k, v in bg.items():
            if k == "material":
                out["background"]["material"] = _material_ref(v, local, kind, "geometry.background.material")
            else:
                out["background"]["element_size"] = w.length(v, "element_size", "geometry.background.element_size")
    elif kind in EM:
        out["background"] = {"material": "physmat:vacuum"}
    if kind in EM and "material" not in out.get("background", {}):
        out["background"]["material"] = "physmat:vacuum"
    if "shapes" in g:
        shapes = []
        for i, s in enumerate(g["shapes"]):
            _closed(s, SHAPE_KEYS | {"mesh_size"}, f"geometry.shapes[{i}]")
            new = {}
            for k, v in s.items():
                if k == "mesh_size":
                    new["element_size"] = w.length(v, "element_size", f"geometry.shapes[{i}].element_size")
                elif k == "material":
                    new[k] = _material_ref(v, local, kind, f"geometry.shapes[{i}].material")
                else:
                    new[k] = copy.deepcopy(v)
            shapes.append(new)
        out["shapes"] = shapes
    return out


#: version 1 feature keys (geometry_document._COMMON and _FIELDS_2D/_FIELDS_3D); ``extrude`` profiles
#: and ``layers`` stacks carry nested material references and are not in this table
FEATURE_KEYS = {"id", "name", "region", "type", "material", "x", "y", "w", "h", "cx", "cy", "cz", "r", "points",
                "edges", "w_top", "start", "segments", "xmin", "xmax", "ymin", "ymax", "zmin", "zmax", "axis"}


def _v1_geometry(g: dict, w: Writer, local: dict, kind: str) -> dict:
    _closed(g, {"version", "parameters", "components"}, "geometry")
    out = {"version": g["version"]}
    if "parameters" in g:
        params = {}
        for name, p in g["parameters"].items():
            _closed(p, {"value", "range", "kind"}, f"geometry.parameters.{name}")
            new = dict(p)
            if p.get("kind", "length") == "length":
                if isinstance(p.get("value"), (int, float)) and not isinstance(p.get("value"), bool):
                    new["value"] = w.length(p["value"], "length", f"geometry.parameters.{name}.value")
                if "range" in p:
                    new["range"] = [w.length(v, "length", f"geometry.parameters.{name}.range[{i}]")
                                    if isinstance(v, (int, float)) and not isinstance(v, bool) else v
                                    for i, v in enumerate(p["range"])]
            params[name] = new
        out["parameters"] = params
    components = {}
    for cname, c in g["components"].items():
        base = f"geometry.components.{cname}"
        _closed(c, {"dimension", "domain", "background", "features", "finalize", "selections", "boundary_tags"},
                base)
        new = {}
        for k, v in c.items():
            new[k] = copy.deepcopy(v)
            if k == "dimension":
                new["length_unit"] = w.length_unit
                if v == "2d":
                    new["depth"] = None
        if "background" in c:
            bg = {}
            for k, v in c["background"].items():
                if k == "material":
                    bg[k] = _material_ref(v, local, kind, f"{base}.background.material")
                elif k == "mesh_size":
                    bg["element_size"] = w.length(v, "element_size", f"{base}.background.element_size")
                else:
                    raise ConversionError(f"{base}.background.{k} is not in the conversion table")
            new["background"] = bg
        features = []
        for i, f in enumerate(c.get("features", [])):
            _closed(f, FEATURE_KEYS | {"mesh_size"}, f"{base}.features[{i}]")
            nf = {}
            for k, v in f.items():
                if k == "mesh_size":
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        raise ConversionError(f"{base}.features[{i}].mesh_size: an expression-valued size is "
                                              "refused in 0.3")
                    nf["element_size"] = w.length(v, "element_size", f"{base}.features[{i}].element_size")
                elif k == "material":
                    nf[k] = _material_ref(v, local, kind, f"{base}.features[{i}].material")
                else:
                    nf[k] = copy.deepcopy(v)
            features.append(nf)
        if "features" in c:
            new["features"] = features
        if "selections" in c:
            new["selections"] = _selector(c["selections"], local, kind, f"{base}.selections")
        components[cname] = new
    out["components"] = components
    return out


# -- materials ------------------------------------------------------------------------------------

REGION_MATERIAL = {
    "conductivity_w_mk": ("thermal_conductivity", "W/(m K)"),
    "volumetric_heat_capacity_j_m3k": ("volumetric_heat_capacity", "J/(m^3 K)"),
    "electrical_conductivity_s_m": ("electrical_conductivity", "S/m"),
    "young_modulus_pa": ("youngs_modulus", "Pa"),
    "thermal_expansion_per_k": ("linear_expansion_coefficient", "1/K"),
}


def _materials(materials: dict, w: Writer, kind: str) -> dict:
    out = {}
    for name, spec in materials.items():
        path = f"materials.{name}"
        new_name = D24_RENAMES.get(name, name) if kind in EM else name
        if kind in EM and new_name in _library().names():
            raise ConversionError(f"{path}: a local name equal to a library name has no rename in the table")
        new = {}
        if kind in EM:
            _closed(spec, {"n", "k", "sellmeier", "source"}, path)
            if "n" in spec:
                if "k" in spec:
                    new["refractive_index"] = {"n": spec["n"], "k": spec["k"]}
                else:
                    new["refractive_index"] = spec["n"]
            if "sellmeier" in spec:
                new["refractive_index"] = _sellmeier(spec["sellmeier"], w, f"{path}.refractive_index")
        elif kind in CAVITY:
            _closed(spec, {"relative_permittivity", "relative_permeability", "source"}, path)
            for key in ("relative_permittivity", "relative_permeability"):
                if key in spec:
                    v = spec[key]
                    if isinstance(v, list):
                        if len(v) != 2:
                            raise ConversionError(f"{path}.{key}: expected [re, im]")
                        new[key] = {"re": v[0], "im": 0.0 - float(v[1])}
                        w.expected.append((f"{path}.{key}", new[key], key, ("complex", float(v[0]), 0.0 - float(v[1]))))
                    else:
                        new[key] = v
        else:
            _closed(spec, set(REGION_MATERIAL) | {"poisson_ratio", "source"}, path)
            for key, value in spec.items():
                if key in REGION_MATERIAL:
                    quantity, unit = REGION_MATERIAL[key]
                    new[quantity] = w.si(value, unit, quantity, f"{path}.{quantity}")
                elif key == "poisson_ratio":
                    new[key] = value
        if "source" in spec:
            new["source"] = spec["source"]
        out[new_name] = new
    return out


def _sellmeier(s: dict, w: Writer, path: str) -> dict:
    _closed(s, {"A", "B", "C", "range"}, path)
    if len(s["B"]) != len(s["C"]):
        raise ConversionError(f"{path}: B and C differ in length")
    out = {"model": "sellmeier"}
    if "A" in s:
        out["constant"] = s["A"]
    out["terms"] = [{"strength": b, "resonance_wavelength_squared":
                     w.length(c, "resonance_wavelength_squared", f"{path}.terms[{i}].resonance_wavelength_squared", 2)}
                    for i, (b, c) in enumerate(zip(s["B"], s["C"]))]
    if "range" in s:
        lo, hi = s["range"]
        out["valid"] = {"vacuum_wavelength": [
            None if float(lo) == 0.0 else w.length(lo, "vacuum_wavelength", f"{path}.valid.vacuum_wavelength[0]"),
            w.length(hi, "vacuum_wavelength", f"{path}.valid.vacuum_wavelength[1]")]}
    out["reference_medium"] = "vacuum"
    return out


# -- physics --------------------------------------------------------------------------------------

def _bmap(values: dict, unit: str, quantity: str, w: Writer, path: str, *, negate=False) -> dict:
    if not isinstance(values, dict):
        raise ConversionError(f"{path}: expected an object")
    return {b: w.si(v, unit, quantity, f"{path}.{b}", negate=negate) for b, v in values.items()}


def _convection(conv: dict, w: Writer, path: str) -> dict:
    out = {}
    for b, c in conv.items():
        _closed(c, {"h_w_m2k", "ambient_temperature_k"}, f"{path}.{b}")
        out[b] = {}
        for k, v in c.items():
            if k == "h_w_m2k":
                out[b]["heat_transfer_coefficient"] = w.si(v, "W/(m^2 K)", "heat_transfer_coefficient",
                                                           f"{path}.{b}.heat_transfer_coefficient")
            else:
                out[b]["ambient_temperature"] = w.si(v, "K", "ambient_temperature", f"{path}.{b}.ambient_temperature")
    return out


def _source(value, w: Writer, path: str):
    if isinstance(value, dict):
        return {r: w.si(v, "W/m^3", "heat_source_density", f"{path}.{r}") for r, v in value.items()}
    return w.si(value, "W/m^3", "heat_source_density", path)


def _temperatures(values: dict, w: Writer, path: str) -> dict:
    out = {}
    for b, v in values.items():
        if isinstance(v, dict):
            _closed(v, {"values_k"}, f"{path}.{b}")
            out[b] = {"unit": "K", "values": list(v["values_k"])}
            for i, x in enumerate(v["values_k"]):
                w.expected.append((f"{path}.{b}.values[{i}]", f"{_digits(x)} K", "prescribed_temperature",
                                   ("double", float(x))))
        else:
            out[b] = w.si(v, "K", "prescribed_temperature", f"{path}.{b}")
    return out


def _vector(values, unit: str, quantity: str, w: Writer, path: str) -> list:
    if not isinstance(values, list):
        raise ConversionError(f"{path}: expected a list")
    return [w.si(v, unit, quantity, f"{path}[{i}]") for i, v in enumerate(values)]


#: rectangle and region keys of the heat, electric, Joule and mechanics entries: 0.2 key ->
#: (new key, how). ``how`` is a unit for a scalar SI value, or the name of a converter.
PHYSICS_RULES = {
    "conductivity_w_mk": ("thermal_conductivity", ("si", "W/(m K)", "thermal_conductivity")),
    "thermal_conductivity_w_mk": ("thermal_conductivity", ("si", "W/(m K)", "thermal_conductivity")),
    "volumetric_heat_capacity_j_m3k": ("volumetric_heat_capacity", ("si", "J/(m^3 K)", "volumetric_heat_capacity")),
    "heat_source_w_m3": ("heat_source_density", "source"),
    "dirichlet_temperature_k": ("prescribed_temperature", "temperatures"),
    "outward_flux_w_m2": ("inward_heat_flux", ("negated", "W/m^2", "inward_heat_flux")),
    "convection": ("convection", "convection"),
    "initial_temperature_k": ("initial_temperature", "initial"),
    "conductivity_s_m": ("electrical_conductivity", ("si", "S/m", "electrical_conductivity")),
    "dirichlet_potential_v": ("prescribed_electric_potential", ("bmap", "V", "prescribed_electric_potential")),
    "outward_current_a_m2": ("inward_current_density", ("negated", "A/m^2", "inward_current_density")),
    "conductivity_model": ("electrical_conductivity", "model"),
    "iteration": ("iteration", "iteration"),
    "plane": ("plane", "copy"),
    "young_modulus_pa": ("youngs_modulus", ("si", "Pa", "youngs_modulus")),
    "poisson_ratio": ("poisson_ratio", "copy"),
    "thermal_expansion_per_k": ("linear_expansion_coefficient", ("si", "1/K", "linear_expansion_coefficient")),
    "reference_temperature_k": ("stress_free_temperature", ("si", "K", "stress_free_temperature")),
    "displacement_m": ("prescribed_displacement", "displacement"),
    "traction_pa": ("traction", "traction"),
    "body_force_n_m3": ("body_force_density", ("vector", "N/m^3", "body_force_density")),
    "pressure_pa": ("gauge_pressure", ("bmap", "Pa", "gauge_pressure")),
    "type": ("type", "copy"),
}


def _physics_entry(name: str, p: dict, w: Writer, kind: str) -> dict:
    path = f"physics.{name}"
    _closed(p, PHYSICS_RULES, path)
    out = {}
    for key, value in p.items():
        new_key, how = PHYSICS_RULES[key]
        where = f"{path}.{new_key}"
        if how == "copy":
            out[new_key] = copy.deepcopy(value)
        elif how == "source":
            out[new_key] = _source(value, w, where)
        elif how == "temperatures":
            out[new_key] = _temperatures(value, w, where)
        elif how == "convection":
            out[new_key] = _convection(value, w, where)
        elif how == "initial":
            out[new_key] = _initial(value, w, where)
        elif how == "model":
            out[new_key] = _conductivity_model(value, w, where)
        elif how == "iteration":
            out[new_key] = _iteration(value, w, where)
        elif how == "displacement":
            out[new_key] = {b: {c: w.si(v, "m", "prescribed_displacement", f"{where}.{b}.{c}")
                                for c, v in comps.items()} for b, comps in value.items()}
        elif how == "traction":
            out[new_key] = {b: _vector(v, "Pa", "traction", w, f"{where}.{b}") for b, v in value.items()}
        elif how[0] == "si":
            out[new_key] = w.si(value, how[1], how[2], where)
        elif how[0] == "bmap":
            out[new_key] = _bmap(value, how[1], how[2], w, where)
        elif how[0] == "negated":
            out[new_key] = _bmap(value, how[1], how[2], w, where, negate=True)
        elif how[0] == "vector":
            out[new_key] = _vector(value, how[1], how[2], w, where)
    if kind == "joule.temperature2d" and "iteration" not in out:
        out["iteration"] = _iteration({}, w, f"{path}.iteration")
    return out


def _initial(value, w: Writer, path: str):
    if isinstance(value, dict):
        _closed(value, {"type", "origin_temperature_k", "gradient_k_per_m"}, path)
        return {"type": value["type"],
                "reference_temperature": w.si(value["origin_temperature_k"], "K", "reference_temperature",
                                              f"{path}.reference_temperature"),
                "temperature_gradient": _vector(value["gradient_k_per_m"], "K/m", "temperature_gradient", w,
                                                f"{path}.temperature_gradient")}
    return w.si(value, "K", "initial_temperature", path)


def _conductivity_model(model: dict, w: Writer, path: str) -> dict:
    _closed(model, {"type", "reference_conductivity_s_m", "reference_temperature_k", "alpha_per_k",
                    "temperature_range_k"}, path)
    lo, hi = model["temperature_range_k"]
    return {"model": model["type"],
            "reference_conductivity": w.si(model["reference_conductivity_s_m"], "S/m", "reference_conductivity",
                                           f"{path}.reference_conductivity"),
            "reference_temperature": w.si(model["reference_temperature_k"], "K", "reference_temperature",
                                          f"{path}.reference_temperature"),
            "resistivity_temperature_coefficient": w.si(model["alpha_per_k"], "1/K",
                                                        "resistivity_temperature_coefficient",
                                                        f"{path}.resistivity_temperature_coefficient"),
            "valid": {"temperature": [w.si(lo, "K", "temperature", f"{path}.valid.temperature[0]"),
                                      w.si(hi, "K", "temperature", f"{path}.valid.temperature[1]")]}}


def _iteration(it: dict, w: Writer, path: str) -> dict:
    _closed(it, {"relaxation", "temperature_atol_k", "relative_tolerance", "max_iterations"}, path)
    out = {}
    if "relaxation" in it:
        out["relaxation_factor"] = it["relaxation"]
    out["temperature_tolerance"] = w.si(it.get("temperature_atol_k", 1e-8), "K", "temperature_tolerance",
                                        f"{path}.temperature_tolerance")
    if "relative_tolerance" in it:
        out["relative_tolerance"] = it["relative_tolerance"]
    if "max_iterations" in it:
        out["iteration_limit"] = _count(it["max_iterations"], f"{path}.iteration_limit")
    return out


EM_PHYSICS = {"type", "formulation", "wavelength", "num_modes", "n_target", "n_cladding", "boundary", "pml", "bend"}


def _em_entry(name: str, p: dict, w: Writer) -> dict:
    path = f"physics.{name}"
    _closed(p, EM_PHYSICS, path)
    out = {"type": p["type"]}
    if "formulation" in p:
        out["formulation"] = p["formulation"]
    out["vacuum_wavelength"] = w.length(p.get("wavelength", 1.55), "vacuum_wavelength", f"{path}.vacuum_wavelength")
    if "wavelength" not in p:
        w.notes.append(f"{path}.vacuum_wavelength: today's default 1.55 {w.length_unit} written")
    if "num_modes" in p:
        out["mode_count"] = _count(p["num_modes"], f"{path}.mode_count")
    if "n_target" in p:
        out["target_effective_index"] = p["n_target"]
    if "n_cladding" in p:
        if p.get("formulation", "scalar") == "vector":
            out["effective_index_threshold"] = p["n_cladding"]
        else:
            w.notes.append(f"{path}.n_cladding: unused by the scalar formulation and refused in 0.3; dropped")
    if "boundary" in p:
        out["boundary"] = dict(p["boundary"])
    if "pml" in p:
        pml = p["pml"]
        _closed(pml, {"thickness", "strength", "order", "min_physical_fraction"}, f"{path}.pml")
        new = {"pml_thickness": {s: w.length(v, "pml_thickness", f"{path}.pml.pml_thickness.{s}")
                                 for s, v in pml["thickness"].items() if float(v) != 0.0}}
        if "strength" in pml:
            new["pml_strength"] = pml["strength"]
        if "order" in pml:
            new["pml_order"] = _count(pml["order"], f"{path}.pml.pml_order")
        if "min_physical_fraction" in pml:
            new["pml_minimum_physical_fraction"] = pml["min_physical_fraction"]
        out["pml"] = new
    if "bend" in p:
        bend = p["bend"]
        _closed(bend, {"radius", "origin", "axis"}, f"{path}.bend")
        new = {"bend_radius": w.length(bend["radius"], "bend_radius", f"{path}.bend.bend_radius"),
               "bend_origin": w.length(bend.get("origin", 0.0), "bend_origin", f"{path}.bend.bend_origin")}
        if "axis" in bend:
            new["axis"] = bend["axis"]
        out["bend"] = new
    return out


def _cavity_entry(name: str, p: dict, w: Writer) -> dict:
    path = f"physics.{name}"
    _closed(p, {"type", "boundary", "search", "target_frequency_hz", "num_modes"}, path)
    out = {}
    for key, value in p.items():
        if key == "target_frequency_hz":
            out["target_frequency"] = w.si(value, "Hz", "target_frequency", f"{path}.target_frequency")
        elif key == "num_modes":
            out["mode_count"] = _count(value, f"{path}.mode_count")
        elif key == "boundary" and isinstance(value, dict):
            _closed(value, {"conductivity_s_per_m"}, f"{path}.boundary")
            sigma, where = value["conductivity_s_per_m"], f"{path}.boundary.electrical_conductivity"
            out["boundary"] = {"electrical_conductivity":
                               _bmap(sigma, "S/m", "electrical_conductivity", w, where) if isinstance(sigma, dict)
                               else w.si(sigma, "S/m", "electrical_conductivity", where)}
        else:
            out[key] = copy.deepcopy(value)
    return out


# -- mesh, study, results -----------------------------------------------------------------------

def _mesh(mesh: dict, w: Writer, kind: str) -> dict:
    _closed(mesh, {"subdivisions", "size", "min_angle", "grading", "controls"}, "mesh")
    out = {}
    for key, value in mesh.items():
        if key == "subdivisions":
            out["subdivision_count"] = [_count(v, f"mesh.subdivision_count[{i}]") for i, v in enumerate(value)]
        elif key == "size":
            out["element_size"] = w.length(value, "element_size", "mesh.element_size")
        elif key == "min_angle":
            out["minimum_angle"] = f"{_digits(value)} deg"
            w.expected.append(("mesh.minimum_angle", out["minimum_angle"], "minimum_angle", ("degrees", float(value))))
        elif key == "grading":
            _closed(value, {"center", "near", "far", "distance"}, "mesh.grading")
            out["grading"] = {"position": [w.length(c, "position", f"mesh.grading.position[{i}]")
                                           for i, c in enumerate(value["center"])],
                              "near": w.length(value["near"], "element_size", "mesh.grading.near"),
                              "far": w.length(value["far"], "element_size", "mesh.grading.far"),
                              "refinement_distance": w.length(value["distance"], "refinement_distance",
                                                              "mesh.grading.refinement_distance")}
        elif key == "controls":
            controls = []
            for i, c in enumerate(value):
                base = f"mesh.controls[{i}]"
                _closed(c, {"select", "size", "near", "far", "distance", "circle_segments"}, base)
                new = {}
                for k, v in c.items():
                    if k == "select":
                        new[k] = copy.deepcopy(v)
                    elif k == "size":
                        new["element_size"] = w.length(v, "element_size", f"{base}.element_size")
                    elif k in ("near", "far"):
                        new[k] = w.length(v, "element_size", f"{base}.{k}")
                    elif k == "distance":
                        new["refinement_distance"] = w.length(v, "refinement_distance", f"{base}.refinement_distance")
                    elif k == "circle_segments":
                        new["circle_segment_count"] = _count(v, f"{base}.circle_segment_count")
                controls.append(new)
            out["controls"] = controls
    if kind in EM and "element_size" not in out:
        out["element_size"] = w.length(0.2, "element_size", "mesh.element_size")
        w.notes.append(f"mesh.element_size: today's em default 0.2 {w.length_unit} written")
    return out


def _study(study: dict, w: Writer, physics_names) -> dict:
    _closed(study, {"type", "time_s", "parameter", "values", "tracking"}, "study")
    out = {}
    for key, value in study.items():
        if key == "time_s":
            out["time"] = {"unit": "s", "values": list(value)}
            for i, t in enumerate(value):
                w.expected.append((f"study.time.values[{i}]", f"{_digits(t)} s", "time", ("double", float(t))))
        elif key == "parameter":
            parts = str(value).split(".")
            if len(parts) == 3 and parts[0] == "physics" and parts[1] in physics_names and parts[2] == "wavelength":
                out["parameter"] = f"physics.{parts[1]}.vacuum_wavelength"
            else:
                raise ConversionError(f"study.parameter {value!r} is not in the conversion table")
        elif key == "values":
            if str(study.get("parameter", "")).endswith(".wavelength"):
                out["values"] = w.lengths(value, "vacuum_wavelength", "study.values")
            else:
                out["values"] = list(value)
        elif key == "tracking":
            out["tracking"] = _tracking(value)
        else:
            out[key] = copy.deepcopy(value)
    return out


TRACKING = {"method": "method", "search_modes": "search_mode_count", "min_overlap": "mode_tracking_threshold",
            "min_margin": "mode_tracking_margin_threshold", "degeneracy_tolerance": "degeneracy_tolerance",
            "cluster_span_max": "cluster_span_tolerance", "external_gap_min": "cluster_gap_threshold"}


def _tracking(tracking: dict) -> dict:
    _closed(tracking, TRACKING, "study.tracking")
    return {TRACKING[k]: (_count(v, "study.tracking.search_mode_count") if k == "search_modes" else v)
            for k, v in tracking.items()}


def _results(results: dict, w: Writer) -> dict:
    _closed(results, {"save_fields", "plots", "mode_overlap"}, "results")
    out = {}
    for key, value in results.items():
        if key == "mode_overlap":
            _closed(value, {"gaussian"}, "results.mode_overlap")
            g = value["gaussian"]
            _closed(g, {"waist", "center"}, "results.mode_overlap.gaussian")
            out[key] = {"gaussian": {
                "beam_waist_radius": w.length(g["waist"], "beam_waist_radius",
                                              "results.mode_overlap.gaussian.beam_waist_radius"),
                "position": [w.length(c, "position", f"results.mode_overlap.gaussian.position[{i}]")
                             for i, c in enumerate(g["center"])]}}
        else:
            out[key] = value
    return out


# -- the document ---------------------------------------------------------------------------------

def _length_unit(units: dict) -> str:
    if not isinstance(units, dict) or "length" not in units:
        raise ConversionError("units.length is missing")
    unit = units["length"]
    if isinstance(unit, dict):
        size = unit.get("in_m")
        for name in LENGTH_UNITS:
            if isinstance(size, (int, float)) and _exact(size) == _length_factor(name):
                return name
        raise ConversionError(f"units.length {unit!r} is no length unit of the 0.3 menu")
    aliases = {"µm": "um", "μm": "um", "Å": "Angstrom", "angstrom": "Angstrom"}
    unit = aliases.get(unit, unit)
    if unit not in LENGTH_UNITS:
        raise ConversionError(f"units.length {unit!r} is no length unit of the 0.3 menu")
    for key, want in (("temperature", "K"), ("time", "s")):
        if key in units and units[key] != want:
            raise ConversionError(f"units.{key} {units[key]!r}: 0.2 documents take only {want!r}")
    extra = set(units) - {"length", "temperature", "time"}
    if extra:
        raise ConversionError(f"units: keys {sorted(extra)} are not in the conversion table")
    return unit


def convert(doc: dict) -> tuple[dict, Writer]:
    """The 0.3 document of a 0.2 document, and the writer holding what each value must resolve to."""
    if not isinstance(doc, dict) or doc.get("openphysics") not in ("0.2", 0.2):
        raise ConversionError("not an openphysics 0.2 document")
    _closed(doc, {"openphysics", "name", "units", "geometry", "materials", "physics", "mesh", "study", "results"},
            "<document>")
    kind = _kind(doc)
    w = Writer(_length_unit(doc.get("units")))
    local = doc.get("materials") or {}
    out = {}
    for key, value in doc.items():
        if key == "openphysics":
            out[key] = FORMAT
        elif key == "units":
            continue
        elif key == "geometry":
            out[key] = (_v1_geometry if "version" in value else _flat_geometry)(value, w, local, kind)
        elif key == "materials":
            out[key] = _materials(value, w, kind)
        elif key == "physics":
            out[key] = {n: (_em_entry(n, p, w) if kind in EM else _cavity_entry(n, p, w) if kind in CAVITY
                            else _physics_entry(n, p, w, kind)) for n, p in value.items()}
        elif key == "mesh":
            out[key] = _mesh(value, w, kind)
        elif key == "study":
            out[key] = _study(value, w, set(doc["physics"]))
        elif key == "results":
            out[key] = _results(value, w)
        else:
            out[key] = copy.deepcopy(value)
    if kind in EM and "mesh" not in out:
        out["mesh"] = _mesh({}, w, kind)
    _annotate(out, w)
    return out, w


def _annotate(doc: dict, w: Writer):
    """Wrap each value the registry band warns about (W-MAGNITUDE) as an annotated value."""
    units = _units()
    for path, text, quantity, _ in w.expected:
        if not isinstance(text, str):
            continue
        c = units.convert(text, quantity)
        if any(d.code == "W-MAGNITUDE" for d in c.diagnostics):
            parent, key = _locate(doc, path)
            if parent is not None and parent[key] == text:
                parent[key] = {"value": text, "accept": {"W-MAGNITUDE": ACCEPT_REASON}}
                w.notes.append(f"{path}: {text} is outside the plausibility band; written with accept")


def _locate(doc, path: str):
    """(container, key) of a dotted path with [i] indices, as the writer records them."""
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    node = doc
    for part in parts[:-1]:
        node = node[int(part[1:-1])] if part.startswith("[") else node.get(part) if isinstance(node, dict) else None
        if node is None:
            return None, None
    last = parts[-1]
    key = int(last[1:-1]) if last.startswith("[") else last
    try:
        node[key]
    except (KeyError, IndexError, TypeError):
        return None, None
    return node, key


def check(w: Writer) -> list[str]:
    """Problems: a written value that does not read, or that does not resolve to the old value."""
    units = _units()
    problems = []
    for path, text, quantity, (how, *want) in w.expected:
        if how == "complex":
            if text != {"re": want[0], "im": want[1]} or (float.hex(text["im"]) != float.hex(want[1])):
                problems.append(f"{path}: {text} is not the conjugate of the old value")
            continue
        c = units.convert(text, quantity)
        if not c.ok:
            problems.append(f"{path}: {text!r} does not read as {quantity}: {c.error.code} {c.error.message}")
            continue
        if how == "double" and float.hex(c.value) != float.hex(want[0]):
            problems.append(f"{path}: {text!r} gives {c.value!r}, not the old {want[0]!r}")
        elif how == "exact" and c.exact != want[0]:
            problems.append(f"{path}: {text!r} is {c.exact} m, not the old {want[0]}")
        elif how == "degrees" and (c.number_text is None or float(Fraction(c.number_text)) != want[0]
                                   or c.unit_text != "deg"):
            problems.append(f"{path}: {text!r} does not hand meshine the old {want[0]!r} degrees")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("document", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="write the 0.3 document here (default: print it)")
    parser.add_argument("--check", action="store_true", help="read every written value back through physmat.units")
    args = parser.parse_args(argv)
    try:
        new, w = convert(json.loads(args.document.read_text(encoding="utf-8")))
    except ConversionError as exc:
        print(f"error: {args.document.name}: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    for note in w.notes:
        print(f"note: {note}", file=sys.stderr)
    if args.check:
        problems = check(w)
        for problem in problems:
            print(f"check: {problem}", file=sys.stderr)
        print(f"checked {len(w.expected)} values: {len(problems)} problems", file=sys.stderr)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
