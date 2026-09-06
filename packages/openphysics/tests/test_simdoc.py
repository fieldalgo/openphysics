# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import copy
import json

import numpy as np
import pytest
from fractions import Fraction

import physmat
from refsol import benchmarks, fiber, slab
from simdoc import Document, DocumentError, build_mesh, examples, run, solve_point
from simdoc import units
from simdoc.geometry import resolve_regions


# ---- document handling ---------------------------------------------------------

def test_examples_validate_and_roundtrip(tmp_path):
    for name, d in examples.EXAMPLES.items():
        doc = Document.from_dict(d)
        doc.save(tmp_path / f"{name}.json")
        again = Document.load(tmp_path / f"{name}.json")
        assert again.data == doc.data
        assert doc.summary()


# ---- units -----------------------------------------------------------------------

SYSTEMS = [("mm-t-s", {"length": "mm", "mass": "t", "time": "s"}),
           ("nm-kg-fs", {"length": "nm", "mass": "kg", "time": "fs"})]


@pytest.mark.parametrize("label,block", SYSTEMS)
@pytest.mark.parametrize("dim,value_si", [
    ({"length": -1, "mass": 1, "time": -2}, 2e11),      # Young's modulus, Pa
    ({"length": -3, "mass": 1}, 7850.0),                # density
    ({"length": 1, "time": -2}, 9.80665),               # g
])
def test_conversion_round_trips_at_two_systems(label, block, dim, value_si):
    """One system is not enough; see the vacuity test below for why."""
    scale = units.resolve(block)
    factor = scale.factor(dim)
    assert factor != 1.0, f"VACUOUS at {label}: factor is 1.0, so an inverted conversion is invisible"
    doc_value = scale.from_si(value_si, dim)
    assert doc_value == pytest.approx(value_si / factor)
    assert scale.to_si(doc_value, dim) == pytest.approx(value_si)


def test_the_thermal_conductivity_trap_is_real_and_is_why_two_systems_are_tested():
    """W/(m K) is L+1 M+1 T-3 Th-1, so mm and tonne cancel exactly.

    A test of this quantity written only at (mm, t, s) passes with the conversion
    inverted. It is the canonical sign-flip case, and it is invisible there.
    """
    conductivity = {"length": 1, "mass": 1, "time": -3, "temperature": -1}
    assert units.resolve({"length": "mm", "mass": "t", "time": "s"}).factor(conductivity) == 1.0
    other = units.resolve({"length": "nm", "mass": "kg", "time": "fs"})
    assert other.factor(conductivity) != 1.0
    assert other.to_si(other.from_si(50.0, conductivity), conductivity) == pytest.approx(50.0)


def test_the_published_structural_table_falls_out_of_the_rule():
    """mm-tonne-second, derived rather than looked up."""
    s = units.resolve({"length": "mm", "mass": "t", "time": "s"})
    assert s.from_si(2e11, {"length": -1, "mass": 1, "time": -2}) == pytest.approx(2.0e5)
    assert s.from_si(7850.0, {"length": -3, "mass": 1}) == pytest.approx(7.85e-9)
    assert s.from_si(9.80665, {"length": 1, "time": -2}) == pytest.approx(9806.65)


@pytest.mark.parametrize("text,length_exponent", [
    ("Pa", -1), ("N", 1), ("N/m", 0), ("N*m", 2), ("W/(m K)", 1), ("J/(kg K)", 2),
    ("S/m", -3), ("F/m", -3), ("1/K", 0), ("-", 0),
])
def test_unit_strings_carry_full_dimension_vectors(text, length_exponent):
    """A watt hides an m^2, so counting 'm' tokens gets W/(m K) backwards."""
    dim, _ = units.parse_unit_string(text)
    assert dim.get("length", 0) == length_exponent


def test_unit_strings_are_case_sensitive_and_fractional_exponents_parse():
    assert units.parse_unit_string("S")[0] != units.parse_unit_string("s")[0]   # siemens vs second
    assert units.parse_unit_string("T")[0] != units.parse_unit_string("t")[0]   # tesla vs tonne
    dim, factor = units.parse_unit_string("MPa*m^1/2")                          # fracture toughness
    assert dim["length"] == Fraction(-1, 2) and factor == pytest.approx(1e6)


@pytest.mark.parametrize("bad", ["furlong", "min", "Pa/", "m/(s", "m^"])
def test_unknown_or_malformed_unit_strings_are_errors(bad):
    with pytest.raises(units.UnitError):
        units.parse_unit_string(bad)


def test_a_document_cannot_get_its_units_by_forgetting():
    d = copy.deepcopy(examples.SOI_STRIP)
    del d["units"]
    with pytest.raises(DocumentError, match="units is missing"):
        Document.from_dict(d)


