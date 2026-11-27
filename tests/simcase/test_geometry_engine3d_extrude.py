# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Stage 5, slice 2: extrudes of rect, trapezoid and polygon profiles through meshloom.

Pre-registered checks (fixed before measuring; never loosened):

- G1-P: seeded later-wins sets of at most 8 prisms (boxes, slab layers, and rect, trapezoid and
  polygon extrudes, non-convex polygons among them) on a half-millimetre grid with shared
  vertices, collinear overlaps, T-junctions, nesting and shared planes, at h = 0.25 mm, against
  an oracle independent of the engine: a point's region is the last prism whose profile (exact
  point in polygon) and z range contain it, and the exact region volumes come from a trapezoidal
  sweep of every slab between all vertex and intersection x values. (a) no tetrahedron whose exact
  centroid the oracle puts in another region; (b) region volumes within 1e-12 (relative) of the
  oracle's. Pull requests run 25 fixed seeds; ``OPENPHYSICS_GEOMETRY3D_FULL=1`` runs all 200
  (the CI job ``geometry3d-full``).
- G2 on those sets: every complex face under a provenance name lies on that part's exact surface
  (pm rationals; a sloped side is the vertical plane through its edge, inside the edge and its z
  range); every complex surface on a part's surface lists the part; every mesh face under a name
  lies on the part's surface (exactly for axis-aligned parts; within 1e-12 of the domain diagonal
  for sloped parts and the sloped edges of caps, since doubles cannot hold a sloped plane); the
  mesh faces under each name cover the complex faces that carry it (area within 1e-12); every
  exterior face is in exactly one tag.
- G3: V1 and V2 on every mesh.
- G6: one document per new refusal (a circle profile; two derived coordinates rounding to one
  double): code, path and names.
- A4: the part names of rect, trapezoid and polygon extrudes (``bottom`` and ``top`` of a rect or
  trapezoid profile become ``y0`` and ``y1``; the caps are ``<id>.bottom`` and ``<id>.top``).
- F (fuzz): 60 seeded T-junction sets of 2-3 polygon extrudes in pm (a vertex of one on the
  sloped edge of another, off the doubles; collinear sloped shared planes). Each set either meshes
  with G1(a) = 0, G1(b) <= 1e-12 and V1/V2, or raises ``Mesh3DError`` whose cause is meshloom's
  ``RoundingError`` and that names provenance; 0 other exceptions; at least 30 of the 60 mesh.
- S1: the 25 pull-request seeds of slice 1's G1 give the complex and mesh SHA-256 recorded on main
  a5c61f8 before this slice (``geometry3d_slice1_digests.json``): slice 1's output is unchanged.
"""

import hashlib
import json
import math
import os
import random
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import test_geometry_engine3d as s1  # noqa: E402
from simcase.geometry_document import GeometryError  # noqa: E402
from simcase.geometry_engine3d import Mesh3DError, _build, build_mesh3d, evaluate3d  # noqa: E402

PM = 10 ** 12
FULL = os.environ.get("OPENPHYSICS_GEOMETRY3D_FULL") == "1"
G1P_SEEDS = list(range(200)) if FULL else list(range(0, 200, 8))
FUZZ_SEEDS = list(range(60))
FUZZ_FLOOR = 30
DIGESTS = Path(__file__).with_name("geometry3d_slice1_digests.json")
doc = s1.doc


# ----------------------------------------------------------------------------- the prism model

_TO_M = {"mm": Fraction(1, 1000), "pm": Fraction(1, PM)}
RECT_PARTS = ["y0", "right", "y1", "left"]          # A4: a rect or trapezoid's bottom and top are y0 and y1
BOX_PARTS = ["y0", "x1", "y1", "x0"]                # the side names of a box, edge by edge (counter-clockwise)


def _q(v) -> Fraction:
    return v if isinstance(v, Fraction) else Fraction(str(v))


class Prism:
    """One prism of the oracle, in exact metres (``poly``, ``z``) and in the metre doubles of
    rule H1 (``rpoly``, ``rz``): a counter-clockwise or clockwise profile with one part name per edge."""

    def __init__(self, name, region, material, poly, parts, z, *, kind, caps, unit):
        s = _TO_M[unit]
        self.name, self.region, self.material, self.kind = name, region, material, kind
        self.poly = [(_q(x) * s, _q(y) * s) for x, y in poly]
        self.rpoly = [(Fraction(float(x)), Fraction(float(y))) for x, y in self.poly]
        self.z = tuple(_q(v) * s for v in z)
        self.rz = tuple(Fraction(float(v)) for v in self.z)
        self.parts, self.caps = parts, caps

    def contains(self, p, rounded=True) -> bool:
        poly, (z0, z1) = (self.rpoly, self.rz) if rounded else (self.poly, self.z)
        return z0 <= p[2] <= z1 and _in_polygon(p[0], p[1], poly)


def _in_polygon(x, y, poly) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _profile(prof):
    """(points, part names) of a rect, trapezoid or polygon profile, in the document's unit."""
    t = prof["type"]
    if t == "rect":
        x, y, w, h = (_q(prof[k]) for k in ("x", "y", "w", "h"))
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], RECT_PARTS
    if t == "trapezoid":
        cx, y, w, h = (_q(prof[k]) for k in ("cx", "y", "w", "h"))
        wt = _q(prof.get("w_top", prof["w"]))
        return [(cx - w / 2, y), (cx + w / 2, y), (cx + wt / 2, y + h), (cx - wt / 2, y + h)], RECT_PARTS
    pts = [(_q(x), _q(y)) for x, y in prof["points"]]
    return pts, prof.get("edges") or [f"e{i + 1}" for i in range(len(pts))]


