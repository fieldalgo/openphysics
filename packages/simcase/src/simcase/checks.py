# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cross-checks of a resolved format 0.3 document, before anything is meshed.

One extent line per geometry component comes first; it says what the numbers mean, in the
component's ``length_unit`` and in metres, so a slip such as millimetres declared as metres
is visible before any warning. Then the scale checks the tagged element size makes possible
(rule 2.2), each at the component's path:

- ``E-MESH-ESTIMATE``: the estimated triangle count, N = 2A/h^2 over the domain plus the same
  for every shape, feature or mesh control with its own size, plus the radial grading,
  exceeds ``mesh.element_count_limit``; the message names a ``length_unit`` that would give
  a sane count;
- ``W-GEOMETRY-SCALE``: N below 10; the millimetres-as-metres pattern (``length_unit`` m,
  every shape number a whole number, a diagonal above 10 m); for waveguide modes, a smallest
  feature outside 1e-3..1e3 vacuum wavelengths or a domain above 1e4 of them;
- ``W-CAVITY-SCALE``: cavity size times target frequency over c outside 0.1..100;
- ``W-DEPTH-RATIO``: depth over the in-plane diagonal outside 1e-6..1e6;
- ``W-CELSIUS-AS-KELVIN``: an absolute temperature written in K or mK below 150 K while
  another one of the document is at least 250 K.

