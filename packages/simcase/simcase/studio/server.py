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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import physmat
from simcase import Document, DocumentError, build_mesh, examples, run, unit_vocabulary
from . import thermal_api as thermal
from . import transient_thermal_api as transient

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="simcase studio", version="0.1.0")

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_thermal_jobs = thermal.ThermalJobs()


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
                               if all(p.get("type") == "em.modes2d" for p in data["physics"].values()))}


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


def _headless_thermal_type(doc: Document):
    return next((p.get("type") for p in doc["physics"].values()
                 if p.get("type") in ("thermal.steady2d", "thermal.transient2d")), None)


def _require_studio_physics(doc: Document):
    if physics_type := _headless_thermal_type(doc):
        raise HTTPException(400, f'{physics_type} is headless Python/CLI only; Studio does not support heat input or results')
    if any(p.get("type") == "em.cavity3d" for p in doc["physics"].values()):
        raise HTTPException(400, "em.cavity3d is available through Python and the CLI; Studio supports 2D only")


@app.post("/api/validate")
def validate(body: DocBody):
    try:
        doc = Document.from_dict(body.doc)
        if physics_type := _headless_thermal_type(doc):
            return {'ok': False, 'error': f'Studio unsupported: {physics_type} is headless Python/CLI only'}
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



def _thermal_error(exc):
    return JSONResponse(exc.body(), status_code=exc.status, headers={"Cache-Control": "no-store"})


@app.get("/api/capabilities")
def studio_capabilities():
    caps = thermal.capabilities(_thermal_jobs.limits)
    caps[transient.KIND] = transient.capabilities()
    return caps


@app.post("/api/thermal/validate")
async def validate_thermal(body: Request):
    spec = None
    permit = None
    jobs = _thermal_jobs
    try:
        permit = jobs.ingress.acquire()
        spec = await thermal.read_request(body, jobs.limits, for_run=False)
        payload = thermal.validation_payload(spec, jobs.limits)
        return Response(payload, media_type="application/json", headers={"Cache-Control": "no-store"})
    except thermal.ThermalAPIError as exc:
        return _thermal_error(exc)
    except Exception as exc:
        return _thermal_error(thermal.ThermalAPIError(
            "invalid_document", str(exc), 400, tags=spec.tags() if spec else None))
    finally:
        if permit is not None:
            permit.release()


def _start_thermal_thread(target, args):
    """Narrow thread-start binding; tests need not patch the global threading module."""
    threading.Thread(target=target, args=args, daemon=True).start()


def _run_thermal_job(jobs, lease, doc):
    stage = "solver_failed"
    try:
        result = run(doc, verbose=False)
        stage = "invalid_result"
        encoded = thermal.capture_result(result, jobs.identity(lease), jobs.limits)
        stage = "publication_failed"
        jobs.complete(lease, encoded, result.log)
    except Exception as exc:
        try:
            jobs.fail(lease, exc, stage)
        except Exception:
            pass  # release retains a bounded publication error, or removes only this own record
        finally:
            jobs.release(lease)
    else:
        jobs.release(lease)


@app.post("/api/thermal/run")
async def start_thermal_run(body: Request):
    jobs = _thermal_jobs  # one store/config lifetime for this request and its worker
    spec = None
    lease = None
    identity = {}
    permit = None
    try:
        permit = jobs.ingress.acquire()
        spec = await thermal.read_request(body, jobs.limits, for_run=True)
        # copy() resets scale; validation restores it before the worker owns it.
        doc = spec.doc.copy()
        doc.validate()
        lease = jobs.reserve()
        token = uuid.uuid4().hex
        identity = jobs.attach(lease, "thermal-"+token, "result-"+token, spec)
        _start_thermal_thread(_run_thermal_job, (jobs, lease, doc))
        return JSONResponse(identity, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        if lease is not None:
            try:
                jobs.fail(lease, exc, "thread_start_failed")
            except Exception:
                pass  # final release is independent of error-publication success
            finally:
                jobs.release(lease)
        if isinstance(exc, thermal.ThermalAPIError):
            exc.tags = {**(spec.tags() if spec else exc.tags), **identity}
            return _thermal_error(exc)
        return _thermal_error(thermal.ThermalAPIError(
            "thread_start_failed" if lease is not None else "invalid_document",
            str(exc), 500 if lease is not None else 400,
            tags={**(spec.tags() if spec else {}), **identity}))
    finally:
        if permit is not None:
            permit.release()


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str, request: Request):
    if job_id.startswith("thermal-"):
        try:
            if request.query_params:
                raise thermal.ThermalAPIError("unsupported_query", "thermal status has no field/time selector")
            pin = _thermal_jobs.pin(job_id)
            return ThermalResponse(pin.payload, pin)
        except thermal.ThermalAPIError as exc:
            return _thermal_error(exc)
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "no such job")
        return {k: v for k, v in job.items() if k != "result"} | {"has_result": job["result"] is not None}


