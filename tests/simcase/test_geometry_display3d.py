# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``simcase.display_shapes3d``: the display shape of cylinders and spheres in meshloom's builder shapes.

The display is not the mesh: its faces carry the mesh's provenance names (so a pick gives the mesh's
names), its planar faces lie exactly on their planes, and its curved faces follow the display rule of
the adopted design (decision 2026-11-28-openphysics-studio-3d-e2-display, section 4.3): l = domain
diagonal / 200; a cylinder side and the discs and annuli its ends cut take the inscribed n-gon,
n = min(256, max(48, ceil(2 pi r / l))); a sphere is an icosahedral geodesic grid of frequency
f = min(64, max(8, ceil(1.05 r / l))) with every vertex on the sphere.

Pre-registered checks (fixed before measuring; never loosened):
- W1(b) (PR), cases C1, C4, C5, C11 and card 2: on every planar face, ``vertices[:, axis] == coord``
  exactly, in pm before float32: 0 off-plane vertices. (W1(a), the mesh triangles' face ids, needs a
  mesh: tests/simcase/test_studio_model3d_shapes_mesh.py.)
- W2 (PR), display areas against the exact areas, s(x) = sin x / x:
  rectangles: relative error <= 1e-6;
  disc: A_h <= A (1 + 1e-12) and (A - A_h) / A <= 1 - s(2 pi / n) + 1e-12;
  annulus: 0 <= A_h - A <= pi r^2 (1 - s(2 pi / n)) + 1e-12 A;
  cylinder side: A_h <= A (1 + 1e-12) and (A - A_h) / A <= 1 - s(pi / n) + 1e-12;
  sphere: 0 <= (A - A_h) / A <= max_f (rho_f / R)^2 + 1e-12, rho_f each drawn triangle's circumradius in
  its plane (radial projection: dA_sphere <= (R / h_f)^2 dA).
