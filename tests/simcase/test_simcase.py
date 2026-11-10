# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import copy
from decimal import Decimal
import json
import re

import numpy as np
import pytest
from fractions import Fraction

import physmat
from meshine import TriMesh
from refsol import benchmarks, fiber, slab
from simcase import Document, DocumentError, build_mesh, examples, run, solve_point
from simcase import units
from simcase.geometry import resolve_regions
from simcase.runner import RunResult


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
    """Format 0.3 (every kind since the cavity moved): the lengths need geometry.length_unit, and
    a format 0.2 units block is an unknown key, not a way to declare them."""
    d = copy.deepcopy(examples.CAVITY_BOX)
    del d["geometry"]["length_unit"]
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [
        ("E-KEY-MISSING", "geometry.length_unit")]
    d["units"] = {"length": "m"}
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert ("E-KEY-UNKNOWN", "units") in [(e.code, e.path) for e in caught.value.diagnostics]


# The format 0.2 unit declaration has no document reader left (C9 moved the last kind); the kernel
# hand-offs still build their 0.2-shaped trees through units.resolve until C11, so it is tested here.
@pytest.mark.parametrize("block,msg", [
    ({"lenght": "um"}, "unknown key"),
    ({"length": "furlong"}, "unknown unit"),
    ({"length": "kg"}, "unit of mass"),
    ({"temperature": "C"}, "unknown unit"),
    ({"length": {"in_s": 1e-6}}, "escape hatch"),
    ({"length": {"in_m": 0}}, "finite and positive"),
])
def test_unit_declarations_that_must_be_refused(block, msg):
    with pytest.raises(units.UnitError, match=msg):
        units.resolve(block)


def test_the_escape_hatch_is_a_unit_like_any_other():
    assert units.resolve({"length": {"in_m": 1e-10}}).size("length") == 1e-10   # angstrom


def test_tagged_quantities_are_reserved():
    """Format 0.2 refused [value, unit] pairs (reserved); format 0.3 writes "250 MHz" and refuses a pair
    by its value form."""
    from simcase.schema import reject_tagged_values
    with pytest.raises(DocumentError, match="reserved"):
        reject_tagged_values({"mesh": {"size": [0.25, "um"]}})
    d = copy.deepcopy(examples.CAVITY_BOX)
    d["physics"]["em1"]["target_frequency"] = [250, "MHz"]
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [
        ("E-VALUE-FORM", "physics.em1.target_frequency")]


def test_a_format_0_3_mode_document_takes_no_unit_declaration():
    d = dict(copy.deepcopy(examples.SLAB_TE_CHECK), units={"length": "um"})
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [
        ("E-KEY-UNKNOWN", "units")]


#: the wavelength menu (nm, um, m): a tagged wavelength in another unit is refused (E-UNIT-NOT-ACCEPTED)
WAVELENGTH_MENU = ("nm", "um", "m")


def _exact(value, factor_text):
    return float(Decimal(repr(float(value))) * Decimal(factor_text))