def prisms_of(comp) -> list:
    """Every prism of a 3d component, in list order (a layers feature gives one per slab layer)."""
    unit, dom = comp["length_unit"], comp["domain"]
    out = []
    for f in comp["features"]:
        if f["type"] == "box":
            poly = [(f["xmin"], f["ymin"]), (f["xmax"], f["ymin"]), (f["xmax"], f["ymax"]), (f["xmin"], f["ymax"])]
            out.append(Prism(f["name"], f["name"], f["material"], poly, BOX_PARTS, (f["zmin"], f["zmax"]),
                             kind="box", caps=("z0", "z1"), unit=unit))
        elif f["type"] == "extrude":
            poly, parts = _profile(f["profile"])
            out.append(Prism(f["name"], f["name"], f["material"], poly, parts, (f["zmin"], f["zmax"]),
                             kind="extrude", caps=("bottom", "top"), unit=unit))
        else:
            z = _q(f["z0"])
            poly = [(dom["xmin"], dom["ymin"]), (dom["xmax"], dom["ymin"]), (dom["xmax"], dom["ymax"]),
                    (dom["xmin"], dom["ymax"])]
            for lay in f["layers"]:
                z1 = z + _q(lay["thickness"])
                region = lay["material"] if lay["material"] is not None else f"{f['name']}.{lay['name']}"
                out.append(Prism(f"{f['name']}.{lay['name']}", region, lay["material"], poly,
                                 ["domain.y0", "domain.x1", "domain.y1", "domain.x0"], (z, z1),
                                 kind="slab", caps=("bottom", "top"), unit=unit))
                z = z1
    return out


def oracle(prisms, background, p, rounded=True):
    for pr in reversed(prisms):
        if pr.contains(p, rounded):
            return pr.region, pr.material
    return "background", background


def _domain_m(comp):
    s = _TO_M[comp["length_unit"]]
    return {k: _q(v) * s for k, v in comp["domain"].items()}


