# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The exact document reader of format 0.3 (units batch C4, check P2-10).

The 0.3 path is tested on the test-only kind of ``units_toy_kind``; rectangle heat reads
format 0.3 since units batch C5a, and its converted examples take the 0.3 path. The documents
still on 0.2 must behave exactly as before: they never take the 0.3 path, and
``Document.canonical_json()`` gives the bytes ``json.dumps`` gave at every serialiser of
``doc.data``.
"""

from __future__ import annotations

import copy
import json
import math
import random
import re
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

import simcase
from simcase import reader
from simcase.diagnostics import DiagnosticList, DocumentError, error_lines
from simcase.geometry_document import GeometryError
from simcase.resolve import resolve_text
from simcase.schema import Document, declares_v03

import units_toy_kind as toy

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples" / "simcase").glob("*.json"))
EXAMPLES_03 = [p for p in EXAMPLES if json.loads(p.read_text(encoding="utf-8"))["openphysics"] == "0.3"]
EXAMPLES_02 = [p for p in EXAMPLES if p not in EXAMPLES_03]
FIXTURES = ROOT / "tools" / "units_batch" / "fixtures" / "v02"
FIXTURES_03 = ROOT / "tools" / "units_batch" / "fixtures" / "v03"


def _corpus(folder: Path) -> list[Path]:
    """The fixture documents of a folder; an empty corpus fails collection instead of turning the
    tests over it into a skip (the installed-package run copies the fixtures too)."""
    paths = sorted(folder.glob("*.json"))
    assert paths, f"no fixture documents in {folder}"
    return paths


@pytest.fixture
def toy_kind():
    with toy.registered():
        yield


def _doc(text):
    return Document.loads(text)


def _codes(diagnostics):
    return [(d.code, d.path) for d in diagnostics]


# -- P2-10 reader exactness -----------------------------------------------------------------------

def test_equal_values_in_other_units_give_one_double(toy_kind):
    values = set()
    for written in ("200 GPa", "200000 MPa", "2e11 Pa"):
        doc = Document.from_dict(toy.document(physics__bar__youngs_modulus=written))
        values.add(float.hex(doc.si["physics"]["bar"]["youngs_modulus"]))
    assert values == {float.hex(2e11)}


def test_celsius_reads_as_the_double_nearest_298_15(toy_kind):
    doc = Document.from_dict(toy.document(physics__bar__prescribed_temperature={"left": "25 degC"}))
    assert doc.si["physics"]["bar"]["prescribed_temperature"]["left"] == 298.15
    assert doc.exact("physics.bar.prescribed_temperature.left") == Fraction("298.15")


def test_a_long_json_literal_is_read_from_its_text(toy_kind):
    text = toy.text(toy.document(physics__bar__poisson_ratio="@")).replace('"@"', "0.1000000000000000000001")
    doc = _doc(text)
    assert doc.data["physics"]["bar"]["poisson_ratio"] == Decimal("0.1000000000000000000001")
    assert doc.exact("physics.bar.poisson_ratio") == Fraction("0.1000000000000000000001")
    assert doc.si["physics"]["bar"]["poisson_ratio"] == 0.1


def test_micrometre_hand_off_comes_from_the_exact_value(toy_kind):
    """H2: "0.25 um" and "2.5e-4 m" hand 0.25 and 250.0 micrometres, never si / 1e-6."""
    assert 2.5e-4 / 1e-6 != 250.0                       # the hazard is real
    doc = Document.from_dict(toy.document(mesh={"element_size": "0.25 um"}, geometry__length_unit="um"))
    assert doc.um("mesh.element_size") == 0.25
    doc = Document.from_dict(toy.document(mesh={"element_size": "2.5e-4 m"}))
    assert doc.um("mesh.element_size") == 250.0
    assert doc.um("geometry.domain.xmax") == 40000.0


@pytest.mark.parametrize("written, number", [("30 deg", 30.0), ("28.5 deg", 28.5), ("0.5 rad", None)])
def test_meshine_gets_the_authored_degree_number(toy_kind, written, number):
    """H3: math.degrees(q("30 deg")) is not 30, so the mesher takes the number as written."""
    doc = Document.from_dict(toy.document(mesh={"element_size": "2 mm", "minimum_angle": written}))
    si = doc.si["mesh"]["minimum_angle"]
    if number is None:
        assert doc.degrees("mesh.minimum_angle") == math.degrees(si)
    else:
        assert doc.degrees("mesh.minimum_angle") == number
    assert math.degrees(Document.from_dict(toy.document(mesh={"element_size": "2 mm", "minimum_angle": "30 deg"}))
                        .si["mesh"]["minimum_angle"]) != 30.0


def test_the_default_minimum_angle_hands_28_degrees(toy_kind):
    doc = Document.from_dict(toy.document())
    assert doc.degrees("mesh.minimum_angle") == 28.0
    assert any(d["path"] == "mesh.minimum_angle" and d["value"] == "28 deg" for d in doc.defaults_applied)


def test_a_document_from_a_file_saves_its_bytes(toy_kind, tmp_path):
    raw = ("﻿" + toy.text(toy.document()).replace("\n", "\r\n") + "\r\n").encode("utf-8")
    source = tmp_path / "model.json"
    source.write_bytes(raw)
    doc = Document.load(source)
    assert doc.source_bytes == raw
    out = toy.run(doc).save(tmp_path / "out")
    assert (out / "model.json").read_bytes() == raw
    doc.save(tmp_path / "copy.json")
    assert (tmp_path / "copy.json").read_bytes() == raw


def test_a_python_dict_with_floats_resolves_like_its_json_text(toy_kind):
    data = toy.document(physics__bar__poisson_ratio=0.1 + 0.2, geometry__shapes=[
        {"name": "core", "type": "rect", "x": 5.5, "y": 0.1, "w": 1e-3, "h": 6.0, "material": "steel"}])
    from_dict = Document.from_dict(copy.deepcopy(data))
    from_text = _doc(json.dumps(data))
    assert from_dict.si == from_text.si
    assert from_dict.data == from_text.data
    assert from_dict.data["physics"]["bar"]["poisson_ratio"] == Decimal(repr(0.1 + 0.2))


def test_a_utf8_bom_is_accepted_and_utf16_is_refused(toy_kind):
    text = toy.text(toy.document())
    assert Document.loads(b"\xef\xbb\xbf" + text.encode("utf-8")).si is not None
    assert Document.loads("﻿" + text).si is not None
    for encoding in ("utf-16", "utf-16-le", "utf-32"):
        raw = text.encode(encoding)
        result = resolve_text(raw)
        assert [d.code for d in result.diagnostics] == ["E-JSON"], encoding
    assert [d.code for d in resolve_text(b'{"openphysics": "0.3", "name": "\xff"}').diagnostics] == ["E-JSON"]


def test_minus_zero_reads_as_plus_zero(toy_kind):
    text = toy.text(toy.document()).replace('"xmin": 0,', '"xmin": -0,', 1).replace('"ymin": 0,', '"ymin": -0.0,', 1)
    doc = _doc(text)
    for key in ("xmin", "ymin"):
        x = doc.si["geometry"]["domain"][key]
        assert x == 0.0 and math.copysign(1.0, x) == 1.0
    doc = Document.from_dict(toy.document(physics__bar__inward_heat_flux={"top": "-0 W/m^2"}))
    assert math.copysign(1.0, doc.si["physics"]["bar"]["inward_heat_flux"]["top"]) == 1.0


def _negative_zeros(node, path=""):
    if isinstance(node, dict):
        return [p for k, v in node.items() for p in _negative_zeros(v, f"{path}.{k}")]
    if isinstance(node, list):
        return [p for i, v in enumerate(node) for p in _negative_zeros(v, f"{path}[{i}]")]
    if isinstance(node, (Decimal, float)) and node == 0 and math.copysign(1, node) < 0:
        return [path]
    if isinstance(node, str) and re.fullmatch(r"-0+(\.0*)?([eE][-+]?\d+)?( .*)?", node):
        return [path]
    return []


def test_no_shipped_value_is_a_negative_zero():
    """H7: a -0.0 input would reach a solver as -0.0; none of the shipped documents has one."""
    assert EXAMPLES
    for path in EXAMPLES:
        assert _negative_zeros(reader.loads(path.read_bytes())) == [], path.name
    for name, data in simcase.examples.EXAMPLES.items():
        assert _negative_zeros(reader.read(data)) == [], name


def test_json_dumps_is_never_called_on_document_data():
    """Every serialiser of doc.data goes through canonical_json() or reader.dumps (Decimals)."""
    source = Path(simcase.__file__).parent
    pattern = re.compile(r"json\.dumps\([^)]*\.data\b|_exact_json\([^)]*\.data\b")
    hits = [f"{p.name}:{i}" for p in sorted(source.rglob("*.py"))
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if pattern.search(line)]
    assert hits == []
    uses = sum(p.read_text(encoding="utf-8").count("canonical_json(") for p in source.rglob("*.py"))
    assert uses >= 19


def test_p2_9_no_stage_copies_diagnostics_by_note_text():
    """P2-9: a stage passes the mesher's findings on by path (``mesh_diagnostics_03``), never by
    filtering note text on a prefix; the last two such filters (the region mesh and the engine
    hand-off) went with the kernel hand-offs' 0.2 trees (units batch C11b)."""
    source = Path(simcase.__file__).parent
    pattern = re.compile(r"startswith\(\(?[\"'](geometry\.|mesh\.controls:)")
    hits = [f"{p.name}:{i}" for p in sorted(source.rglob("*.py"))
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if pattern.search(line)]
    assert hits == []