Also tested without thresholds of their own: each shape's faces against an expected table written here
from slice 3's tag tables (names, shape, tag, sides), the refusals, the exact sections and the rule's n
and f.
"""

import math
from fractions import Fraction

import numpy as np
import pytest

from simcase import Display3D, GeometryError, display_complex3d, display_shapes3d, parse_geometry

PM = 10 ** 12


def doc(features, domain, background, *, name="c", unit="m"):
    keys = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    return {"openphysics": "0.3", "geometry": {"version": 1, "components": {name: {
        "dimension": "3d", "length_unit": unit, "domain": dict(zip(keys, domain)),
        "background": {"material": background}, "features": features}}}}


def c4(cx=0, cy=0, r=0.3):
    return doc([{"name": "via", "type": "cylinder", "cx": cx, "cy": cy, "r": r, "zmin": 0, "zmax": 1,
                 "material": "Cu"}], (-1, 1, -1, 1, 0, 1), "FR4")


def c5(r=0.5, c=(0, 0, 0)):
    return doc([{"name": "ball", "type": "sphere", "cx": c[0], "cy": c[1], "cz": c[2], "r": r, "material": "Cu"}],
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
    import json
    from pathlib import Path
    import simcase
    path = Path(simcase.__file__).parent / "studio" / "static" / "model3d-via-slab-3d.json"
    return json.loads(path.read_text(encoding="utf-8"))


# Expected faces, from slice 3's tag tables (geometry_builders3d.prepare's exterior and interior maps and
# test_geometry_engine3d_curved's): name set -> (shape, tag, minus regions, plus regions). Curved faces
# have the outside as minus and the inside as plus.
def _c4_table(slab="background"):
    return {
        ("domain.x0",): ("plane", "x0", (), (slab,)), ("domain.x1",): ("plane", "x1", (slab,), ()),
        ("domain.y0",): ("plane", "y0", (), (slab,)), ("domain.y1",): ("plane", "y1", (slab,), ()),
        ("domain.z0",): ("plane", "z0", (), (slab,)), ("domain.z0", "via.bottom"): ("plane", "z0", (), ("via",)),
        ("domain.z1",): ("plane", "z1", (slab,), ()), ("domain.z1", "via.top"): ("plane", "z1", ("via",), ()),
        ("via.side",): ("cylinder", None, (slab,), ("via",)),
    }


EXPECTED = {
    "C4": _c4_table(),
    "card2": _c4_table(),
    "C5": {**{(f"domain.{a}{e}",): ("plane", f"{a}{e}", () if e == "0" else ("background",),
                                     ("background",) if e == "0" else ()) for a in "xyz" for e in "01"},
           ("ball.surface",): ("sphere", None, ("background",), ("ball",))},
    "C1": {("ball.surface",): ("sphere", "void", ("background",), ("ball",))},
    "C11": {("sc.surface",): ("sphere", "void", ("background",), ("sc",)),
            ("sb.surface",): ("sphere", None, ("sc",), ("sb",)),
            ("sa.surface",): ("sphere", "void", ("sb",), ("sa",))},
}
CASES = {"C1": c1, "C4": c4, "C5": c5, "C11": c11, "card2": card2}


def shapes(make):
    return display_shapes3d(parse_geometry(make()))


@pytest.mark.parametrize("case", list(CASES))
def test_each_face_is_the_expected_table_row(case):
    d = shapes(CASES[case])
    assert isinstance(d, Display3D)
    got = {tuple(f.names): (f.shape, f.tag, tuple(f.minus), tuple(f.plus)) for f in d.faces}
    assert got == EXPECTED[case]
    assert [f.index for f in d.faces] == list(range(len(d.faces)))
    for f in d.faces:
        assert f.exterior == (f.tag is not None)
        assert tuple(f.names) == tuple(sorted(f.names))


@pytest.mark.parametrize("case", list(CASES))
def test_w1b_every_planar_vertex_is_on_its_exact_plane(case):
    d = shapes(CASES[case])
    off = 0
    planes = 0
    for f in d.faces:
        assert f.vertices.dtype == np.float64 and f.triangles.dtype == np.int64
        assert len(f.triangles) and f.triangles.min() >= 0 and f.triangles.max() < len(f.vertices)
        if f.shape == "plane":
            planes += 1
            assert isinstance(f.coord, int) and f.axis in (0, 1, 2)
            off += int(np.sum(f.vertices[:, f.axis] != f.coord))
            dom = d.domain
            lo, hi = dom["xyz"[f.axis] + "min"], dom["xyz"[f.axis] + "max"]
            assert lo <= f.coord <= hi
        else:
            assert f.axis is None and f.coord is None
    print(f"W1(b) {case}: {planes} planar faces, {off} off-plane vertices")
    assert off == 0


def _areas(f):
    p = f.vertices[f.triangles]
    return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)


def _circumradii(f):
    p = f.vertices[f.triangles]
    a = np.linalg.norm(p[:, 1] - p[:, 2], axis=1)
    b = np.linalg.norm(p[:, 0] - p[:, 2], axis=1)
    c = np.linalg.norm(p[:, 0] - p[:, 1], axis=1)
    return a * b * c / (4 * _areas(f))


def s(x):
    return math.sin(x) / x


def _feature(comp, kind):
    return next(f for f in comp.features if f.type == kind)


@pytest.mark.parametrize("case", list(CASES))
def test_w2_display_areas_against_the_exact_areas(case):
    make = CASES[case]
    comp = next(iter(parse_geometry(make()).components.values()))
    d = shapes(make)
    dom = {k: Fraction(v, PM) for k, v in comp.domain.items()}
    rows = []
    for f in d.faces:
        a_h = float(_areas(f).sum()) / PM ** 2                 # m^2
        a = f.area
        if f.shape == "plane":
            others = [k for k in "xyz" if k != "xyz"[f.axis]]
            rect = float(np.prod([dom[k + "max"] - dom[k + "min"] for k in others]))
            if f.segments == 0:                                  # a rectangle: exact
                assert a == pytest.approx(rect, rel=1e-15)
                err = abs(a_h - a) / a
                rows.append((f.names, "rectangle", err))
                assert err <= 1e-6
            else:
                via = _feature(comp, "cylinder").data
                r = via["r"] / PM
                n = f.segments
                disc = len(f.names) == 2                         # the via's end and the domain's face
                if disc:
                    assert a == pytest.approx(math.pi * r * r, rel=1e-15)
                    rows.append((f.names, "disc", (a - a_h) / a))
                    assert a_h <= a * (1 + 1e-12)
                    assert (a - a_h) / a <= 1 - s(2 * math.pi / n) + 1e-12
                else:
                    assert a == pytest.approx(rect - math.pi * r * r, rel=1e-15)
                    rows.append((f.names, "annulus", (a_h - a) / a))
                    assert 0 <= a_h - a <= math.pi * r * r * (1 - s(2 * math.pi / n)) + 1e-12 * a
        elif f.shape == "cylinder":
            via = _feature(comp, "cylinder").data
            r, length = via["r"] / PM, (via["zmax"] - via["zmin"]) / PM
            assert a == pytest.approx(2 * math.pi * r * length, rel=1e-15)
            n = f.segments
            rows.append((f.names, "cylinder", (a - a_h) / a))
            assert a_h <= a * (1 + 1e-12)
            assert (a - a_h) / a <= 1 - s(math.pi / n) + 1e-12
        else:
            sphere = next(x for x in comp.features if f"{x.id}.surface" in f.names).data
            big_r = sphere["r"] / PM
            assert a == pytest.approx(4 * math.pi * big_r ** 2, rel=1e-15)
            bound = float(np.max(_circumradii(f) / PM / big_r) ** 2)
            rows.append((f.names, f"sphere f={f.segments}", (a - a_h) / a, bound))
            assert 0 <= (a - a_h) / a <= bound + 1e-12
    for row in rows:
        print("W2", case, *row)


@pytest.mark.parametrize("case", list(CASES))
def test_the_rule_gives_n_and_f_and_curved_vertices_lie_on_the_exact_surfaces(case):
    make = CASES[case]
    comp = next(iter(parse_geometry(make()).components.values()))
    d = shapes(make)
    dom = comp.domain
    diag = math.sqrt(sum((dom[a + "max"] - dom[a + "min"]) ** 2 for a in "xyz"))
    assert d.length == diag / 200
    for f in d.faces:
        if f.shape == "cylinder" or (f.shape == "plane" and f.segments):
            via = _feature(comp, "cylinder").data
            r = via["r"]
            assert f.segments == min(256, max(48, math.ceil(2 * math.pi * r / d.length)))
            ring = f.vertices if f.shape == "cylinder" else f.vertices[
                np.abs(np.hypot(f.vertices[:, 0] - via["cx"], f.vertices[:, 1] - via["cy"]) - r) <= 1e-9 * r]
            assert len(ring) == (2 if f.shape == "cylinder" else 1) * f.segments
            dist = np.hypot(ring[:, 0] - via["cx"], ring[:, 1] - via["cy"])
            assert np.max(np.abs(dist - r)) <= 1e-15 * (r + abs(via["cx"]) + abs(via["cy"]))
        elif f.shape == "sphere":
            sp = next(x for x in comp.features if f"{x.id}.surface" in f.names).data
            r = sp["r"]
            assert f.segments == min(64, max(8, math.ceil(1.05 * r / d.length)))
            assert len(f.vertices) == 10 * f.segments ** 2 + 2 and len(f.triangles) == 20 * f.segments ** 2
            c = np.array([sp["cx"], sp["cy"], sp["cz"]], dtype=float)
            dist = np.linalg.norm(f.vertices - c, axis=1)
            assert np.max(np.abs(dist - r)) <= 1e-15 * (r + np.linalg.norm(c))


def near(v):
    """The exact formula's value, to the last bits of its float evaluation."""
    return pytest.approx(v, rel=1e-14)


