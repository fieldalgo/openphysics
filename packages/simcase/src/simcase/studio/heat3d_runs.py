# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The experimental Studio 3D steady-heat run: ``POST /api/model3d/run`` and ``/api/model3d/runs/...``.

A run solves a ``thermal.steady3d`` document in two steps, ``mesh`` and ``solve``. The mesh step is
the 3D mesh job's (``mesh3d_jobs``): a request whose reuse key matches the component's kept mesh takes
it without a process; otherwise the job's spawn child meshes (the kind's own route choice,
``simcase.build_thermal3d_mesh``) and keeps the mesh for the component as Mesh does. The solve step
runs ``simcase.solve_thermal3d`` on a server thread, on the kept mesh read back with
``simcase.mesh3d_from_arrays``. One run at a time, and none while a mesh job runs (they share the child
slot). Cancel in the mesh step ends the child; in the solve step (which cannot be interrupted) the run
is marked cancelled and its result discarded when the solve returns.

Before any process starts the document is read as the kind reads it and the mesh estimate is checked
against ``mesh.element_count_limit``; a refusal is answered in the reader's or the estimate's words. A
connected group of regions with no fixed temperature is refused naming its regions, from galerkin's own
check. The tetrahedra and the solution stay on the server; the answers are the values, the surface
map (T at the surface nodes), a cut by an axis plane (``heat3d_slice.cut``, exact for P1), a probe,
the CSV and JSON exports and the ``thermal-steady3d-run-v1`` record.
"""

from __future__ import annotations

import base64
import copy
import csv
import hashlib
import io
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from simcase import (Document, DocumentError, GeometryError, mesh3d_from_arrays, parse_geometry, reader,
                     solve_thermal3d)
from . import heat3d_slice, mesh3d_jobs
from .bodies import RequestRefused, exact_json, read_envelope

_log = logging.getLogger("simcase.studio")

RECORD = "thermal-steady3d-run-v1"
PHYSICS = "thermal.steady3d"
STEPS = ("mesh", "solve", "done")
BUSY = "Studio is already running one 3D heat model; wait for it or cancel it."
CANCELLED = "Run cancelled; nothing kept."
UNANCHORED = ("Fixed temperature is missing on the connected group of regions {regions}: each connected group "
              "of regions needs one (galerkin: each connected component of the mesh needs a Dirichlet node)")
MAX_FINISHED = 8
RUN_PREFIX = "h3d-"
_RUN_ID = re.compile(r"h3d-[0-9a-f]{12}")
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
_GALERKIN = re.compile(r"each connected component of the mesh needs a Dirichlet node or positive convection; "
                       r"components \[([0-9, ]*)\] have neither")

Refused = mesh3d_jobs.Refused


def document_sha256(doc: dict) -> str:
    """SHA-256 of the whole document in the reuse key's canonical form (``reader.dumps``, keys sorted)."""
    text = reader.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _b64(array, dtype: str) -> str:
    return base64.b64encode(np.ascontiguousarray(array, dtype=np.dtype(dtype).newbyteorder("<")).tobytes()).decode()


@dataclass
class Run:
    id: str
    key: str
    component: str
    doc: dict = field(repr=False)
    expected: float
    status: str = "running"
    step: str = "mesh"
    started: float = field(default_factory=time.monotonic)
    ended: float | None = None
    error: dict | None = None
    reused: bool = False
    route: str | None = None
    mesh_job: str | None = None
    cancel: bool = False
    result: object = field(default=None, repr=False)
    kept: object = field(default=None, repr=False)
    values: dict | None = field(default=None, repr=False)
    unit: str = "m"
    pm_per_unit: int = 10 ** 12


