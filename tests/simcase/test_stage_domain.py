# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``simcase.build_domain``, the public geometry stage, on format 0.3 documents.

For every kind whose run meshes with meshine, ``build_domain(doc)`` is bitwise what ``run(doc)``
hands ``meshine.generate``: the same pending loops (vertices, circles and the circles two loops
share), sizes, names and region materials, and a mesh generated from it with the run's own
keywords equals the run's mesh, so the boundary namer is the same too. Documents that meshine
does not mesh, and documents that are not format 0.3, are refused by name.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import meshine
import numpy as np
import pytest

import simcase
from simcase import Document, DocumentError, build_domain, examples, run
from simcase import geometry, runner

ROOT = Path(__file__).resolve().parents[2]


class _Stop(Exception):
    """Raised by the spy once the run has meshed: nothing after the mesh is under test."""


def _loop(loop, circles):
    if isinstance(loop, meshine.Circle):
        if id(loop) not in circles:
            circles[id(loop)] = len(circles)
        return ("circle", circles[id(loop)], loop.center.tobytes(), float(loop.radius).hex(), loop.n)
    arr = np.asarray(loop)
    return ("loop", arr.shape, str(arr.dtype), arr.tobytes())


def snapshot(domain) -> tuple:
    """Every number meshine reads from a Domain before ``build``, bit for bit."""
    circles: dict = {}
    pending = [(name, tuple(_loop(lp, circles) for lp in loops), None if size is None else float(size).hex())
               for name, loops, size in domain._pending]
    return (float(domain.default_size).hex(), float(domain.merge_eps).hex(), float(domain.param_eps).hex(),
            float(domain.snap_eps).hex(), pending)


def mesh_bytes(tri) -> tuple:
    return (np.asarray(tri.nodes).tobytes(), np.asarray(tri.triangles).tobytes(), np.asarray(tri.regions).tobytes(),
            tuple(tri.region_names),
            tuple(sorted((k, np.asarray(v).tobytes()) for k, v in tri.boundary_edges.items())))


def what_run_meshes(monkeypatch, doc):
    """(domain snapshot, region materials, generate keywords, mesh) of the run's first mesh."""
    seen = {}
    real_domain, real_generate = geometry.build_domain, meshine.generate

    def domain_spy(canonical):
        out = real_domain(canonical)
        seen.setdefault("materials", dict(out[2]))
        return out

    def generate_spy(domain, namer, **kwargs):
        seen["domain"] = snapshot(domain)
        seen["kwargs"] = kwargs
        seen["mesh"] = mesh_bytes(real_generate(domain, namer, **kwargs))
        raise _Stop
    for target, name, spy in ((geometry, "build_domain", domain_spy), (runner, "build_domain", domain_spy),
                              (meshine, "generate", generate_spy), (runner, "generate", generate_spy)):
        monkeypatch.setattr(target, name, spy)
    with pytest.raises(_Stop):
        run(doc, verbose=False)
    monkeypatch.undo()
    return seen


def _example(name):
    return copy.deepcopy(examples.EXAMPLES[name]) if name in examples.EXAMPLES else \
        json.loads((ROOT / "examples" / "simcase" / f"{name}.json").read_text(encoding="utf-8"))


def _electric_coax():
    """An electric region document with circles, void, boundary tags and circle controls (mm)."""
    comp = {"dimension": "2d", "length_unit": "mm", "depth": None,
            "domain": {"xmin": 0, "xmax": 40, "ymin": 0, "ymax": 20}, "background": {"material": "M"},
            "features": [{"name": "cut", "type": "rect", "x": 0, "y": 0, "w": 40, "h": 20, "material": None},
                         {"name": "disc", "type": "circle", "cx": 20, "cy": 10, "r": 9, "material": "M"},
                         {"name": "hole", "type": "circle", "cx": 20, "cy": 10, "r": 3, "material": None}],
            "boundary_tags": [{"tag": "inner", "select": {"boundary": {"of": "hole"}}},
                              {"tag": "rim", "select": {"boundary": {"between": ["disc", "cut"]}}}]}
    return {"openphysics": "0.3", "name": "coax", "geometry": {"version": 1, "components": {"xs": comp}},
            "materials": {"M": {"electrical_conductivity": "3 S/m"}},
            "physics": {"e": {"type": "electric.steady2d",
                              "prescribed_electric_potential": {"inner": "1 V", "rim": "0 V"}}},
            "mesh": {"element_size": "2 mm", "controls": [{"select": "disc", "circle_segment_count": 64},
                                                          {"select": "hole", "circle_segment_count": 48}]},
            "study": {"type": "single"}, "results": {"save_fields": True, "plots": False}}