def test_canonical_json_of_a_0_3_document_keeps_its_decimals(toy_kind):
    text = toy.text(toy.document(physics__bar__poisson_ratio="@")).replace('"@"', "0.30000000000000000001")
    doc = _doc(text)
    canonical = doc.canonical_json()
    assert "0.30000000000000000001" in canonical
    assert reader.loads(canonical) == doc.data
    with pytest.raises(TypeError):
        json.dumps(doc.data)


def test_a_single_kind_refusal_prints_its_message(toy_kind):
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(toy.document(physics__bar__youngs_modulus="2000 GPa"))
    message = toy.STIFF.format(name="bar")
    assert str(caught.value) == message
    assert ("E-CONTRACT", "physics.bar.youngs_modulus") in _codes(caught.value.diagnostics)
    assert "W-MAGNITUDE" in [d.code for d in caught.value.diagnostics]      # kept, not in str()
    error = DocumentError("physics.x.y: refused")
    assert str(error) == "physics.x.y: refused" and error.code == "E-CONTRACT" and error.path is None
    assert [d.code for d in error.diagnostics] == ["E-CONTRACT"]
    error = GeometryError("geometry.components.c: refused", path="geometry.components.c", code="E-KEY-MISSING")
    assert str(error) == "geometry.components.c: refused" and error.code == "E-KEY-MISSING"