@app.get("/api/jobs/{job_id}/result")
async def job_result(job_id: str, request: Request):
    if job_id.startswith("thermal-"):
        try:
            if request.query_params:
                raise thermal.ThermalAPIError("unsupported_query", "steady thermal results have no field/time selector")
            pin = _thermal_jobs.pin(job_id, result=True)
            return ThermalResponse(pin.payload, pin)
        except thermal.ThermalAPIError as exc:
            return _thermal_error(exc)
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    if job["status"] != "done":
        raise HTTPException(409, f"job is {job['status']}")
    return job["result"]




class ThermalResponse(Response):
    """Drop transport references before releasing their logical allocation pins."""

    def __init__(self, payload, *leases):
        self._leases = leases
        try:
            super().__init__(payload, media_type="application/json",
                             headers={"Cache-Control": "no-store"})
        except BaseException:
            self.body = b""
            self._leases = ()
            for lease in reversed(leases):
                lease.release()
            raise

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.body = b""
            leases, self._leases = self._leases, ()
            for lease in reversed(leases):
                lease.release()


def _transient_error(exc):
    exc.tags = {"kind": transient.KIND, **exc.tags}
    return _thermal_error(exc)


@app.post("/api/thermal/transient/validate")
async def validate_transient(body: Request):
    jobs, permit, spec = _thermal_jobs, None, None
    try:
        permit = jobs.ingress.acquire()
        spec = await transient.read_request(body, jobs.limits, for_run=False)
        encoded = transient.validation_payload(spec, jobs.limits)
        return Response(encoded, media_type="application/json", headers={"Cache-Control": "no-store"})
    except thermal.ThermalAPIError as exc:
        return _transient_error(exc)
    except Exception as exc:
        return _transient_error(thermal.ThermalAPIError(
            "invalid_document", str(exc), 400, tags=spec.tags() if spec else None))
    finally:
        if permit is not None:
            permit.release()


def _run_transient_job(jobs, lease, doc):
    stage = "solver_failed"
    try:
        result = run(doc, verbose=False)
        stage = "invalid_result"
        manifest, arrays, scale = transient.capture_result(result, jobs.identity(lease), jobs.limits, doc)
        stage = "publication_failed"
        jobs.complete_transient(lease, manifest, arrays, result.log, scale)
    except Exception as exc:
        try:
            jobs.fail(lease, exc, stage)
        except Exception:
            pass
    finally:
        jobs.release(lease)


@app.post("/api/thermal/transient/run")
async def start_transient(body: Request):
    jobs, permit, spec, lease = _thermal_jobs, None, None, None
    identity = {}
    try:
        permit = jobs.ingress.acquire()
        spec = await transient.read_request(body, jobs.limits, for_run=True)
        doc = spec.doc.copy()
        doc.validate()
        lease = jobs.reserve(transient.reservation(jobs.limits))
        token = uuid.uuid4().hex
        identity = jobs.attach(lease, "thermal-transient-"+token, "result-"+token, spec)
        _start_thermal_thread(_run_transient_job, (jobs, lease, doc))
        return JSONResponse(identity, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        if lease is not None:
            try:
                jobs.fail(lease, exc, "thread_start_failed")
            except Exception:
                pass
            finally:
                jobs.release(lease)
        if isinstance(exc, thermal.ThermalAPIError):
            exc.tags = {**(spec.tags() if spec else exc.tags), **identity}
            return _transient_error(exc)
        return _transient_error(thermal.ThermalAPIError(
            "thread_start_failed" if lease is not None else "invalid_document",
            str(exc), 500 if lease is not None else 400,
            tags={**(spec.tags() if spec else {}), **identity}))
    finally:
        if permit is not None:
            permit.release()


def _transient_view(job_id, request, *, history):
    jobs, permit, pin = _thermal_jobs, None, None
    query = None
    try:
        query = transient.parse_query(request.query_params, history=history)
        pin = jobs.pin(job_id, result=True, result_id=query["result_id"])
        permit = jobs.begin_read(transient.ENCODED_BYTES)
        encoded = transient.encode_view(pin.record, query, history=history)
        permit.publish(encoded)
        return ThermalResponse(encoded, permit, pin)
    except Exception as exc:
        identity = dict(pin.record["identity"]) if pin is not None and pin.record is not None else {}
        if pin is not None:
            pin.release()
        if permit is not None:
            permit.release()
        if not isinstance(exc, thermal.ThermalAPIError):
            exc = thermal.ThermalAPIError("view_failed", str(exc), 500)
        exc.tags = {**identity, **exc.tags}
        if not identity:
            exc.tags.setdefault("requested_job", thermal.limited_text(job_id, 128))
        if query is not None:
            exc.tags.update({k: v for k, v in query.items() if k != "result_id"})
            exc.tags["requested_result_id"] = query["result_id"]
        return _transient_error(exc)


@app.get("/api/jobs/{job_id}/frame")
async def transient_frame(job_id: str, request: Request):
    return _transient_view(job_id, request, history=False)


@app.get("/api/jobs/{job_id}/history")
async def transient_history(job_id: str, request: Request):
    return _transient_view(job_id, request, history=True)


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
