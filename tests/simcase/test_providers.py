# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physics providers (D1): the built-in provider, discovery, failure isolation and manifests."""
import copy
import dataclasses
import json
import sys
import textwrap
from importlib import metadata
from pathlib import Path

import numpy as np
import pytest

from simcase import Document, DocumentError, examples, providers, registry, run

from test_registry import BUILTIN, _ECHO_GEOMETRY, _ECHO_SLOTS, _EchoResult, _validate_echo

EXAMPLE_DOCUMENTS = Path(__file__).resolve().parents[2] / "examples" / "simcase"


@pytest.fixture
def fresh(monkeypatch):
    """A registry that loads its providers again on the next lookup, restored afterwards."""
    monkeypatch.setattr(registry, "_KINDS", {})
    monkeypatch.setattr(registry, "_OWNERS", {})
    monkeypatch.setattr(registry, "_loaded", False)
    monkeypatch.setattr(providers, "_PROVIDERS", [])
    return monkeypatch


def _echo_kind(name="test.echo", types=("test.echo",), **extra):
    return registry.PhysicsKind(
        name=name, types=frozenset(types), precedence=50, validate=_validate_echo,
        run=lambda doc, verbose=True: _EchoResult(doc),
        summary=lambda doc: f"echo count {doc.si['physics']['p']['mode_count']}",
        result_types=(_EchoResult,), slots=_ECHO_SLOTS, **extra)


def _echo_manifest(kinds):
    return {"kinds": {k.name: {
        "types": sorted(k.types), "field": "test", "engine": "echo", "process": "in_process",
        "ports": [{"name": "count_in", "direction": "input", "quantity": "mode_count", "unit": "1",
                   "location": "scalar", "combine": "single"},
                  {"name": "temperature", "direction": "output", "quantity": "temperature", "unit": "K",
                   "location": "node"}],
        "ui": {"label": "Echo", "group": "Tests", "range": [0, 10]}} for k in kinds}}


class FakeProvider:
    def __init__(self, name="test-echo", version="1.0", protocol=1, kinds=None, manifest=None):
        self.name, self.version, self.protocol = name, version, protocol
        self._kinds = (_echo_kind(),) if kinds is None else kinds
        self._manifest = manifest

    def kinds(self):
        return self._kinds

    def manifest(self):
        return _echo_manifest(self._kinds) if self._manifest is None else self._manifest


class FakeEntryPoint:
    """What ``providers`` reads from an ``importlib.metadata.EntryPoint``."""

    def __init__(self, name, factory, dist="test-echo-dist", value=None):
        self.name, self._factory, self.value = name, factory, value or f"tests:{name}"
        self.dist = type("Dist", (), {"metadata": {"Name": dist}})() if dist else None

    def load(self):
        if isinstance(self._factory, BaseException):
            raise self._factory
        return self._factory


def _inject(monkeypatch, *points):
    monkeypatch.setattr(providers, "_entry_points", lambda: sorted(points, key=lambda p: p.name))


def _by_name():
    return {p.name: p for p in providers.providers()}


def _echo_document():
    return {"openphysics": "0.3", "geometry": _ECHO_GEOMETRY, "physics": {"p": {"type": "test.echo", "mode_count": 2}}}


# --- the built-in provider -----------------------------------------------------------------

def test_builtin_provider_holds_todays_kinds_unchanged():
    (fem,) = [p for p in providers.providers() if p.name == providers.BUILTIN]
    assert providers.providers()[0] is fem
    assert (fem.status, fem.error, fem.distribution, fem.protocol) == ("available", None, "simcase", 1)
    from simcase import __version__
    assert fem.version == __version__
    assert set(fem.kinds) == set(BUILTIN)
    assert [k.name for k in registry.kinds()] == list(BUILTIN)       # same kinds, same order
    assert {k.name: registry._OWNERS[k.name] for k in registry.kinds()} == dict.fromkeys(BUILTIN, "openphysics-fem")
    for name, entry in fem.manifest["kinds"].items():
        assert entry["types"] == sorted(registry._KINDS[name].types)
        assert entry["process"] == "in_process"


def test_simcase_registers_the_builtin_entry_point():
    """The built-in provider is in simcase's own distribution metadata (pyproject entry point)."""
    (ep,) = [ep for ep in metadata.entry_points(group=providers.GROUP) if ep.name == providers.BUILTIN]
    assert ep.value == providers.BUILTIN_ENTRY_POINT
    assert ep.dist.metadata["Name"] == "simcase"
    assert providers._is_builtin(ep)
    assert isinstance(ep.load()(), providers.BuiltinProvider)