def _unanchored(mesh, message: str) -> str | None:
    """galerkin's refusal of an unanchored mesh component, in region names: its own labels are
    ``connected_components`` of the tetrahedra's edge graph, recomputed here the same way."""
    found = _GALERKIN.search(message)
    if not found:
        return None
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components
    pairs = mesh.tets[:, [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]].reshape(-1, 2)
    graph = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(mesh.num_nodes,) * 2)
    _, labels = connected_components(graph, directed=False)
    groups = []
    for label in (int(v) for v in found.group(1).split(",") if v.strip()):
        tets = np.flatnonzero(labels[mesh.tets[:, 0]] == label)
        names = sorted({mesh.region_names[int(r)] for r in np.unique(mesh.regions[tets])})
        groups.append(UNANCHORED.format(regions=", ".join(repr(n) for n in names)))
    return "; ".join(groups)


class Heat3DRuns:
    """The 3D heat runs of one server: at most one running, a few finished."""

    def __init__(self, meshes: mesh3d_jobs.Mesh3DJobs, *, start_thread=None):
        self.meshes = meshes
        self.lock = threading.Lock()
        self.runs: dict[str, Run] = {}
        self._start_thread = start_thread or (lambda target, args: threading.Thread(target=target, args=args,
                                                                                    daemon=True).start())

    # -- start
    def start(self, doc: dict, component: str | None = None) -> dict:
        physics = doc.get("physics") if isinstance(doc, dict) else None
        kinds = [p.get("type") for p in physics.values() if isinstance(p, dict)] if isinstance(physics, dict) else []
        if kinds != [PHYSICS]:
            raise Refused(400, f"Run takes a {PHYSICS} document (one physics entry of type {PHYSICS!r})")
        try:
            Document.from_dict(copy.deepcopy(doc))
        except DocumentError as exc:
            raise Refused(400, str(exc), code=getattr(exc, "code", None)) from exc
        try:
            est = mesh3d_jobs.estimate(doc, component)
        except GeometryError as exc:
            raise Refused(400, str(exc), code=getattr(exc, "code", None)) from exc
        comp = est["component"]
        model_comp = parse_geometry(doc).components[comp]
        key = mesh3d_jobs.reuse_key(doc)
        run_id = RUN_PREFIX + uuid.uuid4().hex[:12]
        with self.lock:
            if any(r.status == "running" for r in self.runs.values()):
                raise Refused(429, BUSY)
            run = Run(run_id, key, comp, doc, est["seconds"], unit=str(model_comp.length_unit),
                      pm_per_unit=int(model_comp.pm_per_unit))
            kept = self.meshes.kept_for(doc, comp)
            if kept is None:
                reply = self.meshes.start(doc, component)          # 429 while a mesh job runs
                if reply["reused"]:
                    kept = self.meshes.kept_for(doc, comp)
                else:
                    run.mesh_job = reply["job"]
            if kept is not None:
                run.reused, run.kept, run.step, run.route = True, kept, "solve", kept.route
            self._prune()
            self.runs[run_id] = run
        try:
            self._start_thread(self._work, (run,))
        except BaseException:
            with self.lock:
                self.runs.pop(run_id, None)
            if run.mesh_job:
                self.meshes.cancel_job(run.mesh_job)
            raise
        return {"run": run_id, "status": "running", "reused": run.reused, "estimate": est, "key": key,
                "mesh_job": run.mesh_job}

    def _prune(self) -> None:
        finished = [k for k, r in self.runs.items() if r.status != "running"]
        for k in finished[:-MAX_FINISHED] if len(finished) > MAX_FINISHED else []:
            del self.runs[k]

    # -- the worker thread
    def _work(self, run: Run) -> None:
        try:
            if run.kept is None:
                kept = self._mesh_step(run)
                if kept is None:
                    return
                with self.lock:
                    if run.status != "running":
                        return
                    run.kept, run.route, run.step = kept, kept.route, "solve"
            self._solve_step(run)
        except Exception:
            _log.warning("3D heat run %s failed", run.id, exc_info=True)
            self._finish(run, error={"message": "The run failed unexpectedly; the server log has the details.",
                                     "code": None})

    def _mesh_step(self, run: Run):
        while True:
            if run.cancel:
                return None
            status = self.meshes.status(run.mesh_job)
            if status["status"] == "done":
                break
            if status["status"] != "running":
                self._finish(run, error=status["error"] or {"message": "Meshing ended.", "code": None})
                return None
            time.sleep(0.05)
        kept = self.meshes.kept_for(run.doc, run.component)
        if kept is None:
            self._finish(run, error={"message": "The mesh was replaced by a later one; run again.", "code": None})
        return kept

    def _solve_step(self, run: Run) -> None:
        kept = run.kept
        doc = copy.deepcopy(run.doc)
        try:
            mesh = mesh3d_from_arrays(kept.mesh_arrays, doc)
            result = solve_thermal3d(Document.from_dict(doc), mesh, verbose=False)
        except (DocumentError, GeometryError) as exc:
            self._finish(run, error={"message": str(exc), "code": getattr(exc, "code", None)})
            return
        except ValueError as exc:
            words = _unanchored(getattr(mesh, "mesh", mesh), str(exc))
            self._finish(run, error={"message": words or str(exc), "code": "E-CONTRACT" if words else None})
            return
        values = self._values(run, result, kept)
        self._finish(run, result=result, values=values)

    def _finish(self, run: Run, *, result=None, values=None, error=None) -> None:
        with self.lock:
            if run.cancel or run.status != "running":
                return                                      # a cancelled run keeps nothing
            run.ended = time.monotonic()
            if error is not None:
                run.status, run.error, run.kept = "error", error, None
                return
            run.status, run.step, run.result, run.values = "done", "done", result, values

    # -- values
    def _values(self, run: Run, result, kept) -> dict:
        mesh, T = result.mesh, np.asarray(result.temperature)
        summary = result.summary()

        def extreme(i: int, name: str) -> dict:
            tets = np.flatnonzero(np.any(mesh.tets == i, axis=1))
            return {"value": float(T[i]), "unit": "K", "node": i, "position_m": mesh.nodes[i].tolist(),
                    "region": mesh.region_names[int(mesh.regions[tets[0]])], "quantity": name}
        stats = dict(kept.stats or {})
        return {"run": run.id, "component": run.component, "document_sha256": document_sha256(run.doc),
                "heat_rate_by_selection": {k: {"value": v, "unit": "W"} for k, v in result.heat_rates_by_boundary().items()},
                "total_source": {"value": float(np.sum(result.solution.generated_heat_rate)), "unit": "W"},
                "balance_residual": summary["heat_rate_imbalance"],
                "relative_balance_residual": summary["relative_conservation_residual"],
                "temperature_min": extreme(int(np.argmin(T)), "minimum_temperature"),
                "temperature_max": extreme(int(np.argmax(T)), "maximum_temperature"),
                "mesh": {**stats, "route": run.route, "reused": run.reused, "key": run.key,
                         "tetrahedra": int(mesh.num_tets), "nodes": int(mesh.num_nodes)}}

    # -- status, cancel
    def get(self, run_id: str) -> Run:
        if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
            raise Refused(404, "no such 3D heat run")
        with self.lock:
            run = self.runs.get(run_id)
        if run is None:
            raise Refused(404, "no such 3D heat run")
        return run

    def status(self, run_id: str) -> dict:
        run = self.get(run_id)
        with self.lock:
            end = run.ended if run.ended is not None else time.monotonic()
            elapsed = end - run.started
            return {"run": run.id, "status": run.status, "step": run.step, "steps": list(STEPS),
                    "elapsed_s": round(elapsed, 3), "expected_s": run.expected,
                    "longer_than_estimate": run.status == "running" and elapsed > 2 * run.expected,
                    "reused": run.reused, "route": run.route, "error": run.error,
                    "has_result": run.status == "done", "key": run.key, "mesh_job": run.mesh_job}

    def cancel(self, run_id: str) -> dict:
        run = self.get(run_id)
        with self.lock:
            if run.status != "running":
                return {"run": run.id, "status": run.status, "cancelled": False}
            run.cancel = True
            step = run.step
            run.status, run.ended, run.kept = "cancelled", time.monotonic(), None
            run.error = {"message": CANCELLED, "code": None}
        reply = {"run": run.id, "status": "cancelled", "cancelled": True, "message": CANCELLED, "step": step}
        if step == "mesh" and run.mesh_job:
            reply["mesh"] = self.meshes.cancel_job(run.mesh_job)
        return reply

    def shutdown(self) -> None:
        with self.lock:
            running = [r.id for r in self.runs.values() if r.status == "running"]
        for run_id in running:
            self.cancel(run_id)

    def done(self, run_id: str) -> Run:
        run = self.get(run_id)
        if run.status != "done":
            raise Refused(409, f"the 3D heat run is {run.status}; it has no result")
        return run

    # -- answers
    def values(self, run_id: str) -> dict:
        return self.done(run_id).values

    def surface(self, run_id: str) -> dict:
        run = self.done(run_id)
        kept, T = run.kept, np.asarray(run.result.temperature)
        answer = kept.answer
        t_surface = T[kept.surface["surface_nodes"]]
        keep = ("component", "unit", "origin_m", "faces", "regions", "region_names", "counts", "positions",
                "indices", "triangle_faces", "triangle_regions")
        out = {k: answer[k] for k in keep if k in answer}
        out.update({"ok": True, "run": run.id, "temperature": _b64(t_surface.astype(np.float32), "f4"),
                    "temperature_min": {"value": float(t_surface.min()), "unit": "K"},
                    "temperature_max": {"value": float(t_surface.max()), "unit": "K"}})
        return out

    def _metres(self, run: Run, value) -> float:
        return float(Fraction(str(value)) * run.pm_per_unit / 10 ** 12)

    def _cut(self, run: Run, axis: str, at):
        if axis not in heat3d_slice.AXES:
            raise Refused(400, "axis: the cut plane is x, y or z = const")
        at_m = self._metres(run, at)
        nodes = np.asarray(run.result.mesh.nodes)
        a = heat3d_slice.AXES.index(axis)
        lo, hi = float(nodes[:, a].min()), float(nodes[:, a].max())
        if not lo <= at_m <= hi:
            raise Refused(400, f"cut {axis} = {at} {run.unit} is outside the mesh ({lo * 10 ** 12 / run.pm_per_unit:g} "
                               f"to {hi * 10 ** 12 / run.pm_per_unit:g} {run.unit})")
        return heat3d_slice.cut(nodes, run.result.mesh.tets, run.result.temperature, axis, at_m), at_m

    def cut(self, run_id: str, axis: str, at) -> dict:
        run = self.done(run_id)
        cut, at_m = self._cut(run, axis, at)
        origin = np.asarray(run.kept.answer["origin_m"], dtype=np.float64)
        return {"ok": True, "run": run.id, "axis": axis, "at": at, "at_m": at_m, "unit": run.unit,
                "origin_m": origin.tolist(),
                "counts": {"points": int(len(cut.points)), "triangles": int(len(cut.triangles))},
                "positions": _b64((cut.points - origin).astype(np.float32), "f4"),
                "indices": _b64(cut.triangles, "u4"), "temperature": _b64(cut.values.astype(np.float32), "f4"),
                "temperature_min": {"value": float(cut.values.min()), "unit": "K"} if len(cut.values) else None,
                "temperature_max": {"value": float(cut.values.max()), "unit": "K"} if len(cut.values) else None}

    def probe(self, run_id: str, point) -> dict:
        run = self.done(run_id)
        p = np.array([self._metres(run, v) for v in point], dtype=np.float64)
        mesh = run.result.mesh
        found = heat3d_slice.probe(mesh.nodes, mesh.tets, run.result.temperature, p)
        if found is None:
            return {"ok": False, "point": point, "point_m": p.tolist(), "unit": run.unit,
                    "refused": f"the point ({', '.join(str(v) for v in point)}) {run.unit} is outside the meshed regions"}
        return {"ok": True, "run": run.id, "point": point, "point_m": p.tolist(), "unit": run.unit,
                "temperature": {"value": found.value, "unit": "K"}, "tetrahedron": found.tetrahedron,
                "region": mesh.region_names[int(mesh.regions[found.tetrahedron])],
                "barycentric": found.barycentric.tolist()}

    # -- exports
    def _header(self, run: Run, first: str) -> list[str]:
        return [f"# {first}", f"# run: {run.id}", f"# document_sha256: {run.values['document_sha256']}"]

    def export(self, run_id: str, name: str, axis=None, at=None) -> tuple[bytes, str, str]:
        run = self.done(run_id)
        if name == "run.json":
            body = reader.dumps({"values": run.values, "document": run.doc}, ensure_ascii=True, allow_nan=False)
            return body.encode("utf-8"), "application/json", f"{run.id}.json"
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        if name == "cut.csv":
            if at is None:
                raise Refused(400, "at: the cut plane's position, in the component's length unit")
            cut, at_m = self._cut(run, axis, at)
            for line in self._header(run, f"cut plane: {axis} = {at} {run.unit} ({at_m!r} m)"):
                out.write(line + "\n")
            w.writerow(["x_m", "y_m", "z_m", "temperature_K"])
            for p, v in zip(cut.points.tolist(), cut.values.tolist()):
                w.writerow([repr(p[0]), repr(p[1]), repr(p[2]), repr(v)])
            return out.getvalue().encode("utf-8"), "text/csv", f"{run.id}-cut-{axis}.csv"
        if name == "surface.csv":
            kept = run.kept
            nodes = np.asarray(run.result.mesh.nodes)[kept.surface["surface_nodes"]]
            T = np.asarray(run.result.temperature)[kept.surface["surface_nodes"]]
            faces = {f["id"]: f for f in kept.answer["faces"]}
            first = {}
            for tri, face in zip(kept.surface["surface_triangles"].tolist(), kept.surface["surface_faces"].tolist()):
                for n in tri:
                    first.setdefault(n, face)
            for line in self._header(run, "surface nodes; face: the provenance names of the face of the node's first "
                                          "surface triangle"):
                out.write(line + "\n")
            w.writerow(["x_m", "y_m", "z_m", "temperature_K", "face"])
            for i, (p, v) in enumerate(zip(nodes.tolist(), T.tolist())):
                w.writerow([repr(p[0]), repr(p[1]), repr(p[2]), repr(v), _face_name(faces[first[i]])])
            return out.getvalue().encode("utf-8"), "text/csv", f"{run.id}-surface.csv"
        raise Refused(404, "no such export: cut.csv, surface.csv or run.json")

    def record(self, run_id: str, maps: str = "kept") -> dict:
        run = self.done(run_id)
        if maps not in ("kept", "not kept"):
            raise Refused(400, "maps: \"kept\" or \"not kept\"")
        out = {"result": RECORD, "run": run.id, "document": run.doc, "document_sha256": run.values["document_sha256"],
               "values": run.values, "mesh": run.values["mesh"], "maps": maps}
        if maps == "kept":
            out["surface"] = self.surface(run_id)
        else:
            out["counts"] = {"surface_nodes": int(len(run.kept.surface["surface_nodes"])),
                             "surface_triangles": int(len(run.kept.surface["surface_triangles"]))}
        return out


