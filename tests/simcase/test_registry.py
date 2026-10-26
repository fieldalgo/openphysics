# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The physics registry: which kind claims a document, and what a new kind needs."""
import copy
import json
from pathlib import Path

import pytest

from simcase import Document, DocumentError, build_mesh, examples, registry, run, schema, solve_point

EXAMPLE_DOCUMENTS = Path(__file__).resolve().parents[2] / "examples" / "simcase"

BUILTIN = {
    "electric_joule": {"electric.steady2d", "joule.steady2d", "joule.temperature2d"},
    "thermal.transient2d": {"thermal.transient2d"},
    "thermal.steady2d": {"thermal.steady2d"},
    "em.cavity3d": {"em.cavity3d"},
    "em.modes2d": {"em.modes2d"},
}


def test_builtin_kinds_claim_each_type_once_in_precedence_order():
    kinds = registry.kinds()
    assert [k.name for k in kinds] == list(BUILTIN)
    assert {k.name: set(k.types) for k in kinds} == BUILTIN
    assert [k.name for k in kinds if k.fallback] == ["em.modes2d"]
    assert registry.physics_types() == frozenset().union(*BUILTIN.values())
    assert schema.PHYSICS_TYPES == set(registry.physics_types())


def test_stage_refusals_keep_their_messages():
    refusals = {k.name: k.stage_refusal for k in registry.kinds()}
    assert refusals == {
        "electric_joule": "{stage} is an EM stage; use run(document) for electric/Joule physics",
        "thermal.transient2d": "{stage} is an EM 2D stage; use run(document) for thermal.transient2d",
        "thermal.steady2d": "{stage} is an EM 2D stage; use run(document) for thermal.steady2d",
        "em.cavity3d": "{stage} is a 2D stage; use run(document) for em.cavity3d",
        "em.modes2d": None,
    }
    assert [k.name for k in registry.kinds() if k.fresh_output] == [
        "electric_joule", "thermal.transient2d", "thermal.steady2d"]


@pytest.mark.parametrize("types, kind", [
    (["thermal.steady2d", "joule.steady2d"], "electric_joule"),
    (["thermal.steady2d", "thermal.transient2d"], "thermal.transient2d"),
    (["em.cavity3d", "thermal.steady2d"], "thermal.steady2d"),
    (["em.modes2d", "em.cavity3d"], "em.cavity3d"),
    (["em.modes2d"], "em.modes2d"),
    (["no.such.type"], "em.modes2d"),
    ([None], "em.modes2d"),
])
def test_first_kind_in_precedence_order_claims_a_mixed_document(types, kind):
    data = {"physics": {f"p{i}": {"type": t} for i, t in enumerate(types)}}
    assert registry.kind_of(data).name == kind


@pytest.mark.parametrize("data", [None, [], {}, {"physics": None}, {"physics": []},
                                  {"physics": {"p": "thermal.steady2d"}}])
def test_malformed_physics_goes_to_the_fallback(data):
    assert registry.kind_of(data).name == "em.modes2d"


def test_kind_of_type():
    assert registry.kind_of_type("joule.temperature2d").name == "electric_joule"
    assert registry.kind_of_type("no.such.type") is None


@pytest.mark.parametrize("path", sorted(EXAMPLE_DOCUMENTS.glob("*.json")), ids=lambda p: p.stem)
def test_every_example_document_is_claimed_by_the_kind_of_its_type(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    (physics,) = data["physics"].values()
    assert physics["type"] in registry.kind_of(data).types


def test_unknown_type_error_lists_every_registered_type():
    data = copy.deepcopy(examples.EXAMPLES["soi_strip"])
    data["physics"]["em1"]["type"] = "no.such.type"
    listed = sorted(registry.physics_types())
    assert len(listed) == 7
    with pytest.raises(DocumentError) as error:
        Document.from_dict(data)
    assert str(error.value) == f"physics.em1.type 'no.such.type' not supported ({listed})"


@pytest.mark.parametrize("name", ["thermal_slab", "electric_rectangle"])
def test_run_returns_the_result_types_of_the_kind(name):
    doc = Document.from_dict(copy.deepcopy(examples.EXAMPLES[name]))
    assert isinstance(run(doc, verbose=False), registry.kind_of(doc.data).result_types)


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setattr(registry, "_KINDS", dict(registry._KINDS))


def test_register_refuses_a_second_claim_and_a_second_fallback(isolated):
    base = registry.kinds()[-1]
    with pytest.raises(ValueError, match="already claimed"):
        registry.register(registry.PhysicsKind(**{**base.__dict__, "name": "copy", "fallback": False}))
    with pytest.raises(ValueError, match="both the fallback"):
        registry.register(registry.PhysicsKind(**{**base.__dict__, "name": "copy", "types": frozenset()}))
    registry.register(base)                                  # same name: a reload replaces it
    assert registry.kinds()[-1] is base


class _EchoResult:
    def __init__(self, doc):
        self.doc = doc


def _validate_echo(doc):
    if not isinstance(doc["physics"]["p"].get("gain"), (int, float)):
        raise DocumentError("physics.p.gain must be a number")
    doc.notes = []


def test_a_new_kind_needs_no_edit_to_schema_runner_or_stages(isolated):
    registry.register(registry.PhysicsKind(
        name="test.echo", types=frozenset({"test.echo"}), precedence=50,
        validate=_validate_echo, run=lambda doc, verbose=True: _EchoResult(doc),
        summary=lambda doc: f"echo gain {doc['physics']['p']['gain']}", result_types=(_EchoResult,),
        defaults=lambda: {"study": {"type": "single"}},
        stage_refusal="{stage} does not run test.echo"))
    doc = Document.from_dict({"physics": {"p": {"type": "test.echo", "gain": 2}}})
    assert doc["study"] == {"type": "single"}                # the kind's defaults
    assert doc.summary() == "echo gain 2"
    assert isinstance(run(doc, verbose=False), _EchoResult)
    assert "test.echo" in schema.PHYSICS_TYPES
    with pytest.raises(DocumentError, match="^build_mesh does not run test.echo$"):
        build_mesh(doc)
    with pytest.raises(DocumentError, match="^solve_point does not run test.echo$"):
        solve_point(None, doc["physics"]["p"])
    with pytest.raises(DocumentError, match="gain must be a number"):
        Document.from_dict({"physics": {"p": {"type": "test.echo"}}})