def test_builtin_manifest_is_valid_json_data():
    fem = providers.BuiltinProvider()
    manifest = fem.manifest()
    assert providers.check_manifest(manifest, fem.kinds()) is manifest
    assert json.loads(json.dumps(manifest)) == manifest
    assert providers.providers()[0].as_dict() == json.loads(json.dumps(providers.providers()[0].as_dict()))


def test_builtin_ports_are_registry_quantities_with_their_si_unit():
    from physmat import units
    inputs = []
    for name, entry in providers.BuiltinProvider().manifest()["kinds"].items():
        assert entry["ports"], name
        for port in entry["ports"]:
            q = units.quantity(port["quantity"])
            assert port["unit"] == q.unit
            assert "result" in q.places, (name, port)
            if port["direction"] == "input":
                inputs.append((name, port["name"], port["location"], port["combine"]))
    # the one built-in input port (multiphysics documents, D2): em.modes2d's coupled temperature
    assert inputs == [("em.modes2d", "temperature", "element", "single")]


@pytest.mark.parametrize("name", ["thermal_slab", "thermal_regions", "thermal_boundary", "transient_thermal_uniform",
                                  "transient_thermal_regions", "electric_rectangle", "joule_temperature",
                                  "elastic_plate", "elastic_regions", "thermoelastic_bar", "cavity_box",
                                  "slab_te_check"])
def test_builtin_ports_are_saved_under_their_name(name, tmp_path):
    """Every output port of a kind is an array of that name in fields.npz: a node port has one
    entry per node and an element port one per element (after the time axis of a transient
    history); a scalar port is not on the mesh. Every shipped example document was checked the
    same way when the ports were written (all 32 pass)."""
    doc = Document.from_dict(copy.deepcopy(examples.EXAMPLES[name]))
    kind = registry.kind_of(doc.data)
    entry = providers.BuiltinProvider().manifest()["kinds"][kind.name]
    run(doc, verbose=False).save(tmp_path / "out")
    with np.load(tmp_path / "out" / "fields.npz") as fields:
        nodes = fields["node_coordinates"].shape[0]
        cells = next(fields[k].shape[0] for k in ("triangles", "tetrahedra") if k in fields)
        axis = 1 if kind.name == "thermal.transient2d" else 0
        if axis:
            assert fields["temperature"].shape[0] == fields["time"].shape[0]
        for port in (p for p in entry["ports"] if p["direction"] == "output"):
            values = fields[port["name"]]
            assert np.issubdtype(values.dtype, np.number), port
            if port["location"] == "node":
                assert values.shape[axis] == nodes, port
            elif port["location"] == "element":
                assert values.shape[axis] == cells, port
            else:
                assert nodes not in values.shape and cells not in values.shape, port


def test_a_document_that_saves_no_fields_writes_no_fields_file(tmp_path):
    """The ports describe fields.npz, which ``results.save_fields: false`` leaves out."""
    data = copy.deepcopy(examples.EXAMPLES["thermal_slab"])
    data.setdefault("results", {})["save_fields"] = False
    run(Document.from_dict(data), verbose=False).save(tmp_path / "out")
    assert not (tmp_path / "out" / "fields.npz").exists()


# --- discovery -----------------------------------------------------------------------------

def test_a_fake_provider_adds_a_kind_a_document_runs_on(fresh):
    _inject(fresh, FakeEntryPoint("test-echo", lambda: FakeProvider()))
    listed = _by_name()
    assert list(listed) == ["openphysics-fem", "test-echo"]
    echo = listed["test-echo"]
    assert (echo.status, echo.version, echo.distribution, echo.kinds) == ("available", "1.0", "test-echo-dist",
                                                                          ("test.echo",))
    assert [k.name for k in registry.kinds()] == ["electric_joule", "mechanics", "thermal.transient2d",
                                                  "thermal.steady2d", "em.cavity3d", "test.echo", "em.modes2d"]
    doc = Document.from_dict(_echo_document())
    assert doc.summary() == "echo count 2"
    assert isinstance(run(doc, verbose=False), _EchoResult)
    assert echo.as_dict()["kinds"]["test.echo"]["ui"] == {"label": "Echo", "group": "Tests", "range": [0, 10]}


def test_providers_load_once_lazily_in_name_order(fresh):
    calls = []

    def factory(name):
        def make():
            calls.append(name)
            return FakeProvider(name=name, kinds=(_echo_kind(name=f"k.{name}", types=(f"t.{name}",)),))
        return make

    _inject(fresh, FakeEntryPoint("zz", factory("zz")), FakeEntryPoint("aa", factory("aa")))
    assert calls == []
    registry.kind_of_type("t.aa")
    registry.kinds()
    assert calls == ["aa", "zz"]
    assert [p.name for p in providers.providers()] == ["openphysics-fem", "aa", "zz"]


