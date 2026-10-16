# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Measure an exact Linux Studio server through public API and real loopback HTTP.

Run once in the existing CI environment. Each size gets a fresh owned process.
This is instrumented resource evidence, not a timing gate, browser test or proof
of peak capacity. Tracemalloc and observation overhead are included.
"""
import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request


def model(n):
    return {
        "openphysics": "0.2", "name": "Studio resource observation",
        "units": {"length": "m", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
        "materials": {},
        "physics": {"heat1": {
            "type": "thermal.steady2d", "conductivity_w_mk": 2,
            "heat_source_w_m3": 0, "dirichlet_temperature_k": {"left": 300},
            "outward_flux_w_m2": {"right": 2},
            "convection": {"right": {"h_w_m2k": 4, "ambient_temperature_k": 290}},
        }},
        "mesh": {"subdivisions": [n, n]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False},
    }


def worker(conn, source_root):
    import gc
    import importlib.metadata
    import resource
    import socket
    import threading
    import traceback
    import tracemalloc

    active = False
    observations = {
        name: {"calls": 0, "errors": 0, "wall_s": 0.0, "max_output_bytes": 0}
        for name in ("capture_result", "encode_json")
    }
    hook_events = []

    def observe(name, function):
        def wrapped(*args, **kwargs):
            if not active:
                return function(*args, **kwargs)
            started, before = time.perf_counter(), snapshot()
            output = None
            failed = False
            try:
                output = function(*args, **kwargs)
                return output
            except BaseException:
                failed = True
                raise
            finally:
                elapsed = time.perf_counter() - started
                entry = observations[name]
                entry["calls"] += 1
                entry["errors"] += int(failed)
                entry["wall_s"] += elapsed
                size = len(output) if isinstance(output, bytes) else None
                if size is not None:
                    entry["max_output_bytes"] = max(entry["max_output_bytes"], size)
                if len(hook_events) < 64:
                    value = args[0] if args and isinstance(args[0], dict) else {}
                    hook_events.append({
                        "hook": name, "elapsed_s": elapsed, "failed": failed,
                        "output_bytes": size, "before": before, "after": snapshot(),
                        "payload_format": value.get("payload_format"),
                        "status": value.get("status"),
                    })
        return wrapped

    def snapshot():
        current = None
        try:
            current = int(Path("/proc/self/statm").read_text(
                encoding="ascii").split()[1]) * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError):
            pass
        live, peak = tracemalloc.get_traced_memory()
        return {"rss_current_bytes": current,
                "process_highwater_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
                "traced_live_bytes": live, "traced_phase_peak_bytes": peak}

    server_instance = thread = None
    try:
        import numpy as np
        import uvicorn
        from simcase import Document, run
        from simcase.studio import server

        thermal = server.thermal
        thermal.capture_result = observe("capture_result", thermal.capture_result)
        thermal.encode_json = observe("encode_json", thermal.encode_json)

        source_root = Path(source_root).resolve()
        origins = {}
        for name, module in list(sys.modules.items()):
            if name == "simcase" or name.startswith(("simcase.", "galerkin.", "meshine.", "physmat.", "gmshio.")):
                filename = getattr(module, "__file__", None)
                if filename and filename.endswith(".py"):
                    path = Path(filename).resolve()
                    if not path.is_relative_to(source_root / "packages"):
                        raise RuntimeError("server import outside exact source checkout: " + name)
                    origins[name] = {"origin": str(path),
                                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        server_instance = uvicorn.Server(uvicorn.Config(
            server.app, log_level="error", access_log=False, lifespan="on"))
        thread = threading.Thread(target=server_instance.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 30
        while not server_instance.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("real ASGI server did not start")
            time.sleep(.01)
        tracemalloc.start(1)
        conn.send({"ok": True, "port": port, "pid": os.getpid(), "origins": origins,
                   "baseline": snapshot(), "python": sys.version, "platform": platform.platform(),
                   "versions": {name: importlib.metadata.version(name)
                                for name in ("numpy", "scipy", "shapely", "matplotlib", "fastapi", "uvicorn", "httpx")}})
        phase_start = None
        while True:
            command = conn.recv()
            kind = command["kind"]
            if kind == "begin":
                gc.collect()
                tracemalloc.reset_peak()
                for entry in observations.values():
                    entry.update(calls=0, errors=0, wall_s=0.0, max_output_bytes=0)
                hook_events.clear()
                phase_start = (time.perf_counter(), snapshot())
                active = True
                conn.send({"ok": True})
            elif kind == "end":
                active = False
                conn.send({"ok": True, "phase": command["phase"],
                           "elapsed_s": time.perf_counter() - phase_start[0],
                           "before": phase_start[1], "after": snapshot(),
                           "adapter_hook_observations": {key: dict(value) for key, value in observations.items()},
                           "adapter_hook_events": list(hook_events)})
            elif kind == "public_api":
                doc = Document.from_dict(command["doc"])
                started = time.perf_counter()
                result = run(doc, verbose=False)
                elapsed = time.perf_counter() - started
                summary = result.summary()
                arrays = {}
                for key in summary["field_shapes"]:
                    prop = {"nodes_m": "mesh_nodes_m", "triangles": "mesh_triangles"}.get(key, key)
                    arrays[key] = getattr(result, prop)
                response = {"ok": True, "public_run_s": elapsed,
                            "nodes": len(arrays["nodes_m"]), "cells": len(arrays["triangles"]),
                            "raw_array_bytes": sum(np.asarray(a).nbytes for a in arrays.values()),
                            "result_format": result.result_format, "field_layout": result.field_layout}
                del arrays, result, doc, summary
                gc.collect()
                conn.send(response)
            elif kind == "stop":
                active = False
                started = time.perf_counter()
                server_instance.should_exit = True
                thread.join(10)
                gc.collect()
                conn.send({"ok": not thread.is_alive(), "shutdown_s": time.perf_counter() - started,
                           "after": snapshot(),
                           "scope": "owned ASGI shutdown and GC; not a TTL/eviction measurement"})
                break
            else:
                raise RuntimeError("unknown observer command")
    except BaseException as exc:
        conn.send({"ok": False, "error_type": type(exc).__name__, "error": str(exc),
                   "traceback": traceback.format_exc(limit=8)})
    finally:
        if server_instance is not None:
            server_instance.should_exit = True
        if thread is not None:
            thread.join(2)
        conn.close()


def receive(conn, process, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if conn.poll(min(10, max(0, deadline-time.monotonic()))):
            reply = conn.recv()
            if not reply.get("ok"):
                raise RuntimeError("server observer failure: " + json.dumps(reply))
            return reply
        print("Studio observation still active; owned pid=" + str(process.pid), flush=True)
        if not process.is_alive():
            raise RuntimeError("owned server process exited without a receipt")
    raise TimeoutError("owned server observation deadline exceeded")


def http(port, method, path, data=None, expected=(200, 202)):
    encoded = None if data is None else json.dumps(data, allow_nan=False).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:" + str(port) + path, data=encoded, method=method,
        headers={"content-type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=180) as reply:
            status, body = reply.status, reply.read()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read()
    if status not in expected:
        raise RuntimeError("observed HTTP refusal/error " + str(status) + ": " +
                           body[:1024].decode("utf-8", errors="replace"))
    return body, {"status": status, "elapsed_s": time.perf_counter()-started,
                  "request_utf8_bytes": len(encoded or b""), "response_bytes": len(body),
                  "response_sha256": hashlib.sha256(body).hexdigest()}


def one_case(n, source_root):
    context = mp.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=worker, args=(child, str(source_root)))
    report = {"n": n, "expected_nodes": (n+1)**2, "expected_cells": 2*n*n, "phases": []}
    process.start()
    child.close()

    def rpc(kind, **kwargs):
        parent.send({"kind": kind, **kwargs})
        return receive(parent, process)

    try:
        report["server"] = receive(parent, process, 45)
        port = report["server"]["port"]
        body, report["capability_http"] = http(port, "GET", "/api/capabilities")
        report["capabilities"] = json.loads(body)
        capability = report["capabilities"].get("thermal.steady2d", {})
        if capability.get("run_enabled") is not True:
            raise RuntimeError("actual server does not explicitly advertise run_enabled")
        doc = model(n)
        body, report["admission_validation_http"] = http(
            port, "POST", "/api/thermal/validate",
            {"doc": doc, "client_revision": 1, "request_seq": 0})
        if json.loads(body).get("ok") is not True:
            raise RuntimeError("actual server refused the fixed case before public API measurement")
        rpc("begin")
        report["public_api"] = rpc("public_api", doc=doc)
        report["phases"].append(rpc("end", phase="real_public_api_with_summary_capture_and_release"))
        rpc("begin")
        envelope = {"doc": doc, "client_revision": 1, "request_seq": 1}
        body, report["validation_http"] = http(port, "POST", "/api/thermal/validate", envelope)
        if json.loads(body).get("ok") is not True:
            raise RuntimeError("actual server validation refused the fixed observation case")
        body, report["submit_http"] = http(port, "POST", "/api/thermal/run", envelope)
        accepted = json.loads(body)
        job = accepted["job"]
        deadline = time.monotonic() + 180
        while True:
            body, _ = http(port, "GET", "/api/jobs/" + job)
            state = json.loads(body)
            if state["status"] in ("done", "error"):
                break
            if time.monotonic() > deadline:
                raise TimeoutError("actual thermal job deadline exceeded")
            time.sleep(.05)
        for key in ("kind", "job", "result_id", "client_revision", "request_seq"):
            if state.get(key) != accepted.get(key):
                raise RuntimeError("actual status identity differs from accepted job")
        report["terminal_state"] = state
        if state["status"] != "done" or state.get("has_result") is not True:
            raise RuntimeError("actual thermal job did not publish a complete result")
        body, report["first_result_http"] = http(port, "GET", "/api/jobs/" + job + "/result")
        payload = json.loads(body)
        if payload.get("kind") != "thermal.steady2d":
            raise RuntimeError("actual server returned a nonthermal payload")
        for key in ("kind", "job", "result_id", "client_revision", "request_seq"):
            if payload.get(key) != accepted.get(key):
                raise RuntimeError("actual result identity differs from accepted job")
        scale = payload.get("display_length_in_m")
        if ("coordinates" in payload or isinstance(scale, bool)
                or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0):
            raise RuntimeError("wire differs from the reviewed top-level display scale contract")
        report["display_length_in_m"] = scale
        arrays = payload.get("arrays", {})
        if (len(arrays.get("nodes_m", ())) != (n+1)**2
                or len(arrays.get("triangles", ())) != 2*n*n):
            raise RuntimeError("actual response silently changed the requested mesh size")
        report["wire"] = {key: payload.get(key) for key in
                          ("payload_format", "kind", "result_format", "field_layout")}
        report["phases"].append(rpc("end", phase="real_http_validation_job_capture_encoding_and_first_read"))
        del arrays, payload, body
        rpc("begin")
        reads = []
        for _ in range(10):
            body, entry = http(port, "GET", "/api/jobs/" + job + "/result")
            reads.append(entry)
            del body
        report["reads"] = reads
        report["phases"].append(rpc("end", phase="ten_real_http_result_reads"))
        if any(entry["response_sha256"] != report["first_result_http"]["response_sha256"]
               for entry in reads):
            raise RuntimeError("repeated HTTP reads changed the encoded result")
        # Exercise actual admission/reclamation without changing clocks or global jobs.
        rpc("begin")
        report["subsequent_jobs"] = []
        for sequence in (2, 3):
            body, admission = http(port, "POST", "/api/thermal/run",
                                   {"doc": doc, "client_revision": 1, "request_seq": sequence})
            identity = json.loads(body)
            deadline = time.monotonic() + 180
            while True:
                body, _ = http(port, "GET", "/api/jobs/" + identity["job"])
                state = json.loads(body)
                if state["status"] in ("done", "error"):
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("subsequent real job did not terminate")
                time.sleep(.05)
            if state["status"] != "done" or state.get("has_result") is not True:
                raise RuntimeError("subsequent real job failed")
            body, response = http(port, "GET", "/api/jobs/" + identity["job"] + "/result")
            report["subsequent_jobs"].append(
                {"identity": identity, "admission": admission, "result": response})
            del body
        body, eviction = http(port, "GET", "/api/jobs/" + job + "/result", expected=(200, 404))
        report["oldest_terminal_read"] = eviction
        report["phases"].append(rpc("end", phase="two_more_real_jobs_and_terminal_reclamation"))
        if capability.get("limits", {}).get("terminal_jobs") == 2 and eviction["status"] != 404:
            raise RuntimeError("oldest terminal was not reclaimed under the advertised two-slot policy")
        report["cleanup"] = rpc("stop")
        report["ok"] = True
    except Exception as exc:
        report["ok"] = False
        report["error_type"], report["error"] = type(exc).__name__, str(exc)
    finally:
        process.join(3)
        if process.is_alive():
            # Only this newly spawned, owned child; preserve the timeout/failure.
            report["forced_owned_child_stop"] = True
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(3)
                report["owned_child_kill_required"] = True
            report["ok"] = False
        report["process_exit"] = process.exitcode
        if process.exitcode != 0:
            report["ok"] = False
        parent.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("this resource observation command targets Linux CI only")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        os.environ[name] = "1"
    root = args.source_root.resolve()
    actual = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                            check=True, text=True, encoding="utf-8", capture_output=True).stdout.strip()
    if actual != args.expected_commit:
        parser.error("exact checkout commit differs from the requested observation")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "scope": "actual public API and real loopback ASGI HTTP in fresh server processes",
        "source_commit": actual, "instrumented": True, "cases": [],
        "thread_environment": {key: value for key, value in os.environ.items()
                               if key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                                          "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")},
        "limitations": [
            "shared CI host; no dedicated performance baseline or speed guarantee",
            "tracemalloc excludes some native memory; ru_maxrss is cumulative per child",
            "capture_result includes encode_json; nested hook times overlap and must not be summed",
            "hook observation overhead is included; per-call RSS high-water is still cumulative",
            "server metrics exclude the separate client process",
            "terminal reclamation is actual HTTP evidence, not TTL expiry; shutdown/GC is not a leak proof",
            "fixed workload observations are not maximum capacity certification",
            "independent physics, browser and platform acceptance remain separate",
        ],
    }
    for n in (2, 32, 100):
        print("Observing actual Studio server n=" + str(n), flush=True)
        item = one_case(n, root)
        report["cases"].append(item)
        (args.output / ("n" + str(n) + ".json")).write_text(
            json.dumps(item, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if not item["ok"]:
            break
    report["ok"] = len(report["cases"]) == 3 and all(x["ok"] for x in report["cases"])
    (args.output / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"resource_observation_ok": report["ok"], "source": actual}), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
