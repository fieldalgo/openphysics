# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Stage 5, slice 1: boxes and slab layers through meshloom (``simcase.geometry_engine3d``).

Pre-registered checks (fixed before measuring; never loosened):

- G1: seeded later-wins sets of at most 8 boxes on a small integer grid, with touches, nesting
  and shared planes, at h = 0.25 grid unit, against a brute-force oracle (a point's region is
  the last box containing it): (a) no tetrahedron whose exact centroid the oracle puts in
  another region; (b) region volumes within 1e-12 of the oracle's exact volumes. Pull requests
  run a fixed seeded subset of the 200 sets; ``OPENPHYSICS_GEOMETRY3D_FULL=1`` runs all 200 (the CI job
  ``geometry3d-full`` on main pushes and manual dispatch). A set whose regions are all void (seed 69)
  has nothing to mesh: its refusal is asserted instead.
- G2: on the G1 sets and E1, every face under a provenance name lies on that part's exact
  surface; every complex surface on a part's surface lists the part; every exterior face is in
  exactly one tag.
- G3: on every mesh here, V1 (no tetrahedron with exact orient3d <= 0 on the doubles galerkin
  receives) and V2 (docs/packages/meshine/validation3d.md).
- G4: E1 written in m, mm, um and nm gives one SHA-256 of the canonical mesh arrays (coarsest h).
- G5: E1's SHA-256 is the same in 3 fresh processes.
- G6: one document per slice-1 refusal: code, path and names as the contract's stems say.
- P1: E1 through meshloom and through meshine.extrude against galerkin_refsol's layered slab
  (exact for P1): max nodal |T_h - T| <= 1e-10, top heat rate relative error <= 1e-9, at
  h = 0.8 and 0.4.

