# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``simcase.display_shapes3d``: the display of a 3d component with cylinders or spheres in one of
meshloom's builder shapes (Studio 3D design 4.3, 5.1; decision 2026-11-28-openphysics-studio-3d-e2-display).

The display is not the mesh. Planar faces lie exactly on their plane; a circle is drawn as the inscribed
n-gon of n = min(256, max(48, ceil(2 pi r / l))) segments, a cylinder side as that n-gon's prism and a
sphere as an icosahedral geodesic grid of frequency f = min(64, max(8, ceil(1.05 r / l))) with every
vertex on the sphere; l = the domain diagonal / 200. Face names are the mesh's provenance names.

Pre-registered checks (adopted design 8; fixed before measuring, never loosened). Cases C1, C4, C5 and
C11 of slice 3 and card 2 (C4 at E2's values):

- W1 (a): every display triangle carries a face id, and its face's name set equals the name set of the
  exact surface it draws (the table ``EXPECTED`` below, written from slice 3's tag tables): 0 mismatches.
- W1 (b): on every planar face, every vertex lies exactly on the face's plane, by an exact test on the pm
  values before float32 (``vertices[:, axis] == coord``): 0 off the plane.
- W2: display areas against the exact areas (s(x) = sin x / x):
  - a rectangle: |A_h - A| / A <= 1e-6;
  - a disc (inscribed n-gon): A_h <= A (1 + 1e-12) and (A - A_h) / A <= 1 - s(2 pi / n) + 1e-12;
  - an annulus (rectangle minus that n-gon): 0 <= A_h - A <= pi r^2 (1 - s(2 pi / n)) + 1e-12 A;
  - a cylinder side (inscribed prism): A_h <= A (1 + 1e-12) and (A - A_h) / A <= 1 - s(pi / n) + 1e-12;
  - a sphere (inscribed convex polyhedron): 0 <= (A - A_h) / A <= max_f (rho_f / R)^2 + 1e-12, rho_f
    the circumradius of drawn triangle f in its plane (radial projection maps a face at distance
    h_f = sqrt(R^2 - rho_f^2) from the centre onto at most (R / h_f)^2 its area).

Also tested, without numeric thresholds: the segment counts and frequencies follow the rule; the
sections' exact outlines (a z cut of a cylinder is its n-gon, an x cut two lines at +-sqrt(r^2 - d^2), a
sphere cut a circle of radius sqrt(r^2 - d^2)); regions and their exact volumes; a component without
cylinders or spheres, and a cylinder no builder takes, are refused by name; display_complex3d still
refuses a sampled surface.
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest

import simcase
from simcase import GeometryError, display_complex3d, display_shapes3d, parse_geometry

PM = 10 ** 12
CARD2 = Path(simcase.__file__).parent / "studio" / "static" / "model3d-via-slab-3d.json"


def doc(features, domain, background, h=0.1):
    keys = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    comp = {"dimension": "3d", "length_unit": "m", "domain": dict(zip(keys, domain)),
            "background": {"material": background}, "features": features}
    return {"openphysics": "0.3", "geometry": {"version": 1, "components": {"c": comp}},
            "mesh": {"element_size": f"{h} m"}}


def c4():
    return doc([{"name": "via", "type": "cylinder", "cx": 0, "cy": 0, "r": 0.3, "zmin": 0, "zmax": 1,
                 "material": "Cu"}], (-1, 1, -1, 1, 0, 1), "FR4")


def c5():
    return doc([{"name": "ball", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.5, "material": "Cu"}],
               (-1, 1, -1, 1, -1, 1), "air")


def c11():
    return doc([{"name": "sc", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 1, "material": "eps4"},
                {"name": "sb", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.75, "material": "eps1"},
                {"name": "sa", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.5, "material": None}],
               (-1.2, 1.2, -1.2, 1.2, -1.2, 1.2), None)


def c1():
    return doc([{"name": "ball", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 1, "material": "Cu"}],
               (-1.2, 1.2, -1.2, 1.2, -1.2, 1.2), None)


def card2():
    return json.loads(CARD2.read_text(encoding="utf-8"))


SIDES = [frozenset({f"domain.{s}"}) for s in ("x0", "x1", "y0", "y1")]
BOX = [frozenset({f"domain.{s}"}) for s in ("x0", "x1", "y0", "y1", "z0", "z1")]
VIA = SIDES + [frozenset({"domain.z0"}), frozenset({"via.bottom", "domain.z0"}),
               frozenset({"domain.z1"}), frozenset({"via.top", "domain.z1"}), frozenset({"via.side"})]
# the exact surfaces of each case: name set -> (shape, tag), from slice 3's tag tables
EXPECTED = {
    "C4": {**{s: ("plane", next(iter(s)).split(".")[1]) for s in SIDES},
           frozenset({"domain.z0"}): ("plane", "z0"), frozenset({"via.bottom", "domain.z0"}): ("plane", "z0"),
           frozenset({"domain.z1"}): ("plane", "z1"), frozenset({"via.top", "domain.z1"}): ("plane", "z1"),
           frozenset({"via.side"}): ("cylinder", None)},
    "C5": {**{s: ("plane", next(iter(s)).split(".")[1]) for s in BOX}, frozenset({"ball.surface"}): ("sphere", None)},
    "C11": {frozenset({"sa.surface"}): ("sphere", "void"), frozenset({"sb.surface"}): ("sphere", None),
            frozenset({"sc.surface"}): ("sphere", "void")},
    "C1": {frozenset({"ball.surface"}): ("sphere", "void")},
}
EXPECTED["card 2"] = EXPECTED["C4"]
CASES = {"C1": c1, "C4": c4, "C5": c5, "C11": c11, "card 2": card2}


def shown(name):
    data = CASES[name]()
    return display_shapes3d(parse_geometry(data))


def s(x):
    return math.sin(x) / x


def tri_area(p):
    return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)