def test_several_reader_errors_print_one_line_each(toy_kind):
    data = toy.document(units={"length": "mm"}, mesh={"size": "2 mm"})
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    lines = str(caught.value).splitlines()
    assert lines == error_lines(caught.value.diagnostics)
    assert lines == ['mesh.size: unknown key "size" in mesh. "size" is the format 0.2 name; write element_size '
                     '(with its unit, such as "0.2 um"). (E-KEY-UNKNOWN)',
                     "units: units travel with each value; give geometry.length_unit (or "
                     "geometry.components.<c>.length_unit) and write every other number with its unit (E-KEY-UNKNOWN)"]


# -- the JSON layer -------------------------------------------------------------------------------

def test_duplicate_keys_are_refused_at_any_depth():
    text = '{"openphysics": "0.3", "mesh": {"element_size": "1 mm", "element_size": "2 mm"}, "a": 1, "a": 2}'
    tree, found = reader.parse(text)
    assert _codes(found) == [("E-KEY-DUPLICATE", ""), ("E-KEY-DUPLICATE", "mesh")]
    assert tree["mesh"] == {"element_size": "1 mm"}
    with pytest.raises(DocumentError):
        reader.loads(text)


@pytest.mark.parametrize("text", ['{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}', '{"a": 1,}', "{'a': 1}", ""])
def test_nan_infinity_and_malformed_json_are_refused(text):
    tree, found = reader.parse(text)
    assert tree is None and [d.code for d in found] == ["E-JSON"]


def test_a_huge_number_literal_is_refused_by_length_before_arithmetic():
    big = "1" * (reader.MAX_NUMBER_CHARS + 1)
    tree, found = reader.parse('{"x": {"y": [1, %s]}}' % big)
    assert _codes(found) == [("E-DOMAIN", "x.y[1]")]
    tree, found = reader.parse('{"x": 0.%s}' % ("1" * 900))
    assert found == [] and tree["x"] == Decimal("0." + "1" * 900)
    tree, found = reader.parse('{"x": 1e999999999999}')
    assert found == [] and tree["x"] == Decimal("1e999999999999")      # read; physmat refuses its range