def _joule_strip():
    """A steady Joule region document on two flat regions (mm)."""
    return {"openphysics": "0.3", "name": "joule strip",
            "geometry": {"length_unit": "mm", "depth": None,
                         "domain": {"xmin": 0, "xmax": 2, "ymin": 0, "ymax": 1}, "background": {"material": "A"},
                         "shapes": [{"name": "b", "type": "rect", "x": 1, "y": 0, "w": 1, "h": 1, "material": "B"}]},
            "materials": {"A": {"electrical_conductivity": "2 S/m", "thermal_conductivity": "1 W/(m K)"},
                          "B": {"electrical_conductivity": "0.5 S/m", "thermal_conductivity": "2 W/(m K)"}},
            "physics": {"j": {"type": "joule.steady2d",
                              "prescribed_electric_potential": {"left": "1 V", "right": "0 V"},
                              "prescribed_temperature": {"left": "300 K", "right": "300 K"}}},
            "mesh": {"element_size": "0.25 mm"}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False}}


#: one document per form that meshes with meshine (region heat steady and transient, electric,
#: Joule and mechanics regions, em.modes2d flat with circles and grading, em.modes2d version 1)
MESHED = {
    "thermal_regions": lambda: _example("thermal_regions"),
    "layered_wall": lambda: _example("layered_wall"),
    "transient_thermal_regions": lambda: _example("transient_thermal_regions"),
    "electric coax": _electric_coax,
    "joule strip": _joule_strip,
    "elastic_regions": lambda: _example("elastic_regions"),
    "thermoelastic_regions": lambda: _example("thermoelastic_regions"),
    "soi_strip": lambda: _example("soi_strip"),
    "fiber": lambda: _example("fiber"),
    "hadley_rib": lambda: _example("hadley_rib"),
    "geometry_v1_soi_strip": lambda: _example("geometry_v1_soi_strip"),
    "geometry_v1_imprint_rib": lambda: _example("geometry_v1_imprint_rib"),
}


@pytest.mark.parametrize("name", sorted(MESHED))
def test_build_domain_is_what_run_hands_meshine(monkeypatch, name):
    data = MESHED[name]()
    seen = what_run_meshes(monkeypatch, Document.from_dict(copy.deepcopy(data)))
    domain, namer, materials = build_domain(Document.from_dict(copy.deepcopy(data)))
    assert snapshot(domain) == seen["domain"], name
    assert materials == seen["materials"], name
    assert mesh_bytes(meshine.generate(domain, namer, **seen["kwargs"])) == seen["mesh"], name


def test_the_domain_is_in_the_micrometre_meshing_frame():
    # thermal_regions is written in mm with element_size "2 mm": meshine receives micrometres
    domain, _namer, _materials = build_domain(Document.from_dict(_example("thermal_regions")))
    assert domain.default_size == 2000.0
    um = Document.from_dict(_example("soi_strip"))
    nm = copy.deepcopy(_example("soi_strip"))
    g = nm["geometry"]
    g["length_unit"] = "nm"
    g["domain"] = {k: float(v) * 1000 for k, v in g["domain"].items()}
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h"):
            s[k] = float(s[k]) * 1000
    assert snapshot(build_domain(um)[0]) == snapshot(build_domain(Document.from_dict(nm))[0])


@pytest.mark.parametrize("name, mesh", [("thermal_slab", "rectangle mesh"), ("electric_rectangle", "rectangle mesh"),
                                        ("joule_temperature", "rectangle mesh"), ("elastic_plate", "rectangle mesh"),
                                        ("transient_thermal_uniform", "rectangle mesh"), ("cavity_box", "box mesh")])
def test_documents_meshine_does_not_mesh_are_refused_by_name(name, mesh):
    data = _example(name)
    with pytest.raises(DocumentError) as caught:
        build_domain(Document.from_dict(data))
    entry = next(iter(data["physics"]))
    assert (caught.value.code, caught.value.path) == ("E-CONTRACT", f"physics.{entry}.type")
    assert f"meshed on galerkin's structured {mesh} (mesh.subdivision_count), not by meshine" in str(caught.value)


def test_a_document_that_is_not_format_0_3_is_refused_by_name():
    from simcase.modes_document import kernel_document
    from simcase.thermal_regions import handoff_03
    for internal in (kernel_document(Document.from_dict(_example("soi_strip"))),
                     handoff_03(Document.from_dict(_example("thermal_regions")))):
        with pytest.raises(DocumentError) as caught:
            build_domain(internal)
        assert [(d.code, d.path) for d in caught.value.diagnostics] == [("E-FORMAT", "openphysics")]
    with pytest.raises(TypeError, match="expected a Document"):
        build_domain(_example("soi_strip"))
    assert simcase.build_domain is build_domain and build_domain is not geometry.build_domain
