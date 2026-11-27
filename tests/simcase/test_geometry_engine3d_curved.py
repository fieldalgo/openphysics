# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Stage 5, slice 3: cylinders and spheres in meshloom's public builder shapes.

A 3d component whose features exactly match one of ``meshloom.builder``'s configurations is meshed
by that builder at the document's h, its tags renamed to the document's provenance names:
``via_in_slab`` (C4: one z-cylinder through the whole slab), ``sphere_in_box`` (C5),
``nested_spheres`` (C11) and ``sphere`` (C1). Every other cylinder or sphere configuration is
refused by name; each sampled surface is reported as ``I-SURFACE-SAMPLED``.

Pre-registered checks (adopted, decision 2026-11-27-openphysics-geometry-stage5-adopted; fixed):
- G7 (PR): C4, C5 and C11 written as documents, against ``generate3d(**builder.<fn>(...))`` at the
  same h: nodes, connectivity and regions bitwise identical, and the faces of every builder tag
  under its renamed name. Sizes C4 {0.2, 0.1}, C5 {0.24, 0.12}, C11 {0.2, 0.1}.
- G8 (main): C4's cylinder volume against pi r^2 L: e_V, least-squares slope of log e_V against
  log s with s = 2 pi r / m the ring chord, at h {0.2, 0.1, 0.05}: slope >= 1.8 and
  e_V(finest) <= 5e-3.
- G9 (main): C1's sphere volume against 4 pi / 3 (V6): slope against h >= 1.8 and
  e(0.05) <= 1.5e-3, at h {0.2, 0.1, 0.05}.
- G10 (PR): C4, C5 and C11: V5's delta on every node of a curved surface, against the exact
  parameters of the document in pm (not the builder inputs): <= 1e-15.
- G2: every mesh face under a provenance name lies on its part's surface (planar parts exactly;
  curved parts within 1e-12 of the domain diagonal); every exterior face is in exactly one tag.
- G3: V1 and V2 on every mesh.
- G6: one document per contract stem that can occur in builder shapes (a cylinder crossing or
  touching a side, a sphere touching or crossing a face, two spheres touching or crossing) and the
  staging refusal of a configuration no builder takes; code, path and names.
