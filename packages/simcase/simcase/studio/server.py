# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""HTTP API around simcase: validate, preview mesh, run in the background, fetch results.

The browser page in ``static/`` is the only client for now; other front ends
can use the same endpoints. Everything is JSON; arrays are sent as
plain lists (fine for the mesh sizes a 2D study uses).

Imports from simcase are absolute and limited to ``simcase.__all__`` on purpose:
this file is written as an ordinary consumer of the engine, not as a part of it.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import physmat
from simcase import Document, DocumentError, build_mesh, examples, run, unit_vocabulary

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="simcase studio", version="0.1.0")

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


class DocBody(BaseModel):
    doc: dict


class MaterialPreview(BaseModel):
    name: str
    wl_min: float = 0.4
    wl_max: float = 2.0
    n_points: int = 100


# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/examples")
def list_examples():
    return {"examples": sorted(name for name, data in examples.EXAMPLES.items()
                               if all(p.get("type") != "em.cavity3d" for p in data["physics"].values()))}


@app.get("/api/examples/{name}")
def get_example(name: str):
    if name not in examples.EXAMPLES:
        raise HTTPException(404, f"no example {name}")
    doc = Document.from_dict(examples.EXAMPLES[name])
    _require_studio_physics(doc)
    return doc.data


@app.get("/api/materials")
def list_materials():
    out = []
    for n in physmat.names():
        m = physmat.get(n)
        lo, hi = m.range_um
        out.append({"name": n, "aliases": list(m.aliases), "range_um": [lo, None if hi == float("inf") else hi],
                    "source": m.source.split(";")[0], "properties": sorted(m.properties)})
    return {"materials": out}


@app.post("/api/materials/preview")
def material_preview(body: MaterialPreview):
    try:
        m = physmat.get(body.name)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    lo, hi = m.range_um
    a, b = max(body.wl_min, lo), min(body.wl_max, hi)
    if not a < b:
        raise HTTPException(400, f"material {body.name} has no data in [{body.wl_min}, {body.wl_max}] um")
    wl = np.linspace(a, b, body.n_points)
    idx = m.index(wl)
    return {"name": m.name, "wavelength": wl.tolist(), "n": idx.real.tolist(), "k": idx.imag.tolist(),
            "source": m.source}


def _require_studio_physics(doc: Document):
    if any(p.get("type") == "em.cavity3d" for p in doc["physics"].values()):
        raise HTTPException(400, "em.cavity3d is available through Python and the CLI; Studio supports 2D only")


@app.post("/api/validate")
def validate(body: DocBody):
    try:
        doc = Document.from_dict(body.doc)
    except DocumentError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "summary": doc.summary(), "doc": doc.data, "notes": doc.notes}


@app.get("/api/units")
def units():
    """The declarable units, so the page never carries a second copy of the table."""
    return unit_vocabulary()


@app.post("/api/mesh")
def mesh_preview(body: DocBody):
    try:
        doc = Document.from_dict(body.doc)
        _require_studio_physics(doc)
        model = build_mesh(doc)
    except (DocumentError, ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
    tm, region_materials = model.tri, model.region_materials
    return {"units": doc["units"],
            "nodes": tm.nodes.tolist(), "triangles": tm.triangles.tolist(), "regions": tm.regions.tolist(),
            "region_names": tm.region_names, "region_materials": region_materials,
            "stats": {"nodes": tm.num_nodes, "triangles": tm.num_triangles, "min_angle": round(tm.min_angle(), 2),
                      "quality_mean": round(float(tm.quality().mean()), 3)},
            "boundary_edges": {k: v.tolist() for k, v in tm.boundary_edges.items()}}


def _run_job(job_id: str, doc: Document):
    log: list[str] = []

    def record(msg):
        log.append(msg)
        with _jobs_lock:
            _jobs[job_id]["log"] = list(log)

    try:
        res = run(doc, verbose=False)
        for line in res.log:
            record(line)
        ng = res.group_index()
        payload = {
            "nodes": res.mesh_nodes.tolist(), "triangles": res.mesh_triangles.tolist(),
            "regions": res.mesh_regions.tolist(), "region_names": res.region_names,
            "parameter": res.parameter, "values": [float(v) for v in res.values],
            "neff": res.neff.tolist(), "group_index": None if ng is None else ng.tolist(),
            "fields": [f.T.tolist() for f in res.fields],   # per point: (modes, N)
            "timings": res.timings, "summary": res.summary(),
        }
        if res.vector_fields is not None:
            payload["vector_fields"] = [f.to_dict() for f in res.vector_fields]
        with _jobs_lock:
            _jobs[job_id].update(status="done", result=payload)
    except Exception as exc:  # report anything to the browser
        with _jobs_lock:
            _jobs[job_id].update(status="error", error=f"{type(exc).__name__}: {exc}",
                                 traceback=traceback.format_exc())


@app.post("/api/run")
def start_run(body: DocBody):
    try:
        doc = Document.from_dict(body.doc)
    except DocumentError as exc:
        raise HTTPException(400, str(exc))
    _require_studio_physics(doc)
    job_id = uuid.uuid4().hex[:8]
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(target=_run_job, args=(job_id, doc), daemon=True).start()
    return {"job": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "no such job")
        return {k: v for k, v in job.items() if k != "result"} | {"has_result": job["result"] is not None}


@app.get("/api/jobs/{job_id}/result")
def job_result(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    if job["status"] != "done":
        raise HTTPException(409, f"job is {job['status']}")
    return job["result"]


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main(argv=None):
    import argparse
    import webbrowser

    import uvicorn

    ap = argparse.ArgumentParser(prog="simcase-studio", description="browser UI for simcase models")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"simcase studio at {url}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