def _face_name(face: dict) -> str:
    """The face's provenance names (``feature.part.face``, ``domain.<side>``), space-separated."""
    names = face.get("names") or []
    return " ".join(sorted(names)) if names else f"face {face['id']}"


# ----------------------------------------------------------------------------- the routes

router = APIRouter()
runs: Heat3DRuns | None = None


def bind(meshes: mesh3d_jobs.Mesh3DJobs) -> Heat3DRuns:
    """The server's runs, sharing the 3D mesh jobs' child slot and kept meshes."""
    global runs
    runs = Heat3DRuns(meshes)
    return runs


def _refusal(exc: Refused):
    return JSONResponse({"detail": exc.message, **exc.extra}, status_code=exc.status, headers=NO_STORE)


def _answer(fn, *args):
    try:
        return JSONResponse(fn(*args), headers=NO_STORE)
    except Refused as exc:
        return _refusal(exc)


@router.post("/api/model3d/run")
async def model3d_run(request: Request):
    try:
        tree, found = read_envelope(await request.body(), optional=("component",))
        component = tree.get("component")
        if component is not None and not isinstance(component, str):
            raise RequestRefused("component: a component name is a string")
    except RequestRefused as exc:
        return exc.reply()
    if found:
        return JSONResponse({"detail": "; ".join(f"{d.path or '<document>'}: {d.message} ({d.code})" for d in found)},
                            status_code=400, headers=NO_STORE)
    try:
        return JSONResponse(await run_in_threadpool(runs.start, tree["doc"], component), headers=NO_STORE)
    except Refused as exc:
        return _refusal(exc)