@pytest.mark.parametrize("block,msg", [
    ({"lenght": "um"}, "unknown key"),
    ({"length": "furlong"}, "unknown unit"),
    ({"length": "kg"}, "unit of mass"),
    ({"temperature": "C"}, "unknown unit"),
    ({"length": {"in_s": 1e-6}}, "escape hatch"),
    ({"length": {"in_m": 0}}, "finite and positive"),
])
def test_unit_declarations_that_must_be_refused(block, msg):
    d = dict(copy.deepcopy(examples.SOI_STRIP), units=block)
    with pytest.raises(DocumentError, match=msg):
        Document.from_dict(d)


def test_the_escape_hatch_is_a_unit_like_any_other():
    d = dict(copy.deepcopy(examples.SOI_STRIP), units={"length": {"in_m": 1e-10}})   # angstrom
    assert Document.from_dict(d).scale.size("length") == 1e-10


def test_tagged_quantities_are_reserved():
    d = copy.deepcopy(examples.SOI_STRIP)
    d["mesh"]["size"] = [0.25, "um"]
    with pytest.raises(DocumentError, match="reserved"):
        Document.from_dict(d)


def _rescaled(doc_dict, symbol, ratio):
    """The same waveguide written in a different length unit."""
    d = copy.deepcopy(doc_dict)
    d["units"] = {"length": symbol}
    g = d["geometry"]
    g["domain"] = {k: v * ratio for k, v in g["domain"].items()}
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h", "cx", "cy", "r", "mesh_size"):
            if k in s:
                s[k] *= ratio
    d["mesh"]["size"] *= ratio
    if d["mesh"].get("grading"):
        gr = d["mesh"]["grading"]
        gr["center"] = [c * ratio for c in gr["center"]]
        for k in ("near", "far", "distance"):
            gr[k] *= ratio
    for p in d["physics"].values():
        p["wavelength"] *= ratio
    d["study"] = {"type": "single"}
    return d


def test_the_answer_does_not_depend_on_the_declared_unit():
    """The invariant is the dimensionless answer, not the mesh: connectivity may differ."""
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    base["study"] = {"type": "single"}
    in_um = run(Document.from_dict(base), verbose=False)
    in_nm = run(Document.from_dict(_rescaled(base, "nm", 1000.0)), verbose=False)
    # Meshing at a different scale rounds differently, so the two runs discretize
    # slightly differently; the residual is that, not the unit change.
    assert len(in_nm.mesh_triangles) == pytest.approx(len(in_um.mesh_triangles), rel=0.05)
    assert in_nm.neff[0, 0] == pytest.approx(in_um.neff[0, 0], rel=1e-4)


def test_a_scale_error_is_reported_without_making_the_document_invalid():
    """The one thing no dimension checker anywhere can catch: right dimension, wrong size."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["units"] = {"length": "m"}                       # micrometre numbers, declared as metres
    doc = Document.from_dict(d)                        # still a valid document
    assert any("wavelength" in n and "1.55" in n for n in doc.notes)
    assert Document.from_dict(copy.deepcopy(examples.SLAB_TE_CHECK)).notes == []


def test_a_region_is_a_sliver_relative_to_the_domain_not_absolutely():
    """A 220 nm film is 0.22 in micrometres and 2.2e-13 in metres; both are the same film."""
    from simdoc.geometry import resolve_regions
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    for symbol, ratio in (("um", 1.0), ("m", 1e-6)):
        d = _rescaled(base, symbol, ratio)
        names = [n for n, _m, _g, _s, _e in resolve_regions(Document.from_dict(d))]
        assert names == ["film", "background"], f"{symbol}: regions dropped -> {names}"


def test_a_named_shape_does_not_vanish_without_a_word():
    """A sliver is reported; a shape a later shape covered is not. Only one of them is a mistake."""
    from simdoc.geometry import resolve_regions
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    face = copy.deepcopy(base["geometry"]["shapes"][0])

    sliver = copy.deepcopy(base)
    sliver["geometry"]["shapes"] = [dict(face, name="dopant", w=1e-7, h=1e-7), dict(face, name="film")]
    doc = Document.from_dict(sliver)
    assert "dopant" not in [n for n, *_ in resolve_regions(doc)]
    assert any("dopant" in n for n in doc.notes), "a named region left the model in silence"

    occluded = copy.deepcopy(base)
    occluded["geometry"]["shapes"] = [dict(face, name="buried"), dict(face, name="cover")]
    doc = Document.from_dict(occluded)
    assert [n for n, *_ in resolve_regions(doc)] == ["cover", "background"]
    assert doc.notes == [], "being covered by a later shape is what the booleans are for"


def test_an_empty_mesh_is_refused_where_it_is_made():
    """An empty collection is a valid data structure and never a valid intermediate result."""
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    d = _rescaled(base, "m", 1e-6)                 # meshine's absolute tolerances still empty this
    with pytest.raises(DocumentError, match="0 nodes and 0 triangles"):
        build_mesh(Document.from_dict(d))


def test_a_micrometre_document_still_reaches_physmat_unchanged():
    """The optical boundary factor is exactly 1.0 for um, so nothing moves."""
    doc = Document.from_dict(copy.deepcopy(examples.SOI_STRIP))
    assert units.to_micrometres(1.55, doc.scale) == 1.55


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
