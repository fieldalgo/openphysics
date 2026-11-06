# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A hand-built ``Domain`` as a version 1 geometry block (the simcase geometry document contract).

A ``Domain`` tiles the plane with named regions whose loops are vertex lists or
``Circle`` objects, with holes. The contract's later-wins features express the same
tiling when each region comes after every region that contains it, and each hole
that no region fills becomes a void feature after its region. ``to_geometry_v1``
writes that order. The block is a plain dictionary; meshine does not depend on the
reader that checks it.

A ``Domain`` carries no unit, so the caller names one. What the contract cannot hold
is left out and said so: a boundary-name callback (pass ``boundary_tags`` yourself)
and region materials (each region's material is its name unless ``materials`` maps
it). ``Circle.n`` goes to ``mesh_controls`` and the default size to ``mesh_size``.
"""

from __future__ import annotations

import re

import numpy as np

from .geometry import Circle, Domain

__all__ = ["to_geometry_v1"]

#: The id grammar and reserved ids of the contract (simcase.geometry_document); a
#: test keeps this copy equal to the reader's.
ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
RESERVED_IDS = frozenset(
    ["background", "domain", "exterior", "outer", "void", "axis", "left", "right", "bottom", "top"]
    + [f"{a}{b}" for a in "xyz" for b in "01"]
    + [f"{a}{b}" for a in "xyz" for b in ("min", "max")])


def _vertices(loop) -> np.ndarray:
    return loop.vertices() if isinstance(loop, Circle) else np.asarray(loop, dtype=float)


def _area(v: np.ndarray) -> float:
    x, y = v[:, 0], v[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _inside(p, poly: np.ndarray) -> bool:
    """Point in polygon, counting the boundary as inside (input data, not exact).

    "On the boundary" is a distance below 1e-12 of the polygon's own diagonal, so the
    answer does not depend on the unit the numbers are written in.
    """
    x, y = p
    tol = 1e-12 * float(np.hypot(*(poly.max(axis=0) - poly.min(axis=0))))
    n, hit = len(poly), False
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        t = min(1.0, max(0.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        if np.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= tol:
            return True
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * dx / dy:
            hit = not hit
    return hit


def _contains(outer: np.ndarray, inner: np.ndarray) -> bool:
    return _area(outer) > _area(inner) and all(_inside(p, outer) for p in inner)


def _shape(loop) -> dict:
    if isinstance(loop, Circle):
        return {"type": "circle", "cx": float(loop.center[0]), "cy": float(loop.center[1]), "r": loop.radius}
    return {"type": "polygon", "points": [[float(x), float(y)] for x, y in np.asarray(loop, dtype=float)]}


def _ident(name: str, used: set) -> dict:
    if ID_RE.match(name) and name.lower() not in RESERVED_IDS and name.lower() not in used:
        used.add(name.lower())
        return {}
    k = len(used)
    while f"f{k}" in used:
        k += 1
    used.add(f"f{k}")
    return {"id": f"f{k}"}


def to_geometry_v1(domain: Domain, *, length_unit, materials: dict | None = None) -> dict:
    """The version 1 document parts of ``domain`` (before ``build``).

    ``length_unit`` is the unit the domain's numbers are in, as a ``units.length``
    declaration (``"um"``, ``"m"``, ``{"in_m": ...}``); it is required. Returns
    ``{"units", "geometry", "mesh_size", "mesh_controls"}``.
    """
    if not isinstance(domain, Domain):
        raise TypeError("domain must be a meshine Domain")
    if length_unit is None:
        raise ValueError("a Domain carries no unit; give length_unit")
    pending = list(domain._pending)
    if not pending:
        raise ValueError("the domain has no regions")
    materials = materials or {}
    outers = [_vertices(loops[0]) for _, loops, _ in pending]
    depth = [sum(_contains(outers[j], outers[i]) for j in range(len(pending)) if j != i)
             for i in range(len(pending))]
    order = sorted(range(len(pending)), key=lambda i: (depth[i], i))
    count: dict[str, int] = {}
    used: set = set()
    features, controls = [], []
    for i in order:
        name, loops, size = pending[i]
        k = count[name] = count.get(name, 0) + 1
        fname = name if k == 1 else f"{name}-{k}"
        f = {"name": fname, **_ident(fname, used), **_shape(loops[0]),
             "material": materials.get(name, name)}
        if fname != name:
            f["region"] = name
        if size is not None:
            f["mesh_size"] = float(size)
        features.append(f)
        if isinstance(loops[0], Circle):
            controls.append({"select": f.get("id", fname), "circle_segments": loops[0].n})
        for h, hole in enumerate(loops[1:], start=1):
            hv = _vertices(hole)
            # A hole that is exactly another region's outer loop is filled by that region,
            # which comes later. Any other hole becomes void here; regions inside it still
            # come later and win.
            if any(j != i and np.isclose(_area(hv), _area(outers[j]), rtol=1e-12)
                   and all(_inside(p, hv) for p in outers[j]) and all(_inside(p, outers[j]) for p in hv)
                   for j in range(len(pending))):
                continue
            vname = f"{fname}-hole{h}"
            features.append({"name": vname, **_ident(vname, used), **_shape(hole), "material": None})
    every = np.vstack(outers)
    lo, hi = every.min(axis=0), every.max(axis=0)
    component = {"dimension": "2d",
                 "domain": {"xmin": float(lo[0]), "xmax": float(hi[0]), "ymin": float(lo[1]), "ymax": float(hi[1])},
                 "background": {"material": None}, "features": features, "finalize": "later_wins"}
    return {"units": {"length": length_unit}, "geometry": {"version": 1, "components": {"domain": component}},
            "mesh_size": domain.default_size, "mesh_controls": controls}
