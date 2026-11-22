# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Studio routes for multiphysics documents (contract D2): validate, run with progress, results.

The workspace edits a multiphysics document as the document tree itself and sends it whole.
This module reads it as an ordinary consumer of the engine: ``simcase.reader`` checks it,
``simcase.multiphysics`` runs it (its ``on_event`` progress callback feeds the job's event
list) and ``simcase.providers`` lists the installed kinds and their ports as data. Studio never
loads code from a provider. Which outputs a kind sends to couplings is the engine's to say: a
coupling from one it does not send is reported by the check (``E-CONTRACT``) like any other.

Studio edits two kinds in a multiphysics model, the ones with a coupling hook in this release:
``thermal.steady2d`` and ``em.modes2d`` (``STUDIO_TYPES``). A document with another type is
validated and refused for running with a plain reason. A document with one physics and no
coupling is a format ``"0.3"`` document, and it runs through ``simcase.run``; its reply has the
same layout as a multiphysics run's, with one group in the solve order and no couplings.

Errors follow Studio's policy (``bodies``): a refusal written for users keeps its text, a loop
that does not settle keeps its residual history, and anything else replies with the fixed
message while the traceback goes to the server log.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from simcase import Document, DocumentError, multiphysics, providers, reader, run as run_single
from .bodies import USER_FACING, diagnostics as _diagnostics, unexpected

TEMPLATE = Path(__file__).parent / "static" / "multiphysics-template.json"

#: the kinds Studio has settings for in a multiphysics model: label, the file-name prefix of a
#: new entry, and the entry a new physics starts with
STUDIO_TYPES = {
    "thermal.steady2d": {"label": "Heat transfer", "prefix": "heat",
                         "entry": {"type": "thermal.steady2d", "prescribed_temperature": {"bottom": "300 K"}}},
    "em.modes2d": {"label": "Optical modes", "prefix": "modes",
                   "entry": {"type": "em.modes2d", "formulation": "scalar", "vacuum_wavelength": "1550 nm",
                             "mode_count": 1}},
}
#: compound kinds solve their own coupling; they stay start-page templates (contract D2.2)
COMPOUND_TYPES = frozenset({"joule.steady2d", "joule.temperature2d", "mechanics.thermoelastic2d"})
SWEEP_REFUSAL = ("Sweeps of coupled models cannot run in this release. Studio checks the sweep, but running it "
                 "is refused. Choose Single run, or sweep a model with one physics.")
MAX_RUNNING = 2
MAX_FINISHED = 8