@pytest.mark.parametrize("case", list(CASES))
def test_regions_carry_exact_volumes_and_their_faces(case):
    make = CASES[case]
    d = shapes(make)
    comp = next(iter(parse_geometry(make()).components.values()))
    dom = {k: v / PM for k, v in comp.domain.items()}
    box = (dom["xmax"] - dom["xmin"]) * (dom["ymax"] - dom["ymin"]) * (dom["zmax"] - dom["zmin"])
    regions = {r.name: r for r in d.regions}
    for r in d.regions:
        assert r.faces == tuple(f.index for f in d.faces if r.name in f.minus or r.name in f.plus)
    if case in ("C4", "card2"):
        v = math.pi * 0.09
        assert [r.name for r in d.regions] == ["via", "background"]
        assert regions["via"].volume == near(v) and regions["background"].volume == near(box - v)
        assert not regions["via"].void and not regions["background"].void
    elif case == "C5":
        v = 4 * math.pi / 3 * 0.125
        assert regions["ball"].volume == near(v) and regions["background"].volume == near(box - v)
    elif case == "C1":
        v = 4 * math.pi / 3
        assert regions["ball"].volume == near(v) and regions["background"].void
        assert regions["background"].volume == near(box - v)
    else:
        k = 4 * math.pi / 3
        assert [r.name for r in d.regions] == ["sc", "sb", "sa", "background"]
        assert regions["sc"].volume == near(k * (1 - 0.75 ** 3)) and regions["sb"].volume == near(k * (0.75 ** 3 - 0.5 ** 3))
        assert regions["sa"].volume == near(k * 0.5 ** 3) and regions["sa"].void and regions["sa"].material is None
        assert regions["background"].volume == near(box - k) and regions["background"].void


