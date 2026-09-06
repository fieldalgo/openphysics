# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import copy
import json

import numpy as np
import pytest

import physmat
from refsol import benchmarks, fiber, slab
from simdoc import Document, DocumentError, build_mesh, examples, run, solve_point
from simdoc.geometry import resolve_regions


# ---- document handling ---------------------------------------------------------

def test_examples_validate_and_roundtrip(tmp_path):
    for name, d in examples.EXAMPLES.items():
        doc = Document.from_dict(d)
        doc.save(tmp_path / f"{name}.json")
        again = Document.load(tmp_path / f"{name}.json")
        assert again.data == doc.data
        assert doc.summary()


def test_reads_a_0_1_document_by_migrating_it():
    """0.1 held one unnamed physics; it must still load, under the default name."""
    old = copy.deepcopy(examples.SOI_STRIP)
    old["simdoc"] = "0.1"
    old["physics"] = copy.deepcopy(old["physics"]["em1"])          # unwrap, back to 0.1 shape
    old["study"] = dict(old["study"], parameter="physics.wavelength")

    doc = Document.from_dict(old)

    assert doc["simdoc"] == "0.2"
    assert list(doc["physics"]) == ["em1"]
    assert doc["physics"]["em1"]["wavelength"] == 1.55
    assert doc["study"]["parameter"] == "physics.em1.wavelength"
    assert doc.get_path("physics.em1.wavelength") == 1.55           # the rewritten path resolves


def test_a_lossy_material_is_refused_rather_than_solved_lossless():
    """The scalar path cannot do loss; it must say so instead of dropping Im(eps)."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["geometry"]["shapes"][0]["material"] = "Au"
    doc = Document.from_dict(d)
    model = build_mesh(doc)
    assert np.iscomplexobj(model.eps_per_triangle(1.55))          # loss reaches the physics
    with pytest.raises(NotImplementedError, match="lossy"):
        solve_point(model, doc.sole_physics()[1])


def test_more_than_one_physics_is_rejected_for_now():
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["physics"]["th1"] = copy.deepcopy(d["physics"]["em1"])
    doc = Document.from_dict(d)
    doc.validate()                                                 # two physics is a valid document
    with pytest.raises(DocumentError, match="not implemented yet"):
        doc.sole_physics()                                         # solving both is not


@pytest.mark.parametrize("path,value,msg", [
    ("simdoc", "9.9", "format"),
    ("geometry.domain", {"xmin": 1, "xmax": 0, "ymin": 0, "ymax": 1}, "empty"),
    ("physics.em1.formulation", "magic", "formulation"),
    ("physics.em1.boundary.left", "open", "boundary"),
    ("mesh.size", -1, "mesh.size"),
    ("study", {"type": "sweep", "parameter": "physics.em1.nope", "values": [1]}, "does not exist"),
    ("study", {"type": "sweep", "parameter": "mesh.size", "values": [0.2]}, "not under 'physics.'"),
])
def test_validation_errors(path, value, msg):
    doc = Document.from_dict(examples.SOI_STRIP)
    doc.set_path(path, value)
    with pytest.raises(DocumentError, match=msg):
        doc.validate()


def test_shape_validation():
    d = copy.deepcopy(examples.SOI_STRIP)
    d["geometry"]["shapes"].append({"name": "core", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"})
    with pytest.raises(DocumentError, match="duplicated"):
        Document.from_dict(d)
    d = copy.deepcopy(examples.SOI_STRIP)
    d["geometry"]["shapes"][0].pop("w")
    with pytest.raises(DocumentError, match="missing"):
        Document.from_dict(d)


def test_unknown_material_is_reported():
    d = copy.deepcopy(examples.FIBER)
    d["geometry"]["shapes"][0]["material"] = "kryptonite"
    with pytest.raises(DocumentError, match="kryptonite"):
        run(Document.from_dict(d), verbose=False)


# ---- geometry resolution -------------------------------------------------------

def test_later_shapes_cut_earlier_ones_and_background_fills_the_rest():
    doc = Document.from_dict(examples.HADLEY_RIB)
    regions = {name: geom.area for name, _m, geom, _s, _e in resolve_regions(doc)}
    assert abs(regions["substrate"] - 180.0) < 1e-9
    assert abs(regions["slab"] - (18 * 0.3 - 3 * 0.3)) < 1e-9        # rib removed from the slab
    assert abs(regions["rib"] - 3.0) < 1e-9
    assert abs(regions["background"] - (18 * 3 - 18 * 0.3 - 3 * 0.7)) < 1e-9
    assert abs(sum(regions.values()) - 18 * 13) < 1e-9                  # tiles the whole domain


def test_untouched_circle_stays_exact():
    doc = Document.from_dict(examples.FIBER)
    regs = resolve_regions(doc)
    assert any(ex is not None for _n, _m, _g, _s, ex in regs)
    res = run(doc, verbose=False)
    core = res.mesh_regions == res.region_names.index("core")
    core_nodes = set(res.mesh_triangles[core].ravel())
    clad_nodes = set(res.mesh_triangles[~core].ravel())
    iface = np.array(sorted(core_nodes & clad_nodes))
    assert np.abs(np.hypot(*res.mesh_nodes[iface].T) - 4.0).max() < 1e-9


# ---- end to end against references --------------------------------------------

def test_slab_te_matches_refsol_through_the_whole_chain():
    doc = Document.from_dict(examples.SLAB_TE_CHECK)
    res = run(doc, verbose=False)
    n_si, n_ox = physmat.get("Si").n(1.55), physmat.get("SiO2").n(1.55)
    exact = slab.modes(n_si, n_ox, n_ox, 0.22, 1.55, "TE")[0]
    assert abs(res.neff[0, 0] - exact) < 1.5e-3                      # P1, h = 10 nm in the film


def test_fiber_scalar_matches_lp_modes():
    res = run(Document.from_dict(examples.FIBER), verbose=False)
    lp = fiber.lp_modes(4.0, 1.45, 1.44, 1.55)
    assert abs(res.neff[0, 0] - lp[0].neff) < 2e-4                    # LP01
    assert abs(res.neff[0, 1] - lp[1].neff) < 2e-4                    # LP11


def test_rib_scalar_is_near_hadley():
    res = run(Document.from_dict(examples.HADLEY_RIB), verbose=False)
    assert abs(res.neff[0, 0] - benchmarks.rib_neff(0.3)) < 5e-4      # scalar model: ~2.5e-4 off


def test_sweep_produces_group_index_and_saves(tmp_path):
    d = copy.deepcopy(examples.SOI_STRIP)
    d["study"]["values"] = [1.50, 1.55, 1.60]
    d["physics"]["em1"]["num_modes"] = 1
    res = run(Document.from_dict(d), verbose=False)
    assert res.neff.shape == (3, 1)
    assert np.all(np.diff(res.neff[:, 0]) < 0)                        # n_eff falls with wavelength
    ng = res.group_index()
    assert ng is not None and (ng > res.neff).all()                   # normal dispersion: n_g > n_eff
    out = res.save(tmp_path / "out")
    for f in ("summary.json", "fields.npz", "results.png", "log.txt", "model.json"):
        assert (out / f).exists()
    s = json.loads((out / "summary.json").read_text())
    assert s["study"]["values"] == [1.5, 1.55, 1.6] and len(s["group_index"]) == 3


def test_vector_formulation_not_yet_available():
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["physics"]["em1"]["formulation"] = "vector"
    with pytest.raises(NotImplementedError, match="M3a"):
        run(Document.from_dict(d), verbose=False)
