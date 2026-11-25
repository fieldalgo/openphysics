# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``simcase.run(..., on_event=...)``: the search_started events of em.modes2d (job progress, slice S1).

Pre-registered checks of the job-progress design (lab notes/studio/job-progress-draft.md): J1 (results
unchanged by the callback), J3 (event order and counts against the engine's real searches), J5 (a
kind without ``accepts_on_event`` runs and is never called back) and J6 (a callback that is not
callable). The frozen documents of J1 and J3 include a 3.5 minute open run; here a coarser open
document with the group index (the same shapes, PML and two searches) stands in for it, and the
frozen run is a measured check recorded in the commit that adds this file.
"""
from __future__ import annotations

import copy
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pytest

from simcase import Document, DocumentError, physics_pml_modes, registry, run, runner

FIXTURES = Path(__file__).parent / "studio_session_fixtures"
EXAMPLES = Path(__file__).parents[2] / "examples" / "simcase"


def _open_document(group_index=True):
    """The Studio open document with two searches (strip on a substrate, PML on every edge) on a
    coarse mesh, with the group index of Also compute group index."""
    tree = json.loads((FIXTURES / "optical-document-strip-substrate-open-searches.json").read_text())
    for shape in tree["geometry"]["shapes"]:
        shape["element_size"] = "90 nm"
    tree["mesh"].update(element_size="600 nm", grading={**tree["mesh"]["grading"], "near": "90 nm", "far": "400 nm"})
    if group_index:
        tree["results"]["group_index"] = {"wavelength_step": "1 nm"}
    return tree


def _closed_document(group_index=False):
    tree = json.loads((FIXTURES / "optical-document-template-v8-1.json").read_text())
    if group_index:
        tree["results"]["group_index"] = {"wavelength_step": "1 nm"}
    return tree


def _sweep_document():
    return json.loads((EXAMPLES / "vector_slab_sweep.json").read_text())


def _counted(monkeypatch):
    """The engine's real searches: every PML eigensolve and every closed solve."""
    real = {"searches": 0}
    for module, name in ((physics_pml_modes, "solve_modes"), (physics_pml_modes, "solve_scalar_coordinates")):
        original = getattr(module, name)

        def counted(*args, _original=original, **kwargs):
            real["searches"] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, counted)
    from simcase import physics_em_modes2d
    for name in ("_solve_vector",):
        original = getattr(physics_em_modes2d, name)

        def counted(*args, _original=original, **kwargs):
            real["searches"] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(physics_em_modes2d, name, counted)
    return real


def _saved(result, tmp_path, name):
    """(summary.json without timing, every fields.npz member's dtype, shape and bytes, the log
    without the lines that print seconds) of a saved result."""
    out = result.save(tmp_path / name)
    summary = json.loads((out / "summary.json").read_text())
    summary.pop("timing", None)
    members = {}
    with zipfile.ZipFile(out / "fields.npz") as archive:
        for member in sorted(archive.namelist()):
            array = np.load(io.BytesIO(archive.read(member)), allow_pickle=False)
            if member == "metadata_json.npy":                 # the summary again, with its timing
                metadata = json.loads(str(array))
                metadata.pop("timing", None)
                members[member] = json.dumps(metadata, sort_keys=True)
            else:
                members[member] = (array.dtype.str, array.shape, array.tobytes())
    log = [line for line in (out / "log.txt").read_text().splitlines() if not re.search(r"\d s$", line)]
    return json.dumps(summary, sort_keys=True), members, log


EXPECTED_OPEN = [(solve, kind, search) for solve, kind in ((1, "study_point"), (2, "group_index"), (3, "group_index"))
                 for search in (1, 2)]


@pytest.fixture(scope="module")
def open_runs():
    """The open document run without a callback, and with one (and the engine's real searches)."""
    plain = run(Document.from_dict(_open_document()), verbose=False)
    events = []
    with pytest.MonkeyPatch.context() as monkeypatch:
        real = _counted(monkeypatch)
        called = run(Document.from_dict(_open_document()), verbose=False, on_event=events.append)
    return plain, called, events, real


def test_open_run_with_group_index_sends_one_event_per_search_in_order(open_runs):
    """J3: 3 solves of 2 searches (near the target and near t_low), in the order of the work."""
    _, _, events, real = open_runs
    assert [(e["solve"], e["solve_kind"], e["search"]) for e in events] == EXPECTED_OPEN
    for e in events:
        assert e == {"event": "search_started", "point": 1, "points": 1, "solve": e["solve"], "solves": 3,
                     "solve_kind": e["solve_kind"], "search": e["search"], "searches": 2}
    assert len(events) == real["searches"] == 6