# ----------------------------------------------------------------------------- refusals

STAGED = ("is not taken yet in a 3d component; boxes and slab layers are, and cylinders and spheres in "
          "meshloom's builder shapes only (one cylinder through the whole slab, one sphere, concentric spheres)")


def _refused(d, component=None):
    with pytest.raises(GeometryError) as err:
        display_shapes3d(parse_geometry(d), component)
    return err.value


def test_a_cylinder_no_builder_takes_is_refused_in_the_builders_words():
    # slice A's non-builder cylinder (tests/simcase/test_studio_model3d.py): a cylinder beside a box
    feats = [{"name": "core", "type": "box", "xmin": -0.5, "xmax": 0.5, "ymin": -0.5, "ymax": 0.5, "zmin": 0,
              "zmax": 0.5, "material": "Cu"},
             {"name": "via", "type": "cylinder", "cx": 0, "cy": 0, "r": 0.3, "zmin": 0, "zmax": 1, "material": "Cu"}]
    e = _refused(doc(feats, (-1, 1, -1, 1, 0, 1), "FR4"))
    assert e.code == "E-3D-COMBINATION" and e.path == "geometry.components.c.features[1]"
    assert str(e) == f"cylinder 'via' {STAGED}"
    short = doc([{**feats[1], "zmax": 0.5}], (-1, 1, -1, 1, 0, 1), "FR4")
    e = _refused(short)
    assert e.path == "geometry.components.c.features[0]" and str(e) == f"cylinder 'via' {STAGED}"


def test_the_contract_stems_are_refused_in_the_builders_words():
    e = _refused(c4(cx=0.8))
    assert e.code == "E-3D-COMBINATION"
    assert str(e) == ("cylinder 'via' crosses the side domain.x1 between z = 0 and 1 m; a cylinder must lie inside "
                      "or outside every side it spans")
    e = _refused(c5(r=1))
    assert str(e) == "sphere 'ball' touches or crosses domain.x0; a sphere lies strictly inside one region"


def test_a_component_with_no_cylinder_or_sphere_is_refused_by_name():
    d = doc([{"name": "core", "type": "box", "xmin": -0.5, "xmax": 0.5, "ymin": -0.5, "ymax": 0.5, "zmin": 0,
              "zmax": 0.5, "material": "Cu"}], (-1, 1, -1, 1, 0, 1), "FR4")
    e = _refused(d)
    assert e.code == "E-CONTRACT" and e.path == "geometry.components.c"
    assert str(e) == ("component 'c' holds no cylinder or sphere: display_shapes3d draws cylinders and spheres in "
                      "meshloom's builder shapes; simcase.display_complex3d draws boxes and slab layers")
    display_complex3d(parse_geometry(d))                            # unchanged: it takes the boxes


