# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""W5 for cylinders and spheres (E2-UI): the check's refusals of builder-shape documents.

Pre-registered (fixed before measuring; never loosened): one document per stem the check raises for
cylinders and spheres: a cylinder that touches a domain side, one that crosses a side, the staged
stem (a cylinder not through the slab; a sphere beside a box), a sphere that touches or crosses a
domain face, two spheres that touch or cross, the below-tolerance E-CONTRACT on the builder route and
``circle_segments`` on a 3d cylinder (an unknown key). The check answers the engine's own words as
written (``simcase.estimate_mesh3d``'s refusal of the same document), its code, its path and
``features[i]`` where the path names one: 100%. A refusal while forming answers ``ok: false``; the
below-tolerance refusal comes in ``mesh`` with the shape formed.
"""
import copy
import json

import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402

CARD2 = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-via-slab-3d.json"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def card2():
    return json.loads(CARD2.read_text(encoding="utf-8"))


def cylinder(**change):
    doc = card2()
    doc["geometry"]["components"]["c"]["features"][0].update(change)
    return doc


def features(feats, background):
    doc = card2()
    comp = doc["geometry"]["components"]["c"]
    comp["features"], comp["background"] = copy.deepcopy(feats), {"material": background}
    return doc


def sphere(name, cx, cz, r, material="copper"):
    return {"name": name, "type": "sphere", "cx": cx, "cy": 0, "cz": cz, "r": r, "material": material}


BOX = {"name": "blk", "type": "box", "xmin": -1, "xmax": -0.5, "ymin": -1, "ymax": 1, "zmin": 0, "zmax": 1,
       "material": "copper"}
# (document, forming?, code, path, features[i] or None, a stem of the words)
W5_CURVED = {
    "cylinder touches a side": (lambda: cylinder(cx=0.7), True, "E-3D-COMBINATION",
                                "geometry.components.c.features[0]", 0, "cylinder 'via' touches domain.x1 at one line"),
    "cylinder crosses a side": (lambda: cylinder(cx=0.9), True, "E-3D-COMBINATION",
                                "geometry.components.c.features[0]", 0, "cylinder 'via' crosses the side domain.x1"),
    "cylinder not through the slab": (lambda: cylinder(zmax=0.5), True, "E-3D-COMBINATION",
                                      "geometry.components.c.features[0]", 0, "cylinder 'via' is not taken yet"),
    "sphere beside a box": (lambda: features([BOX, sphere("ball", 0.3, 0.5, 0.2)], "slab"), True, "E-3D-COMBINATION",
                            "geometry.components.c.features[1]", 1, "sphere 'ball' is not taken yet"),
    "sphere touches a side": (lambda: features([sphere("ball", 0, 0.5, 0.5)], "slab"), True, "E-3D-COMBINATION",
                              "geometry.components.c.features[0]", 0, "sphere 'ball' touches or crosses domain.z0"),
    "spheres touch or cross": (lambda: features([sphere("a", 0, 0.5, 0.3), sphere("b", 0.2, 0.5, 0.3, "slab")], None),
                               True, "E-3D-COMBINATION", "geometry.components.c.features[1]", 1,
                               "spheres 'a' and 'b' touch or cross"),
    "below tolerance": (lambda: cylinder(cx=0.7 - 4e-8), False, "E-CONTRACT", "geometry.components.c", None,
                        "below the mesher tolerance 3e-08"),
    "circle_segments": (lambda: cylinder(circle_segments=32), True, "E-KEY-UNKNOWN",
                        "geometry.components.c.features[0].circle_segments", 0, "unknown key 'circle_segments'"),
}


@pytest.mark.parametrize("case", list(W5_CURVED))
def test_w5_curved_the_check_answers_the_engine_s_refusal(client, case):
    make, forming, code, path, index, stem = W5_CURVED[case]
    with pytest.raises((simcase.GeometryError, simcase.DocumentError)) as err:
        simcase.estimate_mesh3d(make())
    engine = err.value
    answer = client.post("/api/model3d/check", json={"doc": make()}).json()
    refusal = {"ok": False, "refused": str(engine), "code": code, "path": path, "feature_index": index}
    if forming:
        assert {k: answer.get(k) for k in refusal} == refusal
        assert "mesh" not in answer and "run" not in answer
    else:
        assert answer["ok"] is True and answer["display"]["faces"], "the shape forms: the view is not greyed"
        assert answer["mesh"] == refusal
    assert stem in str(engine)
    assert (getattr(engine, "code", None), getattr(engine, "path", None)) == (code, path)
