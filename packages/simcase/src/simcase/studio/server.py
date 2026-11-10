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

import json
import logging
import sys
import threading
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import physmat
from simcase import (__version__, Document, DocumentError, SubspaceSweepResult, build_mesh, examples, run,
                     unit_vocabulary)
from . import thermal_api as thermal
from . import thermal_regions_api as regions
from . import transient_thermal_api as transient
from . import security
from . import geometry_api

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="simcase studio", version=__version__)

_workspace_instance = uuid.uuid4().hex
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_MAX_RUNNING_JOBS = 4    # optical solves at once; more get 429
_MAX_FINISHED_JOBS = 16  # newest finished optical jobs kept; older ones are freed
_log = logging.getLogger("simcase.studio")

# Hosts a browser may address besides loopback; ``main`` adds an explicit --host.
_extra_hosts: set[str] = set()
_csp = security.content_security_policy(security.inline_script_hashes(STATIC / "index.html"))
app.add_middleware(security.StudioGuard, csp=_csp, extra_hosts=_extra_hosts)
# The interactive API docs load Swagger UI from a CDN, which the policy forbids.
app.router.routes[:] = [r for r in app.router.routes
                        if getattr(r, "path", None) not in ("/docs", "/docs/oauth2-redirect", "/redoc")]
_thermal_jobs = thermal.ThermalJobs()
_region_limits = regions.RegionLimits()


class DocBody(BaseModel):
    doc: dict


class MaterialPreview(BaseModel):
    """A physmat refractive index over a vacuum wavelength interval in metres (SI)."""
    name: str                                   # "physmat:<Name>"
    vacuum_wavelength_minimum: float = 4e-7
    vacuum_wavelength_maximum: float = 2e-6
    point_count: int = 100


#: the optical window of the workspace adapters, its element sizes and wavelength band: quantity
#: strings under registry names (format 0.3 values), as the workspace builder writes them
_DOMAIN_UM = {"xmin": "-1.5 um", "xmax": "1.5 um", "ymin": "-1.2 um", "ymax": "1.2 um"}
_DOMAIN_NM = {"xmin": "-1500 nm", "xmax": "1500 nm", "ymin": "-1200 nm", "ymax": "1200 nm"}
_SETTINGS = {"domain": _DOMAIN_UM, "boundary": "PEC", "mode_count": 2}
_WAVELENGTH_RANGE = ["1400 nm", "1700 nm"]
_CORE_ELEMENT_SIZE_RANGE = ["20 nm", "60 nm"]
_V4_MATERIALS = {"Silicon": "physmat:Si", "Silicon nitride": "physmat:Si3N4", "Silica": "physmat:SiO2",
                 "Air": "physmat:vacuum"}


# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/workspace")
@app.get("/workspace/")
def workspace_index():
    return FileResponse(STATIC / "workspace.html", headers={"Cache-Control": "no-store"})