class Refused(Exception):
    """A request Studio refuses with a status and a message written for users."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class Stopped(Exception):
    """Raised from the progress callback when the user stops a run."""


# -- kinds --------------------------------------------------------------------------------------

def capabilities() -> dict:
    """The installed providers and their kinds, as data: what Add physics lists. Each type has its
    ports and whether Studio can add it to a multiphysics model, with the reason when it cannot."""
    listing = []
    for p in providers.providers():
        entry = {"name": p.name, "version": p.version, "status": p.status, "error": p.error, "types": []}
        for kind_name, kind in ((p.manifest or {}).get("kinds") or {}).items():
            for type_name in kind["types"]:
                ports = []
                for port in kind["ports"]:
                    item = {k: port[k] for k in ("name", "direction", "quantity", "unit", "location")}
                    if port["direction"] == "input":
                        item["combine"] = port.get("combine", "single")
                    ports.append(item)
                studio = STUDIO_TYPES.get(type_name)
                if studio is not None:
                    reason = None
                elif type_name in COMPOUND_TYPES:
                    reason = "solves its own coupling; start it from its template on the start page"
                else:
                    reason = "is not part of multiphysics models in Studio in this release"
                entry["types"].append({"type": type_name, "kind": kind_name, "field": kind["field"],
                                       "label": studio["label"] if studio else type_name, "ports": ports,
                                       "addable": studio is not None, "reason": reason,
                                       "prefix": studio["prefix"] if studio else None,
                                       "entry": studio["entry"] if studio else None})
        listing.append(entry)
    return {"schema_version": 1, "envelope": multiphysics.ENVELOPE, "result": multiphysics.RESULT_FORMAT,
            "providers": listing, "transfers": ["same_mesh"],     # the one transfer of D2
            "limits": {"running_jobs": MAX_RUNNING}}


def template() -> bytes:
    """The Heated silicon waveguide document, as shipped."""
    return TEMPLATE.read_bytes()


# -- validation ---------------------------------------------------------------------------------

class _Edge:
    def __init__(self, source, target):
        self.source, self.target = source, target


def derived_order(tree: dict) -> list[list[str]]:
    """The engine's solve order over the couplings that join two physics of the document; the
    other couplings are left out, so an order shows even while some coupling is wrong."""
    physics = tree.get("physics") if isinstance(tree.get("physics"), dict) else {}
    names = list(physics)
    couplings = tree.get("couplings") if isinstance(tree.get("couplings"), dict) else {}
    edges = []
    for c in couplings.values():
        if not isinstance(c, dict) or not isinstance(c.get("from"), str) or not isinstance(c.get("to"), str):
            continue
        source, target = c["from"].partition(".")[0], c["to"].partition(".")[0]
        if source in physics and target in physics and source != target:
            edges.append(_Edge(source, target))
    return multiphysics.solve_order(names, edges)


def _types(tree: dict) -> list:
    physics = tree.get("physics") if isinstance(tree.get("physics"), dict) else {}
    return [p.get("type") for p in physics.values() if isinstance(p, dict)]


def studio_refusal(tree: dict) -> str | None:
    """Why Studio does not run this document (None when it does)."""
    others = sorted({t for t in _types(tree) if t not in STUDIO_TYPES}, key=str)
    if others:
        return ("Studio runs heat transfer and optical modes in a multiphysics model; this model also has "
                + ", ".join(str(t) for t in others) + ". Run it with simcase run.")
    study = tree.get("study") if isinstance(tree.get("study"), dict) else {}
    if tree.get("openphysics") == multiphysics.ENVELOPE and study.get("type") == "sweep":
        return SWEEP_REFUSAL
    return None


def validation_payload(tree: dict, found=()) -> dict:
    """Every diagnostic of the document (reader.check, the rules of simcase validate), the derived
    solve order, Studio's run refusal (None when it runs it) and, when valid, the document as sent."""
    diagnostics = list(found)
    doc = None
    if not found:
        doc, diagnostics = reader.check(tree)
    reply = {"ok": doc is not None, "diagnostics": _diagnostics(diagnostics),
             "solve_order": derived_order(tree), "run_refusal": studio_refusal(tree)}
    if doc is not None:
        reply["doc"] = tree         # written back with reader.dumps: the digits as sent
    return reply


# -- jobs ---------------------------------------------------------------------------------------

class Jobs:
    """Multiphysics jobs of this server: one thread each, bounded in number, kept in memory."""

    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}

    def start(self, tree: dict, found, start_thread) -> dict:
        if found:
            raise Refused(400, str(DocumentError("the document is not readable JSON", diagnostics=found)))
        refusal = studio_refusal(tree)
        if refusal:
            raise Refused(400, refusal)
        try:
            doc = Document.from_dict(tree)
        except DocumentError as exc:
            raise Refused(400, str(exc))
        job_id = "mp-" + uuid.uuid4().hex[:12]
        with self.lock:
            if sum(j["status"] == "running" for j in self.jobs.values()) >= MAX_RUNNING:
                raise Refused(429, f"Studio is already running {MAX_RUNNING} multiphysics models; wait for one to "
                                   "finish.")
            finished = [k for k, j in self.jobs.items() if j["status"] != "running"]
            for key in finished[:-MAX_FINISHED] if len(finished) > MAX_FINISHED else []:
                del self.jobs[key]
            self.jobs[job_id] = {"status": "running", "events": [], "solving": None, "stop": False,
                                 "error": None, "result": None, "started": time.time()}
        start_thread(self.work, (job_id, doc))
        return {"job": job_id, "solve_order": derived_order(tree)}

    def _event(self, job_id, event):
        with self.lock:
            job = self.jobs[job_id]
            job["events"].append(event)
            if event["event"] == "physics_started":
                job["solving"] = event["physics"]
            elif event["event"] == "loop_started":
                job["solving"] = list(event["physics"])
            stop = job["stop"]
        if stop:
            raise Stopped()

    def work(self, job_id: str, doc: Document):
        emit = lambda event: self._event(job_id, event)
        try:
            if doc["openphysics"] == multiphysics.ENVELOPE:
                result = multiphysics.run(doc, verbose=False, on_event=emit)
                payload = result_payload(result)
            else:
                (name,) = list(doc.si["physics"])
                emit({"event": "physics_started", "physics": name})
                t0 = time.perf_counter()
                single = run_single(doc, verbose=False)
                emit({"event": "physics_finished", "physics": name, "seconds": time.perf_counter() - t0})
                payload = single_payload(doc, name, single)
            with self.lock:
                job = self.jobs[job_id]
                if job["stop"]:
                    raise Stopped()
                job.update(status="done", result=payload, solving=None)
        except Stopped:
            with self.lock:
                self.jobs[job_id].update(status="stopped", solving=None,
                                         error={"message": "Run stopped. No result was kept."})
        except Exception as exc:
            with self.lock:
                solving = self.jobs[job_id]["solving"]
            error = {"physics": solving}
            if isinstance(exc, multiphysics.LoopNotConverged):
                error.update(message=str(exc), code="E-LOOP-DIVERGED", residuals=list(map(float, exc.history)),
                             unit=exc.unit)
            elif isinstance(exc, USER_FACING):
                error.update(message=str(exc), diagnostics=_diagnostics(getattr(exc, "diagnostics", None) or []))
            else:
                error.update(message=unexpected(exc, "multiphysics job"))
            with self.lock:
                self.jobs[job_id].update(status="error", solving=None, error=error)

    def get(self, job_id: str) -> dict:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise Refused(404, "no such multiphysics job")
            return job

    def status(self, job_id: str, after: int = 0) -> dict:
        job = self.get(job_id)
        with self.lock:
            return {"job": job_id, "status": job["status"], "solving": job["solving"],
                    "events": job["events"][after:], "event_count": len(job["events"]),
                    "error": job["error"], "has_result": job["result"] is not None}

    def stop(self, job_id: str) -> dict:
        job = self.get(job_id)
        with self.lock:
            if job["status"] == "running":
                job["stop"] = True
            return {"job": job_id, "status": job["status"], "stopping": job["stop"]}

    def result(self, job_id: str) -> dict:
        job = self.get(job_id)
        if job["status"] != "done":
            raise Refused(409, f"the job is {job['status']}; it has no result")
        return job["result"]