- S1: slice 1's 25 pull-request seeds and E1 give the SHA-256 recorded on main a5c61f8.
"""

import hashlib
import json
import math
import os
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import test_geometry_engine3d as s1  # noqa: E402
from meshloom import builder  # noqa: E402
from simcase.geometry_document import GeometryError  # noqa: E402
from simcase.geometry_engine3d import _build, build_mesh3d  # noqa: E402

FULL = os.environ.get("OPENPHYSICS_GEOMETRY3D_FULL") == "1"
DIGESTS = Path(__file__).with_name("geometry3d_slice1_digests.json")


def cdoc(features, domain, background, h):
    return s1.doc(features, unit="m", domain=domain, background=background, size=f"{h} m")


# ----------------------------------------------------------------------------- the four shapes

def c4(h, *, cx=0, cy=0, r=0.3, ref=True):
    d = cdoc([{"name": "via", "type": "cylinder", "cx": cx, "cy": cy, "r": r, "zmin": 0, "zmax": 1,
               "material": "Cu"}], (-1, 1, -1, 1, 0, 1), "FR4", h)
    if not ref:                         # a document to be refused: no reference
        return d, None, None, None
    ref = builder.via_in_slab(h, slab=((-1.0, -1.0, 0.0), (1.0, 1.0, 1.0)), radius=float(r), axis=(float(cx), float(cy)),
                              names=("background", "via"))
    tags = {"bottom": ("domain.z0",), "top": ("domain.z1",), "x0": ("domain.x0",), "x1": ("domain.x1",),
            "y0": ("domain.y0",), "y1": ("domain.y1",), "via_bottom": ("via.bottom", "domain.z0"),
            "via_top": ("via.top", "domain.z1")}
    return d, ref, tags, {"via.side": ("background", "via")}


def c5(h, *, r=0.5, c=(0, 0, 0), ref=True):
    d = cdoc([{"name": "ball", "type": "sphere", "cx": c[0], "cy": c[1], "cz": c[2], "r": r, "material": "Cu"}],
             (-1, 1, -1, 1, -1, 1), "air", h)
    if not ref:
        return d, None, None, None
    ref = builder.sphere_in_box(h, box=((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)), center=tuple(map(float, c)),
                                radius=float(r), names=("background", "ball"))
    tags = {a: (f"domain.{a}",) for a in ("x0", "x1", "y0", "y1", "z0", "z1")}
    return d, ref, tags, {"ball.surface": ("background", "ball")}


def c11(h):
    feats = [{"name": "sc", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 1, "material": "eps4"},
             {"name": "sb", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.75, "material": "eps1"},
             {"name": "sa", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.5, "material": None}]
    d = cdoc(feats, (-1.2, 1.2, -1.2, 1.2, -1.2, 1.2), None, h)
    ref = builder.nested_spheres(h, center=(0.0, 0.0, 0.0), radii=(0.5, 0.75, 1.0), names=(None, "sb", "sc"))
    return d, ref, {"sphere0": ("sa.surface",), "sphere2": ("sc.surface",)}, {"sb.surface": ("sb", "sc")}


def c1(h):
    d = cdoc([{"name": "ball", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 1, "material": "Cu"}],
             (-1.2, 1.2, -1.2, 1.2, -1.2, 1.2), None, h)
    ref = builder.sphere(h, center=(0.0, 0.0, 0.0), radius=1.0, name="ball")
    return d, ref, {"sphere": ("ball.surface",)}, {}


CASES = {"C4": (c4, (0.2, 0.1)), "C5": (c5, (0.24, 0.12)), "C11": (c11, (0.2, 0.1))}
PARAMS = [(name, h) for name, (_, sizes) in CASES.items() for h in sizes]


def _faces(a):
    return {tuple(sorted(f)) for f in np.asarray(a).reshape(-1, 3).tolist()}


@pytest.mark.parametrize("name, h", PARAMS)
def test_g7_builder_shapes_are_the_builders_meshes(name, h):
    d, ref_input, tags, interfaces = CASES[name][0](h)
    result = build_mesh3d(d)
    ref = meshloom.generate3d(h=h, **ref_input)
    m = result.mesh
    for ours, theirs in ((m.nodes, ref["nodes"]), (m.tets, ref["tetrahedra"]), (m.regions, ref["regions"])):
        a, b = np.ascontiguousarray(ours), np.ascontiguousarray(theirs, dtype=np.asarray(ours).dtype)
        assert a.shape == b.shape and a.tobytes() == b.tobytes()
    assert list(m.region_names) == list(ref["region_names"])
    # every builder tag's faces carry each part whose surface holds them (a via's cap also lies on the
    # domain's face), so a part's faces are the union of the tags that map to it
    expected: dict = {}
    for tag, parts in tags.items():
        for part in parts:
            expected.setdefault(part, set()).update(_faces(ref["boundary_faces"][tag]))
    for part, faces in expected.items():
        assert _faces(result.provenance_faces[part]) == faces, part
    names = list(ref["region_names"])
    for part, (ra, rb) in interfaces.items():
        key = (names.index(ra), names.index(rb))
        raw = ref["interfaces"].get(key, ref["interfaces"].get(key[::-1]))
        assert _faces(result.provenance_faces[part]) == _faces(raw), part


# ----------------------------------------------------------------------------- G10: V5

def _delta_sphere(p, c, R):
    d2 = sum((p[i] - c[i]) ** 2 for i in range(3))
    return abs(d2 - R * R) / (2 * R * (math.sqrt(float(sum(x * x for x in c))) + R))


def _delta_cylinder(p, c, R):
    d2 = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2
    return abs(d2 - R * R) / (2 * R * (math.sqrt(float(c[0] ** 2 + c[1] ** 2)) + R))


def curved_parts(d):
    """name -> (kind, exact centre (m), exact radius (m)) from the document's pm values."""
    from simcase import parse_geometry
    comp = parse_geometry(d).components["c"]
    out = {}
    for f in comp.features:
        q = f.data
        if f.type == "cylinder":
            out[f"{f.id}.side"] = ("cylinder", (Fraction(q["cx"], 10 ** 12), Fraction(q["cy"], 10 ** 12)),
                                   Fraction(q["r"], 10 ** 12))
        elif f.type == "sphere":
            out[f"{f.id}.surface"] = ("sphere", tuple(Fraction(q[k], 10 ** 12) for k in ("cx", "cy", "cz")),
                                      Fraction(q["r"], 10 ** 12))
    return out


def worst_v5(result, d):
    worst = 0.0
    for name, (kind, c, R) in curved_parts(d).items():
        for v in np.unique(result.provenance_faces[name]).tolist():
            p = [Fraction(float(x)) for x in result.mesh.nodes[v]]
            worst = max(worst, float((_delta_sphere if kind == "sphere" else _delta_cylinder)(p, c, R)))
    return worst