@app.get("/workspace-assets/{filename}")
def workspace_asset(filename: str):
    assets = {path.name: path for path in STATIC.glob("workspace-*.mjs")}
    assets["workspace.css"] = STATIC / "workspace.css"
    path = assets.get(filename)
    if path is None:
        raise HTTPException(404, "Unknown workspace asset")
    mime = "text/css" if path.suffix == ".css" else "text/javascript"
    return FileResponse(path, media_type=mime,
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


# The optical adapters write format 0.3 documents and read the section 5.3.4 result names, so each
# capability names its family's next adapter version (optical-fixed-v1 -> v2, optical-rectangle-v2
# and -v3 -> v4 and v5, optical-shapes-v4 and -v5 -> v6 and v7), and its values are quantity
# strings under registry names. The endpoint paths and schema versions stay.

@app.get("/api/workspace/capabilities")
def workspace_capabilities():
    return JSONResponse({
        "schema_version": 1, "adapter": "optical-fixed-v2", "simcase_version": __version__,
        "optical": True, "coupled": False,
        "settings": {"core_height": "220 nm", "vacuum_wavelength": "1550 nm", "core_element_size": "30 nm",
                     **_SETTINGS},
    }, headers={"Cache-Control": "no-store"})


@app.get("/api/workspace/capabilities/v2")
def workspace_capabilities_v2():
    return JSONResponse({
        "schema_version": 2, "adapter": "optical-rectangle-v4", "simcase_version": __version__,
        "server_instance": _workspace_instance,
        "optical": True, "coupled": False, "core_height_range": ["100 nm", "500 nm"],
        "settings": {"vacuum_wavelength": "1550 nm", "core_element_size": "30 nm", **_SETTINGS},
    }, headers={"Cache-Control": "no-store"})


@app.get("/api/workspace/capabilities/v3")
def workspace_capabilities_v3():
    return JSONResponse({
        "schema_version": 3, "adapter": "optical-rectangle-v5", "simcase_version": __version__,
        "server_instance": _workspace_instance,
        "optical": True, "coupled": False, "core_height_range": ["100 nm", "500 nm"],
        "vacuum_wavelength_range": _WAVELENGTH_RANGE, "core_element_size_range": _CORE_ELEMENT_SIZE_RANGE,
        "settings": dict(_SETTINGS),
    }, headers={"Cache-Control": "no-store"})


@app.get("/api/workspace/capabilities/v4")
def workspace_capabilities_v4():
    return JSONResponse({
        "schema_version": 4, "adapter": "optical-shapes-v6", "simcase_version": __version__,
        "server_instance": _workspace_instance,
        "optical": True, "coupled": False,
        "vacuum_wavelength_range": _WAVELENGTH_RANGE, "core_element_size_range": _CORE_ELEMENT_SIZE_RANGE,
        "domain": _DOMAIN_NM, "max_shapes": 8, "max_polygon_vertices": 12,
        "shape_types": ["rect", "circle", "polygon"],
        "materials": _V4_MATERIALS,
        "settings": dict(_SETTINGS),
    }, headers={"Cache-Control": "no-store"})


@app.get("/api/workspace/capabilities/v5")
def workspace_capabilities_v5():
    caps = json.loads(workspace_capabilities_v4().body)
    caps.update(schema_version=5, adapter="optical-shapes-v7", materials={
        **_V4_MATERIALS,
        "Sapphire (ordinary)": "physmat:Al2O3", "Lithium niobate (ordinary)": "physmat:LiNbO3",
        "Indium phosphide": "physmat:InP", "Gallium arsenide": "physmat:GaAs",
        "Calcium fluoride": "physmat:CaF2", "Magnesium fluoride (ordinary)": "physmat:MgF2"})
    return JSONResponse(caps, headers={"Cache-Control": "no-store"})


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


#: physmat's own wavelength unit (its ranges and index functions take micrometres)
_PHYSMAT_UM = 1e-6


def _metres(um: float) -> float | None:
    """A physmat micrometre bound in metres (None for an open bound)."""
    return None if um == float("inf") else um * _PHYSMAT_UM


@app.get("/api/materials")
def list_materials():
    """The library under the names a format 0.3 document writes ("physmat:Si"); no aliases."""
    out = []
    for n in physmat.names():
        m = physmat.get(n)
        lo, hi = m.range_um
        out.append({"name": "physmat:" + n,
                    "valid": {"vacuum_wavelength": {"unit": "m", "values": [_metres(lo), _metres(hi)]}},
                    "source": m.source.split(";")[0], "properties": sorted(m.properties)})
    return {"materials": out}


@app.post("/api/materials/preview")
def material_preview(body: MaterialPreview):
    """n and k (n + i k, k >= 0 for loss under exp(-i omega t)) over a vacuum wavelength interval in m."""
    if not body.name.startswith("physmat:"):
        raise HTTPException(404, f'{body.name!r}: a library material is written "physmat:<Name>"')
    try:
        m = physmat.get(body.name.removeprefix("physmat:"))
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    lo, hi = (v * _PHYSMAT_UM for v in m.range_um)
    a, b = max(body.vacuum_wavelength_minimum, lo), min(body.vacuum_wavelength_maximum, hi)
    if not a < b:
        raise HTTPException(400, f"material {body.name} has no data in [{body.vacuum_wavelength_minimum}, "
                                 f"{body.vacuum_wavelength_maximum}] m")
    wl = np.linspace(a, b, body.point_count)
    idx = m.index(wl / _PHYSMAT_UM)
    return {"name": body.name, "vacuum_wavelength": {"unit": "m", "values": wl.tolist()},
            "refractive_index": {"n": idx.real.tolist(), "k": idx.imag.tolist()}, "source": m.source}


def _headless_thermal_type(doc: Document):
    return next((p.get("type") for p in doc["physics"].values()
                 if p.get("type") in ("thermal.steady2d", "thermal.transient2d",
                                    "electric.steady2d", "joule.steady2d", "joule.temperature2d",
                                    "mechanics.elasticity2d", "mechanics.thermoelastic2d")), None)


def _require_studio_physics(doc: Document):
    if physics_type := _headless_thermal_type(doc):
        raise HTTPException(400, f'{physics_type} is headless Python/CLI only; Studio does not support its input or results')
    if any(p.get("type") == "em.cavity3d" for p in doc["physics"].values()):
        raise HTTPException(400, "em.cavity3d is available through Python and the CLI; Studio supports 2D only")


@app.post("/api/validate")
def validate(body: DocBody, request: Request = None):
    if request is not None:
        _check_workspace_instance(request)
    try:
        doc = Document.from_dict(body.doc)
        if physics_type := _headless_thermal_type(doc):
            return {'ok': False, 'error': f'Studio unsupported: {physics_type} is headless Python/CLI only'}
    except DocumentError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "summary": doc.summary(), "doc": doc.data, "notes": doc.notes,
            "diagnostics": [d.as_dict() for d in doc.diagnostics]}