@pytest.mark.parametrize("group_index, count", [(False, 1), (True, 3)])
def test_closed_run_sends_one_event_per_solve(monkeypatch, group_index, count):
    """J3: a closed window searches once per solve; the group index adds solves 2 and 3."""
    real = _counted(monkeypatch)
    events = []
    run(Document.from_dict(_closed_document(group_index)), verbose=False, on_event=events.append)
    assert [(e["solve"], e["solves"], e["solve_kind"], e["search"], e["searches"]) for e in events] == [
        (s, count, "study_point" if s == 1 else "group_index", 1, 1) for s in range(1, count + 1)]
    assert len(events) == real["searches"] == count


def test_sweep_sends_one_event_per_study_point(monkeypatch):
    """J3: a tracked sweep solves once per point."""
    real = _counted(monkeypatch)
    events = []
    doc = Document.from_dict(_sweep_document())
    run(doc, verbose=False, on_event=events.append)
    points = len(doc.data["study"]["values"]["values"])
    assert [(e["point"], e["points"], e["solve"], e["solves"], e["search"], e["searches"]) for e in events] == [
        (p, points, 1, 1, 1, 1) for p in range(1, points + 1)]
    assert len(events) == real["searches"] == points


def test_open_results_are_the_same_with_and_without_the_callback(tmp_path, open_runs):
    """J1: summary.json without timing, every fields.npz member and the log, bit for bit."""
    plain, called, _, _ = open_runs
    assert _saved(plain, tmp_path, "plain") == _saved(called, tmp_path, "called")


@pytest.mark.parametrize("make", [_closed_document, lambda: _closed_document(True), _sweep_document],
                         ids=["closed", "closed-group-index", "sweep"])
def test_results_are_the_same_with_and_without_the_callback(tmp_path, make):
    """J1: summary.json without timing, every fields.npz member and the log, bit for bit."""
    plain = run(Document.from_dict(make()), verbose=False)
    called = run(Document.from_dict(make()), verbose=False, on_event=lambda event: None)
    assert _saved(plain, tmp_path, "plain") == _saved(called, tmp_path, "called")


def test_an_exception_of_the_callback_ends_the_run_with_that_exception():
    """A ValueError of the callback inside a group-index solve is not taken for a failed solve."""
    raised = ValueError("stop here")

    def on_event(event):
        if event["solve"] == 2:
            raise raised
    with pytest.raises(ValueError) as caught:
        run(Document.from_dict(_closed_document(True)), verbose=False, on_event=on_event)
    assert caught.value is raised


def test_each_event_is_a_new_dict():
    events = []
    run(Document.from_dict(_closed_document(True)), verbose=False, on_event=events.append)
    assert len({id(e) for e in events}) == len(events) == 3


class _EchoResult:
    def __init__(self, doc):
        self.doc = doc


_ECHO_SLOTS = (
    {"pattern": "physics.*{test.quiet}.type", "kind": "enum", "values": ["test.quiet"], "required": True},
    {"pattern": "study", "kind": "override", "default": {"type": "single"},
     "default_reason": "structural default of test.quiet"},
)


def test_a_kind_without_accepts_on_event_runs_as_before_and_is_never_called_back(monkeypatch):
    """J5: a provider's runner that takes ``(doc, verbose)`` only; no TypeError, no event."""
    monkeypatch.setattr(registry, "_KINDS", dict(registry._KINDS))
    calls = []

    def quiet_run(doc, verbose=True):
        calls.append(verbose)
        return _EchoResult(doc)
    kind = registry.register(registry.PhysicsKind(
        name="test.quiet", types=frozenset({"test.quiet"}), precedence=50, validate=lambda doc: None,
        run=quiet_run, summary=lambda doc: "quiet", result_types=(_EchoResult,), slots=_ECHO_SLOTS))
    assert kind.accepts_on_event is False
    doc = Document.from_dict({"openphysics": "0.3", "physics": {"p": {"type": "test.quiet"}},
                              "geometry": {"length_unit": "m", "depth": None,
                                           "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}}})
    events = []
    assert isinstance(run(doc, verbose=False, on_event=events.append), _EchoResult)
    assert calls == [False] and events == []


def test_built_in_kinds_accept_events_only_for_optical_modes():
    assert {k.name for k in registry.kinds() if k.accepts_on_event} == {"em.modes2d"}


@pytest.mark.parametrize("value", [5, "print", object()])
def test_a_callback_that_is_not_callable_is_refused_before_validation(value):
    """J6: TypeError, even for a document that would not validate."""
    doc = Document.from_dict(_closed_document())
    doc.data["physics"]["em1"]["mode_count"] = -3
    with pytest.raises(TypeError, match="on_event must be a callable or None"):
        run(doc, verbose=False, on_event=value)
    with pytest.raises(DocumentError):
        run(doc, verbose=False, on_event=None)
