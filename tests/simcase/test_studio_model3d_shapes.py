# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio 3D view's display and section answers for cylinders and spheres in meshloom's builder shapes.

``/api/model3d/display`` and ``/api/model3d/section`` branch on the parsed model's feature types: a 3d
component holding a cylinder or a sphere goes through ``simcase.display_shapes3d``; every other one keeps
the complex's answer, unchanged (tests/simcase/test_studio_model3d.py). The answer keeps every field of
the complex's; each face gains ``shape``, a curved face has ``axis`` and ``at`` null, and the answer gains
``display_note``. The checks of the shapes themselves (W1(b), W2) are tests/simcase/test_geometry_display3d.py;
W1(a) and W18 need a mesh: tests/simcase/test_studio_model3d_shapes_mesh.py.
"""
import base64

import numpy as np
import pytest

import test_geometry_display3d as G
from simcase import display_shapes3d, parse_geometry

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app, model3d_api  # noqa: E402

PM = 10 ** 12
NOTE = "Shape drawn for display; the mesh follows it to within its size"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def get(view, key, dtype, width=1):
    a = np.frombuffer(base64.b64decode(view[key]), dtype=np.dtype(dtype).newbyteorder("<"))
    return a.reshape(-1, width) if width > 1 else a


def box_doc():
    return G.doc([{"name": "core", "type": "box", "xmin": -0.5, "xmax": 0.5, "ymin": -0.5, "ymax": 0.5, "zmin": 0,
                   "zmax": 0.5, "material": "Cu"}], (-1, 1, -1, 1, 0, 1), "FR4")


@pytest.mark.parametrize("case", list(G.CASES))
def test_the_display_answer_keeps_every_field_and_draws_the_shapes(client, case):
    doc = G.CASES[case]()
    reply = client.post("/api/model3d/display", json={"doc": doc})
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    view = reply.json()
    boxes = client.post("/api/model3d/display", json={"doc": box_doc()}).json()
    assert set(boxes) | {"display_note"} == set(view)
    assert set(boxes["faces"][0]) | {"shape", "segments"} == set(view["faces"][0])
    assert view["ok"] is True and view["display_note"] == NOTE
    shapes = display_shapes3d(parse_geometry(doc))
    positions, indices, owner = get(view, "positions", "f4", 3), get(view, "indices", "u4", 3), get(view, "triangle_faces", "u4")
    origin = np.array([(shapes.domain[k + "min"] + shapes.domain[k + "max"]) / 2 for k in "xyz"])
    assert view["counts"]["triangles"] == len(indices) == len(owner)
    for f, face in zip(view["faces"], shapes.faces):
        assert f["id"] == face.index and f["shape"] == face.shape and f["names"] == list(face.names)
        assert f["minus"] == list(face.minus) and f["plus"] == list(face.plus) and f["tag"] == face.tag
        if face.shape == "plane":
            assert f["axis"] == "xyz"[face.axis] and f["at"] == face.coord / PM
        else:
            assert f["axis"] is None and f["at"] is None
        mine = slice(f["first_triangle"], f["first_triangle"] + f["triangle_count"])
        assert np.all(owner[mine] == face.index) and f["triangle_count"] == len(face.triangles)
        drawn = positions[indices[mine]].reshape(-1, 3)
        expect = ((face.vertices[face.triangles] - origin) / PM).astype(np.float32).reshape(-1, 3)
        assert np.array_equal(drawn, expect)
        assert f["area"] == pytest.approx(face.area, rel=1e-15)
    assert [r["name"] for r in view["regions"]] == [r.name for r in shapes.regions]
    assert view["selections"] == []


def test_slice_a_answers_are_unchanged_by_the_branch(client):
    """A box document's answer has no shape, no display note, and is the complex's."""
    view = client.post("/api/model3d/display", json={"doc": box_doc()}).json()
    assert "display_note" not in view and all("shape" not in f for f in view["faces"])
    model, comp, cx = model3d_api.complex_of(box_doc())
    assert view == model3d_api._display(model, comp, cx)


def test_the_card_is_served_by_name_and_is_stage_5_e2(client):
    import math
    reply = client.get("/model3d-assets/model3d-via-slab-3d.json")
    assert reply.status_code == 200 and reply.json() == G.card2()
    doc = G.card2()
    comp = doc["geometry"]["components"]["c"]
    via = comp["features"][0]
    k = {name: float(m["thermal_conductivity"].split()[0]) for name, m in doc["materials"].items()}
    k_s, k_v = k[comp["background"]["material"]], k[via["material"]]
    d = comp["domain"]
    area, length = (d["xmax"] - d["xmin"]) * (d["ymax"] - d["ymin"]), d["zmax"] - d["zmin"]
    t = {key: float(v.split()[0]) for key, v in doc["physics"]["heat"]["prescribed_temperature"].items()}
    q = (t["z1"] - t["z0"]) / length * (k_v * math.pi * via["r"] ** 2 + k_s * (area - math.pi * via["r"] ** 2))
    assert round(q, 5) == 31.99159
    assert (k_s, k_v, via["r"], doc["mesh"]["element_size"]) == (1.0, 100.0, 0.3, "0.1 m")


def test_a_section_of_card_2_is_exact(client):
    import math
    doc = G.card2()
    reply = client.post("/api/model3d/section", json={"doc": doc, "axis": "x", "at": 0.1}).json()
    assert reply["ok"] is True and reply["regions"] == ["background", "via"]
    seg = get(reply, "segments", "f4", 6).reshape(-1, 2, 3)
    owner = get(reply, "segment_faces", "u4")
    view = client.post("/api/model3d/display", json={"doc": doc}).json()
    side = next(f["id"] for f in view["faces"] if f["names"] == ["via.side"])
    lines = seg[owner == side]
    assert len(lines) == 2 and np.all(lines[:, :, 0] == np.float32(0.1))
    half = math.sqrt(0.09 - 0.01)
    assert sorted(lines[:, 0, 1].tolist()) == [float(np.float32(-half)), float(np.float32(half))]
    assert side in reply["faces"]
    reply = client.post("/api/model3d/section", json={"doc": doc, "axis": "z", "at": 2}).json()
    assert reply["ok"] is False and "z = 2 m" in reply["refused"] and "domain" in reply["refused"]


def test_a_cylinder_no_builder_takes_keeps_the_builders_words(client):
    feats = [{"name": "via", "type": "cylinder", "cx": 0, "cy": 0, "r": 0.3, "zmin": 0, "zmax": 0.5, "material": "Cu"}]
    view = client.post("/api/model3d/display", json={"doc": G.doc(feats, (-1, 1, -1, 1, 0, 1), "FR4")}).json()
    assert view == {"ok": False, "refused": f"cylinder 'via' {G.STAGED}"}
