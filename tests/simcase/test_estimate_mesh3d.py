# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``simcase.estimate_mesh3d``: build_mesh3d's I-MESH-ESTIMATE and refusals, without meshing.

Boxes and slab layers; a builder-shaped (cylinder, sphere) estimate test follows once that route
is on main."""
import json

import pytest

import model3d_fixtures as F
import simcase

meshloom = pytest.importorskip("meshloom")
needs_kernel = pytest.mark.skipif(not meshloom.kernel_available(), reason="meshloom's compiled kernel is not built")


def card(size=None, **mesh):
    doc = json.loads(json.dumps(F.card()))
    doc["mesh"] = {**doc["mesh"], **({"element_size": size} if size else {}), **mesh}
    return doc


def refusals(doc):
    with pytest.raises(simcase.GeometryError) as built:
        simcase.build_mesh3d(doc)
    with pytest.raises(simcase.GeometryError) as estimated:
        simcase.estimate_mesh3d(doc)
    b, e = built.value, estimated.value
    assert (str(e), getattr(e, "code", None), getattr(e, "path", None)) == \
        (str(b), getattr(b, "code", None), getattr(b, "path", None))
    return e


def test_the_card_s_estimate():
    found = simcase.estimate_mesh3d(card())
    assert (found.component, found.tetrahedra, found.limit) == ("stack3d", 20160, 600000)
    assert found.seconds == pytest.approx(20160 * 6e-4)
    (info,) = found.diagnostics
    assert info.code == "I-MESH-ESTIMATE" and "about 20160 tetrahedra" in info.message
    assert isinstance(found, simcase.Mesh3DEstimate)


@needs_kernel
def test_estimate_parity_with_the_built_mesh_on_the_card():
    doc = card()
    built = simcase.build_mesh3d(doc)
    found = simcase.estimate_mesh3d(doc)
    assert found.tetrahedra == round(built.estimate)
    assert [d.as_dict() for d in built.diagnostics] == [d.as_dict() for d in found.diagnostics]


def test_refusal_parity_at_0_99_and_1_5_times_the_limit():
    t = simcase.estimate_mesh3d(card()).tetrahedra
    under = card(element_count_limit=round(t / 0.99))        # the estimate is 0.99x the limit
    assert simcase.estimate_mesh3d(under).limit == round(t / 0.99)
    # build_mesh3d does not refuse it either: its pre-meshing steps pass (no meshing here)
    from simcase.geometry_engine3d import _prepare
    assert _prepare(under)[2].estimate == t
    over = card(element_count_limit=round(t / 1.5))
    e = refusals(over)
    assert e.code == "E-MESH-ESTIMATE" and e.path == "mesh.element_count_limit"
    assert f"about {t} tetrahedra" in str(e)


def test_a_below_tolerance_document_is_refused_by_both():
    """Two boxes with a background strip 2e-8 of the domain diagonal wide between them (mm, about
    290 pm): below the 3e-8 mesher tolerance, a thin piece."""
    import math
    x = float(f"{5 + 2e-8 * math.sqrt(10 ** 2 + 10 ** 2 + 2.5 ** 2):.12g}")
    doc = F.doc([{"name": "a", "type": "box", "xmin": 0, "xmax": 5, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5,
                  "material": "m1"},
                 {"name": "b", "type": "box", "xmin": x, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5,
                  "material": "m2"}], background="bg", size="2 mm")
    e = refusals(doc)
    assert e.code == "E-CONTRACT" and "below the mesher tolerance" in str(e)


def test_a_feature_not_taken_is_refused_by_both():
    doc = card()
    doc["geometry"]["components"]["stack3d"]["features"].append(
        {"name": "pin", "type": "cylinder", "x": 5, "y": 5, "r": 1, "zmin": 0, "zmax": 4, "material": "copper"})
    refusals(doc)
