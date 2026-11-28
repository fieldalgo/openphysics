# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The experimental Studio 3D view's server side: display triangles and section outlines.

``/api/model3d/display`` answers a display tessellation of a ``3d`` component, built here from
the exact region complex of ``simcase.geometry_engine3d`` (boxes and slab layers, stage 5
slice 1). It is not the mesh: every face of the complex is an axis-aligned polygon, split exactly
into rectangles (pm integers) and each rectangle into two triangles, so every triangle lies on its
face's plane, inside its polygon, and carries that face's id; each face lists its provenance
names. ``/api/model3d/section`` answers the outline where a plane x, y or z = const cuts the faces.
A component whose cylinders or spheres are in a meshloom builder shape has no exact complex: its
answers come from ``simcase.display_shapes3d`` (the faces the mesh's provenance names select,
drawn by a display rule of their own) in the same fields.

Arrays are little-endian and base64 encoded: float32 positions in metres from the domain centre
(each from its exact pm value), uint32 triangle indices, and the face id of each triangle. The
answer is deterministic: no set or dict order of the engine reaches it unsorted. Refusals carry
the engine's own words (``E-3D-COMBINATION`` names the feature).
"""

from __future__ import annotations

import base64
import math
import re
from fractions import Fraction
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from simcase import GeometryError, display_complex3d, display_shapes3d, parse_geometry
from .bodies import RequestRefused, diagnostics, exact_json, read_envelope
from . import heat3d_runs, mesh3d_jobs

STATIC = Path(__file__).parent / "static"
PM = 10 ** 12
AXES = "xyz"
router = APIRouter()
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
# The view's own files; a request only selects one of these fixed paths by name.
ASSETS = {name: (STATIC / name, mime) for name, mime in (
    ("model3d-view.mjs", "text/javascript"), ("model3d-model.mjs", "text/javascript"),
    ("model3d-mesh-view.mjs", "text/javascript"), ("model3d-mesh-model.mjs", "text/javascript"),
    ("model3d-via-stack.json", "application/json"), ("model3d-layer-stack-3d.json", "application/json"),
    ("model3d-via-slab-3d.json", "application/json"))}
#: feature types meshed in meshloom's builder shapes; their components are drawn by ``display_shapes3d``
CURVED = ("cylinder", "sphere")


def install(app) -> None:
    """Add the routes to ``app`` as plain routes (as ``geometry_api.install`` does)."""
    for route in [*router.routes, *heat3d_runs.router.routes]:     # the 3D heat run's routes too
        app.add_api_route(route.path, route.endpoint, methods=list(route.methods),
                          include_in_schema=route.include_in_schema)


# ----------------------------------------------------------------------------- the complex

def _model_of(doc: dict, component: str | None):
    """The parsed model and the component's name (the first ``3d`` one if none is named)."""
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
    return model, component


def complex_of(doc: dict, component: str | None = None):
    """``(model, component, complex)`` of a document's ``3d`` component (the first one if none is
    named), through the public ``simcase.display_complex3d``: for a component holding one layers
    feature (meshed through meshine.extrude) it is the complex the meshloom route would build."""
    model, component = _model_of(doc, component)
    cx = display_complex3d(model, component)
    return model, model.components[cx.component], cx


def builder_shapes(model, component: str):
    """``simcase.display_shapes3d`` of a ``3d`` component holding a cylinder or a sphere (refused in
    the builder's words when no builder takes it), else None: that component goes through the complex."""
    comp = model.components.get(component)
    if comp is None or comp.dimension != "3d" or not any(f.type in CURVED for f in comp.features):
        return None
    return display_shapes3d(model, component)


def shapes_of(doc: dict, component: str | None = None):
    """``(model, component, Display3D)`` when the document's ``3d`` component holds cylinders or spheres
    (meshed in a meshloom builder shape), else None."""
    model, name = _model_of(doc, component)
    shapes = builder_shapes(model, name)
    return None if shapes is None else (model, model.components[shapes.component], shapes)


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
    shaped = shapes_of(doc, component)
    if shaped is not None:
        return _display_shapes(*shaped)
    return _display(*complex_of(doc, component))