def _written_in(data, symbol, factor_text):
    """The same document typed in ``symbol``: the shape numbers in ``length_unit`` and every tagged
    length as exact decimals. Wavelengths stay in micrometres when ``symbol`` is not on their menu."""
    d = copy.deepcopy(data)
    g = d["geometry"]
    g["length_unit"] = symbol
    g["domain"] = {k: _exact(v, factor_text) for k, v in g["domain"].items()}
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h", "cx", "cy", "r"):
            if k in s:
                s[k] = _exact(s[k], factor_text)
        if "points" in s:
            s["points"] = [[_exact(c, factor_text) for c in p] for p in s["points"]]
    menu = symbol in WAVELENGTH_MENU

    def retag(node, key=None):
        if isinstance(node, dict):
            if node.get("unit") == "um" and isinstance(node.get("values"), list):     # a wavelength list
                return {"unit": symbol, "values": [_exact(v, factor_text) for v in node["values"]]} if menu \
                    else node
            return {k: retag(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [retag(v, key) for v in node]
        found = TAGGED.fullmatch(node) if isinstance(node, str) else None
        if found is None or (key == "vacuum_wavelength" and not menu):
            return node
        power = 2 if found.group(2) else 1
        return f"{Decimal(found.group(1)) * Decimal(factor_text) ** power} {symbol}{found.group(2) or ''}"
    return retag(d)


TAGGED = re.compile(r"(-?[0-9][0-9.eE+-]*) um(\^2)?")

#: The same device written five ways; the number is document units per micrometre.
#: Micrometres alone proves nothing here — it is the scale at which the absolute
#: tolerances in the mesher happened to work. Metres used to come back empty (kilometres,
#: which used to raise, are not on the length_unit menu of format 0.3).
LENGTH_SCALES = [("um", "1"), ("nm", "1000"), ("mm", "0.001"), ("m", "1e-6"), ("pm", "1e6")]


@pytest.mark.parametrize("symbol,factor_text", LENGTH_SCALES[1:])
def test_the_answer_does_not_depend_on_the_declared_unit(symbol, factor_text):
    """P2-5: the kernel meshes and solves in micrometres from each length's exact value, so the
    same device typed in any length unit gives bitwise the same mesh and answer."""
    assert factor_text != "1", f"VACUOUS at {symbol}: the scale ratio is 1, so nothing was rescaled"
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    in_um = run(Document.from_dict(base), verbose=False)
    other = run(Document.from_dict(_written_in(base, symbol, factor_text)), verbose=False)
    for name in ("node_coordinates", "triangles", "regions", "vacuum_wavelength", "effective_index"):
        a, b = getattr(other, name), getattr(in_um, name)
        assert a.dtype == b.dtype and a.tobytes() == b.tobytes(), name


def test_a_scale_error_is_reported_and_a_large_one_refused_before_meshing():
    """The one thing no dimension checker anywhere can catch: right dimension, wrong size. Tagged
    sizes keep their unit, so micrometre shape numbers declared as nm are a warned, valid document
    and declared as metres an estimate far over the mesh limit."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["geometry"]["length_unit"] = "nm"
    doc = Document.from_dict(d)
    assert [(x.code, x.path) for x in doc.diagnostics] == [("W-GEOMETRY-SCALE", "geometry")]
    assert "check length_unit" in doc.diagnostics[0].message
    d["geometry"]["length_unit"] = "m"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(x.code, x.path) for x in caught.value.diagnostics if x.severity == "error"] == [
        ("E-MESH-ESTIMATE", "geometry")]
    assert list(Document.from_dict(copy.deepcopy(examples.SLAB_TE_CHECK)).diagnostics) == []


def test_a_region_is_a_sliver_relative_to_the_domain_not_absolutely():
    """A 220 nm film is 0.22 in micrometres and 2.2e-7 in metres; both are the same film."""
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    for symbol, factor_text in (("um", "1"), ("m", "1e-6")):
        model = build_mesh(Document.from_dict(_written_in(base, symbol, factor_text)))
        assert model.tri.region_names == ["film", "background"], f"{symbol}: regions dropped"


def test_a_named_shape_does_not_vanish_without_a_word():
    """A sliver is reported; a shape a later shape covered is not. Only one of them is a mistake.
    The sliver is 1 pm square, the smallest length the grid holds."""
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    face = copy.deepcopy(base["geometry"]["shapes"][0])

    sliver = copy.deepcopy(base)
    sliver["geometry"]["shapes"] = [dict(face, name="dopant", w=1e-6, h=1e-6), dict(face, name="film")]
    doc = Document.from_dict(sliver)
    assert "dopant" not in build_mesh(doc).tri.region_names
    dropped = [x for x in doc.diagnostics if x.code == "W-SHAPE-DROPPED"]
    assert [x.path for x in dropped] == ["geometry.shapes"] and "'dopant'" in dropped[0].message, \
        "a named region left the model in silence"

    occluded = copy.deepcopy(base)
    occluded["geometry"]["shapes"] = [dict(face, name="buried"), dict(face, name="cover")]
    doc = Document.from_dict(occluded)
    assert build_mesh(doc).tri.region_names == ["cover", "background"]
    assert list(doc.diagnostics) == [], "being covered by a later shape is what the booleans are for"


def test_an_empty_mesh_is_refused_where_it_is_made(monkeypatch):
    """An empty collection is a valid data structure and never a valid intermediate result.

    This gate used to be reachable with a real document: the metre-scale slab emptied
    the mesh outright, because meshine's tolerances were absolute. They are relative
    now and that document meshes (see the test below), so the gate is driven with a
    mesher that returns nothing. It stays because this is a backstop, not the fix — a
    gate in the consumer only covers emptiness the consumer can see, and meshine owns
    its own gate for the emptiness it can explain better than we can.
    """
    import simcase.runner as runner

    empty = TriMesh(np.zeros((0, 2)), np.zeros((0, 3), dtype=int), np.zeros(0, dtype=int),
                    [], {}, {}, {})
    monkeypatch.setattr(runner, "generate", lambda *a, **k: empty)
    with pytest.raises(DocumentError, match="0 nodes and 0 triangles"):
        build_mesh(Document.from_dict(copy.deepcopy(examples.SLAB_TE_CHECK)))


def test_the_metre_document_meshes_like_the_micrometre_one():
    """The regression the gate above used to catch. A 220 nm film written in metres is
    the same film; it reaches the mesher as the same micrometre doubles, so the mesh is
    bitwise the micrometre one."""
    base = copy.deepcopy(examples.SLAB_TE_CHECK)
    meshes = {symbol: build_mesh(Document.from_dict(_written_in(base, symbol, factor_text))).tri
              for symbol, factor_text in (("um", "1"), ("m", "1e-6"))}
    um, m = meshes["um"], meshes["m"]
    assert m.num_triangles > 0 and m.num_nodes > 0
    assert m.region_names == um.region_names
    for name in ("nodes", "triangles", "regions"):
        assert getattr(m, name).tobytes() == getattr(um, name).tobytes(), name


@pytest.mark.parametrize("symbol,factor_text", [("um", "1"), ("nm", "1000"), ("m", "1e-6")])
def test_the_kernel_receives_the_micrometre_wavelength_from_its_exact_value(symbol, factor_text):
    """1.55 um, 1550 nm and 1.55e-6 m reach physmat and the kernel as the double 1.55."""
    from simcase.modes_document import kernel_document
    doc = Document.from_dict(_written_in(copy.deepcopy(examples.SOI_STRIP), symbol, factor_text))
    k = kernel_document(doc)
    assert k["physics"]["em1"]["wavelength"] == 1.55
    assert k["study"]["values"] == [1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7]


def test_a_metal_requires_explicit_target_rather_than_a_dielectric_filter():
    """Do not apply the dielectric interval automatically to a metal."""
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["geometry"]["shapes"][0]["material"] = "physmat:Au"
    doc = Document.from_dict(d)
    model = build_mesh(doc)
    eps = model.relative_permittivity(1.55e-6)
    assert np.iscomplexobj(eps) and np.any(eps.imag > 0)         # loss reaches the physics (exp(-i omega t))
    with pytest.raises(ValueError, match="target_effective_index"):
        solve_point(model, doc.si["physics"]["em1"])


def test_more_than_one_physics_is_rejected_for_now():
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["physics"]["th1"] = copy.deepcopy(d["physics"]["em1"])
    with pytest.raises(DocumentError, match="not implemented yet"):
        Document.from_dict(d)


def _put(data, path, value):
    node, keys = data, re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for key in keys[:-1]:
        node = node[int(key[1:-1])] if key.startswith("[") else node[key]
    last = keys[-1]
    if value is _DELETE:
        del node[last]
    elif last.startswith("["):
        node[int(last[1:-1])] = value
    else:
        node[last] = value


_DELETE = object()


@pytest.mark.parametrize("path,value,code,where", [
    ("openphysics", "9.9", "E-FORMAT", "openphysics"),
    ("geometry.domain", {"xmin": 1, "xmax": 0, "ymin": 0, "ymax": 1}, "E-CONTRACT", "geometry.domain.xmax"),
    ("physics.em1.formulation", "magic", "E-VALUE-FORM", "physics.em1.formulation"),
    ("physics.em1.boundary.left", "open", "E-VALUE-FORM", "physics.em1.boundary.left"),
    ("mesh.element_size", "-1 um", "E-DOMAIN", "mesh.element_size"),
    ("study", {"type": "sweep", "parameter": "physics.em1.nope", "values": [1]}, "E-CONTRACT", "study.parameter"),
    ("study", {"type": "sweep", "parameter": "mesh.element_size", "values": ["0.2 um"]}, "E-CONTRACT",
     "study.parameter"),
    ("geometry.shapes[0].w", _DELETE, "E-KEY-MISSING", "geometry.shapes[0].w"),
    ("physics.em1.effective_index_threshold", _DELETE, "E-KEY-MISSING", "physics.em1.effective_index_threshold"),
])
def test_validation_errors(path, value, code, where):
    d = copy.deepcopy(examples.SOI_STRIP)
    _put(d, path, value)
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [(code, where)]


def test_shape_validation():
    d = copy.deepcopy(examples.SOI_STRIP)
    d["geometry"]["shapes"].append(dict(d["geometry"]["shapes"][0]))
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [
        ("E-ID-CLASH", "geometry.shapes[1].name")]


def test_unknown_material_is_reported():
    d = copy.deepcopy(examples.FIBER)
    d["geometry"]["shapes"][0]["material"] = "kryptonite"
    with pytest.raises(DocumentError, match="kryptonite"):
        run(Document.from_dict(d), verbose=False)


# ---- geometry resolution -------------------------------------------------------

def test_later_shapes_cut_earlier_ones_and_background_fills_the_rest():
    """The boolean resolution of the micrometre hand-off (areas in square micrometres)."""
    from simcase.modes_document import kernel_document
    doc = Document.from_dict(examples.HADLEY_RIB)
    regions = {name: geom.area for name, _m, geom, _s, _e in resolve_regions(kernel_document(doc))}
    assert abs(regions["substrate"] - 180.0) < 1e-9
    assert abs(regions["slab"] - (18 * 0.3 - 3 * 0.3)) < 1e-9        # rib removed from the slab
    assert abs(regions["rib"] - 3.0) < 1e-9
    assert abs(regions["background"] - (18 * 3 - 18 * 0.3 - 3 * 0.7)) < 1e-9
    assert abs(sum(regions.values()) - 18 * 13) < 1e-9                  # tiles the whole domain


def test_untouched_circle_stays_exact():
    from simcase.modes_document import kernel_document
    doc = Document.from_dict(examples.FIBER)
    regs = resolve_regions(kernel_document(doc))
    assert any(ex is not None for _n, _m, _g, _s, ex in regs)
    res = run(doc, verbose=False)
    core = res.regions == res.region_names.index("core")
    core_nodes = set(res.triangles[core].ravel())
    clad_nodes = set(res.triangles[~core].ravel())
    iface = np.array(sorted(core_nodes & clad_nodes))
    assert np.abs(np.hypot(*res.node_coordinates[iface].T) - 4e-6).max() < 1e-15      # metres


# ---- end to end against references --------------------------------------------


@pytest.mark.parametrize("symbol,factor_text", [("um", "1"), ("nm", "1000"), ("m", "1e-6")])
def test_document_and_saved_results_display_the_declared_unit(symbol, factor_text, tmp_path, monkeypatch):
    import matplotlib.pyplot as plt

    data = _written_in(examples.SLAB_TE_CHECK, symbol, factor_text)
    doc = Document.from_dict(copy.deepcopy(data))
    original = copy.deepcopy(doc.data)
    per_unit = float(Decimal(1) / Decimal(factor_text)) * 1e-6           # metres per document unit
    wavelength = data["physics"]["em1"]["vacuum_wavelength"]
    summary = doc.summary()
    assert f"(length_unit {symbol})" in summary
    assert f"vacuum_wavelength {wavelength}," in summary                   # the authored text
    assert f"mesh: element_size {data['mesh']['element_size']}" in summary
    assert f"element_size {data['geometry']['shapes'][0]['element_size']}" in summary

    # Inspect the figure that is actually saved, using a minimal triangular field (SI).
    res = RunResult(doc, np.array([[0., 0.], [1e-6, 0.], [0., 1e-6]]), np.array([[0, 1, 2]]), np.array([0]),
                    ["core"], {"core": "physmat:Si"}, None, np.array([1.55e-6]), np.array([[2.8]]),
                    [np.array([[0.], [1.], [0.5]])])
    captured = []
    close = plt.close
    monkeypatch.setattr(plt, "close", lambda fig=None: captured.append(fig) if hasattr(fig, "axes") else close(fig))
    out = res.save(tmp_path / "out")
    fig = captured[-1]
    try:
        assert [ax.get_xlabel() for ax in fig.axes] == [f"x ({symbol})"] * 2
        assert [ax.get_ylabel() for ax in fig.axes] == [f"y ({symbol})"] * 2
        assert f"vacuum_wavelength = {1.55e-6 / per_unit:g} {symbol}:" in fig.axes[1].get_title()
        assert fig.axes[0].get_xlim()[1] >= 1e-6 / per_unit * (1 - 1e-12)
        saved = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        assert "units" not in saved and saved["field_units"]["node_coordinates"] == "m"
        assert saved["study"]["values"] == {"unit": "m", "values": [1.55e-6]}
        assert json.loads((out / "model.json").read_text(encoding="utf-8")) == data
        assert doc.data == original
    finally:
        close(fig)


@pytest.mark.parametrize("parameter,values,study_values,expected,shown", [
    ("physics.em1.vacuum_wavelength", [1.5e-6, 1.6e-6], None, "physics.em1.vacuum_wavelength (nm)", "1600 nm"),
    ("physics.em1.boundary.left", [1.55e-6, 1.55e-6], ["pec", "pmc"], "physics.em1.boundary.left", "pmc"),
])
def test_sweep_plot_labels_only_length_parameters_with_a_length_unit(parameter, values, study_values, expected,
                                                                     shown, tmp_path, monkeypatch):
    import matplotlib.pyplot as plt

    doc = Document.from_dict(_written_in(examples.SLAB_TE_CHECK, "nm", "1000"))
    res = RunResult(doc, np.array([[0., 0.], [1e-9, 0.], [0., 1e-9]]),
                    np.array([[0, 1, 2]]), np.array([0]), ["core"], {"core": "physmat:Si"},
                    parameter, np.array(values), np.array([[2.8], [2.7]]), [np.array([[0.], [1.], [0.5]])] * 2,
                    study_values=None if study_values is None else np.array(study_values))
    captured = []
    close = plt.close
    monkeypatch.setattr(plt, "close", lambda fig=None: captured.append(fig) if hasattr(fig, "axes") else close(fig))
    res.plot(tmp_path / "sweep.png")
    fig = captured[-1]
    try:
        assert fig.axes[2].get_xlabel() == expected
        title = fig.axes[1].get_title()
        name = "vacuum_wavelength" if study_values is None else parameter
        assert f"{name} = {shown}:" in title
    finally:
        close(fig)


def _sellmeier(symbol, factor_text, *, constant=None, valid=("0.5 um", "2 um"), terms=((0.7, "0.01 um^2"),
                                                                                        (0.4, "0.04 um^2"))):
    model = {"model": "sellmeier", "terms": [{"strength": b, "resonance_wavelength_squared": c} for b, c in terms],
             "reference_medium": "vacuum"}
    if constant is not None:
        model["constant"] = constant
    if valid is not None:
        model["valid"] = {"vacuum_wavelength": list(valid)}
    return _written_in({"geometry": {"length_unit": "um", "domain": {}, "shapes": []}, "model": model},
                       symbol, factor_text)["model"]


@pytest.mark.parametrize("symbol,factor_text", [("um", "1"), ("nm", "1000"), ("m", "1e-6")])
def test_sellmeier_roundtrips_and_preserves_physical_dispersion(symbol, factor_text, tmp_path):
    from simcase.modes_document import optical_material
    d = _written_in(examples.SLAB_TE_CHECK, symbol, factor_text)
    d["materials"] = {"glass": {"source": "test reference", "refractive_index": _sellmeier(symbol, factor_text,
                                                                                           constant=1.2)}}
    d["geometry"]["background"] = {"material": "glass"}
    doc = Document.from_dict(d)
    doc.save(tmp_path / "material.json")
    again = Document.load(tmp_path / "material.json")
    assert again.data == doc.data
    mat = optical_material(again, "glass")
    wavelengths = np.array([0.5, 1.0, 1.55, 2.0])                         # the kernel's micrometres
    expected = np.sqrt(1.2 + 0.7 * wavelengths**2 / (wavelengths**2 - 0.01)
                       + 0.4 * wavelengths**2 / (wavelengths**2 - 0.04))
    np.testing.assert_allclose(mat.index(wavelengths), expected, rtol=1e-13)
    assert mat.source == "test reference"
    with pytest.raises(physmat.OutOfRange):
        mat.index(2.1)


def test_minimal_sellmeier_uses_default_constant_and_unbounded_range():
    from simcase.modes_document import optical_material
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["materials"] = {"glass": {"refractive_index": _sellmeier("um", "1", valid=None, terms=((1.0, "0.01 um^2"),))}}
    d["geometry"]["background"] = {"material": "glass"}
    doc = Document.from_dict(d)
    mat = optical_material(doc, "glass")
    assert mat.n(3.0) == pytest.approx(np.sqrt(1 + 9 / 8.99))
    assert ("materials.glass.refractive_index.constant", 1) in [(a["path"], a["value"]) for a in doc.defaults_applied]


_GOOD = {"model": "sellmeier", "terms": [{"strength": 1.0, "resonance_wavelength_squared": "0.01 um^2"}],
         "reference_medium": "vacuum"}


def _model(**changes):
    return dict(copy.deepcopy(_GOOD), **changes)


@pytest.mark.parametrize("spec,code,where", [
    (None, "E-VALUE-FORM", ""),
    ({}, "E-PROPERTY-MISSING", ".refractive_index"),
    ({"refractive_index": True}, "E-VALUE-FORM", ".refractive_index"),
    ({"refractive_index": -1}, "E-DOMAIN", ".refractive_index"),
    ({"refractive_index": 0}, "E-DOMAIN", ".refractive_index"),
    ({"refractive_index": {"n": 1.5, "k": -0.1}}, "E-GAIN", ".refractive_index.k"),
    ({"refractive_index": {"n": 1.5}}, "E-KEY-MISSING", ".refractive_index.k"),
    ({"refractive_index": {"model": "sellmeier", "reference_medium": "vacuum"}}, "E-KEY-MISSING",
     ".refractive_index.terms"),
    ({"refractive_index": _model(terms=[])}, "E-DOMAIN", ".refractive_index.terms"),
    ({"refractive_index": _model(terms=[{"strength": True, "resonance_wavelength_squared": "0.01 um^2"}])},
     "E-VALUE-FORM", ".refractive_index.terms[0].strength"),
    ({"refractive_index": _model(terms=[{"strength": 1, "resonance_wavelength_squared": 0.01}])},
     "E-UNIT-MISSING", ".refractive_index.terms[0].resonance_wavelength_squared"),
    ({"refractive_index": _model(terms=[{"strength": 1}])}, "E-KEY-MISSING",
     ".refractive_index.terms[0].resonance_wavelength_squared"),
    ({"refractive_index": _model(terms=[{"strength": 1, "resonance_wavelength_squared": "0.01 um^2",
                                         "resonance_wavelength": "0.1 um"}])},
     "E-OVERDETERMINED", ".refractive_index.terms[0]"),
    ({"refractive_index": _model(constant=None)}, "E-VALUE-FORM", ".refractive_index.constant"),
    ({"refractive_index": _model(valid={"vacuum_wavelength": ["1 um"]})}, "E-VALUE-FORM",
     ".refractive_index.valid.vacuum_wavelength"),
    ({"refractive_index": _model(valid={"vacuum_wavelength": ["2 um", "1 um"]})}, "E-DOMAIN",
     ".refractive_index.valid.vacuum_wavelength"),
    ({"refractive_index": _model(valid={"vacuum_wavelength": ["-1 um", "2 um"]})}, "E-DOMAIN",
     ".refractive_index.valid.vacuum_wavelength[0]"),
    ({"refractive_index": _model(a=1)}, "E-KEY-UNKNOWN", ".refractive_index.a"),
    ({"refractive_index": {k: v for k, v in _GOOD.items() if k != "reference_medium"}}, "E-KEY-MISSING",
     ".refractive_index.reference_medium"),
    ({"sellmeier": {"B": [1], "C": [0]}}, "E-KEY-UNKNOWN", ".sellmeier"),
    ({"n": 1.5}, "E-KEY-UNKNOWN", ".n"),
    ({"refractive_index": 1.5, "source": 123}, "E-VALUE-FORM", ".source"),
])
def test_invalid_custom_materials_fail_at_document_validation(spec, code, where):
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["materials"] = {"glass": spec}
    d["geometry"]["shapes"][0]["material"] = "glass"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [
        (code, "materials.glass" + where)]


@pytest.mark.parametrize("symbol,factor_text", [("um", "1"), ("nm", "1000"), ("m", "1e-6")])
def test_sellmeier_slab_matches_refsol_across_units(symbol, factor_text):
    d = _written_in(examples.SLAB_TE_CHECK, symbol, factor_text)
    d["materials"] = {"film": {"refractive_index": _sellmeier(symbol, factor_text, valid=("1 um", "2 um"),
                                                              terms=((11.0, "0.01 um^2"),))}}
    d["geometry"]["shapes"][0]["material"] = "film"
    res = run(Document.from_dict(d), verbose=False)
    n_film = np.sqrt(1 + 11 * 1.55**2 / (1.55**2 - 0.01))
    n_clad = physmat.get("SiO2").n(1.55)
    exact = slab.modes(n_film, n_clad, n_clad, 0.22, 1.55, "TE")[0]
    assert abs(res.effective_index[0, 0] - exact) < 1.5e-3


def test_slab_te_matches_refsol_through_the_whole_chain():
    doc = Document.from_dict(examples.SLAB_TE_CHECK)
    res = run(doc, verbose=False)
    n_si, n_ox = physmat.get("Si").n(1.55), physmat.get("SiO2").n(1.55)
    exact = slab.modes(n_si, n_ox, n_ox, 0.22, 1.55, "TE")[0]
    assert abs(res.effective_index[0, 0] - exact) < 1.5e-3            # P1, h = 10 nm in the film


def test_fiber_scalar_matches_lp_modes():
    res = run(Document.from_dict(examples.FIBER), verbose=False)
    lp = fiber.lp_modes(4.0, 1.45, 1.44, 1.55)
    assert abs(res.effective_index[0, 0] - lp[0].neff) < 2e-4         # LP01
    assert abs(res.effective_index[0, 1] - lp[1].neff) < 2e-4         # LP11


def test_rib_scalar_is_near_hadley():
    res = run(Document.from_dict(examples.HADLEY_RIB), verbose=False)
    # Scalar model: 4e-5 off on this mesh, but refining moves it away (1.4e-4 at
    # 0.65x), so the closeness is cancellation; hadley_rib_vector converges to it.
    assert abs(res.effective_index[0, 0] - benchmarks.rib_neff(0.3)) < 5e-4


def test_sweep_produces_group_index_and_saves(tmp_path):
    d = copy.deepcopy(examples.SOI_STRIP)
    d["study"]["values"] = {"unit": "um", "values": [1.50, 1.55, 1.60]}
    d["physics"]["em1"]["mode_count"] = 1
    res = run(Document.from_dict(d), verbose=False)
    assert res.effective_index.shape == (3, 1)
    assert np.all(np.diff(res.effective_index[:, 0]) < 0)            # n_eff falls with wavelength
    ng = res.group_index()
    assert ng is not None and (ng > res.effective_index).all()         # normal dispersion: n_g > n_eff
    out = res.save(tmp_path / "out")
    for f in ("summary.json", "fields.npz", "results.png", "log.txt", "model.json"):
        assert (out / f).exists()
    s = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert s["study"]["values"] == {"unit": "m", "values": [w * 1e-6 for w in (1.5, 1.55, 1.6)]}   # kernel x 1e-6
    assert s["group_index"]["unit"] == "1" and len(s["group_index"]["values"]) == 3


def test_vector_formulation_requires_an_explicit_effective_index_threshold():
    d = copy.deepcopy(examples.SLAB_TE_CHECK)
    d["physics"]["em1"]["formulation"] = "vector"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == "error"] == [
        ("E-KEY-MISSING", "physics.em1.effective_index_threshold")]
