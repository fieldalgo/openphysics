# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The slot table of format 0.3 documents (units batch C4, check P2-12, shared part).

The frozen ``slot_table.json`` equals its generator; every quantity slot names a registry
quantity placed in documents or materials; every path of the shared parts (envelope,
geometry, materials, mesh, study, results) of every converted example and fixture matches
exactly one slot; and a path in no slot is ``E-KEY-UNKNOWN`` at that path. The physics
entries, ``study.tracking`` and ``results.mode_overlap`` are each kind's slots, which arrive
with that kind's commit; no kind brings slots yet.
"""

from __future__ import annotations

import importlib.util
import json
from importlib import resources
from pathlib import Path

import pytest
from physmat import units

from simcase import registry, slots
from simcase.resolve import resolve_text
from simcase.schema import Document

import units_toy_kind as toy

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tools" / "units_batch"
KIND_PATHS = (("physics",), ("study", "tracking"), ("results", "mode_overlap"))


@pytest.fixture
def toy_kind():
    with toy.registered():
        yield


def test_the_frozen_table_equals_its_generator():
    assert slots._main(["--check"]) == 0
    text = resources.files("simcase").joinpath(slots.TABLE_FILE).read_text(encoding="utf-8")
    assert text == slots.generate()
    table = json.loads(text)
    assert table["format"] == slots.TABLE_FORMAT
    # the kinds that read format 0.3 at this step of the units batch: heat (C5), electric and Joule (C6),
    # mechanics (C7), waveguide modes (C8)
    assert table["kinds"] == {"thermal.steady2d": ["thermal.steady2d"], "thermal.transient2d": ["thermal.transient2d"],
                              "electric_joule": ["electric.steady2d", "joule.steady2d", "joule.temperature2d"],
                              "mechanics": ["mechanics.elasticity2d", "mechanics.thermoelastic2d"],
                              "em.modes2d": ["em.modes2d"], "em.cavity3d": ["em.cavity3d"]}
    patterns = [(e["pattern"], e.get("physics_kind") or "", e["kind"]) for e in table["slots"]]
    assert patterns == sorted(patterns)


def test_every_quantity_slot_names_a_registry_quantity_of_documents_or_materials():
    entries = slots.shared_slots() + [{**e, "physics_kind": toy.NAME} for e in toy.SLOTS]
    slots._validate(entries)
    checked = 0
    for e in entries:
        if e["kind"] in ("quantity", "material_property"):
            q = units.quantity(e["quantity"])
            assert {"document", "material"} & set(q.places), e["pattern"]
            checked += 1
        assert e["kind"] in slots.SLOT_KINDS
    assert checked > 30
    bad = {**slots.shared_slots()[0], "pattern": "physics.*.speed", "kind": "quantity", "quantity": "effective_index"}
    with pytest.raises(ValueError, match="not placed in documents or materials"):
        slots._validate([bad])


@pytest.mark.parametrize("pattern", ["a..b", "a.", "[]", "geometry<round>.x", "mesh.*{x}.y", "a b"])
def test_malformed_patterns_are_refused(pattern):
    with pytest.raises(ValueError):
        slots.compile_pattern(pattern)


def test_patterns_match_keys_items_guards_and_literals():
    table = slots.SlotTable([{"pattern": "physics.*{a|b}.x", "kind": "string"},
                             {"pattern": 'materials.*["n.1"]', "kind": "string"},
                             {"pattern": "geometry<v1>.components.*.features[].points[][]", "kind": "shape"}], None)
    tree = {"physics": {"p": {"type": "a"}, "q": {"type": "c"}}, "geometry": {"version": 1}}
    assert table.match(["physics", "p", "x"], tree)
    assert not table.match(["physics", "q", "x"], tree)
    assert table.match(["materials", "m", "n.1"], tree)
    assert table.match(["geometry", "components", "c", "features", 0, "points", 3, 1], tree)
    assert not table.match(["geometry", "components", "c", "features", "0", "points", 3, 1], tree)
    assert not table.match(["geometry", "components", "c", "features", 0, "points", 3, 1], {"geometry": {}})


def _paths(node, prefix=()):
    """Every path of an authored tree, objects and lists included."""
    yield prefix
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _paths(v, prefix + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _paths(v, prefix + (i,))


def _leaves_consumed(slot, value) -> bool:
    """A leaf slot reads its whole value (a tagged array, {n, k}, a component object, a selector);
    a model object or a reference object has slots of its own."""
    if slot["kind"] == "structural":
        return False
    opens = {"MODEL", "OBJECT"} & set(slot.get("forms", ()))
    return not (opens and isinstance(value, dict) and ("model" in value or "OBJECT" in opens))


def _check_closure(tree, table, label, skip=KIND_PATHS):
    """Every path outside ``skip`` (the kinds' own parts) matches exactly one slot; returns the count."""
    count, consumed = 0, []
    for path in _paths(tree):
        value = tree
        for part in path:
            value = value[part]
        if not path or any(path[:len(k)] == k for k in skip):
            continue
        if any(path[:len(c)] == c for c in consumed):
            continue
        found = table.match(list(path), tree)
        assert len(found) == 1, (label, path, [e["pattern"] for e in found])
        if _leaves_consumed(found[0], value):
            consumed.append(path)
        count += 1
    return count


if HARNESS.is_dir():
    # tools/ is not copied to the installed-package run, where a skip would fail it

    def _converter():
        spec = importlib.util.spec_from_file_location("_units_batch_convert_v02_for_slots", HARNESS / "convert_v02.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    _CORPUS = (sorted((ROOT / "examples" / "simcase").glob("*.json")) + sorted((HARNESS / "fixtures" / "v02").glob("*.json"))
               + sorted((HARNESS / "fixtures" / "v03").glob("*.json")))

    @pytest.mark.parametrize("path", _CORPUS, ids=lambda p: f"{p.parent.name}/{p.stem}")
    def test_every_shared_path_of_every_converted_document_matches_one_slot(path):
        """A 0.2 document through the converter, a committed 0.3 document as it is. A kind that reads
        format 0.3 has its physics paths checked too (P2-12)."""
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["openphysics"] == "0.2":
            data, _writer = _converter().convert(data)
        tree = json.loads(json.dumps(data))
        kind = registry.kind_of(tree)
        if kind.slots is None:
            assert _check_closure(tree, slots.table_for(None), path.stem) > 5
        else:
            assert _check_closure(tree, slots.table_for(kind), path.stem, skip=()) > 10


def test_every_shared_path_of_the_toy_document_matches_one_slot(toy_kind):
    table = slots.table_for(registry.kind_of(toy.document()))
    assert _check_closure(toy.document(), table, "toy") > 10


@pytest.mark.parametrize("path, key", [
    (("geometry",), "length_unti"), (("geometry", "domain"), "zmax2"), (("geometry", "shapes", 0), "colour"),
    (("geometry", "background"), "mesh_size"), (("mesh",), "fine"), (("study",), "times"), (("results",), "vtu"),
    (("materials", "steel"), "description"), (("materials", "steel"), "E"), (("physics", "bar"), "wavelenght"),
    ((), "comment")])
def test_a_path_in_no_slot_is_e_key_unknown_at_that_path(toy_kind, path, key):
    data = toy.document(results={"save_fields": True})
    node = data
    for part in path:
        node = node[part]
    node[key] = "1 mm"
    result = resolve_text(json.dumps(data))
    where = ".".join(str(p) for p in path + (key,)).replace(".0.", "[0].")
    assert ("E-KEY-UNKNOWN", where) in [(d.code, d.path) for d in result.diagnostics]
    assert result.document() is None


@pytest.mark.parametrize("old, parent, new, words", [
    ("size", ("mesh",), "element_size", ()), ("min_angle", ("mesh",), "minimum_angle", ()),
    ("mesh_size", ("geometry", "shapes", 0), "element_size", ()),
    ("young_modulus_pa", ("materials", "steel"), "youngs_modulus", ()),
    ("outward_flux_w_m2", ("physics", "bar"), "inward_heat_flux", ("negated",)),
    ("E", ("physics", "bar"), "youngs_modulus", ()), ("time_s", ("study",), "time", ())])
def test_an_unknown_key_says_what_to_write(toy_kind, old, parent, new, words):
    data = toy.document()
    node = data
    for part in parent:
        node = node[part]
    node[old] = 1
    result = resolve_text(json.dumps(data))
    [d] = [d for d in result.diagnostics if d.code == "E-KEY-UNKNOWN"]
    assert new in d.message and all(w in d.message for w in words)
    assert d.fix is None                                 # a renamed key, or a negation, is never a fix


def test_refused_keys_come_first_with_their_own_code(toy_kind):
    result = resolve_text(json.dumps(toy.document(physics__bar__absolute_pressure="2 bar",
                                                  materials={"steel": {"base": "physmat:Si"}})))
    codes = [(d.code, d.path) for d in result.diagnostics]
    assert ("E-ABSOLUTE-AS-LOAD", "physics.bar.absolute_pressure") in codes
    assert ("E-KEY-UNKNOWN", "materials.steel.base") in codes


def test_a_kind_override_changes_only_that_kind(toy_kind):
    doc = Document.from_dict(toy.document(name=toy.DELETE))
    assert doc.si["name"] == "untitled" and doc.si["results"] == {"save_fields": True, "plots": False}
    shared = slots.table_for(None)
    assert "default" not in shared.match(["name"], {})[0]
    assert shared.policy().get("library") is None
    assert slots.table_for(registry.kind_of(toy.document())).policy()["library"] == "any"


def test_required_slots_and_value_forms(toy_kind):
    result = resolve_text(json.dumps(toy.document(geometry__domain={"xmin": 0, "xmax": True, "ymin": "1"})))
    codes = [(d.code, d.path) for d in result.diagnostics]
    assert ("E-VALUE-FORM", "geometry.domain.xmax") in codes
    assert ("E-VALUE-FORM", "geometry.domain.ymin") in codes
    assert ("E-KEY-MISSING", "geometry.domain.ymax") in codes