class _Boom(Exception):
    pass


def _raise():
    raise _Boom("factory failed")


def _registering_import_error():
    registry.register(_echo_kind(name="half", types=("half.type",)))      # a module's import-time register
    raise ImportError("no module named 'half_dependency'")


BROKEN = {
    "import-error": (ImportError("No module named 'missing_provider'"), "ImportError: No module named"),
    "factory-raises": (_raise, "_Boom: factory failed"),
    "returns-none": (lambda: None, "returned None"),
    "half-imported": (_registering_import_error, "ImportError: no module named 'half_dependency'"),
    "protocol-two": (lambda: FakeProvider(name="protocol-two", protocol=2,
                                          kinds=(_echo_kind(name="p2", types=("p2.type",)),)),
                     "declares protocol 2; this simcase reads protocol 1"),
    "bad-manifest": (lambda: FakeProvider(name="bad-manifest", kinds=(_echo_kind(name="bm", types=("bm.type",)),),
                                          manifest={"kinds": {"bm": {"types": ["bm.type"], "field": "test",
                                                                     "engine": "x", "process": "subprocess",
                                                                     "ports": []}}}),
                     "kinds.bm.process: 'subprocess' is not one of"),
    "claims-builtin-type": (lambda: FakeProvider(name="claims-builtin-type",
                                                 kinds=(_echo_kind(name="mine", types=("thermal.steady2d",)),)),
                            "already claimed by 'thermal.steady2d'"),
    "claims-builtin-name": (lambda: FakeProvider(name="claims-builtin-name",
                                                 kinds=(_echo_kind(name="mechanics", types=("own.type",)),)),
                            "kind 'mechanics' is already provided by 'openphysics-fem'"),
    "wrong-name": (lambda: FakeProvider(name="other-name", kinds=(_echo_kind(name="wn", types=("wn.type",)),)),
                   "calls itself 'other-name'"),
    "openphysics-fem": (lambda: FakeProvider(name="openphysics-fem",
                                             kinds=(_echo_kind(name="dup", types=("dup.type",)),)),
                        "provider name 'openphysics-fem' is already loaded"),
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_a_broken_provider_is_unavailable_by_name_and_the_rest_still_work(fresh, name):
    factory, message = BROKEN[name]
    _inject(fresh, FakeEntryPoint(name, factory), FakeEntryPoint("zz-echo", lambda: FakeProvider(name="zz-echo")))
    fem, broken, echo = providers.providers()
    assert (fem.name, broken.name, echo.name) == ("openphysics-fem", name, "zz-echo")
    assert broken.status == "unavailable"
    assert message in broken.error
    assert broken.manifest is None and broken.kinds == ()
    assert fem.status == echo.status == "available"
    assert [k.name for k in registry.kinds() if k.name != "test.echo"] == list(BUILTIN)   # nothing half-registered
    assert {k.name: set(k.types) for k in registry.kinds() if k.name != "test.echo"} == BUILTIN
    assert registry.kind_of_type("thermal.steady2d").name == "thermal.steady2d"
    assert registry.kind_of_type("test.echo").name == "test.echo"
    assert run(Document.from_dict(copy.deepcopy(examples.EXAMPLES["thermal_slab"])), verbose=False)
    json.dumps([p.as_dict() for p in providers.providers()])


def test_two_providers_claiming_one_type_the_second_in_name_order_is_refused(fresh):
    _inject(fresh, FakeEntryPoint("b-echo", lambda: FakeProvider(name="b-echo", kinds=(_echo_kind(name="b"),))),
            FakeEntryPoint("a-echo", lambda: FakeProvider(name="a-echo", kinds=(_echo_kind(name="a"),))))
    listed = _by_name()
    assert listed["a-echo"].status == "available"
    assert listed["b-echo"].status == "unavailable"
    assert "physics kind 'b' claims ['test.echo'], already claimed by 'a'" in listed["b-echo"].error
    assert registry.kind_of_type("test.echo").name == "a"


def test_an_unreadable_entry_point_list_leaves_the_builtin_kinds(fresh):
    fresh.setattr(providers, "_entry_points", _raise)
    assert [k.name for k in registry.kinds()] == list(BUILTIN)
    assert [(p.name, p.status) for p in providers.providers()] == [("openphysics-fem", "available"),
                                                                   ("(entry points)", "unavailable")]


def test_a_provider_distribution_on_the_path_is_found_through_its_metadata(fresh, tmp_path):
    """End to end through importlib.metadata: a test-only distribution with an entry point."""
    (tmp_path / "d1_fake_provider.py").write_text(textwrap.dedent("""
        from simcase import registry

        class Provider:
            name, version, protocol = "d1-fake", "0.1", 1
            kind = registry.PhysicsKind(name="d1.fake", types=frozenset({"d1.fake"}), precedence=60,
                                        validate=lambda doc: None, run=lambda doc, verbose=True: None,
                                        summary=lambda doc: "", result_types=())

            def kinds(self):
                return (self.kind,)

            def manifest(self):
                return {"kinds": {"d1.fake": {"types": ["d1.fake"], "field": "test", "engine": "none",
                                              "process": "worker", "ports": []}}}

        def provider():
            return Provider()
    """), encoding="utf-8")
    info = tmp_path / "d1_fake_provider-0.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: d1-fake-provider\nVersion: 0.1\n", encoding="utf-8")
    (info / "entry_points.txt").write_text(f"[{providers.GROUP}]\nd1-fake = d1_fake_provider:provider\n",
                                           encoding="utf-8")
    fresh.syspath_prepend(str(tmp_path))
    fresh.delitem(sys.modules, "d1_fake_provider", raising=False)
    listed = _by_name()
    assert (listed["d1-fake"].status, listed["d1-fake"].distribution) == ("available", "d1-fake-provider")
    assert registry.kind_of_type("d1.fake").name == "d1.fake"
    assert listed["d1-fake"].as_dict()["kinds"]["d1.fake"]["process"] == "worker"