def test_the_names_are_public():
    assert {"display_shapes3d", "Display3D"} <= set(simcase.__all__)


@pytest.mark.parametrize("name", list(CASES))
def test_w1_every_triangle_carries_its_exact_surface_s_names_and_planar_ones_lie_on_their_plane(name):
    d = shown(name)
    expected = EXPECTED[name]
    mismatches, off = 0, 0
    seen = set()
    for i, f in enumerate(d.faces):
        assert f.index == i
        assert len(f.triangles) > 0
        if f.triangles.max() >= len(f.vertices) or frozenset(f.names) not in expected:
            mismatches += len(f.triangles)
            continue
        shape, tag = expected[frozenset(f.names)]
        if (f.shape, f.tag) != (shape, tag):
            mismatches += len(f.triangles)
        seen.add(frozenset(f.names))
        if f.shape == "plane":
            off += int(np.count_nonzero(f.vertices[:, f.axis] != f.coord))
            assert isinstance(f.coord, int)
    print(f"W1 {name}: {sum(len(f.triangles) for f in d.faces)} triangles, {mismatches} mismatches, {off} off plane")
    assert mismatches == 0 and seen == set(expected)
    assert off == 0


@pytest.mark.parametrize("name", list(CASES))
def test_w2_display_areas_are_within_their_bounds(name):
    d = shown(name)
    worst = {}
    for f in d.faces:
        p = f.vertices[f.triangles] / PM                    # m
        a_h = float(tri_area(p).sum())
        a = f.area
        if f.shape == "plane" and f.circle is None:
            err = abs(a_h - a) / a
            assert err <= 1e-6, (f.names, err)
        elif f.shape == "plane" and f.kind == "disc":
            n, r = f.segments, f.circle[1] / PM
            assert a_h <= a * (1 + 1e-12) and (a - a_h) / a <= 1 - s(2 * math.pi / n) + 1e-12, f.names
            err = (a - a_h) / a
        elif f.shape == "plane":                            # annulus: the rectangle minus the n-gon
            n, r = f.segments, f.circle[1] / PM
            assert 0 <= a_h - a <= math.pi * r * r * (1 - s(2 * math.pi / n)) + 1e-12 * a, f.names
            err = (a_h - a) / a
        elif f.shape == "cylinder":
            n = f.segments
            assert a_h <= a * (1 + 1e-12) and (a - a_h) / a <= 1 - s(math.pi / n) + 1e-12, f.names
            err = (a - a_h) / a
        else:
            R = f.radius / PM
            q = p - f.centre / PM
            ab, ac = q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]
            cross = np.cross(ab, ac)
            # circumradius of each triangle in its plane: |ab| |ac| |bc| / (4 area)
            rho = (np.linalg.norm(ab, axis=1) * np.linalg.norm(ac, axis=1) * np.linalg.norm(q[:, 2] - q[:, 1], axis=1)
                   / (2 * np.linalg.norm(cross, axis=1)))
            bound = float((rho.max() / R) ** 2)
            err = (a - a_h) / a
            assert -1e-12 <= err <= bound + 1e-12, (f.names, err, bound)
            worst.setdefault("sphere bound", []).append(round(bound, 6))
        worst.setdefault(f.shape if f.circle is None else f.kind, []).append(float(f"{err:.3e}"))
    print(f"W2 {name}: l = {d.ell / PM:.6g} m;", json.dumps(worst))


