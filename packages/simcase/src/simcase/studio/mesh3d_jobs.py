# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The experimental Studio 3D mesh job: the ``thermal.steady3d`` kind's mesh (``simcase.build_thermal3d_mesh``:
``meshine.extrude`` for a lone slab ``layers`` component, else ``simcase.build_mesh3d``) in a cancellable
child process. The child also writes the whole mesh as ``simcase.mesh3d_to_arrays`` arrays
(``mesh.npz``), which a later 3D heat run (``heat3d_runs``) solves on.

meshloom cannot be interrupted, and on some thin inputs it does not return at all, so the mesh is
made in a child process (``multiprocessing`` with the ``spawn`` context on every platform) that
Cancel terminates. The child writes the mesh as NumPy arrays under fixed names into a temporary
directory the parent made; the parent reads them back and removes the directory, also after a
cancel or a failure. One 3D mesh job runs at a time per server.

Every job is preceded by the ``I-MESH-ESTIMATE`` estimate (``simcase.estimate_mesh3d``): above
``mesh.element_count_limit`` the request is refused in the estimate's own words before any
process starts. The expected time is the estimate at 0.6 ms per tetrahedron.

The server keeps the latest mesh of each component, keyed by the SHA-256 of the canonical
``geometry`` and ``mesh`` blocks (``reuse_key``), for the life of the server process; a request
whose key matches is answered from it without meshing again. The tetrahedra stay on the server;
the answer carries the mesh's surface only (``surface_answer``).
"""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import multiprocessing
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from simcase import (GeometryError, Mesh3DResult, build_thermal3d_mesh, display_complex3d, estimate_mesh3d,
                     mesh3d_to_arrays, parse_geometry, reader)

_log = logging.getLogger("simcase.studio")

BUSY = "Studio is already meshing one 3D model; wait for it or cancel it."
CANCELLED = "Meshing cancelled; nothing kept."
#: how long Cancel waits for the child to end after terminate, then after kill (s)
TERMINATE_WAIT = 1.0
KILL_WAIT = 1.0
#: the steps Studio knows, in order; the status answers the current one
STEPS = ("forming", "meshing", "checking", "ready")
#: finished jobs kept for their status and result; older ones are freed
MAX_FINISHED = 8
#: components whose latest mesh is kept for reuse; the least recently made goes first
MAX_KEPT = 4
#: the files the child writes: fixed names only, never anything from a request
ARRAYS = ("nodes", "tetrahedra", "tetrahedron_regions", "surface_nodes", "surface_triangles",
          "surface_faces", "surface_regions", "quality")
SUMMARY = "summary.json"
#: the whole mesh as ``simcase.mesh3d_to_arrays`` arrays (a later Run solves on it)
MESH = "mesh.npz"
JOB_PREFIX = "m3d-"


def reuse_key(doc: dict) -> str:
    """SHA-256 of the canonical ``geometry`` and ``mesh`` blocks: keys sorted, no spaces, ASCII,
    numbers as written (``reader.dumps``), so a change of either block changes the key."""
    blocks = {"geometry": doc.get("geometry"), "mesh": doc.get("mesh")}
    text = reader.dumps(blocks, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate(doc: dict, component: str | None = None) -> dict:
    """The ``I-MESH-ESTIMATE`` answer of a document's 3d component, without meshing; raises
    ``GeometryError`` (``E-MESH-ESTIMATE`` above the limit, in the estimate's words)."""
    found = estimate_mesh3d(doc, component)
    (info,) = found.diagnostics
    return {"code": info.code, "message": info.message, "component": found.component,
            "tetrahedra": found.tetrahedra, "limit": found.limit, "seconds": found.seconds,
            "route": found.route, "count": found.count}


# ----------------------------------------------------------------------------- the child

def _quality(nodes: np.ndarray, tets: np.ndarray) -> np.ndarray:
    """q = 3 inradius / circumradius of every tetrahedron (1 for the regular one), the shape
    measure meshloom's documentation grades its meshes with."""
    p = nodes[tets]
    a, b, c, d = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
    volume = np.abs(np.einsum("ij,ij->i", b - a, np.cross(c - a, d - a))) / 6.0
    area = sum(0.5 * np.linalg.norm(np.cross(q - o, r - o), axis=1) for o, q, r in ((a, b, c), (a, b, d), (a, c, d), (b, c, d)))
    inradius = 3.0 * volume / area
    ln = lambda u, v: np.linalg.norm(u - v, axis=1)
    x, y, z = ln(a, b) * ln(c, d), ln(a, c) * ln(b, d), ln(a, d) * ln(b, c)
    s = np.clip((x + y + z) * (x + y - z) * (x - y + z) * (-x + y + z), 0.0, None)
    circumradius = np.sqrt(s) / (24.0 * volume)
    return 3.0 * inradius / circumradius


def _side_regions(cx):
    names = list(cx.region_names())
    void = {c.region for c in cx.cells if c.void}
    side_region = []
    for face in cx.faces:
        sides = [sorted({cx.cells[c].region for c in side} - void) for side in face.sides]
        region = (sides[1] or sides[0] or [None])[0]
        side_region.append(-1 if region is None else names.index(region))
    return names, side_region


def _surface(result):
    """The mesh's exterior and interface triangles, sorted by complex face id: their nodes
    (renumbered), triangles, face ids and the region index of each: the plus side's region, else
    the minus side's (the side the 3D view colours a face by), never a void one."""
    names, side_region = _side_regions(result.complex)
    order = sorted(range(len(result.face_of_facet)), key=lambda fi: (result.face_of_facet[fi], fi))
    parts = [np.asarray(result.facet_faces[fi], dtype=np.int64).reshape(-1, 3) for fi in order]
    faces = np.concatenate([np.full(len(t), result.face_of_facet[fi], dtype=np.int64) for fi, t in zip(order, parts)])
    triangles = np.concatenate(parts)
    used, local = np.unique(triangles, return_inverse=True)
    regions = np.array([side_region[f] for f in faces.tolist()], dtype=np.int64)
    return used, local.reshape(-1, 3), faces, regions, names


def _surface_extrude(mesh, cx):
    """``_surface`` of a ``meshine.extrude`` mesh (a lone slab component): its exterior and interface
    triangles, each given the complex face (``display_complex3d``'s, all axis-aligned) whose plane
    holds it and whose polygon holds its centroid, sorted by face id (stable)."""
    from .model3d_api import _rectangles
    names, side_region = _side_regions(cx)
    parts = [np.asarray(t, dtype=np.int64).reshape(-1, 3) for _, t in sorted(mesh.tagged_faces.items())]
    parts += [np.asarray(t, dtype=np.int64).reshape(-1, 3) for _, t in sorted(mesh.interfaces.items())]
    triangles = np.concatenate(parts)
    p = np.asarray(mesh.nodes, dtype=np.float64)[triangles]
    flat = np.array([[np.all(p[i, :, a] == p[i, 0, a]) for a in range(3)] for i in range(len(p))])
    centre = p.mean(axis=1) * 1e12                          # pm
    plane = {}
    for face in cx.faces:
        plane.setdefault((face.axis, face.coord), []).append((face.index, _rectangles(face)))
    faces = np.full(len(triangles), -1, dtype=np.int64)
    for i in range(len(triangles)):
        axis = int(np.flatnonzero(flat[i])[0])
        coord = round(float(p[i, 0, axis]) * 1e12)
        ua, va = (k for k in range(3) if k != axis)
        cu, cv = centre[i, ua], centre[i, va]
        for index, rects in plane.get((axis, coord), []):
            if any(u0 <= cu <= u1 and v0 <= cv <= v1 for u0, u1, v0, v1 in rects):
                faces[i] = index
                break
    if (faces < 0).any():
        raise GeometryError(f"internal: {int((faces < 0).sum())} extrude mesh triangles lie on no face of the complex")
    order = np.argsort(faces, kind="stable")
    faces, triangles = faces[order], triangles[order]
    used, local = np.unique(triangles, return_inverse=True)
    regions = np.array([side_region[f] for f in faces.tolist()], dtype=np.int64)
    return used, local.reshape(-1, 3), faces, regions, names


def _write(outdir: Path, arrays: dict, summary: dict) -> None:
    for name in ARRAYS:
        np.save(outdir / f"{name}.npy", arrays[name], allow_pickle=False)
    (outdir / SUMMARY).write_text(json.dumps(summary, ensure_ascii=True, allow_nan=False), encoding="utf-8")


def child(doc: dict, component: str | None, outdir: str, conn) -> None:
    """The child process: form the complex, mesh, check, write the arrays; report each step."""
    out = Path(outdir)
    try:
        conn.send(("step", "forming"))
        cx = display_complex3d(parse_geometry(doc), component)
        conn.send(("step", "meshing"))
        built = build_thermal3d_mesh(doc, component)       # the thermal.steady3d kind's route choice
        conn.send(("step", "checking"))
        if isinstance(built, Mesh3DResult):
            mesh, route = built.mesh, ("meshloom" if built.complex is not None else "builder")
            used, triangles, faces, regions, names = _surface(built)
            component_name, estimate, notes = built.complex.component, float(built.estimate), built.diagnostics
        else:
            mesh, route = built, "extrude"
            used, triangles, faces, regions, names = _surface_extrude(mesh, cx)
            found = estimate_mesh3d(doc, component)
            component_name, estimate, notes = cx.component, float(found.tetrahedra), list(found.diagnostics)
        nodes, tets = np.asarray(mesh.nodes, dtype=np.float64), np.asarray(mesh.tets, dtype=np.int64)
        quality = _quality(nodes, tets)
        summary = {"component": component_name, "region_names": names, "route": route,
                   "mesh_region_names": list(mesh.region_names), "estimate": estimate,
                   "diagnostics": [d.message for d in notes],
                   "stats": {"nodes": int(len(nodes)), "tetrahedra": int(len(tets)),
                             "regions": int(len(mesh.region_names)),
                             "quality_min": float(quality.min()), "quality_median": float(np.median(quality)),
                             "surface_triangles": int(len(triangles))}}
        _write(out, {"nodes": nodes, "tetrahedra": tets, "tetrahedron_regions": np.asarray(mesh.regions, dtype=np.int64),
                     "surface_nodes": used, "surface_triangles": triangles, "surface_faces": faces,
                     "surface_regions": regions, "quality": quality}, summary)
        np.savez(out / MESH, **mesh3d_to_arrays(built, doc, component))
        conn.send(("done", None))
    except GeometryError as exc:
        conn.send(("error", {"message": str(exc), "code": getattr(exc, "code", None)}))
    except Exception as exc:  # the parent logs it; the page gets the fixed message
        conn.send(("error", {"message": None, "detail": f"{type(exc).__name__}: {exc}"}))
    finally:
        conn.close()


# ----------------------------------------------------------------------------- the parent

class Refused(Exception):
    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


@dataclass
class Kept:
    """The latest mesh of a component: its key, the tetrahedra (server only) and the answer."""
    key: str
    component: str
    nodes: np.ndarray
    tetrahedra: np.ndarray
    tetrahedron_regions: np.ndarray
    region_names: list
    answer: dict
    mesh_arrays: dict = field(default=None, repr=False)     # simcase.mesh3d_to_arrays (server only)
    route: str | None = None
    surface: dict = field(default=None, repr=False)         # surface_nodes, _triangles, _faces, _regions
    stats: dict = field(default=None)


@dataclass
class Job:
    id: str
    key: str
    component: str
    expected: float
    doc: dict = field(repr=False)
    status: str = "running"
    step: str = "forming"
    started: float = field(default_factory=time.monotonic)
    ended: float | None = None
    error: dict | None = None
    reused: bool = False
    process: object = field(default=None, repr=False)
    conn: object = field(default=None, repr=False)
    tmpdir: str | None = None
    cancel: bool = False
    pid: int | None = None


def remove_tree(path: str | None) -> bool:
    """Remove a job's temporary directory; on Windows a just-ended child can hold a file open for a
    moment, so retry briefly. Whether it is gone."""
    if not path:
        return True
    for _ in range(20):
        shutil.rmtree(path, ignore_errors=True)
        if not Path(path).exists():
            return True
        time.sleep(0.05)
    _log.warning("3D mesh job directory %s could not be removed", path)
    return False


def _stop(process) -> None:
    """End the child: terminate, then kill if it is still there; reap it."""
    if process is None or process.pid is None:      # never started
        return
    if process.is_alive():
        process.terminate()
        process.join(TERMINATE_WAIT)
    if process.is_alive():
        process.kill()
        process.join(KILL_WAIT)
    else:
        process.join(0)


class Mesh3DJobs:
    """The 3D mesh jobs of one server: at most one running, a few finished, the kept meshes."""

    def __init__(self, *, context=None, start_thread=None):
        self.ctx = context or multiprocessing.get_context("spawn")
        self.lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.kept: dict[str, Kept] = {}
        self.processes_started = 0
        self._start_thread = start_thread or (lambda target, args: threading.Thread(target=target, args=args,
                                                                                    daemon=True).start())
        atexit.register(self.shutdown)          # a server that exits leaves no child and no directory

    # -- start
    def start(self, doc: dict, component: str | None) -> dict:
        try:
            est = estimate(doc, component)      # refuses above the limit: no process starts
        except GeometryError as exc:
            raise Refused(400, str(exc), code=getattr(exc, "code", None)) from exc
        key = reuse_key(doc)
        comp = est["component"]
        job_id = JOB_PREFIX + uuid.uuid4().hex[:12]
        with self.lock:
            kept = self.kept.get(comp)
            if kept is not None and kept.key == key:
                self._prune()
                self.jobs[job_id] = Job(job_id, key, comp, est["seconds"], doc, status="done", step="ready",
                                        ended=time.monotonic(), reused=True)
                return {"job": job_id, "status": "done", "reused": True, "estimate": est, "key": key}
            if any(j.status == "running" for j in self.jobs.values()):
                raise Refused(429, BUSY)
            self._prune()
            job = Job(job_id, key, comp, est["seconds"], doc)
            self.jobs[job_id] = job
            try:
                job.tmpdir = tempfile.mkdtemp(prefix="openphysics-mesh3d-")
                receive, send = self.ctx.Pipe(duplex=False)
                job.process = self.ctx.Process(target=child, args=(doc, comp, job.tmpdir, send), daemon=True,
                                               name=f"openphysics-mesh3d-{job_id}")
                job.process.start()
                send.close()
                job.conn, job.pid = receive, job.process.pid
                self.processes_started += 1
                job.started = time.monotonic()
            except BaseException:
                del self.jobs[job_id]
                _stop(job.process)
                remove_tree(job.tmpdir)
                raise
        self._start_thread(self._watch, (job,))
        return {"job": job_id, "status": "running", "reused": False, "estimate": est, "key": key}

    def _prune(self) -> None:
        finished = [k for k, j in self.jobs.items() if j.status != "running"]
        for k in finished[:-MAX_FINISHED] if len(finished) > MAX_FINISHED else []:
            del self.jobs[k]

    # -- the watcher of one job
    def _watch(self, job: Job) -> None:
        """Follow the child's messages; on its end read the arrays, stop the child and remove the
        directory, and only then publish the outcome, so a finished job has nothing on disk."""
        kept, outcome = None, ("ended", None)
        try:
            while True:
                if job.cancel:
                    return                              # cancel_job stops the child and cleans up
                try:
                    ready = job.conn.poll(0.1)
                    message = job.conn.recv() if ready else None
                except (EOFError, OSError):
                    break
                if message is not None:
                    kind, value = message
                    if kind != "step":
                        outcome = (kind, value)
                        break
                    with self.lock:
                        if job.status == "running":
                            job.step = value
                elif not job.process.is_alive() and not job.conn.poll(0):
                    break
            if outcome[0] == "done" and not job.cancel:
                kept = self._read(job)
        except Exception:
            _log.warning("3D mesh job %s: reading its result failed", job.id, exc_info=True)
            kept, outcome = None, ("error", {"message": None, "detail": "reading the result failed"})
        finally:
            self._cleanup(job)
        with self.lock:
            if job.cancel or job.status != "running":
                return
            job.ended, job.doc = time.monotonic(), None
            if kept is not None:
                self.kept.pop(job.component, None)
                self.kept[job.component] = kept
                while len(self.kept) > MAX_KEPT:
                    del self.kept[next(iter(self.kept))]
                job.status, job.step = "done", "ready"
                return
            job.status = "error"
            value = outcome[1] or {}
            if outcome[0] == "error" and value.get("message"):
                job.error = {"message": value["message"], "code": value.get("code")}
                return
            if outcome[0] == "error":
                _log.warning("3D mesh job %s failed: %s", job.id, value.get("detail"))
                job.error = {"message": "Meshing failed unexpectedly; the server log has the details.", "code": None}
            else:
                job.error = {"message": f"The meshing process ended unexpectedly (exit code {job.process.exitcode}).",
                             "code": None}

    def _cleanup(self, job: Job) -> None:
        if job.cancel:
            return                                      # cancel_job owns the process and directory
        _stop(job.process)
        try:
            job.conn.close()
        except Exception:
            pass
        remove_tree(job.tmpdir)

    def _read(self, job: Job) -> Kept:
        out = Path(job.tmpdir)
        arrays = {name: np.load(out / f"{name}.npy", allow_pickle=False) for name in ARRAYS}
        summary = json.loads((out / SUMMARY).read_text(encoding="utf-8"))
        with np.load(out / MESH, allow_pickle=False) as f:
            mesh_arrays = {k: f[k] for k in f.files}
        answer = surface_answer(job.doc, job.component, arrays, summary, job.key)
        return Kept(job.key, job.component, arrays["nodes"], arrays["tetrahedra"], arrays["tetrahedron_regions"],
                    summary["mesh_region_names"], answer, mesh_arrays, summary["route"],
                    {k: arrays[k] for k in ("surface_nodes", "surface_triangles", "surface_faces", "surface_regions")},
                    summary["stats"])

    # -- status, cancel, result
    def get(self, job_id: str) -> Job:
        with self.lock:
            job = self.jobs.get(job_id)
        if job is None:
            raise Refused(404, "no such 3D mesh job")
        return job

    def status(self, job_id: str) -> dict:
        job = self.get(job_id)
        with self.lock:
            end = job.ended if job.ended is not None else time.monotonic()
            elapsed = end - job.started
            return {"job": job.id, "status": job.status, "step": job.step, "steps": list(STEPS),
                    "elapsed_s": round(elapsed, 3), "expected_s": job.expected,
                    "longer_than_estimate": job.status == "running" and elapsed > 2 * job.expected,
                    "reused": job.reused, "error": job.error, "has_result": job.status == "done", "key": job.key}

    def cancel_job(self, job_id: str) -> dict:
        job = self.get(job_id)
        with self.lock:
            if job.status != "running":
                return {"job": job.id, "status": job.status, "cancelled": False}
            job.cancel = True
            job.status, job.step, job.ended, job.doc = "cancelled", None, time.monotonic(), None
            job.error = {"message": CANCELLED, "code": None}
        _stop(job.process)
        remove_tree(job.tmpdir)
        return {"job": job.id, "status": "cancelled", "cancelled": True, "message": CANCELLED,
                "exited": job.process is None or not job.process.is_alive()}

    def result(self, job_id: str) -> dict:
        job = self.get(job_id)
        if job.status != "done":
            raise Refused(409, f"the 3D mesh job is {job.status}; it has no mesh")
        with self.lock:
            kept = self.kept.get(job.component)
        if kept is None or kept.key != job.key:
            raise Refused(410, "this mesh was replaced by a later one of the same component; mesh again")
        return kept.answer

    def kept_for(self, doc: dict, component: str) -> Kept | None:
        """The kept mesh of a component when its key matches the document (the later Run's reuse)."""
        with self.lock:
            kept = self.kept.get(component)
        return kept if kept is not None and kept.key == reuse_key(doc) else None

    def shutdown(self) -> None:
        with self.lock:
            running = [j for j in self.jobs.values() if j.status == "running"]
        for job in running:
            self.cancel_job(job.id)


# ----------------------------------------------------------------------------- the answer

def _b64(array, dtype: str) -> str:
    import base64
    return base64.b64encode(np.ascontiguousarray(array, dtype=np.dtype(dtype).newbyteorder("<")).tobytes()).decode()


def surface_answer(doc: dict, component: str, arrays: dict, summary: dict, key: str) -> dict:
    """The mesh answer: the display answer's faces, regions and frame (so picking gives the same
    face names) with the mesh's surface triangles in place of the display triangles, mesh edges,
    the region index of each triangle and the stats. No tetrahedron is sent."""
    from .model3d_api import display_view
    view = display_view(doc, component)
    origin = np.asarray(view["origin_m"], dtype=np.float64)
    nodes = arrays["nodes"][arrays["surface_nodes"]] - origin
    triangles, faces, regions = arrays["surface_triangles"], arrays["surface_faces"], arrays["surface_regions"]
    counts = np.bincount(faces, minlength=len(view["faces"])) if len(faces) else np.zeros(len(view["faces"]), int)
    first = np.concatenate([[0], np.cumsum(counts)[:-1]]) if len(counts) else counts
    for f in view["faces"]:
        f["first_triangle"], f["triangle_count"] = int(first[f["id"]]), int(counts[f["id"]])
    edges = np.sort(np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), axis=1)
    owner = np.concatenate([faces, faces, faces])
    edges, where = np.unique(edges, axis=0, return_index=True)
    stats = summary["stats"]
    view.update({
        "mesh": True, "key": key, "region_names": summary["region_names"],
        "counts": {"faces": len(view["faces"]), "triangles": int(len(triangles)), "vertices": int(len(nodes)),
                   "edges": int(len(edges))},
        "positions": _b64(nodes.astype(np.float32), "f4"), "indices": _b64(triangles, "u4"),
        "triangle_faces": _b64(faces, "u4"), "triangle_regions": _b64(regions, "i4"),
        "edge_indices": _b64(edges, "u4"), "edge_faces": _b64(owner[where], "u4"),
        "stats": stats, "estimate": summary["estimate"], "diagnostics": summary["diagnostics"],
    })
    view.pop("edges", None)
    view.pop("summary", None)
    return view
