# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The 3D builder's server check (/api/model3d/check): coverage, refusals by feature, and the
selection a picked face becomes (slice B of the Studio 3D view).

Pre-registered checks (fixed before measuring; never loosened):

- W4 (server part): each of 10 listed faces of the card ``layer-stack-3d`` is named alone by a
  provenance name the check offers; the selection ``{"boundary": <name>}`` that "Use for -> New
  selection" writes, resolved by ``build_mesh3d``, gives the same mesh faces as the same selector
  typed by hand, and those are exactly the mesh faces of the picked complex face: 10/10.
- W5 (server part): one document per E-3D-COMBINATION stem the check can raise (footprint layers
  alone, footprint layers beside other features, a feature type not taken yet: extrude, cylinder,
  sphere): the refusal carries the engine's message as written, its code and features[i]: 100%.
  The stem "... round to the same coordinate" is raised before meshing: the check answers it under
  ``mesh`` (test_studio_model3d_check_mesh.py); circle_segments is not applicable.
"""
import json

import numpy as np
import pytest

import simcase
from simcase import GeometryError, display_complex3d, parse_geometry

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402

CARD = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json"
W4_NAMES = ("stack.sub.domain.x0", "stack.oxide.domain.y1", "stack.top.domain.x1", "stack.top.top",
            "via.x0", "via.x1", "via.y0", "via.y1", "via.z0", "via.z1")


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def card():
    return json.loads(CARD.read_text(encoding="utf-8"))


def numeric():
    """Card 1 written out in numbers: the document before it held its design parameters (t_ox, via_w)."""
    doc = card()
    del doc["geometry"]["parameters"]
    comp = doc["geometry"]["components"]["stack3d"]
    comp["features"][0]["layers"][1]["thickness"] = 10
    comp["features"][1].update(xmin=90, xmax=110, ymin=90, ymax=110, zmin=500, zmax=510)
    return doc


def doc3d(features, *, domain=(0, 10, 0, 10, 0, 5), background="air", footprint=False):
    keys = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    comps = {"c": {"dimension": "3d", "length_unit": "um", "domain": dict(zip(keys, domain)),
                   "background": {"material": background}, "features": features}}
    if footprint:       # the 2D component a footprint layer names
        comps["fp"] = {"dimension": "2d", "length_unit": "um", "depth": None,
                       "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10}, "background": {"material": "air"},
                       "features": [{"name": "pad", "type": "rect", "x": 2, "y": 2, "w": 2, "h": 2, "material": "m"}]}
    return {"openphysics": "0.3", "geometry": {"version": 1, "components": comps}}


def check(client, doc, component=None):
    reply = client.post("/api/model3d/check", json={"doc": doc, "component": component})
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    return reply.json()


def box(name, lo, hi, material="m"):
    return {"name": name, "type": "box", "xmin": lo[0], "xmax": hi[0], "ymin": lo[1], "ymax": hi[1],
            "zmin": lo[2], "zmax": hi[2], "material": material}


# ---- the card and coverage ---------------------------------------------------------------------

def test_the_card_is_the_slice_b_document():
    d = card()
    comp = d["geometry"]["components"]["stack3d"]
    assert comp["length_unit"] == "um" and comp["domain"] == {"xmin": 0, "xmax": 200, "ymin": 0, "ymax": 200,
                                                               "zmin": 0, "zmax": 610}
    stack, via = comp["features"]
    assert d["geometry"]["parameters"] == {"t_ox": {"value": "10 um"}, "via_w": {"value": "20 um"}}
    assert [(lay["name"], lay["thickness"], lay["material"]) for lay in stack["layers"]] == [
        ("sub", 500, "Si"), ("oxide", "t_ox", "SiO2"), ("top", 100, "Si (top)")]
    assert (via["type"], via["xmin"], via["xmax"], via["ymin"], via["ymax"], via["zmin"], via["zmax"]) == (
        "box", "100 - via_w / 2", "100 + via_w / 2", "100 - via_w / 2", "100 + via_w / 2", 500, "500 + t_ox")
    assert {k: v["thermal_conductivity"] for k, v in d["materials"].items()} == {
        "Si": "130 W/(m K)", "Si (top)": "130 W/(m K)", "SiO2": "1.4 W/(m K)", "Cu": "400 W/(m K)"}


def test_check_answers_features_with_coverage_from_the_complex(client):
    view = check(client, card())
    assert view["ok"] is True and view["component"] == "stack3d" and view["unit"] == "um"
    stack, via = view["features"]
    assert (stack["index"], stack["id"], stack["type"]) == (0, "stack", "layers")
    assert stack["coverage"] == "partial" and stack["covered_by"] == [1] and stack["text"] == "covered in part by 2 (via)"
    assert stack["volume"] == pytest.approx(200 * 200 * 610) and stack["owned"] == pytest.approx(200 * 200 * 610 - 4000)
    assert via["coverage"] == "full" and via["covered_by"] == [] and via["text"] == ""
    assert via["owned"] == pytest.approx(20 * 20 * 10)
    assert [r["name"] for r in view["regions"]] == ["Si", "SiO2", "Si (top)", "via"]
    assert view["display"]["counts"]["faces"] == len(view["display"]["faces"])


def test_a_fully_covered_feature_adds_no_region(client):
    doc = doc3d([box("a", (2, 2, 1), (4, 4, 2)), box("b", (1, 1, 0), (5, 5, 3)), box("c", (3, 3, 1), (6, 6, 2))])
    a, b, c = check(client, doc)["features"]
    assert (a["coverage"], a["covered_by"], a["text"]) == ("none", [1, 2], "covered by 2 (b), 3 (c); adds no region")
    assert a["owned"] == 0
    assert (b["coverage"], b["covered_by"], b["text"]) == ("partial", [2], "covered in part by 3 (c)")
    assert (c["coverage"], c["text"]) == ("full", "")


def test_coverage_counts_only_the_part_inside_the_domain(client):
    doc = doc3d([box("a", (-5, 0, 0), (5, 10, 5)), box("b", (8, 0, 0), (20, 10, 5))])
    a, b = check(client, doc)["features"]
    assert a["volume"] == pytest.approx(5 * 10 * 5) and a["coverage"] == "full"
    assert b["volume"] == pytest.approx(2 * 10 * 5) and b["coverage"] == "full"


def test_a_later_feature_that_owns_nothing_does_not_cover(client):
    # c lies inside b and is itself covered by d: a is covered by b and d, not c
    doc = doc3d([box("a", (0, 0, 0), (4, 4, 4)), box("b", (0, 0, 0), (2, 4, 4)),
                 box("c", (2, 0, 0), (3, 4, 4)), box("d", (2, 0, 0), (4, 4, 4))])
    a, b, c, d = check(client, doc)["features"]
    assert c["coverage"] == "none" and c["covered_by"] == [3]
    assert a["coverage"] == "none" and a["covered_by"] == [1, 3]


def test_check_lists_parameters_in_si_and_selections(client):
    doc = numeric()
    geometry = doc["geometry"]
    geometry["parameters"] = {"w": {"value": "20 um"}}
    via = geometry["components"]["stack3d"]["features"][1]
    via["xmin"], via["xmax"] = "100 - w / 2", "100 + w / 2"
    geometry["components"]["stack3d"]["selections"] = {"sink": {"boundary": "stack.sub.bottom"}}
    view = check(client, doc)
    assert view["ok"] is True
    assert view["parameters"] == [{"name": "w", "kind": "length", "value": pytest.approx(2e-5), "unit": "m",
                                   "written": "20 um", "used_by": ["features[1].xmax", "features[1].xmin"]}]
    assert view["selections"] == [{"name": "sink", "kind": "boundary", "entries": [0]}]


# ---- faces named alone (Use for -> New selection) and W4 --------------------------------------

def test_each_face_lists_the_names_that_select_it_alone(client):
    view = check(client, card())
    cx = display_complex3d(parse_geometry(card()))
    for face in view["display"]["faces"]:
        alone = [n for n in face["names"] if cx.faces_with(n) == [face["id"]]]
        assert face["alone"] == alone
    by_name = {n: f["id"] for f in view["display"]["faces"] for n in f["alone"]}
    assert set(W4_NAMES) <= set(by_name)


def test_w4_new_selection_resolves_to_the_picked_face_10_of_10():
    pytest.importorskip("meshloom")
    import meshloom
    if not meshloom.kernel_available():
        pytest.fail("W4 needs meshloom's compiled kernel")
    from simcase import build_mesh3d
    from simcase.studio import model3d_api
    picked = check(TestClient(app), card())["display"]["faces"]
    face_of = {n: f["id"] for f in picked for n in f["alone"]}
    made = card()
    for i, name in enumerate(W4_NAMES):
        # what "Use for -> New selection" writes for the picked face, and beside it the listed name
        # typed by hand as a selector
        made = model3d_api.new_selection(made, "stack3d", face_of[name], f"made_{i}")
        made["geometry"]["components"]["stack3d"]["selections"][f"hand_{i}"] = {"boundary": name}
    result = build_mesh3d(made)
    rows = lambda faces: {tuple(sorted(t)) for t in faces.tolist()}  # noqa: E731
    matched = 0
    for i, name in enumerate(W4_NAMES):
        (k1, by_pick), (k2, by_hand) = result.selections[f"made_{i}"], result.selections[f"hand_{i}"]
        picked_faces = np.concatenate([result.facet_faces[k] for k, f in enumerate(result.face_of_facet)
                                       if f == face_of[name]])
        matched += (k1, k2) == ("boundary", "boundary") and rows(by_pick) == rows(by_hand) == rows(picked_faces)
    assert matched == 10


def test_new_selection_refuses_a_face_no_name_selects_alone():
    from simcase.studio import model3d_api
    doc = card()
    # face 3 (z = 510 outside the via) is named stack.oxide.top and stack.top.bottom, each also on face 4
    with pytest.raises(GeometryError, match="no single name selects face 3 alone"):
        model3d_api.new_selection(doc, "stack3d", 3, "s")
    with pytest.raises(GeometryError, match="selection 'via' already exists|'via' is a feature id"):
        model3d_api.new_selection(doc, "stack3d", 4, "via")


def test_new_selection_route(client):
    reply = client.post("/api/model3d/selection", json={"doc": card(), "component": "stack3d", "face": 4,
                                                        "name": "top_of_via"})
    body = reply.json()
    assert reply.status_code == 200 and body["ok"] is True
    assert body["doc"]["geometry"]["components"]["stack3d"]["selections"] == {"top_of_via": {"boundary": "via.z1"}}
    refused = client.post("/api/model3d/selection", json={"doc": card(), "component": "stack3d", "face": 3,
                                                          "name": "x"}).json()
    assert refused["ok"] is False and "no single name selects face 3 alone" in refused["refused"]


# ---- W5: refusals by feature ------------------------------------------------------------------

FOOT = {"name": "f", "type": "layers", "z0": 0, "layers": [{"name": "a", "thickness": 1, "footprint": "fp"}]}
W5 = {      # (features, the features[i] refused, whether the document needs the footprint component)
    "footprint layers alone (S1)": ([FOOT], 0, True),
    "footprint layers beside other features (S2)": ([box("b0", (0, 0, 0), (1, 1, 1)), FOOT], 1, True),
    "extrude not taken yet (S3)": ([box("b0", (0, 0, 0), (1, 1, 1)),
                                    {"name": "e", "type": "extrude", "zmin": 0, "zmax": 1, "material": "m",
                                     "profile": {"type": "rect", "x": 0, "y": 0, "w": 1, "h": 1}}], 1, False),
    "cylinder not taken yet (S3)": ([{"name": "pin", "type": "cylinder", "axis": "z", "cx": 5, "cy": 5, "r": 1,
                                      "zmin": 0, "zmax": 1, "material": "m"}], 0, False),
    "sphere not taken yet (S3)": ([box("b0", (0, 0, 0), (1, 1, 1)), box("b1", (1, 1, 1), (2, 2, 2)),
                                   {"name": "ball", "type": "sphere", "cx": 5, "cy": 5, "cz": 2, "r": 1,
                                    "material": "m"}], 2, False),
}


@pytest.mark.parametrize("case", list(W5))
def test_w5_each_stem_is_refused_with_its_words_code_and_feature(client, case):
    features, index, footprint = W5[case]
    doc = doc3d(features, footprint=footprint)
    with pytest.raises(GeometryError) as engine:
        display_complex3d(parse_geometry(doc), "c")
    assert engine.value.code == "E-3D-COMBINATION"
    view = check(client, doc, "c")
    assert view == {"ok": False, "refused": str(engine.value), "code": "E-3D-COMBINATION",
                    "path": f"geometry.components.c.features[{index}]", "feature_index": index}


def test_other_refusals_carry_their_code_and_path(client):
    doc = doc3d([box("a", (0, 0, 0), (1, 1, 1), "m"), {"name": "s", "type": "layers", "z0": 2, "layers": [
        {"name": "l", "thickness": 1, "material": "n", "region": "a"}]}])
    view = check(client, doc)
    assert view["ok"] is False and view["code"] == "E-CONTRACT" and view["feature_index"] == 1
    flat = {"openphysics": "0.3", "geometry": {"version": 1, "components": {"xs": {
        "dimension": "2d", "length_unit": "um", "depth": None, "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1},
        "background": {"material": "a"}, "features": []}}}}
    view = check(client, flat)
    assert view["ok"] is False and view["feature_index"] is None and "'xs'" in view["refused"]
    assert client.post("/api/model3d/check", content=b"[", headers={"Content-Type": "application/json"}
                       ).status_code == 400


def test_the_card_is_served_by_name(client):
    reply = client.get("/model3d-assets/model3d-layer-stack-3d.json")
    assert reply.status_code == 200 and reply.json() == card()
