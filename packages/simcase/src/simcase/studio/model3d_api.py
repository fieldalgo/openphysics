# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The experimental Studio 3D view's server side: display triangles and section outlines.

``/api/model3d/display`` answers a display tessellation of a ``3d`` component, built here from
the exact region complex of ``simcase.geometry_engine3d`` (boxes and slab layers, stage 5
slice 1). It is not the mesh: every face of the complex is an axis-aligned polygon, split exactly
into rectangles (pm integers) and each rectangle into two triangles, so every triangle lies on its
face's plane, inside its polygon, and carries that face's id; each face lists its provenance
names. ``/api/model3d/section`` answers the outline where a plane x, y or z = const cuts the faces.

Arrays are little-endian and base64 encoded: float32 positions in metres from the domain centre
(each from its exact pm value), uint32 triangle indices, and the face id of each triangle. The
answer is deterministic: no set or dict order of the engine reaches it unsorted. Refusals carry
the engine's own words (``E-3D-COMBINATION`` names the feature).
"""

from __future__ import annotations

import base64
from fractions import Fraction
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from simcase import GeometryError, display_complex3d, parse_geometry
from .bodies import RequestRefused, diagnostics, exact_json, read_envelope

STATIC = Path(__file__).parent / "static"
PM = 10 ** 12
AXES = "xyz"
router = APIRouter()
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
# The view's own files; a request only selects one of these fixed paths by name.
ASSETS = {name: (STATIC / name, mime) for name, mime in (
    ("model3d-via-stack.json", "application/json"),)}


def install(app) -> None:
    """Add the routes to ``app`` as plain routes (as ``geometry_api.install`` does)."""
    for route in router.routes:
        app.add_api_route(route.path, route.endpoint, methods=list(route.methods),
                          include_in_schema=route.include_in_schema)


# ----------------------------------------------------------------------------- the complex

def complex_of(doc: dict, component: str | None = None):
    """``(model, component, complex)`` of a document's ``3d`` component (the first one if none is
    named), through the public ``simcase.display_complex3d``: for a component holding one layers
    feature (meshed through meshine.extrude) it is the complex the meshloom route would build."""
    geometry = doc.get("geometry") if isinstance(doc, dict) else None
    if isinstance(doc, dict) and doc.get("openphysics") == "0.3" and \
            (not isinstance(geometry, dict) or "version" not in geometry):
        raise GeometryError("the document has a flat geometry block (no version); the region complex needs a "
                            "version 1 block (see docs/packages/simcase/geometry_document.md)")
    model = parse_geometry(doc)
    if component is None:
        solid = [n for n, c in model.components.items() if c.dimension == "3d"]
        if not solid:
            names = ", ".join(repr(n) for n in model.components)
            raise GeometryError(f"the document has no 3d component ({names}): the 3D view takes 3d components; "
                                "2d and axisymmetric ones are drawn by the geometry lab")
        component = solid[0]
    cx = display_complex3d(model, component)
    return model, model.components[cx.component], cx


def _rectangles(face) -> list[tuple[int, int, int, int]]:
    """The face's polygon as disjoint rectangles (u0, u1, v0, v1) in pm, u < v the other two axes.

    Exact: the grid of all loop coordinates, a cell kept when its centre is inside (even-odd over
    every loop edge), cells merged into runs along u, equal runs merged along v."""
    ua, va = (i for i in range(3) if i != face.axis)
    us = sorted({p[ua] for loop in face.loops for p in loop})
    vs = sorted({p[va] for loop in face.loops for p in loop})
    edges = [((p[ua], p[va]), (q[ua], q[va])) for loop in face.loops for p, q in zip(loop, loop[1:] + loop[:1])]
    upright = [(a[0], min(a[1], b[1]), max(a[1], b[1])) for a, b in edges if a[0] == b[0]]

    def inside(cu2, cv2):                       # doubled centre coordinates: exact integers
        return sum(1 for u, lo, hi in upright if 2 * u > cu2 and 2 * lo < cv2 < 2 * hi) % 2 == 1

    open_runs: dict = {}
    out = []
    for j in range(len(vs) - 1):
        runs, i = [], 0
        cv2 = vs[j] + vs[j + 1]
        while i < len(us) - 1:
            if inside(us[i] + us[i + 1], cv2):
                k = i
                while k + 1 < len(us) - 1 and inside(us[k + 1] + us[k + 2], cv2):
                    k += 1
                runs.append((us[i], us[k + 1]))
                i = k + 1
            else:
                i += 1
        still = {}
        for run in runs:
            still[run] = open_runs.pop(run, vs[j])
        for (u0, u1), v0 in open_runs.items():
            out.append((u0, u1, v0, vs[j]))
        open_runs = still
    for (u0, u1), v0 in open_runs.items():
        out.append((u0, u1, v0, vs[-1]))
    return sorted(out, key=lambda r: (r[2], r[0], r[3], r[1]))


def tessellate(cx) -> list[tuple[int, list, list]]:
    """``(face index, pm vertices, triangles)`` of every face of the complex, in face order."""
    out = []
    for face in cx.faces:
        ua, va = (i for i in range(3) if i != face.axis)
        index: dict = {}
        vertices: list = []
        triangles: list = []

        def vertex(u, v):
            if (u, v) not in index:
                p = [0, 0, 0]
                p[face.axis], p[ua], p[va] = face.coord, u, v
                index[(u, v)] = len(vertices)
                vertices.append(tuple(p))
            return index[(u, v)]
        for u0, u1, v0, v1 in _rectangles(face):
            a, b, c, d = vertex(u0, v0), vertex(u1, v0), vertex(u1, v1), vertex(u0, v1)
            triangles += [(a, b, c), (a, c, d)]
        out.append((face.index, vertices, triangles))
    return out


# ----------------------------------------------------------------------------- the answers

def _b64(array: np.ndarray, dtype: str) -> str:
    return base64.b64encode(np.ascontiguousarray(array, dtype=np.dtype(dtype).newbyteorder("<")).tobytes()).decode()


def _frame(cx):
    """Twice the domain centre (pm, exact) and a converter of pm points to float32 metres from it."""
    origin2 = [cx.domain[k + "min"] + cx.domain[k + "max"] for k in AXES]
    return origin2, lambda p: [float(Fraction(2 * p[i] - origin2[i], 2 * PM)) for i in range(3)]


def _material(material):
    return material if material is None or isinstance(material, str) else "(homogeneous)"


def display_view(doc: dict, component: str | None = None) -> dict:
    """The display answer of one ``3d`` component; raises ``GeometryError`` on a refusal."""
    model, comp, cx = complex_of(doc, component)
    unit = float(comp.pm_per_unit)
    origin2, to_m = _frame(cx)
    positions, indices, owner, faces = [], [], [], []
    for face_index, vertices, triangles in tessellate(cx):
        face = cx.faces[face_index]
        base = len(positions)
        positions += [to_m(p) for p in vertices]
        first = len(owner)
        indices += [[base + i for i in t] for t in triangles]
        owner += [face_index] * len(triangles)
        regions = [sorted({cx.cells[c].region for c in side}) for side in face.sides]
        faces.append({"id": face_index, "axis": AXES[face.axis], "at": float(Fraction(face.coord) / comp.pm_per_unit),
                      "names": sorted(face.provenance), "minus": regions[0], "plus": regions[1],
                      "exterior": face.exterior, "tag": face.tag,
                      "area": float(Fraction(face.area) / comp.pm_per_unit ** 2),
                      "first_triangle": first, "triangle_count": len(triangles)})
    edges, edge_faces = [], []
    for face in cx.faces:
        for loop in face.loops:
            for p, q in zip(loop, loop[1:] + loop[:1]):
                edges += [to_m(p), to_m(q)]
                edge_faces.append(face.index)
    regions = []
    for name in cx.region_names():
        mine = [c for c in cx.cells if c.region == name]
        regions.append({"name": name, "material": _material(mine[0].material), "void": mine[0].void,
                        "volume": float(Fraction(cx.volume_of_region(name)) / comp.pm_per_unit ** 3),
                        "faces": [f.index for f in cx.faces
                                  if any(cx.cells[c].region == name for c in f.minus | f.plus)]})
    tags: dict = {}
    for f in cx.faces:
        if f.tag:
            tags.setdefault(f.tag, []).append(f.index)
    half = [Fraction(cx.domain[k + "max"] - cx.domain[k + "min"], 2 * PM) for k in AXES]
    return {
        "ok": True, "component": cx.component, "unit": str(comp.length_unit),
        "components": [{"name": n, "dimension": c.dimension} for n, c in model.components.items()],
        "metres_per_unit": unit / PM, "origin_m": [float(Fraction(o, 2 * PM)) for o in origin2],
        "domain": {k: float(Fraction(v) / comp.pm_per_unit) for k, v in sorted(cx.domain.items())},
        "half_extent_m": [float(h) for h in half],
        "regions": regions, "faces": faces,
        "selections": [{"name": n, "kind": kind, "entries": sorted(chosen)}
                       for n, (kind, chosen) in sorted(cx.selections.items())],
        "tags": [{"tag": t, "faces": ids} for t, ids in sorted(tags.items())],
        "counts": {"faces": len(faces), "triangles": len(owner), "vertices": len(positions), "edges": len(edge_faces)},
        "positions": _b64(np.array(positions, dtype=np.float32).reshape(-1, 3), "f4"),
        "indices": _b64(np.array(indices, dtype=np.uint32).reshape(-1, 3), "u4"),
        "triangle_faces": _b64(np.array(owner, dtype=np.uint32), "u4"),
        "edges": _b64(np.array(edges, dtype=np.float32).reshape(-1, 3), "f4"),
        "edge_faces": _b64(np.array(edge_faces, dtype=np.uint32), "u4"),
        "summary": _summary(cx, comp, regions, faces),
    }


def _summary(cx, comp, regions, faces) -> str:
    unit = str(comp.length_unit)
    lines = [f"component {cx.component} (3d, {unit}): {len(regions)} regions, {len(cx.cells)} cells, "
             f"{len(faces)} faces, z levels " + ", ".join(f"{float(Fraction(z) / comp.pm_per_unit):g}" for z in cx.levels)]
    for r in regions:
        lines.append(f"  region {r['name']}: {'void' if r['void'] else r['material']}, volume {r['volume']:g} {unit}^3")
    for f in faces:
        lines.append(f"  face {f['id']}: {f['axis']} = {f['at']:g}, area {f['area']:g} {unit}^2, "
                     + " ".join(f["names"]) + (f" [tag {f['tag']}]" if f["tag"] else ""))
    return "\n".join(lines)


def section_view(doc: dict, component: str | None, axis: str, at) -> dict:
    """The outline where the plane ``axis = at`` (document units) cuts the faces; ``GeometryError``
    when the plane is outside the domain or the document is refused."""
    model, comp, cx = complex_of(doc, component)
    a = AXES.index(axis)
    at_pm = round(Fraction(str(at)) * comp.pm_per_unit)
    lo, hi = cx.domain[axis + "min"], cx.domain[axis + "max"]
    unit = str(comp.length_unit)
    if not lo <= at_pm <= hi:
        raise GeometryError(f"section {axis} = {at} {unit} is outside the domain of {cx.component!r} "
                            f"({float(Fraction(lo) / comp.pm_per_unit):g} to {float(Fraction(hi) / comp.pm_per_unit):g} {unit})")
    origin2, to_m = _frame(cx)
    segments, owner = [], []
    for face in cx.faces:
        if face.axis == a:
            continue
        ua, va = (i for i in range(3) if i != face.axis)
        along = va if ua == a else ua
        spans = []
        for u0, u1, v0, v1 in _rectangles(face):
            (c0, c1), (s0, s1) = ((u0, u1), (v0, v1)) if ua == a else ((v0, v1), (u0, u1))
            if c0 <= at_pm <= c1:
                spans.append((s0, s1))
        for s0, s1 in _union(spans):
            p, q = [0, 0, 0], [0, 0, 0]
            p[face.axis] = q[face.axis] = face.coord
            p[a] = q[a] = at_pm
            p[along], q[along] = s0, s1
            segments.append([to_m(p), to_m(q)])
            owner.append(face.index)
    cut = sorted({c.region for c in cx.cells if _cell_spans(cx, c, a, at_pm)})
    return {"ok": True, "component": cx.component, "unit": unit, "axis": axis, "at": at,
            "faces": sorted(set(owner)), "regions": cut,
            "segments": _b64(np.array(segments, dtype=np.float32).reshape(-1, 2, 3), "f4"),
            "segment_faces": _b64(np.array(owner, dtype=np.uint32), "u4")}


def _union(spans):
    out = []
    for s0, s1 in sorted(spans):
        if out and s0 <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], s1))
        else:
            out.append((s0, s1))
    return out


def _cell_spans(cx, cell, a, at_pm) -> bool:
    """Whether the cell meets the plane (its bounding faces reach both sides or touch it)."""
    if cell.void:
        return False
    coords = [p[a] for f in cx.faces if cell.index in f.minus | f.plus for loop in f.loops for p in loop]
    return bool(coords) and min(coords) <= at_pm <= max(coords)


# ----------------------------------------------------------------------------- the routes

def _reply(fn, *args) -> dict:
    try:
        return fn(*args)
    except GeometryError as exc:
        return {"ok": False, "refused": str(exc)}


async def _read(request: Request, optional=("component",)):
    tree, found = read_envelope(await request.body(), optional=optional)
    component = tree.get("component")
    if component is not None and not isinstance(component, str):
        raise RequestRefused("component: a component name is a string")
    return tree, found


def _found(found) -> dict:
    return {"ok": False, "refused": "; ".join(f"{d.path or '<document>'}: {d.message} ({d.code})" for d in found),
            "diagnostics": diagnostics(found)}


@router.get("/api/model3d/display")
async def model3d_display_card():
    """The display answer of the shipped card document ("Via in a layer stack")."""
    import json
    doc = json.loads((STATIC / "model3d-via-stack.json").read_text(encoding="utf-8"))
    return exact_json(await run_in_threadpool(_reply, display_view, doc, None))


@router.post("/api/model3d/display")
async def model3d_display(request: Request):
    try:
        tree, found = await _read(request)
    except RequestRefused as exc:
        return exc.reply()
    if found:
        return exact_json(_found(found))
    return exact_json(await run_in_threadpool(_reply, display_view, tree["doc"], tree.get("component")))


@router.post("/api/model3d/section")
async def model3d_section(request: Request):
    try:
        tree, found = await _read(request, optional=("component", "axis", "at"))
        axis, at = tree.get("axis"), tree.get("at")
        if axis not in ("x", "y", "z"):
            raise RequestRefused("axis: the section plane is x, y or z = const")
        if isinstance(at, bool) or not isinstance(at, (int, float)) and type(at).__name__ != "Decimal":
            raise RequestRefused("at: the plane's position is a number in the component's length unit")
    except RequestRefused as exc:
        return exc.reply()
    if found:
        return exact_json(_found(found))
    return exact_json(await run_in_threadpool(_reply, section_view, tree["doc"], tree.get("component"), axis, at))


@router.get("/model3d-assets/{filename}")
def model3d_asset(filename: str):
    entry = ASSETS.get(filename)
    if entry is None:
        raise HTTPException(404, "Unknown 3D view asset")
    path, mime = entry
    return FileResponse(path, media_type=mime, headers=NO_STORE)
