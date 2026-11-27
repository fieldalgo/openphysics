# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The expected picks of check W3, by a ray cast of their own against the exact complex.

Written before the 3D view, from the camera contract below, which the view implements
(docs/packages/simcase/studio_3d.md, "Camera"). Nothing here reads the display tessellation:
the faces are the exact polygons of ``simcase.geometry_engine3d.evaluate3d``, in pm.

Camera contract (isometric view of a component, the view's first camera):

- the frame is metres relative to the domain centre c;
- R is half the domain diagonal;
- orthographic camera looking at c from c + 4 R e, e = (1, 1, 1) / sqrt(3), up +z; its axes are
  z = e, x = normalize(up x z), y = z x x (three.js ``lookAt``);
- the frustum fits a sphere of radius 1.1 R: for a W x H canvas with W >= H, half height 1.1 R
  and half width 1.1 R W / H; otherwise half width 1.1 R and half height 1.1 R H / W;
- a canvas point (px, py) in CSS pixels from its top-left corner is at ndc
  (2 px / W - 1, 1 - 2 py / H).

The pick is the nearest face, along the ray, of a face with a non-void region on one side, all
regions shown. The candidates are a 12 x 10 raster over x in [0.22, 0.78] W and y in
[0.17, 0.83] H (the card's domain projects into x 0.19-0.81 W, y 0.15-0.85 H); those within
3 px of any face edge (projected, hidden or not) are listed as excluded, and 40 of the others,
evenly spaced in raster order, are the checked points.

Run ``python tests/simcase/model3d_pick_oracle.py`` to rewrite studio_model3d_pick_points.json;
``test_studio_model3d.py`` checks the stored file against a fresh run.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "studio_model3d_pick_points.json"
WIDTH, HEIGHT = 720, 504              # the 3D view canvas at a 1440 x 900 window, CSS pixels
MARGIN, EYE = 1.1, 4.0
EXCLUDE_PX = 3.0
RASTER = (12, 10)
SPAN = (0.22, 0.78, 0.17, 0.83)        # the raster covers x in [0.22, 0.78] W, y in [0.17, 0.83] H
POINTS = 40
PM = 10 ** 12


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return [c / n for c in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def camera(domain_pm, width=WIDTH, height=HEIGHT):
    """The isometric camera of the contract: centre (pm), axes, R and the half extents (m)."""
    lo = [domain_pm[k + "min"] for k in "xyz"]
    hi = [domain_pm[k + "max"] for k in "xyz"]
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    r = math.sqrt(sum(((b - a) / PM) ** 2 for a, b in zip(lo, hi))) / 2
    z = _norm([1.0, 1.0, 1.0])
    x = _norm(_cross([0.0, 0.0, 1.0], z))
    y = _cross(z, x)
    if width >= height:
        hh, hw = MARGIN * r, MARGIN * r * width / height
    else:
        hw, hh = MARGIN * r, MARGIN * r * height / width
    return {"centre_pm": centre, "x": x, "y": y, "z": z, "r": r, "half_width": hw, "half_height": hh,
            "width": width, "height": height}


def ray(cam, px, py):
    nx, ny = 2 * px / cam["width"] - 1, 1 - 2 * py / cam["height"]
    o = [cam["x"][i] * nx * cam["half_width"] + cam["y"][i] * ny * cam["half_height"] + cam["z"][i] * EYE * cam["r"]
         for i in range(3)]
    return o, [-c for c in cam["z"]]


def project(cam, p_m):
    """Canvas CSS pixels of a point in the frame (m)."""
    u = sum(p_m[i] * cam["x"][i] for i in range(3)) / cam["half_width"]
    v = sum(p_m[i] * cam["y"][i] for i in range(3)) / cam["half_height"]
    return (u + 1) * cam["width"] / 2, (1 - v) * cam["height"] / 2


def _frame(cam, p_pm):
    return [(p_pm[i] - cam["centre_pm"][i]) / PM for i in range(3)]


def _inside(loops2, u, v):
    """Even-odd test of (u, v) against the face's loops (axis-aligned edges)."""
    inside = False
    for loop in loops2:
        for (u0, v0), (u1, v1) in zip(loop, loop[1:] + loop[:1]):
            if (v0 > v) != (v1 > v) and u < u0 + (v - v0) * (u1 - u0) / (v1 - v0):
                inside = not inside
    return inside


def pick(cx, cam, px, py):
    """(face index, first name) of the nearest face hit, or (None, None)."""
    o, d = ray(cam, px, py)
    shown = {c.index for c in cx.cells if not c.void}
    best = None
    for f in cx.faces:
        if not ((f.minus | f.plus) & shown):
            continue
        a = f.axis
        t = ((f.coord - cam["centre_pm"][a]) / PM - o[a]) / d[a]
        p = [o[i] + t * d[i] for i in range(3)]
        others = [i for i in range(3) if i != a]
        loops2 = [[tuple((q[i] - cam["centre_pm"][i]) / PM for i in others) for q in loop] for loop in f.loops]
        if _inside(loops2, p[others[0]], p[others[1]]) and (best is None or t < best[0]):
            best = (t, f)
    if best is None:
        return None, None
    return best[1].index, sorted(best[1].provenance)[0]


def _segment_distance(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L = ax * ax + ay * ay
    s = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L))
    return math.hypot(p[0] - a[0] - s * ax, p[1] - a[1] - s * ay)


def edges_px(cx, cam):
    out = []
    for f in cx.faces:
        for loop in f.loops:
            for a, b in zip(loop, loop[1:] + loop[:1]):
                out.append((project(cam, _frame(cam, a)), project(cam, _frame(cam, b))))
    return out


def expected():
    sys.path.insert(0, str(HERE))
    from model3d_fixtures import card
    from simcase.geometry_document import parse
    from simcase.geometry_engine3d import evaluate3d
    cx = evaluate3d(parse(card()))
    cam = camera(cx.domain)
    edges = edges_px(cx, cam)
    candidates, excluded = [], []
    nx, ny = RASTER
    x0, x1, y0, y1 = SPAN
    for j in range(ny):
        for i in range(nx):
            px = round(WIDTH * (x0 + (x1 - x0) * (i + 0.5) / nx))
            py = round(HEIGHT * (y0 + (y1 - y0) * (j + 0.5) / ny))
            near = min(_segment_distance((px, py), a, b) for a, b in edges)
            if near < EXCLUDE_PX:
                excluded.append({"px": px, "py": py, "edge_distance_px": round(near, 3)})
            else:
                candidates.append((px, py))
    chosen = [candidates[round(k * (len(candidates) - 1) / (POINTS - 1))] for k in range(POINTS)]
    assert len(set(chosen)) == POINTS
    points = []
    for px, py in chosen:
        face, name = pick(cx, cam, px, py)
        points.append({"px": px, "py": py, "face": face, "first_name": name})
    return {"document": "simcase/studio/static/model3d-via-stack.json", "component": cx.component,
            "canvas": {"width": WIDTH, "height": HEIGHT}, "window": {"width": 1440, "height": 900},
            "camera": "isometric (contract in tests/simcase/model3d_pick_oracle.py)",
            "exclude_within_px": EXCLUDE_PX, "points": points, "excluded": excluded}


if __name__ == "__main__":
    OUT.write_text(json.dumps(expected(), indent=1) + "\n", encoding="utf-8")
    print(OUT)
