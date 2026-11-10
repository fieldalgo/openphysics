# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""em.modes2d under the units and naming rules (units batch C8): P2-4, P2-5 negative controls, P2-6,
P2-7/P2-8 (G4 A4 refusal rows), P2-9, P2-11, P2-15, P2-16 and the defining formulas of the
derived results. P2-5 bitwise invariance is tests/simcase/test_length_canonical.py; P2-18 export
is tests/simcase/test_export_modes.py; P2-1 is test_units_batch_equivalence.py."""

from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path

import numpy as np
import pytest

import physmat
from physmat import units
from simcase import Document, DocumentError, build_mesh, examples, run
from simcase.runner import FIELDS

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tools" / "units_batch" / "fixtures" / "v03"
SIMCASE = ROOT / "packages" / "simcase" / "src" / "simcase"
EXAMPLE_FILES = ROOT / "examples" / "simcase"
TEXTUAL = ("resolved_inputs", "defaults_applied", "diagnostics", "extent", "timing")
P = "physics.em1."
TC = "exp(-i omega t)"


def example(name):
    if name in examples.EXAMPLES:
        return copy.deepcopy(examples.EXAMPLES[name])
    return json.loads((EXAMPLE_FILES / f"{name}.json").read_text(encoding="utf-8"))


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def source(name):
    return fixture(name) if name.startswith("em_") else example(name)


def hexed(value):
    """A tree with every float as its float.hex text, so that == is bitwise."""
    if isinstance(value, dict):
        return {key: hexed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [hexed(item) for item in value]
    if isinstance(value, float):
        return value.hex()
    return value


def saved(data, out):
    data = copy.deepcopy(data)
    data["results"] = dict(data.get("results") or {}, plots=False)
    result = run(Document.from_dict(data), verbose=False)
    path = result.save(out)
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    with np.load(path / "fields.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files if key != "metadata_json"}
        metadata = json.loads(str(archive["metadata_json"]))
    return result, path, summary, arrays, metadata


def same_arrays(a, b):
    assert set(a) == set(b)
    for key in a:
        assert a[key].dtype == b[key].dtype and a[key].shape == b[key].shape, key
        assert a[key].tobytes() == b[key].tobytes(), key


def results_of(summary):
    return hexed({key: value for key, value in summary.items() if key not in TEXTUAL})


DELETE = object()


def put(data, path, value):
    """Set ``value`` at a dotted path such as ``geometry.shapes[0].material`` (DELETE removes it)."""
    node, keys = data, re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for key in keys[:-1]:
        node = node[int(key[1:-1])] if key.startswith("[") else node.setdefault(key, {})
    last = keys[-1]
    if value is DELETE:
        del node[last]
    elif last.startswith("["):
        node[int(last[1:-1])] = value
    else:
        node[last] = value


def refusal(data):
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    return [d for d in caught.value.diagnostics if d.severity == "error"]


# ---- P2-4: the same value in any spelling ---------------------------------------------------------

def soi_strip_in_nm():
    """soi_strip with every tagged length written in nm; the shape numbers stay in um."""
    data = example("soi_strip")
    data["geometry"]["shapes"][0]["element_size"] = "20 nm"
    data["physics"]["em1"]["vacuum_wavelength"] = "1550 nm"
    data["mesh"] = {"element_size": "250 nm", "grading": {"position": ["0 nm", "110 nm"], "near": "20 nm",
                                                         "far": "160 nm", "refinement_distance": "1000 nm"}}
    data["study"]["values"] = {"unit": "nm", "values": [1400, 1450, 1500, 1550, 1600, 1650, 1700]}
    return data


def pml_bent_slab_in_m():
    data = example("pml_bent_slab")
    p = data["physics"]["em1"]
    p["vacuum_wavelength"] = "1.55e-6 m"
    p["pml"]["pml_thickness"] = {"bottom": "6e-7 m", "top": "1e-6 m"}
    p["bend"].update(bend_radius="2e-6 m", bend_origin="0 m")
    data["geometry"]["shapes"][0]["element_size"] = "1.2e-8 m"
    return data


@pytest.mark.parametrize("name,rewrite", [("soi_strip", soi_strip_in_nm), ("pml_bent_slab", pml_bent_slab_in_m)])
def test_p2_4_unit_spellings_give_the_same_si_tree_kernel_doubles_arrays_and_summary(tmp_path, name, rewrite):
    from simcase.modes_document import kernel_document
    base, other = Document.from_dict(example(name)), Document.from_dict(rewrite())
    assert hexed(other.si) == hexed(base.si)
    assert hexed(kernel_document(other).data) == hexed(kernel_document(base).data)
    _, _, a, arrays_a, _ = saved(example(name), tmp_path / "a")
    _, _, b, arrays_b, _ = saved(rewrite(), tmp_path / "b")
    same_arrays(arrays_b, arrays_a)
    assert results_of(b) == results_of(a)


@pytest.mark.parametrize("text", ["1.55 µm", "1.55 μm"])
def test_p2_4_a_micro_sign_is_a_spelling_fix_and_no_error(text):
    data = example("vector_slab")
    data["physics"]["em1"]["vacuum_wavelength"] = text
    doc = Document.from_dict(data)
    assert doc.si["physics"]["em1"]["vacuum_wavelength"] == Document.from_dict(example("vector_slab")).si[
        "physics"]["em1"]["vacuum_wavelength"]
    assert [fix["path"] for fix in doc.spelling_fixes()] == [P + "vacuum_wavelength"]


# ---- P2-5 negative controls (the bitwise invariance is test_length_canonical.py) -------------------

def test_p2_5_soi_strip_numbers_declared_in_mm_are_refused_before_meshing():
    data = example("soi_strip")
    data["geometry"]["length_unit"] = "mm"                  # micrometre numbers; tagged sizes stay in um
    assert [(d.code, d.path) for d in refusal(data)] == [("E-MESH-ESTIMATE", "geometry")]


def test_p2_5_soi_strip_numbers_declared_in_nm_warn_and_stay_valid():
    data = example("soi_strip")
    data["geometry"]["length_unit"] = "nm"
    doc = Document.from_dict(data)
    assert [(d.code, d.path) for d in doc.diagnostics] == [("W-GEOMETRY-SCALE", "geometry")]
    assert "vacuum wavelengths" in doc.diagnostics[0].message and "check length_unit" in doc.diagnostics[0].message


# ---- P2-6: a cross-section's depth changes nothing (em results have no per-depth or total names) --

def test_p2_6_depth_leaves_an_em_result_bitwise_unchanged():
    runs = {}
    for depth in (None, "1 m", "40 mm"):
        data = example("vector_slab")
        data["geometry"]["depth"] = depth
        result = run(Document.from_dict(data), verbose=False)
        summary = {k: v for k, v in result.summary().items() if k not in TEXTUAL + ("name",)}
        runs[depth] = ({k: v.tobytes() for k, v in result.arrays().items() if isinstance(v, np.ndarray)},
                       json.dumps(summary, sort_keys=True))
        assert not [k for k in summary if "depth" in k], summary.keys()
    assert runs["1 m"] == runs[None] and runs["40 mm"] == runs[None]


# ---- P2-7 and P2-8: the refusals the rules promise (G4 A4 rows), each with its code and path ------

A4 = [
    # row 1: a dimensional value without its unit (no zero exception)
    ("soi_strip", P + "vacuum_wavelength", 1.55, "E-UNIT-MISSING", P + "vacuum_wavelength"),
    ("pml_bent_slab", P + "pml.pml_thickness.top", 1, "E-UNIT-MISSING", P + "pml.pml_thickness.top"),
    ("pml_bent_slab", P + "bend.bend_radius", 2, "E-UNIT-MISSING", P + "bend.bend_radius"),
    ("pml_bent_slab", P + "bend.bend_origin", 0, "E-UNIT-MISSING", P + "bend.bend_origin"),
    ("em_gaussian_overlap_scalar", "results.mode_overlap.gaussian.beam_waist_radius", 0.5, "E-UNIT-MISSING",
     "results.mode_overlap.gaussian.beam_waist_radius"),
    ("soi_strip", "study.values", [1.5, 1.55, 1.6], "E-UNIT-MISSING", "study.values"),
    ("soi_strip", "mesh.element_size", 0.25, "E-UNIT-MISSING", "mesh.element_size"),
    # row 2: the wrong dimension
    ("soi_strip", P + "vacuum_wavelength", "193.4 THz", "E-UNIT-DIMENSION", P + "vacuum_wavelength"),
    # row 3: off the vacuum_wavelength menu (nm um m); a case slip is a suggestion, never a fix
    ("soi_strip", P + "vacuum_wavelength", "1.55 Mm", "E-UNIT-NOT-ACCEPTED", P + "vacuum_wavelength"),
    ("soi_strip", P + "vacuum_wavelength", "1.55 mm", "E-UNIT-NOT-ACCEPTED", P + "vacuum_wavelength"),
    ("soi_strip", P + "vacuum_wavelength", "1550 nM", "E-UNIT-UNKNOWN", P + "vacuum_wavelength"),
    # row 4: no space
    ("soi_strip", P + "vacuum_wavelength", "1550nm", "E-UNIT-UNKNOWN", P + "vacuum_wavelength"),
    # row 5: the domain
    ("soi_strip", P + "vacuum_wavelength", "0 nm", "E-DOMAIN", P + "vacuum_wavelength"),
    ("soi_strip", P + "vacuum_wavelength", "-1550 nm", "E-DOMAIN", P + "vacuum_wavelength"),
    ("pml_bent_slab", P + "pml.pml_thickness.top", "0 um", "E-DOMAIN", P + "pml.pml_thickness.top"),
    ("pml_bent_slab", P + "pml.pml_minimum_physical_fraction", 0, "E-DOMAIN", P + "pml.pml_minimum_physical_fraction"),
    ("vector_slab", "materials.film.refractive_index", 0, "E-DOMAIN", "materials.film.refractive_index"),
    ("pml_bent_slab", P + "bend.bend_radius", "0 um", "E-DOMAIN", P + "bend.bend_radius"),
    ("soi_strip", "geometry.depth", "0 m", "E-DOMAIN", "geometry.depth"),
    # row 6: counts
    ("soi_strip", P + "mode_count", 2.0, "E-DOMAIN", P + "mode_count"),
    ("soi_strip", P + "mode_count", 1.7, "E-DOMAIN", P + "mode_count"),
    ("pml_bent_slab", P + "pml.pml_order", 5, "E-DOMAIN", P + "pml.pml_order"),
    # row 7: gain, and allow_gain refused by name
    ("vector_slab", "materials.film.refractive_index", {"n": 3.48, "k": -0.002}, "E-GAIN",
     "materials.film.refractive_index.k"),
    ("vector_slab", P + "allow_gain", True, "E-CONTRACT", P + "allow_gain"),
    # row 8: a units block, and format 0.2
    ("soi_strip", "units", {"length": "um"}, "E-KEY-UNKNOWN", "units"),
    ("soi_strip", "openphysics", "0.2", "E-FORMAT", "openphysics"),
    # row 9: the format 0.2 keys
    *[("soi_strip", P + old, 1.0, "E-KEY-UNKNOWN", P + old) for old in ("wavelength", "num_modes", "n_target",
                                                                         "n_cladding")],
    ("pml_bent_slab", P + "pml.thickness", {"top": "1 um"}, "E-KEY-UNKNOWN", P + "pml.thickness"),
    ("pml_bent_slab", P + "bend.radius", "2 um", "E-KEY-UNKNOWN", P + "bend.radius"),
    ("pml_bent_slab", P + "bend.origin", "0 um", "E-KEY-UNKNOWN", P + "bend.origin"),
    ("em_gaussian_overlap_scalar", "results.mode_overlap.gaussian.waist", "0.5 um", "E-KEY-UNKNOWN",
     "results.mode_overlap.gaussian.waist"),
    ("em_gaussian_overlap_scalar", "results.mode_overlap.gaussian.center", ["0 um", "0 um"], "E-KEY-UNKNOWN",
     "results.mode_overlap.gaussian.center"),
    ("soi_strip", "mesh.grading.center", ["0 um", "0.11 um"], "E-KEY-UNKNOWN", "mesh.grading.center"),
    *[("vector_slab_sweep", "study.tracking." + old, 1, "E-KEY-UNKNOWN", "study.tracking." + old)
      for old in ("search_modes", "min_overlap", "min_margin", "cluster_span_max", "external_gap_min")],
    ("vector_slab", "materials.film.n", 3.48, "E-KEY-UNKNOWN", "materials.film.n"),
    ("vector_slab", "materials.film.k", 0.0, "E-KEY-UNKNOWN", "materials.film.k"),
    ("vector_slab", "materials.film.sellmeier", {}, "E-KEY-UNKNOWN", "materials.film.sellmeier"),
    ("soi_strip", "mesh.size", 0.25, "E-KEY-UNKNOWN", "mesh.size"),
    ("soi_strip", "mesh.min_angle", 28, "E-KEY-UNKNOWN", "mesh.min_angle"),
    ("soi_strip", "mesh.subdivisions", [6, 6], "E-KEY-UNKNOWN", "mesh.subdivisions"),
    ("soi_strip", "geometry.shapes[0].mesh_size", 0.02, "E-KEY-UNKNOWN", "geometry.shapes[0].mesh_size"),
    ("soi_strip", "mesh.grading.distance", "1 um", "E-KEY-UNKNOWN", "mesh.grading.distance"),
    # row 10: symbols as keys
    *[("soi_strip", P + symbol, 1.0, "E-KEY-UNKNOWN", P + symbol)
      for symbol in ("n_eff", "neff", "k0", "lambda0", "wl", "eps_r", "sigma")],
    # row 11: required, where format 0.2 had defaults
    ("vector_slab", P + "vacuum_wavelength", DELETE, "E-KEY-MISSING", P + "vacuum_wavelength"),
    ("soi_strip", "mesh.element_size", DELETE, "E-KEY-MISSING", "mesh.element_size"),
    ("soi_strip", "geometry.length_unit", DELETE, "E-KEY-MISSING", "geometry.length_unit"),
    ("soi_strip", "geometry.depth", DELETE, "E-KEY-MISSING", "geometry.depth"),
    ("pml_bent_slab", P + "bend.bend_origin", DELETE, "E-KEY-MISSING", P + "bend.bend_origin"),
    ("em_sellmeier_range", "materials.glass.refractive_index.reference_medium", DELETE, "E-KEY-MISSING",
     "materials.glass.refractive_index.reference_medium"),
    ("soi_strip", "geometry.background.material", DELETE, "E-KEY-MISSING", "geometry.background.material"),
    # row 12: two spectral keys
    ("soi_strip", P + "frequency", "193.4 THz", "E-SPECTRAL", P + "frequency"),
    # row 13: library names are exact; a bare name is local only (the shared resolver's code for it)
    ("soi_strip", "geometry.shapes[0].material", "Si", "E-MATERIAL-UNKNOWN", "geometry.shapes[0].material"),
    ("soi_strip", "geometry.shapes[0].material", "physmat:si", "E-LIBRARY-UNKNOWN", "geometry.shapes[0].material"),
    ("soi_strip", "geometry.shapes[0].material", "physmat:air", "E-LIBRARY-UNKNOWN", "geometry.shapes[0].material"),
    ("soi_strip", "geometry.shapes[0].material", "air", "E-MATERIAL-UNKNOWN", "geometry.shapes[0].material"),
    ("soi_strip", "geometry.shapes[0].material", "glass", "E-MATERIAL-UNKNOWN", "geometry.shapes[0].material"),
    ("soi_strip", "geometry.shapes[0].material", "silicon", "E-MATERIAL-UNKNOWN", "geometry.shapes[0].material"),
    # row 14: not implemented in this batch, by name
    ("em_sellmeier_range", "materials.glass.refractive_index.reference_medium", {"air": {}}, "E-CONTRACT",
     "materials.glass.refractive_index.reference_medium"),
    ("em_sellmeier_range", "materials.glass.refractive_index.model", "rii_formula", "E-CONTRACT",
     "materials.glass.refractive_index.model"),
    # row 15: a typo
    ("soi_strip", P + "mode_cont", 2, "E-KEY-UNKNOWN", P + "mode_cont"),
    # row 16: vector sweep values
    ("vector_slab_sweep", "study.values", {"unit": "um", "values": [1.5, 1.6]}, "E-CONTRACT", "study.values"),
    ("vector_slab_sweep", "study.values", {"unit": "nm", "values": [1500, 1600, 1550]}, "E-CONTRACT", "study.values"),
    # row 17: a tagged size is not an expression
    ("soi_strip", "geometry.shapes[0].element_size", "w/10", "E-UNIT-UNKNOWN", "geometry.shapes[0].element_size"),
    ("soi_strip", "mesh.element_size", "w/4", "E-UNIT-UNKNOWN", "mesh.element_size"),
    # row 19: the kept refusals under the new names
    ("pml_bent_slab", P + "target_effective_index", DELETE, "E-KEY-MISSING", P + "target_effective_index"),
    ("vector_slab", P + "bend", {"bend_radius": "5 um", "axis": "y", "bend_origin": "0 um"}, "E-CONTRACT", P + "bend"),
    ("pml_bent_slab", P + "boundary.top", "pmc", "E-CONTRACT", P + "boundary.top"),
    ("pml_bent_slab", P + "pml.pml_thickness", {"top": "3 um", "bottom": "3.1 um"}, "E-CONTRACT",
     P + "pml.pml_thickness"),
    ("vector_slab", P + "effective_index_threshold", DELETE, "E-KEY-MISSING", P + "effective_index_threshold"),
    ("vector_slab", "materials.film.refractive_index", {"n": 3.48, "k": 0.0, "model": "sellmeier"},
     "E-KEY-UNKNOWN", "materials.film.refractive_index.n"),
]


@pytest.mark.parametrize("name,path,value,code,where", A4, ids=[f"{n}:{p}={v!r}"[:90] for n, p, v, *_ in A4])
def test_p2_8_each_refusal_names_its_code_and_path(name, path, value, code, where):
    data = source(name)
    put(data, path, value)
    found = refusal(data)
    assert (code, where) in [(d.code, d.path) for d in found], [(d.code, d.path, d.message) for d in found]


def test_p2_8_refusal_messages_name_the_new_key_the_menu_and_the_fix():
    def first(path, value, name="soi_strip"):
        data = source(name)
        put(data, path, value)
        return refusal(data)[0]
    assert "vacuum_wavelength takes nm um m" in first(P + "vacuum_wavelength", 1.55).message
    assert first(P + "num_modes", 2).message.endswith("write mode_count.")
    assert "write effective_index_threshold" in first(P + "n_cladding", 1.44).message
    assert first(P + "vacuum_wavelength", "1550nm").fix.value == "1550 nm"
    slip = first(P + "vacuum_wavelength", "1550 nM")
    assert slip.fix is None and [s.value for s in slip.suggestions] == ["1550 nm"]
    gain = first("materials.film.refractive_index", {"n": 3.48, "k": -0.002}, "vector_slab")
    assert "exp(-i omega t)" in gain.message and [s.value for s in gain.suggestions] == [0.002]
    assert "physmat:Si" in [s.value for s in first("geometry.shapes[0].material", "Si").suggestions]
    assert "units travel with each value" in first("units", {"length": "um"}).message


def test_p2_8_a_duplicate_key_is_refused():
    from simcase.reader import check
    text = json.dumps(example("vector_slab")).replace('"mode_count": 1', '"mode_count": 1, "mode_count": 2', 1)
    doc, diagnostics = check(text)
    assert doc is None and ("E-KEY-DUPLICATE", "physics.em1") in [(d.code, d.path) for d in diagnostics]
    assert any('"mode_count"' in d.message for d in diagnostics if d.code == "E-KEY-DUPLICATE")


def test_p2_8_a_physics_entry_keeps_its_own_name():
    data = example("vector_slab")
    data["physics"] = {"wg": data["physics"].pop("em1")}
    result = run(Document.from_dict(data), verbose=False)
    assert list(result.doc.si["physics"]) == ["wg"] and result.effective_index.shape == (1, 1)


def test_p2_8_an_axisymmetric_component_and_a_non_side_tag_are_refused_as_before():
    from simcase.geometry_document import from_flat
    data = example("soi_strip")
    data["geometry"] = from_flat(data["geometry"])
    comp = data["geometry"]["components"]["main"]
    tagged = copy.deepcopy(data)
    comp.update(dimension="axisymmetric", domain={"xmin": 0, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2})
    del comp["depth"]
    comp["features"][0]["x"] = 0
    assert [(d.code, d.path) for d in refusal(data)] == [("E-CONTRACT", "geometry.components.main.dimension")]
    tagged["geometry"]["components"]["main"]["boundary_tags"] = [
        {"tag": "port", "select": {"boundary": {"between": ["background", "exterior"]}}}]
    with pytest.raises(DocumentError, match="exterior edges on the four domain sides only"):
        build_mesh(Document.from_dict(tagged))


# ---- C11b: the former kernel contract is the format 0.3 contract ------------------------------------
# Until C11b the micrometre kernel hand-off was checked once more by the format 0.2 em.modes2d validator
# (Document.validate_em_modes2d), which C11b deletes with the hand-off's 0.2 envelope. Each of its
# checks is one row here: the format 0.3 refusal (code and path) of the same defect in a document.
# Two more stay where they were: the PML contract also runs at solve time on the micrometre mesh
# window (physics_pml_modes.solve, test_pml_contract.py) and the tracking settings at run time
# (tracking_settings, test_tracking.py); an axisymmetric component is refused in the test above.
# The contract's tracking check of a vector sweep is kept on purpose on the hand-off itself
# (kernel_document), with the same arguments at the same point as before: redundant with the
# run-time call, it keeps the contract's check and the recorded calls as they were.

KERNEL_CONTRACT = [
    # the envelope: the hand-off format, its units block, no tagged [value, unit] pairs
    ("soi_strip", "openphysics", "0.2", "E-FORMAT", "openphysics"),
    ("soi_strip", "units", {"length": "um"}, "E-KEY-UNKNOWN", "units"),
    ("soi_strip", "geometry.length_unit", DELETE, "E-KEY-MISSING", "geometry.length_unit"),   # PHYSICS_REQUIRES
    ("soi_strip", P + "vacuum_wavelength", [1.55, "um"], "E-VALUE-FORM", P + "vacuum_wavelength"),
    # the domain
    ("soi_strip", "geometry.domain.xmin", DELETE, "E-KEY-MISSING", "geometry.domain.xmin"),
    ("soi_strip", "geometry.domain", {"xmin": 1, "xmax": 1, "ymin": 0, "ymax": 1}, "E-CONTRACT",
     "geometry.domain.xmax"),
    # results.mode_overlap (mode_postprocessing.validate_mode_overlap)
    ("em_gaussian_overlap_scalar", "results.mode_overlap.other", 1, "E-KEY-UNKNOWN", "results.mode_overlap.other"),
    ("em_gaussian_overlap_scalar", "results.mode_overlap.gaussian.extra", 1, "E-KEY-UNKNOWN",
     "results.mode_overlap.gaussian.extra"),
    ("em_gaussian_overlap_scalar", "results.mode_overlap.gaussian.position", DELETE, "E-KEY-MISSING",
     "results.mode_overlap.gaussian.position"),
    ("em_gaussian_overlap_scalar", "results.mode_overlap.gaussian.beam_waist_radius", "0 um", "E-DOMAIN",
     "results.mode_overlap.gaussian.beam_waist_radius"),
    ("em_gaussian_overlap_scalar", "results.mode_overlap.gaussian.position", ["50 um", "0 um"], "E-CONTRACT",
     "results.mode_overlap.gaussian.position"),
    # the shapes and the background
    ("soi_strip", "geometry.shapes[0].type", "ellipse", "E-VALUE-FORM", "geometry.shapes[0].type"),
    ("soi_strip", "geometry.shapes[0].w", DELETE, "E-KEY-MISSING", "geometry.shapes[0].w"),
    ("soi_strip", "geometry.shapes[0].name", DELETE, "E-KEY-MISSING", "geometry.shapes[0].name"),
    ("soi_strip", "geometry.shapes[0].material", DELETE, "E-KEY-MISSING", "geometry.shapes[0].material"),
    ("soi_strip", "geometry.shapes[0].name", "background", "E-ID-CLASH", "geometry.shapes[0].name"),
    ("soi_strip", "geometry.shapes[0].w", 0, "E-DOMAIN", "geometry.shapes[0].w"),
    ("soi_strip", "geometry.shapes[0].h", -1, "E-DOMAIN", "geometry.shapes[0].h"),
    ("soi_strip", "geometry.shapes[0]", {"name": "c", "type": "circle", "cx": 0, "cy": 0, "r": 0,
                                          "material": "physmat:Si"}, "E-DOMAIN", "geometry.shapes[0].r"),
    ("soi_strip", "geometry.shapes[0]", {"name": "p", "type": "polygon", "points": [[0, 0], [1, 0]],
                                          "material": "physmat:Si"}, "E-CONTRACT", "geometry.shapes[0].points"),
    ("soi_strip", "geometry.background.material", DELETE, "E-KEY-MISSING", "geometry.background.material"),
    # the materials (the record values: test_simcase.py::test_invalid_custom_materials_fail_at_document_validation)
    ("soi_strip", "materials", [], "E-VALUE-FORM", "materials"),
    # the physics map and entry
    ("vector_slab", "physics", {"em-1": example("vector_slab")["physics"]["em1"]}, "E-CONTRACT", "physics.em-1"),
    ("vector_slab", "physics.em1", [], "E-VALUE-FORM", "physics.em1"),
    ("vector_slab", P + "type", "em.modes3d", "E-VALUE-FORM", P + "type"),
    ("fiber", P + "formulation", "magic", "E-VALUE-FORM", P + "formulation"),
    ("soi_strip", P + "target_effective_index", 0, "E-DOMAIN", P + "target_effective_index"),
    ("fiber", P + "boundary.left", "pmx", "E-VALUE-FORM", P + "boundary.left"),
    ("vector_slab", P + "vacuum_wavelength", "0 um", "E-DOMAIN", P + "vacuum_wavelength"),
    ("vector_slab", P + "effective_index_threshold", DELETE, "E-KEY-MISSING", P + "effective_index_threshold"),
    ("vector_slab", P + "effective_index_threshold", 0, "E-DOMAIN", P + "effective_index_threshold"),
    ("vector_slab", P + "mode_count", 2.5, "E-DOMAIN", P + "mode_count"),
    ("fiber", P + "mode_count", 0, "E-DOMAIN", P + "mode_count"),
    # PML and bend (pml_contract.validate on the hand-off's physics)
    ("vector_slab", P + "bend", {"bend_radius": "5 um", "axis": "y", "bend_origin": "0 um"}, "E-CONTRACT", P + "bend"),
    ("pml_bent_slab", P + "target_effective_index", DELETE, "E-KEY-MISSING", P + "target_effective_index"),
    ("pml_bent_slab", P + "pml.extra", 1, "E-KEY-UNKNOWN", P + "pml.extra"),
    ("pml_bent_slab", P + "pml.pml_thickness", {}, "E-KEY-MISSING", P + "pml.pml_thickness"),
    ("pml_bent_slab", P + "pml.pml_thickness.top", "-1 um", "E-DOMAIN", P + "pml.pml_thickness.top"),
    ("pml_bent_slab", P + "boundary.top", "pmc", "E-CONTRACT", P + "boundary.top"),
    ("pml_bent_slab", P + "pml.pml_thickness", {"top": "3 um", "bottom": "3.1 um"}, "E-CONTRACT",
     P + "pml.pml_thickness"),
    ("pml_bent_slab", P + "pml.pml_strength", 0, "E-DOMAIN", P + "pml.pml_strength"),
    ("pml_bent_slab", P + "pml.pml_order", 5, "E-DOMAIN", P + "pml.pml_order"),
    ("pml_bent_slab", P + "pml.pml_minimum_physical_fraction", 2, "E-DOMAIN", P + "pml.pml_minimum_physical_fraction"),
    ("pml_bent_slab", P + "bend.axis", "z", "E-VALUE-FORM", P + "bend.axis"),
    ("pml_bent_slab", P + "bend.bend_radius", "-1 um", "E-DOMAIN", P + "bend.bend_radius"),
    ("pml_bent_slab", P + "bend.bend_radius", "0.1 um", "E-CONTRACT", P + "bend.bend_radius"),
    # the mesh
    ("soi_strip", "mesh.element_size", "0 um", "E-DOMAIN", "mesh.element_size"),
    ("soi_strip", "mesh.grading.near", DELETE, "E-KEY-MISSING", "mesh.grading.near"),
    # the study
    ("soi_strip", "study", {"type": "transient"}, "E-CONTRACT", "study.type"),
    ("soi_strip", "study", {"type": "sweep", "values": ["1.5 um"]}, "E-KEY-MISSING", "study.parameter"),
    ("soi_strip", "study", {"type": "sweep", "parameter": P + "vacuum_wavelength"}, "E-KEY-MISSING",
     "study.parameter"),
    ("soi_strip", "study", {"type": "sweep", "parameter": P + "nope", "values": [1]}, "E-CONTRACT",
     "study.parameter"),
    ("soi_strip", "study", {"type": "sweep", "parameter": "geometry.shapes[0].w", "values": [1]}, "E-CONTRACT",
     "study.parameter"),
    ("pml_bent_slab", "study", {"type": "sweep", "parameter": P + "target_effective_index", "values": [1.5, 1.6]},
     "E-CONTRACT", "study.parameter"),
    ("vector_slab", "study", {"type": "sweep", "parameter": P + "effective_index_threshold",
                              "values": [1.4, 1.41, 1.42]}, "E-CONTRACT", "study.parameter"),
    ("vector_slab", "study", {"type": "sweep", "parameter": P + "vacuum_wavelength",
                              "values": {"unit": "um", "values": [1.5, 1.6]}}, "E-CONTRACT", "study.values"),
    ("vector_slab", "study", {"type": "sweep", "parameter": P + "vacuum_wavelength",
                              "values": {"unit": "um", "values": [1.5, -1, 1.6]}}, "E-DOMAIN", "study.values.values[1]"),
    ("vector_slab", "study", {"type": "sweep", "parameter": P + "vacuum_wavelength",
                              "values": {"unit": "um", "values": [1.5, 1.6, 1.6]}}, "E-CONTRACT", "study.values"),
    ("vector_slab_sweep", "study.tracking", {"search_mode_count": 0}, "E-DOMAIN", "study.tracking.search_mode_count"),
    ("fiber", "study", {"type": "sweep", "parameter": P + "vacuum_wavelength",
                        "values": {"unit": "um", "values": [1.5, 1.55, 1.6]}, "tracking": {"search_mode_count": 4}},
     "E-CONTRACT", "study.tracking"),
    ("fiber", "study", {"type": "sweep", "parameter": P + "formulation", "values": ["scalar", "vector"]},
     "E-CONTRACT", "study.values"),
]


@pytest.mark.parametrize("name,path,value,code,where", KERNEL_CONTRACT,
                         ids=[f"{n}:{p}={v!r}"[:90] for n, p, v, *_ in KERNEL_CONTRACT])
def test_c11b_each_former_kernel_contract_check_is_a_format_0_3_refusal(name, path, value, code, where):
    data = source(name)
    put(data, path, value)
    found = refusal(data)
    assert (code, where) in [(d.code, d.path) for d in found], [(d.code, d.path, d.message) for d in found]


def test_c11b_the_former_implausible_wavelength_note_is_a_magnitude_warning():
    """The kernel contract noted an implausible wavelength; format 0.3 warns with W-MAGNITUDE."""
    for text in ("1e-12 m", "1 m"):
        data = example("fiber")
        put(data, P + "vacuum_wavelength", text)
        doc = Document.from_dict(data)
        assert ("W-MAGNITUDE", P + "vacuum_wavelength") in [(d.code, d.path) for d in doc.diagnostics]


# ---- P2-9: diagnostics reach every output ----------------------------------------------------------

def test_p2_9_em_diagnostics_reach_validate_the_log_the_summary_and_the_metadata(tmp_path, capsys):
    from simcase.cli import main
    from simcase.modes_document import kernel_document
    data = example("vector_slab")
    data["geometry"]["shapes"][0]["h"] = 0.2200003               # off the 1 pm grid by 0.3 pm (G4 A5)
    expected = [("W-PM-ROUNDING", "geometry.shapes[0].h")]
    doc = Document.from_dict(copy.deepcopy(data))
    assert [(d.code, d.path) for d in doc.diagnostics] == expected
    count = len(doc.diagnostics)
    doc.validate()
    kernel_document(doc)
    build_mesh(doc)
    assert len(doc.diagnostics) == count                        # the count never drops, nor doubles
    model = tmp_path / "model.json"
    model.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate", str(model)]) == 0
    assert "W-PM-ROUNDING at geometry.shapes[0].h" in capsys.readouterr().out
    assert main(["run", str(model), "-o", str(tmp_path / "out")]) == 0
    printed = capsys.readouterr().out
    log = (tmp_path / "out" / "log.txt").read_text(encoding="utf-8")
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    with np.load(tmp_path / "out" / "fields.npz", allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata_json"]))
    assert "W-PM-ROUNDING at geometry.shapes[0].h" in printed and "W-PM-ROUNDING at geometry.shapes[0].h" in log
    assert [(d["code"], d["path"]) for d in summary["diagnostics"]] == expected
    assert metadata["diagnostics"] == summary["diagnostics"]


def test_p2_9_defaults_are_echoed_with_their_reasons(tmp_path):
    _, _, summary, _, _ = saved(example("vector_slab_sweep"), tmp_path / "out")
    defaults = {d["path"]: d for d in summary["defaults_applied"]}
    assert defaults["study.tracking.search_mode_count"]["value"] == 5            # max(2 x 1, 1 + 4)
    assert "count default" in defaults["study.tracking.search_mode_count"]["reason"]
    assert {"study.tracking.mode_tracking_threshold", "study.tracking.mode_tracking_margin_threshold",
            "study.tracking.degeneracy_tolerance"} <= set(defaults)
    sellmeier = Document.from_dict(fixture("em_sellmeier_range"))
    assert ("materials.glass.refractive_index.constant", 1) in [(d["path"], d["value"])
                                                               for d in sellmeier.defaults_applied]


# ---- P2-11: result names and units ------------------------------------------------------------------

UNIT_TOKEN = re.compile(r"_(k|m|s|w|j|um|nm|hz|v|a|deg|m2|db_cm|db_90deg|per_m)$")
#: arrays without a registry quantity (connectivity, region ids, text and JSON blocks)
STRUCTURAL = {"triangles", "regions", "region_names", "edges", "field_layout", "study_parameter",
              "field_representation", "mode_tracking_json", "open_boundary_json", "frame_transform",
              "cluster_ids", "cluster_offsets"}
#: the closed structural vocabulary of the mode tracker and the PML diagnostics (spec 5.3.4)
SERIES = ("vacuum_wavelength", "effective_index", "group_index", "propagation_loss", "bend_loss",
          "mean_effective_index", "mean_group_index")
NAMES = ["vector_slab", "soi_strip", "pml_bent_slab", "vector_fiber_subspace_sweep", "em_lossy_scalar_tracked_sweep",
         "em_gaussian_overlap_vector", "em_gaussian_overlap_scalar", "em_pml_scalar"]


def keys(tree):
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield key
            if key not in ("resolved_inputs", "regions"):
                yield from keys(value)
    elif isinstance(tree, list):
        for item in tree:
            yield from keys(item)


@pytest.mark.parametrize("name", NAMES)
def test_p2_11_em_result_names_and_units(tmp_path, name):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    _, _, summary, arrays, metadata = saved(source(name), tmp_path / "out")
    names = list(keys(summary)) + list(arrays)
    assert not [k for k in names if UNIT_TOKEN.search(k)]
    assert not [k for k in names if k.endswith("_unit") or k in ("neff", "neff_imag", "amplitude_unit", "phasor")]
    assert not set(arrays) & {"nodes", "values", "fields", "neff", "vector_electric", "mode_power", "confinement"}
    assert "units" not in summary and "mesh_length_unit" not in summary and "length_unit_to_m" not in arrays
    assert set(summary["field_shapes"]) <= set(arrays) | {"study_values"}
    for array in arrays:
        if array in STRUCTURAL:
            assert array not in summary["field_units"], array
            continue
        quantity = units.quantity(FIELDS[array][0])                # the registry quantity the array is
        assert summary["field_units"][array] == quantity.unit, array
    for key in SERIES:
        if key in summary:
            assert summary[key]["unit"] == units.quantity(key).unit, key
            assert "result" in units.quantity(key).places, key
            if "re" in summary[key]:
                assert summary[key]["time_convention"] == TC
    layout = summary["field_layout"]
    assert layout.endswith("-v2") and layout not in RETIRED_LAYOUTS
    assert layout in SUPPORTED_LAYOUTS or layout == "em-modes2d-subspace-raw-v2"
    assert metadata["field_units"] == summary["field_units"]
    for region, material in summary["mesh"]["regions"].items():
        assert material.startswith("physmat:") or material in source(name).get("materials", {}), region


# ---- P2-15: one convention at simcase's surface ------------------------------------------------------

def test_p2_15_passive_results_carry_loss_as_a_positive_imaginary_index(tmp_path):
    result, _, summary, arrays, _ = saved(fixture("em_lossy_film_vector"), tmp_path / "out")
    assert np.all(arrays["effective_index"].imag > 0)
    assert summary["time_convention"] == TC and summary["propagation"] == "exp(+i beta z)"
    assert np.all(np.asarray(summary["effective_index"]["im"]) > 0)
    assert summary["propagation_loss"]["unit"] == "dB/m" and np.all(np.asarray(summary["propagation_loss"]["values"]) > 0)
    pml, _, pml_summary, _, _ = saved(example("pml_bent_slab"), tmp_path / "pml")
    assert np.all(pml.effective_index.imag > 0) and np.all(np.asarray(pml_summary["bend_loss"]["values"]) > 0)
    for candidate in pml_summary["open_boundary"][0]["candidates"]:
        assert candidate["effective_index"]["time_convention"] == TC
        assert "positive_imaginary_index" not in candidate["reasons"]


#: kernel-frame modules: they take Hermitian inner products on kernel fields (micrometres,
#: exp(+i omega t)) and never see a public result, so their conjugations are not conventions
KERNEL_FRAME = {
    "physics_em_modes2d.py": "the mode kernel: eigen-solve, sign and power normalization of kernel fields",
    "physics_pml_modes.py": "the PML kernel: physical/PML L2 fractions <E, M E> of kernel candidates",
    "tracking.py": "mode tracking: overlaps <E_a, M E_b> between kernel fields of adjacent points",
    "subspace_tracking.py": "subspace tracking: Gram matrices, principal angles and frame rotations of kernel fields",
    "mode_postprocessing.py": "post-processing: <E_a, E_b>, mode power and confinement on kernel fields (spec 3.8)",
}
#: the boundary functions of each module that hands complex values to a kernel (and the helpers only
#: they call), the one place a complex value changes convention. runner.py (em.modes2d): _to_kernel
#: (eps in), _to_public (results out), _public_open_boundary and _public_candidate (PML diagnostics,
#: from _to_public), and _shown (the log text of a kernel index under exp(-i omega t)). cavity.py
#: (em.cavity3d, units batch C9): _to_kernel (eps and mu in, as 0.0 - Im) and _to_public (the saved
#: arrays out; the result properties read them through it).
BOUNDARY = {"runner.py": {"_to_kernel", "_to_public", "_public_open_boundary", "_public_candidate", "_shown"},
            "cavity.py": {"_to_kernel", "_to_public"}}
CONJUGATION = re.compile(r"np\.conj(?:ugate)?\(|\.conj\(\)|0\.0 - [\w\[\]\"'.]*imag|-\s*\w+\.imag\b")


def _functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_p2_15_only_the_boundary_functions_conjugate_on_the_simcase_surface():
    """Interpretation (stated in the commit): P2-15's grep covers the simcase surface. The modules
    of KERNEL_FRAME run in the kernel frame and are exempt by name; on every other module a
    conjugation or a sign flip of an imaginary part occurs only inside BOUNDARY."""
    found = []
    for path in sorted(SIMCASE.rglob("*.py")):
        if path.name in KERNEL_FRAME:
            continue
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        spans = [(f.lineno, f.end_lineno, f.name) for f in _functions(tree)]
        for number, line in enumerate(text.splitlines(), start=1):
            code = line.split("#", 1)[0]
            if not CONJUGATION.search(code) or code.strip().startswith(('"', "'")):
                continue
            owners = [name for start, end, name in spans if start <= number <= end]
            if not owners or not set(owners) & BOUNDARY.get(path.name, set()):
                found.append(f"{path.relative_to(SIMCASE)}:{number}: {line.strip()}")
    assert not found, "conjugation outside the boundary functions:\n" + "\n".join(found)
    cavity = ast.parse((SIMCASE / "cavity.py").read_text(encoding="utf-8"))
    used = {}
    for f in _functions(cavity):
        for node in ast.walk(f):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                used.setdefault(node.func.id, set()).add(f.name)
    assert used["_to_kernel"] == {"kernel_inputs"}
    assert used["_to_public"] <= {"arrays", "resonant_frequency", "wavenumber_squared", "mass_normalized_electric_field",
                                  "mass_normalized_electric_field_line_integral"}
    runner = ast.parse((SIMCASE / "runner.py").read_text(encoding="utf-8"))
    callers = {}
    for f in _functions(runner):
        for node in ast.walk(f):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                callers.setdefault(node.func.id, set()).add(f.name)
    assert callers["_public_candidate"] == {"_public_open_boundary"}
    assert callers["_public_open_boundary"] == {"_to_public"}


@pytest.mark.parametrize("module", sorted(KERNEL_FRAME))
def test_p2_15_kernel_frame_modules_never_import_or_return_public_results(module):
    tree = ast.parse((SIMCASE / module).read_text(encoding="utf-8"))
    public = {"RunResult", "SubspaceSweepResult", "run", "solve_point", "_to_public", "summary_block_public"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[-1] not in ("runner", "subspace_result"), (module, node.module)
            assert not {a.name for a in node.names} & public, (module, [a.name for a in node.names])
        if isinstance(node, ast.Import):
            assert not [a.name for a in node.names if a.name.endswith((".runner", ".subspace_result"))], module
        if isinstance(node, ast.Name):
            assert node.id not in ("RunResult", "SubspaceSweepResult"), (module, node.id)
    assert KERNEL_FRAME[module]                                   # each exemption states its reason


# ---- P2-16: library names --------------------------------------------------------------------------

def _material_refs(tree):
    if isinstance(tree, dict):
        for key, value in tree.items():
            if key == "material" and isinstance(value, str):
                yield value
            else:
                yield from _material_refs(value)
    elif isinstance(tree, list):
        for item in tree:
            yield from _material_refs(item)


def _documents():
    docs = {f"builtin:{k}": v for k, v in examples.EXAMPLES.items()
            if all(p.get("type") == "em.modes2d" for p in v["physics"].values())}
    for path in sorted(EXAMPLE_FILES.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        if all(p.get("type") == "em.modes2d" for p in d.get("physics", {}).values()):
            docs[path.name] = d
    for path in sorted(FIXTURES.glob("em_*.json")):
        docs["fixture:" + path.name] = json.loads(path.read_text(encoding="utf-8"))
    text = (SIMCASE / "studio" / "static" / "geometry-lab-starters.mjs").read_text(encoding="utf-8")
    body = text[text.index("export const STARTERS={") + len("export const STARTERS="):text.rindex("};") + 1]
    for name, d in json.loads(re.sub(r"^\s*(\w+):", r'"\1":', body.replace(",\n}", "\n}"), flags=re.M)).items():
        docs["starter:" + name] = d
    return docs


def test_p2_16_every_em_document_names_materials_locally_or_exactly_from_the_library():
    library = set(physmat.names())
    docs = _documents()
    assert len(docs) >= 13 + 16 + 2
    for name, d in docs.items():
        local = set(d.get("materials", {}))
        for ref in _material_refs(d):
            if ref.startswith("physmat:"):
                assert ref.removeprefix("physmat:") in library, (name, ref)
            else:
                assert ref in local, (name, ref)
        Document.from_dict(copy.deepcopy(d))                           # and each one reads


# ---- the defining formulas of the derived results, bitwise ---------------------------------------

def test_propagation_and_bend_loss_follow_their_definitions_bitwise(tmp_path):
    result, _, summary, arrays, _ = saved(example("pml_bent_slab"), tmp_path / "out")
    factor = 40 * np.pi / np.log(10)                      # dB of exp(-2 Im(n_eff) k0 z) per Im(n_eff) / lambda0
    loss = factor * arrays["effective_index"].imag / arrays["vacuum_wavelength"][:, None]
    assert np.asarray(summary["propagation_loss"]["values"]).tobytes() == loss.tobytes()
    radius = result.doc.si["physics"]["em1"]["bend"]["bend_radius"]
    assert radius == 2e-6
    bend = loss * (np.pi * radius / 2)                    # dB per 90 degrees of the reference radius
    assert np.asarray(summary["bend_loss"]["values"]).tobytes() == bend.tobytes()


def test_group_indices_follow_their_definitions_in_the_kernel_frame_bitwise(tmp_path):
    from simcase.modes_document import kernel_document
    _, _, summary, arrays, _ = saved(example("vector_slab_sweep"), tmp_path / "sweep")
    wl = np.asarray(kernel_document(Document.from_dict(example("vector_slab_sweep")))["study"]["values"])
    n = np.conj(arrays["effective_index"])                                # back in the kernel frame, exactly
    ng = np.conj(n - wl[:, None] * np.gradient(n, wl, axis=0, edge_order=2))       # n_g = n - lambda dn/dlambda
    assert arrays["group_index"].tobytes() == ng.tobytes()
    _, _, summary, arrays, _ = saved(example("vector_fiber_subspace_sweep"), tmp_path / "subspace")
    wl = np.asarray(kernel_document(Document.from_dict(example("vector_fiber_subspace_sweep")))["study"]["values"])
    n, offsets = arrays["effective_index"], arrays["cluster_offsets"]
    mean = np.stack([n[:, offsets[c]:offsets[c + 1]].mean(axis=1) for c in range(len(offsets) - 1)], axis=1)
    assert arrays["mean_effective_index"].tobytes() == mean.tobytes()
    mean_ng = mean - wl[:, None] * np.gradient(mean, wl, axis=0, edge_order=2)
    assert arrays["mean_group_index"].tobytes() == mean_ng.tobytes()
    assert summary["mean_group_index"]["values"] == mean_ng.tolist()