@pytest.mark.parametrize("name, h", PARAMS)
def test_g10_curved_nodes_lie_on_the_exact_surfaces(name, h):
    d = CASES[name][0](h)[0]
    assert worst_v5(build_mesh3d(d), d) <= 1e-15


# ----------------------------------------------------------------------------- G2 and G3

def _on_plane(name, pts, dom):
    axis = "xyz".index(name[-2])
    value = dom[f"{name[-2]}{'min' if name[-1] == '0' else 'max'}"]
    return all(Fraction(float(p[axis])) == value for p in pts)


@pytest.mark.parametrize("name, h", PARAMS)
def test_g2_g3_provenance_tags_v1_and_v2(name, h):
    d = CASES[name][0](h)[0]
    result = build_mesh3d(d)
    dom = {k: Fraction(str(v)) for k, v in d["geometry"]["components"]["c"]["domain"].items()}
    diag = math.sqrt(sum(float(dom[f"{a}max"] - dom[f"{a}min"]) ** 2 for a in "xyz"))
    curved = curved_parts(d)
    nodes = result.mesh.nodes
    for part, faces in result.provenance_faces.items():
        pts = nodes[np.unique(faces)]
        if part in curved:
            kind, c, R = curved[part]
            for p in pts:
                dist = math.dist(p[:2], [float(x) for x in c[:2]]) if kind == "cylinder" else \
                    math.dist(p, [float(x) for x in c])
                assert abs(dist - float(R)) <= 1e-12 * diag, part
        elif part.startswith("domain.") or part.endswith((".bottom", ".top")):
            plane = part if part.startswith("domain.") else ("domain.z0" if part.endswith(".bottom") else "domain.z1")
            assert _on_plane(plane, pts, dom), part
        else:
            raise AssertionError(f"unexpected part {part}")
    assert s1.v1_bad(result.mesh) == 0
    assert s1.check_v2(result)


def test_c1_is_the_builders_ball_and_v5_holds():
    for h in (0.2, 0.1):
        d, ref_input, tags, _ = c1(h)
        result = build_mesh3d(d)
        ref = meshloom.generate3d(h=h, **ref_input)
        assert result.mesh.nodes.tobytes() == np.ascontiguousarray(ref["nodes"]).tobytes()
        assert _faces(result.provenance_faces["ball.surface"]) == _faces(ref["boundary_faces"]["sphere"])
        assert set(result.mesh.tagged_faces) == {"void"}
        assert worst_v5(result, d) <= 1e-15


# ----------------------------------------------------------------------------- I-SURFACE-SAMPLED

def test_each_sampled_surface_is_reported():
    d = c4(0.2)[0]
    result = build_mesh3d(d)
    infos = [x for x in result.diagnostics if x.code == "I-SURFACE-SAMPLED"]
    assert len(infos) == 1 and infos[0].path == "geometry.components.c.features[0]"
    text = infos[0].message
    for piece in ("via.side", "cylinder", "builder.via_in_slab", f"meshloom {meshloom.__version__}",
                  meshloom.kernel_version(), "r = 300000000000 pm", "h = 0.2 m", "m = ", "ring z levels",
                  "sagitta bound", "measured V5 deviation"):
        assert piece in text, piece
    d = c11(0.2)[0]
    infos = [x for x in build_mesh3d(d).diagnostics if x.code == "I-SURFACE-SAMPLED"]
    assert [x.path for x in infos] == [f"geometry.components.c.features[{i}]" for i in range(3)]
    assert all("builder.nested_spheres" in x.message and "frequency n = " in x.message for x in infos)


# ----------------------------------------------------------------------------- G6: refusals

def _refused(d):
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-3D-COMBINATION"
    return err.value


def test_g6_a_cylinder_crossing_a_side():
    e = _refused(c4(0.2, cx=0.8, ref=False)[0])
    assert e.path == "geometry.components.c.features[0]"
    assert str(e) == ("cylinder 'via' crosses the side domain.x1 between z = 0 and 1 m; a cylinder must lie inside "
                      "or outside every side it spans")


def test_g6_a_cylinder_touching_a_side():
    e = _refused(c4(0.2, cx=0.7, ref=False)[0])
    assert e.path == "geometry.components.c.features[0]"
    assert str(e) == "cylinder 'via' touches domain.x1 at one line; move it inside or away"


def test_g6_a_sphere_touching_a_face():
    e = _refused(c5(0.24, r=1, ref=False)[0])
    assert e.path == "geometry.components.c.features[0]"
    assert str(e) == "sphere 'ball' touches or crosses domain.x0; a sphere lies strictly inside one region"