def _alone(cx) -> dict:
    """Per face, its provenance names that select that face and no other (sorted)."""
    faces_of: dict = {}
    for f in cx.faces:
        for n in f.provenance:
            faces_of.setdefault(n, []).append(f.index)
    return {f.index: [n for n in sorted(f.provenance) if faces_of[n] == [f.index]] for f in cx.faces}


def _display(model, comp, cx) -> dict:
    unit = float(comp.pm_per_unit)
    alone = _alone(cx)
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
                      "names": sorted(face.provenance), "alone": alone[face_index],
                      "minus": regions[0], "plus": regions[1],
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


# ----------------------------------------------------------------------------- the builder's check

_FEATURE = re.compile(r"features\[(\d+)\]")


def _boxes(comp, feature) -> list:
    """The exact pm boxes (x0, x1, y0, y1, z0, z1) a box or a layers feature of slab layers fills."""
    d = feature.data
    if feature.type == "box":
        return [tuple(d[k] for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"))]
    dom = comp.domain
    out, z = [], d["z0"]
    for lay in d["layers"]:
        out.append((dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"], z, z + lay["thickness"]))
        z += lay["thickness"]
    return out


def _overlap(a, b) -> int:
    """The exact volume (pm^3) two boxes share; 0 when they only touch."""
    v = 1
    for i in range(3):
        lo, hi = max(a[2 * i], b[2 * i]), min(a[2 * i + 1], b[2 * i + 1])
        if hi <= lo:
            return 0
        v *= hi - lo
    return v


def _coverage(comp, cx) -> list:
    """Per feature: its volume inside the domain, the volume its own cells keep (from the complex),
    the later features that take part of it (their box overlaps it and they keep volume), for a box
    its evaluated size and for a layers feature each layer's evaluated [z0, z1], in the component's unit."""
    dom = comp.domain
    domain = tuple(dom[k] for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"))
    boxes = [_boxes(comp, f) for f in comp.features]
    owned = [0] * len(boxes)
    for c in cx.cells:
        if c.feature_index >= 0:
            owned[c.feature_index] += c.volume
    unit3 = comp.pm_per_unit ** 3
    out = []
    for i, f in enumerate(comp.features):
        volume = sum(_overlap(b, domain) for b in boxes[i])
        by = [j for j in range(i + 1, len(boxes)) if owned[j] > 0
              and any(_overlap(a, b) > 0 for a in boxes[i] for b in boxes[j])]
        refs = ", ".join(f"{j + 1} ({comp.features[j].id})" for j in by)
        if volume == 0:
            coverage, text = "outside", "outside the domain; adds no region"
        elif owned[i] == 0:
            coverage, text = "none", f"covered by {refs}; adds no region"
        elif owned[i] < volume:
            coverage, text = "partial", f"covered in part by {refs}"
        else:
            coverage, text = "full", ""
        entry = {"index": i, "id": f.id, "type": f.type, "volume": float(Fraction(volume) / unit3),
                 "owned": float(Fraction(owned[i]) / unit3), "coverage": coverage, "covered_by": by, "text": text}
        if f.type == "box":                  # the evaluated size in the component's unit (the tree's note)
            x0, x1, y0, y1, z0, z1 = boxes[i][0]
            entry["size"] = [float(Fraction(b - a) / comp.pm_per_unit) for a, b in ((x0, x1), (y0, y1), (z0, z1))]
        elif f.type == "layers":             # each layer's evaluated z range, bottom first (the Layers row)
            entry["layers"] = [[float(Fraction(b[4]) / comp.pm_per_unit), float(Fraction(b[5]) / comp.pm_per_unit)]
                               for b in boxes[i]]
        out.append(entry)
    return out


def _parameters(doc: dict, model, comp_name: str) -> list:
    """Parameters with their SI value and the fields of the component that use them (by name)."""
    raw = (doc.get("geometry") or {}).get("parameters") or {}
    comp = ((doc.get("geometry") or {}).get("components") or {}).get(comp_name) or {}
    fields = []

    def walk(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{path}[{i}]")
        elif isinstance(value, str):
            fields.append((path, value))
    walk({k: comp.get(k) for k in ("domain", "features") if k in comp}, "")
    for name, entry in raw.items():
        if isinstance(entry, dict):
            walk(entry.get("value"), f"parameters.{name}")
    out = []
    for name, (value, kind) in model.parameters.items():
        token = re.compile(rf"(?<![\w.]){re.escape(name)}(?![\w])")
        entry = raw.get(name) if isinstance(raw.get(name), dict) else {}
        out.append({"name": name, "kind": kind,
                    "value": float(Fraction(value) / 10 ** 12) if kind == "length" else float(value),
                    "unit": "m" if kind == "length" else "1", "written": entry.get("value"),
                    "used_by": sorted(p for p, text in fields if p != f"parameters.{name}" and token.search(text))})
    return out


def check_view(doc: dict, component: str | None = None) -> dict:
    """The builder's check of one ``3d`` component: features with their coverage, parameters,
    selections, the display answer and ``mesh``; raises ``GeometryError`` on a refusal while forming.

    ``mesh`` is the estimate of meshing this component (``simcase.estimate_mesh3d``, in the words of
    ``/api/model3d/mesh/estimate``) with the mesh job's reuse key, or the refusal that blocks
    meshing (E-MESH-ESTIMATE, a below-tolerance E-CONTRACT, two values rounding to one coordinate):
    the shape is formed either way, so the view is not greyed for it."""
    if shapes_of(doc, component) is not None:          # cylinders and spheres in a builder shape
        return check_view_shapes(doc, component)
    model, comp, cx = complex_of(doc, component)
    display = _display(model, comp, cx)
    try:
        mesh = {"ok": True, "estimate": mesh3d_jobs.estimate(doc, cx.component), "key": mesh3d_jobs.reuse_key(doc)}
    except GeometryError as exc:
        mesh = _refusal(exc)
        if exc.code == "E-MESH-ESTIMATE":
            mesh.update(_estimate_advice(doc, comp))
    return {"ok": True, "component": cx.component, "unit": str(comp.length_unit),
            "features": _coverage(comp, cx), "regions": display["regions"],
            "parameters": _parameters(doc, model, cx.component),
            "selections": display["selections"], "display": display, "mesh": mesh, "run": _run_part(doc),
            "domain": _domain(comp)}


def _domain(comp) -> dict:
    """The domain in the component's length unit, its parameters and expressions evaluated (numbers):
    what Studio's Domain row, size guards and Add feature's defaults read when a bound is written as
    a parameter or an expression."""
    return {k: float(Fraction(comp.domain[k]) / comp.pm_per_unit)
            for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")}


def _estimate_advice(doc: dict, comp) -> dict:
    """What a plain E-MESH-ESTIMATE message needs (Studio's words; the engine's stay in ``refused``):
    ``tetrahedra`` (this document's estimate), ``limit`` and ``suggested_size``: the smallest mesh
    element size on a grid of three significant digits in the component's unit that the same estimate
    accepts (``simcase.estimate_mesh3d``, called, not changed), or None when no single size is
    accepted (feature sizes, say). Studio's guard keeps the size at most the domain diagonal / 4."""
    import copy
    from simcase import estimate_mesh3d
    unit = str(comp.length_unit)
    limit = int((doc.get("mesh") or {}).get("element_count_limit", 600000))

    def count(size):
        trial = copy.deepcopy(doc)
        trial.setdefault("mesh", {})["element_count_limit"] = 10 ** 12
        if size is not None:
            trial["mesh"]["element_size"] = f"{size:.12g} {unit}"
        try:
            return estimate_mesh3d(trial).tetrahedra
        except GeometryError:
            return None

    out = {"tetrahedra": count(None), "limit": limit, "suggested_size": None}
    d = comp.domain
    diag = math.sqrt(sum((float(Fraction(d[b] - d[a]) / comp.pm_per_unit)) ** 2
                         for a, b in (("xmin", "xmax"), ("ymin", "ymax"), ("zmin", "zmax"))))
    if out["tetrahedra"] is None or not diag:
        return out
    grid = lambda h: float(f"{h:.3g}")                                    # noqa: E731

    def up(h):                       # the next grid value above h
        e = math.floor(math.log10(h)) - 2
        return grid(round(h / 10 ** e + 1) * 10 ** e)

    def down(h):
        e = math.floor(math.log10(h)) - 2
        m = round(h / 10 ** e)
        return grid((m - 1) * 10 ** e) if m > 100 else grid(999 * 10 ** (e - 1))

    probe = diag / 100
    t = count(probe)
    if not t:
        return out
    h = grid(probe * (t / limit) ** (1 / 3))
    for _ in range(60):              # up to the first accepted grid value
        t = count(h)
        if t is None or h > diag / 4:
            return out
        if t <= limit:
            break
        h = up(h)
    else:
        return out
    for _ in range(60):              # down while the value below is still accepted
        t = count(down(h))
        if t is None or t > limit:
            break
        h = down(h)
    out["suggested_size"] = h
    return out


def _run_part(doc: dict) -> dict:
    """Whether Run would take the document: the run route's own reading (``heat3d_runs.read_document``),
    ``{"ok": true}`` or the reader's refusal in its own words and code. It starts nothing."""
    try:
        heat3d_runs.read_document(doc)
        return {"ok": True}
    except heat3d_runs.Refused as exc:
        return {"ok": False, "refused": exc.message, "code": exc.extra.get("code")}


def _refusal(exc: GeometryError) -> dict:
    """A refusal with the engine's words, its code and path, and the feature it names (or None)."""
    path = getattr(exc, "path", None)
    found = _FEATURE.search(path or "") or _FEATURE.search(str(exc))
    return {"ok": False, "refused": str(exc), "code": getattr(exc, "code", None), "path": path,
            "feature_index": int(found.group(1)) if found else None}


def new_selection(doc: dict, component: str | None, face: int, name: str) -> dict:
    """A copy of ``doc`` with ``selections[name] = {"boundary": <the first of the face's names that
    selects it alone>}`` ("Use for -> New selection"); ``GeometryError`` when no name does, or the
    name is taken."""
    import copy
    model, comp, cx = complex_of(doc, component)
    if not isinstance(face, int) or isinstance(face, bool) or not 0 <= face < len(cx.faces):
        raise GeometryError(f"component {cx.component!r} has no face {face!r}")
    names = _alone(cx)[face]
    if not names:
        raise GeometryError(f"no single name selects face {face} alone: its names "
                            f"{', '.join(sorted(cx.faces[face].provenance))} each select more faces")
    raw = doc["geometry"]["components"][cx.component]
    if name in (raw.get("selections") or {}):
        raise GeometryError(f"selection {name!r} already exists")
    if any(f.id == name for f in comp.features):
        raise GeometryError(f"{name!r} is a feature id; choose another selection name")
    out = copy.deepcopy(doc)
    out["geometry"]["components"][cx.component].setdefault("selections", {})[name] = {"boundary": names[0]}
    complex_of(out, cx.component)               # the new document must still form
    return out


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
    shaped = shapes_of(doc, component)
    if shaped is not None:
        return _section_shapes(*shaped, axis, at)
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


# ----------------------------------------------------------------------------- builder shapes
# A component whose cylinders or spheres are in a meshloom builder shape has no exact complex; its
# answers come from ``simcase.display_shapes3d`` (faces with the mesh's provenance names, drawn by the
# display rule, separate from the mesh) in the same fields, with ``shape`` on each face (``axis`` and
# ``at`` null on a curved one) and ``display_note``.

def _display_shapes(model, comp, shapes) -> dict:
    unit_m = float(comp.pm_per_unit) / PM                  # metres per document unit
    origin = np.array([(shapes.domain[k + "min"] + shapes.domain[k + "max"]) / 2 for k in AXES], dtype=np.float64)

    def to_m(points):
        return (np.asarray(points, dtype=np.float64) - origin) / PM

    faces_of: dict = {}
    for f in shapes.faces:
        for n in f.names:
            faces_of.setdefault(n, []).append(f.index)
    positions, indices, owner, edges, edge_faces, faces = [], [], [], [], [], []
    base = first = 0
    for f in shapes.faces:
        positions.append(to_m(f.vertices))
        indices.append(f.triangles + base)
        owner.append(np.full(len(f.triangles), f.index, dtype=np.uint32))
        edges.append(to_m(f.edges.reshape(-1, 3)))
        edge_faces.append(np.full(len(f.edges), f.index, dtype=np.uint32))
        faces.append({"id": f.index, "shape": f.shape, "axis": None if f.axis is None else AXES[f.axis],
                      "at": None if f.coord is None else float(Fraction(f.coord) / comp.pm_per_unit),
                      "names": list(f.names), "alone": [n for n in f.names if faces_of[n] == [f.index]],
                      "minus": list(f.minus), "plus": list(f.plus), "exterior": f.exterior, "tag": f.tag,
                      "area": f.area / unit_m ** 2, "segments": f.segments,
                      "first_triangle": first, "triangle_count": int(len(f.triangles))})
        base += len(f.vertices)
        first += len(f.triangles)
    regions = [{"name": r.name, "material": _material(r.material), "void": r.void, "volume": r.volume / unit_m ** 3,
                "faces": list(r.faces)} for r in shapes.regions]
    tags: dict = {}
    for f in shapes.faces:
        if f.tag:
            tags.setdefault(f.tag, []).append(f.index)
    positions, indices, owner = np.concatenate(positions), np.concatenate(indices), np.concatenate(owner)
    edges, edge_faces = np.concatenate(edges), np.concatenate(edge_faces)
    return {
        "ok": True, "component": shapes.component, "unit": str(comp.length_unit),
        "components": [{"name": n, "dimension": c.dimension} for n, c in model.components.items()],
        "metres_per_unit": unit_m, "origin_m": [float(Fraction(shapes.domain[k + "min"] + shapes.domain[k + "max"],
                                                                2 * PM)) for k in AXES],
        "domain": {k: float(Fraction(v) / comp.pm_per_unit) for k, v in sorted(shapes.domain.items())},
        "half_extent_m": [float(Fraction(shapes.domain[k + "max"] - shapes.domain[k + "min"], 2 * PM)) for k in AXES],
        "regions": regions, "faces": faces, "selections": [],
        "tags": [{"tag": t, "faces": ids} for t, ids in sorted(tags.items())],
        "counts": {"faces": len(faces), "triangles": int(len(owner)), "vertices": int(len(positions)),
                   "edges": int(len(edge_faces))},
        "positions": _b64(positions.astype(np.float32), "f4"),
        "indices": _b64(indices.astype(np.uint32), "u4"),
        "triangle_faces": _b64(owner, "u4"),
        "edges": _b64(edges.astype(np.float32), "f4"),
        "edge_faces": _b64(edge_faces, "u4"),
        "summary": _summary_shapes(shapes, comp, regions, faces),
        "display_note": shapes.note,
    }


def _summary_shapes(shapes, comp, regions, faces) -> str:
    unit = str(comp.length_unit)
    lines = [f"component {shapes.component} (3d, {unit}): {len(regions)} regions, {len(faces)} faces, "
             f"meshloom builder.{shapes.shape}; {shapes.note.lower()}"]
    for r in regions:
        lines.append(f"  region {r['name']}: {'void' if r['void'] else r['material']}, volume {r['volume']:g} {unit}^3")
    for f in faces:
        where = f"{f['axis']} = {f['at']:g}" if f["shape"] == "plane" else f["shape"]
        lines.append(f"  face {f['id']}: {where}, area {f['area']:g} {unit}^2, " + " ".join(f["names"])
                     + (f" [tag {f['tag']}]" if f["tag"] else ""))
    return "\n".join(lines)


def _section_shapes(model, comp, shapes, axis: str, at) -> dict:
    at_pm = round(Fraction(str(at)) * comp.pm_per_unit)
    lo, hi = shapes.domain[axis + "min"], shapes.domain[axis + "max"]
    unit = str(comp.length_unit)
    if not lo <= at_pm <= hi:
        raise GeometryError(f"section {axis} = {at} {unit} is outside the domain of {shapes.component!r} "
                            f"({float(Fraction(lo) / comp.pm_per_unit):g} to {float(Fraction(hi) / comp.pm_per_unit):g} {unit})")
    cut = shapes.section(axis, at_pm)
    origin = np.array([(shapes.domain[k + "min"] + shapes.domain[k + "max"]) / 2 for k in AXES], dtype=np.float64)
    segments = (cut["segments"] - origin) / PM
    return {"ok": True, "component": shapes.component, "unit": unit, "axis": axis, "at": at,
            "faces": sorted(set(cut["faces"].tolist())), "regions": sorted(cut["regions"]),
            "segments": _b64(segments.astype(np.float32).reshape(-1, 2, 3), "f4"),
            "segment_faces": _b64(cut["faces"].astype(np.uint32), "u4")}


def _coverage_shapes(comp, shapes) -> list:
    """Per feature, from the exact volumes: a via or a lone sphere keeps its whole body (full); in
    concentric spheres each one but the innermost keeps its shell (partial, covered by the later ones)."""
    unit3 = (float(comp.pm_per_unit) / PM) ** 3
    volume = {r.name: r.volume for r in shapes.regions}
    out = []
    for i, f in enumerate(comp.features):
        d = f.data
        if f.type == "cylinder":
            whole = math.pi * (d["r"] / PM) ** 2 * ((d["zmax"] - d["zmin"]) / PM)
        else:
            whole = 4 * math.pi / 3 * (d["r"] / PM) ** 3
        by = list(range(i + 1, len(comp.features))) if shapes.shape == "nested_spheres" else []
        refs = ", ".join(f"{j + 1} ({comp.features[j].id})" for j in by)
        coverage, text = ("partial", f"covered in part by {refs}") if by else ("full", "")
        out.append({"index": i, "id": f.id, "type": f.type, "volume": whole / unit3,
                    "owned": (volume[f.region] if by else whole) / unit3, "coverage": coverage, "covered_by": by,
                    "text": text})
    return out


def check_view_shapes(doc: dict, component: str | None = None) -> dict:
    """``check_view`` of a component whose cylinders or spheres are in a meshloom builder shape: features
    with their coverage from the exact volumes, regions with exact volumes, parameters, the display
    answer (``display_shapes3d``), ``mesh``: slice 3's estimate (``simcase.estimate_mesh3d``, route
    ``builder``) with the reuse key, or the refusal that blocks meshing, and ``run`` as ``check_view``
    answers it."""
    model, comp, shapes = shapes_of(doc, component)
    display = _display_shapes(model, comp, shapes)
    try:
        mesh = {"ok": True, "estimate": mesh3d_jobs.estimate(doc, shapes.component), "key": mesh3d_jobs.reuse_key(doc)}
    except GeometryError as exc:
        mesh = _refusal(exc)
        if exc.code == "E-MESH-ESTIMATE":
            mesh.update(_estimate_advice(doc, comp))
    return {"ok": True, "component": shapes.component, "unit": str(comp.length_unit),
            "features": _coverage_shapes(comp, shapes), "regions": display["regions"],
            "parameters": _parameters(doc, model, shapes.component),
            "selections": [], "display": display, "mesh": mesh, "run": _run_part(doc),
            "domain": _domain(comp)}


# ----------------------------------------------------------------------------- the routes

def _reply(fn, *args) -> dict:
    try:
        return fn(*args)
    except GeometryError as exc:
        return {"ok": False, "refused": str(exc)}


def _reply_coded(fn, *args) -> dict:
    try:
        return fn(*args)
    except GeometryError as exc:
        return _refusal(exc)


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


@router.post("/api/model3d/check")
async def model3d_check(request: Request):
    try:
        tree, found = await _read(request)
    except RequestRefused as exc:
        return exc.reply()
    if found:
        return exact_json(_found(found))
    return exact_json(await run_in_threadpool(_reply_coded, check_view, tree["doc"], tree.get("component")))


@router.post("/api/model3d/selection")
async def model3d_selection(request: Request):
    try:
        tree, found = await _read(request, optional=("component", "face", "name"))
        face, name = tree.get("face"), tree.get("name")
        if isinstance(face, bool) or not isinstance(face, int):
            raise RequestRefused("face: the picked face is a face id (an integer)")
        if not isinstance(name, str) or not name:
            raise RequestRefused("name: the new selection's name is a non-empty string")
    except RequestRefused as exc:
        return exc.reply()
    if found:
        return exact_json(_found(found))

    def made(doc, component, face, name):
        return {"ok": True, "doc": new_selection(doc, component, face, name)}
    return exact_json(await run_in_threadpool(_reply_coded, made, tree["doc"], tree.get("component"), face, name))


# ----------------------------------------------------------------------------- the mesh job
# /api/model3d/mesh/estimate answers I-MESH-ESTIMATE; /api/model3d/mesh starts a job in a child
# process (mesh3d_jobs); /api/model3d/jobs/{job} answers its status, /cancel ends it and /result
# answers the mesh's surface. A job id is server-made and only a key of the jobs table.

jobs = mesh3d_jobs.Mesh3DJobs()
_JOB_ID = re.compile(r"m3d-[0-9a-f]{12}")
runs = heat3d_runs.bind(jobs)               # the 3D heat run (heat3d_runs): its routes, the same child slot


def _job_refusal(exc: mesh3d_jobs.Refused):
    return JSONResponse({"detail": exc.message, **exc.extra}, status_code=exc.status, headers=NO_STORE)


def _estimate_reply(doc, component) -> dict:
    try:
        return {"ok": True, "estimate": mesh3d_jobs.estimate(doc, component), "key": mesh3d_jobs.reuse_key(doc)}
    except GeometryError as exc:
        return {"ok": False, "refused": str(exc), "code": getattr(exc, "code", None)}


@router.post("/api/model3d/mesh/estimate")
async def model3d_mesh_estimate(request: Request):
    try:
        tree, found = await _read(request)
    except RequestRefused as exc:
        return exc.reply()
    if found:
        return exact_json(_found(found))
    return exact_json(await run_in_threadpool(_estimate_reply, tree["doc"], tree.get("component")))


@router.post("/api/model3d/mesh")
async def model3d_mesh(request: Request):
    try:
        tree, found = await _read(request)
    except RequestRefused as exc:
        return exc.reply()
    if found:
        return JSONResponse({"detail": _found(found)["refused"]}, status_code=400, headers=NO_STORE)
    try:
        reply = await run_in_threadpool(jobs.start, tree["doc"], tree.get("component"))
    except mesh3d_jobs.Refused as exc:
        return _job_refusal(exc)
    return JSONResponse(reply, headers=NO_STORE)


def _job(job_id: str) -> str:
    if not _JOB_ID.fullmatch(job_id):
        raise mesh3d_jobs.Refused(404, "no such 3D mesh job")
    return job_id


@router.get("/api/model3d/jobs/{job_id}")
def model3d_job(job_id: str):
    try:
        return JSONResponse(jobs.status(_job(job_id)), headers=NO_STORE)
    except mesh3d_jobs.Refused as exc:
        return _job_refusal(exc)


@router.post("/api/model3d/jobs/{job_id}/cancel")
def model3d_job_cancel(job_id: str):
    """Cancel meshing: the child process is terminated and nothing is kept."""
    try:
        return JSONResponse(jobs.cancel_job(_job(job_id)), headers=NO_STORE)
    except mesh3d_jobs.Refused as exc:
        return _job_refusal(exc)


@router.get("/api/model3d/jobs/{job_id}/result")
def model3d_job_result(job_id: str):
    try:
        return JSONResponse(jobs.result(_job(job_id)), headers=NO_STORE)
    except mesh3d_jobs.Refused as exc:
        return _job_refusal(exc)


@router.get("/model3d-assets/{filename}")
def model3d_asset(filename: str):
    entry = ASSETS.get(filename)
    if entry is None:
        raise HTTPException(404, "Unknown 3D view asset")
    path, mime = entry
    return FileResponse(path, media_type=mime, headers=NO_STORE)