@app.get("/api/units")
def units():
    """The declarable units, so the page never carries a second copy of the table."""
    return unit_vocabulary()


@app.post("/api/mesh")
def mesh_preview(body: DocBody, request: Request = None):
    if request is not None:
        _check_workspace_instance(request)
    try:
        doc = Document.from_dict(body.doc)
        _require_studio_physics(doc)
        model = build_mesh(doc)
    except (DocumentError, ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
    tm, region_materials = model.tri, model.region_materials
    return {"node_coordinates": tm.nodes.tolist(), "field_units": {"node_coordinates": "m"},
            "display": _display(doc), "triangles": tm.triangles.tolist(), "regions": tm.regions.tolist(),
            "region_names": tm.region_names, "region_materials": region_materials,
            "stats": {"nodes": tm.num_nodes, "triangles": tm.num_triangles, "min_angle": round(tm.min_angle(), 2),
                      "quality_mean": round(float(tm.quality().mean()), 3)},
            "boundary_edges": {k: v.tolist() for k, v in tm.boundary_edges.items()},
            "diagnostics": [d.as_dict() for d in doc.diagnostics]}


def _display(doc: Document) -> dict:
    """The length unit of the document's shape numbers (the component's length_unit) and its size in
    metres, so a page draws SI coordinates over the document's own numbers (display only)."""
    from physmat import units as registry
    geometry = doc.si["geometry"]
    block = geometry if "version" not in geometry else next(iter(geometry["components"].values()))
    unit = block["length_unit"]
    return {"length_unit": unit, "metres_per_length_unit": float(registry.convert(f"1 {unit}", "length").exact)}


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
        if isinstance(res, SubspaceSweepResult):
            with _jobs_lock:
                _jobs[job_id].update(status="done", result=_subspace_payload(res, res.field_representation))
            return
        summary = res.summary()
        payload = {**_common_payload(res, summary),
                   # the section 5.3.4 series of summary.json: a tagged array, or {"re", "im"} when complex
                   "effective_index": summary["effective_index"], "group_index": summary.get("group_index"),
                   "propagation_loss": summary.get("propagation_loss"),
                   # scalar fields per point, modes first: real parts, and imaginary parts when complex
                   "unnormalized_mode_field": [{"real": f.T.real.tolist(),
                                                "imag": f.T.imag.tolist() if np.iscomplexobj(f) else None}
                                               for f in res.mode_fields]}
        if res.vector_fields is not None:
            payload["vector_fields"] = [f.to_dict() for f in res.vector_fields]
        with _jobs_lock:
            _jobs[job_id].update(status="done", result=payload)
    except Exception as exc:  # report anything to the browser; the traceback stays in the server log
        _log.warning("optical job %s failed", job_id, exc_info=True)
        with _jobs_lock:
            _jobs[job_id].update(status="error", error=f"{type(exc).__name__}: {exc}")
            diagnostic = getattr(exc, "diagnostics", getattr(exc.__cause__, "diagnostics", None))
            if diagnostic is not None:
                _jobs[job_id]["open_boundary"] = diagnostic


def _common_payload(res, summary: dict) -> dict:
    """The mesh (node coordinates in m), the study and the summary of an optical result."""
    return {"node_coordinates": res.node_coordinates.tolist(), "field_units": {"node_coordinates": "m"},
            "display": _display(res.doc), "triangles": res.triangles.tolist(), "regions": res.regions.tolist(),
            "region_names": res.region_names, "parameter": res.parameter,
            "vacuum_wavelength": summary["vacuum_wavelength"],
            "study_values": None if res.study_values is None else summary["study"]["values"],
            "timings": res.timings, "summary": summary}


def _subspace_payload(res, representation: str) -> dict:
    """Versioned cluster payload; per-mode keys stay empty so mode views cannot misread it."""
    summary = res.summary()
    return {
        **_common_payload(res, summary),
        "effective_index": None, "group_index": None, "unnormalized_mode_field": [],
        "subspace": {
            "field_representation": representation,
            "clusters": summary["clusters"],
            "effective_index": res.effective_index.tolist(),
            "mean_effective_index": res.mean_effective_index.tolist(),
            "mean_group_index": res.mean_group_index.tolist(),
            "density": [[res.subspace_density(i, cid).tolist() for cid in res.cluster_ids]
                        for i in range(len(res.vacuum_wavelength))],
            "density_label": "normalized subspace field density",
        },
    }


@app.post("/api/run")
def start_run(body: DocBody, request: Request = None):
    if request is not None:
        _check_workspace_instance(request)
    try:
        doc = Document.from_dict(body.doc)
    except DocumentError as exc:
        raise HTTPException(400, str(exc))
    _require_studio_physics(doc)
    job_id = uuid.uuid4().hex[:8]
    with _jobs_lock:
        if sum(job["status"] == "running" for job in _jobs.values()) >= _MAX_RUNNING_JOBS:
            raise HTTPException(429, f"Studio is already running {_MAX_RUNNING_JOBS} optical jobs; wait for one to finish.")
        finished = [key for key, job in _jobs.items() if job["status"] != "running"]
        for key in finished[:-_MAX_FINISHED_JOBS]:
            del _jobs[key]  # dicts keep insertion order: the oldest finished jobs go first
        _jobs[job_id] = {"status": "running", "log": [], "result": None, "error": None}
    threading.Thread(target=_run_job, args=(job_id, doc), daemon=True).start()
    return {"job": job_id}



def _thermal_error(exc):
    return JSONResponse(exc.body(), status_code=exc.status, headers={"Cache-Control": "no-store"})


@app.get("/api/capabilities")
def studio_capabilities():
    caps = thermal.capabilities(_thermal_jobs.limits)
    caps[transient.KIND] = transient.capabilities(_thermal_jobs.limits)
    for kind in (thermal.KIND, transient.KIND):
        caps[kind]["regions"] = regions.capability(kind, _thermal_jobs.limits, _region_limits)
    return caps


@app.post("/api/thermal/validate")
async def validate_thermal(body: Request):
    spec = None
    permit = None
    jobs = _thermal_jobs
    try:
        permit = jobs.ingress.acquire()
        spec = await thermal.read_request(body, jobs.limits, for_run=False,
                                          region=regions.Route(thermal.KIND, jobs.limits, _region_limits))
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
        rlimits = _region_limits
        spec = await thermal.read_request(body, jobs.limits, for_run=True,
                                          region=regions.Route(thermal.KIND, jobs.limits, rlimits))
        if isinstance(spec, regions.RegionInput):
            lease = jobs.reserve()
            token = uuid.uuid4().hex
            identity = jobs.attach(lease, "thermal-"+token, "result-"+token, spec)
            _start_thermal_thread(_run_region_job, (jobs, lease, spec, rlimits))
            return JSONResponse(identity, headers={"Cache-Control": "no-store"})
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


def _check_workspace_instance(request: Request):
    expected = request.query_params.get("workspace_instance")
    if expected is not None and expected != _workspace_instance:
        raise HTTPException(409, "The Studio server restarted or changed; reconnect before submitting new work. Previous jobs cannot be resumed on this server.")


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
    _check_workspace_instance(request)
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
    _check_workspace_instance(request)
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
        spec = await transient.read_request(body, jobs.limits, for_run=False,
                                            region=regions.Route(transient.KIND, jobs.limits, _region_limits))
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


def _run_region_job(jobs, lease, spec, rlimits):
    """A steady or transient region document: the run is bounded by the job's node and
    triangle caps and the loop-vertex limit, so an over-fine mesh fails before the solve."""
    stage = "solver_failed"
    try:
        try:
            result = run(spec.run_doc, verbose=False, max_nodes=spec.plan.n_cap,
                         max_triangles=spec.plan.m_cap, max_input_vertices=rlimits.max_input_vertices)
        except Exception as exc:
            mapped = regions.job_error(exc, spec.plan)
            if mapped is None:
                raise
            raise mapped from exc
        stage = "invalid_result"
        if spec.kind == thermal.KIND:
            encoded = regions.capture_steady(result, jobs.identity(lease), jobs.limits, rlimits, spec)
            stage = "publication_failed"
            jobs.complete(lease, encoded, result.log)
        else:
            manifest, arrays, scale = regions.capture_transient(result, jobs.identity(lease), jobs.limits,
                                                                rlimits, spec)
            stage = "publication_failed"
            jobs.complete_transient(lease, manifest, arrays, result.log, scale, pair=regions.TRANSIENT_PAIR)
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
        rlimits = _region_limits
        spec = await transient.read_request(body, jobs.limits, for_run=True,
                                            region=regions.Route(transient.KIND, jobs.limits, rlimits))
        if isinstance(spec, regions.RegionInput):
            lease = jobs.reserve(transient.reservation(jobs.limits))
            token = uuid.uuid4().hex
            identity = jobs.attach(lease, "thermal-transient-"+token, "result-"+token, spec)
            _start_thermal_thread(_run_region_job, (jobs, lease, spec, rlimits))
            return JSONResponse(identity, headers={"Cache-Control": "no-store"})
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


geometry_api.install(app)    # the experimental geometry lab, /geometry-lab
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _arguments(argv, *, product):
    import argparse
    ap = argparse.ArgumentParser(prog="openphysics" if product else "simcase-studio",
                                 description="OpenPhysics Studio: the model workspace in your browser" if product
                                 else "browser UI for simcase models")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    if product:
        ap.add_argument("--classic", action="store_true", help="open the classic optical and thermal editor")
    else:
        ap.add_argument("--workspace", action="store_true",
                        help="open the experimental model workspace instead of the classic editor")
    args = ap.parse_args(argv)
    args.path = ("/" if args.classic else "/workspace") if product else ("/workspace" if args.workspace else "/")
    return args


def product_main(argv=None):
    """The ``openphysics`` command: Studio opened on its model workspace."""
    main(argv, product=True)


def main(argv=None, *, product=False):
    import webbrowser

    import uvicorn

    args = _arguments(argv, product=product)
    host = args.host.strip("[]")
    if not security.is_loopback(host):
        print(f"warning: --host {args.host} makes Studio reachable from other machines. Studio has no "
              "accounts or encryption; use it only on a network you trust.", file=sys.stderr)
    if host not in ("0.0.0.0", "::"):
        _extra_hosts.add(host.lower())
    # A wildcard bind is opened through loopback of the same family (``::`` may be IPv6-only).
    url_host = {"0.0.0.0": "127.0.0.1", "::": "[::1]"}.get(host, f"[{host}]" if ":" in host else host)
    url = f"http://{url_host}:{args.port}{args.path}"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"OpenPhysics Studio at {url} (stop with Ctrl+C)" if product else f"simcase studio at {url}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