def test_a_kind_registered_before_discovery_gives_way_to_the_builtin_kind(fresh):
    """A module imported before the first lookup that registers a built-in kind's name directly
    does not replace it: the built-in provider's kind is the module's own."""
    import simcase.thermal as thermal
    registry.register(dataclasses.replace(thermal.KIND, summary=lambda doc: "HIJACKED"))
    _inject(fresh)
    assert registry.kind_of_type("thermal.steady2d") is thermal.KIND
    assert Document.from_dict(copy.deepcopy(examples.EXAMPLES["thermal_slab"])).summary() != "HIJACKED"
    assert registry._OWNERS["thermal.steady2d"] == "openphysics-fem"


def test_a_failing_providers_kinds_registered_before_discovery_are_removed(fresh):
    early = _echo_kind(name="early", types=("early.type",))
    registry.register(early)                             # its module was imported before the first lookup
    _inject(fresh, FakeEntryPoint("early-echo", lambda: FakeProvider(name="early-echo", protocol=1, kinds=(early,),
                                                                     manifest={"kinds": {}})))
    (fem, broken) = providers.providers()
    assert broken.status == "unavailable" and "describes the kinds []" in broken.error
    assert registry.kind_of_type("early.type") is None
    assert [k.name for k in registry.kinds()] == list(BUILTIN)


class _BadMetadata:
    @property
    def metadata(self):
        raise KeyError("Name")


def test_unreadable_distribution_metadata_lists_that_entry_point_only(fresh):
    bad = FakeEntryPoint("bad-meta", lambda: FakeProvider(name="bad-meta"))
    bad.dist = _BadMetadata()
    _inject(fresh, bad, FakeEntryPoint("zz-echo", lambda: FakeProvider(name="zz-echo")))
    fem, broken, echo = providers.providers()
    assert (broken.name, broken.status, broken.error) == ("bad-meta", "unavailable", "KeyError: 'Name'")
    assert fem.status == echo.status == "available"


def test_an_entry_point_name_that_is_no_provider_name_is_refused(fresh):
    _inject(fresh, FakeEntryPoint("Bad Name", lambda: FakeProvider(name="Bad Name")))
    (fem, broken) = providers.providers()
    assert broken.status == "unavailable" and "must be lowercase letters" in broken.error


def test_a_builtin_provider_failure_propagates(fresh):
    """Without the built-in kinds no document runs: the error is raised, not listed."""
    fresh.setattr(providers, "_BUILTIN_MANIFEST", {**providers._BUILTIN_MANIFEST,
                                                   "mechanics": {**providers._BUILTIN_MANIFEST["mechanics"],
                                                                 "process": "thread"}})
    _inject(fresh)
    with pytest.raises(providers.ProviderError, match="kinds.mechanics.process: 'thread' is not one of"):
        registry.kinds()