def oracle_volumes(comp, prisms, background) -> dict:
    """Exact region volumes (m^3) of the non-void regions, by a trapezoidal sweep of every slab."""
    dom = _domain_m(comp)
    X0, X1, Y0, Y1, Z0, Z1 = (dom[k] for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"))
    levels = sorted({Z0, Z1} | {min(max(z, Z0), Z1) for p in prisms for z in p.z})
    box = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    out: dict = {}
    for za, zb in zip(levels, levels[1:]):
        zm = (za + zb) / 2
        active = [p for p in prisms if p.z[0] <= za and p.z[1] >= zb]
        edges = []
        for poly in [box] + [p.poly for p in active]:
            n = len(poly)
            for i in range(n):
                a, b = poly[i], poly[(i + 1) % n]
                if a[0] != b[0]:
                    edges.append((a, b) if a[0] < b[0] else (b, a))
        xs = {X0, X1} | {p[0] for e in edges for p in e}
        for i, (a, b) in enumerate(edges):
            for c, d in edges[i + 1:]:
                den = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
                if den == 0:
                    continue
                t = ((c[0] - a[0]) * (d[1] - c[1]) - (c[1] - a[1]) * (d[0] - c[0])) / den
                u = ((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / den
                if 0 <= t <= 1 and 0 <= u <= 1:
                    xs.add(a[0] + t * (b[0] - a[0]))
        xs = sorted(x for x in xs if X0 <= x <= X1)
        for xa, xb in zip(xs, xs[1:]):
            xm = (xa + xb) / 2

            def y_at(e, x):
                (x0, y0), (x1, y1) = e
                return y0 + (x - x0) * (y1 - y0) / (x1 - x0)

            span = sorted({(y_at(e, xm), y_at(e, xa), y_at(e, xb)) for e in edges if e[0][0] <= xa and e[1][0] >= xb})
            span = [s for s in span if Y0 <= s[0] <= Y1]
            for lo, hi in zip(span, span[1:]):
                region, material = oracle(prisms, background, ((xm), (lo[0] + hi[0]) / 2, zm), rounded=False)
                if material is None:
                    continue
                area = (xb - xa) * ((hi[1] - lo[1]) + (hi[2] - lo[2])) / 2
                out[region] = out.get(region, 0) + area * (zb - za)
    return {k: v for k, v in out.items() if v > 0}


def g1_metrics(result, comp, prisms, background):
    m = result.mesh
    wrong = 0
    for t, row in enumerate(m.tets.tolist()):
        cen = [sum(Fraction(float(m.nodes[v][i])) for v in row) / 4 for i in range(3)]
        region, material = oracle(prisms, background, cen)
        if material is None or region != m.region_names[m.regions[t]]:
            wrong += 1
    p = m.nodes[m.tets]
    vol = np.abs(np.einsum("ti,ti->t", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))) / 6
    mesh_volume = {n: float(vol[m.regions == i].sum()) for i, n in enumerate(m.region_names)}
    exact = oracle_volumes(comp, prisms, background)
    assert set(mesh_volume) == set(exact), (sorted(mesh_volume), sorted(exact))
    worst = max(abs(mesh_volume[n] - float(v)) / float(v) for n, v in exact.items())
    return wrong, worst


# ----------------------------------------------------------------------------- G2: provenance

def surfaces(comp, prisms) -> dict:
    """name -> surface, exact metres: ("axis", a, value, ((lo, hi), (lo, hi)), poly or None),
    ("side", P, Q, z0, z1)."""
    dom = _domain_m(comp)
    out = {}
    lo = [dom["xmin"], dom["ymin"], dom["zmin"]]
    hi = [dom["xmax"], dom["ymax"], dom["zmax"]]
    for a, axis in enumerate("xyz"):
        span = tuple((lo[o], hi[o]) for o in range(3) if o != a)
        out[f"domain.{axis}0"] = ("axis", a, lo[a], span, None)
        out[f"domain.{axis}1"] = ("axis", a, hi[a], span, None)
    for p in prisms:
        xs, ys = [q[0] for q in p.poly], [q[1] for q in p.poly]
        bbox = ((min(xs), max(xs)), (min(ys), max(ys)))
        for cap, z in zip(p.caps, p.z):
            out[f"{p.name}.{cap}"] = ("axis", 2, z, bbox, p.poly)
        if p.kind == "slab":                 # its sides lie on the domain's faces, between its z levels
            for a, axis in enumerate("xy"):
                other = (lo[1 - a], hi[1 - a])
                for e, v in (("0", lo[a]), ("1", hi[a])):
                    out[f"{p.name}.domain.{axis}{e}"] = ("axis", a, v, (other, p.z), None)
            continue
        n = len(p.poly)
        for i, part in enumerate(p.parts):
            out[f"{p.name}.{part}"] = ("side", p.poly[i], p.poly[(i + 1) % n], p.z[0], p.z[1])
    return out


def _on_segment(x, y, P, Q, tol=0):
    dx, dy = Q[0] - P[0], Q[1] - P[1]
    cross = dx * (y - P[1]) - dy * (x - P[0])
    dot = dx * (x - P[0]) + dy * (y - P[1])
    L2 = dx * dx + dy * dy
    if tol == 0:
        return cross == 0 and 0 <= dot <= L2
    L = math.sqrt(float(L2))
    return abs(float(cross)) <= tol * L and -tol * L <= float(dot) <= float(L2) + tol * L


def _in_or_on(x, y, poly, tol=0) -> bool:
    n = len(poly)
    if any(_on_segment(x, y, poly[i], poly[(i + 1) % n], tol) for i in range(n)):
        return True
    return _in_polygon(x, y, poly)


def _interior_point(loops):
    """A point strictly inside a horizontal face given by its loops of (x, y, ...) points (exact): the
    middle of the widest interval on the line half-way between its two lowest distinct heights."""
    ys = sorted({p[1] for lp in loops for p in lp})
    y = (ys[0] + ys[1]) / 2
    xs = []
    for lp in loops:
        for i in range(len(lp)):
            (x0, y0), (x1, y1) = lp[i][:2], lp[(i + 1) % len(lp)][:2]
            if (y0 > y) != (y1 > y):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    xa, xb = max(zip(xs[::2], xs[1::2]), key=lambda iv: iv[1] - iv[0])
    return (xa + xb) / 2, y


def _on(surface, pts, tol=0, loops=None) -> bool:
    """The points lie on the surface. For a cap of a profile that need not be convex, ``loops`` (the
    face's own loops, exact) also puts a point strictly inside the face inside the profile: a face is
    whole fine cells of one membership, so one interior point decides."""
    if surface[0] == "axis":
        _, a, value, span, poly = surface
        others = [o for o in range(3) if o != a]
        for p in pts:
            if p[a] != value:
                return False
            if poly is None:
                if not all(lo <= p[o] <= hi for o, (lo, hi) in zip(others, span)):
                    return False
            elif not _in_or_on(p[0], p[1], poly, tol):
                return False
        if poly is not None and loops is not None and not _in_polygon(*_interior_point(loops), poly):
            return False
        return True
    _, P, Q, z0, z1 = surface
    return all(z0 <= p[2] <= z1 and _on_segment(p[0], p[1], P, Q, tol) for p in pts)


def _rounded(surface):
    R = lambda v: Fraction(float(v))  # noqa: E731
    if surface[0] == "axis":
        _, a, value, span, poly = surface
        return ("axis", a, R(value), tuple((R(lo), R(hi)) for lo, hi in span),
                None if poly is None else [(R(x), R(y)) for x, y in poly])
    _, P, Q, z0, z1 = surface
    return ("side", (R(P[0]), R(P[1])), (R(Q[0]), R(Q[1])), R(z0), R(z1))


def g2_violations(result, comp, prisms) -> int:
    S = surfaces(comp, prisms)
    dom = _domain_m(comp)
    diag = math.sqrt(sum(float(dom[f"{a}max"] - dom[f"{a}min"]) ** 2 for a in "xyz"))
    tol = 1e-12 * diag
    m = result.mesh
    nodes = [[Fraction(float(c)) for c in row] for row in m.nodes.tolist()]
    cx = result.complex
    meshed = set(result.face_of_facet)
    bad = 0
    # complex faces, exactly (pm rationals): every face under a name lies on its part's surface, and
    # every face on a part's surface lists the part (and only those parts)
    for face in cx.faces:
        if face.index not in meshed:
            continue
        loops = [[tuple(Fraction(c) / PM for c in p) for p in lp] for lp in face.loops]
        pts = [p for lp in loops for p in lp]
        on = {n for n, s in S.items() if _on(s, pts, loops=loops if face.axis == 2 else None)}
        bad += on != set(face.provenance)
    # mesh faces: on the rounded surface, exactly for axis-aligned parts, within tol for sloped edges
    for name, faces in result.provenance_faces.items():
        s = _rounded(S[name])
        sloped = s[0] == "side" or (s[4] is not None and any(
            a[0] != b[0] and a[1] != b[1] for a, b in zip(s[4], s[4][1:] + s[4][:1])))
        for f in faces.tolist():
            bad += not _on(s, [nodes[v] for v in f], tol if sloped else 0)
    for name, faces in result.provenance_faces.items():
        p = m.nodes[faces]
        area = float(np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum() / 2)
        exact = sum(float(Fraction(f.area) / (PM * PM)) for f in cx.faces if name in f.provenance and f.index in meshed)
        bad += abs(area - exact) > 1e-12 * exact
    tagged = [tuple(sorted(f)) for t in m.tagged_faces for f in m.tagged_faces[t].tolist()]
    bad += len(tagged) - len(set(tagged))
    exterior = {tuple(sorted(f)) for fi, i in enumerate(result.face_of_facet) if cx.faces[i].exterior
                for f in result.facet_faces[fi].tolist()}
    bad += len(exterior ^ set(tagged))
    return bad


# ----------------------------------------------------------------------------- G1-P: the sets

GRIDP = (4, 3, 2)                       # domain [0, 4] x [0, 3] x [0, 2] mm; profiles on a 0.5 mm grid


def _num(q: Fraction):
    return int(q) if q.denominator == 1 else float(q)


def _star(rng, pts):
    """The points in angular order around their mean (a simple, star-shaped polygon), or None."""
    pts = list(dict.fromkeys(pts))
    if len(pts) < 3:
        return None
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    keyed = sorted(pts, key=lambda p: math.atan2(float(p[1] - cy), float(p[0] - cx)))
    angles = [math.atan2(float(p[1] - cy), float(p[0] - cx)) for p in keyed]
    if len(set(angles)) != len(angles) or (cx, cy) in keyed:
        return None
    n = len(keyed)
    for i in range(n):                   # no three consecutive points on one line
        a, b, c = keyed[i - 1], keyed[i], keyed[(i + 1) % n]
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0:
            return None
    return keyed


def g1p_case(seed):
    rng = random.Random(seed)
    half = lambda lo, hi: Fraction(rng.randint(2 * lo, 2 * hi), 2)  # noqa: E731
    features, corners = [], []
    if rng.random() < 0.25:
        layers = [{"name": f"L{j}", "thickness": rng.choice([1, 0.5]), "material": f"s{j}"}
                  for j in range(rng.randint(1, 2))]
        features.append({"name": "stack", "type": "layers", "z0": 0, "layers": layers})
    n = rng.randint(1, 8 - len(features))
    for i in range(n):
        name = f"f{i}"
        kind = rng.choice(["box", "rect", "trapezoid", "polygon", "polygon", "polygon"])
        zmin = rng.randint(-1 if rng.random() < 0.1 else 0, GRIDP[2] - 1)
        zmax = rng.randint(zmin + 1, GRIDP[2] + (1 if rng.random() < 0.1 else 0))
        material = None if rng.random() < 0.15 else f"m{i}"
        if kind == "box":
            x0, y0 = half(0, GRIDP[0] - 1), half(0, GRIDP[1] - 1)
            x1, y1 = x0 + half(1, 3), y0 + half(1, 2)
            f = {"type": "box", "xmin": _num(x0), "xmax": _num(x1), "ymin": _num(y0), "ymax": _num(y1)}
            poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        elif kind == "rect":
            x, y, w, h = half(0, GRIDP[0] - 1), half(0, GRIDP[1] - 1), half(1, 3), half(1, 2)
            f = {"type": "extrude", "profile": {"type": "rect", "x": _num(x), "y": _num(y), "w": _num(w),
                                                "h": _num(h)}}
            poly = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        elif kind == "trapezoid":
            cx, y, w, wt, h = half(1, 3), half(0, 2), half(1, 3), half(1, 3), half(1, 2)
            f = {"type": "extrude", "profile": {"type": "trapezoid", "cx": _num(cx), "y": _num(y), "w": _num(w),
                                                "w_top": _num(wt), "h": _num(h)}}
            poly = [(cx - w / 2, y), (cx + w / 2, y), (cx + wt / 2, y + h), (cx - wt / 2, y + h)]
        else:
            poly = None
            for _ in range(50):
                pts = [(half(0, GRIDP[0]), half(0, GRIDP[1])) for _ in range(rng.randint(3, 6))]
                if corners and rng.random() < 0.5:              # share a vertex: a touch or a T-junction
                    pts[0] = rng.choice(corners)
                poly = _star(rng, pts)
                if poly is not None:
                    break
            if poly is None:
                poly = [(Fraction(0), Fraction(0)), (Fraction(1), Fraction(0)), (Fraction(0), Fraction(1))]
            prof = {"type": "polygon", "points": [[_num(x), _num(y)] for x, y in poly]}
            if rng.random() < 0.3:
                prof["edges"] = [f"s{j}" for j in range(len(poly))]
            f = {"type": "extrude", "profile": prof}
        f.update({"name": name, "material": material})
        if kind == "box":
            f.update({"zmin": zmin, "zmax": zmax})
        else:
            f.update({"zmin": zmin, "zmax": zmax})
        features.append(f)
        n_ = len(poly)
        corners += list(poly) + [((poly[j][0] + poly[(j + 1) % n_][0]) / 2, (poly[j][1] + poly[(j + 1) % n_][1]) / 2)
                                 for j in range(n_)]
    background = None if seed % 2 else "bg"
    return features, background


def g1p_doc(seed):
    features, background = g1p_case(seed)
    d = doc(features, domain=(0, GRIDP[0], 0, GRIDP[1], 0, GRIDP[2]), background=background, size="0.25 mm")
    return d, background


def _comp(d):
    return d["geometry"]["components"]["c"]


def _mesh_or_void(d):
    """The mesh, or None when every region is void (nothing to mesh; that refusal is asserted)."""
    try:
        return build_mesh3d(d)
    except GeometryError as err:
        if "has nothing to mesh" in str(err):
            return None
        raise


@pytest.mark.parametrize("seed", G1P_SEEDS)
def test_g1p_g2_g3_later_wins_prisms_against_the_oracle(seed):
    d, background = g1p_doc(seed)
    comp = _comp(d)
    prisms = prisms_of(comp)
    result = _mesh_or_void(d)
    if result is None:
        assert not oracle_volumes(comp, prisms, background), f"seed {seed}: refused, but the oracle has volume"
        return
    wrong, worst = g1_metrics(result, comp, prisms, background)
    assert wrong == 0, f"G1-P(a) seed {seed}: {wrong} tetrahedra in another region"
    assert worst <= 1e-12, f"G1-P(b) seed {seed}: relative volume error {worst:.3e}"
    assert g2_violations(result, comp, prisms) == 0, f"G2 seed {seed}"
    assert s1.v1_bad(result.mesh) == 0, f"G3 V1 seed {seed}"
    assert s1.check_v2(result)


def test_g1p_cases_have_every_profile_touches_t_junctions_and_voids():
    """The seeded sets exercise what G1-P is about (counted over all 200)."""
    kinds, shared, void, layers, edges = set(), 0, 0, 0, 0
    for seed in range(200):
        features, background = g1p_case(seed)
        for f in features:
            if f["type"] == "extrude":
                kinds.add(f["profile"]["type"])
                edges += "edges" in f["profile"]
            elif f["type"] == "layers":
                layers += 1
            void += f.get("material", "x") is None
        pts = [tuple(p) for f in features if f["type"] == "extrude" and f["profile"]["type"] == "polygon"
               for p in f["profile"]["points"]]
        shared += len(pts) != len(set(pts))
    assert kinds == {"rect", "trapezoid", "polygon"}
    assert shared >= 20 and void >= 20 and layers >= 20 and edges >= 20


# ----------------------------------------------------------------------------- A4: part names

def test_a4_extrude_part_names():
    feats = [
        {"name": "pad", "type": "extrude", "profile": {"type": "rect", "x": 1, "y": 1, "w": 2, "h": 1},
         "zmin": 0, "zmax": 1, "material": "Cu"},
        {"name": "tz", "type": "extrude", "profile": {"type": "trapezoid", "cx": 6, "y": 1, "w": 3, "w_top": 1,
                                                      "h": 2}, "zmin": 0.5, "zmax": 2, "material": "Cu"},
        {"name": "poly", "type": "extrude", "profile": {"type": "polygon", "points": [[1, 5], [4, 5], [2, 8]],
                                                        "edges": ["base", "slope", "back"]},
         "zmin": 1, "zmax": 2, "material": "Al"},
        {"name": "p2", "type": "extrude", "profile": {"type": "polygon", "points": [[6, 5], [9, 6], [8, 9], [7, 7]]},
         "zmin": 0, "zmax": 2.5, "material": "Al"},
    ]
    cx = evaluate3d(s1_model(doc(feats)))
    names = set().union(*(f.provenance for f in cx.faces))
    expected = {"pad.bottom", "pad.top", "pad.left", "pad.right", "pad.y0", "pad.y1",
                "tz.bottom", "tz.top", "tz.left", "tz.right", "tz.y0", "tz.y1",
                "poly.bottom", "poly.top", "poly.base", "poly.slope", "poly.back",
                "p2.bottom", "p2.top", "p2.e1", "p2.e2", "p2.e3", "p2.e4"}
    assert {n for n in names if not n.startswith("domain.")} == expected
    assert not any(n.endswith((".x0", ".x1")) for n in expected)


def s1_model(d):
    from simcase import parse_geometry
    return parse_geometry(d)


def test_extrude_parts_are_boundary_selectors():
    feats = [{"name": "tz", "type": "extrude", "profile": {"type": "trapezoid", "cx": 5, "y": 2, "w": 4, "w_top": 2,
                                                           "h": 4}, "zmin": 0, "zmax": 2.5, "material": "Cu"}]
    d = doc(feats, size="1 mm", component={"selections": {"slope": {"boundary": "tz.right"},
                                                           "cap": {"boundary": "tz.top"}}})
    result = build_mesh3d(d)
    kind, faces = result.selections["slope"]
    assert kind == "boundary" and len(faces) > 0
    n = result.mesh.nodes[faces].reshape(-1, 3)
    # the right side runs from (7, 2) to (6, 6) mm: x + y/4 = 7.5 mm on every node of it
    assert np.allclose(n[:, 0] + n[:, 1] / 4, 7.5e-3, rtol=0, atol=1e-15)
    kind, faces = result.selections["cap"]
    assert np.all(result.mesh.nodes[faces][..., 2] == 2.5e-3)


# ----------------------------------------------------------------------------- G6: refusals

def test_g6_a_circle_profile_is_refused_by_name():
    feats = [s1.BOX, {"name": "pad", "type": "extrude", "profile": {"type": "circle", "cx": 7, "cy": 7, "r": 1},
                      "zmin": 0, "zmax": 1, "material": "Cu"}]
    with pytest.raises(GeometryError) as err:
        build_mesh3d(doc(feats))
    assert err.value.code == "E-3D-COMBINATION"
    assert err.value.path == "geometry.components.c.features[1]"
    assert ("extrude 'pad' is not taken yet in a 3d component (an extruded circle is a cylinder); boxes, slab "
            "layers and rect, trapezoid and polygon extrudes are") in str(err.value)


def test_g6_derived_coordinates_rounding_to_one_double_are_refused_by_both_names():
    k = 5 * 10 ** 16                          # 50 km in pm: doubles are 7.3 pm apart there
    Y = k // 2
    feats = [{"name": "A", "type": "extrude", "profile": {"type": "rect", "x": 0, "y": 0, "w": 2 * k, "h": Y},
              "zmin": 0, "zmax": k, "material": "Cu"},
             # B's vertex at x = k - 3 pm (edges e2, e3) and its edge e3 crossing A's top edge (y = Y) at the
             # derived x = k - 1 pm: the first two values that round together (e1 crosses it at k + 1/2)
             {"name": "B", "type": "extrude", "profile": {"type": "polygon",
                                                          "points": [[k, Y - 1], [k + 1, Y + 1], [k - 3, Y + 2]]},
              "zmin": 0, "zmax": k, "material": "Al"}]
    d = doc(feats, unit="pm", domain=(0, 2 * k, 0, 2 * k, 0, k), background=None, size="10 km")
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-3D-COMBINATION"
    assert err.value.path == "geometry.components.c.features[1]"
    assert "B.e2 and A.y1 round to the same coordinate 50000.0 m" in str(err.value)


# ----------------------------------------------------------------------------- F: T-junction fuzz

def fuzz_case(seed):
    """Two or three polygon extrudes in pm: B has a vertex on the interior of A's sloped edge PQ; C,
    when present, has an edge along a piece of PQ (a sloped shared plane)."""
    rng = random.Random(10_000 + seed)
    while True:
        ux, uy = rng.randint(1, 5), rng.randint(1, 5)
        if math.gcd(ux, uy) == 1:
            break
    ux, uy = ux * rng.choice([1, -1]), uy * rng.choice([1, -1])
    m = rng.randint(2, 5)
    g = rng.randint(10 ** 8, 3 * 10 ** 8) // max(abs(ux), abs(uy)) // m + rng.randint(1, 999)
    d = (ux * g, uy * g)
    span = (m * d[0], m * d[1])
    P = (2 * 10 ** 9 - span[0] // 2 + rng.randint(-10 ** 6, 10 ** 6),
         int(1.5 * 10 ** 9) - span[1] // 2 + rng.randint(-10 ** 6, 10 ** 6))
    Q = (P[0] + span[0], P[1] + span[1])
    left = (-uy, ux)                                   # the normal to the left of P -> Q
    off = lambda s: (left[0] * g * s, left[1] * g * s)  # noqa: E731
    mid = ((P[0] + Q[0]) // 2, (P[1] + Q[1]) // 2)
    a3 = off(rng.randint(2, 4))
    A = [P, Q, (mid[0] + a3[0], mid[1] + a3[1])]
    j = rng.randint(1, m - 1)
    T = (P[0] + j * d[0], P[1] + j * d[1])
    b = off(-rng.randint(2, 4))
    B = [T, (T[0] + b[0] - d[0], T[1] + b[1] - d[1]), (T[0] + b[0] + d[0], T[1] + b[1] + d[1])]
    polys = [("A", A), ("B", B)]
    if rng.random() < 0.6:
        j1 = rng.randint(0, m - 1)
        j2 = rng.randint(j1 + 1, m)
        c = off(-rng.randint(1, 3))
        S0, S1 = (P[0] + j1 * d[0], P[1] + j1 * d[1]), (P[0] + j2 * d[0], P[1] + j2 * d[1])
        polys.append(("C", [S0, S1, ((S0[0] + S1[0]) // 2 + c[0], (S0[1] + S1[1]) // 2 + c[1])]))
    feats = []
    for name, pts in polys:
        z0 = rng.choice([0, 0, 5 * 10 ** 8])
        z1 = rng.choice([15 * 10 ** 8, 2 * 10 ** 9])
        feats.append({"name": name, "type": "extrude", "profile": {"type": "polygon",
                                                                   "points": [list(p) for p in pts]},
                      "zmin": z0, "zmax": z1, "material": name.lower()})
    e = 10 ** 9
    return doc(feats, unit="pm", domain=(0, 4 * e, 0, 3 * e, 0, 2 * e), background="bg", size="0.25 mm")


def test_fuzz_t_junction_prisms_mesh_or_raise_a_named_rounding_error():
    meshed, rounding, failures = 0, 0, []
    for seed in FUZZ_SEEDS:
        d = fuzz_case(seed)
        comp = _comp(d)
        prisms = prisms_of(comp)
        try:
            result = build_mesh3d(d)
        except Mesh3DError as err:
            if isinstance(err.cause, meshloom.RoundingError) and err.provenance:
                rounding += 1
            else:
                failures.append((seed, f"{type(err.cause).__name__}: {err}"))
            continue
        except Exception as err:  # noqa: BLE001 - every other exception is a failure to report
            failures.append((seed, f"{type(err).__name__}: {err}"))
            continue
        wrong, worst = g1_metrics(result, comp, prisms, "bg")
        v1 = s1.v1_bad(result.mesh)
        try:
            s1.check_v2(result)
            v2 = True
        except AssertionError:
            v2 = False
        if wrong or worst > 1e-12 or v1 or not v2:
            failures.append((seed, f"wrong {wrong}, volume {worst:.3e}, V1 {v1}, V2 {v2}"))
        else:
            meshed += 1
    print(f"T-junction fuzz: {meshed} meshed, {rounding} RoundingError, {len(failures)} other of {len(FUZZ_SEEDS)}")
    assert not failures, failures
    assert meshed >= FUZZ_FLOOR, f"{meshed} of {len(FUZZ_SEEDS)} meshed; the floor is {FUZZ_FLOOR}"


# ----------------------------------------------------------------------------- S1: slice 1 unchanged

def complex_digest(cx) -> str:
    h = hashlib.sha256()
    h.update(repr(cx.levels).encode())
    for c in cx.cells:
        h.update(repr((c.index, c.region, c.material, c.feature, c.feature_index, c.provenance, c.mesh_size,
                       c.fine, c.slab, c.volume)).encode())
    for f in cx.faces:
        h.update(repr((f.index, f.axis, f.coord, f.loops, sorted(f.provenance), sorted(f.minus), sorted(f.plus),
                       f.exterior, f.tag, f.area)).encode())
    return h.hexdigest()


def slice1_digests(seed):
    d, _, _ = s1.g1_doc(seed)
    result = build_mesh3d(d)
    return {"complex": complex_digest(result.complex), "mesh": s1.digest(result)}


@pytest.mark.parametrize("seed", list(range(0, 200, 8)))
def test_s1_slice1_complexes_and_meshes_are_unchanged(seed):
    recorded = json.loads(DIGESTS.read_text(encoding="utf-8"))
    assert slice1_digests(seed) == recorded[str(seed)]


def test_through_meshloom_hook_is_unchanged_for_e1():
    """E1 (slab layers only) through meshloom: the same SHA-256 as slice 1's G4 (same digest function)."""
    recorded = json.loads(DIGESTS.read_text(encoding="utf-8"))
    assert s1.digest(_build(s1.e1(), through_meshloom=True)) == recorded["e1"]