def test_python_objects_are_read_like_their_json_text():
    assert reader.read({"a": [0.1, 2, True, None, "s"]}) == {"a": [Decimal("0.1"), 2, True, None, "s"]}
    for bad in ({"a": math.nan}, {"a": math.inf}, {1: "x"}, {"a": object()}, {"a": Decimal("NaN")}):
        with pytest.raises(DocumentError) as caught:
            reader.read(bad)
        assert [d.code for d in caught.value.diagnostics] == ["E-JSON"]


def _random_tree(rng, depth=0):
    roll = rng.random()
    if depth > 3 or roll < 0.4:
        return rng.choice([rng.uniform(-1e6, 1e6), rng.randint(-10**20, 10**20), rng.random() * 10 ** rng.randint(-320, 300),
                           True, False, None, "plain", "µm ㎚ – − \"q\" \\ \n", 0.0, -0.0, 1e-7, 5e-324])
    if roll < 0.7:
        return [_random_tree(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    return {rng.choice(["a", "b", "z", "é", "key with space", "0"]) + str(i): _random_tree(rng, depth + 1)
            for i in range(rng.randint(0, 4))}


def test_dumps_writes_what_json_dumps_writes():
    rng = random.Random(20261109)
    options = [{}, {"sort_keys": True, "separators": (",", ":")}, {"sort_keys": True}, {"indent": 2},
               {"indent": 0, "ensure_ascii": False}, {"indent": "\t", "sort_keys": True}]
    for _ in range(300):
        tree = _random_tree(rng)
        for kw in options:
            assert reader.dumps(tree, **kw) == json.dumps(tree, **kw)
    with pytest.raises(ValueError):
        reader.dumps({"a": math.nan}, allow_nan=False)
    with pytest.raises(TypeError):
        reader.dumps({"a": object()})
    loop = []
    loop.append(loop)
    with pytest.raises(ValueError):
        reader.dumps(loop)
    # the exponent letter is written as json.dumps writes a float's (lower case)
    assert reader.dumps({"a": Decimal("1.50"), "b": Decimal("1E+5"), "c": Decimal("-0")}) == '{"a": 1.50, "b": 1e+5, "c": -0}'
    # a float read through its repr is written back as json.dumps writes the float, exponent included
    for x in (2e-05, 4e-06, -1.55e-06, 1e-07, 1e-10, 5e-324, 0.0001, 0.00012, 1e16, 1.5e22, 4.6477836068405064e+16,
              1.7976931348623157e308, 123.456):
        assert reader.dumps(reader.read(x)) == json.dumps(x), x
    assert reader.dumps(Decimal("0.000020")) == "2.0e-05"       # its own digits, the float exponent form


def test_paths_and_pointers():
    segments = ["materials", "n3.40", "refractive_index", "terms", 0, "strength"]
    path = reader.display_path(segments)
    assert path == 'materials["n3.40"].refractive_index.terms[0].strength'
    assert reader.split_path(path) == segments
    assert reader.split_path("geometry.components.my-comp.features[2].points[0][1]") == [
        "geometry", "components", "my-comp", "features", 2, "points", 0, 1]
    assert reader.json_pointer(["materials", "a/b~c", 0]) == "/materials/a~1b~0c/0"


# -- the envelope and the kinds -------------------------------------------------------------------

@pytest.mark.parametrize("value, needle", [("0.2", "format 0.2 documents are not read"),
                                           (0.3, 'the JSON string "0.3", not a number'),
                                           ("0.4", "format 0.2 documents are not read"),
                                           (None, "this reader reads the format")])
def test_the_format_is_the_string_0_3(toy_kind, value, needle):
    data = toy.document(openphysics=value)
    result = resolve_text(json.dumps(data))
    assert _codes(result.diagnostics) == [("E-FORMAT", "openphysics")]
    assert needle in result.diagnostics[0].message
    del data["openphysics"]
    assert _codes(resolve_text(json.dumps(data)).diagnostics) == [("E-FORMAT", "openphysics")]


def test_a_kind_without_slots_refuses_format_0_3():
    """Every built-in kind brings its slots since the cavity moved (C9); a kind registered without
    them is still refused by name, before the walk."""
    import dataclasses
    from simcase import registry
    registry.kinds()
    registry.register(dataclasses.replace(toy.kind(), slots=None))
    try:
        with pytest.raises(DocumentError) as caught:
            Document.from_dict(toy.document())
    finally:
        registry._KINDS.pop(toy.NAME, None)
    [d] = caught.value.diagnostics
    assert (d.code, d.path) == ("E-CONTRACT", "physics.bar.type")
    assert "not read in format 0.3 yet" in str(caught.value)


def test_no_example_is_a_format_0_2_document():
    """Every kind reads format 0.3 only since C9: no shipped example takes the 0.2 path."""
    assert EXAMPLES and EXAMPLES_02 == []


@pytest.mark.parametrize("path", _corpus(FIXTURES), ids=lambda p: p.stem)
def test_a_format_0_2_document_is_refused_by_name(path):
    raw = path.read_bytes()
    assert not declares_v03(raw)
    with pytest.raises(DocumentError) as caught:
        Document.load(path)
    assert [(d.code, d.path) for d in caught.value.diagnostics] == [("E-FORMAT", "openphysics")]
    assert (FIXTURES_03 / path.name).is_file()      # its converted twin


@pytest.mark.parametrize("path", EXAMPLES_03, ids=lambda p: p.stem)
def test_converted_documents_take_the_0_3_path(path):
    """The examples of the kinds that read format 0.3 (rectangle heat, units batch C5a)."""
    assert declares_v03(path.read_bytes())
    doc = Document.load(path)
    assert doc.si is not None and doc.format == "0.3" and not doc.diagnostics.errors


def test_unreadable_0_3_text_is_refused_by_the_0_3_reader():
    text = '{"openphysics": "0.3", "name": NaN}'
    assert declares_v03(text)
    with pytest.raises(DocumentError) as caught:
        Document.loads(text)
    assert [d.code for d in caught.value.diagnostics] == ["E-JSON"]
    assert not declares_v03('{"openphysics": "0.2", "name": NaN}')
    with pytest.raises(json.JSONDecodeError):            # a malformed 0.2 text fails as it always did
        Document.loads('{"openphysics": "0.2",')


# -- canonical_json equals today's json.dumps (must hold at C4) ------------------------------------

def _builtins():
    return sorted(simcase.examples.EXAMPLES.items())


def _check_canonical(data, label):
    doc = Document.from_dict(copy.deepcopy(data))
    # a 0.3 tree holds Decimals; its decimals are those of the Python values it was read from
    tree = doc.data if doc.si is None else data
    for separators in ((",", ":"), (", ", ": ")):
        assert doc.canonical_json(separators=separators) == json.dumps(
            tree, sort_keys=True, separators=separators, allow_nan=False), (label, separators)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_canonical_json_equals_json_dumps_for_every_example(path):
    _check_canonical(json.loads(path.read_text(encoding="utf-8")), path.name)


@pytest.mark.parametrize("name, data", _builtins(), ids=[n for n, _ in _builtins()])
def test_canonical_json_equals_json_dumps_for_every_built_in_example(name, data):
    _check_canonical(data, name)


@pytest.mark.parametrize("path", _corpus(FIXTURES) + _corpus(FIXTURES_03),
                         ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_canonical_json_equals_json_dumps_for_every_fixture(path):
    if path.parent == FIXTURES and (FIXTURES_03 / path.name).is_file():
        # a converted form: its 0.2 fixture is read by the baseline code only
        with pytest.raises(DocumentError, match="format 0.2 (rectangle heat|region heat|electric and Joule|"
                                                "mechanics|em.modes2d|em.cavity3d) documents are not read"):
            Document.from_dict(json.loads(path.read_text(encoding="utf-8")))
        return
    _check_canonical(json.loads(path.read_text(encoding="utf-8")), path.name)


def test_diagnostic_list_only_grows():
    found = DiagnosticList()
    from physmat.units import Diagnostic
    found.append(Diagnostic("I-PM-ROUNDING", "x", "m"))
    for name in ("remove", "clear", "pop", "insert", "__setitem__", "__delitem__"):
        assert not hasattr(found, name)
    with pytest.raises(ValueError):
        found.append(Diagnostic("X-NOT-A-CODE", "x", "m"))
    assert len(found) == 1 and found.infos == list(found)
