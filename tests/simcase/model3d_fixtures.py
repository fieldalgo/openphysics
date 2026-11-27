# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Documents of the Studio 3D view checks (W1-W3, W15): the card, E1 and the G1 sets.

``g1_case`` is a copy of the stage 5 G1 generator in ``test_geometry_engine3d.py``, which skips
as a whole module without meshloom's kernel; the 3D view needs no mesher, so its checks keep
their own copy, and ``test_studio_model3d.py`` checks that the copy gives the same sets.
"""
import json
import random
from pathlib import Path

import simcase

STATIC = Path(simcase.__file__).parent / "studio" / "static"
CARD = STATIC / "model3d-via-stack.json"
GRID = (4, 3, 2)                            # the G1 domain [0, 4] x [0, 3] x [0, 2] grid units (mm)
W1_SEEDS = tuple(range(50))


def card() -> dict:
    """The card document "Via in a layer stack" (um): substrate 0-2, oxide 2-3 and top silicon 3-4
    over a 10 x 10 domain, and a copper via box x, y in [4, 6] through the oxide (z in [2, 3])."""
    return json.loads(CARD.read_text(encoding="utf-8"))


def doc(features, *, unit="mm", domain=(0, 10, 0, 10, 0, 2.5), background="air", size="0.8 mm"):
    keys = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    comp = {"dimension": "3d", "length_unit": unit, "domain": dict(zip(keys, domain)),
            "background": {"material": background}, "features": features}
    return {"openphysics": "0.3", "geometry": {"version": 1, "components": {"c": comp}},
            "mesh": {"element_size": size}}


def e1() -> dict:
    """Stage 5 E1: three slab layers of 1, 0.5 and 1 mm over a 10 x 10 mm domain (one layers feature)."""
    layers = [{"name": n, "thickness": t, "material": n} for n, t in (("lower", 1), ("core", 0.5), ("upper", 1))]
    return doc([{"name": "stack", "type": "layers", "z0": 0, "layers": layers}])


def g1_case(seed):
    """Copy of the stage 5 G1 generator (test_geometry_engine3d.g1_case)."""
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


def g1_doc(seed) -> dict:
    boxes, background = g1_case(seed)
    return doc(boxes, domain=(0, GRID[0], 0, GRID[1], 0, GRID[2]), background=background, size="0.25 mm")


def w1_documents():
    """(label, document) of W1: E1, the card and the 50 seeded G1 sets."""
    yield "E1", e1()
    yield "card", card()
    for seed in W1_SEEDS:
        yield f"G1 seed {seed}", g1_doc(seed)
