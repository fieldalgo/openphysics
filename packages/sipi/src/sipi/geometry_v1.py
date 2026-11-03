# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A cross-section as a version 1 geometry block (the simcase geometry document contract).

``to_geometry_v1`` writes a ``CrossSection`` in the form of
``docs/packages/simcase/geometry_document.md``: one ``2d`` component in metres whose
features are the layers bottom-up, then the local dielectric regions, then the traces
in trace order. Later features win, which reproduces sipi's rule that a region cuts
the layers it lies in and a conductor cuts the dielectric. The block is a plain
dictionary; sipi does not depend on the reader that checks it.

Coordinates that sipi derives (a trace's lower-left corner, the height of a layer
interface) are written exactly: as a number when the double holds the value, as an
exact decimal string otherwise. Values sipi was given are written as given, so the
reader rounds only residues that are already in the input.
"""

from __future__ import annotations

import re
from fractions import Fraction

from .crosssection import CrossSection, Trace
from .polygons import PolygonTrace

__all__ = ["to_geometry_v1"]

#: The id grammar and reserved ids of the contract (simcase.geometry_document); a
#: test keeps this copy equal to the reader's.
ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
RESERVED_IDS = frozenset(
    ["background", "domain", "exterior", "outer", "void", "axis", "left", "right", "bottom", "top"]
    + [f"{a}{b}" for a in "xyz" for b in "01"]
    + [f"{a}{b}" for a in "xyz" for b in ("min", "max")])

#: The material name every conductor carries; sipi treats conductors as metal.
CONDUCTOR = "conductor"


def _exact(value) -> Fraction:
    return Fraction(repr(float(value)))


def _write(value: Fraction):
    """A JSON number when the double is exact, otherwise the exact decimal as a string."""
    as_float = float(value)
    if Fraction(repr(as_float)) == value:
        return as_float
    num, den = value.numerator, value.denominator
    digits = 0
    while den % 10:
        num, den = num * 10, den * 10
    while den > 1:
        den //= 10
        digits += 1
    sign = "-" if num < 0 else ""
    text = str(abs(num)).rjust(digits + 1, "0")
    return f"{sign}{text[:-digits]}.{text[-digits:]}" if digits else f"{sign}{text}"


def _ident(name: str, prefix: str, index: int, used: set) -> dict:
    fid = name if ID_RE.match(name) and name.lower() not in RESERVED_IDS else f"{prefix}{index}"
    if fid.lower() in used:
        fid = f"{prefix}{index}"
    used.add(fid.lower())
    return {} if fid == name else {"id": fid}


def to_geometry_v1(section: CrossSection) -> dict:
    """The version 1 document parts of ``section``.

    Returns ``{"units", "geometry", "materials", "conductors", "boundaries", "renamed"}``:
    ``units`` and ``geometry`` form a document's geometry; ``materials`` maps each layer
    and region name to its ``eps_r`` and ``tan_delta`` (and ``conductor`` to metal);
    ``conductors`` lists the signal and ground traces in trace order by region name;
    ``boundaries`` holds the box flags; ``renamed`` maps a trace whose name a layer or
    region already uses to its region name in the block.
    """
    if not isinstance(section, CrossSection):
        raise TypeError("section must be a CrossSection")
    half = _exact(section.width) / 2
    features, used, materials, renamed = [], set(), {}, {}
    y = Fraction(0)
    for i, lay in enumerate(section.layers):
        t = _exact(lay.thickness)
        features.append({"name": lay.name, **_ident(lay.name, "layer", i, used), "type": "rect",
                         "x": _write(-half), "y": _write(y), "w": _write(2 * half), "h": lay.thickness,
                         "material": lay.name})
        materials[lay.name] = {"eps_r": lay.eps_r, "tan_delta": lay.tan_delta}
        y += t
    height = y
    for i, reg in enumerate(section.dielectric_regions):
        features.append({"name": reg.name, **_ident(reg.name, "region", i, used), "type": "polygon",
                         "points": [list(p) for p in reg.vertices], "material": reg.name})
        materials[reg.name] = {"eps_r": reg.eps_r, "tan_delta": reg.tan_delta}
    signals, grounds = [], []
    dielectric = {f["name"] for f in features}
    for i, tr in enumerate(section.traces):
        name = tr.name if tr.name not in dielectric else f"{tr.name}-trace"
        if name != tr.name:
            renamed[tr.name] = name
        feature = {"name": name, **_ident(name, "trace", i, used)}
        if isinstance(tr, PolygonTrace):
            feature.update(type="polygon", points=[list(p) for p in tr.vertices])
        elif tr.thickness == 0:
            x0 = _exact(tr.x) - _exact(tr.width) / 2
            feature.update(type="segment", points=[[_write(x0), tr.y], [_write(x0 + _exact(tr.width)), tr.y]])
        elif isinstance(tr, Trace) and tr.tapered:
            feature.update(type="trapezoid", cx=tr.x, y=tr.y, w=tr.width, w_top=tr.top_width, h=tr.thickness)
        else:
            feature.update(type="rect", x=_write(_exact(tr.x) - _exact(tr.width) / 2), y=tr.y, w=tr.width,
                           h=tr.thickness)
        if feature["type"] != "segment":
            feature["material"] = CONDUCTOR
        features.append(feature)
        (grounds if tr.ground else signals).append(name)
    if any(t.thickness > 0 or isinstance(t, PolygonTrace) for t in section.traces):
        materials[CONDUCTOR] = {"conductor": True}
    component = {"dimension": "2d",
                 "domain": {"xmin": _write(-half), "xmax": _write(half), "ymin": 0, "ymax": _write(height)},
                 "background": {"material": None}, "features": features, "finalize": "later_wins"}
    return {"units": {"length": "m"}, "geometry": {"version": 1, "components": {"section": component}},
            "materials": materials, "conductors": {"signals": signals, "ground": grounds},
            "boundaries": {"bottom": section.bottom, "top": section.top, "sides": section.sides},
            "renamed": renamed}