def test_g6_two_spheres_touching():
    feats = [{"name": "a", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.5, "material": "Cu"},
             {"name": "b", "type": "sphere", "cx": 0, "cy": 0, "cz": 0, "r": 0.5, "material": "Al"}]
    e = _refused(cdoc(feats, (-1, 1, -1, 1, -1, 1), None, 0.2))
    assert e.path == "geometry.components.c.features[1]"
    assert str(e) == "spheres 'a' and 'b' touch or cross; they must be disjoint or strictly nested"


STAGED = ("is not taken yet in a 3d component; boxes and slab layers are, and cylinders and spheres in "
          "meshloom's builder shapes only (one cylinder through the whole slab, one sphere, concentric spheres)")


@pytest.mark.parametrize("case", ["cylinder with a box", "short cylinder", "two cylinders", "sphere with a box",
                                  "off-centre nested spheres"])
def test_g6_other_configurations_are_staged(case):
    box = {"name": "core", "type": "box", "xmin": -0.5, "xmax": 0.5, "ymin": -0.5, "ymax": 0.5, "zmin": 0, "zmax": 0.5,
           "material": "Cu"}
    via = {"name": "via", "type": "cylinder", "cx": 0, "cy": 0, "r": 0.3, "zmin": 0, "zmax": 1, "material": "Cu"}
    ball = {"name": "ball", "type": "sphere", "cx": 0, "cy": 0, "cz": 0.5, "r": 0.2, "material": "Cu"}
    dom = (-1, 1, -1, 1, 0, 1)
    feats, index, name = {
        "cylinder with a box": ([box, via], 1, "cylinder 'via'"),
        "short cylinder": ([{**via, "zmax": 0.5}], 0, "cylinder 'via'"),
        "two cylinders": ([via, {**via, "name": "v2", "cx": 0.6, "r": 0.1}], 1, "cylinder 'v2'"),
        "sphere with a box": ([box, ball], 1, "sphere 'ball'"),
        "off-centre nested spheres": ([{**ball, "r": 0.4}, {**ball, "name": "b2", "cx": 0.1, "r": 0.1}], 1,
                                      "sphere 'b2'"),
    }[case]
    e = _refused(cdoc(feats, dom, "FR4" if "sphere" not in case else None, 0.2))
    assert e.path == f"geometry.components.c.features[{index}]"
    assert str(e) == f"{name} {STAGED}"


def test_g6_sizes_other_than_one_element_size_are_refused_with_a_sampled_surface():
    d = c4(0.2)[0]
    d["mesh"]["controls"] = [{"select": "via", "element_size": "0.1 m"}]
    e = _refused(d)
    assert e.path == "mesh.controls[0]"
    assert "one mesh.element_size" in str(e)


# ----------------------------------------------------------------------------- G8 and G9 (main)

def _slope(x, y):
    return float(np.polyfit(np.log(x), np.log(y), 1)[0])


@pytest.mark.skipif(not FULL, reason="G8 runs on main pushes (geometry3d-full)")
def test_g8_cylinder_volume_converges():
    r = 0.3
    exact = math.pi * r * r * 1.0
    s, e = [], []
    for h in (0.2, 0.1, 0.05):
        d = c4(h)[0]
        result = build_mesh3d(d)
        m = result.mesh
        p = m.nodes[m.tets]
        vol = np.abs(np.einsum("ti,ti->t", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))) / 6
        v = float(vol[m.regions == list(m.region_names).index("via")].sum())
        ring = np.unique(result.provenance_faces["via.side"])
        rz = m.nodes[ring][:, 2]
        n_ring = int(np.sum(rz == rz.min()))
        s.append(2 * math.pi * r / n_ring)
        e.append(abs(v - exact) / exact)
    print("G8", s, e)
    assert _slope(s, e) >= 1.8
    assert e[-1] <= 5e-3


@pytest.mark.skipif(not FULL, reason="G9 runs on main pushes (geometry3d-full)")
def test_g9_sphere_volume_converges():
    hs, e = (0.2, 0.1, 0.05), []
    for h in hs:
        m = build_mesh3d(c1(h)[0]).mesh
        p = m.nodes[m.tets]
        vol = float(np.abs(np.einsum("ti,ti->t", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0],
                                                                             p[:, 3] - p[:, 0]))).sum() / 6)
        e.append(abs(vol - 4 * math.pi / 3) / (4 * math.pi / 3))
    print("G9", e)
    assert _slope(hs, e) >= 1.8
    assert e[-1] <= 1.5e-3


# ----------------------------------------------------------------------------- S1

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