def test_the_listing_is_a_copy_of_the_providers_manifest(fresh):
    manifest = _echo_manifest((_echo_kind(),))
    _inject(fresh, FakeEntryPoint("test-echo", lambda: FakeProvider(manifest=manifest)))
    listed = _by_name()["test-echo"]
    manifest["kinds"]["test.echo"]["engine"] = "changed"
    assert listed.manifest["kinds"]["test.echo"]["engine"] == "echo"


# --- the manifest --------------------------------------------------------------------------

def _valid():
    return _echo_manifest((_echo_kind(),))


def _set(manifest, path, value):
    *head, last = path
    node = manifest
    for key in head:
        node = node[key]
    if value is _DELETE:
        del node[last]
    else:
        node[last] = value
    return manifest


_DELETE = object()
_PORT = ("kinds", "test.echo", "ports", 0)

BAD_MANIFESTS = [
    (("extra",), 1, "unknown keys ['extra']"),
    (("kinds",), [], "kinds: must be an object keyed by kind name"),
    (("kinds", "test.echo", "types"), [], "kinds.test.echo.types: must be a non-empty list"),
    (("kinds", "test.echo", "types"), ["test.echo", "test.echo"], "names a type more than once"),
    (("kinds", "test.echo", "types"), ["other"], "kinds.test.echo.types: lists ['other']; the kind claims"),
    (("kinds", "test.echo", "field"), "Heat", "kinds.test.echo.field: 'Heat' must be lowercase"),
    (("kinds", "test.echo", "engine"), "", "kinds.test.echo.engine: must be a non-empty string"),
    (("kinds", "test.echo", "process"), "thread", "kinds.test.echo.process: 'thread' is not one of"),
    (("kinds", "test.echo", "ports"), {}, "kinds.test.echo.ports: must be a list"),
    (("kinds", "test.echo", "ui"), "<script>", "kinds.test.echo.ui: must be an object of data"),
    (("kinds", "test.echo", "code"), "x", "kinds.test.echo: has unknown keys ['code']"),
    (("kinds", "test.echo", "engine"), _DELETE, "kinds.test.echo: is missing ['engine']"),
    (("kinds", "test.echo", "ui", "range"), [0, float("nan")], "kinds.test.echo.ui.range[1]: is not a finite"),
    (("kinds", "test.echo", "ui", "action"), print, "kinds.test.echo.ui.action: is a builtin_function_or_method"),
    (_PORT + ("direction",), "both", "ports[0].direction: 'both' is not one of"),
    (_PORT + ("quantity",), "count", "ports[0].quantity: 'count' is not a quantity of physmat's registry"),
    (_PORT + ("unit",), "", "ports[0].unit: must be a non-empty string"),
    (_PORT + ("location",), "face", "ports[0].location: 'face' is not one of"),
    (_PORT + ("combine",), _DELETE, "ports[0]: is an input and is missing 'combine'"),
    (_PORT + ("combine",), "max", "ports[0].combine: 'max' is not one of"),
    (_PORT + ("name",), "Count In", "ports[0].name: 'Count In' must be lowercase"),
    (_PORT + ("label",), "x", "ports[0]: has unknown keys ['label']"),
    (("kinds", "test.echo", "ports", 1, "unit"), "degC", "ports[1].unit: 'degC' is not the SI unit of temperature, 'K'"),
    (("kinds", "test.echo", "ports", 1, "combine"), "sum", "ports[1].combine: is an output"),
    (("kinds", "test.echo", "ports", 1, "name"), "count_in", "ports[1].name: repeats the port name 'count_in'"),
]


@pytest.mark.parametrize("path, value, message", BAD_MANIFESTS, ids=lambda v: None)
def test_check_manifest_refuses_each_bad_entry_by_path(path, value, message):
    manifest = _set(_valid(), path, value)
    with pytest.raises(providers.ProviderError) as error:
        providers.check_manifest(manifest, (_echo_kind(),))
    assert message in str(error.value)


def test_check_manifest_compares_the_described_kinds_with_kinds():
    with pytest.raises(providers.ProviderError, match=r"describes the kinds \['test.echo'\]; the provider's"):
        providers.check_manifest(_valid(), (_echo_kind(), _echo_kind(name="second", types=("t2",))))


def test_a_manifest_round_trips_through_json():
    manifest = _valid()
    assert providers.check_manifest(manifest, (_echo_kind(),)) is manifest
    assert providers.check_manifest(json.loads(json.dumps(manifest))) == manifest
    with pytest.raises(providers.ProviderError, match="not JSON data"):
        providers.check_manifest(_set(_valid(), ("kinds", "test.echo", "types"), ("test.echo",)))