@pytest.mark.parametrize("name", list(CASES))
def test_the_segment_counts_follow_the_rule(name):
    d = shown(name)
    ell = d.ell
    for f in d.faces:
        if f.shape == "cylinder" or f.circle is not None:
            r = f.radius if f.shape == "cylinder" else f.circle[1]
            assert f.segments == min(256, max(48, math.ceil(2 * math.pi * r / ell)))
        if f.shape == "sphere":
            assert f.segments == min(64, max(8, math.ceil(1.05 * f.radius / ell)))
            assert len(f.triangles) == 20 * f.segments ** 2
            assert np.allclose(np.linalg.norm(f.vertices - f.centre, axis=1), f.radius, rtol=1e-12, atol=0)
    diag = math.dist(*[[d.domain[f"{a}{e}"] for a in "xyz"] for e in ("min", "max")])
    assert ell == diag / 200


def test_regions_and_exact_volumes():
    d = shown("C4")
    vol = {r.name: r.volume for r in d.regions}
    assert set(vol) == {"background", "via"}
    assert vol["via"] == pytest.approx(math.pi * 0.09, rel=1e-15)
    assert vol["background"] == pytest.approx(4 - math.pi * 0.09, rel=1e-15)
    d = shown("C11")
    vol = {r.name: (r.volume, r.material) for r in d.regions}
    assert vol == {"sb": (pytest.approx(4 / 3 * math.pi * (0.75 ** 3 - 0.5 ** 3), rel=1e-14), "eps1"),
                   "sc": (pytest.approx(4 / 3 * math.pi * (1 - 0.75 ** 3), rel=1e-14), "eps4")}


def test_sections_are_the_exact_outlines():
    d = shown("C4")
    side = next(f for f in d.faces if f.shape == "cylinder")
    n = side.segments
    cut = [seg for seg in d.section("z", PM // 2) if seg.face == side.index]
    assert len(cut) == n
    for seg in cut:
        for p in (seg.p, seg.q):
            assert p[2] == PM // 2 and math.hypot(p[0], p[1]) == pytest.approx(0.3 * PM, rel=1e-14)
    cut = [seg for seg in d.section("x", PM // 10) if seg.face == side.index]
    y = math.sqrt(0.3 ** 2 - 0.1 ** 2) * PM
    assert sorted(round(seg.p[1] / PM, 12) for seg in cut) == [round(-y / PM, 12), round(y / PM, 12)]
    assert all(seg.p[0] == seg.q[0] == PM // 10 and {seg.p[2], seg.q[2]} == {0, PM} for seg in cut)
    # the bottom annulus cut by x = 0.1 m: the rectangle's chord minus the via's chord, two segments
    annulus = next(f for f in d.faces if set(f.names) == {"domain.z0"})
    parts = sorted(sorted((seg.p[1], seg.q[1])) for seg in d.section("x", PM // 10) if seg.face == annulus.index)
    assert [[round(v / PM, 12) for v in p] for p in parts] == [[-1.0, round(-y / PM, 12)], [round(y / PM, 12), 1.0]]
    d = shown("C5")
    ball = next(f for f in d.faces if f.shape == "sphere")
    cut = [seg for seg in d.section("y", PM // 4) if seg.face == ball.index]
    rho = math.sqrt(0.25 - 0.0625) * PM
    assert len(cut) == min(256, max(48, math.ceil(2 * math.pi * rho / d.ell)))
    assert all(math.hypot(p[0], p[2]) == pytest.approx(rho, rel=1e-14) and p[1] == PM // 4
               for seg in cut for p in (seg.p, seg.q))
    assert d.section_regions("y", PM // 4) == ["background", "ball"]
    assert d.section_regions("y", 3 * PM // 4) == ["background"]


def test_refusals():
    boxes = doc([{"name": "b", "type": "box", "xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1,
                  "material": "Cu"}], (0, 2, 0, 2, 0, 2), "air")
    with pytest.raises(GeometryError, match="display_complex3d"):
        display_shapes3d(parse_geometry(boxes))
    short = doc([{"name": "pin", "type": "cylinder", "cx": 0, "cy": 0, "r": 0.3, "zmin": 0, "zmax": 0.5,
                  "material": "Cu"}], (-1, 1, -1, 1, 0, 1), "FR4")
    with pytest.raises(GeometryError) as err:
        display_shapes3d(parse_geometry(short))
    assert err.value.code == "E-3D-COMBINATION" and "is not taken yet in a 3d component" in str(err.value)
    with pytest.raises(GeometryError, match="holds sampled surfaces"):
        display_complex3d(parse_geometry(c4()))         # unchanged: the exact complex of a sampled surface