@pytest.mark.parametrize("seed", list(range(0, 200, 8)))
def test_s1_slice1_complexes_and_meshes_are_unchanged(seed):
    recorded = json.loads(DIGESTS.read_text(encoding="utf-8"))
    result = build_mesh3d(s1.g1_doc(seed)[0])
    assert {"complex": complex_digest(result.complex), "mesh": s1.digest(result)} == recorded[str(seed)]


def test_s1_e1_is_unchanged():
    recorded = json.loads(DIGESTS.read_text(encoding="utf-8"))
    assert s1.digest(_build(s1.e1(), through_meshloom=True)) == recorded["e1"]


def test_the_exact_complex_of_a_sampled_surface_is_refused_by_name():
    from simcase import display_complex3d, parse_geometry
    with pytest.raises(GeometryError) as err:
        display_complex3d(parse_geometry(c4(0.2, ref=False)[0]))
    assert err.value.code == "E-3D-COMBINATION" and err.value.path == "geometry.components.c"
    assert str(err.value) == ("component 'c' holds sampled surfaces (meshloom builder.via_in_slab): the exact 3D complex "
                              "of a sampled surface is not built yet; simcase.build_mesh3d meshes the component")


def test_prepare_gives_the_estimate_and_the_limit_refusal_before_meshing():
    from simcase.geometry_engine3d import _prepare
    cx, comp, ho, info = _prepare(c4(0.2, ref=False)[0])
    assert cx is None and comp.name == "c" and info.code == "I-MESH-ESTIMATE"
    assert ho.shape == "via_in_slab" and ho.estimate > 0
    d = c4(0.1, ref=False)[0]
    d["mesh"]["element_count_limit"] = 100
    with pytest.raises(GeometryError) as err:
        _prepare(d)
    assert err.value.code == "E-MESH-ESTIMATE" and err.value.path == "mesh.element_count_limit"


# ----------------------------------------------------------------------------- below the mesher tolerance
#
# Registered before measuring (coordinator review of #410): on the builder route, the smallest exact
# clearance (pm) below MESHER_RELATIVE_TOLERANCE = 3e-8 of the component's diagonal is refused before the
# hand-off, with E-CONTRACT, the parser's sentence and the later feature: a C4 via surface to each domain
# side, a C5 sphere to each domain face, and C11's consecutive radii. 1.5e-8 is refused; 6e-8 passes and
# the hand-off is formed (meshing it is not asserted, as #408's R2). C1's and C11's domains only bound
# void space, so a sphere's distance to them makes no thin piece and is not checked.

def _thin_sentence(name, size, diag_pm):
    return (f"geometry.components.c: feature {name!r} is {size} pm across, {size / diag_pm:.2e} of the component's "
            "diagonal, below the mesher tolerance 3e-08; it would vanish in the mesh. Meshing such multi-scale geometry "
            "is not supported yet.")


def _m(pm):
    """pm as an exact decimal metre value for a document."""
    return float(Fraction(pm, 10 ** 12))


def _thin(case, ratio):
    if case == "C4":
        diag = 3 * 10 ** 12                           # [-1,1]^2 x [0,1]
        gap = round(ratio * diag)
        cx = _m(10 ** 12 - 3 * 10 ** 11 - gap)        # via surface `gap` from domain.x1
        return c4(0.2, cx=cx, ref=False)[0], "via", gap, diag
    if case == "C5":
        diag = math.sqrt(12) * 10 ** 12
        gap = round(ratio * diag)
        return c5(0.24, r=_m(10 ** 12 - gap), ref=False)[0], "ball", gap, diag
    diag = math.sqrt(3 * 2.4 ** 2) * 10 ** 12
    gap = round(ratio * diag)
    d = c11(0.2)[0]
    d["geometry"]["components"]["c"]["features"][2]["r"] = _m(75 * 10 ** 10 - gap)   # sa just inside sb
    return d, "sa", gap, diag


@pytest.mark.parametrize("case", ["C4", "C5", "C11"])
def test_a_clearance_below_the_tolerance_is_refused_naming_the_feature(case):
    d, name, gap, diag = _thin(case, 1.5e-8)
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-CONTRACT" and err.value.path == "geometry.components.c"
    assert str(err.value) == _thin_sentence(name, gap, diag)


@pytest.mark.parametrize("case", ["C4", "C5", "C11"])
def test_a_clearance_above_the_tolerance_passes_and_the_hand_off_is_formed(case):
    from simcase.geometry_engine3d import _prepare
    d, _, _, _ = _thin(case, 6e-8)
    cx, comp, ho, info = _prepare(d)
    assert cx is None and len(ho.kwargs["points"]) and ho.kwargs["facets"] and info.code == "I-MESH-ESTIMATE"