def test_display_complex3d_still_refuses_the_builder_shapes():
    with pytest.raises(GeometryError) as err:
        display_complex3d(parse_geometry(c4()))
    assert err.value.code == "E-3D-COMBINATION" and "holds sampled surfaces" in str(err.value)


def test_a_component_is_picked_as_display_complex3d_picks():
    two = c4()
    two["geometry"]["components"]["d"] = c5()["geometry"]["components"]["c"]
    e = _refused(two)
    assert e.path == "geometry.components" and str(e).startswith("name a 3d component: the model has 2")
    assert display_shapes3d(parse_geometry(two), "d").component == "d"
    e = _refused(two, "nowhere")
    assert e.path == "geometry.components.nowhere"


# ----------------------------------------------------------------------------- sections

def _by_face(sec, d):
    out = {}
    for seg, f in zip(sec["segments"], sec["faces"].tolist()):
        out.setdefault(tuple(d.faces[f].names), []).append(seg)
    return out


def test_a_cylinder_cut_by_z_gives_its_n_gon_and_by_x_two_exact_lines():
    d = shapes(c4)
    side = next(f for f in d.faces if f.shape == "cylinder")
    r = 3 * 10 ** 11
    sec = d.section("z", 5 * 10 ** 11)
    got = _by_face(sec, d)
    ring = np.array(got[("via.side",)])
    assert len(ring) == side.segments
    assert np.all(ring[:, :, 2] == 5 * 10 ** 11)
    assert np.max(np.abs(np.hypot(ring[:, :, 0], ring[:, :, 1]) - r)) <= 1e-15 * r
    assert sorted(sec["regions"]) == ["background", "via"]
    for name in ("domain.x0", "domain.x1", "domain.y0", "domain.y1"):
        assert len(got[(name,)]) == 1
    at = 10 ** 11
    half = math.sqrt(r * r - at * at)
    sec = d.section("x", at)
    got = _by_face(sec, d)
    lines = np.array(got[("via.side",)])
    assert len(lines) == 2 and np.all(lines[:, :, 0] == at)
    assert sorted(float(v) for v in lines[:, 0, 1]) == [-half, half]
    assert sorted(lines[0, :, 2].tolist()) == [0.0, 1e12]
    disc = np.array(got[("domain.z0", "via.bottom")])
    assert len(disc) == 1 and sorted(disc[0, :, 1].tolist()) == [-half, half]
    annulus = sorted(sorted(seg[:, 1].tolist()) for seg in got[("domain.z0",)])
    assert annulus == [[-1e12, -half], [half, 1e12]]
    assert ("domain.x0",) not in got and ("domain.x1",) not in got
    sec = d.section("x", 5 * 10 ** 11)                               # beside the via
    got = _by_face(sec, d)
    assert ("via.side",) not in got and sec["regions"] == ["background"]
    assert [sorted(x[:, 1].tolist()) for x in got[("domain.z1",)]] == [[-1e12, 1e12]]


def test_a_sphere_cut_at_d_below_r_gives_a_circle_of_its_radius():
    d = shapes(c5)
    r, at = 5 * 10 ** 11, 3 * 10 ** 11
    rho = math.sqrt(r * r - at * at)
    sec = d.section("z", at)
    circle = np.array(_by_face(sec, d)[("ball.surface",)])
    assert len(circle) == min(256, max(48, math.ceil(2 * math.pi * rho / d.length)))
    assert np.all(circle[:, :, 2] == at)
    assert np.max(np.abs(np.hypot(circle[:, :, 0], circle[:, :, 1]) - rho)) <= 1e-15 * r
    assert sorted(sec["regions"]) == ["background", "ball"]
    sec = d.section("z", 6 * 10 ** 11)
    assert ("ball.surface",) not in _by_face(sec, d) and sec["regions"] == ["background"]


def test_a_section_outside_the_domain_is_refused():
    d = shapes(c4)
    with pytest.raises(GeometryError) as err:
        d.section("z", 2 * 10 ** 12)
    assert "outside the domain" in str(err.value)
