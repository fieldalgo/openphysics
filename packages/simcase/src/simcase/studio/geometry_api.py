# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The experimental geometry lab: a version 1 geometry document through the exact 2D engine.

``/geometry-lab`` is a separate page from the model workspace. The browser holds
the document; every edit is sent whole to ``/api/geometry-lab/evaluate``, which
parses it with ``parse_geometry`` and evaluates one component with
``evaluate_geometry``. Nothing is cached, so the drawing is always the engine's
answer to the document as written. A refusal is an ordinary answer,
``{"ok": false, "refused": <message>}``, with the engine's own message, which
names the feature, selection or parameter (a 4xx status would be logged by the
browser as a console error on every refused edit).

The response is a view for this page, not a persisted format: coordinates are
doubles in the evaluated component's length unit (the document's for a 0.2 block),
arcs and circles are sampled for drawing only, and ``summary`` is the text
``python -m simcase geometry`` prints. A format 0.3 parameter is reported with its
authored value and its SI value.

Imports from simcase are absolute and limited to ``simcase.__all__``.
"""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from simcase import GeometryError, evaluate_geometry, parse_geometry

STATIC = Path(__file__).parent / "static"
router = APIRouter()


def install(app) -> None:
    """Add the lab's routes to ``app`` as plain routes (``include_router`` in recent FastAPI
    wraps them in an object without ``path``, which Studio's route checks read)."""
    for route in router.routes:
        app.add_api_route(route.path, route.endpoint, methods=list(route.methods),
                          include_in_schema=route.include_in_schema)

# The page loads only its own files: no inline script or style, no other origin.
PAGE_POLICY = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
               "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
ARC_STEPS = 96      # drawing samples per whole circle; the engine's curves stay exact


class EvaluateBody(BaseModel):
    doc: dict
    component: str | None = None


@router.get("/geometry-lab")
@router.get("/geometry-lab/")
def geometry_lab_index():
    return FileResponse(STATIC / "geometry-lab.html",
                        headers={**NO_STORE, "Content-Security-Policy": PAGE_POLICY})


@router.get("/geometry-lab-assets/{filename}")
def geometry_lab_asset(filename: str):
    assets = {path.name: path for path in STATIC.glob("geometry-lab-*.mjs")}
    assets["geometry-lab.css"] = STATIC / "geometry-lab.css"
    path = assets.get(filename)
    if path is None:
        raise HTTPException(404, "Unknown geometry lab asset")
    mime = "text/css" if path.suffix == ".css" else "text/javascript"
    return FileResponse(path, media_type=mime, headers=NO_STORE)


@router.post("/api/geometry-lab/evaluate")
def geometry_lab_evaluate(body: EvaluateBody):
    try:
        view = {"ok": True, **evaluate_view(body.doc, body.component)}
    except GeometryError as exc:
        view = {"ok": False, "refused": str(exc)}
    return JSONResponse(view, headers={"Cache-Control": "no-store"})


def evaluate_view(doc: dict, component: str | None = None) -> dict:
    """The page's view of one evaluated component; raises ``GeometryError`` on a refusal."""
    geometry = doc.get("geometry")
    if not isinstance(geometry, dict) or "version" not in geometry:
        # The same words as ``python -m simcase geometry``.
        raise GeometryError("the document has a 0.2 geometry block; the region complex needs a version 1 block "
                            "(see docs/packages/simcase/geometry_document.md)")
    model = parse_geometry(doc)
    names = list(model.components)
    flat = [n for n in names if model.components[n].dimension != "3d"]
    if component is None and len(names) > 1:
        # Show the first 2D component rather than refusing a multi-component document.
        component = flat[0] if flat else names[0]
    rc = evaluate_geometry(model, component)
    comp = model.components[rc.component]
    scale = float(comp.pm_per_unit)
    point = lambda v: [float(v[0]) / scale, float(v[1]) / scale]        # noqa: E731
    raw = geometry.get("parameters") or {}
    parameters = []
    for name, (value, kind) in model.parameters.items():
        entry = raw.get(name) if isinstance(raw.get(name), dict) else {}
        item = {"name": name, "kind": kind, "value": float(value), "written": entry.get("value"),
                "range": entry.get("range")}
        if getattr(model, "format", "0.2") == "0.3":
            # a 0.3 parameter is exact pm (length) or a ratio: report its SI value and unit
            item["value"] = float(Fraction(value) / 10 ** 12) if kind == "length" else float(value)
            item["unit"] = "m" if kind == "length" else "1"
        parameters.append(item)
    cells = [{"index": c.index, "region": c.region, "material": _material(c.material), "void": c.void,
              "feature": c.feature, "area": c.area / scale ** 2,
              "loops": [[[i, bool(forward)] for i, forward in loop] for loop in c.loops]} for c in rc.cells]
    curves = [{"index": k.index, "kind": k.kind, "points": _points(rc, k, point, scale),
               "provenance": sorted(k.provenance), "left": k.left, "right": k.right, "tag": k.tag}
              for k in rc.curves]
    regions = []
    for name in rc.region_names():
        mine = [c for c in rc.cells if c.region == name]
        regions.append({"name": name, "material": _material(mine[0].material), "void": mine[0].void,
                        "cells": [c.index for c in mine], "area": rc.area_of_region(name) / scale ** 2})
    tags: dict[str, list[int]] = {}
    for k in rc.curves:
        if k.tag:
            tags.setdefault(k.tag, []).append(k.index)
    return {
        "unit": str(comp.length_unit), "components": names, "component": rc.component,
        "dimension": rc.dimension, "parameters": parameters,
        "domain": {key: float(Fraction(v) / comp.pm_per_unit) for key, v in rc.domain.items()},
        "regions": regions, "cells": cells, "curves": curves,
        "selections": [{"name": name, "kind": kind, "entries": sorted(chosen)}
                       for name, (kind, chosen) in rc.selections.items()],
        "tags": [{"tag": tag, "curves": indices} for tag, indices in tags.items()],
        "roundings": [{"path": r.path, "written": r.written, "displacement_pm": float(r.displacement_pm)}
                      for r in model.roundings],
        "notes": list(rc.notes), "summary": rc.summary(model),
    }


def _material(material):
    """A material name, None for void, or "(homogeneous)" for a background without a material key."""
    return material if material is None or isinstance(material, str) else "(homogeneous)"


def _points(rc, k, point, scale: float) -> list:
    """The curve from vertex a to b in document units; an arc or circle runs counter-clockwise."""
    a, b = point(rc.vertices[k.a]), point(rc.vertices[k.b])
    if k.kind == "line":
        return [a, b]
    cx, cy = (c / scale for c in k.params["center"])
    r = math.sqrt(k.params["r2"]) / scale
    t0 = math.atan2(a[1] - cy, a[0] - cx)
    sweep = (math.atan2(b[1] - cy, b[0] - cx) - t0) % (2 * math.pi) or 2 * math.pi
    n = max(2, math.ceil(sweep / (2 * math.pi) * ARC_STEPS))
    inner = [[cx + r * math.cos(t0 + sweep * i / n), cy + r * math.sin(t0 + sweep * i / n)] for i in range(1, n)]
    return [a, *inner, b]