A geometry-level warning is acknowledged by ``accept`` on its block or component; a value's
warning by an annotated value. Errors cannot be acknowledged.
"""

from __future__ import annotations

import math
from fractions import Fraction

from physmat import units
from physmat.units import Diagnostic, Suggestion

from .diagnostics import acknowledge

SPEED_OF_LIGHT = 299792458.0


def _g(x) -> str:
    text = format(float(x), ".6g")
    return text


def _about(n: float) -> str:
    """A count to two significant digits: ``about 490``, ``about 4.5e+08``."""
    if n >= 1e6:
        return f"{n:.2g}"
    if n >= 100:
        return str(int(round(n, 2 - len(str(int(n))))))
    return str(int(round(n))) if n >= 1 else _g(n)


class _Component:
    """What the checks need of one component, all lengths in metres."""

    def __init__(self, path, unit, dimension, extents_pm, depth, depth_written, shapes, background_size,
                 shape_numbers_pm, features=()):
        self.path, self.unit, self.dimension = path, unit, dimension
        self.extents_pm = extents_pm            # [(min_pm, max_pm), ...] per axis
        self.extents = [(_m(lo), _m(hi)) for lo, hi in extents_pm]
        self.depth, self.depth_written = depth, depth_written
        self.shapes = shapes                    # [(area_m2 or None, smallest side m or None, size m or None, name)]
        self.background_size = background_size
        self.shape_numbers_pm = shape_numbers_pm
        self.features = features

    @property
    def sides(self) -> list[float]:
        return [hi - lo for lo, hi in self.extents]

    @property
    def area(self) -> float:
        return self.sides[0] * self.sides[1]

    @property
    def diagonal(self) -> float:
        return math.sqrt(sum(s * s for s in self.sides))


def _m(k: int) -> float:
    return float(Fraction(k, 10 ** 12))


def _polygon_area(points) -> float:
    n = len(points)
    return abs(sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
                   for i in range(n))) / 2


def _flat(result) -> list[_Component]:
    tree, pm, si = result.tree, result.pm, result.si
    g, gs = tree["geometry"], si.get("geometry") or {}
    axes = [a for a in "xyz" if f"geometry.domain.{a}min" in pm and f"geometry.domain.{a}max" in pm]
    extents = [(pm[f"geometry.domain.{a}min"], pm[f"geometry.domain.{a}max"]) for a in axes]
    shapes = []
    for i, s in enumerate(gs.get("shapes") or []):
        if not isinstance(s, dict):
            continue
        size = s.get("element_size")
        t = s.get("type")
        area = side = None
        try:
            if t == "rect":
                area, side = s["w"] * s["h"], min(s["w"], s["h"])
            elif t == "circle":
                area, side = math.pi * s["r"] ** 2, 2 * s["r"]
            elif t == "polygon":
                pts = s["points"]
                area = _polygon_area(pts)
                side = min(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
            elif t == "box":
                side = min(s[f"{a}max"] - s[f"{a}min"] for a in "xyz")
        except (KeyError, TypeError, IndexError, ValueError):
            pass
        shapes.append((area, side, size if isinstance(size, float) else None, s.get("name", f"shapes[{i}]")))
    background = (gs.get("background") or {}).get("element_size")
    numbers = [k for path, k in pm.items() if path.startswith("geometry.")]
    dimension = "3d" if len(axes) == 3 else "2d"
    return [_Component("geometry", gs.get("length_unit"), dimension, extents, gs.get("depth"), g.get("depth"),
                       shapes, background if isinstance(background, float) else None, numbers)]


def _version_1(result) -> list[_Component]:
    from .geometry_document import _feature_extent
    out = []
    model = result.geometry_model
    for cname, comp in model.components.items():
        path = f"geometry.components.{cname}"
        axes = [a for a in "xyz" if f"{a}min" in comp.domain]
        extents = [(comp.domain[f"{a}min"], comp.domain[f"{a}max"]) for a in axes]
        shapes = []
        for f in comp.features:
            d, area = f.data, None
            if f.type == "rect":
                area = _m(d["w"]) * _m(d["h"])
            elif f.type == "circle":
                area = math.pi * _m(d["r"]) ** 2
            elif f.type == "polygon":
                area = _polygon_area([(_m(x), _m(y)) for x, y in d["points"]])
            elif f.type == "trapezoid":
                area = (_m(d["w"]) + _m(d["w_top"])) / 2 * _m(d["h"])
            side = _feature_extent(f)
            shapes.append((area, None if side is None else _m(side),
                           None if f.mesh_size is None else _m(f.mesh_size), f.region))
        bg = comp.background.get("mesh_size")
        numbers = [k for p, k in model.pm_values.items() if p.startswith(path + ".")
                   and ".element_size" not in p]
        out.append(_Component(path, comp.length_unit, comp.dimension, extents, comp.depth, comp.depth_written,
                              shapes, None if bg is None else _m(bg), numbers, comp.features))
    return out


def components(result) -> list[_Component]:
    """The geometry components of a resolved document (empty when its geometry did not resolve)."""
    g = result.tree.get("geometry") if isinstance(result.tree, dict) else None
    if not isinstance(g, dict) or not isinstance(result.si, dict):
        return []
    if "version" in g:
        return _version_1(result) if result.geometry_model is not None else []
    try:
        return _flat(result)
    except (KeyError, TypeError):
        return []


def _quantity_values(result, name: str) -> list[tuple[str, object]]:
    return [(path, c) for path, c in result.conversions.items() if c.quantity == name]


def _mesh(result) -> dict:
    mesh = result.si.get("mesh") if isinstance(result.si, dict) else None
    return mesh if isinstance(mesh, dict) else {}


def estimate(result, comp: _Component) -> float | None:
    """The estimated triangle count of a 2D component, or None without an element size."""
    mesh = _mesh(result)
    h = mesh.get("element_size")
    if not isinstance(h, float) or comp.dimension == "3d" or len(comp.extents) < 2:
        return None
    if comp.background_size is not None:
        h = min(h, comp.background_size)
    n = 2 * comp.area / h ** 2
    for area, _side, size, _name in comp.shapes:
        if size is not None and area is not None:
            n += 2 * area / size ** 2
    for control in mesh.get("controls") or []:
        size = control.get("element_size") if isinstance(control, dict) else None
        if isinstance(size, float):
            select = control.get("select")
            areas = [a for a, _s, _h, name in comp.shapes if name == select and a is not None]
            n += 2 * (sum(areas) if areas else comp.area) / size ** 2
    grading = mesh.get("grading")
    if isinstance(grading, dict) and all(isinstance(grading.get(k), float) for k in ("near", "far",
                                                                                      "refinement_distance")):
        a, far, d = grading["near"], grading["far"], grading["refinement_distance"]
        b = (far - a) / d
        if b == 0:
            disc = 2 * math.pi * d * d / (a * a)
        else:
            disc = 4 * math.pi * ((math.log(a + b * d) + a / (a + b * d)) - (math.log(a) + 1)) / (b * b)
        n += disc + 2 * max(comp.area - math.pi * d * d, 0.0) / far ** 2
    return n


def _unit_factor(unit: str) -> Fraction:
    return Fraction(units.length_to_pm(1, unit).picometres, 10 ** 12)


def _better_unit(comp: _Component, n: float, limit: float) -> str | None:
    """A length_unit in which the same shape numbers give a count inside [10, limit]."""
    here = _unit_factor(comp.unit)
    best = None
    for unit in units.LENGTH_UNITS:
        ratio = float(_unit_factor(unit) / here)
        count = n * ratio * ratio
        if 10 <= count <= limit:
            score = abs(math.log10(count) - math.log10(math.sqrt(10 * limit)))
            if best is None or score < best[0]:
                best = (score, unit, count)
    return None if best is None else f"{best[1]} (about {_about(best[2])} triangles)"


def _shown_extent(result, comp: _Component) -> str:
    unit = comp.unit
    shown = (result.si.get("display_units") or {}).get("length") if isinstance(result.si, dict) else None
    shown = shown or unit
    factor = _unit_factor(shown)
    sides = " x ".join(f"{_g(Fraction(hi - lo, 10 ** 12) / factor)} {shown}" for lo, hi in comp.extents_pm)
    metres = " x ".join(f"{_g(s)} m" for s in comp.sides)
    return f"{sides} = {metres}"


def _line(result, comp: _Component) -> str:
    head = f"{comp.path} (length_unit {comp.unit}" + (f", {comp.dimension}" if comp.path != "geometry" else "") + "): "
    parts = [_shown_extent(result, comp)]
    if comp.dimension == "2d":
        if comp.depth is None:
            parts.append("depth per metre (null)")
        else:
            written = comp.depth_written.get("value") if isinstance(comp.depth_written, dict) else comp.depth_written
            parts.append(f"depth {written} = {_g(comp.depth)} m")
    mesh, tree_mesh = _mesh(result), (result.tree.get("mesh") or {})
    counts = mesh.get("subdivision_count")
    n = estimate(result, comp)
    if n is not None:
        written = tree_mesh.get("element_size") if isinstance(tree_mesh, dict) else None
        written = written.get("value") if isinstance(written, dict) else written
        parts.append(f"element_size {written}, about {_about(n)} triangles")
    elif isinstance(counts, list) and counts:
        cells = math.prod(counts)
        shape = " x ".join(str(c) for c in counts)
        parts.append(f"subdivision_count {shape} = {2 * cells} triangles" if len(counts) == 2
                     else f"subdivision_count {shape} = {cells} cells")
    ratio = _cavity_ratio(result, comp)
    if ratio is not None:
        parts.append(f"cavity size x f/c = {_g(ratio)}")
    return head + "; ".join(parts)


def _cavity_ratio(result, comp: _Component) -> float | None:
    if comp.dimension != "3d":
        return None
    found = [c.value for path, c in _quantity_values(result, "target_frequency") if path.startswith("physics.")]
    if not found:
        return None
    return max(comp.sides) * found[0] / SPEED_OF_LIGHT


def _accepted(result, path: str, d: Diagnostic) -> Diagnostic:
    reason = (result.accepts.get(path) or {}).get(d.code)
    return acknowledge(d, reason) if reason is not None and d.severity != "error" else d


def cross_checks(result, doc) -> None:
    """Append the extent lines (``result.extent``) and the cross-check diagnostics."""
    found: list[Diagnostic] = []
    comps = components(result)
    result.extent = [_line(result, c) for c in comps]
    mesh = _mesh(result)
    limit = mesh.get("element_count_limit", 600000)
    wavelengths = [c.value for path, c in _quantity_values(result, "vacuum_wavelength") if path.startswith("physics.")]
    for comp in comps:
        if len(comp.extents) < 2:
            continue
        n = estimate(result, comp)
        if n is not None:
            result.estimates[comp.path] = n
            if n > limit:
                better = _better_unit(comp, n, limit)
                found.append(Diagnostic("E-MESH-ESTIMATE", comp.path, (
                    f"about {_about(n)} triangles from the element sizes and the extent in length_unit {comp.unit}; "
                    f"the limit is {limit} (mesh.element_count_limit). "
                    + (f"Written in {better}." if better else "Check length_unit and the element sizes."))))
            elif n < 10:
                found.append(Diagnostic("W-GEOMETRY-SCALE", comp.path, (
                    f"about {_about(n)} triangles: the element size is not small against the extent in length_unit "
                    f"{comp.unit}; check length_unit")))
        if comp.unit == "m" and comp.diagonal > 10 and comp.shape_numbers_pm \
                and all(k % 10 ** 12 == 0 for k in comp.shape_numbers_pm):
            found.append(Diagnostic("W-GEOMETRY-SCALE", comp.path, (
                f"every shape number is a whole number of metres and the diagonal is {_g(comp.diagonal)} m: "
                "millimetres written with length_unit m? Check length_unit")))
        if wavelengths and comp.dimension != "3d":
            lam = min(wavelengths)
            sides = [s for _a, s, _h, _n in comp.shapes if s] or comp.sides[:2]
            small, big = min(sides) / lam, max(comp.sides[:2]) / lam
            if not 1e-3 <= small <= 1e3 or big > 1e4:
                found.append(Diagnostic("W-GEOMETRY-SCALE", comp.path, (
                    f"the smallest feature is {_g(small)} and the domain {_g(big)} vacuum wavelengths "
                    f"({_g(lam)} m); check length_unit")))
        ratio = _cavity_ratio(result, comp)
        if ratio is not None and not 0.1 <= ratio <= 100:
            found.append(Diagnostic("W-CAVITY-SCALE", comp.path, (
                f"cavity size x target frequency / c = {_g(ratio)}, outside 0.1..100: check length_unit and the "
                "target frequency")))
        if comp.dimension == "2d" and comp.depth is not None and comp.diagonal > 0:
            ratio = comp.depth / math.sqrt(comp.sides[0] ** 2 + comp.sides[1] ** 2)
            if not 1e-6 <= ratio <= 1e6:
                found.append(Diagnostic("W-DEPTH-RATIO", f"{comp.path}.depth", (
                    f"depth over the in-plane diagonal is {_g(ratio)}, outside 1e-6..1e6; check the depth's unit")))
    found += _celsius_as_kelvin(result)
    for d in found:
        owner = d.path[:-len(".depth")] if d.path.endswith(".depth") else d.path
        d = _accepted(result, owner, d)
        if d.path.endswith(".value"):
            d = _accepted(result, d.path[:-len(".value")], d)
        result.diagnostics.append(d)


def _celsius_as_kelvin(result) -> list[Diagnostic]:
    temps = [(path, c) for path, c in result.conversions.items()
             if c.value is not None and units.quantity(c.quantity).unit == "K"
             and units.quantity(c.quantity).kind == "absolute"]
    if not any(c.value >= 250 for _p, c in temps):
        return []
    out = []
    for path, c in temps:
        if c.unit_text in ("K", "mK") and c.value < 150:
            hint = f"{c.number_text} degC"
            out.append(Diagnostic("W-CELSIUS-AS-KELVIN", path, (
                f"{c.number_text} {c.unit_text} is {_g(c.value)} K, while another temperature of this document is "
                "at least 250 K: a Celsius value written in K?"),
                suggestions=(Suggestion(hint, c.value, units.convert(hint, c.quantity).value, "K"),)))
    return out