E1: three slab layers of thickness 1, 0.5 and 1 mm (z levels 0, 1, 1.5, 2.5) with k = 1, 0.01
and 1 W/(m K) over a 10 x 10 mm domain; T = 0 on z0, T = 1 on z1, sides insulated.
"""

import copy
import hashlib
import json
import os
import random
import subprocess
import sys
from fractions import Fraction
from itertools import combinations

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from simcase.geometry_document import GeometryError  # noqa: E402
from simcase.geometry_engine3d import _build, _evaluate, build_mesh3d, display_complex3d, evaluate3d  # noqa: E402

PM = 10 ** 12
FULL = os.environ.get("OPENPHYSICS_GEOMETRY3D_FULL") == "1"
G1_SEEDS = list(range(200)) if FULL else list(range(0, 200, 8))      # 25 fixed seeds on pull requests


def doc(features, *, unit="mm", domain=(0, 10, 0, 10, 0, 2.5), background="air", size="0.8 mm", mesh=None,
        component=None):
    keys = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    comp = {"dimension": "3d", "length_unit": unit, "domain": dict(zip(keys, domain)),
            "background": {"material": background}, "features": features}
    comp.update(component or {})
    out = {"openphysics": "0.3", "geometry": {"version": 1, "components": {"c": comp}},
           "mesh": {"element_size": size}}
    out["mesh"].update(mesh or {})
    return out


# ----------------------------------------------------------------------------- E1

E1_K = {"lower": 1.0, "core": 0.01, "upper": 1.0}
E1_LEVELS_MM = [0, 1, 1.5, 2.5]
_SCALE = {"m": Fraction(1, 1000), "mm": Fraction(1), "um": Fraction(1000), "nm": Fraction(10 ** 6)}


def _num(x_mm, unit):
    v = Fraction(str(x_mm)) * _SCALE[unit]
    return int(v) if v.denominator == 1 else float(v)


def e1(unit="mm", h_mm=0.8):
    layers = [{"name": n, "thickness": _num(t, unit), "material": n}
              for n, t in zip(E1_K, (1, 0.5, 1))]
    size = f"{h_mm} mm"
    return doc([{"name": "stack", "type": "layers", "z0": 0, "layers": layers}], unit=unit,
               domain=tuple(_num(v, unit) for v in (0, 10, 0, 10, 0, 2.5)), size=size)


def e1_mesh(unit="mm", h_mm=0.8):
    return _build(e1(unit, h_mm), through_meshloom=True)


def digest(result) -> str:
    """SHA-256 of the canonical mesh arrays: nodes, tetrahedra, regions, region names, tagged faces,
    interfaces and provenance faces, in sorted key order."""
    m = result.mesh
    h = hashlib.sha256()
    for a in (m.nodes, m.tets, m.regions):
        h.update(np.ascontiguousarray(a).tobytes())
    h.update(json.dumps(m.region_names).encode())
    for table in (m.tagged_faces, m.interfaces, result.provenance_faces):
        for k in sorted(table):
            h.update(repr(k).encode())
            h.update(np.ascontiguousarray(table[k], dtype=np.int64).tobytes())
    return h.hexdigest()


# ----------------------------------------------------------------------------- G3: V1 and V2

def _exact_ints(nodes):
    """Node coordinates as integers on one common dyadic grid (exact)."""
    fr = [[Fraction(float(c)) for c in row] for row in nodes.tolist()]
    den = 1
    for row in fr:
        for c in row:
            den = max(den, c.denominator)
    return [[int(c * den) for c in row] for row in fr]


def v1_bad(mesh) -> int:
    """V1: tetrahedra with exact orient3d(p0, p1, p2, p3) <= 0 on the output doubles."""
    P = _exact_ints(mesh.nodes)
    bad = 0
    for a, b, c, d in mesh.tets.tolist():
        pa, pb, pc, pd = P[a], P[b], P[c], P[d]
        u = [pb[i] - pa[i] for i in range(3)]
        v = [pc[i] - pa[i] for i in range(3)]
        w = [pd[i] - pa[i] for i in range(3)]
        det = (u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0])
               + u[2] * (v[0] * w[1] - v[1] * w[0]))
        bad += det <= 0
    return bad


def check_v2(result):
    """V2 of validation3d.md on the mesh simcase returns."""
    from galerkin import from_mesher
    m, raw = result.mesh, result.raw
    tets = m.tets
    faces = np.sort(tets[:, [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]].reshape(-1, 3), axis=1)
    uniq, counts = np.unique(faces, axis=0, return_counts=True)
    assert counts.max() <= 2 and counts.min() >= 1                       # each face in 1 or 2 tetrahedra
    once = {tuple(f) for f in uniq[counts == 1]}
    tagged = [tuple(sorted(f)) for t in m.tagged_faces for f in m.tagged_faces[t].tolist()]
    assert len(tagged) == len(set(tagged))                               # each exterior face in exactly one tag
    assert set(tagged) == once                                           # the union is the topological boundary
    for t, f in m.tagged_faces.items():
        np.testing.assert_array_equal(m.boundary[t], np.unique(f))       # boundary nodes = unique face nodes
    assert set(np.unique(tets).tolist()) == set(range(m.num_nodes))      # no orphan nodes
    assert len({tuple(p) for p in m.nodes.tolist()}) == m.num_nodes      # no duplicate nodes
    assert m.regions.min() >= 0 and m.regions.max() < len(m.region_names)
    assert set(np.unique(m.regions).tolist()) == set(range(len(m.region_names)))
    # each interface face between one tetrahedron of each side
    face_tets: dict = {}
    for t, row in enumerate(faces.reshape(-1, 4, 3)):
        for f in row:
            face_tets.setdefault(tuple(f), []).append(t)
    for (a, b), fs in m.interfaces.items():
        ia, ib = m.region_names.index(a), m.region_names.index(b)
        for f in fs.tolist():
            ts = face_tets[tuple(sorted(f))]
            assert len(ts) == 2 and sorted(m.regions[ts].tolist()) == sorted([ia, ib])
    assert type(from_mesher(raw)).__name__ == "Mesh3D"
    return True


def euler(tets_sub) -> int:
    """V - E + F - T of a set of tetrahedra."""
    t = np.asarray(tets_sub)
    edges = {tuple(e) for e in np.sort(t[:, [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]].reshape(-1, 2),
                                       axis=1).tolist()}
    tris = {tuple(f) for f in np.sort(t[:, [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]].reshape(-1, 3),
                                      axis=1).tolist()}
    return len(np.unique(t)) - len(edges) + len(tris) - len(t)


# ----------------------------------------------------------------------------- G1: the oracle

GRID = (4, 3, 2)                            # domain [0, 4] x [0, 3] x [0, 2] grid units (mm)


def g1_case(seed):
    """At most 8 boxes on the integer grid: touches, nesting, shared planes, some outside the domain,
    some void; the background alternates between a material and void."""
    rng = random.Random(seed)
    n = rng.randint(1, 8)
    boxes = []
    for i in range(n):
        b = {}
        for a, axis in enumerate("xyz"):
            lo = rng.randint(-1 if rng.random() < 0.1 else 0, GRID[a] - 1)
            hi = rng.randint(lo + 1, GRID[a] + (1 if rng.random() < 0.1 else 0))
            b[f"{axis}min"], b[f"{axis}max"] = lo, hi
        if i and rng.random() < 0.3:                     # share a plane or nest inside an earlier box
            other = rng.choice(boxes)
            axis = rng.choice("xyz")
            b[f"{axis}min"] = other[f"{axis}max"] if other[f"{axis}max"] < b[f"{axis}max"] else b[f"{axis}min"]
        material = None if rng.random() < 0.15 else f"m{i}"
        boxes.append({"name": f"b{i}", "type": "box", **b, "material": material})
    background = None if seed % 2 else "bg"
    return boxes, background


def g1_doc(seed):
    boxes, background = g1_case(seed)
    return doc(boxes, domain=(0, GRID[0], 0, GRID[1], 0, GRID[2]), background=background, size="0.25 mm"), boxes, \
        background


def _r(k_mm):
    """A grid value in mm as the exact rational of its metre double (rule H1)."""
    return Fraction(float(Fraction(k_mm, 1000)))


def oracle(boxes, background, p):
    """The region and material at point p (exact, metres): the last box containing it."""
    for b in reversed(boxes):
        if all(_r(b[f"{a}min"]) <= p[i] <= _r(b[f"{a}max"]) for i, a in enumerate("xyz")):
            return b["name"], b["material"]
    return "background", background


def oracle_volumes(boxes, background):
    """Exact region volumes (metres^3) of the non-void regions, over the grid of all planes."""
    planes = []
    for i, a in enumerate("xyz"):
        vals = {0, GRID[i]} | {min(max(b[f"{a}{e}"], 0), GRID[i]) for b in boxes for e in ("min", "max")}
        planes.append(sorted(vals))
    out: dict = {}
    for xa, xb in zip(planes[0], planes[0][1:]):
        for ya, yb in zip(planes[1], planes[1][1:]):
            for za, zb in zip(planes[2], planes[2][1:]):
                lo, hi = (_r(xa), _r(ya), _r(za)), (_r(xb), _r(yb), _r(zb))
                region, material = oracle(boxes, background, [(u + v) / 2 for u, v in zip(lo, hi)])
                if material is not None:
                    out[region] = out.get(region, 0) + (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])
    return out


def g1_metrics(result, boxes, background):
    m = result.mesh
    wrong = 0
    for t, row in enumerate(m.tets.tolist()):
        cen = [sum(Fraction(float(m.nodes[v][i])) for v in row) / 4 for i in range(3)]
        region, material = oracle(boxes, background, cen)
        if material is None or region != m.region_names[m.regions[t]]:
            wrong += 1
    p = m.nodes[m.tets]
    vol = np.abs(np.einsum("ti,ti->t", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))) / 6
    mesh_volume = {n: float(vol[m.regions == i].sum()) for i, n in enumerate(m.region_names)}
    exact = oracle_volumes(boxes, background)
    assert set(mesh_volume) == set(exact)
    worst = max(abs(mesh_volume[n] - float(v)) / float(v) for n, v in exact.items())
    return wrong, worst


# ----------------------------------------------------------------------------- G2: provenance

def part_surfaces(comp_doc):
    """Every part's exact surface: name -> (axis, plane value, (lo, hi) bounds of the other two axes),
    in metres as the rational values of the H1 doubles."""
    comp = comp_doc["geometry"]["components"]["c"]
    unit = Fraction(1, 1000) if comp["length_unit"] == "mm" else _SCALE["mm"] / _SCALE[comp["length_unit"]] / 1000
    dom = {k: Fraction(str(v)) * unit for k, v in comp["domain"].items()}
    R = lambda v: Fraction(float(v))  # noqa: E731

    def box(prefix, b, names):
        out = {}
        for i, a in enumerate("xyz"):
            others = [o for o in range(3) if o != i]
            span = [(R(b["xyz"[o] + "min"]), R(b["xyz"[o] + "max"])) for o in others]
            out[names(a + "0")] = (i, R(b[a + "min"]), span)
            out[names(a + "1")] = (i, R(b[a + "max"]), span)
        return out

    surfaces = box("domain", dom, lambda p: f"domain.{p}")
    for f in comp["features"]:
        if f["type"] == "box":
            b = {k: Fraction(str(f[k])) * unit for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")}
            surfaces.update(box(f["name"], b, lambda p, n=f["name"]: f"{n}.{p}"))
        else:
            z = Fraction(str(f["z0"])) * unit
            for lay in f["layers"]:
                z1 = z + Fraction(str(lay["thickness"])) * unit
                b = {**{k: dom[k] for k in ("xmin", "xmax", "ymin", "ymax")}, "zmin": z, "zmax": z1}
                pre = f"{f['name']}.{lay['name']}"
                surfaces.update(box(pre, b, lambda p, pre=pre: f"{pre}.{ {'z0': 'bottom', 'z1': 'top'}.get(p, 'domain.' + p)}"))
                z = z1
    return surfaces


def _on(surface, pts) -> bool:
    axis, value, span = surface
    others = [o for o in range(3) if o != axis]
    return all(p[axis] == value and all(lo <= p[o] <= hi for o, (lo, hi) in zip(others, span)) for p in pts)


def g2_violations(result, comp_doc) -> int:
    surfaces = part_surfaces(comp_doc)
    m = result.mesh
    nodes = [[Fraction(float(c)) for c in row] for row in m.nodes.tolist()]
    bad = 0
    # every face under a provenance name lies on that part's exact surface
    for name, faces in result.provenance_faces.items():
        for f in faces.tolist():
            bad += not _on(surfaces[name], [nodes[v] for v in f])
    # every complex surface on a part's surface lists the part (and only those parts)
    cx = result.complex
    meshed = set(result.face_of_facet)
    for face in cx.faces:
        if face.index not in meshed:
            continue
        pts = [[Fraction(float(Fraction(c, PM))) for c in p] for lp in face.loops for p in lp]
        on = {n for n, s in surfaces.items() if _on(s, pts)}
        bad += on != set(face.provenance)
    # the mesh faces under each name cover exactly the complex faces that carry it (by area)
    for name, faces in result.provenance_faces.items():
        p = m.nodes[faces]
        area = float(np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum() / 2)
        exact = sum(float(Fraction(f.area, PM * PM)) for f in cx.faces if name in f.provenance and f.index in meshed)
        bad += abs(area - exact) > 1e-12 * exact
    # every exterior face is in exactly one tag
    tagged = [tuple(sorted(f)) for t in m.tagged_faces for f in m.tagged_faces[t].tolist()]
    bad += len(tagged) - len(set(tagged))
    exterior = {tuple(sorted(f)) for fi, i in enumerate(result.face_of_facet) if cx.faces[i].exterior
                for f in result.facet_faces[fi].tolist()}
    bad += len(exterior ^ set(tagged))
    return bad


# ----------------------------------------------------------------------------- the checks

@pytest.mark.parametrize("seed", G1_SEEDS)
def test_g1_g2_g3_later_wins_boxes_against_the_oracle(seed):
    d, boxes, background = g1_doc(seed)
    if not oracle_volumes(boxes, background):              # every region void (seed 69): nothing to mesh
        with pytest.raises(GeometryError, match="has nothing to mesh: every cell is void"):
            build_mesh3d(d)
        return
    result = build_mesh3d(d)
    wrong, worst = g1_metrics(result, boxes, background)
    assert wrong == 0, f"G1(a) seed {seed}: {wrong} tetrahedra in another region"
    assert worst <= 1e-12, f"G1(b) seed {seed}: relative volume error {worst:.3e}"
    assert g2_violations(result, d) == 0, f"G2 seed {seed}"
    assert v1_bad(result.mesh) == 0, f"G3 V1 seed {seed}"
    assert check_v2(result)


def test_g1_cases_have_touches_nesting_shared_planes_and_voids():
    """The seeded sets exercise what G1 is about (counted over all 200)."""
    touch = nest = share = void = outside = 0
    for seed in range(200):
        boxes, background = g1_case(seed)
        void += background is None or any(b["material"] is None for b in boxes)
        for a, b in combinations(boxes, 2):
            lo = [max(a[f"{x}min"], b[f"{x}min"]) for x in "xyz"]
            hi = [min(a[f"{x}max"], b[f"{x}max"]) for x in "xyz"]
            touch += all(l <= h for l, h in zip(lo, hi)) and any(l == h for l, h in zip(lo, hi))
            nest += all(a[f"{x}min"] <= b[f"{x}min"] and b[f"{x}max"] <= a[f"{x}max"] for x in "xyz")
            share += any(a[f"{x}{e}"] == b[f"{x}{e}"] for x in "xyz" for e in ("min", "max"))
        outside += any(b["xmin"] < 0 or b["xmax"] > GRID[0] or b["zmax"] > GRID[2] for b in boxes)
    assert min(touch, nest, share, void, outside) >= 20


def test_e1_g2_g3_and_the_default_tags():
    result = e1_mesh()
    assert result.mesh.region_names == list(E1_K)
    assert sorted(result.mesh.tagged_faces) == ["x0", "x1", "y0", "y1", "z0", "z1"]
    assert g2_violations(result, e1()) == 0
    assert v1_bad(result.mesh) == 0
    assert check_v2(result)
    for i, name in enumerate(result.mesh.region_names):           # each layer is a ball
        assert euler(result.mesh.tets[result.mesh.regions == i]) == 1


def test_g4_e1_is_the_same_mesh_in_every_unit():
    digests = {unit: digest(e1_mesh(unit)) for unit in ("m", "mm", "um", "nm")}
    assert len(set(digests.values())) == 1, digests


_G5 = """
import sys
sys.path[:0] = {paths!r}
from test_geometry_engine3d import digest, e1_mesh
print(digest(e1_mesh()))
"""


def test_g5_e1_is_the_same_mesh_in_three_fresh_processes():
    here = os.path.dirname(os.path.abspath(__file__))
    paths = [here] + [p for p in sys.path if p]
    code = _G5.format(paths=paths)
    out = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                          cwd=os.path.dirname(os.path.dirname(here))).stdout.strip() for _ in range(3)}
    assert len(out) == 1 and next(iter(out)) == digest(e1_mesh()), out


# ----------------------------------------------------------------------------- G6: refusals

BOX = {"name": "core", "type": "box", "xmin": 1, "xmax": 4, "ymin": 1, "ymax": 4, "zmin": 0, "zmax": 2,
       "material": "Cu"}
REFUSALS = {
    "extrude": ([BOX, {"name": "pad", "type": "extrude", "profile": {"type": "circle", "cx": 7, "cy": 7, "r": 1},
                       "zmin": 0, "zmax": 1, "material": "Cu"}], None, 1,
                ["extrude 'pad' is not taken yet in a 3d component (an extruded circle is a cylinder); boxes, slab "
                 "layers and rect, trapezoid and polygon extrudes are"]),
    "cylinder": ([BOX, {"name": "via", "type": "cylinder", "cx": 5, "cy": 5, "r": 1, "zmin": 0, "zmax": 1,
                        "material": "Cu"}], None, 1,
                 ["cylinder 'via' is not taken yet in a 3d component; boxes, slab layers and rect, trapezoid and "
                  "polygon extrudes are"]),
    "sphere": ([BOX, {"name": "ball", "type": "sphere", "cx": 7, "cy": 7, "cz": 1, "r": 0.5, "material": "Cu"}], None,
               1, ["sphere 'ball' is not taken yet in a 3d component; boxes, slab layers and rect, trapezoid and "
                   "polygon extrudes are"]),
    "footprint layers": ([BOX, {"name": "stack", "type": "layers", "z0": 0, "layers": [
        {"name": "sub", "thickness": 1, "footprint": "plan"}]}], None, 1,
        ["layers 'stack' has footprint layers; with other features a 3d component takes slab layers only, "
         "until a later slice"]),
}


def _with_plan(d):
    d["geometry"]["components"]["plan"] = {"dimension": "2d", "length_unit": "mm", "depth": None,
                                           "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10},
                                           "background": {"material": "FR4"}, "features": []}
    return d


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_g6_feature_refusals(case):
    features, _, index, stems = REFUSALS[case]
    d = _with_plan(doc(features))
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d, "c")
    assert err.value.code == "E-3D-COMBINATION"
    assert err.value.path == f"geometry.components.c.features[{index}]"
    for stem in stems:
        assert stem in str(err.value)


def test_g6_two_values_rounding_to_one_double_are_refused_by_both_names():
    k = 5 * 10 ** 16                          # 50 km in pm: doubles are 7.3 pm apart there
    features = [{"name": "west", "type": "box", "xmin": 0, "xmax": k, "ymin": 0, "ymax": k, "zmin": 0,
                 "zmax": k, "material": "Cu"},
                {"name": "east", "type": "box", "xmin": k + 1, "xmax": 2 * k, "ymin": 0, "ymax": k, "zmin": 0,
                 "zmax": k, "material": "Al"}]
    d = doc(features, unit="pm", domain=(0, 2 * k, 0, k, 0, k), background=None, size="10 km")
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-3D-COMBINATION"
    assert err.value.path == "geometry.components.c.features[1]"
    assert "west.x1 and east.x0 round to the same coordinate 50000.0 m" in str(err.value)


def test_g6_circle_segments_on_a_3d_component_is_refused():
    d = doc([BOX], mesh={"controls": [{"select": "core", "circle_segment_count": 16}]})
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-3D-COMBINATION"
    assert err.value.path == "mesh.controls[0]"
    assert "mesh.controls: circle_segments on 'core' is not taken for 3d surfaces yet; use size" in str(err.value)


def test_a_lone_layers_feature_keeps_the_extrude_route():
    with pytest.raises(GeometryError, match="takes the meshine.extrude route"):
        build_mesh3d(e1())
    with pytest.raises(GeometryError, match="takes the meshine.extrude route"):
        from simcase.geometry_document import parse
        evaluate3d(parse(e1()))


def test_the_display_complex_of_a_lone_layers_component_is_the_meshloom_route_complex():
    from simcase.geometry_document import parse
    model = parse(e1())
    shown = display_complex3d(model)
    built = _evaluate(model.components["c"], through_meshloom=True)
    assert [(c.region, c.material, c.fine, c.slab, c.volume) for c in shown.cells] == \
        [(c.region, c.material, c.fine, c.slab, c.volume) for c in built.cells]
    assert [(f.axis, f.coord, f.loops, f.provenance, f.minus, f.plus, f.tag) for f in shown.faces] == \
        [(f.axis, f.coord, f.loops, f.provenance, f.minus, f.plus, f.tag) for f in built.faces]
    assert shown.region_names() == list(E1_K) and shown.levels == [0, 10 ** 9, 15 * 10 ** 8, 25 * 10 ** 8]
    # build_mesh3d still refuses it for the extrude route
    with pytest.raises(GeometryError, match="takes the meshine.extrude route"):
        build_mesh3d(e1())
    # a component with boxes gives evaluate3d's complex
    boxes = parse(doc([BOX]))
    assert [f.provenance for f in display_complex3d(boxes).faces] == [f.provenance for f in evaluate3d(boxes).faces]


def test_display_complex3d_is_public_and_picks_the_component():
    import simcase
    from simcase.geometry_document import parse
    assert "display_complex3d" in simcase.__all__ and "evaluate3d" not in simcase.__all__
    assert simcase.display_complex3d is display_complex3d
    d = e1()
    d["geometry"]["components"]["plan"] = {"dimension": "2d", "length_unit": "mm", "depth": None,
                                           "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10},
                                           "background": {"material": "air"}, "features": []}
    model = simcase.parse_geometry(d)
    assert simcase.display_complex3d(model).component == "c"              # the one 3d component
    assert simcase.display_complex3d(model, "c").component == "c"
    with pytest.raises(GeometryError) as err:
        simcase.display_complex3d(model, "nope")
    assert err.value.code == "E-CONTRACT" and err.value.path == "geometry.components.nope"
    assert "no component 'nope'" in str(err.value)
    with pytest.raises(GeometryError) as err:
        simcase.display_complex3d(model, "plan")
    assert err.value.code == "E-CONTRACT" and err.value.path == "geometry.components.plan.dimension"
    assert "component 'plan' is 2d" in str(err.value)
    d["geometry"]["components"]["other"] = copy.deepcopy(d["geometry"]["components"]["c"])
    with pytest.raises(GeometryError, match="name a 3d component: the model has 2"):
        simcase.display_complex3d(parse(d))


def test_the_estimate_is_checked_before_meshing():
    d = doc([BOX], size="0.05 mm", mesh={"element_count_limit": 30000})
    with pytest.raises(GeometryError) as err:
        build_mesh3d(d)
    assert err.value.code == "E-MESH-ESTIMATE"
    assert "about 12600000 tetrahedra" in str(err.value) and "the limit is 30000" in str(err.value)


def test_the_estimate_is_reported_as_an_info_diagnostic():
    result = build_mesh3d(doc([BOX], background=None, size="0.8 mm"))
    (d,) = result.diagnostics
    assert d.code == "I-MESH-ESTIMATE" and d.severity == "info" and d.path == "geometry.components.c"
    T = 6.3 * 18 / 0.8 ** 3
    assert f"about {T:.0f} tetrahedra" in d.message
    assert f"about {T * 4e-4:.3g}-{T * 6e-4:.3g} s at 0.4-0.6 ms per tetrahedron" in d.message


# ----------------------------------------------------------------------------- selections

def test_selections_resolve_to_faces_and_nodes():
    features = [{"name": "base", "type": "box", "xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 1,
                 "material": "Al"},
                {"name": "cap", "type": "box", "xmin": 3, "xmax": 7, "ymin": 3, "ymax": 7, "zmin": 1, "zmax": 2,
                 "material": "Cu"}]
    sel = {"bottom_tag": {"boundary": "z0"}, "bottom_face": {"boundary": "domain.z0"},
           "cap_top": {"boundary": "cap.z1"}, "joint": {"boundary": {"between": ["base", "cap"]}},
           "copper": {"region": "cap"}}
    d = doc(features, domain=(0, 10, 0, 10, 0, 2.5), background=None, size="0.8 mm",
            component={"selections": sel})
    result = build_mesh3d(d)
    m = result.mesh
    assert m.region_names == ["base", "cap"]
    assert sorted(m.tagged_faces) == ["void", "x0", "x1", "y0", "y1", "z0"]
    kind, faces = result.selections["bottom_tag"]
    assert kind == "boundary"
    np.testing.assert_array_equal(np.sort(faces, axis=0), np.sort(m.tagged_faces["z0"], axis=0))
    np.testing.assert_array_equal(result.selections["bottom_face"][1], result.selections["bottom_tag"][1])
    for name, z in (("cap_top", 2.0e-3), ("joint", 1.0e-3)):
        kind, faces = result.selections[name]
        assert kind == "boundary" and len(faces)
        assert np.all(m.nodes[faces][..., 2] == z)
        np.testing.assert_array_equal(result.selection_nodes[name], np.unique(faces))
    p = m.nodes[result.selections["joint"][1]]
    area = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum() / 2
    assert abs(area - 16e-6) <= 1e-12 * 16e-6
    kind, tets = result.selections["copper"]
    assert kind == "region"
    np.testing.assert_array_equal(tets, np.flatnonzero(m.regions == m.region_names.index("cap")))
    assert set(result.provenance_faces["cap.z0"].ravel()) <= set(result.provenance_faces["base.z1"].ravel())
    assert m.provenance_faces is result.provenance_faces
    assert v1_bad(m) == 0 and check_v2(result)


def test_boundary_tags_rename_exterior_faces():
    d = doc([BOX], background=None, size="0.8 mm",
            component={"boundary_tags": [{"tag": "sink", "select": {"boundary": "core.z0"}}]})
    result = build_mesh3d(d)
    assert sorted(result.mesh.tagged_faces) == ["sink", "void"]
    np.testing.assert_array_equal(np.sort(result.mesh.tagged_faces["sink"], axis=0),
                                  np.sort(result.provenance_faces["core.z0"], axis=0))
    assert v1_bad(result.mesh) == 0 and check_v2(result)


def test_an_enclosed_void_box_is_a_hole():
    features = [{"name": "block", "type": "box", "xmin": 0, "xmax": 4, "ymin": 0, "ymax": 4, "zmin": 0, "zmax": 2,
                 "material": "Al"},
                {"name": "pore", "type": "box", "xmin": 1, "xmax": 3, "ymin": 1, "ymax": 3, "zmin": 0.5, "zmax": 1.5,
                 "material": None}]
    result = build_mesh3d(doc(features, domain=(0, 4, 0, 4, 0, 2), background=None, size="0.5 mm"))
    m = result.mesh
    assert m.region_names == ["block"]
    assert sorted(m.tagged_faces) == ["void", "x0", "x1", "y0", "y1", "z0", "z1"]
    pore = np.concatenate([result.provenance_faces[f"pore.{p}"] for p in ("x0", "x1", "y0", "y1", "z0", "z1")])
    np.testing.assert_array_equal(np.unique(np.sort(pore, axis=1), axis=0),
                                  np.unique(np.sort(m.tagged_faces["void"], axis=1), axis=0))
    p = m.nodes[m.tets]
    vol = np.abs(np.einsum("ti,ti->t", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))).sum() / 6
    assert abs(vol - (32 - 4) * 1e-9) <= 1e-12 * 28e-9
    assert euler(m.tets) == 2                       # a ball with a cavity: chi = 2
    assert v1_bad(m) == 0 and check_v2(result)


# ----------------------------------------------------------------------------- P1

def _solve(mesh, kappa):
    from galerkin.thermal3d import solve_steady_heat_3d
    bottom, top = mesh.boundary["z0"], mesh.boundary["z1"]
    fixed = {int(n): 0.0 for n in bottom}
    fixed.update({int(n): 1.0 for n in top})
    return solve_steady_heat_3d(mesh, thermal_conductivity=kappa, prescribed_temperature=fixed), top


def _exact(points):
    from refsol.thermal3d import layered_slab
    return layered_slab(points, position=[z * 1e-3 for z in E1_LEVELS_MM], thermal_conductivity=list(E1_K.values()),
                        prescribed_temperature=(0.0, 1.0))


def _extrude_e1(h_mm):
    from galerkin import from_mesher
    from meshine import Domain, box_sides, extrude, generate, rectangle
    from simcase.geometry_document import layer_stack, parse
    d = Domain(size=h_mm * 1e-3)
    d.add_region("plate", rectangle(0, 0, 0.01, 0.01))
    footprint = generate(d, box_sides(0, 0.01, 0, 0.01))
    stack = layer_stack(parse(e1()), "c")
    mesh = extrude(footprint, [float(Fraction(z, PM)) for z in stack.levels], stack.table_for(footprint.region_names),
                   size=h_mm * 1e-3)
    return from_mesher(mesh)


@pytest.mark.parametrize("route", ["meshloom", "extrude"])
@pytest.mark.parametrize("h_mm", [0.8, 0.4])
def test_p1_layered_slab_is_exact(route, h_mm):
    mesh = e1_mesh("mm", h_mm).mesh if route == "meshloom" else _extrude_e1(h_mm)
    result, top = _solve(mesh, dict(E1_K))
    exact = _exact(mesh.nodes)
    error = float(np.max(np.abs(result.temperature - exact.temperature)))
    rate = float(result.reaction_heat_rate[top].sum())
    expected = float(-exact.heat_flux[0, 2]) * 1e-4                   # W through the 10 x 10 mm top
    assert error <= 1e-10, f"{route} h={h_mm}: max |T_h - T| = {error:.3e}"
    assert abs(rate - expected) <= 1e-9 * abs(expected), f"{route} h={h_mm}: rate {rate!r} vs {expected!r}"
    if route == "meshloom":
        assert mesh.num_tets <= 30000