# -- results ------------------------------------------------------------------------------------

def _mesh(res) -> dict:
    return {"node_coordinates": np.asarray(res.node_coordinates).tolist(), "field_units": {"node_coordinates": "m"},
            "triangles": np.asarray(res.triangles).tolist(), "regions": np.asarray(_regions(res)).tolist(),
            "region_names": list(res.region_names)}


def _regions(res):
    return res.regions if hasattr(res, "regions") else res.triangle_regions


def _physics_payload(type_name: str, res) -> dict:
    summary = json.loads(json.dumps(res.summary(), default=str))
    if type_name not in ("thermal.steady2d", "em.modes2d"):    # a kind without Studio views: its summary
        return {"type": type_name, "summary": summary}
    if type_name == "thermal.steady2d":
        t = np.asarray(res.temperature, dtype=float)
        return {"type": type_name, "temperature": {"unit": "K", "location": "node", "values": t.tolist()},
                "range": {"min": float(t.min()), "max": float(t.max()), "unit": "K"}, "summary": summary}
    out = {"type": type_name, "effective_index": summary["effective_index"],
           "vacuum_wavelength": summary["vacuum_wavelength"], "summary": summary}
    coupled = getattr(res, "coupled_inputs", None) or {}
    if "temperature" in coupled:
        n = np.asarray(coupled["refractive_index"])[0]
        out["coupled"] = {"temperature": {"unit": "K", "location": "element",
                                          "values": np.asarray(coupled["temperature"], dtype=float).tolist()},
                          "refractive_index": {"location": "element", "n": n.real.tolist(),
                                               "k": n.imag.tolist() if np.iscomplexobj(n) else None}}
    return out


def result_payload(result) -> dict:
    summary = result.summary()
    first = next((r for r in result.results.values() if hasattr(r, "node_coordinates")), None)
    return {"result": summary["result"], "name": summary["name"], "solve_order": summary["solve_order"],
            "couplings": summary["couplings"], "loops": summary["loops"], "timing": summary["timing"],
            "diagnostics": summary["diagnostics"], "mesh": None if first is None else _mesh(first),
            "physics": {name: _physics_payload(result.doc.si["physics"][name]["type"], r)
                        for name, r in result.results.items()}}


def single_payload(doc: Document, name: str, res) -> dict:
    """A one-physics document's result in the layout of a multiphysics reply."""
    summary = json.loads(json.dumps(res.summary(), default=str))
    return {"result": summary.get("result_format") or summary.get("field_layout"), "name": doc.si.get("name"),
            "solve_order": [[name]], "couplings": {}, "loops": [], "timing": {},
            "diagnostics": [d.as_dict() for d in doc.diagnostics], "mesh": _mesh(res),
            "physics": {name: _physics_payload(doc.si["physics"][name]["type"], res)}}