@router.get("/api/model3d/runs/{run_id}")
def model3d_run_status(run_id: str):
    return _answer(runs.status, run_id)


@router.post("/api/model3d/runs/{run_id}/cancel")
def model3d_run_cancel(run_id: str):
    return _answer(runs.cancel, run_id)


@router.get("/api/model3d/runs/{run_id}/values")
def model3d_run_values(run_id: str):
    return _answer(runs.values, run_id)


@router.get("/api/model3d/runs/{run_id}/surface")
def model3d_run_surface(run_id: str):
    return _answer(runs.surface, run_id)


@router.get("/api/model3d/runs/{run_id}/record")
def model3d_run_record(run_id: str, maps: str = "kept"):
    try:
        return exact_json(runs.record(run_id, maps))     # the document keeps its numbers as written
    except Refused as exc:
        return _refusal(exc)


async def _body(request: Request, keys):
    tree, found = reader.parse(await request.body())
    if tree is None or found:
        raise RequestRefused("the request is not readable JSON: " + "; ".join(d.message for d in found))
    if not isinstance(tree, dict) or set(tree) - set(keys):
        raise RequestRefused(f"the request body is a JSON object with the keys {', '.join(keys)}")
    return tree


def _number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) and type(value).__name__ != "Decimal":
        raise RequestRefused(f"{what}: a number in the component's length unit")
    return value


@router.post("/api/model3d/runs/{run_id}/cut")
async def model3d_run_cut(run_id: str, request: Request):
    try:
        tree = await _body(request, ("axis", "at"))
        axis, at = tree.get("axis"), _number(tree.get("at"), "at")
        if axis not in ("x", "y", "z"):
            raise RequestRefused("axis: the cut plane is x, y or z = const")
    except RequestRefused as exc:
        return exc.reply()
    try:
        return exact_json(await run_in_threadpool(runs.cut, run_id, axis, at))
    except Refused as exc:
        return _refusal(exc)


@router.post("/api/model3d/runs/{run_id}/probe")
async def model3d_run_probe(run_id: str, request: Request):
    try:
        tree = await _body(request, ("point",))
        point = tree.get("point")
        if not isinstance(point, list) or len(point) != 3:
            raise RequestRefused("point: [x, y, z] in the component's length unit")
        point = [_number(v, "point") for v in point]
    except RequestRefused as exc:
        return exc.reply()
    try:
        return exact_json(await run_in_threadpool(runs.probe, run_id, point))
    except Refused as exc:
        return _refusal(exc)


@router.get("/api/model3d/runs/{run_id}/export/{name}")
def model3d_run_export(run_id: str, name: str, axis: str | None = None, at: str | None = None):
    try:
        if name == "cut.csv":
            if axis not in ("x", "y", "z"):
                raise Refused(400, "axis: the cut plane is x, y or z = const")
            try:
                Fraction(str(at))
            except (TypeError, ValueError, ZeroDivisionError):
                raise Refused(400, "at: the cut plane's position, a number in the component's length unit") from None
        body, media, filename = runs.export(run_id, name, axis, at)
    except Refused as exc:
        return _refusal(exc)
    return Response(body, media_type=media,
                    headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{filename}"'})
